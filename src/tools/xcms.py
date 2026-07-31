import os
import shutil
import subprocess
import tempfile
import glob
import pandas as pd
from pathlib import Path
from typing import Optional, List, Tuple

from src.platform_utils import PROJECT_ROOT
from web_frontend.backend.export.editable_export import ensure_editable_sidecars, save_editable_metadata


def _xcms_tools_dir() -> str:
    """Return src/tools directory; safe under normal import and exec()."""
    mod_file = globals().get("__file__")
    if mod_file:
        return str(Path(mod_file).resolve().parent)
    return str(PROJECT_ROOT / "src" / "tools")


def _r_plotly_export_path() -> str:
    """Return path to r_plotly_export.R (lives under web_frontend/backend/export)."""
    return str(PROJECT_ROOT / "web_frontend" / "backend" / "export" / "r_plotly_export.R")




# ===================================================== data_preprocessing ================================================================
# XCMS-Centwave, XCMS-Obiwarp
def data_preprocessing_xcms_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    blank_pattern: str = "Blank",
    ms2_ppm: float = 20,
    ms2_rt_window: float = 5,
    blank_ratio_threshold: float = 3,
    n_cores: int | None = None,
    ppm: float = 10,
    peakwidth: tuple = (5, 20),
    snthresh: float = 10,
    prefilter: tuple = (3, 100),
    bin_size: float = 0.25,
    center: int = 1,
    bw: float = 5,
    min_fraction: float = 0.5,
    min_samples: int = 2
):
    """
    Parameters
    ----------
    input_dir : str
        Directory containing mzML files.
    output_dir : str
        Output directory for feature table and MGF spectra.
    file_pattern : str, default="*.mzML"
        Pattern to match mzML files in the input directory.
    blank_pattern : str, default="Blank"
        Keyword used to identify blank samples from file names (case-insensitive).
    ms2_ppm : float, default=20
        Precursor mass tolerance (ppm) used to match MS2 spectra to features.
    ms2_rt_window : float, default=5
        Retention time window (seconds) for MS2 matching.
    blank_ratio_threshold : float, default=3
        Minimum sample-to-blank intensity ratio required to retain a feature.
    n_cores : int or None, default=None
        Number of CPU cores for parallel processing. If None, uses all available cores minus one.
    ppm : float, default=10
        Mass accuracy (ppm) for XCMS peak detection.
    peakwidth : tuple, default=(5, 20)
        Expected chromatographic peak width range in seconds.
    snthresh : float, default=10
        Signal-to-noise ratio threshold for peak detection.
    prefilter : tuple, default=(3, 100)
        Prefilter settings for CentWave: minimum number of scans and minimum intensity.
    bin_size : float, default=0.25
        Bin size for retention time alignment.
    center : int, default=1
        Reference sample index for Obiwarp alignment.
    bw : float, default=5
        Bandwidth for peak grouping.
    min_fraction : float, default=0.5
        Minimum fraction of samples in which a feature must be present.
    min_samples : int, default=2
        Minimum number of samples in which a feature must be present.
    """

    print("\nProcessing LC-MS/MS data with XCMS...")

    os.makedirs(output_dir, exist_ok=True)

    output_csv = os.path.join(output_dir, "feature_table.csv")
    output_mgf = os.path.join(output_dir, "spectra.mgf")

    # 如果结果文件已存在，跳过 XCMS 处理
    if os.path.exists(output_csv) and os.path.exists(output_mgf):
        print(f"  XCMS results already exist, skipping...")
        print(f"    feature_table: {output_csv}")
        print(f"    spectra:       {output_mgf}")
        return

    if n_cores is None:
        n_cores = max(1, os.cpu_count() - 1)

    r_script = f"""
# ============================= packages =============================
library(xcms)
library(MSnbase)
library(foreach)
library(doParallel)
library(BiocParallel)


# ============================= parameters =============================
input_dir <- "{input_dir.replace(os.sep, '/')}"
output_csv <- "{output_csv.replace(os.sep, '/')}"
output_mgf <- "{output_mgf.replace(os.sep, '/')}"

file_pattern <- "{file_pattern}"
blank_pattern <- "{blank_pattern}"
ms2_ppm <- {ms2_ppm}
ms2_rt_window <- {ms2_rt_window}
blank_ratio_threshold <- {blank_ratio_threshold}
n_cores <- {n_cores}

ppm <- {ppm}
peakwidth <- c({peakwidth[0]}, {peakwidth[1]})
snthresh <- {snthresh}
prefilter <- c({prefilter[0]}, {prefilter[1]})
binSize <- {bin_size}
center <- {center}
bw <- {bw}
minFraction <- {min_fraction}
minSamples <- {min_samples}


# ============================= read data =============================
mzml_files <- list.files(path = "{input_dir}", pattern = "{file_pattern}", full.names = TRUE)

if (length(mzml_files) == 0) {{
    stop("No .mzML files found in input_dir")
}}

raw_data <- readMSData(mzml_files, msLevel. = 1:2, mode = "onDisk", verbose = FALSE)


# ============================= peak detection =============================
ms1_data <- filterMsLevel(raw_data, 1)

cwp <- CentWaveParam(
    ppm = ppm,
    peakwidth = peakwidth,
    snthresh = snthresh,
    prefilter = prefilter,
    mzCenterFun = "wMean",
    integrate = 1
)

xdata <- findChromPeaks(ms1_data, param = cwp)


# ============================= RT alignment (serial to avoid parallel issues) =============================
register(SerialParam())
xdata <- adjustRtime(
    xdata,
    param = ObiwarpParam(
        binSize = binSize,
        center = center
    )
)


# ============================= Peak grouping =============================
pdp <- PeakDensityParam(
    sampleGroups = rep(1, length(mzml_files)),
    bw = bw,
    minFraction = minFraction,
    minSamples = minSamples
)

xdata <- groupChromPeaks(xdata, param = pdp)


# ============================= Gap filling =============================
xdata <- fillChromPeaks(xdata)


# ============================= Feature matrix and definitions =============================
feature_matrix <- featureValues(xdata, value = "into")
feature_def <- featureDefinitions(xdata)


# ============================= blank subtraction =============================
blank_idx <- grep(
    blank_pattern,
    basename(mzml_files),
    ignore.case = TRUE
)

if (length(blank_idx) == 0) {{
    warning("No blank samples found - skipping blank subtraction")
    keep_final <- rep(TRUE, nrow(feature_matrix))
    intensity_corrected <- NULL
}} else {{
    sample_idx <- setdiff(seq_len(ncol(feature_matrix)), blank_idx)

    blank_means <- rowMeans(
        feature_matrix[, blank_idx, drop = FALSE],
        na.rm = TRUE
    )

    intensity_corrected <- feature_matrix[, sample_idx, drop = FALSE]
    intensity_corrected <- sweep(
        intensity_corrected,
        1,
        blank_means,
        FUN = "-"
    )

    intensity_corrected[intensity_corrected < 0] <- 0

    max_int <- apply(
        intensity_corrected,
        1,
        max,
        na.rm = TRUE
    )

    ratio <- ifelse(
        blank_means == 0 & max_int == 0,
        0,
        max_int / (blank_means + 1e-9)
    )

    keep_ratio <- !is.na(ratio) & ratio > blank_ratio_threshold
    has_signal <- rowSums(
        intensity_corrected > 0,
        na.rm = TRUE
    ) >= 1

    keep_final <- keep_ratio & has_signal

    cat("Features after blank subtraction:",
        sum(keep_final), "\\n")
}}

selected_ids <- rownames(feature_matrix)[keep_final]

if (length(selected_ids) == 0) {{
    stop("No features passed blank filtering")
}}


# ============================= MS2 extraction =============================
ms2_data <- filterMsLevel(raw_data, 2)

if (length(ms2_data) == 0) {{
    stop("No MS2 spectra found")
}}

cat("Extracting MS2 spectra...\n")

# Robust extraction: avoid spectra(ms2_data), which may fail if featureData
# lacks required columns such as fileIdx, spIdx, acquisitionNum, etc.
ms2_spectra <- vector("list", length(ms2_data))

for (i in seq_len(length(ms2_data))) {{
    sp <- tryCatch(
        ms2_data[[i]],
        error = function(e) NULL
    )
    ms2_spectra[[i]] <- sp
}}

# Remove invalid spectra
valid_idx <- vapply(
    ms2_spectra,
    function(sp) {{
        !is.null(sp) &&
        length(mz(sp)) > 0 &&
        length(intensity(sp)) > 0
    }},
    logical(1)
)

ms2_spectra <- ms2_spectra[valid_idx]

if (length(ms2_spectra) == 0) {{
    stop("No valid MS2 spectra found")
}}

cat("Valid MS2 spectra:", length(ms2_spectra), "\n")

# Extract retention time and precursor m/z
ms2_rt <- vapply(
    ms2_spectra,
    function(sp) {{
        rt <- rtime(sp)
        if (length(rt) == 0 || is.na(rt[1])) {{
            NA_real_
        }} else {{
            rt[1]
        }}
    }},
    numeric(1)
)

ms2_premz <- vapply(
    ms2_spectra,
    function(sp) {{
        pmz <- precursorMz(sp)
        if (length(pmz) == 0 || is.na(pmz[1])) {{
            NA_real_
        }} else {{
            pmz[1]
        }}
    }},
    numeric(1)
)

# Keep only spectra with valid precursor metadata
valid_meta <- !is.na(ms2_rt) & !is.na(ms2_premz)

ms2_spectra <- ms2_spectra[valid_meta]
ms2_rt <- ms2_rt[valid_meta]
ms2_premz <- ms2_premz[valid_meta]

if (length(ms2_spectra) == 0) {{
    stop("No MS2 spectra with valid precursor metadata found")
}}

cat("MS2 spectra with valid precursor metadata:",
    length(ms2_spectra), "\n")


match_ms2 <- function(
    mz,
    rt,
    ms2_rt,
    ms2_premz,
    ms2_sp,
    ppm,
    rt_win
) {{
    mz_err <- (ppm / 1e6) * mz

    rt_ok <- ms2_rt >= (rt - rt_win) &
             ms2_rt <= (rt + rt_win)

    if (!any(rt_ok)) {{
        return(NULL)
    }}

    premz_ok <- !is.na(ms2_premz) &
                ms2_premz >= (mz - mz_err) &
                ms2_premz <= (mz + mz_err)

    idx <- which(rt_ok & premz_ok)

    if (length(idx) == 0) {{
        return(NULL)
    }}

    # If multiple spectra match, choose the closest in RT
    if (length(idx) > 1) {{
        idx <- idx[which.min(abs(ms2_rt[idx] - rt))]
    }}

    sp <- ms2_sp[[idx]]

    keep <- intensity(sp) > 0

    if (sum(keep) == 0) {{
        return(NULL)
    }}

    list(
        mz = mz(sp)[keep],
        int = intensity(sp)[keep]
    )
}}


# ============================= Features retained after blank filtering =============================
feat_sub <- feature_def[selected_ids, , drop = FALSE]
feat_list <- split(feat_sub, seq_len(nrow(feat_sub)))


# ============================= Parallel MS2 matching =============================
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

stopCluster(cl)


# ============================= collect matched spectra =============================
success_ids <- c()
mgf_lines <- c()

for (r in results) {{
    if (!is.null(r)) {{
        success_ids <- c(success_ids, r$feature_id)
        mgf_lines <- c(mgf_lines, r$mgf)
    }}
}}

if (length(success_ids) == 0) {{
    stop("No MS2 spectra matched")
}}

writeLines(mgf_lines, output_mgf)
cat("MGF written:", output_mgf, "\\n")


# ============================= final feature table =============================

# CSV 表格 只保留有 MS2 图谱的特征, 保证 CSV 行数 = MGF 条目数, 一一对应，不会错乱

if (exists("intensity_corrected") &&
    !is.null(intensity_corrected)) {{
    
    final_mat <- intensity_corrected[
        success_ids,
        ,
        drop = FALSE
    ]

    final_tab <- data.frame(
        feature_id = rownames(final_mat),
        mz = feature_def[success_ids, "mzmed"],
        rt_med = feature_def[success_ids, "rtmed"],
        final_mat,
        stringsAsFactors = FALSE,
        check.names = FALSE
    )

}} else {{
    raw_quant <- feature_matrix[success_ids, , drop = FALSE]
    # 构建最终表格
    final_tab <- data.frame(
        feature_id = rownames(raw_quant),
        mz = feature_def[success_ids, "mzmed"],
        rt_med = feature_def[success_ids, "rtmed"],
        raw_quant,
        stringsAsFactors = FALSE,
        check.names = FALSE
    )
}}

write.csv(
    final_tab,
    file = output_csv,
    row.names = FALSE
)

cat("CSV written:", output_csv, "\\n")
cat(
    paste(
        "Final CSV rows:",
        nrow(final_tab),
        "| MGF entries:",
        length(success_ids)
    ),
    "\\n"
)

if (nrow(final_tab) == length(success_ids)) {{
    cat("✓ Row count matches MGF entries.\\n")
}}
"""

    # 写入临时 R 脚本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    # 运行 R 脚本
    try:
        result = subprocess.run(
            ['Rscript', r_file],
            capture_output=True,
            encoding='utf-8'
        )
        if result.returncode != 0:
            print(f"\n[R ERROR] XCMS processing failed (exit code {result.returncode}):")
            print(result.stderr)
            print(result.stdout)
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

    finally:
        os.unlink(r_file)




