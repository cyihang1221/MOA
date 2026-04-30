import os
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.llm_client import LLM_Client
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


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


def db_list_sessions() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, title, updated_at FROM sessions ORDER BY updated_at DESC, created_at DESC"
        )
        rows = cur.fetchall()
        return [
            {"id": r["id"], "title": r["title"], "updated_at": r["updated_at"]}
            for r in rows
        ]


def db_get_session(session_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, title, model, temperature, created_at, updated_at FROM sessions WHERE id=?",
            (session_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return dict(r)


def db_create_session(title: str, model: Optional[str], temperature: float) -> str:
    session_id = uuid.uuid4().hex
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, title, model, temperature, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, title, model, temperature, now, now),
        )
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
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        if cur.rowcount == 0:
            raise KeyError(session_id)


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
        conn.execute("UPDATE sessions SET title=?, updated_at=? WHERE id=?", ("新会话", now, session_id))

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


def db_get_messages(session_id: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT role, content, time, created_at
            FROM messages
            WHERE session_id=?
            ORDER BY id ASC
            """,
            (session_id,),
        )
        rows = cur.fetchall()
        return [{"role": r["role"], "content": r["content"], "time": r["time"]} for r in rows]


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
    if not sess:
        return
    current_title = (sess.get("title") or "").strip()
    if current_title in {"新会话", "默认会话", ""}:
        db_rename_session(session_id, new_title)


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


def parse_models_from_env() -> List[str]:
    configured = os.getenv("LLM_MODEL_CANDIDATES", "")
    values = [item.strip() for item in configured.split(",") if item.strip()]
    default_model = os.getenv("LLM_MODEL_ID", "").strip()
    if default_model and default_model not in values:
        values.insert(0, default_model)
    return values


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


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
    title = (req.title or "新会话").strip()
    session_id = db_create_session(title=title, model=req.model, temperature=req.temperature)
    # 创建会话后写入一条欢迎消息，保证 UI 加载时有内容可展示
    db_append_message(
        session_id=session_id,
        role="assistant",
        content="你好，我是 MassAgent。你可以先选择模型，再输入问题。",
    )
    return {"session_id": session_id}


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return {"session": {"id": sess["id"], "title": sess["title"]}, "messages": db_get_messages(session_id)}


@app.put("/api/sessions/{session_id}")
def rename_session(session_id: str, req: RenameSessionRequest):
    try:
        maybe_update_title_from_first_user_message(session_id=session_id, new_title=req.title)
        db_rename_session(session_id, req.title)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
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


@app.post("/api/chat/stream")
def chat_stream(req: ChatStreamRequest):
    sess = db_get_session(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        client = LLM_Client(model=req.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    history = db_get_messages(req.session_id)
    context = [{"role": m["role"], "content": m["content"]} for m in history]
    payload = context + [{"role": "user", "content": req.user_message}]

    # 先把用户消息写入 DB，保证会话历史一致
    user_time = db_append_message(req.session_id, "user", req.user_message)

    assistant_time_holder = {"time": None}

    def gen():
        assistant_text_parts: list[str] = []
        assistant_time = None
        try:
            for delta in client.stream_think(payload, temperature=req.temperature):
                assistant_text_parts.append(delta)
                yield _sse_pack({"delta": delta})
            assistant_text = "".join(assistant_text_parts)
            assistant_time = db_append_message(req.session_id, "assistant", assistant_text)

            # 如果这是第一轮用户输入，自动用首条问题做会话标题
            title_preview = req.user_message.strip().replace("\n", " ")
            title_preview = title_preview[:22]
            if title_preview:
                maybe_update_title_from_first_user_message(req.session_id, title_preview)

            yield _sse_pack({"done": True, "time": assistant_time})
        except Exception as exc:
            err_msg = f"LLM streaming failed: {exc}"
            db_append_message(req.session_id, "assistant", err_msg)
            yield _sse_pack({"done": True, "error": err_msg})
        finally:
            assistant_time_holder["time"] = assistant_time

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


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

            params = StdioServerParameters(command="python", args=["-m", "src.mcp_server.server"])
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
