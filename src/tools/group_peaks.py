import os
import subprocess
import tempfile


# ============================= XCMS-groupChromPeaks 实现 =============================
def group_peaks_xcms_groupChromPeaks_impl(
    input_rds: str,
    output_rds: str,
    bw: int = 30,
    min_fraction: float = 0.5,
    min_samples: int = 1,
    groups: list = None
) -> str:

    if groups is None:
        group_str = "rep(1, length(fileNames(xdata)))"
    else:
        group_str = "c(" + ",".join(map(str, groups)) + ")"

    r_script = f'''
    library(xcms)

    xdata <- readRDS("{input_rds}")

    sample_groups <- factor({group_str})

    xdata <- groupChromPeaks(
    xdata,
    param = PeakDensityParam(
        sampleGroups = sample_groups,
        bw = {bw},
        minFraction = {min_fraction},
        minSamples = {min_samples}
    )
    )

    saveRDS(xdata, "{output_rds}")
    '''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        os.unlink(r_file)


# ============================= OpenMS-PeakGroup 实现 =============================
def group_peaks_openms_PeakGroup_impl(input_rds: str, output_rds: str) -> str:
    r_script = f'''
    library(OpenMS)
    library(data.table)

    # 读取已完成峰检测、冗余过滤、同位素识别的特征表
    feat_data <- readRDS("{input_rds}")

    # 转换为 OpenMS 标准格式
    features <- data.table(
      id = 1:nrow(feat_data),
      mz = feat_data$mz,
      rt = feat_data$rt,
      intensity = feat_data$intensity
    )

    # OpenMS PeakGroupFinder 谱峰分组 + 保留时间对齐（核心）
    # 基于 m/z + RT 聚类对齐，多样品自动组间对齐
    aligned_result <- peakGroupFinder(
      features = features,
      mz_tol = 0.01,        # 质量容差
      rt_tol = 10,          # 保留时间容差（秒）
      charge = 1,           # 电荷数
      verbose = TRUE
    )

    # 保存对齐后的结果
    saveRDS(aligned_result, "{output_rds}")
    '''

    # 临时 R 脚本执行
    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        os.unlink(r_file)
