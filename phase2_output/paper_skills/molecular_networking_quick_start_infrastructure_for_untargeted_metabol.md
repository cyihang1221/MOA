# Skill: Quick-start infrastructure for untargeted metabolomics analysis in GNPS.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 88/100
- **source**: Leao TF et al. (2021), Nature metabolism, DOI: 10.1038/s42255-021-00429-0, PMID: 34244695

## Analysis Goal
复现/对齐文献研究目标：Quick-start infrastructure for untargeted metabolomics analysis in GNPS.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data upload and format conversion | GNPS | — | `—` |
| 2 | Molecular networking | GNPS Molecular Networking | cosine score | `minimum_cosine_score=0.7, minimum_matched_peaks=6, top_k_matches=10, precursor_mass_tolerance=0.02, fragment_mass_tolerance=0.02` |
| 3 | Multivariate statistical analysis | GNPS Multivariate Analysis | PCA, PLS-DA, OPLS-DA | `scaling=Pareto, cross_validation=7-fold, permutation_tests=100, VIP_threshold=1.0` |
| 4 | Feature detection and alignment | GNPS Feature Detection | CentWave (XCMS-based) | `peak_width_min=10, peak_width_max=60, mz_tolerance_ppm=20, sn_thresh=5` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | The quick-start interface of GNPS can be used for molecular networking and multivariate analysis. | GNPS web interface (D3.js, Plotly) | [2, 3] |

## Parameter Highlights

- **Step 2 (GNPS Molecular Networking)**: `minimum_cosine_score=0.7, minimum_matched_peaks=6, top_k_matches=10, precursor_mass_tolerance=0.02, fragment_mass_tolerance=0.02`
- **Step 3 (GNPS Multivariate Analysis)**: `scaling=Pareto, cross_validation=7-fold, permutation_tests=100, VIP_threshold=1.0`
- **Step 4 (GNPS Feature Detection)**: `peak_width_min=10, peak_width_max=60, mz_tolerance_ppm=20, sn_thresh=5`

## Reproducibility Notes

- All analysis performed via open, publicly accessible GNPS web platform
- Source code openly available on GitHub under MIT license
- Standardized workflows with documented parameters

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
