# 代谢组学完整分析管道 — 阶段顺序与工具选择

本文档定义了从 Thermo .raw 原始数据到差异代谢物注释与通路富集的**完整 13 阶段管道顺序**，与 `paper_method_extractor_V1.py` 中 KEYWORDS 分类对齐。

LLM Agent 生成计划时：
- **文献优先**：若 RAG 检索到的文献中有与用户需求匹配的完整流程，优先采用文献的管线结构和工具选择
- **对比模式**：若文献中明确比较多款工具对同一任务的效果，可激活对比模式，使用多工具交叉验证
- **每阶段默认 1 步 1 工具**，除非激活对比模式
- 标注为 `[MANDATORY]` 的阶段必须执行，`[OPTIONAL]` 的阶段可根据数据/文献需求跳过
- 标注为 `⚠️ 已注释` 的工具在 MCP server 中存在代码但当前未激活，暂不可用

KEYWORD: pipeline, complete workflow, stage order, end-to-end, 完整流程, 全局管道, 13 stages

---

## 所有已注册 MCP 工具总览（按阶段分类）

### 阶段 1：数据格式转换 [MANDATORY]

**目标**: 原始质谱文件（.raw/.d/.wiff）→ .mzML 开放格式

**KEYWORDS**: ProteoWizard, ThermoRawFileParser, msconvert, OpenMS FileConverter

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `convert_raw_to_mzml_msconvert` | ✅ 可用 | Docker + ProteoWizard msconvert，通用 .raw → .mzML |
| `convert_raw_to_mzml_ThermoRawFileParser` | ✅ 可用 | ThermoRawFileParser CLI，Thermo 专用 |
| `convert_raw_to_mzml_OpenMS_FileConverter` | ✅ 可用 | OpenMS FileConverter，mzML/mzXML/mgf 互转 |
| `data_transformation_proteowizard` | ✅ 可用 | ProteoWizard 全流程：转换 + 峰检测 + 过滤 + 压缩 |
| `data_transformation_proteowizard_batch` | ✅ 可用 | ProteoWizard 批量模式，多输入目录 |

---

### 阶段 2：峰检测 [MANDATORY]

**目标**: .mzML → 色谱峰检测 → 特征列表（feature list）

**KEYWORDS**: XCMS-Centwave, MZMine-GirdMass, MZMine-ADAP, OpenMS-PeakPicking, OpenMS-FeatureFinderMetabo, KPIC, PITracer, TracMass, PeakOnly

#### 2a. 一体化预处理管线（含峰检测+对齐+分组，推荐优先使用）

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `data_preprocessing_xcms` | ✅ 可用 | **推荐**。XCMS 一站式：centWave + Obiwarp + PeakDensity + fill + 空白扣除 + MS2 提取 |
| `data_preprocessing_openms` | ✅ 可用 | OpenMS 一站式：PeakPickerHiRes + FeatureFinderMetabo + MapAlignerPoseClustering + FeatureLinkerUnlabeled |
| `data_preprocessing_mzmine` | ✅ 可用 | MZmine 一站式：GridMass + RANSAC + Join aligner + gap fill |
| `data_preprocessing_kpic` | ✅ 可用 | KPIC 纯 Python：核峰识别 + PIC 提取 + 高斯平滑 |
| `data_preprocessing_pitracer` | ✅ 可用 | PITracer 纯 Python：自动质量容差 + 饱和峰处理 |
| `data_preprocessing_tracmass` | ✅ 可用 | TracMass 纯 Python：模块化迹线 + 双零面积滤波 |
| `data_preprocessing_peakonly` | ✅ 可用 | PeakOnly 纯 Python：CNN 深度学习峰检测 |

