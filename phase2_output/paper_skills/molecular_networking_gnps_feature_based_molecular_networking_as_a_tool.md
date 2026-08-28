# Skill: GNPS Feature-Based Molecular Networking as a Tool to Visualize Metabolic Toxicity from Drug-Drug Interactions: A Case Study with Methamphetamine and Ethanol.

- **skill_type**: paper_recipe
- **functional_domain**: `molecular_networking`
- **reproducibility_score**: 87/100
- **source**: Kim M et al., (2026), Analytical chemistry, DOI: 10.1021/acs.analchem.5c06388, PMID: 41481198

## Analysis Goal
复现/对齐文献研究目标：GNPS Feature-Based Molecular Networking as a Tool to Visualize Metabolic Toxicity from Drug-Drug Interactions: A Case Study with Methamphetamine and Ethanol.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Multi-collision energy MS2 acquisition | Agilent LC-QTOF | — | `collision_energy=[10,20,40] eV` |
| 2 | Feature detection and alignment | GNPS FBMN platform | feature-based molecular networking | `ppm=5,cose=0.7,peakwidth=[10,60],snthresh=10` |
| 3 | Molecular network construction | GNPS FBMN | cosine similarity clustering | `cosine=0.7,min_matched_peaks=3,min_cosine=0.7` |
| 4 | Annotation propagation | GNPS FBMN + SIRIUS | spectral matching and in silico fragmentation | `matching_score_threshold=75%,in_silico_model=ICEBERGG,NIST-based` |
| 5 | Neutral loss filtering for conjugates | GNPS FBMN | neutral loss annotation | `neutral_loss=-176 Da` |
| 6 | Spectral similarity validation | mirror plot analysis | cosine similarity comparison | `cosine=0.86 (single-CE), cosine=0.93 (multi-CE),matched_peaks=3 vs 8` |
| 7 | Semi-quantitative abundance normalization | GNPS FBMN + custom processing | creatinine-normalized peak area | `normalization=creatinine` |
| 8 | Isomer differentiation | MS2 spectral pattern analysis + retention time | fragment ion pattern matching | `diagnostic_ions=[m/z 65,77,91,107,119,135,165,196]` |
| 9 | In-source fragment identification | GNPS FBMN + manual curation | mass defect and neutral loss analysis | `in_source_fragmentation=yes,neutral_loss=not_applicable` |
| 10 | Metabolic pathway mapping | custom visualization + GNPS network | biotransformation rule inference | `biotransformation_rules=[hydroxylation,+16 Da],[glucuronidation,-176 Da],[acetylation,+42 Da],[demethylation,-14 Da]` |
| 11 | Statistical prioritization of DDI features | manual inspection + fold-change threshold | semiquantitative differential analysis | `fold_change_threshold=\|1.2\|,significance=not_statistical` |
| 12 | Network topology comparison | GNPS FBMN | cluster count and node connectivity analysis | `cluster_count_single_CE=63,cluster_count_multi_CE=60,connected_nodes_single_CE=407,connected_nodes_multi_CE=423` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | network | CE optimization impact on spectral richness and network connectivity: comparison of single-CE vs merged multi-CE MS2 spectra and resulting FBMN parameters | not_reported | [1, 3, 12] |
| Figure 2 | network | FBMN visualization of MA-related metabolites in rat urine showing two major clusters (MA and glucuronides), node size = intensity, edge thickness = cosine similarity, red circles = \|FC\| > 1.2 | not_reported | [3, 7, 11] |
| Figure 3 | pathway_map | Proposed metabolic pathway of MA reshaped by ethanol co-administration, illustrating suppression of benzene ring hydroxylation, emergence of N-acetylAM, and formation of novel glucuronidated derivatives | not_reported | [10] |

## Parameter Highlights

- **Step 1 (Agilent LC-QTOF)**: `collision_energy=[10,20,40] eV`
- **Step 2 (GNPS FBMN platform)**: `ppm=5,cose=0.7,peakwidth=[10,60],snthresh=10`
- **Step 3 (GNPS FBMN)**: `cosine=0.7,min_matched_peaks=3,min_cosine=0.7`
- **Step 4 (GNPS FBMN + SIRIUS)**: `matching_score_threshold=75%,in_silico_model=ICEBERGG,NIST-based`
- **Step 5 (GNPS FBMN)**: `neutral_loss=-176 Da`
- **Step 6 (mirror plot analysis)**: `cosine=0.86 (single-CE), cosine=0.93 (multi-CE),matched_peaks=3 vs 8`
- **Step 7 (GNPS FBMN + custom processing)**: `normalization=creatinine`
- **Step 8 (MS2 spectral pattern analysis + retention time)**: `diagnostic_ions=[m/z 65,77,91,107,119,135,165,196]`
- **Step 9 (GNPS FBMN + manual curation)**: `in_source_fragmentation=yes,neutral_loss=not_applicable`
- **Step 10 (custom visualization + GNPS network)**: `biotransformation_rules=[hydroxylation,+16 Da],[glucuronidation,-176 Da],[acetylation,+42 Da],[demethylation,-14 Da]`
- **Step 11 (manual inspection + fold-change threshold)**: `fold_change_threshold=|1.2|,significance=not_statistical`
- **Step 12 (GNPS FBMN)**: `cluster_count_single_CE=63,cluster_count_multi_CE=60,connected_nodes_single_CE=407,connected_nodes_multi_CE=423`

## Reproducibility Notes

- explicit collision energies (10/20/40 eV)
- exact cosine thresholds (0.7, 0.86, 0.93)
- precise neutral loss (-176 Da)
- ppm error tolerances reported (e.g., -5.99 ppm for M0)
- public GNPS task URLs provided
- diagnostic fragment ions explicitly listed (m/z 65, 77, 91, etc.)

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
