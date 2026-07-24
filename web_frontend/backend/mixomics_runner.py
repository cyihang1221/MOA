"""mixOmics 统计分析：日志重定向 + 避免 MCP stdio 管道死锁。"""
from __future__ import annotations

import os
import re
import subprocess as sp
import sys
import tempfile as _tf
from pathlib import Path

from src.platform_utils import resolve_rscript
from web_frontend.backend.export.editable_export import ensure_editable_sidecars
from web_frontend.backend.session_metadata import (
    ensure_aligned_metadata_csv,
    resolve_metadata_csv,
    sample_ids_from_feature_table,
)

ROOT = Path(__file__).resolve().parents[2]

_MIXOMICS_R_PACKAGES = ("mixOmics", "pheatmap", "readr", "dplyr", "ggplot2", "plotly")


def _rscript_executable() -> str:
    return resolve_rscript()


def _r_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    prefix = env.get("CONDA_PREFIX")
    if prefix:
        r_home = Path(prefix) / "Lib" / "R"
        if r_home.is_dir():
            env["R_HOME"] = str(r_home)
        r_bin = r_home / "bin" / "x64"
        if r_bin.is_dir():
            env["PATH"] = str(r_bin) + os.pathsep + env.get("PATH", "")
    return env


def _ensure_mixomics_r_packages() -> None:
    """运行前检查 mixOmics 等 R 包是否已安装。"""
    rscript = _rscript_executable()
    check = (
        "pkgs <- c(" + ",".join(f'"{p}"' for p in _MIXOMICS_R_PACKAGES) + "); "
        "missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly=TRUE)]; "
        "if (length(missing)) quit(save='no', status=2); "
        "cat('OK')"
    )
    proc = sp.run(
        [rscript, "-e", check],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=sp.DEVNULL,
        env=_r_subprocess_env(),
    )
    if proc.returncode == 0:
        return
    missing_hint = (
        "MOA 环境缺少 mixOmics / plotly 等 R 包。请在 conda activate MOA 后执行：\n"
        "  conda install -y -c conda-forge r-mixomics r-pheatmap r-plotly\n"
        "或 R 控制台： install.packages(c('mixOmics','plotly'))"
    )
    if proc.returncode == 2:
        raise RuntimeError(missing_hint)
    # 非 0/2 的退出码（如 Windows DLL 路径问题）不阻断；实际 R 脚本会给出明确报错


def _normalize_rscript_cmd(cmd: list) -> list:
    if not cmd:
        return cmd
    exe = str(cmd[0]).lower()
    if exe in ("rscript", "rscript.exe") or exe.endswith("\\rscript") or exe.endswith("/rscript"):
        cmd = [_rscript_executable(), *cmd[1:]]
    if len(cmd) >= 2 and cmd[1] != "--encoding=UTF-8":
        cmd = [cmd[0], "--encoding=UTF-8", *cmd[1:]]
    return list(cmd)


_PATH_BLOCK_OLD = """input_csv <- "{os.path.join(input_dir, 'feature_table_filtered_imputed.csv').replace(os.sep, '/')}"
metadata_csv <- "{metadata_csv.replace(os.sep, '/')}"
outdir <- "{output_dir.replace(os.sep, '/')}"
"""

_PATH_BLOCK_NEW = """input_csv <- Sys.getenv("MASS_MIXOMICS_INPUT_CSV")
metadata_csv <- Sys.getenv("MASS_MIXOMICS_METADATA_CSV")
outdir <- Sys.getenv("MASS_MIXOMICS_OUTPUT_DIR")
if (!nzchar(input_csv) || !nzchar(metadata_csv) || !nzchar(outdir)) {{
  stop("Missing MASS_MIXOMICS_* environment variables")
}}"""

_TEMPFILE_OLD = """    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name"""

_TEMPFILE_NEW = """    _r_tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.R', delete=False, encoding='utf-8'
    )
    try:
        _r_tmp.write(r_script)
        r_file = _r_tmp.name
    finally:
        _r_tmp.close()"""

_OLD_SUB = 'subprocess.run(["Rscript", r_file], capture_output=False)'

