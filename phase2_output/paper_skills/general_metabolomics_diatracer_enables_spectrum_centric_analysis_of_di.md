# Skill: diaTracer enables spectrum-centric analysis of diaPASEF proteomics data.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Li K et al. (2025), Nature communications, DOI: 10.1038/s41467-024-55448-8, PMID: 39747075

## Analysis Goal
复现/对齐文献研究目标：diaTracer enables spectrum-centric analysis of diaPASEF proteomics data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | 3D peak tracing and feature detection | diaTracer | 3D (m/z, RT, IM) Gaussian peak fitting + Savitzky-Golay + Z-Score peak detection | `Delta_Apex_IM=0.01, Delta_Apex_RT=3, RF_max=500, Corr_threshold=0.3, mass_defect_filter_enabled=True, isotope_clustering_min_isotopes=1, isotope_mass_difference=C13-based, neighbor_requirement_relaxed_for_MS2=True, IM_window_frame_scan_range_divided_by_min_IM_difference=True, mz_range_divided_by_min_mz_difference=True` |
| 2 | Spectral library generation | MSFragger + MSBooster + Percolator + EasyPQP | Database search (DDA-derived library), PSM rescoring, RT/MS2 prediction, spectral library compilation | `precursor_mass_tolerance_ppm=10, fragment_mass_tolerance_ppm=20, isotope_error=0/1/2, enzyme_specificity=stricttrypsin, max_missed_cleavages=2, variable_modifications=['Oxidation of methionine', 'N-terminal acetylation', 'pyro-Glu', 'phosphorylation (in PTM workflows)'], fixed_modifications=['methylthiolation of cysteine', 'carbamidomethylation of cysteine (CSF/plasma)', 'cysteinylation (+119) (HLA)'], peptide_length_range=[7, 50], peptide_mass_range_Da=[500, 5000], semi_tryptic=True, nonspecific_cleavage=True, mass_offset_search_windows=[-150, 500], mass_offset_list=predefined common PTMs` |
| 3 | Library-based DIA quantification | DIA-NN (v1.8.1) | Library-matched peak integration and protein inference | `precursor_mz_range=[300, 1800], max_missed_cleavages=1, FDR_threshold=0.01` |
| 4 | Library-free DIA quantification | DIA-NN (v1.8.1) | Direct deconvolution and identification without spectral library | `mode=library-free, default_settings_used=True, precursor_mz_range=[300, 1800], variable_modifications=['Oxidation of methionine'], fixed_modifications=['carbamidomethylation of cysteine'], max_missed_cleavages=1` |
| 5 | Differential expression analysis | FragPipe-Analyst | Missing value imputation + t-test / ANOVA with FDR correction | `min_percentage_non_missing_globally=25, min_percentage_non_missing_in_one_condition=25, DE_adjusted_p_value_cutoff=0.05, DE_log2_fold_change_cutoff=1, imputation_type=Perseus-type, FDR_correction_type=Benjamini Hochberg` |
| 6 | PTM discovery via open/mass-offset search | MSFragger (within FragPipe) | Mass-offset search (targeted) and open search (untargeted) | `mass_offset_search_window_ppm=10, open_search_mass_tolerance_Da=[-150, 500], common_PTMs_database=built-in` |
| 7 | HLA immunopeptide binding affinity prediction | NetMHCpan (v4.1) | Neural network-based MHC class I binding prediction | `peptide_length_range=[8, 12], binding_affinity_percentile_rank_cutoff_strong=0.5, binding_affinity_percentile_rank_cutoff_weak=2.0` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (diaTracer)**: `Delta_Apex_IM=0.01, Delta_Apex_RT=3, RF_max=500, Corr_threshold=0.3, mass_defect_filter_enabled=True, isotope_clustering_min_isotopes=1, isotope_mass_difference=C13-based, neighbor_requirement_relaxed_for_MS2=True, IM_window_frame_scan_range_divided_by_min_IM_difference=True, mz_range_divided_by_min_mz_difference=True`
- **Step 2 (MSFragger + MSBooster + Percolator + EasyPQP)**: `precursor_mass_tolerance_ppm=10, fragment_mass_tolerance_ppm=20, isotope_error=0/1/2, enzyme_specificity=stricttrypsin, max_missed_cleavages=2, variable_modifications=['Oxidation of methionine', 'N-terminal acetylation', 'pyro-Glu', 'phosphorylation (in PTM workflows)'], fixed_modifications=['methylthiolation of cysteine', 'carbamidomethylation of cysteine (CSF/plasma)', 'cysteinylation (+119) (HLA)'], peptide_length_range=[7, 50], peptide_mass_range_Da=[500, 5000], semi_tryptic=True, nonspecific_cleavage=True, mass_offset_search_windows=[-150, 500], mass_offset_list=predefined common PTMs`
- **Step 3 (DIA-NN (v1.8.1))**: `precursor_mz_range=[300, 1800], max_missed_cleavages=1, FDR_threshold=0.01`
- **Step 4 (DIA-NN (v1.8.1))**: `mode=library-free, default_settings_used=True, precursor_mz_range=[300, 1800], variable_modifications=['Oxidation of methionine'], fixed_modifications=['carbamidomethylation of cysteine'], max_missed_cleavages=1`
- **Step 5 (FragPipe-Analyst)**: `min_percentage_non_missing_globally=25, min_percentage_non_missing_in_one_condition=25, DE_adjusted_p_value_cutoff=0.05, DE_log2_fold_change_cutoff=1, imputation_type=Perseus-type, FDR_correction_type=Benjamini Hochberg`
- **Step 6 (MSFragger (within FragPipe))**: `mass_offset_search_window_ppm=10, open_search_mass_tolerance_Da=[-150, 500], common_PTMs_database=built-in`
- **Step 7 (NetMHCpan (v4.1))**: `peptide_length_range=[8, 12], binding_affinity_percentile_rank_cutoff_strong=0.5, binding_affinity_percentile_rank_cutoff_weak=2.0`

## Reproducibility Notes

- All raw data deposited in PRIDE (PXD042187) with full metadata
- diaTracer is open-source (GitHub, Apache-2.0 license) with Zenodo DOI
- FragPipe workflows fully specified with parameter overrides documented
- All computational tools (MSFragger, DIA-NN, NetMHCpan, iq R package) are publicly available and versioned
- Parameter values explicitly reported for all key steps (e.g., Delta Apex IM = 0.01, Corr threshold = 0.3)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
