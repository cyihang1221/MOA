---
name: vip-bar
display_name: VIP 排名图出图规范
description: VIP 排名柱图改图规范：按 VIP 降序、虚线标出 VIP 阈值、柱色表示变化方向；阈值来自方案
plot_types: [vip_bar]
pairs_with: [rohart-2017-mixomics, szymanska-2012-plsda, pang-2024-metaboanalyst6, consensus_statistical_analysis, "branch:lcms-untargeted", "branch:gcms-untargeted", "branch:lcms-targeted"]
references: [10.1016/j.chemolab.2004.12.011, 10.1016/j.chemolab.2012.07.010, 10.1002/cem.2627, 10.1371/journal.pcbi.1005752]
suggest: VIP 图按出图规范收一下：按 VIP 从高到低排，VIP 虚线留着，上调红下调蓝，阈值别动。
---

# VIP 排名图出图规范

## 适用场景

- 数据来源：Agent B mixOmics / SIMCA 步骤的 `vip_scores.csv`；有 `volcano_results.csv` 时用 log2FC 给柱子定方向色。
- 对应分析 Skill：mixOmics、SIMCA PLS-DA、MetaboAnalyst，以及论文 Skill 里"VIP > 阈值且 p < 0.05"的差异代谢物筛选。
- 渲染：`r_plots/render_edit.R` 的 `draw_vip_bar`；通过阈值的特征另存 `*.filtered.csv`。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| VIP Scores | 横轴 VIP，纵轴特征（按 VIP 降序，展示前 N 个），虚线为 VIP 阈值，柱色 = 上调 / 下调 | VIP 是 PLS 的过滤类变量选择；mixOmics 载荷图按重要性排序并用颜色标组 |

- 建议：柱色表示变化方向（上调红、下调蓝），没有 log2FC 时用单一深蓝。
- 建议：特征名过长时截短（保留 ID 前缀），完整名称放在 `*.filtered.csv`。
- 建议：图注写明 VIP 来自哪个模型（PLS-DA 还是 OPLS-DA）以及阈值数值；OPLS 的 VIP 有多种定义。

```yaml
figures:
  - plot_type: vip_bar
    title_align: left
    font_size: {title: 14, axis: 11, legend: 10, label: 9}
    colors: {bar_color: "#3C5488", upregulated: "#E64B35", downregulated: "#4DBBD5", threshold_color: "#666666"}
    basis: "VIP filter for PLS variable selection; loadings ranked by importance and colored by group (10.1371/journal.pcbi.1005752)"
```

## 出图边界（改图时只动样式）

- 可改：柱色、标题、字号、展示前多少个特征（只影响展示）、阈值线颜色。
- 不改：VIP 阈值数值（方案默认值由 Agent A 给出）。用户写明新阈值时按"分析参数"处理，原始 `vip_scores.csv` 不动。

## 文献依据

- Chong IG, Jun CH 2005, Chemometr Intell Lab Syst：多重共线性下 PLS 变量选择方法（含 VIP）的性能比较，常被引用为"VIP > 1"经验规则的来源。DOI 10.1016/j.chemolab.2004.12.011
- Mehmood T 等 2012, Chemometr Intell Lab Syst：PLS 回归变量选择方法综述，VIP 属于过滤类方法。DOI 10.1016/j.chemolab.2012.07.010
- Galindo-Prieto B 等 2014, J Chemometrics：OPLS 的 VIP 四种变体。DOI 10.1002/cem.2627
- Rohart F 等 2017, PLOS Comput Biol：mixOmics 载荷图按重要性排序，颜色表示均值最高的样本组。DOI 10.1371/journal.pcbi.1005752
