# Skill: FragHub: A Mass Spectral Library Data Integration Workflow.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Dablanc A et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.4c02219, PMID: 39028894

## Analysis Goal
复现/对齐文献研究目标：FragHub: A Mass Spectral Library Data Integration Workflow.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | OMSL integration and format harmonization | FragHub | custom metadata mapping and spectral format normalization | `ionization_modes=['positive', 'negative'], chromatography_types=['LC', 'GC'], spectral_filters=['intensity_threshold', 'peak_count_min', 'mass_range']` |
| 2 | Metadata standardization and ontology alignment | FragHub | mapping to generic OMSL ontology (proposed in paper) | `required_metadata_fields=['compound_name', 'inchi_key', 'smiles', 'precursor_mz', 'adduct', 'ion_mode', 'instrument', 'collision_energy', 'retention_time', 'source_organism', 'matrix']` |
| 3 | Spectral filtering via GUI | FragHub | interactive intensity- and quality-based filtering | `min_peak_intensity_percent=1.0, min_number_of_peaks=5, mass_tolerance_ppm=10.0` |
| 4 | In-house library generation workflow | FragHub | template-driven spectral submission pipeline | `required_input_formats=['MSP', 'MGF'], validation_rules=['inchi_key_format', 'adduct_consistency', 'ion_mode_match']` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (FragHub)**: `ionization_modes=['positive', 'negative'], chromatography_types=['LC', 'GC'], spectral_filters=['intensity_threshold', 'peak_count_min', 'mass_range']`
- **Step 2 (FragHub)**: `required_metadata_fields=['compound_name', 'inchi_key', 'smiles', 'precursor_mz', 'adduct', 'ion_mode', 'instrument', 'collision_energy', 'retention_time', 'source_organism', 'matrix']`
- **Step 3 (FragHub)**: `min_peak_intensity_percent=1.0, min_number_of_peaks=5, mass_tolerance_ppm=10.0`
- **Step 4 (FragHub)**: `required_input_formats=['MSP', 'MGF'], validation_rules=['inchi_key_format', 'adduct_consistency', 'ion_mode_match']`

## Reproducibility Notes

- Source code publicly available under MIT license
- All generated data deposited on Zenodo with DOI
- Explicit specification of required metadata fields and spectral filters
- Support for multiple input formats and ionization/chromatography modes

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