#### 2b. 模块化峰检测工具（可单独使用或组合）

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `peak_picking_openms` | ✅ 可用 | OpenMS PeakPickerHiRes：高分辨质心化 + MGF 导出 |
| `feature_detection_openms` | ✅ 可用 | OpenMS FeatureFinderMetabo：质量迹线特征检测 |
| `peak_detection_mzmine_gridmass` | ✅ 可用 | MZmine GridMass：2D 探针峰检测 |
| `peak_detection_mzmine_adap` | ✅ 可用 | MZmine ADAP：色谱构建器 + 小波解析 |

---

### 阶段 3：冗余特征过滤 [MANDATORY]

**位置**: 峰检测之后、缺失值填补之前。同一代谢物的多重信号（加合物、同位素、源内碎片）必须在统计检验前合并，否则多重检验校正会降低统计功效。

**KEYWORDS**: CAMERA, RAMClust, mzAnnotation

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `redundant_feature_filtering_pipeline` | ✅ 可用 | **推荐**。一键串联 CAMERA → mzAnnotation → RAMClust，输出综合冗余报告 |
| `redundant_feature_filtering_camera` | ✅ 可用 | 仅 CAMERA：假谱图分组 + 加合物/同位素/中性丢失注释 |
| `redundant_feature_filtering_ramclust` | ✅ 可用 | 仅 RAMClust：RT 相似性 + 跨样本相关性 + HCA + 动态树切割 |
| `redundant_feature_filtering_mzannotation` | ✅ 可用 | 仅 mzAnnotation：45+ 正离子 / 27+ 负离子加合物规则 + 同位素注释 |

---

### 阶段 4：同位素识别 [OPTIONAL]

**目标**: 识别并注释特征中的同位素峰，区分单同位素峰与同位素簇

**KEYWORDS**: IsoXpress, OpenMS-IsotopeTools, TarMet, AssayR

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `isotope_analysis_openms` | ✅ 可用 | OpenMS MetaboliteAdductDecharger：电荷估计 + 加合物去卷积 |

> ⚠️ IsoXpress, TarMet, AssayR 暂无 MCP 实现。若无可用工具，此阶段可跳过。

---

### 阶段 5：谱峰对齐 [MANDATORY]

**目标**: 跨样本保留时间（RT）对齐 + 特征分组，将同一代谢物在不同样本中的信号归为同一特征

**KEYWORDS**: XCMS-Obiwarp, XCMS-LOESS, MZMine-JointAligner, OpenMS-PeakGroup, FFT-based, DTW-based

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `peak_group_alignment_openms` | ✅ 可用 | OpenMS MapAlignerPoseClustering + FeatureLinkerUnlabeled：RT 对齐 + 跨样本特征分组 |
| `align_features_mzmine_joint_aligner` | ✅ 可用 | MZmine Join Aligner：m/z + RT 加权对齐 |

> ⚠️ 一体化工具（2a 中的 XCMS/OpenMS/MZmine 管线）已内置对齐步骤，使用一体化工具时此阶段由管线自动完成。

---

### 阶段 6：缺失值填补 [MANDATORY]

**目标**: 低丰度/低出现率过滤 + 缺失值填补

**KEYWORDS**: kNN, MissForest, Bayesian PCA

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `feature_filtering_and_missing_value_imputation_knn` | ✅ 可用 | **唯一可用**。低丰度/低出现率过滤 + sklearn KNNImputer 缺失值填补 |

> ⚠️ MissForest, Bayesian PCA 暂无 MCP 实现。

---

### 阶段 7：批次效应校正 [OPTIONAL]

**目标**: 多批次实验间的系统误差校正

**KEYWORDS**: WaveICA, MetNormalizer, MetaboGroupS

| 工具名 | 状态 | 说明 |
|--------|------|------|
| — | ❌ 暂无 | WaveICA, MetNormalizer, MetaboGroupS 均未实现 |

> ⚠️ 若无可用工具或只有单批次数据，此阶段可跳过。

---

### 阶段 8：统计分析 [MANDATORY]

**目标**: PCA、PLS-DA、VIP 评分、差异代谢物筛选

