# Skill: A resource to empirically establish drug exposure records directly from untargeted metabolomics data.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 87/100
- **source**: Zhao HN et al. (2025), Nature communications, DOI: 10.1038/s41467-025-65993-5, PMID: 41366203

## Analysis Goal
复现/对齐文献研究目标：A resource to empirically establish drug exposure records directly from untargeted metabolomics data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Reference spectra collection and curation | GNPS spectral library | ChEMBL structure pipeline | `salt_removal=True, standardization_method=canonical SMILES, isomeric SMILES, InChI, InChIKey, database_search_keys=['InChIKey', 'first_part_of_InChIKey'], databases_queried=['Broad Institute Drug Repurposing Hub', 'DrugBank', 'DrugCentral', 'ChEMBL'], search_date_range=['July 2022', 'August 2022', 'October 2022', 'March 2023']` |
| 2 | Drug analog discovery via molecular networking | GNPS/Molecular Networking | cosine similarity-based clustering | `cosine_similarity_threshold=0.8, minimum_matching_ions=6, network_type=repository-scale` |
| 3 | Drug analog discovery via fastMASST | fastMASST | mass spectral similarity search | `cosine_score_threshold=0.8, minimum_matching_ions=6, precursor_mass_window_da=200, fragment_mz_tolerance_da=0.02, precursor_mz_tolerance_da=0.02, search_date=March 2025, api_used=Fast Search tool API` |
| 4 | Analog filtering (Step One) | Custom R scripts | Metadata-based exclusion | `exclusion_criteria=endogenous or dietary source (manually curated metadata)` |
| 5 | Analog filtering (Step Two) | Custom R scripts | Mass offset filtering using curated delta masses | `allowed_mass_offsets_da=[14.02, 176.03, 17.03], sources_of_offsets=['UNIMOD', 'community-curated list (Supplementary Data 1)', 'Host Gut Microbiota Metabolism Xenobiotics Databases'], total_offsets_included=156` |
| 6 | Analog filtering (Step Three) | Falcon spectrum clustering + GNPS Library Search | Spectral clustering (eps=0.05) followed by library matching | `clustering_eps=0.05, library_search_cosine_threshold=0.7, library_search_minimum_matching_peaks=5, exclusion_rule=remove matches to full GNPS Library` |
| 7 | Analog filtering (Step Four) | GNPS Library Search workflow | Cross-dataset frequency filtering | `test_datasets_count=20, test_datasets_types=['human fecal', 'human breast milk', 'human plasma', 'human skin', 'human brain', 'mouse tissues'], test_datasets_ids=['MSV000080673', 'MSV000095418', 'MSV000094515', 'MSV000092833', 'MSV000082493', 'MSV000091520', 'MSV000090877', 'MSV000094395', 'MSV000085944', 'MSV000084008', 'MSV000090877', 'MSV000086415', 'MSV000091363', 'MSV000096035', 'MSV000096036', 'MSV000096037', 'MSV000096038', 'MSV000096039', 'MSV000093230', 'MSV000093168'], library_search_cosine_threshold=0.7, library_search_minimum_matching_peaks=5` |
| 8 | Structural hypothesis generation for analogs | ModiFinder | MS/MS fragment shift analysis for modification localization | `mass_tolerance_ppm=40, fragmentation_depth=2, confidence_threshold_for_location=0.6, coverage_rate=0.32, high_confidence_coverage_rate=0.6` |
| 9 | Analytical artifact vs. biological derivative classification | fastMASST + XIC correlation + MS/MS fragment logic | Pearson correlation of extracted ion chromatograms + adduct/in-source fragment rules | `precursor_and_fragment_mz_tolerance_da=0.02, cosine_similarity_threshold_for_cooccurrence=0.9, minimum_matching_peaks_for_cooccurrence=6, xic_window_scans=10, correlation_threshold_r2=0.9, isotope_mass_offsets_da=[1.0, 2.0], adduct_mass_offsets_da=[21.98, 37.95, 37.96], intensity_filtering_applied=False` |
| 10 | Ontology-based metadata curation | ChemFOnt, PubChem, Broad Institute Drug Repurposing Hub, FDA documents, ATC Classification, NIH, EMA, DrugBank | Multi-source ontology mapping + expert manual curation | `metadata_fields_curated=['exposure_sources', 'therapeutic_areas', 'pharmacologic_classes', 'therapeutic_indications', 'mechanisms_of_action'], curation_experts=3, coverage_before_curation=3,894 drugs (86,364 spectra); 900 drugs (22,935 spectra), coverage_after_curation=4,560 drugs (90,325 spectra), sources_for_pharmacologic_class=WHO ATC codes` |
| 11 | Empirical validation using pharmacokinetic datasets | GNPS Library Search workflow | Targeted MS/MS library matching | `datasets_validated=['MSV000085944', 'MSV000084008', 'MSV000082493'], drugs_tested=['diphenhydramine', 'caffeine', 'midazolam', 'omeprazole'], sample_types=['plasma', 'skin swabs', 'fecal'], time_series_resolution=multiple timepoints (e.g., 0–24 h post-dose), library_search_cosine_threshold=0.7, library_search_minimum_matching_peaks=5` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (GNPS spectral library)**: `salt_removal=True, standardization_method=canonical SMILES, isomeric SMILES, InChI, InChIKey, database_search_keys=['InChIKey', 'first_part_of_InChIKey'], databases_queried=['Broad Institute Drug Repurposing Hub', 'DrugBank', 'DrugCentral', 'ChEMBL'], search_date_range=['July 2022', 'August 2022', 'October 2022', 'March 2023']`
- **Step 2 (GNPS/Molecular Networking)**: `cosine_similarity_threshold=0.8, minimum_matching_ions=6, network_type=repository-scale`
- **Step 3 (fastMASST)**: `cosine_score_threshold=0.8, minimum_matching_ions=6, precursor_mass_window_da=200, fragment_mz_tolerance_da=0.02, precursor_mz_tolerance_da=0.02, search_date=March 2025, api_used=Fast Search tool API`
- **Step 4 (Custom R scripts)**: `exclusion_criteria=endogenous or dietary source (manually curated metadata)`
- **Step 5 (Custom R scripts)**: `allowed_mass_offsets_da=[14.02, 176.03, 17.03], sources_of_offsets=['UNIMOD', 'community-curated list (Supplementary Data 1)', 'Host Gut Microbiota Metabolism Xenobiotics Databases'], total_offsets_included=156`
- **Step 6 (Falcon spectrum clustering + GNPS Library Search)**: `clustering_eps=0.05, library_search_cosine_threshold=0.7, library_search_minimum_matching_peaks=5, exclusion_rule=remove matches to full GNPS Library`
- **Step 7 (GNPS Library Search workflow)**: `test_datasets_count=20, test_datasets_types=['human fecal', 'human breast milk', 'human plasma', 'human skin', 'human brain', 'mouse tissues'], test_datasets_ids=['MSV000080673', 'MSV000095418', 'MSV000094515', 'MSV000092833', 'MSV000082493', 'MSV000091520', 'MSV000090877', 'MSV000094395', 'MSV000085944', 'MSV000084008', 'MSV000090877', 'MSV000086415', 'MSV000091363', 'MSV000096035', 'MSV000096036', 'MSV000096037', 'MSV000096038', 'MSV000096039', 'MSV000093230', 'MSV000093168'], library_search_cosine_threshold=0.7, library_search_minimum_matching_peaks=5`
- **Step 8 (ModiFinder)**: `mass_tolerance_ppm=40, fragmentation_depth=2, confidence_threshold_for_location=0.6, coverage_rate=0.32, high_confidence_coverage_rate=0.6`
- **Step 9 (fastMASST + XIC correlation + MS/MS fragment logic)**: `precursor_and_fragment_mz_tolerance_da=0.02, cosine_similarity_threshold_for_cooccurrence=0.9, minimum_matching_peaks_for_cooccurrence=6, xic_window_scans=10, correlation_threshold_r2=0.9, isotope_mass_offsets_da=[1.0, 2.0], adduct_mass_offsets_da=[21.98, 37.95, 37.96], intensity_filtering_applied=False`
- **Step 10 (ChemFOnt, PubChem, Broad Institute Drug Repurposing Hub, FDA documents, ATC Classification, NIH, EMA, DrugBank)**: `metadata_fields_curated=['exposure_sources', 'therapeutic_areas', 'pharmacologic_classes', 'therapeutic_indications', 'mechanisms_of_action'], curation_experts=3, coverage_before_curation=3,894 drugs (86,364 spectra); 900 drugs (22,935 spectra), coverage_after_curation=4,560 drugs (90,325 spectra), sources_for_pharmacologic_class=WHO ATC codes`
- **Step 11 (GNPS Library Search workflow)**: `datasets_validated=['MSV000085944', 'MSV000084008', 'MSV000082493'], drugs_tested=['diphenhydramine', 'caffeine', 'midazolam', 'omeprazole'], sample_types=['plasma', 'skin swabs', 'fecal'], time_series_resolution=multiple timepoints (e.g., 0–24 h post-dose), library_search_cosine_threshold=0.7, library_search_minimum_matching_peaks=5`

## Reproducibility Notes

- All 20 validation datasets explicitly accessioned and publicly available
- Full code for fastMASST batch search publicly shared on GitHub under MIT license
- GNPS Drug Library is openly accessible via GNPS web interface with standardized USI links
- Comprehensive, multi-layered filtering and curation steps fully described with quantitative thresholds
- Ontology-based metadata curation grounded in authoritative sources (ATC, FDA, DrugBank, EMA) and expert-reviewed

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
