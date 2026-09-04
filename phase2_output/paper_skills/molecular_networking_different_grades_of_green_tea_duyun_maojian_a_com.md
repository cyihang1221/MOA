# Skill: Different grades of green tea 'Duyun Maojian': a comprehensive constituent, bioactivity, and sensory evaluation from the consumer's specific perspective

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 68/100
- **source**: Wei-wu Xia et al. (2026), Food Chemistry: X, DOI: 10.1016/j.fochx.2026.103843

## Analysis Goal
复现/对齐文献研究目标：Different grades of green tea 'Duyun Maojian': a comprehensive constituent, bioactivity, and sensory evaluation from the consumer's specific perspective。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Study design and grouping (do not invent grades) | metadata.csv | five commercial grades x 3 biological replicates | `groups=Supreme,Premium,Special,Grade I,Grade II, n_replicates=3, qc=pooled equal-volume mix, blank=70% methanol/water, note=current RAW session with BK/DY/QC is NOT this design` |
| 2 | Volatile GC-MS acquisition (wet-lab; skip unless GC-MS data provided) | Agilent 8890-7000D GC-MS | HS-SPME + EI | `fiber=50/30 μm DVB/CAR/PDMS, extraction_time_min=40, extraction_temperature_c=70, carrier_gas=helium, carrier_flow_mL_per_min=1.0, ionization_energy_eV=70, ion_source_temperature_c=230, column=HP-5ms Ultra Inert (30 m × 0.25 mm × 0.25 μm), internal_standard=ethyl decanoate (200 μg)` |
| 3 | GC-MS EI library workflow and volatile statistics | GNPS GC-MS EI Data Analysis workflow; MetaboAnalyst 6.0 | Spectral Library Search; UV-scaling PCA; PLS-DA | `mass_tolerance_da=0.02, pca_scaling=UV, plsda_groups=higher(Supreme+Premium),medium(Special),lower(Grade I+Grade II), vip_threshold=1.5, n_features_after_gnps=2088, n_differential_volatiles=78` |
| 4 | Non-volatile LC-MS acquisition (instrument method; RAW already collected) | Ultimate 3000 UPLC + Q-Exactive Focus | UPLC + full MS dd-MS2 (positive) | `column=ACQUITY UPLC HSS T3 (2.1 × 100 mm, 1.8 μm), flow_rate_mL_per_min=0.2, mobile_phase_A=0.1% formic acid in water, mobile_phase_B=0.1% formic acid in acetonitrile, gradient_time_min_B_percent=[0:10, 1:10, 2.5:15, 7:18, 8:10, 10:16, 10.5:18, 12:22, 14:23, 15:95, 18:95, 19:10, 21:10], injection_volume_uL=2, column_temperature_c=30, spray_voltage_V=3400, capillary_temperature_c=350, sheath_gas=45, auxiliary_gas=15, ms1_resolution=70000, ms1_scan_range_mz=[100, 1500], ms2_resolution=17500, collision_energy_eV=[30, 40, 60], polarity=positive` |
| 5 | RAW to mzML | MSConvert | peak picking filter | `ms_levels=[1, 2], filtering=peak picking enabled` |
| 6 | LC-MS feature detection (paper uses MZmine 4.3.0; SI peak-picking numbers not in main text) | MZmine 4.3.0 | mass detection, chromatogram building, deconvolution, isotope filtering, alignment, row filtering | `version=4.3.0, include_qc_and_blank=true, expected_features_in_paper=920, detailed_params=see SI Section 3 (not in main text; do not invent ppm/peakwidth)` |
| 7 | QC drift correction | RStudio custom script (SI Section 4, not public) | QC-based signal correction and normalization | `qc_correction=QC-based response drift correction, code=not_shared` |
| 8 | LC-MS FBMN annotation | GNPS feature-based molecular networking | FBMN + multi-library matching, MSI identification level 2 | `precursor_mass_tolerance_da=0.02, fragment_mass_tolerance_da=0.02, min_cosine_score=0.7, top_k_matches=10, min_matched_fragment_ions=6, max_precursor_mass_shift_da=500, identification_level=2, annotated_features_in_paper=330/920` |
| 9 | Multivariate statistics for non-volatiles | SIMCA 14.1 | UV/PCA + HCA + PLS-DA + permutation | `software=SIMCA 14.1, pca_show_qc_in_center=true, hca=euclidean, plsda_permutation_n=200, vip_threshold=1.2, univariate=one-way ANOVA p<0.05, n_plsda_differential=102, n_identified_differential_metabolites=23` |
| 10 | Wet-lab constituent, bioactivity, sensory, correlation (tables only; Agent B cannot run assays) | wet-lab + Prism + GB/T 23776-2018 panel | Folin TPC, AlCl3 TFC, ninhydrin TFAA; DPPH/ABTS; RAW264.7 NO; zebrafish thrombus; Kruskal-Wallis+Dunn; Pearson | `sensory_standard=GB/T 23776-2018, panel_n=12, scale=0-5, correlation=Pearson of TPC/TFC/TFAA vs sensory/bioactivity` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | bar_chart | TPC / TFC / TFAA by five grades (mean±SD, significance letters) | one-way ANOVA p<0.05 | 10 |
| Figure 2 | pca_scores | Volatile PCA (UV), PLS-DA of 3 collapsed grade groups, GC-MS molecular network | UV-scaling PCA; PLS-DA VIP>1.5; 78 differential volatiles | 3 |
| Figure 3 | heatmap | Relative abundance of 78 differential aroma compounds across five grades | VIP>1.5 | 3 |
| Figure 4 | network | LC-MS/MS FBMN of non-volatiles | cosine>=0.7, min matched ions=6 | 8 |
| Figure 5 | pca_scores | Non-volatile PCA, HCA, PLS-DA, 200-permutation, 23 differential metabolites | PLS-DA VIP>1.2; permutation n=200; 920 features in paper | 9 |
| Figure 6 | bar_chart | DPPH, ABTS, anti-inflammatory NO, zebrafish anti-thrombotic | mean±SD, triplicate | 10 |
| Figure 7 | bar_chart | Sensory scores (bitterness, astringency, sweetness, umami, intensity) | Kruskal-Wallis + Dunn p<0.05 | 10 |
| Figure 8 | heatmap | Pearson correlation of constituents vs sensory/bioactivity | Pearson r | 10 |

