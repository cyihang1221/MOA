"""从自然语言解析分析意图 → plot_config patch（第二期：多图族 color_by / 通道 / 阈值）。"""
from __future__ import annotations

import re
from typing import Any

from web_frontend.backend.session_metadata import match_color_by_column

_CLUSTER_RE = re.compile(
    r"(?:"
    r"聚(?:成|为|成了)?\s*(\d+)\s*类|"
    r"(?:k[\s-]*means|聚类)\s*(?:成|为|分成)?\s*(\d+)|"
    r"(?:分成|分为|划分成)\s*(\d+)\s*类|"
    r"cluster(?:\s*(?:into|to))?\s*(\d+)|"
    r"(\d+)\s*(?:个)?(?:类|簇|clusters?)"
    r")",
    re.IGNORECASE,
)

_COLOR_BY_RE = re.compile(
    r"(?:"
    r"按\s*([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)\s*(?:着色|上色|染色|配色|颜色|作色)|"
    r"(?:着色|上色|染色|作色)\s*(?:字段|列|维度)?\s*(?:改?为|改成|换成|用)?\s*([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)|"
    r"color\s*(?:by|with)\s+([A-Za-z_][\w]*)|"
    r"(?:用|换成|改为)\s*([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)\s*(?:着色|上色|作色)"
    r")",
    re.IGNORECASE,
)

_TIME_HINT_RE = re.compile(r"时间|时序|time\s*series|timepoint|time\s*point", re.IGNORECASE)
_BATCH_HINT_RE = re.compile(r"batch|批次", re.IGNORECASE)
_GROUP_HINT_RE = re.compile(r"分组|组别|(?<![a-z])group(?![a-z])|类别|class", re.IGNORECASE)
_CLUSTER_HINT_RE = re.compile(r"聚类|k[\s-]*means|cluster", re.IGNORECASE)
_COLORING_HINT_RE = re.compile(
    r"着色|上色|染色|作色|配色|color\s*by|按.{0,12}(?:色|cluster|聚类|batch|时间|组别|分组|化学|家族|度数|degree)",
    re.IGNORECASE,
)

_P_THRESHOLD_RE = re.compile(
    r"(?:p(?:\.?adjust|adj|value)?|fdr|显著性)\s*(?:[<＜≤<=]|小于|低于)\s*(0?\.\d+|\d+(?:\.\d+)?(?:e-?\d+)?)",
    re.IGNORECASE,
)
_FC_THRESHOLD_RE = re.compile(
    r"(?:\|?\s*log2?\s*f[co](?:ld)?\s*c(?:hange)?\s*\|?|\|?fc\|?|倍变|折叠变化)"
    r"\s*(?:[>≥>=]|大于|高于|超过)\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_TOP_N_RE = re.compile(
    r"(?:top\s*|前\s*|展示\s*|显示\s*)(\d+)\s*(?:个|条|项)?",
    re.IGNORECASE,
)

# scores 默认 stems
DEFAULT_COLORING_STEMS = ("pca_plot", "plsda_plot")
DEFAULT_COLORING_PLOT_TYPES = ("pca", "plsda")

# 支持分析意图的图类型（第二期）
INTENT_PLOT_TYPES = frozenset(
    {
        "pca",
        "plsda",
        "volcano",
        "network_topology",
        "family_size",
        "chemical_class_distribution",
        "family_chemical_consensus",
        "fbmn_group_intensity",
        "kegg_bubble",
        "kegg_dotplot",
        "kegg_barplot",
        "mass2motif_overview",
        "degree_hist",
        "cosine_hist",
        "pearson_hist",
        "precursor_mass_diff",
    }
)

# 拓扑图 color_by 别名 → 规范列名
_TOPOLOGY_COLOR_ALIASES: dict[str, str] = {
    "family": "family",
    "molecular_family": "family",
    "分子家族": "family",
    "家族": "family",
    "degree": "degree",
    "度数": "degree",
    "化学类": "chemical_category",
    "化学类别": "chemical_category",
    "chemical": "chemical_category",
    "chemical_category": "chemical_category",
    "chemical_class": "chemical_category",
    "log2fc": "log2FC",
    "log2FC": "log2FC",
    "fc": "log2FC",
    "倍变": "log2FC",
}

_CHANNEL_ALIASES: dict[str, str] = {
    "count": "count",
    "Count": "count",
    "数量": "count",
    "neglog10": "neglog10",
    "fdr": "neglog10",
    "-log10": "neglog10",
    "pvalue": "neglog10",
    "显著性": "neglog10",
    "n_spectra": "n_spectra",
    "谱图数": "n_spectra",
    "load": "load",
    "载荷": "load",
    "log2fc": "log2FC",
    "log2FC": "log2FC",
    "neglog10p": "neglog10p",
}

