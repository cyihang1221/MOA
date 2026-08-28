# Skill: Achieving quantitative reproducibility in label-free multisite DIA experiments through multirun alignment.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 87/100
- **source**: Gupta S et al. (2023), Communications biology, DOI: 10.1038/s42003-023-05437-2, PMID: 37903988

## Analysis Goal
复现/对齐文献研究目标：Achieving quantitative reproducibility in label-free multisite DIA experiments through multirun alignment.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data conversion to mzML | MSConvert | no peak-picking | `docker_image=chambm/pwiz-skyline-i-agree-to-the-vendor-licenses:c30f8e5beb5f, compression=['linear m/z', 'positive integer intensity']` |
| 2 | DIA library preparation | custom curation pipeline | library harmonization | `rt_normalization=average NormalizedRetentionTime across charge states, rt_filter=remove peptides with \|ΔNormalizedRetentionTime\| > 4 across charge states, sequence_validation=Uniprot (Dec 2021) matching + manual correction, iRT_AQUA_addition=['11 iRTs', '30 AQUA peptides']` |
| 3 | Peak picking and XIC extraction | OpenSWATH | targeted extraction using DIA library | `RT_extraction_window_s=600, extra_RT_window_s=50, min_upper_edge_dist=1, MS2_extraction_window_ppm=75, MS1_extraction_window_ppm=35, DIA_extraction_window_ppm=75, mass_correction=ppm quadratic regression, background_subtraction=vertical_division_min, scoring=['mutual_information', 'MS1_scoring']` |
| 4 | Chromatogram compression to sqMass | OpenSwathMzMLFileCacher | lossless chromatogram serialization | `lossy_compression=False` |
| 5 | Feature scoring and FDR control | PyProphet (v2.1.10) | XGBoost classifier | `level=ms1ms2, initial_FDR=0.01, integration_FDR=0.05, mscore_threshold=0.025, q_value_threshold=0.025` |
| 6 | Multirun chromatogram alignment | DIAlignR (v>2.3) | ['Star (reference-based)', 'MST (minimum spanning tree)', 'Progressive (reference-free)'] | `transitionIntensity=True, hardConstrain=True, maxFdrQuery=0.05, alignedFDR1=0.05, alignedFDR2=0.05, fractionation=10, signal_integration_within_run=True` |
| 7 | Alternative alignment for comparison | TRIC (v0.11.0) | MST-based RT correction with LOWESS | `readmethod=cminimal, realign_method=lowess_cython, mst_Stdev_multiplier=4.0, mst_useRTCorrection=True` |
| 8 | Data normalization and transformation | R base + custom scripts | median normalization + log2 transformation | `normalization_strategy=median-normalize per run, transformation=log2` |
| 9 | Protein inference and summarization | custom R pipeline | top-N selection (top-3 peptides, top-3–6 fragment ions) | `peptide_selection=top 3 most intense peptides per protein, fragment_selection=['top 3 (S. pyogenes)', 'top 5 (plasma)', 'top 6 (multisite)'], singleton_removal=True, completeness_threshold=0.4, transition_minimum=4950, run_filtering=exclude runs < μₙ − 1.96·σₙ or low TIC` |
| 10 | Differential proteomics (cross-sectional) | nlme (R package) | linear mixed-effects model (LME) | `model_formula=intensity ~ IRIS + peptideID + (1\|Batch) + (1\|AcqOrder) + (1\|ID), method=ML for p-value, REML for effect size, p_adjustment=Benjamini-Hochberg, significance_threshold_p=0.05, effect_size_threshold=log2(1.25)` |
| 11 | Differential proteomics (longitudinal RVI) | nlme (R package) | linear mixed-effects model with time-event factor | `model_formula=intensity ~ event + peptideID + (1\|Batch) + (1\|AcqOrder) + (1\|ID), event_levels=5, p_adjustment=Benjamini-Hochberg, significance_threshold_p=0.05` |
| 12 | Functional enrichment analysis | IMPaLA | pathway over-representation analysis | `q_value_threshold=1.0, clustering_method=fuzzy c-means, clusters=4, minimum_cluster_score=0.6, standardization=z-score per peptide` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | benchmark_plot | Benchmarking multirun alignment on a manually annotated dataset. | quantitation error-rate calculation (true/false peak ratio) | [6] |
| Fig. 2 | error_rate_plot | Evaluating quantitative error rate control on multi-species dataset. | q-value–based quantitation error-rate | [5, 6] |
| Fig. 3 | alignment_comparison | Comparison of signal alignment by DIAlignR on multisite data. | CV reduction (50% for abundant proteins) | [6] |
| Fig. 4 | alignment_comparison | Comparison of Star, MST and Progressive alignments. | none explicitly stated; qualitative alignment accuracy | [6] |
| Fig. 5 | differential_proteomics | Analysis with aligning 949 plasma runs, identifying IR and RVI-associated proteins. | LME ANOVA with BH correction (p ≤ 0.05, effect > log2(1.25)) | [10, 11] |

