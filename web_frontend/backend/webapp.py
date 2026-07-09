import base64
import binascii
import os
import json
import re
import sqlite3
import sys
import threading
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from web_frontend.backend.agent_intent import looks_like_agent_request
from web_frontend.backend.agent_jobs import cancel_job, clear_job, is_cancelled, register_job
from web_frontend.backend.session_storage import (
    default_session_title,
    delete_workspace_dirs,
    derive_title_from_message,
    derive_title_from_upload,
    is_placeholder_session_title,
    INPUTSPACE_ROOT_NAME,
    OUTPUTSPACE_ROOT_NAME,
    make_storage_slug,
    migrate_legacy_dirs_to_slug,
    migrate_session_storage_dirs,
    rename_workspace_dirs,
    session_upload_dir as storage_upload_dir,
    session_work_dir,
    edited_plots_dir,
    merged_figures_dir,
    upload_target_dir,
)

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web_frontend.backend.web_llm import WebLLMClient as LLM_Client
from src.mcp_server.server import mcp
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from src.platform_utils import check_agent_runtime, mcp_stdio_parameters, normalize_display_path


load_dotenv(find_dotenv(), override=False)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = WEB_ROOT / "static"
DB_PATH = WEB_ROOT / "data" / "sessions.sqlite3"
DB_LOCK = threading.Lock()
INPUTSPACE_ROOT = PROJECT_ROOT / INPUTSPACE_ROOT_NAME
OUTPUTSPACE_ROOT = PROJECT_ROOT / OUTPUTSPACE_ROOT_NAME
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
DATABASE_FILE_DIR = PROJECT_ROOT / "database_file"
REFERENCE_MGF_PATH = DATABASE_FILE_DIR / "spectraverse-1.0.1.mgf"
METHOD_COMPARE_DIR = WORKSPACE_DIR / "library_matching_method_compare"
BASE_DIR = PROJECT_ROOT

app = FastAPI(title="MassAgent Web UI")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              model TEXT,
              temperature REAL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              time TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        try:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN is_shared INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN storage_slug TEXT")
        except sqlite3.OperationalError:
            pass


def db_list_sessions() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, title, updated_at, is_shared, storage_slug FROM sessions ORDER BY updated_at DESC, created_at DESC"
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "updated_at": r["updated_at"],
                "is_shared": bool(r["is_shared"]),
                "storage_slug": r["storage_slug"] or r["id"],
            }
            for r in rows
        ]


def db_get_session(session_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, title, model, temperature, created_at, updated_at, is_shared, storage_slug FROM sessions WHERE id=?",
            (session_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        data = dict(r)
        data["is_shared"] = bool(data.get("is_shared"))
        if not data.get("storage_slug"):
            data["storage_slug"] = session_id
        return data


def db_set_storage_slug(session_id: str, storage_slug: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE sessions SET storage_slug=? WHERE id=?",
            (storage_slug, session_id),
        )


def db_create_session(title: str, model: Optional[str], temperature: float) -> str:
    session_id = uuid.uuid4().hex
    storage_slug = make_storage_slug(session_id, title)
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, title, model, temperature, created_at, updated_at, storage_slug)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, title, model, temperature, now, now, storage_slug),
        )
    storage_upload_dir(PROJECT_ROOT, storage_slug)
    session_work_dir(PROJECT_ROOT, storage_slug)
    return session_id


def db_rename_session(session_id: str, title: str) -> None:
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "UPDATE sessions SET title=?, updated_at=? WHERE id=?",
            (title, now, session_id),
        )
        if cur.rowcount == 0:
            raise KeyError(session_id)


def db_delete_session(session_id: str) -> None:
    sess = db_get_session(session_id)
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        if cur.rowcount == 0:
            raise KeyError(session_id)
    if sess:
        delete_workspace_dirs(
            PROJECT_ROOT,
            session_id,
            sess.get("storage_slug"),
        )


def db_clear_session_messages(session_id: str) -> None:
    """
    清空会话消息（不删会话本身），并重置为“新会话”状态。
    """
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        # 确保 session 存在
        cur = conn.execute("SELECT id FROM sessions WHERE id=?", (session_id,))
        if cur.fetchone() is None:
            raise KeyError(session_id)

        conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        new_title = default_session_title()
        new_slug = make_storage_slug(session_id, new_title)
        old_sess = db_get_session(session_id)
        old_slug = (old_sess or {}).get("storage_slug") or session_id
        conn.execute(
            "UPDATE sessions SET title=?, updated_at=?, storage_slug=? WHERE id=?",
            (new_title, now, new_slug, session_id),
        )
        if old_sess:
            rename_workspace_dirs(PROJECT_ROOT, session_id, old_slug, new_slug)

        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, time, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "assistant",
                "会话已清空，请重新提问。",
                now,
                now,
            ),
        )


def db_set_session_shared(session_id: str, shared: bool) -> None:
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "UPDATE sessions SET is_shared=?, updated_at=? WHERE id=?",
            (1 if shared else 0, now, session_id),
        )
        if cur.rowcount == 0:
            raise KeyError(session_id)


