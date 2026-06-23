"""从 LLM 文本响应中稳健解析 JSON（含 tool_call / plan）。"""
from __future__ import annotations

import json
import re


def extract_first_json_object(text: str) -> dict:
    """按括号深度提取第一个完整 JSON 对象，避免尾部多余 `}` 导致解析失败。"""
    if not text:
        return {}
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned, re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()

    start = cleaned.find("{")
    if start < 0:
        return {}

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def parse_tool_call(raw: str) -> tuple[str | None, dict | None]:
    """解析 tool_call，返回 (name, arguments)。"""
    data = extract_first_json_object(raw)
    if "tool_call" in data and isinstance(data["tool_call"], dict):
        tc = data["tool_call"]
        name = tc.get("name")
        args = tc.get("arguments")
        if name and isinstance(args, dict):
            return str(name), args

    # 兜底：LLM 输出带尾部多余括号时，用正则提取
    m = re.search(
        r'"tool_call"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{[\s\S]*?\})\s*\}',
        raw or "",
    )
    if m:
        try:
            args = json.loads(m.group(2))
            if isinstance(args, dict):
                return m.group(1), args
        except json.JSONDecodeError:
            pass
    return None, None


def extract_plan_list(text: str) -> list[str]:
    """
    从 LLM 响应解析 plan 列表。
    完整 JSON 优先；若响应被截断（缺少结尾括号），用正则提取 "Use <tool> to ..." 步骤。
    """
    if not text:
        return []

    data = extract_first_json_object(text)
    plan = data.get("plan")
    if isinstance(plan, list) and plan:
        steps = [str(x).strip() for x in plan if str(x).strip()]
        if steps:
            return steps

    # 截断 JSON：尝试补全 plan 数组后解析
    start = text.find("{")
    if start >= 0:
        snippet = text[start:].strip()
        for suffix in ('"]}', '"]}', '"}', "}"):
            try:
                repaired = json.loads(snippet + suffix)
                plan = repaired.get("plan")
                if isinstance(plan, list) and plan:
                    return [str(x).strip() for x in plan if str(x).strip()]
            except json.JSONDecodeError:
                continue

    steps: list[str] = []
    for m in re.finditer(
        r'"(\s*Use\s+[a-zA-Z0-9_]+[^"]*)"',
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        step = m.group(1).strip()
        if step and step not in steps:
            steps.append(step)
    if steps:
        return steps

    for m in re.finditer(
        r"(Use\s+[a-zA-Z0-9_]+\s+to[^\n\]}\"]+)",
        text,
        re.IGNORECASE,
    ):
        step = m.group(1).strip().rstrip(".,;")
        if step and step not in steps:
            steps.append(step)
    return steps
