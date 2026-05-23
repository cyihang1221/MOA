import os
import tempfile

from src.tools._r_runner import r_path, run_rscript


def filter_redundant_features_camera_impl(input_file: str, output_rds: str) -> str:
    """
    冗余特征过滤（兼容 xcms 3+ 的 XCMSnExp 与旧版 xcmsSet）。

    CentWave 峰检测输出为 XCMSnExp，旧版 CAMERA(xsAnnotate) 会卡住或报错；
    对 XCMSnExp 使用 groupChromPeaks + findChromPeakFeatures(IsotopeParam)。
    """
    ext = os.path.splitext(input_file)[1].lower()
    if ext != ".rds":
        raise ValueError(f"CAMERA 过滤当前仅支持 .rds 输入，收到: {ext}")

    out_dir = os.path.dirname(output_rds) or "."
    os.makedirs(out_dir, exist_ok=True)
    input_r = r_path(os.path.abspath(input_file))
    output_r = r_path(os.path.abspath(output_rds))
    output_csv = r_path(os.path.splitext(output_rds)[0] + ".csv")

    r_script = f'''
suppressPackageStartupMessages({{
  library(xcms)
  library(MSnbase)
}})

input_rds <- "{input_r}"
output_rds <- "{output_r}"
output_csv <- "{output_csv}"

cat("读取:", input_rds, "\\n")
xdata <- readRDS(input_rds)
cat("类型:", paste(class(xdata), collapse = ", "), "\\n")

if (inherits(xdata, "XCMSnExp")) {{
  if (length(chromPeaks(xdata)) == 0) stop("XCMSnExp 中无色谱峰")

  n_files <- length(fileNames(xdata))
  cat("样本数:", n_files, " 峰数:", nrow(chromPeaks(xdata)), "\\n")

  # 若尚未分组，先做跨样本峰对齐/分组
  pd <- chromPeakData(xdata)
  need_group <- is.null(pd$group) || all(is.na(pd$group))
  if (need_group && n_files > 1) {{
    cat("执行 groupChromPeaks (PeakDensityParam)...\\n")
    sg <- rep(1L, n_files)
    xdata <- groupChromPeaks(
      xdata,
      param = PeakDensityParam(sampleGroups = sg, minFraction = 0.5)
    )
    cat("groupChromPeaks 完成\\n")
  }} else if (need_group) {{
    cat("单文件数据，跳过 groupChromPeaks\\n")
  }}

  # xcms3 同位素注释（替代旧版 CAMERA xsAnnotate，避免对 XCMSnExp 卡死）
  cat("执行 findChromPeakFeatures (IsotopeParam)...\\n")
  tryCatch(
    {{ xdata <- findChromPeakFeatures(xdata, param = IsotopeParam()) }},
    error = function(e) cat("警告 findChromPeakFeatures:", conditionMessage(e), "\\n")
  )
  cat("特征注释步骤结束\\n")

  peaks <- chromPeaks(xdata)
  meta <- as.data.frame(chromPeakData(xdata))
  export <- cbind(peaks, meta)
  write.csv(export, output_csv, row.names = FALSE)
  saveRDS(xdata, output_rds)
  cat("已保存:", output_rds, "与", output_csv, "\\n")

}} else if (inherits(xdata, "xcmsSet")) {{
  suppressPackageStartupMessages(library(CAMERA))
  cat("旧版 xcmsSet，使用 CAMERA xsAnnotate...\\n")
  an <- xsAnnotate(xdata)
  an <- groupFWHM(an)
  an <- findIsotopes(an)
  an <- groupCorr(an)
  saveRDS(an, output_rds)
  cat("CAMERA 完成\\n")
}} else {{
  stop("不支持的 RDS 类型: ", paste(class(xdata), collapse = ", "),
       "（需要 XCMSnExp 或 xcmsSet）")
}}
'''

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".R", delete=False, encoding="utf-8"
    ) as f:
        f.write(r_script)
        r_file = f.name

    try:
        log_path = run_rscript(
            r_file, label="filter_redundant_features_camera", log_dir=out_dir
        )
        if not os.path.isfile(output_rds):
            raise RuntimeError(f"未生成输出: {output_rds}")
        csv_path = os.path.splitext(output_rds)[0] + ".csv"
        extra = f", {csv_path}" if os.path.isfile(csv_path) else ""
        return f"冗余特征过滤完成: {output_rds}{extra}，日志: {log_path}"
    finally:
        os.unlink(r_file)


