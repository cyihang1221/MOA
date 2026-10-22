---
name: opls-model-diagnostics
display_name: OPLS-DA S-plot 与模型诊断图出图规范
description: S-plot、PLS-DA 置换检验、观测诊断（SD/OD）图的改图规范：S-plot 同时看协方差与相关，置换图标出原模型位置
plot_types: [splot, plsda_permutation, opls_outlier]
pairs_with: [szymanska-2012-plsda, rohart-2017-mixomics, consensus_statistical_analysis, "branch:lcms-untargeted", "branch:gcms-untargeted"]
references: [10.1021/ac0713510, 10.1007/s11306-007-0099-6, 10.1007/s11306-011-0330-3, 10.1002/cem.2627, 10.1371/journal.pcbi.1003833]
suggest: 这张模型诊断图按出图规范收一下：轴标题写清楚是哪个统计量，原模型的位置和参考线留着，数值别动。
---

# OPLS-DA S-plot 与模型诊断图出图规范

## 适用场景

- 数据来源：Agent B `statistical_analysis_simca`（S-plot、SD/OD 观测诊断）与 PLS-DA 置换检验结果。
- 对应分析 Skill：SIMCA PLS-DA（Szymańska 2012）、mixOmics，以及茶叶论文 Skill 里的 OPLS-DA 流程。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| OPLS-DA S-plot | 横轴为预测成分载荷（协方差，p[1]），纵轴为相关 p(corr)[1]；两端的点贡献大且可靠 | S-plot 同时可视化协方差与相关 |
| PLS-DA permutation | 置换模型的 R² / Q² 分布，标出原模型数值与经验 p 值 | 置换检验评估模型显著性 |
| Observation diagnostics (SD/OD) | 得分距离与正交距离，临界线来自模型结果 | 离群样本检查（SIMCA 常用诊断） |

- 建议：S-plot 的候选标志物用颜色或标签标出，图注说明筛选依据（例如 VIP 与 p(corr) 的组合），筛选数值来自结果文件。
- 建议：置换图写明置换次数，原模型用醒目颜色，与置换分布区分。
- 建议：图注说明 VIP 是否为 OPLS 版本（预测 / 正交成分的 VIP 含义不同）。

```yaml
figures:
  - plot_type: splot
    title_align: left
    font_size: {title: 14, axis: 11, legend: 10, label: 8}
    basis: "S-plot shows covariance and correlation together (10.1021/ac0713510)"
  - plot_type: plsda_permutation
    title_align: left
    font_size: {title: 14, axis: 11, legend: 10, label: 9}
    basis: "permutation testing for PLS-DA significance (10.1007/s11306-011-0330-3)"
  - plot_type: opls_outlier
    title_align: left
    font_size: {title: 14, axis: 11, legend: 10, label: 8}
    basis: "observation diagnostics; critical lines come from the model output"
```

## 出图边界（改图时只动样式）

- 可改：标题、字号、配色、标签显示、图例位置。
- 不改：置换次数、临界线位置、S-plot 的筛选数值。这些来自 Agent B 的模型结果，改它们需要重新分析。

## 文献依据

- Wiklund S 等 2008, Anal Chem：提出 S-plot，可视化代谢物与类别之间的协方差和相关，用于从 OPLS-DA 模型中挑选统计上与生化上都重要的代谢物。DOI 10.1021/ac0713510
- Westerhuis JA 等 2008, Metabolomics：交叉模型验证与置换检验；验证不当会得到过于乐观的结果。DOI 10.1007/s11306-007-0099-6
- Szymańska E 等 2012, Metabolomics：置换检验评估 PLS-DA 模型显著性，DQ² 与 Q² 需要更多置换次数。DOI 10.1007/s11306-011-0330-3
- Galindo-Prieto B 等 2014, J Chemometrics：OPLS 的 VIP 有四种变体，同时考虑预测与正交成分。DOI 10.1002/cem.2627
- Rougier NP 等 2014, PLoS Comput Biol：图注不可省、不要误导读者。DOI 10.1371/journal.pcbi.1003833
