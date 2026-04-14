import os
import subprocess
import tempfile


# ============================= XCMS-groupChromPeaks 实现 =============================
def group_peaks_xcms_groupChromPeaks_impl(
    input_rds: str,
    output_rds: str,
    bw: int = 30,
    min_fraction: float = 0.5,
    min_samples: int = 1,
    groups: list = None
) -> str:

    if groups is None:
        group_str = "rep(1, length(fileNames(xdata)))"
    else:
        group_str = "c(" + ",".join(map(str, groups)) + ")"

    r_script = f'''
    library(xcms)

    xdata <- readRDS("{input_rds}")

    sample_groups <- factor({group_str})

    xdata <- groupChromPeaks(
    xdata,
    param = PeakDensityParam(
        sampleGroups = sample_groups,
        bw = {bw},
        minFraction = {min_fraction},
        minSamples = {min_samples}
    )
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
