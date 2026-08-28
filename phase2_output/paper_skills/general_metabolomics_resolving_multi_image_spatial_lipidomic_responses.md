# Skill: Resolving multi-image spatial lipidomic responses to inhaled toxicants by machine learning.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 87/100
- **source**: Stevens NC et al. (2025), Nature communications, DOI: 10.1038/s41467-025-58135-4, PMID: 40140638

## Analysis Goal
复现/对齐文献研究目标：Resolving multi-image spatial lipidomic responses to inhaled toxicants by machine learning.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | MALDI-TOF MSI data acquisition | Bruker timsTOF fleX | MALDI-TOF without ion mobility | `ionization_mode=['positive', 'negative'], matrix_positive=40 mg/mL DHB in 70:30 MeOH:H2O, matrix_negative=7 mg/mL 1,5-diaminonaphthalene in 70:30 MeOH:H2O, sprayer_nozzle_temp_positive=75, sprayer_nozzle_temp_negative=70, sprayer_passes_positive=8, sprayer_passes_negative=13, sprayer_flow_rate_mL_per_min=0.1, sprayer_track_distance_mm=2, sprayer_drying_time_sec_between_passes=10, laser_raster_width_um=10, laser_shots_per_burst=150, laser_frequency_hz=10000, laser_field_size_um=5x5, laser_energy_local_percent=50, laser_attenuator_offset_global_percent=0, mz_range_positive=[300, 1300], mz_range_negative=[300, 900], detector_calibration_mix=90% Agilent ESI-TOF tuning mix + 10% sodium formate` |
| 2 | MSI data conversion and preprocessing | SCiLS Lab | 5-ppm binning | `bin_size_ppm=5` |
| 3 | MSI peak detection, binning, and alignment | Cardinal (v3.4.3 or 3.6.2) | peak detection and alignment (default parameters implied) | `—` |
| 4 | MSI lipid annotation | Custom R workflow + LC-MS/MS reference | m/z + RT + MS/MS matching to scraped-tissue LC-MS/MS data | `mass_error_threshold_ppm=None, annotation_sources=['LC-MS/MS from same experiment', 'Supplementary Data 1']` |
| 5 | MSI intensity normalization | R (custom LOESS implementation) | Locally Estimated Scatterplot Smoothing (LOESS) applied per-pixel across all non-zero intensities | `normalization_method=LOESS, applied_to=all non-zero intensity pixels across all samples` |
| 6 | Spatial image segmentation and clustering | Seurat (v5.0.3 or 5.1.0) | graph-based clustering (k-nearest neighbors + Louvain/Leiden) | `clustering_resolution=0.9, default_parameters_used=True` |
| 7 | Morphological region assignment | Manual H&E registration | histology-guided annotation | `—` |
| 8 | Regional lipid abundance quantification | R (custom scripts) | region-wise intensity summarization (mean/median per lipid per region) | `—` |
| 9 | Lipid class enrichment analysis | R (custom implementation) | Kolmogorov-Smirnov test per lipid class | `statistical_test=Kolmogorov-Smirnov, grouping=lipid class, subclass, saturation level` |
| 10 | LC-MS/MS untargeted lipidomics | MS-DIAL (v4.70) | deconvolution, peak picking, alignment, in silico library matching | `identification_criteria=['m/z', 'retention_time', 'MS/MS_fragmentation_pattern'], library_source=built-in in silico libraries` |
| 11 | Multi-omics integration (MSI + LC-MS/MS) | Custom R workflow (RegioMSI) | m/z-driven cross-platform annotation transfer | `validation_source=scraped tissue & microdissected airways under identical experimental conditions` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1a | workflow_diagram | Experimental design showing HDM sensitization, ozone exposure, tissue processing, and analytical workflows for MSI and LC-MS/MS. | Adobe Illustrator / R (ggplot2) | [1, 10, 11] |
| Figure 1b | bar_chart | Summary of lipid annotations stratified by class, subclass, and saturation level from positive and negative mode MSI/LC-MS/MS. | R (ggplot2) | [4, 10, 11] |

## Parameter Highlights

- **Step 1 (Bruker timsTOF fleX)**: `ionization_mode=['positive', 'negative'], matrix_positive=40 mg/mL DHB in 70:30 MeOH:H2O, matrix_negative=7 mg/mL 1,5-diaminonaphthalene in 70:30 MeOH:H2O, sprayer_nozzle_temp_positive=75, sprayer_nozzle_temp_negative=70, sprayer_passes_positive=8, sprayer_passes_negative=13, sprayer_flow_rate_mL_per_min=0.1, sprayer_track_distance_mm=2, sprayer_drying_time_sec_between_passes=10, laser_raster_width_um=10, laser_shots_per_burst=150, laser_frequency_hz=10000, laser_field_size_um=5x5, laser_energy_local_percent=50, laser_attenuator_offset_global_percent=0, mz_range_positive=[300, 1300], mz_range_negative=[300, 900], detector_calibration_mix=90% Agilent ESI-TOF tuning mix + 10% sodium formate`
- **Step 2 (SCiLS Lab)**: `bin_size_ppm=5`
- **Step 4 (Custom R workflow + LC-MS/MS reference)**: `mass_error_threshold_ppm=None, annotation_sources=['LC-MS/MS from same experiment', 'Supplementary Data 1']`
- **Step 5 (R (custom LOESS implementation))**: `normalization_method=LOESS, applied_to=all non-zero intensity pixels across all samples`
- **Step 6 (Seurat (v5.0.3 or 5.1.0))**: `clustering_resolution=0.9, default_parameters_used=True`
- **Step 9 (R (custom implementation))**: `statistical_test=Kolmogorov-Smirnov, grouping=lipid class, subclass, saturation level`
- **Step 10 (MS-DIAL (v4.70))**: `identification_criteria=['m/z', 'retention_time', 'MS/MS_fragmentation_pattern'], library_source=built-in in silico libraries`
- **Step 11 (Custom R workflow (RegioMSI))**: `validation_source=scraped tissue & microdissected airways under identical experimental conditions`

## Reproducibility Notes

- Full codebase publicly available (GitHub + Zenodo DOI)
- Raw and processed MSI/LC-MS/MS data deposited in Zenodo with persistent DOI
- All major software tools are open-source (Cardinal, Seurat, MS-DIAL, RegioMSI)
- Comprehensive annotation tables provided (Supplementary Data 1 & 2)
- Explicit hardware and OS specifications for RegioMSI execution

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
