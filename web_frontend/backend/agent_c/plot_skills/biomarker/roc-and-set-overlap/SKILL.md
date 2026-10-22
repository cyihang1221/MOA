---
name: roc-and-set-overlap
display_name: ROC / AUC 与显著集合交集图出图规范
description: 单变量 ROC AUC 分布与显著特征集合交集（Venn）图的改图规范：AUC 以 0.5 为随机参照，报告置信区间；集合超过 3 个时改用 UpSet 矩阵
plot_types: [roc_auc_hist, significance_venn]
pairs_with: [wen-2017-metax, pang-2024-metaboanalyst6, breiman-2001-random-forests, pedregosa-2011-scikit-learn]
references: [10.1007/s11306-012-0482-9, 10.1109/TVCG.2014.2346248, 10.1371/journal.pcbi.1003833]
suggest: 这张图按出图规范收一下：AUC 图标出 0.5 随机参照，Venn 每块写数目，统计结果别动。
---

# ROC / AUC 与显著集合交集图出图规范

## 适用场景

- 数据来源：Agent B `statistical_analysis_metax` 的单变量 ROC AUC、显著特征集合交集结果。
- 对应分析 Skill：metaX、MetaboAnalyst 生物标志物模块、随机森林 / scikit-learn 分类模型。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| Univariate ROC AUC distribution | 各特征 AUC 的直方图，0.5 为随机分类参照 | AUC = 0.5 等同随机，1 为完美分类 |
| Significance set intersections | 2–3 个集合用 Venn，每块标数目；更多集合用 UpSet 矩阵 | 集合多时交集组合爆炸 |

- 建议：单个标志物或多变量模型的 ROC 曲线要附 AUC 置信区间，并说明模型如何得到。
- 建议：Venn 各集合的定义（哪种检验、哪个阈值）写进图注，数目来自结果文件。

```yaml
figures:
  - {plot_type: roc_auc_hist, title_align: left, font_size: {title: 14, axis: 11, legend: 10, label: 9}, basis: "AUC 0.5 is random classification; report confidence intervals (10.1007/s11306-012-0482-9)"}
  - {plot_type: significance_venn, title_align: left, font_size: {title: 14, axis: 11, legend: 10, label: 10}, basis: "beyond a few sets use a matrix layout of intersections (10.1109/TVCG.2014.2346248)"}
```

## 出图边界（改图时只动样式）

- 可改：标题、字号、配色、直方图分箱数。
- 不改：显著性阈值、AUC 计算方式、集合定义。

## 文献依据

- Xia J 等 2013, Metabolomics：生物标志物研究应报告 ROC 曲线与置信区间；AUC = 0.5 等同随机分类。DOI 10.1007/s11306-012-0482-9
- Lex A 等 2014, IEEE TVCG：集合数超过少数几个时交集组合爆炸，UpSet 用矩阵布局展示交集及其大小。DOI 10.1109/TVCG.2014.2346248
- Rougier NP 等 2014, PLoS Comput Biol：图注不可省、不要误导读者。DOI 10.1371/journal.pcbi.1003833
