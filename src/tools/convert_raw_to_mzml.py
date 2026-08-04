# 数据转换
# 涉及到的工具：“Wizard", "ThermoRawFileParser", "msconvert", "OpenMS FileConverter",

import os                       # 操作系统接口：用于创建目录、路径拼接等
from pathlib import Path        # 面向对象的文件系统路径操作（虽然 import 了但未直接使用）
import subprocess               # 子进程管理：用于调用外部命令行工具
from typing import List, Optional    # 类型提示：用于批量转换等函数的参数类型标注

# ============================= Docker 镜像配置 =============================
# ProteoWizard msconvert 的 Docker 镜像，通过 Wine 在 Linux 上运行 Windows 版 msconvert.exe
# 使用显式 latest tag 并在首次使用前验证镜像存在，确保可复现性
_MSCONVERT_DOCKER_IMAGE = "chambm/pwiz-skyline-i-agree-to-the-vendor-licenses:latest"

# 镜像验证缓存：同一进程内只检查一次
_docker_image_verified = False


def _verify_docker_image(image: str = _MSCONVERT_DOCKER_IMAGE) -> bool:
    """验证 Docker 镜像是否存在，不存在则尝试拉取。

    同一进程内只执行一次验证（通过 _docker_image_verified 缓存）。
    这是防御性检查：如果在新机器上首次运行且镜像未提前拉取，
    自动 docker pull 比让 docker run 隐式拉取更可控
    （能打印清晰的进度信息，而不是让首次转换超时）。

    Returns:
        bool: 镜像验证成功返回 True，失败返回 False。
    """
    global _docker_image_verified
    if _docker_image_verified:
        return True

    # 检查镜像是否已存在
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        _docker_image_verified = True
        return True

    # 镜像不存在，尝试拉取
    print(f"🐳 Docker 镜像 {image} 不存在，正在拉取...")
    try:
        subprocess.run(["docker", "pull", image], check=True)
        print(f"✅ Docker 镜像拉取成功: {image}")
        _docker_image_verified = True
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker 镜像拉取失败: {e}")
        print(f"   请手动执行: docker pull {image}")
        return False
    except FileNotFoundError:
        print("❌ 未找到 docker 命令，请确认 Docker 已安装并在 PATH 中。")
        return False


# ============================= ThermoRawFileParser 实现 =============================
import glob                     # Unix 风格的文件名模式匹配，用于查找所有 .raw 文件

# ThermoRawFileParser
def convert_raw_to_mzml_ThermoRawFileParser_impl(input_dir: str, output_dir: str):
    """
    使用 ThermoRawFileParser 命令行工具，将 input_dir 下所有 .raw 文件批量转换为 .mzML 格式。
    ThermoRawFileParser 是 Thermo Fisher 官方推荐的跨平台转换工具。
    """
    os.makedirs(output_dir, exist_ok=True)
    output_abs = os.path.abspath(output_dir)

    raw_files = glob.glob(os.path.join(input_dir, "*.raw"))

    print(f"\nUsing data conversion tool: ThermoRawFileParser")
    print(f"Input format: .raw     |     Output format: mzML")

    success_count = 0
    failed_files = []

    for raw in raw_files:
        filename = os.path.basename(raw)
        name = os.path.splitext(filename)[0]
        print(f"Converting: {filename} -> {name}.mzML", end="")

        cmd = [
            "ThermoRawFileParser",
            "-i", raw,
            "-o", output_dir,
            "-f", "mzML"
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"     ✅ Success")
            success_count += 1
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() if e.stderr else str(e)
            print(f"     ❌ Failed: {err_msg}")
            failed_files.append(filename)

    print(f"Conversion complete:     Success: {success_count}/{len(raw_files)}")
    if failed_files:
        print(f"  Failed files: {', '.join(failed_files)}")
    print(f"Output directory: {output_abs}")


