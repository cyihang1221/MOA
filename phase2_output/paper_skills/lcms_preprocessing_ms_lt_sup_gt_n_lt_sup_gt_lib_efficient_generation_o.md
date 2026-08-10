# Skill: MS&lt;sup&gt;n&lt;/sup&gt;Lib: efficient generation of open multi-stage fragmentation mass spectral libraries.

- **skill_type**: paper_recipe
- **functional_domain**: `lcms_preprocessing`
- **reproducibility_score**: 92/100
- **source**: Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295

## Analysis Goal
复现/对齐文献研究目标：MS&lt;sup&gt;n&lt;/sup&gt;Lib: efficient generation of open multi-stage fragmentation mass spectral libraries.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Metadata clean-up and structure standardization | Python script (metadata_cleanup_prefect.py) | ChEMBL structure pipeline with custom salt removal and re-cleaning | `salt_removal_enabled=True, structure_standardization_pipeline=ChEMBL, computed_properties=['canonical_SMILES', 'isomeric_SMILES', 'InChI', 'InChIKey', 'logP', 'monoisotopic_mass']` |
| 2 | Sequence table generation for acquisition | Python script (sequence_creation.py) | Plate- and well-aware sequence ordering with polarity interleaving | `polarity_order=['positive', 'negative'], filename_template={date}_{library_plate_well}_{method}_{polarity}, acquisition_platform=Xcalibur (Thermo), flow_injection_method=Orbitrap MS^n` |
| 3 | Sample pooling and dilution | Liquid handlers (Opentrons OT-2, Beckman Coulter Echo 650, Fritz Gyger CERTUS FLEX) | Automated compound pooling by library-specific rules | `MCEBIO={'compounds_per_well': 10, 'concentration': 20.0, 'solvent_ratio': '1:1 methanol:water', 'plate_format': '384-well'}, MCESCAF_MCEDRUG_OTAVAPEP_ENAMMOL_ENAMDISC={'compounds_per_well': 8, 'concentration_range': [8.0, 12.0], 'solvent_ratio': '1:1 methanol:water', 'plate_format': '384-well'}, NIHNP={'compounds_per_well': 7, 'concentration': 5.0, 'solvent_ratio': '4:4:2 methanol:acetonitrile:water', 'plate_format': '96-well', 'evaporation_correction': True}` |
| 4 | Flow injection–MS^n data acquisition | Thermo Vanquish Horizon UHPLC + Orbitrap ID-X | Data-dependent MS^n tree acquisition with dynamic exclusion | `injection_volume={'MCEBIO_MCESCAF_MCEDRUG_OTAVAPEP_ENAMMOL_ENAMDISC': 2.0, 'NIHNP': 3.0}, ionization={'positive': {'vaporizer_temp_C': 75, 'ion_transfer_tube_temp_C': 275, 'spray_voltage_V': 3000, 'sheath_gas': 25, 'aux_gas': 5}, 'negative': {'spray_voltage_V': 2000}}, MS1={'mz_range': [115, 2000], 'resolution': 30000, 'rf_lens_percent': 50, 'agc_target': 40000, 'maxIT_ms': 50}, MS2_selection={'top_n': 3, 'min_intensity_pos': 600000, 'min_intensity_neg': 200000, 'isolation_window': 1.2, 'resolution': 15000, 'agc_target': 12000, 'maxIT_ms': {'pos': 50, 'neg': 80}}, MS2_energies_eV=[20, 60], MS2_assisted_CE_steps_eV=[15, 30, 45, 60, 75], MS3_selection={'top_n': 5, 'min_intensity_pos': 20000, 'min_intensity_neg': 10000, 'mz_range': [90, 2000], 'isolation_window_MS1': 1.2, 'isolation_window_MS2': 2.0, 'resolution': 60000, 'agc_target': 50000, 'maxIT_ms': {'pos': 200, 'neg': 500}, 'energies_eV': [20, 40, 60]}, MS4_selection={'top_n': 2, 'min_intensity_pos': 20000, 'min_intensity_neg': 10000, 'isolation_window': 2.2, 'same_as_MS3_except_energy': True}, MS5_selection={'top_n': 2, 'mz_range': [150, 2000], 'isolation_window': 3.0, 'energies_eV': [40, 60], 'same_as_MS3_except_energy_and_window': True}, dynamic_exclusion={'time_window_s': 200, 'exclusion_duration_s': 70, 'mass_tolerance': 0.2, 'isotope_exclusion_window': 2.0, 'max_occurrence_divisible_by_3': True}, blank_exclusion={'masses': [149.72, 173.52], 'width': 0.03, 'levels': ['MS1', 'MS2', 'MS3', 'MS4', 'MS5']}` |
| 5 | MS^n tree library generation and spectral evaluation | MZmine 3.x (v3.x (exact version not specified; batch files provided)) | Automated feature detection, MS^n tree assembly, spectral quality filtering, and metadata-driven annotation | `import_format=['Thermo .raw', '.mzML (via ThermoRawFileParser)'], batch_files=['mzmine_exclusion_blankprofile_pos.mzbatch', 'mzmine_exclusion_blankprofile_neg.mzbatch', 'mzmine_msn_library_pos.mzbatch', 'mzmine_msn_library_neg.mzbatch'], mzwizard_config=mzwizard_msn_library.mzmwizard, modules_used=['mzwizard', 'peak picker', 'gap filler', 'alignment', 'MS^n tree builder', 'spectral quality assessment', 'metadata annotation engine']` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Extended Data Fig. 2 | workflow_diagram | Schematic of the MS^n acquisition schema showing hierarchical fragmentation from MS1 to MS5 with collision energy selection logic. | Adobe Illustrator | [4] |
| Extended Data Fig. 5 | msn_tree | Representative MS^n tree visualization showing structural validation pathways and substructure confirmation. | MZmine internal viewer | [5] |

