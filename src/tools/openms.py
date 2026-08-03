import os
import subprocess
import tempfile
import glob


# ============================= data_preprocessing =============================
def data_preprocessing_openms_impl(
        input_dir: str,
        output_dir: str,
        threads: int = 4,
        mass_error_ppm: float = 10.0,
        openms_path: str = ""
):
    print("\nPreprocess data including feature detection, align, group and export results...")

    os.makedirs(output_dir, exist_ok=True)

    # 如果指定了 openms_path，添加到 PATH 前
    path_prefix = f'export PATH="{openms_path}:$PATH"' if openms_path else ""

    cmd = f"""
#!/bin/bash
set -e

input_dir="{input_dir}"
output_dir="{output_dir}"
threads={threads}
mass_error_ppm={mass_error_ppm}

{path_prefix}


# -------------------------- 创建文件夹 --------------------------
mkdir -p "$output_dir"/{{mzML_centroid,featureXML,consensus,mgf}}


# -------------------------- 峰检测：质心化 + FeatureFinder --------------------------
echo "=== 峰检测（质心化 + FeatureFinder）==="
MZML_FILES=$(find "$input_dir" -maxdepth 1 -name "*.mzML" | sort | tr '\\n' ' ')

for mzml in $MZML_FILES; do
  filename=$(basename "$mzml" .mzML)
  centroid="$output_dir/mzML_centroid/${{filename}}_centroid.mzML"
  feature="$output_dir/featureXML/${{filename}}.featureXML"

  PeakPickerHiRes \\
    -in "$mzml" \\
    -out "$centroid"

  FileConverter \
    -in "$centroid" \
    -out "$output_dir/mgf/${{filename}}.mgf"

  FeatureFinderMetabo \\
    -in "$centroid" \\
    -out "$feature" \\
    -algorithm:mtd:mass_error_ppm "$mass_error_ppm"
done


# -------------------------- 保留时间对齐 --------------------------
echo "=== 样本保留时间对齐 ==="
feature_files=("$output_dir"/featureXML/*.featureXML)

MapAlignerPoseClustering \\
  -in "${{feature_files[@]}}" \\
  -out "${{feature_files[@]}}" \\
  -threads "$threads"

  
# -------------------------- 生成统一峰表 --------------------------
echo "=== 生成合并峰表 ==="
FeatureLinkerUnlabeledQT \\
  -in "$output_dir"/featureXML/*.featureXML \\
  -out "$output_dir/consensus/consensus.consensusXML" \\
  -threads "$threads"


# -------------------------- 生成定量表 --------------------------
echo "=== 生成定量表 txt ==="
TextExporter \
  -in "$output_dir/consensus/consensus.consensusXML" \
  -out "$output_dir/feature_table.csv"
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(cmd)
        script = f.name

    try:
        subprocess.run(
            ['bash', script],
            capture_output=False,
            text=True,
            encoding='utf-8'
        )

    finally:
        os.unlink(script)


# # ============================= feature filtering & missing value imputation =============================
# def feature_filtering_and_missing_value_imputation_KNN_impl(
#     input_dir: str,
#     output_dir: str,
#     min_presence: float = 0.5,
# ):
#     print("\nFiltering feature and using KNN for missing value imputation...")

#     os.makedirs(output_dir, exist_ok=True)
#     input_csv = os.path.join(input_dir, "feature_table.csv")
#     output_csv = os.path.join(output_dir, "feature_table_imputed.csv")

#     import pandas as pd

#     # 读取所有行
#     with open(input_csv, 'r', encoding='utf-8') as f:
#         lines = f.readlines()

#     # 找到表头行（以 #CONSENSUS, 开头的那行）
#     header_line = None
#     data_lines = []
#     for line in lines:
#         if line.startswith("#CONSENSUS,"):
#             header_line = line.lstrip("#").strip()  # 去掉 #
#         elif line.startswith("CONSENSUS,"):
#             data_lines.append(line.strip())

#     if not header_line or len(data_lines) == 0:
#         raise ValueError("无法解析 OpenMS consensusCSV 文件：未找到 CONSENSUS 数据行")

#     # 构造干净的 DataFrame
#     from io import StringIO
#     clean_csv = header_line + "\n" + "\n".join(data_lines)
#     df = pd.read_csv(StringIO(clean_csv), sep=",")

#     # 过滤：只保留在 50%（可选） 以上样本中存在的特征
#     numeric_df = df.select_dtypes(include=['number'])
#     mask = (numeric_df.notna()).sum(axis=1) >= (min_presence * numeric_df.shape[1])
#     df = df[mask]

#     # 缺失值填补
#     from sklearn.impute import KNNImputer
#     imputer = KNNImputer(n_neighbors=5)
#     df[numeric_df.columns] = imputer.fit_transform(df[numeric_df.columns])

#     # 保存
#     df.to_csv(output_csv, index=False)
#     print(f"✅ 过滤 & 缺失值填补完成，输出：{output_csv}")


# # ============================= statistical analysis =============================
# def statistical_analysis_openms_mixomics_impl(
#     input_dir: str,
#     metadata_csv: str,
#     output_dir: str,
#     ncomp_pca: int = 5,
#     ncomp_plsda: int = 2,
#     scale_method: str = "autoscale",   # "autoscale" or "none"
#     top_n_heatmap: int = 50,
#     seed: int = 123
# ):
#     """
#     Parameters
#     ----------
#     input_dir : str
#         Directory containing feature_table_imputed.csv
#     metadata_csv : str
#         CSV file containing Sample and Group columns
#     output_dir : str
#         Output directory
#     ncomp_pca : int, default=5
#         Number of PCA components
#     ncomp_plsda : int, default=2
#         Number of PLS-DA components
#     scale_method : str, default="autoscale"
#         Scaling method: "autoscale" or "none"
#     top_n_heatmap : int, default=50
#         Number of top VIP features used in heatmap
#     seed : int, default=123
#         Random seed for cross-validation
#     """

