"""Web 端流水线步骤可用性检测与任务裁剪。"""
from __future__ import annotations

from pathlib import Path

from web_frontend.backend.plan_utils import raw_conversion_needed

DIFFERENTIAL_DEPENDENT_TOOLS = frozenset({
    "extract_differential_features",
    "spectral_annotation",
    "kegg_compound_enrichment",
})

# 可直接用 upload 下 .mgf 或 peaks/spectra.mgf，不依赖差异代谢物列表
MGF_STANDALONE_TOOLS = frozenset({
    "molecular_networking_gnps",
    "deepmass_annotation",
})

MZML_DEPENDENT_TOOLS = frozenset({
    "data_preprocessing_xcms",
    "feature_filtering_and_missing_value_imputation_knn",
    "statistical_analysis_mixomics",
    *DIFFERENTIAL_DEPENDENT_TOOLS,
})

_RAW_CONVERTERS = frozenset({
    "convert_raw_to_mzml_msconvert",
    "convert_raw_to_mzml_ThermoRawFileParser",
})

_DIFF_CSV = "differential_metabolites.csv"
_WARNING = "analysis_warning.txt"


def differential_csv_path(paths: dict[str, str]) -> Path:
    return Path(paths["statistical"]) / _DIFF_CSV


def read_analysis_warning(paths: dict[str, str]) -> str:
    warning = Path(paths["statistical"]) / _WARNING
    if warning.is_file():
        return warning.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def differential_csv_has_rows(paths: dict[str, str]) -> bool:
    diff = differential_csv_path(paths)
    if not diff.is_file():
        return False
    lines = [line for line in diff.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    return len(lines) > 1


def differential_downstream_blocked(paths: dict[str, str]) -> tuple[bool, str]:
    """差异代谢物不可用（文件缺失或仅表头）时返回 (True, 原因)。"""
    if differential_csv_has_rows(paths):
        return False, ""
    warning = read_analysis_warning(paths)
    if warning:
        return True, warning
    diff = differential_csv_path(paths)
    if not diff.is_file():
        return True, f"未找到 {_DIFF_CSV}，无法进行差异物提取及后续注释/富集。"
    return True, "差异代谢物列表为空，跳过差异提取及后续注释/富集。"


def ensure_empty_differential_csv(output_dir: Path) -> Path | None:
    """
    PLS-DA/差异分析被跳过时写入仅含表头的 CSV，避免下游 FileNotFoundError。
    若已有非空差异表则不做改动。
    """
    diff = output_dir / _DIFF_CSV
    if diff.is_file():
        lines = [line for line in diff.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        if len(lines) > 1:
            return None
    warning = output_dir / _WARNING
    if not warning.is_file() and diff.is_file():
        return None
    diff.write_text(
        "Feature,mz,rt_med,VIP,log2FC,pvalue,padj\n",
        encoding="utf-8",
    )
    return diff


def prune_differential_dependent_tasks(tasks: list[str]) -> tuple[list[str], list[str]]:
    """从任务列表中移除依赖差异代谢物的步骤，返回 (保留, 移除)。"""
    kept: list[str] = []
    removed: list[str] = []
    for task in tasks:
        text = str(task)
        lower = text.lower()
        if any(name.lower() in lower for name in DIFFERENTIAL_DEPENDENT_TOOLS):
            removed.append(text)
        else:
            kept.append(text)
    return kept, removed


def conversion_downstream_blocked(paths: dict[str, str]) -> tuple[bool, str]:
    """存在 .raw 但 converted_mzml 未就绪时，后续 XCMS 等步骤不可执行。"""
    if not raw_conversion_needed(paths):
        return False, ""
    return True, (
        "converted_mzml 目录中没有与 .raw 对应的 mzML 文件。"
        "请先完成格式转换：Linux 可安装 ThermoRawFileParser，或启动 Docker 后使用 msconvert。"
    )


def conversion_environment_hint() -> str:
    from src.platform_utils import preferred_raw_converter, resolve_docker, resolve_thermo_rawfile_parser

    thermo = resolve_thermo_rawfile_parser()
    docker = resolve_docker()
    pref = preferred_raw_converter()
    lines = [str(pref.get("reason") or "")]
    if thermo:
        lines.append(f"ThermoRawFileParser: {thermo}")
    else:
        lines.append("ThermoRawFileParser: 未安装")
    if docker:
        lines.append("Docker: 已安装（需确保 daemon 已启动，如 sudo systemctl start docker）")
    else:
        lines.append("Docker: 未安装")
    return " ".join(lines)


def prune_mzml_dependent_tasks(tasks: list[str]) -> tuple[list[str], list[str]]:
    """移除依赖 mzML / XCMS 产物的步骤。"""
    kept: list[str] = []
    removed: list[str] = []
    for task in tasks:
        text = str(task)
        lower = text.lower()
        if any(name.lower() in lower for name in MZML_DEPENDENT_TOOLS):
            removed.append(text)
        elif any(name.lower() in lower for name in _RAW_CONVERTERS):
            removed.append(text)
        else:
            kept.append(text)
    return kept, removed
