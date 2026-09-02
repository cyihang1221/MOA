"""网页侧 Agent B：子进程调用 MassOmics-Agent-B 执行器（与 A/C 分离）。"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from web_frontend.backend.agent_backends import massomics_b_available, massomics_b_root
from web_frontend.backend.agent_b.plan_locate import find_massomics_plan_json
from web_frontend.backend.agent_jobs import (
    is_cancelled,
    kill_session_processes,
    register_process,
    unregister_process,
)

_EXECUTE_CLI = Path(__file__).resolve().parent / "execute_cli.py"


def _metadata_csv(upload_dir: str) -> str:
    path = Path(upload_dir) / "metadata.csv"
    return str(path.resolve()) if path.is_file() else ""


def _b_data_dir(upload: Path) -> Path:
    """转换工具只扫目录下的 *.raw，会话文件通常在 upload/raw/。"""
    raw_dir = upload / "raw"
    if raw_dir.is_dir() and (
        any(raw_dir.glob("*.raw")) or any(raw_dir.glob("*.RAW"))
    ):
        return raw_dir
    return upload


async def stream_massomics_b_execution(
    *,
    paths: dict[str, str],
    session_id: str,
    project_root: Path | None = None,
    plan_path: str | Path | None = None,
    cancel_event: Optional[asyncio.Event] = None,
    should_stop: Optional[Callable[[], Awaitable[bool]]] = None,
) -> AsyncIterator[dict[str, Any]]:
    """按已确认的 ``plan_*.json`` 启动独立 B 进程，流式转发日志。"""
    b_root = massomics_b_root(project_root)
    if not massomics_b_available(project_root):
        yield {
            "error": (
                "未找到 MassOmics Agent B 工作区（需要 src/executor.py 与 "
                "src/massomics_adapter.py）。请在 MassOmics-Agent 仓库根启动网页，"
                "或设置 WEB_MASSOMICS_B_ROOT。"
            )
        }
        return

    outputspace = Path(paths["outputspace"])
    upload = Path(paths.get("upload") or paths.get("inputspace") or "")
    resolved_plan = Path(plan_path).expanduser().resolve() if plan_path else None
    if resolved_plan is not None and not resolved_plan.is_file():
        yield {"error": f"指定的计划不存在: {resolved_plan}"}
        return
    plan_path = resolved_plan or find_massomics_plan_json(outputspace, upload)
    if plan_path is None:
        yield {
            "error": (
                "未找到 Agent A 产出的 MassOmics 计划（plan_*.json）。"
                "请先完成规划并确认计划后再执行。"
            )
        }
        return

    receipt_path = outputspace / "agent_b_receipt.json"
    adapted_path = outputspace / "agent_b_adapted_plan.json"
    metadata = _metadata_csv(str(upload))
    data_dir = _b_data_dir(upload)
    outputspace.mkdir(parents=True, exist_ok=True)

    yield {
        "delta": (
            "⚙️ **Agent B**：MassOmics 执行器（独立进程）\n"
            f"- 工作区：`{b_root}`\n"
            f"- 计划：`{plan_path.name}`\n"
            f"- 数据：`{data_dir}`\n"
            f"- 结果目录：`{outputspace}`\n\n"
        )
    }

    env = os.environ.copy()
    env["PYTHONPATH"] = str(b_root)
    env["MASSOMICS_B_ROOT"] = str(b_root)
    env["WEB_MASSOMICS_B_ROOT"] = str(b_root)
    py_bin = str(Path(sys.executable).resolve().parent)
    env["PATH"] = py_bin + os.pathsep + env.get("PATH", "")

    command = [
        sys.executable,
        str(_EXECUTE_CLI),
        "--plan",
        str(plan_path),
        "--data",
        str(data_dir.resolve()),
        "--outputspace",
        str(outputspace.resolve()),
        "--receipt",
        str(receipt_path.resolve()),
        "--adapted-plan",
        str(adapted_path.resolve()),
    ]
    if metadata:
        command.extend(["--metadata", metadata])

    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(b_root),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    register_process(session_id, proc.pid)
    cancelled = False
    try:
        assert proc.stdout is not None
        while True:
            if should_stop is not None and await should_stop():
                cancelled = True
                break
            if is_cancelled(cancel_event):
                cancelled = True
                break
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=0.4)
            except asyncio.TimeoutError:
                continue
            if not line:
                break
            text = line.decode("utf-8", errors="replace")
            if not text.endswith("\n"):
                text += "\n"
            yield {"delta": text}

        if cancelled:
            kill_session_processes(session_id)
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                proc.kill()
            yield {"delta": "\n\n⚠️ **已终止**：Agent B 子进程已停止。\n"}
            yield {"cancelled": True}
            return

        returncode = await proc.wait()
    finally:
        unregister_process(session_id, proc.pid)

    receipt: dict[str, Any] = {}
    if receipt_path.is_file():
        try:
            loaded = json.loads(receipt_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                receipt = loaded
        except json.JSONDecodeError:
            receipt = {}

    if not receipt:
        yield {"error": f"Agent B 未写入回执（退出码 {returncode}）"}
        return

    had_failure = bool(receipt.get("had_tool_failure")) or returncode != 0
    status = str(receipt.get("status") or ("failed" if had_failure else "success"))
    if had_failure:
        err = str(receipt.get("error") or "").strip()
        extra = f"：{err}" if err else f"（退出码 {returncode}）"
        yield {
            "delta": (
                f"\n\n---\n⚠️ **Agent B 未完全成功**（status={status}）{extra}\n"
                f"回执：`{receipt_path.name}`\n"
            )
        }
        if not receipt.get("stages"):
            yield {"error": err or f"Agent B 退出码 {returncode}"}
            return
        done: dict[str, Any] = {
            "delta": f"部分阶段已写入 `{outputspace}`。\n",
            "execute_done": True,
            "had_tool_failure": True,
            "agent_b_receipt": str(receipt_path),
        }
        yield done
        return

    n_stages = int(receipt.get("n_stages") or 0)
    yield {
        "delta": (
            f"\n\n---\n🎉 **Agent B 执行完毕**（{n_stages} 个阶段）。\n"
            f"结果已写入 **{outputspace}/**。\n"
        ),
        "execute_done": True,
        "had_tool_failure": False,
        "agent_b_receipt": str(receipt_path),
    }


__all__ = ["stream_massomics_b_execution"]