TOOL_DEFAULT_STEMS: dict[str, tuple[str, ...]] = {
    "statistical_analysis_mixomics": ("pca_plot", "plsda_plot", "volcano_plot"),
    "molecular_networking_gnps": (
        "network_topology",
        "family_size_distribution",
        "cosine_distribution",
    ),
    "molecular_networking_fbmn": (
        "network_topology",
        "family_size_distribution",
        "pearson_distribution",
        "fbmn_group_intensity",
    ),
    "molecular_networking_ms2lda": (
        "mass2motif_overview",
        "mass2motif_fragments",
        "motif_spectrum_heatmap",
        "mass2motif_network",
    ),
    "molecular_networking_molnetenhancer": (
        "network_topology",
        "chemical_class_distribution",
        "family_chemical_consensus",
        "annotation_propagation_summary",
    ),
    "kegg_compound_enrichment": (
        "kegg_compound_bubble",
        "kegg_compound_dotplot",
        "kegg_compound_barplot",
    ),
}


def _extract_cluster_n(text: str) -> int | None:
    match = _CLUSTER_RE.search(text)
    if not match:
        return None
    for g in match.groups():
        if g and str(g).isdigit():
            n = int(g)
            return max(2, min(12, n))
    return None


def _hint_to_color_by(text: str) -> str | None:
    """无明确列名时，用常见语义提示推断 color_by 别名。"""
    if re.search(r"化学类|chemical\s*class|chemical_category", text, re.IGNORECASE):
        return "chemical_category"
    if re.search(r"分子家族|molecular_family|(?<![a-z])family(?![a-z])", text, re.IGNORECASE):
        if _COLORING_HINT_RE.search(text) or "拓扑" in text or "topology" in text.lower():
            return "family"
    if re.search(r"度数|degree", text, re.IGNORECASE) and _COLORING_HINT_RE.search(text):
        return "degree"
    if re.search(r"log2?\s*f[co]|倍变", text, re.IGNORECASE) and _COLORING_HINT_RE.search(text):
        return "log2FC"
    if _TIME_HINT_RE.search(text):
        return "time"
    if _BATCH_HINT_RE.search(text):
        return "batch"
    if _GROUP_HINT_RE.search(text) and _COLORING_HINT_RE.search(text):
        return "group"
    return None


def _infer_target_stems(text: str) -> list[str]:
    lower = text.lower()
    stems: list[str] = []

    def add(*items: str) -> None:
        for item in items:
            if item not in stems:
                stems.append(item)

    if re.search(r"拓扑|topology", text, re.IGNORECASE):
        add("network_topology")
    if re.search(r"火山|volcano", text, re.IGNORECASE):
        add("volcano_plot")
    if re.search(r"(?<![a-z])vip(?![a-z])|vip\s*得?分|变量重要", text, re.IGNORECASE):
        add("vip_scores")
    if re.search(r"热图|heatmap", text, re.IGNORECASE) and re.search(
        r"vip|重要", text, re.IGNORECASE
    ):
        add("heatmap_top_vip")
    if re.search(r"家族大小|family\s*size", text, re.IGNORECASE):
        add("family_size_distribution")
    if re.search(r"化学类|chemical\s*class", text, re.IGNORECASE):
        add("chemical_class_distribution")
        if "拓扑" in text or "topology" in lower:
            add("network_topology")
    if re.search(r"kegg|气泡|富集", text, re.IGNORECASE):
        add("kegg_compound_bubble")
    if re.search(r"mass2motif|motif\s*overview|总览", text, re.IGNORECASE):
        add("mass2motif_overview")
    if re.search(r"组强度|group\s*intensity|fbmn", text, re.IGNORECASE):
        add("fbmn_group_intensity")
    if re.search(r"\bpca\b|主成分", text, re.IGNORECASE):
        add("pca_plot")
    if re.search(r"pls-?da|plsda", text, re.IGNORECASE):
        add("plsda_plot")
    if re.search(r"pearson|皮尔逊", text, re.IGNORECASE):
        add("pearson_distribution")
    if re.search(r"余弦|cosine", text, re.IGNORECASE):
        add("cosine_distribution")

    # 仅着色意图、未点名图类型时：得分图默认
    if not stems and _COLORING_HINT_RE.search(text):
        if _hint_to_color_by(text) in {"chemical_category", "family", "degree", "log2FC"}:
            add("network_topology")
        else:
            add(*DEFAULT_COLORING_STEMS)
    return stems


# ---------------------------------------------------------------------------
# 第三期：统一意图对象
# {analysis, exclude_analysis, targets, color_by/channel, thresholds, facet?, size_by?}
# ---------------------------------------------------------------------------

ANALYSIS_KINDS = (
    "stats",
    "networking",
    "kegg",
    "annotation",
    "deepmass",
    "xcms",
)

