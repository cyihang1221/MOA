---
name: volcano-plot
display_name: 火山图与 log2FC 分布图出图规范
description: 火山图与 log2(Ratio) 分布图改图规范：横轴 log2FC、纵轴 −log10 p，两条互相垂直的阈值线，上调红下调蓝不显著灰；阈值来自结果文件
plot_types: [volcano, log2fc_hist]
pairs_with: [rohart-2017-mixomics, wen-2017-metax, pang-2024-metaboanalyst6, metaboanalyst5-protocol-2022, consensus_statistical_analysis, statistical_analysis_using_metaboanalyst_5_0_for_lc_hrms_spectra_proce, general_metabolomics_statistical_analysis_in_metabolic_phenotyping, "branch:lcms-untargeted", "branch:gcms-untargeted", "branch:lcms-targeted"]
references: [10.1142/S0219720012310038, 10.1007/s11306-006-0037-z, 10.1093/nar/gkab382, 10.1038/nmeth.1618, 10.1038/s41467-020-19160-7]
suggest: 火山图按出图规范来：上调红下调蓝，不显著的灰点淡一点，阈值虚线留着，p 和 fold change 阈值别改。
---

# 火山图与 log2FC 分布图出图规范

## 适用场景

- 数据来源：Agent B mixOmics 步骤的 `volcano_results.csv`（log2FC、pvalue、padj、neglog10p），metaX 的 log2(Ratio) 分布。
- 对应分析 Skill：mixOmics、metaX、MetaboAnalyst，以及 LC-MS / GC-MS 论文 Skill 里的两组差异代谢物筛选。
- 渲染：`r_plots/render_edit.R` 的 `draw_volcano`；分类结果另存 `*.classified.csv`。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| Volcano plot | 横轴 log2 fold change，纵轴 −log10 p（或 padj）；±log2FC 竖线与 p 横线为虚线 | 火山图把未标准化信号与标准化信号对照；双重过滤即两条垂直阈值线 |
| log2(Ratio) distribution | log2 比值直方图，标出 0 与 ±阈值 | 查看整体偏移与阈值两侧的特征数 |

- 建议：上调红、下调蓝、不显著灰，避免红绿搭配（色觉缺陷读者分不清）。
- 建议：图注写明纵轴是原始 p 还是 FDR 校正后的 padj，以及两条阈值的数值；特征多时优先报告校正后的结果。
- 建议：上调 / 下调数目写进图注或图例，数目以 `*.classified.csv` 为准。

```yaml
figures:
  - plot_type: volcano
    title_align: left
    legend_position: right
    font_size: {title: 14, axis: 11, legend: 10, label: 9}
    colors: {upregulated: "#E64B35", downregulated: "#4DBBD5", nonsignificant: "#B0B0B0", threshold_color: "#666666"}
    basis: "log fold change against -log10 p with two perpendicular cut lines (10.1142/S0219720012310038)"
  - plot_type: log2fc_hist
    title_align: left
    font_size: {title: 14, axis: 11, legend: 10, label: 9}
    basis: "distribution of log2 ratios before filtering"
```

## 出图边界（改图时只动样式）

- 可改：三类点的颜色、点透明度、标题、字号、图例位置、阈值线颜色。
- 不改：p / padj 阈值、log2FC 阈值、用 pvalue 还是 padj。用户在指令里写明数字时才按"分析参数"处理，并保留原始结果文件不动。
- 火山图不按 metadata 列着色（每个点是特征，不是样本）。

## 文献依据

- Li W 2012, J Bioinform Comput Biol：火山图把 log fold change 与 t 统计量或 −log10 p 对照；双重过滤准则在火山图上是两条垂直阈值线。DOI 10.1142/S0219720012310038
- Broadhurst DI, Kell DB 2007, Metabolomics：代谢组学多重检验与假发现的统计策略。DOI 10.1007/s11306-006-0037-z
- Pang Z 等 2021, Nucleic Acids Res：MetaboAnalyst 5.0 的统计与功能分析模块。DOI 10.1093/nar/gkab382
- Wong B 2011, Nat Methods：色盲友好配色。DOI 10.1038/nmeth.1618
- Crameri F 等 2020, Nat Commun：红–绿配色对色觉缺陷读者不可读。DOI 10.1038/s41467-020-19160-7
