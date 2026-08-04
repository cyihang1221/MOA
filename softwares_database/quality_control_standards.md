# Metabolomics Pipeline — Quality Control Standards

This document defines quality control standards and normal metric ranges for each stage of the metabolomics analysis pipeline. The LLM quality inspector uses these standards to judge whether each step succeeded.

KEYWORD: quality control, QC, metrics, troubleshooting, quality standards, quality check, normal range, error detection

---

## Stage 1: Format Conversion

**Expected output:**
- .mzML files in the output directory, same number as input .raw files
- File sizes should be non-zero and similar to input sizes

**Quality checks:**
- Output file count = input file count
- Each output file > 0 bytes
- No "error" or "failed" in the tool return message
- Conversion time per file < 10 minutes (normal for ~500MB raw files)

**Common problems:**
- "msconvert not found" → msconvert not installed in the environment
- "wine error" → Docker not available for running ProteoWizard
- Zero-byte output → input file corrupted or incompatible format
- Partial conversion → check if --filter parameter is correct

---

## Stage 2: Data Preprocessing (XCMS / OpenMS)

**Expected output:**
- feature_table.csv: columns include feature_id, mz, rt_med, and per-sample intensity columns
- spectra.mgf: MS/MS spectra, each TITLE matches a feature_id
- Number of features typically: 500-5000 for LC-MS untargeted data (depends on sample complexity)
- Feature table file size: typically 50KB-5MB

**Quality checks:**
- feature_table.csv exists and has > 100 features (below 100 = likely failed peak detection)
- spectra.mgf exists and has > 10 spectra
- Feature table has expected columns: feature_id, mz, rt_med
- Sample columns in feature table match input sample count
- Intensity values are numeric and non-negative
- No all-NA columns in feature table

**Common problems:**
- Too few features (< 100) → peakwidth or snthresh too strict; try peakwidth=(3,60), snthresh=5
- Too many features (> 10000) → noise being detected; increase snthresh or prefilter
- All values in a sample column are 0 → sample has no data; check input mzML file
- MGF has no spectra → MS2 data missing from raw files or ms2_ppm/ms2_rt_window too narrow

---

## Stage 3: Redundant Feature Filtering

**Expected output:**
- Filtered feature table with reduced feature count
- Redundancy report showing how many features were merged
- Typical reduction: 20-50% of features are redundant (isotopes, adducts, fragments)

**Quality checks:**
- Output feature count < input feature count (must reduce)
- Reduction ratio between 10% and 70% (0% = filter did nothing, >70% = over-aggressive)
- Output file exists and is not empty

**Common problems:**
- Zero reduction → parameters too loose; lower correlation threshold or enable more filters
- >80% reduction → parameters too strict; only strongest correlations should be filtered
- All features assigned to same group → group size limit too large

---

## Stage 4: Missing Value Imputation (KNN)

**Expected output:**
- feature_table_filtered_imputed.csv: imputed feature table with no missing values
- Summary file with filtering statistics

**Quality checks:**
- Output table has no NA/NaN/null values
- Number of features retained >= 50% of input (if < 50%, min_presence may be too strict)
- Summary file shows reasonable filtering statistics
- Imputed values are within range of observed values for the same feature

**Common problems:**
- Too many features removed → increase min_presence (e.g., from 0.5 to 0.3)
- KNN fails → check if n_neighbors exceeds number of samples; reduce n_neighbors
- Imputed values are extreme → normalize data before imputation

---

## Stage 5: Statistical Analysis (mixOmics)

**Expected output:**
- differential_metabolites.csv: differential features with log2FC, pvalue, VIP
- PCA scores plot (pca_plot.png)
- PLS-DA scores plot (plsda_plot.png)
- Volcano plot data (volcano_results.csv)
- VIP scores for all features (vip_scores.csv)