def db_get_messages(session_id: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT id, role, content, time, created_at
            FROM messages
            WHERE session_id=?
            ORDER BY id ASC
            """,
            (session_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "time": r["time"],
            }
            for r in rows
        ]


def db_get_shared_messages(session_id: str) -> Optional[dict]:
    sess = db_get_session(session_id)
    if not sess or not sess.get("is_shared"):
        return None
    return {
        "session": {"id": sess["id"], "title": sess["title"], "is_shared": True},
        "messages": db_get_messages(session_id),
    }


def db_append_message(session_id: str, role: str, content: str) -> str:
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO messages (session_id, role, content, time, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, role, content, now, now),
        )
        conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
    return now


def maybe_update_title_from_first_user_message(session_id: str, new_title: str) -> None:
    sess = db_get_session(session_id)
    if not sess or not new_title:
        return
    current_title = (sess.get("title") or "").strip()
    if not is_placeholder_session_title(current_title):
        return
    old_slug = sess.get("storage_slug") or session_id
    db_rename_session(session_id, new_title)
    new_slug = make_storage_slug(session_id, new_title)
    db_set_storage_slug(session_id, new_slug)
    migrate_legacy_dirs_to_slug(PROJECT_ROOT, session_id, new_slug)
    rename_workspace_dirs(PROJECT_ROOT, session_id, old_slug, new_slug)


def db_update_message(message_id: int, content: str) -> None:
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "UPDATE messages SET content=?, time=? WHERE id=?",
            (content, now, message_id),
        )
        if cur.rowcount == 0:
            raise KeyError(message_id)


def db_get_message(message_id: int) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, session_id, role, content, time FROM messages WHERE id=?",
            (message_id,),
        )
        r = cur.fetchone()
        return dict(r) if r else None


def db_truncate_messages_after(session_id: str, message_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "DELETE FROM messages WHERE session_id=? AND id>?",
            (session_id, message_id),
        )


def resolve_storage_slug(session_id: str) -> str:
    sess = db_get_session(session_id)
    if not sess:
        return session_id
    slug = sess.get("storage_slug") or session_id
    migrate_legacy_dirs_to_slug(PROJECT_ROOT, session_id, slug)
    if not sess.get("storage_slug"):
        db_set_storage_slug(session_id, slug)
    return slug


init_db()
migrate_session_storage_dirs(PROJECT_ROOT)


def get_env_or_default_spec2vec_model_path() -> str:
    return os.getenv(
        "SPEC2VEC_MODEL_PATH",
        str(BASE_DIR / "softwares" / "spec2vec-0.9.1" / "models" / "spec2vec.model"),
    )


def get_env_or_default_ms2deepscore_model_path() -> str:
    return os.getenv(
        "MS2DEEPSCORE_MODEL_PATH",
        str(BASE_DIR / "softwares" / "ms2deepscore" / "ms2deepscore_model.pt"),
    )


def allowed_methods_default() -> list[dict]:
    return [
        {"method": "jaccard", "model_path": ""},
        {"method": "cosine", "model_path": ""},
        {"method": "spectral entropy", "model_path": ""},
        {"method": "blink", "model_path": ""},
        {"method": "spec2vec", "model_path": get_env_or_default_spec2vec_model_path()},
        {"method": "ms2deepscore", "model_path": get_env_or_default_ms2deepscore_model_path()},
    ]


def safe_filename(name: str) -> str:
    # 简单防御：去掉路径分隔符，避免目录穿越
    return name.replace("/", "_").replace("\\", "_")


class ShareSessionRequest(BaseModel):
    shared: bool = True


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.0


class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.0


class RenameSessionRequest(BaseModel):
    title: str


class ChatStreamRequest(BaseModel):
    session_id: str
    user_message: str
    model: Optional[str] = None
    temperature: float = 0.0
    use_agent: bool = False  # True 时走 MCP 工具执行，而非纯 LLM 对话
    edit_message_id: Optional[int] = None  # 编辑用户消息后重发：更新该条并截断其后
    regenerate_assistant: bool = False  # 基于最后一条用户消息重新生成回答


class UpdateMessageRequest(BaseModel):
    content: str
    truncate_following: bool = False  # 编辑后删除该条之后的所有消息


class ImageEditSaveRequest(BaseModel):
    source_rel: str
    image_data: str
    filename: Optional[str] = None
    edit_state: Optional[dict] = None


class PlotlyEditSaveRequest(BaseModel):
    source_rel: str
    figure_json: dict
    image_data: str
    filename: Optional[str] = None


class PlotEditAgentRequest(BaseModel):
    source_rel: str
    instruction: str
    filename: Optional[str] = None


class ImageMergeEditRequest(BaseModel):
    source_rel: str
    instruction: str


def parse_models_from_env() -> List[str]:
    configured = os.getenv("LLM_MODEL_CANDIDATES", "")
    values = [item.strip() for item in configured.split(",") if item.strip()]
    default_model = os.getenv("LLM_MODEL_ID", "").strip()
    if default_model and default_model not in values:
        values.insert(0, default_model)
    return values


def categorize_tool(name: str) -> str:
    """返回稳定分类 ID，前端用 i18n 显示中英文名称。"""
    if name.startswith("convert_") or name.startswith("mzml_"):
        return "convert"
    if name.startswith("molecular_networking"):
        return "networking"
    if name.startswith("deepmass"):
        return "deeplearn"
    if name in ALLOWED_TOOL_NAMES or name.startswith(
        ("data_preprocessing", "feature_filtering", "statistical_analysis", "extract_differential", "spectral_annotation", "kegg_compound")
    ):
        return "xcms"
    if name.startswith("peak_detection"):
        return "peaks"
    if any(
        key in name
        for key in (
            "filter_redundant",
            "align_retention",
            "group_peaks",
            "fill_missing",
            "identify_isotopes",
        )
    ):
        return "processing"
    if name.startswith("library_match"):
        return "library"
    if "mzmine" in name:
        return "workflow"
    return "other"


def categorize_tool_legacy(name: str) -> str:
    """兼容旧版中文分类名。"""
    legacy = {
        "convert": "数据转换",
        "xcms": "XCMS 数据分析",
        "peaks": "峰检测",
        "processing": "峰处理与注释",
        "library": "谱库匹配",
        "workflow": "流程编排",
        "other": "其他工具",
    }
    return legacy.get(categorize_tool(name), "其他工具")


from web_frontend.backend.constants import ALLOWED_TOOL_NAMES


def session_upload_dir(session_id: str) -> Path:
    slug = resolve_storage_slug(session_id)
    return storage_upload_dir(PROJECT_ROOT, slug)


def list_session_files(session_id: str) -> list[dict]:
    folder = session_upload_dir(session_id)
    items = []
    for item in sorted(folder.iterdir()):
        if item.is_file():
            items.append(
                {
                    "name": item.name,
                    "path": normalize_display_path(item),
                    "size": item.stat().st_size,
                }
            )
    return items


def _collect_tree_files(root: Path, max_files: int = 800) -> list[dict]:
    if not root.is_dir():
        return []
    files: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        stat = path.stat()
        files.append(
            {
                "name": rel,
                "path": normalize_display_path(path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds"),
            }
        )
        if len(files) >= max_files:
            break
    return files


def get_session_workspace_files(session_id: str) -> dict:
    slug = resolve_storage_slug(session_id)
    upload_root = storage_upload_dir(PROJECT_ROOT, slug)
    output_root = session_work_dir(PROJECT_ROOT, slug)
    return {
        "storage_slug": slug,
        "inputs_dir": normalize_display_path(upload_root),
        "outputs_dir": normalize_display_path(output_root),
        "inputs": _collect_tree_files(upload_root),
        "outputs": _collect_tree_files(output_root),
    }


@app.get("/")
def index():
    return FileResponse(str(WEB_ROOT / "index.html"))


@app.get("/favicon.ico")
def favicon():
    icon = STATIC_DIR / "favicon.svg"
    if icon.is_file():
        return FileResponse(icon, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="favicon not found")


@app.get("/api/info")
def app_info():
    runtime = check_agent_runtime()
    return {
        "name": "MassAgent Web UI",
        "share_hint": "分享给他人时，请用 uvicorn --host 0.0.0.0 启动，并将链接中的 127.0.0.1 换成本机局域网 IP。",
        "reference": "https://github.com/hcji/DeepMASS2_GUI",
        "runtime": runtime,
    }


@app.get("/api/tools")
async def get_tools():
    from web_frontend.backend.tool_registry import LOCAL_TOOL_SPECS, load_all_tools

    tools = await load_all_tools()
    grouped: dict[str, list[dict]] = {}
    for tool in tools:
        name = getattr(tool, "name", "") or ""
        cat_id = categorize_tool(name)
        if name in LOCAL_TOOL_SPECS:
            cat_id = "visual"
        desc = (getattr(tool, "description", None) or "").strip().split("\n")[0][:120]
        grouped.setdefault(cat_id, []).append(
            {"name": name, "description": desc}
        )
    order = [
        "convert",
        "xcms",
        "networking",
        "deeplearn",
        "peaks",
        "processing",
        "library",
        "workflow",
        "visual",
        "other",
    ]
    categories = [
        {"category": cat_id, "category_id": cat_id, "tools": grouped[cat_id]}
        for cat_id in order
        if cat_id in grouped
    ]
    return {"categories": categories, "total": len(tools)}


@app.get("/api/models")
def get_models():
    models = parse_models_from_env()
    return {
        "default_model": os.getenv("LLM_MODEL_ID"),
        "models": models,
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        client = LLM_Client(model=req.model)
        payload = [{"role": m.role, "content": m.content} for m in req.messages]
        answer = client.think(payload, temperature=req.temperature)
        if answer is None:
            raise HTTPException(status_code=500, detail="LLM returned empty response")
        return {"answer": answer}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"chat failed: {exc}") from exc


@app.get("/api/sessions")
def list_sessions():
    return {"sessions": db_list_sessions()}


@app.post("/api/sessions")
def create_session(req: CreateSessionRequest):
    title = (req.title or default_session_title()).strip()
    session_id = db_create_session(title=title, model=req.model, temperature=req.temperature)
    # 创建会话后写入一条欢迎消息，保证 UI 加载时有内容可展示
    db_append_message(
        session_id=session_id,
        role="assistant",
        content="你好，我是 MassAgent。你可以先选择模型，再输入问题。",
    )
    return {"session_id": session_id}


@app.post("/api/sessions/{session_id}/files")
async def upload_session_files(
    session_id: str,
    files: List[UploadFile] = File(...),
):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    if not files:
        raise HTTPException(status_code=400, detail="no files uploaded")

    folder = session_upload_dir(session_id)
    saved: list[dict] = []
    for upload in files:
        if not upload.filename:
            continue
        filename = safe_filename(upload.filename)
        dest_dir = upload_target_dir(folder, filename)
        target = dest_dir / filename
        if target.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            target = folder / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
            filename = target.name
        content = await upload.read()
        with open(target, "wb") as handle:
            handle.write(content)
        saved.append(
            {
                "name": filename,
                "path": normalize_display_path(target),
                "size": len(content),
            }
        )

    if not saved:
        raise HTTPException(status_code=400, detail="no valid files uploaded")

    # 会话标题仅由用户首条聊天内容决定（见 chat/stream 中的 derive_title_from_message）

    return {"files": saved}


@app.get("/api/sessions/{session_id}/workspace-files")
def session_workspace_files(session_id: str):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return get_session_workspace_files(session_id)


def _resolve_workspace_file(session_id: str, rel: str) -> Path:
    rel_path = rel.strip().lstrip("/").replace("\\", "/")
    if not rel_path or ".." in rel_path.split("/"):
        raise HTTPException(status_code=400, detail="invalid file path")
    slug = resolve_storage_slug(session_id)
    roots = [
        storage_upload_dir(PROJECT_ROOT, slug).resolve(),
        session_work_dir(PROJECT_ROOT, slug).resolve(),
    ]
    for root in roots:
        candidate = (root / rel_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    raise HTTPException(status_code=404, detail="file not found")


@app.get("/api/sessions/{session_id}/workspace-file")
def get_workspace_file(session_id: str, rel: str):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    path = _resolve_workspace_file(session_id, rel)
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".json": "application/json",
    }
    media_type = media_types.get(path.suffix.lower())
    return FileResponse(path, media_type=media_type, filename=path.name)


IMAGE_DATA_URL_RE = re.compile(r"^data:image/png;base64,(?P<data>[A-Za-z0-9+/=\s]+)$")
EDITABLE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _resolve_edited_image_target(output_root: Path, filename: str, *, merged: bool = False) -> Path:
    """改图产物写入 edited_plots/；拼图写入 merged_figures/。"""
    edit_dir = merged_figures_dir(output_root) if merged else edited_plots_dir(output_root)
    requested_name = safe_filename(filename)
    if Path(requested_name).suffix.lower() != ".png":
        requested_name = f"{Path(requested_name).stem}.png"
    target = edit_dir / requested_name
    if target.exists():
        target = edit_dir / f"{target.stem}_{uuid.uuid4().hex[:8]}.png"
    return target


@app.post("/api/sessions/{session_id}/image-edits")
def save_image_edit(session_id: str, req: ImageEditSaveRequest):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    source = _resolve_workspace_file(session_id, req.source_rel)
    if source.suffix.lower() not in EDITABLE_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="source file is not an editable image")

    slug = resolve_storage_slug(session_id)
    output_root = session_work_dir(PROJECT_ROOT, slug).resolve()
    try:
        source.relative_to(output_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="only output images can be edited")

    match = IMAGE_DATA_URL_RE.match(req.image_data.strip())
    if not match:
        raise HTTPException(status_code=400, detail="image_data must be a PNG data URL")

    try:
        png_bytes = base64.b64decode("".join(match.group("data").split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid image data") from exc

    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="image data is not a PNG")
    if len(png_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="edited image is too large")

    requested_name = safe_filename(req.filename or f"{source.stem}_edited.png")
    edit_state = req.edit_state if isinstance(req.edit_state, dict) else {}
    is_merged = edit_state.get("type") == "merged_figure"
    target = _resolve_edited_image_target(output_root, requested_name, merged=is_merged)

    target.write_bytes(png_bytes)
    edit_state.setdefault("version", 1)
    edit_state.setdefault("source_rel", req.source_rel)
    edit_state.setdefault("image", target.name)
    json_suffix = ".merge.json" if is_merged else ".editable.json"
    json_target = target.parent / f"{target.stem}{json_suffix}"
    json_target.write_text(json.dumps(edit_state, ensure_ascii=False, indent=2), encoding="utf-8")
    stat = target.stat()
    return {
        "file": {
            "name": target.relative_to(output_root).as_posix(),
            "path": normalize_display_path(target),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        },
        "editable": {
            "name": json_target.relative_to(output_root).as_posix(),
            "path": normalize_display_path(json_target),
        },
    }


@app.post("/api/sessions/{session_id}/plotly-edits")
def save_plotly_edit(session_id: str, req: PlotlyEditSaveRequest):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    source = _resolve_workspace_file(session_id, req.source_rel)
    if source.suffix.lower() not in EDITABLE_IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="source file is not an editable image")

    slug = resolve_storage_slug(session_id)
    output_root = session_work_dir(PROJECT_ROOT, slug).resolve()
    try:
        source.relative_to(output_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="only output images can be edited")

    match = IMAGE_DATA_URL_RE.match(req.image_data.strip())
    if not match:
        raise HTTPException(status_code=400, detail="image_data must be a PNG data URL")

    try:
        png_bytes = base64.b64decode("".join(match.group("data").split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid image data") from exc

    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="image data is not a PNG")
    if len(png_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="edited image is too large")

    if not isinstance(req.figure_json, dict):
        raise HTTPException(status_code=400, detail="figure_json must be an object")

    stem = Path(safe_filename(req.filename or f"{source.stem}_edited.png")).stem
    png_target = _resolve_edited_image_target(output_root, f"{stem}.png")
    json_target = png_target.parent / f"{png_target.stem}.plotly.json"

    png_target.write_bytes(png_bytes)
    json_target.write_text(json.dumps(req.figure_json, ensure_ascii=False), encoding="utf-8")
    stat = png_target.stat()
    return {
        "file": {
            "name": png_target.relative_to(output_root).as_posix(),
            "path": normalize_display_path(png_target),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        },
        "plotly": {
            "name": json_target.relative_to(output_root).as_posix(),
            "path": normalize_display_path(json_target),
        },
    }


@app.post("/api/sessions/{session_id}/plot-edits/agent")
def agent_plot_edit(session_id: str, req: PlotEditAgentRequest):
    """Agent 解析自然语言改图要求，用 matplotlib 重绘并写入 plot_config / echarts sidecar。"""
    from web_frontend.backend.plot_edit_service import PlotEditError, agent_apply_plot_edit

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is required")

    slug = resolve_storage_slug(session_id)
    model = (sess.get("model") or "").strip() or None
    try:
        result = agent_apply_plot_edit(
            project_root=PROJECT_ROOT,
            session_id=session_id,
            storage_slug=slug,
            source_rel=req.source_rel,
            instruction=req.instruction.strip(),
            model=model,
            filename=req.filename,
        )
    except PlotEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"plot edit failed: {exc}") from exc
    return result


@app.post("/api/sessions/{session_id}/image-merge/edit")
def agent_image_merge_edit(session_id: str, req: ImageMergeEditRequest):
    """Agent 调整已拼合 figure 的标签、字号、列数等，从原图重排并覆盖 merged_figures/ 中 PNG。"""
    from web_frontend.backend.image_merge_service import ImageMergeError, agent_edit_merged_figure

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is required")

    slug = resolve_storage_slug(session_id)
    model = (sess.get("model") or "").strip() or None
    try:
        result = agent_edit_merged_figure(
            project_root=PROJECT_ROOT,
            session_id=session_id,
            storage_slug=slug,
            message=req.instruction.strip(),
            target_rel=req.source_rel,
            model=model,
        )
    except ImageMergeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"merge edit failed: {exc}") from exc
    return result


@app.get("/api/sessions/{session_id}/files")
def get_session_files(session_id: str):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return {"files": list_session_files(session_id)}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return {"session": sess}


@app.get("/api/public/sessions/{session_id}/messages")
def get_public_session_messages(session_id: str):
    payload = db_get_shared_messages(session_id)
    if not payload:
        raise HTTPException(status_code=404, detail="session not found or not shared")
    return payload


@app.post("/api/sessions/{session_id}/share")
def share_session(session_id: str, req: ShareSessionRequest):
    try:
        db_set_session_shared(session_id, req.shared)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    share_url = f"/?session={session_id}&view=shared"
    return {"ok": True, "is_shared": req.shared, "share_path": share_url}


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return {"session": {"id": sess["id"], "title": sess["title"]}, "messages": db_get_messages(session_id)}


@app.put("/api/sessions/{session_id}")
def rename_session(session_id: str, req: RenameSessionRequest):
    try:
        sess = db_get_session(session_id)
        if not sess:
            raise KeyError(session_id)
        new_title = req.title.strip()
        old_slug = sess.get("storage_slug") or session_id
        db_rename_session(session_id, new_title)
        new_slug = make_storage_slug(session_id, new_title)
        db_set_storage_slug(session_id, new_slug)
        migrate_legacy_dirs_to_slug(PROJECT_ROOT, session_id, new_slug)
        rename_workspace_dirs(PROJECT_ROOT, session_id, old_slug, new_slug)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True, "storage_slug": new_slug}


@app.put("/api/sessions/{session_id}/messages/{message_id}")
def update_session_message(session_id: str, message_id: int, req: UpdateMessageRequest):
    msg = db_get_message(message_id)
    if not msg or msg["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="message not found")
    try:
        db_update_message(message_id, req.content.strip())
        if req.truncate_following:
            db_truncate_messages_after(session_id, message_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="message not found")
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    try:
        db_delete_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True}


@app.post("/api/sessions/{session_id}/clear")
def clear_session(session_id: str):
    try:
        db_clear_session_messages(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True}


def _sse_pack(data: dict) -> str:
    # SSE 一条消息格式：data: xxx\n\n
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _should_auto_agent(session_id: str, user_message: str) -> bool:
    """附件或明确分析意图时启用 Agent；普通闲聊仍走纯 LLM。"""
    del session_id
    return looks_like_agent_request(user_message)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatStreamRequest, request: Request):
    sess = db_get_session(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    stream_user_message = req.user_message

    if req.regenerate_assistant:
        history = db_get_messages(req.session_id)
        last_user = next((m for m in reversed(history) if m["role"] == "user"), None)
        if not last_user:
            raise HTTPException(
                status_code=400,
                detail="没有可重新生成的用户提问，请先发送一条消息",
            )
        stream_user_message = last_user["content"]
        if history and history[-1]["role"] == "assistant":
            db_truncate_messages_after(req.session_id, last_user["id"])
    elif req.edit_message_id is not None:
        msg = db_get_message(req.edit_message_id)
        if not msg or msg["session_id"] != req.session_id:
            raise HTTPException(status_code=404, detail="message not found")
        if msg["role"] != "user":
            raise HTTPException(status_code=400, detail="only user messages can be edited for resend")
        db_update_message(req.edit_message_id, req.user_message.strip())
        db_truncate_messages_after(req.session_id, req.edit_message_id)
        stream_user_message = req.user_message.strip()
        title_preview = derive_title_from_message(stream_user_message)
        if title_preview:
            maybe_update_title_from_first_user_message(req.session_id, title_preview)
    else:
        db_append_message(req.session_id, "user", req.user_message)
        title_preview = derive_title_from_message(req.user_message)
        if title_preview:
            maybe_update_title_from_first_user_message(req.session_id, title_preview)

    use_agent = req.use_agent or _should_auto_agent(req.session_id, stream_user_message)
    req.user_message = stream_user_message

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }

    # 改图 / 拼图 / 分析 统一走 Agent loop（LLM 选 plot_edit / image_merge / merge_edit / MCP）
    # 正则旁路仅作兼容兜底：当前默认关闭，避免与统一 Agent 双路径冲突
    # if should_route_plot_edit(stream_user_message):
    #     ...
    # if should_route_image_merge(stream_user_message):
    #     ...

    if use_agent:
        print(f"[agent] route analysis agent: {stream_user_message[:120]!r}", flush=True)
        return StreamingResponse(
            _stream_agent_sse_async(req, request),
            media_type="text/event-stream",
            headers=headers,
        )

    try:
        client = LLM_Client(model=req.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    history = db_get_messages(req.session_id)
    context = [{"role": m["role"], "content": m["content"]} for m in history]
    # 纯对话模式：禁止声称已写文件 / 已跑分析（防幻觉）
    system_guard = {
        "role": "system",
        "content": (
            "你当前处于「纯对话模式」，没有工具执行权限。"
            "不要声称已经合并图片、改图、保存文件、运行 XCMS/GNPS 或给出虚构的 outputspace 路径。"
            "若用户需要改图/拼图/分析，请明确告知需要触发 Agent 工具，并建议其用具体指令重试"
            "（例如「合并 A.png 和 B.png」「把 PCA 标题改成…」「开始分析」）。"
        ),
    }
    payload = [system_guard] + context + [{"role": "user", "content": stream_user_message}]

    async def gen_llm():
        assistant_text_parts: list[str] = []
        try:
            for delta in client.stream_think(payload, temperature=req.temperature):
                assistant_text_parts.append(delta)
                yield _sse_pack({"delta": delta})
            assistant_text = "".join(assistant_text_parts)
            assistant_time = db_append_message(req.session_id, "assistant", assistant_text)
            yield _sse_pack({"done": True, "time": assistant_time, "finished": True})
        except asyncio.CancelledError:
            partial = "".join(assistant_text_parts).strip()
            if partial:
                db_append_message(
                    req.session_id,
                    "assistant",
                    partial + "\n\n[已终止]",
                )
            raise
        except Exception as exc:
            err_msg = f"LLM streaming failed: {exc}"
            db_append_message(req.session_id, "assistant", err_msg)
            yield _sse_pack({"done": True, "error": err_msg})

    return StreamingResponse(gen_llm(), media_type="text/event-stream", headers=headers)


@app.post("/api/sessions/{session_id}/cancel")
async def cancel_session_agent(session_id: str):
    """前端「终止」时调用，跳过后续 Agent 步骤（已在跑的 R/Docker 可能仍会结束）。"""
    cancelled = await cancel_job(session_id)
    return {"ok": True, "cancelled": cancelled}


async def _stream_agent_sse_async(req: ChatStreamRequest, request: Request):
    """Agent + MCP 工具执行，SSE 流式返回进度。"""
    from web_frontend.backend.agent_runner import stream_agent_pipeline

    parts: list[str] = []
    final_error = None
    was_cancelled = False
    visual_results: list = []
    storage_slug = resolve_storage_slug(req.session_id)
    cancel_event = await register_job(req.session_id)
    recent_messages = db_get_messages(req.session_id)[-12:]

    async def _client_gone() -> bool:
        try:
            return await request.is_disconnected()
        except Exception:
            return False

    try:
        yield _sse_pack({"delta": ""})
        async for event in stream_agent_pipeline(
            user_message=req.user_message,
            session_id=req.session_id,
            storage_slug=storage_slug,
            project_root=PROJECT_ROOT,
            persist_dir=str(BASE_DIR / "softwares_database_RAG"),
            source_dir=str(BASE_DIR / "softwares_database"),
            model=req.model,
            temperature=req.temperature,
            cancel_event=cancel_event,
            is_disconnected=_client_gone,
            recent_messages=recent_messages,
        ):
            if "delta" in event:
                parts.append(event["delta"])
                yield _sse_pack({"delta": event["delta"]})
            elif "error" in event:
                final_error = event["error"]
                parts.append(f"\n❌ {final_error}\n")
                yield _sse_pack({"delta": f"\n❌ {final_error}\n"})
            elif event.get("cancelled"):
                was_cancelled = True
            if event.get("visual_results"):
                visual_results = event["visual_results"]

        if is_cancelled(cancel_event) or was_cancelled:
            if not any("已终止" in p or "已执行完毕" in p for p in parts[-3:]):
                parts.append("\n\n⚠️ **已终止**\n")
                yield _sse_pack({"delta": "\n\n⚠️ **已终止**\n"})

        text = "".join(parts) or (final_error or "Agent 未产生输出")
        time_str = db_append_message(req.session_id, "assistant", text)
        done_payload = {
            "done": True,
            "time": time_str,
            "error": final_error,
            "finished": not bool(final_error),
            "cancelled": was_cancelled or is_cancelled(cancel_event),
        }
        if visual_results:
            done_payload["visual_results"] = visual_results
        yield _sse_pack(done_payload)
    except asyncio.CancelledError:
        partial = "".join(parts).strip()
        if partial:
            db_append_message(req.session_id, "assistant", partial + "\n\n[已终止]")
        raise
    except Exception as exc:
        err_msg = f"Agent 执行失败: {exc}"
        parts.append(f"\n❌ {err_msg}\n")
        yield _sse_pack({"delta": f"\n❌ {err_msg}\n"})
        if parts:
            db_append_message(req.session_id, "assistant", "".join(parts))
        yield _sse_pack({"done": True, "error": err_msg, "finished": False})
    finally:
        await clear_job(req.session_id)


async def _stream_plot_edit_sse_async(req: ChatStreamRequest, request: Request):
    """聊天内 Agent 改图，SSE 流式返回进度。"""
    from web_frontend.backend.plot_edit_chat import stream_chat_plot_edit_deltas

    parts: list[str] = []
    final_error = None
    plot_edit_ok = False
    storage_slug = resolve_storage_slug(req.session_id)
    model = (req.model or "").strip() or None
    sess = db_get_session(req.session_id)
    if sess and not model:
        model = (sess.get("model") or "").strip() or None

    try:
        yield _sse_pack({"delta": ""})
        for event in stream_chat_plot_edit_deltas(
            project_root=PROJECT_ROOT,
            session_id=req.session_id,
            storage_slug=storage_slug,
            message=req.user_message,
            model=model,
        ):
            if "delta" in event:
                parts.append(event["delta"])
                yield _sse_pack({"delta": event["delta"]})
            elif event.get("plot_edit_done"):
                plot_edit_ok = True
            elif "error" in event:
                final_error = event["error"]

        text = "".join(parts) or (final_error or "改图未产生输出")
        time_str = db_append_message(req.session_id, "assistant", text)
        yield _sse_pack(
            {
                "done": True,
                "time": time_str,
                "error": final_error,
                "finished": plot_edit_ok and not final_error,
                "plot_edit": True,
            }
        )
    except Exception as exc:
        err_msg = f"改图失败: {exc}"
        parts.append(f"\n❌ {err_msg}\n")
        yield _sse_pack({"delta": f"\n❌ {err_msg}\n"})
        if parts:
            db_append_message(req.session_id, "assistant", "".join(parts))
        yield _sse_pack({"done": True, "error": err_msg, "finished": False, "plot_edit": True})


async def _stream_image_merge_sse_async(req: ChatStreamRequest, request: Request):
    """聊天内 Agent 合并图片，SSE 流式返回进度。"""
    from web_frontend.backend.image_merge_chat import stream_chat_image_merge_deltas

    parts: list[str] = []
    final_error = None
    merge_ok = False
    storage_slug = resolve_storage_slug(req.session_id)

    model = (req.model or "").strip() or None
    sess = db_get_session(req.session_id)
    if sess and not model:
        model = (sess.get("model") or "").strip() or None

    try:
        yield _sse_pack({"delta": ""})
        for event in stream_chat_image_merge_deltas(
            project_root=PROJECT_ROOT,
            session_id=req.session_id,
            storage_slug=storage_slug,
            message=req.user_message,
            model=model,
        ):
            if "delta" in event:
                parts.append(event["delta"])
                yield _sse_pack({"delta": event["delta"]})
            elif event.get("image_merge_done"):
                merge_ok = True
            elif "error" in event:
                final_error = event["error"]

        text = "".join(parts) or (final_error or "拼图未产生输出")
        time_str = db_append_message(req.session_id, "assistant", text)
        yield _sse_pack(
            {
                "done": True,
                "time": time_str,
                "error": final_error,
                "finished": merge_ok and not final_error,
                "image_merge": True,
            }
        )
    except Exception as exc:
        err_msg = f"拼图失败: {exc}"
        parts.append(f"\n❌ {err_msg}\n")
        yield _sse_pack({"delta": f"\n❌ {err_msg}\n"})
        if parts:
            db_append_message(req.session_id, "assistant", "".join(parts))
        yield _sse_pack({"done": True, "error": err_msg, "finished": False, "image_merge": True})


def _methods_from_form(methods_json: str | None) -> list[dict]:
    """
    methods_json 期望形如：
      [{"method":"cosine","model_path":""}, ...]
    """
    if not methods_json:
        return allowed_methods_default()
    try:
        data = json.loads(methods_json)
        if not isinstance(data, list):
            return allowed_methods_default()
        normalized = []
        for item in data:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "method": str(item.get("method") or "").strip(),
                    "model_path": str(item.get("model_path") or "").strip(),
                }
            )
        normalized = [x for x in normalized if x["method"]]
        return normalized or allowed_methods_default()
    except Exception:
        return allowed_methods_default()


@app.post("/api/analyze/mgf/stream")
async def analyze_mgf_stream(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    methods_json: str | None = Form(None),
):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="empty filename")

    filename = safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix != ".mgf":
        # MVP 先限定 mgf：后续再扩展 raw/mzML 上传
        raise HTTPException(status_code=400, detail="只支持上传 .mgf 查询文件（MVP）")

    INPUTSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    job_dir = INPUTSPACE_ROOT / "_mgf_jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    query_mgf_path = str(job_dir / filename)

    # 保存上传文件
    contents = await file.read()
    with open(query_mgf_path, "wb") as f:
        f.write(contents)

    if not os.path.exists(str(REFERENCE_MGF_PATH)):
        raise HTTPException(status_code=500, detail="reference_mgf_path 不存在，请检查 database_file 目录")
    METHOD_COMPARE_DIR.mkdir(parents=True, exist_ok=True)

    methods = _methods_from_form(methods_json)

    # 记录用户上传动作（用于会话标题更新等）
    base = Path(filename).stem[:22] or "MGF分析"
    db_append_message(session_id, "user", f"上传文件：{filename}")
    maybe_update_title_from_first_user_message(session_id, base)

    async def gen():
        all_log_lines: list[str] = []
        assistant_text = ""
        assistant_time = None
        try:
            # 工具链（尤其是 library_match_*）对 matchms 有强依赖；
            # 提前在主进程做一次预检，给出可操作的错误提示。
            try:
                import matchms  # noqa: F401
            except ModuleNotFoundError:
                err_msg = (
                    "分析依赖缺失：需要安装 Python 包 `matchms` 才能解析 MGF 并计算相似度。\n"
                    "建议在当前环境执行：pip install matchms==0.32.0\n"
                    "（你的环境是 Python 3.13，0.27 在此版本通常不可用）"
                )
                yield _sse_pack({"done": True, "error": err_msg})
                try:
                    db_append_message(session_id, "assistant", err_msg)
                except Exception:
                    pass
                return

            params = mcp_stdio_parameters()
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as mcp_session:
                    await mcp_session.initialize()

                    yield _sse_pack({"delta": "开始库匹配分析（MGF 配对）...\n"})
                    all_log_lines.append("开始库匹配分析（MGF 配对）...")

                    tool_name = "library_match_pair_from_mgf"

                    for idx, item in enumerate(methods, start=1):
                        method = item["method"]
                        model_path = item.get("model_path") or ""
                        yield _sse_pack({"delta": f"[{idx}/{len(methods)}] method={method} ...\n"})
                        all_log_lines.append(f"[{idx}/{len(methods)}] method={method} ...")

                        tool_args = {
                            "method": method,
                            "query_mgf_path": query_mgf_path,
                            "reference_mgf_path": str(REFERENCE_MGF_PATH),
                            "query_spectrum_index": 0,
                            "reference_spectrum_index": 0,
                            "mz_tolerance": 0.01,
                            "bin_size": 0.1,
                            "model_path": model_path,
                            "output_dir": str(METHOD_COMPARE_DIR),
                        }
                        result = await mcp_session.call_tool(tool_name, tool_args)
                        result_str = str(result)
                        yield _sse_pack({"delta": result_str + "\n"})
                        all_log_lines.append(result_str)

                    assistant_text = "\n".join(all_log_lines)
                    assistant_time = db_append_message(session_id, "assistant", assistant_text)
                    yield _sse_pack({"done": True, "time": assistant_time})
        except Exception as exc:
            err_msg = f"分析失败：{exc}"
            yield _sse_pack({"done": True, "error": err_msg})
            try:
                db_append_message(session_id, "assistant", err_msg)
            except Exception:
                pass

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