**KEYWORDS**: metaX, mixOmics, scikit-learn, SIMCA, DeepLearning-based

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `statistical_analysis_mixomics` | ✅ 可用 | **唯一可用**。R mixOmics：PCA + PLS-DA + CV + VIP + 火山图 + 差异筛选 + 热图 |

---

### 阶段 9：差异特征提取 [MANDATORY]

**目标**: 从完整数据中提取差异代谢物的 MS/MS 谱图和特征表

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `extract_differential_features` | ✅ 可用 | **唯一可用**。从完整数据中提取差异代谢物的 MS/MS 谱图和特征表 |

---

### 阶段 10：谱库匹配定性 [MANDATORY]

**目标**: 实验 MS/MS 谱图与参考谱库匹配，鉴定代谢物结构

**KEYWORDS**: Jaccard, Cosine, Spectral entropy, Spec2Vec, MS2DeepScore, BLINK, MS-BERT

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `spectral_annotation` | ✅ 可用 | **推荐**。R Spectra + MetaboAnnotation：余弦匹配 GNPS + MoNA + Spectraverse 谱库，含 KEGG ID 映射 |
| `deepmass_annotation` | ✅ 可用 | Docker + DeepMASS2：Spec2Vec 语义相似度，适合未知物定性 |

---

### 阶段 11：未知物定性 [OPTIONAL]

**目标**: 对谱库匹配失败的未知代谢物进行从头结构鉴定

**KEYWORDS**: CFM-ID, SIRIUS, MS-Finder, DeepMASS, CSU-MS2, MetDNA, E-SGMN, NEIMS

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `deepmass_annotation` | ✅ 可用 | DeepMASS2：深度学习语义相似度，可用于未知物定性（与阶段 10 共享） |

> ⚠️ CFM-ID, SIRIUS, MS-Finder, CSU-MS2, MetDNA, E-SGMN, NEIMS 暂无 MCP 实现。

---

### 阶段 12：分子网络分析 [MANDATORY]

**位置**: 谱库注释之后、富集分析之前。将差异代谢物通过 MS/MS 谱图相似度连接成分子家族。

**KEYWORDS**: GNPS, FBMN, MS2LDA, MolNetEnhancer

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `molecular_networking_gnps` | ✅ 可用 | **推荐（最通用）**。经典 GNPS：全对全余弦相似度 + Top-K 边过滤 + 分子家族检测 |
| `molecular_networking_fbmn` | ✅ 可用 | 特征基分子网络：余弦相似度 + Pearson 定量相关性富集 |
| `molecular_networking_ms2lda` | ✅ 可用 | MS2LDA 子结构发现：LDA 主题模型 Mass2Motif，无谱库探索性分析 |
| `molecular_networking_molnetenhancer` | ✅ 可用 | 化学分类 + 注释传播，需依赖 GNPS/FBMN 的边表和节点表作为输入 |

---

### 阶段 13：富集与通路分析 [MANDATORY]

**目标**: 超几何检验富集分析，识别显著富集的代谢通路

**KEYWORDS**: MetaboAnalyst, mummichog, GSEA, ChemRICH, HMDB, KEGG, Reactome, BioCyc

| 工具名 | 状态 | 说明 |
|--------|------|------|
| `kegg_compound_enrichment` | ✅ 可用 | **唯一可用**。R clusterProfiler + Python KEGG REST API：ORA 富集 + 气泡图/点图/条形图 |

> ⚠️ MetaboAnalyst, mummichog, GSEA, ChemRICH, HMDB, Reactome, BioCyc 暂无 MCP 实现。

---

## 管道拓扑（阶段级依赖）

