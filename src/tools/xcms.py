import os
import shutil
import subprocess
import tempfile
import glob
import pandas as pd




# ===================================================== data_preprocessing ================================================================
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
        subprocess.run(
            ['Rscript', r_file],
            capture_output=True,  # MCP 协议严格要求所有通信必须是 JSON 格式，捕获所有输出，禁止它向 stdout 输出非 JSON 格式内容（MCP 客户端会监听 stdout）
            encoding='utf-8'
        )

    finally:
        os.unlink(r_file)




# ============================================ feature filtering & missing value imputation =====================================================
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
    use_fdr: bool = False
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
        subprocess.run(["Rscript", r_file], capture_output=False)

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
def spectral_annotation_impl(
    input_dir: str,
    output_dir: str,
    precursor_ppm: float = 5,
    fragment_tol: float = 0.02,
    min_cosine: float = 0.7
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
    fragment_tol : float, default=0.02
        Fragment ion mass tolerance in Da.
    min_cosine : float, default=0.7
        Minimum cosine similarity score required for annotation.
    """

    print("\nPerforming spectral library annotation...")

    os.makedirs(output_dir, exist_ok=True)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    lib_pos_path = os.path.join(base_dir, "../..", "database_file/GNPS/GNPS-NIH-NATURALPRODUCTSLIBRARY_ROUND2_POSITIVE.msp")
    lib_neg_path = os.path.join(base_dir, "../..", "database_file/GNPS/GNPS-NIH-NATURALPRODUCTSLIBRARY_ROUND2_NEGATIVE.msp")

    r_script = f"""
# ============================= packages =============================
library(Spectra)
library(MetaboAnnotation)
library(MsBackendMgf)
library(MsBackendMsp)
library(dplyr)
library(webchem)
library(rcdk)
library(readr)
library(httr)


# ============================= parameters =============================
mgf_path <- "{os.path.join(input_dir, 'differential_spectra.mgf').replace(os.sep, '/')}"
feat_csv <- "{os.path.join(input_dir, 'differential_feature_table.csv').replace(os.sep, '/')}"

lib_pos_path <- "{lib_pos_path.replace(os.sep, '/')}"
lib_neg_path <- "{lib_neg_path.replace(os.sep, '/')}"

out_csv <- "{os.path.join(output_dir, 'differential_feature_table_library_match.csv').replace(os.sep, '/')}"
out_csv_clean <- "{os.path.join(output_dir, 'differential_feature_table_library_match_clean&add.csv').replace(os.sep, '/')}"

prec_ppm <- {precursor_ppm}
frag_tol <- {fragment_tol}
min_cosine <- {min_cosine}


# ============================= input validation =============================
if (!file.exists(mgf_path)) {{
    stop("MGF file not found")
}}

if (!file.exists(feat_csv)) {{
    stop("Feature table CSV not found")
}}

if (!file.exists(lib_pos_path)) {{
    stop("Positive MSP library not found")
}}

if (!file.exists(lib_neg_path)) {{
    stop("Negative MSP library not found")
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

cat("Query spectra loaded:",
    length(query_spectra), "\\n")


# ============================= read spectral libraries =============================
cat("Reading positive library...\\n")

lib_pos <- Spectra(
    lib_pos_path,
    source = MsBackendMsp()
)

cat("Positive library spectra:",
    length(lib_pos), "\\n")


cat("Reading negative library...\\n")

lib_neg <- Spectra(
    lib_neg_path,
    source = MsBackendMsp()
)

cat("Negative library spectra:",
    length(lib_neg), "\\n")


# ============================= define matching parameters =============================
match_param <- CompareSpectraParam(
    ppm = prec_ppm,
    tolerance = frag_tol,
    requirePrecursor = TRUE,
    FUN = MsCoreUtils::ndotproduct
)


# ============================= spectral matching =============================
cat("Matching positive ion library...\\n")

res_pos <- matchSpectra(
    query_spectra,
    lib_pos,
    match_param
)

cat("Matching negative ion library...\\n")

res_neg <- matchSpectra(
    query_spectra,
    lib_neg,
    match_param
)


# ============================= merge annotations =============================
merge_annotation <- function(
    pos_res,
    neg_res,
    min_score
) {{

    pos_df <- MetaboAnnotation::matches(pos_res)
    neg_df <- MetaboAnnotation::matches(neg_res)

    # Remove low-confidence matches
    pos_df <- pos_df[pos_df$score >= min_score, ]
    neg_df <- neg_df[neg_df$score >= min_score, ]

    # Add ion mode labels
    if (nrow(pos_df) > 0) {{pos_df$ion_mode <- "POS"}}
    if (nrow(neg_df) > 0) {{neg_df$ion_mode <- "NEG"}}

    # Merge results
    all_anno <- rbind(pos_df, neg_df)

    if (nrow(all_anno) == 0) {{
        return(data.frame())
    }}

    # Keep highest-scoring annotation for each query
    all_anno <- all_anno[
        order(all_anno$query_id, -all_anno$score),
    ]

    all_anno <- all_anno[
        !duplicated(all_anno$query_id),
    ]

    return(all_anno)
}}

anno_total <- merge_annotation(
    res_pos,
    res_neg,
    min_cosine
)

cat("Matched spectra:",
    nrow(anno_total), "\\n")


# ============================= read feature table =============================
feat_table <- read.csv(
    feat_csv,
    stringsAsFactors = FALSE,
    check.names = FALSE
)

if (!"Feature" %in% colnames(feat_table)) {{
    stop("Feature column not found in feature table")
}}

# ============================= 新增：初始化扩展字段 =============================
feat_table$compound_name <- NA
feat_table$cosine_score <- NA
feat_table$ion_mode_match <- NA
feat_table$library_precursor_mz <- NA
feat_table$smiles <- NA          # 新增 SMILES

# 注释表新增扩展字段
anno_total$compound_name <- NA
anno_total$library_precursor_mz <- NA
anno_total$smiles <- NA

pos_idx <- which(anno_total$ion_mode == "POS")
neg_idx <- which(anno_total$ion_mode == "NEG")

# ============================= 解析正库元数据（名称/SMILES/KEGG/HMDB） =============================
if (length(pos_idx) > 0) {{
    pos_meta <- spectraData(lib_pos)
    target_idx <- anno_total$target_idx[pos_idx]

    # 化合物名称兼容
    if ("TITLE" %in% colnames(pos_meta)) {{
        anno_total$compound_name[pos_idx] <- pos_meta$TITLE[target_idx]
    }} else if ("name" %in% colnames(pos_meta)) {{
        anno_total$compound_name[pos_idx] <- pos_meta$name[target_idx]
    }} else if ("compound_name" %in% colnames(pos_meta)) {{
        anno_total$compound_name[pos_idx] <- pos_meta$compound_name[target_idx]
    }}

    # SMILES
    if ("SMILES" %in% colnames(pos_meta)) {{
        anno_total$smiles[pos_idx] <- pos_meta$SMILES[target_idx]
    }} else if ("smiles" %in% colnames(pos_meta)) {{
        anno_total$smiles[pos_idx] <- pos_meta$smiles[target_idx]
    }}

    # HMDB ID
    if ("HMDB" %in% colnames(pos_meta)) {{
        anno_total$hmdb_id[pos_idx] <- pos_meta$HMDB[target_idx]
    }} else if ("hmdb" %in% colnames(pos_meta)) {{
        anno_total$hmdb_id[pos_idx] <- pos_meta$hmdb[target_idx]
    }}

    # 库母离子
    anno_total$library_precursor_mz[pos_idx] <- precursorMz(lib_pos)[target_idx]
}}


# ============================= 解析负库元数据（名称/SMILES/KEGG/HMDB） =============================
if (length(neg_idx) > 0) {{
    neg_meta <- spectraData(lib_neg)
    target_idx <- anno_total$target_idx[neg_idx]

    # 化合物名称兼容
    if ("TITLE" %in% colnames(neg_meta)) {{
        anno_total$compound_name[neg_idx] <- neg_meta$TITLE[target_idx]
    }} else if ("name" %in% colnames(neg_meta)) {{
        anno_total$compound_name[neg_idx] <- neg_meta$name[target_idx]
    }} else if ("compound_name" %in% colnames(neg_meta)) {{
        anno_total$compound_name[neg_idx] <- neg_meta$compound_name[target_idx]
    }}

    # SMILES
    if ("SMILES" %in% colnames(neg_meta)) {{
        anno_total$smiles[neg_idx] <- neg_meta$SMILES[target_idx]
    }} else if ("smiles" %in% colnames(neg_meta)) {{
        anno_total$smiles[neg_idx] <- neg_meta$smiles[target_idx]
    }}

    # 库母离子
    anno_total$library_precursor_mz[neg_idx] <- precursorMz(lib_neg)[target_idx]
}}


# ============================= 合并所有注释到特征表 =============================
if (nrow(anno_total) > 0) {{
    for (i in seq_len(nrow(anno_total))) {{
        idx <- anno_total$query_idx[i]
        if (length(idx) > 0) {{
            feat_table$compound_name[idx]    <- anno_total$compound_name[i]
            feat_table$cosine_score[idx]     <- round(anno_total$score[i], 3)
            feat_table$ion_mode_match[idx]   <- anno_total$ion_mode[i]
            feat_table$library_precursor_mz[idx] <- anno_total$library_precursor_mz[i]
            feat_table$smiles[idx]           <- anno_total$smiles[i]
        }}
    }}
}}


# ============================= output =============================
write.csv(
    feat_table,
    out_csv,
    row.names = FALSE
)

cat("Spectral annotation completed!\\n")
cat("Annotated feature table written to:\\n", out_csv, "\\n")
cat("Successfully annotated compounds:", sum(!is.na(feat_table$compound_name)), "\\n")
cat("Compounds with SMILES:", sum(!is.na(feat_table$smiles)), "\\n")


# ============================= clean + keggID =============================
# 保留 smiles 不为 NA、不为空的行
df_smiles <- feat_table %>%
  filter(!is.na(smiles) & smiles != "")

# SMILES -> InChIKey -> KEGG ID 函数
smiles_annotate <- function(smi) {{
  tryCatch({{
    # 1. SMILES -> PubChem CID
    cid_res <- get_cid(smi, from = "smiles")
    if (nrow(cid_res) == 0) {{
      return(data.frame(
        smiles = smi,
        cid = NA,
        inchikey = NA,
        iupac_name = NA,
        kegg_id = NA
      ))
    }}
    cid <- cid_res$cid[1]
    cat("SMILES:", smi, "\\n")
    cat("CID:", cid, "\\n")

    # 2. CID -> InChIKey & IUPAC Name
    prop <- pc_prop(cid, properties = c("InChIKey", "IUPACName"))
    inchikey <- prop$InChIKey[1]
    iupac_name <- prop$IUPACName[1]
    cat("InChIKey:", inchikey, "\\n")
    cat("IUPAC Name:", iupac_name, "\\n")

    # 3. InChIKey -> KEGG Compound ID
    kegg_id <- NA
    if (!is.na(inchikey)) {{
      url <- paste0("https://rest.kegg.jp/find/compound/", inchikey)
      txt <- content(GET(url, timeout(60)), as = "text", encoding = "UTF-8")
      txt <- trimws(txt)
      cat("KEGG raw result:\\n")
      cat(txt, "\\n")
      if (txt != "") {{
        kegg_id <- sub("\\t.*", "", strsplit(txt, "\\n")[[1]][1])
      }}
    }}

    # Return result row
    return(data.frame(
      smiles = smi,
      cid = cid,
      inchikey = inchikey,
      iupac_name = iupac_name,
      kegg_id = kegg_id
    ))

  }}, error = function(e) {{
    cat("ERROR:\\n")
    print(e)
    return(data.frame(
      smiles = smi,
      cid = NA,
      inchikey = NA,
      iupac_name = NA,
      kegg_id = NA
    ))
  }})
}}

# Batch annotation
df_result <- data.frame()

if (nrow(df_smiles) > 0) {{
  df_anno <- bind_rows(lapply(df_smiles$smiles, smiles_annotate))
  # 左连接：原始表 + 注释结果，在原字段后面追加新列
  df_merged <- left_join(df_smiles, df_anno, by = "smiles")
}} else {{
  df_merged <- df_smiles
}}

write.csv(
    df_merged,
    out_csv_clean,
    row.names = FALSE
)
"""

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.R',
        delete=False
    ) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(
            ['Rscript', r_file],
            capture_output=True,
            encoding='utf-8'
        )

    finally:
        os.unlink(r_file)




# ============================================================ sirius unkowns annotation =======================================================
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




# ============================================= pathway enrichment analysis ==================================================
def kegg_compound_enrich_impl(
        input_dir: str,
        output_dir: str,
        pvalue_cutoff: float = 0.05,
        padj_method: str = "BH",
        qvalue_cutoff: float = 0.1,
        min_gs: int = 3,
        max_gs: int = 500,
        top_n: int = 15
) -> None:
    """
    KEGG compound pathway enrichment analysis (ORA style)
    based on compound → pathway mapping (NOT gene-based).
    """

    print("\nPerforming KEGG compound pathway enrichment analysis...")

    input_file = os.path.join(input_dir, "differential_feature_table_library_match_clean&add.csv")

    os.makedirs(output_dir, exist_ok=True)
    enrich_table_out = os.path.join(output_dir, "kegg_compound_enrich.csv")
    bubble_plot_out = os.path.join(output_dir, "kegg_compound_bubble.png")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    compound_pathway_path = os.path.join(base_dir, "../..", "database_file/compound_pathway.tsv")

    r_script = f"""
library(clusterProfiler)
library(ggplot2)
library(KEGGREST)
library(dplyr)

compound_pathway_path <- "{compound_pathway_path.replace(os.sep, '/')}"

# 1. Read input metabolites
sig_met <- read.csv("{input_file}", check.names = FALSE)
compound_list <- unique(sig_met$kegg_id)

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

# 4. Bubble plot
if (nrow(enrich_df) > 0) {{
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
}}
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(["Rscript", r_file], check=True, capture_output=True)
    finally:
        os.unlink(r_file)
        