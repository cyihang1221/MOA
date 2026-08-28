# Skill: Metabolic profiling stratifies colorectal cancer and reveals adenosylhomocysteinase as a therapeutic target.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 87/100
- **source**: Vande Voorde J et al. (2023), Nature metabolism, DOI: 10.1038/s42255-023-00857-0, PMID: 37580540

## Analysis Goal
复现/对齐文献研究目标：Metabolic profiling stratifies colorectal cancer and reveals adenosylhomocysteinase as a therapeutic target.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data acquisition via untargeted LC-MS and MSI | mass spectrometry | — | `—` |
| 2 | Peak detection and feature extraction | XCMS | centWave | `peakwidth=[10, 60], ppm=5, snthr=10` |
| 3 | Retention time alignment and peak matching | XCMS | obiwarp | `method=obiwarp, profiling=True` |
| 4 | Gap filling and missing value imputation | XCMS | fillpeaks | `minfrac=0.5, max=100` |
| 5 | Statistical analysis and biomarker discovery | R (DESeq2, limma, stats) (vDESeq2 v1.22.2) | Wald test (DESeq2), moderated t-test (limma) | `alpha=0.05, padj=BH, log2FC_threshold=1.0` |
| 6 | Multivariate statistical modeling (PCA, PLS-DA) | R (mixOmics, factoextra) | PCA, PLS-DA | `ncomp=3, scale=True` |
| 7 | Metabolite annotation and identification | GNPS, HMDB, METLIN, mzCloud | MS1 accurate mass matching, MS/MS spectral library matching | `mass_tolerance_ppm=5, rt_tolerance_sec=30, cosine_score_threshold=0.7` |
| 8 | Pathway enrichment analysis | MetaboAnalyst | hypergeometric test, impact analysis | `organism=Mus musculus, database=KEGG, p_value_cutoff=0.05` |
| 9 | Integration with transcriptomics (RNA-seq) | R (DESeq2, clusterProfiler) (vDESeq2 v1.22.2) | correlation (Spearman), joint pathway enrichment | `correlation_method=spearman, p_adj_cutoff=0.05, rho_threshold=0.6` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | pca_scores | PCA scores plot showing separation of normal, APC-deficient, and APC/KRAS double-mutant intestinal tissues based on untargeted metabolomics. | PERMANOVA p < 0.001 | [6] |
| Figure 2 | volcano_plot | Volcano plot highlighting significantly dysregulated metabolites (FDR < 0.05, \|log2FC\| > 1) in APC-deficient vs. wild-type intestine. | Wald test (DESeq2), FDR-adjusted p < 0.05 | [5] |
| Figure 3 | pathway_map | KEGG pathway map of the methionine cycle, highlighting upregulated metabolites (e.g., S-adenosylhomocysteine) and AHCY enzyme in APC-deficient tissue. | hypergeometric test p = 1.2e-5 | [8] |
| Figure 4 | boxplot | Boxplots showing AHCY protein expression (IF intensity) across genotypes and treatment groups. | one-way ANOVA with Tukey’s post-hoc, p < 0.001 | [5] |
| Extended Data Fig. 3 | chromatogram | LC-MS extracted ion chromatograms showing tumour-specific accumulation of 13C-glycocholic acid after oral gavage. | none (qualitative localization) | [1, 2] |
| Extended Data Fig. 8a,b | bar_chart | Bar charts showing reduced BrdU+ proliferating cells and tumour burden in DZNeP-treated ApcMin/+ mice. | unpaired two-tailed t-test, p < 0.01 | [5] |

## Parameter Highlights

- **Step 2 (XCMS)**: `peakwidth=[10, 60], ppm=5, snthr=10`
- **Step 3 (XCMS)**: `method=obiwarp, profiling=True`
- **Step 4 (XCMS)**: `minfrac=0.5, max=100`
- **Step 5 (R (DESeq2, limma, stats) (vDESeq2 v1.22.2))**: `alpha=0.05, padj=BH, log2FC_threshold=1.0`
- **Step 6 (R (mixOmics, factoextra))**: `ncomp=3, scale=True`
- **Step 7 (GNPS, HMDB, METLIN, mzCloud)**: `mass_tolerance_ppm=5, rt_tolerance_sec=30, cosine_score_threshold=0.7`
- **Step 8 (MetaboAnalyst)**: `organism=Mus musculus, database=KEGG, p_value_cutoff=0.05`
- **Step 9 (R (DESeq2, clusterProfiler) (vDESeq2 v1.22.2))**: `correlation_method=spearman, p_adj_cutoff=0.05, rho_threshold=0.6`

## Reproducibility Notes

- Raw and processed metabolomics data publicly available in MetaboLights and Figshare
- Full analysis code deposited on GitHub with Zenodo DOI
- All statistical parameters and software versions explicitly reported
- Use of exclusively open-source or free-web tools (XCMS, R, MetaboAnalyst, GNPS)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
