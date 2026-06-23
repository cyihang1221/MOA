"""
在内存中 patch xcms.py 后执行 data_preprocessing，无需改写只读的 xcms.py。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ProteoWizard 新 OBO 项在旧版 MSnbase/psidev-ms 中无法解析
_MZML_CVPARAM_FIXES: tuple[tuple[str, str], ...] = (
    (
        'accession="MS:1002993" name="Q Exactive Focus"',
        'accession="MS:1001911" name="Q Exactive"',
    ),
)


def sanitize_mzml_for_msnbase(mzml_dir: str | Path) -> int:
    """将 msconvert 写入的新 cvParam 替换为 MSnbase 可识别的同义词。"""
    root = Path(mzml_dir)
    if not root.is_dir():
        return 0
    changed = 0
    for path in sorted(root.glob("*.mzML")):
        text = path.read_text(encoding="utf-8", errors="replace")
        new_text = text
        for old, new in _MZML_CVPARAM_FIXES:
            new_text = new_text.replace(old, new)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed += 1
    return changed


OLD_PARALLEL = """# ============================= Parallel MS2 matching =============================
cl <- makeCluster(n_cores)
registerDoParallel(cl)

results <- foreach(
    feat = feat_list,
    .packages = "MSnbase"
) %dopar% {{
    feat_id <- rownames(feat)

    match <- match_ms2(
        feat$mzmed,
        feat$rtmed,
        ms2_rt,
        ms2_premz,
        ms2_spectra,
        ppm = ms2_ppm,
        rt_win = ms2_rt_window
    )

    if (is.null(match)) {{
        return(NULL)
    }}

    peak_str <- paste(
        paste(match$mz, match$int, sep = " "),
        collapse = "\\n"
    )

    block <- c(
        "BEGIN IONS",
        paste0("TITLE=", feat_id),
        sprintf("PEPMASS=%f", feat$mzmed),
        sprintf("RTINSECONDS=%f", feat$rtmed),
        "CHARGE=1+",
        peak_str,
        "END IONS"
    )

    list(
        feature_id = feat_id,
        mgf = block
    )
}}

stopCluster(cl)"""

# Windows 上 foreach/%dopar% 易触发 unserialize 错误，统一改为 lapply
NEW_SERIAL_MS2 = """# ============================= MS2 matching (serial) =============================
match_one_feat <- function(feat) {{
    feat_id <- rownames(feat)
    match <- match_ms2(
        feat$mzmed, feat$rtmed, ms2_rt, ms2_premz, ms2_spectra,
        ppm = ms2_ppm, rt_win = ms2_rt_window
    )
    if (is.null(match)) return(NULL)
    peak_str <- paste(paste(match$mz, match$int, sep = " "), collapse = "\\n")
    block <- c("BEGIN IONS", paste0("TITLE=", feat_id),
        sprintf("PEPMASS=%f", feat$mzmed), sprintf("RTINSECONDS=%f", feat$rtmed),
        "CHARGE=1+", peak_str, "END IONS")
    list(feature_id = feat_id, mgf = block)
}}
cat("MS2 matching: serial mode\\n")
results <- lapply(feat_list, match_one_feat)"""

_PARALLEL_BLOCK_RE = re.compile(
    r"# =+ Parallel MS2 matching =+[\s\S]*?stopCluster\(cl\)",
    re.MULTILINE,
)

# 写入磁盘的 R 脚本（单花括号），与 Python f-string 源码中的 {{ 不同
NEW_SERIAL_MS2_R = """# ============================= MS2 matching (serial) =============================
match_one_feat <- function(feat) {
    feat_id <- rownames(feat)
    match <- match_ms2(
        feat$mzmed, feat$rtmed, ms2_rt, ms2_premz, ms2_spectra,
        ppm = ms2_ppm, rt_win = ms2_rt_window
    )
    if (is.null(match)) return(NULL)
    peak_str <- paste(paste(match$mz, match$int, sep = " "), collapse = "\\n")
    block <- c("BEGIN IONS", paste0("TITLE=", feat_id),
        sprintf("PEPMASS=%f", feat$mzmed), sprintf("RTINSECONDS=%f", feat$rtmed),
        "CHARGE=1+", peak_str, "END IONS")
    list(feature_id = feat_id, mgf = block)
}
cat("MS2 matching: serial mode\\n")
results <- lapply(feat_list, match_one_feat)"""


def _patch_r_script_runtime(r_script: str) -> str:
    """在 Rscript 执行前修补临时 .R 文件内容。"""
    r_script = r_script.replace("\r\n", "\n")
    if "%dopar%" not in r_script:
        return r_script
    m = _PARALLEL_BLOCK_RE.search(r_script)
    if m:
        return r_script[: m.start()] + NEW_SERIAL_MS2_R + r_script[m.end() :]
    return r_script

OLD_MS2_LOOP = """cat("Extracting MS2 spectra...\\n")

