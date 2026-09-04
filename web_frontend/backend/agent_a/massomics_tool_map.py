"""MassOmics 规划工具名 → Web MCP 工具名映射（供 Agent B 本地执行）。"""
from __future__ import annotations

import re
from typing import Any

# MassOmics tools/ 目录名或 Planner 常用别名 → web_frontend ALLOWED 工具
MASSOMICS_TO_WEB: dict[str, str] = {
    "xcms": "data_preprocessing_xcms",
    "xcms_cli": "data_preprocessing_xcms",
    "mzmine": "data_preprocessing_mzmine",
    "ms-dial": "data_preprocessing_mzmine",
    "msdial": "data_preprocessing_mzmine",
    "openms": "data_preprocessing_openms",
    "mixomics": "statistical_analysis_mixomics",
    "ropls": "statistical_analysis_mixomics",
    "opls": "statistical_analysis_mixomics",
    "simca": "statistical_analysis_mixomics",
    "metaboanalyst": "statistical_analysis_mixomics",
    "knn": "feature_filtering_and_missing_value_imputation_knn",
    "imputation": "feature_filtering_and_missing_value_imputation_knn",
    "feature_filter": "feature_filtering_and_missing_value_imputation_knn",
    "gnps": "molecular_networking_gnps",
    "fbmn": "molecular_networking_fbmn",
    "ms2lda": "molecular_networking_ms2lda",
    "kegg": "kegg_compound_enrichment",
    "deepmass": "deepmass_annotation",
    "thermorawfileparser": "convert_raw_to_mzml_ThermoRawFileParser",
    "msconvert": "convert_raw_to_mzml_msconvert",
    "proteowizard": "convert_raw_to_mzml_msconvert",
    "camera": "filter_redundant_features_camera",
}

_NORM = {re.sub(r"[^a-z0-9]+", "", k): v for k, v in MASSOMICS_TO_WEB.items()}


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def resolve_web_mcp_tool(name: str, registered: set[str]) -> str | None:
    """把 MassOmics 步骤里的工具名映射到 Web 已注册 MCP 名。"""
    raw = (name or "").strip()
    if not raw:
        return None
    if raw in registered:
        return raw
    candidates = [raw]
    first = raw.split()[0]
    if first != raw:
        candidates.append(first)
    for cand in candidates:
        key = _normalize(cand)
        if key in _NORM:
            mapped = _NORM[key]
            if mapped in registered:
                return mapped
        stripped = re.sub(r"\d+$", "", key)
        if stripped and stripped in _NORM:
            mapped = _NORM[stripped]
            if mapped in registered:
                return mapped
    key = _normalize(raw)
    if key in _NORM:
        mapped = _NORM[key]
        if mapped in registered:
            return mapped
    for reg in registered:
        rn = _normalize(reg)
        if key == rn or (key and (key in rn or rn in key)):
            return reg
    return None


def _abs_path(base: str, fragment: str) -> str:
    frag = (fragment or "").strip().strip("`")
    if not frag or frag in {"-", "—"}:
        return base
    if frag.startswith("/"):
        return frag
    return f"{base.rstrip('/')}/{frag.lstrip('/')}"


def _vip_from_text(text: str) -> str | None:
    t = text or ""
    m = re.search(r"vip_threshold\s*[=:]\s*([0-9.]+)", t, re.I)
    if m:
        return m.group(1)
    m = re.search(r"VIP\s*>\s*([0-9.]+)", t, re.I)
    if m:
        return m.group(1)
    return None


def step_to_executable_task(
    step: dict[str, Any],
    *,
    paths: dict[str, str],
    registered: set[str],
) -> str | None:
    """MassOmics PlanStep → Web B 可执行的 ``Use <tool> to ...`` 字符串。"""
    tools = step.get("tools") or []
    if isinstance(tools, str):
        tools = [t.strip() for t in tools.split(",") if t.strip()]
    web_tool = None
    for t in tools:
        web_tool = resolve_web_mcp_tool(str(t), registered)
        if web_tool:
            break
    if not web_tool:
        # 从描述里猜工具
        desc_low = str(step.get("description") or "").lower()
        for hint, mapped in MASSOMICS_TO_WEB.items():
            if hint in desc_low and mapped in registered:
                web_tool = mapped
                break
    if not web_tool:
        return None

    desc = str(step.get("description") or step.get("task") or "run analysis step").strip()
    upload = paths.get("upload") or paths.get("inputspace") or "."
    output = paths.get("outputspace") or "."
    inp = _abs_path(upload, str(step.get("input_filename") or ""))
    out = _abs_path(output, str(step.get("output_filename") or ""))

    if web_tool.startswith("convert_raw"):
        return (
            f"Use {web_tool} to convert .raw files in {inp} to mzML format in {out}"
        )
    if web_tool == "data_preprocessing_xcms":
        return (
            f"Use {web_tool} to process mzML files from {inp} "
            f"to generate feature table in {out}"
        )
    if web_tool == "feature_filtering_and_missing_value_imputation_knn":
        return (
            f"Use {web_tool} to filter low-prevalence features and impute missing values "
            f"in {inp}, output to {out}"
        )
    if web_tool == "statistical_analysis_mixomics":
        meta = _abs_path(upload, "metadata.csv")
        vip = _vip_from_text(desc)
        vip_part = f", vip_threshold={vip}" if vip else ""
        return (
            f"Use {web_tool} to perform PCA and differential analysis using metadata.csv "
            f"from {meta}, input_dir={inp}, output_dir={out}, group_column=Group{vip_part}"
        )
    return f"Use {web_tool} to {desc} input={inp} output={out}"


def plan_document_to_tasks(
    plan: dict[str, Any],
    *,
    paths: dict[str, str],
    registered: set[str],
) -> list[str]:
    tasks: list[str] = []
    for step in plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        task = step_to_executable_task(step, paths=paths, registered=registered)
        if task and task not in tasks:
            tasks.append(task)
    return tasks


__all__ = [
    "MASSOMICS_TO_WEB",
    "resolve_web_mcp_tool",
    "step_to_executable_task",
    "plan_document_to_tasks",
]
