# Redundant Feature Filtering — 冗余特征过滤与注释

冗余特征过滤是代谢组学流程中**峰分组之后、统计分析之前**的关键步骤。在 ESI 电离源中，一个代谢物会产生多重信号（[M+H]⁺、[M+Na]⁺、[M+K]⁺、[2M+H]⁺、同位素峰、源内碎片等），如果不加处理直接进行统计分析，会导致假阳性膨胀（如 100 个特征实际仅对应 ~45 个化合物）。

在完整分析管道中的位置：
```
格式转换 → 峰检测 → 峰对齐 → 峰分组 → **[冗余特征过滤]** → 缺失值填补 → 统计分析 → 差异特征提取 → 谱库注释 → 分子网络 → 通路富集
```

三种工具互补定位：
- **CAMERA**: 关注色谱共流出 + 质谱加合物规则（假谱图分组）
- **RAMClust**: 关注跨样本强度相关性 + 层次聚类（数据驱动）
- **mzAnnotation**: 关注精确质量的正向计算与反向推定（纯质谱维度）

---

## 1. CAMERA 假谱图注释与冗余识别 (redundant_feature_filtering_camera)

**KEYWORD: CAMERA, pseudospectra, adduct annotation, isotope annotation, neutral loss, pcgroup, redundant feature**

### 概述
CAMERA (Collection of Algorithms for MEtabolite pRofile Annotation) 是 Bioconductor 的经典代谢物注释 R 包。它通过假谱图（pseudospectra）分组将共流出的峰归类，然后进行同位素、加合物和中性丢失注释，标记同一代谢物的冗余信号形式。输出中 `pcgroup` 相同的特征应合并为单一代谢物进行下游分析。

### 参考
- Kuhl et al. "CAMERA: an integrated strategy for compound spectra extraction and annotation of liquid chromatography/mass spectrometry data sets." Analytical Chemistry, 2012, 84(1), 283–289.
- 官方文档: https://www.bioconductor.org/packages/release/bioc/html/CAMERA.html

### 核心算法
1. **假谱图分组 (groupFWHM)**: 基于 FWHM 模型的 RT 窗口，将共流出峰归入同一假谱图，模拟同一代谢物在 ESI 源中的多重信号
2. **同位素注释 (findIsotopes)**: 在假谱图内识别 ¹³C、³⁴S 等同位素峰（质量差 ~1.003 Da）
3. **EIC 相关性验证 (groupCorr)**: 通过 Pearson 相关系数验证假谱图内峰是否真正共流出
4. **加合物注释 (findAdducts)**: 基于规则表识别 [M+H]⁺、[M+Na]⁺、[M+K]⁺、[M-H₂O+H]⁺ 等 40+ 种加合物
5. **中性丢失筛选 (findNeutralLoss)**: 检测 -H₂O、-CO₂、-NH₃ 等已知中性丢失
6. **冗余标记**: 标记源内产物 (ips=True) 以便下游过滤

### 输入
- `input_dir`: 峰表 CSV 目录（来自 XCMS/data_preprocessing 的 feature_table.csv）
- 支持的列: feature_id, mz, rt, intensity

### 关键参数
- `polarity` (default="positive"): 电离模式 "positive" 或 "negative"
- `ppm` (default=10.0): 质量精度，用于 m/z 匹配
- `perfwhm` (default=0.6): FWHM 峰宽系数，控制假谱图 RT 窗口宽度
- `cor_eic_th` (default=0.75): EIC Pearson 相关阈值，低于此值的峰从假谱图移除
- `maxcharge` (default=3): 最大电荷数
- `maxiso` (default=4): 最大同位素数量

### 输出
- `{sample}_camera_annotated.csv` — 带注释的峰表（含 pcgroup, adduct, isotope, ips 列）
- `{sample}_camera_pseudospectra.csv` — 假谱图汇总
- `camera_redundant_features.csv` — 冗余特征报告
- `camera_summary.txt` — 统计摘要

### 使用场景
- LC-MS 非靶向代谢组学数据的加合物/同位素注释
- 在统计分析前去除冗余特征以减少假阳性
- pcgroup 信息可用于特征合并（同一 pcgroup → 单一代谢物）

---

## 2. RAMClust 特征聚类 (redundant_feature_filtering_ramclust)

**KEYWORD: RAMClust, feature clustering, hierarchical clustering, Pearson correlation, retention time similarity, dynamic tree cut, compound spectrum**

### 概述
RAMClust (RAnking and Merging Clusters) 通过分析行为相似性（保留时间 + 跨样本强度相关性）将源自同一化合物的多重信号聚类为"化合物谱"。与 CAMERA 不同，RAMClust 不依赖加合物规则表，而是通过数据驱动的相似性矩阵和层次聚类发现冗余模式。

### 参考
- Broeckling et al. "RAMClust: A Novel Feature Clustering Method Enables Spectral-Matching-Based Annotation for Metabolomics Data." Analytical Chemistry, 2014, 86(14), 6812–6817.
- 官方文档: https://cran.r-project.org/web/packages/RAMClustR/

### 核心算法
1. **RT 相似性**: S_rt = exp(-((rt_i - rt_j) / st)²)
2. **强度相关性**: 跨样本 Pearson/Spearman 相关系数
3. **联合相似性**: S_combined = S_rt^sr × cor^cor_weight
4. **层次聚类 (HCA)**: 基于相似性矩阵聚类
5. **动态树切割**: 确定最优聚类数
6. **谱图整合**: 每个聚类合并为"化合物"定量值
7. **分子离子推断**: 识别每个聚类中最可能是分子离子的特征

### 输入
- `input_dir`: 峰表 CSV 目录（需包含多样本定量列，即 feature_table.csv 格式）

