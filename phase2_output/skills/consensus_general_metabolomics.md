# Skill: consensus general metabolomics

- **skill_type**: multi_paper_consensus
- **functional_domain**: `general_metabolomics`
- **n_papers**: 40
- **trigger_keywords**: 代谢组, metabolomics, LC-MS, 完整流程

## Analysis Goal
当用户目标匹配「consensus general metabolomics」场景时，采用多篇高水平文献的工具偏好与参数共识，规划分析流程并产出对应科研图与解释。

## Tool Preference Order

- `R` （出现于 9/40 篇）
- `RDKit` （出现于 4/40 篇）
- `PyTorch` （出现于 2/40 篇）
- `custom Python script` （出现于 2/40 篇）
- `matchms` （出现于 2/40 篇）
- `DIA-NN` （出现于 2/40 篇）
- `Custom pipeline` （出现于 2/40 篇）
- `TensorFlow` （出现于 2/40 篇）
- `MS-DIAL` （出现于 2/40 篇）
- `ReAdW.exe` （出现于 1/40 篇）
- `COMET` （出现于 1/40 篇）
- `custom filtering strategy` （出现于 1/40 篇）

## Parameter Consensus（按出现频次）

- **comet** `precursor_mass_tolerance_ppm=50, product_ion_tolerance_da=0.03, fdr_threshold=0.01, static_modifications=['TMTpro on lysine and N-terminus (+304.2071 Da)', 'carbamidomethylation of cysteine (+57.021 Da)'], variable_modifications=['oxidation of methionine (+15.995 Da)']` — 1 篇共识
  - source: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- **custom filtering strategy** `min_resolution_ms2=45000, min_total_signal_to_noise_across_channels=1440, reporter_ion_match_tolerance_da=0.001` — 1 篇共识
  - source: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- **protein parsimony rules** `quantification_method=sum of TMT reporter ion counts across retained PSMs, normalization_method=channel-wise S/N-sum normalization to equalize total signal per channel` — 1 篇共识
  - source: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- **r (base stats)** `model_age_continuous=log2(protein) ~ intercept + age_months + sex, model_age_categorical=log2(protein) ~ intercept + factor(age_group) + sex, model_interaction=log2(protein) ~ intercept + age + sex + age:sex, fdr_method=Benjamini-Hochberg, p_value_threshold_fdr=0.1, model_selection_criterion=BIC` — 1 篇共识
  - source: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- **r (base stats)** `model_full=log2(protein) ~ intercept + age + sex + tissue + age:tissue + sex:tissue, fdr_method=Benjamini-Hochberg, p_value_threshold_fdr=0.1` — 1 篇共识
  - source: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- **pcamethods r package** `n_components=10, preprocessing=log2 transformation, no centering/scaling specified (implied by package defaults)` — 1 篇共识
  - source: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- **clusterprofiler r package** `gene_set_definition=['age_coefficient > 0 & padj < 0.1', 'categorical age trends (e.g., Down-Flat)'], fdr_threshold_gsea=0.1, fdr_threshold_trends=0.01, identifier_mapping={'GO': 'ENSEMBL', 'KEGG': 'UniProt'}, background_gene_set=all analyzed proteins per tissue` — 1 篇共识
  - source: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- **r (custom scripts)** `takasugi_processing=TMT 16-plex, Lumos, 4 age groups, male-only, non-continuous age modeling, wang_processing=DIA, 3 early-life age groups, both sexes, missingness filter (>80% missing → removed)` — 1 篇共识
  - source: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- **custom python pipeline** `mz_range_min=50, mz_range_max=2500, precursor_exclusion_window_da=2, intensity_threshold_percent=1, max_peaks_retained=150, intensity_transformation=square_root, intensity_normalization=sum_normalization` — 1 篇共识
  - source: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- **custom pytorch implementation** `embedding_dimension=512, lambda_min=0.001, lambda_max=10000, d_sin=256, d_cos=256` — 1 篇共识
  - source: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- **custom pytorch implementation** `precursor_mz_embedding=sinusoidal, charge_embedding_dim=16, max_charge_state=10` — 1 篇共识
  - source: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- **pytorch + custom transformer** `num_layers=9, embedding_size=512, num_attention_heads=8, total_parameters=47000000, vocabulary_size=28, max_peptide_length=100, stop_token_id=27` — 1 篇共识
  - source: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- **pytorch** `batch_size=32, weight_decay=1e-05, peak_learning_rate=0.0005, warmup_steps=100000, learning_rate_schedule=linear warmup + cosine decay, training_epochs=1, validation_frequency_iterations=50000` — 1 篇共识
  - source: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- **pytorch** `fine_tuning_learning_rate=5e-05, fine_tuning_epochs=5, validation_selection_criterion=minimum validation loss` — 1 篇共识
  - source: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- **custom pytorch inference** `beam_width=user-specified k, termination_conditions=['stop_token', 'mass_tolerance_match', 'max_length_reached'], precursor_mass_tolerance_ppm=inference-time parameter ϵ, isotope_offset_handling=optional` — 1 篇共识
  - source: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- **custom post-processing** `mass_error_ppm_threshold=ϵ (dataset-specific, e.g., instrument-dependent)` — 1 篇共识
  - source: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- **pymzml (v2.5.2)** `max_fragment_peaks=1000` — 1 篇共识
  - source: Urban J et al. (2024), Nature methods, DOI: 10.1038/s41592-024-02314-6, PMID: 38951670
