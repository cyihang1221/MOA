"""Web 端计划步骤过滤与平台相关修正。"""
from __future__ import annotations

from pathlib import Path

from web_frontend.backend.session_file_resolver import find_session_mgf, mzml_stems
from web_frontend.backend.tool_registry import ALL_AGENT_TOOL_NAMES

RAW_CONVERTER_NAMES = (
    "convert_raw_to_mzml_msconvert",
    "convert_raw_to_mzml_ThermoRawFileParser",
)


def _collect_raw_files(paths: dict[str, str]) -> list[Path]:
    upload = Path(paths["upload"])
    raw_dir = Path(paths.get("raw") or upload / "raw")
    found: list[Path] = []
    seen: set[str] = set()
    for directory in (raw_dir, upload):
        if not directory.is_dir():
            continue
        for pattern in ("*.raw", "*.RAW"):
            for item in directory.glob(pattern):
                key = item.name.lower()
                if key not in seen:
                    seen.add(key)
                    found.append(item)
    return found


def count_raw_files(paths: dict[str, str]) -> int:
    return len(_collect_raw_files(paths))


def raw_conversion_needed(paths: dict[str, str]) -> bool:
    """upload 中有 .raw 且 inputspace/outputspace 中未覆盖全部 raw 文件名时返回 True。"""
    raw_files = _collect_raw_files(paths)
    if not raw_files:
        return False
    available = mzml_stems(paths, paths["upload"])
    raw_stems = {p.stem.lower() for p in raw_files}
    return not raw_stems.issubset(available)


def ensure_raw_conversion_step(
    tasks: list[str],
    paths: dict[str, str],
    convert_tool: str,
) -> list[str]:
    """若存在未转换的 .raw，在计划开头插入格式转换步骤。"""
    if not raw_conversion_needed(paths):
        return [str(t) for t in tasks]

    from web_frontend.backend.raw_converter import build_conversion_plan_step

    convert_step = build_conversion_plan_step(paths, convert_tool)

    filtered: list[str] = []
    for task in tasks:
        text = str(task)
        lower = text.lower()
        if any(name.lower() in lower for name in RAW_CONVERTER_NAMES):
            continue
        filtered.append(text)
    return [convert_step, *filtered]


def normalize_plan_tasks_for_platform(tasks: list) -> list[str]:
    """按平台修正计划中的 raw 转换工具名称。"""
    try:
        from src.platform_utils import normalize_plan_tasks_for_platform as _norm

        return _norm(tasks)
    except Exception:
        return [str(t) for t in tasks]


def raw_conversion_complete(paths: dict[str, str]) -> bool:
    """upload 中无 .raw，或 converted_mzml 已覆盖全部 raw 文件名。"""
    return not raw_conversion_needed(paths)


