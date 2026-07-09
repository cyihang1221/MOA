"""会话级目录：项目根下 inputspace / outputspace，按 storage_slug 分子目录。"""
from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

INPUTSPACE_ROOT_NAME = "inputspace"
OUTPUTSPACE_ROOT_NAME = "outputspace"
# workspace 内旧版目录名
LEGACY_WORKSPACE_DIR_NAME = "workspace"
LEGACY_UPLOADS_ROOT_NAME = "uploads"
LEGACY_SESSIONS_ROOT_NAME = "sessions"

_INVALID_SLUG_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_DASH = re.compile(r"-+")


def default_session_title() -> str:
    now = datetime.now()
    return f"对话 {now.strftime('%m-%d %H:%M')}"


def slugify_title(title: str, max_len: int = 32) -> str:
    text = (title or "").strip()
    if not text:
        text = "session"
    text = _INVALID_SLUG_CHARS.sub("", text)
    text = text.replace(" ", "-").replace(".", "-")
    text = _MULTI_DASH.sub("-", text).strip("-._")
    if not text:
        text = "session"
    if len(text) > max_len:
        text = text[:max_len].rstrip("-._")
    return text or "session"


def make_storage_slug(session_id: str, title: str) -> str:
    short_id = (session_id or uuid.uuid4().hex)[:8]
    return f"{slugify_title(title)}_{short_id}"


_PLACEHOLDER_TITLE_MARKERS = (
    "请根据已上传",
    "请根据文件类型",
    "选择合适的工具",
)


def is_placeholder_session_title(title: str) -> bool:
    t = (title or "").strip()
    if not t or t in {"新会话", "默认会话"}:
        return True
    if t.startswith("对话 "):
        return True
    return any(m in t for m in _PLACEHOLDER_TITLE_MARKERS)


def derive_title_from_upload(filename: str, max_len: int = 24) -> str:
    stem = Path(filename).stem if filename else ""
    if not stem:
        return ""
    title = f"{stem} 质谱分析"
    if len(title) > max_len:
        return title[:max_len].rstrip() + "…"
    return title


def derive_title_from_message(text: str, max_len: int = 24) -> str:
    raw = (text or "").strip()
    for marker in ("[已上传附件]", "[Attachments uploaded]"):
        if marker in raw:
            raw = raw.split(marker)[0].strip()
    line = raw.split("\n")[0].strip()
    line = re.sub(r"\s+", " ", line)
    if not line:
        return ""
    if any(line.startswith(m) or m in line for m in _PLACEHOLDER_TITLE_MARKERS):
        return ""
    if len(line) > max_len:
        return line[:max_len].rstrip() + "…"
    return line


def inputspace_root(project_root: Path) -> Path:
    return project_root / INPUTSPACE_ROOT_NAME


def outputspace_root(project_root: Path) -> Path:
    return project_root / OUTPUTSPACE_ROOT_NAME


def session_upload_dir(project_root: Path, storage_slug: str) -> Path:
    path = inputspace_root(project_root) / storage_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def upload_target_dir(upload_root: Path, filename: str) -> Path:
    """.raw 放入 raw/ 子目录；metadata.csv 等仍放在会话根目录。"""
    if Path(filename).suffix.lower() == ".raw":
        dest = upload_root / "raw"
        dest.mkdir(parents=True, exist_ok=True)
        return dest
    return upload_root


def session_work_dir(project_root: Path, storage_slug: str) -> Path:
    path = outputspace_root(project_root) / storage_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


EDITED_PLOTS_SUBDIR = "edited_plots"
MERGED_FIGURES_SUBDIR = "merged_figures"


def edited_plots_dir(session_output_root: Path) -> Path:
    """会话内 Agent / 手动改图输出目录，与原始分析产物区分。"""
    path = session_output_root / EDITED_PLOTS_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def merged_figures_dir(session_output_root: Path) -> Path:
    """会话内 Agent / 手动拼图输出目录。"""
    path = session_output_root / MERGED_FIGURES_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _merge_tree_into(src: Path, dest: Path) -> None:
    if not src.is_dir():
        return
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dest / item.name
        if target.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    shutil.rmtree(src, ignore_errors=True)


def migrate_session_storage_dirs(project_root: Path) -> None:
    """
    将 workspace 下的 inputspace/outputspace 及 uploads/sessions 迁到项目根目录。
    """
    workspace = project_root / LEGACY_WORKSPACE_DIR_NAME
    migrations = [
        (inputspace_root(project_root), [
            workspace / INPUTSPACE_ROOT_NAME,
            workspace / LEGACY_UPLOADS_ROOT_NAME,
        ]),
        (outputspace_root(project_root), [
            workspace / OUTPUTSPACE_ROOT_NAME,
            workspace / LEGACY_SESSIONS_ROOT_NAME,
        ]),
    ]
    for dest_root, sources in migrations:
        dest_root.mkdir(parents=True, exist_ok=True)
        for src in sources:
            _merge_tree_into(src, dest_root)


def _candidate_dir_names(session_id: str, storage_slug: Optional[str]) -> list[str]:
    names: list[str] = []
    if storage_slug:
        names.append(storage_slug)
    if session_id and session_id not in names:
        names.append(session_id)
    return names


def _iter_input_roots(project_root: Path):
    workspace = project_root / LEGACY_WORKSPACE_DIR_NAME
    for p in (
        inputspace_root(project_root),
        workspace / INPUTSPACE_ROOT_NAME,
        workspace / LEGACY_UPLOADS_ROOT_NAME,
    ):
        if p.is_dir():
            yield p


def _iter_output_roots(project_root: Path):
    workspace = project_root / LEGACY_WORKSPACE_DIR_NAME
    for p in (
        outputspace_root(project_root),
        workspace / OUTPUTSPACE_ROOT_NAME,
        workspace / LEGACY_SESSIONS_ROOT_NAME,
    ):
        if p.is_dir():
            yield p


def rename_workspace_dirs(
    project_root: Path,
    session_id: str,
    old_slug: str,
    new_slug: str,
) -> None:
    if not new_slug or old_slug == new_slug:
        return
    for roots in (_iter_input_roots(project_root), _iter_output_roots(project_root)):
        seen: set[Path] = set()
        for root in roots:
            if root in seen:
                continue
            seen.add(root)
            old_path = root / old_slug
            new_path = root / new_slug
            if not old_path.exists():
                legacy = root / session_id
                if legacy.exists() and legacy != old_path:
                    old_path = legacy
            if old_path.exists() and old_path != new_path:
                if new_path.exists():
                    for item in old_path.iterdir():
                        dest = new_path / item.name
                        if dest.exists():
                            continue
                        if item.is_dir():
                            shutil.copytree(item, dest)
                        else:
                            shutil.copy2(item, dest)
                    shutil.rmtree(old_path, ignore_errors=True)
                else:
                    old_path.rename(new_path)


def delete_workspace_dirs(
    project_root: Path,
    session_id: str,
    storage_slug: Optional[str],
) -> None:
    for roots in (_iter_input_roots(project_root), _iter_output_roots(project_root)):
        seen: set[Path] = set()
        for root in roots:
            if root in seen:
                continue
            seen.add(root)
            for name in _candidate_dir_names(session_id, storage_slug):
                target = root / name
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)


def migrate_legacy_dirs_to_slug(
    project_root: Path,
    session_id: str,
    storage_slug: str,
) -> None:
    """将旧版 uuid 目录迁移到 slug 目录。"""
    if session_id == storage_slug:
        return
    rename_workspace_dirs(project_root, session_id, session_id, storage_slug)