# 图 stem → 依赖的分析种类
_STEM_TO_ANALYSIS: dict[str, str] = {
    "pca_plot": "stats",
    "plsda_plot": "stats",
    "volcano_plot": "stats",
    "vip_scores": "stats",
    "heatmap_top_vip": "stats",
    "network_topology": "networking",
    "family_size_distribution": "networking",
    "cosine_distribution": "networking",
    "degree_distribution": "networking",
    "pearson_distribution": "networking",
    "fbmn_group_intensity": "networking",
    "chemical_class_distribution": "networking",
    "family_chemical_consensus": "networking",
    "annotation_propagation_summary": "networking",
    "mass2motif_overview": "networking",
    "mass2motif_fragments": "networking",
    "motif_spectrum_heatmap": "networking",
    "mass2motif_network": "networking",
    "kegg_compound_bubble": "kegg",
    "kegg_compound_dotplot": "kegg",
    "kegg_compound_barplot": "kegg",
}

# 计划步骤里匹配到这些子串 → 分析种类
_ANALYSIS_TOOL_MARKERS: dict[str, tuple[str, ...]] = {
    "stats": ("statistical_analysis_mixomics", "mixomics"),
    "networking": ("molecular_networking_",),
    "kegg": ("kegg_compound_enrichment",),
    "annotation": ("spectral_annotation", "library_match_"),
    "deepmass": ("deepmass_annotation",),
    "xcms": (
        "data_preprocessing_xcms",
        "feature_filtering_and_missing_value_imputation",
        "extract_differential_features",
    ),
}

_ONLY_FIGURE_RE = re.compile(
    r"(?:只要|仅(?:要|输出|生成|画|做)?|只(?:做|画|出|看)|only\s+(?:need|want|show|plot))\s*",
    re.IGNORECASE,
)
_EXCLUDE_NET_RE = re.compile(
    r"(?:不要|跳过|别做|无需|不用|不跑|禁止).{0,8}(?:分子网络|网络分析|networking|fbmn|gnps|ms2lda|molnet)|"
    r"(?:no|skip|without)\s+(?:molecular\s*)?network",
    re.IGNORECASE,
)
_EXCLUDE_KEGG_RE = re.compile(
    r"(?:不要|跳过|别做|无需|不用|不跑).{0,6}(?:kegg|富集)|(?:no|skip|without)\s+kegg",
    re.IGNORECASE,
)
_EXCLUDE_DEEPMASS_RE = re.compile(
    r"(?:不要|跳过|别做|无需|不用|不跑).{0,6}deepmass|(?:no|skip|without)\s+deepmass",
    re.IGNORECASE,
)
_EXCLUDE_STATS_RE = re.compile(
    r"(?:不要|跳过|别做|无需|不用|不跑).{0,8}(?:统计|pca|pls|mixomics)|"
    r"(?:no|skip|without)\s+(?:stats|statistics|mixomics|pca)",
    re.IGNORECASE,
)
_FACET_RE = re.compile(
    r"(?:按|用)\s*([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)\s*(?:分面|分面展示)|"
    r"facet\s*(?:by|with)\s+([A-Za-z_][\w]*)",
    re.IGNORECASE,
)
_SIZE_BY_RE = re.compile(
    r"(?:点大小|大小|size)\s*(?:按|用|by)\s*([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)|"
    r"size\s*(?:by|with)\s+([A-Za-z_][\w]*)",
    re.IGNORECASE,
)


def _parse_facet(text: str) -> str | None:
    m = _FACET_RE.search(text)
    if not m:
        return None
    for g in m.groups():
        if g:
            return g.strip()
    return None


def _parse_size_by(text: str) -> str | None:
    m = _SIZE_BY_RE.search(text)
    if not m:
        return None
    for g in m.groups():
        if g:
            return g.strip()
    return None


def _parse_exclude_analysis(text: str) -> list[str]:
    out: list[str] = []
    if _EXCLUDE_NET_RE.search(text):
        out.append("networking")
    if _EXCLUDE_KEGG_RE.search(text):
        out.append("kegg")
    if _EXCLUDE_DEEPMASS_RE.search(text):
        out.append("deepmass")
    if _EXCLUDE_STATS_RE.search(text):
        out.append("stats")
    return out


def _parse_only_mode(text: str) -> bool:
    """用户是否用「只要/仅」限定要出的图（而非完整流水线）。"""
    return bool(_ONLY_FIGURE_RE.search(text))


