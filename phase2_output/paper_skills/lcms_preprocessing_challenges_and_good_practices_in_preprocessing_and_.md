# Skill: Challenges and Good Practices in Preprocessing and Normalization of Untargeted DNA Adductomics Data in Exposomics Research.

- **skill_type**: paper_recipe
- **functional_domain**: `lcms_preprocessing`
- **reproducibility_score**: 92/100
- **source**: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712

## Analysis Goal
复现/对齐文献研究目标：Challenges and Good Practices in Preprocessing and Normalization of Untargeted DNA Adductomics Data in Exposomics Research.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | CentWave peak detection | xcms R package v. 4.3.4 | centWave | `ppm=5, peakwidth=[4,30], peakwidth=[1,25], snthresh=10, integrate=TRUE, extendLengthMSW=TRUE, firstBaselineCheck=TRUE` |
| 2 | Retention time alignment (ENVIRONAGE) | xcms R package v. 4.3.4 | OBI-Warp | `binSize=0.01, centerSample=1` |
| 3 | Retention time alignment (ESCCAPE) | xcms R package v. 4.3.4 | PeakGroups | `anchor_peaks=[13C3]-M1-G,[13C,15N2]-Cro-dG,O6-[d3]-Me-dG` |
| 4 | Feature grouping | xcms R package v. 4.3.4 | PeakDensity | `bw=2, minFraction=0.1, minFraction=0.05, ppm=5, binSize=0.01` |
| 5 | Gap filling | xcms R package v. 4.3.4 | fillChromPeaks() | `not_reported` |
| 6 | Missing value filtering | R v. 4.4.1 | feature removal | `missing_threshold=50%` |
| 7 | Missing value imputation | R v. 4.4.1 | uniform sampling imputation | `range=[0.5*min_value, min_value]` |
| 8 | QC-based robust LOESS smoothing (QC-RLSC) | fANCOVA R package | LOESS with GCV | `loess.as_gcv=TRUE` |
| 9 | Within-batch normalization + batch alignment | R v. 4.4.1 | mean response alignment | `batch_definition=column_1&2_vs_column_3, alignment_method=mean_response` |
| 10 | RSD* and D-ratio filtering | MetaboCoreUtils R package | rsd() and rowDratio() | `mad=TRUE, RSD*_threshold=0.2, RSD*_threshold=0.3, D-ratio_threshold=0.4, D-ratio_threshold=0.5` |
| 11 | PCA evaluation | R v. 4.4.1 | principal component analysis | `log2_transform=TRUE, center=TRUE, scale=TRUE` |
| 12 | DNA concentration correction | R v. 4.4.1 | linear scaling | `correction_factor=DNA_concentration / mean_DNA_concentration` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Proposed end-to-end workflow for untargeted DNA adductomics preprocessing in exposome research | not_reported | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] |
| Figure 2 | pca_scores | PCA score plots comparing non-normalized vs QC-RLSC normalized + batch-aligned ENVIRONAGE data, colored by LC column and shaped by run type | not_reported | [10] |
| Figure 3 | boxplot | RSD* comparisons of three ISTD targets across normalization methods in ESCCAPE and ENVIRONAGE | Durbin-Conover test with Holm correction, p<0.05 | [9] |
| Figure 4 | workflow_diagram | Integrated workflow diagram summarizing preprocessing, normalization, filtering, and evaluation steps | not_reported | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] |
| Figure S17 | pathway_map | DNA adductome map of all retained features using selected normalization method | not_reported | [9] |

## Parameter Highlights

- **Step 1 (xcms R package v. 4.3.4)**: `ppm=5, peakwidth=[4,30], peakwidth=[1,25], snthresh=10, integrate=TRUE, extendLengthMSW=TRUE, firstBaselineCheck=TRUE`
- **Step 2 (xcms R package v. 4.3.4)**: `binSize=0.01, centerSample=1`
- **Step 3 (xcms R package v. 4.3.4)**: `anchor_peaks=[13C3]-M1-G,[13C,15N2]-Cro-dG,O6-[d3]-Me-dG`
- **Step 4 (xcms R package v. 4.3.4)**: `bw=2, minFraction=0.1, minFraction=0.05, ppm=5, binSize=0.01`
- **Step 5 (xcms R package v. 4.3.4)**: `not_reported`
- **Step 6 (R v. 4.4.1)**: `missing_threshold=50%`
- **Step 7 (R v. 4.4.1)**: `range=[0.5*min_value, min_value]`
- **Step 8 (fANCOVA R package)**: `loess.as_gcv=TRUE`
- **Step 9 (R v. 4.4.1)**: `batch_definition=column_1&2_vs_column_3, alignment_method=mean_response`
- **Step 10 (MetaboCoreUtils R package)**: `mad=TRUE, RSD*_threshold=0.2, RSD*_threshold=0.3, D-ratio_threshold=0.4, D-ratio_threshold=0.5`
- **Step 11 (R v. 4.4.1)**: `log2_transform=TRUE, center=TRUE, scale=TRUE`
- **Step 12 (R v. 4.4.1)**: `correction_factor=DNA_concentration / mean_DNA_concentration`

## Reproducibility Notes

- all key xcms parameters (ppm, peakwidth, bw, minFraction, binSize, centerSample) explicitly quantified and dataset-specific
- full statistical testing framework described (Durbin-Conover, Dunn’s test, Holm correction)
- clear separation of ENVIRONAGE vs ESCCAPE parameter choices with biological rationale
- use of technical replicates and independent QCs for unbiased normalization evaluation
- comprehensive PCA-based qualitative validation alongside quantitative metrics

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
