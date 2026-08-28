# Skill: Addressing Missing Data in GC × GC Metabolomics: Identifying Missingness Type and Evaluating the Impact of Imputation Methods on Experimental Replication.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 88/100
- **source**: Davis TJ et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c04093, PMID: 35881554

## Analysis Goal
复现/对齐文献研究目标：Addressing Missing Data in GC × GC Metabolomics: Identifying Missingness Type and Evaluating the Impact of Imputation Methods on Experimental Replication.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Missingness type identification | MetabImpute | statistical pattern analysis (e.g., missingness heatmap, proportion of missing values per feature/sample, Little's MCAR test) | `test_method=Little's MCAR test, significance_threshold=0.05` |
| 2 | Within-replicate imputation | MetabImpute | Gibbs sampler (for MAR), Random Forest (for MNAR) | `imputation_strategy=within_replicate, n_trees=100, n_iter=100, burn_in=20` |
| 3 | Comparison of imputation methods | MetabImpute | ['Gibbs sampler', 'Random Forest', 'zero', 'minimum', 'mean', 'median', 'half-minimum', 'Bayesian PCA', 'quantile regression for left-censored data'] | `methods=['gibbs', 'rf', 'zero', 'min', 'mean', 'median', 'half_min', 'bpca', 'qrilc']` |
| 4 | Reproducibility assessment of imputed data | MetabImpute | within-replicate coefficient of variation (CV) and Pearson/Spearman correlation across replicates | `metric=CV, correlation_method=Spearman, threshold_cv=0.3` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (MetabImpute)**: `test_method=Little's MCAR test, significance_threshold=0.05`
- **Step 2 (MetabImpute)**: `imputation_strategy=within_replicate, n_trees=100, n_iter=100, burn_in=20`
- **Step 3 (MetabImpute)**: `methods=['gibbs', 'rf', 'zero', 'min', 'mean', 'median', 'half_min', 'bpca', 'qrilc']`
- **Step 4 (MetabImpute)**: `metric=CV, correlation_method=Spearman, threshold_cv=0.3`

## Reproducibility Notes

- Raw and processed GC×GC metabolomics data publicly available on MetaboLights (MTBLS1876)
- Open-source R package MetabImpute with documented workflows and reproducible vignettes
- All imputation methods and evaluation metrics explicitly described and benchmarked
- Within-replicate imputation strategy clearly defined and validated

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
