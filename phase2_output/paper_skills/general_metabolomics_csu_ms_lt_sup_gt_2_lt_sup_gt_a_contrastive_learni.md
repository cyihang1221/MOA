# Skill: CSU-MS&lt;sup&gt;2&lt;/sup&gt;: A Contrastive Learning Framework for Cross-Modal Compound Identification from MS/MS Spectra to Molecular Structures.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 88/100
- **source**: Xie T et al. (2025), Analytical chemistry, DOI: 10.1021/acs.analchem.5c01594, PMID: 40539908

## Analysis Goal
复现/对齐文献研究目标：CSU-MS&lt;sup&gt;2&lt;/sup&gt;: A Contrastive Learning Framework for Cross-Modal Compound Identification from MS/MS Spectra to Molecular Structures.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | In-silico MS/MS spectrum generation | CFM-ID | fragmentation prediction | `—` |
| 2 | In-silico MS/MS spectrum generation | ICEBERG | deep learning-based fragmentation prediction | `—` |
| 3 | Pretraining of cross-modal contrastive model | CSU-MS² (custom PyTorch framework) | cross-modal contrastive learning with External Space Attention Aggregation (ESA) | `embedding_dim=768, temperature=0.07, batch_size=256, learning_rate=0.0001, optimizer=AdamW, scheduler=cosine annealing` |
| 4 | Fine-tuning on experimental MS/MS data | CSU-MS² | supervised fine-tuning with contrastive loss | `learning_rate=5e-05, epochs=20, warmup_ratio=0.1` |
| 5 | Compound retrieval via cross-modal similarity search | CSU-MS² | cosine similarity search in unified embedding space | `top_k=10, similarity_threshold=None` |
| 6 | Database construction: Spectrum-searchable Structural Feature Database (SSFDB) | Custom pipeline | structural feature extraction + embedding indexing | `source_databases=23, feature_representation=ECFP4 + RDKit descriptors, indexing_method=FAISS` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 3 (CSU-MS² (custom PyTorch framework))**: `embedding_dim=768, temperature=0.07, batch_size=256, learning_rate=0.0001, optimizer=AdamW, scheduler=cosine annealing`
- **Step 4 (CSU-MS²)**: `learning_rate=5e-05, epochs=20, warmup_ratio=0.1`
- **Step 5 (CSU-MS²)**: `top_k=10, similarity_threshold=None`
- **Step 6 (Custom pipeline)**: `source_databases=23, feature_representation=ECFP4 + RDKit descriptors, indexing_method=FAISS`

## Reproducibility Notes

- Full source code publicly available under MIT license
- Pretrained models and SSFDB provided
- Web server deployed and openly accessible
- Validation performed on three well-known external benchmarks (MTBLS265, PMhub, CASMI 2022)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
