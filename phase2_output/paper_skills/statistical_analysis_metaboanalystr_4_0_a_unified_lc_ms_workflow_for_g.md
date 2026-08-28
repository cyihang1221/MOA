# Skill: MetaboAnalystR 4.0: a unified LC-MS workflow for global metabolomics.

- **skill_type**: paper_recipe
- **functional_domain**: `statistical_analysis`
- **reproducibility_score**: 87/100
- **source**: Pang Z et al. (2024), Nature communications, DOI: 10.1038/s41467-024-48009-6, PMID: 38693118

## Analysis Goal
复现/对齐文献研究目标：MetaboAnalystR 4.0: a unified LC-MS workflow for global metabolomics.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data acquisition and LC-MS1/MS2 profiling | Thermo Scientific UltiMate 3000 UHPLC + Q-Exactive Orbitrap | untargeted DDA, DIA (SWATH), iterative targeted DDA | `flow_rate_mL_min=0.4, ion_mode=['ESI+', 'ESI-'], spray_voltage_keV_pos={'C18': 4.0, 'HILIC': 4.0}, spray_voltage_keV_neg={'C18': 3.5, 'HILIC': 3.8}, mobile_phase_A_C18=0.1% FA in water, mobile_phase_B_C18=0.1% FA in ACN, mobile_phase_A_HILIC=50% ACN in water + 5 mmol/L NH4AC, mobile_phase_B_HILIC=95% ACN in water + 5 mmol/L NH4AC, SWATH_windows_count=10, SWATH_window_overlap_mz=1.0, SWATH_cycle_time_s=0.9, DDA_top_n=10, MS1_resolution=Orbitrap (not specified value), MS2_acquisition_strategy=['DDA', 'DIA/SWATH', 'iterative_targeted_DDA']` |
| 2 | Raw file conversion to mzML | msconvert (ProteoWizard) | centroiding, peak picking | `centroiding=True, filter_string=peakPicking true 1-` |
| 3 | Feature detection and quantification (LC-MS1) | MetaboAnalystR 4.0 (v4.0) | auto-optimized feature detection | `mz_tolerance_ppm=None, rt_tolerance_sec=None, min_peak_width_sec=None, sn_thresh=None, noise_threshold=None, integrate_method=centWave` |
| 4 | Retention time alignment and correction | MetaboAnalystR 4.0 (v4.0) | loess-based RT correction | `alignment_method=loess, ref_sample=QC sample, max_rt_shift_sec=None` |
| 5 | Gap filling and missing value imputation | MetaboAnalystR 4.0 (v4.0) | k-nearest neighbors (k-NN) or minimum intensity replacement | `imputation_method=knn, k=5, min_fraction_samples=0.5` |
| 6 | Normalization and scaling | MetaboAnalystR 4.0 (v4.0) | QC-based normalization + Pareto scaling | `normalization_method=QC-RLM, scaling_method=pareto, qc_correction=True` |
| 7 | Statistical analysis (univariate/multivariate) | MetaboAnalystR 4.0 (v4.0) | ['t-test', 'ANOVA', 'PCA', 'PLS-DA', 'OPLS-DA', 'random forest'] | `p_value_cutoff=0.05, fdr_method=BH, n_components_PLS_DA=2, n_components_OPLS_DA=1, cv_method=leave-one-out` |
| 8 | MS2 spectral deconvolution and compound identification | MetaboAnalystR 4.0 (v4.0) | precursor-matched MS2 assignment + spectral library matching | `mz_tolerance_ppm_MS2=10, rt_tolerance_sec_MS2=5, score_threshold=0.7, library_matching_algorithm=dot product, neutral_loss_enabled=True, neutral_loss_databases=['Pathway', 'Biology', 'Lipid', 'Exposomics']` |
| 9 | Functional interpretation and pathway enrichment | MetaboAnalystR 4.0 (v4.0) | hypergeometric test + KEGG/RefMet mapping | `pathway_database=KEGG, organism=Homo sapiens, enrichment_method=hypergeometric, p_value_cutoff=0.05, fdr_method=BH` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (Thermo Scientific UltiMate 3000 UHPLC + Q-Exactive Orbitrap)**: `flow_rate_mL_min=0.4, ion_mode=['ESI+', 'ESI-'], spray_voltage_keV_pos={'C18': 4.0, 'HILIC': 4.0}, spray_voltage_keV_neg={'C18': 3.5, 'HILIC': 3.8}, mobile_phase_A_C18=0.1% FA in water, mobile_phase_B_C18=0.1% FA in ACN, mobile_phase_A_HILIC=50% ACN in water + 5 mmol/L NH4AC, mobile_phase_B_HILIC=95% ACN in water + 5 mmol/L NH4AC, SWATH_windows_count=10, SWATH_window_overlap_mz=1.0, SWATH_cycle_time_s=0.9, DDA_top_n=10, MS1_resolution=Orbitrap (not specified value), MS2_acquisition_strategy=['DDA', 'DIA/SWATH', 'iterative_targeted_DDA']`
- **Step 2 (msconvert (ProteoWizard))**: `centroiding=True, filter_string=peakPicking true 1-`
- **Step 3 (MetaboAnalystR 4.0 (v4.0))**: `mz_tolerance_ppm=None, rt_tolerance_sec=None, min_peak_width_sec=None, sn_thresh=None, noise_threshold=None, integrate_method=centWave`
- **Step 4 (MetaboAnalystR 4.0 (v4.0))**: `alignment_method=loess, ref_sample=QC sample, max_rt_shift_sec=None`
- **Step 5 (MetaboAnalystR 4.0 (v4.0))**: `imputation_method=knn, k=5, min_fraction_samples=0.5`
- **Step 6 (MetaboAnalystR 4.0 (v4.0))**: `normalization_method=QC-RLM, scaling_method=pareto, qc_correction=True`
- **Step 7 (MetaboAnalystR 4.0 (v4.0))**: `p_value_cutoff=0.05, fdr_method=BH, n_components_PLS_DA=2, n_components_OPLS_DA=1, cv_method=leave-one-out`
- **Step 8 (MetaboAnalystR 4.0 (v4.0))**: `mz_tolerance_ppm_MS2=10, rt_tolerance_sec_MS2=5, score_threshold=0.7, library_matching_algorithm=dot product, neutral_loss_enabled=True, neutral_loss_databases=['Pathway', 'Biology', 'Lipid', 'Exposomics']`
- **Step 9 (MetaboAnalystR 4.0 (v4.0))**: `pathway_database=KEGG, organism=Homo sapiens, enrichment_method=hypergeometric, p_value_cutoff=0.05, fdr_method=BH`

## Reproducibility Notes

- Raw data publicly available on Metabolomics Workbench with two accession IDs
- MetaboAnalystR 4.0 is fully open-source (GitHub + Zenodo DOI + GPL-3.0 license)
- Comprehensive curation of nine MS2 databases into unified SQLite schema documented
- All chromatographic and MS instrument parameters referenced in supplementary tables (though not embedded in main text)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
