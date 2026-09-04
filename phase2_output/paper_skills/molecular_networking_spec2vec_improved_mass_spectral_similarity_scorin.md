# Skill: Spec2Vec: Improved mass spectral similarity scoring through learning of structural relationships

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 92/100
- **source**: Huber F et al. (2021), PLoS Computational Biology, DOI: 10.1371/journal.pcbi.1008724, PMID: 33591968

## Analysis Goal
复现/对齐文献研究目标：Spec2Vec: Improved mass spectral similarity scoring through learning of structural relationships。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw spectral data acquisition and curation | GNPS | — | `—` |
| 2 | Metadata cleaning and InChIKey annotation | matchms (v>=0.6.0) | InChIKey inference via PubChem lookup | `pubchempy_lookup=True` |
| 3 | Dataset filtering by ionization mode and spectral quality | custom Python script (matchms-based) | ion mode filtering + peak count thresholding | `ion_mode=positive, min_peaks_per_spectrum=10, mz_range_min=0, mz_range_max=1000` |
| 4 | Peak and neutral loss tokenization into spectrum documents | spec2vec (v0.3.2) | m/z binning + neutral loss derivation | `mz_decimal_precision=2, neutral_loss_range_min_da=5.0, neutral_loss_range_max_da=200.0, token_format_peak=peak@xxx.xx, token_format_loss=loss@xxx.xx` |
| 5 | Word2Vec model training for spectral embeddings | gensim | Continuous Bag of Words (CBOW) | `window_size=500, vector_size=100, min_count=1, epochs={'AllPositive': 15, 'UniqueInchiKeys': 50}, negative_sampling=5, cbow_mean=True, workers=0` |
| 6 | Spectrum vector generation via weighted sum of word embeddings | spec2vec (v0.3.2) | intensity-weighted vector summation | `intensity_normalization=to max = 1.0, missing_fraction_threshold=0.05` |
| 7 | Spec2Vec similarity scoring | spec2vec (v0.3.2) | cosine similarity between spectrum vectors | `—` |
| 8 | Cosine and modified cosine similarity computation | matchms (v>=0.6.0) | Watrous-modified cosine (precursor-shifted matching) | `intensity_threshold_relative=0.01, matching_method=one-to-one, precursor_shift_enabled=True` |
| 9 | Structural similarity calculation (Tanimoto) | RDKit (v2020.03.2) | Daylight-like Morgan fingerprints (2048 bits) | `fingerprint_radius=2, fingerprint_length=2048, tanimoto_metric=Jaccard` |
| 10 | Library matching evaluation | custom Python (pandas, numpy, numba) | top-k retrieval + rank-based performance metrics (e.g., recall@k) | `top_k=[1, 5, 10, 20], evaluation_metric=fraction of correct InChIKey matches in top-k` |
| 11 | Molecular networking and cluster quality assessment | custom Python (networkx, sklearn) | threshold-based spectral clustering + intra-cluster Tanimoto averaging | `similarity_threshold=0.5, cluster_quality_metric=mean_Tanimoto_within_cluster` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Illustrates conceptual analogy between MS/MS spectra as molecular signatures and limitations of cosine-based similarity for structural analogues. | Matplotlib | [1, 7, 8, 9] |
| Figure 2 | chromatogram | Illustrative comparison showing how Spec2Vec captures co-occurring peaks across training data to assign high similarity to structurally related molecules despite m/z shifts, unlike cosine scores. | Matplotlib | [4, 5, 7] |
| Figure 3 | histogram | Histogram of structural (Tanimoto) similarity scores across all spectrum pairs in the UniqueInchiKeys dataset. | Matplotlib | [9] |
| Figure 4 | other | Evaluation of library matching robustness after removing 1000 randomly selected spectra with duplicate InChIKeys. | Matplotlib | [10] |
| Figure 5 | other | Evaluation of molecular networking robustness after removing all spectra for 200 randomly selected InChIKeys (1030 spectra). | Matplotlib | [11] |
| Figure 6 | bar_chart | Cluster quality assessed by average intra-cluster Tanimoto similarity at varying Spec2Vec similarity thresholds, with threshold 0.5 highlighted. | Matplotlib | [11] |

## Parameter Highlights

- **Step 2 (matchms (v>=0.6.0))**: `pubchempy_lookup=True`
- **Step 3 (custom Python script (matchms-based))**: `ion_mode=positive, min_peaks_per_spectrum=10, mz_range_min=0, mz_range_max=1000`
- **Step 4 (spec2vec (v0.3.2))**: `mz_decimal_precision=2, neutral_loss_range_min_da=5.0, neutral_loss_range_max_da=200.0, token_format_peak=peak@xxx.xx, token_format_loss=loss@xxx.xx`
- **Step 5 (gensim)**: `window_size=500, vector_size=100, min_count=1, epochs={'AllPositive': 15, 'UniqueInchiKeys': 50}, negative_sampling=5, cbow_mean=True, workers=0`
- **Step 6 (spec2vec (v0.3.2))**: `intensity_normalization=to max = 1.0, missing_fraction_threshold=0.05`
- **Step 8 (matchms (v>=0.6.0))**: `intensity_threshold_relative=0.01, matching_method=one-to-one, precursor_shift_enabled=True`
- **Step 9 (RDKit (v2020.03.2))**: `fingerprint_radius=2, fingerprint_length=2048, tanimoto_metric=Jaccard`
- **Step 10 (custom Python (pandas, numpy, numba))**: `top_k=[1, 5, 10, 20], evaluation_metric=fraction of correct InChIKey matches in top-k`
- **Step 11 (custom Python (networkx, sklearn))**: `similarity_threshold=0.5, cluster_quality_metric=mean_Tanimoto_within_cluster`

## Reproducibility Notes

- Full workflow documented in executable Jupyter notebooks (github.com/iomega/spec2vec_gnps_data_analysis)
- All key datasets (raw, processed, models, similarity matrices) publicly archived on Zenodo with DOIs
- All software (matchms, spec2vec, RDKit, gensim) is open-source with version pins provided
- Parameterized peak filtering, tokenization, and model training clearly described with rationale

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。

## Available-tool mapping
- `gnps` → molecular_networking_gnps / molecular_networking_fbmn
