"""跨平台辅助：MCP 子进程、路径规范化、Agent 运行时检测。"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_windows() -> bool:
    return sys.platform == "win32"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def platform_label() -> str:
    if is_windows():
        return "Windows"
    if is_linux():
        return "Linux"
    return sys.platform


def normalize_display_path(path: str | Path) -> str:
    """统一为正斜杠绝对路径，便于 LLM / 前端展示。"""
    return str(Path(path).resolve()).replace("\\", "/")


def mcp_server_env() -> dict[str, str]:
    """MCP stdio 子进程环境：UTF-8 + 项目根加入 PYTHONPATH。"""
    env = {
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    root = str(PROJECT_ROOT)
    sep = os.pathsep
    existing = env.get("PYTHONPATH", "")
    parts = [p for p in existing.split(sep) if p]
    if root not in parts:
        parts.insert(0, root)
    env["PYTHONPATH"] = sep.join(parts)
    return env


def mcp_stdio_parameters():
    """创建可在 Windows / Linux 下稳定启动 MCP server 的 StdioServerParameters。"""
    from mcp.client.stdio import StdioServerParameters

    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-c",
            "import src.mcp_stdio_bootstrap; import runpy; "
            "runpy.run_module('src.mcp_server.server', run_name='__main__')",
        ],
        env=mcp_server_env(),
        cwd=str(PROJECT_ROOT),
    )


def resolve_thermo_rawfile_parser() -> str | None:
    for name in ("ThermoRawFileParser", "ThermoRawFileParser.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def resolve_rscript() -> str:
    for name in ("Rscript", "Rscript.exe"):
        path = shutil.which(name)
        if path:
            return path
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        for rel in ("Scripts/Rscript.exe", "bin/Rscript"):
            candidate = os.path.join(conda_prefix, rel.replace("/", os.sep))
            if os.path.isfile(candidate):
                return candidate
    raise FileNotFoundError(
        "未找到 Rscript。请确认已安装 R（Windows: conda install r-base；Linux: conda 或 apt）"
    )


def resolve_docker() -> str | None:
    return shutil.which("docker")


def preferred_raw_converter() -> dict[str, str | None]:
    """
    按平台选择 .raw → mzML 的推荐工具。
    Windows 默认 msconvert（Docker）；Linux 优先 ThermoRawFileParser。
    """
    if is_windows():
        return {
            "tool": "convert_raw_to_mzml_msconvert",
            "reason": "Windows 推荐使用 Docker msconvert（需 Docker Desktop 运行中）",
            "fallback": None,
        }
    if resolve_thermo_rawfile_parser():
        return {
            "tool": "convert_raw_to_mzml_ThermoRawFileParser",
            "reason": "Linux 已检测到 ThermoRawFileParser",
            "fallback": "convert_raw_to_mzml_msconvert",
        }
    return {
        "tool": "convert_raw_to_mzml_msconvert",
        "reason": "未检测到 ThermoRawFileParser，改用 Docker msconvert",
        "fallback": None,
    }


def should_fallback_to_msconvert(tool_name: str) -> bool:
    """ThermoRawFileParser 不可用时是否应自动改用 msconvert。"""
    if tool_name != "convert_raw_to_mzml_ThermoRawFileParser":
        return False
    return resolve_thermo_rawfile_parser() is None


def filter_plan_tasks_to_registered_tools(
    tasks: list,
    tool_names: list[str],
) -> list[str]:
    """只保留计划中引用了当前 MCP 已注册工具名称的步骤。"""
    names = [str(n).strip() for n in tool_names if n]
    if not names:
        return [str(t) for t in tasks]

    kept: list[str] = []
    for task in tasks:
        text = str(task)
        lower = text.lower()
        if any(name.lower() in lower for name in names):
            kept.append(text)
    return kept if kept else [str(t) for t in tasks]


def normalize_plan_tasks_for_platform(tasks: list) -> list[str]:
    """按平台修正计划文本中的转换工具描述。"""
    pref = preferred_raw_converter()
    preferred = str(pref["tool"])
    normalized: list[str] = []
    for task in tasks:
        text = str(task)
        if should_fallback_to_msconvert("convert_raw_to_mzml_ThermoRawFileParser"):
            text = text.replace(
                "convert_raw_to_mzml_ThermoRawFileParser",
                "convert_raw_to_mzml_msconvert",
            )
            text = text.replace("ThermoRawFileParser", "msconvert (Docker)")
        elif preferred == "convert_raw_to_mzml_ThermoRawFileParser":
            text = text.replace(
                "convert_raw_to_mzml_msconvert",
                "convert_raw_to_mzml_ThermoRawFileParser",
            )
        normalized.append(text)
    return normalized


def docker_bind_mount(local_path: str | Path) -> str:
    """
    将主机目录格式化为 Docker -v 可用的路径。
    Windows Docker Desktop 使用 /e/path 形式；Linux 使用绝对 POSIX 路径。
    """
    resolved = Path(local_path).resolve()
    if is_windows():
        drive = resolved.drive.rstrip(":").lower()
        if drive:
            rest = resolved.as_posix().split(":", 1)[-1].lstrip("/")
            return f"/{drive}/{rest}"
    return resolved.as_posix()


def build_goal_description(user_message: str, paths: dict[str, str]) -> str:
    """按当前平台生成 Agent 目标描述（路径约定 + 推荐流程）。"""
    pref = preferred_raw_converter()
    convert_tool = str(pref["tool"])
    platform_note = ""
    if is_windows():
        platform_note = """
