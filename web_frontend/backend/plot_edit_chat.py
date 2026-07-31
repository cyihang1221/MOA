"""聊天内触发的 Agent 改图流程。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from web_frontend.backend.plot_edit_service import (
    PlotEditError,
    agent_apply_plot_edit,
    resolve_chat_plot_edit_tasks,
)


def run_chat_plot_edit(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    message: str,
    model: str | None = None,
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
            )
        )
    return {"results": results, "available_plots": [p["rel"] for p in plots]}


def stream_chat_plot_edit_deltas(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    message: str,
    model: str | None = None,
) -> Iterator[dict[str, Any]]:
    yield {"delta": "**改图模式**：正在解析你的要求并定位目标图片…\n\n"}
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
        for index, (source_rel, instruction) in enumerate(tasks, start=1):
            plot_name = source_rel.split("/")[-1]
            prefix = f"**[{index}/{len(tasks)}]** " if len(tasks) > 1 else ""
            yield {"delta": f"{prefix}目标：`{plot_name}`\n\n"}
            yield {"delta": "正在解析参数并重绘（matplotlib）…\n\n"}
            result = agent_apply_plot_edit(
                project_root=project_root,
                session_id=session_id,
                storage_slug=storage_slug,
                source_rel=source_rel,
                instruction=instruction,
                model=model,
            )
            last_result = result
            new_rel = result["file"]["name"]
            new_name = new_rel.split("/")[-1]
            patch = result.get("agent_patch") or {}
            summary_parts = []
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
            diff_summary = str((result.get("config_diff") or {}).get("summary") or "").strip()
            summary = "；".join(summary_parts) if summary_parts else (
                diff_summary if diff_summary and diff_summary != "无字段变化" else "已应用修改"
            )
            extra = ""
            if diff_summary and diff_summary != "无字段变化" and summary_parts:
                extra = f"\n- 字段 diff：{diff_summary}"
            yield {
                "delta": (
                    f"✅ {prefix}完成：**{new_name}**（`{new_rel}`）\n"
                    f"- {summary}{extra}\n"
                    f"- 已设为当前生效版本（连续改图将基于此图）\n"
                    + (
                        f"- 参数：`{result['plot_config']['name']}`\n\n"
                        if result.get("plot_config")
                        else "\n"
                    )
                )
            }

        yield {"plot_edit_done": True, "result": last_result, "finished": True}
    except PlotEditError as exc:
        yield {"delta": f"⚠️ 改图失败：{exc}\n\n"}
        yield {"error": str(exc), "finished": True}
    except Exception as exc:
        yield {"delta": f"⚠️ 改图异常：{exc}\n\n"}
        yield {"error": str(exc), "finished": True}


__all__ = ["run_chat_plot_edit", "stream_chat_plot_edit_deltas"]
