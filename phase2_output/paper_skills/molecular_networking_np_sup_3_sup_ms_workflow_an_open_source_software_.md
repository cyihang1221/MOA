# Skill: NP<sup>3</sup> MS Workflow: An Open-Source Software System to Empower Natural Product-Based Drug Discovery Using Untargeted Metabolomics.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 92/100
- **source**: Bazzano CF et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05829, PMID: 38702053

## Analysis Goal
复现/对齐文献研究目标：NP<sup>3</sup> MS Workflow: An Open-Source Software System to Empower Natural Product-Based Drug Discovery Using Untargeted Metabolomics.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | LC-MS/MS data conversion to mzML | ProteoWizard MSConvert | default conversion settings | `—` |
| 2 | Feature detection and alignment | XCMS (v3.18.0) | centWave for peak picking; obiwarp for retention time correction; density for peak grouping | `ppm=10, peakwidth=[10, 60], snthr=10, prefilter=[5, 10000], noise=1000, bw=30, mzdiff=0.01` |
| 3 | MS² spectrum extraction and quality filtering | NP³ MS Workflow internal module (v1.0.0) | MS² extraction based on precursor ion isolation window and retention time window; spectral quality scoring using signal-to-noise and fragment ion abundance thresholds | `min_ms2_intensity=5000, min_fragment_ions=3, rt_window_sec=5, isolation_width_da=1.2` |
| 4 | Automatic [M + H]⁺ ion deconvolution | NP³ MS Workflow internal module (v1.0.0) | rule-based deconvolution using neutral loss patterns and fragmentation logic (e.g., loss of H₂O, CH₃OH, CO₂) | `adducts=['[M+H]+', '[M+Na]+', '[M+NH4]+'], neutral_losses=['18.0106', '32.0262', '44.0098'], min_relative_intensity=0.01` |
| 5 | Chemical structural annotation | GNPS + SIRIUS + CSI:FingerID (vGNPS v4.2, SIRIUS 4.8.0, CSI:FingerID 2.2.0) | MS² spectral matching against GNPS libraries; molecular formula prediction via SIRIUS; structure ranking via CSI:FingerID | `cosine_score_threshold=0.7, min_matched_peaks=4, mass_error_ppm=10, top_k_structures=5` |
| 6 | Relative quantification and bioactivity correlation scoring | NP³ MS Workflow internal module (v1.0.0) | peak area normalization across samples; Spearman rank correlation between feature abundance and bioassay readouts (e.g., IC₅₀, % inhibition) | `normalization_method=median fold-change, correlation_method=Spearman, min_correlation_abs=0.6, p_value_adjustment=Benjamini-Hochberg` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 2 (XCMS (v3.18.0))**: `ppm=10, peakwidth=[10, 60], snthr=10, prefilter=[5, 10000], noise=1000, bw=30, mzdiff=0.01`
- **Step 3 (NP³ MS Workflow internal module (v1.0.0))**: `min_ms2_intensity=5000, min_fragment_ions=3, rt_window_sec=5, isolation_width_da=1.2`
- **Step 4 (NP³ MS Workflow internal module (v1.0.0))**: `adducts=['[M+H]+', '[M+Na]+', '[M+NH4]+'], neutral_losses=['18.0106', '32.0262', '44.0098'], min_relative_intensity=0.01`
- **Step 5 (GNPS + SIRIUS + CSI:FingerID (vGNPS v4.2, SIRIUS 4.8.0, CSI:FingerID 2.2.0))**: `cosine_score_threshold=0.7, min_matched_peaks=4, mass_error_ppm=10, top_k_structures=5`
- **Step 6 (NP³ MS Workflow internal module (v1.0.0))**: `normalization_method=median fold-change, correlation_method=Spearman, min_correlation_abs=0.6, p_value_adjustment=Benjamini-Hochberg`

## Reproducibility Notes

- Full source code publicly available under MIT license
- All raw and processed data deposited in GNPS and Zenodo with DOIs
- Uses exclusively open-source tools with versioned dependencies
- Detailed parameterization reported for all core steps
- Bioassay metadata included for correlation modeling

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。

## Available-tool mapping
- `msconvert` → convert_raw_to_mzml_msconvert 或 convert_raw_to_mzml_ThermoRawFileParser
- `gnps` → molecular_networking_gnps / molecular_networking_fbmn
