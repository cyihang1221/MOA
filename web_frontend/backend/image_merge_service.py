"""Agent 聊天合并图片：PIL 自动排版并保存到 merged_figures/。"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.platform_utils import normalize_display_path

from web_frontend.backend.image_merge_registry import (
    DEFAULT_MERGE_OPTIONS,
    apply_merge_options,
    compute_cols,
    list_mergeable_images,
    list_merged_figures,
    parse_merge_options,
    resolve_merge_image_rels,
    resolve_merged_figure_target,
)
from web_frontend.backend.plot_fonts import _resolve_cjk_font_files
from web_frontend.backend.session_storage import merged_figures_dir, session_work_dir

MERGE_CANVAS_BG = (255, 255, 255)


class ImageMergeError(Exception):
    pass


def _panel_label(index: int, mode: str) -> str:
    if mode == "none":
        return ""
    if mode == "num":
        return str(index + 1)
    if mode == "lower":
        return chr(ord("a") + index % 26)
    return chr(ord("A") + index % 26)


def _load_label_font(size: int, *, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    regular, bold_path = _resolve_cjk_font_files()
    path = bold_path if bold and bold_path else regular
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _open_rgba(path: Path) -> Image.Image:
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return img


def merge_images_grid(
    image_paths: list[Path],
    *,
    source_rels: list[str] | None = None,
    cols: int | None = None,
    gap: int = 24,
    label_mode: str = "upper",
    label_font_size: int = 28,
    custom_labels: dict[str, str] | None = None,
    bg_color: tuple[int, int, int] = MERGE_CANVAS_BG,
) -> Image.Image:
    if len(image_paths) < 2:
        raise ImageMergeError("至少需要 2 张图片才能合并")

    images: list[tuple[Path, Image.Image, int, int]] = []
    for path in image_paths:
        img = _open_rgba(path)
        w, h = img.size
        if w <= 0 or h <= 0:
            raise ImageMergeError(f"无效图片尺寸：{path.name}")
        images.append((path, img, w, h))

    n = len(images)
    col_count = compute_cols(n, cols)
    label_pad = 0 if label_mode == "none" else label_font_size + 10
    cell_w = max(w for _, _, w, _ in images)
    cell_h = max(h for _, _, _, h in images)
    rows = (n + col_count - 1) // col_count

    placements: list[tuple[int, int, int, int]] = []
    for index, (_, _, w, h) in enumerate(images):
        col = index % col_count
        row = index // col_count
        x = gap + col * (cell_w + gap) + (cell_w - w) // 2
        y = gap + label_pad + row * (cell_h + label_pad + gap)
        placements.append((x, y, w, h))

    right_edge = max(x + w for x, _, w, _ in placements) + gap
    bottom_edge = max(y + h for _, y, _, h in placements) + gap
    canvas_w = max(right_edge, 200)
    canvas_h = max(bottom_edge, 150)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*bg_color, 255))
    draw = ImageDraw.Draw(canvas)
    font = _load_label_font(label_font_size, bold=True)

    custom_labels = custom_labels or {}

    for index, ((path, img, w, h), (x, y, _, _)) in enumerate(zip(images, placements)):
        canvas.paste(img, (x, y), img)
        rel_key = (source_rels[index] if source_rels and index < len(source_rels) else path.name)
        label = ""
        if label_mode != "none":
            if label_mode == "custom":
                label = custom_labels.get(str(index), custom_labels.get(rel_key, ""))
            else:
                label = _panel_label(index, label_mode)
            override = custom_labels.get(str(index)) or custom_labels.get(rel_key)
            if override:
                label = override
        if label:
            draw.text((x + 6, y - label_font_size - 6), label, fill="#111827", font=font)

    return canvas.convert("RGB")


def _suggest_merge_filename(sources: list[str], cols: int | None) -> str:
    parts: list[str] = []
    for rel in sources[:4]:
        stem = Path(rel).stem
        for suffix in ("_distribution", "_plot", "_edited"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        parts.append(stem[:16] or "img")
    slug = "_".join(parts)[:48] or "figure"
    col_suffix = f"_{cols}col" if cols else ""
    return f"merged_{slug}{col_suffix}.png"


def _resolve_output_png(output_root: Path, filename: str | None = None) -> Path:
    merge_dir = merged_figures_dir(output_root)
    stem = Path(filename or "merged_figure.png").stem
    target = merge_dir / f"{stem}.png"
    if target.exists():
        target = merge_dir / f"{stem}_{uuid.uuid4().hex[:8]}.png"
    return target


def _load_merge_meta(output_root: Path, target_rel: str) -> tuple[Path, dict[str, Any]]:
    png_path = (output_root / target_rel.strip().lstrip("/")).resolve()
    try:
        png_path.relative_to(output_root)
    except ValueError as exc:
        raise ImageMergeError("只能编辑 outputspace 中的拼图") from exc
    if not png_path.is_file() or png_path.suffix.lower() != ".png":
        raise ImageMergeError("目标必须是 PNG 拼图文件")
    meta_path = png_path.with_suffix(".merge.json")
    if not meta_path.is_file():
        raise ImageMergeError(
            f"找不到拼图参数文件 {meta_path.name}，无法 Agent 重绘。"
            "请使用带 .merge.json 的拼图，或重新合并生成。"
        )
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ImageMergeError("拼图参数 JSON 损坏") from exc
    if not isinstance(meta, dict):
        raise ImageMergeError("拼图参数格式无效")
    sources = meta.get("sources")
    if not isinstance(sources, list) or len(sources) < 2:
        raise ImageMergeError("拼图元数据缺少 sources，无法从原图重排")
    return png_path, meta


def _render_merged_figure(
    *,
    output_root: Path,
    sources: list[str],
    options: dict[str, Any],
) -> Image.Image:
    paths: list[Path] = []
    for rel in sources:
        path = (output_root / rel).resolve()
        if not path.is_file():
            raise ImageMergeError(f"拼图源图不存在：{rel}")
        paths.append(path)
    custom = options.get("custom_labels") or {}
    if not isinstance(custom, dict):
        custom = {}
    return merge_images_grid(
        paths,
        source_rels=sources,
        cols=options.get("cols"),
        gap=int(options.get("gap") or 24),
        label_mode=str(options.get("label_mode") or "upper"),
        label_font_size=int(options.get("label_font_size") or 28),
        custom_labels={str(k): str(v) for k, v in custom.items()},
    )


def agent_merge_images(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    message: str,
    filename: str | None = None,
) -> dict[str, Any]:
    output_root = session_work_dir(project_root, storage_slug).resolve()
    images = list_mergeable_images(output_root)
    if len(images) < 2:
        raise ImageMergeError(
            "当前会话可合并的图片不足 2 张。请先完成分析生成结果图，"
            "或在消息中指明要合并的图（如 PCA、火山图、余弦分布）。"
        )

    rels = resolve_merge_image_rels(message, images)
    if len(rels) < 2:
        raise ImageMergeError(
            f"仅匹配到 {len(rels)} 张图片，合并至少需要 2 张。"
            "请明确说明要合并哪些图，例如：「合并 PCA 和火山图」。"
        )

    opts = apply_merge_options(DEFAULT_MERGE_OPTIONS, parse_merge_options(message))
    paths: list[Path] = []
    for rel in rels:
        path = (output_root / rel).resolve()
        try:
            path.relative_to(output_root)
        except ValueError as exc:
            raise ImageMergeError(f"非法图片路径：{rel}") from exc
        if not path.is_file():
            raise ImageMergeError(f"找不到图片：{rel}")
        paths.append(path)

    merged = _render_merged_figure(output_root=output_root, sources=rels, options=opts)

    cols_used = compute_cols(len(rels), opts.get("cols"))
    out_name = filename or _suggest_merge_filename(rels, cols_used)
    target_png = _resolve_output_png(output_root, out_name)
    target_png.parent.mkdir(parents=True, exist_ok=True)
    merged.save(target_png, format="PNG", optimize=True)

    meta = {
        "version": 1,
        "type": "merged_figure",
        "sources": rels,
        "options": opts,
        "instruction": message,
    }
    meta_path = target_png.with_suffix(".merge.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    stat = target_png.stat()
    rel_png = target_png.relative_to(output_root).as_posix()
    return {
        "file": {
            "name": rel_png,
            "path": normalize_display_path(target_png),
            "size": stat.st_size,
        },
        "meta": {
            "name": meta_path.relative_to(output_root).as_posix(),
            "path": normalize_display_path(meta_path),
        },
        "sources": rels,
        "options": opts,
        "cols_used": cols_used,
    }


def agent_edit_merged_figure(
    *,
    project_root: Path,
    session_id: str,
    storage_slug: str,
    message: str,
    target_rel: str | None = None,
    model: str | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    output_root = session_work_dir(project_root, storage_slug).resolve()
    merged_list = list_merged_figures(output_root)
    if not merged_list:
        raise ImageMergeError("当前会话没有可编辑的拼图。请先在 merged_figures/ 中生成拼图。")

    rel = target_rel or resolve_merged_figure_target(message, merged_list)
    if not rel:
        raise ImageMergeError("未找到要编辑的拼图")

    png_path, meta = _load_merge_meta(output_root, rel)
    sources = [str(s) for s in meta.get("sources") or []]
    current_opts = apply_merge_options(DEFAULT_MERGE_OPTIONS, meta.get("options") or {})

    rule_patch = parse_merge_options(message)
    llm_patch: dict[str, Any] = {}
    if use_llm and message.strip():
        try:
            from web_frontend.backend.image_merge_agent import parse_merge_edit_instruction

            llm_patch = parse_merge_edit_instruction(
                instruction=message,
                current_options=current_opts,
                sources=sources,
                model=model,
            )
        except Exception:
            llm_patch = {}

    opts = apply_merge_options(current_opts, rule_patch)
    opts = apply_merge_options(opts, llm_patch)

    merged = _render_merged_figure(output_root=output_root, sources=sources, options=opts)
    merged.save(png_path, format="PNG", optimize=True)

    meta_path = png_path.with_suffix(".merge.json")
    history = meta.get("edit_history") if isinstance(meta.get("edit_history"), list) else []
    history.append({"instruction": message, "options": opts})
    meta.update(
        {
            "options": opts,
            "last_instruction": message,
            "edit_history": history[-10:],
        }
    )
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    stat = png_path.stat()
    rel_png = png_path.relative_to(output_root).as_posix()
    return {
        "file": {
            "name": rel_png,
            "path": normalize_display_path(png_path),
            "size": stat.st_size,
        },
        "meta": {
            "name": meta_path.relative_to(output_root).as_posix(),
            "path": normalize_display_path(meta_path),
        },
        "sources": sources,
        "options": opts,
        "cols_used": compute_cols(len(sources), opts.get("cols")),
        "agent_patch": {**rule_patch, **llm_patch},
        "edited": True,
    }


__all__ = ["ImageMergeError", "agent_merge_images", "agent_edit_merged_figure", "merge_images_grid"]
