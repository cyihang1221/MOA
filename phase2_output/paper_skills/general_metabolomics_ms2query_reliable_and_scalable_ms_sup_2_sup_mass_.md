# Skill: MS2Query: reliable and scalable MS<sup>2</sup> mass spectra-based analogue search.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: de Jonge NF et al. (2023), Nature communications, DOI: 10.1038/s41467-023-37446-4, PMID: 36990978

## Analysis Goal
复现/对齐文献研究目标：MS2Query: reliable and scalable MS<sup>2</sup> mass spectra-based analogue search.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Spectral data cleaning and preprocessing | matchms | intensity normalization, peak filtering, InChIKey imputation | `max_mz=1000, min_intensity_percent=0.1, max_peaks=500, min_peaks_per_spectrum=3, fragment_mass_tolerance_da=0.05` |
| 2 | Chemical fingerprint generation and structural similarity calculation | RDKit | Daylight fingerprint (2048-bit) + Tanimoto coefficient | `fingerprint_type=daylight, n_bits=2048, inchikey_prefix_length=14` |
| 3 | Spec2Vec model training | Spec2Vec | word2vec-based spectral embedding | `epochs=30, binning_decimals=2, use_unannotated_spectra=True` |
| 4 | MS2Deepscore model training | MS2Deepscore | Siamese neural network with cosine similarity on spectral embeddings | `training_data=fully annotated GNPS spectra only, settings_from_publication=True` |
| 5 | Training spectrum pair generation for random forest | custom Python script (scikit-learn + matchms) | top-100 MS2Deepscore pairing per query spectrum | `fraction_of_inchikeys_for_training=0.025, fraction_of_remaining_spectra=0.025, top_k_ms2deepscore_pairs=100` |
| 6 | Random forest model training | scikit-learn | impurity-based (Gini) random forest regression | `n_estimators=250, max_depth=5, loss_function=mean_squared_error, feature_importance_method=Gini importance` |
| 7 | Analogue search execution | MS2Query (v1.0.0 (implied by publication date)) | two-stage ranking: MS2Deepscore prefiltering → RF re-ranking | `preselection_count=2000, chemical_similarity_neighbors=10, precursor_mz_tolerance_da=100.0, exact_match_mz_tolerance_da=0.25` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Overview of MS2Query workflow: MS2Deepscore prefiltering followed by random forest re-ranking using 5 features. | Not specified | [7] |
| Figure 4 | workflow_diagram | Detailed workflow for computing two input features of the random forest: average MS2Deepscore and average Tanimoto score over 10 chemically similar library molecules. | Not specified | [2, 4, 6] |
| Figure 5 | workflow_diagram | End-to-end training workflow showing preparation, Spec2Vec (yellow), MS2Deepscore (red), and MS2Query random forest (green) model training steps. | Not specified | [1, 2, 3, 4, 5, 6] |

## Parameter Highlights

- **Step 1 (matchms)**: `max_mz=1000, min_intensity_percent=0.1, max_peaks=500, min_peaks_per_spectrum=3, fragment_mass_tolerance_da=0.05`
- **Step 2 (RDKit)**: `fingerprint_type=daylight, n_bits=2048, inchikey_prefix_length=14`
- **Step 3 (Spec2Vec)**: `epochs=30, binning_decimals=2, use_unannotated_spectra=True`
- **Step 4 (MS2Deepscore)**: `training_data=fully annotated GNPS spectra only, settings_from_publication=True`
- **Step 5 (custom Python script (scikit-learn + matchms))**: `fraction_of_inchikeys_for_training=0.025, fraction_of_remaining_spectra=0.025, top_k_ms2deepscore_pairs=100`
- **Step 6 (scikit-learn)**: `n_estimators=250, max_depth=5, loss_function=mean_squared_error, feature_importance_method=Gini importance`
- **Step 7 (MS2Query (v1.0.0 (implied by publication date)))**: `preselection_count=2000, chemical_similarity_neighbors=10, precursor_mz_tolerance_da=100.0, exact_match_mz_tolerance_da=0.25`

## Reproducibility Notes

- Full source code publicly available on GitHub under MIT license
- All input data explicitly sourced from GNPS with versioned URLs and timestamps
- Complete description of preprocessing, feature engineering, and model architecture
- Open-source dependencies fully specified (RDKit, matchms, scikit-learn, Spec2Vec, MS2Deepscore)
- Reproducible k-fold cross-validation design with clear train/test separation logic

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。
