"""Web 端文献检索：接入 softwares_database / softwares_database_RAG。

优先向量 RAG（与 CLI PromptGenerator 同索引）；embedding API 失败或未配置时回退到
关键词检索，保证前端规划链路仍能注入文献/方法学上下文。
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any

_CN_EN_KEYWORDS = {
    "代谢组": "metabolomics",
    "脂质组": "lipidomics",
    "统计分析": "statistical analysis",
    "火山图": "volcano plot",
    "差异代谢物": "differential metabolites",
    "分子网络": "molecular networking",
    "峰检测": "peak detection",
    "峰对齐": "peak alignment",
    "缺失值": "missing value imputation",
    "批次效应": "batch effect correction",
    "谱库匹配": "spectral library matching",
    "未知物": "de novo identification",
    "通路分析": "pathway analysis",
    "富集": "enrichment",
    "余弦": "cosine similarity",
    "拓扑": "network topology",
}

_TOOL_HINTS = {
    "xcms": ["XCMS", "data_preprocessing_xcms", "centWave"],
    "mzmine": ["MZMine", "MZmine", "data_preprocessing_mzmine"],
    "openms": ["OpenMS", "data_preprocessing_openms"],
    "mixomics": ["mixOmics", "statistical_analysis_mixomics", "PCA", "PLS-DA"],
    "gnps": ["GNPS", "molecular_networking_gnps"],
    "fbmn": ["FBMN", "molecular_networking_fbmn"],
    "ms2lda": ["MS2LDA", "molecular_networking_ms2lda"],
    "kegg": ["KEGG", "kegg_compound_enrichment"],
    "deepmass": ["DeepMASS", "deepmass_annotation"],
    "sirius": ["SIRIUS"],
    "metaboanalyst": ["MetaboAnalyst"],
}

_MAX_CONTEXT_CHARS = 10000
_MAX_FALLBACK_FILES = 4
_MAX_FILE_CHARS = 2800
# DashScope text-embedding-v2: input length [1, 2048] tokens — keep query short (chars << tokens for CJK)
_EMBED_QUERY_MAX_CHARS = int(os.getenv("WEB_LITERATURE_QUERY_MAX_CHARS", "1200") or 1200)
_EMBED_USER_MAX_CHARS = int(os.getenv("WEB_LITERATURE_USER_MAX_CHARS", "600") or 600)
_EMBED_GOAL_MAX_CHARS = int(os.getenv("WEB_LITERATURE_GOAL_MAX_CHARS", "400") or 400)

_retriever_lock = threading.Lock()
_retriever_cache: dict[str, Any] = {}
_vector_disabled_reason: str | None = None


def _ensure_dotenv() -> None:
    """webapp 已 load_dotenv；独立调用时补一次，避免未配置 LLM_MODEL_TYPE 误走 HF。"""
    if os.getenv("LLM_MODEL_TYPE"):
        return
    try:
        from dotenv import load_dotenv

        root = Path(__file__).resolve().parents[2]
        load_dotenv(root / ".env", override=False)
    except Exception:
        pass


def _vector_backend_ready() -> bool:
    """仅在明确配置了云端 embedding 时走向量检索，避免默认 HuggingFace 卡住。"""
    _ensure_dotenv()
    mt = (os.getenv("LLM_MODEL_TYPE") or "").strip().lower()
    if mt in {"openai", "dashscope"}:
        return True
    # 显式允许本地向量（需本机已缓存 embedding 模型）
    return (os.getenv("WEB_LITERATURE_ALLOW_LOCAL_EMBED") or "").strip() in {
        "1",
        "true",
        "yes",
    }


def enhance_query(query: str) -> str:
    """中文查询追加英文关键词，提升英文文献库召回。"""
    text = (query or "").strip()
    if not text:
        return text
    if not re.search(r"[\u4e00-\u9fff]", text):
        return text
    en_terms = [en for cn, en in _CN_EN_KEYWORDS.items() if cn in text]
    if en_terms:
        return f"{text}\n[English keywords: {', '.join(en_terms)}]"
    return text


def clamp_embedding_query(query: str, *, max_chars: int | None = None) -> str:
    """硬截断文献检索查询，确保不超过 DashScope embedding 输入上限。"""
    limit = max_chars if max_chars is not None else _EMBED_QUERY_MAX_CHARS
    text = (query or "").strip()
    if not text:
        return "metabolomics analysis workflow"
    if len(text) <= limit:
        return text
    return text[: max(80, limit - 24)].rstrip() + "\n...(truncated)"


def compact_literature_goal(goal_description: str, *, max_chars: int | None = None) -> str:
    """从冗长的 Agent goal prompt 提取短摘要，供向量 embedding 使用。"""
    budget = max_chars if max_chars is not None else _EMBED_GOAL_MAX_CHARS
    text = (goal_description or "").strip()
    if not text:
        return ""

    # build_web_goal_description 中的用户意图块
    m = re.search(
        r"CURRENT user request[^\n]*\n(.*?)(?:\n\nRecent conversation|\Z)",
        text,
        re.S | re.I,
    )
    if m and m.group(1).strip():
        text = m.group(1).strip()
    else:
        # 回退：取前若干非空行，跳过明显是系统提示的长段落
        kept: list[str] = []
        for ln in text.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.startswith(
                (
                    "Allowed tools",
                    "Default recommended",
                    "Alternatives (",
                    "CRITICAL path",
                    "Path roots:",
                    "Platform:",
                    "ANTI-HALLUCINATION",
                    "You MUST call tools",
                )
            ):
                break
            if re.match(r"^\d+\.\s", s) and len(s) > 100:
                continue
            kept.append(s)
            if sum(len(x) for x in kept) >= budget * 2:
                break
        if kept:
            text = " ".join(kept)

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > budget:
        text = text[: max(40, budget - 3)].rstrip() + "..."
    return text


def _normalize_user_message_for_literature(user_message: str) -> str:
    user = (user_message or "").strip()
    for marker in ("[已上传附件]", "[Attachments uploaded]"):
        if marker in user:
            user = user.split(marker)[0].strip()
    user = re.sub(r"\s+", " ", user)
    if len(user) > _EMBED_USER_MAX_CHARS:
        user = user[: max(40, _EMBED_USER_MAX_CHARS - 3)].rstrip() + "..."
    return user


def _truncate(text: str, limit: int = _MAX_CONTEXT_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n...(truncated)"


def _get_vector_retriever(persist_dir: str, source_dir: str, top_k: int):
    key = f"{Path(persist_dir).resolve()}|{top_k}"
    with _retriever_lock:
        cached = _retriever_cache.get(key)
        if cached is not None:
            return cached
        from src.build_RAG_private import preload_retriever

        retriever = preload_retriever(
            PERSIST_DIR=persist_dir,
            SOURCE_DIR=source_dir,
            similarity_top_k=top_k,
        )
        _retriever_cache[key] = retriever
        return retriever


def _vector_retrieve(query: str, persist_dir: str, source_dir: str, top_k: int) -> str | None:
    global _vector_disabled_reason
    if _vector_disabled_reason:
        return None
    if not _vector_backend_ready():
        _vector_disabled_reason = "embedding_backend_not_configured"
        return None
    persist = Path(persist_dir)
    if not persist.is_dir() or not (persist / "docstore.json").is_file():
        _vector_disabled_reason = "rag_index_missing"
        return None

    def _run() -> str | None:
        from src.build_RAG_private import retrive

        retriever = _get_vector_retriever(persist_dir, source_dir, top_k)
        safe_prompt = clamp_embedding_query(enhance_query(query))
        text = retrive(retriever, retriever_prompt=safe_prompt)
        if text == "Retrieval error" or (text or "").startswith("Retrieval error"):
            raise RuntimeError("Retrieval error from embedding backend")
        if not text or text in {
            "No context",
            "No relevant information found",
        }:
            return None
        return text

    # 首次加载索引/嵌入较慢；可用 WEB_LITERATURE_VECTOR_TIMEOUT 覆盖
    timeout_s = float(os.getenv("WEB_LITERATURE_VECTOR_TIMEOUT", "60") or 60)
    try:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            try:
                return fut.result(timeout=max(8.0, timeout_s))
            except FuturesTimeout:
                # 冷启动加载大索引可能超时：不永久禁用，便于预热后再试
                print(f"[literature_rag] vector retrieve timed out after {timeout_s}s (not permanently disabled)")
                return None
    except Exception as exc:
        msg = str(exc)
        # API/鉴权类失败才禁用；超时与偶发错误允许重试
        if "Retrieval error" in msg or "AccessDenied" in msg or "403" in msg:
            _vector_disabled_reason = f"vector_init_failed:{exc}"
        print(f"[literature_rag] vector retrieve failed: {exc}")
        return None


def _prefer_vector_mode() -> bool:
    """WEB_LITERATURE_VECTOR：1 强制开；0 强制关；默认 auto=云端 embedding 可用则开。"""
    flag = (os.getenv("WEB_LITERATURE_VECTOR") or "auto").strip().lower()
    if flag in {"0", "false", "no", "off", "lexical"}:
        return False
    if flag in {"1", "true", "yes", "on", "vector"}:
        return True
    return _vector_backend_ready()


def _query_terms(query: str) -> list[str]:
    q = enhance_query(query).lower()
    terms = set(re.findall(r"[a-z0-9_]{3,}|[\u4e00-\u9fff]{2,}", q))
    for key, hints in _TOOL_HINTS.items():
        if key in q or any(h.lower() in q for h in hints):
            terms.update(h.lower() for h in hints)
            terms.add(key)
    # 常见分析意图默认带上统计/可视化相关词，避免纯中文短句召回为空
    if any(x in q for x in ("统计", "pca", "pls", "火山", "差异", "分组")):
        terms.update({"pca", "pls-da", "volcano", "mixomics", "statistical"})
    if any(x in q for x in ("网络", "gnps", "fbmn", "motif", "余弦")):
        terms.update({"gnps", "fbmn", "molecular", "networking", "cosine"})
    return [t for t in terms if t not in {"the", "and", "for", "with", "from"}]


def _score_text(text: str, terms: list[str]) -> int:
    low = text.lower()
    return sum(low.count(t) for t in terms if t)


def _iter_fallback_candidates(source_dir: Path) -> list[Path]:
    preferred = [
        source_dir / "pipeline_overview.md",
        source_dir / "quality_control_standards.md",
        source_dir / "biological_interpretation_guide.md",
        source_dir / "data_preprocess_statistic_analysis.md",
        source_dir / "molecular_networking.md",
        source_dir / "redundant_feature_filtering.md",
    ]
    files = [p for p in preferred if p.is_file()]
    workflows = source_dir / "paper_workflows"
    if workflows.is_dir():
        files.extend(sorted(workflows.glob("*_workflows.txt")))
    # 工具卡片（根目录 txt）
    files.extend(sorted(source_dir.glob("*.txt")))
    # 去重保序
    seen: set[Path] = set()
    out: list[Path] = []
    for path in files:
        rp = path.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(path)
    return out


def _lexical_retrieve(query: str, source_dir: str) -> tuple[str, list[str]]:
    root = Path(source_dir)
    if not root.is_dir():
        return "", []
    terms = _query_terms(query)
    if not terms:
        terms = ["metabolomics", "pipeline", "workflow"]

    scored: list[tuple[int, Path, str]] = []
    for path in _iter_fallback_candidates(root):
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        score = _score_text(raw[:20000], terms)
        # 指南类文档稍微加权，避免被超长 workflow 淹没
        name = path.name.lower()
        if name.endswith(".md"):
            score = int(score * 1.4) + 2
        if "workflow" in name:
            score += 1
        if score <= 0:
            continue
        scored.append((score, path, raw))

    scored.sort(key=lambda x: (-x[0], str(x[1])))
    chunks: list[str] = []
    sources: list[str] = []
    for score, path, raw in scored[:_MAX_FALLBACK_FILES]:
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            rel = path.name
        snippet = raw.strip()
        if len(snippet) > _MAX_FILE_CHARS:
            snippet = snippet[:_MAX_FILE_CHARS] + "\n...(truncated)"
        chunks.append(f"--- Literature Document ({rel}, score={score}) ---\n{snippet}")
        sources.append(rel)
    return "\n\n".join(chunks), sources


def retrieve_literature(
    query: str,
    *,
    persist_dir: str,
    source_dir: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """检索文献/方法学上下文。

    默认（``WEB_LITERATURE_VECTOR=auto``）：云端 embedding 已配置时优先向量 RAG，
    失败则回退关键词；设为 ``0`` 可强制只用关键词。

    Returns:
        {
          "text": str,
          "mode": "vector" | "lexical" | "empty",
          "sources": list[str],
          "error": str | None,
          "prefer_vector": bool,
        }
    """
    q = (query or "").strip()
    if not q:
        return {
            "text": "",
            "mode": "empty",
            "sources": [],
            "error": "empty query",
            "prefer_vector": False,
        }

    prefer_vector = _prefer_vector_mode()

    if prefer_vector:
        vector_text = _vector_retrieve(q, persist_dir, source_dir, top_k)
        if vector_text:
            return {
                "text": _truncate(vector_text),
                "mode": "vector",
                "sources": ["softwares_database_RAG"],
                "error": None,
                "prefer_vector": True,
            }

    lexical_text, sources = _lexical_retrieve(q, source_dir)
    if lexical_text:
        err = None
        if prefer_vector and _vector_disabled_reason:
            err = f"vector_rag_unavailable_fallback_lexical:{_vector_disabled_reason}"
        elif prefer_vector:
            err = "vector_rag_unavailable_fallback_lexical"
        return {
            "text": _truncate(lexical_text),
            "mode": "lexical",
            "sources": sources,
            "error": err,
            "prefer_vector": prefer_vector,
        }

    if not prefer_vector:
        vector_text = _vector_retrieve(q, persist_dir, source_dir, top_k)
        if vector_text:
            return {
                "text": _truncate(vector_text),
                "mode": "vector",
                "sources": ["softwares_database_RAG"],
                "error": None,
                "prefer_vector": False,
            }

    return {
        "text": "",
        "mode": "empty",
        "sources": [],
        "error": _vector_disabled_reason or "no_literature_matched",
        "prefer_vector": prefer_vector,
    }


def warmup_literature_rag(
    *,
    persist_dir: str,
    source_dir: str,
    top_k: int = 3,
) -> dict[str, Any]:
    """启动时预热向量索引，避免首条用户消息卡在冷加载。"""
    return retrieve_literature(
        "metabolomics analysis pipeline statistical PCA molecular networking",
        persist_dir=persist_dir,
        source_dir=source_dir,
        top_k=top_k,
    )


def build_plan_literature_query(*, user_message: str, goal_description: str = "") -> str:
    """构建供向量/关键词检索的短查询（勿传入完整 Agent system goal）。"""
    user = _normalize_user_message_for_literature(user_message)
    short_goal = compact_literature_goal(goal_description)
    parts = [f"User request: {user}"]
    if short_goal and short_goal.lower() != user.lower():
        parts.append(f"Study goal: {short_goal}")
    parts.append(
        "Metabolomics: recommend published analysis pipelines, software tools, "
        "parameters, quality checks, and expected outputs for this study."
    )
    return clamp_embedding_query("\n".join(parts))


def build_tool_literature_query(*, goal_description: str, task: str) -> str:
    short_goal = compact_literature_goal(goal_description, max_chars=300)
    task_text = re.sub(r"\s+", " ", (task or "").strip())
    if len(task_text) > 500:
        task_text = task_text[:497].rstrip() + "..."
    parts = []
    if short_goal:
        parts.append(f"Study goal: {short_goal}")
    parts.append(f"Current step: {task_text}")
    parts.append(
        "What tool and parameters do published metabolomics studies recommend for this step?"
    )
    return clamp_embedding_query("\n".join(parts))


__all__ = [
    "retrieve_literature",
    "warmup_literature_rag",
    "enhance_query",
    "clamp_embedding_query",
    "compact_literature_goal",
    "build_plan_literature_query",
    "build_tool_literature_query",
]
