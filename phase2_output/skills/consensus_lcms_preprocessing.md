# Skill: consensus lcms preprocessing

- **skill_type**: multi_paper_consensus
- **functional_domain**: `lcms_preprocessing`
- **n_papers**: 22
- **trigger_keywords**: 峰检测, XCMS, 预处理, peak picking, alignment, mzML

## Analysis Goal
当用户目标匹配「consensus lcms preprocessing」场景时，采用多篇高水平文献的工具偏好与参数共识，规划分析流程并产出对应科研图与解释。

## Tool Preference Order

- `XCMS` （出现于 12/22 篇）
- `R` （出现于 4/22 篇）
- `ProteoWizard` （出现于 4/22 篇）
- `OpenMS` （出现于 3/22 篇）
- `custom R script` （出现于 3/22 篇）
- `ProteoWizard msconvert` （出现于 2/22 篇）
- `IPO` （出现于 2/22 篇）
- `MZmine` （出现于 2/22 篇）
- `XCMS Online` （出现于 2/22 篇）
- `MZmine 2` （出现于 2/22 篇）
- `PCA` （出现于 2/22 篇）
- `custom Python` （出现于 2/22 篇）

## Parameter Consensus（按出现频次）

- **pca** `n_components=2` — 2 篇共识
  - source: Rong Z et al. (2020), Analytical chemistry, DOI: 10.1021/acs.analchem.9b05460, PMID: 32207605
  - source: Rong Z et al. (2020), Analytical chemistry, DOI: 10.1021/acs.analchem.9b05460, PMID: 32207605
- **xcms (v3.12.0)** `ppm=5, peakwidth=[10, 60], snthresh=10, prefilter=[3, 100], noise=0, verbose.columns=False` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **xcms (v3.12.0)** `span=0.2, plottype=none` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **xcms (v3.12.0)** `minfrac=0.5, max=3` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **r (caret, randomforest, e1071)** `ntree=500, mtry=sqrt(p), repeatedcv_folds=5, repeats=10` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **autotuner (v1.4.0)** `n_iterations=50, population_size=20, mutation_rate=0.1` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **ipo (isotopologue parameter optimization) (v1.18.0)** `minfrac=0.5, maxiso=3, mzdiff=0.01` — 1 篇共识
  - source: Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- **python script (metadata_cleanup_prefect.py)** `salt_removal_enabled=True, structure_standardization_pipeline=ChEMBL, computed_properties=['canonical_SMILES', 'isomeric_SMILES', 'InChI', 'InChIKey', 'logP', 'monoisotopic_mass']` — 1 篇共识
  - source: Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295
- **python script (sequence_creation.py)** `polarity_order=['positive', 'negative'], filename_template={date}_{library_plate_well}_{method}_{polarity}, acquisition_platform=Xcalibur (Thermo), flow_injection_method=Orbitrap MS^n` — 1 篇共识
  - source: Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295
- **liquid handlers (opentrons ot-2, beckman coulter echo 650, fritz gyger certus flex)** `MCEBIO={'compounds_per_well': 10, 'concentration': 20.0, 'solvent_ratio': '1:1 methanol:water', 'plate_format': '384-well'}, MCESCAF_MCEDRUG_OTAVAPEP_ENAMMOL_ENAMDISC={'compounds_per_well': 8, 'concentration_range': [8.0, 12.0], 'solvent_ratio': '1:1 methanol:water', 'plate_format': '384-well'}, NIHNP={'compounds_per_well': 7, 'concentration': 5.0, 'solvent_ratio': '4:4:2 methanol:acetonitrile:water', 'plate_format': '96-well', 'evaporation_correction': True}` — 1 篇共识
  - source: Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295
- **thermo vanquish horizon uhplc + orbitrap id-x** `injection_volume={'MCEBIO_MCESCAF_MCEDRUG_OTAVAPEP_ENAMMOL_ENAMDISC': 2.0, 'NIHNP': 3.0}, ionization={'positive': {'vaporizer_temp_C': 75, 'ion_transfer_tube_temp_C': 275, 'spray_voltage_V': 3000, 'sheath_gas': 25, 'aux_gas': 5}, 'negative': {'spray_voltage_V': 2000}}, MS1={'mz_range': [115, 2000], 'resolution': 30000, 'rf_lens_percent': 50, 'agc_target': 40000, 'maxIT_ms': 50}, MS2_selection={'top_n': 3, 'min_intensity_pos': 600000, 'min_intensity_neg': 200000, 'isolation_window': 1.2, 'resolution': 15000, 'agc_target': 12000, 'maxIT_ms': {'pos': 50, 'neg': 80}}, MS2_energies_eV=[20, 60], MS2_assisted_CE_steps_eV=[15, 30, 45, 60, 75], MS3_selection={'top_n': 5, 'min_intensity_pos': 20000, 'min_intensity_neg': 10000, 'mz_range': [90, 2000], 'isolation_window_MS1': 1.2, 'isolation_window_MS2': 2.0, 'resolution': 60000, 'agc_target': 50000, 'maxIT_ms': {'pos': 200, 'neg': 500}, 'energies_eV': [20, 40, 60]}, MS4_selection={'top_n': 2, 'min_intensity_pos': 20000, 'min_intensity_neg': 10000, 'isolation_window': 2.2, 'same_as_MS3_except_energy': True}, MS5_selection={'top_n': 2, 'mz_range': [150, 2000], 'isolation_window': 3.0, 'energies_eV': [40, 60], 'same_as_MS3_except_energy_and_window': True}, dynamic_exclusion={'time_window_s': 200, 'exclusion_duration_s': 70, 'mass_tolerance': 0.2, 'isotope_exclusion_window': 2.0, 'max_occurrence_divisible_by_3': True}, blank_exclusion={'masses': [149.72, 173.52], 'width': 0.03, 'levels': ['MS1', 'MS2', 'MS3', 'MS4', 'MS5']}` — 1 篇共识
  - source: Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295
