# Skill: MS2DeepScore: a novel deep learning similarity measure to compare tandem mass spectra

- **skill_type**: paper_recipe
- **functional_domain**: `pathway_enrichment`
- **reproducibility_score**: 92/100
- **source**: Huber F et al. (2021), Journal of Cheminformatics, DOI: 10.1186/s13321-021-00558-4, PMID: 34715914

## Analysis Goal
复现/对齐文献研究目标：MS2DeepScore: a novel deep learning similarity measure to compare tandem mass spectra。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | MS/MS data acquisition and metadata cleaning | matchms (v0.8.2) | metadata standardization | `ion_mode=positive, min_peaks=5, mz_range_min=10.0, mz_range_max=1000.0, inchikey_length=14` |
| 2 | Compound annotation enrichment | pubchempy | PubChem API lookup | `—` |
| 3 | Spectral preprocessing and binning | matchms (v0.8.2) | intensity-based peak filtering and fixed-width binning | `intensity_threshold_percent=0.1, max_peaks=1000, intensity_transformation=square_root, mz_min=10.0, mz_max=1000.0, n_bins=10000, bins_used=9948` |
| 4 | Structural similarity labeling | RDKit | Tanimoto similarity on Daylight fingerprints (2048 bits) | `fingerprint_type=Daylight, n_bits=2048, similarity_metric=Tanimoto` |
| 5 | Dataset splitting | custom Python | stratified by InChIKey | `train_inchikeys=14062, validation_inchikeys=500, test_inchikeys=500, validation_spectra=3597, test_spectra=3601, random_seed=fixed` |
| 6 | Data generation with balanced sampling | MS2DeepScore DataGeneratorAllSpectrums | bin-stratified random pairing with adaptive bin widening | `n_bins=10, bin_widening_step=0.1, max_bin_widening=0.5` |
| 7 | Data augmentation | MS2DeepScore | stochastic spectral perturbation | `low_intensity_removal_percent_range=[0, 20], intensity_jitter_percent_range=[-40, 40], new_peak_addition_count_range=[0, 10], new_peak_intensity_range=[0, 0.01], intensity_threshold_for_removal=0.4` |
| 8 | Siamese neural network training | TensorFlow/Keras | Siamese network with cosine head | `base_network_architecture=['Dense(500)', 'Dense(500)', 'Dense(200)'], embedding_dim=200, optimizer=Adam, learning_rate=0.001, batch_size=32, loss_function=MSE, early_stopping_patience=5, l1_regularization=1e-06, l2_regularization=1e-06, dropout_rate=0.2, batch_normalization=True` |
| 9 | Monte-Carlo Dropout inference and uncertainty estimation | MS2DeepScore | MC-Dropout ensemble (N=10) | `mc_dropout_enabled_layers=['dense_2', 'dense_3'], n_samples=10, uncertainty_metric=interquartile_range` |
| 10 | Spectral embedding generation and visualization | scikit-learn | t-SNE | `n_components=2, metric=cosine, perplexity=100, learning_rate=200, n_iter=1000, random_state=None` |
| 11 | Performance evaluation (precision/recall) | custom Python | threshold sweep over similarity scores | `structural_similarity_threshold=0.6, score_threshold_range=[0, 0.99]` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Sketch of the Siamese neural network architecture and training strategy, showing binned spectrum input, base network embedding, cosine similarity head, and MSE loss against Tanimoto labels. | custom diagram (not specified) | [3, 4, 8] |
| Figure 2 | bar_chart | Distribution of MS2DeepScore predictions across Tanimoto score bins (<0.1 to >0.9), average RMSE per bin, and count of spectrum pairs per bin illustrating dataset imbalance. | matplotlib/seaborn (inferred) | [9, 11] |
| Figure 3 | histogram | Comparison of Tanimoto score distributions using different molecular fingerprints (morgan2, morgan3, RDKit-daylight) and similarity metrics, highlighting skewness and label imbalance. | matplotlib/seaborn (inferred) | [4] |
| Figure 4 | roc_curve | Precision-recall curves comparing MS2DeepScore, Spec2Vec, and modified Cosine for retrieving high structural similarity pairs (Tanimoto > 0.6) from test set. | matplotlib/seaborn (inferred) | [11] |
| Figure 5 | line_plot | Demonstration that aggregating multiple MS2DeepScore predictions per molecule pair improves Tanimoto prediction reliability. | matplotlib/seaborn (inferred) | [9] |
| Figure 6 | workflow_diagram | Illustration of Monte-Carlo Dropout execution mode: dropout layers remain active during inference to sample from stochastic network variants. | custom diagram (not specified) | [9] |
| Figure 7 | scatter_plot | Tradeoff between prediction uncertainty (IQR) and RMSE: discarding high-uncertainty predictions improves average performance. | matplotlib/seaborn (inferred) | [9] |
| Figure 8 | t_sne_plot | t-SNE visualization of 3601 test spectra colored by ClassyFire superclasses (A) and subclasses (B,C), using MS2DeepScore embeddings. | scikit-learn + matplotlib | [10] |

## Parameter Highlights

- **Step 1 (matchms (v0.8.2))**: `ion_mode=positive, min_peaks=5, mz_range_min=10.0, mz_range_max=1000.0, inchikey_length=14`
- **Step 3 (matchms (v0.8.2))**: `intensity_threshold_percent=0.1, max_peaks=1000, intensity_transformation=square_root, mz_min=10.0, mz_max=1000.0, n_bins=10000, bins_used=9948`
- **Step 4 (RDKit)**: `fingerprint_type=Daylight, n_bits=2048, similarity_metric=Tanimoto`
- **Step 5 (custom Python)**: `train_inchikeys=14062, validation_inchikeys=500, test_inchikeys=500, validation_spectra=3597, test_spectra=3601, random_seed=fixed`
- **Step 6 (MS2DeepScore DataGeneratorAllSpectrums)**: `n_bins=10, bin_widening_step=0.1, max_bin_widening=0.5`
- **Step 7 (MS2DeepScore)**: `low_intensity_removal_percent_range=[0, 20], intensity_jitter_percent_range=[-40, 40], new_peak_addition_count_range=[0, 10], new_peak_intensity_range=[0, 0.01], intensity_threshold_for_removal=0.4`
- **Step 8 (TensorFlow/Keras)**: `base_network_architecture=['Dense(500)', 'Dense(500)', 'Dense(200)'], embedding_dim=200, optimizer=Adam, learning_rate=0.001, batch_size=32, loss_function=MSE, early_stopping_patience=5, l1_regularization=1e-06, l2_regularization=1e-06, dropout_rate=0.2, batch_normalization=True`
- **Step 9 (MS2DeepScore)**: `mc_dropout_enabled_layers=['dense_2', 'dense_3'], n_samples=10, uncertainty_metric=interquartile_range`
- **Step 10 (scikit-learn)**: `n_components=2, metric=cosine, perplexity=100, learning_rate=200, n_iter=1000, random_state=None`
- **Step 11 (custom Python)**: `structural_similarity_threshold=0.6, score_threshold_range=[0, 0.99]`

## Reproducibility Notes

- Full cleaned dataset publicly available on Zenodo (DOI: 10.5281/zenodo.4699300)
- Source code open-source (MIT license) on GitHub with documented installation and usage
- All preprocessing steps, hyperparameters, and architectural details fully specified
- Fixed random seed used for validation set ensuring reproducible splits
- All software dependencies are open-source (matchms, RDKit, scikit-learn, TensorFlow)
- Monte-Carlo Dropout implementation and uncertainty quantification fully described

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。
