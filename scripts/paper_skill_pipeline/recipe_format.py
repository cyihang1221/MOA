"""将结构化 recipe dict 渲染为 softwares_database/repro_recipes 文本格式。"""
from __future__ import annotations

import re
from typing import Any


def doi_to_stem(doi: str) -> str:
    s = (doi or "").strip()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s, flags=re.I)
    s = s.replace("/", "_").replace(" ", "_")
    s = re.sub(r"[^0-9A-Za-z._\-]+", "_", s)
    return s[:120] or "unknown"


def _kv_block(obj: dict[str, Any] | None, indent: int = 2) -> list[str]:
    if not isinstance(obj, dict):
        return []
    pad = " " * indent
    lines = []
    for k, v in obj.items():
        if v is None:
            continue
        lines.append(f"{pad}{k}: {v}")
    return lines


def render_recipe(data: dict[str, Any]) -> str:
    """渲染单条 reproducibility_recipe entry。"""
    lines: list[str] = [
        "========== reproducibility_recipe entry ==========",
        f"paper_title: {data.get('paper_title') or 'Untitled'}",
        f"source_paper: {data.get('source_paper') or ''}",
        f"overall_reproducibility_score: {int(data.get('overall_reproducibility_score') or 0)}/100",
        "",
    ]

    steps = data.get("workflow_steps") or []
    if not isinstance(steps, list):
        steps = []
    lines.append(f"workflow_steps: {len(steps)}")
    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            continue
        title = step.get("title") or step.get("task") or f"Step {i}"
        lines.append(f"  Step {i}: {title}")
        for key in ("tool", "algorithm", "parameters", "input", "output", "confidence"):
            val = step.get(key)
            if val is None or str(val).strip() == "":
                continue
            # 统一 input/output 字段名
            out_key = key
            lines.append(f"    {out_key}: {val}")
    lines.append("")

    da = data.get("data_availability")
    if isinstance(da, dict):
        lines.append("data_availability:")
        lines.extend(_kv_block(da, indent=2))
    elif da:
        lines.append(f"data_availability: {da}")
    else:
        lines.append("data_availability:")
        lines.append("  raw_data: not_mentioned")
        lines.append("  processed_data: not_mentioned")
        lines.append("  metadata: not_mentioned")
    lines.append("")

    ca = data.get("code_availability")
    if isinstance(ca, dict):
        lines.append(f"code_availability: {ca.get('status') or ca.get('code_availability') or 'not_mentioned'}")
        lines.extend(_kv_block({k: v for k, v in ca.items() if k not in {"status", "code_availability"}}, 2))
    elif ca:
        lines.append(f"code_availability: {ca}")
    else:
        lines.append("code_availability: not_mentioned")
    lines.append("")

    figs = data.get("figure_recipes") or data.get("figures") or []
    if not isinstance(figs, list):
        figs = []
    lines.append(f"figure_recipes: {len(figs)}")
    for i, fig in enumerate(figs, 1):
        if not isinstance(fig, dict):
            continue
        name = fig.get("name") or f"Figure {i}"
        ftype = fig.get("type") or fig.get("fig_type") or "other"
        if not str(name).lower().startswith("fig"):
            name = f"Figure {i}"
        lines.append(f"  {name}: [{ftype}]")
        for key in (
            "caption",
            "produced_by_step",
            "visualization_tool",
            "statistical_test",
        ):
            val = fig.get(key)
            if val is None or str(val).strip() == "":
                continue
            lines.append(f"    {key}: {val}")
    lines.append("")

    gaps = data.get("reproducibility_gaps") or []
    lines.append("reproducibility_gaps:")
    if isinstance(gaps, list) and gaps:
        for g in gaps:
            lines.append(f"  - {g}")
    else:
        lines.append("  - not_assessed")
    lines.append("")

    strengths = data.get("reproducibility_strengths") or []
    lines.append("reproducibility_strengths:")
    if isinstance(strengths, list) and strengths:
        for s in strengths:
            lines.append(f"  - {s}")
    else:
        lines.append("  - not_assessed")
    lines.append("")
    return "\n".join(lines)


def recipe_has_explicit_params(data: dict[str, Any]) -> bool:
    for step in data.get("workflow_steps") or []:
        if not isinstance(step, dict):
            continue
        params = str(step.get("parameters") or "").strip().lower()
        if params and params not in {"not_reported", "not_mentioned", "none", "n/a", "-"}:
            # 至少像 key=value
            if "=" in params or ":" in params:
                return True
    return False
