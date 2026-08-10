# Skill: ChloroDBPFinder: Machine Learning-Guided Recognition of Chlorinated Disinfection Byproducts from Nontargeted LC-HRMS Analysis.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 92/100
- **source**: Zhao T et al., (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c05124, PMID: 38294426

## Analysis Goal
复现/对齐文献研究目标：ChloroDBPFinder: Machine Learning-Guided Recognition of Chlorinated Disinfection Byproducts from Nontargeted LC-HRMS Analysis.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Raw data conversion to mzML | MSConvert version 3.0.22035 | — | `not_reported` |
| 2 | Isotopic pattern simulation | enviPat R package | isopattern() | `error~U(0, 5) ppm, fluctuation~N(0, δ²), δ=11.8% for M+1, δ=15.8% for M+2,+3,+4` |
| 3 | Molecular formula assignment | MassTools R package | calcMF() | `not_reported` |
| 4 | Binary Cl-presence classification | randomForest R package version 4.3.0 | random forest | `n.tree=500, mtry=sqrt(n.features), six engineered features from M, M+1, M+2 peaks` |
| 5 | Multiclass Cl-count classification | randomForest R package version 4.3.0 | random forest | `n.tree=500, mtry=sqrt(n.features), eleven engineered features from M, M+1, M+2, M+3, M+4 peaks` |
| 6 | Feature extraction and isotope averaging | XCMS R package (embedded in ChloroDBPFinder) | chromatographic peak averaging | `not_reported` |
| 7 | False positive filtering | ChloroDBPFinder internal algorithms | salt adduct, natural isotope, and in-source fragment removal | `not_reported` |
| 8 | Spectral library search | ChloroDBPFinder internal function | dot product similarity | `MS/MS match number ≥4, dot product score ≥0.7` |
| 9 | Molecular networking (spectral similarity) | GNPS-based MS/MS similarity | cosine similarity | `cosine=0.7, minimum matched peaks=6, minimum cosine score=0.7` |
| 10 | Integrated molecular networking | ChloroDBPFinder internal implementation | combined spectral similarity + reaction connectivity | `not_reported` |
| 11 | Reaction networking | ChloroDBPFinder internal implementation | mass shift–based transformation inference | `not_reported` |
| 12 | Quantitative confidence assessment | custom R script (implied) | linear correlation across injection volumes | `seven injection volumes: 2, 4, 6, 10, 13, 16, 20 μL` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Hierarchical machine learning model generation: MF extraction → isotope simulation → binary classifier training → multiclass classifier training | not_reported | [4, 5] |
| Figure 4 | workflow_diagram | Schematic workflow of ChloroDBPFinder: (1) Cl-feature extraction, (2) alignment, (3) missing value imputation, (4) annotation via spectral library and molecular networking | not_reported | [6, 7, 8, 9, 10, 11] |
| Figure 5C | network | Integrated molecular networking between 11 reference compounds and 151 newly discovered Cl-containing features | not_reported | [9, 10] |
| Figure 6A | bar_chart | Histogram of correlation coefficients between signal intensity and injection volume for 79 Cl-containing features | not_reported | [12] |

## Parameter Highlights

- **Step 1 (MSConvert version 3.0.22035)**: `not_reported`
- **Step 2 (enviPat R package)**: `error~U(0, 5) ppm, fluctuation~N(0, δ²), δ=11.8% for M+1, δ=15.8% for M+2,+3,+4`
- **Step 3 (MassTools R package)**: `not_reported`
- **Step 4 (randomForest R package version 4.3.0)**: `n.tree=500, mtry=sqrt(n.features), six engineered features from M, M+1, M+2 peaks`
- **Step 5 (randomForest R package version 4.3.0)**: `n.tree=500, mtry=sqrt(n.features), eleven engineered features from M, M+1, M+2, M+3, M+4 peaks`
- **Step 6 (XCMS R package (embedded in ChloroDBPFinder))**: `not_reported`
- **Step 7 (ChloroDBPFinder internal algorithms)**: `not_reported`
- **Step 8 (ChloroDBPFinder internal function)**: `MS/MS match number ≥4, dot product score ≥0.7`
- **Step 9 (GNPS-based MS/MS similarity)**: `cosine=0.7, minimum matched peaks=6, minimum cosine score=0.7`
- **Step 10 (ChloroDBPFinder internal implementation)**: `not_reported`
- **Step 11 (ChloroDBPFinder internal implementation)**: `not_reported`
- **Step 12 (custom R script (implied))**: `seven injection volumes: 2, 4, 6, 10, 13, 16, 20 μL`

## Reproducibility Notes

- All key ML simulation parameters (error distribution, δ values) explicitly reported
- Injection volume series fully enumerated
- Spectral library match criteria (≥4 matches, ≥0.7 dot product) explicitly stated
- Public GitHub repository linked
- Cytoscape version specified for network visualization

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