## Parameter Highlights

- **Step 1 (Python script (metadata_cleanup_prefect.py))**: `salt_removal_enabled=True, structure_standardization_pipeline=ChEMBL, computed_properties=['canonical_SMILES', 'isomeric_SMILES', 'InChI', 'InChIKey', 'logP', 'monoisotopic_mass']`
- **Step 2 (Python script (sequence_creation.py))**: `polarity_order=['positive', 'negative'], filename_template={date}_{library_plate_well}_{method}_{polarity}, acquisition_platform=Xcalibur (Thermo), flow_injection_method=Orbitrap MS^n`
- **Step 3 (Liquid handlers (Opentrons OT-2, Beckman Coulter Echo 650, Fritz Gyger CERTUS FLEX))**: `MCEBIO={'compounds_per_well': 10, 'concentration': 20.0, 'solvent_ratio': '1:1 methanol:water', 'plate_format': '384-well'}, MCESCAF_MCEDRUG_OTAVAPEP_ENAMMOL_ENAMDISC={'compounds_per_well': 8, 'concentration_range': [8.0, 12.0], 'solvent_ratio': '1:1 methanol:water', 'plate_format': '384-well'}, NIHNP={'compounds_per_well': 7, 'concentration': 5.0, 'solvent_ratio': '4:4:2 methanol:acetonitrile:water', 'plate_format': '96-well', 'evaporation_correction': True}`
- **Step 4 (Thermo Vanquish Horizon UHPLC + Orbitrap ID-X)**: `injection_volume={'MCEBIO_MCESCAF_MCEDRUG_OTAVAPEP_ENAMMOL_ENAMDISC': 2.0, 'NIHNP': 3.0}, ionization={'positive': {'vaporizer_temp_C': 75, 'ion_transfer_tube_temp_C': 275, 'spray_voltage_V': 3000, 'sheath_gas': 25, 'aux_gas': 5}, 'negative': {'spray_voltage_V': 2000}}, MS1={'mz_range': [115, 2000], 'resolution': 30000, 'rf_lens_percent': 50, 'agc_target': 40000, 'maxIT_ms': 50}, MS2_selection={'top_n': 3, 'min_intensity_pos': 600000, 'min_intensity_neg': 200000, 'isolation_window': 1.2, 'resolution': 15000, 'agc_target': 12000, 'maxIT_ms': {'pos': 50, 'neg': 80}}, MS2_energies_eV=[20, 60], MS2_assisted_CE_steps_eV=[15, 30, 45, 60, 75], MS3_selection={'top_n': 5, 'min_intensity_pos': 20000, 'min_intensity_neg': 10000, 'mz_range': [90, 2000], 'isolation_window_MS1': 1.2, 'isolation_window_MS2': 2.0, 'resolution': 60000, 'agc_target': 50000, 'maxIT_ms': {'pos': 200, 'neg': 500}, 'energies_eV': [20, 40, 60]}, MS4_selection={'top_n': 2, 'min_intensity_pos': 20000, 'min_intensity_neg': 10000, 'isolation_window': 2.2, 'same_as_MS3_except_energy': True}, MS5_selection={'top_n': 2, 'mz_range': [150, 2000], 'isolation_window': 3.0, 'energies_eV': [40, 60], 'same_as_MS3_except_energy_and_window': True}, dynamic_exclusion={'time_window_s': 200, 'exclusion_duration_s': 70, 'mass_tolerance': 0.2, 'isotope_exclusion_window': 2.0, 'max_occurrence_divisible_by_3': True}, blank_exclusion={'masses': [149.72, 173.52], 'width': 0.03, 'levels': ['MS1', 'MS2', 'MS3', 'MS4', 'MS5']}`
- **Step 5 (MZmine 3.x (v3.x (exact version not specified; batch files provided)))**: `import_format=['Thermo .raw', '.mzML (via ThermoRawFileParser)'], batch_files=['mzmine_exclusion_blankprofile_pos.mzbatch', 'mzmine_exclusion_blankprofile_neg.mzbatch', 'mzmine_msn_library_pos.mzbatch', 'mzmine_msn_library_neg.mzbatch'], mzwizard_config=mzwizard_msn_library.mzmwizard, modules_used=['mzwizard', 'peak picker', 'gap filler', 'alignment', 'MS^n tree builder', 'spectral quality assessment', 'metadata annotation engine']`

## Reproducibility Notes

- Full mzBatch and mzwizard configuration files provided as Supplementary Files 2–6
- All MS^n acquisition parameters fully enumerated with numerical precision (eV, ms, ppm, m/z ranges)
- Open-source toolchain (MZmine + ThermoRawFileParser + Python scripts) with public GitHub links and Zenodo DOI
- Raw data publicly available on MassIVE (MSV000095421) and processed library on GNPS
- Comprehensive metadata cleaning and structure standardization pipeline fully documented and reusable

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
