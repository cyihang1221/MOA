# Skill: consensus pathway enrichment

- **skill_type**: multi_paper_consensus
- **functional_domain**: `pathway_enrichment`
- **n_papers**: 20
- **trigger_keywords**: 通路, KEGG, 富集, pathway, enrichment, MetaboAnalyst

## Analysis Goal
当用户目标匹配「consensus pathway enrichment」场景时，采用多篇高水平文献的工具偏好与参数共识，规划分析流程并产出对应科研图与解释。

## Tool Preference Order

- `scikit-learn` （出现于 3/20 篇）
- `XCMS` （出现于 3/20 篇）
- `R` （出现于 3/20 篇）
- `RDKit` （出现于 2/20 篇）
- `TensorFlow` （出现于 2/20 篇）
- `KEGG database` （出现于 2/20 篇）
- `MetDNA` （出现于 2/20 篇）
- `MetaboAnalyst` （出现于 2/20 篇）
- `XCMS Online` （出现于 2/20 篇）
- `matchms` （出现于 1/20 篇）
- `pubchempy` （出现于 1/20 篇）
- `custom Python` （出现于 1/20 篇）

## Parameter Consensus（按出现频次）

- **matchms (v0.8.2)** `ion_mode=positive, min_peaks=5, mz_range_min=10.0, mz_range_max=1000.0, inchikey_length=14` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **matchms (v0.8.2)** `intensity_threshold_percent=0.1, max_peaks=1000, intensity_transformation=square_root, mz_min=10.0, mz_max=1000.0, n_bins=10000, bins_used=9948` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **rdkit** `fingerprint_type=Daylight, n_bits=2048, similarity_metric=Tanimoto` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **custom python** `train_inchikeys=14062, validation_inchikeys=500, test_inchikeys=500, validation_spectra=3597, test_spectra=3601, random_seed=fixed` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **ms2deepscore datageneratorallspectrums** `n_bins=10, bin_widening_step=0.1, max_bin_widening=0.5` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **ms2deepscore** `low_intensity_removal_percent_range=[0, 20], intensity_jitter_percent_range=[-40, 40], new_peak_addition_count_range=[0, 10], new_peak_intensity_range=[0, 0.01], intensity_threshold_for_removal=0.4` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **tensorflow/keras** `base_network_architecture=['Dense(500)', 'Dense(500)', 'Dense(200)'], embedding_dim=200, optimizer=Adam, learning_rate=0.001, batch_size=32, loss_function=MSE, early_stopping_patience=5, l1_regularization=1e-06, l2_regularization=1e-06, dropout_rate=0.2, batch_normalization=True` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **ms2deepscore** `mc_dropout_enabled_layers=['dense_2', 'dense_3'], n_samples=10, uncertainty_metric=interquartile_range` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **scikit-learn** `n_components=2, metric=cosine, perplexity=100, learning_rate=200, n_iter=1000, random_state=None` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **custom python** `structural_similarity_threshold=0.6, score_threshold_range=[0, 0.99]` — 1 篇共识
  - source: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- **xcms (via metaboseek)** `mass_tolerance_ppm=4, peakwidth=3_20, snthresh=3, prefilter=3_100, fitgauss=False, integrate=1, firstBaselineCheck=True, noise=0, mzCenterFun=wMean, mzdiff=-0.005` — 1 篇共识
  - source: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- **xcms (via metaboseek)** `minfrac=0.2, bw=2, mzwid=0.002, max=500, minsamp=1, usegroups=False` — 1 篇共识
  - source: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- **metaboseek peak filling** `mass_tolerance_ppm=3, rt_tolerance_sec=3, rtrange=True, areaMode=False` — 1 篇共识
  - source: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- **metaboseek data explorer** `blank_threshold_fold_change=10, quality_filter_method=Fast Peak Shapes` — 1 篇共识
  - source: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- **metaboseek basic analysis** `control_group=WT, test_type=unpaired two-sided t-test, p_value_adjustment=not specified (assumed none or default)` — 1 篇共识
  - source: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- **metaboseek advanced analysis (find ms2 scans)** `inclusion_window_sec=20, ms2_resolution=30000, agc_target_ms2=200000, collision_energy=[10, 30], isolation_window_mz=1.0, dynamic_exclusion_sec=5, top_n_ms2_per_scan=8` — 1 篇共识
  - source: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- **metaboseek ms/ms networking** `similarity_threshold=not explicitly stated (implied by 'Simplify Network' in Supplementary Fig. 1)` — 1 篇共识
  - source: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- **metaboseek** `normalization_reference=ascr#3 abundance` — 1 篇共识
  - source: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- **rdkit** `smiles_input=True, neutral_structure=True, atom_features=['element_type', 'hydrogen_count', 'ring_type'], bond_features=['bond_type', 'ring_type'], embedding_dim=300` — 1 篇共识
  - source: Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306
- **custom python implementation** `max_h_losses=4, ion_modes=['[F+H]+', '[F]+', '[F-H]+', '[F-2H]+', '[F-3H]+'], mass_tolerance_ppm=50` — 1 篇共识
  - source: Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306

## Expected Figures Consensus

- `workflow_diagram` （12 次）
- `bar_chart` （8 次）
- `boxplot` （4 次）
- `pathway_map` （4 次）
- `table` （4 次）
- `heatmap` （3 次）
- `network` （3 次）
- `roc_curve` （2 次）
- `line_plot` （2 次）
- `scatter_plot` （2 次）

## Representative Sources

- Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914
- Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306
- Pedersen HK et al. (2018), Nature protocols, DOI: 10.1038/s41596-018-0064-z, PMID: 30382244
- Subramanian A et al. (2005), PNAS, DOI: 10.1073/pnas.0506580102, PMID: 16199517
- Shen X et al. (2019), Nature Communications, DOI: 10.1038/s41467-019-09550-x, PMID: 30944337
- Mildau K et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c04444, PMID: 38564584
- Wang H et al. (2022), Nature communications, DOI: 10.1038/s41467-022-35511-y, PMID: 36528604
- Forsberg EM et al. (2018), Nature protocols, DOI: 10.1038/nprot.2017.151, PMID: 29494574
- Özçam M et al. (2025), Nature communications, DOI: 10.1038/s41467-025-61161-x, PMID: 40634275
- Wang Y et al. (2023), Analytical chemistry, DOI: 10.1021/acs.analchem.2c04603, PMID: 37023366
- Emelianova M et al. (2022), Nucleic acids research, DOI: 10.1093/nar/gkac427, PMID: 35639928

## Agent Usage Notes
- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。
- 必须映射到系统可用工具名；不可发明未注册工具。
- 出图与解释服务于用户分析目的，不只做样式改图。