## Parameter Highlights

- **Step 1 (MSConvert)**: `docker_image=chambm/pwiz-skyline-i-agree-to-the-vendor-licenses:c30f8e5beb5f, compression=['linear m/z', 'positive integer intensity']`
- **Step 2 (custom curation pipeline)**: `rt_normalization=average NormalizedRetentionTime across charge states, rt_filter=remove peptides with |ΔNormalizedRetentionTime| > 4 across charge states, sequence_validation=Uniprot (Dec 2021) matching + manual correction, iRT_AQUA_addition=['11 iRTs', '30 AQUA peptides']`
- **Step 3 (OpenSWATH)**: `RT_extraction_window_s=600, extra_RT_window_s=50, min_upper_edge_dist=1, MS2_extraction_window_ppm=75, MS1_extraction_window_ppm=35, DIA_extraction_window_ppm=75, mass_correction=ppm quadratic regression, background_subtraction=vertical_division_min, scoring=['mutual_information', 'MS1_scoring']`
- **Step 4 (OpenSwathMzMLFileCacher)**: `lossy_compression=False`
- **Step 5 (PyProphet (v2.1.10))**: `level=ms1ms2, initial_FDR=0.01, integration_FDR=0.05, mscore_threshold=0.025, q_value_threshold=0.025`
- **Step 6 (DIAlignR (v>2.3))**: `transitionIntensity=True, hardConstrain=True, maxFdrQuery=0.05, alignedFDR1=0.05, alignedFDR2=0.05, fractionation=10, signal_integration_within_run=True`
- **Step 7 (TRIC (v0.11.0))**: `readmethod=cminimal, realign_method=lowess_cython, mst_Stdev_multiplier=4.0, mst_useRTCorrection=True`
- **Step 8 (R base + custom scripts)**: `normalization_strategy=median-normalize per run, transformation=log2`
- **Step 9 (custom R pipeline)**: `peptide_selection=top 3 most intense peptides per protein, fragment_selection=['top 3 (S. pyogenes)', 'top 5 (plasma)', 'top 6 (multisite)'], singleton_removal=True, completeness_threshold=0.4, transition_minimum=4950, run_filtering=exclude runs < μₙ − 1.96·σₙ or low TIC`
- **Step 10 (nlme (R package))**: `model_formula=intensity ~ IRIS + peptideID + (1|Batch) + (1|AcqOrder) + (1|ID), method=ML for p-value, REML for effect size, p_adjustment=Benjamini-Hochberg, significance_threshold_p=0.05, effect_size_threshold=log2(1.25)`
- **Step 11 (nlme (R package))**: `model_formula=intensity ~ event + peptideID + (1|Batch) + (1|AcqOrder) + (1|ID), event_levels=5, p_adjustment=Benjamini-Hochberg, significance_threshold_p=0.05`
- **Step 12 (IMPaLA)**: `q_value_threshold=1.0, clustering_method=fuzzy c-means, clusters=4, minimum_cluster_score=0.6, standardization=z-score per peptide`

## Reproducibility Notes

- All raw data publicly available in PRIDE, PASS, and iPOP
- Processed libraries and alignment outputs deposited on Zenodo (6677715)
- Core tools (MSConvert, OpenSWATH, PyProphet, TRIC, DIAlignR) are open-source with Docker images provided
- GitHub repository for DIAlignR is linked and MIT licensed
- Statistical models fully specified with formulas and thresholds

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
