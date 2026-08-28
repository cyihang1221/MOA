# Skill: Utilizing Skyline to analyze lipidomics data containing liquid chromatography, ion mobility spectrometry and mass spectrometry dimensions.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 87/100
- **source**: Kirkwood KI et al. (2022), Nature protocols, DOI: 10.1038/s41596-022-00714-6, PMID: 35831612

## Analysis Goal
复现/对齐文献研究目标：Utilizing Skyline to analyze lipidomics data containing liquid chromatography, ion mobility spectrometry and mass spectrometry dimensions.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data import and setup | Skyline | vendor-neutral raw file import | `—` |
| 2 | Library import and lipid definition | Skyline | small-molecule spectral library matching | `library_source=manually validated 500+ lipid library, library_format=Skyline spectral library (.skylib), filtering_enabled=True, indexed_retention_time_filtering=True, ion_mobility_filtering=True` |
| 3 | Retention time prediction and calibration | Skyline | iRT (indexed Retention Time) calibration | `iRT_calibrants=positive-mode iRT calibrants, calibration_method=linear regression, reference_peptides=iRT kit peptides` |
| 4 | Ion mobility drift time alignment and filtering | Skyline | indexed ion mobility (IM) filtering | `IM_tolerance_ms=5.0, IM_calibration_enabled=True` |
| 5 | Peak detection and integration | Skyline | chromatogram-based peak picking with integrated area calculation | `peak_detection_method=integrated peak area, integration_algorithm=smoothed baseline + valley detection, minimum_peak_width_seconds=2.0, signal_to_noise_threshold=3.0` |
| 6 | Annotation validation | Skyline | manual and semi-automated spectral match validation | `match_score_threshold=0.7, MS_MS_library_matching=True, fragment_mass_tolerance_ppm=10.0, precursor_mass_tolerance_ppm=5.0` |
| 7 | Replicate consistency assessment | Skyline | coefficient of variation (CV) and correlation-based replicate comparison | `CV_threshold_percent=20.0, Pearson_r_threshold=0.85` |
| 8 | iRT performance evaluation | Skyline | iRT calibration residual analysis | `residual_threshold_minutes=0.5, calibration_curve_R2_threshold=0.98` |
| 9 | Results export and library curation | Skyline | CSV/TSV export and spectral library editing | `export_format=TSV, include_MS_MS_spectra=True, include_chromatograms=False, library_editing_mode=manual curation` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Overview of the LC-IMS-CID-MS lipidomics protocol using Skyline. | Skyline built-in diagram export + manual annotation | [1, 2, 3, 4, 5, 6, 7, 8, 9] |
| Figure 2 | bar_chart | Summary of lipid classes and counts in the manually validated spectral library. | Skyline Library Explorer + external plotting (not specified) | [2] |
| Figure 3 | table | Skyline spectral library explorer view showing lipid entries, transitions, and metadata. | Skyline GUI | [2] |
| Figure 4 | chromatogram | Precursor chromatogram for positive-mode iRT calibrants used for retention time calibration. | Skyline chromatogram viewer | [3] |
| Figure 5 | table | Annotation validation interface showing spectral matches, scores, and confidence indicators. | Skyline validation panel | [6] |
| Figure 6 | chromatogram | Example of annotation validation showing co-eluting precursor and fragment ions with retention time alignment. | Skyline chromatogram overlay | [6] |
| Figure 7 | other | Example MS/MS spectra for a lipid species, annotated with fragment assignments. | Skyline MS/MS viewer | [6] |
| Figure 8 | boxplot | Replicate comparisons showing peak area variability across technical replicates. | CV < 20%, Pearson r > 0.85 | [7] |
| Figure 9 | scatter_plot | iRT performance assessment showing observed vs. predicted retention times for calibrants. | R² > 0.98, residuals < 0.5 min | [8] |

## Parameter Highlights

- **Step 2 (Skyline)**: `library_source=manually validated 500+ lipid library, library_format=Skyline spectral library (.skylib), filtering_enabled=True, indexed_retention_time_filtering=True, ion_mobility_filtering=True`
- **Step 3 (Skyline)**: `iRT_calibrants=positive-mode iRT calibrants, calibration_method=linear regression, reference_peptides=iRT kit peptides`
- **Step 4 (Skyline)**: `IM_tolerance_ms=5.0, IM_calibration_enabled=True`
- **Step 5 (Skyline)**: `peak_detection_method=integrated peak area, integration_algorithm=smoothed baseline + valley detection, minimum_peak_width_seconds=2.0, signal_to_noise_threshold=3.0`
- **Step 6 (Skyline)**: `match_score_threshold=0.7, MS_MS_library_matching=True, fragment_mass_tolerance_ppm=10.0, precursor_mass_tolerance_ppm=5.0`
- **Step 7 (Skyline)**: `CV_threshold_percent=20.0, Pearson_r_threshold=0.85`
- **Step 8 (Skyline)**: `residual_threshold_minutes=0.5, calibration_curve_R2_threshold=0.98`
- **Step 9 (Skyline)**: `export_format=TSV, include_MS_MS_spectra=True, include_chromatograms=False, library_editing_mode=manual curation`

## Reproducibility Notes

- Raw and processed data publicly available via PanoramaWeb and Zenodo
- Custom lipid library explicitly shared and curated
- All software is open-source (Skyline, BSD-3-Clause licensed)
- Step-by-step protocol with clear parameter thresholds (e.g., ppm tolerances, CV cutoffs)
- Vendor-neutral workflow supporting multiple instrument formats

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
