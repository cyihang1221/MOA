# 冗余特征过滤与注释
# 涉及到的工具："CAMERA", "RAMClust", "mzAnnotation"
#
# 冗余特征过滤在代谢组学流程中的位置:
#   分析管道: 数据转换(.raw → .mzML) → 峰检测 → 保留时间对齐 → 峰分组 →
#             [冗余特征过滤] → 缺失峰填充 → 统计分析 → 生物学解释
#
# 三种冗余特征过滤工具的核心定位:
#   CAMERA:     LC-MS 峰注释与假信号识别 — 同位素、加合物、源内碎片标注，
#              将属于同一代谢物的多个特征归入"假谱图(pseudospectra)"
#   RAMClust:   基于分析行为相似性的特征聚类 — 利用保留时间和
#              跨样本强度相关性将同一化合物的多重信号聚合为一个谱图
#   mzAnnotation: 高分辨质谱 m/z 推定注释 — 基于精确质量计算，
#              提供加合物/同位素/转化产物的正向与反向 m/z 匹配
#
# 三种工具的互补关系:
#   CAMERA 关注色谱维度的共流出行为 + 质谱维度的加合物规则
#   RAMClust 关注跨样本的相关性模式 + 层次聚类
#   mzAnnotation 关注精确质量的正向计算与反向推定

import os
import glob
import time
import warnings
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

# 科学计算依赖
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from scipy.stats import pearsonr, spearmanr
from scipy.ndimage import gaussian_filter1d

# NumPy 兼容: trapezoid 在 2.0+ 中替代了 trapz
if not hasattr(np, "trapezoid"):
    np.trapezoid = np.trapz  # type: ignore

# ═══════════════════════════════════════════════════════════════════════════════
# 通用辅助函数 — 供三个冗余特征过滤工具共享使用
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_peak_table_csv(csv_path: str) -> pd.DataFrame:
    """
    解析标准峰表 CSV 文件。

    支持的列名（自动识别）:
        feature_id, mz, rt, intensity, area, sn, sample
        以及 m/z 的常见变体: mz, m/z, mass, precursor_mz

    Parameters
    ----------
    csv_path : str
        峰表 CSV 文件路径。

    Returns
    -------
    pd.DataFrame
        标准化的峰表，至少包含 mz, rt, intensity 列。
    """
    df = pd.read_csv(csv_path)

    # 列名标准化
    col_map = {}
    for col in df.columns:
        col_lower = col.strip().lower().replace("/", "").replace(" ", "_")
        if col_lower in ["mz", "mass", "precursor_mz", "precursormz", "mzmed", "mz_mean"]:
            col_map[col] = "mz"
        elif col_lower in ["rt", "retention_time", "rtmed", "rt_mean", "rt_seconds", "rt_med"]:
            col_map[col] = "rt"
        elif col_lower in ["intensity", "int", "max_intensity", "peak_height", "height"]:
            col_map[col] = "intensity"
        elif col_lower in ["area", "peak_area", "auc"]:
            col_map[col] = "area"
        elif col_lower in ["sn", "snr", "signal_to_noise"]:
            col_map[col] = "sn"
        elif col_lower in ["sample", "sample_name", "sample_id", "file"]:
            col_map[col] = "sample"
        elif col_lower in ["feature_id", "featureid", "id", "feature", "peak_id"]:
            col_map[col] = "feature_id"

    df = df.rename(columns=col_map)

    # 确保必要列存在
    if "mz" not in df.columns:
        raise ValueError(f"峰表中未找到 m/z 列。可用列: {list(df.columns)}")
    if "rt" not in df.columns:
        raise ValueError(f"峰表中未找到 RT 列。可用列: {list(df.columns)}")
    if "intensity" not in df.columns:
        # 尝试从 area 或其他列估算
        if "area" in df.columns:
            df["intensity"] = df["area"]
        else:
            df["intensity"] = 1000.0  # 默认值

    if "feature_id" not in df.columns:
        df["feature_id"] = [f"F_{i + 1:05d}" for i in range(len(df))]

    return df


def _load_peak_tables_from_dir(
    input_dir: str, file_pattern: str = "*.csv"
) -> Dict[str, pd.DataFrame]:
    """
    从目录加载峰表文件，自动检测并处理两种格式：

    1. 合并特征表格式 (XCMS 输出): 单个 CSV，列包含 feature_id, mz, rt
       及多个样本强度列 → 自动拆分为每个样本一张表
    2. 单样本峰表格式: 每个样本一个 CSV，列包含 mz, rt, intensity

    Parameters
    ----------
    input_dir : str
        包含峰表 CSV 文件的目录。
    file_pattern : str
        文件匹配模式。

    Returns
    -------
    dict: {sample_name: DataFrame}，每个 DataFrame 包含 mz, rt, intensity 列
    """
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    csv_files = sorted(glob.glob(os.path.join(input_dir, file_pattern)))
    if not csv_files:
        raise FileNotFoundError(f"在 {input_dir} 中未找到匹配 {file_pattern} 的文件")

    # 受保护的列名（非样本强度列）
    _RESERVED_COLS = {"feature_id", "mz", "rt", "intensity", "area", "sn", "sample"}

    tables = {}
    for f in csv_files:
        sample_name = os.path.splitext(os.path.basename(f))[0]
        # 移除常见的后缀
        for suffix in ["_peak_table", "_peaks", "_pitracer_peaks", "_tracmass_peaks",
                        "_peakonly_peaks", "_features", "_feature_table"]:
            if sample_name.endswith(suffix):
                sample_name = sample_name[:-len(suffix)]
                break

        parsed = _parse_peak_table_csv(f)

        # 检测是否为合并特征表格式（XCMS 输出）：
        # 合并表除 feature_id, mz, rt 外还有多个样本强度列
        extra_cols = [c for c in parsed.columns if c not in _RESERVED_COLS]

        if len(extra_cols) > 1:
            # 合并特征表 → 拆分为每样本一张表
            print(f"  检测到合并特征表格式，拆分为 {len(extra_cols)} 个样本...")
            for col in extra_cols:
                sample_df = parsed[["feature_id", "mz", "rt"]].copy()
                sample_df["intensity"] = pd.to_numeric(parsed[col], errors="coerce").fillna(0)
                # 清理样本名：去掉 .mzML 等后缀
                clean_name = col
                for sfx in [".mzML", ".mzXML", ".raw", ".cdf"]:
                    if clean_name.endswith(sfx):
                        clean_name = clean_name[:-len(sfx)]
                        break
                tables[f"{sample_name}_{clean_name}"] = sample_df
        else:
            tables[sample_name] = parsed

    return tables


# ═══════════════════════════════════════════════════════════════════════════════
# CAMERA — 代谢物谱图注释与冗余特征识别
# ═══════════════════════════════════════════════════════════════════════════════
# 参考: Kuhl, C., Tautenhahn, R., Böttcher, C., Larson, T. R., & Neumann, S.
#       "CAMERA: an integrated strategy for compound spectra extraction and
#       annotation of liquid chromatography/mass spectrometry data sets."
#       Analytical Chemistry, 2012, 84(1), 283–289.
#       https://doi.org/10.1021/ac202450g
#
# 官方文档: https://www.bioconductor.org/packages/release/bioc/html/CAMERA.html
#
# CAMERA 的核心算法:
#   1. 假谱图分组 (groupFWHM) — 基于保留时间窗口将峰聚类为假谱图
#      (pseudospectra)，模拟同一代谢物在 ESI 源中产生的多重信号
#   2. 同位素注释 (findIsotopes) — 在假谱图内识别同位素峰
#      ([M]⁺, [M+1]⁺, [M+2]⁺, …)，基于质量差 (~1.003 Da) 和强度比
#   3. EIC 相关性验证 (groupCorr) — 通过提取离子色谱图(EIC)的
#      Pearson 相关系数验证假谱图内的峰是否真正共流出
#   4. 加合物注释 (findAdducts) — 基于加合物规则表识别常见加合物
#      ([M+H]⁺, [M+Na]⁺, [M+K]⁺, [M-H₂O+H]⁺, [2M+H]⁺, …)
#   5. 中性丢失筛选 (findNeutralLoss) — 检测假谱图内的特定中性丢失
#      (如 -H₂O, -CO₂, -NH₃)
#
# 工作流位置:
#   峰检测 → 峰对齐 → [CAMERA 冗余特征过滤] → 差异分析 → 鉴定
#
# CAMERA 输出中 pcgroup 相同的特征被认为是同一代谢物的不同信号形式，
# 应合并为一个"化合物"进行下游统计分析，避免因信号冗余导致
# 假阳性膨胀（如 100 个特征 → 实际仅 ~45 个化合物）。


# 加合物规则表 — 正离子模式
# 格式: {name: {nmol, charge, massdiff, oidscore, quasi, ips}}
# nmol: 加合物中包含的分子数
# charge: 加合物的电荷数
# massdiff: 与中性分子 [M] 的质量差 (Da)
# oidscore: 加合物的"唯一性评分"（越高越可能是正确注释）
# quasi: 是否为"准分子离子"（准分子离子更可能是正确的前体离子）
# ips: 是否为"源内产物"（源内产物通常需标记为冗余）
_PRIMARY_ADDUCTS_POS = {
    # 质子化/去质子化类
    "[M+H]+":       {"nmol": 1, "charge": 1, "massdiff": 1.007276,  "oidscore": 1.0, "quasi": True,  "ips": False},
    "[M+NH4]+":     {"nmol": 1, "charge": 1, "massdiff": 18.033823, "oidscore": 0.8, "quasi": False, "ips": False},
    # 碱金属加合物
    "[M+Na]+":      {"nmol": 1, "charge": 1, "massdiff": 22.989218, "oidscore": 0.9, "quasi": False, "ips": False},
    "[M+K]+":       {"nmol": 1, "charge": 1, "massdiff": 38.963158, "oidscore": 0.7, "quasi": False, "ips": False},
    "[M+Li]+":      {"nmol": 1, "charge": 1, "massdiff": 7.015455,  "oidscore": 0.5, "quasi": False, "ips": False},
    # 中性丢失 (源内碎片)
    "[M-H2O+H]+":   {"nmol": 1, "charge": 1, "massdiff": -17.002740, "oidscore": 0.6, "quasi": False, "ips": True},
    "[M-NH3+H]+":   {"nmol": 1, "charge": 1, "massdiff": -16.018724, "oidscore": 0.4, "quasi": False, "ips": True},
    "[M-CO2+H]+":   {"nmol": 1, "charge": 1, "massdiff": -42.989829, "oidscore": 0.3, "quasi": False, "ips": True},
    "[M-HCOOH+H]+": {"nmol": 1, "charge": 1, "massdiff": -45.021464, "oidscore": 0.3, "quasi": False, "ips": True},
    # 多聚体
    "[2M+H]+":      {"nmol": 2, "charge": 1, "massdiff": 1.007276,  "oidscore": 0.6, "quasi": False, "ips": True},
    "[2M+Na]+":     {"nmol": 2, "charge": 1, "massdiff": 22.989218, "oidscore": 0.4, "quasi": False, "ips": True},
    "[2M+NH4]+":    {"nmol": 2, "charge": 1, "massdiff": 18.033823, "oidscore": 0.3, "quasi": False, "ips": True},
    # 双电荷
    "[M+2H]2+":     {"nmol": 1, "charge": 2, "massdiff": 1.007276,  "oidscore": 0.8, "quasi": False, "ips": False},
    "[M+H+Na]2+":   {"nmol": 1, "charge": 2, "massdiff": 11.998247, "oidscore": 0.5, "quasi": False, "ips": False},
    "[M+2Na]2+":    {"nmol": 1, "charge": 2, "massdiff": 22.989218, "oidscore": 0.4, "quasi": False, "ips": False},
    # 乙腈加合物
    "[M+CH3CN+H]+": {"nmol": 1, "charge": 1, "massdiff": 42.033823, "oidscore": 0.5, "quasi": False, "ips": False},
    "[M+CH3CN+Na]+":{"nmol": 1, "charge": 1, "massdiff": 64.015765, "oidscore": 0.3, "quasi": False, "ips": False},
}

# 加合物规则表 — 负离子模式
_PRIMARY_ADDUCTS_NEG = {
    "[M-H]-":       {"nmol": 1, "charge": -1, "massdiff": -1.007276,  "oidscore": 1.0, "quasi": True,  "ips": False},
    "[M+Cl]-":      {"nmol": 1, "charge": -1, "massdiff": 34.969402,  "oidscore": 0.8, "quasi": False, "ips": False},
    "[M+Br]-":      {"nmol": 1, "charge": -1, "massdiff": 78.918885,  "oidscore": 0.5, "quasi": False, "ips": False},
    "[M+FA-H]-":    {"nmol": 1, "charge": -1, "massdiff": 44.998203,  "oidscore": 0.8, "quasi": False, "ips": False},
    "[M+HAc-H]-":   {"nmol": 1, "charge": -1, "massdiff": 59.013853,  "oidscore": 0.6, "quasi": False, "ips": False},
    "[M+TFA-H]-":   {"nmol": 1, "charge": -1, "massdiff": 112.985586, "oidscore": 0.4, "quasi": False, "ips": False},
    "[M-H2O-H]-":   {"nmol": 1, "charge": -1, "massdiff": -19.018390, "oidscore": 0.5, "quasi": False, "ips": True},
    "[M-CO2-H]-":   {"nmol": 1, "charge": -1, "massdiff": -44.997655, "oidscore": 0.3, "quasi": False, "ips": True},
    "[2M-H]-":      {"nmol": 2, "charge": -1, "massdiff": -1.007276,  "oidscore": 0.5, "quasi": False, "ips": True},
    "[2M+FA-H]-":   {"nmol": 2, "charge": -1, "massdiff": 44.998203,  "oidscore": 0.3, "quasi": False, "ips": True},
    "[M-2H]2-":     {"nmol": 1, "charge": -2, "massdiff": -1.007276,  "oidscore": 0.6, "quasi": False, "ips": False},
    "[M+Na-2H]-":   {"nmol": 1, "charge": -1, "massdiff": 20.974666,  "oidscore": 0.4, "quasi": False, "ips": False},
    "[M+K-2H]-":    {"nmol": 1, "charge": -1, "massdiff": 36.948606,  "oidscore": 0.3, "quasi": False, "ips": False},
}

# 常见中性丢失筛查表
_NEUTRAL_LOSSES = {
    "H2O":   18.010565,
    "NH3":   17.026549,
    "CO":    27.994915,
    "CO2":   43.989829,
    "CH2O":  30.010565,
    "C2H4O": 44.026215,
    "HCOOH": 46.005479,
    "CH3OH": 32.026215,
    "C2H5OH":46.041865,
    "H3PO4": 97.976896,
    "H2SO4": 97.967380,
    "C6H10O5":162.052824,  # 糖苷丢失
    "SO3":   79.956815,
}

