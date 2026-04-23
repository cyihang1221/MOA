import os
import subprocess
import tempfile


# ============================= XCMS-centwave 实现 =============================
def peak_detection_xcms_centwave_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    peakwidth_min: int = 5,
    peakwidth_max: int = 30,
    snthresh: int = 10,
    ppm: int = 10,
    prefilter_n: int = 3,
    prefilter_intensity: int = 1000
) -> str:

    os.makedirs(output_dir, exist_ok=True)
    result_rds = os.path.join(output_dir, "XCMS-centwave_peak_detection_result.rds")
    result_csv = os.path.join(output_dir, "XCMS-centwave_peak_detection_result.csv")

    # 生成 R 脚本
    r_script = f'''
    library(xcms)
    library(MSnbase)

    # Step1: 读取 mzML 文件
    mzml_files <- list.files(
        path = "{input_dir}",
        pattern = "{file_pattern}",
        full.names = TRUE
    )

    xdata <- MSnbase::readMSData(
        mzml_files,
        mode = "onDisk"
    )

    # Step2: 峰检测
    xdata <- findChromPeaks(
        xdata,
        param = CentWaveParam(
            peakwidth = c({peakwidth_min}, {peakwidth_max}),
            snthresh = {snthresh},
            ppm = {ppm},
            prefilter = c({prefilter_n}, {prefilter_intensity})
        )
    )

    # Step3: 保存结果到指定输出目录
    saveRDS(xdata, "{result_rds}")
    peak_table <- chromPeaks(xdata)
    write.csv(peak_table, "{result_csv}", row.names = TRUE)
    '''

    # 写入临时 R 脚本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    # 运行 R 脚本
    try:
        subprocess.run(
            ['Rscript', r_file],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )

    finally:
        os.unlink(r_file)


# ============================= OpenMS-PeakPickerHiRes 实现 =============================
def peak_detection_openms_peakpickerhires_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    peak_width: float = 0.15,
    snr_threshold: float = 3.0,
    mz_tol_ppm: float = 10.0,
    intensity_threshold: float = 1000.0
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    result_csv = os.path.join(output_dir, "OpenMS-PeakPickerHiRes_peak_detection_result.csv")
    result_featureXML = os.path.join(output_dir, "OpenMS-PeakPickerHiRes_features.featureXML")

    # OpenMS 命令行脚本
    cmd = f'''
    # 峰检测 → 直接输出完整对象 featureXML
    PeakPickerHiRes -in {input_dir}/{file_pattern} -out {result_featureXML} \
      -peak_width {peak_width} \
      -snr {snr_threshold} \
      -mz_tol_ppm {mz_tol_ppm} \
      -intensity_threshold {intensity_threshold}

    # 导出 CSV 峰表
    TextExporter -in {result_featureXML} -out {result_csv}
    '''

    # 写入临时 shell 脚本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(cmd)
        script_file = f.name

    try:
        subprocess.run(
            ['bash', script_file],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
    finally:
        os.unlink(script_file)


# ============================= OpenMS-FeatureFinderMetabo 实现 =============================
def peak_detection_openms_featurefinder_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    mass_error: float = 10.0,        # ppm 质量偏差
    intensity_threshold: float = 1000.0,  # 最小强度
    min_peak_width: float = 0.05,    # 最小峰宽（分钟）
    max_peak_width: float = 0.5,     # 最大峰宽（分钟）
    snr_threshold: float = 3.0       # 信噪比
) -> str:

    os.makedirs(output_dir, exist_ok=True)
    result_csv = os.path.join(output_dir, "OpenMS-FeatureFinderMetabo_peak_detection_result.csv")
    result_featureXML = os.path.join(output_dir, "OpenMS-FeatureFinderMetabo_features.featureXML")

    # 获取第一个 mzML 文件（OpenMS 单文件处理）
    mzml_files = sorted([f for f in os.listdir(input_dir) if f.endswith(".mzML")])
    if not mzml_files:
        raise FileNotFoundError("未找到 mzML 文件")
    input_mzml = os.path.join(input_dir, mzml_files[0])

    # OpenMS FeatureFinderMetabo 命令（代谢组学专用峰检测）
    cmd = f'''
    FeatureFinderMetabo \
      -in "{input_mzml}" \
      -out "{result_featureXML}" \
      -mass_error_ppm {mass_error} \
      -intensity_threshold {intensity_threshold} \
      -min_peak_width {min_peak_width} \
      -max_peak_width {max_peak_width} \
      -snr {snr_threshold}

    # 导出为 CSV 峰表
    TextExporter \
      -in "{result_featureXML}" \
      -out "{result_csv}"
    '''

    # 写入临时脚本
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(cmd)
        script_file = f.name

    # 执行
    try:
        subprocess.run(
            ['bash', script_file],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
    finally:
        os.unlink(script_file)


# ============================= KPIC 实现 =============================
def peak_detection_kpic_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    ppm: float = 10.0,
    peak_width: float = 10.0,
    sn_thresh: float = 3.0,
    min_intensity: float = 1000.0
) -> str:

    os.makedirs(output_dir, exist_ok=True)
    result_rds = os.path.join(output_dir, "KPIC_peak_detection_result.rds")
    result_csv = os.path.join(output_dir, "KPIC_peak_detection_result.csv")

    r_script = f'''
    library(KPIC)
    library(xcms)
    library(MSnbase)

    # 读取 mzML
    mzml_files <- list.files(
        path = "{input_dir}",
        pattern = "{file_pattern}",
        full.names = TRUE
    )

    xdata <- readMSData(mzml_files, mode = "onDisk")

    # KPIC 峰检测
    kpic_res <- KPIC::KPICpick(
        xdata,
        ppm = {ppm},
        peak.width = {peak_width},
        sn.thresh = {sn_thresh},
        min.intensity = {min_intensity}
    )

    # 保存
    saveRDS(kpic_res, "{result_rds}")

    # 导出 CSV
    peak_table <- as.data.frame(kpicRes2chromPeaks(kpic_res))
    write.csv(peak_table, "{result_csv}", row.names = FALSE)
    '''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        subprocess.run(
            ['Rscript', r_file],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
    finally:
        os.unlink(r_file)


# ============================= ms-peakonly 实现 =============================
from glob import glob
from ms_peakonly import PeakOnly


def peak_detection_peakonly_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    model_dir: str = "workspace/models/"
) -> str:
    """
    使用 PeakOnly 进行峰检测，并保存结果为 CSV 文件
    """
    os.makedirs(output_dir, exist_ok=True)
    result_file = os.path.join(output_dir, "peakonly_peak_detection_result.csv")

    # Step1: 获取 mzML 文件列表
    files = glob(os.path.join(input_dir, file_pattern))

    if not files:
        raise ValueError(f"No mzML files found in {input_dir} with pattern {file_pattern}")

    # Step2: 初始化 PeakOnly（首次会自动下载模型）
    po = PeakOnly(model_dir=model_dir)

    # Step3: 进行峰检测
    peaks = po.process(files)

    # Step4: 保存结果
    peaks.to_csv(result_file, index=False)