- **custom python script (vcandycrunch v.0.3.0)** `mz_tolerance_da=0.5, rt_tolerance_min=2.0` — 1 篇共识
  - source: Urban J et al. (2024), Nature methods, DOI: 10.1038/s41592-024-02314-6, PMID: 38951670
- **candycrunch (custom) (vv.0.3.0)** `rt_min_threshold_min=2.0, rt_normalization_method=divide_by_max_or_30, intensity_normalization=divide_by_total_spectrum_intensity, mz_bin_count=2048, mz_min=39.714, mz_max=3000.0, remainder_encoding=True` — 1 篇共识
  - source: Urban J et al. (2024), Nature methods, DOI: 10.1038/s41592-024-02314-6, PMID: 38951670
- **pytorch (v2.1.0)** `dilation_rates=[1, 2, 4, 8, 16, 32], conv_kernel_size=3, leaky_relu_negative_slope=0.2, max_pool_kernel_size=20, embedding_dims={'glycan_class': 24, 'ion_mode': 24, 'ion_trap': 24, 'lc_type': 24, 'modification': 24}, precursor_mz_embedding_dim=24, rt_embedding_dim=24, fc_dropout_rate=0.2, total_trainable_parameters=12375084` — 1 篇共识
  - source: Urban J et al. (2024), Nature methods, DOI: 10.1038/s41592-024-02314-6, PMID: 38951670

## Expected Figures Consensus

- `workflow_diagram` （25 次）
- `bar_chart` （23 次）
- `boxplot` （10 次）
- `volcano_plot` （10 次）
- `pca_scores` （8 次）
- `heatmap` （7 次）
- `chromatogram` （6 次）
- `pathway_map` （4 次）
- `other` （4 次）
- `table` （4 次）

## Representative Sources

- Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760
- Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256
- Urban J et al. (2024), Nature methods, DOI: 10.1038/s41592-024-02314-6, PMID: 38951670
- Blaise BJ et al. (2021), Nature protocols, DOI: 10.1038/s41596-021-00579-1, PMID: 34321638
- de Jonge NF et al. (2023), Nature communications, DOI: 10.1038/s41467-023-37446-4, PMID: 36990978
- Li K et al. (2025), Nature communications, DOI: 10.1038/s41467-024-55448-8, PMID: 39747075
- Pakkir Shah AK et al. (2025), Nature protocols, DOI: 10.1038/s41596-024-01046-3, PMID: 39304763
- de Jonge NF et al. (2024), Journal of cheminformatics, DOI: 10.1186/s13321-024-00878-1, PMID: 39075613
- Li S et al. (2023), Nature communications, DOI: 10.1038/s41467-023-39889-1, PMID: 37433854
- Pirhaji L et al. (2025), Communications chemistry, DOI: 10.1038/s42004-025-01791-w, PMID: 41413219
- Cordes J et al. (2021), GigaScience, DOI: 10.1093/gigascience/giab049, PMID: 34282451
- Dablanc A et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.4c02219, PMID: 39028894

## Agent Usage Notes
- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。
- 必须映射到系统可用工具名；不可发明未注册工具。
- 出图与解释服务于用户分析目的，不只做样式改图。
