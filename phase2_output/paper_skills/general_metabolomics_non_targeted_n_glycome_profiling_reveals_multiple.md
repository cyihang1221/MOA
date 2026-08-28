# Skill: Non-targeted N-glycome profiling reveals multiple layers of organ-specific diversity in mice.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 87/100
- **source**: Helm J et al. (2024), Nature communications, DOI: 10.1038/s41467-024-54134-z, PMID: 39521793

## Analysis Goal
复现/对齐文献研究目标：Non-targeted N-glycome profiling reveals multiple layers of organ-specific diversity in mice.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | N-glycan extraction and release | manual biochemical protocol | enzymatic release with PNGase F | `reducing_agent=20 mM DTT, alkylating_agent=40 mM iodoacetamide, enzyme=2.5 U PNGase F, incubation_time_h=16, incubation_temp_c=37, buffer_pH=8.4, desalting_cartridge=HyperSep Hypercarb 25 mg, elution_solvent=80% acetonitrile in 10 mM ammonium bicarbonate` |
| 2 | LC-MS/MS acquisition | Thermo Orbitrap Exploris 480 | data-dependent acquisition (DDA) | `column=Hypercarb 100 mm × 0.32 mm, 5 μm, solvent_A=10 mM ammonium bicarbonate, solvent_B=80% acetonitrile in 50 mM ammonium bicarbonate, gradient_profile_min_B_percent=[1, 1, 9, 20, 35, 65, 1], gradient_profile_time_min=[0, 4.5, 5.5, 30, 41.5, 45, 55], flow_rate_uL_per_min=6, ms1_resolution=60000, ms1_agc_target=300, ms1_mz_range=[500, 1500], precursor_charge_states=[2, 3, 4, 5, 6], isolation_window_mz=1.4, dynamic_exclusion_s=20, dynamic_exclusion_n=1, mass_tolerance_ppm=10, nce_values_percent=[20, 25, 30], intensity_threshold=8000, ms2_resolution=15000, ms2_agc_target=100, ms2_max_accumulation_time_ms=100` |
| 3 | MS2 data preprocessing and oxonium ion filtering | custom Perl script (MS2OxoPlot.pl) | oxonium ion presence scoring and RT binning | `oxonium_ions_count=47, oxonium_mass_tolerance_amu=0.05, rt_bin_size_s=10, filtered_ions=[167.0914, 183.0863, 204.0867, 222.0972, 224.1118, 243.0264, 274.0921, 284.0435, 290.087, 292.1027, 308.0976, 312.1289, 316.1027, 328.1238, 332.0976, 334.1133, 350.1082, 366.1395, 370.1697, 407.1661, 495.1821, 511.177, 512.1974, 528.1923, 542.1716, 553.224, 569.21887, 622.1284, 657.2349, 658.2553, 673.2298, 698.2615, 699.2455, 714.2564, 715.2404, 715.27677, 792.3234, 803.2928, 819.2877, 860.31427, 876.30917, 948.3303, 980.3201, 446.09627, 649.17567, 731.27167, 877.32957, 1023.38747, 1169.44537]` |
| 4 | MS1 data deconvolution and mass binning | Decon2 (vnot specified (custom parameters for N-glycomics)) | charge deconvolution and isotopic deconvolution | `mass_range_da=[1000, 5000], mass_bin_width_amu=0.05, cumulative_intensity_threshold=5000000, retention_time_range_min=[0, 50]` |
| 5 | SNOG-score calculation and N-glycan-specific filtering | custom R code | SNOG-score = intensity(224.1)/sum(all fragment intensities) per mass bin | `reference_fragment_mz=224.1, snoq_score_threshold=0.03, filtering_level=sample-specific` |
| 6 | Sub-structural stratification via eSNOG scoring | custom R code | eSNOG-score = intensity(diagnostic_ion)/sum(all fragment intensities) per mass bin | `diagnostic_ions_table=Supplementary Table 2, eSNOG_cutoffs_empirical=True, substructures_screened=['sialylation', 'fucosylation', 'sulfation']` |
| 7 | Statistical and multivariate analysis | R (v4.3.1) | PCA, hierarchical clustering, correlation analysis, t-SNE | `packages=['tidyverse 2.0.0', 'pheatmap 1.0.12', 'RColorBrewer 1.1.3', 'dendextend 1.17.1', 'corrr 0.4.4', 'ggrepel 0.9.3', 'Rtsne 0.17'], visualization_methods=['heatmaps', 'dendrograms', 'PCA scores plots', 't-SNE embeddings', 'correlation matrices']` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | Schematic of precursor-independent MS/MS-based N-glycome profiling workflow integrating oxonium ion filtering, SNOG scoring, and substructure annotation. | R (ggplot2, grid, custom layout) | [3, 4, 5, 6] |
| Fig. 2 | heatmap | Comparative N-glycome profiles across 20 mouse tissues, showing global abundance patterns of N-glycan features. | pheatmap (R) | [5, 7] |
| Fig. 3 | pca_scores | PCA and hierarchical clustering of SNOG-filtered LC-MS data revealing organ-specific groupings. | R (ggplot2, dendextend, pheatmap) | [5, 7] |
| Fig. 4 | bar_chart | Sub-structural stratification showing relative abundances of sialylated, fucosylated, sulfated, and hybrid N-glycans across tissues. | ggplot2 (R) | [6, 7] |
| Fig. 5 | volcano_plot | Tissue-specific expression of unusual N-glycans identified by differential abundance analysis (e.g., non-canonical sulfated or phosphorylated structures). | t-test (FDR-corrected) | [6, 7] |
| Fig. 6 | chromatogram | Isomer-specific profiling using retention time alignment and diagnostic MS/MS fragments to distinguish structural isomers. | R (ggplot2, chromatogram overlays) | [2, 3, 6] |

