import os
import sys
from pathlib import Path
import subprocess

from src.platform_utils import docker_bind_mount, resolve_thermo_rawfile_parser


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ============================= ThermoRawFileParser 实现 =============================
import glob

def convert_raw_to_mzml_ThermoRawFileParser_impl(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    parser = resolve_thermo_rawfile_parser()
    if not parser:
        raise FileNotFoundError(
            "未找到 ThermoRawFileParser。请在 MOA 环境中执行：conda install -c bioconda thermorawfileparser"
        )

    for raw in glob.glob(os.path.join(input_dir, "*.raw")):
        cmd = [
            parser,
            "-i", raw,
            "-o", output_dir,
            "-f", "mzML"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"ThermoRawFileParser 失败 (exit {result.returncode})，文件 {os.path.basename(raw)}。"
                f" 详情: {err[:2000]}"
            )


# ============================= msconvert 实现 =============================
def convert_raw_to_mzml_msconvert_impl(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)
    
    raw_files = [
        f for f in os.listdir(input_dir) if f.lower().endswith(".raw")
    ]
    if not raw_files:
        raise FileNotFoundError(
            f"在 input_dir 中未找到 .raw 文件: {input_abs}"
        )

    input_mount = docker_bind_mount(input_abs)
    output_mount = docker_bind_mount(output_abs)

    for filename in raw_files:
        name = os.path.splitext(filename)[0]
        _log(f"正在转换: {filename} -> {name}.mzML")

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{input_mount}:/data",
            "-v",
            f"{output_mount}:/output",
            "chambm/pwiz-skyline-i-agree-to-the-vendor-licenses",
            "wine",
            "msconvert.exe",
            f"/data/{filename}",
            "--mzML",
            "--64",
            "--filter",
            "peakPicking vendor msLevel=1-",
            "-o",
            "/output",
            "--outfile",
            f"/output/{name}.mzML",
        ]

        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            mzml_out = os.path.join(output_abs, f"{name}.mzML")
            if os.path.isfile(mzml_out):
                try:
                    from web_frontend.backend.xcms_patched_run import (
                        sanitize_mzml_for_msnbase,
                    )

                    sanitize_mzml_for_msnbase(mzml_out)
                except Exception:
                    pass

        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"msconvert 失败 (exit {result.returncode})，文件 {filename}。"
                f" 请确认 Docker Desktop 已启动且可访问数据目录。"
                f" 详情: {err[:2000]}"
            )


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
        subprocess.run(
            ["Rscript", r_file], 
            capture_output=True, 
            check=True
        )
    finally:
        os.unlink(r_file)



if __name__ == "__main__":
    convert_raw_to_mzml_msconvert_impl(
        input_dir="/data2/liuwei/MOA/inputspace/raw1",
        output_dir="/data2/liuwei/MOA/outputspace/mzml1"
    )
    