## Parameter Highlights

- **Step 1 (metadata.csv)**: `groups=Supreme,Premium,Special,Grade I,Grade II, n_replicates=3, qc=pooled equal-volume mix, blank=70% methanol/water, note=current RAW session with BK/DY/QC is NOT this design`
- **Step 2 (Agilent 8890-7000D GC-MS)**: `fiber=50/30 μm DVB/CAR/PDMS, extraction_time_min=40, extraction_temperature_c=70, carrier_gas=helium, carrier_flow_mL_per_min=1.0, ionization_energy_eV=70, ion_source_temperature_c=230, column=HP-5ms Ultra Inert (30 m × 0.25 mm × 0.25 μm), internal_standard=ethyl decanoate (200 μg)`
- **Step 3 (GNPS GC-MS EI Data Analysis workflow; MetaboAnalyst 6.0)**: `mass_tolerance_da=0.02, pca_scaling=UV, plsda_groups=higher(Supreme+Premium),medium(Special),lower(Grade I+Grade II), vip_threshold=1.5, n_features_after_gnps=2088, n_differential_volatiles=78`
- **Step 4 (Ultimate 3000 UPLC + Q-Exactive Focus)**: `column=ACQUITY UPLC HSS T3 (2.1 × 100 mm, 1.8 μm), flow_rate_mL_per_min=0.2, mobile_phase_A=0.1% formic acid in water, mobile_phase_B=0.1% formic acid in acetonitrile, gradient_time_min_B_percent=[0:10, 1:10, 2.5:15, 7:18, 8:10, 10:16, 10.5:18, 12:22, 14:23, 15:95, 18:95, 19:10, 21:10], injection_volume_uL=2, column_temperature_c=30, spray_voltage_V=3400, capillary_temperature_c=350, sheath_gas=45, auxiliary_gas=15, ms1_resolution=70000, ms1_scan_range_mz=[100, 1500], ms2_resolution=17500, collision_energy_eV=[30, 40, 60], polarity=positive`
- **Step 5 (MSConvert)**: `ms_levels=[1, 2], filtering=peak picking enabled`
- **Step 6 (MZmine 4.3.0)**: `version=4.3.0, include_qc_and_blank=true, expected_features_in_paper=920, detailed_params=see SI Section 3 (not in main text; do not invent ppm/peakwidth)`
- **Step 7 (RStudio custom script (SI Section 4, not public))**: `qc_correction=QC-based response drift correction, code=not_shared`
- **Step 8 (GNPS feature-based molecular networking)**: `precursor_mass_tolerance_da=0.02, fragment_mass_tolerance_da=0.02, min_cosine_score=0.7, top_k_matches=10, min_matched_fragment_ions=6, max_precursor_mass_shift_da=500, identification_level=2, annotated_features_in_paper=330/920`
- **Step 9 (SIMCA 14.1)**: `software=SIMCA 14.1, pca_show_qc_in_center=true, hca=euclidean, plsda_permutation_n=200, vip_threshold=1.2, univariate=one-way ANOVA p<0.05, n_plsda_differential=102, n_identified_differential_metabolites=23`
- **Step 10 (wet-lab + Prism + GB/T 23776-2018 panel)**: `sensory_standard=GB/T 23776-2018, panel_n=12, scale=0-5, correlation=Pearson of TPC/TFC/TFAA vs sensory/bioactivity`

## Reproducibility Notes

- LC-MS instrument method (column, gradient, Orbitrap resolutions, NCE 30/40/60) is explicit
- GNPS FBMN tolerances are explicit (0.02 Da, cosine 0.7, topK 10, min ions 6)
- Statistics thresholds are explicit in Results: GC-MS VIP>1.5 (78 volatiles); LC-MS VIP>1.2 (23 identified differentials); PLS-DA permutation n=200
- MSConvert mzML conversion settings stated
- Available-tool mapping for Agent A/B: ThermoRawFileParser or MSConvert; MZmine if registered and installed else XCMS; kNN QC/missing; GNPS/FBMN; SIMCA/MetaboAnalyst -> mixOmics with vip_threshold=1.2 (LC-MS) or 1.5 (GC-MS); exclude QC from biological VIP
- Do not schedule wet-lab/cell/zebrafish/sensory as executable B steps unless the user uploaded the corresponding CSV

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。

## Available-tool mapping
- `msconvert` → convert_raw_to_mzml_msconvert 或 convert_raw_to_mzml_ThermoRawFileParser
- `mzmine` → data_preprocessing_mzmine（已注册且本机可运行时）；否则 data_preprocessing_xcms
- `simca` → statistical_analysis_mixomics（LC-MS vip_threshold=1.2；GC-MS vip_threshold=1.5）
- `metaboanalyst` → statistical_analysis_mixomics
- `gnps` → molecular_networking_gnps / molecular_networking_fbmn
