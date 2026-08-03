# Molecular Networking — 分子网络分析

分子网络分析是代谢组学流程中**谱库注释之后的关键步骤**，它将差异代谢物通过 MS/MS 谱图相似度连接成"分子家族"，打破逐化合物孤立的视角，实现注释传播和结构相关性发现。

在完整分析管道中的位置：
```
格式转换 → 峰检测 → 峰对齐 → 峰分组 → [冗余特征过滤] → 缺失值填补 → 统计分析 → 差异特征提取 → 谱库注释 → **[分子网络分析]** → 通路富集
```

分子网络包含四种互补工具：GNPS、FBMN、MS2LDA、MolNetEnhancer。

---

## 1. GNPS 经典分子网络 (molecular_networking_gnps)

**KEYWORD: GNPS, molecular networking, cosine similarity, molecular family**

### 概述
基于 MS/MS 谱图余弦相似度的分子网络构建方法，是分子网络分析的基石工具。通过全对全谱图相似度计算，将结构相关的代谢物连接成"分子家族"（molecular families），同一家族中的化合物往往具有结构相关性（如同系物、衍生物）。

### 参考
- Wang et al. "Sharing and community curation of mass spectrometry data with Global Natural Products Social Molecular Networking." Nature Biotechnology, 2016, 34(8), 828–837.
- 官方平台: https://gnps.ucsd.edu

### 核心算法
1. 解析 MGF 谱图文件
2. 全对全 greedy 余弦相似度计算（使用 fragment m/z 和 intensity）
3. 按 min_cosine 和 min_matched_peaks 过滤边
4. 每个节点保留 top_k 条最强边
5. NetworkX 构建网络图 → 连通分量检测 → 分子家族

### 输入
- `input_mgf`: 差异代谢物的 differential_spectra.mgf（来自 extract_differential_features 的输出）

### 关键参数
- `min_cosine` (default=0.7): 最小余弦相似度。GNPS 经典阈值 0.7，探索性分析可降至 0.6
- `min_matched_peaks` (default=6): 最小匹配碎片峰数，排除偶然匹配
- `fragment_tol` (default=0.02 Da): 碎片离子匹配容差
- `top_k` (default=10): 每节点保留的最强边数

### 输出
- `molecular_network.graphml` — Cytoscape 可直接打开的网络图
- `network_edges.csv` — 边表（source, target, cosine, matched_peaks, delta_ppm）
- `network_nodes.csv` — 节点表（feature_id, precursor_mz, rt, degree, molecular_family）
- `network_clusters.csv` — 分子家族汇总
- `network_summary.txt` — 统计摘要

### 使用场景
- 差异代谢物 MS/MS 谱图数量在 10–500 之间
- 需要发现结构相关的化合物群（同系物、衍生物）
- 为 MolNetEnhancer 提供网络拓扑基础

---

## 2. FBMN 特征基分子网络 (molecular_networking_fbmn)

**KEYWORD: FBMN, feature-based molecular networking, quantitative correlation, Pearson**

### 概述
在经典 GNPS 基础上的增强版本。节点携带完整的定量信息（各样本强度、log2FC、VIP），边同时包含谱图余弦相似度和样本间强度 Pearson 相关性。特别适合识别在特定实验条件下共调控的代谢物。

### 参考
- Nothias et al. "Feature-based molecular networking in the GNPS analysis environment." Nature Methods, 2020, 17(9), 905–908.

### 核心算法
1. 同 GNPS 的谱图余弦相似度计算
2. 额外计算节点间跨样本的 Pearson 强度相关系数
3. 边表同时包含 cosine + pearson_r 双重评分
4. 节点表包含各组的平均强度和 log2 fold change

### 输入
- `input_mgf`: differential_spectra.mgf
- `input_feature_table`: differential_feature_table.csv（需包含 feature_id, mz, rt_med 及各样本定量列）
- `metadata_csv` (optional): 样本元数据 CSV

### 关键参数
- `min_cosine` (default=0.7): 最小余弦相似度
- `min_matched_peaks` (default=4): FBMN 可设比 GNPS 低（4 vs 6），因为有定量相关性做二次过滤
- `min_correlation` (default=0.0): 最小 Pearson 相关系数。设为 0.5 可仅保留定量轮廓相关的边

### 输出
- `fbmn_network.graphml` — 带定量信息的网络图
- `fbmn_edges.csv` — 边表（cosine + pearson_r）
- `fbmn_nodes.csv` — 节点表（mz, rt, log2FC, VIP, 组均值）
- `fbmn_clusters.csv` — 分子家族汇总

