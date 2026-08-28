"""Figure card 三模块（E 数据支撑 / C 读图观察 / B 图意解读）统一构建。"""
from __future__ import annotations

from typing import Any

from web_frontend.backend.agent_c.figure_data_narrative import format_data_narrative_markdown
from web_frontend.backend.agent_c.figure_vision import format_vision_markdown, vision_enabled
from web_frontend.backend.agent_c.report_insights import format_figure_interpretation_block

ECB_LAYOUT_VERSION = 2
_COMPLETE_STATUSES = frozenset({"rendered", "copied_existing"})


def _plan_fields_from_figure(fig: dict[str, Any]) -> dict[str, str]:
    out = {
        "purpose": str(fig.get("purpose") or "").strip(),
        "theme": str(fig.get("theme") or "").strip(),
        "expected_observation": str(fig.get("expected_observation") or "").strip(),
    }
    if out["purpose"] and out["theme"]:
        return out
    for line in str(fig.get("caption") or "").splitlines():
        text = line.strip()
        if text.startswith("目的："):
            out["purpose"] = out["purpose"] or text[3:].strip()
        elif text.startswith("总体主题："):
            out["theme"] = out["theme"] or text[5:].strip()
        elif text.startswith("方案预期观察："):
            out["expected_observation"] = out["expected_observation"] or text[7:].strip()
    return out


def _plan_interpretation_fallback(fig: dict[str, Any], *, zh: bool) -> dict[str, Any]:
    fields = _plan_fields_from_figure(fig)
    purpose = fields["purpose"]
    theme = fields["theme"]
    expected = fields["expected_observation"]
    parts: list[str] = []
    if purpose:
        parts.append(f"{'方案目的' if zh else 'Planned purpose'}：{purpose}")
    if theme:
        parts.append(f"{'总体主题' if zh else 'Theme'}：{theme}")
    if expected:
        parts.append(f"{'方案预期观察' if zh else 'Planned observation'}：{expected}")
    if not parts:
        parts.append(
            "见本图图注中的方案要求与结果文件事实。"
            if zh
            else "See the caption for planned requirements and file facts."
        )
    what = "；".join(parts)
    link = theme or purpose or (
        "对应分析方案中该图的研究问题。" if zh else "Addresses the figure role in the analysis plan."
    )
    caveats = (
        "本节依据分析方案撰写，未启用 AI 图意解读；不把方案预期观察写成已证实结论。"
        if zh
        else "Plan-based notes only; planned observations are not stated as confirmed findings."
    )
    return {
        "what_it_shows": what,
        "link_to_objective": link,
        "caveats": caveats,
        "source": "plan",
    }


def _has_llm_interpretation(interp: dict[str, Any]) -> bool:
    return bool(
        str(interp.get("what_it_shows") or "").strip()
        or str(interp.get("link_to_objective") or interp.get("relation_to_goal") or "").strip()
        or str(interp.get("caveats") or "").strip()
    )


