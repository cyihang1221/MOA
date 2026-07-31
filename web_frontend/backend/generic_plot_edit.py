"""通用 Agent 改图：对无语义数据源的 PNG，基于 .editable.json + PIL 标题叠加。"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from src.platform_utils import normalize_display_path

from web_frontend.backend.anti_hallucination import (
    GENERIC_PLOT_EDIT_SYSTEM_GUARD,
    messages_with_system,
)
from web_frontend.backend.export.editable_export import (
    build_editable_metadata,
    editable_json_path,
)
from web_frontend.backend.json_parse import extract_first_json_object
from web_frontend.backend.session_storage import edited_plots_dir, session_work_dir
from web_frontend.backend.plot_versioning import (
    canonical_plot_base,
    find_effective_plot_rel,
    stable_intent_filename,
    write_current_pointer,
)
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


def _heuristic_title_patch(instruction: str) -> dict[str, Any] | None:
    """从「标题改成 XXX」类自然语言提取 patch，失败返回 None。"""
    text = (instruction or "").strip()
    if not text:
        return None
    patterns = [
        r"(?:把|将)?标题(?:改成|改为|修改为|设为|换成)\s*[「『\"“](.+?)[」』\"”]\s*$",
        r"(?:把|将)?标题(?:改成|改为|修改为|设为|换成)\s*[「『\"']?(.+?)[」』\"']?\s*$",
        r"(?:change|set)\s+(?:the\s+)?title\s+to\s+[\"']?(.+?)[\"']?\s*$",
        r"title\s*[:=]\s*[\"']?(.+?)[\"']?\s*$",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            title = m.group(1).strip().rstrip("。．.！!")
            if title and "字号" not in title and "放大" not in title:
                return {"title": title}
    return None


def _heuristic_font_size_patch(
    instruction: str,
    current_size: int,
) -> dict[str, Any] | None:
    text = (instruction or "").strip()
    if not text:
        return None
    cur = max(12, min(72, int(current_size or 28)))
    m = re.search(
        r"(?:标题)?(?:的)?(?:字号|字体大小|字体)?(?:再)?(?:放大|增大|增加|加大|加)\s*(\d+)",
        text,
    )
    if m:
        return {"title_size": min(72, cur + int(m.group(1)))}
    m = re.search(
        r"(?:标题)?(?:的)?(?:字号|字体大小|字体)?(?:再)?(?:缩小|减小|减少|减)\s*(\d+)",
        text,
    )
    if m:
        return {"title_size": max(12, cur - int(m.group(1)))}
    m = re.search(
        r"(?:标题)?(?:字号|字体大小|字体)\s*(?:改成|改为|设为|设置成|设置为|=|:|：)\s*(\d+)",
        text,
    )
    if m:
        return {"title_size": max(12, min(72, int(m.group(1))))}
    return None


def parse_generic_edit_instruction(
    *,
    instruction: str,
    current_meta: dict[str, Any],
    source_name: str,
    model: str | None = None,
) -> dict[str, Any]:
    if not instruction.strip():
        raise GenericPlotEditError("改图说明不能为空")

    cur_size = int(current_meta.get("title_size") or 28)
    font_patch = _heuristic_font_size_patch(instruction, cur_size)
    title_patch = _heuristic_title_patch(instruction)
    if font_patch and not title_patch:
        return font_patch

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
- 只改字号时不要返回 title，必须保留当前标题
- 「放大/缩小 N 个字号」基于当前 title_size 加减后输出绝对值
- 颜色必须是 #RRGGBB
- title_size 范围 12-72
- 不要编造源图路径；不要声称已重绘或已保存文件
- 不要 markdown 或解释文字
"""
    # 常见「改标题」指令可无 LLM，避免配置/网络问题时完全不可用
    heuristic = title_patch or font_patch
    try:
        llm = WebLLMClient(model=model)
        raw = llm.think_complete(
            messages_with_system(GENERIC_PLOT_EDIT_SYSTEM_GUARD, prompt),
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
    if font_patch and not title_patch:
        patch.pop("title", None)
        patch["title_size"] = font_patch["title_size"]
    elif title_patch and "title" not in patch:
        patch["title"] = title_patch["title"]
    return patch


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
    eff = find_effective_plot_rel(output_root, source_rel)
    use_rel = eff.get("effective_rel") or source_rel
    source = (output_root / use_rel).resolve()
    try:
        source.relative_to(output_root)
    except ValueError as exc:
        raise GenericPlotEditError("只能编辑会话输出目录中的图片") from exc
    if not source.is_file() or source.suffix.lower() != ".png":
        raise GenericPlotEditError(f"找不到 PNG：{source_rel}")

    current = _load_editable_meta(source)
    # 也尝试从同名 plot_config 继承标题（语义改图产物）
    cfg_sidecar = source.with_name(source.stem + ".plot_config.json")
    if cfg_sidecar.is_file():
        try:
            cfg = json.loads(cfg_sidecar.read_text(encoding="utf-8"))
            if isinstance(cfg, dict):
                if cfg.get("title") and not current.get("title"):
                    current["title"] = cfg["title"]
                fs = cfg.get("font_size")
                if isinstance(fs, dict) and fs.get("title") and not current.get("title_size"):
                    current["title_size"] = int(fs["title"])
                if cfg.get("source_rel") and not current.get("source_rel"):
                    current["source_rel"] = cfg["source_rel"]
        except Exception:
            pass

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
    base = eff.get("base") or canonical_plot_base(use_rel)
    out_name = filename or stable_intent_filename(base or source.stem)
    stem = Path(out_name).stem
    target = edit_dir / f"{stem}.png"
    # 稳定 intent 名覆盖写，避免 hash 分叉

    # 连续改图：叠字必须画在「干净原图」上，避免在已烧录标题的 intent 上再叠一层
    preserved = str(
        current.get("source_rel")
        or eff.get("original_rel")
        or use_rel
    )
    draw_base = source
    clean = (output_root / preserved).resolve()
    try:
        clean.relative_to(output_root)
        if clean.is_file() and clean.suffix.lower() == ".png":
            draw_base = clean
    except ValueError:
        pass

    _draw_title_on_image(
        draw_base,
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
    meta["source_rel"] = preserved
    meta["title_color"] = title_color
    meta["title_size"] = title_size
    meta["title_align"] = patch.get("title_align") or current.get("title_align") or "center"
    meta["last_instruction"] = instruction
    meta["edit_mode"] = "generic"
    sidecar = editable_json_path(target)
    sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    rel_png = target.relative_to(output_root).as_posix()
    if base:
        write_current_pointer(output_root, base, rel_png)

    before_keys = {
        "title": current.get("title"),
        "title_size": current.get("title_size"),
        "title_color": current.get("title_color"),
        "title_position": current.get("title_position"),
    }
    after_keys = {
        "title": title,
        "title_size": title_size,
        "title_color": title_color,
        "title_position": title_position,
    }
    changed = {
        k: {"from": before_keys[k], "to": after_keys[k]}
        for k in before_keys
        if before_keys[k] != after_keys[k]
    }
    config_diff = {
        "changed": changed,
        "added": {},
        "removed": {},
        "summary": "；".join(f"{k}: {v['from']!r} → {v['to']!r}" for k, v in changed.items())
        or "无字段变化",
    }

    stat = target.stat()
    return {
        "file": {
            "name": rel_png,
            "path": normalize_display_path(target),
            "size": stat.st_size,
        },
        "editable": {
            "name": sidecar.relative_to(output_root).as_posix(),
            "path": normalize_display_path(sidecar),
        },
        "source_rel": preserved,
        "effective_rel": rel_png,
        "plot_base": base,
        "plot_type": "generic",
        "edit_mode": "generic",
        "agent_patch": patch,
        "config_diff": config_diff,
    }


__all__ = [
    "GenericPlotEditError",
    "apply_generic_plot_edit",
    "parse_generic_edit_instruction",
]