_NEW_SUB = """log_file = os.path.join(output_dir, "statistical_analysis_mixomics.log")
        print(f"mixOmics log: {log_file}", file=sys.stderr)
        result = subprocess.run(["Rscript", r_file])
        if result.returncode != 0:
            tail = ""
            if os.path.isfile(log_file):
                with open(log_file, encoding="utf-8", errors="replace") as lf:
                    tail = "".join(lf.readlines()[-80:])
            raise RuntimeError(
                f"mixOmics failed (exit {result.returncode}), see {log_file}\\n{tail}"
            )"""

_PERF_OLD = """perf_res <- perf(
    plsda_res,
    validation = "Mfold",
    folds = n_folds,
    nrepeat = 10,
    progressBar = TRUE
)"""

_PERF_NEW = """perf_res <- perf(
    plsda_res,
    validation = "Mfold",
    folds = n_folds,
    nrepeat = 3,
    progressBar = FALSE
)"""

_PCA_PLOT_OLD = """plotIndiv(
    pca_res,
    comp = pca_plot_comps,
    group = Y,
    legend = TRUE,
    title = "PCA"
)"""

_PCA_PLOT_NEW = """plotIndiv(
    pca_res,
    comp = pca_plot_comps,
    group = Y,
    legend = TRUE,
    title = "PCA",
    style = "graphics"
)"""

_PLSDA_PLOT_OLD = """plotIndiv(
    plsda_res,
    comp = plsda_plot_comps,
    group = Y,
    legend = TRUE,
    title = "PLS-DA"
)"""

_PLSDA_PLOT_NEW = """plotIndiv(
    plsda_res,
    comp = plsda_plot_comps,
    group = Y,
    legend = TRUE,
    title = "PLS-DA",
    style = "graphics"
)"""

_GROUP_GUARD = """
# ============================= PLS-DA =============================
if (nlevels(Y) < 2) {{
    writeLines(
        paste(
            "Skipped PLS-DA/CV/VIP/volcano: only",
            nlevels(Y),
            "group(s) matched feature table samples.",
            "PCA was still computed."
        ),
        file.path(outdir, "analysis_warning.txt")
    )
}} else {{
"""

_GROUP_GUARD_CLOSE = """
}}


# ============================= Session Info =============================
"""


