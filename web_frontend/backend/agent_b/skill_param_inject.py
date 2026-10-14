"""把文献 Skill / 论文 recipe 参数写进 PlanDocument.tool_parameters。

在 Agent B 子进程里运行（PYTHONPATH 只有 complete 同根 + 本目录），
因此只用标准库，不 import web_frontend。
师兄 executor / mixOmics 实现不改：只填 adapter 已经认的 tool_parameters。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SIDECAR_NAME = "skill_parameters.json"

_STATS_KEYWORDS = frozenset(
    {"mixomics", "simca", "metax", "ropls", "opls", "statisticalanalysismixomics"}
)
_XCMS_KEYWORDS = frozenset({"xcms", "xcmscentwave", "datapreprocessingxcms"})
_MZMINE_KEYWORDS = frozenset(
    {"mzmine", "mzminepipeline", "mzmineadap", "datapreprocessingmzmine"}
)
_SIMCA_KEYWORDS = frozenset({"simca", "statisticalanalysissimca"})

_SCALE_UV = frozenset({"uv", "unitvariance", "unit variance", "standard", "autoscale"})


def fold_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def parse_skill_parameters(text: str) -> dict[str, Any]:
    """从 Skill Markdown / 步骤描述 / recipe 文本抽出可进 B 的参数。"""
    blob = text or ""
    out: dict[str, Any] = {}
    m = re.search(r"vip_threshold\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)", blob, re.I)
    if not m:
        m = re.search(r"VIP\s*[>≥]\s*([0-9]+(?:\.[0-9]+)?)", blob, re.I)
    if m:
        out["vip_threshold"] = float(m.group(1))
    m = re.search(r"plsda_permutation_n\s*[=:]\s*([0-9]+)", blob, re.I)
    if not m:
        m = re.search(r"n_permutations\s*[=:]\s*([0-9]+)", blob, re.I)
    if not m:
        m = re.search(r"([0-9]{2,4})\s*(?:次)?\s*置换", blob)
    if m:
        out["n_permutations"] = int(m.group(1))
    m = re.search(r"pca_scaling\s*[=:]\s*([A-Za-z_]+)", blob, re.I)
    if not m:
        m = re.search(r"\bUV[-\s]?scaling\b", blob, re.I)
        if m:
            out["scale_method"] = "autoscale"
    else:
        raw = m.group(1).strip().lower()
        if fold_name(raw) in {fold_name(x) for x in _SCALE_UV} or raw in _SCALE_UV:
            out["scale_method"] = "autoscale"
        elif raw in {"none", "center"}:
            out["scale_method"] = "none"
    m = re.search(r"\bppm\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)", blob, re.I)
    if m:
        out["ppm"] = float(m.group(1))
    prefer = _prefer_preprocess(blob)
    if prefer:
        out["prefer_preprocess"] = prefer
    return out


def _prefer_preprocess(blob: str) -> str:
    low = blob.lower()
    mz = bool(re.search(r"\bmzmine\b", low))
    xc = bool(re.search(r"\bxcms\b", low))
    if mz and not xc:
        return "mzmine"
    if xc and not mz:
        return "xcms"
    if mz and xc:
        # 论文 Methods 常同时出现；点名 MZmine 预处理时优先 MZmine
        if re.search(r"mzmine.{0,40}(preprocess|预处理|feature)", low, re.I):
            return "mzmine"
        return ""
    return ""


def load_sidecar(paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        if not path or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def merge_param_dicts(*parts: dict[str, Any]) -> dict[str, Any]:
    """后面的覆盖前面的；空值忽略。"""
    out: dict[str, Any] = {}
    for part in parts:
        for key, value in (part or {}).items():
            if value is None or value == "":
                continue
            out[key] = value
    return out


def _step_blob(step: dict[str, Any]) -> str:
    bits = [
        str(step.get("description") or ""),
        str(step.get("task") or ""),
        str(step.get("expected_output") or ""),
        json.dumps(step.get("tool_parameters") or {}, ensure_ascii=False),
    ]
    return "\n".join(bits)


def _is_stats_step(keywords: list[str]) -> bool:
    return any(fold_name(k) in _STATS_KEYWORDS or "mixomic" in fold_name(k) for k in keywords)


def _is_xcms_step(keywords: list[str]) -> bool:
    return any(fold_name(k) in _XCMS_KEYWORDS for k in keywords)


def _is_mzmine_step(keywords: list[str]) -> bool:
    return any(fold_name(k) in _MZMINE_KEYWORDS for k in keywords)


def _is_simca_step(keywords: list[str]) -> bool:
    return any(fold_name(k) in _SIMCA_KEYWORDS for k in keywords)


def _ensure_params(step: dict[str, Any], tool_key: str) -> dict[str, Any]:
    bag = step.setdefault("tool_parameters", {})
    if not isinstance(bag, dict):
        bag = {}
        step["tool_parameters"] = bag
    slot = bag.get(tool_key)
    if not isinstance(slot, dict):
        slot = {}
        bag[tool_key] = slot
    return slot


def _setdefault_numeric(slot: dict[str, Any], key: str, value: Any) -> bool:
    if value is None or key in slot:
        return False
    slot[key] = value
    return True


def resolve_mzmine_entry(catalog: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from plan_normalize import resolve_catalog_entry
    except ImportError:
        from web_frontend.backend.agent_b.plan_normalize import resolve_catalog_entry

    for name in (
        "data_preprocessing_mzmine",
        "MZMine-Pipeline",
        "MZmine-ADAP",
        "MZmine",
        "mzmine",
    ):
        hit = resolve_catalog_entry(name, catalog)
        if hit:
            return hit
    return None


def apply_skill_parameters(
    plan: dict[str, Any],
    catalog: dict[str, Any],
    *,
    sidecar: dict[str, Any] | None = None,
    sidecar_paths: list[Path] | None = None,
) -> list[str]:
    """就地写入 tool_parameters；已有键不覆盖。返回警告。"""
    warnings: list[str] = []
    loaded = dict(sidecar or {})
    if sidecar_paths:
        loaded = merge_param_dicts(load_sidecar(sidecar_paths), loaded)
    goal_blob = "\n".join(
        str(plan.get(k) or "") for k in ("goal", "objective", "data_understanding")
    )
    global_params = merge_param_dicts(parse_skill_parameters(goal_blob), loaded)

    rewrite = bool(global_params.get("rewrite_preprocess"))
    prefer = str(global_params.get("prefer_preprocess") or "").strip().lower()
    mzmine_entry = resolve_mzmine_entry(catalog) if prefer == "mzmine" else None

    applied: list[dict[str, Any]] = []
    for step in plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        tools = [str(t) for t in (step.get("tools") or []) if str(t).strip()]
        if not tools:
            continue
        local = merge_param_dicts(global_params, parse_skill_parameters(_step_blob(step)))
        if rewrite and prefer == "mzmine" and _is_xcms_step(tools) and not _is_mzmine_step(tools):
            if mzmine_entry:
                old = list(tools)
                tools = [str(mzmine_entry["keyword"])]
                step["tools"] = tools
                bag = step.setdefault("tool_parameters", {})
                if isinstance(bag, dict):
                    for prev in old:
                        slot = bag.get(prev)
                        if isinstance(slot, dict) and tools[0] not in bag:
                            bag[tools[0]] = dict(slot)
                if mzmine_entry.get("stage"):
                    step["stage"] = str(mzmine_entry["stage"])
                warnings.append(
                    f"步骤 {step.get('step_number')} 预处理按论文/Skill 从 {old} 改为 {tools}"
                )
                applied.append(
                    {
                        "step": step.get("step_number"),
                        "action": "rewrite_preprocess",
                        "from": old,
                        "to": tools,
                    }
                )
            else:
                step.setdefault("software_substitution", {})
                if isinstance(step["software_substitution"], dict):
                    step["software_substitution"]["requested"] = "MZmine"
                    step["software_substitution"]["actual"] = tools[0]
                warnings.append(
                    f"步骤 {step.get('step_number')} 论文要 MZmine，catalog 无可用条目，仍用 {tools}"
                )
                applied.append(
                    {
                        "step": step.get("step_number"),
                        "action": "software_substitution",
                        "requested": "MZmine",
                        "actual": tools,
                    }
                )

        primary = tools[0]
        slot = _ensure_params(step, primary)
        # 同步挂到 MCP 名，adapter 两种 key 都能取到
        mcp_name = ""
        try:
            try:
                from plan_normalize import resolve_catalog_entry
            except ImportError:
                from web_frontend.backend.agent_b.plan_normalize import resolve_catalog_entry

            entry = resolve_catalog_entry(primary, catalog)
            if entry:
                mcps = entry.get("mcp_tools") or []
                if mcps:
                    mcp_name = str(mcps[0])
        except Exception:
            mcp_name = ""

        changed: dict[str, Any] = {}
        if _is_stats_step(tools):
            if _setdefault_numeric(slot, "vip_threshold", local.get("vip_threshold")):
                changed["vip_threshold"] = slot["vip_threshold"]
            if local.get("scale_method") and "scale_method" not in slot:
                slot["scale_method"] = local["scale_method"]
                changed["scale_method"] = slot["scale_method"]
            if _is_simca_step(tools) and _setdefault_numeric(
                slot, "n_permutations", local.get("n_permutations")
            ):
                changed["n_permutations"] = slot["n_permutations"]
        if _is_xcms_step(tools) and _setdefault_numeric(slot, "ppm", local.get("ppm")):
            changed["ppm"] = slot["ppm"]
        if mcp_name and changed:
            mcp_slot = _ensure_params(step, mcp_name)
            for key, val in changed.items():
                mcp_slot.setdefault(key, val)
        if changed:
            applied.append({"step": step.get("step_number"), "tool": primary, "params": changed})

    plan["_injected_skill_parameters"] = {
        "source": loaded.get("source") or [],
        "values": {k: global_params[k] for k in global_params if k != "source"},
        "applied": applied,
    }
    return warnings


def write_sidecar(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


__all__ = [
    "SIDECAR_NAME",
    "apply_skill_parameters",
    "fold_name",
    "load_sidecar",
    "merge_param_dicts",
    "parse_skill_parameters",
    "write_sidecar",
]