def _infer_analysis_from_targets(targets: list[str], text: str) -> list[str]:
    kinds: list[str] = []
    for stem in targets:
        kind = _STEM_TO_ANALYSIS.get(stem)
        if kind and kind not in kinds:
            kinds.append(kind)
    lower = text.lower()
    if re.search(r"\bxcms\b|峰检测|预处理", text, re.IGNORECASE) and "xcms" not in kinds:
        kinds.insert(0, "xcms")
    if re.search(r"注释|annotation|library\s*match", text, re.IGNORECASE) and "annotation" not in kinds:
        kinds.append("annotation")
    if re.search(r"deepmass", text, re.IGNORECASE) and "deepmass" not in kinds:
        kinds.append("deepmass")
    if re.search(r"统计|mixomics|pca|pls|火山|vip", text, re.IGNORECASE) and "stats" not in kinds:
        # 仅排除「不要统计」时不加
        if "stats" not in _parse_exclude_analysis(text):
            kinds.append("stats")
    if re.search(r"分子网络|networking|fbmn|gnps|ms2lda|拓扑", text, re.IGNORECASE):
        if "networking" not in kinds and "networking" not in _parse_exclude_analysis(text):
            kinds.append("networking")
    if re.search(r"kegg|通路富集", text, re.IGNORECASE):
        if "kegg" not in kinds and "kegg" not in _parse_exclude_analysis(text):
            kinds.append("kegg")
    del lower
    return kinds


def _validate_metadata_color_by(
    color_by: str | None,
    *,
    metadata_columns: list[str],
    metadata_csv: str | None,
    targets: list[str],
) -> tuple[str | None, list[str], list[str]]:
    """返回 (resolved_color_by, errors, warnings)。

    非拓扑内置字段一律按 metadata 列校验；缺列时给出可用列与引导。
    """
    del targets  # 保留签名兼容；校验不再依赖目标图类型
    errors: list[str] = []
    warnings: list[str] = []
    builtin = {"Cluster", "family", "degree", "chemical_category", "log2FC", "count", "neglog10"}
    if not color_by or color_by in builtin:
        return color_by, errors, warnings
    if not metadata_columns and not metadata_csv:
        warnings.append(
            f"请求按「{color_by}」着色，但当前会话未找到 metadata.csv，"
            "请上传含该列的 metadata 后再试。"
        )
        return color_by, errors, warnings
    try:
        matched = match_color_by_column(
            color_by,
            metadata_csv,
            columns=metadata_columns or None,
            fallback=False,
        )
    except Exception:
        matched = None
    if matched:
        return matched, errors, warnings
    available = ", ".join(metadata_columns) if metadata_columns else "(无可用列)"
    hint = ""
    low = color_by.lower()
    if low in {"time", "timepoint"} or "时间" in color_by:
        hint = " 若要用时间着色，请在 metadata 中增加 Time/timepoint 等列。"
    elif low == "batch" or "批次" in color_by:
        hint = " 若要用批次着色，请在 metadata 中增加 Batch 列。"
    elif low in {"group", "class"} or "分组" in color_by:
        hint = " 请确认 metadata 中分组列名（常见：Group/class）。"
    errors.append(
        f"metadata 中不存在「{color_by}」列，无法按该字段着色。"
        f"可用列：{available}。{hint}".strip()
    )
    # 保留用户请求的 color_by 便于提示；调用方见 errors 后勿落盘重绘
    return color_by, errors, warnings

def intent_to_plot_patch(intent: dict[str, Any]) -> dict[str, Any]:
    """从统一意图对象取出可并入 plot_config 的字段。"""
    if not intent:
        return {}
    patch: dict[str, Any] = {}
    for key in (
        "color_by",
        "color_type",
        "cluster",
        "thresholds",
        "color_channel",
        "facet",
        "size_by",
    ):
        if intent.get(key) is not None:
            patch[key] = intent[key]
    if isinstance(intent.get("marks"), dict) and intent["marks"]:
        patch["marks"] = dict(intent["marks"])
    targets = intent.get("targets") or intent.get("target_stems")
    if targets:
        patch["target_stems"] = list(targets)
        patch["targets"] = list(targets)
    return patch


def _parse_thresholds(text: str) -> dict[str, float] | None:
    thresholds: dict[str, float] = {}
    m = _P_THRESHOLD_RE.search(text)
    if m:
        try:
            thresholds["p"] = float(m.group(1))
        except ValueError:
            pass
    m = _FC_THRESHOLD_RE.search(text)
    if m:
        try:
            thresholds["log2fc"] = float(m.group(1))
        except ValueError:
            pass
    # 常见「p<0.05」简写
    if "p" not in thresholds:
        m2 = re.search(r"p\s*[<＜≤<=]\s*(0?\.\d+)", text, re.IGNORECASE)
        if m2:
            try:
                thresholds["p"] = float(m2.group(1))
            except ValueError:
                pass
    return thresholds or None


def _parse_color_channel(text: str) -> str | None:
    # 「按 Count 着色」「颜色用 FDR」
    m = re.search(
        r"(?:按|用|换成|改为)\s*([A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)\s*(?:着色|上色|作色|配色|颜色)",
        text,
        re.IGNORECASE,
    )
    token = m.group(1).strip() if m else None
    if not token:
        if re.search(r"(?:颜色|着色).{0,12}(?:count|数量)", text, re.IGNORECASE):
            return "count"
        if re.search(r"(?:颜色|着色).{0,12}(?:fdr|neglog|-log10|显著性)", text, re.IGNORECASE):
            return "neglog10"
        if re.search(r"(?:颜色|着色).{0,12}(?:load|载荷)", text, re.IGNORECASE):
            return "load"
        if re.search(r"(?:颜色|着色).{0,12}(?:谱图|n_spectra)", text, re.IGNORECASE):
            return "n_spectra"
        return None
    for alias, canon in _CHANNEL_ALIASES.items():
        if token.lower() == alias.lower() or alias in token:
            return canon
    return None