def _patch_mixomics_source(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("✓", "OK")
    if _PATH_BLOCK_OLD in text:
        text = text.replace(_PATH_BLOCK_OLD, _PATH_BLOCK_NEW)
    if _TEMPFILE_OLD in text:
        text = text.replace(_TEMPFILE_OLD, _TEMPFILE_NEW)
    if _OLD_SUB in text:
        text = text.replace(_OLD_SUB, _NEW_SUB)
    if _PERF_OLD in text:
        text = text.replace(_PERF_OLD, _PERF_NEW)
    if _PCA_PLOT_OLD in text:
        text = text.replace(_PCA_PLOT_OLD, _PCA_PLOT_NEW)
    if _PLSDA_PLOT_OLD in text:
        text = text.replace(_PLSDA_PLOT_OLD, _PLSDA_PLOT_NEW)
    if "import sys" not in text:
        text = text.replace("import os\n", "import os\nimport sys\n", 1)

    marker = "# ============================= PLS-DA ============================="
    if marker in text and _GROUP_GUARD.strip() not in text:
        text = text.replace(marker, _GROUP_GUARD.strip(), 1)
        heatmap_marker = "# ============================= Heatmap ============================="
        session_marker = "# ============================= Session Info ============================="
        if heatmap_marker in text and session_marker in text:
            text = text.replace(
                session_marker,
                _GROUP_GUARD_CLOSE.strip() + "\n",
                1,
            )
    return text


def run_statistical_analysis_mixomics(
    input_dir: str,
    metadata_csv: str,
    output_dir: str,
    **kwargs,
) -> Path:
    """执行 patch 后的 mixOmics 流程，返回日志路径。"""
    input_path = Path(input_dir).resolve()
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    imputed = input_path / "feature_table_filtered_imputed.csv"
    if not imputed.is_file():
        raise FileNotFoundError(f"未找到 feature_table_filtered_imputed.csv: {imputed}")

    meta_candidate = Path(metadata_csv)
    upload_for_meta = (
        meta_candidate.parent
        if meta_candidate.suffix.lower() == ".csv"
        else meta_candidate
    )
    # 先保证有会话 metadata 文件，再按特征表样本自动对齐（避免旧实验 Sample 残留）
    resolve_metadata_csv(upload_for_meta)
    sample_ids = sample_ids_from_feature_table(imputed)
    if not sample_ids:
        raise ValueError(f"特征表中未找到样本列: {imputed}")
    metadata_csv, align_report = ensure_aligned_metadata_csv(
        upload_for_meta,
        sample_ids,
    )
    _ensure_mixomics_r_packages()

    imputed_csv = imputed.resolve().as_posix()
    meta_csv = Path(metadata_csv).resolve().as_posix()
    out_dir = output_path.as_posix()
    align_note = output_path / "metadata_alignment_report.txt"
    align_note.write_text(
        "\n".join(
            [
                f"action={align_report.get('action')}",
                f"source={align_report.get('source')}",
                f"matched={align_report.get('n_matched')}/{align_report.get('n_samples')}",
                f"inferred={align_report.get('n_inferred')}",
                f"groups={','.join(align_report.get('groups') or [])}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env_backup = {
        key: os.environ.get(key)
        for key in (
            "MASS_MIXOMICS_INPUT_CSV",
            "MASS_MIXOMICS_METADATA_CSV",
            "MASS_MIXOMICS_OUTPUT_DIR",
        )
    }
    os.environ["MASS_MIXOMICS_INPUT_CSV"] = imputed_csv
    os.environ["MASS_MIXOMICS_METADATA_CSV"] = meta_csv
    os.environ["MASS_MIXOMICS_OUTPUT_DIR"] = out_dir

    from src.tools.xcms import statistical_analysis_mixomics_impl as fn

    log_path = output_path / "statistical_analysis_mixomics.log"
    _orig_run = sp.run

    def _logged_run(cmd, **kwargs):
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
        cmd = _normalize_rscript_cmd(list(cmd))
        with open(log_path, "w", encoding="utf-8") as log_f:
            proc = _orig_run(
                cmd,
                stdin=sp.DEVNULL,
                stdout=log_f,
                stderr=sp.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=_r_subprocess_env(),
                **kwargs,
            )
        if proc.returncode != 0:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
            raise RuntimeError(
                f"Rscript exit {proc.returncode}, see {log_path}\n{tail}"
            )
        return proc

    sp.run = _logged_run
    try:
        fn(
            input_dir=input_path.as_posix(),
            metadata_csv=meta_csv,
            output_dir=out_dir,
            **kwargs,
        )
    finally:
        sp.run = _orig_run
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    if not (output_path / "pca_scores.csv").is_file():
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:] if log_path.is_file() else ""
        raise RuntimeError(f"未生成 pca_scores.csv，见 {log_path}\n{tail}")

    from web_frontend.backend.pipeline_utils import ensure_empty_differential_csv

    ensure_empty_differential_csv(output_path)
    ensure_editable_sidecars(
        output_path,
        title_map={
            "pca_plot.png": "PCA",
            "plsda_plot.png": "PLS-DA",
            "volcano_plot.png": "Volcano Plot",
            "vip_scores.png": "VIP Scores",
            "heatmap_top_vip.png": "Top VIP Heatmap",
        },
    )
    from web_frontend.backend.export.plotly_sidecar_backfill import backfill_statistical_plotly_sidecars

    try:
        backfill_statistical_plotly_sidecars(output_path, meta_csv)
    except Exception as exc:
        print(f"    ⚠️ Plotly sidecar backfill skipped: {exc}")
    try:
        from web_frontend.backend.plot_edit_service import ensure_default_plot_configs

        ensure_default_plot_configs(output_path, upload_dir=Path(meta_csv).parent if meta_csv else None)
    except Exception as exc:
        print(f"    ⚠️ Default plot_config backfill skipped: {exc}")
    return log_path
