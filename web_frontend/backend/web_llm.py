"""Web 专用 LLM 客户端（支持静默流式输出、可覆盖模型与用户自备 API）。"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Dict, Iterator, List, Optional

from langchain_openai import ChatOpenAI

# 单次请求内覆盖服务端 .env（浏览器弹窗配置的用户 API）
_llm_override: ContextVar[dict | None] = ContextVar("llm_override", default=None)


def format_llm_api_error(exc: BaseException) -> str:
    """把供应商错误转成可读中文提示（避免前端只看到「返回为空」）。"""
    from web_frontend.backend.llm_security import redact_secrets

    text = redact_secrets(str(exc))
    lower = text.lower()
    if (
        "arrearage" in lower
        or "overdue-payment" in lower
        or "欠费" in text
        or "insufficient balance" in lower
        or "402" in text
        or "payment required" in lower
    ):
        return (
            "模型服务商返回余额不足 / 需要付费（HTTP 402）。"
            "请到对应控制台充值后再测："
            "DeepSeek → https://platform.deepseek.com ；"
            "阿里云百炼 → https://bailian.console.aliyun.com/ 。"
            "确认 Key、Base URL、模型名属于同一家服务商。"
            f" 详情：{text}"
        )
    if "invalid_api_key" in lower or "incorrect api key" in lower or (
        "401" in text and "unauthorized" in lower
    ):
        return f"API Key 无效或未授权，请检查 API Key。原始错误：{text}"
    if "429" in text or "rate limit" in lower or "quota" in lower:
        return f"调用频率或配额超限，请稍后重试。原始错误：{text}"
    if "timeout" in lower or "timed out" in lower:
        return f"调用 LLM 超时，可增大 LLM_TIMEOUT 后重试。原始错误：{text}"
    if "connect" in lower or "network" in lower or "name or service not known" in lower:
        return f"无法连接 LLM 服务，请检查网络与 Base URL。原始错误：{text}"
    m = re.search(r"Error code:\s*(\d+)\s*-\s*(\{.*\})", text, re.DOTALL)
    if m:
        return f"LLM API 错误（HTTP {m.group(1)}）：{m.group(2)}"
    return f"调用 LLM API 失败：{text}"


def set_llm_override(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> object:
    """设置当前异步/线程上下文的 LLM 覆盖；返回 token 供 reset。"""
    from web_frontend.backend.llm_security import assert_safe_llm_override

    safe_key, safe_url = assert_safe_llm_override(api_key=api_key, base_url=base_url)
    payload: dict[str, str] = {}
    if safe_key:
        payload["api_key"] = safe_key
    if safe_url:
        payload["base_url"] = safe_url
    if model and str(model).strip():
        payload["model"] = str(model).strip()
    return _llm_override.set(payload or None)


def reset_llm_override(token: object | None = None) -> None:
    """结束请求时清理 LLM 覆盖。

    StreamingResponse 的 generator finally 常落在不同 Context，
    ContextVar.reset(token) 会抛 ValueError —— 因此优先 set(None)，reset 失败则忽略。
    """
    try:
        _llm_override.set(None)
    except Exception:
        pass
    if token is None:
        return
    try:
        _llm_override.reset(token)  # type: ignore[arg-type]
    except ValueError:
        pass
    except Exception:
        pass


@contextmanager
def llm_override_context(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
):
    token = set_llm_override(api_key=api_key, base_url=base_url, model=model)
    try:
        yield
    finally:
        reset_llm_override(token)


def get_llm_override() -> dict:
    return dict(_llm_override.get() or {})


class WebLLMClient:
    def __init__(
        self,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        override = get_llm_override()
        self.model = (
            (model or "").strip()
            or override.get("model")
            or (os.getenv("LLM_MODEL_ID") or "").strip()
        )
        resolved_key = (
            (api_key or "").strip()
            or override.get("api_key")
            or (os.getenv("LLM_API_KEY") or "").strip()
        )
        resolved_base = (
            (base_url or "").strip().rstrip("/")
            or override.get("base_url")
            or (os.getenv("LLM_BASE_URL") or "").strip().rstrip("/")
        )
        self.timeout = int(timeout or os.getenv("LLM_TIMEOUT", "180"))

        if not all([self.model, resolved_key, resolved_base]):
            raise ValueError(
                "请配置模型、API Key 与 Base URL（工具栏「API 设置」或服务端 .env）"
            )

        self.llm = ChatOpenAI(
            model=self.model,
            api_key=resolved_key,
            base_url=resolved_base,
            timeout=self.timeout,
            temperature=0.0,
        )

    def think(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        stream_to_stdout: bool = False,
    ) -> Optional[str]:
        try:
            response = self.llm.stream(input=messages, temperature=temperature)
            parts: list[str] = []
            for chunk in response:
                content = chunk.content
                if not content:
                    continue
                if stream_to_stdout:
                    print(content, end="", flush=True)
                parts.append(content)
            if stream_to_stdout and parts:
                print()
            return "".join(parts)
        except Exception as exc:
            msg = format_llm_api_error(exc)
            print(f"❌ {msg}", flush=True)
            raise RuntimeError(msg) from exc

    def stream_think(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
    ) -> Iterator[str]:
        """流式生成，逐块 yield 文本（供非 Agent 聊天 SSE 使用）。"""
        try:
            response = self.llm.stream(input=messages, temperature=temperature)
            for chunk in response:
                content = chunk.content
                if content:
                    yield content
        except Exception as exc:
            raise RuntimeError(format_llm_api_error(exc)) from exc

    def think_complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> Optional[str]:
        """非流式调用，适合生成较长 JSON 计划，避免截断。"""
        try:
            resp = self.llm.invoke(
                input=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = getattr(resp, "content", None) or str(resp)
            return content if content else None
        except Exception as exc:
            msg = format_llm_api_error(exc)
            print(f"❌ {msg}", flush=True)
            raise RuntimeError(msg) from exc


__all__ = [
    "WebLLMClient",
    "format_llm_api_error",
    "set_llm_override",
    "reset_llm_override",
    "llm_override_context",
    "get_llm_override",
]