#     print("\nPerforming statistical analysis using mixOmics...")

#     os.makedirs(output_dir, exist_ok=True)
#     input_csv = os.path.join(input_dir, "feature_table_imputed.csv")

#     r_script = f"""
# # ============================= packages =============================
# library(readr)
# library(dplyr)
# library(tibble)
# library(ggplot2)
# library(mixOmics)
# library(pheatmap)


# # ============================= parameters =============================
# input_csv <- "{input_csv.replace(os.sep, '/')}"
# metadata_csv <- "{metadata_csv.replace(os.sep, '/')}"
# outdir <- "{output_dir.replace(os.sep, '/')}"

# ncomp_pca <- {ncomp_pca}
# ncomp_plsda <- {ncomp_plsda}
# scale_method <- "{scale_method}"
# top_n_heatmap <- {top_n_heatmap}
# seed <- {seed}

# dir.create(outdir, showWarnings = FALSE, recursive = TRUE)


# # ============================= read data =============================
# feature_df <- read_csv(input_csv, show_col_types = FALSE)
# metadata <- read_csv(metadata_csv, show_col_types = FALSE)

# # 删除第一列 CONSENSUS（如果存在）
# if (colnames(feature_df)[1] == "CONSENSUS") {{
#     feature_df <- feature_df[, -1]
# }}

# # 参数检查
# if (!scale_method %in% c("autoscale", "none")) {{
#     stop("scale_method must be 'autoscale' or 'none'")
# }}


# # ============================= extract intensity columns =============================
# sample_cols <- c(
#   "rt_cf",
#   "mz_cf",
#   grep("^intensity_[0-9]+$", colnames(feature_df), value = TRUE)
# )

# if (length(sample_cols) == 0) {{
#     stop("No columns matching '^intensity_[0-9]+$' were found.")
# }}


# # ============================= construct matrix =============================
# # 行 = 样本，列 = 特征
# X <- feature_df %>%
#     dplyr::select(dplyr::all_of(sample_cols)) %>%
#     as.matrix() 

    
# # ============================= align metadata =============================
# if (!all(c("Sample", "Group") %in% colnames(metadata))) {{
#     stop("metadata 必须包含 Sample 和 Group 两列")
# }}

# # openms 输出的峰表中，样本列名是 intensity_1, intensity_2, ...，我们需要把它们替换成 metadata 中的 Sample 列对应的名称
# colnames(X)[colnames(X) == "rt_cf"] <- "rt"
# colnames(X)[colnames(X) == "mz_cf"] <- "mz"
# colnames(X)[grepl("^intensity_[0-9]+$", colnames(X))] <- metadata$Sample

# metadata <- metadata %>%
#   dplyr::filter(Sample %in% colnames(X))

# if (nrow(metadata) == 0) {{
#     stop("metadata 中没有与峰表匹配的样本名称")
# }}


# # ============================= remove zero-variance features =============================
# keep <- apply(X[, 3:ncol(X)], 1, function(v) sd(v, na.rm = TRUE) > 0)

# if (!any(keep)) {{
#     stop("所有特征的方差均为 0")
# }}

# X <- X[keep, , drop = FALSE]


