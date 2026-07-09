"""统一 Agent 工具注册表：MCP 分析工具 + 本地 visual 工具（改图/拼图）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from web_frontend.backend.constants import ALLOWED_TOOL_NAMES

LOCAL_TOOL_NAMES = frozenset({"plot_edit", "image_merge", "merge_edit"})
ALL_AGENT_TOOL_NAMES = frozenset(ALLOWED_TOOL_NAMES | LOCAL_TOOL_NAMES)


@dataclass
class AgentContext:
    project_root: Path
    session_id: str
    storage_slug: str
    paths: dict[str, str]
    model: str | None = None
    user_message: str = ""


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    runtime: Literal["mcp", "local"]
    category: str = "other"
    # MCP 原始对象（list_tools 返回）；local 工具为 None
    mcp_tool: Any = None


def _schema(
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


LOCAL_TOOL_SPECS: dict[str, ToolSpec] = {
    "plot_edit": ToolSpec(
        name="plot_edit",
        description=(
            "Agent 改图：按自然语言修改 PCA/PLS-DA/火山图/网络分布图等的标题、颜色、字号，"
            "用 matplotlib 重绘并写入 edited_plots/。需会话中已有对应 PNG 与数据 CSV。"
        ),
        input_schema=_schema(
            {
                "instruction": {
                    "type": "string",
                    "description": "改图要求，如：把 PCA 标题改成「分组比较」，Control 用 #4DBBD5",
                },
                "source_rel": {
                    "type": "string",
                    "description": "可选，outputspace 内 PNG 相对路径；省略则从 instruction 自动解析",
                },
            },
            ["instruction"],
        ),
        runtime="local",
        category="visual",
    ),
    "image_merge": ToolSpec(
        name="image_merge",
        description=(
            "合并多张结果图为论文拼图，保存到 merged_figures/。"
            "可指定文件名、列数、标签样式。至少需要 2 张 PNG。"
        ),
        input_schema=_schema(
            {
                "instruction": {
                    "type": "string",
                    "description": "合并要求，如：合并 cosine_distribution.png 和 degree_distribution.png，两列",
                },
            },
            ["instruction"],
        ),
        runtime="local",
        category="visual",
    ),
    "merge_edit": ToolSpec(
        name="merge_edit",
        description=(
            "编辑已有拼图：调整标签模式/字号/列数/间距，从 .merge.json 记录的原图重排，"
            "覆盖 merged_figures/ 中的 PNG。需已有带 sidecar 的拼图。"
        ),
        input_schema=_schema(
            {
                "instruction": {
                    "type": "string",
                    "description": "改拼图要求，如：标签改成小写，标签字号 36",
                },
                "target_rel": {
                    "type": "string",
                    "description": "可选，merged_figures/ 下 PNG 相对路径；省略则选最新拼图",
                },
            },
            ["instruction"],
        ),
        runtime="local",
        category="visual",
    ),
}


def tool_spec_as_mcp_like(spec: ToolSpec) -> Any:
    """包装成与 MCP Tool 类似的对象，供 web_prompts._compact_tools 使用。"""

    class _T:
        pass

    t = _T()
    t.name = spec.name
    t.description = spec.description
    t.inputSchema = spec.input_schema
    return t


async def load_all_tools() -> list[Any]:
    """返回 MCP 白名单工具 + 本地 visual 工具（MCP-like 对象列表）。"""
    from src.mcp_server.server import mcp

    mcp_tools = await mcp.list_tools()
    tools = [t for t in mcp_tools if t.name in ALLOWED_TOOL_NAMES]
    for spec in LOCAL_TOOL_SPECS.values():
        tools.append(tool_spec_as_mcp_like(spec))
    return tools


def is_local_tool(name: str) -> bool:
    return name in LOCAL_TOOL_NAMES


def get_local_spec(name: str) -> ToolSpec | None:
    return LOCAL_TOOL_SPECS.get(name)


def normalize_local_tool_args(tool_name: str, tool_args: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
    args = dict(tool_args or {})
    instruction = str(args.get("instruction") or "").strip()
    if not instruction:
        # 兜底：用当前用户消息或计划任务上下文
        instruction = (ctx.user_message or "").strip()
    if not instruction:
        raise ValueError(f"{tool_name} 需要 instruction 参数")
    args["instruction"] = instruction

    if tool_name == "plot_edit":
        source = str(args.get("source_rel") or "").strip()
        if source:
            args["source_rel"] = source.lstrip("/")
        else:
            args.pop("source_rel", None)
    elif tool_name == "merge_edit":
        target = str(args.get("target_rel") or "").strip()
        if target:
            args["target_rel"] = target.lstrip("/")
        else:
            args.pop("target_rel", None)
    return args


def run_local_tool(tool_name: str, tool_args: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
    """同步执行本地 visual 工具，返回结构化结果。"""
    args = normalize_local_tool_args(tool_name, tool_args, ctx)

    if tool_name == "plot_edit":
        return _run_plot_edit(args, ctx)
    if tool_name == "image_merge":
        return _run_image_merge(args, ctx)
    if tool_name == "merge_edit":
        return _run_merge_edit(args, ctx)
    raise ValueError(f"未知本地工具: {tool_name}")


def _run_plot_edit(args: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
    from web_frontend.backend.plot_edit_service import (
        PlotEditError,
        agent_apply_plot_edit,
        resolve_chat_plot_edit_tasks,
    )

    instruction = args["instruction"]
    source_rel = args.get("source_rel")
    results = []
    try:
        if source_rel:
            results.append(
                agent_apply_plot_edit(
                    project_root=ctx.project_root,
                    session_id=ctx.session_id,
                    storage_slug=ctx.storage_slug,
                    source_rel=source_rel,
                    instruction=instruction,
                    model=ctx.model,
                )
            )
        else:
            tasks, _plots = resolve_chat_plot_edit_tasks(
                project_root=ctx.project_root,
                storage_slug=ctx.storage_slug,
                message=instruction,
            )
            for rel, line_instruction in tasks:
                results.append(
                    agent_apply_plot_edit(
                        project_root=ctx.project_root,
                        session_id=ctx.session_id,
                        storage_slug=ctx.storage_slug,
                        source_rel=rel,
                        instruction=line_instruction or instruction,
                        model=ctx.model,
                    )
                )
    except PlotEditError as exc:
        raise RuntimeError(str(exc)) from exc

    files = [r["file"]["name"] for r in results if r.get("file")]
    return {
        "kind": "plot_edit",
        "ok": True,
        "files": files,
        "message": f"改图完成，共 {len(files)} 张：{', '.join(files)}",
        "results": results,
    }


def _run_image_merge(args: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
    from web_frontend.backend.image_merge_service import ImageMergeError, agent_merge_images

    try:
        result = agent_merge_images(
            project_root=ctx.project_root,
            session_id=ctx.session_id,
            storage_slug=ctx.storage_slug,
            message=args["instruction"],
        )
    except ImageMergeError as exc:
        raise RuntimeError(str(exc)) from exc

    name = result["file"]["name"]
    return {
        "kind": "image_merge",
        "ok": True,
        "files": [name],
        "message": f"拼图完成：{name}",
        "result": result,
    }


def _run_merge_edit(args: dict[str, Any], ctx: AgentContext) -> dict[str, Any]:
    from web_frontend.backend.image_merge_service import ImageMergeError, agent_edit_merged_figure

    try:
        result = agent_edit_merged_figure(
            project_root=ctx.project_root,
            session_id=ctx.session_id,
            storage_slug=ctx.storage_slug,
            message=args["instruction"],
            target_rel=args.get("target_rel"),
            model=ctx.model,
        )
    except ImageMergeError as exc:
        raise RuntimeError(str(exc)) from exc

    name = result["file"]["name"]
    return {
        "kind": "merge_edit",
        "ok": True,
        "files": [name],
        "message": f"拼图已更新：{name}",
        "result": result,
    }


def format_local_tool_result(payload: dict[str, Any]) -> str:
    msg = payload.get("message") or ""
    files = payload.get("files") or []
    if files and msg:
        return msg
    if files:
        return "输出文件：\n" + "\n".join(f"- {f}" for f in files)
    return msg or str(payload)


__all__ = [
    "LOCAL_TOOL_NAMES",
    "ALL_AGENT_TOOL_NAMES",
    "AgentContext",
    "ToolSpec",
    "LOCAL_TOOL_SPECS",
    "load_all_tools",
    "is_local_tool",
    "get_local_spec",
    "normalize_local_tool_args",
    "run_local_tool",
    "format_local_tool_result",
    "tool_spec_as_mcp_like",
]
