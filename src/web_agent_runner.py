"""
Web 端 Agent 执行：与 run_agent.py 相同流程（计划 → 选工具 → MCP call_tool），
通过 SSE 推送进度，而非仅 LLM 文字建议。
"""
from __future__ import annotations

import asyncio
import json
import traceback
from pathlib import Path
from typing import AsyncIterator, Awaitable, Callable, Optional

from src.agent_jobs import is_cancelled

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

from src.agent import Agent
from src.platform_utils import (
    build_goal_description,
    mcp_stdio_parameters,
    normalize_display_path,
    normalize_plan_tasks_for_platform,
    should_fallback_to_msconvert,
)
from src.json_parse import extract_first_json_object, parse_tool_call
from src.llm_client import LLM_Client


def build_session_paths(
    session_id: str,
    workspace_root: Path,
    storage_slug: Optional[str] = None,
) -> dict[str, str]:
    """为每个会话准备输入/输出目录（目录名使用可读 storage_slug）。"""
    slug = storage_slug or session_id
    base = workspace_root / "sessions" / slug
    upload_dir = workspace_root / "uploads" / slug
    paths = {
        "upload": normalize_display_path(upload_dir),
        "raw": normalize_display_path(base / "raw"),
        "converted_mzml": normalize_display_path(base / "converted_mzml"),
        "peaks": normalize_display_path(base / "peak_detection_results"),
        "annotated": normalize_display_path(base / "annotation_results"),
    }
    for key in ("raw", "converted_mzml", "peaks", "annotated"):
        Path(paths[key]).mkdir(parents=True, exist_ok=True)
    return paths


def build_data_list(upload_dir: str, paths: dict[str, str]) -> str:
    lines = []
    upload = Path(upload_dir)
    if upload.is_dir():
        for item in sorted(upload.iterdir()):
            if item.is_file():
                lines.append(
                    f"{normalize_display_path(item)}: 用户上传的质谱原始/数据文件 ({item.name})"
                )
    lines.append(f"{paths['upload']}: 本会话上传文件目录")
    lines.append(f"{paths['converted_mzml']}: mzML 转换输出目录")
    lines.append(f"{paths['peaks']}: 峰检测与峰处理结果目录")
    lines.append(f"{paths['annotated']}: 注释/冗余特征过滤等结果目录")
    return "\n".join(lines)


