"""结果图「当前生效版本」：intent/edited 优先于原始分析 PNG。

规则（同 canonical base）：
1. edited_plots/{base}.current.json 指针（若存在且文件仍在）
2. edited_plots 中最新的 ``{base}_intent*.png`` / ``{base}_edited*.png``
3. 原始分析目录中的 ``{base}.png``
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from web_frontend.backend.session_storage import EDITED_PLOTS_SUBDIR, edited_plots_dir

_INTENT_OR_EDITED_RE = re.compile(
    r"^(?P<base>.+?)_(?:intent|edited)(?:_[a-f0-9]{6,12})?$",
    re.IGNORECASE,
)
_HASH_SUFFIX_RE = re.compile(r"_[a-f0-9]{6,12}$", re.IGNORECASE)


def canonical_plot_base(name_or_stem: str) -> str:
    """pca_plot_intent_abc123 / pca_plot_edited → pca_plot；pca_plot.png → pca_plot。"""
    stem = Path(str(name_or_stem or "").strip()).stem
    if not stem:
        return ""
    m = _INTENT_OR_EDITED_RE.match(stem)
    if m:
        return m.group("base")
    return stem


def is_derived_plot_name(name_or_rel: str) -> bool:
    name = Path(str(name_or_rel or "")).name
    stem = Path(name).stem
    return bool(_INTENT_OR_EDITED_RE.match(stem)) or EDITED_PLOTS_SUBDIR in str(
        name_or_rel or ""
    ).replace("\\", "/")


def current_pointer_path(output_root: Path, base: str) -> Path:
    return edited_plots_dir(output_root) / f"{base}.current.json"


def read_current_pointer(output_root: Path, base: str) -> str | None:
    path = current_pointer_path(output_root, base)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    rel = str((data or {}).get("rel") or "").strip().lstrip("/")
    if not rel:
        return None
    candidate = (output_root / rel).resolve()
    try:
        candidate.relative_to(output_root.resolve())
    except ValueError:
        return None
    if candidate.is_file() and candidate.suffix.lower() == ".png":
        return Path(rel).as_posix()
    return None


def write_current_pointer(output_root: Path, base: str, rel: str) -> None:
    if not base or not rel:
        return
    edit_dir = edited_plots_dir(output_root)
    payload = {
        "base": base,
        "rel": Path(rel).as_posix(),
    }
    (edit_dir / f"{base}.current.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def list_derived_pngs(output_root: Path, base: str) -> list[Path]:
    edit_dir = edited_plots_dir(output_root)
    if not edit_dir.is_dir() or not base:
        return []
    out: list[Path] = []
    for png in edit_dir.glob("*.png"):
        if canonical_plot_base(png.name) == base and is_derived_plot_name(png.name):
            out.append(png)
    out.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return out


def find_original_plot_rel(output_root: Path, base: str) -> str | None:
    """在非 edited/merged 目录找 ``{base}.png``（最新）。"""
    from web_frontend.backend.session_storage import MERGED_FIGURES_SUBDIR

    if not output_root.is_dir() or not base:
        return None
    matches: list[Path] = []
    for png in output_root.rglob(f"{base}.png"):
        parts = png.relative_to(output_root).parts
        if parts and parts[0] in {EDITED_PLOTS_SUBDIR, MERGED_FIGURES_SUBDIR}:
            continue
        if png.stem != base:
            continue
        matches.append(png)
    if not matches:
        return None
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0].relative_to(output_root).as_posix()


def find_effective_plot_rel(
    output_root: Path,
    hint_rel_or_name: str | None,
) -> dict[str, Any]:
    """解析当前生效图。

    返回::
        {
          "base": str,
          "effective_rel": str | None,   # 聊天/图库/连续改图应使用
          "original_rel": str | None,    # 分析原图（数据目录）
          "is_derived": bool,
        }
    """
    hint = str(hint_rel_or_name or "").strip().lstrip("/")
    base = canonical_plot_base(Path(hint).name if hint else "")
    if not base and hint:
        base = canonical_plot_base(hint)

    original_rel = find_original_plot_rel(output_root, base) if base else None
    pointer = read_current_pointer(output_root, base) if base else None
    derived = list_derived_pngs(output_root, base) if base else []

    effective: str | None = None
    if pointer:
        effective = pointer
    elif derived:
        effective = derived[0].relative_to(output_root).as_posix()
    elif original_rel:
        effective = original_rel
    elif hint:
        candidate = (output_root / hint).resolve()
        try:
            candidate.relative_to(output_root.resolve())
            if candidate.is_file():
                effective = Path(hint).as_posix()
        except ValueError:
            pass

    return {
        "base": base,
        "effective_rel": effective,
        "original_rel": original_rel,
        "is_derived": bool(effective and is_derived_plot_name(effective)),
    }


def stable_intent_filename(base: str) -> str:
    """连续改图固定写入名，避免无限 hash 分叉。"""
    return f"{canonical_plot_base(base) or base}_intent.png"


def prefer_effective_among_rels(rels: list[str]) -> list[str]:
    """同 base 只保留一份：derived/intent 优先，同为 derived 时保留列表中后者（通常更新）。"""
    chosen: dict[str, str] = {}
    order: list[str] = []
    for rel in rels:
        clean = str(rel or "").strip()
        if not clean:
            continue
        base = canonical_plot_base(clean) or clean.lower()
        prev = chosen.get(base)
        if prev is None:
            chosen[base] = clean
            order.append(base)
            continue
        if is_derived_plot_name(clean) and not is_derived_plot_name(prev):
            chosen[base] = clean
        elif is_derived_plot_name(clean) and is_derived_plot_name(prev):
            # 后写入覆盖（流式先原图后 intent）
            chosen[base] = clean
    return [chosen[b] for b in order if b in chosen]


__all__ = [
    "canonical_plot_base",
    "is_derived_plot_name",
    "current_pointer_path",
    "read_current_pointer",
    "write_current_pointer",
    "list_derived_pngs",
    "find_original_plot_rel",
    "find_effective_plot_rel",
    "stable_intent_filename",
    "prefer_effective_among_rels",
]
