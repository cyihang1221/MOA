# Skill: Automated Annotation of Untargeted All-Ion Fragmentation LC-MS Metabolomics Data with MetaboAnnotatoR.

- **skill_type**: paper_recipe
- **functional_domain**: `lcms_preprocessing`
- **reproducibility_score**: 88/100
- **source**: Graça G et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c03032, PMID: 35180347

## Analysis Goal
复现/对齐文献研究目标：Automated Annotation of Untargeted All-Ion Fragmentation LC-MS Metabolomics Data with MetaboAnnotatoR.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | AIF LC-MS data acquisition | LC-MS instrument (unspecified vendor) | — | `—` |
| 2 | Data conversion to mzML | ProteoWizard (msconvert) | — | `32bit=True, filter=['peakPicking', 'zeroSample', 'titleMaker']` |
| 3 | Feature detection and alignment | XCMS | centWave | `ppm=5, snthr=10, prefilter=[3, 100], peakwidth=[10, 60], noise=500, bw=10, mzdiff=-0.001, minfrac=0.5, max=50` |
| 4 | Correlation-based parent-fragment linking | MetaboAnnotatoR (v1.0.0) | Pearson correlation + retention time consistency filtering | `cor_threshold=0.7, rt_window_sec=3, intensity_ratio_min=0.01, intensity_ratio_max=0.9` |
| 5 | Molecular fragment matching and annotation | MetaboAnnotatoR (v1.0.0) | in-silico fragment matching against built-in fragment libraries | `mass_tol_ppm=10, library_match_score_min=0.6, min_fragment_matches=2` |
| 6 | Ranking and prioritization of annotations | MetaboAnnotatoR (v1.0.0) | composite scoring (correlation strength × fragment match score × library confidence) | `top_n=5` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 2 (ProteoWizard (msconvert))**: `32bit=True, filter=['peakPicking', 'zeroSample', 'titleMaker']`
- **Step 3 (XCMS)**: `ppm=5, snthr=10, prefilter=[3, 100], peakwidth=[10, 60], noise=500, bw=10, mzdiff=-0.001, minfrac=0.5, max=50`
- **Step 4 (MetaboAnnotatoR (v1.0.0))**: `cor_threshold=0.7, rt_window_sec=3, intensity_ratio_min=0.01, intensity_ratio_max=0.9`
- **Step 5 (MetaboAnnotatoR (v1.0.0))**: `mass_tol_ppm=10, library_match_score_min=0.6, min_fragment_matches=2`
- **Step 6 (MetaboAnnotatoR (v1.0.0))**: `top_n=5`

## Reproducibility Notes

- All code open-source (MIT license) with Zenodo DOI
- Raw and processed data publicly available on MetaboLights and GitHub
- Workflow uses only open-source tools (XCMS, ProteoWizard, R)
- Benchmarking against MS-DIAL with shared test datasets

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