# ============================================ feature filtering & missing value imputation =====================================================
# kNN



# ============================================ feature filtering & missing value imputation =====================================================
# kNN
def feature_filtering_and_missing_value_imputation_KNN_impl(
    input_dir: str,
    output_dir: str,
    min_presence: float = 0.5,  # filtering
    min_intensity: float = 0.0,  # filtering
    n_neighbors: int = 5  # KNN
):
    """
    Feature filtering and missing value imputation.

    Input feature table format:
    feature_id,mz,rt_med,sample1,sample2,...

    Parameters
    ----------
    input_dir : str
        Path to the input directory containing the feature table.

    output_dir : str
        Path to the output directory to save the filtered and imputed feature table.

    min_presence : float
        Minimum fraction of non-missing samples required.

    min_intensity : float
        Minimum mean intensity threshold.

    n_neighbors : int
        Number of neighbors for KNN imputation.
    """

    print("\nFiltering features and performing KNN missing value imputation...")

    os.makedirs(output_dir, exist_ok=True)
    summary_txt = os.path.join(output_dir, "feature_filtering_and_missing_value_imputation_summary.txt")

    import pandas as pd
    import numpy as np

    # ============================= read table =============================
    df = pd.read_csv(os.path.join(input_dir, "feature_table.csv"))

    required_cols = [
        "feature_id",
        "mz",
        "rt_med"
    ]

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(
                f"Missing required column: {col}"
            )

    # ============================= sample columns =============================
    sample_cols = [
        c for c in df.columns
        if c not in required_cols
    ]

    if len(sample_cols) == 0:
        raise ValueError(
            "No sample columns found."
        )

    # ============================= convert numeric =============================
    df[sample_cols] = df[sample_cols].apply(
        pd.to_numeric,
        errors="coerce"
    )

    n_before = df.shape[0]

    # ============================= missing ratio filtering =============================
    presence_ratio = (
        df[sample_cols]
        .notna()
        .sum(axis=1)
        / len(sample_cols)
    )

    df = df[
        presence_ratio >= min_presence
    ].copy()

    n_after_presence = df.shape[0]

    # ============================= intensity filtering =============================
    mean_intensity = df[sample_cols].mean(
        axis=1,
        skipna=True
    )

    df = df[
        mean_intensity >= min_intensity
    ].copy()

    n_after_intensity = df.shape[0]

    # ============================= KNN imputation =============================
    from sklearn.impute import KNNImputer

    imputer = KNNImputer(
        n_neighbors=n_neighbors
    )

    df[sample_cols] = imputer.fit_transform(
        df[sample_cols]
    )

    # ============================= save =============================
    df.to_csv(
        os.path.join(output_dir, "feature_table_filtered_imputed.csv"),
        index=False
    )

    # ============================= summary =============================
    summary_lines = [
        "Feature Filtering Summary",
        "=========================",
        f"Input features: {n_before}",
        f"After presence filtering: {n_after_presence}",
        f"After intensity filtering: {n_after_intensity}",
        f"min_presence: {min_presence}",
        f"min_intensity: {min_intensity}",
        f"KNN neighbors: {n_neighbors}",
        f"Final output: {os.path.join(output_dir, 'feature_table_filtered_imputed.csv')}"
    ]

    with open(summary_txt, "w") as f:
        f.write("\n".join(summary_lines))

    print(
        f"✅ Filtering & imputation complete:\n"
        f"   {os.path.join(output_dir, 'feature_table_filtered_imputed.csv')}"
    )

    print(
        f"Features retained: "
        f"{n_after_intensity}/{n_before}"
    )




# ======================================================= statistical analysis ==================================================================
# mixOmics



