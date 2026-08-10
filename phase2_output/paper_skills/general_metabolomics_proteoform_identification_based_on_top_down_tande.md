# Skill: Proteoform identification based on top-down tandem mass spectra with peak error corrections.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Zhan Z et al. (2022), Briefings in bioinformatics, DOI: 10.1093/bib/bbab599, PMID: 35136947

## Analysis Goal
复现/对齐文献研究目标：Proteoform identification based on top-down tandem mass spectra with peak error corrections.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Proteoform mass graph (PMG) construction | TopMGRefine | graph-based proteoform representation | `—` |
| 2 | Spectrum mass graph (SMG) construction | TopMGRefine | peak connectivity graph from top-down MS/MS spectrum | `error_range_per_peak=predefined` |
| 3 | Exact-mass-constrained alignment of PMG and SMG | TopMGRefine | maximum node-pair matching under global mass consistency constraint | `mass_consistency_constraint=exact match between sub-path masses in PMG and corrected peak intervals in SMG` |
| 4 | Diagonal alignment for scalability | TopMGRefine | heuristic diagonal traversal of alignment space | `—` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 2 (TopMGRefine)**: `error_range_per_peak=predefined`
- **Step 3 (TopMGRefine)**: `mass_consistency_constraint=exact match between sub-path masses in PMG and corrected peak intervals in SMG`

## Reproducibility Notes

- Full source code publicly available on GitHub
- Test datasets included in the repository
- Algorithmic constraints and error model explicitly defined
- Open-source MIT license

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
