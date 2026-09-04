import base64
import binascii
import logging
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

from web_frontend.backend.agent_intent import (
    classify_frontend_intent,
    looks_like_agent_request,
    looks_like_c_visual_request,
)
from web_frontend.backend.agent_jobs import cancel_job, clear_job, is_cancelled, register_job
from web_frontend.backend.anti_hallucination import chat_guard_messages
from web_frontend.backend.plot_versioning import prefer_effective_among_rels
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
from web_frontend.backend.literature_paths import resolve_literature_dirs
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
LITERATURE_PERSIST_DIR, LITERATURE_SOURCE_DIR = resolve_literature_dirs(PROJECT_ROOT)

app = FastAPI(title="MassAgent Web UI")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_logger = logging.getLogger(__name__)


@app.on_event("startup")
def _warmup_literature_rag_on_startup() -> None:
    """后台预热文献向量索引，避免首条 Agent 消息冷启动超时。"""

    def _run() -> None:
        try:
            from web_frontend.backend.literature_rag import warmup_literature_rag

            persist, source = LITERATURE_PERSIST_DIR, LITERATURE_SOURCE_DIR
            has_index = (Path(persist) / "docstore.json").is_file()
            has_source = Path(source).is_dir()
            if not has_index and not has_source:
                _logger.info("文献库与 RAG 索引均不存在，跳过预热")
                return
            hit = warmup_literature_rag(persist_dir=persist, source_dir=source)
            _logger.info(
                "文献 RAG 预热完成 mode=%s chars=%s error=%s",
                hit.get("mode"),
                len(hit.get("text") or ""),
                hit.get("error"),
            )
        except Exception as exc:
            _logger.warning("文献 RAG 预热失败: %s", exc)

    threading.Thread(target=_run, name="literature-rag-warmup", daemon=True).start()


try:
    from web_frontend.backend.semantic_plot_renderer import is_vl_convert_available

    if is_vl_convert_available():
        _logger.info("vl-convert-python 可用 (python=%s)", sys.executable)
    else:
        _logger.warning(
            "vl-convert-python 未安装 (python=%s)，plot_edit 将回退 matplotlib 导出 PNG",
            sys.executable,
        )
except Exception as exc:
    _logger.warning("语义图表导出自检失败: %s", exc)


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
        try:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN workflow_status TEXT NOT NULL DEFAULT 'WAITING_INPUT'"
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN plan_version INTEGER NOT NULL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN plan_locked_at TEXT")
        except sqlite3.OperationalError:
            pass


def db_list_sessions() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, title, updated_at, is_shared, storage_slug, workflow_status FROM sessions ORDER BY updated_at DESC, created_at DESC"
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "updated_at": r["updated_at"],
                "is_shared": bool(r["is_shared"]),
                "storage_slug": r["storage_slug"] or r["id"],
                "workflow_status": r["workflow_status"] if "workflow_status" in r.keys() else "WAITING_INPUT",
            }
            for r in rows
        ]