def _rewrite_plan_tool_aliases(task: str) -> str:
    """把 LLM 编造的 plot_merge 等改写成已注册工具名。"""
    import re

    from web_frontend.backend.tool_registry import LOCAL_TOOL_ALIASES

    text = str(task)
    for alias, real in sorted(LOCAL_TOOL_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        text = re.sub(rf"\b{re.escape(alias)}\b", real, text, flags=re.IGNORECASE)
    # 幻觉输出目录
    text = re.sub(r"\bmerged_plots\b", "merged_figures", text, flags=re.IGNORECASE)
    return text


def filter_plan_tasks_to_registered_tools(
    tasks: list,
    tool_names: list[str] | None = None,
) -> list[str]:
    from web_frontend.backend.tool_registry import LOCAL_TOOL_ALIASES

    names = list(tool_names or ALL_AGENT_TOOL_NAMES)
    alias_names = set(LOCAL_TOOL_ALIASES.keys())
    if not names:
        return [_rewrite_plan_tool_aliases(t) for t in tasks]

    kept: list[str] = []
    for task in tasks:
        text = _rewrite_plan_tool_aliases(str(task).strip())
        if not text.lower().startswith("use "):
            continue
        lower = text.lower()
        if any(name.lower() in lower for name in names) or any(
            alias.lower() in lower for alias in alias_names
        ):
            kept.append(text)
    if kept:
        return kept
    return [
        _rewrite_plan_tool_aliases(t)
        for t in tasks
        if str(t).strip().lower().startswith("use ")
    ]


def guess_tool_name_from_task(task: str, allowed: frozenset[str] | set[str]) -> str | None:
    """从计划步骤文本中猜测工具名（LLM 匹配失败时的兜底）。"""
    import re

    from web_frontend.backend.tool_registry import normalize_agent_tool_name

    text = _rewrite_plan_tool_aliases(task)
    m = re.search(r"Use\s+([a-zA-Z0-9_]+)", text, re.IGNORECASE)
    if m:
        name = normalize_agent_tool_name(m.group(1))
        if name in allowed:
            return name
    lower = text.lower()
    for name in sorted(allowed, key=len, reverse=True):
        if name.lower() in lower:
            return name
    return None


def inject_mgf_standalone_tasks(
    tasks: list[str],
    user_message: str,
    paths: dict[str, str],
    tool_names: list[str] | None = None,
) -> list[str]:
    """LLM 计划被差异物裁剪为空时，根据用户意图与 upload 中的 .mgf 补一步。"""
    if tasks:
        return tasks
    upload = Path(paths.get("upload") or "")
    mgf_path = find_session_mgf(paths, str(upload))
    if not mgf_path:
        return tasks

    names = set(tool_names or ALL_AGENT_TOOL_NAMES)
    lower = (user_message or "").lower()
    out: list[str] = []
    deepmass_dir = paths.get("deepmass") or str(
        Path(paths["outputspace"]) / "deepmass_annotation_results"
    )
    network_dir = paths.get("molecular_network") or str(
        Path(paths["outputspace"]) / "molecular_network_results"
    )
    mgf_hint = mgf_path

    if "deepmass" in lower and "deepmass_annotation" in names:
        out.append(
            f"Use deepmass_annotation to perform deep learning annotation with "
            f"input_dir {deepmass_dir} and output_dir {deepmass_dir}."
        )
    if any(
        k in lower
        for k in (
            "分子网络",
            "molecular network",
            "networking",
            "gnps",
            "fbmn",
            "ms2lda",
            "molnetenhancer",
        )
    ):
        preferred = "molecular_networking_gnps"
        # 化学类/拓扑着色通常需要 MolNetEnhancer 节点类别
        chem_color = any(
            k in lower
            for k in (
                "化学类",
                "化学类别",
                "chemical_category",
                "chemical class",
                "按化学",
                "molnetenhancer",
                "molnet",
            )
        )
        topology_color = ("拓扑" in lower or "topology" in lower) and (
            "着色" in lower or "color" in lower or chem_color
        )
        if "fbmn" in lower and "molecular_networking_fbmn" in names:
            preferred = "molecular_networking_fbmn"
        elif "ms2lda" in lower and "molecular_networking_ms2lda" in names:
            preferred = "molecular_networking_ms2lda"
        elif (chem_color or topology_color) and (
            "molecular_networking_molnetenhancer" in names
        ):
            preferred = "molecular_networking_molnetenhancer"
        elif ("molnetenhancer" in lower or "molnet" in lower) and (
            "molecular_networking_molnetenhancer" in names
        ):
            preferred = "molecular_networking_molnetenhancer"
        if preferred in names:
            method = preferred.replace("molecular_networking_", "")
            out_dir = (
                f"{paths['outputspace']}/molecular_network_results/{method}"
            )
            mgf_path = mgf_hint or f"{paths['outputspace']}/peak_detection_results/spectra.mgf"
            out.append(
                f"Use {preferred} to build molecular network from "
                f"input_mgf {mgf_path} and output_dir {out_dir}."
            )
    return out or tasks


def inject_visual_standalone_tasks(
    tasks: list[str],
    user_message: str,
    tool_names: list[str] | None = None,
) -> list[str]:
    """计划被裁空或未含 visual 工具时，按用户意图补 plot_edit / image_merge / merge_edit。"""
    from web_frontend.backend.image_merge_registry import (
        looks_like_image_merge_request,
        looks_like_merged_figure_edit_request,
    )
    from web_frontend.backend.plot_edit_registry import looks_like_plot_edit_request

    names = set(tool_names or ALL_AGENT_TOOL_NAMES)
    text = (user_message or "").strip()
    if not text:
        return tasks

    lower_tasks = " ".join(tasks).lower()
    out = list(tasks)

    # 改拼图优先于新建拼图
    if looks_like_merged_figure_edit_request(text) and "merge_edit" in names:
        if "merge_edit" not in lower_tasks:
            out.append(
                f"Use merge_edit to adjust the merged figure layout/labels per: {text[:200]}"
            )
        return out

    if looks_like_image_merge_request(text) and "image_merge" in names:
        if "image_merge" not in lower_tasks and "merge_edit" not in lower_tasks:
            out.append(
                f"Use image_merge to merge session plots into one figure per: {text[:200]}"
            )
        # 分析+拼图：不要再补分析意图类 plot_edit
        return out

    # 仅当计划里还没有分析出图工具时，才把「改图/着色」补成独立 plot_edit
    has_analysis_plot_tool = any(
        key in lower_tasks or key in " ".join(out).lower()
        for key in (
            "statistical_analysis_mixomics",
            "mixomics",
            "molecular_networking",
            "kegg_compound_enrichment",
        )
    )
    if has_analysis_plot_tool:
        return out

    if looks_like_plot_edit_request(text) and "plot_edit" in names:
        if "plot_edit" not in lower_tasks:
            out.append(
                f"Use plot_edit to re-render the plot with style changes per: {text[:200]}"
            )
        return out

    return out


def _is_analysis_intent_plot_edit_task(task: str) -> bool:
    """判断是否为「分析意图着色/阈值/通道」类 plot_edit（应交给运行时确定性重绘）。"""
    text = str(task)
    lower = text.lower()
    if "plot_edit" not in lower:
        return False
    # 拼图相关不是这类
    if "image_merge" in lower or "merge_edit" in lower:
        return False
    intent_markers = (
        "color_by",
        "cluster",
        "recolor",
        "thresholds",
        "color_channel",
        "top_n",
        "着色",
        "chemical_category",
        "chemical class",
        "化学类",
        "log2fc",
        "|fc|",
        "p<",
        "p <",
        "by count",
        "按 count",
        "neglog10",
        "kmeans",
        "k-means",
        "按 group",
        "按 batch",
        "按时间",
    )
    return any(m in lower or m in text for m in intent_markers)


def inject_analysis_coloring_tasks(
    tasks: list[str],
    user_message: str,
    tool_names: list[str] | None = None,
    *,
    metadata_csv: str | None = None,
    metadata_columns: list[str] | None = None,
) -> tuple[list[str], dict]:
    """裁掉分析意图类 plot_edit，并按结构化意图裁剪旁支分析步骤。

    返回 (tasks, info)，info 含：
      intent / removed_plot_edits / removed_by_intent
    """
    del tool_names  # 兼容旧调用签名
    info: dict = {
        "intent": {},
        "removed_plot_edits": [],
        "removed_by_intent": [],
    }
    if not tasks:
        return tasks, info

    from web_frontend.backend.analysis_intent import (
        build_analysis_intent,
        prune_plan_tasks_by_intent,
    )

    intent = build_analysis_intent(
        user_message or "",
        metadata_columns=metadata_columns,
        metadata_csv=metadata_csv,
    )
    info["intent"] = intent or {}

    lower_joined = " ".join(str(t) for t in tasks).lower()
    has_plot_tool = any(
        key in lower_joined
        for key in (
            "statistical_analysis_mixomics",
            "mixomics",
            "molecular_networking",
            "kegg_compound_enrichment",
        )
    )
    working = list(tasks)
    if has_plot_tool:
        kept_plots: list[str] = []
        removed_plots: list[str] = []
        for t in working:
            if _is_analysis_intent_plot_edit_task(t):
                removed_plots.append(t)
            else:
                kept_plots.append(t)
        working = kept_plots
        info["removed_plot_edits"] = removed_plots

    if intent:
        working, removed_intent = prune_plan_tasks_by_intent(working, intent)
        info["removed_by_intent"] = removed_intent

    return working, info
