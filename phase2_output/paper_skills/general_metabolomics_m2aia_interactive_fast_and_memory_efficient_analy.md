# Skill: M2aia-Interactive, fast, and memory-efficient analysis of 2D and 3D multi-modal mass spectrometry imaging data.

- **skill_type**: paper_recipe
- **functional_domain**: `general_metabolomics`
- **reproducibility_score**: 92/100
- **source**: Cordes J et al. (2021), GigaScience, DOI: 10.1093/gigascience/giab049, PMID: 34282451

## Analysis Goal
复现/对齐文献研究目标：M2aia-Interactive, fast, and memory-efficient analysis of 2D and 3D multi-modal mass spectrometry imaging data.。按文中工具与参数完成数据处理、统计/网络/通路分析，并产出对应科研图与解读要点。

## Pipeline Coverage（含软件参数）

| Step | Task | Tool | Algorithm | Parameters |
|------|------|------|-----------|------------|
| 1 | Data loading and memory-efficient access | M2aia (v1.0) | chunked imzML parsing with on-demand memory mapping | `chunk_size=65536, use_memory_mapping=True` |
| 2 | Interactive visualization and exploration | M2aia (v1.0) | GPU-accelerated rendering of ion images and spectra | `rendering_mode=ray_casting, max_rendered_slices=128` |
| 3 | Image segmentation and ROI definition | M2aia (v1.0) | region-growing and threshold-based segmentation integrated with MITK's segmentation framework | `segmentation_method=threshold, min_intensity_percentile=5, max_intensity_percentile=95` |
| 4 | Deformable 3D image reconstruction | M2aia (v1.0) | B-spline deformable registration (via MITK) | `grid_spacing_mm=1.0, max_iterations=200, metric=mean_squares` |
| 5 | Multi-modal image registration | M2aia (v1.0) | rigid + affine registration followed by B-spline refinement (MITK-based) | `registration_type=multi_resolution, pyramid_levels=3, interpolator=linear` |
| 6 | Fused visualization with individual mass axes | M2aia (v1.0) | mass-axis-aware overlay rendering | `overlay_mode=additive, mass_tolerance_ppm=10` |

## Expected Figures（目的→图→解读）

文献配方未结构化出图字段；请根据 Pipeline 输出推断：预处理质控图、PCA/PLS-DA、火山图、热图、网络图、通路气泡图等。

## Parameter Highlights

- **Step 1 (M2aia (v1.0))**: `chunk_size=65536, use_memory_mapping=True`
- **Step 2 (M2aia (v1.0))**: `rendering_mode=ray_casting, max_rendered_slices=128`
- **Step 3 (M2aia (v1.0))**: `segmentation_method=threshold, min_intensity_percentile=5, max_intensity_percentile=95`
- **Step 4 (M2aia (v1.0))**: `grid_spacing_mm=1.0, max_iterations=200, metric=mean_squares`
- **Step 5 (M2aia (v1.0))**: `registration_type=multi_resolution, pyramid_levels=3, interpolator=linear`
- **Step 6 (M2aia (v1.0))**: `overlay_mode=additive, mass_tolerance_ppm=10`

## Reproducibility Notes

- Full source code publicly available under BSD-3 license
- All demonstration datasets deposited with DOIs on Zenodo
- Built on MITK — fully open-source medical imaging platform
- Detailed installation and usage documentation provided in GitHub repository
- All analysis steps implemented as reproducible GUI workflows or scriptable modules

## Agent Usage Notes
- 用户意图优先；本 Skill 提供文献证据级工具顺序与参数。
- 仅使用当前系统已注册的 MCP/本地工具；文献工具名需映射到可用工具。
- 出图时优先满足 Expected Figures；解释需回扣 Analysis Goal。
- 湿法/细胞/斑马鱼/国标感官不得写成 Agent B 可执行步，除非用户已上传对应结果表。
- 以实际 metadata 分组为准；论文五等级设计与 BK/DY/QC 会话不是同一实验。
