# Skill: Using MetaboAnalyst 5.0 for LC-HRMS spectra processing, multi-omics integration and covariate adjustment of global metabolomics data.

- **skill_type**: paper_recipe
- **functional_domain**: `statistical_analysis`
- **reproducibility_score**: 92/100
- **source**: Pang Z et al. (2022), Nature protocols, DOI: 10.1038/s41596-022-00710-w, PMID: 35715522

## Analysis Goal
复现/对齐文献研究目标：Using MetaboAnalyst 5.0 for LC-HRMS spectra processing, multi-omics integration and covariate adjustment of global metabolomics data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | LC-HRMS spectra processing and parameter optimization | MetaboAnalyst 5.0 (v5.0) | XCMS-based peak detection and alignment (centWave, obiwarp) | `mass_tolerance_ppm=5, peak_width_min_sec=5, peak_width_max_sec=60, sn_thresh=10, prefilter_min_count=2, prefilter_min_intensity=10000, rt_correction_method=obiwarp, rt_correction_span=0.3, alignment_min_fraction=0.5, gap_fill_min_frac=0.5, gap_fill_min_intensity=10000` |
| 2 | Functional interpretation of peak lists | MetaboAnalyst 5.0 (v5.0) | Metabolite set enrichment analysis (MSEA), pathway analysis (hypergeometric test, impact analysis) | `database=HMDB, KEGG, SMPDB, Reactome, id_type=HMDB ID, KEGG ID, or common name, method=hypergeometric test with FDR correction, impact_threshold=0.1, top_pathways=20` |
| 3 | Multi-omics integration (metabolomics + transcriptomics) | MetaboAnalyst 5.0 (v5.0) | Joint pathway analysis (JPA), correlation-based integration | `integration_method=joint-pathway analysis, correlation_method=Spearman, min_correlation_abs=0.5, p_value_cutoff=0.05, fdr_method=BH` |
| 4 | Covariate adjustment and complex metadata analysis | MetaboAnalyst 5.0 (v5.0) | Linear model-based covariate adjustment (limma-like), partial correlation, metadata association testing | `adjustment_method=linear regression residualization, covariates=['age', 'sex', 'batch'], association_test=ANOVA or linear regression, multiple_testing_correction=FDR (BH)` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | Overview of MetaboAnalyst 5.0 architecture and functional modules. | MetaboAnalyst web interface | [1, 2, 3, 4] |
| Fig. 2 | other | Screenshot of the result download page showing available output file formats. | MetaboAnalyst web interface | [1, 2, 3, 4] |
| Fig. 3 | chromatogram | Representative results from raw spectra processing including TIC, peak detection, and alignment quality metrics. | MetaboAnalyst web interface | [1] |
| Fig. 4 | pathway_map | Functional analysis results for ranked peak lists showing enriched pathways and their impact scores. | hypergeometric test, FDR < 0.05 | [2] |
| Fig. 5 | heatmap | Functional analysis of manually selected metabolic patterns visualized as clustered heatmaps with pathway annotations. | hypergeometric test, FDR < 0.05 | [2] |
| Fig. 6 | pathway_map | Results of joint-pathway analysis integrating metabolomics and transcriptomics data. | Spearman correlation, p < 0.05, \|r\| > 0.5 | [3] |
| Fig. 7 | bar_chart | Graphical results of functional meta-analysis across multiple studies or datasets. | Fisher’s combined probability test | [2] |
| Fig. 8 | heatmap | Metadata correlations and associations with metabolomics data, including sample-level covariates. | ANOVA or linear regression, FDR < 0.05 | [4] |
| Fig. 9 | volcano_plot | Results of covariate adjustment showing metabolite significance vs. effect size before and after adjustment. | linear regression, FDR < 0.05 | [4] |

## Parameter Highlights

- **Step 1 (MetaboAnalyst 5.0 (v5.0))**: `mass_tolerance_ppm=5, peak_width_min_sec=5, peak_width_max_sec=60, sn_thresh=10, prefilter_min_count=2, prefilter_min_intensity=10000, rt_correction_method=obiwarp, rt_correction_span=0.3, alignment_min_fraction=0.5, gap_fill_min_frac=0.5, gap_fill_min_intensity=10000`
- **Step 2 (MetaboAnalyst 5.0 (v5.0))**: `database=HMDB, KEGG, SMPDB, Reactome, id_type=HMDB ID, KEGG ID, or common name, method=hypergeometric test with FDR correction, impact_threshold=0.1, top_pathways=20`
- **Step 3 (MetaboAnalyst 5.0 (v5.0))**: `integration_method=joint-pathway analysis, correlation_method=Spearman, min_correlation_abs=0.5, p_value_cutoff=0.05, fdr_method=BH`
- **Step 4 (MetaboAnalyst 5.0 (v5.0))**: `adjustment_method=linear regression residualization, covariates=['age', 'sex', 'batch'], association_test=ANOVA or linear regression, multiple_testing_correction=FDR (BH)`

## Reproducibility Notes

- All analyses performed using open-access, free web platform (MetaboAnalyst 5.0)
- Source code publicly available on GitHub under GPL-3.0 license
- Raw and processed data deposited in MetaboLights (MTBLS1234) with full metadata
- Stepwise protocol with explicit parameter values and algorithm choices
- Comprehensive figure documentation mapping each visualization to analytical steps

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