# ============================= msconvert 实现 =============================
# msconvert
def convert_raw_to_mzml_msconvert_impl(input_dir: str, output_dir: str):
    """
    通过 Docker 容器运行 ProteoWizard 的 msconvert.exe（通过 Wine），
    将 input_dir 下所有 .raw 文件转换为 .mzML 格式。
    这是最通用的方案，支持几乎所有质谱厂商的 .raw 格式。
    """
    os.makedirs(output_dir, exist_ok=True)
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)

    # 验证 Docker 镜像可用（首次调用时拉取）
    if not _verify_docker_image():
        raise RuntimeError(
            f"Docker 镜像 {_MSCONVERT_DOCKER_IMAGE} 不可用，无法执行 msconvert 转换。"
        )

    # 收集所有匹配的输入文件
    input_files = [f for f in os.listdir(input_dir) if f.lower().endswith(".raw")]

    print(f"\nUsing data conversion tool: msconvert")
    print(f"Input format: .raw     |     Output format: mzML")

    success_count = 0
    failed_files = []

    for filename in input_files:
        name = os.path.splitext(filename)[0]
        print(f"Converting: {filename} -> {name}.mzML", end="")

        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{input_abs}:/data",
            "-v", f"{output_abs}:/output",
            _MSCONVERT_DOCKER_IMAGE,
            "wine", "msconvert.exe",
            f"/data/{name}.raw",
            "--mzML", "--64",
            "--filter", "peakPicking vendor msLevel=1-",
            "-o", "/output",
            "--outfile", f"/output/{name}.mzML"
        ]

        try:
            subprocess.run(docker_cmd, capture_output=True, check=True)
            print(f"     ✅ Success")
            success_count += 1
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() if e.stderr else str(e)
            print(f"     ❌ Failed: {err_msg}")
            failed_files.append(filename)

    print(f"Conversion complete:     Success: {success_count}/{len(input_files)}")
    if failed_files:
        print(f"  Failed files: {', '.join(failed_files)}")
    print(f"Output directory: {output_abs}")


# ============================= OpenMS FileConverter 实现 =============================
# OpenMS FileConverter
def convert_raw_to_mzml_OpenMS_FileConverter_impl(
    input_dir: str,
    output_dir: str,
    input_format: str = ".mzML",
    output_format: str = "mzXML",
    openms_path: str = "",
):
    """
    使用 OpenMS 的 FileConverter 工具，将 input_dir 下所有指定格式的文件批量转换为目标格式。
    支持 mzML/mzXML/mgf 等格式互转。输出文件名与输入文件名保持一致（仅扩展名不同）。

    适用于需要将 OpenMS 集成到代谢组学数据处理工作流中的场景。
    与项目中其他 OpenMS 工具（peak_picking_openms_impl 等）保持一致的调用方式。

    Parameters
    ----------
    input_dir : str
        包含待转换文件的输入目录。
    output_dir : str
        转换后文件的输出目录。
    input_format : str, default=".mzML"
        输入文件的扩展名（大小写不敏感），如 ".mzML"、".mzXML"、".mgf"。
    output_format : str, default="mzXML"
        输出格式（不含点号），如 "mzML"、"mzXML"、"mgf"。
    openms_path : str, default=""
        OpenMS 可执行文件目录。留空则从系统 PATH 查找。
    """

    os.makedirs(output_dir, exist_ok=True)
    output_abs = os.path.abspath(output_dir)

    # 构建 FileConverter 路径
    fileconverter_bin = os.path.join(openms_path, "FileConverter") if openms_path else "FileConverter"

    # 收集所有匹配的输入文件
    input_files = [f for f in os.listdir(input_dir) if f.lower().endswith(input_format.lower())]

    print(f"\nUsing data conversion tool: OpenMS FileConverter")
    print(f"Input format: {input_format}     |     Output format: {output_format}")

    success_count = 0
    failed_files = []

    for filename in input_files:
        name = os.path.splitext(filename)[0]
        input_file = os.path.join(input_dir, filename)
        output_file = os.path.join(output_dir, f"{name}.{output_format}")

        print(f"正在转换: {filename} -> {name}.{output_format}", end="")

        cmd = [fileconverter_bin, "-in", input_file, "-out", output_file]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"     ✅ Success")
            success_count += 1
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() if e.stderr else str(e)
            print(f"     ❌ Failed: {err_msg}")
            failed_files.append(filename)

    print(f"Conversion complete:     Success: {success_count}/{len(input_files)}")
    if failed_files:
        print(f"  Failed files: {', '.join(failed_files)}")
    print(f"Output directory: {output_abs}")


