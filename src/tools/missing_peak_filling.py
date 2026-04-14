import tempfile
import subprocess
import os


# ============================= XCMS-fillChromPeaks 实现 =============================
def fill_missing_peaks_xcms_fillChromPeaks_impl(
    input_rds: str,
    output_rds: str,
    expand_rt: float = 0.0,
    expand_mz: float = 0.0
) -> str:

    r_script = f'''
    library(xcms)

    xdata <- readRDS("{input_rds}")

    param <- FillChromPeaksParam(
        expandRt = {expand_rt},
        expandMz = {expand_mz}
    )

    xdata <- fillChromPeaks(
    xdata,
    param = param
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
