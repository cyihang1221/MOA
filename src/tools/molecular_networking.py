# 网络分析
# 涉及到的工具："GNPS", "FBMN", "MS2LDA", "MolNetEnhancer"

# ═══════════════════════════════════════════════════════════════════════════════
# GNPS 经典分子网络工具 — 基于 MS/MS 谱图余弦相似度的分子网络构建
# ═══════════════════════════════════════════════════════════════════════════════
# 核心算法：全对全谱图余弦相似度匹配 → 阈值过滤 → NetworkX 图构建 → 导出 GraphML/CSV
# 参考：Wang et al. Nature Biotechnology, 2016, 34(8), 828–837
#       https://doi.org/10.1038/nbt.3597
#
# 网络分析在代谢组学流程中的位置与作用:
#
#   分析管道：预处理 → 统计 → 差异代谢物 → 谱库注释 → [网络分析] → 生物学解释
#
#   GNPS 分子网络的核心作用：
#   1. 打破"逐化合物"的孤立视角 — 通过谱图相似度将代谢物连接成"分子家族"
#   2. 注释传播 — 已知化合物的注释可以传播给同一家族中未被注释的邻居
#   3. 发现同系物和代谢通路 — 同一分子家族中的节点往往具有结构相关性
#   4. 为下游 MolNetEnhancer 等工具提供网络拓扑基础

import os
import json
import time
import warnings
import numpy as np
import pandas as pd
import networkx as nx
from typing import List, Dict, Tuple, Optional


# ============================= MGF 解析器 =============================

def _parse_mgf(mgf_path: str) -> List[Dict]:
    """
    解析 MGF 文件，返回谱图列表。

    MGF 格式（与 xcms data_preprocessing 输出一致）：
        BEGIN IONS
        TITLE=feature_id
        PEPMASS=precursor_mz
        RTINSECONDS=retention_time_seconds
        CHARGE=1+
        mz1 intensity1
        mz2 intensity2
        ...
        END IONS

    Parameters
    ----------
    mgf_path : str
        MGF 文件路径。

    Returns
    -------
    list of dict
        每个谱图包含: feature_id, precursor_mz, rt, charge, mz_array, intensity_array
    """
    spectra = []

    with open(mgf_path, 'r') as f:
        inside_block = False
        current = {}

        for line in f:
            line_strip = line.strip()

            if line_strip == "BEGIN IONS":
                inside_block = True
                current = {
                    "feature_id": None,
                    "precursor_mz": None,
                    "rt": None,
                    "charge": "1+",
                    "peaks": []  # list of (mz, intensity) tuples
                }

            elif line_strip == "END IONS" and inside_block:
                inside_block = False
                if current["peaks"] and current["precursor_mz"] is not None:
                    # 转换为 numpy 数组加速后续计算
                    peaks_arr = np.array(current["peaks"], dtype=np.float64)
                    mz_mask = peaks_arr[:, 0] > 0
                    current["mz_array"] = peaks_arr[mz_mask, 0]
                    current["intensity_array"] = peaks_arr[mz_mask, 1]
                    # 归一化强度到 [0, 1]，等同于 sqrt 归一化（GNPS 标准）
                    norm = np.linalg.norm(current["intensity_array"])
                    if norm > 0:
                        current["intensity_array"] = current["intensity_array"] / norm
                    spectra.append(current)

            elif inside_block:
                if line_strip.startswith("TITLE="):
                    current["feature_id"] = line_strip.replace("TITLE=", "").strip()
                elif line_strip.startswith("PEPMASS="):
                    try:
                        current["precursor_mz"] = float(line_strip.replace("PEPMASS=", "").strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                elif line_strip.startswith("RTINSECONDS="):
                    try:
                        current["rt"] = float(line_strip.replace("RTINSECONDS=", "").strip())
                    except ValueError:
                        pass
                elif line_strip.startswith("CHARGE="):
                    current["charge"] = line_strip.replace("CHARGE=", "").strip()
                elif line_strip and not line_strip.startswith(("TITLE", "PEPMASS", "RTINSECONDS", "CHARGE")):
                    # 峰数据行: mz intensity
                    parts = line_strip.split()
                    if len(parts) >= 2:
                        try:
                            mz = float(parts[0])
                            intensity = float(parts[1])
                            if mz > 0 and intensity > 0:
                                current["peaks"].append((mz, intensity))
                        except ValueError:
                            continue

    return spectra


# ============================= 余弦相似度计算 =============================

def _compute_cosine_greedy(
    mz1: np.ndarray,
    int1: np.ndarray,
    mz2: np.ndarray,
    int2: np.ndarray,
    fragment_tol: float,
) -> Tuple[float, int]:
    """
    计算两个谱图之间的 greedy 余弦相似度。

    对 query 中每个峰，在 reference 中找到 fragment_tol 范围内强度最大的匹配峰，
    然后计算匹配峰的余弦相似度。

    这是 GNPS 实践中使用的 greedy 匹配方法（而非 Hungarian），
    因为它更保守、假阳性更少。

    Parameters
    ----------
    mz1, int1 : np.ndarray
        谱图1的 m/z 和（归一化后的）强度数组。
    mz2, int2 : np.ndarray
        谱图2的 m/z 和（归一化后的）强度数组。
    fragment_tol : float
        碎片离子匹配的 m/z 容差（Da）。

    Returns
    -------
    tuple of (cosine_score, matched_peaks)
        cosine_score: float, 范围 [0, 1]
        matched_peaks: int, 匹配到的峰数量
    """
    matched_int1 = []
    matched_int2 = []

    # 对谱图1的每个峰，在谱图2中找最佳匹配
    used = np.zeros(len(mz2), dtype=bool)

    for i in range(len(mz1)):
        # 找谱图2中 m/z 容差范围内、未被使用的峰
        mass_diff = np.abs(mz2 - mz1[i])
        candidates = np.where((mass_diff <= fragment_tol) & (~used))[0]

        if len(candidates) > 0:
            # 选择强度最大的作为匹配
            best_idx = candidates[np.argmax(int2[candidates])]
            matched_int1.append(int1[i])
            matched_int2.append(int2[best_idx])
            used[best_idx] = True

    if len(matched_int1) == 0:
        return 0.0, 0

    v1 = np.array(matched_int1)
    v2 = np.array(matched_int2)

    # 余弦相似度
    dot_product = np.dot(v1, v2)
    norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)

    if norm_product == 0:
        return 0.0, 0

    cosine = dot_product / norm_product
    return float(np.clip(cosine, 0.0, 1.0)), len(matched_int1)