### 关键参数
- `st` (default=5.0): RT 相似性参数，值越大 RT 窗口越宽
- `sr` (default=0.5): RT 相似性在总相似性中的权重
- `cor_method` (default="pearson"): 相关性方法 "pearson" 或 "spearman"
- `deep_split` (default=2): 动态树切割深度（2=中等, 1=保守, 3=激进）
- `min_module_size` (default=2): 最小聚类大小
- `normalize_method` (default="none"): 归一化方法 "none"/"pqn"/"median"
- `qc_tag`/`blank_tag`: QC 和 Blank 标签，用于 CV 过滤和空白扣除

### 输出
- `{sample}_ramclust_clusters.csv` — 聚类结果（每个特征的 cluster_id）
- `ramclust_compound_spectra.csv` — 化合物谱（聚类合并后的定量值）
- `ramclust_summary.txt` — 统计摘要

### 使用场景
- 需要数据驱动的冗余发现（不依赖加合物规则）
- 有多样的样本（≥ 6 个），能提供稳健的跨样本相关性
- 与 CAMERA 互补验证

---

## 3. mzAnnotation 精确质量注释 (redundant_feature_filtering_mzannotation)

**KEYWORD: mzAnnotation, exact mass, m/z annotation, adduct calculation, molecular mass, high-resolution mass spectrometry, HRMS**

### 概述
mzAnnotation 基于精确质量计算对高分辨质谱峰表进行 m/z 推定注释。它的核心是"正向计算 + 反向推定"——对每个推定分子质量计算其所有可能的加合物/同位素/转化产物的 m/z，然后反向在峰表中搜索匹配。支持 40+ 正离子和 30+ 负离子加合物规则。

### 参考
- mzAnnotation R package, aberHRML/jasenfinch: https://aberhrml.github.io/mzAnnotation/

### 核心算法
1. 遍历每个特征的观测 m/z，反推所有可能的分子质量
2. 对每个推定分子质量，正向预测其所有可能的加合物/同位素/转化产物的 m/z
3. 在峰表中搜索预测 m/z 的匹配
4. 基于 oidscore（唯一性评分）、quasi（准分子离子）、ips（源内产物）对关联关系排序
5. 标记冗余特征（ips + 同位素 + 非准分子离子）

### 输入
- `input_dir`: 峰表 CSV 目录

### 关键参数
- `polarity` (default="positive"): 电离模式
- `ppm` (default=5.0): 质量精度，HRMS 推荐 1–5 ppm
- `mzabs` (default=0.001 Da): 绝对 m/z 容差，适合 Orbitrap/FT-ICR
- `include_isotopes` (default=True): 是否进行同位素注释
- `include_transformations` (default=True): 是否进行化学转化注释（甲基化、乙酰化等）
- `filter_redundant_adducts` (default=True): 是否标记冗余加合物特征
- `min_oidscore` (default=0.3): 最小加合物唯一性评分
- `max_features` (default=15000): 最大处理特征数

### 输出
- `{sample}_mzannotation_results.csv` — 完整注释结果（含 annotation, molecular_mass, charge, oidscore, redundancy 列）
- `mzannotation_summary.txt` — 统计摘要

### 使用场景
- 高分辨质谱数据（Orbitrap, FT-ICR, Q-TOF）
- 纯质谱维度的冗余发现（与 CAMERA 互补）
- 需要正向/反向精确质量匹配

---

## 4. 冗余特征过滤综合管线 (redundant_feature_filtering_pipeline)

**KEYWORD: redundant feature filtering pipeline, combined annotation, CAMERA + mzAnnotation + RAMClust**

### 概述
串联运行 CAMERA → mzAnnotation → RAMClust 三个工具，输出综合冗余特征报告，全方位覆盖色谱、质谱和数据分析三个维度的冗余发现。

### 核心流程
1. **阶段 1**: CAMERA — 假谱图分组 + 加合物/同位素/中性丢失注释
2. **阶段 2**: mzAnnotation — 高分辨精确质量正向/反向推定
3. **阶段 3**: RAMClust — 基于分析行为的特征聚类
4. 输出综合冗余报告，整合三个工具的结果

### 输入
- `input_dir`: 峰表 CSV 目录
- `polarity` (default="positive"): 电离模式

### 输出
- `camera/` — CAMERA 结果子目录
- `mzannotation/` — mzAnnotation 结果子目录
- `ramclust/` — RAMClust 结果子目录
- `combined_redundant_report.csv` — 综合冗余特征报告

### 使用场景
- 完整冗余分析，需要多维度交叉验证
- 高分辨数据，有足够的样本数（≥ 6）

---

## 推荐工作流

```
data_preprocessing_xcms（XCMS 峰检测 + 峰对齐 + 峰分组）
    │
    └─→  feature_table.csv（峰表，含各样本定量列）
              │
              ├─→  redundant_feature_filtering_camera（假谱图 + 加合物注释）
              │         │
              │         └─→  pcgroup 列 → 合并同一 pcgroup 的特征
              │
              ├─→  redundant_feature_filtering_mzannotation（精确质量注释）
              │         │
              │         └─→  redundancy 列 → 过滤冗余特征
              │
              ├─→  redundant_feature_filtering_ramclust（特征聚类）
              │         │
              │         └─→  cluster_id 列 → 合并同一 cluster 的特征
              │
              └─→  redundant_feature_filtering_pipeline（一键完整管线）
                        │
                        └─→  combined_redundant_report.csv
                                  │
                                  └─→  去冗余后的特征表 → 缺失值填补 → 统计分析
```

**注意**: 冗余特征过滤应在缺失值填补和统计分析**之前**执行。同一个代谢物的多重信号如果作为独立特征进入统计检验，会因多重检验校正而降低统计功效（power），导致真正的差异代谢物被漏掉。