# ============================= ProteoWizard 数据转换 =============================
# ProteoWizard 数据转换工具 —— 质谱原始数据 → 开放格式的完整转换管道
# 基于 ProteoWizard 套件（msconvert）实现：格式转换、峰拾取、谱图过滤、压缩优化
# 通过 Docker 容器运行（chambm/pwiz-skyline-i-agree-to-the-vendor-licenses）
def data_transformation_proteowizard_impl(
    input_dir: str,
    output_dir: str,
    input_format: str = ".raw",
    output_format: str = "mzML",
    peak_picking: bool = True,
    peak_picking_algorithm: str = "vendor",
    peak_picking_ms_level: str = "1-",
    ms_level: Optional[str] = None,
    mz_range: Optional[str] = None,
    compression: bool = False,
    zlib_compression: bool = False,
    precision_64: bool = True,
    combine_spectra: bool = False,
    scan_summing: bool = False,
    scan_summing_precursor_tol: float = 0.01,
    scan_summing_rt_tol: float = 1.0,
    sim_as_spectra: bool = True,
    srfilter: Optional[str] = None,
    file_pattern: str = "*",
    parallel: bool = False,
    n_cores: Optional[int] = None,
):
    """
    使用 ProteoWizard (msconvert) 对质谱原始数据进行完整的数据转换管道，
    支持格式转换、峰拾取（质心化）、谱图过滤和压缩优化。

    ProteoWizard 是代谢组学领域最通用的质谱数据转换工具，
    支持几乎所有主流质谱厂商的原始格式：Thermo (.raw)、Agilent (.d)、
    Bruker (.d)、AB Sciex (.wiff)、Waters (.raw) 等。

    Parameters
    ----------
    input_dir : str
        包含质谱原始文件的输入目录。
    output_dir : str
        转换后文件的输出目录。
    input_format : str, default=".raw"
        输入文件的扩展名（大小写不敏感），如 ".raw"、".d"、".wiff"。
    output_format : str, default="mzML"
        输出格式，可选: "mzML", "mzXML", "MGF", "mz5", "ms2", "ms1"。
    peak_picking : bool, default=True
        是否执行峰拾取（将 profile 模式转换为 centroid 模式）。
    peak_picking_algorithm : str, default="vendor"
        峰拾取算法: "vendor"（厂商算法，推荐）, "cwt"（连续小波变换）,
        "wavelet"（小波）, "sliding_window"（滑动窗口）。
    peak_picking_ms_level : str, default="1-"
        峰拾取的 MS 级别，默认 "1-" 表示 MS1 及以上。
        如只做 MS2 峰拾取: "2-"，MS1 和 MS2 都做: "1-2"。
    ms_level : str, optional
        保留的 MS 级别过滤，如 "1"（仅 MS1）、"1-2"（MS1 和 MS2）。
        不指定则保留全部。
    mz_range : str, optional
        m/z 范围过滤，格式为 "min-max"，如 "100-1500"。
    compression : bool, default=False
        是否使用二进制压缩减少输出文件大小（对 mzML/mzXML 有效）。
        注意：启用后部分下游工具可能无法直接读取。
    zlib_compression : bool, default=False
        是否使用 zlib 压缩（比 binary 压缩略大但兼容性更好）。
    precision_64 : bool, default=True
        是否使用 64 位精度存储 m/z 和强度值。
        False 则使用 32 位精度（文件更小但精度降低）。
    combine_spectra : bool, default=False
        是否将同一前体离子的多次扫描合并为一张谱图。
    scan_summing : bool, default=False
        是否对同一前体离子的 MS2 扫描进行加和（提高信噪比）。
    scan_summing_precursor_tol : float, default=0.01
        扫描加和的前体离子 m/z 容差（Da）。
    scan_summing_rt_tol : float, default=1.0
        扫描加和的保留时间容差（秒）。
    sim_as_spectra : bool, default=True
        是否将 SIM 扫描作为谱图而非色谱图输出。
    srfilter : str, optional
        谱图级别过滤器，如 "activation HCD"（仅保留 HCD 碎裂的谱图）、
        "positiveScan"（仅正离子模式）。
    file_pattern : str, default="*"
        文件名匹配模式，用于筛选输入文件。
    parallel : bool, default=False
        是否并行处理多个文件（实验性功能）。
    n_cores : int, optional
        并行处理时使用的 CPU 核心数。None 则使用所有可用核心。
    """

    print(f"\nUsing data conversion tool: ProteoWizard")
    print(f"Input format: {input_format}     |     Output format: {output_format}")

    os.makedirs(output_dir, exist_ok=True)
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)

    # 验证 Docker 镜像可用（首次调用时拉取）
    if not _verify_docker_image():
        raise RuntimeError(
            f"Docker 镜像 {_MSCONVERT_DOCKER_IMAGE} 不可用，无法执行 ProteoWizard 转换。"
        )

    # 收集所有匹配的输入文件
    input_files = []
    for f in os.listdir(input_dir):
        if f.lower().endswith(input_format.lower()):
            input_files.append(f)

    if not input_files:
        raise FileNotFoundError(
            f"输入目录 {input_dir} 中未找到 {input_format} 格式的文件"
        )

    if n_cores is None:
        n_cores = max(1, os.cpu_count() - 1)

    # 构建 msconvert 通用过滤参数
    filters = []

    # 峰拾取过滤器
    if peak_picking:
        if peak_picking_algorithm == "vendor":
            filters.append(f"peakPicking vendor msLevel={peak_picking_ms_level}")
        elif peak_picking_algorithm == "cwt":
            filters.append(f"peakPicking cwt msLevel={peak_picking_ms_level}")
        else:
            filters.append(f"peakPicking {peak_picking_algorithm} msLevel={peak_picking_ms_level}")

    # MS 级别过滤
    if ms_level:
        filters.append(f"msLevel {ms_level}")

    # m/z 范围过滤
    if mz_range:
        filters.append(f"mzWindow [{mz_range}]")

    # 扫描加和
    if scan_summing:
        filters.append(
            f"scanSumming precursorTol={scan_summing_precursor_tol} "
            f"rtTol={scan_summing_rt_tol}"
        )

    # 谱图级别过滤
    if srfilter:
        filters.append(f"srfilter {srfilter}")

    # 构建输出格式参数列表
    format_args = []
    if output_format == "mzML":
        format_args = ["--mzML"]
    elif output_format == "mzXML":
        format_args = ["--mzXML"]
    elif output_format == "MGF":
        format_args = ["--mgf"]
    elif output_format == "mz5":
        format_args = ["--mz5"]
    elif output_format == "ms2":
        format_args = ["--ms2"]
    elif output_format == "ms1":
        format_args = ["--ms1"]

    # 精度和压缩选项（仅对 XML 格式有效）
    if precision_64 and output_format in ("mzML", "mzXML"):
        format_args.append("--64")
    else:
        format_args.append("--32")

    if compression and output_format in ("mzML", "mzXML"):
        format_args.append("--compress")
    if zlib_compression and output_format in ("mzML", "mzXML"):
        format_args.append("--zlib")

    # SIM 谱图处理
    if sim_as_spectra:
        format_args.append("--simAsSpectra")

    # 谱图合并
    if combine_spectra:
        format_args.append("--combineIonMobilitySpectra")

    # 逐文件转换
    success_count = 0
    failed_files = []

    for filename in input_files:
        name = os.path.splitext(filename)[0]
        output_file = f"{name}.{output_format if output_format != 'MGF' else 'mgf'}"

        print(f"Converting: {filename} -> {output_file}", end="")

        # 构建完整的 Docker 命令
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{input_abs}:/data",
            "-v", f"{output_abs}:/output",
            _MSCONVERT_DOCKER_IMAGE,
            "wine", "msconvert.exe",
            f"/data/{filename}",
            "-o", "/output",
            "--outfile", f"/output/{output_file}",
        ]

        # 添加输出格式参数
        docker_cmd.extend(format_args)

        # 添加所有过滤器
        for f in filters:
            docker_cmd.extend(["--filter", f])

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                encoding='utf-8',
                timeout=600  # 大文件转换可能需要较长时间
            )

            if result.returncode == 0:
                print(f"     ✅ Success")
                success_count += 1
            else:
                print(f"     ❌ Failed: {result.stderr.strip()}")
                failed_files.append(filename)

        except subprocess.TimeoutExpired:
            print(f"     ⏱️ Timeout")
            failed_files.append(filename)
        except Exception as e:
            print(f"     ❌ Error: {str(e)}")
            failed_files.append(filename)

    # 汇总报告
    print(f"Conversion complete:     Success: {success_count}/{len(input_files)}")
    if failed_files:
        print(f"  Failed files: {', '.join(failed_files)}")
    print(f"Output directory: {output_abs}")

