import os
import subprocess
import tempfile
import glob


# ============================= data_preprocessing =============================
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
            capture_output=False,
            text=True,
            encoding='utf-8'
        )

    finally:
        os.unlink(r_file)



# ============================= spectral_annotation =============================
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
        Directory containing MGF spectra, and feature table.
    output_dir : str
        Output directory for annotated feature table.
    precursor_ppm : float, default=5
        Precursor ion mass tolerance in ppm.
    fragment_tol : float, default=0.02
        Fragment ion mass tolerance in Da.
    min_cosine : float, default=0.7
        Minimum cosine similarity score required for annotation.
    """

    print("\nPerforming spectral library annotation...")

    os.makedirs(output_dir, exist_ok=True)

    mgf_path = os.path.join(input_dir, mgf_file)
    feat_csv = os.path.join(input_dir, feature_table_file)

    
    lib_pos_path = os.path.join(input_dir, "LC-MS-MS_Positive_Mode.msp")
    lib_neg_path = os.path.join(input_dir, "LC-MS-MS_Negative_Mode.msp")

    out_csv = os.path.join(output_dir, "feature_annotated.csv")

    r_script = f"""
# ============================= packages =============================
if (!requireNamespace("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

required_pkgs <- c(
    "Spectra",
    "MsBackendMgf",
    "MsBackendMsp",
    "dplyr"
)

for (pkg in required_pkgs) {{
    if (!requireNamespace(pkg, quietly = TRUE)) {{
        BiocManager::install(pkg, update = FALSE, ask = FALSE)
    }}
}}

library(Spectra)
library(MsBackendMgf)
library(MsBackendMsp)
library(dplyr)


# ============================= parameters =============================
mgf_path <- "{mgf_path.replace(os.sep, '/')}"
feat_csv <- "{feat_csv.replace(os.sep, '/')}"

lib_pos_path <- "{lib_pos_path.replace(os.sep, '/')}"
lib_neg_path <- "{lib_neg_path.replace(os.sep, '/')}"

out_csv <- "{out_csv.replace(os.sep, '/')}"

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
match_param <- MatchSpectraParam(
    ppm = prec_ppm,
    tolerance = frag_tol,
    method = "cosine",
    requirePrecursor = TRUE,
    topN = 1
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

    pos_df <- as.data.frame(pos_res)
    neg_df <- as.data.frame(neg_res)

    # Remove low-confidence matches
    pos_df <- pos_df[pos_df$score >= min_score, ]
    neg_df <- neg_df[neg_df$score >= min_score, ]

    # Add ion mode labels
    pos_df$ion_mode <- "POS"
    neg_df$ion_mode <- "NEG"

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

if (!"feature_id" %in% colnames(feat_table)) {{
    stop("feature_id column not found in feature table")
}}


# ============================= initialize annotation columns =============================
feat_table$compound_name <- NA
feat_table$cosine_score <- NA
feat_table$ion_mode_match <- NA
feat_table$library_precursor_mz <- NA


# ============================= merge annotations into feature table =============================
if (nrow(anno_total) > 0) {{

    for (i in seq_len(nrow(anno_total))) {{

        fid <- anno_total$query_id[i]

        idx <- which(feat_table$feature_id == fid)

        if (length(idx) > 0) {{

            feat_table$compound_name[idx] <-
                anno_total$name[i]

            feat_table$cosine_score[idx] <-
                round(anno_total$score[i], 3)

            feat_table$ion_mode_match[idx] <-
                anno_total$ion_mode[i]

            feat_table$library_precursor_mz[idx] <-
                anno_total$precursorMz[i]
        }}
    }}
}}


# ============================= output =============================
write.csv(
    feat_table,
    out_csv,
    row.names = FALSE
)

cat(
    "Spectral annotation completed!\\n"
)

cat(
    "Annotated feature table written to:\\n",
    out_csv,
    "\\n"
)

cat(
    "Successfully annotated compounds:",
    sum(!is.na(feat_table$compound_name)),
    "\\n"
)
"""

    # ============================= write temporary R script =============================
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.R',
        delete=False
    ) as f:

        f.write(r_script)
        r_file = f.name

    # ============================= run R script =============================
    try:
        subprocess.run(
            ['Rscript', r_file],
            capture_output=False,
            text=True,
            encoding='utf-8',
            check=True
        )

    finally:
        os.unlink(r_file)



if __name__ == "__main__":
    input_dir = "/data2/liuwei/MOA/workspace/mzml"
    output_dir = "/data2/liuwei/MOA/workspace/xcms_results"

    data_preprocessing_xcms_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        file_pattern="*.mzML",
        blank_pattern="Blank",
        ms2_ppm=20,
        ms2_rt_window=5,
        blank_ratio_threshold=3,
        n_cores=None,
        ppm=10,
        peakwidth=(5, 20),
        snthresh=10,
        prefilter=(3, 100),
        bin_size=0.25,
        center=1,
        bw=5,
        min_fraction=0.5,
        min_samples=2
    )
