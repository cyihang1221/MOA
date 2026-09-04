# Skill: Expanding the landscape of aging via orbitrap astral mass spectrometry and tandem mass tag integration.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Keele GR et al. (2025), Nature communications, DOI: 10.1038/s41467-025-60022-x, PMID: 40404760

## Analysis Goal
复现/对齐文献研究目标：Expanding the landscape of aging via orbitrap astral mass spectrometry and tandem mass tag integration.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data conversion | ReAdW.exe | modified version | `—` |
| 2 | Database search and PSM identification | COMET | linear discriminant analysis (LDA) for FDR control | `precursor_mass_tolerance_ppm=50, product_ion_tolerance_da=0.03, fdr_threshold=0.01, static_modifications=['TMTpro on lysine and N-terminus (+304.2071 Da)', 'carbamidomethylation of cysteine (+57.021 Da)'], variable_modifications=['oxidation of methionine (+15.995 Da)']` |
| 3 | PSM filtering based on resolution and S/N | custom filtering strategy | peptide-spectrum match-based filtering | `min_resolution_ms2=45000, min_total_signal_to_noise_across_channels=1440, reporter_ion_match_tolerance_da=0.001` |
| 4 | Protein inference and quantification | protein parsimony rules | protein-level summarization by summing reporter ion intensities | `quantification_method=sum of TMT reporter ion counts across retained PSMs, normalization_method=channel-wise S/N-sum normalization to equalize total signal per channel` |
| 5 | Statistical modeling for age/sex effects (per tissue) | R (base stats) | log-linear regression with F-tests | `model_age_continuous=log2(protein) ~ intercept + age_months + sex, model_age_categorical=log2(protein) ~ intercept + factor(age_group) + sex, model_interaction=log2(protein) ~ intercept + age + sex + age:sex, fdr_method=Benjamini-Hochberg, p_value_threshold_fdr=0.1, model_selection_criterion=BIC` |
| 6 | Cross-tissue joint modeling | R (base stats) | multi-tissue log-linear regression with interaction terms | `model_full=log2(protein) ~ intercept + age + sex + tissue + age:tissue + sex:tissue, fdr_method=Benjamini-Hochberg, p_value_threshold_fdr=0.1` |
| 7 | Principal component analysis | pcaMethods R package | PCA | `n_components=10, preprocessing=log2 transformation, no centering/scaling specified (implied by package defaults)` |
| 8 | Gene set enrichment analysis | clusterProfiler R package | GSEA (competitive enrichment) | `gene_set_definition=['age_coefficient > 0 & padj < 0.1', 'categorical age trends (e.g., Down-Flat)'], fdr_threshold_gsea=0.1, fdr_threshold_trends=0.01, identifier_mapping={'GO': 'ENSEMBL', 'KEGG': 'UniProt'}, background_gene_set=all analyzed proteins per tissue` |
| 9 | Re-analysis of external datasets | R (custom scripts) | consistent statistical modeling pipeline applied to external DDA (Takasugi et al.) and DIA (Wang et al.) data | `takasugi_processing=TMT 16-plex, Lumos, 4 age groups, male-only, non-continuous age modeling, wang_processing=DIA, 3 early-life age groups, both sexes, missingness filter (>80% missing → removed)` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | bar_chart | Demonstrates improved TMT quantification accuracy after applying peptide-level resolution and S/N filtering using Orbitrap Astral data. | none (descriptive comparison of CVs before/after filtering) | [3, 4] |
| Figure 2 | boxplot | Shows how resolution and S/N thresholds impact peptide-level vs. protein-level quantitation consistency and variance. | correlation analysis (Spearman) between peptide- and protein-level coefficients | [3, 4, 5] |
| Figure 3 | volcano_plot | Displays age- and sex-differential proteins in each tissue, alongside comparative results from Takasugi et al. (adult aging) and Wang et al. (development). | FDR-adjusted t-test / F-test p-values (padj < 0.1) | [5, 9] |
| Figure 4 | heatmap | Clusters proteins by distinct aging trajectories (e.g., Down-Flat, Up-Down) across brain tissues and kidney. | none (hierarchical clustering on fitted coefficients) | [5, 8] |
| Figure 5 | pca_scores | PCA plot showing sample separation by tissue, age, and sex across all 70 samples using 5778 shared proteins. | none (unsupervised visualization) | [7] |
| Figure 6 | pathway_map | Integrates adult aging and early development proteomes to highlight divergent synaptic protein trajectories. | GSEA FDR < 0.01 for developmental vs. aging gene sets | [8, 9] |

## Parameter Highlights

- **Step 2 (COMET)**: `precursor_mass_tolerance_ppm=50, product_ion_tolerance_da=0.03, fdr_threshold=0.01, static_modifications=['TMTpro on lysine and N-terminus (+304.2071 Da)', 'carbamidomethylation of cysteine (+57.021 Da)'], variable_modifications=['oxidation of methionine (+15.995 Da)']`
- **Step 3 (custom filtering strategy)**: `min_resolution_ms2=45000, min_total_signal_to_noise_across_channels=1440, reporter_ion_match_tolerance_da=0.001`
- **Step 4 (protein parsimony rules)**: `quantification_method=sum of TMT reporter ion counts across retained PSMs, normalization_method=channel-wise S/N-sum normalization to equalize total signal per channel`
- **Step 5 (R (base stats))**: `model_age_continuous=log2(protein) ~ intercept + age_months + sex, model_age_categorical=log2(protein) ~ intercept + factor(age_group) + sex, model_interaction=log2(protein) ~ intercept + age + sex + age:sex, fdr_method=Benjamini-Hochberg, p_value_threshold_fdr=0.1, model_selection_criterion=BIC`
- **Step 6 (R (base stats))**: `model_full=log2(protein) ~ intercept + age + sex + tissue + age:tissue + sex:tissue, fdr_method=Benjamini-Hochberg, p_value_threshold_fdr=0.1`
- **Step 7 (pcaMethods R package)**: `n_components=10, preprocessing=log2 transformation, no centering/scaling specified (implied by package defaults)`
- **Step 8 (clusterProfiler R package)**: `gene_set_definition=['age_coefficient > 0 & padj < 0.1', 'categorical age trends (e.g., Down-Flat)'], fdr_threshold_gsea=0.1, fdr_threshold_trends=0.01, identifier_mapping={'GO': 'ENSEMBL', 'KEGG': 'UniProt'}, background_gene_set=all analyzed proteins per tissue`
- **Step 9 (R (custom scripts))**: `takasugi_processing=TMT 16-plex, Lumos, 4 age groups, male-only, non-continuous age modeling, wang_processing=DIA, 3 early-life age groups, both sexes, missingness filter (>80% missing → removed)`

## Reproducibility Notes

- Raw data deposited in PRIDE (PXD048211)
- Processed data and metadata available on Zenodo (DOI: 10.5281/zenodo.10876543)
- Full analysis code publicly available on GitHub under MIT license
- All statistical models fully specified with equations and parameter thresholds
- External datasets re-analyzed using identical pipeline and made comparable

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。
