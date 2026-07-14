# DeepMASS2 深度学习代谢物注释工具
# 通过 Docker 子进程调用 deepmass2_cli.py，对 MGF 文件中的未知谱图进行
# Spec2Vec 语义相似度注释，预测结构相关的代谢物候选化合物。

import os
import csv
import subprocess
import logging

logger = logging.getLogger(__name__)

DEEPMASS_IMAGE = "deepmass2:test"
MODEL_DIR = os.environ.get("DEEPMASS_MODEL_DIR", "/data2/liuwei/MOA/softwares/DeepMASS/model")
DATA_DIR = os.environ.get("DEEPMASS_DATA_DIR", "/data2/liuwei/MOA/softwares/DeepMASS/data")


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

    最终还会生成一个 deepmass_summary.csv 汇总文件，收集每个特征排名第一
    （index=0）的候选化合物。
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

    # Aggregate top-ranked candidate from each feature CSV into a summary file
    _aggregate_top_results(output_abs)


def _aggregate_top_results(output_dir: str):
    """
    汇总每个特征的排名第一（index=0）候选化合物到 deepmass_summary.csv。

    从 output_dir 下每个 CSV 文件中读取 index=0 行（排名最高的候选），
    合并写入 deepmass_summary.csv，列为 Feature_ID + 原有各列。
    """
    output_abs = os.path.abspath(output_dir)
    csv_files = sorted(
        f for f in os.listdir(output_abs)
        if f.endswith(".csv") and f != "deepmass_summary.csv"
    )

    summary_header = [
        "Feature_ID", "Title", "MolecularFormula", "CanonicalSMILES",
        "InChIKey", "Database_IDs", "Formula_Score", "Structure_Score",
        "Consensus_Score", "DeepMASS_raw",
    ]
    summary_rows = []
    skipped = 0

    for fname in csv_files:
        fpath = os.path.join(output_abs, fname)
        with open(fpath, "r", newline="") as fh:
            reader = list(csv.reader(fh))
        if len(reader) < 2:
            skipped += 1
            continue
        top_row = reader[1]  # index=0，排名最高的候选
        feature_id = os.path.splitext(fname)[0]
        summary_rows.append([feature_id] + top_row[1:])

    summary_path = os.path.join(output_abs, "deepmass_summary.csv")
    with open(summary_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(summary_header)
        writer.writerows(summary_rows)

    print(
        f"  Summary → {summary_path} "
        f"({len(summary_rows)} features, {skipped} empty skipped)"
    )
    logger.info(
        f"deepmass_summary.csv written: {len(summary_rows)} features, "
        f"{skipped} empty files skipped"
    )


if __name__ == "__main__":
    base = "/data2/luxiang/MOA/outputspace"

    deepmass_annotation_impl(
        input_dir=f"{base}/statistical_analysis/differential_feature_extraction",
        output_dir=f"{base}/unknown_identification/deepmass_results",
    )
