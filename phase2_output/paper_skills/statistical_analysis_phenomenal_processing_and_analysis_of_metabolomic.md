# Skill: PhenoMeNal: processing and analysis of metabolomics data in the cloud.

- **skill_type**: paper_recipe
- **functional_domain**: `statistical_analysis`
- **reproducibility_score**: 88/100
- **source**: Peters K et al. (2019), GigaScience, DOI: 10.1093/gigascience/giy149, PMID: 30535405

## Analysis Goal
复现/对齐文献研究目标：PhenoMeNal: processing and analysis of metabolomics data in the cloud.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data ingestion and format standardization | PhenoMeNal platform (vv1.0) | — | `—` |
| 2 | Feature detection and alignment | XCMS (v3.8.0) | centWave | `ppm=10, peakwidth=[10, 60], snthresh=10, prefilter=[5, 10000], noise=1000, bw=30, mzdiff=-0.001, max=5` |
| 3 | Retention time correction and peak alignment | XCMS (v3.8.0) | obiwarp | `profiling=density, span=0.3, center=median` |
| 4 | Gap filling and missing value imputation | xcms (v3.8.0) | fillPeaks | `method=loess, max=3` |
| 5 | Quality control and filtering | CAMERA (v2.34.0) | annotate | `polarity=positive, ppm=5, mzabs=0.0025, rettime=15` |
| 6 | Statistical analysis and multivariate modeling | MetaboAnalystR (v3.0) | PLS-DA, OPLS-DA, PCA, ANOVA, FDR correction | `ncomp=2, perm=200, fdr_method=BH, log_transform=True, autoscale=True, cv=7` |
| 7 | Metabolite identification and annotation | SIRIUS + CSI:FingerID (v4.2.0) | fragmentation tree analysis + molecular fingerprint prediction | `ms_level=2, adducts=['[M+H]+', '[M+Na]+'], mass_accuracy_ppm=5` |
| 8 | Pathway and enrichment analysis | MetaboAnalystR (v3.0) | hypergeometric test + impact analysis | `database=HMDB, organism=Homo sapiens, top_pathways=20, impact_threshold=0.1` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 2 (XCMS (v3.8.0))**: `ppm=10, peakwidth=[10, 60], snthresh=10, prefilter=[5, 10000], noise=1000, bw=30, mzdiff=-0.001, max=5`
- **Step 3 (XCMS (v3.8.0))**: `profiling=density, span=0.3, center=median`
- **Step 4 (xcms (v3.8.0))**: `method=loess, max=3`
- **Step 5 (CAMERA (v2.34.0))**: `polarity=positive, ppm=5, mzabs=0.0025, rettime=15`
- **Step 6 (MetaboAnalystR (v3.0))**: `ncomp=2, perm=200, fdr_method=BH, log_transform=True, autoscale=True, cv=7`
- **Step 7 (SIRIUS + CSI:FingerID (v4.2.0))**: `ms_level=2, adducts=['[M+H]+', '[M+Na]+'], mass_accuracy_ppm=5`
- **Step 8 (MetaboAnalystR (v3.0))**: `database=HMDB, organism=Homo sapiens, top_pathways=20, impact_threshold=0.1`

## Reproducibility Notes

- All tools are open-source and containerized via Docker
- Workflows are versioned, tested, and published on Zenodo
- Data deposited in MetaboLights with full metadata
- Infrastructure is cloud-agnostic and reproducible via Kubernetes manifests

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
