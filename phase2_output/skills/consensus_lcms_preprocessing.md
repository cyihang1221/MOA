# Skill: consensus lcms preprocessing

- **skill_type**: multi_paper_consensus
- **functional_domain**: `lcms_preprocessing`
- **n_papers**: 24
- **trigger_keywords**: 峰检测, XCMS, 预处理, peak picking, alignment, mzML

## Analysis Goal
当用户目标匹配「consensus lcms preprocessing」场景时，采用多篇高水平文献的工具偏好与参数共识，规划分析流程并产出对应科研图与解释。

## Tool Preference Order

- `XCMS` （出现于 13/24 篇）
- `R` （出现于 4/24 篇）
- `ProteoWizard` （出现于 4/24 篇）
- `OpenMS` （出现于 3/24 篇）
- `custom R script` （出现于 3/24 篇）
- `ProteoWizard msconvert` （出现于 2/24 篇）
- `IPO` （出现于 2/24 篇）
- `ProteoWizard MSConvert` （出现于 2/24 篇）
- `MZmine` （出现于 2/24 篇）
- `XCMS Online` （出现于 2/24 篇）
- `MZmine 2` （出现于 2/24 篇）
- `PCA` （出现于 2/24 篇）

## Parameter Consensus（按出现频次）

- **pca** `n_components=2` — 2 篇共识
  - source: Rong Z et al. (2020), Analytical chemistry, DOI: 10.1021/acs.analchem.9b05460, PMID: 32207605
  - source: Rong Z et al. (2020), Analytical chemistry, DOI: 10.1021/acs.analchem.9b05460, PMID: 32207605
- **xcms r package v. 4.3.4** `ppm=5, peakwidth=[4,30], peakwidth=[1,25], snthresh=10, integrate=TRUE, extendLengthMSW=TRUE, firstBaselineCheck=TRUE` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **xcms r package v. 4.3.4** `binSize=0.01, centerSample=1` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **xcms r package v. 4.3.4** `anchor_peaks=[13C3]-M1-G,[13C,15N2]-Cro-dG,O6-[d3]-Me-dG` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **xcms r package v. 4.3.4** `bw=2, minFraction=0.1, minFraction=0.05, ppm=5, binSize=0.01` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **xcms r package v. 4.3.4** `not_reported` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **r v. 4.4.1** `missing_threshold=50%` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **r v. 4.4.1** `range=[0.5*min_value, min_value]` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **fancova r package** `loess.as_gcv=TRUE` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **r v. 4.4.1** `batch_definition=column_1&2_vs_column_3, alignment_method=mean_response` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **metabocoreutils r package** `mad=TRUE, RSD*_threshold=0.2, RSD*_threshold=0.3, D-ratio_threshold=0.4, D-ratio_threshold=0.5` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **r v. 4.4.1** `log2_transform=TRUE, center=TRUE, scale=TRUE` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **r v. 4.4.1** `correction_factor=DNA_concentration / mean_DNA_concentration` — 1 篇共识
  - source: Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- **xcms (v3.12.0)** `ppm=5, peakwidth=[10, 60], snthresh=10, prefilter=[3, 100], noise=0, verbose.columns=False` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **xcms (v3.12.0)** `span=0.2, plottype=none` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **xcms (v3.12.0)** `minfrac=0.5, max=3` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **r (caret, randomforest, e1071)** `ntree=500, mtry=sqrt(p), repeatedcv_folds=5, repeats=10` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **autotuner (v1.4.0)** `n_iterations=50, population_size=20, mutation_rate=0.1` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **ipo (isotopologue parameter optimization) (v1.18.0)** `minfrac=0.5, maxiso=3, mzdiff=0.01` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **python script (metadata_cleanup_prefect.py)** `salt_removal_enabled=True, structure_standardization_pipeline=ChEMBL, computed_properties=['canonical_SMILES', 'isomeric_SMILES', 'InChI', 'InChIKey', 'logP', 'monoisotopic_mass']` — 1 篇共识
  - source: Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295

## Expected Figures Consensus

- `workflow_diagram` （18 次）
- `bar_chart` （15 次）
- `boxplot` （8 次）
- `pca_scores` （7 次）
- `pathway_map` （7 次）
- `heatmap` （6 次）
- `volcano_plot` （6 次）
- `other` （4 次）
- `subnetwork_graph` （3 次）
- `chromatogram` （2 次）

## Representative Sources

- Vangeenderhuysen P et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06549, PMID: 41834712
- Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295
- Graça G et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c03032, PMID: 35180347
- Brix F et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c01380, PMID: 38113356
- Hughes A et al. (2025), Analytical chemistry, DOI: 10.1021/acs.analchem.4c03124, PMID: 39757901
- Kambhampati S et al. (2024), Communications biology, DOI: 10.1038/s42003-024-05844-z, PMID: 38347116
- Heuckeroth S et al. (2024), Nature protocols, DOI: 10.1038/s41596-024-00996-y, PMID: 38769143
- Tripathi A et al. (2021), Nature chemical biology, DOI: 10.1038/s41589-020-00677-3, PMID: 33199911
- Wang H et al. (2023), Analytical chemistry, DOI: 10.1021/acs.analchem.2c05079, PMID: 37042095
- Stancliffe E et al. (2023), Analytical chemistry, DOI: 10.1021/acs.analchem.3c00764, PMID: 37314824
- Müller E et al. (2020), Analytical chemistry, DOI: 10.1021/acs.analchem.0c00899, PMID: 32786516

## Agent Usage Notes
- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。
- 必须映射到系统可用工具名；不可发明未注册工具。
- 出图与解释服务于用户分析目的，不只做样式改图。
