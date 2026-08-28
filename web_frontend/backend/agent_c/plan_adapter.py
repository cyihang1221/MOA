"""把 MassOmics-Agent PlanDocument 规范化为 Agent C 可消费的 canonical plan。

MassOmics A 产出（``plan/schema.py``）字段：
  goal, steps[], visualizations[], interpretations[], report{},
  risks[], assumptions[], references[]

Web FR-2 产出（``agent_a/plan_document.py``）字段：
  objective, workflow[], required_visualization[], interpretation_guideline,
  reporting_plan{}, ...

本模块只做**结构映射**，不调用 LLM，不重写分析目的。
"""
from __future__ import annotations

import re
from typing import Any

# 注意：不在模块顶层 import plan_parser，避免与 plan_parser ↔ plan_adapter 循环依赖

# MassOmics Markdown 章节（plan/schema.py to_markdown）
_MASSOMICS_MD_SECTIONS: dict[str, tuple[str, ...]] = {
    "objective": ("分析目标", "代谢组学分析计划"),
    "workflow": ("分析工作流",),
    "required_visualization": ("可视化方案",),
    "interpretations": ("结果解读要点",),
    "reporting_plan": ("报告撰写方案",),
    "assumptions": ("假设",),
    "risks": ("风险",),
    "references": ("参考文献",),
}

_STEP_HEADING_RE = re.compile(r"^###\s+Step\s+(\d+)\s*[:：]?\s*(.*)$", re.I | re.M)
_VIZ_BULLET_RE = re.compile(
    r"^-\s+\*\*(.+?)\*\*\s*(?:\(来源\s*Step\s*(\d+)\))?\s*[:：]?\s*(.+)$",
    re.I | re.M,
)
_INTERP_BULLET_RE = re.compile(
    r"^-\s+\*\*(.+?)\*\*\s*[:：]\s*(.+?)(?:\s*\|\s*解读\s*[:：]\s*(.+))?$",
    re.I | re.M,
)


def is_massomics_plan_document(data: dict[str, Any]) -> bool:
    """判断 JSON 是否为 MassOmics PlanDocument（而非 Web FR-2 canonical）。"""
    if not isinstance(data, dict):
        return False
    if data.get("plan_format") == "massomics":
        return True
    # Web canonical 优先
    if "required_visualization" in data and ("objective" in data or "reporting_plan" in data):
        return False
    if "goal" in data and isinstance(data.get("steps"), list):
        return True
    if "goal" in data and isinstance(data.get("visualizations"), list):
        return True
    return False


def _step_to_workflow_item(step: dict[str, Any], index: int) -> dict[str, Any]:
    tools = step.get("tools") or []
    if isinstance(tools, str):
        tools = [t.strip() for t in tools.split(",") if t.strip()]
    tool_str = ", ".join(str(t) for t in tools) if tools else ""
    num = step.get("step_number") or index
    desc = str(step.get("description") or step.get("task") or "").strip()
    return {
        "step_id": num,
        "stage": f"Step {num}",
        "objective": desc,
        "task": desc,
        "input": str(step.get("input_filename") or step.get("input") or ""),
        "operations": desc,
        "output": str(step.get("output_filename") or step.get("output") or ""),
        "tools": tool_str,
        "expected_output": str(step.get("expected_output") or ""),
    }


def _visualization_to_figure(item: dict[str, Any], index: int) -> dict[str, Any]:
    from web_frontend.backend.agent_c.plan_parser import resolve_plot_type

    name = str(item.get("name") or item.get("title") or f"Figure {index}").strip()
    chart = str(item.get("chart_type") or item.get("plot_type") or item.get("type") or "").strip()
    plot_type = resolve_plot_type(chart) or ""
    description = str(item.get("description") or item.get("theme") or "").strip()
    source_step = int(item.get("source_step") or 0)
    purpose = description or f"来源 Step {source_step}" if source_step else ""
    return {
        "figure_id": name if name.lower().startswith("figure") else f"Figure {index}",
        "title": name,
        "plot_type": plot_type,
        "theme": description or chart,
        "logic": f"Step {source_step} 产出 → {chart or plot_type}" if source_step else "",
        "purpose": purpose,
        "expected_observation": str(item.get("expected_observation") or ""),
        "source_step": source_step,
        "description": description,
        "panels": list(item.get("panels") or []),
        "plot_config_hint": dict(item.get("plot_config_hint") or {}),
    }


def _interpretations_to_guideline(items: list[Any]) -> str:
    lines: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            lines.append(str(it))
            continue
        target = str(it.get("target") or "").strip()
        criteria = str(it.get("criteria") or "").strip()
        note = str(it.get("note") or "").strip()
        parts = [p for p in (criteria, note) if p]
        body = "；".join(parts) if parts else ""
        if target and body:
            lines.append(f"- **{target}**：{body}")
        elif body:
            lines.append(f"- {body}")
        elif target:
            lines.append(f"- **{target}**")
    return "\n".join(lines)