def db_get_session(session_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, title, model, temperature, created_at, updated_at, is_shared, storage_slug, workflow_status, plan_version, plan_locked_at FROM sessions WHERE id=?",
            (session_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        data = dict(r)
        data["is_shared"] = bool(data.get("is_shared"))
        if not data.get("storage_slug"):
            data["storage_slug"] = session_id
        data["workflow_status"] = data.get("workflow_status") or "WAITING_INPUT"
        data["plan_version"] = int(data.get("plan_version") or 0)
        return data


def db_set_storage_slug(session_id: str, storage_slug: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE sessions SET storage_slug=? WHERE id=?",
            (storage_slug, session_id),
        )


def db_set_workflow(
    session_id: str,
    status: str,
    *,
    bump_plan: bool = False,
    lock_plan: bool = False,
) -> None:
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        if bump_plan:
            conn.execute(
                "UPDATE sessions SET workflow_status=?, plan_version=COALESCE(plan_version,0)+1, "
                "plan_locked_at=NULL, updated_at=? WHERE id=?",
                (status, now, session_id),
            )
        elif lock_plan:
            conn.execute(
                "UPDATE sessions SET workflow_status=?, plan_locked_at=?, updated_at=? WHERE id=?",
                (status, now, now, session_id),
            )
        else:
            conn.execute(
                "UPDATE sessions SET workflow_status=?, updated_at=? WHERE id=?",
                (status, now, session_id),
            )


def db_create_session(title: str, model: Optional[str], temperature: float) -> str:
    session_id = uuid.uuid4().hex
    storage_slug = make_storage_slug(session_id, title)
    now = utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, title, model, temperature, created_at, updated_at, storage_slug, workflow_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'WAITING_INPUT')
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


def _session_has_result_figures(session_id: str) -> bool:
    from web_frontend.backend.workflow import session_has_result_figures

    slug = resolve_storage_slug(session_id)
    return session_has_result_figures(PROJECT_ROOT, slug)


def _sync_workflow_for_existing_outputs(session_id: str, sess: dict) -> tuple[dict, bool]:
    """若 outputspace 已有结果图，将陈旧 workflow 同步为 COMPLETED。"""
    from web_frontend.backend.workflow import maybe_advance_workflow_for_outputs

    has_figs = _session_has_result_figures(session_id)
    new_st = maybe_advance_workflow_for_outputs(
        sess.get("workflow_status"),
        has_result_figures=has_figs,
    )
    if new_st:
        db_set_workflow(session_id, new_st)
        sess = dict(sess)
        sess["workflow_status"] = new_st
    return sess, has_figs


def _resolve_session_chat_action(
    session_id: str,
    user_message: str,
    sess: dict,
    *,
    has_figs: bool,
) -> tuple[str, str | None, dict]:
    """LLM 路由 + 规则兜底；返回 (action, clarify_message, meta)。"""
    from web_frontend.backend.chat_router import resolve_chat_action
    from web_frontend.backend.workflow import session_has_locked_plan

    llm_client = None
    try:
        from web_frontend.backend.chat_router import llm_router_enabled

        if llm_router_enabled():
            llm_client = LLM_Client(
                model=os.getenv("MASSAGENT_ROUTER_MODEL", "").strip() or None
            )
    except Exception:
        llm_client = None

    slug = resolve_storage_slug(session_id)
    action, clarify, meta = resolve_chat_action(
        sess.get("workflow_status"),
        user_message,
        has_result_figures=has_figs,
        has_locked_plan=session_has_locked_plan(PROJECT_ROOT, slug),
        project_root=PROJECT_ROOT,
        storage_slug=slug,
        llm_client=llm_client,
    )
    return action, clarify, meta


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
    use_agent: bool = False  # True 时走 Agent C（出图/报告或向 B 交接），而非纯 LLM 对话
    edit_message_id: Optional[int] = None  # 编辑用户消息后重发：更新该条并截断其后
    regenerate_assistant: bool = False  # 基于最后一条用户消息重新生成回答
    # 用户自备 OpenAI 兼容 API（仅本次请求生效，不落库）
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None


class LlmProbeRequest(BaseModel):
    model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None


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


class SemanticPlotSaveRequest(BaseModel):
    source_rel: str
    plot_config: dict
    filename: Optional[str] = None


class PlotEditAgentRequest(BaseModel):
    source_rel: str
    instruction: str
    filename: Optional[str] = None
    model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None


class ImageMergeEditRequest(BaseModel):
    source_rel: str
    instruction: str
    model: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None


class MetadataSaveRequest(BaseModel):
    rows: list[dict]
    align_to_inputs: bool = True


class AgentCParsePlanRequest(BaseModel):
    plan_path: Optional[str] = None
    plan_text: Optional[str] = None
    plan: Optional[dict] = None


class AgentCInventoryRequest(BaseModel):
    results_dir: str
    metadata_csv: Optional[str] = None


class AgentCRunRequest(BaseModel):
    plan_path: Optional[str] = None
    plan_text: Optional[str] = None
    plan: Optional[dict] = None
    repro_recipe_id: Optional[str] = None
    results_dir: str
    output_dir: Optional[str] = None
    metadata_csv: Optional[str] = None
    figure_mode: str = "plan"
    language: Optional[str] = None
    use_llm: bool = False


class AgentCSessionRunRequest(BaseModel):
    plan_path: Optional[str] = None
    results_dir: Optional[str] = None
    repro_recipe_id: Optional[str] = None
    figure_mode: str = "plan"
    language: Optional[str] = None
    use_llm: bool = False


def _session_metadata_paths(session_id: str) -> dict[str, str]:
    from web_frontend.backend.agent_runner import build_session_paths

    slug = resolve_storage_slug(session_id)
    return build_session_paths(session_id, PROJECT_ROOT, storage_slug=slug)


def parse_models_from_env() -> List[str]:
    configured = os.getenv("LLM_MODEL_CANDIDATES", "")
    values = [item.strip() for item in configured.split(",") if item.strip()]
    default_model = os.getenv("LLM_MODEL_ID", "").strip()
    if default_model and default_model not in values:
        values.insert(0, default_model)
    return values


def _agent_c_safe_path(raw: str | None, *, required: bool = True) -> Path | None:
    """HTTP 接口只允许项目根下的路径，避免任意读盘。"""
    if not raw or not str(raw).strip():
        if required:
            raise HTTPException(status_code=400, detail="path is required")
        return None
    path = Path(str(raw).strip()).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()
    root = PROJECT_ROOT.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path must be under the project root") from exc
    return path


def _agent_c_plan_source(req: AgentCParsePlanRequest | AgentCRunRequest):
    if req.plan is not None:
        return req.plan
    if req.plan_text:
        return req.plan_text
    path = _agent_c_safe_path(req.plan_path, required=True)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail=f"plan not found: {req.plan_path}")
    return path


# 常见 OpenAI 兼容供应商预设（前端弹窗下拉）
LLM_PROVIDER_PRESETS: list[dict[str, str]] = [
    {
        "id": "server",
        "label": "使用服务端默认 (.env)",
        "base_url": "",
        "model_hint": "",
    },
    {
        "id": "dashscope",
        "label": "阿里云百炼 DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_hint": "qwen-plus",
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model_hint": "deepseek-chat",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model_hint": "gpt-4o-mini",
    },
    {
        "id": "siliconflow",
        "label": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model_hint": "Qwen/Qwen2.5-7B-Instruct",
    },
    {
        "id": "moonshot",
        "label": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "model_hint": "moonshot-v1-8k",
    },
    {
        "id": "zhipu",
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model_hint": "glm-4-flash",
    },
    {
        "id": "custom",
        "label": "自定义 OpenAI 兼容接口",
        "base_url": "",
        "model_hint": "",
    },
]


def _apply_request_llm_override(req: ChatStreamRequest | LlmProbeRequest):
    """启用本次请求的用户 API 覆盖，返回 reset token。"""
    from web_frontend.backend.web_llm import set_llm_override

    return set_llm_override(
        api_key=getattr(req, "llm_api_key", None),
        base_url=getattr(req, "llm_base_url", None),
        model=getattr(req, "model", None),
    )


def categorize_tool(name: str) -> str:
    """返回稳定分类 ID，前端用 i18n 显示中英文名称。"""
    if name in {"plot_edit", "image_merge", "merge_edit"}:
        return "visual"
    if (
        name.startswith("convert_")
        or name.startswith("mzml_")
        or name.startswith("data_transformation_")
    ):
        return "convert"
    if name.startswith("molecular_networking"):
        return "networking"
    if name.startswith("deepmass"):
        return "deeplearn"
    if name.startswith("library_match") or name == "spectral_annotation":
        return "library"
    if name.startswith(("peak_detection_", "peak_picking_", "feature_detection_")):
        return "peaks"
    if any(
        key in name
        for key in (
            "filter_redundant",
            "redundant_feature",
            "align_retention",
            "align_features",
            "group_peaks",
            "peak_group",
            "fill_missing",
            "identify_isotopes",
            "isotope_analysis",
        )
    ):
        return "processing"
    if name.startswith(
        (
            "data_preprocessing",
            "feature_filtering",
            "statistical_analysis",
            "extract_differential",
            "kegg_compound",
        )
    ):
        return "xcms"
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
        "agent_c": "/api/agent-c/contract",
        "abc_contract": "/api/abc/contract",
        "agent_backends": "/api/agent-backends",
    }


