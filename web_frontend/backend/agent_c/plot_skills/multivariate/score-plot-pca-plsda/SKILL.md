---
name: score-plot-pca-plsda
display_name: PCA / PLS-DA 得分图出图规范
description: PCA 与 PLS-DA 得分图改图规范：按分组着色、95% 置信椭圆、成分号轴标题；监督模型的分离要靠交叉验证与置换检验说明
plot_types: [pca, plsda]
pairs_with: [rohart-2017-mixomics, szymanska-2012-plsda, pang-2024-metaboanalyst6, metaboanalyst5-protocol-2022, pedregosa-2011-scikit-learn, consensus_statistical_analysis, statistical_analysis_using_metaboanalyst_5_0_for_lc_hrms_spectra_proce, general_metabolomics_statistical_analysis_in_metabolic_phenotyping, "branch:gcms-untargeted", "branch:lcms-untargeted", "branch:lcms-targeted", "branch:targeted"]
references: [10.1371/journal.pcbi.1005752, 10.1007/s11306-007-0099-6, 10.1007/s11306-011-0330-3, 10.2174/2213235X11301010092, 10.1002/cem.785, 10.1038/nmeth.1618]
suggest: 得分图按出图规范收一下：按分组着色，保留 95% 置信椭圆，图例放右侧，样本名挤就别标，数据和成分别动。
---

# PCA / PLS-DA 得分图出图规范

## 适用场景

- 数据来源：Agent B mixOmics 步骤的 `pca_scores.csv`、`plsda_scores.csv`，以及 SIMCA / MetaboAnalyst 风格的 PCA、PLS-DA 结果。
- 对应分析 Skill：mixOmics、SIMCA PLS-DA、MetaboAnalyst，及 GC-MS / LC-MS 茶叶与食品论文 Skill 里的 PCA、PLS-DA 得分图。
- 渲染：`r_plots/render_edit.R` 的 `draw_scores`（SIMCA 风格用 t 分布椭圆，ggplot 风格用正态椭圆加填充）。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| PCA score plot | 横纵轴为 PC1/PC2（轴标题写成分号），点色 = metadata Group，每组 95% 置信椭圆 | mixOmics 样本图（plotIndiv）；PCA 是无监督概览 |
| PLS-DA score plot | 横纵轴为 t[1]/t[2]，点色 = 类别，每组 95% 置信椭圆 | mixOmics PLS-DA 样本图带置信椭圆；监督模型需另行验证 |

- 建议：颜色只编码分组。QC 样本单独一色，不画椭圆（QC 不是生物组）。
- 建议：PLS-DA 组间分开不能单凭得分图下结论，图注或报告写交叉验证（Q²、分类错误率）与置换检验结果。
- 建议：组数不超过 8 时用离散色板；要色盲友好时换 Okabe–Ito 色板，按组依次取 #0072B2、#D55E00、#009E73、#CC79A7、#E69F00、#56B4E9、#F0E442、#000000。
- 样本数多（约 30 个以上）时样本名会互相遮挡，可关掉样本标签，只留椭圆和图例。

```yaml
figures:
  - plot_type: pca
    title_align: center
    legend_position: right
    ellipse: true
    font_size: {title: 14, axis: 11, legend: 10, label: 8}
    basis: "plotIndiv sample plot with confidence ellipses (10.1371/journal.pcbi.1005752)"
  - plot_type: plsda
    title_align: center
    legend_position: right
    ellipse: true
    font_size: {title: 14, axis: 11, legend: 10, label: 8}
    basis: "PLS-DA sample plot with ellipses; separation must be validated (10.1007/s11306-007-0099-6)"
```

## 出图边界（改图时只动样式）

- 可改：配色、椭圆开关、图例位置、字号、标题与对齐、样本标签、SIMCA / ggplot 风格、展示哪两个成分。
- 不改：缩放方式、样本集合、成分数与模型参数。重算 PCA / PLS-DA 要回到 Agent B。
- 椭圆只是按组的二维 95% 区域，用来看离散程度，不等于显著性检验。

## 文献依据

- Rohart F 等 2017, PLOS Comput Biol：mixOmics 的 PLS-DA / sPLS-DA 样本图配置信椭圆，分类性能用重复分层交叉验证评估。DOI 10.1371/journal.pcbi.1005752
- Westerhuis JA 等 2008, Metabolomics：PLSDA 容易过拟合，需交叉模型验证与置换检验；作者反对用 PLSDA 得分图推断组间差异。DOI 10.1007/s11306-007-0099-6
- Szymańska E 等 2012, Metabolomics：比较 NMC、AUROC、Q²、DQ² 四种诊断量，模型优化与评估放在双重交叉验证里，用置换检验看显著性。DOI 10.1007/s11306-011-0330-3
- Worley B, Powers R 2012, Curr Metabolomics：代谢组学 PCA / PLS 多元分析的用法与局限。DOI 10.2174/2213235X11301010092
- Barker M, Rayens W 2003, J Chemometrics：以判别为目标时 PLS 比 PCA 合适，说明两种得分图回答的问题不同。DOI 10.1002/cem.785
- Wong B 2011, Nat Methods（Points of view: Color blindness）：色盲友好配色。DOI 10.1038/nmeth.1618