### 使用场景
- 有完整的定量矩阵和分组信息
- 需要识别在特定实验条件下共调控的代谢物
- 后续 MolNetEnhancer 增强注释

---

## 3. MS2LDA 质谱潜在主题发现 (molecular_networking_ms2lda)

**KEYWORD: MS2LDA, Mass2Motif, LDA, substructure discovery, fragment co-occurrence**

### 概述
使用 Latent Dirichlet Allocation (LDA) 从 MS/MS 谱图中发现 Mass2Motifs——共现碎片离子的保守模式，代表了化学子结构或碎片特征。不依赖任何谱库，可对完全未知的化合物进行结构特征分析。

### 参考
- van der Hooft et al. "Topic modeling for untargeted substructure exploration in metabolomics." PNAS, 2016, 113(48), 13738–13743.
- 官方平台: https://ms2lda.org

### 核心算法
1. 碎片离散化 — 按 m/z 容差将碎片 bin 化为"词"
2. 构建文档-词矩阵 — 每个谱图是文档，碎片 bin 是词
3. sklearn LatentDirichletAllocation 训练
4. 主题 → Mass2Motif（每组共现碎片对应一个化学子结构模式）

### 输入
- `input_mgf`: differential_spectra.mgf

### 关键参数
- `n_motifs` (default=300): LDA 主题数，经验法则 ≈ n_spectra × 2
- `fragment_tol` (default=0.005 Da): 碎片离散化容差
- `n_iterations` (default=1000): LDA 最大迭代次数

### 输出
- `mass2motifs.csv` — 每个 Motif 的 top 碎片
- `spectra_motif_scores.csv` — 谱图 × Motif 概率矩阵
- `motif_fragment_distribution.csv` — 所有 Motif × 碎片分布

### 使用场景
- 谱图数量 > 20
- 探索性分析：无需谱库即可发现化学子结构模式
- 与 GNPS 互补 — MS2LDA 提供子结构层面的解读

---

## 4. MolNetEnhancer 分子网络增强注释 (molecular_networking_molnetenhancer)

**KEYWORD: MolNetEnhancer, network enhancement, annotation propagation, chemical classification, Cytoscape**

### 概述
将谱库注释结果映射到分子网络上，在每个分子家族内进行注释传播，并为节点推断化学分类。输出增强后的网络图，可在 Cytoscape 中按化学类别着色，实现"已知注释带动未知发现"。

### 参考
- Ernst et al. "MolNetEnhancer: Enhanced Molecular Networks by Integrating Metabolome Mining and Annotation." Metabolites, 2019, 9(7), 144.

### 核心操作
1. 将谱库注释（compound_name）映射到网络节点
2. 从化合物名称推断化学分类（如 flavonoids, alkaloids, lipids）
3. 分子家族内注释传播 — 邻居获得同样的推断化学类别
4. 输出增强网络，节点带 chemical_category 标签

### 输入
- `network_edges_csv`: GNPS/FBMN 输出的边表
- `network_nodes_csv`: GNPS/FBMN 输出的节点表
- `annotation_csv`: 谱库注释结果（来自 spectral_annotation），包含 feature_id 和 compound_name

### 关键参数
- `annotation_col` (default="compound_name"): 注释表中化合物名称列名

### 输出
- `enhanced_network.graphml` — 带化学分类的增强网络
- `enhanced_nodes.csv` — 增强节点表（含 chemical_category）
- `chemical_class_distribution.csv` — 化学类别分布
- `annotation_propagation_log.csv` — 注释传播记录

### 使用场景
- 已完成 GNPS 或 FBMN 网络构建
- 已完成谱库注释（spectral_annotation）
- 需要在 Cytoscape 中可视化化学类别分布
- 将已知注释传播给同一分子家族中的未知节点

---

## 推荐工作流

```
extract_differential_features（差异特征提取）
    │
    ├─→  differential_spectra.mgf
    │         │
    │         ├─→ molecular_networking_gnps（经典 GNPS 网络）
    │         │         │
    │         │         ├─→ network_edges.csv + network_nodes.csv
    │         │         │
    │         │         └─→ molecular_networking_molnetenhancer（增强注释）
    │         │                   │
    │         │                   └─→ enhanced_network.graphml（Cytoscape 可视化）
    │         │
    │         ├─→ molecular_networking_fbmn（如需定量信息）
    │         │
    │         └─→ molecular_networking_ms2lda（子结构发现）
    │
    └─→  spectral_annotation（谱库注释）
              │
              └─→ annotation CSV → 输入 MolNetEnhancer
```
