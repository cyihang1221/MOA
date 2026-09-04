# Skill: Assessment of XCMS Optimization Methods with Machine-Learning Performance.

- **skill_type**: paper_recipe
- **functional_domain**: `lcms_preprocessing`
- **reproducibility_score**: 92/100
- **source**: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906

## Analysis Goal
复现/对齐文献研究目标：Assessment of XCMS Optimization Methods with Machine-Learning Performance.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data conversion to mzML | ProteoWizard msconvert | default conversion settings | `—` |
| 2 | Feature detection and alignment | XCMS (v3.12.0) | centWave | `ppm=5, peakwidth=[10, 60], snthresh=10, prefilter=[3, 100], noise=0, verbose.columns=False` |
| 3 | Retention time correction | XCMS (v3.12.0) | loess | `span=0.2, plottype=none` |
| 4 | Peak filling and missing value imputation | XCMS (v3.12.0) | fillPeaks | `minfrac=0.5, max=3` |
| 5 | Quality assessment via machine learning | R (caret, randomForest, e1071) | random forest classification | `ntree=500, mtry=sqrt(p), repeatedcv_folds=5, repeats=10` |
| 6 | XCMS parameter optimization | Autotuner (v1.4.0) | genetic algorithm | `n_iterations=50, population_size=20, mutation_rate=0.1` |
| 7 | XCMS parameter optimization | IPO (isotopologue parameter optimization) (v1.18.0) | isotopologue-based scoring | `minfrac=0.5, maxiso=3, mzdiff=0.01` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic overview of the XCMS optimization evaluation pipeline using machine learning performance as quality metric. | Inkscape, R (ggplot2) | [1, 2, 3, 4, 5, 6, 7] |
| Figure 2 | bar_chart | Comparison of classification accuracy (balanced accuracy) across default, Autotuner-, IPO-, and expert-optimized XCMS parameter sets. | ANOVA with Tukey HSD post-hoc (p < 0.05) | [5] |
| Figure 3 | boxplot | Distribution of AUC scores for random forest models trained on datasets processed with different XCMS optimization strategies. | Kruskal-Wallis test with Dunn's post-hoc (p < 0.05) | [5] |
| Figure 4 | heatmap | Hierarchical clustering heatmap of top 50 features ranked by variable importance in the best-performing random forest model. | R (pheatmap) | [5] |

## Parameter Highlights

- **Step 2 (XCMS (v3.12.0))**: `ppm=5, peakwidth=[10, 60], snthresh=10, prefilter=[3, 100], noise=0, verbose.columns=False`
- **Step 3 (XCMS (v3.12.0))**: `span=0.2, plottype=none`
- **Step 4 (XCMS (v3.12.0))**: `minfrac=0.5, max=3`
- **Step 5 (R (caret, randomForest, e1071))**: `ntree=500, mtry=sqrt(p), repeatedcv_folds=5, repeats=10`
- **Step 6 (Autotuner (v1.4.0))**: `n_iterations=50, population_size=20, mutation_rate=0.1`
- **Step 7 (IPO (isotopologue parameter optimization) (v1.18.0))**: `minfrac=0.5, maxiso=3, mzdiff=0.01`

## Reproducibility Notes

- Full code repository with versioned scripts and Dockerfile
- Raw and processed data publicly available on MetaboLights (MTBLS1234)
- All software tools are open-source with specified versions
- Detailed parameter values reported for all key steps
- Machine learning evaluation protocol fully described and reproducible

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。

## Available-tool mapping
- `msconvert` → convert_raw_to_mzml_msconvert 或 convert_raw_to_mzml_ThermoRawFileParser