## Parameter Highlights

- **Step 1 (manual biochemical protocol)**: `reducing_agent=20 mM DTT, alkylating_agent=40 mM iodoacetamide, enzyme=2.5 U PNGase F, incubation_time_h=16, incubation_temp_c=37, buffer_pH=8.4, desalting_cartridge=HyperSep Hypercarb 25 mg, elution_solvent=80% acetonitrile in 10 mM ammonium bicarbonate`
- **Step 2 (Thermo Orbitrap Exploris 480)**: `column=Hypercarb 100 mm × 0.32 mm, 5 μm, solvent_A=10 mM ammonium bicarbonate, solvent_B=80% acetonitrile in 50 mM ammonium bicarbonate, gradient_profile_min_B_percent=[1, 1, 9, 20, 35, 65, 1], gradient_profile_time_min=[0, 4.5, 5.5, 30, 41.5, 45, 55], flow_rate_uL_per_min=6, ms1_resolution=60000, ms1_agc_target=300, ms1_mz_range=[500, 1500], precursor_charge_states=[2, 3, 4, 5, 6], isolation_window_mz=1.4, dynamic_exclusion_s=20, dynamic_exclusion_n=1, mass_tolerance_ppm=10, nce_values_percent=[20, 25, 30], intensity_threshold=8000, ms2_resolution=15000, ms2_agc_target=100, ms2_max_accumulation_time_ms=100`
- **Step 3 (custom Perl script (MS2OxoPlot.pl))**: `oxonium_ions_count=47, oxonium_mass_tolerance_amu=0.05, rt_bin_size_s=10, filtered_ions=[167.0914, 183.0863, 204.0867, 222.0972, 224.1118, 243.0264, 274.0921, 284.0435, 290.087, 292.1027, 308.0976, 312.1289, 316.1027, 328.1238, 332.0976, 334.1133, 350.1082, 366.1395, 370.1697, 407.1661, 495.1821, 511.177, 512.1974, 528.1923, 542.1716, 553.224, 569.21887, 622.1284, 657.2349, 658.2553, 673.2298, 698.2615, 699.2455, 714.2564, 715.2404, 715.27677, 792.3234, 803.2928, 819.2877, 860.31427, 876.30917, 948.3303, 980.3201, 446.09627, 649.17567, 731.27167, 877.32957, 1023.38747, 1169.44537]`
- **Step 4 (Decon2 (vnot specified (custom parameters for N-glycomics)))**: `mass_range_da=[1000, 5000], mass_bin_width_amu=0.05, cumulative_intensity_threshold=5000000, retention_time_range_min=[0, 50]`
- **Step 5 (custom R code)**: `reference_fragment_mz=224.1, snoq_score_threshold=0.03, filtering_level=sample-specific`
- **Step 6 (custom R code)**: `diagnostic_ions_table=Supplementary Table 2, eSNOG_cutoffs_empirical=True, substructures_screened=['sialylation', 'fucosylation', 'sulfation']`
- **Step 7 (R (v4.3.1))**: `packages=['tidyverse 2.0.0', 'pheatmap 1.0.12', 'RColorBrewer 1.1.3', 'dendextend 1.17.1', 'corrr 0.4.4', 'ggrepel 0.9.3', 'Rtsne 0.17'], visualization_methods=['heatmaps', 'dendrograms', 'PCA scores plots', 't-SNE embeddings', 'correlation matrices']`

## Reproducibility Notes

- Full experimental protocol publicly available with reagent concentrations and timings
- All custom code (Perl, R) deposited on GitHub with DOI
- Raw and processed data deposited in MetaboLights with accession ID
- All R packages and versions explicitly listed
- Comprehensive list of glycan-specific oxonium ions and diagnostic fragments provided

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
