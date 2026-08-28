# Skill: Predicting Ion Mobility Collision Cross-Sections Using a Deep Neural Network: DeepCCS.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 88/100
- **source**: Plante PL et al. (2019), Analytical chemistry, DOI: 10.1021/acs.analchem.8b05821, PMID: 30932474

## Analysis Goal
复现/对齐文献研究目标：Predicting Ion Mobility Collision Cross-Sections Using a Deep Neural Network: DeepCCS.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data collection and curation | Custom pipeline | Manual curation + standardization | `smiles_validation=True, ion_type_standardization=['[M+H]+', '[M-H]-', '[M+Na]+', '[M+K]+', '[M+NH4]+']` |
| 2 | Molecular featurization | RDKit | Extended-connectivity fingerprints (ECFP4) + physicochemical descriptors | `ecfp_radius=2, ecfp_length=2048, descriptors=['molecular_weight', 'logp', 'tpsa', 'heavy_atom_count', 'h_bond_donor_count', 'h_bond_acceptor_count', 'rotatable_bond_count']` |
| 3 | Deep neural network training | TensorFlow (v1.12.0) | Fully connected feedforward neural network | `hidden_layers=[1024, 512, 256, 128], dropout_rate=0.3, batch_size=64, epochs=200, learning_rate=0.001, loss_function=mean_absolute_error, optimizer=Adam` |
| 4 | Model evaluation | Scikit-learn | Coefficient of determination (R²), median relative error, mean absolute error | `r2_threshold=0.95, relative_error_metric=median_absolute_percentage_error` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (Custom pipeline)**: `smiles_validation=True, ion_type_standardization=['[M+H]+', '[M-H]-', '[M+Na]+', '[M+K]+', '[M+NH4]+']`
- **Step 2 (RDKit)**: `ecfp_radius=2, ecfp_length=2048, descriptors=['molecular_weight', 'logp', 'tpsa', 'heavy_atom_count', 'h_bond_donor_count', 'h_bond_acceptor_count', 'rotatable_bond_count']`
- **Step 3 (TensorFlow (v1.12.0))**: `hidden_layers=[1024, 512, 256, 128], dropout_rate=0.3, batch_size=64, epochs=200, learning_rate=0.001, loss_function=mean_absolute_error, optimizer=Adam`
- **Step 4 (Scikit-learn)**: `r2_threshold=0.95, relative_error_metric=median_absolute_percentage_error`

## Reproducibility Notes

- Full source code publicly available under MIT license
- Training and test data deposited in MetaboLights (MTBLS1524) and GitHub
- All molecular featurization and model hyperparameters explicitly reported
- Cross-laboratory dataset ensures generalizability

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