@app.get("/api/agent-backends")
def agent_backends_info():
    from web_frontend.backend.agent_backends import backend_status

    return backend_status()


@app.get("/api/abc/contract")
def abc_contract_info():
    from web_frontend.backend.abc_contract import contract_document
    from web_frontend.backend.agent_backends import backend_status

    doc = contract_document()
    doc["backends"] = backend_status()
    return doc


@app.get("/api/agent-c/repro-recipes")
def agent_c_repro_recipes():
    from web_frontend.backend.agent_c import list_repro_recipes

    return {"recipes": list_repro_recipes()}


@app.get("/api/agent-c/repro-recipes/{recipe_id}")
def agent_c_repro_recipe_detail(recipe_id: str):
    from web_frontend.backend.agent_c import load_repro_recipe, recipe_to_canonical_plan

    recipe = load_repro_recipe(recipe_id)
    return {
        "recipe": recipe,
        "canonical_plan": recipe_to_canonical_plan(recipe),
    }


@app.post("/api/agent-c/repro-checklist")
def agent_c_repro_checklist(req: AgentCInventoryRequest, recipe_id: str):
    from web_frontend.backend.agent_c import checklist_inventory, inventory_results, load_repro_recipe

    results_dir = _agent_c_safe_path(req.results_dir, required=True)
    metadata = _agent_c_safe_path(req.metadata_csv, required=False)
    recipe = load_repro_recipe(recipe_id)
    inv = inventory_results(results_dir, metadata_csv=metadata)
    return checklist_inventory(recipe, inv)


@app.get("/api/agent-c/contract")
def agent_c_contract():
    from web_frontend.backend.agent_c import contract_document

    return contract_document()


@app.post("/api/agent-c/parse-plan")
def agent_c_parse_plan(req: AgentCParsePlanRequest):
    from web_frontend.backend.agent_c import parse_plan

    source = _agent_c_plan_source(req)
    return parse_plan(source)


@app.post("/api/agent-c/inventory")
def agent_c_inventory(req: AgentCInventoryRequest):
    from web_frontend.backend.agent_c import inventory_results

    results_dir = _agent_c_safe_path(req.results_dir, required=True)
    metadata = _agent_c_safe_path(req.metadata_csv, required=False)
    return inventory_results(results_dir, metadata_csv=metadata)


def _session_plot_goal(session_id: str) -> str:
    from web_frontend.backend.literature_plot_knowledge import session_goal_text

    return session_goal_text(db_get_session(session_id), db_get_messages(session_id))


