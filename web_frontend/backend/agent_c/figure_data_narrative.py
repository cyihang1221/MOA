"""从 B 侧 CSV 生成图下「数据支撑句」（Package E）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from web_frontend.backend.plot_edit_registry import (
    get_plot_spec,
    plot_type_from_stem,
    resolve_plot_data_file,
)

_PLOT_TYPE_ALIASES = {
    "kegg_bar": "kegg_barplot",
}


def normalize_plot_type(plot_type: str) -> str:
    pt = str(plot_type or "").strip()
    return _PLOT_TYPE_ALIASES.get(pt, pt)


def resolve_figure_plot_type(fig: dict[str, Any]) -> str:
    """从 figure 字段或 PNG 文件名推断 plot_type。"""
    pt = normalize_plot_type(str(fig.get("plot_type") or ""))
    if pt:
        return pt
    png = fig.get("png")
    if not png:
        return ""
    stem = Path(str(png)).stem
    for part in stem.replace("-", "_").split("__"):
        hit = plot_type_from_stem(part)
        if hit:
            return hit
    return plot_type_from_stem(stem) or ""


def find_plot_data_file(results_root: Path, filename: str) -> Path | None:
    """在结果目录（含一级子目录）中定位 CSV。"""
    root = Path(results_root)
    if not root.is_dir():
        return None
    direct = resolve_plot_data_file(root, filename)
    if direct:
        return direct
    try:
        for sub in sorted(root.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            hit = resolve_plot_data_file(sub, filename)
            if hit:
                return hit
    except OSError:
        pass
    return None


def plot_data_files_available(results_root: Path, plot_type: str) -> bool:
    """结果目录中是否具备该图型所需的全部 CSV（含一级子目录）。"""
    pt = normalize_plot_type(plot_type)
    spec = get_plot_spec(pt)
    if not spec or not spec.data_files:
        return False
    root = Path(results_root)
    return all(find_plot_data_file(root, name) is not None for name in spec.data_files)


def resolve_figure_data_dir(
    fig: dict[str, Any],
    *,
    results_dir: str | Path,
    plot_type: str = "",
) -> Path:
    """解析用于读 CSV 的目录（优先 figure.data_dir，再按 spec 搜 results）。"""
    root = Path(results_dir)
    data_dir = fig.get("data_dir")
    if data_dir:
        p = Path(str(data_dir))
        if p.is_dir():
            return p
    pt = normalize_plot_type(plot_type or resolve_figure_plot_type(fig))
    spec = get_plot_spec(pt) if pt else None
    if spec and spec.data_files:
        hit = find_plot_data_file(root, spec.data_files[0])
        if hit:
            return hit.parent
    return root


def enrich_figures_data_narrative(
    figures: list[dict[str, Any]],
    *,
    results_dir: str | Path,
    metadata_csv: str | Path | None = None,
) -> None:
    """就地写入 figure['data_narrative']，并回填缺失的 plot_type。"""
    root = Path(results_dir)
    for fig in figures:
        if fig.get("status") not in {"rendered", "copied_existing", "missing_data"}:
            continue
        pt = resolve_figure_plot_type(fig)
        if pt and not fig.get("plot_type"):
            fig["plot_type"] = pt
        data_dir = resolve_figure_data_dir(fig, results_dir=root, plot_type=pt)
        fig["data_narrative"] = build_figure_data_narrative(
            pt,
            data_dir,
            metadata_csv=metadata_csv,
            results_root=root,
        )


def build_figure_data_narrative(
    plot_type: str,
    data_dir: str | Path,
    *,
    metadata_csv: str | Path | None = None,
    results_root: str | Path | None = None,
) -> dict[str, Any]:
    """按 plot_type 读取结果 CSV，产出可写入报告的结构化数据解读（不臆造）。"""
    pt = normalize_plot_type(plot_type)
    root = Path(data_dir)
    search_root = Path(results_root) if results_root else root
    spec = get_plot_spec(pt) if pt else None
    out: dict[str, Any] = {
        "plot_type": pt or plot_type,
        "sentences": [],
        "bullets": [],
        "stats": {},
    }
    if not pt or not spec:
        if pt:
            out["bullets"].append(f"（plot_type `{pt}` 暂无专用数据支撑模板）")
        return out
    if not root.is_dir() and search_root.is_dir():
        root = resolve_figure_data_dir({"plot_type": pt}, results_dir=search_root, plot_type=pt)

    try:
        import pandas as pd
    except ImportError:
        out["bullets"].append("（未安装 pandas，无法读取 CSV 统计）")
        return out

    handler = _NARRATIVE_HANDLERS.get(pt, _narrative_generic)
    try:
        import inspect

        kwargs: dict[str, Any] = {"search_root": search_root}
        if "metadata_csv" in inspect.signature(handler).parameters:
            kwargs["metadata_csv"] = metadata_csv
        handler(root, spec, out, pd, **kwargs)
    except Exception as exc:
        out["bullets"].append(f"读取数据时出错：{exc}")

    if out["bullets"] and not out["sentences"]:
        out["sentences"] = list(out["bullets"])
    return out


def format_data_narrative_markdown(narr: dict[str, Any] | None, *, zh: bool = True) -> str:
    if not narr:
        return ""
    bullets = narr.get("bullets") or narr.get("sentences") or []
    if not bullets:
        return ""
    head = "#### 数据支撑\n\n" if zh else "#### Data support\n\n"
    return head + "\n".join(f"- {b}" for b in bullets if str(b).strip()) + "\n"


def _read_csv(root: Path, spec, pd, filename: str | None = None, *, search_root: Path | None = None):
    name = filename or (spec.data_files[0] if spec.data_files else "")
    if not name:
        return None, None
    path = resolve_plot_data_file(root, name)
    if not path and search_root:
        found = find_plot_data_file(search_root, name)
        if found:
            path = found
    if not path or not path.is_file():
        return None, name
    return pd.read_csv(path), path.name


def _pick_col(df, candidates: tuple[str, ...]) -> str | None:
    lower = {str(c).lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return str(lower[cand.lower()])
    return None


def _count_groups(df, col: str) -> str | None:
    vc = df[col].astype(str).value_counts()
    return "、".join(f"{k}×{int(v)}" for k, v in vc.items())


def _read_metadata_groups(metadata_csv: str | Path | None, pd) -> str | None:
    if not metadata_csv:
        return None
    path = Path(metadata_csv)
    if not path.is_file():
        return None
    try:
        mdf = pd.read_csv(path)
    except Exception:
        return None
    gcol = _pick_col(mdf, ("Group", "group", "class", "Condition"))
    if not gcol:
        return None
    vc = mdf[gcol].astype(str).value_counts()
    return "、".join(f"{k}×{int(v)}" for k, v in vc.items())


def _narrative_scores(
    root: Path,
    spec,
    out: dict,
    pd,
    *,
    label: str,
    search_root: Path | None = None,
    metadata_csv: str | Path | None = None,
) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        out["bullets"].append(f"未找到 `{spec.data_files[0]}`，无法描述样本分布。")
        meta_groups = _read_metadata_groups(metadata_csv, pd)
        if meta_groups:
            out["bullets"].append(f"metadata 分组：{meta_groups}。")
        return
    out["stats"]["n_samples"] = len(df)
    out["bullets"].append(f"{label} 得分表 `{fname}` 含 **{len(df)}** 个样本点。")
    gcol = _pick_col(df, ("Group", "group", "class"))
    if gcol:
        out["stats"]["groups"] = {str(k): int(v) for k, v in df[gcol].astype(str).value_counts().items()}
        out["bullets"].append(f"分组样本数：{_count_groups(df, gcol)}。")
    pc_cols = [c for c in df.columns if str(c).upper().startswith("PC") and str(c)[2:3].isdigit()]
    comp_cols = [c for c in df.columns if str(c).startswith("Comp") or str(c).startswith("comp")]
    axis_cols = pc_cols or comp_cols
    if len(axis_cols) >= 2:
        out["bullets"].append(f"坐标轴使用 {axis_cols[0]} 与 {axis_cols[1]}（列存在于表中）。")
        out["stats"]["axis_columns"] = axis_cols[:4]
    elif not gcol:
        meta_groups = _read_metadata_groups(metadata_csv, pd)
        if meta_groups:
            out["bullets"].append(f"metadata 分组：{meta_groups}。")


def _narrative_volcano(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        out["bullets"].append(f"未找到 `{spec.data_files[0]}`。")
        return
    n = len(df)
    out["stats"]["n_features"] = n
    out["bullets"].append(f"火山图数据 `{fname}` 共 **{n}** 个特征。")
    if "Significant" in df.columns:
        sig = int(df["Significant"].fillna(False).astype(bool).sum())
        out["stats"]["n_significant"] = sig
        out["bullets"].append(f"其中 Significant=True **{sig}** 个。")
    for col, thr, label in (("p_value", 0.05, "p<0.05"), ("adj_p_value", 0.05, "FDR<0.05")):
        if col in df.columns:
            cnt = int((pd.to_numeric(df[col], errors="coerce") < thr).sum())
            out["stats"][f"n_{col}_lt_{thr}"] = cnt
            out["bullets"].append(f"{label} 约 **{cnt}** 个（按 `{col}` 列计数）。")
    fc_col = _pick_col(df, ("log2FC", "log2FoldChange", "log2fc"))
    if fc_col:
        up = int((pd.to_numeric(df[fc_col], errors="coerce") > 0).sum())
        down = int((pd.to_numeric(df[fc_col], errors="coerce") < 0).sum())
        out["bullets"].append(f"{fc_col}>0 **{up}** 个，{fc_col}<0 **{down}** 个。")


def _narrative_vip(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"VIP 表 `{fname}` 共 {len(df)} 行。")
    vcol = _pick_col(df, ("VIP", "vip"))
    if vcol:
        high = df[pd.to_numeric(df[vcol], errors="coerce") > 1]
        out["stats"]["n_vip_gt1"] = len(high)
        out["bullets"].append(f"VIP>1 的特征 **{len(high)}** 个。")
        name_col = _pick_col(df, ("Feature", "feature", "name", "metabolite", "compound"))
        if name_col and len(high):
            top = high.sort_values(vcol, ascending=False).head(5)
            names = [str(x) for x in top[name_col].tolist()]
            out["stats"]["top_vip_names"] = names
            out["bullets"].append("VIP 最高若干特征：" + "、".join(names[:5]) + "。")


def _narrative_kegg(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"KEGG 富集表 `{fname}` 共 {len(df)} 条通路/条目。")
    pcol = _pick_col(df, ("p_value", "pvalue", "PValue", "padj", "fdr", "adj_p_value"))
    if pcol:
        sig = int((pd.to_numeric(df[pcol], errors="coerce") < 0.05).sum())
        out["bullets"].append(f"{pcol}<0.05 约 **{sig}** 条。")
    name_col = _pick_col(df, ("pathway", "Pathway", "Description", "term", "ID"))
    if name_col and len(df):
        top = df.head(3)[name_col].astype(str).tolist()
        out["bullets"].append("表内前列条目示例：" + "；".join(top) + "。")


def _narrative_heatmap(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"热图矩阵 `{fname}` 规模约 **{len(df)}** 行 × **{len(df.columns)}** 列。")


def _narrative_network(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"网络布局表 `{fname}` 共 **{len(df)}** 个节点。")
    fam_col = _pick_col(df, ("Family", "family", "molecular_family"))
    if fam_col:
        out["bullets"].append(f"节点 `{fam_col}` 类别 **{df[fam_col].nunique()}** 种。")
    edges = resolve_plot_data_file(root, "network_edges.csv") or (
        find_plot_data_file(search_root, "network_edges.csv") if search_root else None
    )
    if edges and edges.is_file():
        edf = pd.read_csv(edges)
        out["bullets"].append(f"边表 `network_edges.csv` 共 **{len(edf)}** 条边。")


def _narrative_network_nodes(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"网络节点表 `{fname}` 共 **{len(df)}** 个节点。")
    fam_col = _pick_col(df, ("Family", "family", "molecular_family"))
    if fam_col:
        vc = df[fam_col].astype(str).value_counts()
        out["bullets"].append(f"分子家族 **{len(vc)}** 类；最大类 **{int(vc.max())}** 个节点。")
    deg_col = _pick_col(df, ("degree", "Degree", "node_degree"))
    if deg_col:
        deg = pd.to_numeric(df[deg_col], errors="coerce").dropna()
        if len(deg):
            out["bullets"].append(
                f"节点度：最小 **{int(deg.min())}**，最大 **{int(deg.max())}**，均值 **{deg.mean():.1f}**。"
            )


def _narrative_edges_distribution(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"边表 `{fname}` 共 **{len(df)}** 条边。")
    wcol = _pick_col(
        df,
        ("cosine", "Cosine", "similarity", "correlation", "pearson", "weight", "Weight"),
    )
    if wcol:
        vals = pd.to_numeric(df[wcol], errors="coerce").dropna()
        if len(vals):
            out["bullets"].append(
                f"`{wcol}`：范围 **[{vals.min():.3f}, {vals.max():.3f}]**，均值 **{vals.mean():.3f}**。"
            )


def _narrative_mass2motifs(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"Mass2Motif 表 `{fname}` 共 **{len(df)}** 条。")
    name_col = _pick_col(df, ("motif", "Motif", "name", "mass2motif"))
    if name_col:
        top = df.head(3)[name_col].astype(str).tolist()
        out["bullets"].append("前列 motif：" + "、".join(top) + "。")


def _narrative_spectra_motif(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"谱图–Motif 关联矩阵 `{fname}` 约 **{len(df)}** 行 × **{len(df.columns)}** 列。")


def _narrative_chemical_class(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"化学类别表 `{fname}` 共 **{len(df)}** 行。")
    cls_col = _pick_col(df, ("class", "Class", "chemical_class", "superclass"))
    if cls_col:
        vc = df[cls_col].astype(str).value_counts()
        out["bullets"].append(f"化学类别 **{len(vc)}** 种；前列：" + "、".join(vc.head(3).index.astype(str)) + "。")


def _narrative_annotation_propagation(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"注释传播节点表 `{fname}` 共 **{len(df)}** 个节点。")
    src_col = _pick_col(df, ("annotation_source", "source", "propagation", "type"))
    if src_col:
        vc = df[src_col].astype(str).value_counts()
        parts = "、".join(f"{k}×{int(v)}" for k, v in vc.items())
        out["bullets"].append(f"注释来源分布：{parts}。")


def _narrative_mass2motif_network(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    nodes, nf = _read_csv(root, spec, pd, spec.data_files[0], search_root=search_root)
    if nodes is not None:
        out["bullets"].append(f"Motif 网络节点 `{nf}` 共 **{len(nodes)}** 个。")
    if len(spec.data_files) > 1:
        edges, ef = _read_csv(root, spec, pd, spec.data_files[1], search_root=search_root)
        if edges is not None:
            out["bullets"].append(f"Motif 网络边 `{ef}` 共 **{len(edges)}** 条。")


def _narrative_fbmn_group(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"FBMN 分组强度表 `{fname}` 共 **{len(df)}** 行。")
    grp_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if grp_cols:
        out["bullets"].append(f"数值列 **{len(grp_cols)}** 列：" + "、".join(map(str, grp_cols[:6])) + "。")


def _narrative_constituent_bar(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"成分含量表 `{fname}` 共 **{len(df)}** 行。")
    mcol = _pick_col(df, ("metric", "Metric", "constituent"))
    gcol = _pick_col(df, ("grade", "Grade", "group", "Group"))
    if mcol:
        out["bullets"].append("指标：" + "、".join(df[mcol].astype(str).unique()[:8]) + "。")
    if gcol:
        out["bullets"].append(f"等级/分组 **{df[gcol].nunique()}** 档。")


def _narrative_relative_abundance(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    used = None
    for fname in spec.data_files:
        df, name = _read_csv(root, spec, pd, fname, search_root=search_root)
        if df is not None:
            used = (df, name)
            break
    if not used:
        out["bullets"].append("未找到差异代谢物丰度表。")
        return
    df, fname = used
    out["bullets"].append(f"相对丰度矩阵 `{fname}`：**{len(df)}** 个特征 × **{len(df.columns)}** 列。")


def _narrative_correlation(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"相关矩阵 `{fname}` 规模 **{len(df)}×{len(df.columns)}**。")


def _narrative_bioactivity(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"生物活性表 `{fname}` 共 **{len(df)}** 行。")
    acol = _pick_col(df, ("assay", "Assay", "activity"))
    if acol:
        out["bullets"].append("测定项目：" + "、".join(df[acol].astype(str).unique()[:6]) + "。")


def _narrative_sensory(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"感官评分表 `{fname}` 共 **{len(df)}** 行。")
    acol = _pick_col(df, ("attribute", "Attribute", "descriptor"))
    scol = _pick_col(df, ("score", "Score", "value"))
    if acol:
        out["bullets"].append("感官属性：" + "、".join(df[acol].astype(str).unique()[:8]) + "。")
    if scol:
        vals = pd.to_numeric(df[scol], errors="coerce").dropna()
        if len(vals):
            out["bullets"].append(f"评分范围 **{vals.min():.2f}–{vals.max():.2f}**。")


def _narrative_plsda_permutation(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    df, fname = _read_csv(root, spec, pd, search_root=search_root)
    if df is None:
        return
    out["bullets"].append(f"PLS-DA 置换检验表 `{fname}` 共 **{len(df)}** 次置换记录。")
    pcol = _pick_col(df, ("permutation", "Permutation", "perm"))
    if pcol and "R2" in df.columns and "Q2" in df.columns:
        real = df[pd.to_numeric(df[pcol], errors="coerce") == 0]
        if len(real):
            out["bullets"].append(
                f"真实模型 R²=**{float(real['R2'].iloc[0]):.3f}**，Q²=**{float(real['Q2'].iloc[0]):.3f}**。"
            )


def _narrative_precursor_mass_diff(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    _narrative_network_nodes(root, spec, out, pd, search_root=search_root)
    if len(spec.data_files) > 1:
        edges, ef = _read_csv(root, spec, pd, spec.data_files[1], search_root=search_root)
        if edges is not None:
            out["bullets"].append(f"前体质量差边表 `{ef}` **{len(edges)}** 条。")


def _narrative_generic(root: Path, spec, out: dict, pd, *, search_root: Path | None = None) -> None:
    for fname in spec.data_files:
        df, name = _read_csv(root, spec, pd, fname, search_root=search_root)
        if df is not None:
            out["bullets"].append(f"结果表 `{name}` 共 **{len(df)}** 行、**{len(df.columns)}** 列。")
            return
    out["bullets"].append(f"未找到数据文件：{', '.join(spec.data_files)}。")


_NARRATIVE_HANDLERS: dict[str, Callable[..., None]] = {
    "pca": lambda r, s, o, p, **kw: _narrative_scores(r, s, o, p, label="PCA", **kw),
    "plsda": lambda r, s, o, p, **kw: _narrative_scores(r, s, o, p, label="PLS-DA", **kw),
    "volcano": _narrative_volcano,
    "vip_bar": _narrative_vip,
    "heatmap_vip": _narrative_heatmap,
    "kegg_bubble": _narrative_kegg,
    "kegg_dotplot": _narrative_kegg,
    "kegg_barplot": _narrative_kegg,
    "network_topology": _narrative_network,
    "family_size": _narrative_network_nodes,
    "degree_hist": _narrative_network_nodes,
    "cosine_hist": _narrative_edges_distribution,
    "pearson_hist": _narrative_edges_distribution,
    "precursor_mass_diff": _narrative_precursor_mass_diff,
    "mass2motif_overview": _narrative_mass2motifs,
    "mass2motif_fragments": _narrative_mass2motifs,
    "motif_spectrum_heatmap": _narrative_spectra_motif,
    "chemical_class_distribution": _narrative_chemical_class,
    "family_chemical_consensus": _narrative_chemical_class,
    "annotation_propagation": _narrative_annotation_propagation,
    "mass2motif_network": _narrative_mass2motif_network,
    "fbmn_group_intensity": _narrative_fbmn_group,
    "constituent_bar": _narrative_constituent_bar,
    "relative_abundance_heatmap": _narrative_relative_abundance,
    "hca_heatmap": _narrative_heatmap,
    "correlation_heatmap": _narrative_correlation,
    "bioactivity_bar": _narrative_bioactivity,
    "sensory_scores": _narrative_sensory,
    "plsda_permutation": _narrative_plsda_permutation,
}


__all__ = [
    "build_figure_data_narrative",
    "enrich_figures_data_narrative",
    "format_data_narrative_markdown",
    "find_plot_data_file",
    "normalize_plot_type",
    "plot_data_files_available",
    "resolve_figure_data_dir",
    "resolve_figure_plot_type",
]
