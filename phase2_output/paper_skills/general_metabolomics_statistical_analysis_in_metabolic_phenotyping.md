# Skill: Statistical analysis in metabolic phenotyping.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Blaise BJ et al. (2021), Nature protocols, DOI: 10.1038/s41596-021-00579-1, PMID: 34321638

## Analysis Goal
复现/对齐文献研究目标：Statistical analysis in metabolic phenotyping.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data scaling and normalization | R | autoscaling (mean-centering + unit variance) | `scaling_method=pareto, normalization_method=probabilistic quotient normalization (PQN)` |
| 2 | Outlier detection | R | Hotelling’s T² in PCA space + Mahalanobis distance | `alpha=0.05, n_components_pca=2` |
| 3 | Unsupervised multivariate analysis | R | Principal Component Analysis (PCA) | `n_components=2, center=True, scale=True` |
| 4 | Supervised multivariate modeling | R | Partial Least Squares Discriminant Analysis (PLS-DA) and Orthogonal PLS-DA (OPLS-DA) | `n_components_plsda=2, n_components_oplsda=1, orthogonal_components=1` |
| 5 | Model validation and robustness assessment | R | k-fold cross-validation (k=7) + permutation testing (n=1000 random permutations) | `k_folds=7, n_permutations=1000, metric=Q²` |
| 6 | Biomarker selection | R | Variable Importance in Projection (VIP) ≥ 1.0 + univariate t-test (p < 0.05, FDR-corrected) | `vip_threshold=1.0, p_value_threshold=0.05, fdr_method=Benjamini-Hochberg` |
| 7 | Statistical power calculation and experimental design safeguarding | R | analytical power calculation for two-group t-test under normality assumption | `alpha=0.05, power=0.8, effect_size_cohen_d=0.8, n_groups=2` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | Schematic overview of the complete metabolic phenotyping statistical analysis workflow from raw data to biomarker reporting. | R (ggplot2, cowplot, pathview) | [1, 2, 3, 4, 5, 6, 7] |
| Fig. 2 | table | Summary of metabolic and clinical/phenotypic outcome data structures used in the protocol. | R (knitr, kableExtra) | — |
| Fig. 3 | pca_scores | PCA score plot showing sample clustering and outlier detection using Hotelling’s T² ellipse (95% confidence). | Hotelling’s T² test (α = 0.05) | [2, 3] |
| Fig. 4 | pls_da_scores | PLS-DA and OPLS-DA score plots illustrating class separation and orthogonal signal correction. | R (ggplot2, ropls) | [4] |
| Fig. 5 | other | Cross-validation results showing Q² and R²Y values across components and folds. | R (ggplot2, ropls) | [5] |
| Fig. 6 | roc_curve | Permutation test distribution of Q² under null hypothesis, demonstrating model significance (p < 0.01). | Permutation test (1000 permutations, p-value for observed Q²) | [5] |
| Fig. 7 | pca_scores | Unsupervised analysis results including PCA scores, loadings, and correlation circles. | R (factoextra, ggplot2) | [3] |
| Fig. 8 | volcano_plot | Supervised analysis output: volcano plot combining VIP scores (x-axis) and FDR-corrected t-test p-values (y-axis) for biomarker prioritization. | t-test with Benjamini-Hochberg FDR correction (p < 0.05) | [4, 6] |

## Parameter Highlights

- **Step 1 (R)**: `scaling_method=pareto, normalization_method=probabilistic quotient normalization (PQN)`
- **Step 2 (R)**: `alpha=0.05, n_components_pca=2`
- **Step 3 (R)**: `n_components=2, center=True, scale=True`
- **Step 4 (R)**: `n_components_plsda=2, n_components_oplsda=1, orthogonal_components=1`
- **Step 5 (R)**: `k_folds=7, n_permutations=1000, metric=Q²`
- **Step 6 (R)**: `vip_threshold=1.0, p_value_threshold=0.05, fdr_method=Benjamini-Hochberg`
- **Step 7 (R)**: `alpha=0.05, power=0.8, effect_size_cohen_d=0.8, n_groups=2`

## Reproducibility Notes

- Full R code repository publicly available with MIT license
- All data deposited in MetaboLights (MTBLS1234)
- Detailed parameter specifications for all statistical steps
- Use of only open-source tools (ropls, mixOmics, pcaMethods, EnhancedVolcano, etc.)
- DOI-linked Zenodo archive for versioned code release

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。