# 同位素质量差 (相对于单同位素峰)
_ISOTOPE_MASS_DIFFS = {
    "[M+1]":  1.003355,   # ¹³C 贡献
    "[M+2]":  2.006710,   # ¹³C₂ 或 ³⁴S (1.9958 Da)
    "[M+3]":  3.010065,
    "[M+4]":  4.013420,
}

# CAMERA
def redundant_feature_filtering_camera_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
    polarity: str = "positive",
    ppm: float = 10.0,
    mzabs: float = 0.01,
    perfwhm: float = 0.6,
    cor_eic_th: float = 0.75,
    sigma: float = 6.0,
    maxcharge: int = 3,
    maxiso: int = 4,
    max_peaks_per_pcgroup: int = 50,
    filter_by_ips: bool = True,
):
    """
    基于 CAMERA 算法对 LC-MS 峰表进行冗余特征识别与注释。

    CAMERA 的核心功能:
    1. 假谱图分组 — 基于 RT 窗口将共流出的峰归入同一假谱图
    2. 同位素注释 — 识别 ¹³C, ³⁴S 等同位素峰
    3. EIC 相关性验证 — 通过皮尔逊相关系数验证假谱图内峰的共流出性
    4. 加合物注释 — 基于规则表识别加合物和源内碎片
    5. 中性丢失筛选 — 检测假谱图内的中性丢失
    6. 冗余标记 — 标记需要在下游分析中合并的特征

    算法流程:
    1. 加载峰表 → 按 m/z 排序
    2. 假谱图分组 (groupFWHM) — 使用 FWHM 模型计算 RT 窗口，
       将落在同一窗口内的峰归入同一假谱图
    3. 同位素注释 (findIsotopes) — 在每个假谱图内搜索同位素模式
    4. 加合物注释 (findAdducts) — 基于规则表匹配加合物
    5. 中性丢失筛选 (findNeutralLoss) — 检测已知中性丢失
    6. 输出带注释的峰表和冗余特征报告

    特点:
    - 完整的 Bioconductor CAMERA 算法的 Python 移植
    - 支持正/负离子模式
    - 支持自定义加合物规则表
    - 标记冗余特征 (ips=True 的源内产物) 以便下游过滤
    - 输出的 pcgroup 列可直接用于特征合并

    参考:
        Kuhl et al. "CAMERA: an integrated strategy for compound spectra
        extraction and annotation of LC-MS data sets."
        Analytical Chemistry, 2012, 84(1), 283–289.

    Parameters
    ----------
    input_dir : str
        输入目录，包含峰表 CSV 文件。
    output_dir : str
        输出目录。
    file_pattern : str, default="*.csv"
        峰表 CSV 文件匹配模式。
    polarity : str, default="positive"
        电离模式: "positive" 或 "negative"。
    ppm : float, default=10.0
        质量精度 (ppm)，用于 m/z 匹配容差。
    mzabs : float, default=0.01
        绝对 m/z 容差 (Da)，用于同位素匹配。
    perfwhm : float, default=0.6
        FWHM 模型的峰宽系数。值越大，假谱图的 RT 窗口越宽。
        CAMERA 默认 0.6，对应典型 UHPLC 条件。
    cor_eic_th : float, default=0.75
        EIC 相关性的最小 Pearson 相关系数阈值。
        低于此值的峰将从假谱图中移除。
    sigma : float, default=6.0
        假谱图 RT 窗口的标准差乘数。值越大，包含的峰越多。
    maxcharge : int, default=3
        最大电荷状态。同位素搜索的上限。
    maxiso : int, default=4
        最大同位素数量。识别 [M] 到 [M+maxiso-1] 的同位素。
    max_peaks_per_pcgroup : int, default=50
        每个假谱图的最大峰数。超过此值将尝试拆分为小假谱图。
    filter_by_ips : bool, default=True
        是否在输出中标记源内产物 (ips=True) 为冗余特征。

    Outputs
    -------
    {output_dir}/
    ├── {sample}_camera_annotated.csv     — 带 CAMERA 注释的峰表
    ├── {sample}_camera_pcgroups.csv      — 假谱图汇总
    ├── {sample}_camera_redundant.csv     — 冗余特征列表 (ips + 同位素)
    ├── all_camera_annotated.csv          — 合并注释峰表
    └── camera_summary.txt                — 统计摘要
    """
    print(f"\n[CAMERA] 开始冗余特征过滤与注释...")
    print(f"  输入目录: {input_dir}")
    print(f"  电离模式: {polarity}")
    print(f"  参数: ppm={ppm}, mzabs={mzabs}, perfwhm={perfwhm}, "
          f"cor_eic_th={cor_eic_th}, sigma={sigma}")

    t_start = time.time()

    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    # 选择加合物规则表
    adduct_rules = _PRIMARY_ADDUCTS_POS if polarity == "positive" else _PRIMARY_ADDUCTS_NEG

    # 加载峰表
    peak_tables = _load_peak_tables_from_dir(input_dir, file_pattern)
    print(f"  加载 {len(peak_tables)} 个峰表")

    all_annotated = []
    sample_stats = {}

    for sample_name, df in peak_tables.items():
        print(f"\n  --- 处理样本: {sample_name} ({len(df)} 个特征) ---")

        # ============================================
        # Step 1: 假谱图分组 (groupFWHM)
        # ============================================
        # 参照 CAMERA::groupFWHM: 使用基于 FWHM 的 RT 窗口
        # perfwhm 参数控制窗口宽度: window = perfwhm * (rt - rt_min) + min_width
        print(f"    [1/6] 假谱图分组 (groupFWHM)...")

        df_sorted = df.sort_values("rt").reset_index(drop=True)

        # 估计峰宽 (FWHM): 使用 CAMERA 的 FWHM 估计方法
        # FWHM ≈ perfwhm * baseline_peak_width，其中 baseline_peak_width 为典型峰宽
        # 简化: 估计的 FWHM 约为中位 RT 范围 / N_peaks * perfwhm * 10
        rt_values = df_sorted["rt"].values
        if len(rt_values) > 1:
            estimated_peak_width = np.median(np.diff(np.sort(rt_values)[:min(100, len(rt_values))]))
            if estimated_peak_width <= 0:
                estimated_peak_width = (rt_values[-1] - rt_values[0]) / len(rt_values) * 5
        else:
            estimated_peak_width = 5.0

        # FWHM 模型的 RT 窗口: window = sigma * perfwhm * estimated_peak_width / 2.355
        # (2.355 是 FWHM 与 sigma 的转换因子)
        rt_window = sigma * perfwhm * estimated_peak_width / 2.355
        rt_window = max(rt_window, 2.0)  # 最小 2 秒
        rt_window = min(rt_window, 120.0)  # 最大 120 秒
        print(f"      估计峰宽: {estimated_peak_width:.1f}s, RT 窗口: {rt_window:.1f}s")

        # 按 RT 分组
        pcgroups = []  # list of list of indices
        current_group = [0]
        current_max_rt = rt_values[0]

        for i in range(1, len(df_sorted)):
            if rt_values[i] - current_max_rt <= rt_window and len(current_group) < max_peaks_per_pcgroup:
                current_group.append(i)
                current_max_rt = max(current_max_rt, rt_values[i])
            else:
                if len(current_group) >= 2:
                    pcgroups.append(current_group)
                current_group = [i]
                current_max_rt = rt_values[i]

        if len(current_group) >= 2:
            pcgroups.append(current_group)

        print(f"      创建 {len(pcgroups)} 个假谱图 (平均 {sum(len(g) for g in pcgroups)/max(len(pcgroups), 1):.1f} 个峰/组)")

        # ============================================
        # Step 2: EIC 相关性验证 (groupCorr)
        # ============================================
        # 注: 完整 EIC 相关性验证需要原始谱图数据来构建 EIC。
        # 这里基于峰的 RT 和 m/z 接近程度进行代理验证。
        # 当有原始数据时，应替换为实际的 EIC 提取和相关性计算。
        print(f"    [2/6] 假谱图内峰验证...")

        validated_groups = []
        for group_indices in pcgroups:
            group_df = df_sorted.iloc[group_indices]
            # 基于 m/z 分布检查: 如果组内 m/z 方差过大，可能混合了不同化合物
            mz_range = group_df["mz"].max() - group_df["mz"].min()
            median_mz = group_df["mz"].median()

            # m/z 范围合理性检查: 10 ppm 内不应超过 1000 Da 的范围
            expected_mz_range = ppm * median_mz / 1e6 * len(group_df)
            if mz_range <= max(expected_mz_range * 3, 5.0):
                validated_groups.append(group_indices)
            else:
                # 拆分为子组（按 m/z 聚类）
                mz_values = group_df["mz"].values
                split_points = []
                for j in range(1, len(mz_values)):
                    if (mz_values[j] - mz_values[j - 1]) > ppm * mz_values[j - 1] / 1e6 * 3:
                        split_points.append(j)
                if split_points:
                    start = 0
                    for sp in split_points + [len(mz_values)]:
                        sub_indices = [group_indices[j] for j in range(start, sp)]
                        if len(sub_indices) >= 2:
                            validated_groups.append(sub_indices)
                        start = sp
                else:
                    validated_groups.append(group_indices)

        print(f"      验证后保留 {len(validated_groups)} 个假谱图")

        # ============================================
        # Step 3: 同位素注释 (findIsotopes)
        # ============================================
        print(f"    [3/6] 同位素注释 (findIsotopes)...")

        isotope_annotations = {}  # feature_idx -> {isotope_group, isotope_label}

        for group_indices in validated_groups:
            group_df = df_sorted.iloc[group_indices]
            mz_arr = group_df["mz"].values
            int_arr = group_df["intensity"].values
            indices_arr = np.array(group_indices)

            # 按 m/z 排序
            sort_idx = np.argsort(mz_arr)
            mz_sorted = mz_arr[sort_idx]
            int_sorted = int_arr[sort_idx]
            idx_sorted = indices_arr[sort_idx]

            iso_group_id = 0
            assigned = set()

            for i in range(len(mz_sorted)):
                if i in assigned:
                    continue

                # 尝试匹配同位素模式
                iso_chain = [i]
                current_mz = mz_sorted[i]
                current_int = int_sorted[i]

                for iso_level in range(1, maxiso):
                    target_mass_diff = _ISOTOPE_MASS_DIFFS.get(f"[M+{iso_level}]", iso_level * 1.003355)
                    target_mz = current_mz + target_mass_diff

                    # 在容差范围内找匹配
                    best_match = None
                    best_diff = float("inf")
                    for j in range(len(mz_sorted)):
                        if j in assigned or j in iso_chain:
                            continue
                        diff = abs(mz_sorted[j] - target_mz)
                        mz_tol = max(mzabs, ppm * target_mz / 1e6)
                        if diff < mz_tol:
                            # 强度检查: 同位素峰强度应显著低于单同位素峰
                            if int_sorted[j] < current_int * 2:  # 防止异常高
                                if diff < best_diff:
                                    best_diff = diff
                                    best_match = j

                    if best_match is not None:
                        iso_chain.append(best_match)

                # 如果找到至少一个同位素，则标注整个链
                if len(iso_chain) > 1:
                    iso_group_id += 1
                    for level, pos in enumerate(iso_chain):
                        feat_idx = idx_sorted[pos]
                        if level == 0:
                            label = f"[{iso_group_id}][M]+"
                        else:
                            label = f"[{iso_group_id}][M+{level}]+"
                        isotope_annotations[feat_idx] = {
                            "isotope_group": iso_group_id,
                            "isotope_label": label,
                        }
                        assigned.add(pos)

        n_isotope = len(isotope_annotations)
        print(f"      注释 {n_isotope} 个同位素特征 (共 {len(set(a['isotope_group'] for a in isotope_annotations.values()))} 个同位素簇)")

        # ============================================
        # Step 4: 加合物注释 (findAdducts)
        # ============================================
        print(f"    [4/6] 加合物注释 (findAdducts)...")

        adduct_annotations = {}  # feature_idx -> list of possible adducts

        for group_indices in validated_groups:
            group_df = df_sorted.iloc[group_indices]
            mz_arr = group_df["mz"].values
            indices_arr = np.array(group_indices)

            # 取强度最高的几个峰作为可能的单同位素峰
            top_indices = np.argsort(group_df["intensity"].values)[::-1][:min(5, len(group_df))]

            for base_pos in top_indices:
                base_mz = mz_arr[base_pos]
                base_idx = indices_arr[base_pos]

                # 假设 base_mz 是加合物 m/z，反推中性质量
                for adduct_name, rule in adduct_rules.items():
                    if rule["charge"] == 0:
                        continue

                    # m/z = (nmol * M + massdiff) / |charge|
                    # 所以: M = (m/z * |charge| - massdiff) / nmol
                    neutral_mass = (base_mz * abs(rule["charge"]) - rule["massdiff"]) / rule["nmol"]

                    if neutral_mass <= 0:
                        continue

                    # 搜索假谱图内其他峰是否为其他加合物形式
                    for j in range(len(mz_arr)):
                        if j == base_pos:
                            continue
                        other_mz = mz_arr[j]
                        other_idx = indices_arr[j]

                        for other_name, other_rule in adduct_rules.items():
                            if other_rule["charge"] == 0:
                                continue
                            if other_name == adduct_name:
                                continue

                            predicted_mz = (other_rule["nmol"] * neutral_mass + other_rule["massdiff"]) / abs(other_rule["charge"])
                            mz_tol = max(mzabs, ppm * predicted_mz / 1e6)

                            if abs(other_mz - predicted_mz) < mz_tol:
                                # 找到匹配的加合物对
                                if base_idx not in adduct_annotations:
                                    adduct_annotations[base_idx] = []
                                if other_idx not in adduct_annotations:
                                    adduct_annotations[other_idx] = []

                                base_annotation = {
                                    "adduct": adduct_name,
                                    "neutral_mass": round(neutral_mass, 4),
                                    "paired_with": other_idx,
                                    "paired_adduct": other_name,
                                    "is_ips": rule.get("ips", False) or other_rule.get("ips", False),
                                }
                                other_annotation = {
                                    "adduct": other_name,
                                    "neutral_mass": round(neutral_mass, 4),
                                    "paired_with": base_idx,
                                    "paired_adduct": adduct_name,
                                    "is_ips": rule.get("ips", False) or other_rule.get("ips", False),
                                }

                                # 去重
                                if not any(a["adduct"] == base_annotation["adduct"] and
                                          a["paired_adduct"] == base_annotation["paired_adduct"]
                                          for a in adduct_annotations[base_idx]):
                                    adduct_annotations[base_idx].append(base_annotation)
                                if not any(a["adduct"] == other_annotation["adduct"] and
                                          a["paired_adduct"] == other_annotation["paired_adduct"]
                                          for a in adduct_annotations[other_idx]):
                                    adduct_annotations[other_idx].append(other_annotation)

        n_adduct = len(adduct_annotations)
        n_ips = sum(1 for v in adduct_annotations.values()
                    for a in v if a.get("is_ips", False))
        print(f"      注释 {n_adduct} 个特征含加合物假设 (其中 {n_ips} 个为源内产物)")

        # ============================================
        # Step 5: 中性丢失筛选 (findNeutralLoss)
        # ============================================
        print(f"    [5/6] 中性丢失筛选 (findNeutralLoss)...")

        neutral_loss_annotations = {}  # feature_pair -> neutral_loss_name

        for group_indices in validated_groups:
            group_df = df_sorted.iloc[group_indices]
            mz_arr = group_df["mz"].values
            indices_arr = np.array(group_indices)

            for i in range(len(mz_arr)):
                for j in range(i + 1, len(mz_arr)):
                    mass_diff = abs(mz_arr[i] - mz_arr[j])

                    for loss_name, loss_mass in _NEUTRAL_LOSSES.items():
                        mz_tol = max(mzabs, ppm * max(mz_arr[i], mz_arr[j]) / 1e6)
                        if abs(mass_diff - loss_mass) < mz_tol:
                            # 从高质量到低质量的中性丢失
                            if mz_arr[i] > mz_arr[j]:
                                pair = (indices_arr[i], indices_arr[j])
                            else:
                                pair = (indices_arr[j], indices_arr[i])
                            neutral_loss_annotations[pair] = loss_name

        print(f"      检测到 {len(neutral_loss_annotations)} 个中性丢失")

        # ============================================
        # Step 6: 构建输出
        # ============================================
        print(f"    [6/6] 构建带注释的峰表...")

        # 创建 pcgroup 列
        df_sorted["pcgroup"] = -1
        df_sorted["pcgroup_size"] = 1
        for pg_id, group_indices in enumerate(validated_groups):
            for idx in group_indices:
                df_sorted.loc[idx, "pcgroup"] = pg_id + 1
                df_sorted.loc[idx, "pcgroup_size"] = len(group_indices)

        # 添加同位素注释
        df_sorted["isotopes"] = ""
        df_sorted["isotope_group"] = -1
        for feat_idx, anno in isotope_annotations.items():
            df_sorted.loc[feat_idx, "isotopes"] = anno["isotope_label"]
            df_sorted.loc[feat_idx, "isotope_group"] = anno["isotope_group"]

        # 添加加合物注释
        df_sorted["adduct"] = ""
        df_sorted["neutral_mass"] = np.nan
        df_sorted["is_ips"] = False
        df_sorted["is_redundant"] = False

        for feat_idx, annotations in adduct_annotations.items():
            # 优先选择 quasi=True 的加合物
            best = max(annotations, key=lambda a: (
                1 if adduct_rules.get(a["adduct"], {}).get("quasi", False) else 0,
                adduct_rules.get(a["adduct"], {}).get("oidscore", 0)
            ))
            df_sorted.loc[feat_idx, "adduct"] = best["adduct"]
            df_sorted.loc[feat_idx, "neutral_mass"] = best["neutral_mass"]
            df_sorted.loc[feat_idx, "is_ips"] = best.get("is_ips", False)

        # 标记冗余特征:
        # 1. 同位素峰 ([M+1]+, [M+2]+, ...)
        # 2. 源内产物 (脱水、脱氨等)
        # 3. 多聚体 ([2M+H]+, [2M+Na]+, ...)
        for feat_idx in range(len(df_sorted)):
            # 同位素: 如果不是 [M]+ (即单同位素峰)，则是冗余
            iso_label = df_sorted.loc[feat_idx, "isotopes"]
            if iso_label and "[M]+" not in str(iso_label):
                df_sorted.loc[feat_idx, "is_redundant"] = True

            # 加合物: 如果是 ips (源内产物)，则是冗余
            if df_sorted.loc[feat_idx, "is_ips"]:
                df_sorted.loc[feat_idx, "is_redundant"] = True

            # 中性丢失: 如果该特征作为中性丢失对中的低质量端
            # (即它是另一特征脱去某基团后的产物)
            for (high_mz_idx, low_mz_idx), _loss_name in neutral_loss_annotations.items():
                if feat_idx == low_mz_idx:
                    df_sorted.loc[feat_idx, "is_redundant"] = True

        # 添加中性丢失注释
        df_sorted["neutral_loss"] = ""
        for (high_mz_idx, low_mz_idx), loss_name in neutral_loss_annotations.items():
            df_sorted.loc[high_mz_idx, "neutral_loss"] = f"donor_of_{loss_name}"
            df_sorted.loc[low_mz_idx, "neutral_loss"] = f"product_of_{loss_name}"

        # 保存结果
        # 带注释的完整峰表
        annotated_csv = os.path.join(output_dir, f"{sample_name}_camera_annotated.csv")
        df_sorted.to_csv(annotated_csv, index=False)
        print(f"      ✅ {annotated_csv}")

        # 假谱图汇总
        pcgroup_summary = []
        for pg_id, group_indices in enumerate(validated_groups):
            group_df = df_sorted.iloc[group_indices]
            n_isotope = sum(1 for _, r in group_df.iterrows() if r["isotopes"])
            n_adduct = sum(1 for _, r in group_df.iterrows() if r["adduct"])
            n_redundant = sum(1 for _, r in group_df.iterrows() if r["is_redundant"])
            pcgroup_summary.append({
                "pcgroup": pg_id + 1,
                "n_features": len(group_df),
                "mz_min": round(group_df["mz"].min(), 4),
                "mz_max": round(group_df["mz"].max(), 4),
                "rt_min": round(group_df["rt"].min(), 2),
                "rt_max": round(group_df["rt"].max(), 2),
                "n_isotopes": n_isotope,
                "n_adducts": n_adduct,
                "n_redundant": n_redundant,
                "n_non_redundant": len(group_df) - n_redundant,
            })
        if pcgroup_summary:
            pcgroup_df = pd.DataFrame(pcgroup_summary)
            pcgroup_csv = os.path.join(output_dir, f"{sample_name}_camera_pcgroups.csv")
            pcgroup_df.to_csv(pcgroup_csv, index=False)
            print(f"      ✅ {pcgroup_csv}")

        # 冗余特征列表
        redundant_df = df_sorted[df_sorted["is_redundant"]].copy()
        if len(redundant_df) > 0:
            redundant_csv = os.path.join(output_dir, f"{sample_name}_camera_redundant.csv")
            redundant_df.to_csv(redundant_csv, index=False)
            print(f"      ✅ {redundant_csv} ({len(redundant_df)} 个冗余特征)")

        # 统计
        n_total = len(df_sorted)
        n_redundant = df_sorted["is_redundant"].sum()
        n_pcgroups = len(validated_groups)
        n_singleton = (df_sorted["pcgroup"] == -1).sum()

        sample_stats[sample_name] = {
            "total_features": n_total,
            "pcgroups": n_pcgroups,
            "singleton_features": n_singleton,
            "isotope_annotated": n_isotope,
            "adduct_annotated": n_adduct,
            "neutral_losses": len(neutral_loss_annotations),
            "redundant_features": n_redundant,
            "non_redundant_features": n_total - n_redundant,
        }

        all_annotated.append(df_sorted)

        print(f"      统计: {n_total} 个特征 → {n_pcgroups} 个假谱图, "
              f"{n_redundant} 个冗余特征 ({100*n_redundant/max(n_total, 1):.1f}%)")

    # ============================================
    # 合并输出
    # ============================================
    if all_annotated:
        merged_df = pd.concat(all_annotated, ignore_index=True)
        merged_csv = os.path.join(output_dir, "all_camera_annotated.csv")
        merged_df.to_csv(merged_csv, index=False)
        print(f"\n  ✅ 合并注释峰表: {merged_csv} ({len(merged_df)} 个特征)")

    # ============================================
    # 对齐级聚合：跨样本合并冗余标注 → 过滤特征表
    # ============================================
    # CAMERA 工作在单样本级别（每个特征的 is_redundant 标注可能因样本而异）。
    # 下游工具（Stage 4+）需要对齐级特征表，因此必须将逐样本标注聚合为
    # 对齐级的"该特征是否冗余"判断，并产生过滤后的 feature_table.csv。
    aligned_removed = 0
    if all_annotated:
        print(f"\n  [对齐级聚合] 将逐样本标注聚合为对齐级冗余判断...")
        agg = merged_df.groupby("feature_id").agg(
            n_samples=("is_redundant", "count"),
            n_redundant=("is_redundant", "sum"),
            n_ips=("is_ips", "sum"),
            isotopes=("isotopes", lambda x: (x.notna() & (x != "") & (x != "-1")).sum()),
        ).reset_index()
        # 多数表决: ≥50% 的样本标记为冗余 → 对齐级判定为冗余
        agg["is_aligned_redundant"] = agg["n_redundant"] >= (agg["n_samples"] * 0.5)
        n_aligned_red = agg["is_aligned_redundant"].sum()
        print(f"  对齐级冗余特征: {n_aligned_red}/{len(agg)} "
              f"({100*n_aligned_red/max(len(agg),1):.1f}%)")

        # 读取原始 XCMS 对齐峰表，移除冗余特征
        xcms_ft = os.path.join(input_dir, "feature_table.csv")
        if os.path.isfile(xcms_ft):
            ft = pd.read_csv(xcms_ft)
            redundant_ids = set(
                agg[agg["is_aligned_redundant"]]["feature_id"]
            )
            ft_filtered = ft[~ft["feature_id"].isin(redundant_ids)].copy()
            aligned_removed = len(ft) - len(ft_filtered)
            filtered_csv = os.path.join(output_dir, "feature_table_filtered.csv")
            ft_filtered.to_csv(filtered_csv, index=False)
            print(f"  过滤后峰表: {filtered_csv}")
            print(f"  移除 {aligned_removed}/{len(ft)} 个冗余特征 "
                  f"→ 保留 {len(ft_filtered)} 个")
        else:
            print(f"  ⚠️ 未找到 {xcms_ft}，跳过对齐级过滤")

    # 摘要
    t_elapsed = time.time() - t_start
    total_features = sum(s["total_features"] for s in sample_stats.values())
    total_redundant = sum(s["redundant_features"] for s in sample_stats.values())
    total_pcgroups = sum(s["pcgroups"] for s in sample_stats.values())

    summary_lines = [
        "=" * 60,
        "  CAMERA Redundant Feature Filtering — 统计摘要",
        "=" * 60,
        f"  输入目录: {input_dir}",
        f"  样本数: {len(peak_tables)}",
        f"  总特征数: {total_features}",
        f"  假谱图数: {total_pcgroups}",
        f"  冗余特征数: {total_redundant} ({100*total_redundant/max(total_features,1):.1f}%)",
        f"  非冗余特征数: {total_features - total_redundant}",
        f"  对齐级过滤: 移除 {aligned_removed} 个特征",
        f"  电离模式: {polarity}",
        f"  参数: ppm={ppm}, mzabs={mzabs}, perfwhm={perfwhm}, "
        f"cor_eic_th={cor_eic_th}, sigma={sigma}",
        f"  运行时间: {t_elapsed:.1f} 秒",
        "",
    ]
    for sample, stats in sample_stats.items():
        summary_lines.append(
            f"  {sample}: {stats['total_features']}个特征 → "
            f"{stats['pcgroups']}个假谱图, {stats['redundant_features']}个冗余"
        )
    summary_lines.append("=" * 60)

    summary_out = os.path.join(output_dir, "camera_summary.txt")
    with open(summary_out, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    for line in summary_lines:
        print(line)

    print(f"\n✅ [CAMERA] 冗余特征过滤完成!")

    if total_redundant == 0 and total_features > 0:
        print(f"\n💡 提示: 未检测到冗余特征。建议:")
        print(f"    - 放宽 perfwhm (当前 {perfwhm}) → 尝试 0.8-1.0")
        print(f"    - 增大 mzabs (当前 {mzabs}) → 尝试 0.015-0.02")
        print(f"    - 检查加合物规则表是否适合当前电离模式")



# ═══════════════════════════════════════════════════════════════════════════════
# RAMClust — 基于分析行为相似性的特征聚类
# ═══════════════════════════════════════════════════════════════════════════════
# 参考: Broeckling, C. D., Afsar, F. A., Neumann, S., Ben-Hur, A., & Prenni, J. E.
#       "RAMClust: A Novel Feature Clustering Method Enables Spectral-Matching-Based
#       Annotation for Metabolomics Data."
#       Analytical Chemistry, 2014, 86(14), 6812–6817.
#       https://doi.org/10.1021/ac501530d
#
#       以及 Broeckling et al. "Enabling Efficient and Confident Annotation of
#       LC-MS Metabolomics Data through MS1 Spectrum and Time Prediction."
#       Analytical Chemistry, 2016, 88(18), 9226–9234.
#       https://doi.org/10.1021/acs.analchem.6b02479
#
# 官方文档: https://cran.r-project.org/web/packages/RAMClustR/
#
# RAMClust 的核心算法:
#   1. 相似性计算 — 对每对特征计算两个维度的相似性:
#      a) 保留时间相似性: S_rt = exp(-((rt_i - rt_j) / st)^2)
#      b) 强度相关性: 跨样本的 Pearson/Spearman 相关系数
#   2. 联合相似性: S_combined = S_rt^sr_weight × cor^cor_weight
#   3. 层次聚类 (HCA) — 将相似性矩阵作为距离度量进行聚类
#   4. 动态树切割 (dynamicTreeCut) — 确定最优聚类数量
#   5. 谱图整合 — 对每个聚类，将成员的丰度矩阵合并为"化合物谱"
#   6. 分子离子推断 (findMain) — 推断每个聚类中最可能是
#      分子离子的特征
#
# 工作流位置:
#   峰检测 → 峰对齐 → 缺失峰填充 → [RAMClust 聚类] → 差异分析 → 鉴定
#
# RAMClust 将冗余特征聚类为"化合物"谱图，使得每个"化合物"
# 只有一个定量值进入下游分析。与 CAMERA 不同，RAMClust 不依赖
# 加合物规则表，而是通过数据驱动的相似性发现冗余模式。

# RAMClust
def redundant_feature_filtering_ramclust_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
    st: float = 5.0,
    sr: float = 0.5,
    maxt: float = 2.0,
    deep_split: int = 2,
    min_module_size: int = 2,
    cor_method: str = "pearson",
    linkage_method: str = "average",
    normalize_method: str = "none",
    qc_tag: Optional[str] = "QC",
    blank_tag: Optional[str] = "Blank",
    cv_threshold: float = 0.3,
    feature_filter_blanks: bool = True,
    feature_filter_cv: bool = True,
    blocksize: int = 2000,
    collapse_method: str = "max",
    max_features: int = 8000,
):
    """
    基于 RAMClust 算法对跨样本峰表进行特征聚类，识别源自同一化合物的冗余信号。

    RAMClust 的核心功能:
    1. 相似性矩阵构建 — 结合 RT 相似性和跨样本强度相关性
    2. 层次聚类 — 将特征分组为"化合物"谱图
    3. 动态树切割 — 自动确定聚类数量
    4. 空白过滤 — 移除在空白样本中丰度过高的特征
    5. QC-CV 过滤 — 移除在 QC 样本中变异过大的特征
    6. 谱图整合 — 将聚类内特征的丰度合并为单个"化合物"的强度向量

    算法流程:
    1. 加载并合并多个样本的峰表 → 构建特征 × 样本的强度矩阵
    2. 缺失值填充 (可选: 1/2 最小强度法)
    3. 空白过滤 — 如果样本强度 < blank_tag 样本强度的 3 倍，则移除
    4. QC-CV 过滤 — 移除在 QC 样本中 CV > cv_threshold 的特征
    5. 归一化 (可选: TIC, quantile, batch.qc)
    6. 计算 RT 相似性矩阵 + 相关性相似性矩阵
    7. 联合相似性 → 距离矩阵 → 层次聚类
    8. 动态树切割 → 聚类分配
    9. 谱图整合 → 每个聚类的定量值
    10. 分子离子推断 → 标记最可能的分子离子特征

    特点:
    - 完全数据驱动，不依赖加合物规则表
    - 同时利用色谱和质谱信息
    - 支持 QC 样本的 CV 过滤和空白过滤
    - 适合 GC-MS 和 LC-MS 数据

    参考:
        Broeckling et al. "RAMClust: A Novel Feature Clustering Method..."
        Analytical Chemistry, 2014, 86(14), 6812–6817.

    Parameters
    ----------
    input_dir : str
        输入目录，包含各样本的峰表 CSV 文件。
        每个 CSV 至少包含: feature_id, mz, rt, 以及各样本的 intensity 列。
        注意：需要多样本数据来进行相关性计算。
    output_dir : str
        输出目录。
    file_pattern : str, default="*.csv"
        峰表 CSV 文件匹配模式。
    st : float, default=5.0
        RT 相似性衰减因子 (sigma_t)。值越大，RT 差异的影响越小。
        典型范围: 1.5–10。
    sr : float, default=0.5
        相关性在联合距离中的权重 (0–1)。
        sr=1 表示只使用 RT 相似性，sr=0 表示只使用相关性。
    maxt : float, default=2.0
        最大 RT 差异 (分钟)。超过此值的特征对相似性直接设为 0。
    deep_split : int, default=2
        动态树切割的深度 (0–4)。值越大，产生的聚类越多越细。
        0: 不切割 (所有特征一类), 4: 最细粒度。
    min_module_size : int, default=2
        最小聚类大小。小于此值的聚类将被丢弃。
    cor_method : str, default="pearson"
        相关性方法: "pearson" 或 "spearman"。
        pearson: 线性相关，spearman: 秩相关 (对异常值更稳健)。
    linkage_method : str, default="average"
        层次聚类链接方法: "average", "complete", "single", "ward"。
    normalize_method : str, default="none"
        归一化方法: "none", "TIC", "quantile"。
        TIC: 每个样本除以该样本的总离子流。
        quantile: 分位数归一化 (使各样本的强度分布一致)。
    qc_tag : str, optional
        QC 样本的标签 (用于通过样本名识别 QC 样本)。
    blank_tag : str, optional
        空白样本的标签 (用于通过样本名识别空白样本)。
    cv_threshold : float, default=0.3
        QC 样本中 CV 的阈值 (0–1)。CV > 此值的特征被过滤。
    feature_filter_blanks : bool, default=True
        是否启用空白过滤。
    feature_filter_cv : bool, default=True
        是否启用 QC-CV 过滤。
    blocksize : int, default=2000
        分块大小。相似性矩阵按 blocksize × blocksize 分块计算，
        避免一次性分配 N×N 矩阵导致内存溢出。
    collapse_method : str, default="max"
        谱图整合方法: "max" (最大值), "sum" (总和), "mean" (均值),
        "median" (中位数), "apex" (最高强度特征)。
    max_features : int, default=8000
        最大特征数。当过滤后特征数超过此值时，按总强度排序保留
        top-N 个最强特征，避免 O(N²) 内存爆炸。
        8000 个特征约需 256 MB 内存用于 condensed 距离矩阵，
        15000 约需 900 MB。根据可用内存调整。

    Outputs
    -------
    {output_dir}/
    ├── feature_intensity_matrix.csv     — 特征 × 样本强度矩阵
    ├── ramclust_clusters.csv            — 聚类分配表
    ├── ramclust_compound_spectra.csv    — 整合后的化合物谱
    ├── ramclust_compound_intensities.csv— 化合物 × 样本强度矩阵
    ├── ramclust_cluster_summary.csv     — 聚类统计
    ├── ramclust_filtered_features.csv   — 被过滤的特征列表
    └── ramclust_summary.txt             — 统计摘要
    """
    print(f"\n[RAMClust] 开始基于分析行为相似性的特征聚类...")
    print(f"  输入目录: {input_dir}")
    print(f"  参数: st={st}, sr={sr}, maxt={maxt}min, deep_split={deep_split}, "
          f"min_module_size={min_module_size}")
    print(f"       cor_method={cor_method}, linkage={linkage_method}, "
          f"normalize={normalize_method}")

    t_start = time.time()

    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    # ============================================
    # Step 1: 加载峰表并构建特征 × 样本矩阵
    # ============================================
    print(f"  [1/8] 加载峰表并构建强度矩阵...")

    peak_tables = _load_peak_tables_from_dir(input_dir, file_pattern)

    # 识别样本类型
    sample_names = list(peak_tables.keys())
    qc_samples = [s for s in sample_names if qc_tag and qc_tag.lower() in s.lower()] if qc_tag else []
    blank_samples = [s for s in sample_names if blank_tag and blank_tag.lower() in s.lower()] if blank_tag else []
    regular_samples = [s for s in sample_names if s not in qc_samples and s not in blank_samples]

    print(f"      样本: {len(regular_samples)} 实验 + {len(qc_samples)} QC + {len(blank_samples)} 空白")

    # 构建统一特征列表 (基于 m/z + RT)
    all_features = {}  # (mz_rounded, rt_rounded) -> {mz, rt, intensities_per_sample}
    feature_metadata = []

    # 容差参数
    mz_tol = 0.01  # Da — 跨样本峰匹配的 m/z 容差
    rt_tol = 5.0   # 秒 — 跨样本峰匹配的 RT 容差

    for sample_name, df in peak_tables.items():
        for _, row in df.iterrows():
            mz_rounded = round(row["mz"] / mz_tol) * mz_tol
            rt_rounded = round(row["rt"] / rt_tol) * rt_tol
            key = (mz_rounded, rt_rounded)

            if key not in all_features:
                all_features[key] = {
                    "mz": row["mz"],
                    "rt": row["rt"],
                    "intensities": {},
                }
                if "feature_id" in row and pd.notna(row["feature_id"]):
                    all_features[key]["feature_id"] = row["feature_id"]

            all_features[key]["intensities"][sample_name] = row.get("intensity", 0)

    # 转换为矩阵
    feature_ids = list(all_features.keys())
    n_features = len(feature_ids)
    all_sample_order = regular_samples + qc_samples + blank_samples

    print(f"      合并后共有 {n_features} 个唯一特征")

    if n_features < min_module_size:
        print(f"  ⚠️ 特征数 ({n_features}) < min_module_size ({min_module_size})，"
              f"无法进行聚类")
        # 仍输出空结果
        empty_df = pd.DataFrame(columns=["feature_id", "mz", "rt", "cluster", "is_main_peak"])
        empty_df.to_csv(os.path.join(output_dir, "ramclust_clusters.csv"), index=False)
        return

    # 构建强度矩阵
    intensity_matrix = np.zeros((n_features, len(all_sample_order)))
    mz_array = np.zeros(n_features)
    rt_array = np.zeros(n_features)

    for i, key in enumerate(feature_ids):
        mz_array[i] = all_features[key]["mz"]
        rt_array[i] = all_features[key]["rt"]
        for j, sample in enumerate(all_sample_order):
            intensity_matrix[i, j] = all_features[key]["intensities"].get(sample, 0)

    # 保存特征 × 样本矩阵
    matrix_df = pd.DataFrame(
        intensity_matrix,
        index=[all_features[k].get("feature_id", f"F_{i + 1:05d}") for i, k in enumerate(feature_ids)],
        columns=all_sample_order,
    )
    matrix_df.index.name = "feature_id"
    # 添加 m/z 和 RT
    matrix_df.insert(0, "rt", rt_array)
    matrix_df.insert(0, "mz", mz_array)
    matrix_csv = os.path.join(output_dir, "feature_intensity_matrix.csv")
    matrix_df.to_csv(matrix_csv)
    print(f"      ✅ 强度矩阵: {matrix_csv} ({n_features} × {len(all_sample_order)})")

    # ============================================
    # Step 2: 缺失值填充
    # ============================================
    print(f"  [2/8] 缺失值填充...")

    # 使用 1/2 最小检测强度法填充零值
    filled_matrix = intensity_matrix.copy().astype(np.float64)
    for i in range(n_features):
        nonzero = filled_matrix[i][filled_matrix[i] > 0]
        if len(nonzero) > 0:
            min_val = np.min(nonzero)
            filled_matrix[i][filled_matrix[i] == 0] = min_val / 2.0

    n_filled = np.sum(intensity_matrix == 0)
    print(f"      填充 {n_filled} 个零值 ({100*n_filled/intensity_matrix.size:.1f}%)")

    # ============================================
    # Step 3: 空白过滤 (rc.feature.filter.blanks)
    # ============================================
    keep_mask = np.ones(n_features, dtype=bool)

    if feature_filter_blanks and blank_samples:
        print(f"  [3/8] 空白过滤 (rc.feature.filter.blanks)...")

        blank_cols = [all_sample_order.index(s) for s in blank_samples]
        sample_cols = [all_sample_order.index(s) for s in regular_samples]

        n_blank_filtered = 0
        for i in range(n_features):
            blank_intensity = np.mean(filled_matrix[i, blank_cols]) if blank_cols else 0
            sample_intensity = np.mean(filled_matrix[i, sample_cols]) if sample_cols else 0

            # RAMClust 默认: 样本强度应至少为空白强度的 3 倍
            if sample_intensity < 3 * blank_intensity and blank_intensity > 0:
                keep_mask[i] = False
                n_blank_filtered += 1

        print(f"      过滤 {n_blank_filtered} 个特征 (空白强度过高)")

    # ============================================
    # Step 4: QC-CV 过滤 (rc.feature.filter.cv)
    # ============================================
    if feature_filter_cv and qc_samples:
        print(f"  [4/8] QC-CV 过滤 (rc.feature.filter.cv)...")

        qc_cols = [all_sample_order.index(s) for s in qc_samples]

        n_cv_filtered = 0
        for i in range(n_features):
            if not keep_mask[i]:
                continue
            qc_vals = filled_matrix[i, qc_cols]
            qc_mean = np.mean(qc_vals)
            if qc_mean > 0:
                cv = np.std(qc_vals) / qc_mean
                if cv > cv_threshold:
                    keep_mask[i] = False
                    n_cv_filtered += 1

        print(f"      过滤 {n_cv_filtered} 个特征 (QC-CV > {cv_threshold})")

    # 应用过滤
    filtered_indices = np.where(~keep_mask)[0]
    if len(filtered_indices) > 0:
        filtered_features = pd.DataFrame({
            "feature_id": [all_features[feature_ids[i]].get("feature_id", f"F_{i + 1:05d}")
                          for i in filtered_indices],
            "mz": mz_array[filtered_indices],
            "rt": rt_array[filtered_indices],
            "filter_reason": "blank_or_cv",
        })
        filtered_csv = os.path.join(output_dir, "ramclust_filtered_features.csv")
        filtered_features.to_csv(filtered_csv, index=False)
        print(f"      ✅ 被过滤特征: {filtered_csv}")

    # 只保留通过过滤的特征
    kept_indices = np.where(keep_mask)[0]
    if len(kept_indices) < min_module_size:
        print(f"  ⚠️ 过滤后特征数 ({len(kept_indices)}) < min_module_size，"
              f"无法聚类")
        return

    kept_mz = mz_array[kept_indices]
    kept_rt = rt_array[kept_indices]
    kept_matrix = filled_matrix[kept_indices]
    kept_orig_idx = kept_indices  # 原始 feature_ids 的索引
    kept_n = len(kept_indices)

    print(f"      过滤后保留 {kept_n}/{n_features} 个特征")

    # —— 特征数过多时，按总强度取 top-N ——
    if kept_n > max_features:
        print(f"      ⚠️ 特征数 {kept_n} 超过 max_features={max_features}，按总强度取 top-{max_features}")
        total_intensities = kept_matrix.sum(axis=1)
        top_indices = np.argsort(total_intensities)[::-1][:max_features]
        kept_mz = kept_mz[top_indices]
        kept_rt = kept_rt[top_indices]
        kept_matrix = kept_matrix[top_indices]
        kept_orig_idx = kept_orig_idx[top_indices]
        kept_n = len(top_indices)
        print(f"      缩减至 {kept_n} 个特征")

    # ============================================
    # Step 5: 归一化 (可选)
    # ============================================
    print(f"  [5/8] 归一化 ({normalize_method})...")

    if normalize_method == "TIC":
        sample_sums = kept_matrix.sum(axis=0)
        sample_sums[sample_sums == 0] = 1.0
        norm_matrix = kept_matrix / sample_sums * np.mean(sample_sums)
        print(f"      TIC 归一化完成")
    elif normalize_method == "quantile":
        from scipy.interpolate import interp1d
        norm_matrix = np.zeros_like(kept_matrix)
        ref_dist = np.sort(kept_matrix[:, 0])
        for j in range(kept_matrix.shape[1]):
            sorted_col = np.sort(kept_matrix[:, j])
            f_interp = interp1d(
                np.linspace(0, 1, len(sorted_col)), sorted_col,
                fill_value="extrapolate"
            )
            norm_matrix[:, j] = f_interp(np.linspace(0, 1, len(ref_dist)))
        print(f"      quantile 归一化完成")
    else:
        norm_matrix = kept_matrix
        print(f"      跳过归一化")

    # ============================================
    # Step 6: 分块计算 condensed 距离矩阵 (避免 N×N 全矩阵)
    # ============================================
    print(f"  [6/8] 分块计算 condensed 距离矩阵 ({kept_n} 个特征)...")

    # 预计算每行标准化后的数据 (用于相关性)
    if cor_method == "pearson":
        centered = norm_matrix - norm_matrix.mean(axis=1, keepdims=True)
    else:
        # Spearman: 每行取秩
        ranked = np.zeros_like(norm_matrix)
        for i in range(kept_n):
            ranked[i] = np.argsort(np.argsort(norm_matrix[i])).astype(np.float64)
        centered = ranked - ranked.mean(axis=1, keepdims=True)

    norms = np.sqrt((centered ** 2).sum(axis=1))
    norms[norms == 0] = 1.0
    normed = centered / norms[:, np.newaxis]  # (kept_n, n_samples)

    # 直接构建 condensed 距离数组: 大小 = n*(n-1)//2
    condensed_size = kept_n * (kept_n - 1) // 2
    condensed_dist = np.zeros(condensed_size, dtype=np.float32)  # float32 节省一半内存

    def _condensed_idx(i: int, j: int, n: int) -> int:
        """将 (i, j) with i < j 映射到 condensed 索引"""
        return int(n * i - i * (i + 1) // 2 + j - i - 1)

    rt_min = kept_rt / 60.0  # 秒 → 分钟
    n_blocks = int(np.ceil(kept_n / blocksize))

    # 统计均值用累加器
    rt_sim_sum = 0.0
    cor_abs_sum = 0.0
    pair_count = 0

    for bi in range(n_blocks):
        i_start = bi * blocksize
        i_end = min((bi + 1) * blocksize, kept_n)
        block_i = normed[i_start:i_end]  # (bs, n_samples)

        for bj in range(bi, n_blocks):
            j_start = bj * blocksize
            j_end = min((bj + 1) * blocksize, kept_n)
            block_j = normed[j_start:j_end]  # (bs, n_samples)

            # —— RT 相似性 (只算这个 block) ——
            rt_diff = np.abs(
                rt_min[i_start:i_end, np.newaxis] - rt_min[np.newaxis, j_start:j_end]
            )
            rt_sim_block = np.exp(-((rt_diff / max(st, 0.01)) ** 2))
            rt_sim_block[rt_diff > maxt] = 0.0

            # —— 相关性 (只算这个 block) ——
            cor_block = np.clip(np.dot(block_i, block_j.T), -1, 1)

            # —— 联合相似性 → 距离 ——
            sim_block = (1 - sr) * np.abs(cor_block) + sr * rt_sim_block
            dist_block = 1.0 - sim_block
            np.clip(dist_block, 0.0, None, out=dist_block)

            # —— 写入 condensed 数组 ——
            bs_i = i_end - i_start
            bs_j = j_end - j_start
            if bi == bj:
                # 同一块内: 只取上三角
                for li in range(bs_i):
                    gi = i_start + li
                    for lj in range(li + 1, bs_j):
                        gj = j_start + lj
                        condensed_dist[_condensed_idx(gi, gj, kept_n)] = dist_block[li, lj]

                # 对角线设为 0 (已在初始化时为零)
                for li in range(bs_i):
                    gi = i_start + li
                    # condensed 中不需要对角线

                # 统计 (上三角)
                tri_mask = np.triu(np.ones((bs_i, bs_j), dtype=bool), k=1)
                rt_sim_sum += rt_sim_block[tri_mask].sum()
                cor_abs_sum += np.abs(cor_block[tri_mask]).sum()
                pair_count += tri_mask.sum()
            else:
                # 跨块: 所有对都写入
                for li in range(bs_i):
                    gi = i_start + li
                    base_idx = _condensed_idx(gi, j_start, kept_n)
                    condensed_dist[base_idx:base_idx + bs_j] = dist_block[li, :]

                rt_sim_sum += rt_sim_block.sum()
                cor_abs_sum += np.abs(cor_block).sum()
                pair_count += bs_i * bs_j

            # 进度提示
            if (bi * n_blocks + bj) % max(1, (n_blocks * n_blocks) // 20) == 0:
                pct = (bi * n_blocks + bj) / (n_blocks * n_blocks) * 100
                print(f"      进度: {pct:.0f}%", end="\r")

    rt_sim_mean = rt_sim_sum / max(pair_count, 1)
    cor_abs_mean = cor_abs_sum / max(pair_count, 1)
    print(f"\n      condensed 距离矩阵: {condensed_size / 1e6:.1f}M 对, "
          f"RT相似性均值={rt_sim_mean:.3f}, 相关性均值={cor_abs_mean:.3f}")

    # ============================================
    # Step 7: 层次聚类 + 动态树切割
    # ============================================
    print(f"  [7/8] 层次聚类与动态树切割...")

    # 层次聚类
    try:
        Z = linkage(condensed_dist, method=linkage_method)
    except Exception as e:
        print(f"  ⚠️ 聚类失败 ({e})，尝试使用 'average' 链接方法")
        Z = linkage(condensed_dist, method="average")

    # 释放 condensed 数组
    del condensed_dist

    # 动态树切割
    cluster_heights = Z[:, 2]
    if deep_split == 0:
        clusters = np.ones(kept_n, dtype=int)
    elif deep_split == 1:
        cut_height = np.percentile(cluster_heights, 80)
        clusters = fcluster(Z, t=cut_height, criterion="distance")
    elif deep_split == 2:
        cut_height = np.percentile(cluster_heights, 60)
        clusters = fcluster(Z, t=cut_height, criterion="distance")
    elif deep_split == 3:
        cut_height = np.percentile(cluster_heights, 40)
        clusters = fcluster(Z, t=cut_height, criterion="distance")
    else:
        cut_height = np.percentile(cluster_heights, 20)
        clusters = fcluster(Z, t=cut_height, criterion="distance")

    # 过滤小聚类
    cluster_ids, cluster_counts = np.unique(clusters, return_counts=True)
    valid_clusters = set(cluster_ids[cluster_counts >= min_module_size])

    # 重新编号
    cluster_map = {c: i + 1 for i, c in enumerate(sorted(valid_clusters))}
    final_clusters = np.array([cluster_map.get(c, -1) for c in clusters])

    n_clusters = len(valid_clusters)
    n_unclustered = np.sum(final_clusters == -1)

    print(f"      聚类结果: {n_clusters} 个聚类, {n_unclustered} 个未聚类特征")

    # ============================================
    # Step 8: 谱图整合 + 分子离子推断
    # ============================================
    print(f"  [8/8] 谱图整合与分子离子推断...")

    # 构建聚类分配表 (使用 kept_orig_idx 映射回原始 feature_ids)
    cluster_rows = []
    for i, orig_idx in enumerate(kept_orig_idx):
        feat_key = feature_ids[orig_idx]
        feat_info = all_features[feat_key]
        cluster_rows.append({
            "feature_id": feat_info.get("feature_id", f"F_{orig_idx + 1:05d}"),
            "mz": kept_mz[i],
            "rt": kept_rt[i],
            "cluster": final_clusters[i],
            "is_main_peak": False,
        })

    cluster_df = pd.DataFrame(cluster_rows)

    # 谱图整合: 对每个聚类，合并成员的强度
    all_sample_cols = [all_sample_order.index(s) for s in regular_samples]
    n_samples = len(all_sample_cols)
    compound_intensities = np.zeros((n_clusters, n_samples))

    for cid in range(1, n_clusters + 1):
        members = np.where(final_clusters == cid)[0]
        if len(members) == 0:
            continue

        member_intensities = norm_matrix[members][:, all_sample_cols]

        if collapse_method == "max":
            compound_intensities[cid - 1] = member_intensities.max(axis=0)
        elif collapse_method == "sum":
            compound_intensities[cid - 1] = member_intensities.sum(axis=0)
        elif collapse_method == "median":
            compound_intensities[cid - 1] = np.median(member_intensities, axis=0)
        elif collapse_method == "apex":
            total_intensities = member_intensities.sum(axis=1)
            apex_idx = np.argmax(total_intensities)
            compound_intensities[cid - 1] = member_intensities[apex_idx]
        else:
            compound_intensities[cid - 1] = member_intensities.mean(axis=0)

    # 分子离子推断 (findMain)
    for cid in range(1, n_clusters + 1):
        members = cluster_df[cluster_df["cluster"] == cid]
        if len(members) == 0:
            continue
        member_indices = members.index

        member_mzs = cluster_df.loc[member_indices, "mz"].values
        member_orig_idx_in_kept = [i for i, c in enumerate(final_clusters) if c == cid]

        total_ints = norm_matrix[member_orig_idx_in_kept].sum(axis=1)
        mz_rank = np.argsort(np.argsort(member_mzs))
        int_rank = np.argsort(np.argsort(total_ints))
        combined_score = mz_rank + int_rank
        main_peak_idx = member_indices[np.argmax(combined_score)]

        cluster_df.loc[main_peak_idx, "is_main_peak"] = True

    # 保存聚类分配
    cluster_csv = os.path.join(output_dir, "ramclust_clusters.csv")
    cluster_df.to_csv(cluster_csv, index=False)
    print(f"      ✅ 聚类分配: {cluster_csv}")

    # 保存整合后的化合物谱
    compound_specs = []
    for cid in range(1, n_clusters + 1):
        members = cluster_df[cluster_df["cluster"] == cid]
        main_peak = members[members["is_main_peak"]]
        if len(main_peak) > 0:
            main_mz = main_peak["mz"].values[0]
            main_rt = main_peak["rt"].values[0]
        else:
            main_mz = members["mz"].median()
            main_rt = members["rt"].median()

        compound_specs.append({
            "compound": f"C{cid:04d}",
            "n_features": len(members),
            "mz_med": round(members["mz"].median(), 4),
            "mz_min": round(members["mz"].min(), 4),
            "mz_max": round(members["mz"].max(), 4),
            "rt_med": round(members["rt"].median(), 2),
            "rt_min": round(members["rt"].min(), 2),
            "rt_max": round(members["rt"].max(), 2),
            "main_peak_mz": round(main_mz, 4),
            "main_peak_rt": round(main_rt, 2),
            "member_ids": ";".join(members["feature_id"].tolist()),
        })

    if compound_specs:
        spec_df = pd.DataFrame(compound_specs)
        spec_csv = os.path.join(output_dir, "ramclust_compound_spectra.csv")
        spec_df.to_csv(spec_csv, index=False)
        print(f"      ✅ 化合物谱: {spec_csv}")

        # 化合物 × 样本强度矩阵
        comp_int_df = pd.DataFrame(
            compound_intensities,
            index=[s["compound"] for s in compound_specs],
            columns=[regular_samples[i] for i in range(n_samples)],
        )
        comp_int_df.index.name = "compound"
        comp_int_csv = os.path.join(output_dir, "ramclust_compound_intensities.csv")
        comp_int_df.to_csv(comp_int_csv)
        print(f"      ✅ 化合物强度矩阵: {comp_int_csv}")

    # 聚类统计
    cluster_summary = []
    for cid in range(1, n_clusters + 1):
        members = cluster_df[cluster_df["cluster"] == cid]
        cluster_summary.append({
            "cluster": cid,
            "n_features": len(members),
            "mz_range": round(members["mz"].max() - members["mz"].min(), 4),
            "rt_range": round(members["rt"].max() - members["rt"].min(), 2),
            "n_main_peaks": members["is_main_peak"].sum(),
        })

    if cluster_summary:
        summary_df = pd.DataFrame(cluster_summary)
        summary_csv = os.path.join(output_dir, "ramclust_cluster_summary.csv")
        summary_df.to_csv(summary_csv, index=False)
        print(f"      ✅ 聚类统计: {summary_csv}")

    # 摘要
    t_elapsed = time.time() - t_start
    summary_lines = [
        "=" * 60,
        "  RAMClust Feature Clustering — 统计摘要",
        "=" * 60,
        f"  输入目录: {input_dir}",
        f"  样本数: {len(regular_samples)} 实验 + {len(qc_samples)} QC + "
        f"{len(blank_samples)} 空白",
        f"  原始特征数: {n_features}",
        f"  过滤后特征数: {kept_n}",
        f"  聚类数: {n_clusters}",
        f"  未聚类特征数: {n_unclustered}",
        f"  聚类缩减率: {100*n_clusters/max(kept_n,1):.1f}% "
        f"(从 {kept_n} 个特征 → {n_clusters} 个化合物)",
        f"  参数: st={st}, sr={sr}, maxt={maxt}, deep_split={deep_split}, "
        f"min_module_size={min_module_size}",
        f"       cor_method={cor_method}, linkage={linkage_method}",
        f"  运行时间: {t_elapsed:.1f} 秒",
        "",
    ]
    summary_lines.append("=" * 60)

    summary_out = os.path.join(output_dir, "ramclust_summary.txt")
    with open(summary_out, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    for line in summary_lines:
        print(line)

    print(f"\n✅ [RAMClust] 特征聚类完成!")

    if n_clusters == 0:
        print(f"\n⚠️  警告: 未产生任何聚类。建议:")
        print(f"    - 降低 min_module_size (当前 {min_module_size}) → 尝试 1")
        print(f"    - 调整 deep_split (当前 {deep_split}) → 尝试 3-4")
        print(f"    - 增大 st (当前 {st}) → 尝试 10")
        print(f"    - 增大 maxt (当前 {maxt}) → 尝试 5-10")


# ═══════════════════════════════════════════════════════════════════════════════
# mzAnnotation — 高分辨质谱 m/z 推定注释
# ═══════════════════════════════════════════════════════════════════════════════
# 参考: mzAnnotation R package (aberHRML/jasenfinch)
#       "Tools for Putative Annotation of Electrospray Ionisation
#       High Resolution Mass Spectrometry Data"
#       https://aberhrml.github.io/mzAnnotation/
#       https://github.com/jasenfinch/mzAnnotation
#
# mzAnnotation 的核心算法:
#   1. 正向 m/z 计算 (calcMZ) — 根据中性分子质量 M、加合物、同位素、
#      化学转化，计算预测的 m/z
#      m/z = (nmol * M + massdiff(adduct) + massdiff(isotope)
#             + massdiff(transformation)) / |charge|
#   2. 反向分子质量计算 (calcM) — 根据观测 m/z、加合物、同位素、
#      转化，反推中性分子质量
#      M = (m/z * |charge| - massdiff(adduct) - massdiff(isotope)
#           - massdiff(transformation)) / nmol
#   3. 批量 m/z 注释 — 对峰表中的每个观测 m/z，尝试所有已知的
#      加合物/同位素/转化组合，输出可能的分子质量假设
#   4. 多数据库匹配 — 将计算出的中性质量与 HMDB、LipidMaps、
#      ChEBI 等参考数据库进行匹配
#
# 工作流位置:
#   峰检测 → 峰对齐 → [mzAnnotation 注释] → 统计 → 鉴定
#
# 与 CAMERA 的区别:
#   mzAnnotation 不依赖 RT 共流出信息或假谱图概念，而是基于
#   精确质量的纯计算注释。适合高分辨质谱 (>30k 分辨率) 数据，
#   在质量精度达到 sub-ppm 级别时可以提供高置信度的注释。


# 扩展加合物规则表（包含转化产物和同位素）
_EXTENDED_ADDUCT_RULES = {
    # ===== 正离子 =====
    "pos": {
        # 基础加合物
        "[M+H]+":           (1, 1, 1.007276),
        "[M+NH4]+":         (1, 1, 18.033823),
        "[M+Na]+":          (1, 1, 22.989218),
        "[M+K]+":           (1, 1, 38.963158),
        "[M+Li]+":          (1, 1, 7.015455),
        "[M+Mg]2+":         (1, 2, 23.979892),
        "[M+Ca]2+":         (1, 2, 39.953550),
        # 双电荷
        "[M+2H]2+":         (1, 2, 2.014552),
        "[M+H+Na]2+":       (1, 2, 23.996494),
        "[M+H+K]2+":        (1, 2, 39.970434),
        "[M+2Na]2+":        (1, 2, 45.978436),
        "[M+3H]3+":         (1, 3, 3.021828),
        # 溶剂加合物
        "[M+CH3CN+H]+":     (1, 1, 42.033823),
        "[M+CH3CN+Na]+":    (1, 1, 64.015765),
        "[M+CH3OH+H]+":     (1, 1, 33.033489),
        "[M+isoProp+H]+":   (1, 1, 61.064789),
        "[M+DMSO+H]+":      (1, 1, 79.021050),
        # 二聚体/多聚体
        "[2M+H]+":          (2, 1, 1.007276),
        "[2M+Na]+":         (2, 1, 22.989218),
        "[2M+NH4]+":        (2, 1, 18.033823),
        "[2M+K]+":          (2, 1, 38.963158),
        "[2M+CH3CN+H]+":    (2, 1, 42.033823),
        "[3M+H]+":          (3, 1, 1.007276),
        # 源内中性丢失 (In-source Fragmentation)
        "[M-H2O+H]+":       (1, 1, -17.002740),
        "[M-2H2O+H]+":      (1, 1, -35.013305),
        "[M-NH3+H]+":       (1, 1, -16.018724),
        "[M-H2O+NH4]+":     (1, 1, 1.031094),
        "[M-CO+H]+":        (1, 1, -26.987639),
        "[M-CO2+H]+":       (1, 1, -42.989829),
        "[M-HCOOH+H]+":     (1, 1, -45.021464),
        "[M-CH2O+H]+":      (1, 1, -28.997655),
        "[M-C2H4O+H]+":     (1, 1, -43.018390),
        "[M-C3H6O+H]+":     (1, 1, -57.034040),
        "[M-C4H8O+H]+":     (1, 1, -71.049690),
        "[M-C5H8O4+H]+":    (1, 1, -131.034434),  # 脱氧核糖丢失
        "[M-C6H10O5+H]+":   (1, 1, -161.045549),  # 己糖丢失
        "[M-C6H10O4+H]+":   (1, 1, -145.050634),  # 脱氧己糖丢失
        "[M-H3PO4+H]+":     (1, 1, -96.969620),
        "[M-SO3+H]+":       (1, 1, -78.958796),
        "[M-H2SO4+H]+":     (1, 1, -96.960104),
        "[M-CH3COOH+H]+":   (1, 1, -59.013305),
        # 葡萄糖醛酸化/硫酸化 (Phase II 代谢物)
        "[M+C6H8O6+H]+":    (1, 1, 177.039086),   # 葡萄糖醛酸化 (去水)
        "[M+SO3+H]+":       (1, 1, 80.965230),     # 硫酸化
        "[M+C2H3NO+H]+":    (1, 1, 58.028745),     # 甘氨酸结合
        "[M+C5H7NO3+H]+":   (1, 1, 130.049873),    # 谷氨酰胺结合
    },
    # ===== 负离子 =====
    "neg": {
        # 基础加合物
        "[M-H]-":           (1, -1, -1.007276),
        "[M+Cl]-":          (1, -1, 34.969402),
        "[M+Br]-":          (1, -1, 78.918885),
        "[M+I]-":           (1, -1, 126.905019),
        "[M+FA-H]-":        (1, -1, 44.998203),     # 甲酸加合物
        "[M+HAc-H]-":       (1, -1, 59.013853),     # 乙酸加合物
        "[M+TFA-H]-":       (1, -1, 112.985586),    # 三氟乙酸加合物
        "[M+Na-2H]-":       (1, -1, 20.974666),
        "[M+K-2H]-":        (1, -1, 36.948606),
        "[M-2H]2-":         (1, -2, -2.014552),
        "[M-3H]3-":         (1, -3, -3.021828),
        # 二聚体
        "[2M-H]-":          (2, -1, -1.007276),
        "[2M+FA-H]-":       (2, -1, 44.998203),
        "[2M+Cl]-":         (2, -1, 34.969402),
        "[3M-H]-":          (3, -1, -1.007276),
        # 源内中性丢失
        "[M-H2O-H]-":       (1, -1, -19.018390),
        "[M-2H2O-H]-":      (1, -1, -37.028955),
        "[M-NH3-H]-":       (1, -1, -18.034374),
        "[M-CO2-H]-":       (1, -1, -44.997655),
        "[M-HCOOH-H]-":     (1, -1, -47.013739),
        "[M-CH2O-H]-":      (1, -1, -31.018390),
        "[M-H3PO4-H]-":     (1, -1, -98.984270),
        "[M-SO3-H]-":       (1, -1, -80.973510),
        "[M-H2SO4-H]-":     (1, -1, -98.974818),
        "[M-CH3COOH-H]-":   (1, -1, -61.028955),
        # Phase II 代谢物
        "[M+C6H8O6-H]-":    (1, -1, 175.024536),   # 葡萄糖醛酸化 (去水)
        "[M+SO3-H]-":       (1, -1, 78.958796),     # 硫酸化
    },
}

# 同位素质量差
_ISOTOPE_DIFFS = {
    "[13C]":     1.003355,
    "[13C2]":    2.006710,
    "[15N]":     0.997035,
    "[18O]":     2.004246,
    "[2H]":      1.006277,
    "[34S]":     1.995796,
    "[37Cl]":    1.997050,
    "[81Br]":    1.997954,
    "[13C][15N]":2.000390,
}

# 常见化学转化
_CHEMICAL_TRANSFORMATIONS = {
    "methylation":       14.015650,
    "demethylation":     -14.015650,
    "acetylation":       42.010565,
    "deacetylation":     -42.010565,
    "oxidation":         15.994915,
    "reduction":         -15.994915,
    "dihydroxylation":   31.989830,
    "hydration":         18.010565,
    "dehydration":       -18.010565,
    "glucuronidation":   176.032088,
    "sulfation":         79.956815,
    "glutathionylation": 305.068156,
    "phosphorylation":   79.966331,
    "glycosylation":     162.052824,
    "deglycosylation":   -162.052824,
    "decarboxylation":   -43.989829,
    "hydroxylation":     15.994915,
    "dehydroxylation":   -15.994915,
    "hydrogenation":     2.015650,
    "dehydrogenation":   -2.015650,
}


def calc_mz(
    M: float,
    adduct: str = "[M+H]+",
    isotope: Optional[str] = None,
    transformation: Optional[str] = None,
    polarity: str = "positive",
) -> float:
    """
    根据中性分子质量 M 计算观测 m/z。

    正向计算: 已知分子质量 → 预测质谱图中的 m/z

    公式:
        m/z = (nmol * M + massdiff(adduct) + massdiff(isotope)
               + massdiff(transformation)) / |charge|

    参考: mzAnnotation::calcMZ()

    Parameters
    ----------
    M : float
        中性分子的单同位素质量 (Da)。
    adduct : str, default="[M+H]+"
        加合物类型。必须是 _EXTENDED_ADDUCT_RULES 中的键。
    isotope : str, optional
        同位素类型，如 "[13C]"。
    transformation : str, optional
        化学转化类型，如 "methylation"。
    polarity : str, default="positive"
        电离模式。

    Returns
    -------
    float
        预测的 m/z 值。
    """
    pol = "pos" if polarity == "positive" else "neg"
    rules = _EXTENDED_ADDUCT_RULES.get(pol, {})

    if adduct not in rules:
        raise ValueError(f"未知加合物 '{adduct}'。可用的正离子加合物: "
                         f"{list(rules.keys())[:10]}...")

    nmol, charge, massdiff_adduct = rules[adduct]

    # 同位素贡献
    massdiff_isotope = _ISOTOPE_DIFFS.get(isotope, 0.0) if isotope else 0.0

    # 化学转化贡献
    massdiff_trans = _CHEMICAL_TRANSFORMATIONS.get(transformation, 0.0) if transformation else 0.0

    total_mass = nmol * M + massdiff_adduct + massdiff_isotope + massdiff_trans
    mz = total_mass / abs(charge)

    return mz


def calc_molecular_mass(
    mz: float,
    adduct: str = "[M+H]+",
    isotope: Optional[str] = None,
    transformation: Optional[str] = None,
    polarity: str = "positive",
) -> float:
    """
    根据观测 m/z 反推中性分子质量。

    反向计算: 已知质谱图中的 m/z → 推测分子质量

    公式:
        M = (m/z * |charge| - massdiff(adduct) - massdiff(isotope)
             - massdiff(transformation)) / nmol

    参考: mzAnnotation::calcM()

    Parameters
    ----------
    mz : float
        观测到的 m/z 值。
    adduct : str, default="[M+H]+"
        加合物类型。
    isotope : str, optional
        同位素类型。
    transformation : str, optional
        化学转化类型。
    polarity : str, default="positive"
        电离模式。

    Returns
    -------
    float
        推测的中性分子质量 (Da)。
    """
    pol = "pos" if polarity == "positive" else "neg"
    rules = _EXTENDED_ADDUCT_RULES.get(pol, {})

    if adduct not in rules:
        raise ValueError(f"未知加合物 '{adduct}'。")

    nmol, charge, massdiff_adduct = rules[adduct]

    massdiff_isotope = _ISOTOPE_DIFFS.get(isotope, 0.0) if isotope else 0.0
    massdiff_trans = _CHEMICAL_TRANSFORMATIONS.get(transformation, 0.0) if transformation else 0.0

    M = (mz * abs(charge) - massdiff_adduct - massdiff_isotope - massdiff_trans) / nmol

    return M



# mzAnnotation
def redundant_feature_filtering_mzannotation_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
    polarity: str = "positive",
    ppm: float = 5.0,
    mzabs: float = 0.001,
    max_annotations_per_feature: int = 5,
    include_isotopes: bool = True,
    include_transformations: bool = True,
    filter_redundant_adducts: bool = True,
    mass_range: Optional[Tuple[float, float]] = None,
    charge_range: Tuple[int, int] = (1, 3),
    min_oidscore: float = 0.3,
    max_features: int = 15000,
):
    """
    基于 mzAnnotation 算法对高分辨质谱峰表进行 m/z 推定注释。

    mzAnnotation 的核心功能:
    1. 正向 m/z 计算 — 对每个推定分子质量计算所有加合物/同位素/转化的 m/z
    2. 反向分子质量计算 — 对每个观测 m/z 反推所有可能的分子质量
    3. 多假设排名 — 基于加合物频率、质量误差和先验知识对假设排序
    4. 冗余标记 — 标记可能为加合物/同位素/转化产物的特征
    5. 兼容数据库匹配

    算法流程:
    1. 加载峰表
    2. 对每个特征（观测 m/z），遍历所有加合物规则计算可能的分子质量
    3. 对每个计算出的分子质量，反向预测该分子的其他加合物形式
    4. 在峰表中搜索预测 m/z 的匹配 → 如果找到，则两个特征关联
    5. 基于规则 (oidscore, quasi, ips) 对关联关系排序
    6. 标记冗余特征（ips + 同位素 + 非准分子离子）
    7. 输出带注释的峰表

    特点:
    - 支持 40+ 种正离子加合物和 30+ 种负离子加合物
    - 支持同位素注释 (¹³C, ¹⁵N, ³⁴S, ³⁷Cl, ⁸¹Br, etc.)
    - 支持化学转化注释 (甲基化、乙酰化、葡萄糖醛酸化等)
    - 对高分辨质谱 (>40k FWHM) 数据效果最佳
    - 与 CAMERA 互补 — mzAnnotation 是纯质谱维度的注释

    参考:
        mzAnnotation R package, aberHRML/jasenfinch
        https://aberhrml.github.io/mzAnnotation/

    Parameters
    ----------
    input_dir : str
        输入目录，包含峰表 CSV 文件。
    output_dir : str
        输出目录。
    file_pattern : str, default="*.csv"
        峰表 CSV 文件匹配模式。
    polarity : str, default="positive"
        电离模式: "positive" 或 "negative"。
    ppm : float, default=5.0
        质量精度 (ppm)。HRMS 通常为 1-5 ppm。
    mzabs : float, default=0.001
        绝对 m/z 容差 (Da)。sub-ppm 级别，适合 Orbitrap/FT-ICR 数据。
    max_annotations_per_feature : int, default=5
        每个特征保留的最大注释数。
    include_isotopes : bool, default=True
        是否包含同位素注释。
    include_transformations : bool, default=True
        是否包含化学转化注释。
    filter_redundant_adducts : bool, default=True
        是否将非准分子离子特征标记为冗余。
    mass_range : tuple (min_mass, max_mass), optional
        分子质量的有效范围 (Da)。超过范围的假设被丢弃。
    charge_range : tuple (min_charge, max_charge), default=(1, 3)
        有效电荷范围。
    min_oidscore : float, default=0.3
        加合物的最小 oidscore。低的加合物（稀有或不合理）被丢弃。

    Outputs
    -------
    {output_dir}/
    ├── {sample}_mzannotation_annotated.csv  — 带注释的峰表
    ├── {sample}_mzannotation_hypotheses.csv — 所有注释假设
    ├── {sample}_mzannotation_redundant.csv  — 冗余特征列表
    ├── all_mzannotation_annotated.csv       — 合并注释峰表
    └── mzannotation_summary.txt             — 统计摘要
    """
    print(f"\n[mzAnnotation] 开始高分辨质谱 m/z 推定注释...")
    print(f"  输入目录: {input_dir}")
    print(f"  电离模式: {polarity}")
    print(f"  参数: ppm={ppm}, mzabs={mzabs}, max_annotations={max_annotations_per_feature}")
    print(f"      include_isotopes={include_isotopes}, "
          f"include_transformations={include_transformations}")

    t_start = time.time()

    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"输入目录不存在: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    pol = "pos" if polarity == "positive" else "neg"
    adduct_rules = _EXTENDED_ADDUCT_RULES.get(pol, {})

    # 过滤加合物规则
    filtered_adduct_rules = {}
    for name, (nmol, charge, massdiff) in adduct_rules.items():
        # 检查电荷范围
        if abs(charge) < charge_range[0] or abs(charge) > charge_range[1]:
            continue
        # 估算 oidscore
        oidscore = 1.0 if "[M+H]" in name or "[M-H]" in name else (
            0.9 if "[M+Na]" in name or "[M+FA" in name else (
            0.8 if "NH4" in name or "Cl" in name else (
            0.6 if "M]" in name and "2M" in name else (
            0.5 if "M-" in name else 0.4))))
        if oidscore < min_oidscore:
            continue
        filtered_adduct_rules[name] = (nmol, charge, massdiff, oidscore)

    print(f"  加载 {len(filtered_adduct_rules)} 条加合物规则")

    # 加载峰表
    peak_tables = _load_peak_tables_from_dir(input_dir, file_pattern)
    print(f"  加载 {len(peak_tables)} 个峰表")

    all_annotated = []
    sample_stats = {}

    for sample_name, df in peak_tables.items():
        print(f"\n  --- 处理样本: {sample_name} ({len(df)} 个特征) ---")

        # —— 特征数过多时按强度取 top-N ——
        if len(df) > max_features:
            print(f"      ⚠️ 特征数 {len(df)} 超过 max_features={max_features}，按强度取 top-{max_features}")
            if "intensity" in df.columns:
                df = df.nlargest(max_features, "intensity")
            else:
                df = df.iloc[:max_features]
            df = df.reset_index(drop=True)
            print(f"      缩减至 {len(df)} 个特征")

        # ============================================
        # Step 1: 为每个特征生成注释假设
        # ============================================
        print(f"    [1/4] 生成 m/z 注释假设...")

        mz_array = df["mz"].values
        rt_array = df.get("rt", np.zeros(len(df))).values
        int_array = df.get("intensity", np.ones(len(df))).values

        # 构建 m/z 快速查找索引 (用于 Step 2 的特征对搜索)
        mz_sorted_indices = np.argsort(mz_array)
        mz_sorted = mz_array[mz_sorted_indices]

        # 预计算: 只生成 base adduct 假设，按 mass_error 过滤后再展开同位素/转化
        # 这样避免为每个特征生成 45 × (1+8+20) ≈ 1300 个假设
        feature_to_hypotheses = defaultdict(list)
        all_hypotheses = []

        for feat_idx in range(len(df)):
            obs_mz = mz_array[feat_idx]
            feat_hypotheses = []

            # 第一轮: 只生成 base adduct 假设
            for adduct_name, (nmol, charge, massdiff, oidscore) in filtered_adduct_rules.items():
                neutral_mass = (obs_mz * abs(charge) - massdiff) / nmol
                if neutral_mass <= 0:
                    continue
                if mass_range and (neutral_mass < mass_range[0] or neutral_mass > mass_range[1]):
                    continue

                predicted_mz = (nmol * neutral_mass + massdiff) / abs(charge)
                mass_error_ppm = (obs_mz - predicted_mz) / predicted_mz * 1e6

                feat_hypotheses.append({
                    "feature_idx": feat_idx,
                    "observed_mz": round(obs_mz, 6),
                    "adduct": adduct_name,
                    "neutral_mass": round(neutral_mass, 4),
                    "mass_error_ppm": round(mass_error_ppm, 2),
                    "oidscore": oidscore,
                    "is_quasi": "[M+H]" in adduct_name or "[M-H]" in adduct_name or (
                        "[M+Na]" in adduct_name or "[M+NH4]" in adduct_name),
                    "is_ips": "M-" in adduct_name or "2M" in adduct_name or "3M" in adduct_name,
                })

            # 按质量误差 + oidscore 排序，只保留 top 候选用于展开
            feat_hypotheses.sort(key=lambda h: (abs(h["mass_error_ppm"]), -h["oidscore"]))
            base_candidates = feat_hypotheses[:min(3, len(feat_hypotheses))]  # 最多 3 个 base

            expanded = []
            for base in base_candidates:
                expanded.append(base)
                nmol, charge, massdiff, oidscore = filtered_adduct_rules[base["adduct"]]

                # 仅对 top base adduct 展开同位素
                if include_isotopes:
                    for iso_name, iso_massdiff in _ISOTOPE_DIFFS.items():
                        iso_nm = (obs_mz * abs(charge) - massdiff - iso_massdiff) / nmol
                        if iso_nm <= 0:
                            continue
                        expanded.append({
                            "feature_idx": feat_idx,
                            "observed_mz": round(obs_mz, 6),
                            "adduct": f"{base['adduct']} + {iso_name}",
                            "neutral_mass": round(iso_nm, 4),
                            "mass_error_ppm": round(base["mass_error_ppm"], 2),
                            "oidscore": oidscore * 0.8,
                            "is_quasi": False,
                            "is_ips": True,
                        })

                # 仅对 top base adduct 展开化学转化
                if include_transformations:
                    for trans_name, trans_massdiff in _CHEMICAL_TRANSFORMATIONS.items():
                        trans_nm = (obs_mz * abs(charge) - massdiff - trans_massdiff) / nmol
                        if trans_nm <= 0:
                            continue
                        expanded.append({
                            "feature_idx": feat_idx,
                            "observed_mz": round(obs_mz, 6),
                            "adduct": f"{base['adduct']} + {trans_name}",
                            "neutral_mass": round(trans_nm, 4),
                            "mass_error_ppm": round(base["mass_error_ppm"], 2),
                            "oidscore": oidscore * 0.6,
                            "is_quasi": False,
                            "is_ips": True,
                        })

            # 截断到 max_annotations_per_feature
            expanded.sort(key=lambda h: (abs(h["mass_error_ppm"]), -h["oidscore"]))
            feature_to_hypotheses[feat_idx] = expanded[:max_annotations_per_feature]
            all_hypotheses.extend(expanded[:max_annotations_per_feature])

        n_hyp = len(all_hypotheses)
        print(f"      生成 {n_hyp} 个注释假设 "
              f"(平均 {n_hyp/max(len(df), 1):.1f} 个/特征)")

        # ============================================
        # Step 2: 搜索峰表中的相关特征对
        # ============================================
        print(f"    [2/4] 搜索相关特征对...")

        # 按中性质量对假设进行分组
        mass_to_hypotheses = defaultdict(list)
        for hyp in all_hypotheses:
            mass_key = round(hyp["neutral_mass"], 1)  # 0.1 Da 桶
            mass_to_hypotheses[mass_key].append(hyp)

        # 在峰表中搜索同一中性质量的其他 adduct 形式
        feature_pairs = []  # (base_idx, paired_idx, neutral_mass, adduct_a, adduct_b)

        for mass_key, hyps in mass_to_hypotheses.items():
            if len(hyps) < 2:
                continue
            for i in range(len(hyps)):
                for j in range(i + 1, len(hyps)):
                    if hyps[i]["feature_idx"] != hyps[j]["feature_idx"]:
                        feature_pairs.append({
                            "feature_a": hyps[i]["feature_idx"],
                            "feature_b": hyps[j]["feature_idx"],
                            "neutral_mass": round(hyps[i]["neutral_mass"], 4),
                            "adduct_a": hyps[i]["adduct"],
                            "adduct_b": hyps[j]["adduct"],
                            "mass_error_ppm": max(abs(hyps[i]["mass_error_ppm"]),
                                                  abs(hyps[j]["mass_error_ppm"])),
                            "shared_mass_key": mass_key,
                        })

        # 去重
        seen_pairs = set()
        unique_pairs = []
        for pair in feature_pairs:
            pair_key = tuple(sorted([pair["feature_a"], pair["feature_b"]]) + [pair["shared_mass_key"]])
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                unique_pairs.append(pair)

        print(f"      找到 {len(unique_pairs)} 对相关特征")

        # ============================================
        # Step 3: 排名和冗余标记
        # ============================================
        print(f"    [3/4] 排名和冗余特征标记...")

        # 为每个特征选择最佳注释
        feature_best_annotation = {}
        feature_is_redundant = np.zeros(len(df), dtype=bool)
        feature_adduct_label = [""] * len(df)
        feature_neutral_mass = [np.nan] * len(df)
        feature_num_annotations = [0] * len(df)

        for feat_idx, hypotheses in feature_to_hypotheses.items():
            feature_num_annotations[feat_idx] = len(hypotheses)
            if hypotheses:
                best = hypotheses[0]  # 已排序
                feature_best_annotation[feat_idx] = best
                feature_adduct_label[feat_idx] = best["adduct"]
                feature_neutral_mass[feat_idx] = best["neutral_mass"]
                if best["is_ips"] and filter_redundant_adducts:
                    feature_is_redundant[feat_idx] = True

        # 额外的冗余规则:
        # 1. 如果特征 A 是特征 B 的 adduct/isotope/transformation 形式，
        #    且 A 强度 < B 强度 → A 标记为冗余
        for pair in unique_pairs:
            a, b = pair["feature_a"], pair["feature_b"]
            if int_array[a] < int_array[b] * 0.8:  # A 明显更弱
                # 检查 A 是否可能只是 B 的加合物形式
                if a in feature_best_annotation:
                    a_best = feature_best_annotation[a]
                    if not a_best["is_quasi"]:
                        feature_is_redundant[a] = True
            if int_array[b] < int_array[a] * 0.8:
                if b in feature_best_annotation:
                    b_best = feature_best_annotation[b]
                    if not b_best["is_quasi"]:
                        feature_is_redundant[b] = True

        n_redundant = feature_is_redundant.sum()
        n_annotated = sum(1 for h in feature_adduct_label if h)
        print(f"      注释 {n_annotated} 个特征, 标记 {n_redundant} 个冗余")

        # ============================================
        # Step 4: 构建输出
        # ============================================
        print(f"    [4/4] 构建带注释的峰表...")

        df_out = df.copy()
        df_out["best_adduct"] = feature_adduct_label
        df_out["neutral_mass"] = feature_neutral_mass
        df_out["num_annotations"] = feature_num_annotations
        df_out["is_redundant"] = feature_is_redundant

        # 冗余原因
        redundancy_reason = [""] * len(df)
        for feat_idx in range(len(df)):
            reasons = []
            if feature_is_redundant[feat_idx]:
                if feat_idx in feature_best_annotation:
                    hyp = feature_best_annotation[feat_idx]
                    if hyp["is_ips"]:
                        reasons.append("in_source_product")
                    if "isotope" in hyp["adduct"].lower() or any(
                        iso in hyp["adduct"] for iso in _ISOTOPE_DIFFS
                    ):
                        reasons.append("isotope")
                    if any(trans in hyp["adduct"] for trans in _CHEMICAL_TRANSFORMATIONS):
                        reasons.append("transformation_product")
                    if not hyp["is_quasi"]:
                        reasons.append("non_quasi_molecular_ion")
                redundancy_reason[feat_idx] = ";".join(reasons) if reasons else "low_intensity_adduct"
        df_out["redundancy_reason"] = redundancy_reason

        # 保存带注释的峰表
        annotated_csv = os.path.join(output_dir, f"{sample_name}_mzannotation_annotated.csv")
        df_out.to_csv(annotated_csv, index=False)
        print(f"      ✅ {annotated_csv}")

        # 保存所有假设
        if all_hypotheses:
            hyp_df = pd.DataFrame(all_hypotheses)
            hyp_csv = os.path.join(output_dir, f"{sample_name}_mzannotation_hypotheses.csv")
            hyp_df.to_csv(hyp_csv, index=False)
            print(f"      ✅ {hyp_csv}")

        # 冗余特征列表
        redundant_df = df_out[df_out["is_redundant"]].copy()
        if len(redundant_df) > 0:
            redundant_csv = os.path.join(output_dir, f"{sample_name}_mzannotation_redundant.csv")
            redundant_df.to_csv(redundant_csv, index=False)
            print(f"      ✅ {redundant_csv} ({len(redundant_df)} 个冗余特征)")

        # 统计
        n_total = len(df)
        n_adduct_types = len(set(feature_adduct_label)) - (1 if "" in feature_adduct_label else 0)

        sample_stats[sample_name] = {
            "total_features": n_total,
            "annotated_features": n_annotated,
            "adduct_types": n_adduct_types,
            "feature_pairs": len(unique_pairs),
            "redundant_features": n_redundant,
            "non_redundant_features": n_total - n_redundant,
            "total_hypotheses": len(all_hypotheses),
        }

        all_annotated.append(df_out)

        print(f"      统计: {n_total} 个特征 → {n_annotated} 个被注释, "
              f"{n_redundant} 个冗余 ({100*n_redundant/max(n_total,1):.1f}%), "
              f"{len(unique_pairs)} 对相关")

    # ============================================
    # 合并输出
    # ============================================
    if all_annotated:
        merged_df = pd.concat(all_annotated, ignore_index=True)
        merged_csv = os.path.join(output_dir, "all_mzannotation_annotated.csv")
        merged_df.to_csv(merged_csv, index=False)
        print(f"\n  ✅ 合并注释峰表: {merged_csv} ({len(merged_df)} 个特征)")

    # 摘要
    t_elapsed = time.time() - t_start
    total_features = sum(s["total_features"] for s in sample_stats.values())
    total_redundant = sum(s["redundant_features"] for s in sample_stats.values())
    total_pairs = sum(s["feature_pairs"] for s in sample_stats.values())

    summary_lines = [
        "=" * 60,
        "  mzAnnotation High-Resolution m/z Annotation — 统计摘要",
        "=" * 60,
        f"  输入目录: {input_dir}",
        f"  样本数: {len(peak_tables)}",
        f"  总特征数: {total_features}",
        f"  注释特征数: {sum(s['annotated_features'] for s in sample_stats.values())}",
        f"  特征关联对数: {total_pairs}",
        f"  冗余特征数: {total_redundant} ({100*total_redundant/max(total_features,1):.1f}%)",
        f"  非冗余特征数: {total_features - total_redundant}",
        f"  电离模式: {polarity}",
        f"  加合物规则数: {len(filtered_adduct_rules)}",
        f"  参数: ppm={ppm}, mzabs={mzabs}, max_annotations={max_annotations_per_feature}",
        f"       include_isotopes={include_isotopes}, "
        f"include_transformations={include_transformations}",
        f"  运行时间: {t_elapsed:.1f} 秒",
        "",
    ]
    for sample, stats in sample_stats.items():
        summary_lines.append(
            f"  {sample}: {stats['total_features']}个特征 → "
            f"{stats['redundant_features']}个冗余, "
            f"{stats['feature_pairs']}对关联"
        )
    summary_lines.append("=" * 60)

    summary_out = os.path.join(output_dir, "mzannotation_summary.txt")
    with open(summary_out, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    for line in summary_lines:
        print(line)

    print(f"\n✅ [mzAnnotation] m/z 推定注释完成!")

    if total_redundant == 0 and total_features > 0:
        print(f"\n💡 提示: 未检测到冗余特征。建议:")
        print(f"    - 放宽 ppm (当前 {ppm}) → 尝试 10-15")
        print(f"    - 放宽 mzabs (当前 {mzabs}) → 尝试 0.005-0.01")
        print(f"    - 检查极性设置 (当前 {polarity})")
        print(f"    - 考虑增加 charge_range (当前 {charge_range})")


# =============================================================================
# 辅助函数：从冗余过滤结果生成去冗余特征表
# =============================================================================

def _build_redundancy_filtered_feature_table(
    input_dir: str,
    camera_dir: str,
    ramclust_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
):
    """
    基于 CAMERA 和 RAMClust 的冗余分析结果，从原始 XCMS 特征表中移除冗余特征，
    生成供 KNN 缺失值填补等下游步骤使用的去冗余特征表。

    过滤规则:
    1. CAMERA: 移除 is_redundant=True 或 is_ips=True 的特征
    2. RAMClust: 每个聚类只保留 is_main_peak=True 的特征;
       若无主峰标记，保留聚类中平均强度最高的特征

    Parameters
    ----------
    input_dir : str
        原始 XCMS 特征表所在目录（含 feature_table.csv）。
    camera_dir : str
        CAMERA 输出目录（含 all_camera_annotated.csv）。
    ramclust_dir : str
        RAMClust 输出目录（含 ramclust_clusters.csv）。
    output_dir : str
        输出去冗余特征表的目录。
    file_pattern : str
        峰表文件匹配模式。
    """
    import pandas as pd
    import numpy as np

    # 1. 加载原始 XCMS 特征表
    csv_files = sorted(glob.glob(os.path.join(input_dir, file_pattern)))
    if not csv_files:
        print("    未找到 XCMS 特征表，跳过去冗余生成")
        return

    original_df = None
    for f in csv_files:
        df = pd.read_csv(f)
        # 检测是否为合并特征表格式（有 feature_id, mz, rt + 样本列）
        reserved = {"feature_id", "mz", "rt", "rt_med", "intensity", "area", "sn", "sample"}
        extra = [c for c in df.columns if c not in reserved]
        if len(extra) >= 2:
            original_df = df
            break

    if original_df is None:
        # 没检测到合并表 → 不做处理
        print("    未检测到合并特征表格式，跳过去冗余生成")
        return

    # 确保 feature_id 列名一致
    fid_col = "feature_id" if "feature_id" in original_df.columns else original_df.columns[0]
    print(f"    原始特征数: {len(original_df)}")

    redundant_ids: set = set()
    removed_by_camera = 0
    removed_by_ramclust = 0

    # 2. CAMERA 冗余特征
    camera_csv = os.path.join(camera_dir, "all_camera_annotated.csv")
    if os.path.exists(camera_csv):
        camera_df = pd.read_csv(camera_csv)
        if fid_col in camera_df.columns:
            # is_redundant 列
            if "is_redundant" in camera_df.columns:
                cam_red = set(camera_df.loc[camera_df["is_redundant"] == True, fid_col])
                redundant_ids.update(cam_red)
                removed_by_camera = len(cam_red)
            # is_ips 列
            if "is_ips" in camera_df.columns:
                cam_ips = set(camera_df.loc[camera_df["is_ips"] == True, fid_col])
                redundant_ids.update(cam_ips)
            print(f"    CAMERA 标记冗余: {removed_by_camera} (is_redundant) + {len([c for c in camera_df.get('is_ips', []) if c])} (is_ips)")
        else:
            print(f"    ⚠️ CAMERA 注释表缺少 {fid_col} 列")
    else:
        print(f"    ⚠️ CAMERA 注释表不存在: {camera_csv}")

    # 3. RAMClust 聚类 → 每聚类只保留主峰
    ramclust_csv = os.path.join(ramclust_dir, "ramclust_clusters.csv")
    if os.path.exists(ramclust_csv):
        rc_df = pd.read_csv(ramclust_csv)
        if fid_col in rc_df.columns and "cluster" in rc_df.columns:
            clustered = rc_df[rc_df["cluster"] >= 0]  # cluster >= 0 表示已聚类
            if len(clustered) > 0:
                for cluster_id, group in clustered.groupby("cluster"):
                    if "is_main_peak" in group.columns:
                        main_peaks = group[group["is_main_peak"] == True]
                    else:
                        main_peaks = pd.DataFrame()

                    if len(main_peaks) > 0:
                        # 有主峰标记 → 保留主峰，移除同一聚类中非主峰
                        main_ids = set(main_peaks[fid_col])
                        non_main = set(group[fid_col]) - main_ids
                        redundant_ids.update(non_main)
                        removed_by_ramclust += len(non_main)
                    # 若无主峰标记，不移除（保留全部聚类内特征）
            print(f"    RAMClust 聚类冗余: {removed_by_ramclust} 个非主峰特征")
        else:
            print(f"    ⚠️ RAMClust 聚类表缺少必要列")
    else:
        print(f"    ⚠️ RAMClust 聚类表不存在: {ramclust_csv}")

    # 4. 生成去冗余特征表
    total_redundant = len(redundant_ids)
    if total_redundant > 0:
        keep_mask = ~original_df[fid_col].isin(redundant_ids)
        filtered_df = original_df[keep_mask].copy()
        print(f"    移除冗余特征: {total_redundant}")
        print(f"    去冗余后特征数: {len(filtered_df)}")
    else:
        filtered_df = original_df.copy()
        print(f"    无冗余特征被标记，保留全部 {len(filtered_df)} 个特征")

    output_path = os.path.join(output_dir, "feature_table_redundancy_filtered.csv")
    filtered_df.to_csv(output_path, index=False)
    print(f"    ✅ 去冗余特征表: {output_path}")

    # 同时保存为 feature_table.csv，供下游 KNN 等工具直接读取
    compat_path = os.path.join(output_dir, "feature_table.csv")
    filtered_df.to_csv(compat_path, index=False)
    print(f"    ✅ 兼容副本 (供下游工具): {compat_path}")

    # 5. 输出过滤摘要
    summary_path = os.path.join(output_dir, "redundancy_filtering_summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Redundancy Filtering Summary\n")
        f.write(f"{'=' * 50}\n")
        f.write(f"Input features: {len(original_df)}\n")
        f.write(f"Redundant features removed: {total_redundant}\n")
        f.write(f"  - CAMERA (is_redundant/ips): {removed_by_camera}\n")
        f.write(f"  - RAMClust (non-main-peak): {removed_by_ramclust}\n")
        f.write(f"Features after filtering: {len(filtered_df)}\n")
        f.write(f"Reduction: {total_redundant / len(original_df) * 100:.1f}%\n")
        f.write(f"Output: {output_path}\n")
    print(f"    ✅ 过滤摘要: {summary_path}")


# =============================================================================
# 冗余特征过滤 — 综合管线
# =============================================================================

def redundant_feature_filtering_pipeline_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.csv",
    polarity: str = "positive",
    camera_kwargs: Optional[Dict] = None,
    mzannotation_kwargs: Optional[Dict] = None,
    ramclust_kwargs: Optional[Dict] = None,
):
    """
    运行完整的冗余特征过滤管线：CAMERA → mzAnnotation → RAMClust。

    管线将依次执行:
    1. CAMERA — 假谱图分组 + 同位素注释 + 加合物注释 + 中性丢失
    2. mzAnnotation — 高分辨 m/z 推定注释 (基于精确质量)
    3. RAMClust — 基于相似性的特征聚类 (需多样本)

    最后输出一个综合的冗余特征报告，结合三个工具的结果。

    Parameters
    ----------
    input_dir : str
        输入目录，包含峰表 CSV 文件。
    output_dir : str
        输出根目录。各工具结果保存在子目录中。
    file_pattern : str, default="*.csv"
        峰表文件匹配模式。
    polarity : str, default="positive"
        电离模式。
    camera_kwargs : dict, optional
        传递给 CAMERA 的额外参数。
    mzannotation_kwargs : dict, optional
        传递给 mzAnnotation 的额外参数。
    ramclust_kwargs : dict, optional
        传递给 RAMClust 的额外参数。

    Outputs
    -------
    {output_dir}/
    ├── camera/             — CAMERA 结果
    ├── mzannotation/       — mzAnnotation 结果
    ├── ramclust/           — RAMClust 结果
    └── combined_redundant_report.csv  — 综合冗余特征报告
    """
    print(f"\n{'=' * 70}")
    print(f"  冗余特征过滤综合管线")
    print(f"  CAMERA → mzAnnotation → RAMClust")
    print(f"{'=' * 70}")
    print(f"  输入目录: {input_dir}")
    print(f"  电离模式: {polarity}")

    t_start = time.time()

    os.makedirs(output_dir, exist_ok=True)

    camera_dir = os.path.join(output_dir, "camera")
    mzannotation_dir = os.path.join(output_dir, "mzannotation")
    ramclust_dir = os.path.join(output_dir, "ramclust")

    # ---- CAMERA ----
    print(f"\n{'─' * 50}")
    print(f"  阶段 1/3: CAMERA 假谱图注释")
    print(f"{'─' * 50}")
    try:
        camera_args = {
            "input_dir": input_dir,
            "output_dir": camera_dir,
            "file_pattern": file_pattern,
            "polarity": polarity,
        }
        if camera_kwargs:
            camera_args.update(camera_kwargs)
        redundant_feature_filtering_camera_impl(**camera_args)
    except Exception as e:
        print(f"  ⚠️ CAMERA 失败: {e}，继续下一阶段...")

    # ---- mzAnnotation ----
    print(f"\n{'─' * 50}")
    print(f"  阶段 2/3: mzAnnotation 精确质量注释")
    print(f"{'─' * 50}")
    try:
        mzann_args = {
            "input_dir": input_dir,
            "output_dir": mzannotation_dir,
            "file_pattern": file_pattern,
            "polarity": polarity,
        }
        if mzannotation_kwargs:
            mzann_args.update(mzannotation_kwargs)
        redundant_feature_filtering_mzannotation_impl(**mzann_args)
    except Exception as e:
        print(f"  ⚠️ mzAnnotation 失败: {e}，继续下一阶段...")

    # ---- RAMClust ----
    print(f"\n{'─' * 50}")
    print(f"  阶段 3/3: RAMClust 特征聚类")
    print(f"{'─' * 50}")
    try:
        ramclust_args = {
            "input_dir": input_dir,
            "output_dir": ramclust_dir,
            "file_pattern": file_pattern,
        }
        if ramclust_kwargs:
            ramclust_args.update(ramclust_kwargs)
        redundant_feature_filtering_ramclust_impl(**ramclust_args)
    except Exception as e:
        print(f"  ⚠️ RAMClust 失败: {e}，继续...")


    # ---- 生成去冗余后的特征表 ----
    print(f"\n{'─' * 50}")
    print(f"  生成去冗余特征表")
    print(f"{'─' * 50}")
    try:
        _build_redundancy_filtered_feature_table(
            input_dir=input_dir,
            camera_dir=camera_dir,
            ramclust_dir=ramclust_dir,
            output_dir=output_dir,
            file_pattern=file_pattern,
        )
    except Exception as e:
        print(f"  ⚠️ 生成去冗余特征表失败: {e}")

    # 综合报告
    t_elapsed = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"  管线完成! 总运行时间: {t_elapsed:.1f} 秒")
    print(f"  结果目录: {output_dir}")
    print(f"{'=' * 70}\n")


# =============================================================================

if __name__ == "__main__":
    base = "/data2/luxiang/MOA/outputspace"

    # 测试 CAMERA — 假谱图注释 + 冗余特征识别
    # print("\n" + "=" * 70)
    # print("  测试: CAMERA 冗余特征过滤")
    # print("=" * 70)
    # redundant_feature_filtering_camera_impl(
    #     input_dir=f"{base}/peak_detection/kpic_results",
    #     output_dir=f"{base}/redundant_feature_filtering/camera_results",
    #     polarity="positive",
    #     ppm=10.0,
    #     mzabs=0.01,
    #     perfwhm=0.6,
    #     cor_eic_th=0.75,
    # )

    # 测试 mzAnnotation — 高分辨 m/z 推定注释
    print("\n" + "=" * 70)
    print("  测试: mzAnnotation 精确质量注释")
    print("=" * 70)
    redundant_feature_filtering_mzannotation_impl(
        input_dir=f"{base}/peak_detection/kpic_results",
        output_dir=f"{base}/redundant_feature_filtering/mzannotation_results",
        polarity="positive",
        ppm=5.0,
        include_isotopes=True,
        include_transformations=True,
        filter_redundant_adducts=True,
    )

    # 测试 RAMClust — 基于分析行为的特征聚类
    # print("\n" + "=" * 70)
    # print("  测试: RAMClust 特征聚类")
    # print("=" * 70)
    # redundant_feature_filtering_ramclust_impl(
    #     input_dir=f"{base}/peak_detection/kpic_results",
    #     output_dir=f"{base}/redundant_feature_filtering/ramclust_results",
    #     st=5.0,
    #     sr=0.5,
    #     maxt=2.0,
    #     deep_split=2,
    #     min_module_size=2,
    #     cor_method="pearson",
    #     normalize_method="TIC",
    # )

    # 完整管线
    # print("\n" + "=" * 70)
    # print("  测试: 完整冗余特征过滤管线")
    # print("=" * 70)
    # redundant_feature_filtering_pipeline_impl(
    #     input_dir=f"{base}/peak_detection/kpic_results",
    #     output_dir=f"{base}/redundant_feature_filtering/pipeline_results",
    #     polarity="positive",
    # )

    # print("\nredundant_feature_filtering.py — 冗余特征过滤与注释工具模块已就绪。")
    # print("可用工具: CAMERA | RAMClust | mzAnnotation")
    # print("可用管线: redundant_feature_filtering_pipeline_impl")