def build_ecb_blocks(
    fig: dict[str, Any],
    interpretation: dict[str, Any] | None = None,
    *,
    insights_enabled: bool = False,
    zh: bool = True,
) -> dict[str, Any]:
    """为已完成图构建固定的 E/C/B 三模块（缺失时用占位或方案 fallback）。"""
    status = str(fig.get("status") or "")
    if status not in _COMPLETE_STATUSES:
        return {}

    narr = fig.get("data_narrative") or {}
    vision = fig.get("vision_observation") or {}
    interp = dict(interpretation or fig.get("interpretation") or {})

    blocks: dict[str, Any] = {}

    # E — 数据支撑
    e_bullets = list(narr.get("bullets") or narr.get("sentences") or [])
    if e_bullets:
        blocks["e"] = {
            "title": "数据支撑" if zh else "Data support",
            "status": "ready",
            "bullets": e_bullets,
            "markdown": format_data_narrative_markdown(narr, zh=zh).strip(),
        }
    else:
        msg = (
            "暂无结构化 CSV 计数；请参见上方图注中的「结果文件事实」。"
            if zh
            else "No structured CSV summary; see file facts in the caption above."
        )
        blocks["e"] = {
            "title": "数据支撑" if zh else "Data support",
            "status": "placeholder",
            "bullets": [msg],
            "markdown": f"#### {'数据支撑' if zh else 'Data support'}\n\n{msg}",
        }

    # C — 读图观察
    vision_ok = bool(vision) and not vision.get("skipped") and not vision.get("error")
    c_patterns = list(vision.get("visible_patterns") or []) if vision_ok else []
    group_sep = str(vision.get("group_separation") or "").strip() if vision_ok else ""
    if vision_ok and (c_patterns or (group_sep and group_sep.upper() != "N/A")):
        blocks["c"] = {
            "title": "读图观察（AI，供参考）" if zh else "Visual observation (AI)",
            "status": "ready",
            "patterns": c_patterns,
            "group_separation": group_sep,
            "notable_features": str(vision.get("notable_features") or "").strip(),
            "interpretation_boundary": str(vision.get("interpretation_boundary") or "").strip(),
            "markdown": format_vision_markdown(vision, zh=zh).strip(),
        }
    else:
        if not insights_enabled:
            reason = (
                "未启用 AI 深度解读（use_llm=False），读图观察未运行。"
                if zh
                else "AI insights disabled (use_llm=False); visual observation was not run."
            )
        elif not vision_enabled():
            reason = (
                "读图观察已关闭（MASSAGENT_FIGURE_VISION=0）。"
                if zh
                else "Visual observation disabled (MASSAGENT_FIGURE_VISION=0)."
            )
        elif vision.get("error"):
            reason = (
                f"读图观察失败：{vision.get('error')}"
                if zh
                else f"Visual observation failed: {vision.get('error')}"
            )
        else:
            reason = (
                "读图观察未产生有效描述。"
                if zh
                else "No visual observation was produced."
            )
        blocks["c"] = {
            "title": "读图观察（AI，供参考）" if zh else "Visual observation (AI)",
            "status": "placeholder",
            "patterns": [],
            "markdown": f"#### {'读图观察（AI，供参考）' if zh else 'Visual observation (AI)'}\n\n{reason}",
            "placeholder_reason": reason,
        }

    # B — 图意解读
    if _has_llm_interpretation(interp):
        link = str(interp.get("link_to_objective") or interp.get("relation_to_goal") or "").strip()
        blocks["b"] = {
            "title": "图意解读" if zh else "Figure interpretation",
            "status": "ready",
            "source": "llm",
            "what_it_shows": str(interp.get("what_it_shows") or "").strip(),
            "link_to_objective": link,
            "caveats": str(interp.get("caveats") or "").strip(),
            "markdown": format_figure_interpretation_block(interp, zh=zh).strip(),
        }
    else:
        plan_interp = _plan_interpretation_fallback(fig, zh=zh)
        blocks["b"] = {
            "title": "图意解读" if zh else "Figure interpretation",
            "status": "plan_fallback" if not insights_enabled else "placeholder",
            "source": plan_interp.get("source") or "plan",
            "what_it_shows": plan_interp["what_it_shows"],
            "link_to_objective": plan_interp["link_to_objective"],
            "caveats": plan_interp["caveats"],
            "markdown": format_figure_interpretation_block(plan_interp, zh=zh).strip(),
        }
        if insights_enabled:
            extra = (
                "（深度解读已启用，但未生成本图 LLM 图意解读。）"
                if zh
                else " (Insights enabled, but LLM figure interpretation is missing for this figure.)"
            )
            blocks["b"]["markdown"] = (blocks["b"]["markdown"] or "") + "\n\n" + extra

    return blocks


def format_ecb_markdown_sections(
    fig: dict[str, Any],
    interpretation: dict[str, Any] | None = None,
    *,
    insights_enabled: bool = False,
    zh: bool = True,
) -> str:
    """将 E/C/B 三模块拼成 Markdown（用于 final_report.md）。"""
    blocks = build_ecb_blocks(
        fig,
        interpretation,
        insights_enabled=insights_enabled,
        zh=zh,
    )
    parts = [str(blocks[k].get("markdown") or "").strip() for k in ("e", "c", "b") if k in blocks]
    return "\n\n".join(p for p in parts if p)


__all__ = [
    "ECB_LAYOUT_VERSION",
    "build_ecb_blocks",
    "format_ecb_markdown_sections",
]
