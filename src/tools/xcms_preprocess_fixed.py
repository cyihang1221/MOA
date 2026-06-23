"""Windows-safe data_preprocessing_xcms（串行 MS2 + 日志）。MCP 可改调此模块。"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from src.platform_utils import is_windows

# 复用原实现中的 R 脚本模板：通过 import 原函数并替换关键步骤不可行，故内联精简调用链
from src.tools.xcms import data_preprocessing_xcms_impl as _orig_impl


def data_preprocessing_xcms_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    blank_pattern: str = "Blank",
    **kwargs,
):
    """包装原 impl：Windows 强制 n_cores=1，写日志，检查输出。"""
    if is_windows():
        kwargs["n_cores"] = 1
    log_file = Path(output_dir) / "data_preprocessing_xcms.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 临时替换 subprocess.run
    orig_run = subprocess.run

    def _logged_run(cmd, **kw):
        with open(log_file, "w", encoding="utf-8") as log_f:
            return orig_run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **{k: v for k, v in kw.items() if k not in ("stdin", "stdout", "stderr", "capture_output")},
            )

    subprocess.run = _logged_run
    try:
        _orig_impl(
            input_dir=input_dir,
            output_dir=output_dir,
            file_pattern=file_pattern,
            blank_pattern=blank_pattern,
            **kwargs,
        )
    finally:
        subprocess.run = orig_run

    out_csv = Path(output_dir) / "feature_table.csv"
    if not out_csv.is_file():
        tail = log_file.read_text(encoding="utf-8", errors="replace")[-8000:] if log_file.is_file() else ""
        raise RuntimeError(
            f"XCMS 未生成 feature_table.csv。日志: {log_file}\n{tail}"
        )
    if log_file.is_file():
        r = subprocess.run(
            ["Rscript", "-e", "0"],
            capture_output=True,
        )  # noop placeholder
        # check log for obvious stop
        log_text = log_file.read_text(encoding="utf-8", errors="replace")
        if "Error" in log_text and "CSV written" not in log_text:
            raise RuntimeError(f"XCMS R 报错，见 {log_file}\n{log_text[-4000:]}")
