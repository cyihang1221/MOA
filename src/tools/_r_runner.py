"""Rscript 子进程统一封装（日志写文件，避免 MCP stdout 阻塞）。"""
from __future__ import annotations

import os
import subprocess
import tempfile

from src.platform_utils import normalize_display_path, resolve_rscript
from src.tools._mcp_io import tool_log


def r_path(path: str) -> str:
    return normalize_display_path(path)


def run_rscript(r_file: str, label: str = "r_tool", log_dir: str | None = None) -> str:
    log_dir = log_dir or tempfile.gettempdir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{label}.log")

    tool_log(f"[{label}] start Rscript: {r_file}", log_path)
    tool_log(f"[{label}] log: {log_path}", log_path)

    with open(log_path, "w", encoding="utf-8") as log:
        result = subprocess.run(
            [resolve_rscript(), r_file],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    if result.returncode != 0:
        with open(log_path, encoding="utf-8") as f:
            tail = f.read()[-6000:]
        raise RuntimeError(
            f"Rscript 失败，退出码 {result.returncode}\n日志: {log_path}\n{tail}"
        )
    tool_log(f"[{label}] finished: {log_path}", log_path)
    return log_path
