# Skill: Sequence-to-sequence translation from mass spectra to peptides with a transformer model.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Yilmaz M et al. (2024), Nature communications, DOI: 10.1038/s41467-024-49731-x, PMID: 39080256

## Analysis Goal
复现/对齐文献研究目标：Sequence-to-sequence translation from mass spectra to peptides with a transformer model.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Spectrum preprocessing | Custom Python pipeline | Peak filtering and intensity transformation | `mz_range_min=50, mz_range_max=2500, precursor_exclusion_window_da=2, intensity_threshold_percent=1, max_peaks_retained=150, intensity_transformation=square_root, intensity_normalization=sum_normalization` |
| 2 | Input embedding generation | Custom PyTorch implementation | Sinusoidal m/z embedding + linear intensity embedding | `embedding_dimension=512, lambda_min=0.001, lambda_max=10000, d_sin=256, d_cos=256` |
| 3 | Precursor embedding | Custom PyTorch implementation | Sinusoidal m/z embedding + categorical charge embedding | `precursor_mz_embedding=sinusoidal, charge_embedding_dim=16, max_charge_state=10` |
| 4 | Transformer-based sequence-to-sequence modeling | PyTorch + custom transformer | Encoder-decoder transformer (Vaswani et al.) | `num_layers=9, embedding_size=512, num_attention_heads=8, total_parameters=47000000, vocabulary_size=28, max_peptide_length=100, stop_token_id=27` |
| 5 | Training with teacher forcing | PyTorch | Cross-entropy loss minimization | `batch_size=32, weight_decay=1e-05, peak_learning_rate=0.0005, warmup_steps=100000, learning_rate_schedule=linear warmup + cosine decay, training_epochs=1, validation_frequency_iterations=50000` |
| 6 | Fine-tuning for non-enzymatic peptides | PyTorch | Transfer learning with reduced learning rate | `fine_tuning_learning_rate=5e-05, fine_tuning_epochs=5, validation_selection_criterion=minimum validation loss` |
| 7 | Inference with beam search | Custom PyTorch inference | Autoregressive beam search decoding | `beam_width=user-specified k, termination_conditions=['stop_token', 'mass_tolerance_match', 'max_length_reached'], precursor_mass_tolerance_ppm=inference-time parameter ϵ, isotope_offset_handling=optional` |
| 8 | Precursor mass filter | Custom post-processing | ppm mass error thresholding | `mass_error_ppm_threshold=ϵ (dataset-specific, e.g., instrument-dependent)` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Fig. 1 | workflow_diagram | Schematic illustration of Casanovo’s transformer architecture for de novo peptide sequencing from tandem mass spectra. | Adobe Illustrator / Inkscape | [1, 2, 3, 4] |
| Fig. 2 | bar_chart | Casanovo achieves higher de novo sequencing accuracy than PointNovo, DeepNovo, and Novor on the nine-species benchmark dataset. | Wilcoxon signed-rank test (p < 0.001) | [7, 8] |
| Fig. 3 | boxplot | Fine-tuned Casanovo shows reduced bias toward tryptic cleavage patterns compared to the base model. | Kolmogorov–Smirnov test (p < 0.01) | [6, 7, 8] |
| Fig. 4 | volcano_plot | Casanovo enables detection of more unique peptides in metaproteomics samples compared to database-search methods. | Fisher’s exact test (FDR-adjusted p < 0.05) | [7, 8] |

## Parameter Highlights

- **Step 1 (Custom Python pipeline)**: `mz_range_min=50, mz_range_max=2500, precursor_exclusion_window_da=2, intensity_threshold_percent=1, max_peaks_retained=150, intensity_transformation=square_root, intensity_normalization=sum_normalization`
- **Step 2 (Custom PyTorch implementation)**: `embedding_dimension=512, lambda_min=0.001, lambda_max=10000, d_sin=256, d_cos=256`
- **Step 3 (Custom PyTorch implementation)**: `precursor_mz_embedding=sinusoidal, charge_embedding_dim=16, max_charge_state=10`
- **Step 4 (PyTorch + custom transformer)**: `num_layers=9, embedding_size=512, num_attention_heads=8, total_parameters=47000000, vocabulary_size=28, max_peptide_length=100, stop_token_id=27`
- **Step 5 (PyTorch)**: `batch_size=32, weight_decay=1e-05, peak_learning_rate=0.0005, warmup_steps=100000, learning_rate_schedule=linear warmup + cosine decay, training_epochs=1, validation_frequency_iterations=50000`
- **Step 6 (PyTorch)**: `fine_tuning_learning_rate=5e-05, fine_tuning_epochs=5, validation_selection_criterion=minimum validation loss`
- **Step 7 (Custom PyTorch inference)**: `beam_width=user-specified k, termination_conditions=['stop_token', 'mass_tolerance_match', 'max_length_reached'], precursor_mass_tolerance_ppm=inference-time parameter ϵ, isotope_offset_handling=optional`
- **Step 8 (Custom post-processing)**: `mass_error_ppm_threshold=ϵ (dataset-specific, e.g., instrument-dependent)`

## Reproducibility Notes

- Full source code publicly available under MIT license
- All training and benchmark datasets openly accessible (MassIVE, Zenodo)
- Complete hyperparameter specification including learning rate schedule, architecture dimensions, and preprocessing logic
- Reproducible inference protocol with explicit beam search and mass filtering rules
- Pre-trained models and fine-tuned variants provided

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
