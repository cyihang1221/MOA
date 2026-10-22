---
name: mass2motif-figures
display_name: MS2LDA Mass2Motif 图出图规范
description: Mass2Motif 概览、碎片 / 中性丢失、谱图–Motif 关联热图与网络图的改图规范：碎片与中性丢失用色觉缺陷可区分的两色，概率类热图用顺序色标
plot_types: [mass2motif_overview, mass2motif_fragments, motif_spectrum_heatmap, mass2motif_network]
pairs_with: [vanderhooft-2016-ms2lda, ernst-2019-molnetenhancer]
references: [10.1073/pnas.1608041113, 10.1038/nmeth.1618, 10.1038/s41467-020-19160-7]
suggest: Motif 图按出图规范收一下：碎片用橙红、中性丢失用蓝，热图用顺序色标，概率数值别动。
---

# MS2LDA Mass2Motif 图出图规范

## 适用场景

- 数据来源：Agent B MS2LDA 步骤的 Mass2Motif 结果（Motif 特征与概率、谱图–Motif 关联）。
- 对应分析 Skill：MS2LDA（van der Hooft 2016）、MolNetEnhancer。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| Mass2Motif overview | 每个 Motif 关联的谱图数等概览 | Mass2Motif 是共现的碎片 / 中性丢失模式 |
| Mass2Motif top fragments | 碎片与中性丢失按概率排序，两类用不同颜色 | 同上 |
| Spectrum–Mass2Motif association | 谱图 × Motif 关联强度，顺序色标 | 概率 / 重叠度是非负量 |
| Mass2Motif–spectrum network | Motif 节点与谱图节点用不同颜色区分 | 网络图编码两类节点 |

- 建议：碎片用橙红（#D55E00）、中性丢失用蓝（#0072B2），替代默认的红–绿搭配。
- 建议：图注写明 Motif 的筛选条件（概率、重叠度），数值来自结果文件。

```yaml
figures:
  - {plot_type: mass2motif_overview, title_align: left, basis: "Mass2Motifs are co-occurring fragment and neutral loss patterns (10.1073/pnas.1608041113)"}
  - {plot_type: mass2motif_fragments, title_align: left, colors: {fragment_color: "#D55E00", loss_color: "#0072B2"}, basis: "fragments and losses in two colours readers with colour-vision deficiency can separate (10.1038/nmeth.1618)"}
  - {plot_type: motif_spectrum_heatmap, title_align: left, basis: "association strength is non-negative; use a sequential colour map (10.1038/s41467-020-19160-7)"}
  - {plot_type: mass2motif_network, title_align: left, basis: "motif nodes and spectrum nodes coloured differently"}
```

## 出图边界（改图时只动样式）

- 可改：碎片 / 丢失颜色、标题、字号、展示前多少个 Motif 或碎片。
- 不改：Motif 数目、概率与重叠度阈值。这些要回到 Agent B 重跑 MS2LDA。

## 文献依据

- van der Hooft JJJ 等 2016, PNAS：MS2LDA 以无监督方式从碎裂谱中抽取共现的碎片与中性丢失模式（Mass2Motif）。DOI 10.1073/pnas.1608041113
- Wong B 2011, Nat Methods：色盲友好配色。DOI 10.1038/nmeth.1618
- Crameri F 等 2020, Nat Commun：红–绿配色对色觉缺陷读者不可读；按数据类型选顺序或发散色标。DOI 10.1038/s41467-020-19160-7