# ======================================================= statistical analysis ==================================================================
def statistical_analysis_mixomics_impl(
    input_dir: str,
    metadata_csv: str,
    output_dir: str,
    ncomp_pca: int = 5,
    ncomp_plsda: int = 2,
    scale_method: str = "autoscale",
    top_n_heatmap: int = 50,
    seed: int = 123,

    # differential metabolite thresholds
    vip_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
    padj_threshold: float = 0.05,
    log2fc_threshold: float = 0.58,
    use_fdr: bool = False,

    # analysis goal parameterization
    group_column: str = "Group",
    contrast_group1: str | None = None,
    contrast_group2: str | None = None,
):
    """
    Statistical analysis for metabolomics feature table.

    Parameters
    ----------
    input_dir : str
        Path to the input directory containing the feature table after filtering and imputation.

    output_dir : str
        Directory to save the statistical analysis results.

    group_column : str, default "Group"
        Metadata column used as PLS-DA Y (and PCA/PLS plotIndiv group).

    contrast_group1, contrast_group2 : str, optional
        Volcano contrast levels within ``group_column``. When both set, volcano
        uses those two levels even if there are more groups overall.
        When omitted and exactly 2 levels exist, uses alphabetical factor order.

    Input feature table format:
    feature_id,mz,rt_med,sample1,sample2,...

    metadata.csv format:
    Sample,<group_column>,...
    """

    print("\nPerforming statistical analysis using mixOmics...")

    os.makedirs(output_dir, exist_ok=True)
    _r_plotly_helpers = _r_plotly_export_path().replace(os.sep, "/")

    imputed_csv = os.path.join(input_dir, "feature_table_filtered_imputed.csv").replace(os.sep, "/")
    os.environ["MASS_MIXOMICS_INPUT_CSV"] = imputed_csv
    os.environ["MASS_MIXOMICS_METADATA_CSV"] = metadata_csv.replace(os.sep, "/")
    os.environ["MASS_MIXOMICS_OUTPUT_DIR"] = output_dir.replace(os.sep, "/")
    os.environ["MASS_MIXOMICS_GROUP_COLUMN"] = str(group_column or "Group").strip() or "Group"
    os.environ["MASS_MIXOMICS_CONTRAST_G1"] = str(contrast_group1 or "").strip()
    os.environ["MASS_MIXOMICS_CONTRAST_G2"] = str(contrast_group2 or "").strip()

    r_script = f"""
# ============================= packages =============================
library(readr)
library(dplyr)
library(tibble)
library(ggplot2)
library(mixOmics)
library(pheatmap)

try(source("{_r_plotly_helpers}", local = FALSE, encoding = "UTF-8"), silent = TRUE)


# ============================= parameters =============================
input_csv <- Sys.getenv("MASS_MIXOMICS_INPUT_CSV")
metadata_csv <- Sys.getenv("MASS_MIXOMICS_METADATA_CSV")
outdir <- Sys.getenv("MASS_MIXOMICS_OUTPUT_DIR")
if (!nzchar(input_csv) || !nzchar(metadata_csv) || !nzchar(outdir)) {{
  stop("Missing MASS_MIXOMICS_* environment variables")
}}

ncomp_pca <- {ncomp_pca}
ncomp_plsda <- {ncomp_plsda}

scale_method <- "{scale_method}"
top_n_heatmap <- {top_n_heatmap}

seed <- {seed}

vip_threshold <- {vip_threshold}
pvalue_threshold <- {pvalue_threshold}
padj_threshold <- {padj_threshold}
log2fc_threshold <- {log2fc_threshold}
use_fdr <- {str(use_fdr).upper()}

group_column_req <- Sys.getenv("MASS_MIXOMICS_GROUP_COLUMN", unset = "Group")
if (!nzchar(group_column_req)) group_column_req <- "Group"
contrast_g1_req <- Sys.getenv("MASS_MIXOMICS_CONTRAST_G1")
contrast_g2_req <- Sys.getenv("MASS_MIXOMICS_CONTRAST_G2")

dir.create(outdir, showWarnings = FALSE, recursive = TRUE)


# ============================= read data =============================
feature_df <- read_csv(
    input_csv,
    show_col_types = FALSE
)

metadata <- read_csv(
    metadata_csv,
    show_col_types = FALSE
)


# ============================= parameter check =============================
if (!scale_method %in% c("autoscale", "none")) {{
    stop("scale_method must be 'autoscale' or 'none'")
}}

if (!("Sample" %in% colnames(metadata))) {{
    stop("metadata must contain a Sample column")
}}

resolve_meta_column <- function(requested, available) {{
    if (requested %in% available) return(requested)
    hit <- available[tolower(available) == tolower(requested)]
    if (length(hit) >= 1) return(hit[[1]])
    NULL
}}

group_column <- resolve_meta_column(group_column_req, colnames(metadata))
if (is.null(group_column)) {{
    stop(paste0(
        "metadata missing group_column '", group_column_req,
        "'. Available: ", paste(colnames(metadata), collapse = ", ")
    ))
}}


# ============================= sample columns =============================
sample_cols <- setdiff(
    colnames(feature_df),
    c("feature_id", "mz", "rt_med")
)

if (length(sample_cols) == 0) {{
    stop("No sample columns found.")
}}


# ============================= construct matrix =============================
X <- feature_df %>%
    dplyr::select(
        mz,
        rt_med,
        dplyr::all_of(sample_cols)
    ) %>%
    as.matrix()

colnames(X)[1] <- "mz"
colnames(X)[2] <- "rt"


# ============================= align metadata =============================
metadata <- metadata %>%
    dplyr::filter(Sample %in% sample_cols)

if (nrow(metadata) == 0) {{
    stop("No matched samples between metadata and feature table")
}}

sample_cols <- metadata$Sample


# ============================= remove zero variance =============================
keep <- apply(
    X[, 3:ncol(X)],
    1,
    function(v) sd(v, na.rm = TRUE) > 0
)

if (!any(keep)) {{
    stop("All features have zero variance")
}}

X <- X[keep, , drop = FALSE]
feature_df <- feature_df[keep, , drop = FALSE]


# ============================= transform =============================
X[, 3:ncol(X)] <- log2(
    X[, 3:ncol(X)] + 1
)

if (scale_method == "autoscale") {{

    X[, 3:ncol(X)] <- t(
        apply(
            X[, 3:ncol(X)],
            1,
            scale
        )
    )
}}


# ============================= prepare matrix =============================
Y <- factor(metadata[[group_column]])

feature_matrix <- as.matrix(
    X[, sample_cols, drop = FALSE]
)

rownames(feature_matrix) <- feature_df$feature_id

X_tmp <- t(feature_matrix)

X_tmp <- X_tmp[
    metadata$Sample,
    ,
    drop = FALSE
]

writeLines(
    c(
        paste0("group_column=", group_column),
        paste0("n_levels=", nlevels(Y)),
        paste0("levels=", paste(levels(Y), collapse = ",")),
        paste0("contrast_group1_req=", contrast_g1_req),
        paste0("contrast_group2_req=", contrast_g2_req),
        paste0("n_samples=", nrow(X_tmp)),
        paste0("group_sizes=", paste(names(table(Y)), as.integer(table(Y)), sep = "=", collapse = "; "))
    ),
    file.path(outdir, "analysis_params.txt")
)
# 每轮重写警告文件，避免旧 run 的「only 1 group」残留误导
warning_file <- file.path(outdir, "analysis_warning.txt")
if (file.exists(warning_file)) file.remove(warning_file)


# ============================= PCA =============================
pca_res <- pca(
    X_tmp,
    ncomp = min(
        ncomp_pca,
        ncol(X_tmp),
        nrow(X_tmp) - 1
    )
)

write.csv(
    pca_res$variates$X,
    file.path(outdir, "pca_scores.csv")
)

png(
    file.path(outdir, "pca_plot.png"),
    width = 1800,
    height = 1500,
    res = 300
)

pca_plot_comps <- if (
    ncol(pca_res$variates$X) >= 2
) c(1, 2) else c(1, 1)

plotIndiv(
    pca_res,
    comp = pca_plot_comps,
    group = Y,
    legend = TRUE,
    title = "PCA",
    style = "graphics"
)

dev.off()

try(
try(
    save_pca_plsda_plotly_sidecar(
        pca_res$variates$X,
        Y,
        file.path(outdir, "pca_plot.png"),
        "PCA",
        pca_plot_comps
    ),
    silent = TRUE
),
    silent = TRUE
)


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
plsda_res <- plsda(
    X_tmp,
    Y,
    ncomp = min(
        ncomp_plsda,
        nlevels(Y) - 1,
        ncol(X_tmp),
        nrow(X_tmp) - 1
    )
)

write.csv(
    plsda_res$variates$X,
    file.path(outdir, "plsda_scores.csv")
)

png(
    file.path(outdir, "plsda_plot.png"),
    width = 1800,
    height = 1500,
    res = 300
)

plsda_plot_comps <- if (
    ncol(plsda_res$variates$X) >= 2
) c(1, 2) else c(1, 1)

plotIndiv(
    plsda_res,
    comp = plsda_plot_comps,
    group = Y,
    legend = TRUE,
    title = "PLS-DA",
    style = "graphics"
)

dev.off()

try(
try(
    save_pca_plsda_plotly_sidecar(
        plsda_res$variates$X,
        Y,
        file.path(outdir, "plsda_plot.png"),
        "PLS-DA",
        plsda_plot_comps
    ),
    silent = TRUE
),
    silent = TRUE
)


# ============================= Cross Validation =============================
# 小样本时 mixOmics::perf() 的 Mfold 极易在 solve(Sr) 上奇异崩溃；
# CV 失败不应阻断 VIP / 火山图 / 差异代谢物输出。
set.seed(seed)

min_group_size <- min(as.integer(table(Y)))
n_samples <- nrow(X_tmp)
n_folds <- min(5L, max(2L, min_group_size))

# 经验阈值：每组 <3 或总样本 <6 时跳过 CV（仍保留 PLS-DA 得分图）
skip_perf <- (min_group_size < 3L) || (n_samples < 6L) || (n_folds < 2L)

if (skip_perf) {{
    write(
        paste0(
            "Skipped PLS-DA cross-validation (perf): too few samples for stable Mfold ",
            "(n=", n_samples, ", min_group_size=", min_group_size,
            ", folds=", n_folds, "). VIP/volcano still computed from plsda model."
        ),
        file = file.path(outdir, "analysis_warning.txt"),
        append = file.exists(file.path(outdir, "analysis_warning.txt"))
    )
    writeLines(
        paste0(
            "CV skipped: n=", n_samples,
            ", min_group_size=", min_group_size,
            ", folds=", n_folds
        ),
        file.path(outdir, "plsda_cv_results.txt")
    )
}} else {{
    perf_ok <- FALSE
    tryCatch(
        {{
            perf_res <- perf(
                plsda_res,
                validation = "Mfold",
                folds = n_folds,
                nrepeat = 3,
                progressBar = FALSE
            )
            capture.output(
                print(perf_res$error.rate),
                file = file.path(outdir, "plsda_cv_results.txt")
            )
            perf_ok <- TRUE
        }},
        error = function(e) {{
            write(
                paste0(
                    "PLS-DA cross-validation (perf) failed: ",
                    conditionMessage(e),
                    ". Continuing with VIP/volcano from the fitted plsda model."
                ),
                file = file.path(outdir, "analysis_warning.txt"),
                append = file.exists(file.path(outdir, "analysis_warning.txt"))
            )
            writeLines(
                paste0("CV failed: ", conditionMessage(e)),
                file.path(outdir, "plsda_cv_results.txt")
            )
        }}
    )
    if (!perf_ok) {{
        message("perf() failed; continuing without CV metrics")
    }}
}}


# ============================= VIP =============================
vip_scores <- vip(plsda_res)

if (length(dim(vip_scores)) == 2) {{

    ncomp_used <- min(
        ncomp_plsda,
        ncol(vip_scores)
    )

    vip_mean <- rowMeans(
        vip_scores[
            ,
            seq_len(ncomp_used),
            drop = FALSE
        ]
    )

}} else {{

    vip_mean <- vip_scores
}}

vip_df <- data.frame(
    Feature = names(vip_mean),
    VIP = as.numeric(vip_mean),
    stringsAsFactors = FALSE
) %>%
    arrange(desc(VIP))

write.csv(
    vip_df,
    file.path(outdir, "vip_scores.csv"),
    row.names = FALSE
)

write.csv(
    vip_df %>% filter(VIP > 1),
    file.path(outdir, "vip_gt_1.csv"),
    row.names = FALSE
)


# ============================= Volcano =============================
volcano_df <- NULL

resolve_level <- function(requested, lev) {{
    if (!nzchar(requested)) return(NULL)
    if (requested %in% lev) return(requested)
    hit <- lev[tolower(lev) == tolower(requested)]
    if (length(hit) >= 1) return(hit[[1]])
    NULL
}}

vol_g1 <- NULL
vol_g2 <- NULL
volcano_skip_reason <- NULL

if (nzchar(contrast_g1_req) && nzchar(contrast_g2_req)) {{
    vol_g1 <- resolve_level(contrast_g1_req, levels(Y))
    vol_g2 <- resolve_level(contrast_g2_req, levels(Y))
    if (is.null(vol_g1) || is.null(vol_g2)) {{
        volcano_skip_reason <- paste0(
            "contrast levels not found in ", group_column, ": requested ",
            contrast_g1_req, " vs ", contrast_g2_req,
            "; available=", paste(levels(Y), collapse = ",")
        )
    }} else if (identical(vol_g1, vol_g2)) {{
        volcano_skip_reason <- paste0(
            "contrast groups must differ; got ", vol_g1, " vs ", vol_g2
        )
        vol_g1 <- NULL
        vol_g2 <- NULL
    }}
}} else if (nlevels(Y) == 2) {{
    vol_g1 <- levels(Y)[1]
    vol_g2 <- levels(Y)[2]
}} else if (nlevels(Y) > 2) {{
    volcano_skip_reason <- paste0(
        "Skipped volcano: ", nlevels(Y), " levels in ", group_column,
        ". Pass contrast_group1/contrast_group2 to compare two groups."
    )
}} else {{
    volcano_skip_reason <- paste0(
        "Skipped volcano: fewer than 2 levels in ", group_column
    )
}}

if (!is.null(volcano_skip_reason)) {{
    write(
        volcano_skip_reason,
        file = file.path(outdir, "analysis_warning.txt"),
        append = file.exists(file.path(outdir, "analysis_warning.txt"))
    )
}}

if (!is.null(vol_g1) && !is.null(vol_g2)) {{

    idx1 <- which(as.character(Y) == vol_g1)
    idx2 <- which(as.character(Y) == vol_g2)

    write(
        paste0("volcano_contrast=", vol_g1, " vs ", vol_g2,
               " (log2FC = mean(", vol_g2, ") - mean(", vol_g1, "))"),
        file = file.path(outdir, "analysis_params.txt"),
        append = TRUE
    )

    mean1 <- colMeans(
        X_tmp[idx1, , drop = FALSE],
        na.rm = TRUE
    )

    mean2 <- colMeans(
        X_tmp[idx2, , drop = FALSE],
        na.rm = TRUE
    )

    log2FC <- mean2 - mean1

    pvalues <- apply(
        X_tmp,
        2,
        function(v) {{
            tryCatch(
                t.test(
                    v[idx1],
                    v[idx2]
                )$p.value,
                error = function(e) NA_real_
            )
        }}
    )

    volcano_df <- data.frame(
        Feature = colnames(X_tmp),
        log2FC = log2FC,
        pvalue = pvalues,
        padj = p.adjust(
            pvalues,
            method = "fdr"
        ),
        neglog10p = -log10(pvalues),
        stringsAsFactors = FALSE
    )

    volcano_df$Significant <- with(
        volcano_df,
        !is.na(pvalue) &
        pvalue < pvalue_threshold &
        abs(log2FC) >= log2fc_threshold
    )

    write.csv(
        volcano_df,
        file.path(outdir, "volcano_results.csv"),
        row.names = FALSE
    )

    p <- ggplot(
        volcano_df,
        aes(
            x = log2FC,
            y = neglog10p,
            color = Significant
        )
    ) +
        geom_point(size = 1.5) +
        geom_vline(
            xintercept = c(
                -log2fc_threshold,
                log2fc_threshold
            ),
            linetype = 2
        ) +
        geom_hline(
            yintercept = -log10(pvalue_threshold),
            linetype = 2
        ) +
        theme_bw() +
        ggtitle(paste0("Volcano: ", vol_g2, " vs ", vol_g1))

    ggsave(
        file.path(outdir, "volcano_plot.png"),
        p,
        width = 6,
        height = 5,
        dpi = 300
    )
    try(save_ggplot_plotly_sidecar(p, file.path(outdir, "volcano_plot.png")), silent = TRUE)


    # ============================= Differential Metabolites =============================
    diff_df <- volcano_df %>%
        left_join(
            vip_df,
            by = c("Feature" = "Feature")
        )

    feature_info <- data.frame(
        Feature = feature_df$feature_id,
        mz = feature_df$mz,
        rt = feature_df$rt_med,
        stringsAsFactors = FALSE
    )

    diff_df <- diff_df %>%
        left_join(
            feature_info,
            by = "Feature"
        )

    if (use_fdr) {{

        diff_metabolites <- diff_df %>%
            filter(
                VIP >= vip_threshold,
                abs(log2FC) >= log2fc_threshold,
                padj < padj_threshold
            )

    }} else {{

        diff_metabolites <- diff_df %>%
            filter(
                VIP >= vip_threshold,
                abs(log2FC) >= log2fc_threshold,
                pvalue < pvalue_threshold
            )
    }}

    diff_metabolites <- diff_metabolites %>%
        arrange(
            padj,
            desc(VIP),
            desc(abs(log2FC))
        )

    write.csv(
        diff_metabolites,
        file.path(
            outdir,
            "differential_metabolites.csv"
        ),
        row.names = FALSE
    )

    diff_up <- diff_metabolites %>%
        filter(log2FC > 0)

    diff_down <- diff_metabolites %>%
        filter(log2FC < 0)

    write.csv(
        diff_up,
        file.path(
            outdir,
            "differential_metabolites_up.csv"
        ),
        row.names = FALSE
    )

    write.csv(
        diff_down,
        file.path(
            outdir,
            "differential_metabolites_down.csv"
        ),
        row.names = FALSE
    )

    writeLines(
        paste0(
            "Differential metabolites: ",
            nrow(diff_metabolites)
        ),
        file.path(
            outdir,
            "differential_summary.txt"
        )
    )
}}


# ============================= Heatmap =============================
n_top <- min(
    top_n_heatmap,
    nrow(vip_df)
)

if (n_top > 0) {{

    top_features <- vip_df$Feature[
        seq_len(n_top)
    ]

    heatmap_matrix <- X_tmp[
        ,
        top_features,
        drop = FALSE
    ]

    heatmap_matrix <- t(heatmap_matrix)

    # 空 data.frame 再 [[<- 赋值会因行数不匹配报错；按样本数一次性建表
    annotation_col <- data.frame(
        setNames(list(Y), group_column),
        check.names = FALSE,
        stringsAsFactors = FALSE
    )
    rownames(annotation_col) <- rownames(X_tmp)

    tryCatch(
        {{
            png(
                file.path(
                    outdir,
                    "heatmap_top_vip.png"
                ),
                width = 2400,
                height = 1800,
                res = 300
            )

            pheatmap(
                heatmap_matrix,
                annotation_col = annotation_col,
                scale = "none",
                show_rownames = TRUE,
                show_colnames = FALSE,
                fontsize_row = 8
            )

            dev.off()

            tryCatch(
                write.csv(
                    as.data.frame(heatmap_matrix),
                    file.path(outdir, "heatmap_top_vip_matrix.csv"),
                    quote = TRUE
                ),
                error = function(e) invisible(NULL)
            )

            try(
                save_heatmap_plotly_sidecar(
                    heatmap_matrix,
                    file.path(outdir, "heatmap_top_vip.png"),
                    "Top VIP Heatmap"
                ),
                silent = TRUE
            )
        }},
        error = function(e) {{
            if (dev.cur() > 1) try(dev.off(), silent = TRUE)
            write(
                paste0("Heatmap skipped: ", conditionMessage(e)),
                file = file.path(outdir, "analysis_warning.txt"),
                append = TRUE
            )
        }}
    )
}}


}}


# ============================= Session Info =============================
writeLines(
    capture.output(sessionInfo()),
    file.path(outdir, "sessionInfo.txt")
)
"""

    _r_tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".R", delete=False, encoding="utf-8"
    )
    try:
        _r_tmp.write(r_script)
        r_file = _r_tmp.name
    finally:
        _r_tmp.close()

    try:
        subprocess.run(["Rscript", r_file], capture_output=False)
        ensure_editable_sidecars(
            output_dir,
            title_map={
                "pca_plot.png": "PCA",
                "plsda_plot.png": "PLS-DA",
                "volcano_plot.png": "Volcano Plot",
                "vip_scores.png": "VIP Scores",
                "heatmap_top_vip.png": "Top VIP Heatmap",
            },
        )
        try:
            from web_frontend.backend.plot_edit_service import ensure_default_plot_configs

            ensure_default_plot_configs(output_dir)
        except Exception:
            pass

    finally:
        os.unlink(r_file)




