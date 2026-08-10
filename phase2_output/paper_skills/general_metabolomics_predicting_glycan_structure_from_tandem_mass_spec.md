# Skill: Predicting glycan structure from tandem mass spectrometry via deep learning.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Urban J et al. (2024), Nature methods, DOI: 10.1038/s41592-024-02314-6, PMID: 38951670

## Analysis Goal
复现/对齐文献研究目标：Predicting glycan structure from tandem mass spectrometry via deep learning.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data conversion to mzML | msconvert | ProteoWizard | `—` |
| 2 | MS/MS spectrum extraction | pymzML (v2.5.2) | custom script | `max_fragment_peaks=1000` |
| 3 | Spectrum filtering by glycan peak proximity | custom Python script (vCandyCrunch v.0.3.0) | m/z ±0.5 Da and RT ±2 min windowing | `mz_tolerance_da=0.5, rt_tolerance_min=2.0` |
| 4 | Data preprocessing for model input | CandyCrunch (custom) (vv.0.3.0) | intensity normalization + m/z binning + remainder encoding | `rt_min_threshold_min=2.0, rt_normalization_method=divide_by_max_or_30, intensity_normalization=divide_by_total_spectrum_intensity, mz_bin_count=2048, mz_min=39.714, mz_max=3000.0, remainder_encoding=True` |
| 5 | Model architecture execution | PyTorch (v2.1.0) | dilated residual 1D CNN with learned embeddings and domain-aware losses | `dilation_rates=[1, 2, 4, 8, 16, 32], conv_kernel_size=3, leaky_relu_negative_slope=0.2, max_pool_kernel_size=20, embedding_dims={'glycan_class': 24, 'ion_mode': 24, 'ion_trap': 24, 'lc_type': 24, 'modification': 24}, precursor_mz_embedding_dim=24, rt_embedding_dim=24, fc_dropout_rate=0.2, total_trainable_parameters=12375084` |
| 6 | Supervised + self-supervised training | PyTorch + ASAM + PolyLoss (vPyTorch v.2.1.0, ASAM v.1.x, PolyLoss v.1.x) | ASAM-regularized AdamW with structure/composition distance losses | `epochs=200, early_stopping_patience=12, batch_size=256, learning_rate=0.0001, lr_scheduler_factor=0.2, lr_scheduler_patience=4, weight_decay=2e-05, label_smoothing_epsilon=0.1, polyloss_epsilon=1.0, structure_distance_loss_weight=1.0, composition_distance_loss_weight=1.0, data_augmentation=['low_intensity_peak_removal', 'peak_jitter', 'new_peak_addition', 'adduct_simulation', 'precursor_mz_noise_±0.5Da', 'rt_noise_±10%']` |
| 7 | Inference and post-processing | CandyCrunch package (vv.0.3.0) | test-time augmentation + Platt scaling + biosynthetic confidence boosting + diagnostic ion filtering | `top_k_predictions=25, platt_scaling_factor=1.15, tta_inferences=5, min_prediction_probability=0.01, mass_tolerance_da=0.5, biosynthetic_window_masses=['M-1', 'M-2', 'M-n'], biosynthetic_confidence_boost=0.1, cross_class_threshold=0.2` |
| 8 | Retention time alignment across samples | CandyCrunch wrap_inference_batch (vv.0.3.0) | discontinuity-based m/z grouping + 0.5-min RT chunking + cross-sample RT alignment | `rt_chunk_width_min=0.5, mz_discontinuity_threshold_da=0.5` |
| 9 | Zero-shot biosynthetic network inference | glycowork (vv.1.1.0) | subgraph_isomorphism + evolutionary pruning (for milk oligosaccharides) | `mass_tolerance_da=0.5, network_pruning=evolutionary_if_available` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | Overview of the CandyCrunch deep learning pipeline for predicting glycan structure from LC-MS/MS data. | matplotlib, seaborn, or custom Python plotting | [1, 2, 3, 4, 5, 6, 7] |
| Fig. 2 | bar_chart | Identification of diagnostic fragment ions using CandyCrunch predictions and statistical enrichment analysis. | matplotlib, seaborn | [7, 9] |
| Fig. 3 | other | Molecular dynamics simulations revealing mechanistic basis of observed fragmentation patterns. | VMD or PyMOL | — |
| Fig. 4 | network | Biosynthetic networks derived from CandyCrunch predictions enabling biological interpretation. | NetworkX + matplotlib or Cytoscape | [9] |

## Parameter Highlights

- **Step 2 (pymzML (v2.5.2))**: `max_fragment_peaks=1000`
- **Step 3 (custom Python script (vCandyCrunch v.0.3.0))**: `mz_tolerance_da=0.5, rt_tolerance_min=2.0`
- **Step 4 (CandyCrunch (custom) (vv.0.3.0))**: `rt_min_threshold_min=2.0, rt_normalization_method=divide_by_max_or_30, intensity_normalization=divide_by_total_spectrum_intensity, mz_bin_count=2048, mz_min=39.714, mz_max=3000.0, remainder_encoding=True`
- **Step 5 (PyTorch (v2.1.0))**: `dilation_rates=[1, 2, 4, 8, 16, 32], conv_kernel_size=3, leaky_relu_negative_slope=0.2, max_pool_kernel_size=20, embedding_dims={'glycan_class': 24, 'ion_mode': 24, 'ion_trap': 24, 'lc_type': 24, 'modification': 24}, precursor_mz_embedding_dim=24, rt_embedding_dim=24, fc_dropout_rate=0.2, total_trainable_parameters=12375084`
- **Step 6 (PyTorch + ASAM + PolyLoss (vPyTorch v.2.1.0, ASAM v.1.x, PolyLoss v.1.x))**: `epochs=200, early_stopping_patience=12, batch_size=256, learning_rate=0.0001, lr_scheduler_factor=0.2, lr_scheduler_patience=4, weight_decay=2e-05, label_smoothing_epsilon=0.1, polyloss_epsilon=1.0, structure_distance_loss_weight=1.0, composition_distance_loss_weight=1.0, data_augmentation=['low_intensity_peak_removal', 'peak_jitter', 'new_peak_addition', 'adduct_simulation', 'precursor_mz_noise_±0.5Da', 'rt_noise_±10%']`
- **Step 7 (CandyCrunch package (vv.0.3.0))**: `top_k_predictions=25, platt_scaling_factor=1.15, tta_inferences=5, min_prediction_probability=0.01, mass_tolerance_da=0.5, biosynthetic_window_masses=['M-1', 'M-2', 'M-n'], biosynthetic_confidence_boost=0.1, cross_class_threshold=0.2`
- **Step 8 (CandyCrunch wrap_inference_batch (vv.0.3.0))**: `rt_chunk_width_min=0.5, mz_discontinuity_threshold_da=0.5`
- **Step 9 (glycowork (vv.1.1.0))**: `mass_tolerance_da=0.5, network_pruning=evolutionary_if_available`

## Reproducibility Notes

- Full dataset publicly available on Zenodo with DOI
- Entire workflow open-source on GitHub under MIT license
- Colab notebook provided for immediate testing
- All preprocessing, model architecture, training, and inference steps fully specified with hyperparameters
- Dependencies (pymzML, pyteomics, glycowork, PyTorch) versioned and cited

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
