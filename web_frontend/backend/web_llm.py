"""Web 专用 LLM 客户端（支持静默流式输出、可覆盖模型）。"""
from __future__ import annotations

import os
from typing import Dict, Iterator, List, Optional

from langchain_openai import ChatOpenAI


class WebLLMClient:
    def __init__(self, model: Optional[str] = None, timeout: Optional[int] = None):
        self.model = (model or os.getenv("LLM_MODEL_ID") or "").strip()
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        self.timeout = int(timeout or os.getenv("LLM_TIMEOUT", "180"))

        if not all([self.model, api_key, base_url]):
            raise ValueError("请在 .env 中配置 LLM_MODEL_ID、LLM_API_KEY、LLM_BASE_URL")

        self.llm = ChatOpenAI(
            model=self.model,
            api_key=api_key,
            base_url=base_url,
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
            if stream_to_stdout:
                print(f"❌ 调用 LLM API 时发生错误: {exc}")
            return None

    def stream_think(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
    ) -> Iterator[str]:
        """流式生成，逐块 yield 文本（供非 Agent 聊天 SSE 使用）。"""
        response = self.llm.stream(input=messages, temperature=temperature)
        for chunk in response:
            content = chunk.content
            if content:
                yield content

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
            print(f"❌ 调用 LLM API 时发生错误: {exc}")
            return None
