# Skill: Sharing and community curation of mass spectrometry data with Global Natural Products Social Molecular Networking

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 92/100
- **source**: Wang M et al. (2016), Nature Biotechnology, DOI: 10.1038/nbt.3597, PMID: 27504778

## Analysis Goal
复现/对齐文献研究目标：Sharing and community curation of mass spectrometry data with Global Natural Products Social Molecular Networking。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | MS/MS data upload and storage | GNPS platform | — | `—` |
| 2 | Molecular networking via spectral similarity | Cytoscape + GNPS backend (based on Cosine score) | Cosine correlation | `min_cosine_score=0.7, min_matched_peaks=6, fragment_mz_tolerance=0.5, precursor_mz_tolerance=0.5` |
| 3 | Spectral library matching | GNPS spectral library search | dot-product similarity (modified cosine) | `min_similarity_score=0.3, min_matched_peaks=3, max_precursor_mass_diff=2.0, library_matching_mode=best_match_only` |
| 4 | Crowdsourced curation and annotation | GNPS community annotation interface | manual and consensus-based annotation | `—` |
| 5 | Reanalysis of deposited data ('living data') | GNPS automated reprocessing pipeline | re-clustering and re-matching against updated libraries | `reanalysis_frequency=quarterly, trigger_conditions=['new library additions', 'user request']` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | workflow_diagram | Overview of the GNPS platform architecture, including data upload, molecular networking, spectral library matching, and community curation. | Custom web interface + Cytoscape | [1, 2, 3, 4] |
| Figure 2 | bar_chart | Statistics on GNPS spectral libraries, including number of spectra, compounds, and contributing labs. | D3.js / custom GNPS dashboard | [3, 4] |
| Figure 3 | network | Example molecular network visualized in Cytoscape, showing clusters of related natural products based on MS/MS spectral similarity. | Cytoscape | [2] |
| Figure 4 | workflow_diagram | Illustration of 'living data' concept: iterative reannotation of spectra through community voting and library updates. | Custom web interface | [4, 5] |
| Figure 5 | network | GNPS-enabled discovery of stenothricin, showing its molecular network cluster and structural elucidation pathway. | Cytoscape + ChemDraw integration | [2, 3, 4] |

## Parameter Highlights

- **Step 2 (Cytoscape + GNPS backend (based on Cosine score))**: `min_cosine_score=0.7, min_matched_peaks=6, fragment_mz_tolerance=0.5, precursor_mz_tolerance=0.5`
- **Step 3 (GNPS spectral library search)**: `min_similarity_score=0.3, min_matched_peaks=3, max_precursor_mass_diff=2.0, library_matching_mode=best_match_only`
- **Step 5 (GNPS automated reprocessing pipeline)**: `reanalysis_frequency=quarterly, trigger_conditions=['new library additions', 'user request']`

## Reproducibility Notes

- Fully open-source platform with public GitHub repository
- All source code and workflows publicly available (Supplementary Source Code ZIP)
- Raw and processed data publicly accessible via GNPS web interface
- Standardized parameters for cosine scoring and library matching explicitly reported
- Apache-2.0 licensed software

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。

## Available-tool mapping
- `gnps` → molecular_networking_gnps / molecular_networking_fbmn