def _report_to_reporting_plan(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {"language": "zh", "sections": [], "notes": str(report or "")}
    sections = report.get("sections") or []
    notes_parts: list[str] = []
    audience = str(report.get("audience") or "").strip()
    decision = str(report.get("decision_to_report") or "").strip()
    refs = report.get("references") or []
    if audience:
        notes_parts.append(f"目标读者：{audience}")
    if decision:
        notes_parts.append(f"结论导出：{decision}")
    if refs:
        notes_parts.append("报告引用：" + "；".join(str(r) for r in refs))
    return {
        "language": str(report.get("language") or "zh"),
        "sections": [str(s) for s in sections] if isinstance(sections, list) else [],
        "audience": audience,
        "decision_to_report": decision,
        "references": [str(r) for r in refs] if isinstance(refs, list) else [],
        "notes": "\n".join(notes_parts),
    }


def normalize_massomics_plan(data: dict[str, Any]) -> dict[str, Any]:
    """PlanDocument dict → Web FR-2 风格 canonical dict（供 parse_plan 二次规范化）。"""
    steps = data.get("steps") or []
    if not isinstance(steps, list):
        steps = []
    workflow = [
        _step_to_workflow_item(s, i)
        for i, s in enumerate(steps, start=1)
        if isinstance(s, dict)
    ]
    tools: list[str] = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        for t in s.get("tools") or []:
            ts = str(t).strip()
            if ts and ts not in tools:
                tools.append(ts)
    expected_lines = []
    for w in workflow:
        eo = w.get("expected_output") or ""
        if eo:
            expected_lines.append(f"- Step {w.get('step_id')}: {eo}")

    viz_raw = data.get("visualizations") or data.get("required_visualization") or []
    figures = [
        _visualization_to_figure(v, i)
        for i, v in enumerate(viz_raw, start=1)
        if isinstance(v, dict)
    ]

    interpretations = data.get("interpretations") or []
    if not isinstance(interpretations, list):
        interpretations = []

    assumptions = data.get("assumptions") or []
    risks = data.get("risks") or []
    references = data.get("references") or []

    data_understanding_parts: list[str] = []
    if assumptions:
        data_understanding_parts.append("假设：" + "；".join(str(a) for a in assumptions))

    # 从步骤 input/output 链推断数据理解
    io_hints = []
    for w in workflow[:3]:
        inp = w.get("input") or ""
        if inp and inp not in io_hints:
            io_hints.append(inp)
    if io_hints:
        data_understanding_parts.append("输入：" + "；".join(io_hints))

    return {
        "plan_format": "massomics",
        "objective": str(data.get("goal") or data.get("objective") or ""),
        "data_understanding": "\n".join(data_understanding_parts),
        "workflow": workflow,
        "tools_required": "\n".join(f"- `{t}`" for t in tools) if tools else "",
        "expected_results": "\n".join(expected_lines),
        "required_visualization": figures,
        "interpretations": interpretations,
        "interpretation_guideline": _interpretations_to_guideline(interpretations),
        "reporting_plan": _report_to_reporting_plan(data.get("report") or data.get("reporting_plan")),
        "risks": [str(r) for r in risks] if isinstance(risks, list) else [],
        "assumptions": [str(a) for a in assumptions] if isinstance(assumptions, list) else [],
        "references": [str(r) for r in references] if isinstance(references, list) else [],
    }


def _normalize_md_heading(title: str) -> str | None:
    t = re.sub(r"^[\d.、\s]+", "", (title or "").strip()).lower()
    for field, aliases in _MASSOMICS_MD_SECTIONS.items():
        for alias in aliases:
            if t == alias.lower() or alias.lower() in t:
                return field
    return None


def parse_massomics_markdown(text: str) -> dict[str, Any] | None:
    """解析 MassOmics ``PlanDocument.to_markdown()`` 产出；无法识别时返回 None。"""
    if not text or "分析目标" not in text and "分析工作流" not in text:
        return None
    sections: dict[str, list[str]] = {}
    current = "_preamble"
    sections[current] = []
    for line in text.splitlines():
        m = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if m:
            field = _normalize_md_heading(m.group(1))
            if field:
                current = field
                sections.setdefault(current, [])
                continue
        sections.setdefault(current, []).append(line)

    if "objective" not in sections and "workflow" not in sections:
        return None

    goal = "\n".join(sections.get("objective") or []).strip()
    workflow: list[dict[str, Any]] = []
    wf_text = "\n".join(sections.get("workflow") or [])
    for m in _STEP_HEADING_RE.finditer(wf_text):
        num = int(m.group(1))
        desc = m.group(2).strip()
        block_start = m.end()
        next_m = _STEP_HEADING_RE.search(wf_text, block_start)
        block = wf_text[block_start : next_m.start() if next_m else len(wf_text)]
        step: dict[str, Any] = {
            "step_number": num,
            "description": desc,
            "tools": [],
            "input_filename": "",
            "output_filename": "",
            "expected_output": "",
        }
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("- **输入**"):
                step["input_filename"] = re.sub(r"^[^`]*`([^`]+)`.*", r"\1", line).strip("` ")
            elif line.startswith("- **输出**"):
                step["output_filename"] = re.sub(r"^[^`]*`([^`]+)`.*", r"\1", line).strip("` ")
            elif line.startswith("- **工具**"):
                tools = re.sub(r"^-\s*\*\*工具\*\*:\s*", "", line)
                step["tools"] = [t.strip() for t in tools.split(",") if t.strip() and t != "-"]
            elif line.startswith("- **预期结果**"):
                step["expected_output"] = re.sub(r"^-\s*\*\*预期结果\*\*:\s*", "", line)
        workflow.append(_step_to_workflow_item(step, num))

    figures: list[dict[str, Any]] = []
    viz_text = "\n".join(sections.get("required_visualization") or [])
    for i, m in enumerate(_VIZ_BULLET_RE.finditer(viz_text), start=1):
        name = m.group(1).strip()
        source_step = int(m.group(2) or 0)
        rest = m.group(3).strip()
        # "PCA得分图 — 展示分组" 或 "PCA得分图: 展示"
        chart, _, desc = rest.partition("—")
        if not desc:
            chart, _, desc = rest.partition(":")
        figures.append(
            _visualization_to_figure(
                {
                    "name": name,
                    "chart_type": chart.strip(),
                    "source_step": source_step,
                    "description": desc.strip(),
                },
                i,
            )
        )

    interpretations: list[dict[str, str]] = []
    interp_text = "\n".join(sections.get("interpretations") or [])
    for m in _INTERP_BULLET_RE.finditer(interp_text):
        interpretations.append(
            {
                "target": m.group(1).strip(),
                "criteria": m.group(2).strip(),
                "note": (m.group(3) or "").strip(),
            }
        )

    report_section = "\n".join(sections.get("reporting_plan") or [])
    report: dict[str, Any] = {}
    aud = re.search(r"目标读者\*\*:\s*(.+)", report_section)
    if aud:
        report["audience"] = aud.group(1).strip()
    sec = re.search(r"章节结构\*\*:\s*(.+)", report_section)
    if sec:
        report["sections"] = [s.strip() for s in sec.group(1).split("；") if s.strip()]
    dec = re.search(r"结论导出\*\*:\s*(.+)", report_section)
    if dec:
        report["decision_to_report"] = dec.group(1).strip()

    def _bullets(key: str) -> list[str]:
        lines = sections.get(key) or []
        return [ln.strip()[2:].strip() for ln in lines if ln.strip().startswith("- ")]

    payload = normalize_massomics_plan(
        {
            "goal": goal,
            "steps": [
                {
                    "step_number": w["step_id"],
                    "description": w.get("task") or w.get("objective") or "",
                    "input_filename": w.get("input") or "",
                    "output_filename": w.get("output") or "",
                    "tools": (w.get("tools") or "").split(", ") if w.get("tools") else [],
                    "expected_output": w.get("expected_output") or "",
                }
                for w in workflow
            ],
            "visualizations": [
                {
                    "name": f["title"],
                    "chart_type": f.get("plot_type") or f.get("theme"),
                    "source_step": f.get("source_step") or 0,
                    "description": f.get("description") or f.get("theme") or "",
                }
                for f in figures
            ],
            "interpretations": interpretations,
            "report": report,
            "assumptions": _bullets("assumptions"),
            "risks": _bullets("risks"),
            "references": _bullets("references"),
        }
    )
    payload["source"] = {"format": "massomics_md", "path": ""}
    return payload


def attach_source_files(plan: dict[str, Any]) -> None:
    """根据 source_step 把 workflow 预期输出文件名挂到 figure 上，供 match_figures 优先匹配。"""
    workflow = plan.get("workflow") or []
    step_outputs: dict[int, list[str]] = {}
    for step in workflow:
        if not isinstance(step, dict):
            continue
        sid = step.get("step_id") or step.get("step_number")
        if sid is None:
            continue
        try:
            num = int(sid)
        except (TypeError, ValueError):
            continue
        out = str(step.get("output") or step.get("expected_output") or "").strip()
        if out:
            files = [f.strip() for f in re.split(r"[,;\s]+", out) if f.strip() and "." in f]
            step_outputs[num] = files

    for fig in plan.get("required_visualization") or []:
        if not isinstance(fig, dict):
            continue
        src = int(fig.get("source_step") or 0)
        if src and src in step_outputs:
            fig["source_files"] = list(step_outputs[src])
        elif fig.get("source_files"):
            continue
        else:
            fig.setdefault("source_files", [])
