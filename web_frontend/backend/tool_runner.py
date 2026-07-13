"""Web 端 MCP 工具调用：长任务心跳提示，避免页面长时间无输出。"""
from __future__ import annotations

import asyncio
import traceback
from typing import Any, AsyncIterator

from mcp.client.session import ClientSession

TOOL_RUNTIME_HINTS: dict[str, str] = {
    "convert_raw_to_mzml_msconvert": "Docker msconvert 转换每个 .raw 约 1–5 分钟。",
    "convert_raw_to_mzml_ThermoRawFileParser": "ThermoRawFileParser 转换每个 .raw 约 1–3 分钟。",
    "data_preprocessing_xcms": (
        "XCMS 全流程（centWave、Obiwarp、峰分组、Gap filling、MS2 提取）"
        "通常需 **10–40 分钟**，请耐心等待。"
    ),
    "feature_filtering_and_missing_value_imputation_knn": "特征过滤与 KNN 填补约 1–5 分钟。",
    "statistical_analysis_mixomics": "mixOmics 统计与作图约 2–10 分钟。",
    "extract_differential_features": "差异物提取约 1–3 分钟。",
    "spectral_annotation": "谱库注释耗时取决于谱库大小。",
    "kegg_compound_enrichment": "KEGG 富集约 1–5 分钟。",
    "molecular_networking_gnps": "GNPS 分子网络构建，谱图较多时可能需数分钟至数十分钟。",
    "deepmass_annotation": "DeepMASS2 深度学习注释（需 Docker 镜像 deepmass2:test 与模型目录）。",
}

HEARTBEAT_INTERVAL_SEC = 25


def format_tick_message(tool_name: str, elapsed_sec: int) -> str:
    hint = TOOL_RUNTIME_HINTS.get(tool_name, "该步骤可能耗时较长，请稍候。")
    minutes = max(0, elapsed_sec // 60)
    if minutes > 0:
        return f"⏳ **{tool_name}** 仍在运行（已约 {minutes} 分钟）。{hint}\n"
    return f"⏳ **{tool_name}** 正在运行… {hint}\n"


async def call_tool_with_heartbeat(
    session: ClientSession,
    tool_name: str,
    tool_args: dict,
    *,
    heartbeat_interval: float = HEARTBEAT_INTERVAL_SEC,
) -> AsyncIterator[dict[str, Any]]:
    """执行 MCP 工具；期间 yield tick 事件，结束时 yield result 或 error。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def _worker() -> None:
        try:
            result = await session.call_tool(tool_name, tool_args)
            await queue.put({"type": "result", "result": result})
        except Exception as exc:
            await queue.put(
                {
                    "type": "error",
                    "error": exc,
                    "traceback": traceback.format_exc(),
                }
            )

    async def _ticker() -> None:
        elapsed = 0
        await queue.put({"type": "tick", "elapsed_sec": elapsed})
        while True:
            await asyncio.sleep(heartbeat_interval)
            elapsed += int(heartbeat_interval)
            await queue.put({"type": "tick", "elapsed_sec": elapsed})

    worker_task = asyncio.create_task(_worker())
    ticker_task = asyncio.create_task(_ticker())

    try:
        while True:
            event = await queue.get()
            if event["type"] == "tick":
                yield event
                continue
            yield event
            break
    finally:
        ticker_task.cancel()
        try:
            await ticker_task
        except asyncio.CancelledError:
            pass
        if not worker_task.done():
            await worker_task
