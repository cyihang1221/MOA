---
name: pathway-enrichment-plots
display_name: KEGG 通路富集图出图规范
description: KEGG 富集气泡图、点图、条形图改图规范：通路按显著性排序，点大小 = 命中化合物数，颜色 = 显著性（越显著越红），长通路名换行
plot_types: [kegg_bubble, kegg_dotplot, kegg_barplot]
pairs_with: [kanehisa-2017-kegg, li-2013-mummichog, subramanian-2005-gsea, barupal-2017-chemrich, caspi-2016-biocyc, gillespie-2022-reactome, pang-2024-metaboanalyst6, consensus_pathway_enrichment, pathway_enrichment_comparative_metabolomics_with_metaboseek_reveals_fu, pathway_enrichment_ms2deepscore_a_novel_deep_learning_similarity_measu]
references: [10.21769/BioProtoc.3429, 10.1016/j.xinn.2021.100141, 10.1089/omi.2011.0118, 10.1093/nar/gkw1092, 10.1038/s41467-020-19160-7]
suggest: KEGG 富集图按出图规范收一下：通路按 FDR 排序，点大小是命中数，越显著越红，长名字换行，FDR 阈值别动。
---

# KEGG 通路富集图出图规范

## 适用场景

- 数据来源：Agent B 富集步骤的 `kegg_compound_enrich.csv`（ID、Description、Count、pvalue、p.adjust）。
- 对应分析 Skill：KEGG（Kanehisa 2017）、mummichog、GSEA、ChemRICH、BioCyc、Reactome、MetaboAnalyst 功能分析，以及 phase2 的通路富集 Skill。
- 渲染：`r_plots/render_edit.R` 的 `draw_kegg`（bubble / dotplot / barplot 三种）。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| KEGG bubble | 纵轴通路（按显著性排序），横轴命中化合物数，点大小 = Count，颜色 = −log10 FDR | 富集条目图同时表示命中数、富集倍数与显著性 |
| KEGG dotplot | 横轴 −log10 FDR，点大小 = Count，颜色 = FDR | enrichplot 点图惯例 |
| KEGG barplot | 条长 = Count，顺序与气泡图一致 | 条形图只表达命中数 |

- 建议：三种图的颜色方向保持一致（越显著越红），读者在图之间切换时不用重新理解色标。
- 建议：只展示 FDR 最小的前 N 条通路，图注写明 N 和 FDR 校正方法；通路名用 KEGG map 名，表里保留 map 编号。
- 建议：通路多且重复时先去冗余再作图，避免条目过多看不清。
- 建议：图注写明背景集合（全部检测到的化合物还是数据库全集），富集倍数依赖背景。

```yaml
figures:
  - plot_type: kegg_bubble
    title_align: left
    legend_position: right
    font_size: {title: 14, axis: 11, legend: 10, label: 9}
    colors: {enrich_high: "#B2182B", enrich_low: "#2166AC"}
    basis: "enriched terms plotted with hit count and significance (10.21769/BioProtoc.3429)"
  - plot_type: kegg_dotplot
    title_align: left
    legend_position: right
    font_size: {title: 14, axis: 11, legend: 10, label: 9}
    colors: {enrich_high: "#B2182B", enrich_low: "#2166AC"}
    basis: "enrichplot dot plot for enrichment results (10.1016/j.xinn.2021.100141)"
  - plot_type: kegg_barplot
    title_align: left
    font_size: {title: 14, axis: 11, legend: 10, label: 9}
    colors: {bar_color: "#3C5488"}
    basis: "bar length encodes the hit count only"
```

## 出图边界（改图时只动样式）

- 可改：颜色两端、条形颜色、标题、字号、图例位置、展示前多少条通路。
- 不改：FDR 阈值、富集方法与背景集合。按新 FDR 筛选时原始富集表不动，只写 `*.filtered.csv`。

## 文献依据

- Bonnot T 等 2019, Bio-protocol：用 ggplot2 画富集条目，同时表示命中数、富集倍数与显著性；先用 REVIGO 去冗余。DOI 10.21769/BioProtoc.3429
- Wu T 等 2021, The Innovation：clusterProfiler 4.0，enrichplot 生成可发表的富集图；fold enrichment = GeneRatio / BgRatio。DOI 10.1016/j.xinn.2021.100141
- Yu G 等 2012, OMICS：clusterProfiler 把富集分析与可视化组合成可复用流程。DOI 10.1089/omi.2011.0118
- Kanehisa M 等 2017, Nucleic Acids Res：KEGG 以通路图、BRITE 层级与模块表示高层功能。DOI 10.1093/nar/gkw1092
- Crameri F 等 2020, Nat Commun：避免彩虹与红–绿色标。DOI 10.1038/s41467-020-19160-7