```
阶段1: 数据格式转换                          [MANDATORY]  [5个候选工具]
  │
  ▼
阶段2: 峰检测                                [MANDATORY]  [7个一体化 + 4个模块化]
  │    ⚠️ 一体化工具（XCMS/OpenMS/MZmine）同时覆盖阶段5对齐
  ▼
阶段3: 冗余特征过滤                           [MANDATORY]  [4个候选工具]
  │
  ▼
阶段4: 同位素识别                             [OPTIONAL]   [1个工具]
  │
  ▼
阶段5: 谱峰对齐                               [MANDATORY]  [2个模块化工具]
  │    ⚠️ 若阶段2使用一体化管线，此阶段已内置覆盖
  ▼
阶段6: 缺失值填补                             [MANDATORY]  [1个工具]
  │
  ▼
阶段7: 批次效应校正                           [OPTIONAL]   [0个工具 — 暂无]
  │
  ▼
阶段8: 统计分析                               [MANDATORY]  [1个工具]
  │
  ▼
阶段9: 差异特征提取                           [MANDATORY]  [1个工具]
  │
  ▼
阶段10: 谱库匹配定性                           [MANDATORY]  [2个候选工具]
  │
  ▼
阶段11: 未知物定性                             [OPTIONAL]   [1个工具 — 与阶段10共享DeepMASS]
  │
  ▼
阶段12: 分子网络分析                           [MANDATORY]  [4个候选工具]
  │
  ▼
阶段13: 富集与通路分析                         [MANDATORY]  [1个工具]
```

**总计: 13 个阶段（10 MANDATORY + 3 OPTIONAL），当前可用 MCP 工具: 33 个。**

---

## 新模式：文献驱动管线与对比模式

### 文献优先（Literature-First）

LLM Agent 在生成计划时遵循以下优先级：

1. **优先匹配文献流程**：若 RAG 检索到与用户数据类型和研究目标匹配的文献流程，直接采用该文献的管线结构（阶段顺序、工具选择、参数设置），跳过预设管线
2. **回退预设管线**：若无匹配文献，使用上述 13 阶段标准管线

### 多工具对比模式（Comparison Mode）

当文献中明确比较多款工具对同一任务的效果时（如"比较了 XCMS 和 MZmine 的峰检测性能"），LLM 可激活对比模式：

- 同一阶段创建多个步骤，每步使用不同的对比工具
- 阶段名添加 `[COMPARISON]` 标记
- 质量检查包含跨工具结果对比标准

---

## KEYWORDS 论文方法覆盖度统计

以下列出 `paper_method_extractor_V1.py` 中 KEYWORDS 对应的 MCP 工具实现状态：

### ✅ 已有 MCP 工具实现（KEYWORDS → MCP 工具名）

| 论文 KEYWORD | MCP 工具 | 对应阶段 |
|-------------|---------|---------|
| ProteoWizard | `data_transformation_proteowizard` | 阶段1 |
| ThermoRawFileParser | `convert_raw_to_mzml_ThermoRawFileParser` | 阶段1 |
| msconvert | `convert_raw_to_mzml_msconvert` | 阶段1 |
| OpenMS FileConverter | `convert_raw_to_mzml_OpenMS_FileConverter` | 阶段1 |
| XCMS-Centwave | `data_preprocessing_xcms` | 阶段2 |
| MZMine-GirdMass | `data_preprocessing_mzmine`, `peak_detection_mzmine_gridmass` | 阶段2 |
| MZMine-ADAP | `peak_detection_mzmine_adap` | 阶段2 |
| OpenMS-PeakPicking | `peak_picking_openms` | 阶段2 |
| OpenMS-FeatureFinderMetabo | `feature_detection_openms` | 阶段2 |
| KPIC | `data_preprocessing_kpic` | 阶段2 |
| PITracer | `data_preprocessing_pitracer` | 阶段2 |
| TracMass | `data_preprocessing_tracmass` | 阶段2 |
| PeakOnly | `data_preprocessing_peakonly` | 阶段2 |
| CAMERA | `redundant_feature_filtering_camera` | 阶段3 |
| RAMClust | `redundant_feature_filtering_ramclust` | 阶段3 |
| mzAnnotation | `redundant_feature_filtering_mzannotation` | 阶段3 |
| OpenMS-IsotopeTools | `isotope_analysis_openms` | 阶段4 |
| MZMine-JointAligner | `align_features_mzmine_joint_aligner` | 阶段5 |
| OpenMS-PeakGroup | `peak_group_alignment_openms` | 阶段5 |
| kNN | `feature_filtering_and_missing_value_imputation_knn` | 阶段6 |
| mixOmics | `statistical_analysis_mixomics` | 阶段8 |
| DeepMASS | `deepmass_annotation` | 阶段10/11 |
| GNPS | `molecular_networking_gnps` | 阶段12 |
| FBMN | `molecular_networking_fbmn` | 阶段12 |
| MS2LDA | `molecular_networking_ms2lda` | 阶段12 |
| MolNetEnhancer | `molecular_networking_molnetenhancer` | 阶段12 |
| KEGG | `kegg_compound_enrichment` | 阶段13 |