def _parse_top_n(text: str) -> int | None:
    m = _TOP_N_RE.search(text)
    if not m:
        return None
    try:
        return max(3, min(100, int(m.group(1))))
    except ValueError:
        return None


def _normalize_topology_color_by(token: str) -> str:
    key = token.strip()
    if key in _TOPOLOGY_COLOR_ALIASES:
        return _TOPOLOGY_COLOR_ALIASES[key]
    lower = key.lower()
    for alias, canon in _TOPOLOGY_COLOR_ALIASES.items():
        if alias.lower() == lower:
            return canon
    return key


def has_coloring_intent(message: str) -> bool:
    """用户消息是否包含「按某维度/聚类着色」或阈值/通道类分析意图。"""
    text = (message or "").strip()
    if not text:
        return False
    if _COLOR_BY_RE.search(text):
        return True
    if _CLUSTER_HINT_RE.search(text) and _COLORING_HINT_RE.search(text):
        return True
    if _extract_cluster_n(text) and ("着色" in text or "color" in text.lower() or "作色" in text):
        return True
    if _hint_to_color_by(text) and _COLORING_HINT_RE.search(text):
        return True
    if _TIME_HINT_RE.search(text) and _COLORING_HINT_RE.search(text):
        return True
    if _BATCH_HINT_RE.search(text) and _COLORING_HINT_RE.search(text):
        return True
    if _parse_thresholds(text):
        return True
    if _parse_color_channel(text):
        return True
    if re.search(r"拓扑.{0,20}(?:化学|家族|度数|着色)", text) or re.search(
        r"(?:化学|家族|度数).{0,12}(?:拓扑|着色)", text
    ):
        return True
    return False


def has_analysis_plot_intent(message: str) -> bool:
    """更宽：含着色意图，或明确点名图类型并要求改映射。"""
    text = (message or "").strip()
    if not text:
        return False
    if has_coloring_intent(text):
        return True
    if _infer_target_stems(text) and (
        _COLORING_HINT_RE.search(text) or _parse_thresholds(text) or _parse_top_n(text)
    ):
        return True
    return False