# ========================================================= extract differential features =======================================================



# ========================================================= extract differential features =======================================================
def extract_differential_features_impl(
    differential_csv: str,
    input_mgf: str,
    output_dir: str,
):
    """
    Extract differential metabolite spectra and feature table.

    Parameters
    ----------
    differential_csv : str
        differential_metabolites.csv which is the output of statistical analysis step.

    input_mgf : str
        input MGF file which is the output of data preprocessing step.

    output_dir : str
        directory to save extracted differential features files
    """

    import pandas as pd

    print("\nExtracting differential features...")

    os.makedirs(output_dir, exist_ok=True)


    # ============= read differential metabolites ==================
    diff_df = pd.read_csv(differential_csv)

    if "Feature" not in diff_df.columns:
        raise ValueError(
            "Differential table must contain 'Feature' column"
        )

    target_features = set(
        diff_df["Feature"].astype(str)
    )

    print(
        f"Target differential features: "
        f"{len(target_features)}"
    )


    # ==================== copy feature table =================
    diff_df.to_csv(
        os.path.join(output_dir, "differential_feature_table.csv"),
        index=False
    )


    # ==================== extract MGF spectra ====================
    extracted_blocks = []

    with open(input_mgf, "r") as f:

        current_block = []
        current_title = None
        inside_block = False

        for line in f:

            line_strip = line.strip()

            # BEGIN
            if line_strip == "BEGIN IONS":

                inside_block = True
                current_block = [line]
                current_title = None
                continue

            # END
            if line_strip == "END IONS":

                current_block.append(line)

                if (
                    current_title is not None
                    and current_title in target_features
                ):
                    extracted_blocks.append(
                        "".join(current_block)
                    )

                inside_block = False
                current_block = []
                current_title = None

                continue

            # inside block
            if inside_block:

                current_block.append(line)

                if line_strip.startswith("TITLE="):

                    current_title = (
                        line_strip
                        .replace("TITLE=", "")
                        .strip()
                    )


    # ============================= save mgf =============================
    with open(os.path.join(output_dir, "differential_spectra.mgf"), "w") as f:

        for block in extracted_blocks:

            f.write(block)

            if not block.endswith("\n"):
                f.write("\n")

    print(
        f"✅ Extracted spectra: "
        f"{len(extracted_blocks)}"
    )

    print(
        f"\nOutput files:\n"
        f"MGF: {os.path.join(output_dir, 'differential_spectra.mgf')}\n"
        f"Feature table: {os.path.join(output_dir, 'differential_feature_table.csv')}"
    )




