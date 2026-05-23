"""MCP 工具进程的 I/O 辅助：stdout 留给 JSON-RPC，日志只写 stderr 或文件。"""
import sys


def tool_log(message: str, log_path: str | None = None) -> None:
    line = message if message.endswith("\n") else message + "\n"
    sys.stderr.write(line)
    sys.stderr.flush()
    if log_path:
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(line)