def build_analysis_intent(
    instruction: str,
    *,
    plot_type: str | None = None,
    metadata_columns: list[str] | None = None,
    metadata_csv: str | None = None,
) -> dict[str, Any]:
    """解析统一分析意图对象（第三期）。

    结构：
      analysis / exclude_analysis / only_figures
      targets
      color_by / color_type / color_channel / cluster / thresholds
      facet? / size_by?
      marks / errors / warnings
    """
    text = (instruction or "").strip()
    if not text:
        return {}

    # 先走第二期映射解析（得到 color_by / thresholds / target_stems 等）
    mapping = _parse_mapping_intent(
        text,
        plot_type=plot_type,
        metadata_columns=metadata_columns,
        metadata_csv=metadata_csv,
    )

    targets = list(mapping.get("target_stems") or [])
    only_figures = _parse_only_mode(text)
    # 「只要火山+VIP」：若 only 模式且已点名图，以点名 stems 为准
    if only_figures:
        named = _infer_target_stems(text)
        # 去掉「仅着色默认」的误加：only 模式下必须显式点名
        named = [
            s
            for s in named
            if not (
                s in DEFAULT_COLORING_STEMS
                and not re.search(r"\bpca\b|主成分|pls", text, re.IGNORECASE)
                and s in ("pca_plot", "plsda_plot")
                and "火山" not in text
                and "vip" not in text.lower()
            )
        ]
        # 重新推断：only 模式优先显式图名
        explicit: list[str] = []
        if re.search(r"火山|volcano", text, re.IGNORECASE):
            explicit.append("volcano_plot")
        if re.search(r"(?<![a-z])vip(?![a-z])|vip\s*得?分|变量重要", text, re.IGNORECASE):
            explicit.append("vip_scores")
        if re.search(r"热图|heatmap", text, re.IGNORECASE) and re.search(
            r"vip|重要", text, re.IGNORECASE
        ):
            explicit.append("heatmap_top_vip")
        if re.search(r"\bpca\b|主成分", text, re.IGNORECASE):
            explicit.append("pca_plot")
        if re.search(r"pls-?da|plsda", text, re.IGNORECASE):
            explicit.append("plsda_plot")
        if re.search(r"拓扑|topology", text, re.IGNORECASE):
            explicit.append("network_topology")
        if re.search(r"kegg|气泡", text, re.IGNORECASE):
            explicit.append("kegg_compound_bubble")
        if explicit:
            targets = list(dict.fromkeys(explicit))
        elif named:
            targets = named

    exclude_analysis = _parse_exclude_analysis(text)
    analysis = _infer_analysis_from_targets(targets, text)
    analysis = [a for a in analysis if a not in exclude_analysis]
    # only_figures：分析集合收缩为 targets 所需
    if only_figures and targets:
        needed = []
        for stem in targets:
            kind = _STEM_TO_ANALYSIS.get(stem)
            if kind and kind not in needed and kind not in exclude_analysis:
                needed.append(kind)
        analysis = needed

    facet = _parse_facet(text)
    size_by = _parse_size_by(text)

    color_by = mapping.get("color_by")
    resolved, errors, warnings = _validate_metadata_color_by(
        str(color_by) if color_by else None,
        metadata_columns=[str(c) for c in (metadata_columns or [])],
        metadata_csv=metadata_csv,
        targets=targets,
    )
    if resolved:
        mapping["color_by"] = resolved

    # 无任何有效信号则空
    has_signal = bool(
        analysis
        or exclude_analysis
        or only_figures
        or targets
        or mapping.get("color_by")
        or mapping.get("cluster")
        or mapping.get("thresholds")
        or mapping.get("color_channel")
        or mapping.get("marks")
        or facet
        or size_by
        or errors
    )
    if not has_signal:
        return {}

    intent: dict[str, Any] = {
        "analysis": analysis,
        "exclude_analysis": exclude_analysis,
        "only_figures": only_figures,
        "targets": targets,
        "target_stems": targets,  # 兼容旧字段
        "color_by": mapping.get("color_by"),
        "color_type": mapping.get("color_type"),
        "color_channel": mapping.get("color_channel"),
        "cluster": mapping.get("cluster"),
        "thresholds": mapping.get("thresholds"),
        "facet": facet,
        "size_by": size_by,
        "marks": mapping.get("marks") if isinstance(mapping.get("marks"), dict) else None,
        "errors": errors,
        "warnings": warnings,
    }
    # 去掉纯 None（保留 cluster:None 有时有用；这里清空 marks）
    if not intent["marks"]:
        intent["marks"] = None
    return intent


