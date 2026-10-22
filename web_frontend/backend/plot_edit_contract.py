"""把改图指令分成样式、分析参数、分析方法三类。

样式只改配置后重绘。分析参数用已有统计列重算筛选，不改 B 的原表。
分析方法必须回到 Agent B，这里直接拒绝。
"""
from __future__ import annotations

import re
from typing import Any

EDIT_STYLE = "style"
EDIT_ANALYSIS_PARAM = "analysis_param"
EDIT_ANALYSIS_METHOD = "analysis_method"

_METHOD_RE = re.compile(
    r"归一化|换模型|重新训练|重跑分析|重新分析|重新做|重新计算模型|"
    r"改用.{0,12}检验|t\s*检验|wilcox|更换统计|换一种统计",
    re.I,
)
_PARAM_RE = re.compile(
    r"阈值|p\s*值|p\s*-?\s*value|pvalue|fdr|padj|log\s*2\s*fc|log2fc|倍数|"
    r"vip\s*(?:大于|＞|>|≥|>=)|前\s*\d+\s*(?:行|条|个)|行数",
    re.I,
)
_STYLE_RE = re.compile(r"标题|颜色|配色|色号|字体|字号|图例")
_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")
_TITLE_RE = re.compile(r"标题(?:改为|改成|换成|为)\s*[「\"']?(.+?)[」\"']?(?:[，,。.]|$)")
_P_RE = re.compile(
    r"(?:p\s*值|p\s*-?\s*value|pvalue|显著性阈值|^|[^a-z])p\s*"
    r"(?:小于|<|＜|≤|<=|=|＝)\s*(0?\.\d+)",
    re.I,
)
_FC_RE = re.compile(
    r"(?:log\s*2\s*fc|log2fc|倍数)\s*(?:大于|≥|>=|>|＝|=)\s*(\d+(?:\.\d+)?)",
    re.I,
)
_UP_RE = re.compile(r"上调(?:用|为|改成|改为)?\s*(#[0-9A-Fa-f]{6})")
_DOWN_RE = re.compile(r"下调(?:用|为|改成|改为)?\s*(#[0-9A-Fa-f]{6})")
_VIP_RE = re.compile(r"vip\s*(?:阈值)?\s*(?:改为|改成|大于|＞|>|≥|>=|＝|=)\s*(\d+(?:\.\d+)?)", re.I)
_FDR_RE = re.compile(r"(?:fdr|padj|校正(?:后)?\s*p)\s*(?:小于|<|＜|≤|<=)\s*(0?\.\d+)", re.I)
_TOP_RE = re.compile(r"(?:前|top)\s*(\d+)\s*(?:行|条|个)?", re.I)
_COMP_RE = re.compile(
    r"(?:第\s*)?([1-9])\s*(?:和|与|,|，)\s*(?:第\s*)?([1-9])\s*(?:主成分|成分|pc)",
    re.I,
)
_GROUP_COLOR_RE = re.compile(
    r"把\s*([A-Za-z0-9_\-]+|[\u4e00-\u9fff]{1,12})\s*(?:样本|组)?\s*改成\s*(红色|蓝色|绿色|#[0-9A-Fa-f]{6})"
)
_NAMED_COLORS = {"红色": "#E64B35", "蓝色": "#4DBBD5", "绿色": "#00A087"}
_NEGATED_PARAM_RE = re.compile(
    r"(?:不要|别|勿|无需|不用|不改|别改).{0,12}(?:阈值|p\s*值|pvalue|fdr|padj|"
    r"log\s*2\s*fc|log2fc|vip|主成分|统计)",
    re.I,
)
_POSITIVE_PARAM_RE = re.compile(
    r"(?:改为|改成|大于|小于|＞|＜|>=|<=|>|<|＝|=)\s*(?:0?\.\d+|\d+(?:\.\d+)?)",
    re.I,
)
_STYLE_KEYS = (
    "title",
    "title_align",
    "palette",
    "colors",
    "font_size",
    "figure_size",
    "legend",
    "cmap",
    "ellipse",
    "hide_isolates",
    "show_grid",
    "show_sample_labels",
    "score_style",
    "size_by",
    "axes",
    "color_by",
    "color_type",
)
_ANALYSIS_KEYS = ("thresholds", "vip_threshold", "fdr_cut", "components", "p_stat")
_MARK_ANALYSIS = frozenset({"top_n", "vip_threshold", "top_frags", "top_motifs", "top_spectra"})
_PARAM_PLOT_TYPES = frozenset(
    {"volcano", "vip_bar", "heatmap_vip", "kegg_bubble", "kegg_dotplot", "kegg_barplot", "pca", "plsda"}
)


