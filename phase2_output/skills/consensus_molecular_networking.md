# Skill: consensus molecular networking

- **skill_type**: multi_paper_consensus
- **functional_domain**: `molecular_networking`
- **n_papers**: 32
- **trigger_keywords**: 分子网络, GNPS, FBMN, MS2LDA, molecular networking, motif, 余弦

## Analysis Goal
当用户目标匹配「consensus molecular networking」场景时，采用多篇高水平文献的工具偏好与参数共识，规划分析流程并产出对应科研图与解释。

## Tool Preference Order

- `GNPS` （出现于 24/32 篇）
- `XCMS` （出现于 8/32 篇）
- `MetaboAnalyst` （出现于 5/32 篇）
- `SIRIUS` （出现于 4/32 篇）
- `R` （出现于 3/32 篇）
- `ClassyFire` （出现于 3/32 篇）
- `Custom R` （出现于 3/32 篇）
- `MZmine` （出现于 3/32 篇）
- `LC-MS` （出现于 2/32 篇）
- `ProteoWizard msconvert` （出现于 2/32 篇）
- `GNPS spectral library search` （出现于 2/32 篇）
- `custom Python script` （出现于 2/32 篇）

## Parameter Consensus（按出现频次）

- **proteowizard msconvert** `32-bit=True, filter=['peakPicking true 1e-3']` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **xcms (v3.4.1)** `ppm=10, peakwidth=[5, 30], snthresh=10, prefilter=[3, 100], noise=10000, bw=10, mzdiff=-0.001, minfrac=0.5, max=3` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **xcms (v3.4.1)** `profStep=0.01` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **imputelcmd** `k=5, method=rowmean` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **gnps** `cosine_score_threshold=0.7, min_matched_peaks=6` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **r / limma** `adjust_method=BH, pval_cutoff=0.05, logFC_cutoff=0.585` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **classyfire** `threshold=0.7` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **sparcc** `correlation_threshold=0.3, pval_cutoff=0.01` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **maaslin2 (v2.0.0)** `transform=CLR, min_abundance=0.0001, min_prev=0.1, random_effect=['cohort', 'batch'], pval_cutoff=0.05, qval_cutoff=0.1` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **randomforest** `ntree=1000, mtry=sqrt(p), importance=True, strata=IBD_status` — 1 篇共识
  - source: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- **gnps/massive** `ion_mode=positive, sample_count=10000` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **gnps** `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.8, min_matched_peaks=6, min_spectra_per_cluster=2, max_edges_per_node=10, mscluster_mixture_probability_threshold=0.05, mscluster_rounds=3, preprocessing={'remove_ions_near_precursor': True, 'remove_window_da': 17.0, 'top_ions_per_50_mz_window': 6}` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **gnps** `precursor_mass_tolerance_mz=0.1, fragment_mass_tolerance_mz=0.1, cosine_similarity_threshold=0.8, min_matched_peaks=6, min_spectra_per_cluster=2, max_edges_per_node=10, preprocessing={'remove_ions_near_precursor': True, 'remove_window_da': 17.0, 'top_ions_per_50_mz_window': 6}` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **gnps spectral library search** `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.7, min_matched_peaks=6, reference_libraries_count=22, reference_spectra_count=221224` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **custom gnps pipeline** `max_precursor_mass_tolerance_ppm=20, cosine_similarity_threshold=0.8, min_matched_peaks=6, require_nonzero_precursor_delta=True, min_occurrence_of_delta_mass=10` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **sirius (v4.5.2)** `precursor_mass_tolerance_ppm={'Orbitrap': 10, 'Q-TOF': 25}, input_data_type=MS/MS only, other_settings=default` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **buddy (v1.3)** `precursor_mass_tolerance_ppm={'FT-ICR': 5, 'Orbitrap': 10, 'Q-TOF': 25}, fragment_mass_tolerance_ppm=2× precursor tolerance, allowed_elements_initial=['C', 'H', 'N', 'O', 'P', 'S'], allowed_elements_extended=['C', 'H', 'N', 'O', 'P', 'S', 'F', 'Cl', 'Br', 'I']` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **unimod + custom list** `modification_sources=['UNIMOD', 'Supplementary Data 3'], min_delta_frequency=10` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **custom script** `naming_template=Suspect related to [compound name] (predicted molecular formula: [SIRIUS and/or BUDDY]) with delta m/z [sign delta] (putative explanation: [modification])` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- **gnps spectral library search** `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.8, min_matched_peaks=6, test_datasets_total=1407, test_spectra_total=592000000, independent_test_set_size=72` — 1 篇共识
  - source: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557

## Expected Figures Consensus

- `workflow_diagram` （23 次）
- `network` （17 次）
- `bar_chart` （13 次）
- `boxplot` （8 次）
- `molecular_network` （5 次）
- `volcano_plot` （5 次）
- `pathway_map` （4 次）
- `chromatogram` （4 次）
- `pca_scores` （3 次）
- `heatmap` （2 次）

## Representative Sources

- Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- Huber F et al. (2021), PLoS Computational Biology, DOI: 10.1371/journal.pcbi.1008724, PMID: 33591968
- Yu JS et al. (2026), Nature protocols, DOI: 10.1038/s41596-025-01237-6, PMID: 40921758
- Liebergesell TCE et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.4c03528, PMID: 39367814
- Bazzano CF et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05829, PMID: 38702053
- Aron AT et al. (2020), Nature protocols, DOI: 10.1038/s41596-020-0317-5, PMID: 32405051
- Wang M et al. (2016), Nature Biotechnology, DOI: 10.1038/nbt.3597, PMID: 27504778
- Zhao T et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- Leao TF et al. (2021), Nature metabolism, DOI: 10.1038/s42255-021-00429-0, PMID: 34244695
- Zhao HN et al. (2025), Nature communications, DOI: 10.1038/s41467-025-65993-5, PMID: 41366203
- Kontou EE et al. (2023), Journal of cheminformatics, DOI: 10.1186/s13321-023-00724-w, PMID: 37173725

## Agent Usage Notes
- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。
- 必须映射到系统可用工具名；不可发明未注册工具。
- 出图与解释服务于用户分析目的，不只做样式改图。
