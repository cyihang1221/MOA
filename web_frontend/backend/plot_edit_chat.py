"""聊天内触发的 Agent 改图流程。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator

from web_frontend.backend.plot_edit_service import (
    PlotEditError,
    agent_apply_plot_edit,
    resolve_chat_plot_edit_tasks,
)
from web_frontend.backend.session_storage import session_work_dir


def run_chat_plot_edit(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    message: str,
    model: str | None = None,
    goal_text: str | None = None,
) -> dict[str, Any]:
    tasks, plots = resolve_chat_plot_edit_tasks(
        project_root=project_root,
        storage_slug=storage_slug,
        message=message,
    )
    results = []
    for source_rel, instruction in tasks:
        results.append(
            agent_apply_plot_edit(
                project_root=project_root,
                session_id=session_id,
                storage_slug=storage_slug,
                source_rel=source_rel,
                instruction=instruction,
                model=model,
                goal_text=goal_text,
            )
        )
    return {"results": results, "available_plots": [p["rel"] for p in plots]}


def _file_rel_from_result(result: dict[str, Any] | None) -> str:
    """改图结果中的会话相对 PNG 路径，供聊天预览。"""
    if not isinstance(result, dict):
        return ""
    file_info = result.get("file")
    if isinstance(file_info, dict):
        rel = str(file_info.get("name") or "").strip()
        if rel:
            return rel
    return str(result.get("effective_rel") or "").strip()


def _literature_progress_line(result: dict[str, Any]) -> str:
    skills = [str(s) for s in (result.get("literature_skills") or []) if s]
    rag_mode = str(result.get("literature_rag_mode") or "").strip()
    sources = [str(s) for s in (result.get("literature_rag_sources") or []) if s]
    refs = result.get("evidence_refs") or []
    dois = []
    for ref in refs:
        if isinstance(ref, dict) and ref.get("doi"):
            dois.append(str(ref["doi"]))
    bits: list[str] = []
    if skills:
        bits.append("、".join(skills[:3]))
    if rag_mode and rag_mode not in {"", "disabled", "empty"}:
        bits.append(f"RAG {rag_mode}")
    if sources:
        bits.append(Path(sources[0]).name)
    if dois:
        bits.append(f"DOI {dois[0]}")
    if not bits:
        return ""
    return "- 文献依据：" + "；".join(bits) + "\n"


_REDRAW_ONLY_RE = re.compile(
    r"(?:标题|颜色|色号|配色|字号|字体|图例|椭圆|改成|改为|换成|不要|去掉|隐藏|显示)"
)


def _instruction_for_redraw(instruction: str, score_style: str | None) -> str:
    """只说「重新绘制」时，不要让模型把整句改成标题。风格单独由 score_style 决定。"""
    text = (instruction or "").strip()
    if not text or _REDRAW_ONLY_RE.search(text):
        return text
    if not re.search(r"重新绘|重绘|重新画|重新作图|重新生成", text):
        return text
    style = "ggplot 分组椭圆" if str(score_style or "").startswith("ggplot") else "SIMCA 得分图"
    return f"只按{style}重绘这张得分图，不要修改标题、配色、坐标范围或数据。"


def stream_chat_plot_edit_deltas(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    message: str,
    model: str | None = None,
    goal_text: str | None = None,
    score_style: str | None = None,
) -> Iterator[dict[str, Any]]:
    yield {"delta": "**改图模式**：正在解析你的要求，并对照知识库文献改图…\n\n"}
    output_root = session_work_dir(project_root, storage_slug)
    try:
        tasks, plots = resolve_chat_plot_edit_tasks(
            project_root=project_root,
            storage_slug=storage_slug,
            message=message,
        )
        if len(tasks) > 1:
            yield {"delta": f"检测到 **{len(tasks)}** 条改图指令，将依次处理。\n\n"}
        elif len(plots) > 1:
            yield {"delta": f"当前会话共有 **{len(plots)}** 张可改图；已按描述自动选择。\n\n"}

        last_result = None
        preview_rels: list[str] = []
        for index, (source_rel, instruction) in enumerate(tasks, start=1):
            plot_name = source_rel.split("/")[-1]
            prefix = f"**[{index}/{len(tasks)}]** " if len(tasks) > 1 else ""
            yield {"delta": f"{prefix}目标：`{plot_name}`\n\n"}
            yield {"delta": "正在检索文献作图知识并重绘（matplotlib）…\n\n"}
            instruction = _instruction_for_redraw(instruction, score_style)
            result = agent_apply_plot_edit(
                project_root=project_root,
                session_id=session_id,
                storage_slug=storage_slug,
                source_rel=source_rel,
                instruction=instruction,
                model=model,
                goal_text=goal_text,
                score_style=score_style,
            )
            last_result = result
            new_rel = _file_rel_from_result(result)
            new_name = new_rel.split("/")[-1] if new_rel else "plot.png"
            patch = result.get("agent_patch") or {}
            summary_parts = []
            style_used = str(((result.get("plot_config") or {}).get("data") or {}).get("score_style") or "")
            if style_used:
                summary_parts.append("风格 → " + ("ggplot 分组椭圆" if style_used.startswith("ggplot") else "SIMCA"))
            if patch.get("title"):
                summary_parts.append(f"标题 → {patch['title']}")
            if patch.get("palette"):
                summary_parts.append(f"配色 {len(patch['palette'])} 项")
            if patch.get("colors"):
                summary_parts.append(f"颜色 {len(patch['colors'])} 项")
            if patch.get("font_size"):
                summary_parts.append("字号已调整")
            if patch.get("color_by"):
                summary_parts.append(f"着色 → {patch['color_by']}")
            if patch.get("ellipse") or (isinstance(patch.get("marks"), dict) and patch["marks"].get("ellipse")):
                summary_parts.append("置信椭圆")
            diff_summary = str((result.get("config_diff") or {}).get("summary") or "").strip()
            summary = "；".join(summary_parts) if summary_parts else (
                diff_summary if diff_summary and diff_summary != "无字段变化" else "已应用修改"
            )
            extra = ""
            if diff_summary and diff_summary != "无字段变化" and summary_parts:
                extra = f"\n- 字段 diff：{diff_summary}"
            lit_line = _literature_progress_line(result)
            warn_lines = ""
            for w in (result.get("visual_warnings") or [])[:3]:
                warn_lines += f"- 注意：{w}\n"
            yield {
                "delta": (
                    f"✅ {prefix}完成：**{new_name}**（`{new_rel}`）\n"
                    f"- {summary}{extra}\n"
                    f"{lit_line}"
                    f"{warn_lines}"
                    f"- 已设为当前生效版本（连续改图将基于此图）\n"
                    + (
                        f"- 参数：`{result['plot_config']['name']}`\n\n"
                        if result.get("plot_config")
                        else "\n"
                    )
                )
            }
            if new_rel:
                preview_rels.append(new_rel)
                version = ""
                try:
                    version = str(int((output_root / new_rel).stat().st_mtime))
                except OSError:
                    version = ""
                yield {"chat_image": {"file": new_rel, "version": version}}

        yield {
            "plot_edit_done": True,
            "result": last_result,
            "finished": True,
            "chat_images": preview_rels,
        }
    except PlotEditError as exc:
        yield {"delta": f"⚠️ 改图失败：{exc}\n\n"}
        yield {"error": str(exc), "finished": True}
    except Exception as exc:
        yield {"delta": f"⚠️ 改图异常：{exc}\n\n"}
        yield {"error": str(exc), "finished": True}


__all__ = ["run_chat_plot_edit", "stream_chat_plot_edit_deltas"]
