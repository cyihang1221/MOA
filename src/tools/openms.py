import os
import subprocess
import tempfile
import glob


# ============================= peak detection =============================
def peak_detection_openms_impl(
    input_dir: str,
    output_dir: str,
    mass_error_ppm: float = 10.0
):
    os.makedirs(output_dir, exist_ok=True)
    mzml_files = sorted([f for f in os.listdir(input_dir) if f.endswith(".mzML")])

    for mzml_file in mzml_files:
        print(f"\nprocess：{mzml_file}")
        input_mzml = os.path.join(input_dir, mzml_file)
        base_name = os.path.splitext(mzml_file)[0]

        centroid_mzml = os.path.join(output_dir, f"{base_name}_centroided.mzML")
        feature_xml = os.path.join(output_dir, f"{base_name}_features.featureXML")

        cmd = f"""
#!/bin/bash
set -e

# 1. 峰拾取（质心化）
PeakPickerHiRes \\
  -in "{input_mzml}" \\
  -out "{centroid_mzml}" \\

# 2. 峰检测
FeatureFinderMetabo \\
  -in "{centroid_mzml}" \\
  -out "{feature_xml}" \\
  -algorithm:mtd:mass_error_ppm {mass_error_ppm}
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(cmd)
            script = f.name

        try:
            subprocess.run(['bash', script], capture_output=True, text=True, encoding='utf-8')
        finally:
            os.unlink(script)


# ============================= align retention time & peak grouping =============================
def align_retention_time_and_peak_grouping_openms_impl(
    input_dir: str,
    output_dir: str,
):
    os.makedirs(output_dir, exist_ok=True)
    import glob

    # 获取所有 featureXML
    feature_files = sorted(glob.glob(os.path.join(input_dir, "*.featureXML")))
    if not feature_files:
        raise FileNotFoundError("未找到 .featureXML 文件")

    # 输出对齐后文件
    aligned_files = [os.path.join(output_dir, os.path.basename(f)) for f in feature_files]
    aligned_consensus = os.path.join(output_dir, "aligned_consensus.consensusXML")

    # 拼接命令
    in_list = " ".join(f'"{f}"' for f in feature_files)
    out_list = " ".join(f'"{f}"' for f in aligned_files)

    cmd = f"""
#!/bin/bash
set -e

# 1. 保留时间校正
MapAlignerPoseClustering \
  -in {in_list} \
  -out {out_list} 

# 2. 峰分组链接（生成统一峰表）
FeatureLinkerUnlabeledQT \
  -in {out_list} \
  -out "{aligned_consensus}"
"""

    # 运行
    print(f"\nis doing：align retention time and peak grouping")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
        f.write(cmd)
        script = f.name

    try:
        proc = subprocess.run(['bash', script], capture_output=True, text=True, encoding='utf-8')
        if proc.returncode != 0:
            raise RuntimeError(f"对齐失败：{proc.stderr}")
    finally:
        os.unlink(script)