# Robust extraction: avoid spectra(ms2_data), which may fail if featureData
# lacks required columns such as fileIdx, spIdx, acquisitionNum, etc.
ms2_spectra <- vector("list", length(ms2_data))

for (i in seq_len(length(ms2_data))) {{
    sp <- tryCatch(
        ms2_data[[i]],
        error = function(e) NULL
    )
    ms2_spectra[[i]] <- sp
}}"""

NEW_MS2_LOOP = """cat("Extracting MS2 spectra:", length(ms2_data), "total...\\n")
ms2_spectra <- tryCatch(
    as.list(spectra(ms2_data)),
    error = function(e) {{
        cat("spectra(ms2_data) failed:", conditionMessage(e), "; using slow loop\\n")
        out <- vector("list", length(ms2_data))
        for (i in seq_len(length(ms2_data))) {{
            if (i %% 5000 == 0) cat("  MS2 extract", i, "/", length(ms2_data), "\\n")
            out[[i]] <- tryCatch(ms2_data[[i]], error = function(e) NULL)
        }}
        out
    }}
)"""


def _patch_source(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("✓", "OK")
    if OLD_MS2_LOOP in text:
        text = text.replace(OLD_MS2_LOOP, NEW_MS2_LOOP)

    if OLD_PARALLEL in text:
        text = text.replace(OLD_PARALLEL, NEW_SERIAL_MS2)
    else:
        m = _PARALLEL_BLOCK_RE.search(text)
        if m:
            text = text[: m.start()] + NEW_SERIAL_MS2 + text[m.end() :]

    if sys.platform == "win32":
        text = text.replace(
            "    if n_cores is None:\n        n_cores = max(1, os.cpu_count() - 1)\n\n    r_script = f\"\"\"",
            "    n_cores = 1  # Windows: serial MS2 only\n\n    r_script = f\"\"\"",
        )
    old_sub = """        subprocess.run(
            ['Rscript', r_file],
            capture_output=True,  # MCP 协议严格要求所有通信必须是 JSON 格式，捕获所有输出，禁止它向 stdout 输出非 JSON 格式内容（MCP 客户端会监听 stdout）
            encoding='utf-8'
        )"""
    new_sub = """        log_file = os.path.join(output_dir, "data_preprocessing_xcms.log")
        print(f"XCMS log: {log_file}", file=sys.stderr)
        result = subprocess.run(["Rscript", r_file])
        if result.returncode != 0:
            tail = ""
            if os.path.isfile(log_file):
                with open(log_file, encoding="utf-8", errors="replace") as lf:
                    tail = "".join(lf.readlines()[-60:])
            raise RuntimeError(
                f"XCMS failed (exit {result.returncode}), see {log_file}\\n{tail}"
            )
        if not os.path.isfile(output_csv):
            raise RuntimeError(f"XCMS did not write feature_table.csv, see {log_file}")"""
    if old_sub in text:
        text = text.replace(old_sub, new_sub)
    if "import sys" not in text:
        text = text.replace("import os\n", "import os\nimport sys\n", 1)
    return text


def run_data_preprocessing_xcms(
    input_dir: str,
    output_dir: str,
    *,
    blank_pattern: str = "QC",
    file_pattern: str = "*.mzML",
    **kwargs,
) -> Path:
    """执行 patch 后的 XCMS，返回日志路径。"""
    src_path = ROOT / "src" / "tools" / "xcms.py"
    code = _patch_source(src_path.read_text(encoding="utf-8"))
    g: dict = {"__name__": "xcms_patched_exec", "sys": sys}
    exec(compile(code, str(src_path), "exec"), g)
    fn = g["data_preprocessing_xcms_impl"]
    import subprocess as sp
    import tempfile as _tf

    input_path = Path(input_dir).resolve()
    output_path = Path(output_dir).resolve()
    n_fixed = sanitize_mzml_for_msnbase(input_path)
    if n_fixed:
        print(f"已修复 {n_fixed} 个 mzML 的 cvParam 兼容性", file=sys.stderr)
    input_dir = input_path.as_posix()
    output_dir = output_path.as_posix()

    log_path = output_path / "data_preprocessing_xcms.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    _orig_run = sp.run
    _orig_ntf = _tf.NamedTemporaryFile

    def _utf8_ntf(*args, **kwargs):
        if "mode" in kwargs and "b" not in str(kwargs.get("mode", "")):
            kwargs.setdefault("encoding", "utf-8")
        return _orig_ntf(*args, **kwargs)

    def _logged_run(cmd, **kwargs):
        # 补丁后的 xcms.py 会传入 stdin/stdout 等；此处统一由包装层接管
        for key in (
            "capture_output",
            "encoding",
            "stdin",
            "stdout",
            "stderr",
            "text",
            "errors",
            "check",
        ):
            kwargs.pop(key, None)
        if cmd and len(cmd) >= 2:
            r_exe = str(cmd[0]).lower()
            if r_exe.endswith("rscript") or r_exe.endswith("rscript.exe"):
                r_path = Path(cmd[1])
                if r_path.is_file():
                    raw = r_path.read_text(encoding="utf-8", errors="replace")
                    patched = _patch_r_script_runtime(raw)
                    if patched != raw:
                        r_path.write_text(patched, encoding="utf-8")
                        print(
                            "Patched R script for serial MS2:",
                            r_path,
                            file=sys.stderr,
                        )
        with open(log_path, "w", encoding="utf-8") as log_f:
            proc = _orig_run(
                cmd,
                stdin=sp.DEVNULL,
                stdout=log_f,
                stderr=sp.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **kwargs,
            )
        if proc.returncode != 0:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-6000:]
            raise RuntimeError(
                f"Rscript exit {proc.returncode}, see {log_path}\n{tail}"
            )
        return proc

    _tf.NamedTemporaryFile = _utf8_ntf
    sp.run = _logged_run
    try:
        fn(
            input_dir=input_dir,
            output_dir=output_dir,
            file_pattern=file_pattern,
            blank_pattern=blank_pattern,
            **kwargs,
        )
    finally:
        sp.run = _orig_run
        _tf.NamedTemporaryFile = _orig_ntf

    if not (Path(output_dir) / "feature_table.csv").is_file():
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:] if log_path.is_file() else ""
        raise RuntimeError(f"未生成 feature_table.csv，见 {log_path}\n{tail}")
    return log_path


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "DY-1-1-质谱分析_a817b90a"
    inp = ROOT / "outputspace" / slug / "converted_mzml"
    out = ROOT / "outputspace" / slug / "peak_detection_results"
    print("input:", inp, file=sys.stderr)
    print("output:", out, file=sys.stderr)
    log = run_data_preprocessing_xcms(str(inp), str(out), blank_pattern="QC")
    print("OK", log)