def _param_change_requested(text: str) -> bool:
    """否定句里的「不要改阈值」不是在改阈值。写明了数字才算参数修改。"""
    if _NEGATED_PARAM_RE.search(text) and not _POSITIVE_PARAM_RE.search(text):
        return False
    return True


def classify_plot_edit(instruction: str, plot_type: str = "") -> str:
    text = instruction or ""
    if _METHOD_RE.search(text):
        return EDIT_ANALYSIS_METHOD
    if _param_change_requested(text) and plot_type in _PARAM_PLOT_TYPES and _PARAM_RE.search(text):
        return EDIT_ANALYSIS_PARAM
    if _param_change_requested(text) and plot_type in {"pca", "plsda"} and _COMP_RE.search(text):
        return EDIT_ANALYSIS_PARAM
    if _STYLE_RE.search(text):
        return EDIT_STYLE
    return EDIT_STYLE


def _volcano_style_and_params(instruction: str) -> dict[str, Any]:
    text = instruction or ""
    patch: dict[str, Any] = {}
    title = _TITLE_RE.search(text)
    if title:
        patch["title"] = title.group(1).strip()
    colors: dict[str, str] = {}
    up = _UP_RE.search(text)
    down = _DOWN_RE.search(text)
    if up:
        colors["upregulated"] = up.group(1)
    if down:
        colors["downregulated"] = down.group(1)
    if not colors:
        hexes = _HEX_RE.findall(text)
        if len(hexes) >= 1 and re.search(r"上调|显著", text):
            colors["upregulated"] = hexes[0]
        if len(hexes) >= 2 and re.search(r"下调", text):
            colors["downregulated"] = hexes[1]
    if colors:
        patch["colors"] = colors
    thresholds: dict[str, float] = {}
    p_match = _P_RE.search(text)
    if p_match:
        value = float(p_match.group(1))
        if re.search(r"fdr|padj|校正", text, re.I):
            thresholds["padj"] = value
            patch["p_stat"] = "padj"
        else:
            thresholds["p"] = value
            patch["p_stat"] = "pvalue"
    fc_match = _FC_RE.search(text)
    if fc_match:
        thresholds["log2fc"] = float(fc_match.group(1))
    if thresholds:
        patch["thresholds"] = thresholds
    return patch


def _title_and_group_color(instruction: str) -> dict[str, Any]:
    text = instruction or ""
    patch: dict[str, Any] = {}
    title = _TITLE_RE.search(text)
    if title:
        patch["title"] = title.group(1).strip()
    color_match = _GROUP_COLOR_RE.search(text)
    if color_match:
        raw = color_match.group(2)
        patch["palette"] = {color_match.group(1): _NAMED_COLORS.get(raw, raw)}
    return patch


def _analysis_param_patch(plot_type: str, instruction: str) -> dict[str, Any]:
    text = instruction or ""
    patch: dict[str, Any] = {}
    vip = _VIP_RE.search(text)
    if vip and plot_type in {"vip_bar", "heatmap_vip"}:
        patch["vip_threshold"] = float(vip.group(1))
    fdr = _FDR_RE.search(text)
    if fdr and plot_type.startswith("kegg"):
        patch["fdr_cut"] = float(fdr.group(1))
    top = _TOP_RE.search(text)
    if top and plot_type in {"heatmap_vip", "vip_bar", "kegg_bubble", "kegg_dotplot", "kegg_barplot"}:
        patch.setdefault("marks", {})["top_n"] = int(top.group(1))
    comps = _COMP_RE.search(text)
    if comps and plot_type in {"pca", "plsda"}:
        patch["components"] = [int(comps.group(1)), int(comps.group(2))]
    return patch


