"""运行时图语义中间表示（VisualIR）。

不写回 Agent A 计划；仅包装 plot_config / merge meta，供文献证据与校验使用。
"""
from __future__ import annotations

from typing import Any


def figure_ir_from_config(
    *,
    plot_type: str,
    source_rel: str,
    plot_config: dict[str, Any],
    data_dir: str = "",
    goal_text: str = "",
) -> dict[str, Any]:
    return {
        "kind": "figure",
        "plot_type": plot_type,
        "source_rel": source_rel,
        "data_dir": data_dir,
        "goal_text": (goal_text or "")[:2000],
        "intent": {
            "title": plot_config.get("title") or "",
            "color_by": plot_config.get("color_by"),
            "cluster": plot_config.get("cluster"),
        },
        "style": {
            "palette": dict(plot_config.get("palette") or {}),
            "colors": dict(plot_config.get("colors") or {}),
            "font_size": dict(plot_config.get("font_size") or {}),
            "figure_size": list(plot_config.get("figure_size") or []),
            "title_align": plot_config.get("title_align"),
            "legend": dict(plot_config.get("legend") or {}),
            "axes": dict(plot_config.get("axes") or {}),
            "marks": dict(plot_config.get("marks") or {}),
        },
        "evidence_refs": [],
        "constraints": [],
    }


def merge_ir_from_meta(
    *,
    sources: list[str],
    options: dict[str, Any],
    goal_text: str = "",
) -> dict[str, Any]:
    label_mode = str(options.get("label_mode") or "upper")
    panels = []
    custom = options.get("custom_labels") or {}
    if not isinstance(custom, dict):
        custom = {}
    for i, rel in enumerate(sources):
        label = custom.get(str(i)) or custom.get(rel) or ""
        panels.append({"index": i, "source_rel": rel, "label": label})
    return {
        "kind": "merge",
        "goal_text": (goal_text or "")[:2000],
        "sources": list(sources),
        "layout": {
            "cols": options.get("cols"),
            "gap": options.get("gap"),
            "label_mode": label_mode,
            "label_font_size": options.get("label_font_size"),
        },
        "panels": panels,
        "evidence_refs": [],
        "panel_intent": [],
    }


def attach_evidence(ir: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any]:
    out = dict(ir)
    refs = []
    for c in cards:
        refs.append(
            {
                "evidence_id": c.get("evidence_id"),
                "skill_id": c.get("skill_id"),
                "doi": c.get("doi"),
                "claim_type": c.get("claim_type"),
                "field_hints": list(c.get("field_hints") or []),
                "quote": (c.get("quote") or "")[:300],
            }
        )
    out["evidence_refs"] = refs
    return out