def _compute_all_vs_all_similarity(
    spectra: List[Dict],
    fragment_tol: float,
    precursor_ppm: float,
) -> List[Dict]:
    """
    全对全谱图余弦相似度计算。

    对每对谱图 (i, j) (i < j)：
    1. 检查前体离子 m/z 是否在 precursor_ppm 容差范围内
    2. 计算 greedy 余弦相似度
    3. 记录匹配峰数

    Parameters
    ----------
    spectra : list of dict
        谱图列表（来自 _parse_mgf）。
    fragment_tol : float
        碎片离子匹配容差（Da）。
    precursor_ppm : float
        前体离子容差（ppm），仅记录在边属性中做参考。

    Returns
    -------
    list of dict
        每条记录: source, target, cosine, matched_peaks, precursor_delta_ppm
    """
    n = len(spectra)
    edges = []
    total_pairs = n * (n - 1) // 2
    report_interval = max(1, total_pairs // 10)

    print(f"  开始全对全比较: {n} 个谱图, 共 {total_pairs} 对")
    pair_count = 0

    for i in range(n):
        for j in range(i + 1, n):
            pair_count += 1

            if pair_count % report_interval == 0:
                print(f"    进度: {pair_count}/{total_pairs} 对 "
                      f"({100 * pair_count / total_pairs:.1f}%), "
                      f"已找到 {len(edges)} 条边")

            cosine, matched_peaks = _compute_cosine_greedy(
                mz1=spectra[i]["mz_array"],
                int1=spectra[i]["intensity_array"],
                mz2=spectra[j]["mz_array"],
                int2=spectra[j]["intensity_array"],
                fragment_tol=fragment_tol,
            )

            # 计算前体离子差值 (ppm)
            pmz1 = spectra[i]["precursor_mz"]
            pmz2 = spectra[j]["precursor_mz"]
            if pmz1 and pmz2 and pmz1 > 0:
                delta_ppm = abs(pmz1 - pmz2) / pmz1 * 1e6
            else:
                delta_ppm = 0.0

            edges.append({
                "source": spectra[i]["feature_id"],
                "target": spectra[j]["feature_id"],
                "cosine": round(cosine, 4),
                "matched_peaks": matched_peaks,
                "precursor_delta_ppm": round(delta_ppm, 2),
            })

    print(f"  全对全比较完成, 共生成 {len(edges)} 条候选边")
    return edges


# ============================= GNPS 分子网络主实现 =============================

# KEYWORD: GNPS
def molecular_networking_gnps_impl(
    input_mgf: str,
    output_dir: str,
    min_cosine: float = 0.7,
    min_matched_peaks: int = 6,
    fragment_tol: float = 0.02,
    top_k: int = 10,
    precursor_ppm: float = 5,
):
    """
    基于 GNPS 经典分子网络方法，对差异代谢物 MS/MS 谱图进行网络分析。

    算法流程:
    1. 解析输入 MGF 文件（来自 data_preprocessing 或 extract_differential_features 的输出）
    2. 全对全 greedy 余弦相似度计算
    3. 按 min_cosine 和 min_matched_peaks 过滤边
    4. 每个节点仅保留 top_k 条最强边（减少图复杂度）
    5. 用 NetworkX 构建分子网络
    6. 检测连通分量 → 分子家族（molecular families）
    7. 导出 GraphML、边表、节点表、网络统计

    方法参考:
        Wang et al. "Sharing and community curation of mass spectrometry data
        with Global Natural Products Social Molecular Networking."
        Nature Biotechnology, 2016, 34(8), 828–837.
        https://doi.org/10.1038/nbt.3597

    Parameters
    ----------
    input_mgf : str
        MS/MS 谱图 MGF 文件路径。通常是 extract_differential_features 输出的
        differential_spectra.mgf。
    output_dir : str
        输出目录，保存网络文件和统计表。
    min_cosine : float, default=0.7
        最小余弦相似度阈值。GNPS 默认 0.7，值越高网络越稀疏但置信度越高。
        典型范围：0.6（探索性）到 0.8（高置信度）。
    min_matched_peaks : int, default=6
        最小匹配碎片峰数。GNPS 默认 6，用于排除仅有少量共有碎片的偶然匹配。
        对小分子（< 200 Da）可降低到 4。
    fragment_tol : float, default=0.02
        碎片离子匹配容差（Da）。对于 Orbitrap 高分辨数据，0.02 Da 是合理默认值。
        对于 TOF 低分辨数据，可放宽到 0.05 Da。
    top_k : int, default=10
        每个节点保留的最强边数。避免 hub 节点产生过多边，使网络可视化更清晰。
        GNPS 默认显示 top 10。
    precursor_ppm : float, default=5
        前体离子容差（ppm）。记录在边属性中，当前版本不用于过滤，
        但输出到边表中以便后续分析。

    Outputs
    -------
    {output_dir}/
    ├── molecular_network.graphml    — 分子网络图（Cytoscape 可直接打开）
    ├── network_edges.csv            — 边表：source, target, cosine, matched_peaks, delta_ppm
    ├── network_nodes.csv            — 节点表：feature_id, precursor_mz, rt, degree, molecular_family
    ├── network_clusters.csv         — 分子家族汇总：family_id, size, avg_cosine
    └── network_summary.txt          — 网络统计摘要

    Notes
    -----
    - 输入 MGF 应来自差异代谢物提取步骤（differential_spectra.mgf），
      而非全量原始 specta.mgf，因为后者谱图数量过多，全对全比较计算量大且网络难以解释。
    - 如果谱图数量 > 500，建议提高 min_cosine（如 0.8）或缩小输入谱图范围以控制计算时间。
    - 分子家族（molecular_family）列可用于后续注释传播和化学分类富集分析。
    """
    import time

    print(f"\n[GNPS Molecular Networking] 开始经典分子网络分析...")
    print(f"  输入 MGF: {input_mgf}")
    print(f"  参数: min_cosine={min_cosine}, min_matched_peaks={min_matched_peaks}, "
          f"fragment_tol={fragment_tol}, top_k={top_k}")

    t_start = time.time()

    # ========== 输入验证 ==========
    if not os.path.isfile(input_mgf):
        raise FileNotFoundError(
            f"输入 MGF 文件未找到: {input_mgf}\n"
            f"请先运行 data_preprocessing_xcms 和 extract_differential_features "
            f"生成 differential_spectra.mgf。"
        )

    os.makedirs(output_dir, exist_ok=True)

    # ========== 1. 解析 MGF ==========
    print(f"\n  [Step 1/5] 解析 MGF 谱图...")
    spectra = _parse_mgf(input_mgf)

    if len(spectra) < 2:
        raise ValueError(
            f"MGF 文件中仅有 {len(spectra)} 个有效谱图，"
            f"至少需要 2 个谱图才能构建网络。"
        )

    print(f"成功解析 {len(spectra)} 个有效谱图")

    # ========== 2. 全对全余弦相似度 ==========
    print(f"\n  [Step 2/5] 全对全余弦相似度计算...")
    all_edges = _compute_all_vs_all_similarity(
        spectra=spectra,
        fragment_tol=fragment_tol,
        precursor_ppm=precursor_ppm,
    )

    # ========== 3. 过滤边 ==========
    print(f"\n  [Step 3/5] 边过滤...")
    print(f"    min_cosine >= {min_cosine}")
    print(f"    min_matched_peaks >= {min_matched_peaks}")

    edges_df = pd.DataFrame(all_edges)
    edges_df_filtered = edges_df[
        (edges_df["cosine"] >= min_cosine) &
        (edges_df["matched_peaks"] >= min_matched_peaks)
    ].copy()

    print(f"    过滤前: {len(edges_df)} 条边")
    print(f"    过滤后: {len(edges_df_filtered)} 条边")

    # Top-K 过滤：每个节点只保留 top_k 条最强边
    if top_k > 0 and len(edges_df_filtered) > 0:
        # 对每个 source 节点，按 cosine 降序，取前 top_k
        edges_df_filtered["rank"] = edges_df_filtered.groupby("source")["cosine"].rank(
            ascending=False, method="first"
        )
        # 也对 target 做对称 top-k
        edges_df_filtered["rank_target"] = edges_df_filtered.groupby("target")["cosine"].rank(
            ascending=False, method="first"
        )
        edges_df_filtered = edges_df_filtered[
            (edges_df_filtered["rank"] <= top_k) |
            (edges_df_filtered["rank_target"] <= top_k)
        ].copy()
        edges_df_filtered.drop(columns=["rank", "rank_target"], inplace=True)

        print(f"    Top-{top_k} 过滤后: {len(edges_df_filtered)} 条边")

    # ========== 4. 构建网络图 ==========
    print(f"\n  [Step 4/5] 构建 NetworkX 分子网络...")

    G = nx.Graph()

    # 添加节点：即使没有边的孤立节点也加入
    for sp in spectra:
        G.add_node(
            sp["feature_id"],
            precursor_mz=round(sp["precursor_mz"], 4) if sp["precursor_mz"] else None,
            rt=round(sp["rt"], 2) if sp["rt"] else None,
            charge=sp.get("charge", "1+"),
            num_peaks=len(sp["mz_array"]),
        )

    # 添加边
    for _, row in edges_df_filtered.iterrows():
        G.add_edge(
            str(row["source"]),
            str(row["target"]),
            cosine=row["cosine"],
            matched_peaks=int(row["matched_peaks"]),
            delta_ppm=row["precursor_delta_ppm"],
        )

    # 计算连通分量 → 分子家族
    connected_components = list(nx.connected_components(G))
    family_map = {}
    for i, comp in enumerate(connected_components):
        family_id = f"MF_{i + 1:04d}"
        for node in comp:
            family_map[node] = family_id

    # 将分子家族信息写入图节点
    for node in G.nodes():
        G.nodes[node]["molecular_family"] = family_map.get(node, "singleton")
        G.nodes[node]["degree"] = G.degree(node)

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    n_families = len(connected_components)
    n_singletons = sum(1 for comp in connected_components if len(comp) == 1)

    print(f"    节点数: {n_nodes}")
    print(f"    边数: {n_edges}")
    print(f"    分子家族数: {n_families}")
    print(f"    孤立节点数: {n_singletons}")

    # ========== 5. 导出结果 ==========
    print(f"\n  [Step 5/5] 导出网络文件...")

    # --- GraphML（Cytoscape 兼容）---
    graphml_path = os.path.join(output_dir, "molecular_network.graphml")
    nx.write_graphml(G, graphml_path)
    print(f"    ✅ GraphML: {graphml_path}")

    # --- 边表 CSV ---
    edges_out = os.path.join(output_dir, "network_edges.csv")
    edges_df_filtered.to_csv(edges_out, index=False)
    print(f"    ✅ 边表: {edges_out}")

    # --- 节点表 CSV ---
    nodes_data = []
    for node, attrs in G.nodes(data=True):
        nodes_data.append({
            "feature_id": node,
            "precursor_mz": attrs.get("precursor_mz"),
            "rt": attrs.get("rt"),
            "charge": attrs.get("charge"),
            "num_peaks": attrs.get("num_peaks"),
            "degree": attrs.get("degree", 0),
            "molecular_family": attrs.get("molecular_family", "singleton"),
        })
    nodes_df = pd.DataFrame(nodes_data)
    nodes_out = os.path.join(output_dir, "network_nodes.csv")
    nodes_df.to_csv(nodes_out, index=False)
    print(f"    ✅ 节点表: {nodes_out}")

    # --- 分子家族汇总 ---
    cluster_rows = []
    for i, comp in enumerate(connected_components):
        # 计算家族内平均余弦相似度
        subgraph = G.subgraph(comp)
        cosine_values = []
        for u, v, d in subgraph.edges(data=True):
            cosine_values.append(d.get("cosine", 0))
        avg_cosine = np.mean(cosine_values) if cosine_values else 0.0

        # 收集家族成员的 m/z 范围
        mz_values = [G.nodes[n].get("precursor_mz", 0) or 0 for n in comp]
        mz_values = [m for m in mz_values if m > 0]

        cluster_rows.append({
            "molecular_family": f"MF_{i + 1:04d}",
            "size": len(comp),
            "members": "|".join(sorted(comp)),
            "avg_cosine": round(avg_cosine, 4),
            "min_mz": round(min(mz_values), 4) if mz_values else None,
            "max_mz": round(max(mz_values), 4) if mz_values else None,
        })

    cluster_df = pd.DataFrame(cluster_rows)
    # 按家族大小降序排列
    if len(cluster_df) > 0:
        cluster_df = cluster_df.sort_values("size", ascending=False).reset_index(drop=True)
    clusters_out = os.path.join(output_dir, "network_clusters.csv")
    cluster_df.to_csv(clusters_out, index=False)
    print(f"    ✅ 分子家族: {clusters_out}")

    # --- 网络统计摘要 ---
    t_elapsed = time.time() - t_start
    summary_lines = [
        "=" * 60,
        "  GNPS Molecular Networking — 网络统计摘要",
        "=" * 60,
        f"  输入文件: {input_mgf}",
        f"  总谱图数: {len(spectra)}",
        f"  节点数: {n_nodes}",
        f"  边数: {n_edges}",
        f"  分子家族数: {n_families}",
        f"  孤立节点数 (singletons): {n_singletons}",
        f"  最大分子家族: {cluster_df.iloc[0]['size'] if len(cluster_df) > 0 else 0} 个节点",
        "",
        f"  参数:",
        f"    min_cosine = {min_cosine}",
        f"    min_matched_peaks = {min_matched_peaks}",
        f"    fragment_tol = {fragment_tol} Da",
        f"    top_k = {top_k}",
        "",
        f"  连通性:",
    ]

    if n_edges > 0:
        degrees = [d for _, d in G.degree()]
        summary_lines.extend([
            f"    平均度: {np.mean(degrees):.2f}",
            f"    最大度: {np.max(degrees)}",
            f"    网络密度: {nx.density(G):.6f}",
            f"    平均聚类系数: {nx.average_clustering(G):.4f}",
        ])
    else:
        summary_lines.append(f"    (无有效边)")

    summary_lines.extend([
        "",
        f"  运行时间: {t_elapsed:.1f} 秒",
        "",
        f"  输出文件:",
        f"    {graphml_path}",
        f"    {edges_out}",
        f"    {nodes_out}",
        f"    {clusters_out}",
        "=" * 60,
    ])

    summary_out = os.path.join(output_dir, "network_summary.txt")
    with open(summary_out, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    # 同时打印到控制台
    for line in summary_lines:
        print(line)

    print(f"\n✅ [GNPS] 分子网络分析完成!")

    # 如果网络为空，给出提示
    if n_edges == 0:
        print(f"\n⚠️  警告: 当前参数下未生成任何边。建议:")
        print(f"    - 降低 min_cosine (当前 {min_cosine}) → 尝试 0.5-0.6")
        print(f"    - 降低 min_matched_peaks (当前 {min_matched_peaks}) → 尝试 3-4")
        print(f"    - 增大 fragment_tol (当前 {fragment_tol}) → 尝试 0.05 Da")

    # --- 生成图表 ---
    generate_network_figures(
        method="gnps",
        output_dir=output_dir,
        G=G,
        edges_df=edges_df_filtered,
        title_prefix="GNPS",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FBMN — 特征基分子网络 (Feature-Based Molecular Networking)
# ═══════════════════════════════════════════════════════════════════════════════
# 参考: Nothias et al. Nature Methods, 2020, 17(9), 905–908
#       https://doi.org/10.1038/s41592-020-0933-6
#
# FBMN 在经典 GNPS 基础上的核心改进：
#   1. 以特征定量表为锚点 — 每个节点同时携带谱图和定量信息
#   2. 节点属性增强 — m/z, RT, 各样本强度, log2FC, VIP 等
#   3. 边属性增强 — 在余弦相似度外增加样本间强度 Pearson 相关性
#   4. 区分 MS/MS 相似但不同源的节点 — 定量轮廓不一致的节点不会被错误连接


def _compute_intensity_correlation(
    intensities1: np.ndarray,
    intensities2: np.ndarray,
) -> float:
    """
    计算两个特征在样本间强度轮廓的 Pearson 相关系数。

    需要在至少 3 个共有非零值样本上计算，否则返回 0。
    """
    mask = (intensities1 > 0) & (intensities2 > 0)
    if mask.sum() < 3:
        return 0.0
    try:
        from scipy.stats import pearsonr
        corr, _ = pearsonr(intensities1[mask], intensities2[mask])
        if np.isnan(corr):
            return 0.0
        return float(corr)
    except Exception:
        return 0.0


# KEYWORD: FBMN
def molecular_networking_fbmn_impl(
    input_mgf: str,
    input_feature_table: str,
    output_dir: str,
    metadata_csv: Optional[str] = None,
    min_cosine: float = 0.7,
    min_matched_peaks: int = 4,
    fragment_tol: float = 0.02,
    top_k: int = 10,
    min_correlation: float = 0.0,
):
    """
    基于 FBMN（Feature-Based Molecular Networking）方法构建带定量信息的分子网络。

    与经典 GNPS 的关键区别：
    - 输入包含特征定量表（feature_table.csv），节点携带完整的定量和统计信息
    - 边同时包含谱图余弦相似度 + 样本间强度 Pearson 相关性
    - 适合识别在特定实验条件下共调控的代谢物

    参考:
        Nothias et al. "Feature-based molecular networking in the GNPS
        analysis environment." Nature Methods, 2020, 17(9), 905–908.

    Parameters
    ----------
    input_mgf : str
        差异代谢物 MS/MS 谱图 MGF 文件路径。
    input_feature_table : str
        特征定量表 CSV 路径。需要包含 feature_id, mz, rt_med 列，
        其余列为各样本的定量强度值。
        通常来自 extract_differential_features 输出的
        differential_feature_table.csv。
    output_dir : str
        输出目录。
    metadata_csv : str, optional
        样本元数据 CSV（Sample, Group 列）。提供后，节点表会额外包含
        各组的平均强度和 log2 fold change 信息。
    min_cosine : float, default=0.7
        最小余弦相似度阈值。FBMN 推荐 0.7。
    min_matched_peaks : int, default=4
        最小匹配碎片峰数。FBMN 因为有定量信息做二次过滤，
        可比 GNPS 略低（4 vs 6）。
    fragment_tol : float, default=0.02
        碎片离子匹配容差（Da）。
    top_k : int, default=10
        每节点保留的最强边数。
    min_correlation : float, default=0.0
        最小样本间强度 Pearson 相关系数。默认 0 表示不禁用此过滤。
        设为 0.5 表示仅保留定量轮廓相关 (r ≥ 0.5) 的边。

    Outputs
    -------
    {output_dir}/
    ├── fbmn_network.graphml        — 带定量信息的分子网络图
    ├── fbmn_edges.csv              — 边表 (cosine + pearson_r)
    ├── fbmn_nodes.csv              — 节点表 (mz, rt, log2FC, VIP, 组均值...)
    ├── fbmn_clusters.csv           — 分子家族汇总
    └── fbmn_summary.txt            — 统计摘要
    """
    print(f"\n[FBMN] 开始特征基分子网络分析...")
    print(f"  MGF: {input_mgf}")
    print(f"  特征表: {input_feature_table}")
    print(f"  min_cosine={min_cosine}, min_matched_peaks={min_matched_peaks}, "
          f"min_correlation={min_correlation}")

    t_start = time.time()

    # ========== 输入验证 ==========
    if not os.path.isfile(input_mgf):
        raise FileNotFoundError(f"MGF 文件未找到: {input_mgf}")
    if not os.path.isfile(input_feature_table):
        raise FileNotFoundError(f"特征表未找到: {input_feature_table}")

    os.makedirs(output_dir, exist_ok=True)

    # ========== 1. 解析输入 ==========
    print(f"\n  [Step 1/6] 解析输入数据...")
    spectra = _parse_mgf(input_mgf)
    if len(spectra) < 2:
        raise ValueError(f"MGF 中仅有 {len(spectra)} 个谱图，至少需要 2 个")

    feat_df = pd.read_csv(input_feature_table)
    if "feature_id" not in feat_df.columns:
        raise ValueError("特征表必须包含 feature_id 列")

    # 识别样本列（排除 feature_id, mz, rt_med 等元数据列）
    meta_cols = {"feature_id", "mz", "rt_med", "rt", "mz_med"}
    sample_cols = [c for c in feat_df.columns if c not in meta_cols]

    print(f"    谱图: {len(spectra)} 个, 特征表: {feat_df.shape[0]} 行 × "
          f"{len(sample_cols)} 个样本列")

    # ========== 2. 谱图余弦相似度 ==========
    print(f"\n  [Step 2/6] 全对全余弦相似度...")
    all_edges = _compute_all_vs_all_similarity(
        spectra=spectra, fragment_tol=fragment_tol, precursor_ppm=5,
    )

    # ========== 3. 余弦相似度过滤 ==========
    print(f"\n  [Step 3/6] 余弦相似度过滤...")
    edges_df = pd.DataFrame(all_edges)
    edges_df = edges_df[
        (edges_df["cosine"] >= min_cosine) &
        (edges_df["matched_peaks"] >= min_matched_peaks)
    ].copy()
    print(f"    过滤后候选边: {len(edges_df)}")

    # ========== 4. 强度相关性计算 ==========
    print(f"\n  [Step 4/6] 计算样本间强度 Pearson 相关性...")

    # 构建 feature_id → 强度向量映射
    feat_intensity = {}
    for _, row in feat_df.iterrows():
        fid = str(row["feature_id"])
        intensities = row[sample_cols].values.astype(np.float64)
        intensities = np.nan_to_num(intensities, nan=0.0)
        feat_intensity[fid] = intensities

    pearson_values = []
    for _, row in edges_df.iterrows():
        src = str(row["source"])
        tgt = str(row["target"])
        if src in feat_intensity and tgt in feat_intensity:
            r = _compute_intensity_correlation(
                feat_intensity[src], feat_intensity[tgt]
            )
        else:
            r = 0.0
        pearson_values.append(round(r, 4))

    edges_df["pearson_r"] = pearson_values

    # 相关性过滤
    if min_correlation > 0:
        before = len(edges_df)
        edges_df = edges_df[edges_df["pearson_r"] >= min_correlation].copy()
        print(f"    相关性过滤 (r >= {min_correlation}): {before} → {len(edges_df)} 条边")

    calcd = (edges_df["pearson_r"] != 0).sum()
    print(f"    有定量信息可计算相关性的边: {calcd}/{len(edges_df)}")

    # top-K
    if top_k > 0 and len(edges_df) > 0:
        edges_df["rank"] = edges_df.groupby("source")["cosine"].rank(
            ascending=False, method="first"
        )
        edges_df["rank_tgt"] = edges_df.groupby("target")["cosine"].rank(
            ascending=False, method="first"
        )
        edges_df = edges_df[
            (edges_df["rank"] <= top_k) | (edges_df["rank_tgt"] <= top_k)
        ].copy()
        edges_df.drop(columns=["rank", "rank_tgt"], inplace=True)

    # ========== 5. 构建 FBMN 网络 ==========
    print(f"\n  [Step 5/6] 构建 FBMN 网络...")

    # 解析元数据（如果提供）
    group_map = {}
    if metadata_csv and os.path.isfile(metadata_csv):
        try:
            meta = pd.read_csv(metadata_csv)
            if "Sample" in meta.columns and "Group" in meta.columns:
                group_map = dict(zip(meta["Sample"], meta["Group"]))
                print(f"    加载元数据: {len(group_map)} 个样本, "
                      f"{meta['Group'].nunique()} 个分组")
        except Exception:
            pass

    G = nx.Graph()

    # 构建 feature 信息字典
    feat_info = {}
    for _, row in feat_df.iterrows():
        fid = str(row["feature_id"])
        info = {"mz": None, "rt": None}
        for col in ["mz", "rt_med", "mz_med"]:
            if col in feat_df.columns and pd.notna(row.get(col)):
                info["mz"] = round(float(row[col]), 4)
                break
        for col in ["rt_med", "rt"]:
            if col in feat_df.columns and pd.notna(row.get(col)):
                info["rt"] = round(float(row[col]), 2)
                break

        # 组均值
        group_means = {}
        if group_map and info["mz"] is not None:
            for sample_name, group in group_map.items():
                if sample_name in feat_df.columns:
                    try:
                        val = float(row[sample_name])
                        if pd.notna(val):
                            group_means.setdefault(group, []).append(val)
                    except (ValueError, TypeError):
                        pass
        group_avg = {g: round(np.mean(vals), 2) for g, vals in group_means.items()} if group_means else {}

        feat_info[fid] = {
            "mz": info["mz"],
            "rt": info["rt"],
            "group_means": group_avg,
        }

    # 添加节点
    for sp in spectra:
        fid = sp["feature_id"]
        fi = feat_info.get(fid, {})
        G.add_node(
            fid,
            precursor_mz=fi.get("mz") or round(sp["precursor_mz"], 4),
            rt=fi.get("rt") or round(sp["rt"], 2) if sp["rt"] else None,
            charge=sp.get("charge", "1+"),
            num_peaks=len(sp["mz_array"]),
        )
        # 添加组均值信息
        for grp, val in fi.get("group_means", {}).items():
            G.nodes[fid][f"mean_{grp}"] = val

    # 添加边
    for _, row in edges_df.iterrows():
        src, tgt = str(row["source"]), str(row["target"])
        if src in G and tgt in G:
            G.add_edge(
                src, tgt,
                cosine=row["cosine"],
                matched_peaks=int(row["matched_peaks"]),
                pearson_r=row.get("pearson_r", 0.0),
                delta_ppm=row.get("precursor_delta_ppm", 0.0),
            )

    # 分子家族
    connected_components = list(nx.connected_components(G))
    family_map = {}
    for i, comp in enumerate(connected_components):
        for node in comp:
            family_map[node] = f"MF_{i + 1:04d}"

    for node in G.nodes():
        G.nodes[node]["molecular_family"] = family_map.get(node, "singleton")
        G.nodes[node]["degree"] = G.degree(node)

    # 计算 log2FC（对于两组设计）
    if len(group_map) > 0:
        groups = sorted(set(group_map.values()))
        if len(groups) == 2:
            for node in G.nodes():
                key1 = f"mean_{groups[0]}"
                key2 = f"mean_{groups[1]}"
                v1 = G.nodes[node].get(key1, 0) or 0
                v2 = G.nodes[node].get(key2, 0) or 0
                if v1 > 0 and v2 > 0:
                    G.nodes[node]["log2FC"] = round(np.log2((v2 + 1) / (v1 + 1)), 3)
                else:
                    G.nodes[node]["log2FC"] = None

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    n_families = len(connected_components)
    n_singletons = sum(1 for c in connected_components if len(c) == 1)

    print(f"    节点: {n_nodes}, 边: {n_edges}, 分子家族: {n_families}, 孤立节点: {n_singletons}")

    # ========== 6. 导出 ==========
    print(f"\n  [Step 6/6] 导出 FBMN 文件...")

    # GraphML
    graphml_path = os.path.join(output_dir, "fbmn_network.graphml")
    nx.write_graphml(G, graphml_path)
    print(f"    ✅ {graphml_path}")

    # 边表
    edges_out = os.path.join(output_dir, "fbmn_edges.csv")
    edges_df.to_csv(edges_out, index=False)
    print(f"    ✅ {edges_out}")

    # 节点表
    nodes_data = []
    for node, attrs in G.nodes(data=True):
        row = {
            "feature_id": node,
            "precursor_mz": attrs.get("precursor_mz"),
            "rt": attrs.get("rt"),
            "charge": attrs.get("charge"),
            "num_peaks": attrs.get("num_peaks"),
            "degree": attrs.get("degree", 0),
            "molecular_family": attrs.get("molecular_family", "singleton"),
        }
        if "log2FC" in attrs:
            row["log2FC"] = attrs["log2FC"]
        for grp in sorted(set(group_map.values())):
            k = f"mean_{grp}"
            if k in attrs:
                row[k] = attrs[k]
        nodes_data.append(row)
    nodes_df = pd.DataFrame(nodes_data)
    nodes_out = os.path.join(output_dir, "fbmn_nodes.csv")
    nodes_df.to_csv(nodes_out, index=False)
    print(f"    ✅ {nodes_out}")

    # 分子家族
    cluster_rows = []
    for i, comp in enumerate(connected_components):
        subg = G.subgraph(comp)
        cos_vals = [d.get("cosine", 0) for _, _, d in subg.edges(data=True)]
        r_vals = [d.get("pearson_r", 0) for _, _, d in subg.edges(data=True) if d.get("pearson_r", 0) != 0]
        mzs = [G.nodes[n].get("precursor_mz", 0) or 0 for n in comp]
        mzs = [m for m in mzs if m > 0]
        cluster_rows.append({
            "molecular_family": f"MF_{i + 1:04d}",
            "size": len(comp),
            "members": "|".join(sorted(comp)),
            "avg_cosine": round(np.mean(cos_vals), 4) if cos_vals else 0.0,
            "avg_pearson_r": round(np.mean(r_vals), 4) if r_vals else 0.0,
            "min_mz": round(min(mzs), 4) if mzs else None,
            "max_mz": round(max(mzs), 4) if mzs else None,
        })
    cluster_df = pd.DataFrame(cluster_rows)
    if len(cluster_df) > 0:
        cluster_df = cluster_df.sort_values("size", ascending=False).reset_index(drop=True)
    clusters_out = os.path.join(output_dir, "fbmn_clusters.csv")
    cluster_df.to_csv(clusters_out, index=False)
    print(f"    ✅ {clusters_out}")

    # 摘要
    t_elapsed = time.time() - t_start
    summary = [
        "=" * 60,
        "  FBMN 特征基分子网络 — 统计摘要",
        "=" * 60,
        f"  MGF: {input_mgf}",
        f"  特征表: {input_feature_table}",
        f"  谱图: {len(spectra)}, 节点: {n_nodes}, 边: {n_edges}",
        f"  分子家族: {n_families}, 孤立节点: {n_singletons}",
        f"  最大分子家族: {cluster_df.iloc[0]['size'] if len(cluster_df) > 0 else 0} 个节点",
        f"  参数: min_cosine={min_cosine}, min_matched_peaks={min_matched_peaks}, "
        f"min_correlation={min_correlation}, top_k={top_k}",
        "",
    ]
    if n_edges > 0:
        degrees = [d for _, d in G.degree()]
        summary.extend([
            f"  连通性:",
            f"    平均度: {np.mean(degrees):.2f}, 最大度: {np.max(degrees)}",
            f"    网络密度: {nx.density(G):.6f}",
            f"    平均聚类系数: {nx.average_clustering(G):.4f}",
        ])
    if calcd > 0:
        summary.append(f"  有效 Pearson r 边: {calcd}/{len(edges_df)}")
    summary.extend([
        f"  运行时间: {t_elapsed:.1f} 秒",
        "=" * 60,
    ])

    summary_out = os.path.join(output_dir, "fbmn_summary.txt")
    with open(summary_out, "w", encoding="utf-8") as f:
        f.write("\n".join(summary))
    for line in summary:
        print(line)

    print(f"\n✅ [FBMN] 特征基分子网络分析完成!")

    # --- 生成图表 ---
    generate_network_figures(
        method="fbmn",
        output_dir=output_dir,
        G=G,
        edges_df=edges_df,
        title_prefix="FBMN",
        group_map=group_map,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MS2LDA — 质谱潜在 Dirichlet 分配 (Mass2Motif 发现)
# ═══════════════════════════════════════════════════════════════════════════════
# 参考: van der Hooft et al. PNAS, 2016, 113(48), 13738–13743
#       https://doi.org/10.1073/pnas.1608041113
#
# MS2LDA 的核心思想：
#   - 将 MS/MS 碎片模式视为"文本"，每个谱图是一个"文档"，每个碎片是一个"词"
#   - 使用 LDA 主题模型发现反复出现的共现碎片模式 → Mass2Motifs
#   - 每个 Mass2Motif 代表一种保守的化学子结构或碎片模式
#   - 不依赖任何谱库，能发现全新未知化合物的结构特征


def _bin_fragments_for_lda(
    spectra: List[Dict],
    fragment_tol: float = 0.005,
    min_fragment_intensity: float = 0.01,
    max_fragments_per_spectrum: int = 100,
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    将谱图碎片离散化为 LDA 所需的"词袋"矩阵。

    步骤:
    1. 对每个谱图，过滤掉相对强度 < min_fragment_intensity 的碎片
    2. 保留强度最大的 max_fragments_per_spectrum 个碎片
    3. 按 fragment_tol 将 m/z 四舍五入到最近的 bin
    4. 收集所有谱图中出现的唯一 bin → 词汇表
    5. 构建 谱图 × 词汇 的计数矩阵（强度加权）

    Returns
    -------
    doc_term_matrix : np.ndarray (n_spectra × n_vocab)
    fragment_bins : np.ndarray  — 每个 bin 的中心 m/z
    feature_ids : list of str
    """
    import math

    n_spectra = len(spectra)
    # 确定 bin 大小对应的精度
    if fragment_tol >= 0.01:
        decimals = 2
    elif fragment_tol >= 0.001:
        decimals = 3
    else:
        decimals = 4

    # 第一遍：收集所有碎片 m/z 值，构建全局词汇表
    all_fragments = []
    for sp in spectra:
        mz = sp["mz_array"]
        intensity = sp["intensity_array"]
        # 按相对强度过滤
        max_int = intensity.max() if len(intensity) > 0 else 1.0
        if max_int == 0:
            max_int = 1.0
        keep = intensity >= (min_fragment_intensity * max_int)
        mz_filt = mz[keep]
        int_filt = intensity[keep]
        # 保留 top N
        if len(mz_filt) > max_fragments_per_spectrum:
            top_idx = np.argsort(int_filt)[-max_fragments_per_spectrum:]
            mz_filt = mz_filt[top_idx]
            int_filt = int_filt[top_idx]
        # 离散化
        binned = np.round(mz_filt, decimals)
        all_fragments.extend(binned.tolist())

    # 构建词汇表（排序后的唯一 bin 值）
    vocab = sorted(set(all_fragments))
    if len(vocab) < 5:
        raise ValueError(
            f"碎片词汇表过小 ({len(vocab)} 个唯一 bin)，请降低 fragment_tol 或 "
            f"min_fragment_intensity"
        )

    vocab_to_idx = {v: i for i, v in enumerate(vocab)}
    print(f"    碎片词汇表: {len(vocab)} 个唯一 m/z bins "
          f"(tol={fragment_tol} Da)")

    # 第二遍：构建文档-词矩阵
    doc_term = np.zeros((n_spectra, len(vocab)), dtype=np.float64)
    feature_ids = []

    for i, sp in enumerate(spectra):
        feature_ids.append(sp["feature_id"])
        mz = sp["mz_array"]
        intensity = sp["intensity_array"]
        max_int = intensity.max() if len(intensity) > 0 else 1.0
        if max_int == 0:
            max_int = 1.0
        keep = intensity >= (min_fragment_intensity * max_int)
        mz_filt = mz[keep]
        int_filt = intensity[keep]
        if len(mz_filt) > max_fragments_per_spectrum:
            top_idx = np.argsort(int_filt)[-max_fragments_per_spectrum:]
            mz_filt = mz_filt[top_idx]
            int_filt = int_filt[top_idx]

        binned = np.round(mz_filt, decimals)
        for b, val in zip(binned, int_filt):
            idx = vocab_to_idx.get(b)
            if idx is not None:
                doc_term[i, idx] += float(val)

    return doc_term, np.array(vocab), feature_ids


# KEYWORD: MS2LDA
def molecular_networking_ms2lda_impl(
    input_mgf: str,
    output_dir: str,
    n_motifs: int = 300,
    fragment_tol: float = 0.005,
    min_fragment_intensity: float = 0.01,
    n_iterations: int = 1000,
    random_seed: int = 42,
):
    """
    使用 MS2LDA（Latent Dirichlet Allocation）从 MS/MS 谱图中发现 Mass2Motifs。

    Mass2Motif 是一组共现的碎片离子 m/z 值，代表了保守的化学子结构或碎片模式。
    不依赖任何谱库，可以对完全未知的化合物进行结构特征分析。

    算法:
    1. 碎片离散化 — 将谱图碎片按 m/z 容差离散化为"词"
    2. 文档-词矩阵 — 每个谱图是一个文档，碎片 bin 是词，强度为权重
    3. LDA 训练 — 使用 sklearn LatentDirichletAllocation 发现潜在主题
    4. 主题 → Mass2Motif — 每个主题对应一个 Mass2Motif
    5. 谱图-Motif 关联 — 计算每个谱图与每个 Motif 的相关概率

    参考:
        van der Hooft et al. "Topic modeling for untargeted substructure
        exploration in metabolomics." PNAS, 2016, 113(48), 13738–13743.

    Parameters
    ----------
    input_mgf : str
        差异代谢物 MS/MS 谱图 MGF 文件路径。
    output_dir : str
        输出目录。
    n_motifs : int, default=300
        要发现的 Mass2Motif 数量（LDA 主题数）。
        谱图越多，可设置越多的 motif。经验法则: n_motifs ≈ n_spectra × 2。
    fragment_tol : float, default=0.005
        碎片离散化的 m/z 容差（Da）。决定了 bin 的粒度。
        0.005 Da 适合 Orbitrap 高分辨数据，0.01 Da 适合 TOF 数据。
    min_fragment_intensity : float, default=0.01
        最小碎片相对强度（相对于谱图最高峰）。低于此值的碎片被忽略。
    n_iterations : int, default=1000
        LDA 训练的最大迭代次数。更大值可能获得更稳定的结果，但计算时间更长。
    random_seed : int, default=42
        随机种子，保证结果可重现。

    Outputs
    -------
    {output_dir}/
    ├── mass2motifs.csv             — Mass2Motif 详情 (每个 motif 的 top 碎片)
    ├── spectra_motif_scores.csv    — 谱图 × Motif 概率矩阵
    ├── motif_fragment_distribution.csv — 所有 Motif × 碎片概率分布
    └── ms2lda_summary.txt          — 统计摘要

    Notes
    -----
    - 谱图数量建议 > 20 以获得有意义的 LDA 结果。
    - n_motifs 应小于谱图数量，否则模型会过拟合。
    - 结果解读：每个 Mass2Motif 的 top 碎片 m/z 和 m/z 差异可能对应
      特定的化学子结构（如糖基、氨基酸残基、脂肪酸链等）。
    """
    from sklearn.decomposition import LatentDirichletAllocation

    print(f"\n[MS2LDA] 开始 Mass2Motif 发现...")
    print(f"  MGF: {input_mgf}")
    print(f"  n_motifs={n_motifs}, fragment_tol={fragment_tol}, "
          f"n_iterations={n_iterations}, seed={random_seed}")

    t_start = time.time()

    # ========== 输入验证 ==========
    if not os.path.isfile(input_mgf):
        raise FileNotFoundError(f"MGF 文件未找到: {input_mgf}")

    os.makedirs(output_dir, exist_ok=True)

    # ========== 1. 解析 MGF ==========
    print(f"\n  [Step 1/5] 解析 MGF 谱图...")
    spectra = _parse_mgf(input_mgf)
    n_spectra = len(spectra)

    if n_spectra < 10:
        raise ValueError(
            f"仅 {n_spectra} 个谱图，MS2LDA 建议至少 20 个谱图。"
            f"当前数据量不足以发现可靠的 Mass2Motif。"
        )

    # 自动调整 n_motifs
    if n_motifs >= n_spectra:
        n_motifs = max(10, n_spectra // 2)
        print(f"    ⚠️ n_motifs 自动调整: {n_motifs} (谱图数={n_spectra})")

    print(f"    谱图数: {n_spectra}, Mass2Motif 数: {n_motifs}")

    # ========== 2. 碎片离散化 ==========
    print(f"\n  [Step 2/5] 碎片离散化...")
    doc_term, fragment_bins, feature_ids = _bin_fragments_for_lda(
        spectra=spectra,
        fragment_tol=fragment_tol,
        min_fragment_intensity=min_fragment_intensity,
    )
    n_vocab = len(fragment_bins)
    total_fragments = int(doc_term.sum())
    print(f"    文档-词矩阵: {n_spectra} 谱图 × {n_vocab} bins")
    print(f"    总碎片计数: {total_fragments}")

    # ========== 3. LDA 训练 ==========
    print(f"\n  [Step 3/5] LDA 模型训练 (sklearn, {n_iterations} 次迭代)...")

    lda = LatentDirichletAllocation(
        n_components=n_motifs,
        max_iter=n_iterations,
        learning_method="batch",
        random_state=random_seed,
        n_jobs=1,
        verbose=0,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lda.fit(doc_term)

    # 主题-词分布 (motif × fragment)
    topic_word = lda.components_  # shape: (n_motifs, n_vocab)
    # 文档-主题分布 (spectrum × motif)
    doc_topic = lda.transform(doc_term)  # shape: (n_spectra, n_motifs)

    # 计算每个主题的困惑度贡献
    perpl = lda.perplexity(doc_term)
    print(f"    训练完成, 困惑度 (perplexity): {perpl:.2f}")

    # ========== 4. 提取 Mass2Motif 特征 ==========
    print(f"\n  [Step 4/5] 提取 Mass2Motif 特征...")

    motif_details = []
    for motif_idx in range(n_motifs):
        # 获取该 motif 的 top 碎片
        frag_weights = topic_word[motif_idx]
        # 归一化为概率
        frag_prob = frag_weights / (frag_weights.sum() + 1e-10)

        # Top 20 碎片
        top_n = min(20, n_vocab)
        top_idx = np.argsort(frag_prob)[-top_n:][::-1]

        top_frags = []
        for idx in top_idx:
            if frag_prob[idx] > 1e-6:
                top_frags.append({
                    "mz": round(float(fragment_bins[idx]), 4),
                    "probability": round(float(frag_prob[idx]), 6),
                })

        # 计算该 motif 在所有谱图中的总"载荷"
        motif_load = doc_topic[:, motif_idx].sum()

        # 找到与该 motif 最相关的 top 谱图
        top_spectra_idx = np.argsort(doc_topic[:, motif_idx])[-5:][::-1]
        top_spectra = [feature_ids[i] for i in top_spectra_idx
                       if doc_topic[i, motif_idx] > 0.01]

        motif_details.append({
            "motif_id": f"Motif_{motif_idx + 1:04d}",
            "total_load": round(float(motif_load), 4),
            "n_top_spectra": len(top_spectra),
            "top_spectra": "|".join(top_spectra[:5]),
            "top_fragments": json.dumps(top_frags, ensure_ascii=False),
            "top_frag_mz": "|".join(
                str(f["mz"]) for f in top_frags[:10]
            ),
        })

    motif_df = pd.DataFrame(motif_details)
    # 按总载荷降序
    motif_df = motif_df.sort_values("total_load", ascending=False).reset_index(drop=True)

    n_active = (motif_df["n_top_spectra"] > 0).sum()
    print(f"    活跃 Mass2Motif (至少关联1个谱图): {n_active}/{n_motifs}")

    # ========== 5. 导出 ==========
    print(f"\n  [Step 5/5] 导出 MS2LDA 结果...")

    # --- Mass2Motif 详情 ---
    motifs_out = os.path.join(output_dir, "mass2motifs.csv")
    motif_df.to_csv(motifs_out, index=False)
    print(f"    ✅ {motifs_out}")

    # --- 谱图-Motif 矩阵 ---
    sm_df = pd.DataFrame(
        doc_topic,
        index=feature_ids,
        columns=[f"Motif_{i + 1:04d}" for i in range(n_motifs)]
    )
    sm_df.index.name = "feature_id"
    sm_out = os.path.join(output_dir, "spectra_motif_scores.csv")
    sm_df.to_csv(sm_out)
    print(f"    ✅ {sm_out}")

    # --- Motif × 碎片全概率分布 ---
    mf_data = {}
    for motif_idx in range(n_motifs):
        prob = topic_word[motif_idx] / (topic_word[motif_idx].sum() + 1e-10)
        col_name = f"Motif_{motif_idx + 1:04d}"
        mf_data[col_name] = prob
    mf_data["fragment_mz"] = [round(float(m), 4) for m in fragment_bins]
    mf_df = pd.DataFrame(mf_data)
    cols = ["fragment_mz"] + [c for c in mf_df.columns if c != "fragment_mz"]
    mf_df = mf_df[cols]
    mf_out = os.path.join(output_dir, "motif_fragment_distribution.csv")
    mf_df.to_csv(mf_out, index=False)
    print(f"    ✅ {mf_out}")

    # --- 摘要 ---
    t_elapsed = time.time() - t_start
    summary = [
        "=" * 60,
        "  MS2LDA Mass2Motif 发现 — 统计摘要",
        "=" * 60,
        f"  MGF: {input_mgf}",
        f"  谱图数: {n_spectra}",
        f"  Mass2Motif 数: {n_motifs}",
        f"  活跃 Motif 数: {n_active}",
        f"  碎片词汇表: {n_vocab} bins",
        f"  总碎片计数: {total_fragments}",
        f"  困惑度: {perpl:.2f}",
        f"  参数: fragment_tol={fragment_tol}, n_iterations={n_iterations}",
        f"  运行时间: {t_elapsed:.1f} 秒",
        "",
    ]
    if n_active >= 5:
        summary.append(f"  Top 5 Mass2Motifs:")
        for _, row in motif_df.head(5).iterrows():
            summary.append(f"    {row['motif_id']}: "
                           f"载荷={row['total_load']:.1f}, "
                           f"碎片={row['top_frag_mz'][:80]}...")
    summary.append("=" * 60)

    summary_out = os.path.join(output_dir, "ms2lda_summary.txt")
    with open(summary_out, "w", encoding="utf-8") as f:
        f.write("\n".join(summary))
    for line in summary:
        print(line)

    print(f"\n✅ [MS2LDA] Mass2Motif 发现完成!")
    print(f"   提示: 每个 Mass2Motif 的 top 碎片模式可能对应特定的化学子结构。")
    print(f"   例如: 持续出现的 m/z 差异 162.05 Da 可能表示己糖基团的丢失。")

    # --- 生成图表 ---
    # 收集所有谱图的前体 m/z 用于中性丢失计算
    precursor_mz_vals = [sp["precursor_mz"] for sp in spectra if sp["precursor_mz"]]
    generate_network_figures(
        method="ms2lda",
        output_dir=output_dir,
        motif_df=motif_df,
        spectra_motif_scores_csv=os.path.join(output_dir, "spectra_motif_scores.csv"),
        title_prefix="MS2LDA",
        precursor_mz_values=precursor_mz_vals if precursor_mz_vals else None,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MolNetEnhancer — 分子网络增强注释与化学分类
# ═══════════════════════════════════════════════════════════════════════════════
# 参考: Ernst et al. Metabolites, 2019, 9(7), 144
#       https://doi.org/10.3390/metabo9070144
#
# MolNetEnhancer 的核心功能：
#   1. 整合网络拓扑 + 谱库注释 + 化学分类信息
#   2. 注释传播 — 已注释节点帮助推断同一分子家族中未注释节点的化学类别
#   3. 化学分类富集 — 在分子家族层面统计化学类别分布
#   4. 输出增强网络 → Cytoscape 可视化，用化学分类着色


def _parse_compound_name(name: str) -> Dict[str, str]:
    """
    从化合物名称中提取初步的化学分类线索。

    基于命名模式启发式识别常见的代谢物类别，作为 ClassyFire 不可用时的后备方案。
    这些模式匹配基于代谢组学中常见的命名约定。

    Returns dict with keys: category, confidence
    """
    if not name or pd.isna(name):
        return {"category": "unknown", "confidence": "low"}

    name_lower = str(name).lower()

    # 糖类模式
    sugar_patterns = [
        "glucose", "fructose", "sucrose", "maltose", "lactose", "galactose",
        "mannose", "xylose", "ribose", "arabinose", "fucose", "rhamnose",
        "glucoside", "galactoside", "glycoside", "disaccharide", "trisaccharide",
        "oligosaccharide", "sugar", "mannan", "glucan",
    ]
    for p in sugar_patterns:
        if p in name_lower:
            return {"category": "Carbohydrates and carbohydrate conjugates", "confidence": "medium"}

    # 氨基酸和肽类
    aa_patterns = [
        "amino acid", "alanine", "arginine", "asparagine", "aspartate",
        "cysteine", "glutamine", "glutamate", "glycine", "histidine",
        "isoleucine", "leucine", "lysine", "methionine", "phenylalanine",
        "proline", "serine", "threonine", "tryptophan", "tyrosine", "valine",
        "dipeptide", "tripeptide", "peptide", "cyclopeptide",
    ]
    for p in aa_patterns:
        if p in name_lower:
            return {"category": "Amino acids, peptides, and analogues", "confidence": "medium"}

    # 脂质
    lipid_patterns = [
        "fatty acid", "palmitic", "stearic", "oleic", "linoleic", "linolenic",
        "arachidonic", "glycerol", "phospholipid", "sphingolipid", "ceramide",
        "monoglyceride", "diglyceride", "triglyceride", "acylcarnitine",
        "lysophosphatidyl", "phosphatidyl", "lipid",
    ]
    for p in lipid_patterns:
        if p in name_lower:
            return {"category": "Lipids and lipid-like molecules", "confidence": "medium"}

    # 黄酮类
    flavonoid_patterns = [
        "flavone", "flavonol", "flavanone", "flavanol", "flavonoid",
        "isoflavone", "anthocyanin", "catechin", "quercetin", "kaempferol",
        "apigenin", "luteolin", "genistein", "daidzein", "naringenin",
        "hesperetin", "rutin", "proanthocyanidin",
    ]
    for p in flavonoid_patterns:
        if p in name_lower:
            return {"category": "Flavonoids", "confidence": "medium"}

    # 萜类
    terpenoid_patterns = [
        "terpene", "terpenoid", "monoterpene", "sesquiterpene", "diterpene",
        "triterpene", "carotenoid", "sterol", "steroid", "cholesterol",
        "ergosterol", "saponin", "limonene", "menthol",
    ]
    for p in terpenoid_patterns:
        if p in name_lower:
            return {"category": "Terpenoids", "confidence": "medium"}

    # 生物碱
    alkaloid_patterns = [
        "alkaloid", "morphine", "caffeine", "nicotine", "atropine",
        "quinine", "berberine", "vinblastine", "vincristine", "colchicine",
        "piperine", "capsaicin", "ergotamine",
    ]
    for p in alkaloid_patterns:
        if p in name_lower:
            return {"category": "Alkaloids and derivatives", "confidence": "medium"}

    # 苯丙素类
    pp_patterns = [
        "coumarin", "lignan", "cinnamic", "caffeic", "ferulic",
        "chlorogenic", "rosmarinic", "curcumin",
    ]
    for p in pp_patterns:
        if p in name_lower:
            return {"category": "Phenylpropanoids and polyketides", "confidence": "medium"}

    # 核苷类
    nucleo_patterns = [
        "nucleoside", "nucleotide", "adenosine", "guanosine", "cytidine",
        "thymidine", "uridine", "inosine", "adenine", "guanine", "cytosine",
        "thymine", "uracil",
    ]
    for p in nucleo_patterns:
        if p in name_lower:
            return {"category": "Nucleosides, nucleotides, and analogues", "confidence": "medium"}

    # 苯环类（通用）
    if any(p in name_lower for p in ["benzoic", "phenol", "benzene", "phenyl"]):
        return {"category": "Benzenoids", "confidence": "low"}

    return {"category": "unknown", "confidence": "low"}


# KEYWORD: MolNetEnhancer
def molecular_networking_molnetenhancer_impl(
    network_edges_csv: str,
    network_nodes_csv: str,
    annotation_csv: Optional[str],
    output_dir: str,
    annotation_col: str = "compound_name",
):
    """
    基于 MolNetEnhancer 思路对分子网络进行增强注释。

    核心操作:
    1. 将谱库注释（compound_name）映射到网络节点
    2. 从化合物名称推断化学分类
    3. 在每个分子家族内进行注释传播 — 邻居获得同样的推断化学类别
    4. 输出增强后的网络，节点带化学分类标签，可在 Cytoscape 中按类别着色

    参考:
        Ernst et al. "MolNetEnhancer: Enhanced Molecular Networks by
        Integrating Metabolome Mining and Annotation." Metabolites, 2019.

    Parameters
    ----------
    network_edges_csv : str
        GNPS 或 FBMN 输出的边表 (network_edges.csv / fbmn_edges.csv)。
    network_nodes_csv : str
        GNPS 或 FBMN 输出的节点表 (network_nodes.csv / fbmn_nodes.csv)。
    annotation_csv : str or None
        谱库注释结果，来自 spectral_annotation 的
        annotated_differential_feature_table.csv。
        需要包含 feature_id 和化合物名称列。
        如果为 None，将仅基于节点表已有的 compound_name 列进行增强。
    output_dir : str
        输出目录。
    annotation_col : str, default="compound_name"
        注释表中化合物名称所在的列名。

    Outputs
    -------
    {output_dir}/
    ├── enhanced_network.graphml          — 带化学分类信息的增强网络
    ├── enhanced_nodes.csv                — 增强节点表 (含 chemical_category)
    ├── chemical_class_distribution.csv   — 化学类别在各分子家族的分布
    ├── annotation_propagation_log.csv    — 注释传播记录
    └── molnetenhancer_summary.txt        — 统计摘要
    """
    print(f"\n[MolNetEnhancer] 开始分子网络增强注释...")
    print(f"  边表: {network_edges_csv}")
    print(f"  节点表: {network_nodes_csv}")
    print(f"  注释表: {annotation_csv}")

    t_start = time.time()

    # ========== 输入验证 ==========
    for path, desc in [(network_edges_csv, "边表"), (network_nodes_csv, "节点表")]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{desc}未找到: {path}")

    os.makedirs(output_dir, exist_ok=True)

    # ========== 1. 加载网络数据 ==========
    print(f"\n  [Step 1/5] 加载网络数据...")
    edges_df = pd.read_csv(network_edges_csv)
    nodes_df = pd.read_csv(network_nodes_csv)

    if "feature_id" not in nodes_df.columns:
        raise ValueError("节点表必须包含 feature_id 列")

    print(f"    边: {len(edges_df)}, 节点: {len(nodes_df)}")

    # 确定边表的 source/target 列
    src_col = "source" if "source" in edges_df.columns else "Source"
    tgt_col = "target" if "target" in edges_df.columns else "Target"

    # ========== 2. 加载并映射注释 ==========
    print(f"\n  [Step 2/5] 加载谱库注释...")
    annotation_map = {}  # feature_id → compound_name

    # 从节点表已有的 compound_name 加载
    if "compound_name" in nodes_df.columns:
        for _, row in nodes_df.iterrows():
            val = row["compound_name"]
            if pd.notna(val) and str(val).strip():
                annotation_map[str(row["feature_id"])] = str(val).strip()
        print(f"    从节点表加载: {len(annotation_map)} 个已有注释")

    # 从独立的注释表加载（优先级更高）
    if annotation_csv and os.path.isfile(annotation_csv):
        anno_df = pd.read_csv(annotation_csv)
        # 兼容 xcms 输出的 Feature 列名和标准 feature_id
        id_col = "feature_id" if "feature_id" in anno_df.columns else (
            "Feature" if "Feature" in anno_df.columns else None
        )
        if id_col and annotation_col in anno_df.columns:
            count = 0
            for _, row in anno_df.iterrows():
                val = row[annotation_col]
                if pd.notna(val) and str(val).strip():
                    annotation_map[str(row[id_col])] = str(val).strip()
                    count += 1
            print(f"    从注释表加载: {count} 个注释")
        else:
            print(f"    ⚠️ 注释表缺少 feature_id/Feature 或 {annotation_col} 列")

    total_annotated = len(annotation_map)
    print(f"    总计注释节点: {total_annotated}/{len(nodes_df)} "
          f"({100 * total_annotated / max(1, len(nodes_df)):.1f}%)")

    # ========== 3. 化学分类推断 ==========
    print(f"\n  [Step 3/5] 化学分类推断...")
    node_category = {}    # feature_id → category
    node_conf = {}        # feature_id → confidence

    for fid, cpd_name in annotation_map.items():
        result = _parse_compound_name(cpd_name)
        node_category[fid] = result["category"]
        node_conf[fid] = result["confidence"]

    n_classified = sum(1 for v in node_category.values() if v != "unknown")
    print(f"    直接分类: {n_classified}/{len(node_category)} "
          f"({100 * n_classified / max(1, len(node_category)):.1f}%)")

    # ========== 4. 网络注释传播 ==========
    print(f"\n  [Step 4/5] 分子家族内注释传播...")

    # 重建网络图
    G = nx.Graph()
    for _, row in nodes_df.iterrows():
        G.add_node(str(row["feature_id"]))
    for _, row in edges_df.iterrows():
        src, tgt = str(row[src_col]), str(row[tgt_col])
        if src in G and tgt in G:
            G.add_edge(src, tgt)

    components = list(nx.connected_components(G))
    print(f"    分子家族数: {len(components)}")

    propagation_log = []

    for comp_idx, comp in enumerate(components):
        family_id = f"MF_{comp_idx + 1:04d}"

        # 在家族内统计化学类别
        family_categories = {}
        for node in comp:
            cat = node_category.get(node, "unknown")
            if cat != "unknown":
                family_categories[cat] = family_categories.get(cat, 0) + 1

        # 确定该家族的"共识类别"（最频繁的类别）
        if family_categories:
            consensus_cat = max(family_categories, key=family_categories.get)
            n_known = family_categories[consensus_cat]
            n_family = len(comp)

            # 传播到未注释的邻居
            for node in comp:
                if node not in node_category or node_category[node] == "unknown":
                    node_category[node] = consensus_cat
                    node_conf[node] = "propagated"
                    propagation_log.append({
                        "family_id": family_id,
                        "feature_id": node,
                        "inferred_category": consensus_cat,
                        "based_on_known": n_known,
                        "family_size": n_family,
                    })

    prop_df = pd.DataFrame(propagation_log)
    n_prop = len(prop_df)
    print(f"    传播注释: {n_prop} 个节点")

    # 更新覆盖率
    final_classified = sum(1 for v in node_category.values() if v != "unknown")
    coverage = 100 * final_classified / max(1, len(G.nodes()))
    print(f"    最终分类覆盖率: {final_classified}/{len(G.nodes())} ({coverage:.1f}%)")

    # ========== 5. 导出增强结果 ==========
    print(f"\n  [Step 5/5] 导出增强结果...")

    # --- 增强节点表 ---
    enhanced_nodes = []
    for _, row in nodes_df.iterrows():
        fid = str(row["feature_id"])
        node_data = row.to_dict()
        node_data["chemical_category"] = node_category.get(fid, "unknown")
        node_data["category_confidence"] = node_conf.get(fid, "low")
        node_data["has_direct_annotation"] = (
            fid in annotation_map and node_conf.get(fid) != "propagated"
        )
        enhanced_nodes.append(node_data)

    enh_nodes_df = pd.DataFrame(enhanced_nodes)
    nodes_out = os.path.join(output_dir, "enhanced_nodes.csv")
    enh_nodes_df.to_csv(nodes_out, index=False)
    print(f"    ✅ {nodes_out}")

    # --- 增强网络 GraphML ---
    for node in G.nodes():
        G.nodes[node]["chemical_category"] = node_category.get(node, "unknown")
        G.nodes[node]["category_confidence"] = node_conf.get(node, "low")

    graphml_out = os.path.join(output_dir, "enhanced_network.graphml")
    nx.write_graphml(G, graphml_out)
    print(f"    ✅ {graphml_out}")

    # --- 化学类别分布 ---
    if n_classified > 0 or n_prop > 0:
        cat_dist = {}
        for comp_idx, comp in enumerate(components):
            family_id = f"MF_{comp_idx + 1:04d}"
            family_cats = {}
            for node in comp:
                cat = node_category.get(node, "unknown")
                family_cats[cat] = family_cats.get(cat, 0) + 1
            for cat, cnt in family_cats.items():
                cat_dist.setdefault(cat, []).append({
                    "molecular_family": family_id,
                    "count_in_family": cnt,
                    "family_size": len(comp),
                    "fraction_in_family": round(cnt / len(comp), 3),
                })

        dist_rows = []
        for cat, entries in cat_dist.items():
            for e in entries:
                dist_rows.append({"chemical_category": cat, **e})
        dist_df = pd.DataFrame(dist_rows)
        if len(dist_df) > 0:
            dist_df = dist_df.sort_values(
                ["chemical_category", "fraction_in_family"], ascending=[True, False]
            )
        dist_out = os.path.join(output_dir, "chemical_class_distribution.csv")
        dist_df.to_csv(dist_out, index=False)
        print(f"    ✅ {dist_out}")

    # --- 传播日志 ---
    if n_prop > 0:
        prop_out = os.path.join(output_dir, "annotation_propagation_log.csv")
        prop_df.to_csv(prop_out, index=False)
        print(f"    ✅ {prop_out}")

    # --- 摘要 ---
    t_elapsed = time.time() - t_start
    cat_counts = {}
    for v in node_category.values():
        cat_counts[v] = cat_counts.get(v, 0) + 1
    top_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)

    summary = [
        "=" * 60,
        "  MolNetEnhancer 分子网络增强注释 — 统计摘要",
        "=" * 60,
        f"  节点数: {len(G.nodes())}",
        f"  边数: {len(G.edges())}",
        f"  分子家族数: {len(components)}",
        f"  直接注释节点: {total_annotated}",
        f"  传播注释节点: {n_prop}",
        f"  总分类覆盖率: {coverage:.1f}%",
        "",
        f"  化学类别分布:",
    ]
    for cat, cnt in top_cats:
        pct = 100 * cnt / max(1, len(G.nodes()))
        summary.append(f"    {cat}: {cnt} ({pct:.1f}%)")
    summary.extend([
        "",
        f"  运行时间: {t_elapsed:.1f} 秒",
        "=" * 60,
    ])

    summary_out = os.path.join(output_dir, "molnetenhancer_summary.txt")
    with open(summary_out, "w", encoding="utf-8") as f:
        f.write("\n".join(summary))
    for line in summary:
        print(line)

    print(f"\n✅ [MolNetEnhancer] 分子网络增强注释完成!")
    print(f"   提示: 在 Cytoscape 中打开 enhanced_network.graphml，")
    print(f"   按 chemical_category 列着色即可看到化学类别分布。")

    # --- 生成图表 ---
    generate_network_figures(
        method="molnetenhancer",
        output_dir=output_dir,
        G=G,
        nodes_df=enh_nodes_df,
        title_prefix="MolNetEnhancer",
        color_by="chemical_category",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 网络分析可视化 — 生成出版物级图表
# ═══════════════════════════════════════════════════════════════════════════════
# 为四种网络分析方法（GNPS / FBMN / MS2LDA / MolNetEnhancer）生成标准图表，
# 包括网络拓扑图、分子家族分布、相似度分布、度数分布、
# 化学类别分布、Mass2Motif 碎片图等。
#
# 所有图均使用 matplotlib 渲染，项目中已通过 BLINK 引入 matplotlib。
# 输出 300 DPI PNG，适合直接用于论文发表。

import matplotlib
matplotlib.use("Agg")  # 非交互后端，服务器环境安全
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import Counter
from web_frontend.backend.export.editable_export import save_editable_figure

# 全局绘图风格
plt.rcParams.update({
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})

# 分子家族着色调色板（高对比度，最多 20 个）
FAMILY_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
    "#a65628", "#f781bf", "#999999", "#66c2a5", "#fc8d62",
]

# 化学类别专用调色板
CHEM_CLASS_PALETTE = {
    "Carbohydrates and carbohydrate conjugates": "#1b9e77",
    "Amino acids, peptides, and analogues":      "#d95f02",
    "Lipids and lipid-like molecules":            "#7570b3",
    "Flavonoids":                                 "#e7298a",
    "Terpenoids":                                 "#66a61e",
    "Alkaloids and derivatives":                  "#e6ab02",
    "Phenylpropanoids and polyketides":           "#a6761d",
    "Nucleosides, nucleotides, and analogues":    "#666666",
    "Benzenoids":                                 "#8dd3c7",
    "unknown":                                    "#bdbdbd",
}


# ======================== 底层绘图函数 ========================

def _get_family_color(family_id, family_list):
    """为分子家族分配颜色，singleton 用浅灰。"""
    if family_id == "singleton":
        return "#cccccc"
    try:
        idx = family_list.index(family_id)
        return FAMILY_PALETTE[idx % len(FAMILY_PALETTE)]
    except (ValueError, IndexError):
        return "#cccccc"


# ---------- 网络拓扑图 ----------

def _plot_network_topology(
    G,
    output_path,
    title="Molecular Network Topology",
    color_by="molecular_family",
    figsize=(14, 10),
):
    """
    渲染分子网络拓扑图，节点按分子家族着色，节点大小反映度数。

    小型网络（≤200 节点）使用 Kamada-Kawai 布局，大型网络使用 Spring 布局。
    """
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    if n_nodes == 0:
        print("    ⚠️ 图为空，跳过拓扑图渲染")
        return

    fig, ax = plt.subplots(figsize=figsize)

    # 布局选择
    if n_nodes <= 200:
        try:
            pos = nx.kamada_kawai_layout(G, weight=None)
        except Exception:
            pos = nx.spring_layout(G, k=2 / max(1, n_nodes ** 0.3), seed=42, iterations=50)
    else:
        pos = nx.spring_layout(G, k=1.5 / max(1, n_nodes ** 0.3), seed=42, iterations=30)

    # 统计家族大小
    family_sizes = {}
    for _node, attrs in G.nodes(data=True):
        fam = attrs.get(color_by, "singleton")
        family_sizes[fam] = family_sizes.get(fam, 0) + 1
    sorted_fams = sorted(
        [f for f in family_sizes if f != "singleton"],
        key=lambda f: family_sizes[f], reverse=True,
    )

    # 边（透明度按余弦相似度）
    edge_alphas = []
    for _u, _v, d in G.edges(data=True):
        cosine = d.get("cosine", 0.5)
        edge_alphas.append(max(0.05, min(0.5, cosine * 0.5)))
    if not edge_alphas:
        edge_alphas = [0.2]

    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color="#888888", alpha=edge_alphas, width=0.3,
    )

    # 按家族分组画节点
    for fam in sorted_fams:
        fam_nodes = [n for n, a in G.nodes(data=True) if a.get(color_by) == fam]
        if not fam_nodes:
            continue
        fam_color = _get_family_color(fam, sorted_fams)
        sizes = [max(15, min(200, G.degree(n) * 25 + 15)) for n in fam_nodes]
        nx.draw_networkx_nodes(
            G, pos, ax=ax, nodelist=fam_nodes,
            node_color=[fam_color] * len(fam_nodes),
            node_size=sizes, alpha=0.85,
            edgecolors="white", linewidths=0.3,
        )

    # singletons 最后画（灰色小点）
    singleton_nodes = [n for n, a in G.nodes(data=True) if a.get(color_by) == "singleton"]
    if singleton_nodes:
        nx.draw_networkx_nodes(
            G, pos, ax=ax, nodelist=singleton_nodes,
            node_color="#cccccc", node_size=10, alpha=0.4, edgecolors="none",
        )

    # 图例（top 10 家族 + singletons）
    legend_items = []
    for fam in sorted_fams[:10]:
        legend_items.append(mpatches.Patch(
            color=_get_family_color(fam, sorted_fams), alpha=0.85,
            label=f"{fam} (n={family_sizes[fam]})",
        ))
    if singleton_nodes:
        legend_items.append(mpatches.Patch(
            color="#cccccc", alpha=0.5,
            label=f"singleton (n={len(singleton_nodes)})",
        ))
    if len(sorted_fams) > 10:
        legend_items.append(mpatches.Patch(
            color="none", label=f"... +{len(sorted_fams) - 10} more families",
        ))

    ax.legend(
        handles=legend_items, loc="upper left",
        fontsize=7, framealpha=0.8, ncol=1,
        title="Molecular Families", title_fontsize=8,
    )

    ax.set_title(
        f"{title}\n{n_nodes} nodes, {n_edges} edges, "
        f"{len(sorted_fams)} families, {len(singleton_nodes)} singletons",
        fontsize=13, fontweight="bold",
    )
    ax.axis("off")
    fig.tight_layout()
    save_editable_figure(
        fig,
        output_path,
        title=title,
        skip_plotly=True,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)
    print(f"    ✅ 网络拓扑图: {output_path}")


# ---------- 分子家族大小分布 ----------

def _plot_family_size_distribution(
    G,
    output_path,
    title="Molecular Family Size Distribution",
    color_by="molecular_family",
    figsize=(10, 5),
):
    """绘制分子家族大小分布柱状图，singleton 在最右侧单独标注。"""
    families = {}
    for _node, attrs in G.nodes(data=True):
        fam = attrs.get(color_by, "singleton")
        families[fam] = families.get(fam, 0) + 1

    n_singletons = families.pop("singleton", 0)
    sorted_fams = sorted(families.items(), key=lambda x: x[1], reverse=True)
    if not sorted_fams and n_singletons == 0:
        print("    ⚠️ 无分子家族数据，跳过分布图")
        return

    fig, ax = plt.subplots(figsize=figsize)
    labels, sizes, colors = [], [], []
    for i, (fam, size) in enumerate(sorted_fams):
        labels.append(fam)
        sizes.append(size)
        colors.append(FAMILY_PALETTE[i % len(FAMILY_PALETTE)])

    if n_singletons > 0:
        labels.append("singleton")
        sizes.append(n_singletons)
        colors.append("#cccccc")

    # 超过 30 个家族则合并其余
    max_display = 30
    if len(sizes) > max_display:
        others = sum(sizes[max_display:])
        labels = labels[:max_display] + [f"others ({len(sizes) - max_display} families)"]
        sizes = sizes[:max_display] + [others]
        colors = colors[:max_display] + ["#999999"]

    bars = ax.bar(range(len(labels)), sizes, color=colors, edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars, sizes):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(sizes) * 0.01,
                    str(val), ha="center", va="bottom", fontsize=7)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Number of Nodes", fontsize=11)
    ax.set_xlabel("Molecular Family", fontsize=11)
    ax.set_title(
        f"{title}\n({len(sorted_fams)} families, {n_singletons} singletons)",
        fontsize=13, fontweight="bold",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    from web_frontend.backend.export.plotly_export import build_family_size_distribution_figure

    plotly_fig = None
    try:
        plotly_fig = build_family_size_distribution_figure(
            labels=labels,
            sizes=sizes,
            colors=colors,
            title=title,
            n_families=len(sorted_fams),
            n_singletons=n_singletons,
        )
    except Exception:
        pass
    save_editable_figure(
        fig,
        output_path,
        title=title,
        plotly_fig=plotly_fig,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)
    print(f"    ✅ 家族大小分布图: {output_path}")


# ---------- 余弦相似度分布 ----------

def _plot_cosine_distribution(
    edges_df,
    output_path,
    title="Cosine Similarity Distribution",
    cosine_col="cosine",
    figsize=(8, 5),
):
    """
    绘制 MS² 谱图间余弦相似度分布直方图，标注 GNPS 默认阈值 (0.7) 和中位数。

    用于评估过滤阈值的合理性：
    - 高峰在低值区 → 大部分代谢物结构不相似，网络稀疏是合理的
    - 高峰在高值区 → 数据中可能存在大量同系物/衍生物
    """
    if len(edges_df) == 0:
        print("    ⚠️ 无边数据，跳过相似度分布图")
        return
    cosines = edges_df[cosine_col].dropna().values
    if len(cosines) == 0:
        print("    ⚠️ 无有效余弦值，跳过")
        return

    fig, ax = plt.subplots(figsize=figsize)
    ax.hist(cosines, bins=40, color="#4c72b0", edgecolor="white",
            alpha=0.8, linewidth=0.5)

    median = np.median(cosines)
    ax.axvline(x=0.7, color="#d62728", linestyle="--", linewidth=1.5,
               label="GNPS default threshold (0.7)")
    ax.axvline(x=median, color="#ff7f0e", linestyle=":", linewidth=1.5,
               label=f"Median ({median:.3f})")

    ax.set_xlabel("Cosine Similarity", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.set_title(
        f"{title}\nn={len(cosines):,} edges, mean={np.mean(cosines):.3f}, "
        f"median={median:.3f}",
        fontsize=13, fontweight="bold",
    )
    ax.legend(fontsize=9, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    from web_frontend.backend.export.plotly_export import build_cosine_distribution_figure

    plotly_fig = None
    try:
        plotly_fig = build_cosine_distribution_figure(
            cosines=cosines,
            title=title,
            median=median,
        )
    except Exception:
        pass
    save_editable_figure(
        fig,
        output_path,
        title=title,
        plotly_fig=plotly_fig,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)
    print(f"    ✅ 余弦相似度分布图: {output_path}")


# ---------- 节点度数分布 ----------

def _plot_degree_distribution(
    G,
    output_path,
    title="Node Degree Distribution",
    figsize=(8, 5),
):
    """
    绘制节点度数分布直方图，标注平均度数。
    度数分布反映网络连通性特征：
    - 大量低度节点 + 少量 hub → scale-free 网络
    - 集中在某一区间 → 均匀网络
    """
    degrees = [d for _, d in G.degree()]
    if not degrees:
        print("    ⚠️ 无度数数据，跳过")
        return

    fig, ax = plt.subplots(figsize=figsize)
    max_deg = max(degrees)
    bins = range(0, max_deg + 2) if max_deg <= 20 else min(30, max_deg)

    ax.hist(degrees, bins=bins, color="#2ca02c", edgecolor="white",
            alpha=0.8, linewidth=0.5)

    avg_deg = np.mean(degrees)
    ax.axvline(x=avg_deg, color="#d62728", linestyle="--", linewidth=1.5,
               label=f"Mean degree ({avg_deg:.1f})")

    ax.set_xlabel("Degree (number of connections)", fontsize=11)
    ax.set_ylabel("Number of Nodes", fontsize=11)
    ax.set_title(
        f"{title}\nn={G.number_of_nodes()} nodes, "
        f"mean={avg_deg:.2f}, max={max_deg}, isolated={degrees.count(0)}",
        fontsize=13, fontweight="bold",
    )
    ax.legend(fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    from web_frontend.backend.export.plotly_export import build_degree_distribution_figure

    plotly_fig = None
    try:
        plotly_fig = build_degree_distribution_figure(
            degrees=degrees,
            title=title,
            avg_deg=float(avg_deg),
            max_deg=max_deg,
            isolated=degrees.count(0),
            n_nodes=G.number_of_nodes(),
        )
    except Exception:
        pass
    save_editable_figure(
        fig,
        output_path,
        title=title,
        plotly_fig=plotly_fig,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)
    print(f"    ✅ 度数分布图: {output_path}")


# ---------- FBMN 专用：Pearson 相关性 ----------

def _plot_pearson_r_distribution(
    edges_df,
    output_path,
    title="Pearson Correlation Distribution (FBMN)",
    figsize=(14, 5),
):
    """
    FBMN 专用：样本间强度 Pearson 相关系数分布 + Cosine vs Pearson r 散点图。

    左侧：Pearson r 分布直方图
    右侧：Cosine vs Pearson r 散点图，标注四个象限的边数
    """
    if len(edges_df) == 0 or "pearson_r" not in edges_df.columns:
        return
    pearson_vals = edges_df["pearson_r"].dropna().values
    nonzero = pearson_vals[pearson_vals != 0]
    if len(nonzero) == 0:
        print("    ⚠️ 无可计算 Pearson r 的有效边（需样本共用非零值 ≥ 3）")
        return

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # 左图：直方图
    ax1 = axes[0]
    ax1.hist(nonzero, bins=30, color="#9467bd", edgecolor="white",
             alpha=0.8, linewidth=0.5)
    ax1.axvline(x=0, color="#333333", linestyle="-", linewidth=1)
    ax1.axvline(x=0.5, color="#d62728", linestyle="--", linewidth=1, label="r = 0.5")
    med = np.median(nonzero)
    ax1.axvline(x=med, color="#ff7f0e", linestyle=":", linewidth=1.5,
                label=f"Median ({med:.3f})")
    ax1.set_xlabel("Pearson r", fontsize=11)
    ax1.set_ylabel("Frequency", fontsize=11)
    ax1.set_title(
        f"Pearson r Distribution\nn={len(nonzero):,} edges, mean={np.mean(nonzero):.3f}",
        fontsize=11, fontweight="bold",
    )
    ax1.legend(fontsize=8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # 右图：散点图
    ax2 = axes[1]
    if "cosine" in edges_df.columns:
        mask = edges_df["pearson_r"] != 0
        cos = edges_df.loc[mask, "cosine"].values
        pr = edges_df.loc[mask, "pearson_r"].values
        ax2.scatter(cos, pr, c="#4c72b0", alpha=0.3, s=8, edgecolors="none")
        ax2.set_xlabel("Cosine Similarity", fontsize=11)
        ax2.set_ylabel("Pearson r", fontsize=11)
        ax2.set_title(
            f"Cosine vs Pearson r\nn={len(cos):,} edges",
            fontsize=11, fontweight="bold",
        )
        ax2.axhline(y=0.5, color="#d62728", linestyle="--", linewidth=1, alpha=0.5)
        ax2.axvline(x=0.7, color="#d62728", linestyle="--", linewidth=1, alpha=0.5)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        if len(cos) > 0:
            q1 = ((cos >= 0.7) & (pr >= 0.5)).sum()
            q2 = ((cos >= 0.7) & (pr < 0.5)).sum()
            ax2.text(0.95, 0.95,
                     f"cos≥0.7, r≥0.5: {q1}\ncos≥0.7, r<0.5: {q2}",
                     transform=ax2.transAxes, ha="right", va="top", fontsize=8,
                     bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ Pearson 相关性图: {output_path}")


# ---------- MolNetEnhancer 专用：化学类别分布 ----------

def _plot_chemical_class_distribution(
    nodes_df,
    output_path,
    title="Chemical Class Distribution (MolNetEnhancer)",
    category_col="chemical_category",
    figsize=(12, 6),
):
    """
    MolNetEnhancer 专用：化学类别饼图 + 柱状图（区分直接注释 vs 传播注释）。

    左侧：饼图 — 各类别占比
    右侧：柱状图 — 各类别绝对数量，深浅色区分注释来源
    """
    if category_col not in nodes_df.columns:
        print(f"    ⚠️ 节点表缺少 '{category_col}' 列，跳过化学类别分布图")
        return

    cat_counts = Counter(nodes_df[category_col].dropna().values)
    if not cat_counts:
        print("    ⚠️ 无有效化学类别数据")
        return

    sorted_cats = sorted(cat_counts.items(), key=lambda x: (x[0] == "unknown", -x[1]))
    labels = [c[0] for c in sorted_cats]
    sizes = [c[1] for c in sorted_cats]
    colors = [CHEM_CLASS_PALETTE.get(lbl, "#bdbdbd") for lbl in labels]

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # --- 左图：饼图 ---
    ax1 = axes[0]
    total = sum(sizes)
    threshold_pct = 2.0
    main_labels, main_sizes, main_colors = [], [], []
    other_size = 0
    for lbl, s, c in zip(labels, sizes, colors):
        if s / total * 100 >= threshold_pct:
            main_labels.append(f"{lbl}\n({s}, {s / total * 100:.1f}%)")
            main_sizes.append(s)
            main_colors.append(c)
        else:
            other_size += s
    if other_size > 0:
        main_labels.append(f"Other ({other_size}, {other_size / total * 100:.1f}%)")
        main_sizes.append(other_size)
        main_colors.append("#d9d9d9")

    ax1.pie(
        main_sizes, labels=main_labels, colors=main_colors,
        autopct="", startangle=90, pctdistance=0.75,
        textprops={"fontsize": 7},
    )
    ax1.set_title(f"Chemical Class Composition\n(n={total} nodes)",
                  fontsize=12, fontweight="bold")

    # --- 右图：柱状图（直接 vs 传播）---
    ax2 = axes[1]
    if "category_confidence" in nodes_df.columns:
        direct_counts = Counter(
            nodes_df[nodes_df["category_confidence"].isin(["medium", "high"])][category_col].dropna()
        )
        prop_counts = Counter(
            nodes_df[nodes_df["category_confidence"] == "propagated"][category_col].dropna()
        )
    else:
        direct_counts, prop_counts = Counter(), Counter()

    top_n = min(15, len(sorted_cats))
    plot_cats = sorted_cats[:top_n]
    x_labels = [c[0] for c in plot_cats]
    direct_vals = [direct_counts.get(c[0], 0) for c in plot_cats]
    prop_vals = [prop_counts.get(c[0], 0) for c in plot_cats]

    x = range(len(x_labels))
    ax2.bar(x, direct_vals, 0.6, color="#4c72b0", label="Direct annotation",
            edgecolor="white", linewidth=0.5)
    ax2.bar(x, prop_vals, 0.6, bottom=direct_vals, color="#f0ad4e",
            label="Propagated", edgecolor="white", linewidth=0.5)

    for i, (d, p) in enumerate(zip(direct_vals, prop_vals)):
        total_bar = d + p
        if total_bar > 0:
            ax2.text(i, total_bar + max(1, max(direct_vals + prop_vals or [0])) * 0.02,
                     str(total_bar), ha="center", va="bottom", fontsize=7)

    ax2.set_xticks(list(x))
    ax2.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=7)
    ax2.set_ylabel("Number of Nodes", fontsize=11)
    ax2.set_title("Chemical Class by Annotation Type", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=9, loc="upper right")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ 化学类别分布图: {output_path}")


# ---------- MS2LDA 专用：Mass2Motif 碎片图 ----------

# 常见中性丢失（Da），用于标注
COMMON_NEUTRAL_LOSSES = {
    "H₂O": 18.0106,
    "NH₃": 17.0265,
    "CO": 27.9949,
    "CO₂": 43.9898,
    "HCOOH": 46.0055,
    "CH₃COOH": 60.0211,
    "CH₃OH": 32.0262,
    "C₂H₄": 28.0313,
    "SO₃": 79.9568,
    "H₃PO₄": 97.9769,
    "Hexose": 162.0528,
    "Deoxyhexose": 146.0579,
    "Pentose": 132.0423,
    "GlcA": 176.0321,
    "Malonyl": 86.0004,
}


def _plot_mass2motif_top_fragments(
    motif_df,
    output_path,
    title="Top Mass2Motifs — Fragment & Neutral Loss Patterns",
    top_motifs=9,
    top_frags_per_motif=15,
    precursor_mz_values=None,
    figsize=(18, 16),
):
    """
    MS2LDA 专用：多子图展示 top Mass2Motif 的碎片模式（mirror plot 风格）。

    上半部分（红色 ↑）= 碎片离子 m/z，表示质谱碎裂产生的离子
    下半部分（绿色 ↓）= 中性丢失，即 precursor_mz - fragment_mz，
                         揭示从分子离去的化学基团

    这个设计与官方 MS2LDA PDF 报告一致：
    - 碎片峰 (red, pointing up)
    - 中性丢失 (green, pointing down)

    Parameters
    ----------
    precursor_mz_values : list of float or None
        所有输入谱图的前体离子 m/z 列表。用于计算中性丢失。
        如果为 None，使用碎片 m/z 的 3 倍作为近似前体质量。
    """
    if motif_df is None or len(motif_df) == 0:
        print("    ⚠️ 无 Mass2Motif 数据")
        return

    n_show = min(top_motifs, len(motif_df))
    if "top_fragments" not in motif_df.columns:
        print("    ⚠️ motif 表缺少 top_fragments 列")
        return

    # 确定参考前体质量（用于计算中性丢失）
    if precursor_mz_values and len(precursor_mz_values) > 0:
        ref_precursor = np.median(precursor_mz_values)
    else:
        ref_precursor = None  # 将从碎片最大 m/z 推断

    n_cols = 3
    n_rows = int(np.ceil(n_show / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    axes = axes.flatten() if n_rows * n_cols > 1 else [axes]

    for idx in range(n_show):
        ax = axes[idx]
        row = motif_df.iloc[idx]
        try:
            frags = json.loads(row["top_fragments"]) if isinstance(row["top_fragments"], str) else row["top_fragments"]
        except (json.JSONDecodeError, TypeError, KeyError):
            ax.set_visible(False)
            continue
        if not frags:
            ax.set_visible(False)
            continue

        frags = frags[:top_frags_per_motif]
        mz_vals = np.array([f["mz"] for f in frags])
        prob_vals = np.array([f["probability"] for f in frags])
        max_prob = prob_vals.max() if len(prob_vals) > 0 else 1.0

        # 确定该 motif 的前体质量参考值
        if ref_precursor is not None:
            p_mz = ref_precursor
        else:
            # 推测：碎片中最大 m/z 的 1.2 倍
            p_mz = mz_vals.max() * 1.2

        # 计算中性丢失
        neutral_losses = p_mz - mz_vals
        # 仅保留正的中性丢失（碎片 m/z 小于前体质量）
        valid_nl = neutral_losses > 0

        # ---- 上半部分：碎片离子（红色 ↑）----
        for mz_val, prob in zip(mz_vals, prob_vals):
            norm_prob = prob / max_prob
            ax.vlines(mz_val, 0, norm_prob, color="#c0392b",
                      linewidth=max(0.8, norm_prob * 4), alpha=max(0.5, norm_prob))

        # 标注 top 3 碎片 m/z
        sorted_frags = sorted(frags, key=lambda x: x["probability"], reverse=True)
        for frag in sorted_frags[:3]:
            ax.annotate(
                f"{frag['mz']:.2f}",
                xy=(frag["mz"], frag["probability"] / max_prob),
                xytext=(0, 6), textcoords="offset points",
                fontsize=5.5, ha="center", rotation=90, color="#c0392b",
            )

        # ---- 下半部分：中性丢失（绿色 ↓）----
        if valid_nl.any():
            nl_vals = neutral_losses[valid_nl]
            nl_probs = prob_vals[valid_nl]
            nl_max = nl_probs.max() if len(nl_probs) > 0 else 1.0

            for nl_val, prob in zip(nl_vals, nl_probs):
                norm_prob = prob / nl_max
                ax.vlines(nl_val, 0, -norm_prob, color="#27ae60",
                          linewidth=max(0.8, norm_prob * 4), alpha=max(0.5, norm_prob))

            # 标注已知中性丢失
            xlim = ax.get_xlim()
            nl_tolerance = (xlim[1] - xlim[0]) * 0.02
            for loss_name, loss_mass in COMMON_NEUTRAL_LOSSES.items():
                if xlim[0] <= loss_mass <= xlim[1]:
                    # 检查是否有实际中性丢失接近此值
                    nearby = np.abs(nl_vals - loss_mass) < nl_tolerance
                    if nearby.any():
                        ax.axvline(x=loss_mass, color="#27ae60", linestyle=":",
                                   linewidth=0.5, alpha=0.6)
                        ax.annotate(loss_name, xy=(loss_mass, -0.85),
                                    fontsize=5, ha="center", color="#27ae60",
                                    rotation=90)

        # 零线
        ax.axhline(y=0, color="#333333", linewidth=0.8)

        # 标注参考前体质量
        ax.annotate(f"precursor ~{p_mz:.1f} Da",
                    xy=(0.95, 0.95), xycoords="axes fraction",
                    ha="right", va="top", fontsize=5.5,
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#f5f5f5", alpha=0.7))

        motif_id = row.get("motif_id", f"Motif_{idx + 1}")
        load_val = row.get("total_load", 0)
        nspec = row.get("n_top_spectra", 0)
        ax.set_title(
            f"{motif_id}  load={load_val:.1f}, N={nspec}",
            fontsize=7, fontweight="bold",
        )
        ax.set_xlabel("m/z or Δm/z (Da)", fontsize=6)
        ax.set_ylabel("↑ frag  ↓ loss", fontsize=6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(labelsize=5.5)
        ax.set_ylim(-1.15, 1.15)

        # 图例（仅第一个子图）
        if idx == 0:
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], color="#c0392b", lw=2, label="Fragment ions"),
                Line2D([0], [0], color="#27ae60", lw=2, label="Neutral losses"),
            ]
            ax.legend(handles=legend_elements, fontsize=5.5, loc="upper left")

    for idx in range(n_show, len(axes)):
        axes[idx].set_visible(False)

    fig.suptitle(
        f"{title}\nTop {n_show} Mass2Motifs — Fragment Ions (red↑) & Neutral Losses (green↓)",
        fontsize=14, fontweight="bold", y=1.01,
    )
    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ Mass2Motif 碎片图 (mirror plot): {output_path}")


# ---------- MS2LDA 专用：谱图-Motif 关联热图 ----------

def _plot_motif_spectrum_association_heatmap(
    spectra_motif_scores_csv,
    output_path,
    title="Spectrum–Mass2Motif Association",
    top_spectra=50,
    top_motifs=20,
    figsize=(16, 10),
):
    """
    MS2LDA 专用：谱图 × Mass2Motif 关联概率热图。

    行 = top 谱图（按 motif 总得分排序），列 = top motif（按总载荷排序）。
    颜色深浅 = P(motif | spectrum)。
    """
    if not os.path.isfile(spectra_motif_scores_csv):
        print(f"    ⚠️ 谱图-Motif 分数文件未找到: {spectra_motif_scores_csv}")
        return

    sm_df = pd.read_csv(spectra_motif_scores_csv, index_col=0)
    if sm_df.empty:
        return

    motif_cols = [c for c in sm_df.columns if c.startswith("Motif_")]
    if not motif_cols:
        return
    motif_sums = sm_df[motif_cols].sum(axis=0).sort_values(ascending=False)
    top_m_cols = motif_sums.head(top_motifs).index.tolist()

    sm_df["_score"] = sm_df[top_m_cols].sum(axis=1)
    top_s_df = sm_df.nlargest(top_spectra, "_score")
    sm_df.drop(columns=["_score"], inplace=True, errors="ignore")

    data = top_s_df[top_m_cols].values

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(data, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    ax.set_xticks(range(len(top_m_cols)))
    ax.set_xticklabels([c.replace("Motif_", "M") for c in top_m_cols],
                       rotation=90, fontsize=6)
    ax.set_yticks(range(min(top_spectra, len(top_s_df))))
    ax.set_yticklabels(top_s_df.index[:top_spectra], fontsize=5)
    ax.set_xlabel("Mass2Motif", fontsize=11)
    ax.set_ylabel("Feature / Spectrum", fontsize=11)
    ax.set_title(
        f"{title}\n{min(top_spectra, len(top_s_df))} spectra × {len(top_m_cols)} motifs",
        fontsize=13, fontweight="bold",
    )
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("P(motif | spectrum)", fontsize=9)
    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ Motif 关联热图: {output_path}")


# ---------- 前体质量差分布（GNPS / FBMN 共用）----------

# 常见化学变换对应的 Δm/z（用于标注）
KNOWN_TRANSFORMATIONS = {
    # 甲基化/去甲基化
    "±CH₂": 14.0157,
    # 羟基化
    "±O": 15.9949,
    # 氨失
    "−NH₃": 17.0265,
    # 水失
    "−H₂O": 18.0106,
    # CO 失
    "−CO": 27.9949,
    # CO₂ 失
    "−CO₂": 43.9898,
    # 甲酸失
    "−HCOOH": 46.0055,
    # 乙酸失
    "−CH₃COOH": 60.0211,
    # 甘氨酸
    "±C₂H₃NO": 57.0215,
    # 丙氨酸
    "±C₃H₅NO": 71.0371,
    # 硫酸化
    "±SO₃": 79.9568,
    # 磷酸化
    "±H₃PO₄": 97.9769,
    # 半胱氨酸
    "±C₃H₅NOS": 103.0092,
    # 己糖（葡萄糖/半乳糖）
    "±Hexose": 162.0528,
    # 脱氧己糖（鼠李糖/岩藻糖）
    "±Deoxyhexose": 146.0579,
    # 戊糖
    "±Pentose": 132.0423,
    # 葡萄糖醛酸
    "±GlcA": 176.0321,
    # 丙二酰
    "±Malonyl": 86.0004,
    # 乙酰基
    "±Acetyl": 42.0106,
    # 香豆酰
    "±Coumaroyl": 146.0368,
    # 咖啡酰
    "±Caffeoyl": 162.0317,
    # 阿魏酰
    "±Feruloyl": 176.0473,
    # 二糖
    "±Disaccharide": 324.1056,
    # 谷胱甘肽
    "±Glutathione": 305.0682,
    # 牛磺酸
    "±Taurine": 107.0035,
    # 肉碱
    "±Carnitine": 161.1049,
}


def _precursor_mass_diff_payload(G):
    """Collect filtered Δm/z values and top annotated transformations."""
    mass_diffs = []
    for u, v in G.edges():
        mz_u = G.nodes[u].get("precursor_mz")
        mz_v = G.nodes[v].get("precursor_mz")
        if mz_u and mz_v and mz_u > 0 and mz_v > 0:
            mass_diffs.append(abs(float(mz_u) - float(mz_v)))

    if len(mass_diffs) < 5:
        return None

    mass_diffs = np.array(mass_diffs, dtype=float)
    mass_diffs = mass_diffs[(mass_diffs >= 0.1) & (mass_diffs <= 600)]
    if mass_diffs.size < 5:
        return None

    nearby_transforms: dict[str, tuple[float, int]] = {}
    for name, delta in KNOWN_TRANSFORMATIONS.items():
        if 0 <= delta <= mass_diffs.max():
            count = int(((mass_diffs >= delta - 0.5) & (mass_diffs <= delta + 0.5)).sum())
            if count > 0:
                nearby_transforms[name] = (float(delta), count)

    sorted_transforms = sorted(
        nearby_transforms.items(),
        key=lambda item: item[1][1],
        reverse=True,
    )[:15]
    annotated = [(name, delta, count) for name, (delta, count) in sorted_transforms]
    return mass_diffs, annotated


def _plot_precursor_mass_difference(
    G,
    output_path,
    title="Precursor Mass Difference Distribution",
    figsize=(14, 6),
):
    """
    绘制连接节点间前体离子质量差（Δm/z）分布直方图。

    质量差反映了可能的化学变换关系（如糖基化 +162 Da、甲基化 +14 Da 等），
    是 GNPS 分子网络分析中识别代谢物结构关联的重要手段。

    标注已知的常见化学变换位置，帮助快速识别数据中的主要代谢转化模式。
    """
    payload = _precursor_mass_diff_payload(G)
    if payload is None:
        print("    ⚠️ 不足 5 个有效前体质量差，跳过")
        return

    mass_diffs, sorted_transforms = payload

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # --- 左图：全范围直方图 ---
    ax1 = axes[0]
    ax1.hist(mass_diffs, bins=60, color="#4c72b0", edgecolor="white",
             alpha=0.8, linewidth=0.5)
    ax1.set_xlabel("Δm/z (Da)", fontsize=11)
    ax1.set_ylabel("Frequency", fontsize=11)
    ax1.set_title(
        f"Precursor Mass Differences\nn={len(mass_diffs)} edges, "
        f"median={np.median(mass_diffs):.2f} Da",
        fontsize=11, fontweight="bold",
    )
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # --- 右图：标注已知化学变换 ---
    ax2 = axes[1]
    colors_transform = plt.cm.tab10.colors
    y_max = np.histogram(mass_diffs, bins=80)[0].max()

    ax2.hist(mass_diffs, bins=80, color="#888888", edgecolor="white",
             alpha=0.3, linewidth=0.3)
    ax2.set_xlabel("Δm/z (Da)", fontsize=11)
    ax2.set_ylabel("Frequency", fontsize=11)
    ax2.set_title(
        "Annotated with Known Transformations",
        fontsize=11, fontweight="bold",
    )

    for i, (name, delta, count) in enumerate(sorted_transforms):
        color = colors_transform[i % len(colors_transform)]
        ax2.axvline(x=delta, color=color, linestyle="--", linewidth=1.2, alpha=0.8)
        ax2.annotate(
            f"  {name}\n  ({delta:.1f} Da, n={count})",
            xy=(delta, y_max * 0.95),
            xytext=(delta + 5, y_max * (0.95 - i * 0.07)),
            fontsize=6, color=color,
            arrowprops=dict(arrowstyle="->", color=color, lw=0.5),
        )

    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    from web_frontend.backend.export.plotly_export import build_precursor_mass_diff_figure

    plotly_fig = None
    try:
        plotly_fig = build_precursor_mass_diff_figure(
            mass_diffs=mass_diffs,
            title=title,
            annotated_transforms=sorted_transforms,
        )
    except Exception:
        pass
    save_editable_figure(
        fig,
        output_path,
        title=title,
        plotly_fig=plotly_fig,
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)
    print(f"    ✅ 前体质量差分布图: {output_path}")


# ---------- FBMN 专用：样本组强度对比 ----------

def _plot_fbmn_group_intensity(
    G,
    output_path,
    title="FBMN — Group Intensity Comparison",
    top_families=8,
    figsize=(14, 8),
):
    """
    FBMN 专用：对 top 分子家族，展示每个家族在两组间的平均强度对比。

    使用分组柱状图（grouped bar chart），展示各家族在实验组和对照组的
    mean ± 范围，帮助识别在特定条件下共调控的代谢物家族。
    """
    # 提取组信息
    group_keys = set()
    for node, attrs in G.nodes(data=True):
        for k in attrs:
            if k.startswith("mean_"):
                group_keys.add(k.replace("mean_", ""))

    if len(group_keys) < 2:
        print("    ⚠️ 需要至少 2 个样本组才能生成组强度对比图")
        return

    group_keys = sorted(group_keys)

    # 按家族聚合
    family_groups = {}
    family_sizes = {}
    for node, attrs in G.nodes(data=True):
        fam = attrs.get("molecular_family", "singleton")
        if fam == "singleton":
            continue
        family_sizes[fam] = family_sizes.get(fam, 0) + 1
        if fam not in family_groups:
            family_groups[fam] = {g: [] for g in group_keys}
        for g in group_keys:
            val = attrs.get(f"mean_{g}", 0)
            if val is not None and val > 0:
                family_groups[fam][g].append(val)

    if not family_groups:
        print("    ⚠️ 无有效分子家族数据")
        return

    # 计算每个家族的组均值
    family_stats = {}
    for fam, group_data in family_groups.items():
        stats = {}
        for g, vals in group_data.items():
            if vals:
                stats[g] = {
                    "mean": np.mean(vals),
                    "std": np.std(vals) if len(vals) > 1 else 0,
                    "n": len(vals),
                }
            else:
                stats[g] = {"mean": 0, "std": 0, "n": 0}
        # 计算组间差值（用于排序）
        means = [stats[g]["mean"] for g in group_keys[:2]]
        fold_change = abs(means[0] - means[1]) if len(means) >= 2 else 0
        family_stats[fam] = {"stats": stats, "fold_change": fold_change}

    # 按组间差异降序取 top 家族
    sorted_fams = sorted(family_stats.items(),
                         key=lambda x: x[1]["fold_change"], reverse=True)
    show_fams = sorted_fams[:top_families]

    fig, ax = plt.subplots(figsize=figsize)
    n_fams = len(show_fams)
    n_groups = len(group_keys[:2])  # 比较前两组
    bar_width = 0.35
    x = np.arange(n_fams)

    for g_idx, g in enumerate(group_keys[:2]):
        means = [fs[1]["stats"][g]["mean"] for fs in show_fams]
        stds = [fs[1]["stats"][g]["std"] for fs in show_fams]
        offset = (g_idx - n_groups / 2 + 0.5) * bar_width
        color = "#4c72b0" if g_idx == 0 else "#c44e52"
        bars = ax.bar(x + offset, means, bar_width, yerr=stds,
                      color=color, alpha=0.85, edgecolor="white",
                      linewidth=0.5, capsize=3, label=g,
                      error_kw={"linewidth": 0.8})

    # 标注 log2FC
    for i, (fam, fs) in enumerate(show_fams):
        m0 = fs["stats"][group_keys[0]]["mean"]
        m1 = fs["stats"][group_keys[1]]["mean"]
        if m0 > 0 and m1 > 0:
            log2fc = np.log2((m1 + 1) / (m0 + 1))
            direction = "↑" if log2fc > 0 else "↓"
            max_h = max(m0, m1) + max(fs["stats"][group_keys[0]]["std"],
                                       fs["stats"][group_keys[1]]["std"])
            ax.text(i, max_h + max(means) * 0.02,
                    f"FC{direction}{2 ** abs(log2fc):.1f}",
                    ha="center", fontsize=7, fontweight="bold",
                    color="#c44e52" if log2fc > 0 else "#4c72b0")

    family_labels = [f"{fam}\n(n={family_sizes.get(fam, '?')})"
                     for fam, _ in show_fams]
    ax.set_xticks(x)
    ax.set_xticklabels(family_labels, fontsize=7)
    ax.set_ylabel("Mean Intensity", fontsize=11)
    ax.set_xlabel("Molecular Family", fontsize=11)
    ax.set_title(
        f"{title}\nTop {n_fams} families by group difference, "
        f"{len(family_groups)} total families",
        fontsize=12, fontweight="bold",
    )
    ax.legend(fontsize=9, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ FBMN 组强度对比图: {output_path}")


# ---------- MS2LDA 专用：Mass2Motif 总览 ----------

def _plot_mass2motif_overview(
    motif_df,
    output_path,
    title="Mass2Motif Overview — Load & Spectrum Coverage",
    top_motifs=30,
    figsize=(14, 6),
):
    """
    MS2LDA 专用：Mass2Motif 总览柱状图。

    展示 top N Motif 的 total_load（所有谱图中的累计概率质量），
    颜色表示关联的谱图数 (n_top_spectra)，帮助快速识别
    最重要的、广泛存在的亚结构模式。
    """
    if motif_df is None or len(motif_df) == 0:
        print("    ⚠️ 无 Mass2Motif 数据，跳过总览图")
        return

    show_n = min(top_motifs, len(motif_df))
    sub = motif_df.head(show_n).copy()
    # 反转使最大的在顶部
    sub = sub.iloc[::-1]

    fig, ax = plt.subplots(figsize=figsize)

    loads = sub["total_load"].values
    n_spec = sub["n_top_spectra"].values
    motif_ids = [row["motif_id"].replace("Motif_", "M")
                 for _, row in sub.iterrows()]

    # 按 n_top_spectra 着色
    norm = plt.Normalize(vmin=n_spec.min(), vmax=n_spec.max())
    cmap = plt.cm.YlOrRd
    colors_bar = cmap(norm(n_spec))

    bars = ax.barh(range(len(sub)), loads, color=colors_bar,
                   edgecolor="white", linewidth=0.5)

    # 数值标注
    for i, (load, nsp) in enumerate(zip(loads, n_spec)):
        ax.text(load + loads.max() * 0.01, i,
                f"load={load:.1f}, N={nsp}",
                va="center", fontsize=6)

    ax.set_yticks(range(len(sub)))
    ax.set_yticklabels(motif_ids, fontsize=7)
    ax.set_xlabel("Total Load (sum of P(motif | spectrum))", fontsize=11)
    ax.set_title(
        f"{title}\nTop {show_n} Mass2Motifs by total load "
        f"({len(motif_df)} total, {motif_df['n_top_spectra'].gt(0).sum()} active)",
        fontsize=12, fontweight="bold",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # colorbar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.6)
    cbar.set_label("N associated spectra", fontsize=9)

    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ Mass2Motif 总览图: {output_path}")


# ---------- MS2LDA 专用：Motif-谱图关联网络图 ----------

def _plot_mass2motif_network(
    motif_df,
    spectra_motif_scores_csv,
    output_path,
    title="Mass2Motif–Spectrum Association Network",
    top_motifs=15,
    score_threshold=0.1,
    figsize=(16, 12),
):
    """
    MS2LDA 专用：Mass2Motif × 谱图 的关联网络图。

    圆形节点 = Mass2Motif（大小 ∝ total_load，颜色 = 不同 motif）
    方形节点 = 谱图（小方块，仅显示与 top motif 有强关联的）
    边 = P(motif | spectrum) > score_threshold

    这个可视化帮助理解哪些谱图共享哪些亚结构模式。
    """
    if motif_df is None or len(motif_df) == 0:
        print("    ⚠️ 无 Mass2Motif 数据，跳过网络图")
        return
    if not spectra_motif_scores_csv or not os.path.isfile(spectra_motif_scores_csv):
        print("    ⚠️ 谱图-Motif 分数文件未找到，跳过网络图")
        return

    sm_df = pd.read_csv(spectra_motif_scores_csv, index_col=0)
    if sm_df.empty:
        return

    motif_cols = [c for c in sm_df.columns if c.startswith("Motif_")]
    if not motif_cols:
        return

    # 选出 top motifs
    top_motif_ids = motif_df.head(top_motifs)["motif_id"].tolist()
    # 确保列名匹配
    valid_motif_cols = [c for c in motif_cols if c in top_motif_ids]
    if not valid_motif_cols:
        return

    # 找出与这些 motif 有强关联的谱图
    sm_sub = sm_df[valid_motif_cols]
    sm_sub["_max_score"] = sm_sub.max(axis=1)
    active_spectra = sm_sub[sm_sub["_max_score"] >= score_threshold]

    if len(active_spectra) == 0:
        print(f"    ⚠️ 无谱图满足 score ≥ {score_threshold}，跳过网络图")
        return

    # 限制节点数
    max_spectra = 100
    if len(active_spectra) > max_spectra:
        active_spectra = active_spectra.nlargest(max_spectra, "_max_score")

    # 构建 bipartite 网络布局
    motif_nodes = []
    spectrum_nodes = []
    pos = {}

    # Motif 节点分布在大圆上
    n_m = len(valid_motif_cols)
    radius_m = 1.5
    for i, mcol in enumerate(valid_motif_cols):
        angle = 2 * np.pi * i / n_m - np.pi / 2
        node_id = f"motif:{mcol}"
        motif_nodes.append(node_id)
        pos[node_id] = (radius_m * np.cos(angle), radius_m * np.sin(angle))

    # 谱图节点分布在更大的圆上
    n_s = len(active_spectra)
    radius_s = 3.5
    for i, spec_id in enumerate(active_spectra.index):
        angle = 2 * np.pi * i / n_s - np.pi / 2
        node_id = f"spec:{spec_id}"
        spectrum_nodes.append(node_id)
        pos[node_id] = (radius_s * np.cos(angle), radius_s * np.sin(angle))

    fig, ax = plt.subplots(figsize=figsize)

    # 计算 motif 节点大小
    motif_loads = {}
    for mcol in valid_motif_cols:
        motif_id = mcol
        match = motif_df[motif_df["motif_id"] == motif_id]
        if len(match) > 0:
            motif_loads[motif_id] = match.iloc[0]["total_load"]
        else:
            motif_loads[motif_id] = 1
    max_load = max(motif_loads.values()) if motif_loads else 1

    # 绘制边（从谱图到 motif）
    edge_count = 0
    for spec_idx, spec_id in enumerate(active_spectra.index):
        spec_node = f"spec:{spec_id}"
        for mcol in valid_motif_cols:
            score = active_spectra.loc[spec_id, mcol]
            if score >= score_threshold:
                motif_node = f"motif:{mcol}"
                alpha = max(0.1, min(0.6, score * 0.8))
                ax.plot([pos[spec_node][0], pos[motif_node][0]],
                        [pos[spec_node][1], pos[motif_node][1]],
                        color="#aaaaaa", alpha=alpha, linewidth=0.3, zorder=1)
                edge_count += 1

    # 绘制谱图节点（小方块）
    spec_x = [pos[n][0] for n in spectrum_nodes]
    spec_y = [pos[n][1] for n in spectrum_nodes]
    ax.scatter(spec_x, spec_y, c="#4c72b0", s=15, marker="s",
               alpha=0.6, edgecolors="none", zorder=2, label="Spectra")

    # 绘制 motif 节点（圆）
    motif_colors = plt.cm.Set3.colors
    for i, mcol in enumerate(valid_motif_cols):
        node_id = f"motif:{mcol}"
        size = max(80, min(800, motif_loads.get(mcol, 1) / max_load * 600))
        motif_label = mcol.replace("Motif_", "M")
        ax.scatter(pos[node_id][0], pos[node_id][1],
                   c=[motif_colors[i % len(motif_colors)]],
                   s=size, marker="o", alpha=0.9, edgecolors="white",
                   linewidths=1, zorder=3)
        ax.annotate(motif_label, xy=pos[node_id], fontsize=6,
                    ha="center", va="center", fontweight="bold")

    ax.set_title(
        f"{title}\n{len(valid_motif_cols)} motifs, {len(spectrum_nodes)} spectra, "
        f"{edge_count} edges (score ≥ {score_threshold})",
        fontsize=12, fontweight="bold",
    )
    ax.legend(fontsize=8, loc="upper left")
    ax.axis("equal")
    ax.axis("off")
    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ Motif-谱图关联网络图: {output_path}")


# ---------- MolNetEnhancer 专用：分子家族化学一致性 ----------

def _plot_family_chemical_consensus(
    nodes_df,
    G,
    output_path,
    title="Molecular Family Chemical Consensus (MolNetEnhancer)",
    top_families=12,
    figsize=(16, 8),
):
    """
    MolNetEnhancer 专用：top 分子家族的化学类别堆叠柱状图。

    每个柱子 = 一个分子家族，颜色 = 化学类别，高度 = 节点数。
    在柱顶标注共识类别比例（类似 MolNetEnhancer 的 CF_subclass_score）。

    这个可视化直接对应 MolNetEnhancer 的核心输出——
    展示每个分子家族中化学分类的一致程度。
    """
    if nodes_df is None or len(nodes_df) == 0:
        print("    ⚠️ 无节点数据，跳过化学一致性图")
        return

    if "chemical_category" not in nodes_df.columns:
        print("    ⚠️ 缺少 chemical_category 列")
        return

    # 按家族聚合
    family_col = "molecular_family" if "molecular_family" in nodes_df.columns else None
    if family_col is None:
        print("    ⚠️ 缺少 molecular_family 列")
        return

    # 排除 singletons
    families_data = {}
    for _, row in nodes_df.iterrows():
        fam = row[family_col]
        if fam == "singleton" or pd.isna(fam):
            continue
        cat = row.get("chemical_category", "unknown")
        if pd.isna(cat):
            cat = "unknown"
        families_data.setdefault(fam, {}).setdefault(cat, 0)
        families_data[fam][cat] += 1

    if not families_data:
        print("    ⚠️ 无有效分子家族数据")
        return

    # 按家族大小排序，取 top
    fam_sizes = {fam: sum(cats.values()) for fam, cats in families_data.items()}
    sorted_fams = sorted(fam_sizes, key=fam_sizes.get, reverse=True)[:top_families]

    # 收集所有出现的类别
    all_cats = set()
    for fam in sorted_fams:
        all_cats.update(families_data[fam].keys())
    all_cats = sorted(all_cats, key=lambda c: (
        c == "unknown",
        -sum(families_data.get(fam, {}).get(c, 0) for fam in sorted_fams)
    ))

    fig, ax = plt.subplots(figsize=figsize)

    x = np.arange(len(sorted_fams))
    bar_width = 0.7
    bottom = np.zeros(len(sorted_fams))

    for cat in all_cats:
        vals = [families_data[fam].get(cat, 0) for fam in sorted_fams]
        color = CHEM_CLASS_PALETTE.get(cat, "#bdbdbd")
        ax.bar(x, vals, bar_width, bottom=bottom, color=color,
               edgecolor="white", linewidth=0.5, label=cat)
        bottom += np.array(vals)

    # 标注共识分数
    for i, fam in enumerate(sorted_fams):
        total = fam_sizes[fam]
        cats_in_fam = families_data[fam]
        if cats_in_fam:
            consensus_cat = max(cats_in_fam, key=cats_in_fam.get)
            consensus_n = cats_in_fam[consensus_cat]
            score = consensus_n / total  # CF_subclass_score 类比
            ax.text(i, total + max(fam_sizes.values()) * 0.02,
                    f"score={score:.2f}\n({consensus_cat})",
                    ha="center", fontsize=6, fontweight="bold",
                    color="#333333")

    family_labels = [f"{fam}\n(n={fam_sizes[fam]})" for fam in sorted_fams]
    ax.set_xticks(x)
    ax.set_xticklabels(family_labels, fontsize=7)
    ax.set_ylabel("Number of Nodes", fontsize=11)
    ax.set_xlabel("Molecular Family", fontsize=11)
    ax.set_title(
        f"{title}\nTop {len(sorted_fams)} families, "
        f"{len(all_cats)} chemical classes",
        fontsize=12, fontweight="bold",
    )
    ax.legend(fontsize=7, loc="upper right", ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ 分子家族化学一致性图: {output_path}")


# ---------- MolNetEnhancer 专用：注释传播总结 ----------

def _plot_annotation_propagation_summary(
    nodes_df,
    output_path,
    title="Annotation Propagation Summary (MolNetEnhancer)",
    figsize=(14, 6),
):
    """
    MolNetEnhancer 专用：注释传播总结图。

    左侧饼图：direct annotation vs propagated vs unknown 的占比。
    右侧柱状图：每个化学类别的注释来源分解（direct vs propagated）。

    对应 MolNetEnhancer 官方输出中的 annotation coverage 统计。
    """
    if nodes_df is None or len(nodes_df) == 0:
        print("    ⚠️ 无节点数据")
        return

    if "chemical_category" not in nodes_df.columns:
        print("    ⚠️ 缺少 chemical_category 列")
        return

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # --- 左图：注释来源饼图 ---
    ax1 = axes[0]
    total = len(nodes_df)

    n_direct = 0
    n_propagated = 0
    n_unknown = 0

    if "category_confidence" in nodes_df.columns:
        n_direct = (nodes_df["category_confidence"].isin(["medium", "high"])).sum()
        n_propagated = (nodes_df["category_confidence"] == "propagated").sum()
    elif "has_direct_annotation" in nodes_df.columns:
        n_direct = nodes_df["has_direct_annotation"].sum()
        n_propagated = ((~nodes_df["has_direct_annotation"]) &
                        (nodes_df["chemical_category"] != "unknown")).sum()

    n_unknown = total - n_direct - n_propagated

    pie_sizes = []
    pie_labels = []
    pie_colors = []
    if n_direct > 0:
        pie_sizes.append(n_direct)
        pie_labels.append(f"Direct annotation\n({n_direct}, {n_direct/total*100:.1f}%)")
        pie_colors.append("#2ca02c")
    if n_propagated > 0:
        pie_sizes.append(n_propagated)
        pie_labels.append(f"Propagated\n({n_propagated}, {n_propagated/total*100:.1f}%)")
        pie_colors.append("#ff7f0e")
    if n_unknown > 0:
        pie_sizes.append(n_unknown)
        pie_labels.append(f"Unknown\n({n_unknown}, {n_unknown/total*100:.1f}%)")
        pie_colors.append("#bdbdbd")

    if pie_sizes:
        ax1.pie(pie_sizes, labels=pie_labels, colors=pie_colors,
                startangle=90, textprops={"fontsize": 8})
    ax1.set_title(
        f"Annotation Coverage\nn={total} total nodes",
        fontsize=12, fontweight="bold",
    )

    # --- 右图：按类别分解 ---
    ax2 = axes[1]
    cat_direct = Counter()
    cat_prop = Counter()

    for _, row in nodes_df.iterrows():
        cat = row.get("chemical_category", "unknown")
        if pd.isna(cat):
            cat = "unknown"

        if "category_confidence" in nodes_df.columns:
            conf = row["category_confidence"]
            if conf in ("medium", "high"):
                cat_direct[cat] += 1
            elif conf == "propagated":
                cat_prop[cat] += 1
        elif "has_direct_annotation" in nodes_df.columns:
            if row["has_direct_annotation"]:
                cat_direct[cat] += 1
            elif cat != "unknown":
                cat_prop[cat] += 1

    # 合并所有类别，按总数排序
    all_cats_set = set(list(cat_direct.keys()) + list(cat_prop.keys()))
    cat_totals = {c: cat_direct.get(c, 0) + cat_prop.get(c, 0) for c in all_cats_set}
    sorted_cats = sorted(cat_totals, key=cat_totals.get, reverse=True)
    top_cats = sorted_cats[:12]

    x = np.arange(len(top_cats))
    bar_w = 0.6
    direct_vals = [cat_direct.get(c, 0) for c in top_cats]
    prop_vals = [cat_prop.get(c, 0) for c in top_cats]

    ax2.bar(x, direct_vals, bar_w, color="#2ca02c", label="Direct",
            edgecolor="white", linewidth=0.5)
    ax2.bar(x, prop_vals, bar_w, bottom=direct_vals, color="#ff7f0e",
            label="Propagated", edgecolor="white", linewidth=0.5)

    for i, (d, p) in enumerate(zip(direct_vals, prop_vals)):
        if d + p > 0:
            ax2.text(i, d + p + max(1, max(direct_vals + prop_vals or [0])) * 0.02,
                     str(d + p), ha="center", fontsize=7)

    ax2.set_xticks(x)
    ax2.set_xticklabels(top_cats, rotation=45, ha="right", fontsize=7)
    ax2.set_ylabel("Number of Nodes", fontsize=11)
    ax2.set_title(
        "Annotation Source by Chemical Class",
        fontsize=12, fontweight="bold",
    )
    ax2.legend(fontsize=9)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ 注释传播总结图: {output_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# 统一入口函数
# ═══════════════════════════════════════════════════════════════════════════════

def generate_network_figures(
    method,
    output_dir,
    G=None,
    edges_df=None,
    nodes_df=None,
    motif_df=None,
    spectra_motif_scores_csv=None,
    color_by="molecular_family",
    title_prefix="",
    group_map=None,
    precursor_mz_values=None,
):
    """
    根据网络分析方法类型，生成对应的全套出版物级图表。

    统一入口，根据 method 参数调用适当的绘图函数组合。

    Parameters
    ----------
    method : str
        "gnps", "fbmn", "ms2lda", "molnetenhancer"
    output_dir : str
        输出目录，所有 PNG 文件保存在此目录下。
    G : nx.Graph, optional
        NetworkX 图对象（gnps/fbmn/molnetenhancer 需要）。
    edges_df : pd.DataFrame, optional
        边表（需包含 cosine 列）。
    nodes_df : pd.DataFrame, optional
        节点表（molnetenhancer 需 chemical_category 列）。
    motif_df : pd.DataFrame, optional
        Mass2Motif 详情表（ms2lda 需要）。
    spectra_motif_scores_csv : str, optional
        谱图-Motif 分数路径（ms2lda 需要）。
    color_by : str
        节点着色属性名，默认 "molecular_family"。
    title_prefix : str
        标题前缀，如 "GNPS"、"FBMN"。
    group_map : dict or None
        样本到分组的映射 {sample_name: group_name}（fbmn 需要）。
    precursor_mz_values : list of float or None
        所有输入谱图的前体 m/z 列表（ms2lda 中性丢失计算需要）。
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"  📊 生成 {title_prefix or method.upper()} 网络分析图表...")
    print(f"{'=' * 60}")

    # ════════════════════════════════════════════════════════
    # ---- 通用图（GNPS / FBMN / MolNetEnhancer 共用）----
    # ════════════════════════════════════════════════════════

    if G is not None and G.number_of_nodes() > 0:
        _plot_network_topology(
            G,
            output_path=os.path.join(output_dir, "network_topology.png"),
            title=f"{title_prefix} — Network Topology",
            color_by=color_by,
        )

        _plot_family_size_distribution(
            G,
            output_path=os.path.join(output_dir, "family_size_distribution.png"),
            title=f"{title_prefix} — Molecular Family Size Distribution",
            color_by=color_by,
        )

        if G.number_of_edges() > 0:
            _plot_degree_distribution(
                G,
                output_path=os.path.join(output_dir, "degree_distribution.png"),
                title=f"{title_prefix} — Node Degree Distribution",
            )
            # 前体质量差分布（GNPS / FBMN / MolNetEnhancer 共用）
            _plot_precursor_mass_difference(
                G,
                output_path=os.path.join(output_dir, "precursor_mass_diff.png"),
                title=f"{title_prefix} — Precursor Mass Differences",
            )

    if edges_df is not None and len(edges_df) > 0 and "cosine" in edges_df.columns:
        _plot_cosine_distribution(
            edges_df,
            output_path=os.path.join(output_dir, "cosine_distribution.png"),
            title=f"{title_prefix} — Cosine Similarity Distribution",
        )

    # ════════════════════════════════════════════════════════
    # ---- FBMN 专用图 ----
    # ════════════════════════════════════════════════════════

    if method == "fbmn":
        if edges_df is not None and "pearson_r" in edges_df.columns:
            _plot_pearson_r_distribution(
                edges_df,
                output_path=os.path.join(output_dir, "pearson_distribution.png"),
                title=f"{title_prefix} — Pearson Correlation (FBMN)",
            )
        # 样本组强度对比
        if G is not None and G.number_of_nodes() > 0:
            _plot_fbmn_group_intensity(
                G,
                output_path=os.path.join(output_dir, "fbmn_group_intensity.png"),
                title=f"{title_prefix} — Group Intensity Comparison",
            )

    # ════════════════════════════════════════════════════════
    # ---- MS2LDA 专用图 ----
    # ════════════════════════════════════════════════════════

    if method == "ms2lda":
        if motif_df is not None and len(motif_df) > 0:
            # Mass2Motif 总览柱状图
            _plot_mass2motif_overview(
                motif_df,
                output_path=os.path.join(output_dir, "mass2motif_overview.png"),
                title=f"{title_prefix} — Mass2Motif Load Overview",
            )
            # Motif 碎片 mirror plot（含中性丢失）
            _plot_mass2motif_top_fragments(
                motif_df,
                output_path=os.path.join(output_dir, "mass2motif_fragments.png"),
                title=f"{title_prefix} — Mass2Motif Fragment & Neutral Loss Patterns",
                precursor_mz_values=precursor_mz_values,
            )
        if spectra_motif_scores_csv:
            # 谱图-Motif 关联热图
            _plot_motif_spectrum_association_heatmap(
                spectra_motif_scores_csv,
                output_path=os.path.join(output_dir, "motif_spectrum_heatmap.png"),
                title=f"{title_prefix} — Spectrum–Motif Association",
            )
            # Motif-谱图关联网络图
            if motif_df is not None and len(motif_df) > 0:
                _plot_mass2motif_network(
                    motif_df,
                    spectra_motif_scores_csv,
                    output_path=os.path.join(output_dir, "mass2motif_network.png"),
                    title=f"{title_prefix} — Motif–Spectrum Network",
                )

    # ════════════════════════════════════════════════════════
    # ---- MolNetEnhancer 专用图 ----
    # ════════════════════════════════════════════════════════

    if method == "molnetenhancer":
        if nodes_df is not None and len(nodes_df) > 0:
            _plot_chemical_class_distribution(
                nodes_df,
                output_path=os.path.join(output_dir, "chemical_class_distribution.png"),
                title=f"{title_prefix} — Chemical Class Distribution",
            )
            # 分子家族化学一致性
            if "chemical_category" in nodes_df.columns and G is not None:
                _plot_family_chemical_consensus(
                    nodes_df,
                    G,
                    output_path=os.path.join(output_dir, "family_chemical_consensus.png"),
                    title=f"{title_prefix} — Family Chemical Consensus",
                )
            # 注释传播总结
            if "category_confidence" in nodes_df.columns or "has_direct_annotation" in nodes_df.columns:
                _plot_annotation_propagation_summary(
                    nodes_df,
                    output_path=os.path.join(output_dir, "annotation_propagation_summary.png"),
                    title=f"{title_prefix} — Annotation Propagation Summary",
                )

    print(f"\n✅ 所有图表已生成到: {output_dir}/")
    print(f"{'=' * 60}\n")

    from web_frontend.backend.export.plotly_sidecar_backfill import backfill_molecular_network_plotly_sidecars

    backfill_molecular_network_plotly_sidecars(
        output_dir,
        title_prefix=title_prefix or (method.upper() if method else "GNPS"),
        color_by=color_by,
    )


# ======================== 综合仪表板 ========================

def generate_network_dashboard(
    G,
    edges_df,
    nodes_df,
    output_path,
    method_label="GNPS",
    additional_info=None,
):
    """
    生成单张综合仪表板图 (2×2 面板)，适合论文组合图或快速预览。

    面板布局：
    ┌─────────────────┬──────────────────┐
    │  网络拓扑缩略图   │  余弦相似度分布    │
    ├─────────────────┼──────────────────┤
    │  家族大小分布    │  化学类别/网络统计  │
    └─────────────────┴──────────────────┘

    Parameters
    ----------
    G : nx.Graph — 网络图
    edges_df : pd.DataFrame — 边表
    nodes_df : pd.DataFrame or None — 节点表（可选化学类别信息）
    output_path : str — 输出 PNG 路径
    method_label : str — 方法标签
    additional_info : dict or None — 额外统计信息
    """
    info = additional_info or {}
    n_nodes = info.get("nodes", G.number_of_nodes())
    n_edges = info.get("edges", G.number_of_edges())
    n_families = info.get("families", "?")
    n_singletons = info.get("singletons", "?")

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # -- (0,0) 网络拓扑缩略图 --
    ax1 = axes[0, 0]
    if n_nodes > 0:
        pos = nx.spring_layout(G, k=1.5 / max(1, n_nodes ** 0.3), seed=42, iterations=30)
        families = {}
        for _, a in G.nodes(data=True):
            fam = a.get("molecular_family", "singleton")
            families[fam] = families.get(fam, 0) + 1
        sorted_fams = sorted(
            [f for f in families if f != "singleton"],
            key=lambda f: families[f], reverse=True,
        )
        nx.draw_networkx_edges(G, pos, ax=ax1, edge_color="#cccccc",
                               alpha=0.15, width=0.2)
        for fam in sorted_fams[:10]:
            fam_nodes = [n for n, a in G.nodes(data=True) if a.get("molecular_family") == fam]
            fam_color = _get_family_color(fam, sorted_fams)
            nx.draw_networkx_nodes(G, pos, ax=ax1, nodelist=fam_nodes,
                                   node_color=[fam_color] * len(fam_nodes),
                                   node_size=20, alpha=0.8, edgecolors="none")
        singletons = [n for n, a in G.nodes(data=True) if a.get("molecular_family") == "singleton"]
        if singletons:
            nx.draw_networkx_nodes(G, pos, ax=ax1, nodelist=singletons,
                                   node_color="#dddddd", node_size=8, alpha=0.3)
        ax1.set_title(
            f"Network Topology\n{n_nodes} nodes, {n_edges} edges, {n_families} families",
            fontsize=11, fontweight="bold",
        )
    ax1.axis("off")

    # -- (0,1) 余弦相似度直方图 --
    ax2 = axes[0, 1]
    if len(edges_df) > 0 and "cosine" in edges_df.columns:
        cosines = edges_df["cosine"].dropna().values
        ax2.hist(cosines, bins=40, color="#4c72b0", edgecolor="white", alpha=0.8)
        ax2.axvline(x=0.7, color="#d62728", linestyle="--", label="threshold=0.7")
        ax2.set_xlabel("Cosine Similarity")
        ax2.set_ylabel("Frequency")
        ax2.set_title(f"Cosine Similarity (n={len(cosines):,})", fontsize=11, fontweight="bold")
        ax2.legend(fontsize=8)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

    # -- (1,0) 分子家族大小分布 --
    ax3 = axes[1, 0]
    families = {}
    for _, a in G.nodes(data=True):
        fam = a.get("molecular_family", "singleton")
        families[fam] = families.get(fam, 0) + 1
    n_sing = families.pop("singleton", 0)
    sorted_f = sorted(families.items(), key=lambda x: x[1], reverse=True)
    if sorted_f:
        show_n = min(20, len(sorted_f))
        f_labels = [f"MF_{i + 1}" for i in range(show_n)]
        f_sizes = [s for _, s in sorted_f[:show_n]]
        f_colors = [FAMILY_PALETTE[i % len(FAMILY_PALETTE)] for i in range(show_n)]
        ax3.bar(range(show_n), f_sizes, color=f_colors, edgecolor="white", linewidth=0.5)
        ax3.set_xticks(range(show_n))
        ax3.set_xticklabels(f_labels, rotation=45, ha="right", fontsize=6)
        if n_sing > 0:
            ax3.text(0.98, 0.95, f"Singletons: {n_sing}",
                     transform=ax3.transAxes, ha="right", va="top", fontsize=8,
                     bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        ax3.set_ylabel("Node Count")
        ax3.set_title(f"Family Sizes (Top {show_n} of {len(sorted_f)})",
                      fontsize=11, fontweight="bold")
        ax3.spines["top"].set_visible(False)
        ax3.spines["right"].set_visible(False)

    # -- (1,1) 化学类别或网络统计 --
    ax4 = axes[1, 1]
    if nodes_df is not None and "chemical_category" in nodes_df.columns:
        cat_counts = Counter(nodes_df["chemical_category"].dropna())
        if cat_counts:
            labels = list(cat_counts.keys())
            sizes = list(cat_counts.values())
            colors_pie = [CHEM_CLASS_PALETTE.get(lbl, "#bdbdbd") for lbl in labels]
            ax4.pie(sizes, labels=[f"{lbl}\n({s})" for lbl, s in zip(labels, sizes)],
                    colors=colors_pie, startangle=90, textprops={"fontsize": 7})
            ax4.set_title("Chemical Class Composition", fontsize=11, fontweight="bold")
    else:
        stats_text = (
            f"Network Statistics:\n"
            f"{'─' * 30}\n"
            f"  Nodes: {n_nodes}\n"
            f"  Edges: {n_edges}\n"
            f"  Families: {n_families}\n"
            f"  Singletons: {n_singletons}\n"
            f"  Density: {nx.density(G):.6f}\n"
        )
        if n_edges > 0:
            degrees = [d for _, d in G.degree()]
            stats_text += (
                f"  Avg degree: {np.mean(degrees):.2f}\n"
                f"  Max degree: {np.max(degrees)}\n"
                f"  Avg clustering coeff: {nx.average_clustering(G):.4f}\n"
            )
        ax4.text(0.1, 0.9, stats_text, transform=ax4.transAxes,
                 fontsize=10, fontfamily="monospace", va="top",
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#f5f5f5", alpha=0.9))
        ax4.set_title("Network Summary", fontsize=11, fontweight="bold")
        ax4.axis("off")

    fig.suptitle(
        f"Molecular Network Analysis Dashboard — {method_label}",
        fontsize=15, fontweight="bold", y=1.01,
    )
    fig.tight_layout()
    save_editable_figure(fig, output_path, title=title, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"    ✅ 综合仪表板: {output_path}")


if __name__ == "__main__":
    # ---- 输入文件路径 ----
    input_mgf = "/data2/liuwei/MOA/outputspace/differential_extraction/differential_spectra.mgf"
    output_dir = "/data2/liuwei/MOA/outputspace/networking_gnps"

    # ---- GNPS 经典分子网络 ----
    molecular_networking_gnps_impl(
        input_mgf=input_mgf,
        output_dir=output_dir,
        min_cosine=0.7, min_matched_peaks=6, fragment_tol=0.02, top_k=10,
    )
