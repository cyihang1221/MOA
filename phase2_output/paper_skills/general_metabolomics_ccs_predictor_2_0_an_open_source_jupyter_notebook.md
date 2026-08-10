# Skill: CCS Predictor 2.0: An Open-Source Jupyter Notebook Tool for Filtering Out False Positives in Metabolomics.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Rainey MA et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.2c03491, PMID: 36473057

## Analysis Goal
复现/对齐文献研究目标：CCS Predictor 2.0: An Open-Source Jupyter Notebook Tool for Filtering Out False Positives in Metabolomics.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | CCS value prediction | CCS Predictor 2.0 (v2.0) | linear support vector regression | `mass_error_ppm=10, delta_ccs_threshold_percent=2.8, adducts_tested=['[M - H]-', '[M + H]+', '[M + Na]+'], training_set_customizable=True` |
| 2 | False positive filtering in metabolite annotation | CCS Predictor 2.0 (v2.0) | CCS-based structural filtering | `delta_ccs_threshold_percent=2.8, mass_error_ppm=10, retention_of_correct_annotations_percent=100, false_positive_reduction_percent=36.1` |
| 3 | Molecular descriptor calculation | Mordred | 1613 molecular descriptors | `—` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (CCS Predictor 2.0 (v2.0))**: `mass_error_ppm=10, delta_ccs_threshold_percent=2.8, adducts_tested=['[M - H]-', '[M + H]+', '[M + Na]+'], training_set_customizable=True`
- **Step 2 (CCS Predictor 2.0 (v2.0))**: `delta_ccs_threshold_percent=2.8, mass_error_ppm=10, retention_of_correct_annotations_percent=100, false_positive_reduction_percent=36.1`

## Reproducibility Notes

- Fully open-source Jupyter Notebook implementation
- Public GitHub repository with MIT license
- Uses only open-source dependencies (Mordred, scikit-learn)
- Validation performed on publicly available McLean CCS Compendium
- Explicit reporting of performance metrics (median relative error, % FP reduction, % correct retention)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