# # ============================= transform =============================
# X[, 3:ncol(X)] <- log2((X[, 3:ncol(X)] + 1))  # 数据扁平化

# if (scale_method == "autoscale") {{  
#     X[, 3:ncol(X)] <- t(apply(X[, 3:ncol(X)], 1, scale))  # 对 第3列 ~ 最后一列 按行 Z-score 标准化
# }}


# # ============================= PCA =============================
# Y <- factor(metadata$Group)

# sample_cols <- setdiff(colnames(X), c("rt", "mz"))  # 只提取样本列（去掉 rt 和 mz）
# sample_cols <- sample_cols[sample_cols != "X"]  # 如果第一列是自动生成的行号，也去掉

# feature_matrix <- as.matrix(X[, sample_cols, drop = FALSE])  # 提取 feature * sample 矩阵

# if (is.null(rownames(feature_matrix))) {{
#     rownames(feature_matrix) <- paste0("Feature_", seq_len(nrow(feature_matrix)))
# }}

# X_tmp <- t(feature_matrix)  # 转置为 sample * feature（mixOmics 要求），后续分析也使用这个 X_tmp
# X_tmp <- X_tmp[metadata$Sample, , drop = FALSE]  # 确保样本顺序与 metadata 一致

# # PCA
# pca_res <- pca(
#     X_tmp,
#     ncomp = min(
#         ncomp_pca,
#         ncol(X_tmp),       # feature 数
#         nrow(X_tmp) - 1    # sample 数 - 1
#     )
# )

# # 保存 scores
# write.csv(
#     pca_res$variates$X,
#     file.path(outdir, "pca_scores.csv")
# )

# # 绘图
# png(
#     file.path(outdir, "pca_plot.png"),
#     width = 1800,
#     height = 1500,
#     res = 300
# )

# # 根据实际 component 数决定绘图维度：
# # - 只有 1 个 component 时：comp = c(1, 1)
# # - 至少 2 个 component 时：comp = c(1, 2)
# pca_plot_comps <- if (ncol(pca_res$variates$X) >= 2) c(1, 2) else c(1, 1)

# plotIndiv(
#     pca_res,
#     comp = pca_plot_comps,
#     group = Y,
#     legend = TRUE,
#     title = "PCA"
# )

# dev.off()


# # ============================= PLS-DA =============================
# plsda_res <- plsda(
#     X_tmp,
#     Y,
#     ncomp = min(
#         ncomp_plsda,
#         nlevels(Y) - 1,
#         ncol(X_tmp),
#         nrow(X_tmp) - 1
#     )
# )

# write.csv(
#     plsda_res$variates$X,
#     file.path(outdir, "plsda_scores.csv")
# )

# png(
#     file.path(outdir, "plsda_plot.png"),
#     width = 1800,
#     height = 1500,
#     res = 300
# )

# plsda_plot_comps <- if (ncol(plsda_res$variates$X) >= 2) c(1, 2) else c(1, 1)

# plotIndiv(
#     plsda_res,
#     comp = plsda_plot_comps,
#     group = Y,
#     legend = TRUE,
#     title = "PLS-DA"
# )

# dev.off()


# # ============================= Cross Validation =============================
# set.seed(seed)

# min_group_size <- min(table(Y))
# n_folds <- min(5, max(2, min_group_size))

# perf_res <- perf(
#     plsda_res,
#     validation = "Mfold",
#     folds = n_folds,
#     nrepeat = 10,
#     progressBar = TRUE
# )

# capture.output(
#     print(perf_res$error.rate),
#     file = file.path(outdir, "plsda_cv_results.txt")
# )


# # ============================= VIP =============================
# vip_scores <- vip(plsda_res)

# if (length(dim(vip_scores)) == 2) {{
#     ncomp_used <- min(ncomp_plsda, ncol(vip_scores))
#     vip_mean <- rowMeans(
#         vip_scores[, seq_len(ncomp_used), drop = FALSE]
#     )
# }} else {{
#     vip_mean <- vip_scores
# }}

# vip_df <- data.frame(
#     Feature = names(vip_mean),
#     VIP = as.numeric(vip_mean),
#     stringsAsFactors = FALSE
# ) %>%
#     arrange(desc(VIP))

# write.csv(
#     vip_df,
#     file.path(outdir, "vip_scores.csv"),
#     row.names = FALSE
# )

# write.csv(
#     vip_df %>% filter(VIP > 1),
#     file.path(outdir, "vip_gt_1.csv"),
#     row.names = FALSE
# )


# # ============================= Volcano Plot =============================
# volcano_df <- NULL

