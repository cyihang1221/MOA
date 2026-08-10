# Skill: consensus molecular networking

- **skill_type**: multi_paper_consensus
- **functional_domain**: `molecular_networking`
- **n_papers**: 29
- **trigger_keywords**: 分子网络, GNPS, FBMN, MS2LDA, molecular networking, motif, 余弦

## Analysis Goal
当用户目标匹配「consensus molecular networking」场景时，采用多篇高水平文献的工具偏好与参数共识，规划分析流程并产出对应科研图与解释。

## Tool Preference Order

- `GNPS` （出现于 22/29 篇）
- `XCMS` （出现于 7/29 篇）
- `MetaboAnalyst` （出现于 4/29 篇）
- `R` （出现于 3/29 篇）
- `SIRIUS` （出现于 3/29 篇）
- `Custom R` （出现于 3/29 篇）
- `MZmine` （出现于 3/29 篇）
- `custom R script` （出现于 2/29 篇）
- `LC-MS` （出现于 2/29 篇）
- `ProteoWizard msconvert` （出现于 2/29 篇）
- `ClassyFire` （出现于 2/29 篇）
- `ModiFinder` （出现于 2/29 篇）

## Parameter Consensus（按出现频次）

- **chlorodbpfinder internal implementation** `not_reported` — 2 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **msconvert version 3.0.22035** `not_reported` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **envipat r package** `error~U(0, 5) ppm, fluctuation~N(0, δ²), δ=11.8% for M+1, δ=15.8% for M+2,+3,+4` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **masstools r package** `not_reported` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **randomforest r package version 4.3.0** `n.tree=500, mtry=sqrt(n.features), six engineered features from M, M+1, M+2 peaks` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **randomforest r package version 4.3.0** `n.tree=500, mtry=sqrt(n.features), eleven engineered features from M, M+1, M+2, M+3, M+4 peaks` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **xcms r package (embedded in chlorodbpfinder)** `not_reported` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **chlorodbpfinder internal algorithms** `not_reported` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **chlorodbpfinder internal function** `MS/MS match number ≥4, dot product score ≥0.7` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **gnps-based ms/ms similarity** `cosine=0.7, minimum matched peaks=6, minimum cosine score=0.7` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- **custom r script (implied)** `seven injection volumes: 2, 4, 6, 10, 13, 16, 20 μL` — 1 篇共识
  - source: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
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

## Expected Figures Consensus

- `workflow_diagram` （18 次）
- `network` （17 次）
- `bar_chart` （11 次）
- `boxplot` （8 次）
- `pathway_map` （5 次）
- `molecular_network` （5 次）
- `volcano_plot` （4 次）
- `chromatogram` （3 次）
- `pca_scores` （3 次）
- `heatmap` （2 次）

## Representative Sources

- Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426
- Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976
- Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557
- Yu JS et al. (2026), Nature protocols, DOI: 10.1038/s41596-025-01237-6, PMID: 40921758
- Liebergesell TCE et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.4c03528, PMID: 39367814
- Bazzano CF et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05829, PMID: 38702053
- Aron AT et al. (2020), Nature protocols, DOI: 10.1038/s41596-020-0317-5, PMID: 32405051
- Leao TF et al. (2021), Nature metabolism, DOI: 10.1038/s42255-021-00429-0, PMID: 34244695
- Kim M et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06388, PMID: 41481198
- Zhao HN et al. (2025), Nature communications, DOI: 10.1038/s41467-025-65993-5, PMID: 41366203
- Kontou EE et al. (2023), Journal of cheminformatics, DOI: 10.1186/s13321-023-00724-w, PMID: 37173725
- Breeur M et al. (2024), eLife, DOI: 10.7554/elife.91597, PMID: 38896449

## Agent Usage Notes
- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。
- 必须映射到系统可用工具名；不可发明未注册工具。
- 出图与解释服务于用户分析目的，不只做样式改图。
