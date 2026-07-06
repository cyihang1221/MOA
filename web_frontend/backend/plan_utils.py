"""Web 端计划步骤过滤与平台相关修正。"""
from __future__ import annotations

from pathlib import Path

from web_frontend.backend.session_file_resolver import find_session_mgf, mzml_stems

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


def filter_plan_tasks_to_registered_tools(
    tasks: list,
    tool_names: list[str] | None = None,
) -> list[str]:
    names = list(tool_names or ALLOWED_TOOL_NAMES)
    if not names:
        return [str(t) for t in tasks]

    kept: list[str] = []
    for task in tasks:
        text = str(task).strip()
        if not text.lower().startswith("use "):
            continue
        lower = text.lower()
        if any(name.lower() in lower for name in names):
            kept.append(text)
    return kept if kept else [str(t) for t in tasks if str(t).strip().lower().startswith("use ")]


def guess_tool_name_from_task(task: str, allowed: frozenset[str] | set[str]) -> str | None:
    """从计划步骤文本中猜测工具名（LLM 匹配失败时的兜底）。"""
    import re

    m = re.search(r"Use\s+([a-zA-Z0-9_]+)", task, re.IGNORECASE)
    if m:
        name = m.group(1)
        if name in allowed:
            return name
    lower = task.lower()
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

    names = set(tool_names or ALLOWED_TOOL_NAMES)
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
    if any(k in lower for k in ("分子网络", "molecular network", "networking", "gnps")) and (
        "molecular_networking_gnps" in names
    ):
        mgf_path = mgf_hint or f"{paths['outputspace']}/peak_detection_results/spectra.mgf"
        out.append(
            f"Use molecular_networking_gnps to build molecular network from "
            f"input_mgf {mgf_path} and output_dir {network_dir}."
        )
    return out or tasks