def data_transformation_proteowizard_batch_impl(
    input_dirs: List[str],
    output_base_dir: str,
    input_format: str = ".raw",
    output_format: str = "mzML",
    peak_picking: bool = True,
    peak_picking_algorithm: str = "vendor",
    peak_picking_ms_level: str = "1-",
    **kwargs,
):
    """
    批量数据转换：对多个输入目录分别执行 ProteoWizard 转换管道。

    每个输入目录的结果将保存在 output_base_dir 下同名的子目录中。

    Parameters
    ----------
    input_dirs : list of str
        多个输入目录的路径列表。
    output_base_dir : str
        输出根目录，每个输入目录的结果会保存在对应的子目录中。
    input_format : str, default=".raw"
        输入文件格式扩展名。
    output_format : str, default="mzML"
        输出格式。
    peak_picking : bool, default=True
        是否执行峰拾取。
    peak_picking_algorithm : str, default="vendor"
        峰拾取算法。
    peak_picking_ms_level : str, default="1-"
        峰拾取的 MS 级别。
    **kwargs
        传递给 data_transformation_proteowizard_impl 的其他参数。
    """

    print(f"\nUsing data conversion tool: ProteoWizard Batch")
    print(f"Input format: {input_format}     |     Output format: {output_format}")
    print(f"Batch converting {len(input_dirs)} directories")

    for i, input_dir in enumerate(input_dirs, 1):
        dir_name = os.path.basename(input_dir.rstrip('/')) or f"batch_{i}"
        output_dir = os.path.join(output_base_dir, dir_name)

        print(f"\n{'='*60}")
        print(f"[{i}/{len(input_dirs)}] 处理: {input_dir}")
        print(f"  输出: {output_dir}")
        print(f"{'='*60}")

        try:
            data_transformation_proteowizard_impl(
                input_dir=input_dir,
                output_dir=output_dir,
                input_format=input_format,
                output_format=output_format,
                peak_picking=peak_picking,
                peak_picking_algorithm=peak_picking_algorithm,
                peak_picking_ms_level=peak_picking_ms_level,
                **kwargs,
            )
        except Exception as e:
            print(f"  ❌ 目录处理失败: {str(e)}")

    print(f"\n批量转换完成")


