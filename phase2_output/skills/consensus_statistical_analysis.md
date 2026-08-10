# Skill: consensus statistical analysis

- **skill_type**: multi_paper_consensus
- **functional_domain**: `statistical_analysis`
- **n_papers**: 8
- **trigger_keywords**: 统计分析, PCA, PLS-DA, 火山图, VIP, 差异代谢物, mixOmics, volcano

## Analysis Goal
当用户目标匹配「consensus statistical analysis」场景时，采用多篇高水平文献的工具偏好与参数共识，规划分析流程并产出对应科研图与解释。

## Tool Preference Order

- `XCMS` （出现于 5/8 篇）
- `MetaboAnalystR` （出现于 3/8 篇）
- `MetaboAnalyst` （出现于 3/8 篇）
- `CAMERA` （出现于 2/8 篇）
- `Custom R script` （出现于 2/8 篇）
- `R` （出现于 2/8 篇）
- `MetaboAnalyst 5.0` （出现于 1/8 篇）
- `PhenoMeNal platform` （出现于 1/8 篇）
- `xcms` （出现于 1/8 篇）
- `SIRIUS + CSI:FingerID` （出现于 1/8 篇）
- `Metabolite extraction protocol` （出现于 1/8 篇）
- `Agilent 6230 TOF LC-MS` （出现于 1/8 篇）

## Parameter Consensus（按出现频次）

- **metaboanalyst 5.0 (v5.0)** `mass_tolerance_ppm=5, peak_width_min_sec=5, peak_width_max_sec=60, sn_thresh=10, prefilter_min_count=2, prefilter_min_intensity=10000, rt_correction_method=obiwarp, rt_correction_span=0.3, alignment_min_fraction=0.5, gap_fill_min_frac=0.5, gap_fill_min_intensity=10000` — 1 篇共识
  - source: Pang Z et al. (2022), Nature protocols, DOI: 10.1038/s41596-022-00710-w, PMID: 35715522
- **metaboanalyst 5.0 (v5.0)** `database=HMDB, KEGG, SMPDB, Reactome, id_type=HMDB ID, KEGG ID, or common name, method=hypergeometric test with FDR correction, impact_threshold=0.1, top_pathways=20` — 1 篇共识
  - source: Pang Z et al. (2022), Nature protocols, DOI: 10.1038/s41596-022-00710-w, PMID: 35715522
- **metaboanalyst 5.0 (v5.0)** `integration_method=joint-pathway analysis, correlation_method=Spearman, min_correlation_abs=0.5, p_value_cutoff=0.05, fdr_method=BH` — 1 篇共识
  - source: Pang Z et al. (2022), Nature protocols, DOI: 10.1038/s41596-022-00710-w, PMID: 35715522
- **metaboanalyst 5.0 (v5.0)** `adjustment_method=linear regression residualization, covariates=['age', 'sex', 'batch'], association_test=ANOVA or linear regression, multiple_testing_correction=FDR (BH)` — 1 篇共识
  - source: Pang Z et al. (2022), Nature protocols, DOI: 10.1038/s41596-022-00710-w, PMID: 35715522
- **xcms (v3.8.0)** `ppm=10, peakwidth=[10, 60], snthresh=10, prefilter=[5, 10000], noise=1000, bw=30, mzdiff=-0.001, max=5` — 1 篇共识
  - source: Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405
- **xcms (v3.8.0)** `profiling=density, span=0.3, center=median` — 1 篇共识
  - source: Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405
- **xcms (v3.8.0)** `method=loess, max=3` — 1 篇共识
  - source: Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405
- **camera (v2.34.0)** `polarity=positive, ppm=5, mzabs=0.0025, rettime=15` — 1 篇共识
  - source: Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405
- **metaboanalystr (v3.0)** `ncomp=2, perm=200, fdr_method=BH, log_transform=True, autoscale=True, cv=7` — 1 篇共识
  - source: Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405
- **sirius + csi:fingerid (v4.2.0)** `ms_level=2, adducts=['[M+H]+', '[M+Na]+'], mass_accuracy_ppm=5` — 1 篇共识
  - source: Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405
- **metaboanalystr (v3.0)** `database=HMDB, organism=Homo sapiens, top_pathways=20, impact_threshold=0.1` — 1 篇共识
  - source: Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405
- **metabolite extraction protocol** `solvent=methanol:water (80:20), extraction_method=cold methanol quenching, centrifugation=14,000 g, 10 min, 4°C` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- **agilent 6230 tof lc-ms** `column=ZORBAX Eclipse Plus C18, gradient=not fully specified, flow_rate=0.3 mL/min, column_temp=40°C, mass_range=50–1000 m/z, polarity=['positive', 'negative']` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- **proteowizard msconvert** `32-bit=True, filter=peakPicking true 1-2` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- **xcms (r/bioconductor) (v3.14.0)** `ppm=10, peakwidth=[10, 60], snthresh=10, prefilter=[3, 100], noise=1000, bw=30, mzwid=0.015, minfrac=0.5, intensity=10000` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- **xcms (v3.14.0)** `method=obiwarp, profiling=False, span=0.5` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- **imputelcmd (r package) (v3.4.0)** `k=5, method=knn` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- **metaboanalystr (v3.0.3)** `cv_cutoff=0.25, scaling=pareto, filtering_method=CV-based` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- **metaboanalystr (v3.0.3)** `alpha=0.05, fdr_method=BH` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- **metaboanalystr (v3.0.3)** `ncomp_PCA=2, ncomp_PLS_DA=2, ncomp_OPLS_DA=2, validation=permutation test (200 permutations)` — 1 篇共识
  - source: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366

## Expected Figures Consensus

- `workflow_diagram` （5 次）
- `heatmap` （4 次）
- `pathway_map` （3 次）
- `volcano_plot` （3 次）
- `chromatogram` （2 次）
- `bar_chart` （2 次）
- `pca_scores` （2 次）
- `other` （1 次）
- `violin_plot` （1 次）
- `network` （1 次）

## Representative Sources

- Pang Z et al. (2022), Nature protocols, DOI: 10.1038/s41596-022-00710-w, PMID: 35715522
- Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405
- Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366
- Pang Z et al. (2024), Nature communications, DOI: 10.1038/s41467-024-48009-6, PMID: 38693118
- Chen YC et al. (2023), Analytical chemistry, DOI: 10.1021/acs.analchem.3c02419, PMID: 37713273
- Hector EC et al. (2025), Briefings in bioinformatics, DOI: 10.1093/bib/bbaf095, PMID: 40067114
- Chen CY et al. (2025), Nature communications, DOI: 10.1038/s41467-025-64328-8, PMID: 41173857
- Yuan Y et al. (2023), Analytical chemistry, DOI: 10.1021/acs.analchem.3c01864, PMID: 37428854

## Agent Usage Notes
- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。
- 必须映射到系统可用工具名；不可发明未注册工具。
- 出图与解释服务于用户分析目的，不只做样式改图。
