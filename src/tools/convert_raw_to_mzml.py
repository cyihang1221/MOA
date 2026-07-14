import os
from pathlib import Path
import subprocess
from typing import List, Optional

import pymzml

from src.tools._mcp_io import tool_log


# ============================= ThermoRawFileParser 实现 =============================
import glob


def _run_quiet(cmd: list[str], log_path: str | None = None) -> None:
    """
    执行外部命令并将输出写入日志文件，避免占用 MCP 的 stdio JSON-RPC 管道。
    """
    if log_path:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as log:
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
    else:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    if result.returncode != 0:
        err = ""
        if log_path and os.path.isfile(log_path):
            with open(log_path, encoding="utf-8") as f:
                err = f.read()[-4000:]
        raise RuntimeError(f"命令执行失败: {' '.join(cmd)}\n{err}")

from src.platform_utils import docker_bind_mount, resolve_thermo_rawfile_parser


def convert_raw_to_mzml_ThermoRawFileParser_impl(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    parser = resolve_thermo_rawfile_parser()
    if not parser:
        raise FileNotFoundError(
            "未找到 ThermoRawFileParser。请先安装：\n"
            "  1) 从 https://github.com/compomics/ThermoRawFileParser/releases 下载 Windows 版，解压后将目录加入 PATH；或\n"
            "  2) conda install -c bioconda thermorawfileparser（Linux 推荐）。\n"
            "若已有 mzML，可跳过本步，将文件放入 converted_mzml 目录。"
        )

    raw_files = glob.glob(os.path.join(input_dir, "*.raw"))
    if not raw_files:
        raise FileNotFoundError(f"输入目录中未找到 .raw 文件: {input_dir}")

    for raw in raw_files:
        cmd = [parser, "-i", raw, "-o", output_dir, "-f", "mzML"]
        _run_quiet(cmd)


def _ensure_docker_running() -> None:
    """确认 Docker 守护进程已启动（Docker Desktop 需在 Windows 上运行）。"""
    result = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "无法连接 Docker 引擎。请先启动 Docker Desktop，等待左下角显示 Running 后再重试。\n"
            f"详情: {(result.stderr or result.stdout or '').strip()}"
        )


# ============================= msconvert 实现 =============================
def convert_raw_to_mzml_msconvert_impl(input_dir: str, output_dir: str):
    _ensure_docker_running()
    os.makedirs(output_dir, exist_ok=True)
    input_abs = docker_bind_mount(input_dir)
    output_abs = docker_bind_mount(output_dir)
    
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".raw"):
            name = os.path.splitext(filename)[0]  # 去掉后缀
            log_path = os.path.join(output_abs, f"msconvert_{name}.log")

            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{input_abs}:/data",
                "-v", f"{output_abs}:/output",
                "chambm/pwiz-skyline-i-agree-to-the-vendor-licenses",
                "wine", "msconvert.exe",
                f"/data/{name}.raw",
                "--mzML", "--64",
                "--filter", "peakPicking vendor msLevel=1-",
                "-o", "/output",
                "--outfile", f"/output/{name}.mzML"
            ]

            tool_log(f"[msconvert] converting {filename}, log: {log_path}")
            _run_quiet(docker_cmd, log_path=log_path)

    # 修复新版 ProteoWizard 写入的 cvParam，避免下游 mzR/xcms 报错
    _sanitize_mzml_dir_for_mzr(output_abs)


def _sanitize_mzml_dir_for_mzr(output_dir: str) -> None:
    """将 MS:1002993 等新版 CV 项替换为 mzR 可识别的旧项。"""
    replacements = {
        'accession="MS:1002993" name="Q Exactive Focus"': 'accession="MS:1001911" name="Q Exactive"',
    }
    for name in os.listdir(output_dir):
        if not name.lower().endswith(".mzml"):
            continue
        path = os.path.join(output_dir, name)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        new_content = content
        for old, new in replacements.items():
            new_content = new_content.replace(old, new)
        if new_content != content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)


# ============================= OpenMS FileConverter 实现 =============================
def convert_raw_to_mzml_OpenMS_FileConverter_impl(
    input_file: str,
    output_file: str
) -> str:

    r_script = f'''
    system("FileConverter -in {input_file} -out {output_file}")
    '''

    import tempfile, subprocess, os

    with tempfile.NamedTemporaryFile(mode='w', suffix='.R', delete=False) as f:
        f.write(r_script)
        r_file = f.name

    try:
        _run_quiet(["Rscript", r_file])
    finally:
        os.unlink(r_file)


# ============================= mzML -> MGF 实现 =============================
def mzml_directory_to_mgf_impl(input_dir: str, output_dir: str, ms_level: int = 2) -> str:
    """
    将目录下所有 .mzML 批量转为 .mgf（每个 mzML 对应一个同名 .mgf）。
    默认只导出 MS2；若某文件无 MS2 则跳过该文件并记录。
    使用 pymzml，不依赖 Docker / OpenMS。
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.is_dir():
        raise NotADirectoryError(f"输入目录不存在或不是目录: {input_dir}")

    mzml_files = sorted(input_path.glob("*.mzML")) + sorted(input_path.glob("*.mzml"))
    if not mzml_files:
        raise FileNotFoundError(f"目录中未找到 .mzML 文件: {input_dir}")

    written = []
    skipped = []

    for mzml_file in mzml_files:
        out_file = output_path / f"{mzml_file.stem}.mgf"
        n_written = 0
        with out_file.open("w", encoding="utf-8") as handle:
            reader = pymzml.run.Reader(str(mzml_file))
            for spec in reader:
                if spec.ms_level != ms_level:
                    continue
                peaks = spec.peaks("raw")
                if peaks is None or len(peaks) == 0:
                    continue
                title = f"{mzml_file.stem}_scan_{spec.ID}"
                handle.write("BEGIN IONS\n")
                handle.write(f"TITLE={title}\n")
                s_prec = getattr(spec, "selected_precursors", None) or []
                if s_prec:
                    pmz = float(s_prec[0]["mz"])
                    charge = int(s_prec[0].get("charge", 1) or 1)
                    handle.write(f"PEPMASS={pmz}\n")
                    handle.write(f"CHARGE={charge}+\n")
                for mz, intensity in peaks:
                    handle.write(f"{float(mz)} {float(intensity)}\n")
                handle.write("END IONS\n")
                n_written += 1

        if n_written == 0:
            skipped.append(mzml_file.name)
            if out_file.exists():
                out_file.unlink()
        else:
            written.append(f"{mzml_file.name} -> {out_file.name} ({n_written} spectra)")

    summary = (
        f"共处理 {len(mzml_files)} 个 mzML，成功写出 {len(written)} 个 mgf。"
        f"\n详情:\n" + "\n".join(written)
    )
    if skipped:
        summary += "\n无 MS2 已跳过: " + ", ".join(skipped)
    return summary


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
            "chambm/pwiz-skyline-i-agree-to-the-vendor-licenses",
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
