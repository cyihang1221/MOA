# Skill: Open access repository-scale propagated nearest neighbor suspect spectral library for untargeted metabolomics.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 92/100
- **source**: Bittremieux W et al. (2023), Nature communications, DOI: 10.1038/s41467-023-44035-y, PMID: 38123557

## Analysis Goal
复现/对齐文献研究目标：Open access repository-scale propagated nearest neighbor suspect spectral library for untargeted metabolomics.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data ingestion from MetaboLights | GNPS/MassIVE | mirroring | `ion_mode=positive, sample_count=10000` |
| 2 | Molecular networking (first round, per-dataset) | GNPS | MS-Cluster + GNPS molecular networking | `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.8, min_matched_peaks=6, min_spectra_per_cluster=2, max_edges_per_node=10, mscluster_mixture_probability_threshold=0.05, mscluster_rounds=3, preprocessing={'remove_ions_near_precursor': True, 'remove_window_da': 17.0, 'top_ions_per_50_mz_window': 6}` |
| 3 | Molecular networking (second round, cross-dataset) | GNPS | MS-Cluster + GNPS molecular networking | `precursor_mass_tolerance_mz=0.1, fragment_mass_tolerance_mz=0.1, cosine_similarity_threshold=0.8, min_matched_peaks=6, min_spectra_per_cluster=2, max_edges_per_node=10, preprocessing={'remove_ions_near_precursor': True, 'remove_window_da': 17.0, 'top_ions_per_50_mz_window': 6}` |
| 4 | Spectral library searching for annotation | GNPS spectral library search | modified cosine similarity | `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.7, min_matched_peaks=6, reference_libraries_count=22, reference_spectra_count=221224` |
| 5 | Nearest neighbor suspect identification | custom GNPS pipeline | propagated annotation via spectral similarity in molecular network | `max_precursor_mass_tolerance_ppm=20, cosine_similarity_threshold=0.8, min_matched_peaks=6, require_nonzero_precursor_delta=True, min_occurrence_of_delta_mass=10` |
| 6 | Molecular formula prediction | SIRIUS (v4.5.2) | CSI:FingerID + CANOPUS | `precursor_mass_tolerance_ppm={'Orbitrap': 10, 'Q-TOF': 25}, input_data_type=MS/MS only, other_settings=default` |
| 7 | Molecular formula prediction | BUDDY (v1.3) | elemental composition enumeration + scoring | `precursor_mass_tolerance_ppm={'FT-ICR': 5, 'Orbitrap': 10, 'Q-TOF': 25}, fragment_mass_tolerance_ppm=2× precursor tolerance, allowed_elements_initial=['C', 'H', 'N', 'O', 'P', 'S'], allowed_elements_extended=['C', 'H', 'N', 'O', 'P', 'S', 'F', 'Cl', 'Br', 'I']` |
| 8 | Delta mass calibration and modification annotation | UNIMOD + custom list | mass difference matching to biochemical modifications | `modification_sources=['UNIMOD', 'Supplementary Data 3'], min_delta_frequency=10` |
| 9 | Suspect spectral library curation and naming | custom script | structured nomenclature generation | `naming_template=Suspect related to [compound name] (predicted molecular formula: [SIRIUS and/or BUDDY]) with delta m/z [sign delta] (putative explanation: [modification])` |
| 10 | Library validation via spectral searching | GNPS spectral library search | cosine similarity search | `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.8, min_matched_peaks=6, test_datasets_total=1407, test_spectra_total=592000000, independent_test_set_size=72` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (GNPS/MassIVE)**: `ion_mode=positive, sample_count=10000`
- **Step 2 (GNPS)**: `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.8, min_matched_peaks=6, min_spectra_per_cluster=2, max_edges_per_node=10, mscluster_mixture_probability_threshold=0.05, mscluster_rounds=3, preprocessing={'remove_ions_near_precursor': True, 'remove_window_da': 17.0, 'top_ions_per_50_mz_window': 6}`
- **Step 3 (GNPS)**: `precursor_mass_tolerance_mz=0.1, fragment_mass_tolerance_mz=0.1, cosine_similarity_threshold=0.8, min_matched_peaks=6, min_spectra_per_cluster=2, max_edges_per_node=10, preprocessing={'remove_ions_near_precursor': True, 'remove_window_da': 17.0, 'top_ions_per_50_mz_window': 6}`
- **Step 4 (GNPS spectral library search)**: `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.7, min_matched_peaks=6, reference_libraries_count=22, reference_spectra_count=221224`
- **Step 5 (custom GNPS pipeline)**: `max_precursor_mass_tolerance_ppm=20, cosine_similarity_threshold=0.8, min_matched_peaks=6, require_nonzero_precursor_delta=True, min_occurrence_of_delta_mass=10`
- **Step 6 (SIRIUS (v4.5.2))**: `precursor_mass_tolerance_ppm={'Orbitrap': 10, 'Q-TOF': 25}, input_data_type=MS/MS only, other_settings=default`
- **Step 7 (BUDDY (v1.3))**: `precursor_mass_tolerance_ppm={'FT-ICR': 5, 'Orbitrap': 10, 'Q-TOF': 25}, fragment_mass_tolerance_ppm=2× precursor tolerance, allowed_elements_initial=['C', 'H', 'N', 'O', 'P', 'S'], allowed_elements_extended=['C', 'H', 'N', 'O', 'P', 'S', 'F', 'Cl', 'Br', 'I']`
- **Step 8 (UNIMOD + custom list)**: `modification_sources=['UNIMOD', 'Supplementary Data 3'], min_delta_frequency=10`
- **Step 9 (custom script)**: `naming_template=Suspect related to [compound name] (predicted molecular formula: [SIRIUS and/or BUDDY]) with delta m/z [sign delta] (putative explanation: [modification])`
- **Step 10 (GNPS spectral library search)**: `precursor_mass_tolerance_mz=2.0, fragment_mass_tolerance_mz=0.5, cosine_similarity_threshold=0.8, min_matched_peaks=6, test_datasets_total=1407, test_spectra_total=592000000, independent_test_set_size=72`

## Reproducibility Notes

- All raw data deposited in MassIVE with DOIs
- Entire workflow executed on open-source GNPS platform
- Suspect library publicly downloadable and queryable via GNPS web interface
- Detailed parameters for all computational steps reported (tolerances, thresholds, versions)
- Reference implementations of SIRIUS and BUDDY used with versioned settings
- Independent test set explicitly defined (72 later-deposited datasets)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。

## Available-tool mapping
- `gnps` → molecular_networking_gnps / molecular_networking_fbmn