def _parse_mapping_intent(
    text: str,
    *,
    plot_type: str | None = None,
    metadata_columns: list[str] | None = None,
    metadata_csv: str | None = None,
) -> dict[str, Any]:
    """第二期映射字段解析（内部）。"""
    if plot_type and plot_type not in INTENT_PLOT_TYPES:
        return {}

    patch: dict[str, Any] = {}
    columns = [str(c) for c in (metadata_columns or [])]
    stems = _infer_target_stems(text)

    thresholds = _parse_thresholds(text)
    if thresholds:
        patch["thresholds"] = thresholds
        if "volcano_plot" not in stems and (
            plot_type in {None, "volcano"} or "火山" in text or "volcano" in text.lower()
        ):
            stems = list(dict.fromkeys([*stems, "volcano_plot"]))

    top_n = _parse_top_n(text)
    if top_n is not None:
        patch.setdefault("marks", {})
        if isinstance(patch["marks"], dict):
            patch["marks"]["top_n"] = top_n

    channel = _parse_color_channel(text)
    if channel:
        patch["color_channel"] = channel
        if channel in {"count", "neglog10"} and "kegg_compound_bubble" not in stems:
            if plot_type in {None, "kegg_bubble", "kegg_dotplot"} or re.search(
                r"kegg|气泡|富集", text, re.IGNORECASE
            ):
                stems = list(dict.fromkeys([*stems, "kegg_compound_bubble"]))
        if channel in {"n_spectra", "load"} and "mass2motif_overview" not in stems:
            if plot_type in {None, "mass2motif_overview"} or "motif" in text.lower():
                stems = list(dict.fromkeys([*stems, "mass2motif_overview"]))
        if channel in {"log2FC", "neglog10p"} and plot_type in {None, "volcano"}:
            patch["color_type"] = "quantitative"

    cluster_n = _extract_cluster_n(text)
    wants_cluster = bool(cluster_n) or (
        _CLUSTER_HINT_RE.search(text)
        and ("着色" in text or "color" in text.lower() or "上色" in text or "作色" in text)
    )
    scores_context = plot_type in {None, "pca", "plsda"} and (
        not stems
        or any(s in {"pca_plot", "plsda_plot"} for s in stems)
        or not any(
            s.startswith("network_") or s.startswith("kegg_") or "motif" in s or "volcano" in s
            for s in stems
        )
    )
    if wants_cluster and scores_context and plot_type in {None, "pca", "plsda"}:
        n = cluster_n or 3
        patch["cluster"] = {"method": "kmeans", "n": n}
        patch["color_by"] = "Cluster"
        patch["color_type"] = "nominal"
        patch["target_stems"] = [s for s in stems if s in DEFAULT_COLORING_STEMS] or list(
            DEFAULT_COLORING_STEMS
        )
        return patch

    color_token: str | None = None
    match = _COLOR_BY_RE.search(text)
    if match:
        for g in match.groups():
            if g:
                color_token = g.strip()
                break
    if not color_token:
        color_token = _hint_to_color_by(text)

    if color_token:
        if color_token.lower() in {"pca", "pls", "plsda", "图", "颜色", "color", "样本", "sample"}:
            color_token = None

    if color_token:
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in color_token)
        if has_cjk or " " in color_token:
            if _TIME_HINT_RE.search(color_token):
                color_token = "time"
            elif _BATCH_HINT_RE.search(color_token):
                color_token = "batch"
            elif re.search(r"化学", color_token):
                color_token = "chemical_category"
            elif re.search(r"家族", color_token):
                color_token = "family"
            elif re.search(r"度数", color_token):
                color_token = "degree"

        topology_like = plot_type == "network_topology" or (
            plot_type is None
            and (
                "network_topology" in stems
                or color_token.lower() in {k.lower() for k in _TOPOLOGY_COLOR_ALIASES}
                or color_token in {"chemical_category", "family", "degree", "log2FC"}
            )
        )
        if topology_like and color_token.lower() not in {"time", "batch", "group"}:
            resolved = _normalize_topology_color_by(color_token)
            patch["color_by"] = resolved
            patch["cluster"] = None
            if resolved in {"degree", "log2FC"}:
                patch["color_type"] = "quantitative"
            else:
                patch["color_type"] = "nominal"
            if "network_topology" not in stems:
                stems = list(dict.fromkeys([*stems, "network_topology"]))
        else:
            resolved = color_token
            if metadata_csv or columns:
                try:
                    matched = match_color_by_column(
                        color_token,
                        metadata_csv,
                        columns=columns or None,
                        fallback=False,
                    )
                    if matched:
                        resolved = matched
                except Exception:
                    resolved = color_token
            patch["color_by"] = resolved
            patch["cluster"] = None
            if color_token.lower() in {"time", "timepoint"} or _TIME_HINT_RE.search(str(resolved)):
                patch["color_type"] = "quantitative"
            if not stems:
                stems = list(DEFAULT_COLORING_STEMS)

    if stems:
        patch["target_stems"] = stems

    useful_keys = {"color_by", "cluster", "thresholds", "color_channel", "marks", "target_stems"}
    if not any(k in patch for k in useful_keys if k != "target_stems"):
        if "target_stems" in patch and not (
            thresholds or channel or top_n is not None or color_token
        ):
            if not has_coloring_intent(text) and not _parse_thresholds(text):
                # 仍保留 stems，供 only_figures / 计划裁剪
                if not stems:
                    return {}
    return patch


def parse_analysis_intent(
    instruction: str,
    *,
    plot_type: str | None = None,
    metadata_columns: list[str] | None = None,
    metadata_csv: str | None = None,
) -> dict[str, Any]:
    """
    兼容入口：返回统一意图对象（含 targets/analysis 等），
    同时保留 target_stems 等旧字段，可直接作 plot_config patch 使用。
    """
    return build_analysis_intent(
        instruction,
        plot_type=plot_type,
        metadata_columns=metadata_columns,
        metadata_csv=metadata_csv,
    )


def task_matches_analysis_kind(task: str, kind: str) -> bool:
    lower = str(task).lower()
    markers = _ANALYSIS_TOOL_MARKERS.get(kind) or ()
    return any(m.lower() in lower for m in markers)


# only_figures 时仍保留的上游步骤（产出差异表/峰表，火山与 VIP 常依赖）
_ONLY_KEEP_KINDS = frozenset({"xcms"})