# if (nlevels(Y) == 2) {{
#     idx1 <- which(Y == levels(Y)[1])
#     idx2 <- which(Y == levels(Y)[2])

#     # X_tmp: 行=样本，列=特征
#     mean1 <- colMeans(X_tmp[idx1, , drop = FALSE], na.rm = TRUE)
#     mean2 <- colMeans(X_tmp[idx2, , drop = FALSE], na.rm = TRUE)

#     log2FC <- mean2 - mean1

#     # 对每个 feature（每一列）做 t-test
#     pvalues <- apply(X_tmp, 2, function(v) {{
#         tryCatch(
#             t.test(v[idx1], v[idx2])$p.value,
#             error = function(e) NA_real_
#         )
#     }})

#     volcano_df <- data.frame(
#         Feature = colnames(X_tmp),
#         log2FC = log2FC,
#         pvalue = pvalues,
#         padj = p.adjust(pvalues, method = "fdr"),
#         neglog10p = -log10(pvalues),
#         stringsAsFactors = FALSE
#     )

#     volcano_df$Significant <- with(
#         volcano_df,
#         !is.na(pvalue) &
#         pvalue < 0.05 &
#         abs(log2FC) >= 1
#     )

#     write.csv(
#         volcano_df,
#         file.path(outdir, "volcano_results.csv"),
#         row.names = FALSE
#     )

#     p <- ggplot(
#         volcano_df,
#         aes(
#             x = log2FC,
#             y = neglog10p,
#             color = Significant
#         )
#     ) +
#         geom_point(size = 1.5) +
#         geom_vline(
#             xintercept = c(-1, 1),
#             linetype = 2
#         ) +
#         geom_hline(
#             yintercept = -log10(0.05),
#             linetype = 2
#         ) +
#         theme_bw() +
#         ggtitle("Volcano Plot")

#     ggsave(
#         file.path(outdir, "volcano_plot.png"),
#         p,
#         width = 6,
#         height = 5,
#         dpi = 300
#     )
# }}


# # ============================= Heatmap =============================
# n_top <- min(top_n_heatmap, nrow(vip_df))

# if (n_top > 0) {{
#     top_features <- vip_df$Feature[seq_len(n_top)]

#     # 提取 top VIP 特征
#     # X_tmp: 行=样本，列=特征
#     heatmap_matrix <- X_tmp[, top_features, drop = FALSE]

#     # pheatmap 要求 行=feature，列=sample
#     heatmap_matrix <- t(heatmap_matrix)

#     # 样本注释
#     annotation_col <- data.frame(Group = Y)
#     rownames(annotation_col) <- rownames(X_tmp)

#     png(
#         file.path(outdir, "heatmap_top_vip.png"),
#         width = 2400,
#         height = 1800,
#         res = 300
#     )

#     pheatmap(
#         heatmap_matrix,
#         annotation_col = annotation_col,
#         scale = "none",
#         show_rownames = TRUE,
#         show_colnames = FALSE,
#         fontsize_row = 8
#     )

#     dev.off()
# }}


# # ============================= Session Info =============================
# writeLines(
#     capture.output(sessionInfo()),
#     file.path(outdir, "sessionInfo.txt")
# )
# """

#     with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
#         f.write(r_script)
#         r_file = f.name

#     try:
#         subprocess.run(["Rscript", r_file], check=True)
#     finally:
#         os.unlink(r_file)




if __name__ == "__main__":
    input_dir = "/data2/luxiang/MOA/outputspace/data_conversion/msconvert"
    output_dir = "/data2/luxiang/MOA/outputspace/openms_test_output"
    metadata_csv = "/data2/liuwei/MOA/workspace/metadata.csv"

    data_preprocessing_openms_impl(
        input_dir=input_dir,
        output_dir=output_dir,
        mass_error_ppm=10.0,
        openms_path="/home/luxiang/anaconda/envs/openms_env/bin"
    )
    # feature_filtering_and_missing_value_imputation_KNN_impl(
    #     input_dir="/data2/liuwei/MOA/workspace/data_preprocessing_results",
    #     output_dir="/data2/liuwei/MOA/workspace/imputed_results"
    # )
    # statistical_analysis_openms_mixomics_impl(
    #     input_dir="/data2/liuwei/MOA/workspace/imputed_results",
    #     metadata_csv=metadata_csv,
    #     output_dir="/data2/liuwei/MOA/workspace/statistical_analysis_results",
    #     ncomp_pca=5,
    #     ncomp_plsda=2,
    #     scale_method="autoscale",
    #     top_n_heatmap=50,
    #     seed=123
    # )
  

    

    print("end")
