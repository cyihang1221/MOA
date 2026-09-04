# Skill: Statistical analysis of feature-based molecular networking results from non-targeted metabolomics data.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Pakkir Shah AK et al. (2025), Nature protocols, DOI: 10.1038/s41596-024-01046-3, PMID: 39304763

## Analysis Goal
复现/对齐文献研究目标：Statistical analysis of feature-based molecular networking results from non-targeted metabolomics data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data cleanup and preprocessing of FBMN output table | R | custom filtering and imputation | `min_samples_per_feature=3, min_relative_abundance=0.01, imputation_method=minimum` |
| 2 | Normalization and scaling | R | probabilistic quotient normalization (PQN) followed by Pareto scaling | `pqn_reference=median, scaling=pareto` |
| 3 | Univariate statistical analysis | R | two-sided t-test with Benjamini-Hochberg FDR correction | `alpha=0.05, fdr_method=BH` |
| 4 | Multivariate statistical analysis | R | PLS-DA and PCA | `n_components_pca=2, n_components_plsda=2, cv_folds=7` |
| 5 | Statistical analysis using QIIME2 framework | QIIME2 | q2-statistics (PERMANOVA, ANCOM-BC) | `permanova_permutations=999, ancombc_alpha=0.05, ancombc_theta=0.01` |
| 6 | Python-based statistical analysis | Python | scikit-learn PLS-DA, scipy t-test | `random_state=42, n_jobs=-1` |
| 7 | Integration of statistical results into molecular network | Cytoscape | attribute-based node coloring and filtering | `color_by=log2_fold_change, size_by=VIP_score, filter_by_qvalue=0.05` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (R)**: `min_samples_per_feature=3, min_relative_abundance=0.01, imputation_method=minimum`
- **Step 2 (R)**: `pqn_reference=median, scaling=pareto`
- **Step 3 (R)**: `alpha=0.05, fdr_method=BH`
- **Step 4 (R)**: `n_components_pca=2, n_components_plsda=2, cv_folds=7`
- **Step 5 (QIIME2)**: `permanova_permutations=999, ancombc_alpha=0.05, ancombc_theta=0.01`
- **Step 6 (Python)**: `random_state=42, n_jobs=-1`
- **Step 7 (Cytoscape)**: `color_by=log2_fold_change, size_by=VIP_score, filter_by_qvalue=0.05`

## Reproducibility Notes

- All code provided as executable Jupyter Notebooks in R and Python
- Web application with GUI lowers barrier to entry
- Uses only open-source tools (R, Python, QIIME2, Cytoscape)
- Demonstration dataset publicly available on GNPS and GitHub
- Detailed step-by-step Supplementary Methods and Hitchhiker’s App guide

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。