async def stream_agent_pipeline(
    *,
    user_message: str,
    session_id: str,
    storage_slug: Optional[str] = None,
    workspace_root: Path,
    database_file_dir: str,
    persist_dir: str,
    source_dir: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    cancel_event: Optional[asyncio.Event] = None,
    is_disconnected: Optional[Callable[[], Awaitable[bool]]] = None,
) -> AsyncIterator[dict]:
    """
    异步生成 SSE 事件 dict：{"delta": "..."} | {"done": True, "time": ...} | {"error": "..."}
    """
    paths = build_session_paths(session_id, workspace_root, storage_slug=storage_slug)
    data_list = build_data_list(paths["upload"], paths)
    goal = build_goal_description(user_message, paths)

    async def _should_stop() -> bool:
        if is_cancelled(cancel_event):
            return True
        if is_disconnected is not None and await is_disconnected():
            return True
        return False

    yield {"delta": "🔧 **Agent 模式**：正在加载工具列表并生成执行计划…\n\n"}

    loop = asyncio.get_event_loop()

    def _make_agent() -> Agent:
        return Agent(
            data_list=data_list,
            database_file_dir=database_file_dir,
            goal_description=goal,
            workspace=str(workspace_root.resolve()),
            PERSIST_DIR=persist_dir,
            SOURCE_DIR=source_dir,
        )

    agent = await loop.run_in_executor(None, _make_agent)

    yield {"delta": f"已注册 **{len(agent.tools_info)}** 个 MCP 工具。\n\n"}

    def _plan():
        prompt = agent.prompt_generator.plan_prompt(
            data_list=agent.data_list, tools_info=agent.tools_info
        )
        client = LLM_Client(model=model)
        return client.think([{"role": "user", "content": str(prompt)}], temperature=temperature)

    yield {"delta": "📋 正在调用 LLM 生成计划…\n"}
    try:
        plan_resp = await loop.run_in_executor(None, _plan)
    except Exception as exc:
        yield {"error": f"计划生成失败: {exc}"}
        return

    if await _should_stop():
        yield {"delta": "\n\n⚠️ **已终止**（计划阶段）\n"}
        yield {"cancelled": True}
        return

    plan_data = extract_first_json_object(plan_resp or "")
    agent.tasks = plan_data.get("plan", [])
    agent.tasks = normalize_plan_tasks_for_platform(agent.tasks)
    if not agent.tasks:
        yield {
            "delta": "⚠️ 未能解析出可执行计划，原始响应：\n"
            + (plan_resp or "")[:2000]
            + "\n\n"
        }
        yield {"error": "计划为空，未执行工具"}
        return

    agent.history_summary.append(
        {"role": "user", "content": f"Plan for goal: {agent.tasks}"}
    )
    yield {"delta": f"✅ 计划共 **{len(agent.tasks)}** 步：\n"}
    for i, t in enumerate(agent.tasks, 1):
        yield {"delta": f"  {i}. {t}\n"}
    yield {"delta": "\n---\n\n"}

    params = mcp_stdio_parameters()

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                while agent.tasks:
                    if await _should_stop():
                        yield {
                            "delta": "\n\n⚠️ **已终止**：后续步骤已跳过（当前工具若已在运行，终端可能仍会输出片刻）\n"
                        }
                        yield {"cancelled": True}
                        return

                    task = agent.tasks.pop(0)
                    yield {"delta": f"\n### 执行任务\n{task}\n\n"}
                    yield {"delta": "🔍 正在匹配工具…\n"}

                    def _match_tool():
                        prompt = agent.prompt_generator.tool_match_prompt(
                            task=task,
                            tools_info=agent.tools_info,
                            workspace=agent.workspace,
                            history_summary=agent.history_summary,
                        )
                        client = LLM_Client(model=model)
                        return client.think(
                            [{"role": "user", "content": str(prompt)}],
                            temperature=temperature,
                            stream_to_stdout=False,
                        )

                    raw_match = await loop.run_in_executor(None, _match_tool)
                    tool_name, tool_args = parse_tool_call(raw_match or "")

                    if not tool_name or not tool_args:
                        err = f"工具匹配失败（无法解析 JSON），LLM 返回：\n{raw_match or ''}\n"
                        agent.history_summary.append({"role": "assistant", "content": err})
                        yield {"delta": f"❌ {err}\n"}
                        continue

                    if should_fallback_to_msconvert(tool_name):
                        tool_name = "convert_raw_to_mzml_msconvert"
                        yield {
                            "delta": "ℹ️ 未检测到 ThermoRawFileParser，已自动改用 **convert_raw_to_mzml_msconvert**（Docker）。\n"
                        }

                    # 峰检测产物路径纠正（LLM 常误写 xcms_result.rds）
                    if tool_name == "filter_redundant_features_camera":
                        peak_rds = str(
                            Path(paths["peaks"]) / "XCMS-centwave_peak_detection_result.rds"
                        )
                        out_dir = Path(paths["annotated"])
                        out_dir.mkdir(parents=True, exist_ok=True)
                        default_out = str(out_dir / "filtered_features.rds")
                        inp = tool_args.get("input_rds")
                        if not inp or not Path(str(inp)).is_file():
                            tool_args["input_rds"] = peak_rds
                        if not tool_args.get("output_rds"):
                            tool_args["output_rds"] = default_out
                        yield {
                            "delta": (
                                f"ℹ️ 冗余过滤：输入 `{tool_args['input_rds']}`\n"
                                f"   输出 `{tool_args['output_rds']}`（XCMSnExp 用 xcms 同位素注释，非旧版 CAMERA）\n"
                            )
                        }
                    yield {
                        "delta": f"⚙️ 调用工具 **`{tool_name}`**（可能需数分钟，请耐心等待）…\n"
                    }
                    yield {"delta": f"```json\n{json.dumps(tool_args, ensure_ascii=False, indent=2)}\n```\n\n"}

                    if await _should_stop():
                        yield {"delta": "\n\n⚠️ **已终止**（工具调用前）\n"}
                        yield {"cancelled": True}
                        return

                    try:
                        result = await session.call_tool(tool_name, tool_args)
                        result_str = str(result)
                        agent.history_summary.append({"role": "tool", "content": result_str})
                        yield {"delta": f"✅ **{tool_name}** 完成：\n{result_str}\n\n"}
                    except Exception as exc:
                        err_msg = f"工具 {tool_name} 失败: {exc}\n{traceback.format_exc()}"
                        agent.history_summary.append({"role": "tool", "content": err_msg})
                        yield {"delta": f"❌ {err_msg}\n\n"}

        yield {"delta": "\n\n---\n🎉 **所有计划任务已执行完毕。**\n✅ 结果已写入会话目录，可在 workspace/sessions 下查看。\n"}

    except Exception as exc:
        yield {"delta": f"\n❌ Agent 执行中断: {exc}\n{traceback.format_exc()}\n"}
        yield {"error": str(exc)}
