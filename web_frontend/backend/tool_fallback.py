"""可互换工具的等价组与回退顺序（Agent 在运行时依次尝试）。"""
from __future__ import annotations

from web_frontend.backend.constants import ALLOWED_TOOL_NAMES
from web_frontend.backend.plan_utils import RAW_CONVERTER_NAMES

# 组名 -> 组内工具（顺序无关，由各组自己的 order 函数决定）
TOOL_FALLBACK_GROUPS: dict[str, tuple[str, ...]] = {
    "raw_converter": RAW_CONVERTER_NAMES,
}

_GROUP_BY_TOOL: dict[str, str] = {
    tool: group for group, tools in TOOL_FALLBACK_GROUPS.items() for tool in tools
}


def tool_fallback_group(tool_name: str) -> str | None:
    return _GROUP_BY_TOOL.get(tool_name)


def tools_in_fallback_group(tool_name: str) -> list[str]:
    """返回与 tool_name 可互换、且在 Web 白名单内的工具列表。"""
    group = tool_fallback_group(tool_name)
    if not group:
        return []
    names = TOOL_FALLBACK_GROUPS.get(group, ())
    return [n for n in names if n in ALLOWED_TOOL_NAMES]


def has_tool_fallback(tool_name: str) -> bool:
    return len(tools_in_fallback_group(tool_name)) > 1
