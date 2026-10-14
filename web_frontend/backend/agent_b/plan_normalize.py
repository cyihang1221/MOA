"""把 Agent A（complete PlanDocument）的步骤工具名对齐到 B 的 tool_catalog。

A 的 schema 没有强制 ``stage``，工具名也常是 ``xcms`` / ``mixomics``；
B 的 ``adapt_massomics_plan`` 要求 catalog 内的 stage + keyword。
此模块只改交接 JSON，不把 A/B 合成一个 Agent。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_FOLD = re.compile(r"[^a-z0-9]+")

# 规划侧常用别名 → B catalog canonical keyword
EXTRA_ALIASES: dict[str, str] = {
    "xcms": "XCMS-Centwave",
    "xcmscentwave": "XCMS-Centwave",
    "xcmscli": "XCMS-Centwave",
    "mixomics": "mixOmics",
    "ropls": "mixOmics",
    "opls": "mixOmics",
    "knn": "kNN",
    "imputation": "kNN",
    "featurefilter": "kNN",
    "kegg": "KEGG",
    "gnps": "GNPS",
    "fbmn": "FBMN",
    "ms2lda": "MS2LDA",
    "deepmass": "DeepMASS",
    "msconvert": "msconvert",
    "proteowizard": "ProteoWizard",
    "thermorawfileparser": "ThermoRawFileParser",
    "camera": "CAMERA",
    "sirius": "SIRIUS",
    "molnetenhancer": "MolNetEnhancer",
    "mzmine": "MZMine-Pipeline",
    "mzminepipeline": "MZMine-Pipeline",
    "mzmineadap": "MZmine-ADAP",
}

_IMPUTE_KEYWORDS = frozenset({"kNN", "MissForest", "Bayesian PCA"})
_STATS_KEYWORDS = frozenset(
    {"mixOmics", "metaX", "scikit-learn", "SIMCA", "DeepLearning-based"}
)


def fold_name(name: str) -> str:
    return _FOLD.sub("", (name or "").lower())


def load_tool_catalog(path: str | Path) -> dict[str, Any]:
    catalog_path = Path(path)
    text = catalog_path.read_text(encoding="utf-8")
    if text.startswith("version https://git-lfs.github.com/spec/v1"):
        raise ValueError(
            f"tool_catalog.json 仍是 Git LFS 指针（未 smudge）：{catalog_path}。"
            "请执行 git lfs pull --include='src/tool_catalog.json'"
        )
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("tools"), list):
        raise ValueError(f"无效的 tool_catalog: {catalog_path}")
    return data


def _index_catalog(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    tools = catalog.get("tools") or []
    return [t for t in tools if isinstance(t, dict)]


def resolve_catalog_entry(
    name: str,
    catalog: dict[str, Any],
    *,
    stage_hint: str = "",
) -> dict[str, Any] | None:
    """按 keyword / alias / MCP 工具名 / 额外别名解析 catalog 条目。"""
    raw = (name or "").strip()
    if not raw:
        return None
    entries = _index_catalog(catalog)
    stage_hint = (stage_hint or "").strip()

    def _in_stage(entry: dict[str, Any]) -> bool:
        return not stage_hint or str(entry.get("stage") or "") == stage_hint

    folded = fold_name(raw)
    extra_kw = EXTRA_ALIASES.get(folded)
    if extra_kw is None:
        if "thermoraw" in folded or "msconvert" in folded or "proteowizard" in folded:
            extra_kw = "ThermoRawFileParser"

    exact: list[dict[str, Any]] = []
    alias_hits: list[dict[str, Any]] = []
    mcp_hits: list[dict[str, Any]] = []
    extra_hits: list[dict[str, Any]] = []
    for entry in entries:
        if not _in_stage(entry):
            continue
        keyword = str(entry.get("keyword") or "")
        aliases = [str(a) for a in (entry.get("aliases") or []) if str(a).strip()]
        mcp_tools = [str(t) for t in (entry.get("mcp_tools") or []) if str(t).strip()]
        if keyword == raw or fold_name(keyword) == folded:
            exact.append(entry)
            continue
        if raw in aliases or fold_name(raw) in {fold_name(a) for a in aliases}:
            alias_hits.append(entry)
            continue
        if raw in mcp_tools or folded in {fold_name(t) for t in mcp_tools}:
            mcp_hits.append(entry)
            continue
        if extra_kw and (keyword == extra_kw or fold_name(keyword) == fold_name(extra_kw)):
            extra_hits.append(entry)

    for group in (exact, alias_hits, extra_hits, mcp_hits):
        supported = [e for e in group if e.get("support_status") == "supported"]
        chosen = supported or group
        if len(chosen) == 1:
            return chosen[0]
        if len(chosen) > 1:
            return chosen[0]
    return None


def normalize_plan_for_b(
    document: dict[str, Any],
    catalog: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """返回可交给 ``adapt_massomics_plan`` 的 PlanDocument，以及警告。"""
    if not isinstance(document, dict):
        raise ValueError("计划必须是对象")
    warnings: list[str] = []
    steps_in = document.get("steps") or []
    if not isinstance(steps_in, list) or not steps_in:
        raise ValueError("MassOmics 计划为空：没有可执行步骤")

    out_steps: list[dict[str, Any]] = []
    for index, raw in enumerate(steps_in):
        if not isinstance(raw, dict):
            raise ValueError(f"步骤 {index + 1} 必须是对象")
        step_number = int(raw.get("step_number") or index + 1)
        tools_raw = raw.get("tools") or []
        if isinstance(tools_raw, str):
            tools_raw = [part.strip() for part in tools_raw.split(",") if part.strip()]
        if not isinstance(tools_raw, list):
            tools_raw = []

        stage_hint = str(raw.get("stage") or "").strip()
        mapped: list[str] = []
        mapped_entries: list[dict[str, Any]] = []
        requested: list[str] = []
        resolved_stage = stage_hint
        for tool in tools_raw:
            entry = resolve_catalog_entry(str(tool), catalog, stage_hint=stage_hint)
            if entry is None:
                warnings.append(f"步骤 {step_number} 工具 {tool!r} 不在 B 的 tool_catalog，已跳过")
                continue
            mapped.append(str(entry["keyword"]))
            mapped_entries.append(entry)
            requested.append(str(tool))
            if not resolved_stage:
                resolved_stage = str(entry.get("stage") or "")

        if not mapped:
            warnings.append(f"步骤 {step_number} 没有可映射到 B 的工具，整步跳过")
            continue
        if not resolved_stage:
            warnings.append(f"步骤 {step_number} 缺少 stage，且无法从工具名推断")

        mode = str(raw.get("mode") or "sequential").strip() or "sequential"
        remapped_params = _remap_tool_parameters(
            raw.get("tool_parameters") or {},
            requested,
            mapped,
            mapped_entries,
        )
        carried = {k: v for k, v in raw.items() if k not in {"tools", "stage", "mode", "tool_parameters"}}
        out_steps.append(
            {
                **carried,
                "step_number": step_number,
                "description": str(raw.get("description") or raw.get("task") or "").strip(),
                "tools": mapped,
                "stage": resolved_stage,
                "mode": mode,
                "tool_parameters": remapped_params,
            }
        )

    normalized = dict(document)
    normalized["steps"] = _ensure_imputation_before_stats(out_steps, catalog, warnings)
    _chain_step_filenames(normalized["steps"])
    return normalized, warnings


def _remap_tool_parameters(
    raw_params: Any,
    requested: list[str],
    mapped: list[str],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """把 A 写在 mixomics / MCP 名下的参数挂到 catalog keyword 上，避免 adapter 取不到。"""
    if not isinstance(raw_params, dict):
        return {}
    out: dict[str, Any] = {}
    for old, new, entry in zip(requested, mapped, entries):
        keys = [old, new, *(str(t) for t in (entry.get("mcp_tools") or []))]
        merged: dict[str, Any] = {}
        for key in keys:
            slot = raw_params.get(key)
            if isinstance(slot, dict):
                merged.update(slot)
        if merged:
            out[new] = dict(merged)
            for mcp in entry.get("mcp_tools") or []:
                out.setdefault(str(mcp), dict(merged))
    for key, slot in raw_params.items():
        if key in out or not isinstance(slot, dict):
            continue
        out[key] = dict(slot)
    return out


def _step_keywords(step: dict[str, Any]) -> list[str]:
    tools = step.get("tools") or []
    return [str(t) for t in tools]


def _ensure_imputation_before_stats(
    steps: list[dict[str, Any]],
    catalog: dict[str, Any],
    warnings: list[str],
) -> list[dict[str, Any]]:
    """mixOmics 硬编码 feature_table_filtered_imputed.csv；A 常跳过 kNN。"""
    first_stats: int | None = None
    has_impute_before = False
    for index, step in enumerate(steps):
        keys = set(_step_keywords(step))
        if keys & _IMPUTE_KEYWORDS and first_stats is None:
            has_impute_before = True
        if keys & _STATS_KEYWORDS and first_stats is None:
            first_stats = index
            break
    if first_stats is None or has_impute_before:
        return steps
    knn = resolve_catalog_entry("kNN", catalog)
    if knn is None:
        return steps
    insert = {
        "step_number": first_stats + 1,
        "description": "缺失值填补（自动补步：mixOmics 需要 feature_table_filtered_imputed.csv）",
        "tools": [str(knn["keyword"])],
        "stage": str(knn.get("stage") or "missing_value_imputation"),
        "mode": "sequential",
        "input_filename": "",
        "output_filename": "imputed_feature_table",
        "expected_output": "feature_table_filtered_imputed.csv",
    }
    out = list(steps)
    out.insert(first_stats, insert)
    for index, step in enumerate(out, start=1):
        step["step_number"] = index
    warnings.append("已在统计分析前自动插入 kNN 填补，避免把 XCMS/CAMERA 表直接交给 mixOmics")
    return out


def _chain_step_filenames(steps: list[dict[str, Any]]) -> None:
    """后一步的 input_filename 指向前一步逻辑产物名，供 B adapter 跨步衔接。"""
    previous_out = ""
    for index, step in enumerate(steps):
        out_name = str(step.get("output_filename") or "").strip()
        if not out_name:
            out_name = f"step_{step.get('step_number') or index + 1}_output"
            step["output_filename"] = out_name
        if index > 0 and previous_out:
            step["input_filename"] = previous_out
        previous_out = out_name.split(",")[0].strip()


__all__ = [
    "EXTRA_ALIASES",
    "fold_name",
    "load_tool_catalog",
    "normalize_plan_for_b",
    "resolve_catalog_entry",
]