- **mzmine 3.x (v3.x (exact version not specified; batch files provided))** `import_format=['Thermo .raw', '.mzML (via ThermoRawFileParser)'], batch_files=['mzmine_exclusion_blankprofile_pos.mzbatch', 'mzmine_exclusion_blankprofile_neg.mzbatch', 'mzmine_msn_library_pos.mzbatch', 'mzmine_msn_library_neg.mzbatch'], mzwizard_config=mzwizard_msn_library.mzmwizard, modules_used=['mzwizard', 'peak picker', 'gap filler', 'alignment', 'MS^n tree builder', 'spectral quality assessment', 'metadata annotation engine']` — 1 篇共识
  - source: Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295
- **proteowizard (msconvert)** `32bit=True, filter=['peakPicking', 'zeroSample', 'titleMaker']` — 1 篇共识
  - source: Graça G et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c03032, PMID: 35180347
- **xcms** `ppm=5, snthr=10, prefilter=[3, 100], peakwidth=[10, 60], noise=500, bw=10, mzdiff=-0.001, minfrac=0.5, max=50` — 1 篇共识
  - source: Graça G et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c03032, PMID: 35180347
- **metaboannotator (v1.0.0)** `cor_threshold=0.7, rt_window_sec=3, intensity_ratio_min=0.01, intensity_ratio_max=0.9` — 1 篇共识
  - source: Graça G et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c03032, PMID: 35180347
- **metaboannotator (v1.0.0)** `mass_tol_ppm=10, library_match_score_min=0.6, min_fragment_matches=2` — 1 篇共识
  - source: Graça G et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c03032, PMID: 35180347
- **metaboannotator (v1.0.0)** `top_n=5` — 1 篇共识
  - source: Graça G et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c03032, PMID: 35180347
- **ft-icr-ms** `ionization=ESI, polarity=['positive', 'negative']` — 1 篇共识
  - source: Brix F et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c01380, PMID: 38113356
- **compassxtract** `output_format=mzML` — 1 篇共识
  - source: Brix F et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c01380, PMID: 38113356
- **openms (v2.7.0)** `mass_tolerance_ppm=2, rt_tolerance_sec=15, min_charge=1, max_charge=3` — 1 篇共识
  - source: Brix F et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c01380, PMID: 38113356

## Expected Figures Consensus

- `workflow_diagram` （16 次）
- `bar_chart` （15 次）
- `boxplot` （7 次）
- `heatmap` （6 次）
- `pca_scores` （6 次）
- `volcano_plot` （6 次）
- `pathway_map` （6 次）
- `other` （4 次）
- `subnetwork_graph` （3 次）
- `chromatogram` （2 次）

## Representative Sources

- Lassen J et al. (2021), Analytical chemistry, DOI: 10.1021/acs.analchem.1c02000, PMID: 34585906
- Brungs C et al. (2025), Nature methods, DOI: 10.1038/s41592-025-02813-0, PMID: 40954295
- Graça G et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c03032, PMID: 35180347
- Brix F et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c01380, PMID: 38113356
- Hughes A et al. (2025), Analytical chemistry, DOI: 10.1021/acs.analchem.4c03124, PMID: 39757901
- Kambhampati S et al. (2024), Communications biology, DOI: 10.1038/s42003-024-05844-z, PMID: 38347116
- Heuckeroth S et al. (2024), Nature protocols, DOI: 10.1038/s41596-024-00996-y, PMID: 38769143
- Tripathi A et al. (2021), Nature chemical biology, DOI: 10.1038/s41589-020-00677-3, PMID: 33199911
- Wang H et al. (2023), Analytical chemistry, DOI: 10.1021/acs.analchem.2c05079, PMID: 37042095
- Stancliffe E et al. (2023), Analytical chemistry, DOI: 10.1021/acs.analchem.3c00764, PMID: 37314824
- Müller E et al. (2020), Analytical chemistry, DOI: 10.1021/acs.analchem.0c00899, PMID: 32786516
- El Abiead Y et al. (2022), Analytical chemistry, DOI: 10.1021/acs.analchem.1c05270, PMID: 35671103

## Agent Usage Notes
- 参数冲突时：多篇共识 > 单篇报告 > 工具默认值。
- 必须映射到系统可用工具名；不可发明未注册工具。
- 出图与解释服务于用户分析目的，不只做样式改图。
