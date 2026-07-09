"""聊天内触发的 Agent 合并/编辑拼图流程。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from web_frontend.backend.image_merge_registry import (
    list_mergeable_images,
    list_merged_figures,
    looks_like_merged_figure_edit_request,
)
from web_frontend.backend.image_merge_service import (
    ImageMergeError,
    agent_edit_merged_figure,
    agent_merge_images,
)


def stream_chat_image_merge_deltas(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    message: str,
    model: str | None = None,
) -> Iterator[dict[str, Any]]:
    from web_frontend.backend.session_storage import session_work_dir

    work_dir = session_work_dir(project_root, storage_slug).resolve()
    is_edit = looks_like_merged_figure_edit_request(message)

    if is_edit:
        yield {"delta": "**拼图编辑模式**：正在读取拼图参数并从原图重排…\n\n"}
    else:
        yield {"delta": "**拼图模式**：正在解析要合并的图片…\n\n"}

    try:
        if is_edit:
            merged_list = list_merged_figures(work_dir)
            if not merged_list:
                raise ImageMergeError(
                    "当前会话没有可编辑的拼图。请先在 merged_figures/ 生成拼图，"
                    "或说明要编辑的拼图文件名。"
                )
            yield {"delta": f"找到 **{len(merged_list)}** 张已保存拼图，正在应用修改…\n\n"}
            result = agent_edit_merged_figure(
                project_root=project_root,
                session_id=session_id,
                storage_slug=storage_slug,
                message=message,
                model=model,
            )
        else:
            available = list_mergeable_images(work_dir)
            if len(available) < 2:
                raise ImageMergeError(
                    "当前会话可合并的图片不足 2 张。请先完成分析，或在右侧输出文件区确认已有 PNG 结果图。"
                )
            yield {
                "delta": f"当前会话共有 **{len(available)}** 张可合并图片，正在自动选择并排版…\n\n"
            }
            result = agent_merge_images(
                project_root=project_root,
                session_id=session_id,
                storage_slug=storage_slug,
                message=message,
            )

        sources = result.get("sources") or []
        opts = result.get("options") or {}
        rel_png = result["file"]["name"]
        cols = result.get("cols_used")
        label_mode = opts.get("label_mode", "upper")
        patch = result.get("agent_patch") or {}

        source_lines = "\n".join(f"- `{rel}`" for rel in sources)
        summary_parts = []
        if patch.get("label_mode"):
            summary_parts.append(f"标签模式 → {patch['label_mode']}")
        if patch.get("label_font_size"):
            summary_parts.append(f"标签字号 → {patch['label_font_size']}")
        if patch.get("cols"):
            summary_parts.append(f"列数 → {patch['cols']}")
        if patch.get("gap"):
            summary_parts.append(f"间距 → {patch['gap']}")
        if patch.get("custom_labels"):
            summary_parts.append(f"自定义标签 {len(patch['custom_labels'])} 项")
        summary = "；".join(summary_parts) if summary_parts else ("已重排" if is_edit else "已合并")

        action = "更新" if is_edit else "写入"
        yield {
            "delta": (
                f"✅ 拼图已{action}（从原图真实重绘，非 LLM 模拟）\n"
                f"- 文件夹：`merged_figures/`\n"
                f"- 文件：`{rel_png}`\n"
                f"- {summary}\n"
                f"- 子图 **{len(sources)}** 张"
                f"{f'，{cols} 列排版' if cols else ''}"
                f"{'' if label_mode == 'none' else ''}\n"
                f"{source_lines}\n"
                f"- 可在图库点击 **AI 改拼图** 继续调整标签/字号\n\n"
            )
        }
        yield {"image_merge_done": True, "result": result, "finished": True, "edited": is_edit}
    except ImageMergeError as exc:
        yield {"delta": f"⚠️ 拼图失败：{exc}\n\n"}
        yield {"error": str(exc), "finished": True}
    except Exception as exc:
        yield {"delta": f"⚠️ 拼图异常：{exc}\n\n"}
        yield {"error": str(exc), "finished": True}


__all__ = ["stream_chat_image_merge_deltas"]
