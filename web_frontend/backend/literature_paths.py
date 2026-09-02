"""定位网页使用的文献库：项目根下的 softwares_database / softwares_database_RAG。

有 ``start`` 时只沿其父链查找，找不到再从本文件所在仓库根找。
不自动改去 MassOmics-Agent-B 目录；要用 B 的库时，把内容同步到这两份目录，
或设 ``WEB_LITERATURE_SOURCE_DIR`` / ``WEB_LITERATURE_PERSIST_DIR``。
"""
from __future__ import annotations

import os
from pathlib import Path


def _is_usable_source(path: Path) -> bool:
    if not path.is_dir():
        return False
    if (path / "repro_recipes").is_dir():
        return True
    if (path / "figure_index.txt").is_file() or (path / "figure_catalog.txt").is_file():
        return True
    if (path / "pipeline_overview.md").is_file():
        return True
    return any(path.glob("*.txt")) or any(path.glob("*.md"))


def _search_chain(start: Path) -> tuple[Path, Path] | None:
    """从 start 向父目录走，返回最近一层带 repro_recipes（或图目录）的库。"""
    fallback: tuple[Path, Path] | None = None
    cur = start.expanduser().resolve()
    for _ in range(8):
        source = cur / "softwares_database"
        persist = cur / "softwares_database_RAG"
        if _is_usable_source(source):
            persist_out = persist if persist.is_dir() else cur / "softwares_database_RAG"
            if (source / "repro_recipes").is_dir() or (source / "figure_catalog.txt").is_file():
                return persist_out, source
            if fallback is None:
                fallback = (persist_out, source)
        if cur.parent == cur:
            break
        cur = cur.parent
    return fallback


def resolve_literature_dirs(
    start: Path | str | None = None,
    *,
    allow_install_fallback: bool = True,
) -> tuple[str, str]:
    """返回 ``(persist_dir, source_dir)`` 字符串路径。

    优先级：
    1. ``WEB_LITERATURE_PERSIST_DIR`` / ``WEB_LITERATURE_SOURCE_DIR``
    2. 从 start 向父目录找（师兄仓嵌套布局会走到上级 ``softwares_database``）
    3. 从本模块所在仓库根向父目录找（``allow_install_fallback=True`` 时）
    """
    env_persist = (os.getenv("WEB_LITERATURE_PERSIST_DIR") or "").strip()
    env_source = (os.getenv("WEB_LITERATURE_SOURCE_DIR") or "").strip()
    if env_source and _is_usable_source(Path(env_source)):
        persist = Path(env_persist) if env_persist else Path(env_source).parent / "softwares_database_RAG"
        return str(persist), str(Path(env_source).resolve())

    if start is not None:
        hit = _search_chain(Path(start))
        if hit is not None:
            return str(hit[0]), str(hit[1])
        if not allow_install_fallback:
            root = Path(start).expanduser().resolve()
            return str(root / "softwares_database_RAG"), str(root / "softwares_database")

    here_root = Path(__file__).resolve().parents[2]
    hit = _search_chain(here_root)
    if hit is not None:
        return str(hit[0]), str(hit[1])

    return str(here_root / "softwares_database_RAG"), str(here_root / "softwares_database")


def resolve_phase2_registry(start: Path | str | None = None) -> Path:
    """定位 ``phase2_output/skill_registry.json``（含从嵌套仓向上查找）。"""
    env = (os.getenv("WEB_PHASE2_REGISTRY") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p.resolve()

    def _walk(origin: Path) -> Path | None:
        cur = origin.expanduser().resolve()
        for _ in range(8):
            cand = cur / "phase2_output" / "skill_registry.json"
            if cand.is_file():
                return cand
            if cur.parent == cur:
                break
            cur = cur.parent
        return None

    if start is not None:
        hit = _walk(Path(start))
        if hit is not None:
            return hit
        return Path(start).expanduser().resolve() / "phase2_output" / "skill_registry.json"

    here_root = Path(__file__).resolve().parents[2]
    return _walk(here_root) or (here_root / "phase2_output" / "skill_registry.json")


__all__ = ["resolve_literature_dirs", "resolve_phase2_registry"]
