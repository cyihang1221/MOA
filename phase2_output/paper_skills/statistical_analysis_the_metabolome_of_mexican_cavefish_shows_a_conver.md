# Skill: The metabolome of Mexican cavefish shows a convergent signature highlighting sugar, antioxidant, and Ageing-Related metabolites.

- **skill_type**: paper_recipe
- **functional_domain**: `statistical_analysis`
- **reproducibility_score**: 87/100
- **source**: Medley JK et al. (2022), eLife, DOI: 10.7554/elife.74539, PMID: 35703366

## Analysis Goal
复现/对齐文献研究目标：The metabolome of Mexican cavefish shows a convergent signature highlighting sugar, antioxidant, and Ageing-Related metabolites.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Sample preparation and metabolite extraction | Metabolite extraction protocol | — | `solvent=methanol:water (80:20), extraction_method=cold methanol quenching, centrifugation=14,000 g, 10 min, 4°C` |
| 2 | LC-MS data acquisition | Agilent 6230 TOF LC-MS | — | `column=ZORBAX Eclipse Plus C18, gradient=not fully specified, flow_rate=0.3 mL/min, column_temp=40°C, mass_range=50–1000 m/z, polarity=['positive', 'negative']` |
| 3 | Data conversion | ProteoWizard msconvert | peak picking (Centroiding) | `32-bit=True, filter=peakPicking true 1-2` |
| 4 | Feature detection and alignment | XCMS (R/Bioconductor) (v3.14.0) | centWave | `ppm=10, peakwidth=[10, 60], snthresh=10, prefilter=[3, 100], noise=1000, bw=30, mzwid=0.015, minfrac=0.5, intensity=10000` |
| 5 | Retention time correction and peak alignment | XCMS (v3.14.0) | obiwarp | `method=obiwarp, profiling=False, span=0.5` |
| 6 | Gap filling and missing value imputation | imputeLCMD (R package) (v3.4.0) | k-nearest neighbors (k=5) | `k=5, method=knn` |
| 7 | Filtering and normalization | MetaboAnalystR (v3.0.3) | Pareto scaling + CV filtering | `cv_cutoff=0.25, scaling=pareto, filtering_method=CV-based` |
| 8 | Univariate statistical analysis | MetaboAnalystR (v3.0.3) | two-tailed t-test with Benjamini-Hochberg FDR correction | `alpha=0.05, fdr_method=BH` |
| 9 | Multivariate statistical analysis | MetaboAnalystR (v3.0.3) | PCA, PLS-DA, OPLS-DA | `ncomp_PCA=2, ncomp_PLS_DA=2, ncomp_OPLS_DA=2, validation=permutation test (200 permutations)` |
| 10 | Metabolite annotation | XCMS + METLIN + HMDB + LipidMaps | accurate mass matching (±5 ppm) + MS/MS spectral matching | `mass_tolerance_ppm=5, msms_similarity_threshold=0.7` |
| 11 | Pathway enrichment analysis | MetaboAnalyst web server (v5.0) | hypergeometric test + impact analysis | `organism=Danio rerio, database=KEGG, p_value_cutoff=0.05, impact_threshold=0.1` |
| 12 | Shiny app deployment and interactive visualization | R Shiny (v1.7.1) | — | `app_hosting=shinyapps.io, data_format=processed metabolite table + metadata` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic overview of the cavefish metabolic resilience hypothesis and experimental design comparing surface vs. cave populations under long- and short-term fasting. | Adobe Illustrator | [1, 2] |

## Parameter Highlights

- **Step 1 (Metabolite extraction protocol)**: `solvent=methanol:water (80:20), extraction_method=cold methanol quenching, centrifugation=14,000 g, 10 min, 4°C`
- **Step 2 (Agilent 6230 TOF LC-MS)**: `column=ZORBAX Eclipse Plus C18, gradient=not fully specified, flow_rate=0.3 mL/min, column_temp=40°C, mass_range=50–1000 m/z, polarity=['positive', 'negative']`
- **Step 3 (ProteoWizard msconvert)**: `32-bit=True, filter=peakPicking true 1-2`
- **Step 4 (XCMS (R/Bioconductor) (v3.14.0))**: `ppm=10, peakwidth=[10, 60], snthresh=10, prefilter=[3, 100], noise=1000, bw=30, mzwid=0.015, minfrac=0.5, intensity=10000`
- **Step 5 (XCMS (v3.14.0))**: `method=obiwarp, profiling=False, span=0.5`
- **Step 6 (imputeLCMD (R package) (v3.4.0))**: `k=5, method=knn`
- **Step 7 (MetaboAnalystR (v3.0.3))**: `cv_cutoff=0.25, scaling=pareto, filtering_method=CV-based`
- **Step 8 (MetaboAnalystR (v3.0.3))**: `alpha=0.05, fdr_method=BH`
- **Step 9 (MetaboAnalystR (v3.0.3))**: `ncomp_PCA=2, ncomp_PLS_DA=2, ncomp_OPLS_DA=2, validation=permutation test (200 permutations)`
- **Step 10 (XCMS + METLIN + HMDB + LipidMaps)**: `mass_tolerance_ppm=5, msms_similarity_threshold=0.7`
- **Step 11 (MetaboAnalyst web server (v5.0))**: `organism=Danio rerio, database=KEGG, p_value_cutoff=0.05, impact_threshold=0.1`
- **Step 12 (R Shiny (v1.7.1))**: `app_hosting=shinyapps.io, data_format=processed metabolite table + metadata`

## Reproducibility Notes

- Raw and processed data deposited in MetaboLights (MTBLS1827)
- Full analysis pipeline code publicly available on GitHub under MIT license
- Interactive Shiny app provided for community exploration
- All statistical parameters (FDR cutoff, scaling method, annotation tolerances) explicitly reported

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
