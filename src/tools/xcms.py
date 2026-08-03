import os
import shutil
import subprocess
import tempfile
import glob
import pandas as pd
from typing import Optional, List, Tuple


# ===================== Rscript resolution =====================
def _find_rscript():
    """Find the Rscript binary on the system.

    Searches common conda envs and system PATH. Raises FileNotFoundError
    if no Rscript is found.
    """
    # 1) check explicit env paths (most reliable)
    explicit_paths = [
        os.path.expanduser("~/anaconda/envs/MOA/bin/Rscript"),
        os.path.expanduser("~/anaconda/envs/MelonnPan/bin/Rscript"),
        os.path.expanduser("~/anaconda/bin/Rscript"),
        os.path.expanduser("~/miniconda3/bin/Rscript"),
        "/home/luxiang/anaconda/envs/MOA/bin/Rscript",
    ]
    for p in explicit_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p

    # 2) check PATH via shutil
    found = shutil.which("Rscript")
    if found:
        return found

    # 3) desperate search in common prefixes
    search_roots = [
        os.path.expanduser("~/anaconda"),
        os.path.expanduser("~/miniconda3"),
        "/home/luxiang/anaconda",
        "/home/lizhengyan/miniconda3",
    ]
    for root in search_roots:
        for dirpath, _dirnames, filenames in os.walk(root):
            if "Rscript" in filenames:
                candidate = os.path.join(dirpath, "Rscript")
                if os.access(candidate, os.X_OK):
                    return candidate
            if dirpath.count(os.sep) - root.count(os.sep) > 3:
                # don't recurse too deep
                _dirnames.clear()

    raise FileNotFoundError(
        "Rscript not found. Please install R and required packages: "
        "conda install -c conda-forge r-base r-clusterprofiler r-dose r-pathview r-ggplot2"
    )


# cached Rscript path (resolved once at first use)
_RSCRIPT_PATH = None


def _get_rscript():
    """Return cached Rscript path, resolving on first call."""
    global _RSCRIPT_PATH
    if _RSCRIPT_PATH is None:
        _RSCRIPT_PATH = _find_rscript()
    return _RSCRIPT_PATH




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

