# Skill: mzLearn as a data-driven LC/MS signal detection algorithm that enables pre-trained generative models for untargeted metabolomics.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Pirhaji L et al. (2025), Communications chemistry, DOI: 10.1038/s42004-025-01791-w, PMID: 41413219

## Analysis Goal
复现/对齐文献研究目标：mzLearn as a data-driven LC/MS signal detection algorithm that enables pre-trained generative models for untargeted metabolomics.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Patch creation and noise filtering | mzLearn | Dynamic patching with autocorrelation-based noise filtering | `MZ_coarse=2 * mz_tol * MZ_max, RT_coarse=RT_max / 5, D_rt=mu_drt + 0.1 * sigma_drt, D_mz=mu_dmz + 0.1 * sigma_dmz, T_ac_initial=0.5, T_ac_final=5th percentile of per-peak autocorrelation among pins (after Stage-1 and Stage-2), autocorrelation_formula=AC(X) = (1/(M-2)) * sum_{i=1}^{M-1} ((u_{i-1} - mu_{-1})/sqrt(sigma_{-1})) * ((u_{i+1} - mu_{+1})/sqrt(sigma_{+1}))` |
| 2 | Cross-correlation-based patch alignment across samples | mzLearn | Cross-correlation with rt-displacement optimization and drift-aware weighting | `lb_d=-RT_max / 50, ub_d=RT_max / 50, rt_bin_size_delta=mu_drt / 10, T_cc_initial=0, T_cc_final=5th percentile of per-peak cross-correlation among pins (after Stage-1 and Stage-2), alignment_function=AL(X_p, X', d) = w_mu_d,sigma_d[d] * (F_delta(X_p) ⋆ F_delta(X'))[d], weight_function=w_mu_d,sigma_d[d] = 1 if \|d - mu_d\| <= 2*sigma_d, else decays to 0, cross_correlation_formula=XC_Xp(X'_p) = (1/M) * sum_n ((F_delta(X_p)[rt_min+n*delta] - mu_Xp)/sqrt(sigma_Xp)) * ((F_delta(X'_p)[rt_min+n*delta+d*] - mu_X'_p)/sqrt(sigma_X'_p))` |
| 3 | Retention time drift estimation and correction | mzLearn | Pin-based rt-drift mapping using high-confidence correlated patches | `pin_selection_criteria=patches present in most samples with above-average autocorrelation and cross-correlation scores, drift_map_update_frequency=updated at each stage (Stage-1, Stage-2, final), drift_uncertainty_handling=w_mu_d,sigma_d[d] incorporates sigma_d as rt-drift uncertainty` |
| 4 | Peak extraction from aligned patches | mzLearn | Peak detection within aligned correlated-patch groups | `peak_definition=subset of points in a patch with nearly identical m/z and bell-shaped intensity profile along rt axis` |
| 5 | Peak group refinement and re-alignment | mzLearn | Iterative refinement using updated parameters and drift map | `refinement_iterations=3, stages=['Stage-1 pin discovery', 'Stage-2 re-alignment', 'final refinement']` |
| 6 | Intensity drift correction and normalization | mzLearn | Intensity drift map estimation and feature-wise intensity normalization | `intensity_drift_correction=estimates and corrects instrument-level intensity drifts across large cohorts without QC samples` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (mzLearn)**: `MZ_coarse=2 * mz_tol * MZ_max, RT_coarse=RT_max / 5, D_rt=mu_drt + 0.1 * sigma_drt, D_mz=mu_dmz + 0.1 * sigma_dmz, T_ac_initial=0.5, T_ac_final=5th percentile of per-peak autocorrelation among pins (after Stage-1 and Stage-2), autocorrelation_formula=AC(X) = (1/(M-2)) * sum_{i=1}^{M-1} ((u_{i-1} - mu_{-1})/sqrt(sigma_{-1})) * ((u_{i+1} - mu_{+1})/sqrt(sigma_{+1}))`
- **Step 2 (mzLearn)**: `lb_d=-RT_max / 50, ub_d=RT_max / 50, rt_bin_size_delta=mu_drt / 10, T_cc_initial=0, T_cc_final=5th percentile of per-peak cross-correlation among pins (after Stage-1 and Stage-2), alignment_function=AL(X_p, X', d) = w_mu_d,sigma_d[d] * (F_delta(X_p) ⋆ F_delta(X'))[d], weight_function=w_mu_d,sigma_d[d] = 1 if |d - mu_d| <= 2*sigma_d, else decays to 0, cross_correlation_formula=XC_Xp(X'_p) = (1/M) * sum_n ((F_delta(X_p)[rt_min+n*delta] - mu_Xp)/sqrt(sigma_Xp)) * ((F_delta(X'_p)[rt_min+n*delta+d*] - mu_X'_p)/sqrt(sigma_X'_p))`
- **Step 3 (mzLearn)**: `pin_selection_criteria=patches present in most samples with above-average autocorrelation and cross-correlation scores, drift_map_update_frequency=updated at each stage (Stage-1, Stage-2, final), drift_uncertainty_handling=w_mu_d,sigma_d[d] incorporates sigma_d as rt-drift uncertainty`
- **Step 4 (mzLearn)**: `peak_definition=subset of points in a patch with nearly identical m/z and bell-shaped intensity profile along rt axis`
- **Step 5 (mzLearn)**: `refinement_iterations=3, stages=['Stage-1 pin discovery', 'Stage-2 re-alignment', 'final refinement']`
- **Step 6 (mzLearn)**: `intensity_drift_correction=estimates and corrects instrument-level intensity drifts across large cohorts without QC samples`

## Reproducibility Notes

- Full open-source implementation on GitHub with DOI
- All raw and processed data publicly available in MetaboLights and Zenodo
- No user-set parameters — fully automated workflow
- Detailed mathematical specification of all algorithms and thresholds
- Validation across 15 public datasets with benchmarking against XCMS and ASARI

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。