**已覆盖: 27/60 KEYWORDS (45%)**

### ⚠️ MCP server 中有代码但当前已注释（需激活才能用）

| 论文 KEYWORD | 已注释的 MCP 工具 | 对应阶段 |
|-------------|------------------|---------|
| Cosine | `library_match_cosine` | 阶段10 |
| Jaccard | `library_match_jaccard` | 阶段10 |
| Spectral entropy | `library_match_spectral_entropy` | 阶段10 |
| Spec2Vec | `library_match_spec2vec` | 阶段10 |
| MS2DeepScore | `library_match_ms2deepscore` | 阶段10 |
| BLINK | `library_match_blink` | 阶段10 |
| MS-BERT | `library_match_msbert` | 阶段10 |
| XCMS-Obiwarp | `align_retention_time_xcms_obiwarp` | 阶段5 |

**可激活覆盖: +8 KEYWORDS → 总覆盖可达 35/60 (58%)**

### ❌ 暂无 MCP 实现（需要新增开发）

| 类别 | 阶段 | 缺失的 KEYWORDS |
|------|------|----------------|
| 同位素 | 4 | IsoXpress, TarMet, AssayR |
| 峰对齐 | 5 | XCMS-LOESS, FFT-based, DTW-based |
| 缺失值 | 6 | MissForest, Bayesian PCA |
| 批次效应 | 7 | WaveICA, MetNormalizer, MetaboGroupS |
| 统计分析 | 8 | metaX, scikit-learn, SIMCA, DeepLearning-based |
| 未知物定性 | 11 | CFM-ID, SIRIUS, MS-Finder, CSU-MS2, MetDNA, E-SGMN, NEIMS |
| 富集分析 | 13 | MetaboAnalyst, mummichog, GSEA, ChemRICH |
| 通路分析 | 13 | HMDB, Reactome, BioCyc |

**待开发: ~25 KEYWORDS**

---

## 必须遵循的规则

1. **文献优先**: 先查 RAG 文献是否有匹配流程，有则优先采用；无则回退标准管线
2. **对比模式**: 仅当文献明确比较多款工具且工具均可用时激活
3. **每阶段 1 步 1 工具**: 除非激活对比模式
4. **顺序可变**: 采用文献流程时可调整阶段顺序；使用标准管线时遵循上述 1→13 顺序
5. **MANDATORY 不跳过**: 阶段 3（冗余过滤）、阶段 12（分子网络）等标注 [MANDATORY] 的阶段都必须执行
6. **OPTIONAL 可跳过**: 阶段 4（同位素）、阶段 7（批次效应）、阶段 11（未知物定性）在无工具或数据不适用时可跳过
7. **工具名称**: 以上述表格中的 `monospace` 格式工具名为准，不得修改或编造不存在的工具名
8. **优先选择**: 阶段 2 推荐 XCMS 一体化，阶段 3 推荐 pipeline 一体化，阶段 12 推荐 GNPS（最通用）
9. **工具存在性校验**: 只选择标注为 ✅ 可用的工具，不要选择标注为 ⚠️ 已注释的工具