平台说明（Windows）：
- .raw 转换必须使用 convert_raw_to_mzml_msconvert（Docker msconvert），禁止使用 ThermoRawFileParser。
- 请确保 Docker Desktop 已启动；R 工具依赖 conda 环境中的 Rscript。
"""
    else:
        platform_note = f"""
平台说明（Linux）：
- .raw 转换优先使用 {convert_tool}（{pref["reason"]}）。
- 若 ThermoRawFileParser 不可用，自动改用 convert_raw_to_mzml_msconvert。
"""

    upload = normalize_display_path(paths["upload"])
    converted = normalize_display_path(paths["converted_mzml"])
    peaks = normalize_display_path(paths["peaks"])
    annotated = normalize_display_path(paths["annotated"])

    return f"""
用户任务描述：
{user_message.strip()}

你必须通过调用 MCP 工具实际执行，不要只给出文字建议。
{platform_note}
路径约定（参数必须使用以下绝对路径，正斜杠格式）：
- 若需处理 .raw：input_dir 优先使用上传目录 {upload}
- mzML 输出目录：{converted}
- 峰检测结果目录：{peaks}
- 注释/过滤结果目录：{annotated}

推荐流程（每一步都必须 call 工具）：
1. {convert_tool}
   - input_dir = {upload}
   - output_dir = {converted}
2. peak_detection_xcms_centwave
   - input_dir = {converted}
   - output_dir = {peaks}
   - 输出 RDS 固定为：{peaks}/XCMS-centwave_peak_detection_result.rds
3. 若需注释/去冗余：filter_redundant_features_camera
   - input_rds = {peaks}/XCMS-centwave_peak_detection_result.rds
   - output_rds = {annotated}/filtered_features.rds

工具匹配时 JSON 必须严格为：
{{"tool_call": {{"name": "工具名", "arguments": {{...}}}}}}
不要加 markdown 代码块，不要多余括号。
"""


def check_agent_runtime() -> dict[str, Any]:
    """检测 Agent 运行依赖，results 供 /api/info 与前端展示）。"""
    issues: list[str] = []
    hints: list[str] = []

    try:
        resolve_rscript()
        r_ok = True
    except FileNotFoundError as exc:
        r_ok = False
        issues.append(str(exc))

    docker_path = resolve_docker()
    docker_ok = docker_path is not None
    if not docker_ok:
        hints.append("未检测到 docker 命令；Windows 下 .raw 转换需 Docker Desktop")

    parser = resolve_thermo_rawfile_parser()
    converter = preferred_raw_converter()

    if is_windows() and not docker_ok:
        issues.append("Windows 下 convert_raw_to_mzml_msconvert 需要 Docker Desktop")

    agent_ready = r_ok and (docker_ok or is_linux() or parser is not None)

    return {
        "platform": platform_label(),
        "sys_platform": sys.platform,
        "python": normalize_display_path(sys.executable),
        "project_root": normalize_display_path(PROJECT_ROOT),
        "r_available": r_ok,
        "docker_available": docker_ok,
        "thermo_rawfile_parser": parser,
        "preferred_raw_converter": converter,
        "agent_ready": agent_ready,
        "issues": issues,
        "hints": hints,
    }
