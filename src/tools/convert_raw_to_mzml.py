import os
from pathlib import Path
import subprocess


# ============================= ThermoRawFileParser 实现 =============================
import glob

def convert_raw_to_mzml_ThermoRawFileParser_impl(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    
    for raw in glob.glob(os.path.join(input_dir, "*.raw")):
        cmd = [
            "ThermoRawFileParser",
            "-i", raw,
            "-o", output_dir,
            "-f", "mzML"
        ]
        subprocess.run(cmd, check=True)


# ============================= msconvert 实现 =============================
def convert_raw_to_mzml_msconvert_impl(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)
    
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".raw"):
            name = os.path.splitext(filename)[0]  # 去掉后缀
            print(f"正在转换: {filename} -> {name}.mzML")
            
            # 拼接 Docker 命令
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

            subprocess.run(docker_cmd)


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
        subprocess.run(["Rscript", r_file], check=True)
    finally:
        os.unlink(r_file)
