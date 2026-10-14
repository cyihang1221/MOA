"""会话级目录：项目根下 inputspace / outputspace，按 storage_slug 分子目录。"""
from __future__ import annotations

import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

IMPORTABLE_SUFFIXES = {
    ".raw",
    ".mzml",
    ".mzxml",
    ".mgf",
    ".csv",
    ".tsv",
    ".txt",
    ".xlsx",
    ".xls",
    ".pdf",
}
MAX_IMPORT_FILES = 500
MAX_IMPORT_DEPTH = 5

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


def collect_importable_files(source: Path) -> list[Path]:
    """收集服务器本地可导入的质谱/表格文件（不经浏览器上传）。"""
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"路径不存在：{source}")
    if source.is_file():
        if source.suffix.lower() not in IMPORTABLE_SUFFIXES:
            raise ValueError(f"不支持的文件类型：{source.suffix or source.name}")
        return [source]
    if not source.is_dir():
        raise ValueError("路径必须是文件或目录")

    files: list[Path] = []

    def walk(dir_path: Path, depth: int) -> None:
        if depth > MAX_IMPORT_DEPTH or len(files) >= MAX_IMPORT_FILES:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for item in entries:
            if len(files) >= MAX_IMPORT_FILES:
                return
            if item.name.startswith("."):
                continue
            try:
                if item.is_dir() and not item.is_symlink():
                    walk(item, depth + 1)
                elif item.is_file() and item.suffix.lower() in IMPORTABLE_SUFFIXES:
                    files.append(item)
            except OSError:
                continue

    walk(source, 0)
    if not files:
        raise FileNotFoundError("该路径下没有可导入的数据文件（raw / mzML / csv 等）")
    return files


def link_or_copy_file(src: Path, dest: Path) -> None:
    """同盘硬链接（瞬时、不占额外空间）；失败再复制。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        try:
            if dest.samefile(src):
                return
        except OSError:
            pass
        if dest.stat().st_size == src.stat().st_size:
            return
        dest.unlink()
    try:
        os.link(src, dest)
        return
    except OSError:
        shutil.copy2(src, dest)


def import_files_into_upload_dir(upload_root: Path, source: Path) -> list[dict]:
    """把服务器本地文件挂到会话 inputspace，返回 {name, path, size}。"""
    upload_root = upload_root.resolve()
    saved: list[dict] = []
    for src in collect_importable_files(source):
        filename = src.name.replace("/", "_").replace("\\", "_")
        dest_dir = upload_target_dir(upload_root, filename)
        dest = dest_dir / filename
        try:
            if dest.exists() and dest.samefile(src):
                saved.append(
                    {"name": filename, "path": str(dest), "size": dest.stat().st_size}
                )
                continue
        except OSError:
            pass
        if dest.exists() and dest.stat().st_size != src.stat().st_size:
            dest = dest_dir / f"{src.stem}_{uuid.uuid4().hex[:8]}{src.suffix}"
            filename = dest.name
        link_or_copy_file(src, dest)
        saved.append(
            {"name": filename, "path": str(dest), "size": dest.stat().st_size}
        )
    return saved


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
