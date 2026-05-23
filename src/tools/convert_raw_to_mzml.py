import os
from pathlib import Path
import subprocess
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
