# Skill: Reproducible molecular networking of untargeted mass spectrometry data using GNPS.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 92/100
- **source**: Aron AT et al. (2020), Nature protocols, DOI: 10.1038/s41596-020-0317-5, PMID: 32405051

## Analysis Goal
复现/对齐文献研究目标：Reproducible molecular networking of untargeted mass spectrometry data using GNPS.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data upload and registration | GNPS | web-based submission | `—` |
| 2 | Spectral pre-processing | GNPS | peak filtering, deisotoping, dereplication | `min_peak_intensity=0.001, max_number_of_peaks_per_spectrum=100, precursor_mass_tolerance=0.02, fragment_mass_tolerance=0.02` |
| 3 | Molecular networking via spectral similarity | GNPS | Cosine similarity (modified dot product) | `cosine_score_threshold=0.7, min_matched_peaks=6, max_shift_mz=1.0, min_precursor_difference=5.0, max_precursor_difference=1000.0` |
| 4 | Annotation propagation and spectral library matching | GNPS | library search against GNPS Mass Spectrometry Reference Library | `library_match_threshold=0.7, min_matched_peaks_for_annotation=6, mass_error_tolerance_ppm=20.0` |
| 5 | Network visualization and subnetwork extraction | Cytoscape | force-directed layout (e.g., Prefuse Force Directed) | `node_size_attribute=number_of_spectra, edge_thickness_attribute=cosine_score` |
| 6 | Cross-dataset propagation and knowledge sharing | GNPS | job cloning and annotation inheritance | `—` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | Schematic of molecular network generation from tandem mass spectra, showing preprocessing, spectral comparison, network construction, and annotation. | Adobe Illustrator / GNPS web interface | [1, 2, 3, 4] |
| Fig. 2 | workflow_diagram | Flowchart of the full protocol through Step 32, highlighting core molecular networking steps and optional downstream analyses. | Lucidchart / GNPS documentation | [1, 2, 3, 4, 5, 6] |
| Fig. 3 | network | Mouse duodenum global molecular network visualized in Cytoscape, illustrating metabolite diversity and clustering by spectral similarity. | Cytoscape | [3, 5] |
| Fig. 6 | network | Propagation of molecular networking to reveal cross-sample relationships between structurally related molecules. | Cytoscape / GNPS web viewer | [6] |
| Fig. 7 | network | Stenothricin molecular family subnetwork showing strain-specific and shared detections across Streptomyces isolates. | Cytoscape | [3, 4, 5] |
| Fig. 8 | network | Quinolone molecular family subnetwork detected in lung tissue and Pseudomonas isolates, demonstrating host–microbe metabolic overlap. | Cytoscape | [3, 4, 5] |

## Parameter Highlights

- **Step 2 (GNPS)**: `min_peak_intensity=0.001, max_number_of_peaks_per_spectrum=100, precursor_mass_tolerance=0.02, fragment_mass_tolerance=0.02`
- **Step 3 (GNPS)**: `cosine_score_threshold=0.7, min_matched_peaks=6, max_shift_mz=1.0, min_precursor_difference=5.0, max_precursor_difference=1000.0`
- **Step 4 (GNPS)**: `library_match_threshold=0.7, min_matched_peaks_for_annotation=6, mass_error_tolerance_ppm=20.0`
- **Step 5 (Cytoscape)**: `node_size_attribute=number_of_spectra, edge_thickness_attribute=cosine_score`

## Reproducibility Notes

- All raw data deposited in MassIVE with public accession IDs
- GNPS workflows are open-source and version-controlled on GitHub
- Every analysis job is shareable/clonable with full provenance
- Protocol includes step numbers (1–53) and explicit parameter thresholds for cosine scoring and library matching
- Uses only free, web-accessible tools (GNPS) and open-source visualization (Cytoscape)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