# ============================================================= spectral_annotation =======================================================
# Cosine



# ============================================================= spectral_annotation =======================================================
# Cosine
def spectral_annotation_impl(
    input_dir: str,
    output_dir: str,
    precursor_ppm: float = 5,
    fragment_tol: float = 0.05,
    min_cosine: float = 0.5,
    include_precursor: bool = False,
    use_mona: bool = True,
    use_spectraverse: bool = True
):
    """
    Parameters
    ----------
    input_dir : str
        Path to the directory containing extracted differential features files.
    output_dir : str
        Path to the directory saving annotation results CSV file.
    precursor_ppm : float, default=5
        Precursor ion mass tolerance in ppm.
    fragment_tol : float, default=0.05
        Fragment ion mass tolerance in Da.
    min_cosine : float, default=0.5
        Minimum cosine similarity score required for annotation.
    include_precursor : bool, default=False
        If True, require precursor m/z match (requirePrecursor=TRUE).
        If False, skip precursor requirement for broader matching.
    use_mona : bool, default=True
        If True, also search the MoNA spectral libraries (much larger coverage).
    use_spectraverse : bool, default=True
        If True, also search the spectraverse spectral library (1.3 GB, broad coverage).
    """

    print("\nPerforming spectral library annotation...")

    os.makedirs(output_dir, exist_ok=True)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    gnps_pos_path = os.path.join(base_dir, "../..", "database_file/GNPS/GNPS-NIH-NATURALPRODUCTSLIBRARY_ROUND2_POSITIVE.msp")
    gnps_neg_path = os.path.join(base_dir, "../..", "database_file/GNPS/GNPS-NIH-NATURALPRODUCTSLIBRARY_ROUND2_NEGATIVE.msp")
    mona_pos_path = os.path.join(base_dir, "../..", "database_file/MoNA/LC-MS-MS_Positive_Mode.msp")
    mona_neg_path = os.path.join(base_dir, "../..", "database_file/MoNA/LC-MS-MS_Negative_Mode.msp")
    spectraverse_path = os.path.join(base_dir, "../..", "database_file/spectraverse-1.0.1.mgf")

    req_precursor_str = "TRUE" if include_precursor else "FALSE"
    use_mona_str = "TRUE" if use_mona else "FALSE"
    use_spectraverse_str = "TRUE" if use_spectraverse else "FALSE"
    gnps_pos_path_r = gnps_pos_path.replace(os.sep, '/')
    gnps_neg_path_r = gnps_neg_path.replace(os.sep, '/')
    mona_pos_path_r = mona_pos_path.replace(os.sep, '/')
    mona_neg_path_r = mona_neg_path.replace(os.sep, '/')
    spectraverse_path_r = spectraverse_path.replace(os.sep, '/')

    r_script = f"""
# ============================= packages =============================
library(Spectra)
library(MetaboAnnotation)
library(MsBackendMgf)
library(MsBackendMsp)
library(dplyr)
library(KEGGREST)
library(readr)


# ============================= parameters =============================
mgf_path <- "{os.path.join(input_dir, 'differential_spectra.mgf').replace(os.sep, '/')}"
feat_csv <- "{os.path.join(input_dir, 'differential_feature_table.csv').replace(os.sep, '/')}"

gnps_pos_path <- "{gnps_pos_path_r}"
gnps_neg_path <- "{gnps_neg_path_r}"
mona_pos_path <- "{mona_pos_path_r}"
mona_neg_path <- "{mona_neg_path_r}"
spectraverse_path <- "{spectraverse_path_r}"

out_csv <- "{os.path.join(output_dir, 'differential_feature_table_library_match.csv').replace(os.sep, '/')}"
out_csv_clean <- "{os.path.join(output_dir, 'differential_feature_table_library_match_clean&add.csv').replace(os.sep, '/')}"

prec_ppm <- {precursor_ppm}
frag_tol <- {fragment_tol}
min_cosine <- {min_cosine}
include_precursor <- {req_precursor_str}
use_mona <- {use_mona_str}
use_spectraverse <- {use_spectraverse_str}


# ============================= input validation =============================
if (!file.exists(mgf_path)) {{
    stop("MGF file not found")
}}

if (!file.exists(feat_csv)) {{
    stop("Feature table CSV not found")
}}

if (!file.exists(gnps_pos_path)) {{
    cat("WARNING: GNPS positive library not found, skipping\\n")
}}

if (!file.exists(gnps_neg_path)) {{
    cat("WARNING: GNPS negative library not found, skipping\\n")
}}


# ============================= read query spectra =============================
cat("Reading query spectra...\\n")

query_spectra <- Spectra(
    mgf_path,
    source = MsBackendMgf()
)

if (length(query_spectra) == 0) {{
    stop("No spectra found in MGF file")
}}

cat("Query spectra loaded:", length(query_spectra), "\\n")


# ============================= define matching parameters =============================
match_param <- CompareSpectraParam(
    ppm = prec_ppm,
    tolerance = frag_tol,
    requirePrecursor = include_precursor,
    FUN = MsCoreUtils::ndotproduct
)


# ============================= helper: extract metadata from a library =============================
extract_lib_metadata <- function(lib_spectra, target_idx, lib_name) {{
    meta <- spectraData(lib_spectra)
    colnames_avail <- colnames(meta)

    # --- compound name ---
    name <- rep(NA_character_, length(target_idx))
    if ("TITLE" %in% colnames_avail) {{
        name <- meta$TITLE[target_idx]
    }} else if ("name" %in% colnames_avail) {{
        name <- meta$name[target_idx]
    }} else if ("Name" %in% colnames_avail) {{
        name <- meta$Name[target_idx]
    }} else if ("COMPOUND_NAME" %in% colnames_avail) {{
        name <- meta$COMPOUND_NAME[target_idx]
    }}

    # --- SMILES ---
    smiles <- rep(NA_character_, length(target_idx))
    if ("SMILES" %in% colnames_avail) {{
        smiles <- meta$SMILES[target_idx]
    }} else if ("smiles" %in% colnames_avail) {{
        smiles <- meta$smiles[target_idx]
    }}

    # MoNA: SMILES is embedded in Comments field like "SMILES=O=C(...)"
    if (all(is.na(smiles)) && "Comments" %in% colnames_avail) {{
        comments <- as.character(meta$Comments[target_idx])
        has_smiles <- grepl('SMILES=', comments, fixed = TRUE)
        if (any(has_smiles)) {{
            extracted <- rep(NA_character_, length(comments))
            extracted[has_smiles] <- sub('.*SMILES=([^"]+).*', '\\\\1', comments[has_smiles], perl = TRUE)
            extracted[extracted == "" | extracted == "NA"] <- NA_character_
            smiles <- extracted
        }}
    }}

    # --- precursor mz ---
    prec_mz <- rep(NA_real_, length(target_idx))
    tryCatch({{
        prec_mz <- precursorMz(lib_spectra)[target_idx]
    }}, error = function(e) {{
        # Try PRECURSOR_MZ / PrecursorMZ column
        if ("PRECURSOR_MZ" %in% colnames_avail) {{
            prec_mz <<- as.numeric(meta$PRECURSOR_MZ[target_idx])
        }} else if ("PrecursorMZ" %in% colnames_avail) {{
            prec_mz <<- as.numeric(meta$PrecursorMZ[target_idx])
        }}
    }})

    # --- molecular formula ---
    formula <- rep(NA_character_, length(target_idx))
    if ("formula" %in% colnames_avail) {{
        formula <- meta$formula[target_idx]
    }} else if ("FORMULA" %in% colnames_avail) {{
        formula <- meta$FORMULA[target_idx]
    }} else if ("Formula" %in% colnames_avail) {{
        formula <- meta$Formula[target_idx]
    }}

    list(name = name, smiles = smiles, prec_mz = prec_mz, formula = formula)
}}


# ============================= search one library =============================
search_library <- function(lib_path, backend_type, lib_name) {{
    if (!file.exists(lib_path)) {{
        cat("  Library not found, skipping:", lib_path, "\\n")
        return(data.frame())
    }}

    cat("  Loading:", lib_name, "(", lib_path, ")\\n")

    backend <- if (backend_type == "msp") MsBackendMsp() else MsBackendMgf()
    lib_spectra <- Spectra(lib_path, source = backend)

    cat("    Spectra count:", length(lib_spectra), "\\n")

    if (length(lib_spectra) == 0) {{
        cat("    WARNING: 0 spectra loaded, skipping\\n")
        return(data.frame())
    }}

    res <- matchSpectra(query_spectra, lib_spectra, match_param)
    matches <- MetaboAnnotation::matches(res)

    if (nrow(matches) == 0) {{
        cat("    No matches found\\n")
        return(data.frame())
    }}

    cat("    Matches found:", nrow(matches), "\\n")

    # Extract metadata
    meta_info <- extract_lib_metadata(lib_spectra, matches$target_idx, lib_name)

    matches$compound_name <- meta_info$name
    matches$smiles <- meta_info$smiles
    matches$library_precursor_mz <- meta_info$prec_mz
    matches$formula <- meta_info$formula
    matches$library_source <- lib_name

    return(matches)
}}


# ============================= search all libraries =============================
all_matches <- list()

# 1. GNPS
cat("\\n--- Searching GNPS libraries ---\\n")
if (file.exists(gnps_pos_path)) {{
    gnps_pos <- search_library(gnps_pos_path, "msp", "GNPS_POS")
    if (nrow(gnps_pos) > 0) {{
        gnps_pos$ion_mode <- "POS"
        gnps_pos$target_idx_orig <- gnps_pos$target_idx
        all_matches[[length(all_matches) + 1]] <- gnps_pos
    }}
}}

if (file.exists(gnps_neg_path)) {{
    gnps_neg <- search_library(gnps_neg_path, "msp", "GNPS_NEG")
    if (nrow(gnps_neg) > 0) {{
        gnps_neg$ion_mode <- "NEG"
        gnps_neg$target_idx_orig <- gnps_neg$target_idx
        all_matches[[length(all_matches) + 1]] <- gnps_neg
    }}
}}

# 2. MoNA
if (use_mona) {{
    cat("\\n--- Searching MoNA libraries ---\\n")
    if (file.exists(mona_pos_path)) {{
        mona_pos <- search_library(mona_pos_path, "msp", "MoNA_POS")
        if (nrow(mona_pos) > 0) {{
            mona_pos$ion_mode <- "POS"
            mona_pos$target_idx_orig <- mona_pos$target_idx
            all_matches[[length(all_matches) + 1]] <- mona_pos
        }}
    }}
    if (file.exists(mona_neg_path)) {{
        mona_neg <- search_library(mona_neg_path, "msp", "MoNA_NEG")
        if (nrow(mona_neg) > 0) {{
            mona_neg$ion_mode <- "NEG"
            mona_neg$target_idx_orig <- mona_neg$target_idx
            all_matches[[length(all_matches) + 1]] <- mona_neg
        }}
    }}
}}

# 3. Spectraverse (MGF format)
if (use_spectraverse) {{
    cat("\\n--- Searching Spectraverse library ---\\n")
    if (file.exists(spectraverse_path)) {{
        sv <- search_library(spectraverse_path, "mgf", "Spectraverse")
        if (nrow(sv) > 0) {{
            # Spectraverse ion mode detection: check IONMODE in metadata
            sv$ion_mode <- "POS"  # default; could check metadata for "POS"/"NEG"
            sv$target_idx_orig <- sv$target_idx
            all_matches[[length(all_matches) + 1]] <- sv
        }}
    }}
}}


# ============================= merge all library results =============================
cat("\\n--- Merging results from all libraries ---\\n")

if (length(all_matches) == 0) {{
    anno_total <- data.frame()
    cat("WARNING: No matches found in any library!\\n")
}} else {{
    # Combine all matches
    anno_total <- bind_rows(all_matches)

    # Filter by min_cosine
    anno_total <- anno_total[anno_total$score >= min_cosine, ]

    cat("Total raw matches (all libraries, min_cosine >=", min_cosine, "):", nrow(anno_total), "\\n")

    if (nrow(anno_total) > 0) {{
        # Keep best match per query (highest cosine score)
        anno_total <- anno_total[
            order(anno_total$query_id, -anno_total$score),
        ]
        anno_total <- anno_total[!duplicated(anno_total$query_id), ]

        cat("Best matches per query (deduplicated):", nrow(anno_total), "\\n")
    }} else {{
        anno_total <- data.frame()
    }}
}}


# ============================= read feature table =============================
feat_table <- read.csv(
    feat_csv,
    stringsAsFactors = FALSE,
    check.names = FALSE
)

if (!"Feature" %in% colnames(feat_table)) {{
    stop("Feature column not found in feature table")
}}

# Initialize annotation fields
feat_table$compound_name <- NA
feat_table$cosine_score <- NA
feat_table$ion_mode_match <- NA
feat_table$library_precursor_mz <- NA
feat_table$smiles <- NA
feat_table$formula <- NA
feat_table$library_source <- NA


# ============================= merge annotations into feature table =============================
if (nrow(anno_total) > 0) {{
    for (i in seq_len(nrow(anno_total))) {{
        idx <- anno_total$query_idx[i]
        if (length(idx) > 0) {{
            feat_table$compound_name[idx]    <- anno_total$compound_name[i]
            feat_table$cosine_score[idx]     <- round(anno_total$score[i], 3)
            feat_table$ion_mode_match[idx]   <- anno_total$ion_mode[i]
            feat_table$library_precursor_mz[idx] <- anno_total$library_precursor_mz[i]
            feat_table$smiles[idx]           <- anno_total$smiles[i]
            feat_table$formula[idx]          <- anno_total$formula[i]
            feat_table$library_source[idx]   <- anno_total$library_source[i]
        }}
    }}
}}


# ============================= output raw match table =============================
write.csv(
    feat_table,
    out_csv,
    row.names = FALSE
)

n_annotated <- sum(!is.na(feat_table$compound_name))
n_smiles <- sum(!is.na(feat_table$smiles))
cat("\\nSpectral annotation completed!\\n")
cat("Annotated feature table written to:", out_csv, "\\n")
cat("Successfully annotated compounds:", n_annotated, "of", nrow(feat_table), "\\n")
cat("Compounds with SMILES:", n_smiles, "\\n")

if (n_annotated > 0) {{
    lib_counts <- table(feat_table$library_source[!is.na(feat_table$compound_name)])
    cat("Matches by library:\\n")
    for (lib_name in names(lib_counts)) {{
        cat("  ", lib_name, ":", lib_counts[lib_name], "\\n")
    }}
}}


# ============================= KEGG ID annotation via KEGGREST =============================
# Include ALL features in the clean output (not just spectrally matched ones),
# so downstream tools can supplement KEGG IDs for unmatched features via mass lookup.
feat_table$cid <- NA
feat_table$inchikey <- NA
feat_table$iupac_name <- NA
feat_table$kegg_id <- NA

df_annotated <- feat_table %>% filter(!is.na(compound_name))

if (nrow(df_annotated) > 0) {{
    cat("\\n--- KEGG ID lookup via KEGG REST API ---\\n")

    for (i in seq_len(nrow(df_annotated))) {{
        comp_name <- df_annotated$compound_name[i]
        smi <- df_annotated$smiles[i]
        formula <- df_annotated$formula[i]

        kegg_id <- NA_character_

        # Try 1: molecular formula search (most reliable)
        if (is.na(kegg_id) && !is.na(formula) && nchar(formula) >= 2) {{
            tryCatch({{
                kegg_result <- keggFind("compound", formula, "formula")
                if (length(kegg_result) > 0) {{
                    kegg_id <<- names(kegg_result)[1]
                    cat("  KEGG match (formula):", formula, "->", kegg_id, "\\n")
                }}
            }}, error = function(e) {{ }})
        }}

        # Try 2: name search
        if (is.na(kegg_id) && !is.na(comp_name)) {{
            # Extract short name from GNPS "DB_ID!chemical_name" format
            short_name <- comp_name
            if (grepl("!", comp_name, fixed=TRUE)) {{
                short_name <- strsplit(comp_name, "!")[[1]][2]
            }}

            # Remove bracketed notes
            clean_name <- gsub("\\\\[IIN-based on:.*?\\\\]", "", short_name)
            clean_name <- gsub("\\\\[.*?\\\\]", "", clean_name)
            clean_name <- trimws(clean_name)

            tryCatch({{
                kegg_result <- keggFind("compound", clean_name)
                if (length(kegg_result) > 0) {{
                    kegg_id <<- names(kegg_result)[1]
                    cat("  KEGG match (full name):", clean_name, "->", kegg_id, "\\n")
                }}
            }}, error = function(e) {{ }})

            # Try 2b: first part of name (before first '(' or '[')
            if (is.na(kegg_id)) {{
                short_fragment <- trimws(strsplit(clean_name, "[\\\\(\\\\[]")[[1]][1])
                if (nchar(short_fragment) >= 5) {{
                    tryCatch({{
                        kegg_result <- keggFind("compound", short_fragment)
                        if (length(kegg_result) > 0) {{
                            kegg_id <<- names(kegg_result)[1]
                            cat("  KEGG match (short name):", short_fragment, "->", kegg_id, "\\n")
                        }}
                    }}, error = function(e) {{ }})
                }}
            }}

            if (is.na(kegg_id)) {{
                cat("  KEGG NOT FOUND:", clean_name, "\\n")
            }}
        }}

        # Store results
        df_annotated$kegg_id[i] <- kegg_id
    }}

    # Merge KEGG annotations back into full feat_table
    if (nrow(df_annotated) > 0) {{
        for (i in seq_len(nrow(df_annotated))) {{
            match_name <- df_annotated$compound_name[i]
            if (!is.na(match_name)) {{
                feat_rows <- which(feat_table$compound_name == match_name)
                if (length(feat_rows) > 0) {{
                    feat_table$kegg_id[feat_rows[1]] <- df_annotated$kegg_id[i]
                }}
            }}
        }}
    }}
}}  # end if(nrow(df_annotated) > 0)

# ============================ Mass-based KEGG lookup for unmatched features ============================
    cat("\\n--- Mass-based KEGG lookup for unmatched features ---\\n")
    n_mass_found <- 0
    for (i in seq_len(nrow(feat_table))) {{
        if (is.na(feat_table$kegg_id[i])) {{
            mz_val <- feat_table$mz[i]
            if (!is.na(mz_val) && is.numeric(mz_val) && mz_val > 50) {{
                # Assume [M+H]+ adduct, calculate neutral mass
                neutral_mass <- mz_val - 1.0078
                tryCatch({{
                    mass_str <- as.character(round(neutral_mass, 4))
                    kegg_result <- keggFind("compound", mass_str, "exact_mass")
                    if (length(kegg_result) > 0) {{
                        feat_table$kegg_id[i] <- names(kegg_result)[1]
                        n_mass_found <- n_mass_found + 1
                    }}
                }}, error = function(e) {{ }})
            }}
        }}
    }}
    cat("  Mass-based KEGG IDs found:", n_mass_found, "\\n")

    # Build output table (ALL features, not just matched ones)
    df_merged <- feat_table

    write.csv(
        df_merged,
        out_csv_clean,
        row.names = FALSE
    )

    n_kegg <- sum(!is.na(df_merged$kegg_id))
    n_matched <- sum(!is.na(df_merged$compound_name))
    cat("\\nTotal KEGG ID annotated:", n_kegg, "of", nrow(df_merged), "features (", n_matched, "spectrally matched)\\n")

    cat("Clean annotated table written to:", out_csv_clean, "\\n")
"""

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.R',
        delete=False
    ) as f:
        f.write(r_script)
        r_file = f.name

    try:
        result = subprocess.run(
            ['Rscript', r_file],
            capture_output=True,
            encoding='utf-8'
        )
        if result.returncode != 0:
            print(f"\n[R ERROR] Spectral annotation failed (exit code {result.returncode}):")
            print(result.stderr)
            print(result.stdout)
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
        # Print R stdout for diagnostics
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    print(f"  [R] {line.strip()}")

    finally:
        os.unlink(r_file)