@app.post("/api/agent-c/run")
def agent_c_run(req: AgentCRunRequest):
    from web_frontend.backend.agent_c import run_agent_c

    plan = None if req.repro_recipe_id else _agent_c_plan_source(req)
    results_dir = _agent_c_safe_path(req.results_dir, required=True)
    output_dir = _agent_c_safe_path(req.output_dir, required=False)
    metadata = _agent_c_safe_path(req.metadata_csv, required=False)
    try:
        return run_agent_c(
            plan=plan,
            results_dir=results_dir,
            output_dir=output_dir,
            metadata_csv=metadata,
            figure_mode=req.figure_mode or "plan",
            language=req.language,
            use_llm=bool(req.use_llm),
            repro_recipe_id=req.repro_recipe_id,
            project_root=PROJECT_ROOT,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions/{session_id}/agent-c/report")
def agent_c_report_view(session_id: str):
    """一键查看 Agent C 报告：Markdown/HTML + 解读摘要 + 图表列表。"""
    from web_frontend.backend.agent_c.report_view import load_report_bundle
    from web_frontend.backend.session_storage import session_work_dir

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    slug = resolve_storage_slug(session_id)
    output_root = session_work_dir(PROJECT_ROOT, slug)
    try:
        return load_report_bundle(session_id=session_id, results_dir=output_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/agent-c/regenerate-pdf")
def agent_c_regenerate_pdf(session_id: str):
    """从已有 final_report.md 重新导出 PDF（修复路径/字体后无需重跑 C）。"""
    from web_frontend.backend.agent_c.pdf_export import markdown_file_to_pdf
    from web_frontend.backend.agent_c.report_view import find_agent_c_output_dir, _rel_to_session
    from web_frontend.backend.session_storage import session_work_dir

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    slug = resolve_storage_slug(session_id)
    output_root = session_work_dir(PROJECT_ROOT, slug)
    out_dir = find_agent_c_output_dir(output_root)
    if not out_dir:
        raise HTTPException(status_code=404, detail="未找到 agent_c_output/final_report.md")
    md_path = out_dir / "final_report.md"
    if not md_path.is_file():
        raise HTTPException(status_code=404, detail="final_report.md 不存在")
    try:
        pdf_path = markdown_file_to_pdf(md_path, results_dir=output_root)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {exc}") from exc
    return {
        "pdf_rel": _rel_to_session(output_root, pdf_path),
        "markdown_rel": _rel_to_session(output_root, md_path),
    }


@app.post("/api/sessions/{session_id}/agent-c/run")
def agent_c_run_session(session_id: str, req: AgentCSessionRunRequest):
    """用当前会话的 outputspace 当 B 结果，自动找 analysis_plan.*。"""
    from web_frontend.backend.agent_c import run_agent_c
    from web_frontend.backend.session_metadata import resolve_metadata_csv

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    slug = resolve_storage_slug(session_id)
    output_root = session_work_dir(PROJECT_ROOT, slug)
    upload_root = storage_upload_dir(PROJECT_ROOT, slug)
    results_dir = _agent_c_safe_path(req.results_dir, required=False) or output_root
    if req.plan_path:
        plan = _agent_c_safe_path(req.plan_path, required=True)
    else:
        plan = None
        for name in ("analysis_plan.json", "analysis_plan.md"):
            for folder in (output_root, upload_root, results_dir):
                cand = Path(folder) / name
                if cand.is_file():
                    plan = cand
                    break
            if plan:
                break
        if plan is None:
            for folder in (output_root, upload_root, results_dir):
                found = sorted(Path(folder).glob("plan_*.json"), reverse=True)
                if found:
                    plan = found[0]
                    break
        if plan is None:
            raise HTTPException(
                status_code=400,
                detail="session 中未找到 analysis_plan.md / analysis_plan.json，请传入 plan_path",
            )
    metadata = None
    try:
        metadata = resolve_metadata_csv(upload_root)
    except Exception:
        metadata = None
    out = Path(results_dir) / "agent_c_output"
    try:
        return run_agent_c(
            plan=plan,
            results_dir=results_dir,
            output_dir=out,
            metadata_csv=metadata,
            figure_mode=req.figure_mode or "plan",
            language=req.language,
            use_llm=bool(req.use_llm),
            goal_text=_session_plot_goal(session_id),
            project_root=PROJECT_ROOT,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/tools")
async def get_tools():
    """前端 Agent 只暴露 C 侧工具；分析 MCP 不在此列表。"""
    from web_frontend.backend.tool_registry import LOCAL_TOOL_SPECS, tool_spec_as_mcp_like
    from web_frontend.backend.tool_registry import ToolSpec, _schema

    c_run = ToolSpec(
        name="agent_c_run",
        description=(
            "按 A 的 analysis_plan 与 B 的结果目录出图并写 final_report.md。"
            "不调用 XCMS/mixOmics 等分析工具。"
        ),
        input_schema=_schema(
            {
                "plan": {"type": "string", "description": "方案路径或会话内 analysis_plan.md"},
                "results_dir": {"type": "string", "description": "B 的结果目录"},
            },
            [],
        ),
        runtime="local",
        category="visual",
    )
    tools = [tool_spec_as_mcp_like(spec) for spec in LOCAL_TOOL_SPECS.values()]
    tools.append(tool_spec_as_mcp_like(c_run))
    grouped: dict[str, list[dict]] = {}
    for tool in tools:
        name = getattr(tool, "name", "") or ""
        desc = (getattr(tool, "description", None) or "").strip().split("\n")[0][:160]
        grouped.setdefault("visual", []).append({"name": name, "description": desc})
    return {
        "categories": [{"category": "visual", "category_id": "visual", "tools": grouped["visual"]}],
        "total": len(tools),
        "agent_role": "C",
        "note": "Web Agent 只做可视化与报告；分析执行请走 Agent B。",
    }


@app.get("/api/models")
def get_models():
    models = parse_models_from_env()
    return {
        "default_model": os.getenv("LLM_MODEL_ID"),
        "default_base_url": (os.getenv("LLM_BASE_URL") or "").strip().rstrip("/"),
        "models": models,
        "providers": LLM_PROVIDER_PRESETS,
        "has_server_key": bool((os.getenv("LLM_API_KEY") or "").strip()),
    }


@app.post("/api/llm/probe")
def probe_llm(req: LlmProbeRequest):
    """用当前表单配置试连一次（不落库、不写会话）。"""
    from web_frontend.backend.llm_security import redact_secrets
    from web_frontend.backend.web_llm import WebLLMClient, reset_llm_override

    try:
        token = _apply_request_llm_override(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        client = WebLLMClient(model=req.model)
        reply = client.think_complete(
            [{"role": "user", "content": "Reply with exactly: ok"}],
            temperature=0.0,
            max_tokens=16,
        )
        text = (reply or "").strip()
        if not text:
            raise HTTPException(status_code=502, detail="LLM 返回为空")
        return {"ok": True, "model": client.model, "preview": text[:80]}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=redact_secrets(str(exc))) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=redact_secrets(str(exc))) from exc
    finally:
        reset_llm_override(token)


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        client = LLM_Client(model=req.model)
        # 与 SSE 纯对话一致：注入防幻觉 system
        payload = chat_guard_messages() + [
            {"role": m.role, "content": m.content} for m in req.messages
        ]
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
        content="你好，我是 MassAgent。请上传数据并描述分析目标；我会先给出分析计划，你回复「确认计划」后再执行，最后自动出图与报告。",
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

    metadata_info: dict | None = None
    try:
        from web_frontend.backend.agent_runner import build_session_paths
        from web_frontend.backend.session_metadata import (
            ensure_metadata_from_inputs,
            format_metadata_report_summary,
        )

        slug = resolve_storage_slug(session_id)
        paths = build_session_paths(session_id, PROJECT_ROOT, storage_slug=slug)
        _, metadata_info = ensure_metadata_from_inputs(folder, paths=paths)
        metadata_info = {
            **metadata_info,
            "summary": format_metadata_report_summary(metadata_info),
        }
    except FileNotFoundError:
        metadata_info = None
    except Exception:
        metadata_info = None

    # 会话标题仅由用户首条聊天内容决定（见 chat/stream 中的 derive_title_from_message）

    return {"files": saved, "metadata": metadata_info}


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


_OUTPUT_IMAGE_SIDECAR_SUFFIXES = (
    ".editable.json",
    ".plotly.json",
    ".plot_config.json",
    ".vl.json",
    ".echarts.json",
    ".merge.json",
    ".svg",
)


@app.delete("/api/sessions/{session_id}/workspace-file")
def delete_workspace_file(session_id: str, rel: str):
    """删除 outputspace 中的结果文件（及同名 sidecar）。仅允许 output 目录。"""
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    rel_path = rel.strip().lstrip("/").replace("\\", "/")
    if not rel_path or ".." in rel_path.split("/"):
        raise HTTPException(status_code=400, detail="invalid file path")
    slug = resolve_storage_slug(session_id)
    output_root = session_work_dir(PROJECT_ROOT, slug).resolve()
    target = (output_root / rel_path).resolve()
    try:
        target.relative_to(output_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="只能删除会话输出目录中的文件") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    removed = [rel_path]
    target.unlink()
    stem = target.stem
    parent = target.parent
    for suffix in _OUTPUT_IMAGE_SIDECAR_SUFFIXES:
        side = parent / f"{stem}{suffix}"
        if side.is_file():
            side.unlink()
            removed.append(side.relative_to(output_root).as_posix())
    return {"ok": True, "removed": removed}


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


@app.get("/api/sessions/{session_id}/semantic-plot")
def get_semantic_plot(session_id: str, source_rel: str):
    """Build an editable Vega-Lite preview from source data without writing files."""
    from web_frontend.backend.plot_edit_service import PlotEditError, get_semantic_plot_payload

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        return get_semantic_plot_payload(
            project_root=PROJECT_ROOT,
            storage_slug=resolve_storage_slug(session_id),
            source_rel=source_rel,
        )
    except (PlotEditError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/semantic-plot-edits")
def save_semantic_plot_edit(session_id: str, req: SemanticPlotSaveRequest):
    """Validate semantic controls and export matching Vega-Lite, SVG and PNG files."""
    from web_frontend.backend.plot_edit_service import PlotEditError, apply_plot_config

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        return apply_plot_config(
            project_root=PROJECT_ROOT,
            session_id=session_id,
            storage_slug=resolve_storage_slug(session_id),
            source_rel=req.source_rel,
            plot_config_patch=req.plot_config,
            filename=req.filename,
        )
    except (PlotEditError, ValueError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/semantic-plot/preview")
def preview_semantic_plot(session_id: str, req: SemanticPlotSaveRequest):
    """Return a validated Vega-Lite preview without creating output files."""
    from web_frontend.backend.plot_edit_service import PlotEditError, get_semantic_plot_payload

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        return get_semantic_plot_payload(
            project_root=PROJECT_ROOT,
            storage_slug=resolve_storage_slug(session_id),
            source_rel=req.source_rel,
            plot_config_patch=req.plot_config,
        )
    except (PlotEditError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/plot-edits/agent")
def agent_plot_edit(session_id: str, req: PlotEditAgentRequest):
    """Agent 解析自然语言改图要求，并导出语义一致的 Vega-Lite/SVG/PNG。"""
    from web_frontend.backend.plot_edit_service import PlotEditError, agent_apply_plot_edit
    from web_frontend.backend.literature_plot_knowledge import session_goal_text

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is required")

    slug = resolve_storage_slug(session_id)
    model = (req.model or "").strip() or (sess.get("model") or "").strip() or None
    goal = session_goal_text(sess, db_get_messages(session_id))
    from web_frontend.backend.web_llm import llm_override_context

    try:
        with llm_override_context(
            api_key=req.llm_api_key,
            base_url=req.llm_base_url,
            model=model,
        ):
            result = agent_apply_plot_edit(
                project_root=PROJECT_ROOT,
                session_id=session_id,
                storage_slug=slug,
                source_rel=req.source_rel,
                instruction=req.instruction.strip(),
                model=model,
                filename=req.filename,
                goal_text=goal,
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


@app.get("/api/sessions/{session_id}/plot-literature-hints")
def plot_literature_hints(session_id: str, source_rel: str = ""):
    """返回与当前图型匹配的文献作图建议（MassOmics skills + phase2_output）。"""
    from web_frontend.backend.literature_plot_knowledge import match_plot_literature, session_goal_text

    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    if not source_rel.strip():
        raise HTTPException(status_code=400, detail="source_rel is required")

    goal = session_goal_text(sess, db_get_messages(session_id))
    payload = match_plot_literature(
        goal_text=goal,
        source_rel=source_rel.strip(),
        project_root=PROJECT_ROOT,
    )
    return {
        "goal_text": goal,
        "matched": payload.get("matched") or [],
        "hints": payload.get("hints") or [],
        "context_preview": (payload.get("text") or "")[:800],
    }


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


@app.get("/api/sessions/{session_id}/metadata")
def get_session_metadata(session_id: str):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    from web_frontend.backend.metadata_editor import get_metadata_editor_state

    slug = resolve_storage_slug(session_id)
    try:
        paths = _session_metadata_paths(session_id)
    except Exception:
        paths = None
    try:
        state = get_metadata_editor_state(
            project_root=PROJECT_ROOT,
            storage_slug=slug,
            paths=paths,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return state


@app.put("/api/sessions/{session_id}/metadata")
def put_session_metadata(session_id: str, req: MetadataSaveRequest):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    from web_frontend.backend.metadata_editor import MetadataEditorError, save_metadata_rows

    slug = resolve_storage_slug(session_id)
    try:
        paths = _session_metadata_paths(session_id)
    except Exception:
        paths = None
    try:
        result = save_metadata_rows(
            project_root=PROJECT_ROOT,
            storage_slug=slug,
            rows=req.rows,
            paths=paths,
            align_to_inputs=req.align_to_inputs,
            user_locked=True,
        )
    except MetadataEditorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/api/sessions/{session_id}/metadata/infer")
def infer_session_metadata(session_id: str):
    sess = db_get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    from web_frontend.backend.metadata_editor import MetadataEditorError, infer_metadata_from_inputs

    slug = resolve_storage_slug(session_id)
    try:
        paths = _session_metadata_paths(session_id)
    except Exception:
        paths = None
    try:
        result = infer_metadata_from_inputs(
            project_root=PROJECT_ROOT,
            storage_slug=slug,
            paths=paths,
            preserve_user_locked=True,
        )
    except MetadataEditorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
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
    sess, _ = _sync_workflow_for_existing_outputs(session_id, sess)
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
    sess, _ = _sync_workflow_for_existing_outputs(session_id, sess)
    return {"session": {"id": sess["id"], "title": sess["title"], "workflow_status": sess.get("workflow_status")}, "messages": db_get_messages(session_id)}


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


def _append_chat_images_marker(text: str, files: list[str]) -> str:
    """助手消息末尾写入隐藏标记；同底图只保留当前生效 intent/edited 版。"""
    clean = [str(f).strip() for f in files if str(f).strip()]
    if not clean:
        return text
    ordered = prefer_effective_among_rels(clean)
    marker = f"<!--massagent:chat_images:{json.dumps(ordered, ensure_ascii=False)}-->"
    body = (text or "").rstrip()
    if "<!--massagent:chat_images:" in body:
        body = re.sub(
            r"\n*<!--massagent:chat_images:\[.*?\]-->\s*$",
            "",
            body,
            flags=re.DOTALL,
        )
    return f"{body}\n\n{marker}"


def _should_auto_agent(session_id: str, user_message: str) -> bool:
    """规划 / 确认 / 执行 / 出图 / 改图 时走编排器，闲聊仍走纯 LLM。"""
    from web_frontend.backend.workflow import is_plan_confirmation

    sess = db_get_session(session_id) or {}
    sess, has_figs = _sync_workflow_for_existing_outputs(session_id, sess)
    action, _, _ = _resolve_session_chat_action(
        session_id, user_message, sess, has_figs=has_figs
    )
    if action not in {"chat", "clarify", "remind_confirm", "remind_rerun"}:
        return True
    return looks_like_agent_request(user_message) or is_plan_confirmation(user_message)


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

    from web_frontend.backend.workflow import is_plan_confirmation

    sess, has_figs = _sync_workflow_for_existing_outputs(req.session_id, sess)
    action, clarify_msg, router_meta = _resolve_session_chat_action(
        req.session_id, stream_user_message, sess, has_figs=has_figs
    )
    print(
        f"[workflow] status={sess.get('workflow_status')} action={action} "
        f"rule={router_meta.get('rule_action')} router={router_meta.get('router_used')} "
        f"msg={stream_user_message[:120]!r}",
        flush=True,
    )

    if action == "clarify" and clarify_msg:
        return StreamingResponse(
            _stream_plain_sse_async(req, clarify_msg),
            media_type="text/event-stream",
            headers=headers,
        )

    if action == "remind_confirm":
        return StreamingResponse(
            _stream_plain_sse_async(
                req,
                (
                    "分析计划已在上方生成，当前处于 **待确认** 状态，无需重复发送完整分析目标。\n\n"
                    "请直接回复 **确认计划** 启动 Agent B 执行；"
                    "若需修改方案，请说明具体修改意见（例如「第三步改用 MZmine」）。"
                ),
            ),
            media_type="text/event-stream",
            headers=headers,
        )
    if action == "remind_rerun":
        return StreamingResponse(
            _stream_plain_sse_async(
                req,
                (
                    "本会话已有确认过的分析计划与结果。\n\n"
                    "若需 **重跑 Agent B 分析**，请回复 **重新分析** 或 **确认计划**；"
                    "若需 **写报告/出图**，请说「写报告」或「按方案出图」；"
                    "若需 **修订计划**，请说明修改意见。"
                ),
            ),
            media_type="text/event-stream",
            headers=headers,
        )

    if action == "refuse_unconfirmed":
        return StreamingResponse(
            _stream_plain_sse_async(
                req,
                (
                    "当前计划尚未确认，**不能启动分析**。"
                    "请回复「确认计划」，或直接说明修改意见（例如改用 MZmine、不要分子网络）。"
                ),
            ),
            media_type="text/event-stream",
            headers=headers,
        )
    if action == "refuse_visual_early":
        return StreamingResponse(
            _stream_plain_sse_async(
                req,
                (
                    "改图/拼图在分析完成并出图之后进行。"
                    "请先确认计划并执行；若要改方案，请直接说明修改意见。"
                ),
            ),
            media_type="text/event-stream",
            headers=headers,
        )
    if action == "visual":
        from web_frontend.backend.image_merge_registry import (
            looks_like_merged_figure_edit_request,
            should_route_image_merge,
        )
        from web_frontend.backend.plot_edit_registry import should_route_plot_edit
        from web_frontend.backend.visual_message_router import split_compound_visual_message

        plot_msg, merge_msg = split_compound_visual_message(stream_user_message)
        if not plot_msg and should_route_plot_edit(stream_user_message):
            plot_msg = stream_user_message
        if not merge_msg and (
            looks_like_merged_figure_edit_request(stream_user_message)
            or should_route_image_merge(stream_user_message)
        ):
            merge_msg = stream_user_message

        if plot_msg and merge_msg:
            return StreamingResponse(
                _stream_compound_visual_sse_async(
                    req, request, plot_message=plot_msg, merge_message=merge_msg
                ),
                media_type="text/event-stream",
                headers=headers,
            )
        if merge_msg:
            return StreamingResponse(
                _stream_image_merge_sse_async(req, request, message=merge_msg),
                media_type="text/event-stream",
                headers=headers,
            )
        if plot_msg:
            return StreamingResponse(
                _stream_plot_edit_sse_async(req, request, message=plot_msg),
                media_type="text/event-stream",
                headers=headers,
            )

    if action == "plan":
        return StreamingResponse(
            _stream_orchestrated_sse_async(req, request, action="plan"),
            media_type="text/event-stream",
            headers=headers,
        )
    if action == "execute":
        return StreamingResponse(
            _stream_orchestrated_sse_async(req, request, action="execute"),
            media_type="text/event-stream",
            headers=headers,
        )
    if action == "report":
        return StreamingResponse(
            _stream_orchestrated_sse_async(req, request, action="report"),
            media_type="text/event-stream",
            headers=headers,
        )

    if use_agent and action != "chat":
        return StreamingResponse(
            _stream_orchestrated_sse_async(req, request, action="plan"),
            media_type="text/event-stream",
            headers=headers,
        )

    from web_frontend.backend.web_llm import reset_llm_override

    llm_token = _apply_request_llm_override(req)
    try:
        client = LLM_Client(model=req.model)
    except ValueError as exc:
        reset_llm_override(llm_token)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    history = db_get_messages(req.session_id)
    context = [{"role": m["role"], "content": m["content"]} for m in history]
    # 纯对话模式：禁止声称已写文件 / 已跑分析（防幻觉）
    payload = chat_guard_messages() + context + [
        {"role": "user", "content": stream_user_message}
    ]

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
        finally:
            reset_llm_override(llm_token)

    return StreamingResponse(gen_llm(), media_type="text/event-stream", headers=headers)


@app.post("/api/sessions/{session_id}/cancel")
async def cancel_session_agent(session_id: str):
    """前端「终止」：置取消标志，并尽力杀掉已登记的子进程（如 Rscript）。"""
    cancelled = await cancel_job(session_id)
    return {"ok": True, "cancelled": cancelled}


async def _stream_plain_sse_async(req: ChatStreamRequest, text: str):
    yield _sse_pack({"delta": text})
    time_str = db_append_message(req.session_id, "assistant", text)
    sess = db_get_session(req.session_id) or {}
    yield _sse_pack(
        {
            "done": True,
            "time": time_str,
            "finished": True,
            "workflow_status": sess.get("workflow_status"),
        }
    )


async def _stream_orchestrated_sse_async(req: ChatStreamRequest, request: Request, *, action: str):
    from web_frontend.backend.workflow import (
        AWAITING_APPROVAL,
        COMPLETED,
        EXECUTING,
        FAILED,
        PLANNING,
        REPORTING,
    )

    if action == "plan":
        db_set_workflow(req.session_id, PLANNING, bump_plan=True)
        async for pack in _stream_agent_sse_async(req, request, mode="plan"):
            yield pack
        return
    if action == "execute":
        db_set_workflow(req.session_id, EXECUTING, lock_plan=True)
        async for pack in _stream_agent_sse_async(
            req, request, mode="execute", chain_agent_c=True
        ):
            yield pack
        return
    db_set_workflow(req.session_id, REPORTING)
    async for pack in _stream_agent_c_sse_async(req, request, intent="c_report"):
        yield pack
    sess = db_get_session(req.session_id) or {}
    if sess.get("workflow_status") == REPORTING:
        db_set_workflow(req.session_id, COMPLETED)


async def _stream_agent_c_sse_async(req: ChatStreamRequest, request: Request, *, intent: str):
    """前端 Agent C：出图/报告，或把分析计算交接给 B。不启动 MCP。"""
    from web_frontend.backend.agent_c.session_chat import stream_session_agent_c

    parts: list[str] = []
    final_error = None
    visual_results: list = []
    chat_images: list = []
    agent_c_report: dict | None = None
    storage_slug = resolve_storage_slug(req.session_id)
    cancel_event = await register_job(req.session_id)

    try:
        yield _sse_pack({"delta": ""})
        for event in stream_session_agent_c(
            project_root=PROJECT_ROOT,
            session_id=req.session_id,
            storage_slug=storage_slug,
            user_message=req.user_message,
            intent=intent,
            goal_text=_session_plot_goal(req.session_id),
        ):
            if is_cancelled(cancel_event):
                yield _sse_pack({"delta": "\n\n⚠️ **已终止**\n"})
                break
            if "delta" in event:
                parts.append(event["delta"])
                yield _sse_pack({"delta": event["delta"]})
            elif "error" in event:
                final_error = event["error"]
                parts.append(f"\n❌ {final_error}\n")
                yield _sse_pack({"delta": f"\n❌ {final_error}\n"})
            if event.get("chat_image"):
                img = event["chat_image"]
                chat_images.append(img)
                yield _sse_pack({"chat_image": img})
            if event.get("visual_results"):
                visual_results = event["visual_results"]
            if event.get("agent_c_report"):
                agent_c_report = event["agent_c_report"]

        text = "".join(parts) or (final_error or "Agent C 未产生输出")
        chat_files = [
            str(item.get("file") or "").strip()
            for item in chat_images
            if isinstance(item, dict) and item.get("file")
        ]
        vr_files = [
            str(item.get("file") or "").strip()
            for item in visual_results
            if isinstance(item, dict) and str(item.get("file") or "").strip()
        ]
        chat_files = prefer_effective_among_rels([*chat_files, *vr_files])
        text = _append_chat_images_marker(text, chat_files)
        time_str = db_append_message(req.session_id, "assistant", text)
        done_payload = {
            "done": True,
            "time": time_str,
            "error": final_error,
            "finished": not bool(final_error),
            "agent_role": "C",
        }
        if visual_results:
            done_payload["visual_results"] = visual_results
        if chat_files:
            done_payload["chat_images"] = chat_files
        if agent_c_report:
            done_payload["agent_c_report"] = agent_c_report
        sess_now = db_get_session(req.session_id) or {}
        done_payload["workflow_status"] = sess_now.get("workflow_status")
        yield _sse_pack(done_payload)
    except Exception as exc:
        err_msg = f"Agent C 失败: {exc}"
        parts.append(f"\n❌ {err_msg}\n")
        yield _sse_pack({"delta": f"\n❌ {err_msg}\n"})
        if parts:
            db_append_message(req.session_id, "assistant", "".join(parts))
        yield _sse_pack({"done": True, "error": err_msg, "finished": False, "agent_role": "C"})
    finally:
        await clear_job(req.session_id)


async def _stream_agent_sse_async(
    req: ChatStreamRequest,
    request: Request,
    *,
    mode: str = "full",
    chain_agent_c: bool = False,
):
    """Agent A 规划或 Agent B 执行。chain_agent_c 时 B 成功后自动调用独立的 Agent C。"""
    from web_frontend.backend.agent_c.session_chat import stream_session_agent_c
    from web_frontend.backend.agent_runner import stream_agent_pipeline
    from web_frontend.backend.web_llm import reset_llm_override
    from web_frontend.backend.workflow import AWAITING_APPROVAL, COMPLETED, FAILED, REPORTING

    parts: list[str] = []
    final_error = None
    was_cancelled = False
    visual_results: list = []
    chat_images: list = []
    agent_c_report: dict | None = None
    storage_slug = resolve_storage_slug(req.session_id)
    cancel_event = await register_job(req.session_id)
    recent_messages = db_get_messages(req.session_id)[-12:]
    llm_token = _apply_request_llm_override(req)

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
            persist_dir=LITERATURE_PERSIST_DIR,
            source_dir=LITERATURE_SOURCE_DIR,
            model=req.model,
            temperature=req.temperature,
            llm_api_key=req.llm_api_key,
            llm_base_url=req.llm_base_url,
            cancel_event=cancel_event,
            is_disconnected=_client_gone,
            recent_messages=recent_messages,
            mode=mode,
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
            if event.get("chat_image"):
                img = event["chat_image"]
                chat_images.append(img)
                yield _sse_pack({"chat_image": img})
            if event.get("visual_results"):
                visual_results = event["visual_results"]
            if event.get("plan_ready"):
                db_set_workflow(req.session_id, AWAITING_APPROVAL)
            if event.get("execute_done"):
                if event.get("had_tool_failure"):
                    db_set_workflow(req.session_id, FAILED)
                elif chain_agent_c and not was_cancelled and not final_error:
                    db_set_workflow(req.session_id, REPORTING)
                    yield _sse_pack({"delta": "\n\n---\n🎨 **Agent C**：按方案与结果出图并写报告…\n\n"})
                    parts.append("\n\n---\n🎨 **Agent C**：按方案与结果出图并写报告…\n\n")
                    for cev in stream_session_agent_c(
                        project_root=PROJECT_ROOT,
                        session_id=req.session_id,
                        storage_slug=storage_slug,
                        user_message=req.user_message,
                        intent="c_report",
                        goal_text=_session_plot_goal(req.session_id),
                    ):
                        if is_cancelled(cancel_event):
                            was_cancelled = True
                            break
                        if "delta" in cev:
                            parts.append(cev["delta"])
                            yield _sse_pack({"delta": cev["delta"]})
                        elif "error" in cev:
                            final_error = cev["error"]
                            parts.append(f"\n❌ {final_error}\n")
                            yield _sse_pack({"delta": f"\n❌ {final_error}\n"})
                        if cev.get("chat_image"):
                            img = cev["chat_image"]
                            chat_images.append(img)
                            yield _sse_pack({"chat_image": img})
                        if cev.get("visual_results"):
                            visual_results = cev["visual_results"]
                        if cev.get("agent_c_report"):
                            agent_c_report = cev["agent_c_report"]
                    if not was_cancelled:
                        db_set_workflow(
                            req.session_id, FAILED if final_error else COMPLETED
                        )
                elif not was_cancelled and not final_error:
                    db_set_workflow(req.session_id, COMPLETED)

        if is_cancelled(cancel_event) or was_cancelled:
            if not any("已终止" in p or "已执行完毕" in p for p in parts[-3:]):
                parts.append("\n\n⚠️ **已终止**\n")
                yield _sse_pack({"delta": "\n\n⚠️ **已终止**\n"})

        if final_error or was_cancelled:
            cur = (db_get_session(req.session_id) or {}).get("workflow_status")
            if cur in {"PLANNING", "EXECUTING", "REPORTING"}:
                db_set_workflow(req.session_id, FAILED)

        text = "".join(parts) or (final_error or "Agent 未产生输出")
        chat_files = [
            str(item.get("file") or "").strip()
            for item in chat_images
            if isinstance(item, dict) and item.get("file")
        ]
        # 任意分析产物：合并 visual_results → 聊天预览（同底图优先 intent）
        vr_files = [
            str(item.get("file") or "").strip()
            for item in visual_results
            if isinstance(item, dict) and str(item.get("file") or "").strip()
        ]
        chat_files = prefer_effective_among_rels([*chat_files, *vr_files])
        text = _append_chat_images_marker(text, chat_files)
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
        if chat_files:
            done_payload["chat_images"] = chat_files
        if agent_c_report:
            done_payload["agent_c_report"] = agent_c_report
        sess_now = db_get_session(req.session_id) or {}
        done_payload["workflow_status"] = sess_now.get("workflow_status")
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
        db_set_workflow(req.session_id, FAILED)
    finally:
        reset_llm_override(llm_token)
        await clear_job(req.session_id)


async def _stream_plot_edit_sse_async(
    req: ChatStreamRequest, request: Request, *, message: str | None = None
):
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
    user_message = (message or req.user_message or "").strip()

    try:
        yield _sse_pack({"delta": ""})
        for event in stream_chat_plot_edit_deltas(
            project_root=PROJECT_ROOT,
            session_id=req.session_id,
            storage_slug=storage_slug,
            message=user_message,
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


async def _stream_image_merge_sse_async(
    req: ChatStreamRequest, request: Request, *, message: str | None = None
):
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
    user_message = (message or req.user_message or "").strip()

    try:
        yield _sse_pack({"delta": ""})
        for event in stream_chat_image_merge_deltas(
            project_root=PROJECT_ROOT,
            session_id=req.session_id,
            storage_slug=storage_slug,
            message=user_message,
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


async def _stream_compound_visual_sse_async(
    req: ChatStreamRequest,
    request: Request,
    *,
    plot_message: str,
    merge_message: str,
):
    """同一条消息内先改图、再拼图。"""
    from web_frontend.backend.image_merge_chat import stream_chat_image_merge_deltas
    from web_frontend.backend.plot_edit_chat import stream_chat_plot_edit_deltas

    parts: list[str] = []
    final_error = None
    plot_ok = False
    merge_ok = False
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
            message=plot_message,
            model=model,
        ):
            if "delta" in event:
                parts.append(event["delta"])
                yield _sse_pack({"delta": event["delta"]})
            elif event.get("plot_edit_done"):
                plot_ok = True
            elif "error" in event:
                final_error = event["error"]

        parts.append("\n---\n\n")
        yield _sse_pack({"delta": "\n---\n\n"})

        for event in stream_chat_image_merge_deltas(
            project_root=PROJECT_ROOT,
            session_id=req.session_id,
            storage_slug=storage_slug,
            message=merge_message,
            model=model,
        ):
            if "delta" in event:
                parts.append(event["delta"])
                yield _sse_pack({"delta": event["delta"]})
            elif event.get("image_merge_done"):
                merge_ok = True
            elif "error" in event:
                final_error = event["error"]

        text = "".join(parts) or (final_error or "改图/拼图未产生输出")
        time_str = db_append_message(req.session_id, "assistant", text)
        yield _sse_pack(
            {
                "done": True,
                "time": time_str,
                "error": final_error,
                "finished": (plot_ok or merge_ok) and not final_error,
                "plot_edit": True,
                "image_merge": True,
            }
        )
    except Exception as exc:
        err_msg = f"改图/拼图失败: {exc}"
        parts.append(f"\n❌ {err_msg}\n")
        yield _sse_pack({"delta": f"\n❌ {err_msg}\n"})
        if parts:
            db_append_message(req.session_id, "assistant", "".join(parts))
        yield _sse_pack(
            {
                "done": True,
                "error": err_msg,
                "finished": False,
                "plot_edit": True,
                "image_merge": True,
            }
        )


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
