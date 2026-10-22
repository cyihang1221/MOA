---
name: figure-design-baseline
display_name: 论文复现柱图与组合图出图规范
description: 论文复现里的成分柱图、生物活性柱图、感官评分与组合图的改图规范：一图一个信息，误差线写明含义，组合图各面板分组颜色一致
plot_types: [constituent_bar, bioactivity_bar, sensory_scores, paper_fig2_composite, paper_fig5_composite]
pairs_with: ["branch:gcms-untargeted", "branch:lcms-untargeted", "branch:lcms-targeted", "branch:targeted"]
references: [10.1371/journal.pcbi.1003833, 10.1198/jcgs.2009.07098, 10.1038/nmeth.1618, 10.1038/s41467-020-19160-7]
suggest: 这张图按出图规范收一下：分组颜色和其他图保持一致，误差线和样本数写清楚，数据别动。
---

# 论文复现柱图与组合图出图规范

## 适用场景

- 数据来源：茶叶 / 食品论文复现产出的 TPC / TFC / TFAA 等成分表、生物活性测定、感官评分，以及论文 Fig.2 / Fig.5 组合图。
- 对应分析 Skill：`gcms-untargeted`、`lcms-untargeted`、`lcms-targeted`、`targeted` 目录下的论文 Skill（白茶、武夷岩茶、祁门红茶、黄山毛峰、都匀毛尖、金华白茶、海胆、桑叶乌龙、金银花糖等）。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| Constituent / bioactivity bar | 柱高 = 组均值，误差线 = SD 或 SEM（必须写明），可加显著性字母 | 一图一个信息、不误导读者 |
| Sensory scores | 各感官属性按组对比 | 同上 |
| Paper composite (Fig.2 / Fig.5) | 多面板组合，各面板分组颜色与图例一致 | 图形语法：同一变量用同一映射 |

- 建议：同一会话里各图的分组颜色保持同一映射（同一组在 PCA、柱图、热图里是同一颜色）。
- 建议：误差线写明是 SD 还是 SEM，以及每组样本数。
- 建议：不要信默认值，去掉无信息的装饰（底色、立体效果、多余网格）。
- 建议：配色避免红–绿搭配；色盲友好时按组依次取 Okabe–Ito 色：#0072B2、#D55E00、#009E73、#CC79A7、#E69F00、#56B4E9、#F0E442、#000000。

```yaml
figures:
  - {plot_type: constituent_bar, title_align: left, font_size: {title: 14, axis: 11, legend: 10, label: 9}, basis: "one message per figure; state what error bars mean (10.1371/journal.pcbi.1003833)"}
  - {plot_type: bioactivity_bar, title_align: left, font_size: {title: 14, axis: 11, legend: 10, label: 9}, basis: "one message per figure; state what error bars mean (10.1371/journal.pcbi.1003833)"}
  - {plot_type: sensory_scores, title_align: left, font_size: {title: 14, axis: 11, legend: 10, label: 9}, basis: "compare attributes across groups"}
  - {plot_type: paper_fig2_composite, title_align: left, basis: "same variable keeps the same aesthetic mapping across panels (10.1198/jcgs.2009.07098)"}
  - {plot_type: paper_fig5_composite, title_align: left, basis: "same variable keeps the same aesthetic mapping across panels (10.1198/jcgs.2009.07098)"}
```

## 出图边界（改图时只动样式）

- 可改：标题、字号、配色、图例位置、面板标题。
- 不改：均值、误差线、显著性标记，这些来自论文复现结果。

## 文献依据

- Rougier NP 等 2014, PLoS Comput Biol：十条规则（了解读者、明确信息、适配媒介、图注不可省、不要信默认值、有效用色、不误导、避免图表垃圾、信息优先于美观、选对工具）。DOI 10.1371/journal.pcbi.1003833
- Wickham H 2010, J Comput Graph Stat：图形语法把图拆成数据到美学的映射、几何对象与标度，ggplot2 即其实现。DOI 10.1198/jcgs.2009.07098
- Wong B 2011, Nat Methods：色盲友好配色。DOI 10.1038/nmeth.1618
- Crameri F 等 2020, Nat Commun：避免彩虹与红–绿色标。DOI 10.1038/s41467-020-19160-7
