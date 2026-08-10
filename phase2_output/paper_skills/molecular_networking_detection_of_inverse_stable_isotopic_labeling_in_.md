# Skill: Detection of Inverse Stable Isotopic Labeling in Untargeted Metabolomic Data.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 92/100
- **source**: Liebergesell TCE et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.4c03528, PMID: 39367814

## Analysis Goal
复现/对齐文献研究目标：Detection of Inverse Stable Isotopic Labeling in Untargeted Metabolomic Data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data acquisition and preprocessing | XCMS | centWave | `ppm=5, snthr=10, prefilter=3, noise=1000, peakwidth=[10, 60], mzdiff=0.001, fitgauss=False, integrate=1, reverse=False, verbose.columns=True` |
| 2 | Retention time alignment and correction | XCMS | obiwarp | `profStep=0.01, span=0.5, family=symmetric, smooth=loess` |
| 3 | Inverse labeling pattern detection | custom R package (InverSILdetect) | mass-difference-based isotopic pattern scoring with background-subtracted intensity ratio thresholds | `min_ratio_change=1.5, max_ratio_change=0.67, min_intensity_fold_change=2.0, mass_tolerance_ppm=5, min_isotopic_peak_distance_Da=1.00335, max_isotopic_peak_distance_Da=1.00345, min_labeling_confidence_score=0.85` |
| 4 | Feature annotation and metabolite identification | GNPS | MS/MS molecular networking + spectral library matching | `cosine_score_threshold=0.7, min_matched_peaks=6, min_cosine=0.7, max_shift_mz=1.0` |
| 5 | Statistical validation and pathway mapping | MetaboAnalyst | two-tailed t-test with FDR correction (Benjamini-Hochberg) | `p_value_threshold=0.05, fdr_method=BH, fold_change_threshold=1.5` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Overview of the InverSIL automated detection workflow, from raw data to biosynthetic hypothesis generation. | Inkscape, R (ggplot2) | [1, 2, 3, 4, 5] |
| Figure 2 | volcano_plot | Volcano plot showing inverse labeling significance (−log10(p-value)) versus log2 fold-change for pABA and L-methionine feeding experiments. | t-test with BH FDR correction | [3, 5] |
| Figure 3 | boxplot | Boxplots of normalized intensities for key inverse-labeled features across control and InverSIL conditions, demonstrating directional intensity shifts consistent with precursor incorporation. | t-test p<0.05 | [3, 5] |
| Figure 4 | pathway_map | KEGG pathway map highlighting dephosphotetrahydromethanopterin biosynthesis with C-7 and C-9 methyl groups annotated as derived from L-methionine via InverSIL evidence. | KEGG Mapper + Adobe Illustrator | [4, 5] |

## Parameter Highlights

- **Step 1 (XCMS)**: `ppm=5, snthr=10, prefilter=3, noise=1000, peakwidth=[10, 60], mzdiff=0.001, fitgauss=False, integrate=1, reverse=False, verbose.columns=True`
- **Step 2 (XCMS)**: `profStep=0.01, span=0.5, family=symmetric, smooth=loess`
- **Step 3 (custom R package (InverSILdetect))**: `min_ratio_change=1.5, max_ratio_change=0.67, min_intensity_fold_change=2.0, mass_tolerance_ppm=5, min_isotopic_peak_distance_Da=1.00335, max_isotopic_peak_distance_Da=1.00345, min_labeling_confidence_score=0.85`
- **Step 4 (GNPS)**: `cosine_score_threshold=0.7, min_matched_peaks=6, min_cosine=0.7, max_shift_mz=1.0`
- **Step 5 (MetaboAnalyst)**: `p_value_threshold=0.05, fdr_method=BH, fold_change_threshold=1.5`

## Reproducibility Notes

- Raw and processed data publicly available in MassIVE and MetaboLights
- Custom InverSILdetect code open-source with DOI and MIT license
- All analysis parameters explicitly reported
- Web-based tools (GNPS, MetaboAnalyst) fully documented and accessible

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
