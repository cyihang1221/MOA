# DeepMASS2 深度学习代谢物注释工具
# 通过 Docker 子进程调用 deepmass2_cli.py，对 MGF 文件中的未知谱图进行
# Spec2Vec 语义相似度注释，预测结构相关的代谢物候选化合物。

import os
import subprocess
import logging

logger = logging.getLogger(__name__)

DEEPMASS_IMAGE = "deepmass2:test"
MODEL_DIR = "/data2/liuwei/MOA/softwares/DeepMASS/model"
DATA_DIR = "/data2/liuwei/MOA/softwares/DeepMASS/data"


# DeepMASS
def deepmass_annotation_impl(input_dir: str, output_dir: str):
    """
    使用 DeepMASS2 对差异代谢物谱图进行深度学习注释。

    与 spectral_annotation（基于 GNPS 谱库余弦匹配，仅识别已知化合物）互补，
    本工具通过 Spec2Vec 质谱语义相似度搜索，可为完全未知的化合物预测
    结构相关的候选代谢物。

    Parameters
    ----------
    input_dir : str
        包含 differential_spectra.mgf 文件的目录路径
    output_dir : str
        保存注释结果 CSV 文件的输出目录路径

    Outputs
    -------
    每题谱图生成一个 CSV 文件，包含以下列：
        Title, MolecularFormula, CanonicalSMILES, InChIKey,
        Formula Score, Structure Score, Consensus Score, DeepMASS_raw
    """
    input_abs = os.path.abspath(input_dir)
    output_abs = os.path.abspath(output_dir)
    mgf_file = os.path.join(input_abs, "differential_spectra.mgf")

    if not os.path.isfile(mgf_file):
        raise FileNotFoundError(
            f"Input MGF file not found: {mgf_file}\n"
            f"Please run data_preprocessing_xcms or equivalent first to generate "
            f"differential_spectra.mgf in the input directory."
        )

    os.makedirs(output_abs, exist_ok=True)

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{input_abs}:/input:ro",
        "-v", f"{output_abs}:/output",
        "-v", f"{MODEL_DIR}:/app/model:ro",
        "-v", f"{DATA_DIR}:/app/data:ro",
        "--entrypoint", "python",
        DEEPMASS_IMAGE,
        "deepmass2_cli.py", "/input/differential_spectra.mgf", "/output/",
    ]

    logger.info(f"Running DeepMASS2: {' '.join(cmd)}")
    print(f"\nPerforming DeepMASS2 deep learning annotation...")
    print(f"  Input : {mgf_file}")
    print(f"  Output: {output_abs}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        timeout=3600,  # 1 hour timeout for large files
    )

    # Print stdout for visibility
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, end="")

    if result.returncode != 0:
        raise RuntimeError(
            f"DeepMASS2 failed with exit code {result.returncode}\n"
            f"stderr: {result.stderr}"
        )

    # List generated files
    csv_files = [f for f in os.listdir(output_abs) if f.endswith(".csv")]
    print(f"  Generated {len(csv_files)} annotation CSV(s): {', '.join(csv_files)}")
    logger.info(f"DeepMASS2 completed, {len(csv_files)} CSV(s) generated")

    # Extract the first data record (second line) from each CSV
    # and merge them into a single file with a common header
    merged_path = os.path.join(output_abs, "top1_annotations.csv")
    records = []
    common_header = None

    for csv_file in sorted(csv_files):
        csv_path = os.path.join(output_abs, csv_file)
        with open(csv_path, "r") as f:
            header = f.readline().strip()
            first_record = f.readline().strip()
        if first_record:
            if common_header is None:
                common_header = header
            # Replace first column (0) with feature name (filename without .csv)
            feature_name = os.path.splitext(csv_file)[0]
            parts = first_record.split(",", 1)
            parts[0] = feature_name
            first_record = ",".join(parts)
            records.append(first_record)
            print(f"  {csv_file}: extracted top-1 record")
        else:
            print(f"  {csv_file}: no data records found")

    if common_header and records:
        with open(merged_path, "w") as f:
            f.write(common_header + "\n")
            for record in records:
                f.write(record + "\n")
        print(f"  Merged {len(records)} top-1 records into: {merged_path}")
        logger.info(f"Merged {len(records)} top-1 records into {merged_path}")


if __name__ == "__main__":
    deepmass_annotation_impl(
        input_dir="/data2/liuwei/MOA/outputspace/differential_features",
        output_dir="/data2/liuwei/MOA/outputspace/unknown_identification",
    )
