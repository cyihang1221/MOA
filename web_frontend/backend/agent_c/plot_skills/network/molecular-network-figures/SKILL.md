---
name: molecular-network-figures
display_name: 分子网络与网络质控图出图规范
description: GNPS / FBMN 分子网络拓扑图与余弦、度数、家族大小、前体质量差、注释传播、组强度等网络质控图的改图规范：节点按属性着色，边淡灰，孤立点可隐藏，阈值线来自组网参数
plot_types: [network_topology, cosine_hist, degree_hist, family_size, precursor_mass_diff, pearson_hist, annotation_propagation, fbmn_group_intensity, chemical_class_distribution, family_chemical_consensus]
pairs_with: [wang-2016-gnps, nothias-2020-fbmn, gnps-fbmn-2020, ernst-2019-molnetenhancer, schmid-2021-iimn, watrous-2012-modified-cosine, huber-2020-matchms, huber-2021-spec2vec, huber-2021-ms2deepscore, li-2021-spectral-entropy, duyun-maojian-lcms-fochx-2026, consensus_molecular_networking, molecular_networking_reproducible_molecular_networking_of_untargeted_m, molecular_networking_sharing_and_community_curation_of_mass_spectromet, molecular_networking_different_grades_of_green_tea_duyun_maojian_a_com, molecular_networking_spec2vec_improved_mass_spectral_similarity_scorin, molecular_networking_open_access_repository_scale_propagated_nearest_n, general_metabolomics_statistical_analysis_of_feature_based_molecular_n]
references: [10.1038/s41592-020-0933-6, 10.1038/s41596-020-0317-5, 10.1038/nbt.3597, 10.1101/gr.1239303, 10.1038/nmeth.1618]
suggest: 网络图按出图规范来：按分子家族或分组着色，边淡一点，孤立点可以藏掉，余弦阈值线留着。
---

# 分子网络与网络质控图出图规范

## 适用场景

- 数据来源：Agent B GNPS / FBMN 组网步骤的 `network_nodes.csv`、`network_edges.csv`、`enhanced_nodes.csv`，以及 MolNetEnhancer 化学类别结果。
- 对应分析 Skill：GNPS、FBMN、MolNetEnhancer、IIMN、modified cosine、matchms、Spec2Vec、MS2DeepScore、spectral entropy，以及都匀毛尖等带分子网络的论文 Skill。

## 出图清单

| 图 | 编码 | 依据 |
|---|---|---|
| Molecular Network Topology | 节点 = 谱图或 LC-MS 特征，边 = 谱图相似度，连通分量 = 分子家族；节点按家族或属性着色 | 分子网络把 MS2 数据组织成结构相关的家族；特征信息与统计结果可映射到节点 |
| Cosine / Pearson distribution | 边相似度分布，竖线标出组网阈值 | 阈值来自组网参数 |
| Degree / family size | 节点度数、家族大小分布 | 网络质控 |
| Precursor mass difference | 相连节点前体质量差分布 | 提示常见修饰或加合物差 |
| Annotation propagation | 直接注释与传播注释分色计数 | 区分库匹配与网络传播 |
| FBMN group intensity | 各组特征强度对比 | FBMN 支持定量比较 |
| Chemical class / family consensus | 化学类别构成与家族一致性 | MolNetEnhancer 类别注释 |

- 建议：边用浅灰，节点颜色承担主要信息；节点按属性着色或定大小时在图例写明映射。
- 建议：拓扑总览图可隐藏孤立节点（singleton），图注写明隐藏了多少个。
- 建议：直接注释与传播注释的两种颜色要能被色觉缺陷读者区分，色盲友好时用蓝 #0072B2 与橙红 #D55E00。

```yaml
figures:
  - plot_type: network_topology
    title_align: left
    hide_isolates: true
    colors: {edge_color: "#c8c8c8"}
    font_size: {title: 14, axis: 11, legend: 10, label: 8}
    basis: "features mapped onto network nodes; families are connected components (10.1038/s41592-020-0933-6)"
  - {plot_type: cosine_hist, title_align: left, colors: {histogram_color: "#4DBBD5", threshold_color: "#E64B35"}, basis: "edge similarity distribution with the networking cut line"}
  - {plot_type: pearson_hist, title_align: left, colors: {histogram_color: "#4DBBD5", threshold_color: "#E64B35"}, basis: "correlation distribution with the cut line"}
  - {plot_type: degree_hist, title_align: left, colors: {histogram_color: "#4DBBD5"}, basis: "node degree distribution for network QC"}
  - {plot_type: family_size, title_align: left, basis: "molecular family size distribution"}
  - {plot_type: precursor_mass_diff, title_align: left, basis: "precursor mass difference between linked nodes"}
  - {plot_type: annotation_propagation, title_align: left, basis: "library matches versus propagated annotations"}
  - {plot_type: fbmn_group_intensity, title_align: left, legend_position: right, basis: "feature intensity by sample group (10.1038/s41592-020-0933-6)"}
  - {plot_type: chemical_class_distribution, title_align: left, basis: "chemical class composition"}
  - {plot_type: family_chemical_consensus, title_align: left, basis: "chemical class consensus within families"}
```

## 出图边界（改图时只动样式）

- 可改：节点 / 边颜色、孤立点显示、标题、字号、直方图颜色、图例位置。
- 不改：余弦阈值、最少匹配峰数、家族大小上限等组网参数。这些要回到 Agent B 重新组网。

## 文献依据

- Nothias LF 等 2020, Nat Methods：FBMN 基于色谱特征检测与对齐，支持定量分析与异构体区分；LC-MS 特征信息或统计结果可直接映射到网络节点，可在浏览器或 Cytoscape 中查看。DOI 10.1038/s41592-020-0933-6
- Aron AT 等 2020, Nat Protoc：GNPS 分子网络可复现流程，把 MS2 数据组织成结构相关的分子网络并联系样本元数据。DOI 10.1038/s41596-020-0317-5
- Wang M 等 2016, Nat Biotechnol：GNPS 社区共享与整理 MS/MS 数据，基于分子网络组织谱图。DOI 10.1038/nbt.3597
- Shannon P 等 2003, Genome Res：Cytoscape 把网络与表达谱、表型等分子状态整合可视化。DOI 10.1101/gr.1239303
- Wong B 2011, Nat Methods：色盲友好配色。DOI 10.1038/nmeth.1618
