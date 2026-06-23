"""Web 端 Agent 允许调用的 MCP 工具白名单（与 server.py 注册、前端展示一致）。"""

ALLOWED_TOOL_NAMES = frozenset({
    "convert_raw_to_mzml_msconvert",
    "convert_raw_to_mzml_ThermoRawFileParser",
    "data_preprocessing_xcms",
    "feature_filtering_and_missing_value_imputation_knn",
    "statistical_analysis_mixomics",
    "extract_differential_features",
    "spectral_annotation",
    "kegg_compound_enrichment",
    "molecular_networking_gnps",
    "deepmass_annotation",
})
