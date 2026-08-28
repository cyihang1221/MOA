"""会话内跑 Agent C，或在缺少 B 结果时给出交接说明。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from web_frontend.backend.agent_c.plan_parser import parse_plan, resolve_all_plot_types
from web_frontend.backend.agent_c.results_inventory import find_metadata_csv, inventory_results
from web_frontend.backend.agent_c.runner import run_agent_c
from web_frontend.backend.plot_edit_registry import get_plot_spec
from web_frontend.backend.session_storage import session_upload_dir, session_work_dir


def find_session_plan(output_root: Path, upload_root: Path) -> Path | dict | None:
    for folder in (output_root, upload_root):
        for name in ("analysis_plan.json", "analysis_plan.md"):
            cand = folder / name
            if cand.is_file():
                return cand
        # MassOmics manifest: plan_<timestamp>.json（取最新）
        massomics = sorted(folder.glob("plan_*.json"), reverse=True)
        if massomics:
            return massomics[0]
        massomics_md = sorted(folder.glob("plan_*.md"), reverse=True)
        if massomics_md:
            return massomics_md[0]
    return None


def _handoff_message(
    *,
    user_message: str,
    inventory: dict[str, Any],
    requested_types: list[str],
) -> str:
    missing_lines: list[str] = []
    have = {str(p.get("plot_type")) for p in (inventory.get("plottable") or [])}
    for pt in requested_types:
        spec = get_plot_spec(pt)
        if pt in have:
            continue
        files = ", ".join(spec.data_files) if spec else "(未注册图类型)"
        missing_lines.append(f"- `{pt}` 需要：{files}")
    if not missing_lines and requested_types:
        missing_lines = ["- 结果目录存在，但未能匹配到可渲染数据"]
    if not requested_types:
        missing_lines = [
            "- 峰表 / 统计结果 / 网络表等（由 B 按方案写入 `outputspace`）",
        ]
    n_files = len(inventory.get("files") or [])
    return (
        "本前端是 **Agent C（可视化与报告）**，不再调用 XCMS / mixOmics / GNPS 等分析 MCP。\n\n"
        "你这条消息属于 **Agent B（分析执行）** 的职责。"
        "请先让 B 在本会话的 `outputspace` 写出结果文件，再回来作出图或写报告。\n\n"
        f"**当前结果目录**：`{inventory.get('results_dir')}`（{n_files} 个文件）\n\n"
        "**仍缺：**\n"
        + "\n".join(missing_lines)
        + "\n\nB 完成后可以说「按方案出图」或「写报告」。"
        + " 写报告时将自动生成 **结果解读与科研意义**（AI 深度解读，需 B 已写入统计结果文件）。"
        + "\n进程内也可直接调用 `run_agent_c(plan=..., results_dir=..., use_llm=True)`。\n\n"
        f"> 原话：{user_message[:200]}"
    )


def _synthetic_plan(user_message: str, plot_types: list[str]) -> dict[str, Any]:
    viz = []
    for i, pt in enumerate(plot_types, start=1):
        spec = get_plot_spec(pt)
        viz.append(
            {
                "figure_id": f"Figure {i}",
                "plot_type": pt,
                "title": spec.default_title if spec else pt,
                "theme": user_message[:120],
            }
        )
    return {
        "objective": user_message.strip()[:500],
        "required_visualization": viz,
        "interpretation_guideline": "只陈述结果文件中的可核对事实。",
        "reporting_plan": {"language": "zh"},
    }


def _wants_deep_report(message: str) -> bool:
    """用户消息是否显式要求深度解读（非仅出图）。"""
    text = (message or "").strip()
    if not text:
        return False
    triggers = (
        "深度报告",
        "深度解读",
        "分析意义",
        "科研意义",
        "分析价值",
        "价值与意义",
        "写解读",
        "interpretation report",
        "insight report",
    )
    lower = text.lower()
    return any(t in text or t in lower for t in triggers)


def _use_report_insights(message: str, intent: str) -> bool:
    """写报告路径默认启用 AI 深度解读；纯出图不启用。"""
    if intent == "c_report":
        return True
    return _wants_deep_report(message)


# 兼容旧单测/引用
_wants_insights_demo = _wants_deep_report


def stream_session_agent_c(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    user_message: str,
    intent: str,
) -> Iterator[dict[str, Any]]:
    """产出 SSE 事件：delta / visual_results / chat_image / error。"""
    output_root = session_work_dir(project_root, storage_slug)
    upload_root = session_upload_dir(project_root, storage_slug)
    output_root.mkdir(parents=True, exist_ok=True)

    yield {"delta": "🎨 **Agent C**：按方案与已有结果出图/写报告（不执行分析计算）。\n\n"}

    inv = inventory_results(output_root)
    requested = resolve_all_plot_types(user_message)
    plottable_types = {str(p.get("plot_type")) for p in (inv.get("plottable") or [])}
    can_plot = bool(inv.get("plottable"))
    if requested:
        can_plot = any(pt in plottable_types for pt in requested)

    if intent == "b_analysis":
        yield {"delta": _handoff_message(
            user_message=user_message,
            inventory=inv,
            requested_types=requested,
        )}
        return

    if intent == "c_from_results" and requested and not can_plot:
        yield {"delta": _handoff_message(
            user_message=user_message,
            inventory=inv,
            requested_types=requested,
        )}
        return

    plan_src: Any = find_session_plan(output_root, upload_root)
    figure_mode = "plan"
    if plan_src is None:
        if requested:
            plan_src = _synthetic_plan(user_message, requested)
            figure_mode = "plan"
        else:
            plan_src = {
                "objective": user_message.strip()[:500] or "根据已有结果出图",
                "required_visualization": [],
                "reporting_plan": {"language": "zh"},
            }
            figure_mode = "available"
            yield {"delta": "ℹ️ 未找到 `analysis_plan.md`，按结果目录中已有数据出图。\n\n"}
    elif intent == "c_from_results" and requested:
        figure_mode = "plan_then_available"

    if not can_plot and figure_mode == "available":
        yield {"delta": _handoff_message(
            user_message=user_message,
            inventory=inv,
            requested_types=requested,
        )}
        return

    meta = inv.get("metadata_csv") or find_metadata_csv(output_root, upload_root / "metadata.csv")
    out = output_root / "agent_c_output"
    use_insights = _use_report_insights(user_message, intent)
    if use_insights:
        yield {
            "delta": (
                "📝 报告将包含 **结果解读与科研意义**（AI 深度解读，基于现有结果文件）。\n\n"
            )
        }
    yield {"delta": "正在渲染图表并组装 `final_report.md`…\n\n"}
    try:
        manifest = run_agent_c(
            plan=plan_src,
            results_dir=output_root,
            output_dir=out,
            metadata_csv=meta,
            figure_mode=figure_mode,
            language="zh",
            use_llm=use_insights,
            goal_text=user_message,
            project_root=project_root,
        )
    except Exception as exc:
        yield {"error": f"Agent C 失败: {exc}"}
        return

    checklist_md = manifest.get("figure_checklist_md") or ""
    if checklist_md:
        yield {"delta": checklist_md + "\n\n"}

    status = manifest.get("status")
    n_ok = manifest.get("n_rendered") or 0
    n_bad = manifest.get("n_incomplete") or 0
    report = (manifest.get("report") or {}).get("markdown") or ""
    report_pdf = (manifest.get("report") or {}).get("pdf") or ""
    yield {
        "delta": (
            f"**状态**：{status}；完成 {n_ok} 张图"
            + (f"，{n_bad} 张未完成" if n_bad else "")
            + "。\n\n"
        )
    }
    lit = manifest.get("literature_style") or {}
    if lit.get("matched_skills"):
        skills = "`、`".join(str(s) for s in lit["matched_skills"][:3])
        journals = "/".join(str(j) for j in (lit.get("journals") or ["npg"]))
        yield {"delta": f"📚 **作图依据**：文献 Skill `{skills}`；配色 {journals}。\n\n"}
    elif lit.get("enabled"):
        yield {"delta": "📚 **作图依据**：未匹配到针对性文献，已套用发表级基线样式。\n\n"}
    for w in (lit.get("warnings") or [])[:2]:
        yield {"delta": f"ℹ️ {w}\n"}

    if report:
        yield {
            "delta": (
                "📄 **分析报告已生成** — 聊天下方可点击 **「查看分析报告」** 一键预览"
                "（含图表与深度解读），无需到 outputspace 找文件。\n\n"
            )
        }
    insights_json = (manifest.get("report") or {}).get("insights_json")
    if insights_json and use_insights:
        yield {"delta": "📝 已写入 **结果解读与科研意义** 章节（见报告预览）。\n\n"}
    if report_pdf:
        yield {"delta": f"PDF：`{report_pdf}`\n\n"}

    visual: list[dict[str, Any]] = []
    for fig in manifest.get("figures") or []:
        png = fig.get("png")
        st = fig.get("status")
        if st not in {"rendered", "copied_existing"} or not png:
            cap = (fig.get("caption") or "").strip()
            if cap:
                yield {"delta": cap + "\n\n"}
            elif fig.get("missing_reason"):
                yield {"delta": f"- {fig.get('figure_id')}: {fig['missing_reason']}\n"}
            continue
        try:
            rel = str(Path(png).resolve().relative_to(output_root.resolve())).replace("\\", "/")
        except ValueError:
            rel = str(png)
        # 聊天区只预览 C 新渲染图；B 侧已有 PNG 仅在报告/图库中展示
        if st == "rendered" and rel.startswith("agent_c_output/figures/"):
            visual.append({"kind": "agent_c", "file": rel})
            yield {"chat_image": {"file": rel, "kind": "agent_c"}}
        cap = (fig.get("caption") or "").strip()
        if cap:
            yield {"delta": cap + "\n\n"}
        elif fig.get("missing_reason"):
            yield {"delta": f"- {fig.get('figure_id')}: {fig['missing_reason']}\n"}

    if visual:
        yield {"visual_results": visual}

    report_md = (manifest.get("report") or {}).get("markdown") or ""
    if report_md:
        try:
            rel = str(Path(report_md).resolve().relative_to(output_root.resolve())).replace("\\", "/")
        except ValueError:
            rel = "agent_c_output/final_report.md"
        yield {
            "agent_c_report": {
                "report_rel": rel,
                "view_url": f"/api/sessions/{session_id}/agent-c/report",
                "n_rendered": manifest.get("n_rendered"),
                "insights_enabled": bool((manifest.get("report") or {}).get("insights_enabled")),
            }
        }

    parsed = parse_plan(plan_src)
    for w in (parsed.get("warnings") or [])[:3]:
        yield {"delta": f"ℹ️ {w}\n"}
