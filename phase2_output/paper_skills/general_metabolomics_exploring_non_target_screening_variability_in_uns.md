# Skill: Exploring non-target screening variability in unsupervised multivariate time trend analysis of LC-HRMS data.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 87/100
- **source**: Armin R et al. (2026), Analytical and bioanalytical chemistry, DOI: 10.1007/s00216-025-06225-z, PMID: 41284005

## Analysis Goal
复现/对齐文献研究目标：Exploring non-target screening variability in unsupervised multivariate time trend analysis of LC-HRMS data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Feature extraction | MarkerView v. 1.3.1, MZmine3 v. 3.2.8, PatRoon v.2.1.0 with OpenMS, Sirius, XCMS3 | — | `not_reported` |
| 2 | Near-zero variance filtering | caret R package | nearZeroVar | `freqCut=95/5, uniqueCut=8` |
| 3 | Data normalization | MATLAB R2022a | — | `IS-based normalization, log transformation, row-wise total abundance normalization` |
| 4 | Procrustes alignment | MEDA toolbox (GitHub: josecamachop/MEDA-Toolbox) | Procrustes analysis | `not_reported` |
| 5 | PCA | MEDA toolbox | — | `autoscaling applied, 10 PCs computed` |
| 6 | SPCA with Elastic Net regularization | SpaSM MATLAB toolbox (http://www2.imm.dtu.dk/projects/spasm/) | Zou's SPCA | `L1 sparsity=70–90%, L2 penalty=0.1–100, empirically tuned per dataset and compound` |
| 7 | Stratified bootstrapped SPCA (SBS-SPCA) | custom MATLAB script | stratified bootstrap (500 replicates) + SPCA | `stratification over 5-consecutive-time-point groups, L1/L2 grid search, selection frequency threshold=p<0.05` |
| 8 | Feature ranking | MATLAB R2022a | — | `ranking by absolute SPCA loading value` |

## Expected Figures（目的→图→解读）

| Figure | Type | Why / Caption | How to read / stats | Produced by |
|---------|------|---------------|---------------------|-------------|
| Figure 1 | line_plot | Reference intensity profiles for eight spiked targets in validation dataset I to assess trend detection | not_reported | [6] |
| Figure 2 | line_plot | Reference intensity profiles for nine compounds spiked into validation dataset II simulating real concentration fluctuations (spill types, episodic patterns) | not_reported | [6] |
| Figure 3 | scatter_plot | Procrustes analysis comparing each software-derived target matrix to the SCIEX OS reference | not_reported | [4] |
| Figure 4 | score_plot | SPCA score plots from XCMS-derived data for detecting spiked targets across seven PCs under L1=90% and L2=1 | not_reported | [6] |
| Figure 5 | heatmap | Comparative SPCA results for detecting spill III (sulfamethoxazole) across five software tools, including score profiles and top-ranked features under 90% sparsity | 99% control limits | [7, 8] |

## Parameter Highlights

- **Step 1 (MarkerView v. 1.3.1, MZmine3 v. 3.2.8, PatRoon v.2.1.0 with OpenMS, Sirius, XCMS3)**: `not_reported`
- **Step 2 (caret R package)**: `freqCut=95/5, uniqueCut=8`
- **Step 3 (MATLAB R2022a)**: `IS-based normalization, log transformation, row-wise total abundance normalization`
- **Step 4 (MEDA toolbox (GitHub: josecamachop/MEDA-Toolbox))**: `not_reported`
- **Step 5 (MEDA toolbox)**: `autoscaling applied, 10 PCs computed`
- **Step 6 (SpaSM MATLAB toolbox (http://www2.imm.dtu.dk/projects/spasm/))**: `L1 sparsity=70–90%, L2 penalty=0.1–100, empirically tuned per dataset and compound`
- **Step 7 (custom MATLAB script)**: `stratification over 5-consecutive-time-point groups, L1/L2 grid search, selection frequency threshold=p<0.05`
- **Step 8 (MATLAB R2022a)**: `ranking by absolute SPCA loading value`

## Reproducibility Notes

- Explicit caret nearZeroVar parameters (freqCut=95/5, uniqueCut=8)
- Full SPCA Elastic Net tuning grid (L1=70–90%, L2=0.1–100) with compound-specific optimization rationale
- Stratified bootstrap procedure fully described (500 replicates, 5-point strata, p<0.05 threshold)
- Public tool repositories cited (MEDA, SpaSM, GitHub links)
- Validation datasets with ground-truth temporal patterns explicitly defined

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
