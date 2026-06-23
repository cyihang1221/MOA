"""Web 端 .raw → mzML 转换工具选择与失败回退。"""
from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from mcp.client.session import ClientSession

from src.platform_utils import preferred_raw_converter, resolve_docker, resolve_thermo_rawfile_parser

from web_frontend.backend.constants import ALLOWED_TOOL_NAMES
from web_frontend.backend.plan_utils import RAW_CONVERTER_NAMES, raw_conversion_complete
from web_frontend.backend.tool_args_normalizer import format_mcp_tool_result, is_mcp_tool_result_error
from web_frontend.backend.tool_runner import call_tool_with_heartbeat

_CONVERTER_SET = frozenset(RAW_CONVERTER_NAMES)


def is_raw_converter(tool_name: str) -> bool:
    return tool_name in _CONVERTER_SET


def build_conversion_plan_step(paths: dict[str, str], convert_tool: str) -> str:
    raw_in = paths.get("raw") or f"{paths['upload']}/raw"
    converted = paths["converted_mzml"]
    return (
        f"Use {convert_tool} to convert .raw files in {raw_in} "
        f"to mzML format in {converted}."
    )


def resolve_initial_raw_converter(tool_name: str) -> str:
    """执行前解析首选转换工具（ThermoRawFileParser 不可用时静默改用 msconvert）。"""
    if tool_name not in _CONVERTER_SET:
        return tool_name
    pref = str(preferred_raw_converter()["tool"])
    if tool_name == "convert_raw_to_mzml_ThermoRawFileParser":
        if resolve_thermo_rawfile_parser() is None:
            return "convert_raw_to_mzml_msconvert"
    if tool_name == "convert_raw_to_mzml_msconvert" and pref == tool_name:
        return tool_name
    return tool_name if tool_name in ALLOWED_TOOL_NAMES else pref


def raw_converter_fallback_order(initial: str) -> list[str]:
    """按平台偏好排列可尝试的转换工具（均在 Web 白名单内）。"""
    pref = str(preferred_raw_converter()["tool"])
    ordered: list[str] = []
    for name in (initial, pref, *RAW_CONVERTER_NAMES):
        if name not in ALLOWED_TOOL_NAMES or name not in _CONVERTER_SET:
            continue
        if name not in ordered:
            ordered.append(name)
    return ordered


def _converter_likely_available(tool_name: str) -> bool:
    if tool_name == "convert_raw_to_mzml_ThermoRawFileParser":
        return resolve_thermo_rawfile_parser() is not None
    if tool_name == "convert_raw_to_mzml_msconvert":
        return resolve_docker() is not None
    return True


async def call_raw_converter_with_fallback(
    session: ClientSession,
    tool_name: str,
    tool_args: dict,
    paths: dict[str, str],
) -> AsyncIterator[dict[str, Any]]:
    """
    依次尝试已注册的 raw 转换工具；仅在切换时 yield delta 事件。
    结束时 yield {"type": "done", "tool_name", "result", "result_str", "failed_tools"}。
    """
    candidates = [
        name for name in raw_converter_fallback_order(tool_name) if _converter_likely_available(name)
    ]
    if not candidates:
        candidates = raw_converter_fallback_order(tool_name)

    failed: list[str] = []
    last_result = None
    last_result_str = ""
    last_exc: Optional[BaseException] = None
    final_tool = tool_name

    for idx, candidate in enumerate(candidates):
        if idx > 0:
            prev = failed[-1]
            yield {
                "type": "delta",
                "text": f"⚠️ **{prev}** 未成功，改用 **{candidate}** 重试格式转换…\n",
            }

        final_tool = candidate
        try:
            result = None
            async for ev in call_tool_with_heartbeat(session, candidate, tool_args):
                if ev["type"] == "tick":
                    yield {"type": "tick", "tool_name": candidate, "elapsed_sec": ev.get("elapsed_sec", 0)}
                elif ev["type"] == "result":
                    result = ev["result"]
                elif ev["type"] == "error":
                    raise ev["error"]

            result_str = format_mcp_tool_result(result)
            last_result = result
            last_result_str = result_str
            if is_mcp_tool_result_error(result, result_str):
                failed.append(candidate)
                continue
            if not raw_conversion_complete(paths):
                failed.append(candidate)
                last_result_str = (
                    f"{result_str}\n转换后 converted_mzml 仍缺少与 .raw 对应的 mzML 文件。"
                ).strip()
                continue

            yield {
                "type": "done",
                "tool_name": candidate,
                "result": result,
                "result_str": result_str,
                "failed_tools": failed,
            }
            return
        except Exception as exc:
            last_exc = exc
            failed.append(candidate)
            last_result_str = str(exc)

    err_detail = last_result_str or (str(last_exc) if last_exc else "所有格式转换工具均未成功")
    yield {
        "type": "done",
        "tool_name": final_tool,
        "result": last_result,
        "result_str": err_detail,
        "failed_tools": failed,
        "all_failed": True,
    }
