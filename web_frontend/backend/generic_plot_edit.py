"""通用 Agent 改图：对无语义数据源的 PNG，基于 .editable.json + PIL 标题叠加。"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from src.platform_utils import normalize_display_path

from web_frontend.backend.export.editable_export import (
    build_editable_metadata,
    editable_json_path,
)
from web_frontend.backend.json_parse import extract_first_json_object
from web_frontend.backend.session_storage import edited_plots_dir, session_work_dir
from web_frontend.backend.web_llm import WebLLMClient


class GenericPlotEditError(Exception):
    pass


def _load_editable_meta(png: Path) -> dict[str, Any]:
    sidecar = editable_json_path(png)
    if sidecar.is_file():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return build_editable_metadata(png, title=png.stem.replace("_", " "))


def parse_generic_edit_instruction(
    *,
    instruction: str,
    current_meta: dict[str, Any],
    source_name: str,
    model: str | None = None,
) -> dict[str, Any]:
    if not instruction.strip():
        raise GenericPlotEditError("改图说明不能为空")

    prompt = f"""你是图表样式编辑助手。根据用户要求，输出对可编辑图元数据的 JSON patch。
只输出一个 JSON 对象，不要 markdown。

当前图文件: {source_name}
当前元数据:
{json.dumps(current_meta, ensure_ascii=False, indent=2)}

用户要求:
{instruction.strip()}

可修改字段（只返回需要改的键）:
{{
  "title": "新标题",
  "title_position": "top-center|top-left|top-right|custom",
  "title_color": "#RRGGBB",
  "title_size": 28,
  "title_align": "left|center|right"
}}

规则:
- 未提及的字段不要返回
- 颜色必须是 #RRGGBB
- title_size 范围 12-72
"""
    # 常见「改标题」指令可无 LLM，避免配置/网络问题时完全不可用
    heuristic = _heuristic_title_patch(instruction)
    try:
        llm = WebLLMClient(model=model)
        raw = llm.think_complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1024,
        )
    except ValueError as exc:
        if heuristic:
            return heuristic
        raise GenericPlotEditError(str(exc)) from exc
    except Exception as exc:
        if heuristic:
            return heuristic
        raise GenericPlotEditError(f"LLM 调用失败：{exc}") from exc

    if not raw:
        if heuristic:
            return heuristic
        raise GenericPlotEditError("LLM 未返回有效内容，请检查 API 配置")
    patch = extract_first_json_object(raw)
    if not patch or not isinstance(patch, dict):
        if heuristic:
            return heuristic
        raise GenericPlotEditError(f"无法解析 Agent 返回：{raw[:400]}")
    return patch


def _heuristic_title_patch(instruction: str) -> dict[str, Any] | None:
    """从「标题改成 XXX」类自然语言提取 patch，失败返回 None。"""
    text = (instruction or "").strip()
    if not text:
        return None
    patterns = [
        r"(?:把|将)?标题(?:改成|改为|修改为|设为|换成)\s*[「『\"']?(.+?)[」』\"']?\s*$",
        r"(?:change|set)\s+(?:the\s+)?title\s+to\s+[\"']?(.+?)[\"']?\s*$",
        r"title\s*[:=]\s*[\"']?(.+?)[\"']?\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            title = m.group(1).strip().rstrip("。．.！!")
            if title:
                return {"title": title}
    return None


def _draw_title_on_image(
    source: Path,
    target: Path,
    *,
    title: str,
    title_color: str = "#111827",
    title_size: int = 28,
    title_position: str = "top-center",
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.open(source).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", title_size)
    except OSError:
        try:
            font = ImageFont.truetype("Arial.ttf", title_size)
        except OSError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), title, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    margin_x = max(12, image.width // 40)
    margin_y = max(10, image.height // 50)
    if title_position == "top-left":
        x = margin_x
    elif title_position == "top-right":
        x = max(margin_x, image.width - text_w - margin_x)
    else:
        x = max(margin_x, (image.width - text_w) // 2)
    y = margin_y

    # 半透明白底，避免标题看不清
    pad = 6
    draw.rectangle(
        [x - pad, y - pad, x + text_w + pad, y + text_h + pad],
        fill=(255, 255, 255, 180),
    )
    draw.text((x, y), title, fill=title_color, font=font)
    composed = Image.alpha_composite(image, overlay).convert("RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    composed.save(target, format="PNG")


def apply_generic_plot_edit(
    *,
    project_root: Path,
    storage_slug: str,
    source_rel: str,
    instruction: str,
    model: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    output_root = session_work_dir(project_root, storage_slug).resolve()
    source = (output_root / source_rel).resolve()
    try:
        source.relative_to(output_root)
    except ValueError as exc:
        raise GenericPlotEditError("只能编辑会话输出目录中的图片") from exc
    if not source.is_file() or source.suffix.lower() != ".png":
        raise GenericPlotEditError(f"找不到 PNG：{source_rel}")

    current = _load_editable_meta(source)
    patch = parse_generic_edit_instruction(
        instruction=instruction,
        current_meta=current,
        source_name=source.name,
        model=model,
    )

    title = str(patch.get("title") or current.get("title") or source.stem.replace("_", " "))
    title_position = str(patch.get("title_position") or current.get("title_position") or "top-center")
    title_color = str(patch.get("title_color") or current.get("title_color") or "#111827")
    title_size = int(patch.get("title_size") or current.get("title_size") or 28)
    title_size = max(12, min(72, title_size))

    edit_dir = edited_plots_dir(output_root)
    stem = Path(filename or f"{source.stem}_edited.png").stem
    target = edit_dir / f"{stem}.png"
    if target.exists():
        target = edit_dir / f"{stem}_{uuid.uuid4().hex[:8]}.png"

    _draw_title_on_image(
        source,
        target,
        title=title,
        title_color=title_color,
        title_size=title_size,
        title_position=title_position,
    )

    meta = build_editable_metadata(
        target,
        title=title,
        title_position=title_position,
        width=current.get("width"),
        height=current.get("height"),
        objects=current.get("objects") if isinstance(current.get("objects"), list) else [],
    )
    meta["source_rel"] = source_rel
    meta["title_color"] = title_color
    meta["title_size"] = title_size
    meta["title_align"] = patch.get("title_align") or current.get("title_align") or "center"
    meta["last_instruction"] = instruction
    meta["edit_mode"] = "generic"
    sidecar = editable_json_path(target)
    sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    stat = target.stat()
    return {
        "file": {
            "name": target.relative_to(output_root).as_posix(),
            "path": normalize_display_path(target),
            "size": stat.st_size,
        },
        "editable": {
            "name": sidecar.relative_to(output_root).as_posix(),
            "path": normalize_display_path(sidecar),
        },
        "source_rel": source_rel,
        "plot_type": "generic",
        "edit_mode": "generic",
        "agent_patch": patch,
    }


__all__ = [
    "GenericPlotEditError",
    "apply_generic_plot_edit",
    "parse_generic_edit_instruction",
]
