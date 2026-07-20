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


from web_frontend.backend.session_metadata import resolve_metadata_csv


def _metadata_path(upload_dir: str) -> str:
    try:
        return resolve_metadata_csv(upload_dir)
    except FileNotFoundError:
        meta = _path_obj(upload_dir) / "metadata.csv"
        return normalize_display_path(meta)


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


def _dir_has_mzml(path: str) -> bool:
    p = _path_obj(path)
    if not p.is_dir():
        return False
    return bool(list(p.glob("*.mzML")) + list(p.glob("*.mzml")))


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
    meta = _metadata_path(upload_dir)
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

        out = {
            "input_dir": input_dir,
            "metadata_csv": _pick_str(args, "metadata_csv", "metadata", "metadata_path")
            or meta,
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
        ):
            if opt in args:
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
        inp = _pick_str(args, "input_dir", "input_msp", "input_path")
        if inp and _path_obj(inp).suffix.lower() in (".msp", ".mgf"):
            input_dir = _dir_of(inp)
        elif inp:
            input_dir = _dir_of(inp)
        else:
            input_dir = (
                resolve_dir_with_file(
                    differential,
                    "differential_spectra.mgf",
                    differential,
                    search_roots=search_roots,
                )
                or differential
            )

        out = _pick_str(args, "output_dir", "output_csv", "output_path")
        return _posix_paths(
            {
                "input_dir": input_dir,
                "output_dir": _dir_of(out) if out else annotated,
                **{
                    k: args[k]
                    for k in ("precursor_ppm", "fragment_tol", "min_cosine")
                    if k in args
                },
            }
        )

    if tool_name == "kegg_compound_enrichment":
        inp = _pick_str(args, "input_dir", "input_csv", "input_path")
        if inp and _path_obj(inp).suffix.lower() == ".csv":
            input_dir = _dir_of(inp)
        elif inp:
            input_dir = _dir_of(inp)
        else:
            input_dir = (
                resolve_dir_with_file(
                    annotated,
                    "differential_feature_table_library_match_clean&add.csv",
                    annotated,
                    search_roots=search_roots,
                )
                or annotated
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
        mgf = _pick_str(args, "input_mgf", "input_msp", "mgf", "spectra_mgf")
        if not mgf or not _path_obj(mgf).is_file():
            upload_root = _path_obj(upload_dir)
            mgf = _first_existing(
                str(_path_obj(differential) / "differential_spectra.mgf"),
                str(_path_obj(peaks) / "spectra.mgf"),
                str(upload_root / "spectra.mgf"),
            ) or find_session_mgf(paths, upload_dir)
        if not mgf or not _path_obj(mgf).is_file():
            raise FileNotFoundError(
                "无法执行分子网络：缺少 differential_spectra.mgf 或 spectra.mgf。"
                " 请先完成差异物提取、峰检测 MS2 导出，或直接上传 .mgf。"
            )
        default_out = molecular_network
        if tool_name != "molecular_networking_gnps":
            method = tool_name.replace("molecular_networking_", "")
            default_out = str(Path(paths["outputspace"]) / f"molecular_network_{method}_results")
        out = {
            "input_mgf": mgf,
            "output_dir": _dir_of(_pick_str(args, "output_dir", "output_path") or default_out),
        }
        for key, value in args.items():
            if key not in out and key not in ("input_msp", "mgf", "spectra_mgf", "output_path"):
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
