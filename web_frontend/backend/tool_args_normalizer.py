"""将 LLM 生成的工具参数名/路径规范为 MCP 工具 schema（input_dir / output_dir 等）。"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Optional

from src.platform_utils import normalize_display_path
from web_frontend.backend.session_file_resolver import (
    ensure_mzml_input_dir,
    find_differential_csv,
    find_first_file,
    find_session_mgf,
    resolve_dir_with_file,
    session_search_roots,
)


def _pick_str(args: dict, *keys: str) -> Optional[str]:
    for key in keys:
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().strip('"')
    return None


def _path_obj(value: str) -> Path:
    return Path(value.replace("\\", os.sep))


def _dir_of(value: str) -> str:
    p = _path_obj(value)
    return normalize_display_path(p.parent if p.suffix else p)


def _ensure_dir(path: str) -> str:
    p = _path_obj(path)
    p.mkdir(parents=True, exist_ok=True)
    return normalize_display_path(p)


def _first_existing(*candidates: str) -> Optional[str]:
    for c in candidates:
        if c and _path_obj(c).is_file():
            return normalize_display_path(c)
    return None


def _dir_has_raw_files(path: str) -> bool:
    p = _path_obj(path)
    if not p.is_dir():
        return False
    return bool(list(p.glob("*.raw")) + list(p.glob("*.RAW")))


def _use_existing_dir(
    candidate: Optional[str],
    fallback: str,
    *,
    require_raw: bool = False,
) -> str:
    """LLM 可能返回已重命名前的旧 slug 路径；不存在或无 .raw 时回退到 canonical。"""
    if candidate:
        p = _path_obj(candidate)
        if p.is_dir() and (not require_raw or _dir_has_raw_files(candidate)):
            return normalize_display_path(p)
    return normalize_display_path(fallback)


from web_frontend.backend.session_metadata import (
    ensure_aligned_metadata_csv,
    ensure_metadata_from_inputs,
    resolve_metadata_csv,
    sample_ids_from_feature_table,
)


def _metadata_path(upload_dir: str) -> str:
    try:
        return resolve_metadata_csv(upload_dir)
    except FileNotFoundError:
        meta = _path_obj(upload_dir) / "metadata.csv"
        return normalize_display_path(meta)


def _aligned_metadata_for_feature_dir(upload_dir: str, feature_dir: str) -> str:
    """按特征表样本自动对齐 metadata；无 metadata 时从样本名推断分组。"""
    table = _path_obj(feature_dir) / "feature_table_filtered_imputed.csv"
    if not table.is_file():
        table = _path_obj(feature_dir) / "feature_table.csv"
    samples = sample_ids_from_feature_table(table) if table.is_file() else []
    if not samples:
        return _metadata_path(upload_dir)
    meta, _report = ensure_metadata_from_inputs(upload_dir, sample_ids=samples)
    return meta


def _resolve_fbmn_feature_table(
    args: dict,
    paths: dict[str, str],
    search_roots: list[str],
) -> str:
    """FBMN 特征表：优先差异表 → 过滤表 → XCMS 峰表 → OpenMS 对齐表。"""
    picked = _pick_str(
        args,
        "input_feature_table",
        "feature_table",
        "input_csv",
    )
    if picked and _path_obj(picked).is_file():
        return normalize_display_path(picked)

    peaks = paths["peaks"]
    filtered = paths.get("filtered") or str(_path_obj(paths["outputspace"]) / "filtered_features")
    differential = paths.get("differential") or str(
        _path_obj(paths["outputspace"]) / "differential_features"
    )
    openms_aligned = str(_path_obj(paths["outputspace"]) / "openms_aligned_features")
    candidates = [
        str(_path_obj(differential) / "differential_feature_table.csv"),
        str(_path_obj(filtered) / "feature_table_filtered_imputed.csv"),
        str(_path_obj(peaks) / "feature_table.csv"),
        str(_path_obj(openms_aligned) / "feature_table.csv"),
    ]
    found = _first_existing(*candidates)
    if found:
        return found
    # 会话内兜底搜索
    for root in search_roots:
        hit = find_first_file(
            str(_path_obj(root) / "feature_table.csv"),
            search_roots=[root],
            patterns=(
                "differential_feature_table.csv",
                "feature_table_filtered_imputed.csv",
                "feature_table.csv",
            ),
        )
        if hit:
            return hit
    raise FileNotFoundError(
        "无法执行 FBMN：缺少特征定量表。"
        " 请先完成 XCMS/过滤（peak_detection_results/feature_table.csv），"
        "或提供 differential_feature_table.csv。"
        " 不要依赖尚未生成的 openms_aligned_features/。"
    )


def _dir_has_featurexml(path: str) -> bool:
    p = _path_obj(path)
    if not p.is_dir():
        return False
    return bool(list(p.glob("*.featureXML")) + list(p.glob("*.featurexml")))


def _dir_has_mzml(path: str) -> bool:
    p = _path_obj(path)
    if not p.is_dir():
        return False
    return bool(list(p.glob("*.mzML")) + list(p.glob("*.mzml")))


def _count_mgf_spectra(path: str) -> int:
    """快速统计 MGF 中 BEGIN IONS 数量；文件不存在返回 0。"""
    p = _path_obj(path)
    if not p.is_file():
        return 0
    count = 0
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith("BEGIN IONS"):
                    count += 1
    except OSError:
        return 0
    return count


def _resolve_networking_mgf(
    args: dict,
    paths: dict[str, str],
    upload_dir: str,
    *,
    prefer_feature_corpus: bool = False,
) -> str:
    """
    选择分子网络用的 MGF。

    - GNPS / FBMN：优先用户指定 → 差异谱 → XCMS 特征谱
    - MS2LDA（Mass2Motif 发现）：优先 XCMS 特征对齐全量谱
      peak_detection_results/spectra.mgf（语料发现需要足够谱图；
      不要用仅含数条差异代谢物的 differential_spectra.mgf，
      也不要用未对齐的逐文件原始 MS2 dump）
    """
    peaks = paths["peaks"]
    differential = paths.get("differential") or str(
        _path_obj(paths["outputspace"]) / "differential_features"
    )
    upload_root = _path_obj(upload_dir)

    picked = _pick_str(args, "input_mgf", "input_msp", "mgf", "spectra_mgf")
    feature_mgf = str(_path_obj(peaks) / "spectra.mgf")
    diff_mgf = str(_path_obj(differential) / "differential_spectra.mgf")
    upload_mgf = str(upload_root / "spectra.mgf")

    if prefer_feature_corpus:
        # Motif 发现：特征级全量语料优先于用户误传的 differential_spectra.mgf
        candidates = [feature_mgf, upload_mgf, picked, diff_mgf]
    else:
        candidates = [picked, diff_mgf, feature_mgf, upload_mgf]

    for c in candidates:
        if c and _path_obj(c).is_file():
            return normalize_display_path(c)

    fallback = find_session_mgf(paths, upload_dir)
    if fallback and _path_obj(fallback).is_file():
        return normalize_display_path(fallback)
    raise FileNotFoundError(
        "无法执行分子网络：缺少 differential_spectra.mgf 或 spectra.mgf。"
        " 请先完成差异物提取、峰检测 MS2 导出，或直接上传 .mgf。"
    )

def _resolve_spectral_annotation_dir(
    args: dict,
    differential: str,
    search_roots: list,
) -> str:
    """spectral_annotation 必须使用含 differential_spectra.mgf + feature table 的目录。"""
    required = ("differential_spectra.mgf", "differential_feature_table.csv")

    def _ok(directory: str) -> bool:
        root = _path_obj(directory)
        return all((root / name).is_file() for name in required)

    inp = _pick_str(args, "input_dir", "input_msp", "input_path")
    candidates: list[str] = []
    if inp:
        p = _path_obj(inp)
        candidates.append(normalize_display_path(p.parent if p.suffix else p))
    candidates.append(differential)
    resolved = resolve_dir_with_file(
        differential,
        "differential_spectra.mgf",
        differential,
        search_roots=search_roots,
    )
    if resolved:
        candidates.append(resolved)

    for c in candidates:
        if c and _ok(c):
            return normalize_display_path(_path_obj(c))

    raise FileNotFoundError(
        "spectral_annotation 需要目录内同时存在 "
        "differential_spectra.mgf 与 differential_feature_table.csv。"
        f" 请先运行 extract_differential_features（输出通常在 {differential}）。"
        " 不要把 peak_detection_results 当作 annotation 输入目录。"
    )


def format_mcp_tool_result(result: Any) -> str:
    """从 MCP CallToolResult 提取可读文本。"""
    if result is None:
        return ""
    content = getattr(result, "content", None)
    if content:
        lines = []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                lines.append(str(text).strip())
        if lines:
            return "\n".join(lines)
    is_error = getattr(result, "isError", False)
    if is_error:
        return f"工具返回错误：{result}"
    return str(result)


def is_mcp_tool_result_error(result: Any, result_str: str) -> bool:
    """MCP 有时把异常写进文本但仍标记为成功，需额外识别。"""
    if getattr(result, "isError", False):
        return True
    text = (result_str or "").strip()
    if not text:
        return False
    lower = text.lower()
    markers = (
        "error executing tool",
        "numpy.core.multiarray failed to import",
        "traceback (most recent call last)",
        "modulenotfounderror",
        "importerror",
        "runtimeerror",
        "工具返回错误",
    )
    return any(m in lower for m in markers)


def _find_session_mgf(upload_dir: str, paths: dict[str, str] | None = None) -> str | None:
    """会话 input/output 目录下任意 .mgf（含用户上传的自定义文件名）。"""
    if paths is not None:
        return find_session_mgf(paths, upload_dir)
    root = _path_obj(upload_dir)
    if not root.is_dir():
        return None
    for pattern in ("*.mgf", "*.MGF"):
        hits = sorted(root.glob(pattern))
        if hits:
            return normalize_display_path(hits[0])
    return None


def normalize_tool_args(
    tool_name: str,
    tool_args: Optional[dict],
    paths: dict[str, str],
    upload_dir: str,
) -> dict:
    """
    按 MCP 定义补全/纠正参数；返回仅含合法键的字典。
    若 LLM 把 output 写成单个 .csv 文件路径，会转为所在目录。
    """
    args = dict(tool_args or {})
    base = paths["outputspace"]
    peaks = paths["peaks"]
    filtered = paths.get("filtered") or _ensure_dir(str(_path_obj(base) / "filtered_features"))
    statistical = paths.get("statistical") or _ensure_dir(
        str(_path_obj(base) / "statistical_results")
    )
    differential = paths.get("differential") or _ensure_dir(
        str(_path_obj(base) / "differential_features")
    )
    annotated = paths.get("annotated") or _ensure_dir(
        str(_path_obj(base) / "annotation_results")
    )
    kegg_out = paths.get("kegg") or _ensure_dir(
        str(_path_obj(base) / "kegg_enrichment_results")
    )
    molecular_network = paths.get("molecular_network") or _ensure_dir(
        str(_path_obj(base) / "molecular_network_results")
    )
    deepmass_out = paths.get("deepmass") or _ensure_dir(
        str(_path_obj(base) / "deepmass_annotation_results")
    )
    search_roots = session_search_roots(paths, upload_dir)

    if tool_name in (
        "convert_raw_to_mzml_msconvert",
        "convert_raw_to_mzml_ThermoRawFileParser",
    ):
        canonical_in = _msconvert_input_dir(paths)
        canonical_out = paths["converted_mzml"]
        out = {
            "input_dir": _use_existing_dir(
                _pick_str(args, "input_dir"),
                canonical_in,
                require_raw=True,
            ),
            "output_dir": _use_existing_dir(
                _pick_str(args, "output_dir"),
                canonical_out,
            ),
        }
        return _posix_paths(out)

    if tool_name.startswith("data_preprocessing_") or tool_name == "mzmine_lcms_datapreprocess":
        candidate = _pick_str(args, "input_dir")
        input_dir = None
        if candidate and _dir_has_mzml(candidate):
            input_dir = normalize_display_path(_path_obj(candidate))
        if not input_dir:
            input_dir = ensure_mzml_input_dir(paths, upload_dir)
        if not input_dir:
            raise FileNotFoundError(
                "无法执行预处理：未找到 mzML 文件。"
                " 请上传 .mzML 到 inputspace，或将 .raw 放入 raw/ 并完成格式转换。"
            )
        default_out = peaks
        if tool_name != "data_preprocessing_xcms":
            # 非 XCMS 预处理写入独立子目录，避免覆盖 XCMS 产物
            stem = tool_name.replace("data_preprocessing_", "").replace("mzmine_lcms_", "mzmine_")
            default_out = str(Path(paths["outputspace"]) / f"{stem}_results")
        out = {
            "input_dir": input_dir,
            "output_dir": _pick_str(args, "output_dir") or default_out,
        }
        if tool_name == "data_preprocessing_xcms":
            for opt in ("blank_pattern", "file_pattern", "ppm", "n_cores"):
                if opt in args:
                    out[opt] = args[opt]
        else:
            for key, value in args.items():
                if key not in out:
                    out[key] = value
        return _posix_paths(out)

    if tool_name == "feature_filtering_and_missing_value_imputation_knn":
        inp_file = _pick_str(
            args,
            "input_feature_table",
            "input_csv",
            "input_path",
            "feature_table",
        )
        inp_dir = _pick_str(args, "input_dir")
        peak_table = _path_obj(peaks) / "feature_table.csv"
        resolved = resolve_dir_with_file(
            inp_dir or (peaks if peak_table.is_file() else None),
            "feature_table.csv",
            peaks,
            search_roots=search_roots,
        )
        if resolved:
            input_dir = resolved
        elif inp_file:
            p = _path_obj(inp_file)
            if p.is_file() and p.name != "feature_table.csv":
                target_dir = peaks if peak_table.is_file() else _dir_of(inp_file)
                input_dir = normalize_display_path(target_dir)
            else:
                input_dir = _dir_of(inp_file)
        else:
            input_dir = peaks

        out_path = _pick_str(args, "output_csv", "output_path", "output_file")
        out_dir = _pick_str(args, "output_dir")
        if out_dir:
            output_dir = _dir_of(out_dir)
        elif out_path:
            output_dir = _dir_of(out_path)
        else:
            output_dir = filtered

        out = {
            "input_dir": input_dir,
            "output_dir": output_dir,
        }
        for opt in ("min_presence", "min_intensity", "n_neighbors"):
            if opt in args:
                out[opt] = args[opt]
        return _posix_paths(out)

    if tool_name == "statistical_analysis_mixomics":
        inp = _pick_str(args, "input_dir", "input_csv", "input_path")
        if inp and _path_obj(inp).suffix.lower() == ".csv":
            candidate_dir = _dir_of(inp)
        elif inp:
            candidate_dir = _dir_of(inp)
        else:
            candidate_dir = filtered
        input_dir = (
            resolve_dir_with_file(
                candidate_dir,
                "feature_table_filtered_imputed.csv",
                filtered,
                search_roots=search_roots,
            )
            or filtered
        )
        # 与特征表样本自动对齐；显式传入的 metadata 若位于会话目录也会被对齐覆盖写回
        meta_aligned = _aligned_metadata_for_feature_dir(upload_dir, input_dir)

        out = {
            "input_dir": input_dir,
            "metadata_csv": meta_aligned,
            "output_dir": _dir_of(_pick_str(args, "output_dir", "output_path") or statistical),
        }
        for opt in (
            "ncomp_pca",
            "ncomp_plsda",
            "scale_method",
            "top_n_heatmap",
            "seed",
            "vip_threshold",
            "pvalue_threshold",
            "padj_threshold",
            "log2fc_threshold",
            "use_fdr",
            "group_column",
            "contrast_group1",
            "contrast_group2",
        ):
            if opt in args and args[opt] is not None and str(args[opt]).strip() != "":
                out[opt] = args[opt]
        return _posix_paths(out)

    if tool_name == "extract_differential_features":
        diff = _pick_str(
            args,
            "differential_csv",
            "input_csv",
            "differential_metabolites",
        )
        if not diff or not _path_obj(diff).is_file():
            diff = find_differential_csv(paths, upload_dir)
        if not diff or not _path_obj(diff).is_file():
            from web_frontend.backend.pipeline_utils import read_analysis_warning

            warning = read_analysis_warning(paths)
            hint = warning or "statistical_results 中缺少 differential_metabolites.csv"
            raise FileNotFoundError(
                f"无法执行差异物提取：{hint}。"
                " 请检查 metadata 是否在特征表中至少包含 2 个分组（QC 样本通常被 XCMS 用作空白扣除，不会进入特征表）。"
            )

        mgf = _pick_str(args, "input_mgf", "mgf", "input_msp", "spectra_mgf")
        if not mgf or not _path_obj(mgf).is_file():
            mgf = find_first_file(
                str(_path_obj(peaks) / "spectra.mgf"),
                search_roots=search_roots,
                patterns=("spectra.mgf", "*.mgf", "*.MGF"),
            )

        out_pick = _pick_str(args, "output_dir", "output_path", "output_msp")
        if out_pick and _path_obj(out_pick).suffix.lower() in (".msp", ".mgf"):
            output_dir = _dir_of(out_pick)
        elif out_pick:
            output_dir = _dir_of(out_pick)
        else:
            output_dir = differential

        return _posix_paths(
            {
                "differential_csv": diff,
                "input_mgf": mgf,
                "output_dir": output_dir,
            }
        )

    if tool_name == "spectral_annotation":
        input_dir = _resolve_spectral_annotation_dir(args, differential, search_roots)
        out = _pick_str(args, "output_dir", "output_csv", "output_path")
        result = {
            "input_dir": input_dir,
            "output_dir": _dir_of(out) if out else annotated,
        }
        for opt in (
            "precursor_ppm",
            "fragment_tol",
            "min_cosine",
            "include_precursor",
            "use_mona",
            "use_spectraverse",
        ):
            if opt in args:
                result[opt] = args[opt]
        return _posix_paths(result)

    if tool_name == "kegg_compound_enrichment":
        inp = _pick_str(args, "input_dir", "input_csv", "input_path")
        annot_name = "differential_feature_table_library_match_clean&add.csv"
        if inp and _path_obj(inp).suffix.lower() == ".csv":
            candidate = _dir_of(inp)
        elif inp:
            candidate = _dir_of(inp)
        else:
            candidate = annotated
        input_dir = (
            resolve_dir_with_file(
                candidate,
                annot_name,
                annotated,
                search_roots=search_roots,
            )
            or candidate
        )
        if not (_path_obj(input_dir) / annot_name).is_file():
            raise FileNotFoundError(
                "kegg_compound_enrichment 需要谱库注释结果 "
                f"{annot_name}。"
                " 请先成功运行 spectral_annotation"
                f"（输出通常在 {annotated}），"
                "不要把 statistical_results 当作 KEGG 输入。"
            )

        out = _pick_str(args, "output_dir", "output_path") or kegg_out
        result = {
            "input_dir": input_dir,
            "output_dir": _dir_of(out),
        }
        for opt in (
            "pvalue_cutoff",
            "padj_method",
            "qvalue_cutoff",
            "min_gs",
            "max_gs",
            "top_n",
            "method",
        ):
            if opt in args and opt != "method":
                result[opt] = args[opt]
        return _posix_paths(result)

    if tool_name.startswith("molecular_networking_"):
        # MS2LDA：Mass2Motif 发现必须用特征对齐全量 MS2 语料，而非差异谱子集
        is_ms2lda = tool_name == "molecular_networking_ms2lda"
        mgf = _resolve_networking_mgf(
            args,
            paths,
            upload_dir,
            prefer_feature_corpus=is_ms2lda,
        )
        if not mgf or not _path_obj(mgf).is_file():
            raise FileNotFoundError(
                "无法执行分子网络：缺少 differential_spectra.mgf 或 spectra.mgf。"
                " 请先完成差异物提取、峰检测 MS2 导出，或直接上传 .mgf。"
            )
        if is_ms2lda:
            n_spec = _count_mgf_spectra(mgf)
            if n_spec < 20:
                raise FileNotFoundError(
                    f"MS2LDA 需要至少约 20 个特征级谱图，当前 {n_spec} 个（{mgf}）。"
                    "请先完成 data_preprocessing_xcms 生成 peak_detection_results/spectra.mgf；"
                    "不要仅用 differential_spectra.mgf 做 Mass2Motif 发现。"
                )
        method = tool_name.replace("molecular_networking_", "")
        # 统一到 molecular_network_results/<method>/，避免 GNPS 根目录与 FBMN 子目录同名图重复
        default_out = str(Path(molecular_network) / method)
        out = {
            "input_mgf": mgf,
            "output_dir": _dir_of(_pick_str(args, "output_dir", "output_path") or default_out),
        }
        if tool_name == "molecular_networking_fbmn":
            feat = _resolve_fbmn_feature_table(args, paths, search_roots)
            out["input_feature_table"] = feat
            out["metadata_csv"] = _aligned_metadata_for_feature_dir(
                upload_dir,
                _dir_of(feat),
            )
        for key, value in args.items():
            if key in out:
                continue
            if key in (
                "input_msp",
                "mgf",
                "spectra_mgf",
                "output_path",
                "input_feature_table",
                "feature_table",
                "input_csv",
                "metadata_csv",
                "metadata",
                "metadata_path",
                "input_mgf",
            ):
                continue
            out[key] = value
        return _posix_paths(out)

    if tool_name in (
        "feature_detection_openms",
        "peak_picking_openms",
        "peak_detection_openms_peakpickerhires",
        "peak_detection_openms_featurefinder",
    ):
        candidate = _pick_str(args, "input_dir")
        converted = paths.get("converted_mzml") or str(
            _path_obj(base) / "converted_mzml"
        )
        input_dir = None
        for d in (candidate, converted):
            if d and _dir_has_mzml(d):
                input_dir = normalize_display_path(_path_obj(d))
                break
        if not input_dir:
            raise FileNotFoundError(
                f"{tool_name} 需要含 *.mzML 的输入目录。"
                f" 候选目录为空：{candidate or '(未指定)'}；"
                f"请先完成 raw→mzML 转换到 {converted}，"
                "或先运行 peak_picking_openms。"
            )
        default_out = {
            "peak_picking_openms": str(_path_obj(base) / "peak_detection_openms_peakpickerhires"),
            "peak_detection_openms_peakpickerhires": str(
                _path_obj(base) / "peak_detection_openms_peakpickerhires"
            ),
            "feature_detection_openms": str(_path_obj(base) / "feature_detection_openms"),
            "peak_detection_openms_featurefinder": str(
                _path_obj(base) / "feature_detection_openms"
            ),
        }.get(tool_name, str(_path_obj(base) / tool_name))
        out = {
            "input_dir": input_dir,
            "output_dir": _dir_of(
                _pick_str(args, "output_dir", "output_path") or default_out
            ),
        }
        for key, value in args.items():
            if key not in out and key not in ("output_path",):
                out[key] = value
        return _posix_paths(out)

    if tool_name == "peak_group_alignment_openms":
        candidate = _pick_str(args, "input_dir")
        openms_feat = str(_path_obj(base) / "openms_feature_detection_results")
        input_dir = None
        for d in (candidate, openms_feat):
            if d and _dir_has_featurexml(d):
                input_dir = normalize_display_path(_path_obj(d))
                break
        if not input_dir:
            xcms_table = _path_obj(peaks) / "feature_table.csv"
            hint = (
                "当前会话已有 XCMS 特征表，可跳过 OpenMS 对齐，"
                "直接用 peak_detection_results 做过滤/统计/FBMN。"
                if xcms_table.is_file()
                else "请先运行 feature_detection_openms / data_preprocessing_openms。"
            )
            raise FileNotFoundError(
                "peak_group_alignment_openms 需要 *.featureXML，"
                f"但未在 openms_feature_detection_results 中找到。{hint}"
            )
        out = {
            "input_dir": input_dir,
            "output_dir": _dir_of(
                _pick_str(args, "output_dir", "output_path")
                or str(_path_obj(base) / "openms_aligned_features")
            ),
        }
        for key, value in args.items():
            if key not in out and key not in ("output_path",):
                out[key] = value
        return _posix_paths(out)

    if tool_name == "deepmass_annotation":
        inp = _pick_str(args, "input_dir", "input_mgf", "input_path")
        if inp and _path_obj(inp).suffix.lower() in (".mgf", ".msp"):
            input_dir = _dir_of(inp)
        elif inp:
            input_dir = _dir_of(inp)
        else:
            input_dir = differential

        out_dir = _dir_of(_pick_str(args, "output_dir", "output_path") or deepmass_out)
        mgf_path = _path_obj(input_dir) / "differential_spectra.mgf"
        if not mgf_path.is_file():
            src = _pick_str(args, "input_mgf", "mgf") or find_session_mgf(paths, upload_dir)
            if not src or not _path_obj(src).is_file():
                src = find_first_file(
                    str(_path_obj(differential) / "differential_spectra.mgf"),
                    str(_path_obj(peaks) / "spectra.mgf"),
                    search_roots=search_roots,
                    patterns=("differential_spectra.mgf", "spectra.mgf", "*.mgf", "*.MGF"),
                )
            if src and _path_obj(src).is_file():
                _path_obj(out_dir).mkdir(parents=True, exist_ok=True)
                dest = _path_obj(out_dir) / "differential_spectra.mgf"
                if not dest.is_file():
                    shutil.copy2(src, dest)
                input_dir = out_dir
                mgf_path = dest
        if not mgf_path.is_file():
            raise FileNotFoundError(
                f"DeepMASS2 需要 differential_spectra.mgf。"
                f" 请上传 MGF 或先运行 extract_differential_features。"
            )
        return _posix_paths(
            {
                "input_dir": input_dir,
                "output_dir": out_dir,
            }
        )

    return _posix_paths(args)


def _msconvert_input_dir(paths: dict[str, str]) -> str:
    """msconvert 读取 raw/ 子目录；兼容旧版平铺在会话根目录的 .raw。"""
    raw_dir = _path_obj(paths.get("raw") or paths["upload"])
    upload_root = _path_obj(paths["upload"])
    if raw_dir.is_dir():
        raws = list(raw_dir.glob("*.raw")) + list(raw_dir.glob("*.RAW"))
        if raws:
            return normalize_display_path(raw_dir)
    if upload_root.is_dir():
        raws = list(upload_root.glob("*.raw")) + list(upload_root.glob("*.RAW"))
        if raws:
            return normalize_display_path(upload_root)
    return normalize_display_path(raw_dir if raw_dir.name == "raw" else raw_dir / "raw")


def _posix_paths(args: dict) -> dict:
    """MCP/工具实现混用路径时统一为正斜杠，避免 peak_detection_results\\file 找不到。"""
    out = {}
    for key, val in args.items():
        if isinstance(val, str) and (
            key.endswith("_dir")
            or key.endswith("_csv")
            or key.endswith("_mgf")
            or key.endswith("_msp")
            or "path" in key
        ):
            out[key] = _path_obj(val).as_posix()
        else:
            out[key] = val
    return out
