import os
from pathlib import Path
import subprocess
import pymzml


# ============================= ThermoRawFileParser 实现 =============================
import glob


def _run_quiet(cmd: list[str]) -> None:
    """
    以静默方式执行外部命令，避免污染 MCP 的 stdio JSONRPC 通道。
    如执行失败，抛出包含关键 stderr 的异常信息。
    """
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"命令执行失败: {' '.join(cmd)}\n{err}")

def convert_raw_to_mzml_ThermoRawFileParser_impl(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    
    for raw in glob.glob(os.path.join(input_dir, "*.raw")):
        cmd = [
            "ThermoRawFileParser",
            "-i", raw,
            "-o", output_dir,
            "-f", "mzML"
        ]
        _run_quiet(cmd)


# ============================= msconvert 实现 =============================
def convert_raw_to_mzml_msconvert_impl(input_dir: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)
    
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".raw"):
            name = os.path.splitext(filename)[0]  # 去掉后缀
            
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

            _run_quiet(docker_cmd)


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