# ============================================================ sirius unkowns annotation =======================================================
# SIRIUS



# ============================================================ sirius unkowns annotation =======================================================
# SIRIUS
def sirius_unknowns_annotation_impl(
    input_dir: str,
    output_dir: str,
    profile: str = "orbitrap",
    database: str = "pubchem"
):
    """
    Perform SIRIUS annotation and merge annotation results back into feature table.

    Parameters
    ----------
    input_dir : str
        Directory containing:
            - differential_spectra.mgf
            - differential_feature_table.csv

    output_dir : str
        Directory for SIRIUS outputs and merged annotation table.

    profile : str
        Instrument profile. e.g. orbitrap, qtof

    database : str
        Structure database.
    """

    print("\nPerforming SIRIUS annotation for unknown compounds...")

    # =========================
    # Input paths
    # =========================
    mgf_path = os.path.join(input_dir, "differential_spectra.mgf")
    feat_csv = os.path.join(input_dir, "differential_feature_table.csv")

    if not os.path.exists(mgf_path):
        raise FileNotFoundError(f"MGF file not found: {mgf_path}")

    if not os.path.exists(feat_csv):
        raise FileNotFoundError(f"Feature table not found: {feat_csv}")

    # =========================
    # Output paths
    # =========================
    os.makedirs(output_dir, exist_ok=True)
    
    # sirius不会覆盖既往结果，紧跟清空输出目录
    for f in os.listdir(output_dir):
        fp = os.path.join(output_dir, f)
        if os.path.isfile(fp):
            os.remove(fp)
        else:
            shutil.rmtree(fp)

    project_dir = os.path.join(output_dir, "sirius_project")
    summary_dir = os.path.join(output_dir, "sirius_summary")

    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(summary_dir, exist_ok=True)

    # =========================
    # Run SIRIUS
    # =========================
    cmd = [
        "sirius",
        "--input", mgf_path,
        "--project", project_dir,

        "formula",  
        "-p", profile,

        "fingerprint",  # 预测分子指纹
        "structure",  # 识别分子结构
        "--database", database,

        "write-summaries",
        "--output", summary_dir
    ]
    subprocess.run(cmd, check=True)



