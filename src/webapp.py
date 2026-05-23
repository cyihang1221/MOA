import os
import json
import sqlite3
import sys
import threading
import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from src.agent_jobs import cancel_job, clear_job, is_cancelled, register_job
from src.session_storage import (
    default_session_title,
    delete_workspace_dirs,
    derive_title_from_message,
    make_storage_slug,
    migrate_legacy_dirs_to_slug,
    rename_workspace_dirs,
    session_upload_dir as storage_upload_dir,
)

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.llm_client import LLM_Client
from src.mcp_server.server import mcp
from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from src.platform_utils import check_agent_runtime, mcp_stdio_parameters, normalize_display_path


load_dotenv(find_dotenv(), override=False)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "web_frontend"
DB_PATH = FRONTEND_DIR / "sessions.sqlite3"
DB_LOCK = threading.Lock()
WORKSPACE_DIR = BASE_DIR / "workspace"
UPLOADS_DIR = WORKSPACE_DIR / "uploads"
DATABASE_FILE_DIR = BASE_DIR / "database_file"
REFERENCE_MGF_PATH = DATABASE_FILE_DIR / "spectraverse-1.0.1.mgf"
METHOD_COMPARE_DIR = WORKSPACE_DIR / "library_matching_method_compare"

app = FastAPI(title="MassAgent Web UI")
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


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
    storage_upload_dir(WORKSPACE_DIR, storage_slug)
    (WORKSPACE_DIR / "sessions" / storage_slug).mkdir(parents=True, exist_ok=True)
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
            WORKSPACE_DIR,
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
            rename_workspace_dirs(WORKSPACE_DIR, session_id, old_slug, new_slug)

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


def _auto_title_placeholders() -> set[str]:
    return {"新会话", "默认会话", ""}


def maybe_update_title_from_first_user_message(session_id: str, new_title: str) -> None:
    sess = db_get_session(session_id)
    if not sess or not new_title:
        return
    current_title = (sess.get("title") or "").strip()
    if current_title not in _auto_title_placeholders() and not current_title.startswith("对话 "):
        return
    old_slug = sess.get("storage_slug") or session_id
    db_rename_session(session_id, new_title)
    new_slug = make_storage_slug(session_id, new_title)
    db_set_storage_slug(session_id, new_slug)
    migrate_legacy_dirs_to_slug(WORKSPACE_DIR, session_id, new_slug)
    rename_workspace_dirs(WORKSPACE_DIR, session_id, old_slug, new_slug)


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
    migrate_legacy_dirs_to_slug(WORKSPACE_DIR, session_id, slug)
    if not sess.get("storage_slug"):
        db_set_storage_slug(session_id, slug)
    return slug


init_db()


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


def parse_models_from_env() -> List[str]:
    configured = os.getenv("LLM_MODEL_CANDIDATES", "")
    values = [item.strip() for item in configured.split(",") if item.strip()]
    default_model = os.getenv("LLM_MODEL_ID", "").strip()
    if default_model and default_model not in values:
        values.insert(0, default_model)
    return values


def categorize_tool(name: str) -> str:
    if name.startswith("convert_") or name.startswith("mzml_"):
        return "数据转换"
    if name.startswith("peak_detection"):
        return "峰检测"
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
        return "峰处理与注释"
    if name.startswith("library_match"):
        return "谱库匹配"
    if "mzmine" in name:
        return "流程编排"
    return "其他工具"


def session_upload_dir(session_id: str) -> Path:
    slug = resolve_storage_slug(session_id)
    return storage_upload_dir(WORKSPACE_DIR, slug)


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


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


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
    tools = await mcp.list_tools()
    grouped: dict[str, list[dict]] = {}
    for tool in tools:
        category = categorize_tool(tool.name)
        desc = (tool.description or "").strip().split("\n")[0][:120]
        grouped.setdefault(category, []).append(
            {"name": tool.name, "description": desc}
        )
    order = [
        "数据转换",
        "峰检测",
        "峰处理与注释",
        "谱库匹配",
        "流程编排",
        "其他工具",
    ]
    categories = [
        {"category": cat, "tools": grouped[cat]}
        for cat in order
        if cat in grouped
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
        target = folder / filename
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
    return {"files": saved}


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
        migrate_legacy_dirs_to_slug(WORKSPACE_DIR, session_id, new_slug)
        rename_workspace_dirs(WORKSPACE_DIR, session_id, old_slug, new_slug)
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
    """有上传文件或消息里含附件路径时，自动启用 Agent 工具执行。"""
    if list_session_files(session_id):
        return True
    if "[已上传附件]" in user_message:
        return True
    upload_dir = session_upload_dir(session_id)
    if upload_dir.is_dir() and any(upload_dir.iterdir()):
        return True
    return False


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

    if use_agent:
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
    payload = context + [{"role": "user", "content": stream_user_message}]

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
    from src.web_agent_runner import stream_agent_pipeline

    parts: list[str] = []
    final_error = None
    was_cancelled = False
    storage_slug = resolve_storage_slug(req.session_id)
    cancel_event = await register_job(req.session_id)

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
            workspace_root=WORKSPACE_DIR,
            database_file_dir=str(DATABASE_FILE_DIR),
            persist_dir=str(BASE_DIR / "softwares_database_RAG"),
            source_dir=str(BASE_DIR / "softwares_database"),
            model=req.model,
            temperature=req.temperature,
            cancel_event=cancel_event,
            is_disconnected=_client_gone,
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

        if is_cancelled(cancel_event) or was_cancelled:
            if not any("已终止" in p or "已执行完毕" in p for p in parts[-3:]):
                parts.append("\n\n⚠️ **已终止**\n")
                yield _sse_pack({"delta": "\n\n⚠️ **已终止**\n"})

        text = "".join(parts) or (final_error or "Agent 未产生输出")
        time_str = db_append_message(req.session_id, "assistant", text)
        yield _sse_pack(
            {
                "done": True,
                "time": time_str,
                "error": final_error,
                "finished": not bool(final_error),
                "cancelled": was_cancelled or is_cancelled(cancel_event),
            }
        )
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

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    job_dir = UPLOADS_DIR / job_id
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
