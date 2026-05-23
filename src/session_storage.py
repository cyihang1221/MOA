"""会话级 workspace 目录：按可读 slug 命名 uploads / sessions。"""
from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

UPLOADS_ROOT_NAME = "uploads"
SESSIONS_ROOT_NAME = "sessions"

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


def derive_title_from_message(text: str, max_len: int = 24) -> str:
    raw = (text or "").strip()
    if "[已上传附件]" in raw:
        raw = raw.split("[已上传附件]")[0].strip()
    line = raw.split("\n")[0].strip()
    line = re.sub(r"\s+", " ", line)
    if not line:
        return ""
    if len(line) > max_len:
        return line[:max_len].rstrip() + "…"
    return line


def session_upload_dir(workspace_root: Path, storage_slug: str) -> Path:
    path = workspace_root / UPLOADS_ROOT_NAME / storage_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_work_dir(workspace_root: Path, storage_slug: str) -> Path:
    path = workspace_root / SESSIONS_ROOT_NAME / storage_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _candidate_dir_names(session_id: str, storage_slug: Optional[str]) -> list[str]:
    names: list[str] = []
    if storage_slug:
        names.append(storage_slug)
    if session_id and session_id not in names:
        names.append(session_id)
    return names


def rename_workspace_dirs(
    workspace_root: Path,
    session_id: str,
    old_slug: str,
    new_slug: str,
) -> None:
    if not new_slug or old_slug == new_slug:
        return
    for root_name in (UPLOADS_ROOT_NAME, SESSIONS_ROOT_NAME):
        root = workspace_root / root_name
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
    workspace_root: Path,
    session_id: str,
    storage_slug: Optional[str],
) -> None:
    for root_name in (UPLOADS_ROOT_NAME, SESSIONS_ROOT_NAME):
        root = workspace_root / root_name
        for name in _candidate_dir_names(session_id, storage_slug):
            target = root / name
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)


def migrate_legacy_dirs_to_slug(
    workspace_root: Path,
    session_id: str,
    storage_slug: str,
) -> None:
    """将旧版 uuid 目录迁移到 slug 目录。"""
    if session_id == storage_slug:
        return
    rename_workspace_dirs(workspace_root, session_id, session_id, storage_slug)
