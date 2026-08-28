# Skill: Modifying Chromatography Conditions for Improved Unknown Feature Identification in Untargeted Metabolomics.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 87/100
- **source**: Anderson BG et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02149, PMID: 34794310

## Analysis Goal
复现/对齐文献研究目标：Modifying Chromatography Conditions for Improved Unknown Feature Identification in Untargeted Metabolomics.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | LC-MS/MS data acquisition with modified chromatography conditions | Thermo Scientific Q-Exactive HF-X | — | `gradient_length=extended (vs. standard 20-min), mass_loading=optimized (reduced for HILIC, increased for RPLC), rolling_precursor_ion_exclusion=enabled with dynamic exclusion window and duration tuned for improved MS/MS sampling` |
| 2 | Data conversion to open format | msconvert | ProteoWizard | `filter=peakPicking true 1-3, intenFilter=true` |
| 3 | Feature detection and alignment | XCMS (v3.12.0) | centWave | `ppm=5, peakwidth=[10, 60], snthresh=10, prefilter=[5, 10000], noise=1000, verbose.columns=False` |
| 4 | Retention time alignment and correction | XCMS (v3.12.0) | obiwarp | `method=obiwarp, profStep=0.01` |
| 5 | MS/MS spectral matching against reference database | GNPS | Molecular Networking + Spectral Library Search | `min_peaks=6, min_matched_peaks=6, top_k=10, cosine_score_threshold=0.7, max_mz_diff=0.02` |
| 6 | Manual curation and threshold determination for semi-automated annotation | GNPS web interface + custom Excel review | — | `score_threshold=0.75, matched_peaks_ratio_threshold=0.5, library_match_confidence=high (manual validation)` |
| 7 | Cross-run detection and quantitation transfer | XCMS (v3.12.0) | fillPeaks | `minfrac=0.5, max=0.9, value=na` |
| 8 | Machine learning-based classification of remaining unknowns | custom Python scikit-learn model | Random Forest classifier trained on spectral features (e.g., peak intensity ratios, fragmentation patterns, retention time behavior) | `n_estimators=100, max_depth=10, random_state=42, feature_set=['cosine_similarity_to_known', 'spectral_entropy', 'RT_deviation_zscore', 'peak_intensity_ratio_1st_to_2nd']` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic overview of the experimental and computational workflow comparing standard vs. modified LC-MS/MS conditions and downstream annotation strategies. | Adobe Illustrator | [1, 2, 3, 4, 5, 6, 7, 8] |
| Figure 2 | bar_chart | Comparison of total unique metabolite identifications under standard vs. modified chromatographic conditions across HILIC and RPLC methods. | GraphPad Prism | [5, 6] |
| Figure 3 | volcano_plot | Volcano plot showing differential features between HILIC and RPLC runs, highlighting newly identified metabolites. | t-test p<0.05 with Benjamini-Hochberg FDR correction | [3, 4, 7] |
| Figure 4 | heatmap | Hierarchical clustering heatmap of top 50 prioritized unknowns based on spectral similarity and machine learning scores. | R pheatmap | [8] |

## Parameter Highlights

- **Step 1 (Thermo Scientific Q-Exactive HF-X)**: `gradient_length=extended (vs. standard 20-min), mass_loading=optimized (reduced for HILIC, increased for RPLC), rolling_precursor_ion_exclusion=enabled with dynamic exclusion window and duration tuned for improved MS/MS sampling`
- **Step 2 (msconvert)**: `filter=peakPicking true 1-3, intenFilter=true`
- **Step 3 (XCMS (v3.12.0))**: `ppm=5, peakwidth=[10, 60], snthresh=10, prefilter=[5, 10000], noise=1000, verbose.columns=False`
- **Step 4 (XCMS (v3.12.0))**: `method=obiwarp, profStep=0.01`
- **Step 5 (GNPS)**: `min_peaks=6, min_matched_peaks=6, top_k=10, cosine_score_threshold=0.7, max_mz_diff=0.02`
- **Step 6 (GNPS web interface + custom Excel review)**: `score_threshold=0.75, matched_peaks_ratio_threshold=0.5, library_match_confidence=high (manual validation)`
- **Step 7 (XCMS (v3.12.0))**: `minfrac=0.5, max=0.9, value=na`
- **Step 8 (custom Python scikit-learn model)**: `n_estimators=100, max_depth=10, random_state=42, feature_set=['cosine_similarity_to_known', 'spectral_entropy', 'RT_deviation_zscore', 'peak_intensity_ratio_1st_to_2nd']`

## Reproducibility Notes

- Raw and processed data deposited in MassIVE and MetaboLights with DOIs
- Custom ML code publicly available on GitHub with Zenodo DOI and MIT license
- All major analysis tools are open-source or freely accessible web platforms
- Manual curation criteria and thresholds explicitly defined and validated

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