def prune_plan_tasks_by_intent(
    tasks: list[str],
    intent: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    """按意图裁剪计划步骤。返回 (kept, removed)。"""
    if not intent or not tasks:
        return list(tasks or []), []

    exclude = set(intent.get("exclude_analysis") or [])
    only_figures = bool(intent.get("only_figures"))
    analysis = set(intent.get("analysis") or [])

    kept: list[str] = []
    removed: list[str] = []

    for task in tasks:
        text = str(task)
        lower = text.lower()
        # 本地 visual 工具：拼图始终保留；分析意图 plot_edit 由别处裁
        if any(k in lower for k in ("image_merge", "merge_edit")):
            kept.append(text)
            continue
        if "plot_edit" in lower:
            kept.append(text)
            continue

        drop = False
        for kind in exclude:
            if task_matches_analysis_kind(text, kind):
                drop = True
                break

        if not drop and only_figures and analysis:
            # 只要指定图：丢掉不在 analysis 集合内的旁支分析（网络/KEGG 等）
            # xcms 等上游保留，除非已被 exclude
            matched_kinds = [
                k for k in ANALYSIS_KINDS if task_matches_analysis_kind(text, k)
            ]
            if matched_kinds:
                if all(k in _ONLY_KEEP_KINDS for k in matched_kinds):
                    drop = False
                elif not any(k in analysis or k in _ONLY_KEEP_KINDS for k in matched_kinds):
                    drop = True

        if drop:
            removed.append(text)
        else:
            kept.append(text)

    return kept, removed


def format_coloring_task(intent: dict[str, Any], user_message: str) -> str:
    """生成计划步骤文本，供 Agent 执行 plot_edit（兜底用）。"""
    stems = intent.get("targets") or intent.get("target_stems") or list(DEFAULT_COLORING_STEMS)
    stem_list = " / ".join(f"{s}.png" for s in stems)
    parts: list[str] = []
    if intent.get("cluster"):
        n = (intent["cluster"] or {}).get("n") or 3
        parts.append(f"k-means cluster coloring with n={n}")
    if intent.get("color_by"):
        parts.append(f"color_by={intent['color_by']}")
    if intent.get("color_channel"):
        parts.append(f"color_channel={intent['color_channel']}")
    if intent.get("thresholds"):
        parts.append(f"thresholds={intent['thresholds']}")
    if intent.get("facet"):
        parts.append(f"facet={intent['facet']}")
    if intent.get("size_by"):
        parts.append(f"size_by={intent['size_by']}")
    marks = intent.get("marks") if isinstance(intent.get("marks"), dict) else {}
    if marks and marks.get("top_n"):
        parts.append(f"top_n={marks['top_n']}")
    detail = ", ".join(parts) if parts else "analysis intent"
    snippet = (user_message or "").strip().replace("\n", " ")[:180]
    return (
        f"Use plot_edit to recolor {stem_list} with analysis intent ({detail}) "
        f"per user request: {snippet}"
    )


def describe_intent(intent: dict[str, Any]) -> str:
    if not intent:
        return ""
    bits: list[str] = []
    if intent.get("only_figures") and (intent.get("targets") or intent.get("target_stems")):
        bits.append("只要图：" + "/".join(intent.get("targets") or intent.get("target_stems") or []))
    if intent.get("exclude_analysis"):
        bits.append("排除：" + ",".join(intent["exclude_analysis"]))
    if intent.get("analysis"):
        bits.append("分析：" + ",".join(intent["analysis"]))
    if intent.get("cluster"):
        n = (intent.get("cluster") or {}).get("n") or 3
        bits.append(f"KMeans 聚类着色（k={n}）")
    col = intent.get("color_by")
    if col:
        ctype = intent.get("color_type") or "nominal"
        bits.append(f"按「{col}」着色（{ctype}）")
    ch = intent.get("color_channel")
    if ch:
        bits.append(f"颜色通道={ch}")
    thr = intent.get("thresholds")
    if isinstance(thr, dict) and thr:
        bits.append(f"阈值 {thr}")
    if intent.get("facet"):
        bits.append(f"分面={intent['facet']}")
    if intent.get("size_by"):
        bits.append(f"点大小={intent['size_by']}")
    marks = intent.get("marks") if isinstance(intent.get("marks"), dict) else {}
    if marks and marks.get("top_n"):
        bits.append(f"top_n={marks['top_n']}")
    if intent.get("errors"):
        bits.append("错误：" + "；".join(intent["errors"]))
    return "；".join(bits)


def merge_intent_into_patch(patch: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    """意图字段优先于 LLM patch。"""
    merged = dict(patch or {})
    if not intent:
        return merged
    plot_patch = intent_to_plot_patch(intent)
    for key in ("color_by", "color_type", "cluster", "thresholds", "color_channel", "facet", "size_by"):
        if key in plot_patch:
            merged[key] = plot_patch[key]
    if isinstance(plot_patch.get("marks"), dict):
        merged.setdefault("marks", {})
        if isinstance(merged["marks"], dict):
            merged["marks"].update(plot_patch["marks"])
    return merged


def default_stems_for_tool(tool_name: str) -> list[str]:
    return list(TOOL_DEFAULT_STEMS.get(tool_name or "", ()))


__all__ = [
    "ANALYSIS_KINDS",
    "DEFAULT_COLORING_STEMS",
    "DEFAULT_COLORING_PLOT_TYPES",
    "INTENT_PLOT_TYPES",
    "TOOL_DEFAULT_STEMS",
    "has_coloring_intent",
    "has_analysis_plot_intent",
    "build_analysis_intent",
    "parse_analysis_intent",
    "intent_to_plot_patch",
    "prune_plan_tasks_by_intent",
    "task_matches_analysis_kind",
    "format_coloring_task",
    "describe_intent",
    "merge_intent_into_patch",
    "default_stems_for_tool",
]