# ============================= RAMClustR 实现（保留原逻辑，改用 run_rscript） =============================
def filter_redundant_features_ramclustr_impl(input_file: str, output_rds: str) -> str:
    ext = os.path.splitext(input_file)[1].lower()
    if ext == ".rds":
        read_code = f'library(xcms)\nxdata <- readRDS("{r_path(input_file)}")\npeak_table <- chromPeaks(xdata)'
    elif ext == ".csv":
        read_code = f'peak_table <- read.csv("{r_path(input_file)}", check.names=FALSE)'
    elif ext == ".featurexml":
        read_code = f'''
        library(MSnbase)
        f <- readFeatureXML("{r_path(input_file)}")
        peak_table <- as.data.frame(f)
        '''
    elif ext == ".mzmine":
        raise ValueError("不支持 .mzmine，请使用导出的 .csv")
    else:
        raise ValueError(f"不支持的输入格式：{ext}")

    out_dir = os.path.dirname(output_rds) or "."
    os.makedirs(out_dir, exist_ok=True)
    r_script = f'''
    library(RAMClustR)
    library(xcms)
    {read_code}
    df <- data.frame(
      mz = peak_table[,"mz"],
      rt = peak_table[,"rt"],
      into = peak_table[,"into"]
    )
    ramclust <- ramclustR(
      ms = df,
      pheno = data.frame(sample = rep(1, nrow(df))),
      st = NULL, sampNames = NULL,
      usePheno = FALSE, rtmax = 1, mzdec = 4, rtdec = 2
    )
    saveRDS(ramclust, "{r_path(output_rds)}")
    '''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".R", delete=False, encoding="utf-8") as f:
        f.write(r_script)
        r_file = f.name
    try:
        log_path = run_rscript(r_file, label="filter_ramclustr", log_dir=out_dir)
        return f"RAMClustR 完成: {output_rds}，日志: {log_path}"
    finally:
        os.unlink(r_file)


def filter_redundant_features_mzannotation_impl(input_file: str, output_rds: str) -> str:
    ext = os.path.splitext(input_file)[1].lower()
    if ext == ".rds":
        read_code = f'library(xcms)\nxdata <- readRDS("{r_path(input_file)}")\npeak_table <- chromPeaks(xdata)'
    elif ext == ".csv":
        read_code = f'peak_table <- read.csv("{r_path(input_file)}", check.names=FALSE)'
    elif ext == ".featurexml":
        read_code = f'library(MSnbase)\nf <- readFeatureXML("{r_path(input_file)}")\npeak_table <- as.data.frame(f)'
    elif ext == ".mzmine":
        raise ValueError("不支持 .mzmine，请使用导出的 .csv")
    else:
        raise ValueError(f"不支持的格式：{ext}")

    out_dir = os.path.dirname(output_rds) or "."
    os.makedirs(out_dir, exist_ok=True)
    r_script = f'''
    library(mzAnnotation)
    library(xcms)
    {read_code}
    df <- data.frame(
        mz = peak_table[,"mz"],
        rt = peak_table[,"rt"],
        intensity = peak_table[,"into"]
    )
    filtered <- filterFeatures(
        df, ppm = 10, rt_window = 0.1,
        remove_isotopes = TRUE, remove_adducts = TRUE, keep_best = TRUE
    )
    saveRDS(filtered, "{r_path(output_rds)}")
    '''
    with tempfile.NamedTemporaryFile(mode="w", suffix=".R", delete=False, encoding="utf-8") as f:
        f.write(r_script)
        r_file = f.name
    try:
        log_path = run_rscript(r_file, label="filter_mzannotation", log_dir=out_dir)
        return f"mzAnnotation 完成: {output_rds}，日志: {log_path}"
    finally:
        os.unlink(r_file)
