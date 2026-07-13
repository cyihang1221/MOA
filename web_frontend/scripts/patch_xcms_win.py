"""一次性补丁：修复 xcms data_preprocessing Windows 卡死与静默失败。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = ROOT / "src" / "tools" / "xcms.py"
t = p.read_text(encoding="utf-8")

OLD_PARALLEL = r"""# ============================= Parallel MS2 matching =============================
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

NEW_PARALLEL = r"""# ============================= MS2 matching =============================
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
if (run_serial_ms2) {{
    cat("MS2 matching: serial mode\\n")
    results <- lapply(feat_list, match_one_feat)
}} else {{
    cat("MS2 matching: parallel mode, cores=", n_cores, "\\n")
    cl <- makeCluster(n_cores)
    registerDoParallel(cl)
    results <- foreach(feat = feat_list, .packages = "MSnbase") %dopar% {{
        match_one_feat(feat)
    }}
    stopCluster(cl)
}}"""

if OLD_PARALLEL not in t:
    raise SystemExit("parallel block not found - already patched?")

t = t.replace(OLD_PARALLEL, NEW_PARALLEL)

if "from src.platform_utils import is_windows" not in t:
    t = t.replace(
        "import pandas as pd",
        "import pandas as pd\nimport sys\nfrom src.platform_utils import is_windows",
    )

if "run_serial_ms2" not in t:
    t = t.replace(
        "    if n_cores is None:\n        n_cores = max(1, os.cpu_count() - 1)\n\n    r_script = f\"\"\"",
        "    if n_cores is None:\n        n_cores = max(1, (os.cpu_count() or 2) - 1)\n"
        "    run_serial_ms2 = is_windows()\n"
        "    if run_serial_ms2:\n        n_cores = 1\n\n    r_script = f\"\"\"",
    )
    t = t.replace(
        "n_cores <- {n_cores}\n\nppm <- {ppm}",
        "n_cores <- {n_cores}\nrun_serial_ms2 <- {str(run_serial_ms2).upper()}\n\nppm <- {ppm}",
    )

OLD_SUB = """        subprocess.run(
            ['Rscript', r_file],
            capture_output=True,  # MCP 协议严格要求所有通信必须是 JSON 格式，捕获所有输出，禁止它向 stdout 输出非 JSON 格式内容（MCP 客户端会监听 stdout）
            encoding='utf-8'
        )"""

NEW_SUB = """        log_file = os.path.join(output_dir, "data_preprocessing_xcms.log")
        print(f"XCMS log: {log_file}", file=sys.stderr)
        with open(log_file, "w", encoding="utf-8") as log_f:
            result = subprocess.run(
                ["Rscript", r_file],
                stdin=subprocess.DEVNULL,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
            )
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

if OLD_SUB in t:
    t = t.replace(OLD_SUB, NEW_SUB)

p.write_text(t, encoding="utf-8")
print("patched", p)