# ============================================= KEGG ID lookup helpers ==================================================



# ============================================= KEGG ID lookup helpers ==================================================

def _lookup_kegg_by_name(compound_name: str, timeout: float = 10.0) -> Optional[str]:
    """
    Look up a KEGG compound ID by chemical name via the KEGG REST API.

    Parameters
    ----------
    compound_name : str
        Chemical name to search for.
    timeout : float
        HTTP request timeout in seconds.

    Returns
    -------
    str or None
        KEGG compound ID (e.g. "C00031") if found, else None.
    """
    import urllib.request
    import urllib.error

    # Clean the name for URL
    encoded = urllib.parse.quote(compound_name.strip())
    url = f"https://rest.kegg.jp/find/compound/{encoded}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode('utf-8').strip()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"    [KEGG API] Connection error for '{compound_name[:60]}': {e}")
        return None

    if not text:
        return None

    # Response format: "C00031\tD-Glucose; ..."
    first_line = text.split('\n')[0]
    parts = first_line.split('\t')
    if len(parts) >= 1:
        cpd_id = parts[0].strip()
        if cpd_id.startswith('C') and cpd_id[1:].isdigit():
            return cpd_id
    return None


def _lookup_kegg_by_mass(neutral_mass: float, ppm: float = 10.0, timeout: float = 10.0) -> List[str]:
    """
    Look up KEGG compound IDs by exact neutral mass via KEGG REST API.

    Parameters
    ----------
    neutral_mass : float
        Neutral monoisotopic mass to search for.
    ppm : float
        Mass tolerance in ppm.
    timeout : float
        HTTP request timeout in seconds.

    Returns
    -------
    List[str]
        KEGG compound IDs matching the mass within tolerance.
    """
    import urllib.request
    import urllib.error

    url = f"https://rest.kegg.jp/find/compound/{neutral_mass}/exact_mass"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode('utf-8').strip()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"    [KEGG API] Connection error for mass {neutral_mass:.4f}: {e}")
        return []

    if not text:
        return []

    # Response format: "C00031\tC6H12O6" (one per line)
    results = []
    for line in text.split('\n'):
        parts = line.strip().split('\t')
        if len(parts) >= 1 and parts[0].startswith('C') and parts[0][1:].isdigit():
            results.append(parts[0])
    return results


