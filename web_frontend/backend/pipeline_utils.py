"""Web 端流水线步骤可用性检测与任务裁剪。"""
from __future__ import annotations

from pathlib import Path

from web_frontend.backend.plan_utils import raw_conversion_needed
from web_frontend.backend.session_file_resolver import mzml_ready_for_xcms

DIFFERENTIAL_DEPENDENT_TOOLS = frozenset({
    "extract_differential_features",
    "spectral_annotation",
    "kegg_compound_enrichment",
})

# 可直接用 upload 下 .mgf 或 peaks/spectra.mgf，不依赖差异代谢物列表
MGF_STANDALONE_TOOLS = frozenset({
    "molecular_networking_gnps",
    "molecular_networking_fbmn",
    "molecular_networking_ms2lda",
    "molecular_networking_molnetenhancer",
    "deepmass_annotation",
    "library_match_cosine",
    "library_match_jaccard",
    "library_match_spectral_entropy",
    "library_match_spec2vec",
    "library_match_ms2deepscore",
    "library_match_blink",
    "library_match_msbert",
    "library_match_pair_from_mgf",
    "library_match_full_workflow",
})

MZML_DEPENDENT_TOOLS = frozenset({
    "data_preprocessing_xcms",
    "data_preprocessing_openms",
    "data_preprocessing_mzmine",
    "data_preprocessing_kpic",
    "data_preprocessing_pitracer",
    "data_preprocessing_tracmass",
    "data_preprocessing_peakonly",
    "mzmine_lcms_datapreprocess",
    "peak_detection_xcms_centwave",
    "peak_detection_openms_peakpickerhires",
    "peak_detection_openms_featurefinder",
    "peak_detection_kpic",
    "peak_detection_peakonly",
    "peak_detection_mzmine_gridmass",
    "peak_detection_mzmine_adap",
    "peak_picking_openms",
    "feature_detection_openms",
    "feature_filtering_and_missing_value_imputation_knn",
    "statistical_analysis_mixomics",
    *DIFFERENTIAL_DEPENDENT_TOOLS,
})

OPENMS_FEATUREXML_TOOLS = frozenset({
    "peak_group_alignment_openms",
    "group_peaks_openms_PeakGroup",
    "isotope_analysis_openms",
    "identify_isotopes_openms_IsotopeTools",
})

_RAW_CONVERTERS = frozenset({
    "convert_raw_to_mzml_msconvert",
    "convert_raw_to_mzml_ThermoRawFileParser",
    "convert_raw_to_mzml_OpenMS_FileConverter",
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
    """无可用 mzML（inputspace 与 outputspace 均无）且仍需 raw 转换时，阻止 XCMS 等步骤。"""
    if mzml_ready_for_xcms(paths, paths["upload"]):
        return False, ""
    if not raw_conversion_needed(paths):
        return False, ""
    return True, (
        "未在 inputspace 或 converted_mzml 中找到 mzML，且仍有未转换的 .raw。"
        "请先完成格式转换：Linux 可安装 ThermoRawFileParser，或启动 Docker 后使用 msconvert；"
        "也可直接上传 .mzML 到 inputspace。"
    )


def _has_featurexml(directory: str | Path) -> bool:
    root = Path(directory)
    if not root.is_dir():
        return False
    return bool(list(root.glob("*.featureXML")) + list(root.glob("*.featurexml")))


def openms_featurexml_blocked(paths: dict[str, str]) -> tuple[bool, str]:
    """无 OpenMS featureXML 时跳过对齐/分组；若已有 XCMS 产物则提示改用 XCMS 路径。"""
    out = Path(paths["outputspace"])
    candidates = [
        out / "openms_feature_detection_results",
        out / "data_preprocessing_openms_results",
        out / "feature_detection_openms_results",
    ]
    if any(_has_featurexml(d) for d in candidates):
        return False, ""
    # 任意 output 子目录若已有 featureXML 也不阻断
    if out.is_dir():
        for child in out.iterdir():
            if child.is_dir() and _has_featurexml(child):
                return False, ""
    xcms_table = Path(paths["peaks"]) / "feature_table.csv"
    if xcms_table.is_file():
        return True, (
            "未找到 OpenMS *.featureXML，且已有 XCMS 特征表。"
            "请跳过 peak_group_alignment_openms，继续使用 peak_detection_results "
            "做过滤/统计/FBMN。"
        )
    return True, (
        "未找到 OpenMS *.featureXML。"
        "请先运行 feature_detection_openms / data_preprocessing_openms，"
        "或改用默认 XCMS 预处理流程。"
    )


def conversion_environment_hint() -> str:
    from src.platform_utils import (
        docker_daemon_accessible,
        preferred_raw_converter,
        resolve_docker,
        resolve_thermo_rawfile_parser,
    )

    thermo = resolve_thermo_rawfile_parser()
    docker = resolve_docker()
    docker_ok = docker_daemon_accessible()
    pref = preferred_raw_converter()
    tool = str(pref.get("tool") or "")
    # Linux 优先 ThermoRawFileParser 时，不必用 Docker 警告刷屏
    if thermo and "ThermoRawFileParser" in tool:
        return f"将使用 ThermoRawFileParser（{thermo}）"
    lines = [str(pref.get("reason") or "")]
    if thermo:
        lines.append(f"ThermoRawFileParser: {thermo}")
    else:
        lines.append("ThermoRawFileParser: 未安装")
    if docker:
        if docker_ok:
            lines.append("Docker: daemon 可访问")
        else:
            lines.append(
                "Docker: 已安装但 daemon 不可访问（如需 msconvert：sudo systemctl start docker，"
                "或将当前用户加入 docker 组）"
            )
    else:
        lines.append("Docker: 未安装（msconvert 需要）")
    return " ".join(x for x in lines if x)


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
