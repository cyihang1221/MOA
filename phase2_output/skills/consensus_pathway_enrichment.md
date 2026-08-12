# Skill: consensus pathway enrichment

- **skill_type**: multi_paper_consensus
- **functional_domain**: `pathway_enrichment`
- **n_papers**: 17
- **trigger_keywords**: 通路, KEGG, 富集, pathway, enrichment, MetaboAnalyst

## Analysis Goal
当用户目标匹配「consensus pathway enrichment」场景时，采用多篇高水平文献的工具偏好与参数共识，规划分析流程并产出对应科研图与解释。

## Tool Preference Order

- `XCMS` （出现于 4/17 篇）
- `R` （出现于 3/17 篇）
- `KEGG database` （出现于 2/17 篇）
- `scikit-learn` （出现于 2/17 篇）
- `MetaboAnalyst` （出现于 2/17 篇）
- `XCMS Online` （出现于 2/17 篇）
- `MSConvert` （出现于 1/17 篇）
- `Metaboseek peak filling` （出现于 1/17 篇）
- `Metaboseek Data Explorer` （出现于 1/17 篇）
- `Metaboseek Basic Analysis` （出现于 1/17 篇）
- `Metaboseek Advanced Analysis` （出现于 1/17 篇）
- `Metaboseek MS` （出现于 1/17 篇）

## Parameter Consensus（按出现频次）

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
- **pytorch geometric** `num_layers=6, activation=ELU, message_passing=True, aggregation=mean_pooling, edge_map_enabled=True, covariates=['molecular_weight', 'precursor_ion_mode', 'collision_energy_eV', 'instrument_type']` — 1 篇共识
  - source: Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306
- **custom python implementation** `softmax_denominator=exp(σ) + sum(exp(θ_f)), peak_merging=sum probabilities for same m/z within tolerance` — 1 篇共识
  - source: Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306
- **custom pytorch model** `loss_function=MSE, frozen_backbone=True, training_phase=post-fragmentation` — 1 篇共识
  - source: Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306
- **custom scripts + rdkit + lib2nist** `libraries=["NIST'17", 'MS-DIAL', 'MSnLib v1.0'], collision_energy_conversion=NCE → eV via Proteomicsnews formula, mass_tolerance_ppm={"NIST'17": 50, 'MSnLib': 10}, filters=['SMILES-MOL-InChiKey consistency', 'ionization_mode ∈ {[M+H]+, [M-H]-, [M]+, [M]-}', 'MW ≤ 1000 Da', 'CE ≤ 100 eV']` — 1 篇共识
  - source: Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306
- **pytorch** `loss_weighting=1 / number_of_spectra_per_compound, optimizer=ADAM, learning_rate=None, batch_size=None, epochs=None` — 1 篇共识
  - source: Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306
- **r** `correlation_threshold=0.7, clustering_method=average linkage` — 1 篇共识
  - source: Pedersen HK et al. (2018), Nature protocols, DOI: 10.1038/s41596-018-0064-z, PMID: 30382244
- **humann2 / metaphlan2** `min_coverage=1.0, min_abundance=0.001` — 1 篇共识
  - source: Pedersen HK et al. (2018), Nature protocols, DOI: 10.1038/s41596-018-0064-z, PMID: 30382244
- **kegg database (vkegg release 91 (2018))** `module_aggregation=sum, KO_filtering=present in ≥2 samples` — 1 篇共识
  - source: Pedersen HK et al. (2018), Nature protocols, DOI: 10.1038/s41596-018-0064-z, PMID: 30382244
- **r** `n_permutations=1000, FDR_control=Benjamini-Hochberg, covariates=['age', 'sex', 'BMI']` — 1 篇共识
  - source: Pedersen HK et al. (2018), Nature protocols, DOI: 10.1038/s41596-018-0064-z, PMID: 30382244
- **r** `MGS_removal_threshold=abundance > 0.1% in ≥10% samples` — 1 篇共识
  - source: Pedersen HK et al. (2018), Nature protocols, DOI: 10.1038/s41596-018-0064-z, PMID: 30382244

## Expected Figures Consensus

- `workflow_diagram` （8 次）
- `bar_chart` （7 次）
- `heatmap` （5 次）
- `boxplot` （4 次）
- `pathway_map` （4 次）
- `table` （4 次）
- `volcano_plot` （2 次）
- `network` （2 次）
- `pca_scores` （2 次）
- `schematic` （1 次）

## Representative Sources

- Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075
- Nowatzky Y et al. (2025), Nature communications, DOI: 10.1038/s41467-025-57422-4, PMID: 40055306
- Pedersen HK et al. (2018), Nature protocols, DOI: 10.1038/s41596-018-0064-z, PMID: 30382244
- Li Z et al., (2026), Metabolites, DOI: 10.3390/metabo16040279, PMID: 42042924
- Mildau K et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c04444, PMID: 38564584
- Wang H et al. (2022), Nature communications, DOI: 10.1038/s41467-022-35511-y, PMID: 36528604
- Forsberg EM et al. (2018), Nature protocols, DOI: 10.1038/nprot.2017.151, PMID: 29494574
- Özçam M et al. (2025), Nature communications, DOI: 10.1038/s41467-025-61161-x, PMID: 40634275
- Wang Y et al. (2023), Analytical chemistry, DOI: 10.1021/acs.analchem.2c04603, PMID: 37023366
- Emelianova M et al. (2022), Nucleic acids research, DOI: 10.1093/nar/gkac427, PMID: 35639928
- Hu J et al. (2025), Analytical chemistry, DOI: 10.1021/acs.analchem.5c00449, PMID: 40709718
- Zilocchi M et al. (2023), Nature protocols, DOI: 10.1038/s41596-023-00901-z, PMID: 37985878

## Agent Usage Notes
- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。
- 必须映射到系统可用工具名；不可发明未注册工具。
- 出图与解释服务于用户分析目的，不只做样式改图。
