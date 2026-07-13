import os
import subprocess
import tempfile

from src.platform_utils import normalize_display_path, resolve_rscript
from src.tools._mcp_io import tool_log


def _run_rscript(r_file: str, label: str = "peak_detection", log_dir: str | None = None) -> str:
    """
    运行 R 脚本。输出写入日志文件，避免写入 stdout：
    - 直接运行时 stdout 是终端，一般无妨
    - Agent/MCP 子进程中 stdout 是 JSON-RPC 管道，R 大量输出会导致阻塞或协议损坏
    """
    log_dir = log_dir or tempfile.gettempdir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{label}.log")

    tool_log(f"[{label}] start Rscript: {r_file}", log_path)
    tool_log(f"[{label}] R log file: {log_path}", log_path)

    with open(log_path, "w", encoding="utf-8") as log:
        result = subprocess.run(
            [resolve_rscript(), r_file],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if result.returncode != 0:
        with open(log_path, encoding="utf-8") as f:
            tail = f.read()[-4000:]
        raise RuntimeError(
            f"Rscript 失败，退出码 {result.returncode}\n日志: {log_path}\n{tail}"
        )
    tool_log(f"[{label}] Rscript finished: {log_path}", log_path)
    return log_path


def _r_path(path: str) -> str:
    """路径转为 R 可识别的正斜杠绝对路径。"""
    return normalize_display_path(path)


# ProteoWizard 新版写入的 CV 项，旧版 mzR 无法识别（见 mzR#229）
_MZR_CV_REPLACEMENTS = {
    'accession="MS:1002993" name="Q Exactive Focus"': 'accession="MS:1001911" name="Q Exactive"',
}


def _sanitize_mzml_for_mzr(input_dir: str) -> int:
    """修复 msconvert 新版 mzML 中 mzR 不支持的 cvParam，返回处理文件数。"""
    fixed = 0
    for name in os.listdir(input_dir):
        if not name.lower().endswith(".mzml"):
            continue
        path = os.path.join(input_dir, name)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        new_content = content
        for old, new in _MZR_CV_REPLACEMENTS.items():
            new_content = new_content.replace(old, new)
        if new_content != content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            fixed += 1
            tool_log(f"[peak_detection] patched mzML cvParam: {path}")
    return fixed


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
    _sanitize_mzml_for_mzr(input_dir)
    result_rds = os.path.join(output_dir, "XCMS-centwave_peak_detection_result.rds")
    result_csv = os.path.join(output_dir, "XCMS-centwave_peak_detection_result.csv")
    input_r = _r_path(input_dir)
    rds_r = _r_path(result_rds)
    csv_r = _r_path(result_csv)
    # 使用 Sys.glob 避免 list.files 正则中反斜杠转义问题（Windows 路径）

    r_script = f'''
library(xcms)
library(MSnbase)

mzml_files <- Sys.glob(file.path("{input_r}", "*.mzML"))
if (length(mzml_files) == 0) {{
    mzml_files <- Sys.glob(file.path("{input_r}", "*.mzml"))
}}
if (length(mzml_files) == 0) {{
    stop("未找到 mzML 文件: {input_r}")
}}
cat("找到", length(mzml_files), "个 mzML 文件\\n")

xdata <- MSnbase::readMSData(mzml_files, mode = "onDisk")
cat("读取完成，开始 CentWave 峰检测...\\n")

xdata <- findChromPeaks(
    xdata,
    param = CentWaveParam(
        peakwidth = c({peakwidth_min}, {peakwidth_max}),
        snthresh = {snthresh},
        ppm = {ppm},
        prefilter = c({prefilter_n}, {prefilter_intensity})
    )
)

saveRDS(xdata, "{rds_r}")
peak_table <- chromPeaks(xdata)
write.csv(peak_table, "{csv_r}", row.names = TRUE)
cat("峰检测完成，已保存 RDS 与 CSV\\n")
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".R", delete=False, encoding="utf-8") as f:
        f.write(r_script)
        r_file = f.name

    try:
        log_path = _run_rscript(r_file, label="peak_detection_xcms_centwave", log_dir=output_dir)
        if not os.path.isfile(result_rds):
            raise RuntimeError(f"未生成结果文件: {result_rds}")
        return f"峰检测完成: {result_rds}, {result_csv}，日志: {log_path}"
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
    mzml_files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith(".mzml")
    )
    if not mzml_files:
        raise FileNotFoundError(f"未找到 mzML 文件: {input_dir}")
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
        _run_rscript(r_file, label="peak_detection_kpic")
        return f"峰检测完成: {result_rds}, {result_csv}"
    finally:
        os.unlink(r_file)


# ============================= ms-peakonly 实现 =============================
from glob import glob
try:
    from ms_peakonly import PeakOnly
except ModuleNotFoundError:
    PeakOnly = None


def peak_detection_peakonly_impl(
    input_dir: str,
    output_dir: str,
    file_pattern: str = "*.mzML",
    model_dir: str = "workspace/models/"
) -> str:
    """
    使用 PeakOnly 进行峰检测，并保存结果为 CSV 文件
    """
    if PeakOnly is None:
        raise ModuleNotFoundError(
            "缺少 ms_peakonly 依赖，无法执行 peak_detection_peakonly_impl。"
            "你可以先只做库匹配（library_match_*）的流程，或安装 ms-peakonly 以启用该工具。"
        )

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
