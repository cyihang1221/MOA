# Skill: Comparative metabolomics with Metaboseek reveals functions of a conserved fat metabolism pathway in C. elegans.

- **skill_type**: paper_recipe
- **functional_domain**: `pathway_enrichment`
- **reproducibility_score**: 92/100
- **source**: Helf MJ et al. (2022), Nature communications, DOI: 10.1038/s41467-022-28391-9, PMID: 35145075

## Analysis Goal
复现/对齐文献研究目标：Comparative metabolomics with Metaboseek reveals functions of a conserved fat metabolism pathway in C. elegans.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data conversion to mzXML | MSConvert (v3.0) | ProteoWizard conversion | `—` |
| 2 | Molecular feature detection | XCMS (via Metaboseek) | centWave | `mass_tolerance_ppm=4, peakwidth=3_20, snthresh=3, prefilter=3_100, fitgauss=False, integrate=1, firstBaselineCheck=True, noise=0, mzCenterFun=wMean, mzdiff=-0.005` |
| 3 | Feature grouping and alignment | XCMS (via Metaboseek) | obiwarp | `minfrac=0.2, bw=2, mzwid=0.002, max=500, minsamp=1, usegroups=False` |
| 4 | Gap filling | Metaboseek peak filling | Metaboseek gap-filling algorithm | `mass_tolerance_ppm=3, rt_tolerance_sec=3, rtrange=True, areaMode=False` |
| 5 | Blank subtraction and quality filtering | Metaboseek Data Explorer | blank abundance thresholding + Fast Peak Shapes (Peak Quality) | `blank_threshold_fold_change=10, quality_filter_method=Fast Peak Shapes` |
| 6 | Grouping and statistical testing | Metaboseek Basic Analysis | unpaired two-sided t-test | `control_group=WT, test_type=unpaired two-sided t-test, p_value_adjustment=not specified (assumed none or default)` |
| 7 | MS/MS matching and annotation | Metaboseek Advanced Analysis (Find MS2 scans) | inclusion list–driven dd-MS2 matching | `inclusion_window_sec=20, ms2_resolution=30000, agc_target_ms2=200000, collision_energy=[10, 30], isolation_window_mz=1.0, dynamic_exclusion_sec=5, top_n_ms2_per_scan=8` |
| 8 | MS/MS networking and structural inference | Metaboseek MS/MS Networking | cosine similarity–based network clustering | `similarity_threshold=not explicitly stated (implied by 'Simplify Network' in Supplementary Fig. 1)` |
| 9 | Normalization | Metaboseek | internal standard normalization | `normalization_reference=ascr#3 abundance` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | Overview of comparative metabolomics workflow using Metaboseek. | Metaboseek built-in export (vector graphics) | [1, 2, 3, 4, 5, 6, 7, 8, 9] |
| Fig. 2 | volcano_plot | Differential metabolite analysis of CA-fed hacl-1 mutants vs WT, showing α-oxidation–dependent accumulation. | unpaired two-sided t-test | [6, 9] |
| Fig. 3 | heatmap | Heatmap of endogenous metabolites accumulating in hacl-1 mutant larvae. | t-test p-value thresholding | [5, 6, 9] |
| Fig. 4 | network | MS/MS molecular network comparing exo-metabolomes of hacl-1 and WT adults. | Metaboseek MS/MS Networking + Simplify Network display | [7, 8] |
| Fig. 5 | bar_chart | Quantification showing enrichment of cyclopropane-containing glycolipids in hacl-1 mutants. | t-test p < 0.05 | [6, 9] |

## Parameter Highlights

- **Step 2 (XCMS (via Metaboseek))**: `mass_tolerance_ppm=4, peakwidth=3_20, snthresh=3, prefilter=3_100, fitgauss=False, integrate=1, firstBaselineCheck=True, noise=0, mzCenterFun=wMean, mzdiff=-0.005`
- **Step 3 (XCMS (via Metaboseek))**: `minfrac=0.2, bw=2, mzwid=0.002, max=500, minsamp=1, usegroups=False`
- **Step 4 (Metaboseek peak filling)**: `mass_tolerance_ppm=3, rt_tolerance_sec=3, rtrange=True, areaMode=False`
- **Step 5 (Metaboseek Data Explorer)**: `blank_threshold_fold_change=10, quality_filter_method=Fast Peak Shapes`
- **Step 6 (Metaboseek Basic Analysis)**: `control_group=WT, test_type=unpaired two-sided t-test, p_value_adjustment=not specified (assumed none or default)`
- **Step 7 (Metaboseek Advanced Analysis (Find MS2 scans))**: `inclusion_window_sec=20, ms2_resolution=30000, agc_target_ms2=200000, collision_energy=[10, 30], isolation_window_mz=1.0, dynamic_exclusion_sec=5, top_n_ms2_per_scan=8`
- **Step 8 (Metaboseek MS/MS Networking)**: `similarity_threshold=not explicitly stated (implied by 'Simplify Network' in Supplementary Fig. 1)`
- **Step 9 (Metaboseek)**: `normalization_reference=ascr#3 abundance`

## Reproducibility Notes

- Full open-source pipeline (Metaboseek + ProteoWizard) with versioned releases
- Public deposition of raw and processed data in MetaboLights (MTBLS1872)
- Detailed, parameterized XCMS and Metaboseek settings provided
- Internal standard (ascr#3) normalization explicitly defined
- All MS acquisition parameters fully reported (gradient, voltages, temperatures, resolution, NCE)
- Code repository linked with DOI and MIT license

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