def apply_instruction_contract(
    plot_type: str,
    instruction: str,
    patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """返回 edit_kind、合并后的 patch、给用户看的说明。分析方法不改图。"""
    kind = classify_plot_edit(instruction, plot_type)
    merged = dict(patch or {})
    warnings: list[str] = []
    message = ""
    if kind == EDIT_ANALYSIS_METHOD:
        message = (
            "这是分析方法修改（归一化、模型或统计检验）。"
            "绘图不会改样本坐标或重跑检验，请回到分析步骤重新执行后再出图。"
        )
        return {
            "edit_kind": kind,
            "patch": merged,
            "warnings": warnings,
            "message": message,
            "blocked": True,
        }
    if plot_type == "volcano":
        parsed = _volcano_style_and_params(instruction)
        if "title" in parsed:
            merged["title"] = parsed["title"]
        if parsed.get("colors"):
            colors = dict(merged.get("colors") or {})
            colors.update(parsed["colors"])
            merged["colors"] = colors
        if parsed.get("thresholds"):
            thresholds = dict(merged.get("thresholds") or {})
            thresholds.update(parsed["thresholds"])
            merged["thresholds"] = thresholds
            kind = EDIT_ANALYSIS_PARAM
        if parsed.get("p_stat"):
            merged["p_stat"] = parsed["p_stat"]
        if kind == EDIT_ANALYSIS_PARAM:
            stat = "校正后 p（padj）" if merged.get("p_stat") == "padj" else "原始 p 值"
            thr = merged.get("thresholds") if isinstance(merged.get("thresholds"), dict) else {}
            bits = []
            if thr.get("p") is not None:
                bits.append(f"p<{thr['p']}")
            if thr.get("padj") is not None:
                bits.append(f"padj<{thr['padj']}")
            if thr.get("log2fc") is not None:
                bits.append(f"|log2FC|≥{thr['log2fc']}")
            detail = "，".join(bits) if bits else stat
            warnings.append(
                f"确认按已有火山表重算显著分类：{detail}。不覆盖 volcano_results.csv，也不重跑统计检验。"
            )
        else:
            warnings.append("只更新标题或颜色后重绘，显著分类和样本坐标保持不变。")
    elif plot_type in {"pca", "plsda", "vip_bar", "heatmap_vip", "kegg_bubble", "kegg_dotplot", "kegg_barplot"}:
        parsed = _title_and_group_color(instruction)
        extra = _analysis_param_patch(plot_type, instruction)
        if "title" in parsed:
            merged["title"] = parsed["title"]
        if parsed.get("palette"):
            palette = dict(merged.get("palette") or {})
            palette.update(parsed["palette"])
            merged["palette"] = palette
        if extra.get("vip_threshold") is not None:
            merged["vip_threshold"] = extra["vip_threshold"]
            kind = EDIT_ANALYSIS_PARAM
        if extra.get("fdr_cut") is not None:
            merged["fdr_cut"] = extra["fdr_cut"]
            kind = EDIT_ANALYSIS_PARAM
        if extra.get("components"):
            merged["components"] = extra["components"]
            kind = EDIT_ANALYSIS_PARAM
        if extra.get("marks"):
            marks = dict(merged.get("marks") or {})
            marks.update(extra["marks"])
            merged["marks"] = marks
            if "top_n" in extra["marks"]:
                kind = EDIT_ANALYSIS_PARAM
        if kind == EDIT_ANALYSIS_PARAM:
            bits: list[str] = []
            if merged.get("vip_threshold") is not None:
                bits.append(f"VIP≥{merged['vip_threshold']}")
            if merged.get("fdr_cut") is not None:
                bits.append(f"FDR<{merged['fdr_cut']}")
            if merged.get("components"):
                bits.append(f"成分 {merged['components']}")
            top_n = (merged.get("marks") or {}).get("top_n")
            if top_n:
                bits.append(f"前 {top_n} 条")
            detail = "，".join(bits) if bits else "已写明的筛选条件"
            warnings.append(
                f"确认按已有结果表重算：{detail}。不覆盖 Agent B 的原始表，也不重新拟合模型或重跑检验。"
            )
        else:
            warnings.append("只更新标题、颜色或图例后重绘，样本坐标和统计结果保持不变。")
    merged["edit_kind"] = kind
    return {
        "edit_kind": kind,
        "patch": merged,
        "warnings": warnings,
        "message": message,
        "blocked": False,
    }


def _style_slice(patch: dict[str, Any] | None) -> dict[str, Any]:
    src = patch or {}
    out: dict[str, Any] = {}
    for key in _STYLE_KEYS:
        if key in src and src[key] is not None:
            out[key] = src[key]
    marks = src.get("marks")
    if isinstance(marks, dict):
        kept = {key: val for key, val in marks.items() if key not in _MARK_ANALYSIS}
        if kept:
            out["marks"] = kept
    return out


def _merge_named(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for key, val in src.items():
        if key in {"palette", "colors", "font_size", "legend", "marks", "axes"} and isinstance(val, dict):
            base = dict(dst.get(key) or {})
            base.update(val)
            dst[key] = base
        else:
            dst[key] = val


def _analysis_slice(patch: dict[str, Any] | None) -> dict[str, Any]:
    src = patch or {}
    out: dict[str, Any] = {}
    for key in _ANALYSIS_KEYS:
        if key in src and src[key] is not None:
            out[key] = src[key]
    marks = src.get("marks")
    if isinstance(marks, dict):
        kept = {key: val for key, val in marks.items() if key in _MARK_ANALYSIS}
        if kept:
            out["marks"] = kept
    return out


def guard_nl_edit(
    plot_type: str,
    instruction: str,
    model_patch: dict[str, Any] | None = None,
    literature_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """自然语言改图的出口：文献只贡献样式，统计数字只来自用户写明的指令。"""
    parsed = apply_instruction_contract(plot_type, instruction, {})
    if parsed.get("blocked"):
        return parsed

    warnings = list(parsed.get("warnings") or [])
    kind = str(parsed.get("edit_kind") or EDIT_STYLE)
    instruction_patch = dict(parsed.get("patch") or {})
    model = dict(model_patch or {})
    literature = dict(literature_patch or {})

    dropped_model = [key for key in _ANALYSIS_KEYS if key in model]
    model_marks = model.get("marks") if isinstance(model.get("marks"), dict) else {}
    dropped_model.extend(f"marks.{key}" for key in _MARK_ANALYSIS if key in model_marks)
    if dropped_model and kind != EDIT_ANALYSIS_PARAM:
        warnings.append("模型返回了统计阈值或筛选条件，但这条指令没有要求修改它们，已忽略。")
    if kind == EDIT_ANALYSIS_PARAM and dropped_model:
        warnings.append("统计阈值以你写明的数字为准，已忽略模型另写的阈值。")

    used_literature = False
    try:
        from web_frontend.backend.plot_edit_registry import looks_like_literature_plot_restyle

        used_literature = looks_like_literature_plot_restyle(instruction)
    except Exception:
        used_literature = False
    lit_analysis = _analysis_slice(literature)
    if used_literature:
        warnings.append("文献只提供配色、图例和标题，不改统计阈值。")
        if lit_analysis:
            warnings.append("已忽略文献里的统计阈值。")

    merged: dict[str, Any] = {}
    if used_literature:
        _merge_named(merged, _style_slice(literature))
    _merge_named(merged, _style_slice(model))
    _merge_named(merged, _style_slice(instruction_patch))
    if kind == EDIT_ANALYSIS_PARAM:
        _merge_named(merged, _analysis_slice(instruction_patch))
    merged["edit_kind"] = kind
    return {
        "edit_kind": kind,
        "patch": merged,
        "warnings": warnings,
        "message": str(parsed.get("message") or ""),
        "blocked": False,
        "used_literature": used_literature,
    }
