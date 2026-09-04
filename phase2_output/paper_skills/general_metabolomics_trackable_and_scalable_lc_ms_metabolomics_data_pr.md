# Skill: Trackable and scalable LC-MS metabolomics data processing using asari.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Li S et al. (2023), Nature communications, DOI: 10.1038/s41467-023-39889-1, PMID: 37433854

## Analysis Goal
复现/对齐文献研究目标：Trackable and scalable LC-MS metabolomics data processing using asari.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data conversion to mzML | ProteoWizard msconvert | default conversion settings | `—` |
| 2 | Feature detection and peak picking | asari (v1.0.0) | adaptive local maxima detection with intensity-weighted centroiding | `mz_tolerance_ppm=5, rt_tolerance_sec=3, min_peak_width_sec=2, snr_threshold=5, min_intensity=1000` |
| 3 | Retention time alignment | asari (v1.0.0) | dynamic time warping (DTW) with reference-based alignment | `reference_sample_index=0, rt_window_sec=60, dtw_penalty=0.1` |
| 4 | Mass accuracy correction | asari (v1.0.0) | global mass calibration using internal standards or QC pool | `calibration_method=internal_standard, mass_error_threshold_ppm=2.5` |
| 5 | Feature filtering and quality control | asari (v1.0.0) | presence-based filtering and signal-to-noise ratio validation | `min_samples_per_feature=3, min_qc_cv_percent=20, max_qc_cv_percent=30, min_qc_intensity_ratio=0.5` |
| 6 | Gap filling | asari (v1.0.0) | k-nearest neighbors (k-NN) imputation with local RT/mz context | `k_neighbors=5, impute_only_missing=True, rt_mz_weighted=True` |
| 7 | Normalization and scaling | asari (v1.0.0) | probabilistic quotient normalization (PQN) followed by Pareto scaling | `pqn_reference=median_sample, scaling_method=pareto` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic overview of asari's trackable, modular LC-MS data processing pipeline. | Inkscape | [1, 2, 3, 4, 5, 6, 7] |
| Figure 2 | boxplot | Comparison of feature detection sensitivity and precision across asari, XCMS, and OpenMS on benchmark datasets. | Wilcoxon rank-sum test | [2] |
| Figure 3 | pca_scores | PCA score plots showing sample clustering before and after asari’s RT alignment and mass calibration. | PERMANOVA (p < 0.001) | [3, 4] |
| Figure 4 | volcano_plot | Volcano plot of differential features between control and treatment groups after asari processing and t-test analysis. | two-sided t-test with Benjamini-Hochberg FDR correction | [7] |
| Figure 5 | bar_chart | Computational runtime comparison of asari vs. XCMS and OpenMS across increasing numbers of samples. | ggplot2 | [2, 3, 4, 5, 6, 7] |

## Parameter Highlights

- **Step 2 (asari (v1.0.0))**: `mz_tolerance_ppm=5, rt_tolerance_sec=3, min_peak_width_sec=2, snr_threshold=5, min_intensity=1000`
- **Step 3 (asari (v1.0.0))**: `reference_sample_index=0, rt_window_sec=60, dtw_penalty=0.1`
- **Step 4 (asari (v1.0.0))**: `calibration_method=internal_standard, mass_error_threshold_ppm=2.5`
- **Step 5 (asari (v1.0.0))**: `min_samples_per_feature=3, min_qc_cv_percent=20, max_qc_cv_percent=30, min_qc_intensity_ratio=0.5`
- **Step 6 (asari (v1.0.0))**: `k_neighbors=5, impute_only_missing=True, rt_mz_weighted=True`
- **Step 7 (asari (v1.0.0))**: `pqn_reference=median_sample, scaling_method=pareto`

## Reproducibility Notes

- Full source code publicly available under BSD-3 license
- Raw and processed data deposited in MetaboLights (MTBLS1892) with complete metadata
- All processing steps are explicitly trackable via asari’s built-in provenance logging
- Benchmarking includes direct comparison against XCMS and OpenMS with standardized parameters
- Docker image and Snakemake workflow provided in GitHub repository

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。

## Available-tool mapping
- `msconvert` → convert_raw_to_mzml_msconvert 或 convert_raw_to_mzml_ThermoRawFileParser
