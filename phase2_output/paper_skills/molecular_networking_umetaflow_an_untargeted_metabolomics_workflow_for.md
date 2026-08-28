# Skill: UmetaFlow: an untargeted metabolomics workflow for high-throughput data processing and analysis.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 87/100
- **source**: Kontou EE et al. (2023), Journal of cheminformatics, DOI: 10.1186/s13321-023-00724-w, PMID: 37173725

## Analysis Goal
复现/对齐文献研究目标：UmetaFlow: an untargeted metabolomics workflow for high-throughput data processing and analysis.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data conversion and preprocessing | OpenMS | FileConverter, PeakPickerHiRes | `peak_width=0.1, signal_to_noise=3` |
| 2 | Feature detection and alignment | OpenMS | FeatureFinderMetabo | `mass_error_ppm=5, rt_tolerance=30, intensity_threshold=1000` |
| 3 | Retention time correction | OpenMS | MapAlignerIdentification | `reference_file=first_sample.mzML, method=lowess` |
| 4 | Gap filling | OpenMS | FeatureFinderMultiplex | `use_identifications=True, min_rt_intensity=100` |
| 5 | Molecular formula prediction | SIRIUS | CSI:FingerID + CANOPUS | `max_adducts=5, ppm_tolerance=10, isotope_count=3` |
| 6 | Structural annotation | SIRIUS | CSI:FingerID | `fingerprint_similarity_threshold=0.3` |
| 7 | Dereplication and spectral matching | GNPS | Feature-Based Molecular Networking (FBMN) | `cosine_score_threshold=0.7, min_matched_peaks=6, max_mz_diff=0.02` |
| 8 | Ion Identity Molecular Networking (IIMN) | GNPS | IIMN | `adduct_tolerance_ppm=5, ionization_mode=positive` |
| 9 | Statistical analysis and biomarker selection | MetaboAnalyst | ANOVA + FDR correction, PLS-DA, ROC analysis | `p_value_cutoff=0.05, fdr_method=BH, n_components=2, auc_threshold=0.8` |
| 10 | Pathway enrichment and biological interpretation | MetaboAnalyst | Hypergeometric test + topology analysis | `database=HMDB, organism=Homo sapiens` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (OpenMS)**: `peak_width=0.1, signal_to_noise=3`
- **Step 2 (OpenMS)**: `mass_error_ppm=5, rt_tolerance=30, intensity_threshold=1000`
- **Step 3 (OpenMS)**: `reference_file=first_sample.mzML, method=lowess`
- **Step 4 (OpenMS)**: `use_identifications=True, min_rt_intensity=100`
- **Step 5 (SIRIUS)**: `max_adducts=5, ppm_tolerance=10, isotope_count=3`
- **Step 6 (SIRIUS)**: `fingerprint_similarity_threshold=0.3`
- **Step 7 (GNPS)**: `cosine_score_threshold=0.7, min_matched_peaks=6, max_mz_diff=0.02`
- **Step 8 (GNPS)**: `adduct_tolerance_ppm=5, ionization_mode=positive`
- **Step 9 (MetaboAnalyst)**: `p_value_cutoff=0.05, fdr_method=BH, n_components=2, auc_threshold=0.8`
- **Step 10 (MetaboAnalyst)**: `database=HMDB, organism=Homo sapiens`

## Reproducibility Notes

- Full Snakemake workflow publicly available on GitHub with Zenodo DOI
- Uses only open-source or free web tools (OpenMS, SIRIUS, GNPS, MetaboAnalyst)
- Validated on two public MetaboLights datasets with accession IDs provided
- Jupyter notebooks and GUI support multiple user entry points and parameter exploration

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
