# Skill: Reproducible MS/MS library cleaning pipeline in matchms.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: de Jonge NF et al. (2024), Journal of cheminformatics, DOI: 10.1186/s13321-024-00878-1, PMID: 39075613

## Analysis Goal
复现/对齐文献研究目标：Reproducible MS/MS library cleaning pipeline in matchms.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Input spectral library loading and format standardization | matchms (v0.19.0) | SpectrumLoader | `metadata_harmonization=True, ignore_unknown_adducts=True` |
| 2 | Metadata curation and validation | matchms (v0.19.0) | MetadataValidator | `required_fields=['compound_name', 'smiles', 'inchi', 'precursor_mz', 'ionmode'], strict_smiles_validation=True, allow_missing_inchi=False` |
| 3 | Structure annotation validation via chemical consistency checks | rdkit | RDKit MolFromSmiles + sanitization + InChI round-trip validation | `sanitize=True, require_inchi_consistency=True, max_allowed_atom_count=100` |
| 4 | Spectral quality filtering | matchms (v0.19.0) | SpectrumFilter | `min_peaks=5, min_intensity_fraction=0.01, remove_precursor_peak=True, precursor_tolerance Dalton=0.5` |
| 5 | Adduct type inference and correction | matchms (v0.19.0) | AdductGuesser | `adducts_to_consider=['[M+H]+', '[M-H]-', '[M+Na]+', '[M+K]+', '[M+NH4]+', '[M-H2O+H]+'], mass_tolerance_ppm=10.0` |
| 6 | Library deduplication and clustering | matchms (v0.19.0) | SpectrumSimilarity (Cosine) | `tolerance_ppm=10.0, n_decimals_mass=3, min_similarity_score=0.95, cluster_method=single_linkage` |
| 7 | Logging, provenance tracking, and report generation | matchms (v0.19.0) | CleaningReportGenerator | `log_level=INFO, include_statistics=True, export_intermediate_results=False` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (matchms (v0.19.0))**: `metadata_harmonization=True, ignore_unknown_adducts=True`
- **Step 2 (matchms (v0.19.0))**: `required_fields=['compound_name', 'smiles', 'inchi', 'precursor_mz', 'ionmode'], strict_smiles_validation=True, allow_missing_inchi=False`
- **Step 3 (rdkit)**: `sanitize=True, require_inchi_consistency=True, max_allowed_atom_count=100`
- **Step 4 (matchms (v0.19.0))**: `min_peaks=5, min_intensity_fraction=0.01, remove_precursor_peak=True, precursor_tolerance Dalton=0.5`
- **Step 5 (matchms (v0.19.0))**: `adducts_to_consider=['[M+H]+', '[M-H]-', '[M+Na]+', '[M+K]+', '[M+NH4]+', '[M-H2O+H]+'], mass_tolerance_ppm=10.0`
- **Step 6 (matchms (v0.19.0))**: `tolerance_ppm=10.0, n_decimals_mass=3, min_similarity_score=0.95, cluster_method=single_linkage`
- **Step 7 (matchms (v0.19.0))**: `log_level=INFO, include_statistics=True, export_intermediate_results=False`

## Reproducibility Notes

- Full pipeline implemented in open-source matchms (BSD-3-Clause licensed)
- Versioned software (v0.19.0) with DOI
- Comprehensive logging and HTML reporting built-in
- All parameters explicitly documented in manuscript and code
- Uses only open-source dependencies (RDKit, NumPy, SciPy)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
