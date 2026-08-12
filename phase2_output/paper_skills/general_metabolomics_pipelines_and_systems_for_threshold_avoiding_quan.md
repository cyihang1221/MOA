# Skill: Pipelines and Systems for Threshold-Avoiding Quantification of LC-MS/MS Data.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 89/100
- **source**: Sánchez Brotons A et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c01892, PMID: 34355890

## Analysis Goal
复现/对齐文献研究目标：Pipelines and Systems for Threshold-Avoiding Quantification of LC-MS/MS Data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data conversion to open format | ProteoWizard | msconvert | `32bit=True, filter=['peakPicking true 1-3', 'zeroSampleRate false']` |
| 2 | Retention time alignment | PASTAQ (v1.0.0) | dynamic time warping (DTW) with adaptive windowing | `rt_window=60, rt_step=5, max_shift=120` |
| 3 | Feature detection and quantification (MS1-based) | PASTAQ (v1.0.0) | threshold-avoiding peak integration using adaptive local noise modeling | `min_intensity=1000, min_rt_width=10, max_rt_width=60, mass_tolerance_ppm=5, sn_threshold=3` |
| 4 | Feature linking across runs | PASTAQ (v1.0.0) | consensus feature mapping with RT and m/z tolerance-guided clustering | `rt_tolerance_sec=15, mz_tolerance_ppm=5, min_overlap_runs=2` |
| 5 | Annotation integration from multiple identification engines | PASTAQ (v1.0.0) | evidence-weighted consensus scoring across search engines (e.g., MaxQuant, MSFragger, Comet) | `min_engines=2, score_threshold=0.95, fdr_threshold=0.01` |
| 6 | Quality control plot generation | PASTAQ (v1.0.0) | automated QC metrics computation and visualization | `qc_metrics=['median intensity CV', 'missingness per run', 'RT shift distribution', 'peak width distribution']` |
| 7 | Statistical analysis and differential expression | R (limma) | empirical Bayes moderated t-test | `trend=True, robust=True, adjust_method=BH` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic overview of the PASTAQ pipeline architecture, showing modules for RT alignment, threshold-avoiding quantification, annotation integration, and QC reporting. | Inkscape | [2, 3, 4, 5, 6] |
| Figure 2 | boxplot | Distribution of median intensity CVs across technical replicates for PASTAQ vs. MaxQuant and DIA-NN, demonstrating lower variability with PASTAQ. | Kruskal-Wallis test with Dunn’s post-hoc, p < 0.001 | [7] |
| Figure 3 | volcano_plot | Volcano plot of differential abundance analysis in human serum comparing male vs. female samples, highlighting gender-associated proteins identified by PASTAQ. | limma moderated t-test, FDR < 0.05 | [7] |
| Figure 4 | pca_scores | PCA score plot of PASTAQ-processed serum samples showing clear separation between male and female groups. | PERMANOVA (R² = 0.28, p = 0.002) | [7] |

## Parameter Highlights

- **Step 1 (ProteoWizard)**: `32bit=True, filter=['peakPicking true 1-3', 'zeroSampleRate false']`
- **Step 2 (PASTAQ (v1.0.0))**: `rt_window=60, rt_step=5, max_shift=120`
- **Step 3 (PASTAQ (v1.0.0))**: `min_intensity=1000, min_rt_width=10, max_rt_width=60, mass_tolerance_ppm=5, sn_threshold=3`
- **Step 4 (PASTAQ (v1.0.0))**: `rt_tolerance_sec=15, mz_tolerance_ppm=5, min_overlap_runs=2`
- **Step 5 (PASTAQ (v1.0.0))**: `min_engines=2, score_threshold=0.95, fdr_threshold=0.01`
- **Step 6 (PASTAQ (v1.0.0))**: `qc_metrics=['median intensity CV', 'missingness per run', 'RT shift distribution', 'peak width distribution']`
- **Step 7 (R (limma))**: `trend=True, robust=True, adjust_method=BH`

## Reproducibility Notes

- Full source code publicly available on GitHub under MIT license
- All raw and processed data deposited in PRIDE and MetaboLights with DOIs
- Automated QC plots generated internally reduce manual intervention
- Parameter values fully reported for core PASTAQ steps

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
