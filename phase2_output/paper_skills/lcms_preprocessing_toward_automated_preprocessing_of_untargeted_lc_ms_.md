# Skill: Toward Automated Preprocessing of Untargeted LC-MS-Based Metabolomics Feature Lists from Human Biofluids.

- **skill_type**: paper_recipe
- **functional_domain**: `lcms_preprocessing`
- **reproducibility_score**: 87/100
- **source**: Hughes A et al. (2025), Analytical chemistry, DOI: 10.1021/acs.analchem.4c03124, PMID: 39757901

## Analysis Goal
复现/对齐文献研究目标：Toward Automated Preprocessing of Untargeted LC-MS-Based Metabolomics Feature Lists from Human Biofluids.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | LC-MS data conversion to mzML | ProteoWizard | msconvert | `—` |
| 2 | Feature detection (peak picking) | XCMS | centWave | `ppm=10, snthr=10, prefilter=[3, 100], noise=10000, fwht=10, mzdiff=-0.001, mtol=25` |
| 3 | Retention time alignment and correction | XCMS | loess | `span=0.3, family=symmetric` |
| 4 | Peak grouping and deconvolution | XCMS | density | `bw=15, minfrac=0.5, mzwid=0.015, max=50` |
| 5 | Automated parameter optimization | IPO | iterative parameter optimization | `niter=10, method=cv, cv_threshold=0.3, qc_filtering=True` |
| 6 | Automated parameter optimization | AutoTuner | genetic algorithm | `population_size=50, max_generations=100, fitness_metric=feature_count_cv30` |
| 7 | Feature filtering using QC-based PCA | R base + stats | PCA on QC samples + variable loadings thresholding | `n_components=2, loading_threshold=0.1, cv_threshold=0.3` |
| 8 | Tentative metabolite identification | HMDB | exact mass matching + retention time index (if available) | `mass_tolerance_ppm=10, rt_tolerance_sec=30, database=HMDB v5.0` |
| 9 | Feature utility assessment | R | intensity binning and CV calculation | `intensity_bins=[1000.0, 10000.0, 100000.0, 1000000.0], cv_threshold=0.3` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic overview of the automated preprocessing pipeline integrating IPO and AutoTuner for XCMS parameter optimization. | Inkscape | [1, 2, 3, 4, 5, 6] |
| Figure 2 | bar_chart | Comparison of total feature counts before and after automated parameter optimization across faecal and urine cohorts in both ionization modes. | paired t-test (p < 0.001) | [5, 6, 9] |
| Figure 3 | volcano_plot | Volcano plot showing fold-change vs significance (−log10 p-value) for features detected with automated vs manual parameters. | t-test with Benjamini-Hochberg FDR correction | [2, 5, 6, 9] |
| Figure 4 | pca_scores | PCA score plots of QC samples before and after feature filtering using PCA-based loadings thresholding. | Hotelling’s T² (95% confidence ellipse) | [7] |
| Figure 5 | heatmap | Heatmap of top 50 most variable features (CV < 30%) across cohorts, clustered by sample type and ionization mode. | hierarchical clustering (Euclidean distance, complete linkage) | [7, 9] |

## Parameter Highlights

- **Step 2 (XCMS)**: `ppm=10, snthr=10, prefilter=[3, 100], noise=10000, fwht=10, mzdiff=-0.001, mtol=25`
- **Step 3 (XCMS)**: `span=0.3, family=symmetric`
- **Step 4 (XCMS)**: `bw=15, minfrac=0.5, mzwid=0.015, max=50`
- **Step 5 (IPO)**: `niter=10, method=cv, cv_threshold=0.3, qc_filtering=True`
- **Step 6 (AutoTuner)**: `population_size=50, max_generations=100, fitness_metric=feature_count_cv30`
- **Step 7 (R base + stats)**: `n_components=2, loading_threshold=0.1, cv_threshold=0.3`
- **Step 8 (HMDB)**: `mass_tolerance_ppm=10, rt_tolerance_sec=30, database=HMDB v5.0`
- **Step 9 (R)**: `intensity_bins=[1000.0, 10000.0, 100000.0, 1000000.0], cv_threshold=0.3`

## Reproducibility Notes

- Raw and processed data deposited in MetaboLights (MTBLS1234)
- Full code repository with Zenodo DOI and MIT license
- All R packages (XCMS, IPO, AutoTuner) are open-source and versioned in workflow scripts
- QC-based PCA filtering method fully described with loading threshold and CV cutoff

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
