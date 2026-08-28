"""拆分同一条聊天中的改图 / 拼图指令。"""
from __future__ import annotations

import re

from web_frontend.backend.image_merge_registry import (
    looks_like_image_merge_request,
    looks_like_merged_figure_edit_request,
)
from web_frontend.backend.plot_edit_registry import looks_like_plot_edit_request

_PLOT_LABEL_RE = re.compile(r"^(?:改图|编辑图|plot\s*edit)\s*[:：]\s*", re.I)
_MERGE_LABEL_RE = re.compile(r"^(?:拼图|合并图|image\s*merge)\s*[:：]\s*", re.I)
_QUOTE_TRIM = "「」\"'“”"


def _strip_wrapping_quotes(text: str) -> str:
    s = (text or "").strip()
    while len(s) >= 2 and s[0] in _QUOTE_TRIM and s[-1] in _QUOTE_TRIM:
        s = s[1:-1].strip()
    return s


def _classify_visual_block(block: str) -> tuple[str | None, str | None]:
    """将单段文本归类为 (plot_edit, merge) 之一。"""
    line = _strip_wrapping_quotes(block)
    if not line:
        return None, None

    if _PLOT_LABEL_RE.search(line):
        return _PLOT_LABEL_RE.sub("", line, count=1).strip(), None
    if _MERGE_LABEL_RE.search(line):
        return None, _MERGE_LABEL_RE.sub("", line, count=1).strip()

    is_merge = looks_like_merged_figure_edit_request(line) or looks_like_image_merge_request(line)
    is_plot = looks_like_plot_edit_request(line)

    if is_plot and is_merge:
        # 同一段内同时出现改图与拼图关键词时，按「拼图/合并」切分
        parts = re.split(
            r"(?=(?:拼图|合并图?|image\s*merge)\s*[:：])",
            line,
            maxsplit=1,
            flags=re.I,
        )
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            plot_left = _PLOT_LABEL_RE.sub("", left, count=1).strip() if left else None
            merge_right = _MERGE_LABEL_RE.sub("", right, count=1).strip() if right else None
            if plot_left and looks_like_plot_edit_request(plot_left):
                plot_left = plot_left
            else:
                plot_left = left if looks_like_plot_edit_request(left) else None
            if merge_right and (
                looks_like_image_merge_request(merge_right)
                or looks_like_merged_figure_edit_request(merge_right)
            ):
                merge_right = merge_right
            else:
                merge_right = right if looks_like_image_merge_request(right) else None
            return plot_left, merge_right

    if is_merge and not is_plot:
        return None, line
    if is_plot:
        return line, None
    return None, None


def split_compound_visual_message(message: str) -> tuple[str | None, str | None]:
    """解析复合消息，返回 (改图文本, 拼图文本)。未识别的一侧为 None。"""
    text = (message or "").strip()
    if not text:
        return None, None

    plot_parts: list[str] = []
    merge_parts: list[str] = []

    blocks = [b.strip() for b in re.split(r"\n+", text) if b.strip()]
    if not blocks:
        blocks = [text]

    for block in blocks:
        plot_bit, merge_bit = _classify_visual_block(block)
        if plot_bit:
            plot_parts.append(plot_bit)
        if merge_bit:
            merge_parts.append(merge_bit)

    plot_msg = "\n".join(plot_parts).strip() or None
    merge_msg = "\n".join(merge_parts).strip() or None
    return plot_msg, merge_msg


__all__ = ["split_compound_visual_message"]