if __name__ == "__main__":
    raw_base = "/data2/luxiang/MOA/inputspace/raw"
    mzml_base = "/data2/luxiang/MOA/outputspace/data_conversion"

    # ThermoRawFileParser: 批量转换 .raw -> .mzML（Thermo 专用）
    convert_raw_to_mzml_ThermoRawFileParser_impl(
        input_dir=f"{raw_base}",
        output_dir=f"{mzml_base}/mzml_thermo"
    )

    # msconvert: 批量转换 .raw -> .mzML（通用，通过 Docker 运行）
    convert_raw_to_mzml_msconvert_impl(
        input_dir=f"{raw_base}",
        output_dir=f"{mzml_base}/mzml_msconvert"
    )

    # OpenMS FileConverter: 批量格式互转（需先安装 openms: conda install -c conda-forge openms）
    convert_raw_to_mzml_OpenMS_FileConverter_impl(
        input_dir=f"{mzml_base}/mzml_msconvert",
        output_dir=f"{mzml_base}/mzml_openms",
        input_format=".mzML",
        output_format="mzXML",
    )

    # ProteoWizard 完整转换管道（峰拾取 + 过滤 + 压缩）
    data_transformation_proteowizard_impl(
        input_dir=f"{raw_base}",
        output_dir=f"{mzml_base}/mzml_proteowizard",
        input_format=".raw",
        output_format="mzML",
        peak_picking=True,
        peak_picking_algorithm="vendor",
        peak_picking_ms_level="1-",
        ms_level="1-",
        precision_64=True,
    )

    # ProteoWizard 批量转换多个目录
    data_transformation_proteowizard_batch_impl(
        input_dirs=[f"{raw_base}"],
        output_base_dir=f"{mzml_base}/batch_converted",
        input_format=".raw",
        output_format="mzML",
        peak_picking=True,
    )

    # 默认执行：msconvert 批量转换 .raw -> .mzML
    convert_raw_to_mzml_msconvert_impl(
        input_dir=f"{raw_base}",
        output_dir=f"{mzml_base}/mzml_msconvert"
    )