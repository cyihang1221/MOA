# Skill: Optimal transport for automatic alignment of untargeted metabolomic data.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 87/100
- **source**: Breeur M et al. (2024), eLife, DOI: 10.7554/elife.91597, PMID: 38896449

## Analysis Goal
复现/对齐文献研究目标：Optimal transport for automatic alignment of untargeted metabolomic data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | LC-MS data acquisition | liquid chromatography-mass spectrometry | — | `—` |
| 2 | Data conversion to open format | ProteoWizard (msconvert) | centroiding | `filter=peakPicking true 1-3` |
| 3 | Feature detection and extraction | XCMS | centWave | `ppm=10, snthr=10, prefilter=[3, 100], peakwidth=[5, 30], noise=0, bw=15, mzdiff=0.01, fitgauss=False, smooth=loess` |
| 4 | Retention time alignment across batches | GromovMatcher (v1.0.0) | Gromov-Wasserstein optimal transport | `lambda_reg=0.001, max_iter=100, tol=1e-06, n_jobs=-1, use_intensity_correlation=True, distance_metric=correlation` |
| 5 | Gap filling and missing value imputation | missForest | random forest-based imputation | `ntree=100, maxiter=5` |
| 6 | Feature filtering | custom R script | variance-based filtering | `cv_threshold=0.3, nonzero_fraction=0.5` |
| 7 | Normalization and scaling | MetaboAnalystR (v3.2.0) | Pareto scaling | `method=pareto` |
| 8 | Statistical analysis and biomarker discovery | limma | empirical Bayes moderated t-test | `adjust_method=BH, p_threshold=0.05, logFC_threshold=0.585` |
| 9 | Metabolite annotation | GNPS | MS/MS molecular networking | `precursor_mass_tol=0.02, fragment_mass_tol=0.02, min_peaks_match=6` |
| 10 | Pathway enrichment analysis | MetaboAnalyst (v5.0) | hypergeometric test with FDR correction | `database=HMDB, organism=Homo sapiens, method=Fisher exact, fdr_threshold=0.05` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic overview of GromovMatcher’s optimal transport-based alignment workflow applied to untargeted LC-MS datasets. | Inkscape | [4] |
| Figure 2 | pca_scores | PCA scores plots comparing alignment performance of GromovMatcher vs. other methods on simulated and split-validation datasets. | ggplot2 | [4, 7] |
| Figure 3 | volcano_plot | Volcano plot showing differentially abundant features associated with alcohol intake in liver and pancreatic cancer cohorts after GromovMatcher alignment. | limma moderated t-test, BH-adjusted p < 0.05, \|log2FC\| > 0.585 | [8] |
| Figure 4 | pathway_map | Pathway enrichment map highlighting significantly altered metabolic pathways (e.g., ethanol degradation, glutathione metabolism) linked to alcohol intake. | Hypergeometric test, FDR < 0.05 | [10] |
| Figure 5 | boxplot | Boxplots of selected aligned features (e.g., acetaldehyde, glutathione disulfide) across alcohol-intake strata in combined cancer cohorts. | Wilcoxon rank-sum test | [4, 8] |

## Parameter Highlights

- **Step 2 (ProteoWizard (msconvert))**: `filter=peakPicking true 1-3`
- **Step 3 (XCMS)**: `ppm=10, snthr=10, prefilter=[3, 100], peakwidth=[5, 30], noise=0, bw=15, mzdiff=0.01, fitgauss=False, smooth=loess`
- **Step 4 (GromovMatcher (v1.0.0))**: `lambda_reg=0.001, max_iter=100, tol=1e-06, n_jobs=-1, use_intensity_correlation=True, distance_metric=correlation`
- **Step 5 (missForest)**: `ntree=100, maxiter=5`
- **Step 6 (custom R script)**: `cv_threshold=0.3, nonzero_fraction=0.5`
- **Step 7 (MetaboAnalystR (v3.2.0))**: `method=pareto`
- **Step 8 (limma)**: `adjust_method=BH, p_threshold=0.05, logFC_threshold=0.585`
- **Step 9 (GNPS)**: `precursor_mass_tol=0.02, fragment_mass_tol=0.02, min_peaks_match=6`
- **Step 10 (MetaboAnalyst (v5.0))**: `database=HMDB, organism=Homo sapiens, method=Fisher exact, fdr_threshold=0.05`

## Reproducibility Notes

- All code publicly available under MIT license with Zenodo DOI
- Raw and processed data deposited in MetaboLights and GitHub
- Uses exclusively open-source or free web tools (no commercial software dependencies)
- Validation via reproducible dataset split procedure

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
