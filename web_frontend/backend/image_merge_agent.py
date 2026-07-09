"""Agent：将自然语言拼图编辑要求解析为 merge options patch。"""
from __future__ import annotations

import json
from typing import Any

from web_frontend.backend.json_parse import extract_first_json_object
from web_frontend.backend.web_llm import WebLLMClient

_MERGE_EDIT_SCHEMA = """{
  "cols": 2,
  "label_mode": "upper|lower|num|none|custom",
  "label_font_size": 28,
  "gap": 24,
  "custom_labels": {"0": "A", "1": "B"}
}"""


def _build_merge_edit_prompt(
    *,
    current_options: dict[str, Any],
    sources: list[str],
    instruction: str,
) -> str:
    return f"""你是科研论文拼图排版助手。用户已有一张由多张分析子图拼合而成的 figure，现在要调整排版参数（子图标签、字号、列数、间距等）。

子图来源（按从左到右、从上到下顺序）：
{json.dumps(sources, ensure_ascii=False, indent=2)}

当前拼图参数：
{json.dumps(current_options, ensure_ascii=False, indent=2)}

用户调整要求：
{instruction.strip()}

请只输出一个 JSON 对象，包含**需要修改**的字段（未提及的不要输出）：
{_MERGE_EDIT_SCHEMA}

规则：
- label_mode: upper=A/B/C, lower=a/b/c, num=1/2/3, none=无标签, custom=使用 custom_labels
- custom_labels 的键用子图序号字符串 "0","1",...（从 0 开始），值为标签文字
- cols 为列数；gap 为像素间距
- 不要输出 markdown 或解释
"""


def parse_merge_edit_instruction(
    *,
    instruction: str,
    current_options: dict[str, Any],
    sources: list[str],
    model: str | None = None,
) -> dict[str, Any]:
    if not instruction.strip():
        raise ValueError("拼图编辑说明不能为空")

    llm = WebLLMClient(model=model)
    prompt = _build_merge_edit_prompt(
        current_options=current_options,
        sources=sources,
        instruction=instruction,
    )
    raw = llm.think_complete([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=1024)
    if not raw:
        raise RuntimeError("LLM 未返回有效内容，请检查 API 配置")

    patch = extract_first_json_object(raw)
    if not patch:
        raise RuntimeError(f"无法解析 Agent 返回的拼图参数：{raw[:500]}")
    return patch
