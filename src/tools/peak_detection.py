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
    result_file = os.path.join(output_dir, "peak_detection_result.rds")

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
    saveRDS(xdata, "{result_file}")
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
    result_file = os.path.join(output_dir, "peak_detection_result.csv")

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