**Quality checks:**
- PCA plot shows separation between groups (if groups are biologically different)
- PLS-DA cross-validation error rate < 0.5 (if > 0.5, groups may not be separable)
- Number of differential metabolites > 0 (if 0, thresholds may be too strict)
- VIP > 1 features exist (if none, PLS-DA model is not finding discriminative features)
- p-values follow expected distribution (not all near 0 or all near 1)

**Common problems:**
- No differential metabolites → increase pvalue_threshold or decrease log2fc_threshold
- PCA shows no group separation → biological difference may be subtle; consider alternative normalization
- PLS-DA overfitting (perfect separation but high CV error) → reduce ncomp_plsda
- Volcano plot asymmetric → data not properly normalized before statistical testing

---

## Stage 6a: Differential Feature Extraction

**Expected output:**
- differential_feature_table.csv: feature table filtered to differential features only
- differential_spectra.mgf: MGF containing only spectra of differential features

**Quality checks:**
- Output feature table row count matches differential metabolite count from Stage 5
- Output MGF has spectra count > 0
- Feature IDs in table match those in differential_metabolites.csv

---

## Stage 6b: Spectral Annotation

**Expected output:**
- differential_feature_table_library_match.csv: raw annotation matches
- differential_feature_table_library_match_clean&add.csv: cleaned annotations with compound names, SMILES, KEGG IDs

**Quality checks:**
- Annotation file has > 0 rows (if 0, no matches found in any library)
- Annotation rate typically 10-60% (depends on library coverage and data quality)
- cosine score distribution: most matches should have cosine > 0.7
- KEGG compound IDs present for pathway-annotatable compounds

**Common problems:**
- Zero annotations → check if spectra have sufficient fragment peaks; lower min_cosine to 0.5
- All annotations have low cosine (< 0.5) → spectral quality may be poor; check raw MS2 data
- No KEGG IDs → library may not contain KEGG mappings; use broader libraries

---

## Stage 7: Molecular Networking

**Expected output:**
- Network graph file (.graphml)
- network_edges.csv, network_nodes.csv
- network_summary.txt with statistics
- Molecular families/clusters detected

**Quality checks:**
- Network has > 0 edges (if 0, no spectral similarity found)
- Number of molecular families > 0
- Average nodes per family: ideally 2-10 (1 = no connections; 100 = one giant cluster)
- Cosine score distribution for edges: most should be 0.7-1.0
- Network density: typically sparse (< 5% of possible edges)

**Common problems:**
- No edges → lower min_cosine (e.g., 0.6) or min_matched_peaks (e.g., 3)
- Giant single cluster → top_k too high; reduce to 5 or lower
- All singleton nodes → spectra too dissimilar; consider if MS2 data quality is adequate

---

## Stage 8: KEGG Pathway Enrichment

**Expected output:**
- kegg_compound_enrich.csv: enrichment results
- Bubble plot, dotplot, barplot PNG files
- Significantly enriched pathways (p < 0.05)

**Quality checks:**
- Enrichment result has > 0 rows
- At least 1 pathway with p < 0.05 (if none, metabolic changes may be subtle)
- Enriched pathways are biologically relevant to the study context
- Plots are generated and non-empty

**Common problems:**
- Zero enriched pathways → too few KEGG IDs available; may need supplementary ID lookup
- All pathways are "Metabolic pathways" (too broad) → use more specific pathway database
- p-values all near 1 → no significant enrichment; consider less strict cutoff (p < 0.1)

---

## Global Pipeline Quality Summary

| Stage | Warning Threshold | Critical Threshold |
|-------|------------------|-------------------|
| Format Conversion | >20% files fail | >50% files fail |
| Preprocessing | <200 features | <50 features |
| Redundant Filtering | <10% reduction | 0% reduction or >80% |
| Imputation | <70% features retained | <30% features retained |
| Statistical Analysis | 0 differential metabolites | PCA shows no separation AND 0 differential |
| Spectral Annotation | <10% annotation rate | 0 annotations |
| Molecular Networking | 0 edges | 0 nodes in network |
| KEGG Enrichment | 0 significant pathways (p<0.05) | 0 pathways testable |
