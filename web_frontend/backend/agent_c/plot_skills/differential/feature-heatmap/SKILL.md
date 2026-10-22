---
name: feature-heatmap
display_name: 代谢物热图出图规范
description: Top VIP 热图、层次聚类热图、相对丰度热图、相关热图的改图规范：z-score 数据用以 0 为中心的蓝白红发散色标，非负数据用顺序色标，列上方加分组注释
plot_types: [heatmap_vip, hca_heatmap, relative_abundance_heatmap, correlation_heatmap]
pairs_with: [rohart-2017-mixomics, pang-2024-metaboanalyst6, metaboanalyst5-protocol-2022, consensus_statistical_analysis, statistical_analysis_using_metaboanalyst_5_0_for_lc_hrms_spectra_proce, "branch:lcms-untargeted", "branch:gcms-untargeted", "branch:lcms-targeted", "branch:targeted"]
references: [10.1186/1471-2164-7-142, 10.1093/bioinformatics/btw313, 10.1371/journal.pcbi.1005752, 10.1093/nar/gkab382, 10.1038/s41467-020-19160-7]
suggest: 热图按出图规范来：红蓝发散色标、白色对齐 0，列上方保留分组色条，行聚类留着，别改筛选阈值。
---

# 代谢物热图出图规范

## 适用场景

- 数据来源：Agent B mixOmics 步骤的 `heatmap_top_vip_matrix.csv`（log2 后按特征 autoscale，即行 z-score）；论文复现的 HCA、相对丰度与相关矩阵。
- 对应分析 Skill：mixOmics（CIM 聚类热图）、MetaboAnalyst，以及茶叶 / 食品论文 Skill 里的差异代谢物热图与聚类热图。
- 渲染：`heatmap_vip` 走 `r_plots/render_edit.R` 的 `draw_heatmap`（pheatmap）；其余热图走 Python 渲染器。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| Top VIP Heatmap | 行 = 特征，列 = 样本，色 = 行 z-score；列上方分组色条；行列层次聚类 | 聚类热图展示特征签名；带注释的热图更易读出模式 |
| HCA heatmap | 层次聚类热图，感知均匀的顺序色标（viridis） | 感知均匀色标如实反映数据变化 |
| Relative abundance heatmap | 非负相对丰度，顺序色标（YlOrRd） | 非负数据不用发散色标 |
| Correlation heatmap | −1 到 1 的相关系数，蓝白红发散色标 | 有自然中点（0）的数据用发散色标 |

- 建议（工程约定）：数据已经是行 z-score 时不再二次缩放；色标两端对称，白色落在 0。
- 建议：图注写明缩放方式（autoscale / pareto / 仅 log2），不同预处理会改变哪些代谢物主导图案。
- 建议：不用彩虹（jet）或红–绿色标。
- 建议：行数多时只展示方差最大或 VIP 最高的前 N 行，并在图注写明 N。

```yaml
figures:
  - plot_type: heatmap_vip
    title_align: left
    cmap: RdBu_r
    colors: {heatmap_low: "#2166AC", heatmap_mid: "#FFFFFF", heatmap_high: "#B2182B"}
    font_size: {title: 14, axis: 11, legend: 10, label: 8}
    basis: "row z-scored matrix with a diverging scale centred on 0; group annotation on columns (10.1093/bioinformatics/btw313)"
  - plot_type: hca_heatmap
    title_align: left
    cmap: viridis
    basis: "perceptually uniform sequential colour map (10.1038/s41467-020-19160-7)"
  - plot_type: relative_abundance_heatmap
    title_align: left
    cmap: YlOrRd
    basis: "non-negative values use a sequential colour map"
  - plot_type: correlation_heatmap
    title_align: left
    cmap: RdBu_r
    basis: "correlation from -1 to 1 uses a diverging colour map"
```

## 出图边界（改图时只动样式）

- 可改：色标与两端颜色、标题、字号、行名显示、展示行数。
- 不改：VIP 筛选阈值、缩放方式、聚类所用的特征集合。按新阈值筛选时原始矩阵不动，只写 `*.filtered.csv`。

## 文献依据

- van den Berg RA 等 2006, BMC Genomics：比较 centering、autoscaling、pareto、range、vast scaling 与 log / power 变换；autoscaling 与 range scaling 消除了排序对平均浓度的依赖。DOI 10.1186/1471-2164-7-142
- Gu Z 等 2016, Bioinformatics：ComplexHeatmap，带注释图形的并列热图能揭示高维数据的模式与关联。DOI 10.1093/bioinformatics/btw313
- Rohart F 等 2017, PLOS Comput Biol：mixOmics 用聚类热图（CIM）展示多组学特征签名。DOI 10.1371/journal.pcbi.1005752
- Pang Z 等 2021, Nucleic Acids Res：MetaboAnalyst 5.0 先以交互热图展示峰强度表。DOI 10.1093/nar/gkab382
- Crameri F 等 2020, Nat Commun：彩虹与红–绿色标扭曲数据；推荐感知均匀的顺序、发散、循环色标（如 viridis）。DOI 10.1038/s41467-020-19160-7
