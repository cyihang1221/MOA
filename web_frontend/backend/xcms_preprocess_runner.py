"""
Web 端 XCMS 预处理：修复 Windows 并行卡死、写入日志、失败时抛出明确错误。
供 agent_runner 在 MCP data_preprocessing_xcms 超时/无输出时改道调用，或命令行手动重跑。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from src.platform_utils import is_windows

# 从 xcms 模块复用 R 脚本生成逻辑（仅 data_preprocessing 段）
from src.tools import xcms as xcms_module


def run_data_preprocessing_xcms(
    input_dir: str,
    output_dir: str,
    *,
    blank_pattern: str = "QC",
    file_pattern: str = "*.mzML",
    timeout_sec: int | None = None,
) -> str:
    """
    执行 XCMS 预处理，返回日志路径；失败抛 RuntimeError。
    timeout_sec: None 表示不限制（6 个 ~60MB mzML 建议预留 60–90 分钟）
    """
    input_dir = str(Path(input_dir).resolve())
    output_dir = str(Path(output_dir).resolve())
    os.makedirs(output_dir, exist_ok=True)

    log_path = Path(output_dir) / "data_preprocessing_xcms.log"
    output_csv = Path(output_dir) / "feature_table.csv"

    # 调用原 impl 的 R 脚本构建：通过读取源码不现实，内联调用原函数并 monkeypatch subprocess
    impl = xcms_module.data_preprocessing_xcms_impl
    original_run = subprocess.run

    def _patched_run(cmd, **kwargs):
        kwargs.pop("capture_output", None)
        with open(log_path, "w", encoding="utf-8") as log_f:
            return original_run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                **{k: v for k, v in kwargs.items() if k not in ("stdin", "stdout", "stderr", "check", "text", "encoding", "errors")},
            )

    subprocess.run = _patched_run
    try:
        impl(
            input_dir=input_dir,
            output_dir=output_dir,
            file_pattern=file_pattern,
            blank_pattern=blank_pattern,
            n_cores=1 if is_windows() else None,
        )
    finally:
        subprocess.run = original_run

    if not output_csv.is_file():
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:] if log_path.is_file() else ""
        raise RuntimeError(
            f"未生成 {output_csv}。请查看日志: {log_path}\n{tail}"
        )
    return str(log_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="重跑 XCMS data_preprocessing")
    parser.add_argument("--session-slug", required=True, help="如 DY-1-1-质谱分析_a817b90a")
    parser.add_argument("--blank-pattern", default="QC")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    slug = args.session_slug
    inp = root / "outputspace" / slug / "converted_mzml"
    out = root / "outputspace" / slug / "peak_detection_results"
    print(f"input: {inp}", file=sys.stderr)
    print(f"output: {out}", file=sys.stderr)
    log = run_data_preprocessing_xcms(str(inp), str(out), blank_pattern=args.blank_pattern)
    print(f"OK, log={log}")
