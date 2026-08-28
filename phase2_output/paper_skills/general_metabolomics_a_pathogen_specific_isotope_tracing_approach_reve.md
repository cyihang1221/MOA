# Skill: A pathogen-specific isotope tracing approach reveals metabolic activities and fluxes of intracellular Salmonella.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 87/100
- **source**: Mitosch K et al. (2023), PLoS biology, DOI: 10.1371/journal.pbio.3002198, PMID: 37594988

## Analysis Goal
复现/对齐文献研究目标：A pathogen-specific isotope tracing approach reveals metabolic activities and fluxes of intracellular Salmonella.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Isotope tracing experiment design | custom experimental protocol | — | `substrate=U-13C-mannitol, incubation_time=4 hours, cell_types=['murine macrophages (J774A.1)', 'human epithelial cells (HeLa)'], pathogen=Salmonella enterica serovar Typhimurium, infection_multiplicity=MOI = 10` |
| 2 | Metabolite extraction | methanol/water/chloroform extraction | — | `solvent_ratio=40:40:20 (methanol:water:chloroform), quenching_temperature=-80°C, centrifugation=16,000 × g, 10 min, 4°C` |
| 3 | LC-MS data acquisition | Q-Exactive HF-X mass spectrometer | — | `chromatography=HILIC (SeQuant ZIC-pHILIC column), gradient=not fully specified (ammonium acetate/methanol mobile phase), ionization_mode=positive and negative ESI, mass_resolution=120,000 (at m/z 200), scan_range=m/z 70–1050, polarity_switching=enabled` |
| 4 | Data processing and isotopic enrichment quantification | TraceFinder (Thermo Fisher) | peak integration with isotope pattern matching | `mass_tolerance_ppm=5, retention_time_window_min=0.2, integration_method=baseline-to-baseline, correction_for_natural_abundance=enabled` |
| 5 | Metabolite identification | mzCloud, HMDB, METLIN, in-house standards | accurate mass + retention time + MS/MS spectral matching | `mass_accuracy_threshold_ppm=5, MS_MS_similarity_threshold=0.7, RT_deviation_threshold_min=0.3` |
| 6 | 13C-flux analysis and metabolic modeling | INCA (Isotopomer Network Compartmental Analysis) (v2.3.1) | isotopomer balancing + flux estimation via least-squares optimization | `model=Salmonella central carbon metabolism (glycolysis, TCA, PPP, EDP, anaplerotic reactions), constraints=['growth rate', 'carbon source uptake', 'redox cofactor balances'], fitting_method=weighted nonlinear least squares, confidence_interval_method=profile likelihood` |
| 7 | Statistical analysis and visualization | R (ggplot2, pheatmap, ComplexHeatmap) | two-tailed t-test, hierarchical clustering, PCA | `significance_threshold=0.05, multiple_testing_correction=Benjamini-Hochberg, clustering_distance=Euclidean, clustering_method=complete linkage` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Schematic of the mannitol-based 13C-tracing strategy to selectively label intracellular Salmonella metabolites. | Adobe Illustrator | [1, 2] |
| Figure 2 | bar_chart | Relative 13C-label incorporation into key central metabolites in intracellular Salmonella across cell types. | two-tailed t-test, p < 0.05 | [4, 5, 7] |
| Figure 3 | heatmap | Hierarchical clustering of isotopologue distributions across conditions reveals distinct metabolic states. | none (unsupervised) | [4, 7] |
| Figure 4 | pca_scores | PCA of isotopologue profiles separates infection conditions and highlights metabolic divergence. | none (unsupervised) | [4, 7] |
| Figure 5 | bar_chart | Estimated intracellular fluxes through central carbon pathways, emphasizing EDP and PEP carboxylase activity. | profile likelihood 95% confidence intervals shown | [6, 7] |
| Figure 6 | pathway_map | Integration of flux data onto a schematic metabolic map highlighting active routes during intracellular growth. | PathVisio / Adobe Illustrator | [6] |
| Figure S1 | chromatogram | Representative extracted ion chromatograms showing separation and detection of labeled metabolites. | TraceFinder | [3, 4] |

## Parameter Highlights

- **Step 1 (custom experimental protocol)**: `substrate=U-13C-mannitol, incubation_time=4 hours, cell_types=['murine macrophages (J774A.1)', 'human epithelial cells (HeLa)'], pathogen=Salmonella enterica serovar Typhimurium, infection_multiplicity=MOI = 10`
- **Step 2 (methanol/water/chloroform extraction)**: `solvent_ratio=40:40:20 (methanol:water:chloroform), quenching_temperature=-80°C, centrifugation=16,000 × g, 10 min, 4°C`
- **Step 3 (Q-Exactive HF-X mass spectrometer)**: `chromatography=HILIC (SeQuant ZIC-pHILIC column), gradient=not fully specified (ammonium acetate/methanol mobile phase), ionization_mode=positive and negative ESI, mass_resolution=120,000 (at m/z 200), scan_range=m/z 70–1050, polarity_switching=enabled`
- **Step 4 (TraceFinder (Thermo Fisher))**: `mass_tolerance_ppm=5, retention_time_window_min=0.2, integration_method=baseline-to-baseline, correction_for_natural_abundance=enabled`
- **Step 5 (mzCloud, HMDB, METLIN, in-house standards)**: `mass_accuracy_threshold_ppm=5, MS_MS_similarity_threshold=0.7, RT_deviation_threshold_min=0.3`
- **Step 6 (INCA (Isotopomer Network Compartmental Analysis) (v2.3.1))**: `model=Salmonella central carbon metabolism (glycolysis, TCA, PPP, EDP, anaplerotic reactions), constraints=['growth rate', 'carbon source uptake', 'redox cofactor balances'], fitting_method=weighted nonlinear least squares, confidence_interval_method=profile likelihood`
- **Step 7 (R (ggplot2, pheatmap, ComplexHeatmap))**: `significance_threshold=0.05, multiple_testing_correction=Benjamini-Hochberg, clustering_distance=Euclidean, clustering_method=complete linkage`

## Reproducibility Notes

- Raw and processed data publicly available in MassIVE and Zenodo with DOIs
- Full analysis code (R, INCA scripts, plotting) shared on GitHub under MIT license
- Comprehensive metadata including infection conditions, extraction protocols, and instrument parameters
- Use of community-standard tools (INCA, R, HILIC-LC-MS) enhances methodological transparency

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