def _supplement_kegg_ids(input_csv: str, mzannotation_dir: str = None) -> str:
    """
    Supplement KEGG compound IDs in the spectral annotation clean output CSV.

    For rows where kegg_id is NA, attempts to look up KEGG IDs via:
    1. Molecular formula search (if formula column is available)
    2. Compound name search on KEGG REST API
    3. m/z → neutral mass → KEGG exact mass lookup (for all unmatched features)

    Parameters
    ----------
    input_csv : str
        Path to differential_feature_table_library_match_clean&add.csv
    mzannotation_dir : str, optional
        Path to mzAnnotation output directory for supplementary annotations.

    Returns
    -------
    str
        Path to the (possibly updated) CSV file. If no changes were needed,
        returns the original path. If changes were made, writes a temp file.
    """
    import re
    import urllib.request
    import urllib.error

    if not os.path.exists(input_csv):
        print(f"  [KEGG supplement] Input CSV not found: {input_csv}")
        return input_csv

    df = pd.read_csv(input_csv)
    if 'kegg_id' not in df.columns:
        print("  [KEGG supplement] No 'kegg_id' column in input CSV, skipping")
        return input_csv

    # Count rows needing supplementation
    na_mask = df['kegg_id'].isna() | (df['kegg_id'].astype(str).str.strip() == '')
    n_na = na_mask.sum()
    if n_na == 0:
        print("  [KEGG supplement] All rows already have KEGG IDs, skipping")
        return input_csv

    print(f"  [KEGG supplement] {n_na} rows need KEGG ID. Looking up via KEGG REST API...")

    n_found = 0
    for idx in df[na_mask].index:
        row = df.loc[idx]
        kegg_id = None

        # --- Strategy 1: molecular formula search ---
        formula = row.get('formula', None)
        if kegg_id is None and not pd.isna(formula) and str(formula).strip() not in ('', 'NA'):
            formula_str = str(formula).strip()
            try:
                encoded = urllib.parse.quote(formula_str)
                url = f"https://rest.kegg.jp/find/compound/{encoded}/formula"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    text = resp.read().decode('utf-8').strip()
                if text:
                    first_line = text.split('\n')[0]
                    parts = first_line.split('\t')
                    if len(parts) >= 1 and parts[0].startswith('C') and parts[0][1:].isdigit():
                        kegg_id = parts[0]
                        print(f"    [formula] {formula_str} → {kegg_id}")
            except Exception:
                pass

        # --- Strategy 2: compound name search ---
        if kegg_id is None:
            compound_name = row.get('compound_name', None)
            if not pd.isna(compound_name) and str(compound_name).strip() not in ('', 'NA'):
                name = str(compound_name).strip()
                if '!' in name:
                    name = name.split('!', 1)[1]
                name = re.sub(r'\[.*?\]', '', name).strip()
                name = re.sub(r'^[A-Za-z -]+based on:\s*', '', name).strip()

                if len(name) >= 3:
                    kegg_id = _lookup_kegg_by_name(name)
                    if kegg_id is None:
                        short = name.split('(')[0].split('[')[0].strip()
                        if short != name and len(short) >= 5:
                            kegg_id = _lookup_kegg_by_name(short)
                    if kegg_id:
                        print(f"    [name] {name[:50]}... → {kegg_id}")

        # --- Strategy 3: m/z → neutral mass → KEGG exact mass lookup ---
        if kegg_id is None:
            mz_val = row.get('mz', None)
            if not pd.isna(mz_val) and mz_val is not None:
                try:
                    mz_f = float(mz_val)
                    neutral_mass = mz_f - 1.0078
                    if neutral_mass > 50:
                        candidates = _lookup_kegg_by_mass(neutral_mass, ppm=20)
                        if candidates:
                            kegg_id = candidates[0]
                            print(f"    [mass] m/z={mz_f:.4f} → {kegg_id}")
                except (ValueError, TypeError):
                    pass
                except Exception:
                    pass  # network errors are expected, handled silently

        if kegg_id is not None:
            df.at[idx, 'kegg_id'] = kegg_id
            n_found += 1

    print(f"  [KEGG supplement] Found KEGG IDs for {n_found}/{n_na} unannotated rows")

    if n_found > 0:
        # Write to a temp file so the original is preserved
        import tempfile as _tempfile
        with _tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False, prefix='kegg_supplemented_'
        ) as f:
            df.to_csv(f.name, index=False)
            supplemented_path = f.name
        print(f"  [KEGG supplement] Supplemented CSV written to: {supplemented_path}")
        return supplemented_path

    return input_csv


# ============================================= pathway enrichment analysis ==================================================
# KEGG



# ============================================= pathway enrichment analysis ==================================================
# KEGG
def kegg_compound_enrich_impl(
    input_dir: str,
    output_dir: str,
    pvalue_cutoff: float = 0.05,
    padj_method: str = "BH",
    qvalue_cutoff: float = 0.1,
    min_gs: int = 3,
    max_gs: int = 500,
    top_n: int = 15,
    mzannotation_dir: str = None
) -> None:
    """
    KEGG compound pathway enrichment analysis (ORA style)
    based on compound → pathway mapping (NOT gene-based).

    Parameters
    ----------
    mzannotation_dir : str, optional
        Path to mzAnnotation output directory. If provided, mzAnnotation
        annotation hypotheses are used as a supplementary source of KEGG
        compound IDs when spectral library matches have no KEGG IDs.
    """

    print("\nPerforming KEGG compound pathway enrichment analysis...")

    input_file = os.path.join(input_dir, "differential_feature_table_library_match_clean&add.csv")

    # --- Supplement KEGG IDs from Python level ---
    input_file = _supplement_kegg_ids(input_file, mzannotation_dir)

    os.makedirs(output_dir, exist_ok=True)
    _r_plotly_helpers = _r_plotly_export_path().replace(os.sep, "/")
    enrich_table_out = os.path.join(output_dir, "kegg_compound_enrich.csv")
    bubble_plot_out = os.path.join(output_dir, "kegg_compound_bubble.png")
    dotplot_out = os.path.join(output_dir, "kegg_compound_dotplot.png")
    barplot_out = os.path.join(output_dir, "kegg_compound_barplot.png")

    compound_pathway_path = str(PROJECT_ROOT / "database_file" / "compound_pathway.tsv")

    r_script = f"""
library(clusterProfiler)
library(ggplot2)
library(KEGGREST)
library(dplyr)
library(enrichplot)

try(source("{_r_plotly_helpers}", local = FALSE, encoding = "UTF-8"), silent = TRUE)

compound_pathway_path <- "{compound_pathway_path.replace(os.sep, '/')}"

# 1. Read input metabolites
sig_met <- read.csv("{input_file}", check.names = FALSE)
compound_list <- unique(
    sig_met$kegg_id[
        !is.na(sig_met$kegg_id) &
        sig_met$kegg_id != ""
    ]
)

# 2. Build KEGG compound-pathway mapping
cpd2path <- read.table(
    compound_pathway_path,
    sep = "\t",
    header = FALSE,
    stringsAsFactors = FALSE,
    fill = TRUE,
    quote = "",
    comment.char = ""
)
cpd2path <- cpd2path[,1:2]
colnames(cpd2path) <- c("compound", "pathway")

term2gene <- data.frame(
    pathway = sub("path:", "", cpd2path$pathway),
    compound = sub("cpd:", "", cpd2path$compound)
)

# 3. ORA enrichment
enrich_res <- enricher(
    gene = compound_list,
    TERM2GENE = term2gene,
    pvalueCutoff = {pvalue_cutoff},
    pAdjustMethod = "{padj_method}",
    qvalueCutoff = {qvalue_cutoff},
    minGSSize = {min_gs},
    maxGSSize = {max_gs}
)
enrich_df <- as.data.frame(enrich_res)
write.csv(enrich_df, "{enrich_table_out}", row.names = FALSE)

if (nrow(enrich_df) > 0) {{

    # 4. Bubble plot
    plot_data <- enrich_df %>% head({top_n})
    p <- ggplot(plot_data, aes(
        x = Count,
        y = reorder(Description, -p.adjust),
        size = Count,
        color = -log10(p.adjust)
    )) +
    geom_point(alpha = 0.8) +
    scale_color_gradient(low = "blue", high = "red") +
    labs(
        x = "Number of Compounds",
        y = "Pathway",
        title = "KEGG Compound Pathway Enrichment",
        color = "-log10(FDR)",
        size = "Count"
    ) +
    theme_minimal()
    ggsave("{bubble_plot_out}", plot = p, width = 12, height = 8, dpi = 300)
    try(save_ggplot_plotly_sidecar(p, "{bubble_plot_out}"), silent = TRUE)

    # 5. clusterProfiler dotplot
    p_dot <- dotplot(
        enrich_res,
        showCategory = {top_n},
        font.size = 12,
        title = "KEGG Compound Enrichment Dotplot"
    )

    ggsave(
        "{dotplot_out}",
        plot = p_dot,
        width = 12,
        height = 8,
        dpi = 300
    )
    try(save_ggplot_plotly_sidecar(p_dot, "{dotplot_out}"), silent = TRUE)

    # 6. clusterProfiler barplot
    p_bar <- barplot(
        enrich_res,
        showCategory = {top_n},
        font.size = 12,
        title = "KEGG Compound Enrichment Barplot"
    )

    ggsave(
        "{barplot_out}",
        plot = p_bar,
        width = 12,
        height = 8,
        dpi = 300
    )
    try(save_ggplot_plotly_sidecar(p_bar, "{barplot_out}"), silent = TRUE)
}}
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(["Rscript", r_file], check=True, capture_output=True)
    finally:
        os.unlink(r_file)

    # Frontend editable / plotly sidecars for KEGG plots (incl. new dot/bar plots)
    for png_path, title in (
        (bubble_plot_out, "KEGG Compound Pathway Enrichment"),
        (dotplot_out, "KEGG Compound Enrichment Dotplot"),
        (barplot_out, "KEGG Compound Enrichment Barplot"),
    ):
        if os.path.isfile(png_path):
            save_editable_metadata(png_path, title=title)
    ensure_editable_sidecars(
        output_dir,
        title_map={
            "kegg_compound_bubble.png": "KEGG Compound Pathway Enrichment",
            "kegg_compound_dotplot.png": "KEGG Compound Enrichment Dotplot",
            "kegg_compound_barplot.png": "KEGG Compound Enrichment Barplot",
        },
    )

