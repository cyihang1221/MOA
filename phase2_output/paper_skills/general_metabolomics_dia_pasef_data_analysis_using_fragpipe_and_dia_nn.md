# Skill: dia-PASEF data analysis using FragPipe and DIA-NN for deep proteomics of low sample amounts.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 88/100
- **source**: Demichev V et al. (2022), Nature communications, DOI: 10.1038/s41467-022-31492-0, PMID: 35803928

## Analysis Goal
复现/对齐文献研究目标：dia-PASEF data analysis using FragPipe and DIA-NN for deep proteomics of low sample amounts.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Spectral library generation | FragPipe (v15) | MSFragger + PeptideProphet + ProteinProphet + EasyPQP | `precursor_mass_tolerance_ppm=20, fragment_mass_tolerance_ppm=20, enzyme_specificity=stricttrypsin, max_missed_cleavages=2, isotope_error=[0, 1, 2], peptide_length_min=7, peptide_length_max=50, peptide_mass_min_da=500, peptide_mass_max_da=5000, fixed_modifications=['Carbamidomethylation of Cysteine'], variable_modifications=['Oxidation of Methionine', 'Acetylation of protein N-termini', '-18.0106 Da on N-terminal Glutamic acid', '-17.0265 Da on N-terminal Glutamine and Cysteine'], max_variable_mods_per_peptide=3, fdr_strategy=2D FDR, protein_fdr_threshold=0.01, peptide_fdr_threshold=0.01, psm_fdr_threshold=0.01, ion_fdr_threshold=0.01, rt_alignment_method=lowess, irt_calibration_set=extended HeLa iRT, im_alignment_reference_run=auto-selected` |
| 2 | 2D peak picking for dia-PASEF data | DIA-NN (v1.8.1) | 2D local maximum detection with intensity-based filtering | `im_tolerance_frames=10 * (frame scan range / 900) / (frame 1/K0 range), mz_tolerance_bins=2, im_weighted_distance_threshold=ion mobility tolerance, im_window_size_constant=True, frame_summing_enabled=True, mass_tolerance_ppm_ms1=10, mass_tolerance_ppm_ms2=10` |
| 3 | Chromatogram extraction | DIA-NN (v1.8.1) | binary search + IM window filtering | `mass_search_method=binary search, im_tolerance_auto=True, im_prediction_method=library-based alignment (observed vs. library IM values), intensity_selection=highest intensity peak within IM/mass window` |
| 4 | Spectral library processing and filtering | DIA-NN (v1.8.1) | Reannotate + species-specific filtering | `library_filtering_mode=species-specific (human/yeast), in_silico_rt_im_generation=True, replace_spectra_with_in_silico=True, precursor_fdr_threshold=0.1, quantification_mode=Robust LC (high precision), mbr_enabled=True, protein_inference_disabled=True, relaxed_prot_inf=True, q_value_filter_precursor=0.01, q_value_filter_protein_global=0.01, q_value_filter_protein_run_specific=True` |
| 5 | Protein inference and quantification | DIA-NN (v1.8.1) | MaxLFQ normalization + protein grouping | `quantification_algorithm=MaxLFQ, protein_group_column=Protein.Group, quantity_column=PG.MaxLFQ, proteotypic_peptide_annotation=via Reannotate, gene_column_used_for_counting=Genes, filtering_strategy=precursor q-value < 1%, global protein q-value < 1%` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | Illustrates the conceptual pipeline for processing trapped ion mobility proteomic data, including spectral library generation, 2D peak picking, chromatogram extraction, and quantification. | Adobe Illustrator / custom script | [1, 2, 3, 4, 5] |
| Fig. 2 | bar_chart | Compares protein detection and quantification performance across different acquisition methods and sample amounts, showing increased depth with dia-PASEF + DIA-NN/FragPipe. | R ggplot2 or GraphPad Prism | [5] |

## Parameter Highlights

- **Step 1 (FragPipe (v15))**: `precursor_mass_tolerance_ppm=20, fragment_mass_tolerance_ppm=20, enzyme_specificity=stricttrypsin, max_missed_cleavages=2, isotope_error=[0, 1, 2], peptide_length_min=7, peptide_length_max=50, peptide_mass_min_da=500, peptide_mass_max_da=5000, fixed_modifications=['Carbamidomethylation of Cysteine'], variable_modifications=['Oxidation of Methionine', 'Acetylation of protein N-termini', '-18.0106 Da on N-terminal Glutamic acid', '-17.0265 Da on N-terminal Glutamine and Cysteine'], max_variable_mods_per_peptide=3, fdr_strategy=2D FDR, protein_fdr_threshold=0.01, peptide_fdr_threshold=0.01, psm_fdr_threshold=0.01, ion_fdr_threshold=0.01, rt_alignment_method=lowess, irt_calibration_set=extended HeLa iRT, im_alignment_reference_run=auto-selected`
- **Step 2 (DIA-NN (v1.8.1))**: `im_tolerance_frames=10 * (frame scan range / 900) / (frame 1/K0 range), mz_tolerance_bins=2, im_weighted_distance_threshold=ion mobility tolerance, im_window_size_constant=True, frame_summing_enabled=True, mass_tolerance_ppm_ms1=10, mass_tolerance_ppm_ms2=10`
- **Step 3 (DIA-NN (v1.8.1))**: `mass_search_method=binary search, im_tolerance_auto=True, im_prediction_method=library-based alignment (observed vs. library IM values), intensity_selection=highest intensity peak within IM/mass window`
- **Step 4 (DIA-NN (v1.8.1))**: `library_filtering_mode=species-specific (human/yeast), in_silico_rt_im_generation=True, replace_spectra_with_in_silico=True, precursor_fdr_threshold=0.1, quantification_mode=Robust LC (high precision), mbr_enabled=True, protein_inference_disabled=True, relaxed_prot_inf=True, q_value_filter_precursor=0.01, q_value_filter_protein_global=0.01, q_value_filter_protein_run_specific=True`
- **Step 5 (DIA-NN (v1.8.1))**: `quantification_algorithm=MaxLFQ, protein_group_column=Protein.Group, quantity_column=PG.MaxLFQ, proteotypic_peptide_annotation=via Reannotate, gene_column_used_for_counting=Genes, filtering_strategy=precursor q-value < 1%, global protein q-value < 1%`

## Reproducibility Notes

- All raw and processed data deposited in PRIDE (PXD022216, PXD013658)
- Open-source tools with versioned releases (FragPipe v15, DIA-NN v1.8.1)
- Detailed parameterization of MSFragger, Philosopher, and DIA-NN settings
- Public GitHub repository with DOI for DIA-NN
- Explicit FDR calculation methodology and π₀ correction formula provided

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
