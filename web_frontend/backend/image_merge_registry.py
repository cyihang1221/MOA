"""聊天内 Agent 合并图片：意图识别与源图解析。"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from web_frontend.backend.plot_edit_registry import PLOT_ALIASES, plot_type_from_stem
from web_frontend.backend.session_storage import EDITED_PLOTS_SUBDIR, MERGED_FIGURES_SUBDIR

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

_IMAGE_MERGE_INTENT_RE = re.compile(
    r"(?:"
    r"合并(?:一下)?(?:图片|图|照片|子图|结果图|分析图|figure|figures|images?)|"
    r"合并.{0,120}(?:和|与|、|,|\+|以及|and).{0,120}(?:"
    r"\.(?:png|jpe?g|webp|gif)|图|plot|figure|image|distribution|diagram"
    r")|"
    r"合并\s+[\w./-]+\.(?:png|jpe?g|webp|gif)|"
    r"拼图|拼在一起|拼成(?:一张|1张)?(?:图|figure)?|"
    r"组合(?:成)?(?:一张|1张)?(?:图|figure)?|"
    r"一键合并|"
    r"merge\s+(?:the\s+)?(?:images?|figures?|plots?)|"
    r"merge.{0,120}(?:and|&|,).{0,120}(?:\.(?:png|jpe?g|webp)|plot|figure|image|distribution)|"
    r"combine\s+(?:the\s+)?(?:images?|figures?|plots?)|"
    r"make\s+(?:a\s+)?(?:composite|panel)\s+figure"
    r")",
    re.IGNORECASE,
)

_CN_COLS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

# 与改图区分：含「标题/颜色/色号/改图」等样式词时不走合并
_MERGE_EXCLUDE_STYLE_RE = re.compile(
    r"标题|颜色|色号|配色|#|改成|改为|改图|字号|字体|图例|recolor|font\s+size|change\s+(?:the\s+)?title",
    re.IGNORECASE,
)


DEFAULT_MERGE_OPTIONS: dict[str, Any] = {
    "cols": None,
    "label_mode": "upper",
    "label_font_size": 28,
    "gap": 24,
    "custom_labels": {},
}


def looks_like_merged_figure_edit_request(message: str) -> bool:
    """调整已拼合 figure 的标签、字号、列数等（非首次合并）。"""
    text = (message or "").strip()
    if not text:
        return False
    if re.search(
        r"(?:"
        r"改(?:一下)?拼图|调整(?:一下)?拼图|编辑拼图|修改拼图|更新拼图|"
        r"拼图.{0,24}(?:标签|字号|字大小|列|间距|legend|label|font)|"
        r"合并(?:后的|好的|完的)?图.{0,24}(?:标签|字号|列|间距)|"
        r"merged_figures/|merged_[\w-]+\.png|"
        r"edit(?:ing)?\s+(?:the\s+)?(?:merged|composite)\s+(?:figure|image|plot)"
        r")",
        text,
        re.IGNORECASE,
    ):
        return True
    # 「拼图/合并图」+ 样式调整词，但不是「合并 A 和 B」新建
    if re.search(r"拼图|合并图|merged\s+figure|composite\s+figure", text, re.IGNORECASE):
        if re.search(r"标签|字号|字大小|列|间距|legend|label|font\s*size|gap", text, re.IGNORECASE):
            if not re.search(
                r"合并.{0,80}(?:和|与|、|,|\+|以及|and).{0,80}(?:\.(?:png|jpe?g)|distribution|plot|figure|图)",
                text,
                re.IGNORECASE,
            ):
                return True
    return False


def looks_like_image_merge_request(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if looks_like_merged_figure_edit_request(text):
        return True
    if _MERGE_EXCLUDE_STYLE_RE.search(text):
        return False
    if _IMAGE_MERGE_INTENT_RE.search(text):
        return True
    # 合并 A 和 B（含 .png 文件名或 distribution 等 stem）
    if "合并" in text and re.search(r"(?:和|与|、|,|\+|以及|and)", text):
        if re.search(r"\.(?:png|jpe?g|webp|gif)\b", text, re.IGNORECASE):
            return True
        if re.search(
            r"(?:cosine|degree|pca|volcano|distribution|heatmap|network|plot|figure|图)",
            text,
            re.IGNORECASE,
        ):
            return True
    return False


def should_route_image_merge(message: str) -> bool:
    return looks_like_image_merge_request(message) or looks_like_merged_figure_edit_request(message)


def list_merged_figures(output_root: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    """扫描 merged_figures/ 中已保存的拼图及 sidecar。"""
    merge_dir = output_root / MERGED_FIGURES_SUBDIR
    if not merge_dir.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for png in sorted(merge_dir.glob("*.png")):
        meta_path = png.with_suffix(".merge.json")
        meta: dict[str, Any] | None = None
        if meta_path.is_file():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                meta = data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                meta = None
        rel = png.relative_to(output_root).as_posix()
        stat = png.stat()
        found.append(
            {
                "rel": rel,
                "name": png.name,
                "meta_rel": meta_path.relative_to(output_root).as_posix() if meta_path.is_file() else None,
                "sources": (meta or {}).get("sources") or [],
                "options": (meta or {}).get("options") or {},
                "modified": stat.st_mtime,
            }
        )
    found.sort(key=lambda item: item["modified"], reverse=True)
    return found[:limit]


def resolve_merged_figure_target(message: str, merged: list[dict[str, Any]]) -> str | None:
    if not merged:
        return None
    text = (message or "").strip()
    for item in merged:
        if item["name"] in text or item["rel"] in text:
            return item["rel"]
    if len(merged) == 1:
        return merged[0]["rel"]
    lower = text.lower()
    best_rel = None
    best_score = -1
    for item in merged:
        score = 0
        stem = Path(item["name"]).stem
        if stem in lower or stem.replace("_", "") in lower.replace("_", "").replace(" ", ""):
            score += 5
        if "merged_figures" in text and item["rel"] in text:
            score += 10
        if score > best_score:
            best_score = score
            best_rel = item["rel"]
    if best_score > 0:
        return best_rel
    return merged[0]["rel"]


def apply_merge_options(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = {**DEFAULT_MERGE_OPTIONS, **base}
    for key, val in patch.items():
        if val is None:
            continue
        if key == "custom_labels" and isinstance(val, dict):
            labels = dict(merged.get("custom_labels") or {})
            labels.update({str(k): str(v) for k, v in val.items()})
            merged["custom_labels"] = labels
        else:
            merged[key] = val
    return merged


def list_mergeable_images(output_root: Path, *, limit: int = 40) -> list[dict[str, Any]]:
    """扫描 outputspace 中可用于拼图的 PNG/JPG（排除 merged_figures 目录自身）。"""
    if not output_root.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        try:
            rel_parts = path.relative_to(output_root).parts
        except ValueError:
            continue
        if rel_parts and rel_parts[0] in {MERGED_FIGURES_SUBDIR}:
            continue
        rel = path.relative_to(output_root).as_posix()
        stem = path.stem
        stat = path.stat()
        found.append(
            {
                "rel": rel,
                "name": path.name,
                "stem": stem,
                "plot_type": plot_type_from_stem(stem),
                "modified": stat.st_mtime,
                "size": stat.st_size,
            }
        )
        if len(found) >= limit * 3:
            break
    found.sort(key=lambda item: item["modified"], reverse=True)
    return found[:limit]


def _alias_stems_from_message(message: str) -> list[str]:
    lower = message.lower()
    stems: list[str] = []
    seen: set[str] = set()
    for alias, stem in sorted(PLOT_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in lower or alias in message:
            if stem not in seen:
                seen.add(stem)
                stems.append(stem)
    return stems


def _match_images_by_stems(stems: list[str], images: list[dict[str, Any]]) -> list[str]:
    selected: list[str] = []
    used: set[str] = set()
    for stem in stems:
        for item in images:
            rel = item["rel"]
            if rel in used:
                continue
            item_stem = item["stem"]
            if item_stem == stem or item_stem.startswith(f"{stem}_"):
                selected.append(rel)
                used.add(rel)
                break
        if stem not in {Path(r).stem.split("_")[0] for r in selected}:
            for item in images:
                rel = item["rel"]
                if rel in used:
                    continue
                if stem.replace("_", "") in item["stem"].replace("_", ""):
                    selected.append(rel)
                    used.add(rel)
                    break
    return selected


def _match_images_by_filename(message: str, images: list[dict[str, Any]]) -> list[str]:
    """按消息中出现顺序匹配文件名 / stem / 相对路径。"""
    hits: list[tuple[int, str]] = []
    seen: set[str] = set()
    for item in images:
        rel = item["rel"]
        keys = [item["name"], item["stem"], rel]
        best_pos = -1
        for key in keys:
            if not key:
                continue
            pos = message.find(key)
            if pos >= 0 and (best_pos < 0 or pos < best_pos):
                best_pos = pos
        if best_pos >= 0 and rel not in seen:
            hits.append((best_pos, rel))
            seen.add(rel)
    hits.sort(key=lambda pair: pair[0])
    return [rel for _, rel in hits]


def _default_merge_selection(images: list[dict[str, Any]]) -> list[str]:
    """未指明具体图时：每个已知 stem 前缀取最新一张，至少 2 张。"""
    known_prefixes = set(PLOT_ALIASES.values())
    by_prefix: dict[str, dict[str, Any]] = {}
    for item in images:
        stem = item["stem"]
        prefix = stem
        for known in known_prefixes:
            if stem == known or stem.startswith(f"{known}_"):
                prefix = known
                break
        prev = by_prefix.get(prefix)
        if prev is None or item["modified"] > prev["modified"]:
            by_prefix[prefix] = item
    ordered = sorted(by_prefix.values(), key=lambda x: x["modified"], reverse=True)
    rels = [item["rel"] for item in ordered]
    if len(rels) >= 2:
        return rels
    return [item["rel"] for item in images[: max(2, len(images))]]


def resolve_merge_image_rels(message: str, images: list[dict[str, Any]]) -> list[str]:
    if not images:
        return []
    text = (message or "").strip()
    lower = text.lower()

    if re.search(r"所有|全部|all\s+(?:images?|figures?|plots?)", lower):
        return [item["rel"] for item in images[:12]]

    by_name = _match_images_by_filename(text, images)
    if by_name:
        return by_name[:12]

    alias_stems = _alias_stems_from_message(text)
    if alias_stems:
        picked = _match_images_by_stems(alias_stems, images)
        if len(picked) >= 2:
            return picked[:12]
        if picked:
            # 只提到一张时，补全其他最新图
            rest = [item["rel"] for item in images if item["rel"] not in picked]
            return (picked + rest)[:12]

    default = _default_merge_selection(images)
    return default[:12]


def parse_merge_options(message: str) -> dict[str, Any]:
    """从消息解析拼图参数；仅包含用户明确提到的字段。"""
    text = (message or "").strip()
    lower = text.lower()
    opts: dict[str, Any] = {}

    if re.search(r"不要标签|无标签|no\s+labels?", lower):
        opts["label_mode"] = "none"
    elif re.search(r"小写标签|标签(?:改成|改为|换成|用)?小写|abc|a,\s*b|lower\s+labels?", lower):
        opts["label_mode"] = "lower"
    elif re.search(r"大写标签|标签(?:改成|改为|换成|用)?大写|upper\s+labels?", lower):
        opts["label_mode"] = "upper"
    elif re.search(r"数字标签|\d+\s*[、,]\s*\d+|numeric\s+labels?", lower):
        opts["label_mode"] = "num"
    elif re.search(r"自定义标签|custom\s+labels?", lower):
        opts["label_mode"] = "custom"

    m = re.search(r"(?:标签|子图标签)(?:字号|大小|字体)?\s*(\d+)", text)
    if not m:
        m = re.search(r"(?:label|legend)\s*(?:font\s*)?size\s*(\d+)", lower)
    if m:
        opts["label_font_size"] = max(8, min(72, int(m.group(1))))

    m = re.search(r"(\d+)\s*列", text)
    if m:
        opts["cols"] = max(1, int(m.group(1)))
    else:
        m = re.search(r"([一二两三四五六七八九十]+)\s*列", text)
        if m:
            token = m.group(1)
            if token in _CN_COLS:
                opts["cols"] = _CN_COLS[token]
        elif re.search(r"(\d+)\s*columns?", lower):
            m = re.search(r"(\d+)\s*columns?", lower)
            if m:
                opts["cols"] = max(1, int(m.group(1)))
        elif re.search(r"一行|一排|single\s+row|one\s+row", lower):
            opts["cols"] = 99
        elif re.search(r"一列|single\s+column|one\s+column", lower):
            opts["cols"] = 1
        elif re.search(r"两列|二列", text):
            opts["cols"] = 2
        elif re.search(r"三列", text):
            opts["cols"] = 3

    m = re.search(r"间距\s*(\d+)", text)
    if m:
        opts["gap"] = max(0, min(120, int(m.group(1))))

    custom: dict[str, str] = {}
    for m in re.finditer(
        r"(?:第\s*([一二两三四12345678910]+)\s*(?:张|个|幅)|标签\s*([A-Da-d]))(?:的)?标签?(?:改成|改为|换成|设为|为)\s*[「\"']?([^」\"'\n,，]+)",
        text,
    ):
        idx_raw = m.group(1) or m.group(2)
        label_text = m.group(3).strip()
        if not label_text:
            continue
        if idx_raw in _CN_COLS:
            custom[str(_CN_COLS[idx_raw] - 1)] = label_text
        elif idx_raw.isdigit():
            custom[str(int(idx_raw) - 1 if int(idx_raw) > 0 else int(idx_raw))] = label_text
        elif len(idx_raw) == 1 and idx_raw.upper() in "ABCD":
            custom[str(ord(idx_raw.upper()) - ord("A"))] = label_text
    if custom:
        opts["custom_labels"] = custom
        opts["label_mode"] = "custom"

    return opts


def compute_cols(count: int, cols: int | None) -> int:
    if count <= 0:
        return 1
    if cols is None:
        return max(1, math.ceil(math.sqrt(count)))
    if cols >= count:
        return count
    return max(1, cols)


__all__ = [
    "DEFAULT_MERGE_OPTIONS",
    "looks_like_image_merge_request",
    "looks_like_merged_figure_edit_request",
    "should_route_image_merge",
    "list_mergeable_images",
    "list_merged_figures",
    "resolve_merge_image_rels",
    "resolve_merged_figure_target",
    "apply_merge_options",
    "parse_merge_options",
    "compute_cols",
]
