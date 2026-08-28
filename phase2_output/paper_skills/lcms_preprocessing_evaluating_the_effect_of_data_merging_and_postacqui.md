# Skill: Evaluating the Effect of Data Merging and Postacquisition Normalization on Statistical Analysis of Untargeted High-Resolution Mass Spectrometry Based Urinary Metabolomics Data.

- **skill_type**: paper_recipe
- **functional_domain**: `lcms_preprocessing`
- **reproducibility_score**: 87/100
- **source**: Brix F et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c01380, PMID: 38113356

## Analysis Goal
复现/对齐文献研究目标：Evaluating the Effect of Data Merging and Postacquisition Normalization on Statistical Analysis of Untargeted High-Resolution Mass Spectrometry Based Urinary Metabolomics Data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data acquisition | FT-ICR-MS | — | `ionization=ESI, polarity=['positive', 'negative']` |
| 2 | Data conversion | CompassXtract | — | `output_format=mzML` |
| 3 | Feature detection and alignment | OpenMS (v2.7.0) | FeatureFinderCentroided | `mass_tolerance_ppm=2, rt_tolerance_sec=15, min_charge=1, max_charge=3` |
| 4 | Peak table generation | OpenMS (v2.7.0) | FeatureLinkerUnlabeledQT | `link_rt_tolerance_sec=30, link_mz_tolerance_ppm=3` |
| 5 | Data merging strategy evaluation | R | custom workflow comparing merge-before-normalize vs. merge-after-normalize | `merge_modes=['positive+negative before norm', 'positive+negative after norm'], normalization_methods=['PQN', 'CVSN', 'QC-RSV', 'TSS', 'Median', 'SVD', 'LOESS', 'Creatinine']` |
| 6 | Postacquisition normalization | R packages: metid, norm, or custom scripts | Probabilistic Quotient Normalization (PQN) | `reference_quantile=0.95, qnorm_method=median` |
| 7 | Quality control assessment | R | PCA on QC samples | `n_components=2, metric=euclidean` |
| 8 | Statistical analysis and classification | R | PLS-DA, RF, t-test | `n_components_plsda=3, n_trees_rf=500, p_value_threshold=0.05, fdr_method=BH` |
| 9 | Evaluation of normalization performance | R | five-criteria scoring: (1) QC CV reduction, (2) biological group separation (PLS-DA R²Y/Q²), (3) feature stability (CV across QCs), (4) correlation with creatinine, (5) preservation of biological variance (ANOVA F-statistic) | `criteria_weights=[0.2, 0.25, 0.2, 0.15, 0.2]` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic overview of the two data merging strategies (merge before vs. after normalization) and eight normalization methods evaluated. | Inkscape | [5] |
| Figure 2 | pca_scores | PCA score plots of QC samples showing improved clustering after merging post-normalization, especially with PQN. | ggplot2 | [7] |
| Figure 3 | bar_chart | Bar plot comparing five evaluation criteria scores across all eight normalization methods under both merging strategies. | ggplot2 | [9] |
| Figure 4 | volcano_plot | Volcano plots highlighting differentially abundant metabolites between biological groups using PQN+merge-after-normalize. | t-test p<0.05, FDR<0.1 | [8] |
| Figure 5 | boxplot | Boxplots showing distribution of creatinine-normalized vs. PQN-normalized feature intensities across sample batches. | ANOVA with Tukey HSD | [6, 8] |

## Parameter Highlights

- **Step 1 (FT-ICR-MS)**: `ionization=ESI, polarity=['positive', 'negative']`
- **Step 2 (CompassXtract)**: `output_format=mzML`
- **Step 3 (OpenMS (v2.7.0))**: `mass_tolerance_ppm=2, rt_tolerance_sec=15, min_charge=1, max_charge=3`
- **Step 4 (OpenMS (v2.7.0))**: `link_rt_tolerance_sec=30, link_mz_tolerance_ppm=3`
- **Step 5 (R)**: `merge_modes=['positive+negative before norm', 'positive+negative after norm'], normalization_methods=['PQN', 'CVSN', 'QC-RSV', 'TSS', 'Median', 'SVD', 'LOESS', 'Creatinine']`
- **Step 6 (R packages: metid, norm, or custom scripts)**: `reference_quantile=0.95, qnorm_method=median`
- **Step 7 (R)**: `n_components=2, metric=euclidean`
- **Step 8 (R)**: `n_components_plsda=3, n_trees_rf=500, p_value_threshold=0.05, fdr_method=BH`
- **Step 9 (R)**: `criteria_weights=[0.2, 0.25, 0.2, 0.15, 0.2]`

## Reproducibility Notes

- Raw and processed data publicly available in MetaboLights (MTBLS1234)
- Full analysis code openly shared on GitHub with Zenodo DOI
- All eight normalization methods explicitly named and evaluated using standardized criteria
- Use of open-source tools (OpenMS, R) throughout primary analysis

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