# Register multicore backend — findChromPeaks uses bpparam() at call time.
register(MulticoreParam(workers = n_cores))
cwp <- CentWaveParam(
    ppm = ppm,
    peakwidth = peakwidth,
    snthresh = snthresh,
    prefilter = prefilter,
    mzCenterFun = "wMean",
    integrate = 1
)
xdata <- findChromPeaks(ms1_data, param = cwp)


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
            [_get_rscript(), r_file],
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
def feature_filtering_and_missing_value_imputation_KNN_impl(
    input_dir: str,
    output_dir: str,
    min_presence: float = 0.8,  # filtering (80% rule: keep features present in ≥80% of samples)
    min_intensity: float = 1000.0,  # filtering (minimum mean integrated peak area)
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
        Minimum fraction of non-missing samples required (default 0.8, i.e. the
        "80% rule": keep features present in at least 80% of samples).

    min_intensity : float
        Minimum mean integrated peak area threshold (default 1000.0).  Features
        whose mean intensity across samples falls below this value are discarded
        as noise.  This should be tuned to the instrument; 0 disables the filter.

    n_neighbors : int
        Number of neighbors for KNN imputation (default 5).
    """

    print("\nFiltering features and performing KNN missing value imputation...")

    os.makedirs(output_dir, exist_ok=True)
    summary_txt = os.path.join(output_dir, "feature_filtering_and_missing_value_imputation_summary.txt")

    import pandas as pd
    import numpy as np

    # ============================= read table =============================
    # Auto-detect input file: try Stage 3 outputs first, then fall back to
    # Stage 2 XCMS output.
    #
    # Priority order is intentional:
    #   1. feature_table_redundancy_filtered.csv — pipeline combined output
    #      (CAMERA + mzAnnotation + RAMClust). Must be checked FIRST to
    #      prevent camera/feature_table_filtered.csv (CAMERA-only partial
    #      result) from shadowing the full combined result.
    #   2. feature_table_filtered.csv — standalone CAMERA output
    #   3. camera/feature_table_filtered.csv — CAMERA output in pipeline
    #      subdirectory (fallback when combined result is absent).
    #   4-5. RAMClust outputs (compound-level intensity matrix).
    #   6. feature_table.csv — XCMS peak detection output (no Stage 3).
    input_candidates = [
        "feature_table_redundancy_filtered.csv",           # Stage 3 pipeline combined
        "feature_table_filtered.csv",                     # Stage 3 CAMERA standalone
        "camera/feature_table_filtered.csv",              # Stage 3 CAMERA subdir
        "ramclust_compound_intensities.csv",              # Stage 3 RAMClust standalone
        "ramclust/ramclust_compound_intensities.csv",     # Stage 3 RAMClust subdir
        "feature_table.csv",                              # Stage 1 XCMS fallback
    ]
    input_file = None
    for candidate in input_candidates:
        candidate_path = os.path.join(input_dir, candidate)
        if os.path.isfile(candidate_path):
            input_file = candidate_path
            break
    if input_file is None:
        raise FileNotFoundError(
            f"No input file found in {input_dir}. Tried: {input_candidates}"
        )
    print(f"  Reading input from: {input_file}")
    df = pd.read_csv(input_file)

    # ——— Detect and normalize input format ———
    if "compound" in df.columns:
        # RAMClust format: compound, feature_table_SAMPLE, ...
        # → normalize to XCMS format for downstream Stage 5 compatibility
        df = df.rename(columns={"compound": "feature_id"})
        # Strip 'feature_table_' prefix so sample names match metadata.csv
        rename_map = {}
        for c in df.columns:
            if c.startswith("feature_table_"):
                rename_map[c] = c[len("feature_table_"):]
        if rename_map:
            df = df.rename(columns=rename_map)
            print(f"  Stripped 'feature_table_' prefix from {len(rename_map)} sample columns")
        # Compound-level data lacks per-feature mz/rt — try to recover from
        # ramclust_compound_spectra.csv (written by RAMClust alongside the
        # intensities CSV in the same directory). This file carries mz_med,
        # rt_med, main_peak_mz, and main_peak_rt for every compound.
        if "mz" not in df.columns or "rt_med" not in df.columns:
            spectra_path = os.path.join(input_dir, "ramclust_compound_spectra.csv")
            if os.path.isfile(spectra_path):
                spec_df = pd.read_csv(spectra_path)
                # Prefer main_peak (best representative ion for the compound);
                # fall back to cluster median when main_peak is absent.
                mz_col = "main_peak_mz" if "main_peak_mz" in spec_df.columns else "mz_med"
                rt_col = "main_peak_rt" if "main_peak_rt" in spec_df.columns else "rt_med"
                merge_df = spec_df[["compound", mz_col, rt_col]].rename(
                    columns={mz_col: "mz", rt_col: "rt_med", "compound": "feature_id"}
                )
                df = df.merge(merge_df, on="feature_id", how="left")
                print(f"  Merged mz/rt from ramclust_compound_spectra.csv "
                      f"({len(merge_df)} compounds)")
            else:
                # ramclust_compound_spectra.csv not available — try to recover
                # mz/rt from XCMS feature table via ramclust_clusters.csv mapping.
                clusters_path = os.path.join(input_dir, "ramclust_clusters.csv")
                feature_table_path = os.path.join(input_dir, "feature_table.csv")
                if os.path.isfile(clusters_path) and os.path.isfile(feature_table_path):
                    clusters_df = pd.read_csv(clusters_path)
                    ft_df = pd.read_csv(feature_table_path)
                    if ("feature_id" in clusters_df.columns and "cluster" in clusters_df.columns
                            and "feature_id" in ft_df.columns
                            and "mz" in ft_df.columns and "rt_med" in ft_df.columns):
                        # Map cluster → median mz/rt via XCMS feature IDs
                        xcms_info = ft_df[["feature_id", "mz", "rt_med"]].copy()
                        xcms_info = xcms_info.merge(
                            clusters_df[["feature_id", "cluster"]],
                            on="feature_id", how="inner"
                        )
                        # Compound IDs use Cxxxx format
                        xcms_info["compound_id"] = xcms_info["cluster"].apply(
                            lambda c: f"C{int(c):04d}"
                        )
                        # Aggregate: median mz/rt per compound (more robust than mean)
                        agg_mz = xcms_info.groupby("compound_id")["mz"].median()
                        agg_rt = xcms_info.groupby("compound_id")["rt_med"].median()
                        merge_df = pd.DataFrame({
                            "feature_id": agg_mz.index,
                            "mz": agg_mz.values,
                            "rt_med": agg_rt.values
                        })
                        df = df.merge(merge_df, on="feature_id", how="left")
                        print(f"  Recovered mz/rt from XCMS feature_table via "
                              f"ramclust_clusters.csv mapping "
                              f"({len(merge_df)} compounds)")
                    else:
                        print("  WARNING: ramclust_clusters.csv or feature_table.csv "
                              "missing required columns; mz/rt set to 0")
                else:
                    print("  WARNING: ramclust_compound_spectra.csv, "
                          "ramclust_clusters.csv, and feature_table.csv not found; "
                          "mz/rt set to 0 — mass-based KEGG lookup will be disabled")
            # Fill any remaining NaN mz/rt with 0.0
            # (e.g. spectra file or clusters file had missing rows).
            if "mz" not in df.columns:
                df["mz"] = 0.0
            else:
                df["mz"] = df["mz"].fillna(0.0)
            if "rt_med" not in df.columns:
                df["rt_med"] = 0.0
            else:
                df["rt_med"] = df["rt_med"].fillna(0.0)
        required_cols = ["feature_id", "mz", "rt_med"]
    elif "feature_id" in df.columns:
        # XCMS format: already has feature_id, mz, rt_med — use as-is
        required_cols = ["feature_id", "mz", "rt_med"]
    else:
        raise ValueError(
            f"Unknown input format. Expected 'compound' or 'feature_id' column. "
            f"Found columns: {list(df.columns)}"
        )

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

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
    # Count missing values before imputation
    missing_before = int(df[sample_cols].isna().sum().sum())

    from sklearn.impute import KNNImputer

    imputer = KNNImputer(
        n_neighbors=n_neighbors
    )

    df[sample_cols] = imputer.fit_transform(
        df[sample_cols]
    )

    # Count missing values after imputation
    missing_after = int(df[sample_cols].isna().sum().sum())
    missing_imputed = missing_before - missing_after

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
        f"Missing values before imputation: {missing_before}",
        f"Missing values after imputation: {missing_after}",
        f"Missing values imputed: {missing_imputed}",
        f"Imputation method: KNN",
    ]
    if missing_before == 0:
        summary_lines.append("NOTE: Input data has no missing values — filtering and imputation are no-ops. This is normal for RAMClust compound-level output.")
    summary_lines.append(f"Final output: {os.path.join(output_dir, 'feature_table_filtered_imputed.csv')}")

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
    use_fdr: bool = True
):
    """
    Statistical analysis for metabolomics feature table.

    Parameters
    ----------
    input_dir : str
        Path to the input directory containing the feature table after filtering and imputation.

    output_dir : str
        Directory to save the statistical analysis results.

    Input feature table format:
    feature_id,mz,rt_med,sample1,sample2,...

    metadata.csv format:
    Sample,Group
    """

    print("\nPerforming statistical analysis using mixOmics...")

    os.makedirs(output_dir, exist_ok=True)

    r_script = f"""
# ============================= packages =============================
library(readr)
library(dplyr)
library(tibble)
library(ggplot2)
library(mixOmics)
library(pheatmap)


# ============================= parameters =============================
input_csv <- "{os.path.join(input_dir, 'feature_table_filtered_imputed.csv').replace(os.sep, '/')}"
metadata_csv <- "{metadata_csv.replace(os.sep, '/')}"
outdir <- "{output_dir.replace(os.sep, '/')}"

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

# Normalize sample names: strip file extensions from BOTH feature table
# column names AND metadata Sample column. This handles all 4 cases:
#   CSV: DY-1-1    / metadata: DY-1-1        → both unchanged → match
#   CSV: DY-1-1    / metadata: DY-1-1.mzML   → metadata stripped → match
#   CSV: DY-1-1.mzML / metadata: DY-1-1      → CSV stripped → match
#   CSV: DY-1-1.mzML / metadata: DY-1-1.mzML → both stripped → match
# feature_id, mz, rt_med have no dot → sub is no-op on them.
colnames(feature_df) <- sub("\\\\.[^.]+$", "", colnames(feature_df))
metadata$Sample <- sub("\\\\.[^.]+$", "", metadata$Sample)


# ============================= parameter check =============================
if (!scale_method %in% c("autoscale", "none")) {{
    stop("scale_method must be 'autoscale' or 'none'")
}}

if (!all(c("Sample", "Group") %in% colnames(metadata))) {{
    stop("metadata must contain Sample and Group columns")
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
Y <- factor(metadata$Group)

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
    title = "PCA"
)

dev.off()


# ============================= PLS-DA =============================
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
    title = "PLS-DA"
)

dev.off()


# ============================= Cross Validation =============================
set.seed(seed)

min_group_size <- min(table(Y))

n_folds <- min(
    5,
    max(2, min_group_size)
)

perf_res <- perf(
    plsda_res,
    validation = "Mfold",
    folds = n_folds,
    nrepeat = 10,
    progressBar = TRUE
)

capture.output(
    print(perf_res$error.rate),
    file = file.path(
        outdir,
        "plsda_cv_results.txt"
    )
)


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

if (nlevels(Y) == 2) {{

    idx1 <- which(Y == levels(Y)[1])
    idx2 <- which(Y == levels(Y)[2])

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

    if (use_fdr) {{
        volcano_df$Significant <- with(
            volcano_df,
            !is.na(padj) &
            padj < padj_threshold &
            abs(log2FC) >= log2fc_threshold
        )
    }} else {{
        volcano_df$Significant <- with(
            volcano_df,
            !is.na(pvalue) &
            pvalue < pvalue_threshold &
            abs(log2FC) >= log2fc_threshold
        )
    }}

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
        ggtitle("Volcano Plot")

    ggsave(
        file.path(outdir, "volcano_plot.png"),
        p,
        width = 6,
        height = 5,
        dpi = 300
    )


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

    annotation_col <- data.frame(
        Group = Y
    )

    rownames(annotation_col) <- rownames(X_tmp)

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
}}


# ============================= Session Info =============================
writeLines(
    capture.output(sessionInfo()),
    file.path(outdir, "sessionInfo.txt")
)
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        result = subprocess.run([_get_rscript(), r_file], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"\n[R ERROR] Statistical analysis failed (exit code {result.returncode}):")
            print(result.stderr)
            print(result.stdout)
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

    finally:
        os.unlink(r_file)




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

    # ============ ID mapping: compound → XCMS feature ============
    # Stage 5 differential_metabolites.csv uses RAMClust compound IDs (C0201),
    # but Stage 2 spectra.mgf uses XCMS feature IDs (FT00033).
    # ramclust_clusters.csv maps: feature_id → cluster (compound number).
    # Compound ID format: C + zero-padded 4-digit cluster number.
    clusters_csv = None
    outputspace_root = os.path.dirname(   # .../outputspace/
        os.path.dirname(                   # .../statistical_analysis/
            os.path.dirname(differential_csv)  # .../statistical_analysis_mixomics/
        )
    )
    for root, dirs, files in os.walk(
        os.path.join(outputspace_root, "redundant_feature_filtering")
    ):
        if "ramclust_clusters.csv" in files:
            clusters_csv = os.path.join(root, "ramclust_clusters.csv")
            break
    # Fallback: search entire outputspace
    if clusters_csv is None:
        for root, dirs, files in os.walk(outputspace_root):
            if "ramclust_clusters.csv" in files:
                clusters_csv = os.path.join(root, "ramclust_clusters.csv")
                break

    if clusters_csv is not None:
        print(f"  Found cluster mapping: {clusters_csv}")
        clusters_df = pd.read_csv(clusters_csv)
        # Build reverse mapping: compound ID → set of XCMS feature IDs
        compound_to_features = {}
        for _, row in clusters_df.iterrows():
            cluster_num = row.get("cluster", -1)
            if pd.notna(cluster_num) and int(cluster_num) >= 0:
                cid = f"C{int(cluster_num):04d}"
                compound_to_features.setdefault(cid, set()).add(
                    str(row["feature_id"])
                )
        # Expand target_features to include underlying XCMS feature IDs
        expanded = set(target_features)
        mapped_count = 0
        for cid in target_features:
            if cid in compound_to_features:
                expanded.update(compound_to_features[cid])
                mapped_count += 1
        print(
            f"  ID mapping: {mapped_count}/{len(target_features)} "
            f"compounds mapped to {len(expanded)} total feature IDs"
        )
        target_features = expanded
    else:
        print(
            "  WARNING: ramclust_clusters.csv not found — "
            "compound-to-feature ID mapping skipped. "
            "Spectra may not match if IDs differ between stages."
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
def spectral_annotation_impl(
    input_dir: str,
    output_dir: str,
    precursor_ppm: float = 5,
    fragment_tol: float = 0.05,
    min_cosine: float = 0.5,
    include_precursor: bool = True,
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
    include_precursor : bool, default=True
        If True, require precursor m/z match (requirePrecursor=TRUE).
        Enables fast path with precursor pre-filtering and parallel processing.
        Set to False only if precursor m/z data is unavailable.
    use_mona : bool, default=True
        If True, also search the MoNA spectral libraries (much larger coverage).
    use_spectraverse : bool, default=True
        If True, also search the spectraverse spectral library (1.3 GB, broad coverage).
    """

    print("\nPerforming spectral library annotation...")

    os.makedirs(output_dir, exist_ok=True)

    # --- Auto-detect ramclust_clusters.csv for feature_id → compound mapping ---
    # Query MGF contains XCMS feature IDs (FT00073), but the feature table
    # contains RAMClust compound IDs (C0044). We need the cluster mapping to
    # bridge these two ID systems when merging annotations.
    outputspace_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(input_dir))
    )))  # input_dir is .../differential_feature_extraction/extract_differential_features/
    clusters_csv = None
    search_roots = [
        os.path.join(outputspace_root, "redundant_feature_filtering"),
        outputspace_root,
    ]
    for search_root in search_roots:
        if os.path.isdir(search_root):
            for root, dirs, files in os.walk(search_root):
                if "ramclust_clusters.csv" in files:
                    clusters_csv = os.path.join(root, "ramclust_clusters.csv")
                    break
        if clusters_csv:
            break
    if clusters_csv:
        print(f"  Found cluster mapping: {clusters_csv}")
    else:
        print("  WARNING: ramclust_clusters.csv not found — "
              "compound-level annotation merging may fail")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    gnps_pos_path = os.path.join(base_dir, "../..", "database_file/GNPS/GNPS-NIH-NATURALPRODUCTSLIBRARY_ROUND2_POSITIVE.msp")
    gnps_neg_path = os.path.join(base_dir, "../..", "database_file/GNPS/GNPS-NIH-NATURALPRODUCTSLIBRARY_ROUND2_NEGATIVE.msp")
    mona_pos_path = os.path.join(base_dir, "../..", "database_file/MoNA/LC-MS-MS_Positive_Mode.msp")
    mona_neg_path = os.path.join(base_dir, "../..", "database_file/MoNA/LC-MS-MS_Negative_Mode.msp")
    spectraverse_path = os.path.join(base_dir, "../..", "database_file/spectraverse-1.0.1.mgf")

    req_precursor_str = "TRUE" if include_precursor else "FALSE"
    use_mona_str = "TRUE" if use_mona else "FALSE"
    use_spectraverse_str = "TRUE" if use_spectraverse else "FALSE"
    clusters_csv_r = clusters_csv.replace(os.sep, '/') if clusters_csv else ""
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
library(BiocParallel)


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
clusters_csv <- "{clusters_csv_r}"


# ============================= parallel backend =============================
# Register multicore parallel backend for matchSpectra.
# When include_precursor=TRUE, matchSpectra uses bplapply to parallelize
# per-query-spectrum matching against precursor-filtered library candidates.
n_workers <- max(1, parallel::detectCores() - 1)
register(MulticoreParam(workers = n_workers))
bp <- bpparam()
cat("Parallel backend registered with", n_workers, "workers\\n")


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
    # Priority: COMPOUND_NAME (semantically correct field) first,
    # then TITLE (which is an internal ID for Spectraverse MGF files
    # but a real compound name in GNPS/MoNA MSP format).
    name <- rep(NA_character_, length(target_idx))
    if ("COMPOUND_NAME" %in% colnames_avail) {{
        name <- meta$COMPOUND_NAME[target_idx]
    }}
    if (all(is.na(name)) && "TITLE" %in% colnames_avail) {{
        name <- meta$TITLE[target_idx]
    }}
    if (all(is.na(name)) && "name" %in% colnames_avail) {{
        name <- meta$name[target_idx]
    }}
    if (all(is.na(name)) && "Name" %in% colnames_avail) {{
        name <- meta$Name[target_idx]
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
        # precursorMz() threw an error — fall back to column lookup
    }})
    # Second fallback: precursorMz() returned NA (no error), e.g. MoNA MSP
    # where MsBackendMsp does not map "PrecursorMZ:" to the precursorMz slot.
    if (all(is.na(prec_mz))) {{
        if ("PrecursorMZ" %in% colnames_avail) {{
            prec_mz <- as.numeric(meta$PrecursorMZ[target_idx])
        }} else if ("PRECURSOR_MZ" %in% colnames_avail) {{
            prec_mz <- as.numeric(meta$PRECURSOR_MZ[target_idx])
        }}
    }}

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

    # Fix: MsBackendMsp may not map all PrecursorMZ field variants to the
    # precursorMz slot. GNPS uses "PRECURSORMZ:" (all-caps, mapped correctly)
    # but MoNA uses "PrecursorMZ:" (CamelCase, NOT mapped by MsBackendMsp).
    # Without this fix, requirePrecursor=TRUE blocks all MoNA matches because
    # precursorMz() returns NA for every library spectrum.
    if (backend_type == "msp") {{
        pmz <- precursorMz(lib_spectra)
        if (all(is.na(pmz))) {{
            meta_cols <- colnames(spectraData(lib_spectra))
            if ("PrecursorMZ" %in% meta_cols) {{
                precursorMz(lib_spectra) <- as.numeric(
                    spectraData(lib_spectra)$PrecursorMZ
                )
                n_fixed <- sum(!is.na(precursorMz(lib_spectra)))
                cat("    Fixed precursorMz from PrecursorMZ column:",
                    n_fixed, "of", length(lib_spectra), "values\\n")
            }}
        }}
    }}

    res <- matchSpectra(query_spectra, lib_spectra, match_param, BPPARAM = bp)
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
# Query MGF contains XCMS feature IDs (e.g. FT00073) while feat_table
# contains RAMClust compound IDs (e.g. C0044). Build a mapping from
# XCMS feature_id → compound_id using ramclust_clusters.csv, then
# aggregate multiple features mapping to the same compound.
if (nrow(anno_total) > 0) {{

    # ---- Build feature_id → compound_id mapping ----
    feature_to_compound <- list()
    if (clusters_csv != "" && file.exists(clusters_csv)) {{
        clusters_df <- read.csv(clusters_csv, stringsAsFactors = FALSE)
        for (j in seq_len(nrow(clusters_df))) {{
            fid <- as.character(clusters_df$feature_id[j])
            cnum <- clusters_df$cluster[j]
            if (!is.na(cnum) && cnum >= 0) {{
                cid <- sprintf("C%04d", as.integer(cnum))
                feature_to_compound[[fid]] <- cid
            }}
        }}
    }}

    # ---- Get TITLE (feature ID) for each query spectrum ----
    query_titles <- spectraData(query_spectra)$TITLE
    if (is.null(query_titles)) {{
        query_titles <- as.character(seq_along(query_spectra))
    }}

    # ---- Map matches to feat_table rows ----
    for (i in seq_len(nrow(anno_total))) {{
        qidx <- anno_total$query_idx[i]
        title <- query_titles[qidx]
        cid <- feature_to_compound[[as.character(title)]]
        if (is.null(cid)) {{
            # Fallback: use TITLE as-is (may match directly)
            cid <- as.character(title)
        }}
        feat_row <- which(feat_table$Feature == cid)
        if (length(feat_row) == 0) next

        # Keep best score if multiple features map to same compound
        existing_score <- feat_table$cosine_score[feat_row[1]]
        new_score <- round(anno_total$score[i], 3)
        if (!is.na(existing_score) && existing_score >= new_score) next

        feat_table$compound_name[feat_row[1]]    <- anno_total$compound_name[i]
        feat_table$cosine_score[feat_row[1]]     <- new_score
        feat_table$ion_mode_match[feat_row[1]]   <- anno_total$ion_mode[i]
        feat_table$library_precursor_mz[feat_row[1]] <- anno_total$library_precursor_mz[i]
        feat_table$smiles[feat_row[1]]           <- anno_total$smiles[i]
        feat_table$formula[feat_row[1]]          <- anno_total$formula[i]
        feat_table$library_source[feat_row[1]]   <- anno_total$library_source[i]
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
    # Try both [M+H]+ and [M-H]- adducts, guided by ion_mode_match when available.
    cat("\\n--- Mass-based KEGG lookup for unmatched features ---\\n")
    n_mass_found <- 0
    for (i in seq_len(nrow(feat_table))) {{
        if (is.na(feat_table$kegg_id[i])) {{
            mz_val <- feat_table$mz[i]
            if (!is.na(mz_val) && is.numeric(mz_val) && mz_val > 50) {{
                ion_mode <- feat_table$ion_mode_match[i]
                if (is.na(ion_mode)) ion_mode <- "UNKNOWN"

                # Build adduct list: try known mode first, then the other
                if (ion_mode == "NEG") {{
                    adducts <- c(-1.0078, 1.0078)   # [M-H]- first, then [M+H]+ as fallback
                }} else {{
                    adducts <- c(1.0078, -1.0078)   # [M+H]+ first (POS and UNKNOWN), then [M-H]-
                }}

                for (adduct in adducts) {{
                    if (!is.na(feat_table$kegg_id[i])) break
                    neutral_mass <- mz_val - adduct
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
            [_get_rscript(), r_file],
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

def _kegg_api_request(url_path: str, timeout: float = 10.0) -> Optional[str]:
    """
    Make a request to the KEGG REST API with HTTPS→HTTP fallback.

    From mainland China, HTTPS connections to rest.kegg.jp often experience
    SSL handshake timeouts due to network interference.  KEGG REST API
    supports plain HTTP, so we try HTTPS first (for security), then fall
    back to HTTP when the SSL layer fails.

    Proxy support: respects the conventional http_proxy / HTTP_PROXY
    environment variables.

    Parameters
    ----------
    url_path : str
        Path portion of the URL, e.g. "find/compound/glucose".
    timeout : float
        Request timeout in seconds.

    Returns
    -------
    str or None
        Response body text, or None if all attempts fail.
    """
    import urllib.request
    import urllib.error
    import ssl

    # Respect proxy environment variables
    proxies = {}
    http_proxy = os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
    if http_proxy:
        proxies['http'] = http_proxy
        # Also use http proxy for https when no separate https_proxy is set
        if not (os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')):
            proxies['https'] = http_proxy
    https_proxy = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
    if https_proxy:
        proxies['https'] = https_proxy

    proxy_handler = urllib.request.ProxyHandler(proxies) if proxies else None

    # Try HTTPS first, then HTTP (KEGG supports both)
    for scheme in ('https', 'http'):
        url = f"{scheme}://rest.kegg.jp/{url_path}"
        try:
            if proxy_handler:
                opener = urllib.request.build_opener(proxy_handler)
                with opener.open(url, timeout=timeout) as resp:
                    return resp.read().decode('utf-8').strip()
            else:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=timeout,
                                             context=ssl._create_unverified_context()) as resp:
                    return resp.read().decode('utf-8').strip()
        except Exception:
            continue  # try next scheme

    return None


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
    text = _kegg_api_request(f"find/compound/{encoded}", timeout=timeout)

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
    text = _kegg_api_request(
        f"find/compound/{neutral_mass}/exact_mass", timeout=timeout
    )

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
                text = _kegg_api_request(f"find/compound/{encoded}/formula", timeout=10)
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
                    # Determine adducts to try based on ion_mode if available
                    ion_mode = row.get('ion_mode_match', None)
                    if pd.isna(ion_mode) or str(ion_mode).strip() in ('', 'NA'):
                        ion_mode = 'UNKNOWN'
                    else:
                        ion_mode = str(ion_mode).strip().upper()
                    if ion_mode == 'NEG':
                        adducts = [-1.0078, 1.0078]   # [M-H]- first, then [M+H]+ fallback
                    else:
                        adducts = [1.0078, -1.0078]   # [M+H]+ first (POS & UNKNOWN), then [M-H]-
                    for adduct in adducts:
                        if kegg_id is not None:
                            break
                        neutral_mass = mz_f - adduct
                        if neutral_mass > 50:
                            candidates = _lookup_kegg_by_mass(neutral_mass, ppm=20)
                            if candidates:
                                kegg_id = candidates[0]
                                print(f"    [mass] m/z={mz_f:.4f} ion_mode={ion_mode} → {kegg_id}")
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
    enrich_table_out = os.path.join(output_dir, "kegg_compound_enrich.csv")
    bubble_plot_out = os.path.join(output_dir, "kegg_compound_bubble.png")
    dotplot_out = os.path.join(output_dir, "kegg_compound_dotplot.png")
    barplot_out = os.path.join(output_dir, "kegg_compound_barplot.png")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    compound_pathway_path = os.path.join(base_dir, "../..", "database_file/compound_pathway.tsv")

    r_script = f"""
library(clusterProfiler)
library(ggplot2)
library(KEGGREST)
library(dplyr)
library(enrichplot)

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
}}
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run([_get_rscript(), r_file], check=True, capture_output=True)
    finally:
        os.unlink(r_file)




if __name__ == "__main__":
    base = "/data2/luxiang/MOA/outputspace"

    # data_preprocessing_xcms_impl(
    #     input_dir=f"{base}/data_conversion/mzml",
    #     output_dir=f"{base}/data_preprocessing/xcms_processed",
    #     file_pattern="*.mzML",
    #     blank_pattern="Blank",
    #     ms2_ppm=20,
    #     ms2_rt_window=5,
    #     blank_ratio_threshold=3,
    #     n_cores=None,
    #     ppm=10,
    #     peakwidth=(5, 20),
    #     snthresh=10,
    #     prefilter=(3, 100),
    #     bin_size=0.25,
    #     center=1,
    #     bw=5,
    #     min_fraction=0.5,
    #     min_samples=2
    # )

    # feature_filtering_and_missing_value_imputation_KNN_impl(
    #     input_dir=f"{base}/data_preprocessing/xcms_processed",
    #     output_dir=f"{base}/missing_value_imputation/filtered_imputed_results",
    #     min_presence=0.5,
    #     min_intensity=0.0,
    #     n_neighbors=5
    # )

    # statistical_analysis_mixomics_impl(
    #     input_dir=f"{base}/missing_value_imputation/filtered_imputed_results",
    #     metadata_csv="/data2/luxiang/MOA/inputspace/metadata.csv",
    #     output_dir=f"{base}/statistical_analysis/mixomics_results",
    #     ncomp_pca=5,
    #     ncomp_plsda=2,
    #     scale_method="autoscale",
    #     top_n_heatmap=50,
    #     seed=123,
    #     vip_threshold=1.0,
    #     pvalue_threshold=0.05,
    #     padj_threshold=0.05,
    #     log2fc_threshold=0.58,
    #     use_fdr=False
    # )

    # extract_differential_features_impl(
    #     differential_csv=f"{base}/statistical_analysis/mixomics_results/differential_metabolites.csv",
    #     input_mgf=f"{base}/data_preprocessing/xcms_processed/spectra.mgf",
    #     output_dir=f"{base}/statistical_analysis/differential_features"
    # )

    # spectral_annotation_impl(
    #     input_dir=f"{base}/statistical_analysis/differential_features",
    #     output_dir=f"{base}/library_matching/annotation_results",
    #     precursor_ppm=100,
    #     fragment_tol=0.2,
    #     min_cosine=0.2
    # )

    # sirius_unknowns_annotation_impl(
    #     input_dir=f"{base}/statistical_analysis/differential_features",
    #     output_dir=f"{base}/unknown_identification/sirius_results",
    #     profile="orbitrap",
    #     database="pubchem"
    # )

    kegg_compound_enrich_impl(
        input_dir=f"{base}/library_matching/annotation_results",
        output_dir=f"{base}/enrichment_analysis/kegg_results",
    )
