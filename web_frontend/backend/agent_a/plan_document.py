"""把可执行步骤写成需求文档第 8.1 节形态的 analysis_plan.md / json。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_a.plan_catalog import (
    figure_payload,
    hint_for_tool,
)
from web_frontend.backend.agent_c.plan_parser import resolve_all_plot_types
from web_frontend.backend.plot_edit_registry import get_plot_spec

C_VISUAL_TOOL_NAMES = ("plot_edit", "image_merge", "merge_edit")
_USE_TOOL_RE = re.compile(r"\buse\s+([a-z0-9_]+)", re.IGNORECASE)


def is_c_visual_task(task: str) -> bool:
    low = (task or "").lower()
    return any(name in low for name in C_VISUAL_TOOL_NAMES)


def executable_tasks_for_b(tasks: list[str]) -> list[str]:
    return [t for t in tasks if str(t).strip() and not is_c_visual_task(str(t))]


def _tool_names(tasks: list[str]) -> list[str]:
    found: list[str] = []
    for task in tasks:
        for match in _USE_TOOL_RE.finditer(task):
            name = match.group(1)
            if name not in found and name not in C_VISUAL_TOOL_NAMES:
                found.append(name)
    return found


def _figures_from_tasks(tasks: list[str]) -> list[dict[str, Any]]:
    figures: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task in tasks:
        for plot_type in resolve_all_plot_types(task):
            if plot_type in seen:
                continue
            seen.add(plot_type)
            spec = get_plot_spec(plot_type)
            figures.append(
                figure_payload(
                    plot_type,
                    len(figures) + 1,
                    spec.default_title if spec else plot_type,
                )
            )
    return figures


def _render_workflow(tasks: list[str]) -> tuple[str, str, str]:
    """返回 workflow md、tools md、expected md。"""
    b_tasks = executable_tasks_for_b(tasks)
    workflow_parts: list[str] = []
    tool_rows: list[str] = []
    expected_parts: list[str] = []
    used: list[str] = []
    for i, task in enumerate(b_tasks, start=1):
        hint = hint_for_tool(task)
        names = _tool_names([task])
        tool_label = ", ".join(f"`{n}`" for n in names) if names else "（见 Operations）"
        workflow_parts.append(
            f"### Step {i}\n"
            f"- Objective: {hint['objective']}\n"
            f"- Input: {hint['input']}\n"
            f"- Operations: {task}\n"
            f"- Output: {hint['output']}\n"
        )
        expected_parts.append(f"- Step {i}（{tool_label}）：{hint['expected']}")
        for n in names:
            if n not in used:
                used.append(n)
                tool_rows.append(f"| `{n}` | {hint['reason']} |")
    tools_md = (
        "| 工具 | 选择理由（推断） |\n|------|------------------|\n" + "\n".join(tool_rows)
        if tool_rows
        else "（规划步骤中未解析到已注册工具名）"
    )
    expected_md = "\n".join(expected_parts) if expected_parts else "（暂无计算步骤）"
    return "\n".join(workflow_parts) if workflow_parts else "（暂无计算步骤）", tools_md, expected_md


def _render_figures_md(figures: list[dict[str, Any]]) -> str:
    if not figures:
        return "（规划步骤中未识别到已注册图型；执行后可按结果目录补图。）\n"
    chunks: list[str] = []
    for fig in figures:
        panels = fig.get("panels") or []
        panel = panels[0] if panels else {}
        hint = fig.get("plot_config_hint") or {}
        sfiles = ", ".join(fig.get("source_files") or []) or "（由 PlotSpec 推断）"
        step = fig.get("source_step") or "—"
        journal = hint.get("journal_palette") or "npg"
        style_src = hint.get("style_source") or "baseline"
        refs = fig.get("literature_refs") or []
        ref_line = ""
        if refs:
            doi = next((r.get("doi") for r in refs if r.get("doi")), "")
            skills = [r.get("skill_id") for r in refs if r.get("skill_id")]
            parts = []
            if doi:
                parts.append(f"DOI `{doi}`")
            if skills:
                parts.append("Skill: " + ", ".join(f"`{s}`" for s in skills[:3]))
            ref_line = "- 文献依据：" + "；".join(parts) + "\n"
        chunks.append(
            f"### {fig.get('figure_id')} {fig.get('title') or fig.get('plot_type')}\n"
            f"- 图型：{fig.get('plot_type')}\n"
            f"- 数据步骤：Step {step}；预期文件：{sfiles}\n"
            f"- 样式 hint：期刊配色 {journal}（{style_src}）\n"
            f"{ref_line}"
            f"- 总体主题：{fig.get('theme')}\n"
            f"- 核心逻辑链：{fig.get('logic')}\n"
            f"- Panel A Purpose：{panel.get('purpose') or fig.get('purpose')}\n"
            f"- Panel A 建议设计：{panel.get('design') or ''}\n"
            f"- Panel A 预期观察：{panel.get('expected_observation') or fig.get('expected_observation')}\n"
            f"- Panel A 存在理由：{panel.get('rationale') or ''}\n"
        )
    return "\n".join(chunks)


def _render_interpretation(figures: list[dict[str, Any]]) -> str:
    lines = [
        "解读只陈述结果文件中的可核对事实；图中的分组分离不等于生物标志物。",
        "每条结论必须引用图号。下列要点供报告撰写对照，不是执行前的既成结论。",
        "",
    ]
    if not figures:
        lines.append("（尚无图清单；报告阶段按实际生成图填写。）")
        return "\n".join(lines)
    for fig in figures:
        lines.append(
            f"- **{fig.get('figure_id')}**（{fig.get('plot_type')}）："
            f"{fig.get('expected_observation')}"
        )
    return "\n".join(lines)


def render_analysis_plan_md(
    *,
    objective: str,
    data_understanding: str,
    tasks: list[str],
    figures: list[dict[str, Any]] | None = None,
) -> str:
    figs = figures if figures is not None else _figures_from_tasks(tasks)
    workflow_md, tools_md, expected_md = _render_workflow(tasks)
    viz_md = _render_figures_md(figs)
    interp_md = _render_interpretation(figs)
    obj = (objective or "").strip() or "（用户未写明目标，将按数据做常规非靶向分析）"
    data_u = (data_understanding or "").strip() or "见会话 inputspace 文件列表。"
    return (
        "> 下列八节对应需求 FR-2.1～FR-2.8。"
        "工作流步骤来自规划模型；工具理由、图 Panel 与解读要点由已注册工具/图型**推断**补全，供评审，并非另一次目的驱动重规划。\n\n"
        "# Objective\n"
        f"{obj}\n\n"
        "# Data understanding\n"
        f"{data_u}\n\n"
        "# Workflow\n"
        f"{workflow_md}\n\n"
        "# Tools required\n"
        f"{tools_md}\n\n"
        "# Expected results\n"
        f"{expected_md}\n\n"
        "# Required visualization\n"
        f"{viz_md}\n"
        "# Interpretation guideline\n"
        f"{interp_md}\n\n"
        "# Reporting plan\n"
        "- 语言：中文\n"
        "- 章节：Introduction / Methods / Analysis Workflow / Results / Figures / "
        "Scientific Interpretation / Conclusion / Appendix\n"
        "- 图表：按上节图号嵌入 Results/Figures，图注引用文件名\n"
        "- 结论必须引用图号；不得写出结果文件中不存在的数值\n\n"
        "---\n"
        "请审阅本计划。确认后回复 **确认计划**；若要修改请直接说明意见。"
        "未确认前不会启动分析执行。\n"
    )


def write_analysis_plan(
    output_dir: Path,
    *,
    objective: str,
    data_understanding: str,
    tasks: list[str],
    plan_version: int = 1,
    user_message: str = "",
    project_root: Any = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    b_tasks = executable_tasks_for_b(tasks)
    from web_frontend.backend.agent_a.figure_blueprint import (
        blueprint_summary_markdown,
        figures_from_tasks_with_blueprints,
    )

    figures, blueprint_meta = figures_from_tasks_with_blueprints(
        tasks,
        user_message=user_message,
        objective=objective,
        project_root=project_root,
    )
    md = render_analysis_plan_md(
        objective=objective,
        data_understanding=data_understanding,
        tasks=tasks,
        figures=figures,
    )
    md += "\n\n" + blueprint_summary_markdown(blueprint_meta, figures) + "\n"
    payload: dict[str, Any] = {
        "objective": objective,
        "data_understanding": data_understanding,
        "workflow": [
            {
                "stage": f"Step {i}",
                "task": t,
                "objective": hint_for_tool(t)["objective"],
                "input": hint_for_tool(t)["input"],
                "operations": t,
                "output": hint_for_tool(t)["output"],
                "expected_output": hint_for_tool(t)["expected"],
                "tools": ", ".join(_tool_names([t])),
            }
            for i, t in enumerate(b_tasks, start=1)
        ],
        "tools_required": "\n".join(
            f"- `{n}`：{hint_for_tool(n)['reason']}" for n in _tool_names(b_tasks)
        )
        or "（未解析到工具名）",
        "expected_results": "\n".join(
            f"- Step {i}: {hint_for_tool(t)['expected']}"
            for i, t in enumerate(b_tasks, start=1)
        ),
        "required_visualization": figures,
        "interpretation_guideline": _render_interpretation(figures),
        "reporting_plan": {
            "language": "zh",
            "sections": [
                "Introduction",
                "Methods",
                "Analysis Workflow",
                "Results",
                "Figures",
                "Scientific Interpretation",
                "Conclusion",
                "Appendix",
            ],
            "notes": "结论必须引用图号；不得写出结果文件中不存在的数值。",
        },
        "reproduction_target": blueprint_meta.get("reproduction_target"),
        "figure_blueprint": blueprint_meta,
        "executable_tasks": b_tasks,
        "plan_version": plan_version,
    }
    (output_dir / "analysis_plan.md").write_text(md, encoding="utf-8")
    (output_dir / "analysis_plan.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def load_executable_tasks(output_dir: Path) -> list[str]:
    path = Path(output_dir) / "analysis_plan.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        tasks = data.get("executable_tasks")
        if isinstance(tasks, list) and tasks:
            return [str(t).strip() for t in tasks if str(t).strip()]
        plan = data.get("plan") or data.get("workflow")
        if isinstance(plan, list) and plan:
            out: list[str] = []
            for item in plan:
                if isinstance(item, dict):
                    text = str(item.get("task") or item.get("operations") or "").strip()
                else:
                    text = str(item).strip()
                if text:
                    out.append(text)
            return executable_tasks_for_b(out)
    if isinstance(data, list):
        return executable_tasks_for_b(
            [str(x.get("task") if isinstance(x, dict) else x).strip() for x in data]
        )
    return []
