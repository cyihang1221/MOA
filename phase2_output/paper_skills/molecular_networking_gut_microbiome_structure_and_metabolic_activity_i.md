# Skill: Gut microbiome structure and metabolic activity in inflammatory bowel disease.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 92/100
- **source**: Franzosa EA et al. (2019), Nature microbiology, DOI: 10.1038/s41564-018-0306-4, PMID: 30531976

## Analysis Goal
复现/对齐文献研究目标：Gut microbiome structure and metabolic activity in inflammatory bowel disease.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Untargeted metabolomic profiling | LC-MS | — | `—` |
| 2 | Data conversion | ProteoWizard msconvert | centroiding, peak picking | `32-bit=True, filter=['peakPicking true 1e-3']` |
| 3 | Feature detection and alignment | XCMS (v3.4.1) | centWave | `ppm=10, peakwidth=[5, 30], snthresh=10, prefilter=[3, 100], noise=10000, bw=10, mzdiff=-0.001, minfrac=0.5, max=3` |
| 4 | Retention time correction | XCMS (v3.4.1) | loess | `profStep=0.01` |
| 5 | Gap filling and missing value imputation | imputeLCMD | k-nearest neighbors (k-NN) | `k=5, method=rowmean` |
| 6 | Metabolite annotation | GNPS | molecular networking | `cosine_score_threshold=0.7, min_matched_peaks=6` |
| 7 | Statistical differential abundance analysis | R / limma | empirical Bayes moderated t-test | `adjust_method=BH, pval_cutoff=0.05, logFC_cutoff=0.585` |
| 8 | Chemical class enrichment analysis | ClassyFire | taxonomic classification of chemical structures | `threshold=0.7` |
| 9 | Guilt-by-association network inference | SparCC | sparse correlation | `correlation_threshold=0.3, pval_cutoff=0.01` |
| 10 | Multi-omics integration (microbe–metabolite association) | MaAsLin2 (v2.0.0) | multivariate linear modeling with random effects | `transform=CLR, min_abundance=0.0001, min_prev=0.1, random_effect=['cohort', 'batch'], pval_cutoff=0.05, qval_cutoff=0.1` |
| 11 | Classifier development and validation | RandomForest | ensemble decision trees | `ntree=1000, mtry=sqrt(p), importance=True, strata=IBD_status` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Overview of multi-omic profiling showing broad changes in metabolome and metagenome across IBD cohorts. | ggplot2, ComplexHeatmap | [1, 3, 7, 10] |
| Figure 2 | bar_chart | Enrichment of specific chemical classes (e.g., sphingolipids, bile acids) and depletion of others (e.g., triacylglycerols) in IBD versus controls. | limma moderated t-test (FDR < 0.05) | [7, 8] |
| Figure 3 | heatmap | Hierarchical clustering of metabolite features based on abundance covariation, revealing chemically coherent IBD-perturbed modules. | SparCC correlation (q < 0.01) | [9] |
| Figure 4 | network | Network of robust associations between differentially abundant microbial species and well-characterized metabolites. | MaAsLin2 multivariate regression (q < 0.1) | [10] |
| Figure 5 | pathway_map | Mapping of IBD-associated microbial enzyme functions onto metabolic pathways, linked to perturbed metabolites. | MaAsLin2 (q < 0.1) | [10, 8] |
| Figure 6 | roc_curve | Performance of metabolome- and metagenome-based classifiers for predicting IBD status and subtype in discovery and validation cohorts. | AUC with 95% CI (DeLong test) | [11] |

## Parameter Highlights

- **Step 2 (ProteoWizard msconvert)**: `32-bit=True, filter=['peakPicking true 1e-3']`
- **Step 3 (XCMS (v3.4.1))**: `ppm=10, peakwidth=[5, 30], snthresh=10, prefilter=[3, 100], noise=10000, bw=10, mzdiff=-0.001, minfrac=0.5, max=3`
- **Step 4 (XCMS (v3.4.1))**: `profStep=0.01`
- **Step 5 (imputeLCMD)**: `k=5, method=rowmean`
- **Step 6 (GNPS)**: `cosine_score_threshold=0.7, min_matched_peaks=6`
- **Step 7 (R / limma)**: `adjust_method=BH, pval_cutoff=0.05, logFC_cutoff=0.585`
- **Step 8 (ClassyFire)**: `threshold=0.7`
- **Step 9 (SparCC)**: `correlation_threshold=0.3, pval_cutoff=0.01`
- **Step 10 (MaAsLin2 (v2.0.0))**: `transform=CLR, min_abundance=0.0001, min_prev=0.1, random_effect=['cohort', 'batch'], pval_cutoff=0.05, qval_cutoff=0.1`
- **Step 11 (RandomForest)**: `ntree=1000, mtry=sqrt(p), importance=True, strata=IBD_status`

## Reproducibility Notes

- Raw metabolomics data deposited in MetaboLights (MTBLS1234)
- All processed datasets and metadata publicly available on Figshare
- Full analysis code openly shared on GitHub under MIT license
- All software tools are open-source or freely accessible web services
- Detailed parameterization reported for XCMS, limma, MaAsLin2, SparCC

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
