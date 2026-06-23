"""MCP stdio 子进程启动时先导入本模块，将 print 重定向到 stderr。"""
import builtins
import sys

if not getattr(builtins, "_mcp_print_patched", False):
    _builtin_print = builtins.print

    def _print_to_stderr(*args, **kwargs):
        kwargs.setdefault("file", sys.stderr)
        _builtin_print(*args, **kwargs)

    builtins.print = _print_to_stderr
    builtins._mcp_print_patched = True
