import os
import subprocess
import tempfile


# ============================= XCMS-Obiwarp 实现 =============================
def align_retention_time_obiwarp_impl(input_rds: str, output_rds: str) -> str:
    r_script = f'''
    library(xcms)

    xdata <- readRDS("{input_rds}")

    # Obiwarp 对齐
    xdata <- adjustRtime(
        xdata,
        param = ObiwarpParam()
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


# ============================= XCMS-LOESS 实现 =============================
def align_retention_time_loess_impl(input_rds: str, output_rds: str) -> str:
    r_script = f'''
    library(xcms)

    xdata <- readRDS("{input_rds}")

    # LOESS 校正
    xdata <- adjustRtime(
        xdata,
        param = PeakGroupsParam()
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
