"""A→B 产物交接：按工具类型把上一阶段目录整理成下一工具要的文件名。

B 工具多数硬编码文件名；网页编排器在调用 MCP 前做一次落盘，不把 A/B/C 合成一个 Agent。
实现复用 MassOmics-Agent-B 的 ``src.tools._artifact_resolve``；子进程由 execute_cli 注入
PYTHONPATH，网页进程内则用 ``ensure_b_importable`` 扩展 ``src`` 包搜索路径。
"""
from __future__ import annotations

import csv
import json
import types
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_b.b_imports import ensure_b_importable

_PEAK_TABLE_TOOLS = frozenset(
    {
        "redundant_feature_filtering_camera",
        "redundant_feature_filtering_ramclust",
        "redundant_feature_filtering_mzannotation",
        "feature_filtering_and_missing_value_imputation_knn",
        "missing_value_imputation_missforest",
        "missing_value_imputation_bpca",
        "isotope_identification_isoxpress",
        "isotope_identification_tarmet",
        "isotope_identification_assayr",
        "peak_alignment_xcms_obiwarp",
        "peak_alignment_xcms_loess",
        "align_features_mzmine_joint_aligner",
        "peak_alignment_fft",
        "peak_alignment_dtw",
        "batch_effect_correction_waveica",
        "batch_effect_correction_metnormalizer",
        "batch_effect_correction_metabogroups",
    }
)
_STATS_TOOLS = frozenset(
    {
        "statistical_analysis_mixomics",
        "statistical_analysis_metax",
        "statistical_analysis_sklearn",
        "statistical_analysis_simca",
        "statistical_analysis_dl",
        "statistical_analysis_metaboanalyst",
    }
)
_ID_TOOLS = frozenset(
    {
        "sirius_annotation",
        "deepmass_annotation",
        "csu_ms2_annotation",
        "cfm_id_annotation",
        "library_match_jaccard",
        "library_match_cosine",
        "library_match_spectral_entropy",
        "library_match_spec2vec",
        "library_match_ms2deepscore",
        "library_match_blink",
        "library_match_msbert",
        "spectral_annotation",
    }
)
_NETWORK_TOOLS = frozenset(
    {
        "molecular_networking_gnps",
        "molecular_networking_fbmn",
        "molecular_networking_ms2lda",
    }
)


def prepare_tool_args(
    tool_name: str,
    args: dict[str, Any],
    *,
    run_output_dir: str,
) -> dict[str, Any]:
    """按工具类型整理 input_dir / input_mgf；失败则原样返回，交给工具自己报错。"""
    ensure_b_importable()
    from src.tools._artifact_resolve import (
        materialize_identification_dir,
        materialize_peak_table_dir,
        materialize_stats_dir,
        resolve_spectra_mgf,
        run_search_roots,
    )

    out = dict(args)
    run_dir = str(Path(run_output_dir).resolve()) if run_output_dir else ""
    extras: list[str] = []
    if run_dir:
        extras.append(run_dir)
    input_dir = str(out.get("input_dir") or "").strip()
    if input_dir:
        extras.extend(str(p) for p in run_search_roots(input_dir))
    dest = Path(run_dir or ".") / "_abc_handoff" / tool_name

    try:
        if tool_name == "extract_differential_features":
            csv = str(out.get("differential_csv") or "").strip()
            csv_path = Path(csv) if csv else None
            if csv_path is not None and csv_path.is_dir():
                nested = csv_path / "differential_metabolites.csv"
                csv_path = nested if nested.is_file() else csv_path
            if csv_path is None or not csv_path.is_file():
                hits = []
                for root in [Path(run_dir)] if run_dir else []:
                    hits.extend(root.rglob("differential_metabolites.csv"))
                hits = [p for p in hits if p.is_file() and p.stat().st_size > 0]
                if hits:
                    out["differential_csv"] = str(hits[0].resolve())
            elif csv_path.is_file():
                out["differential_csv"] = str(csv_path.resolve())
            mgf = str(out.get("input_mgf") or "").strip()
            if not mgf or not Path(mgf).is_file():
                search = input_dir or run_dir
                out["input_mgf"] = resolve_spectra_mgf(
                    search,
                    extra_roots=extras,
                    prefer_differential=False,
                )
        elif tool_name in _PEAK_TABLE_TOOLS and input_dir:
            out["input_dir"] = materialize_peak_table_dir(
                input_dir, dest / "peaks", extra_roots=extras
            )
        elif tool_name in _STATS_TOOLS and input_dir:
            out["input_dir"] = materialize_stats_dir(
                input_dir, dest / "stats", extra_roots=extras
            )
        elif (tool_name in _ID_TOOLS or tool_name.startswith("library_match_")) and input_dir:
            out["input_dir"] = materialize_identification_dir(
                input_dir, dest / "id", extra_roots=extras
            )
        elif tool_name in _NETWORK_TOOLS:
            from src.tools._artifact_resolve import resolve_feature_table_csv

            mgf = str(out.get("input_mgf") or "").strip()
            if not mgf or not Path(mgf).is_file():
                search = mgf if Path(mgf).is_dir() else (input_dir or run_dir)
                out["input_mgf"] = resolve_spectra_mgf(search, extra_roots=extras)
            feat = str(out.get("input_feature_table") or "").strip()
            needs_table = tool_name.endswith("_fbmn") or bool(feat)
            if needs_table and (not feat or not Path(feat).is_file()):
                search = feat if Path(feat).is_dir() else (input_dir or run_dir)
                out["input_feature_table"] = resolve_feature_table_csv(
                    search, extra_roots=extras
                )
    except FileNotFoundError as exc:
        print(f"[Agent B] ⚠️ 交接未能为 {tool_name} 备齐输入: {exc}", flush=True)
    return out


_REUSE_MZML_TOOLS = frozenset(
    {
        "convert_raw_to_mzml_ThermoRawFileParser",
        "convert_raw_to_mzml_msconvert",
        "convert_raw_to_mzml_OpenMS_FileConverter",
        "data_transformation_proteowizard",
    }
)
_REUSE_NAMED_FILES: dict[str, tuple[str, ...]] = {
    "data_preprocessing_xcms": ("feature_table.csv",),
    "redundant_feature_filtering_camera": ("feature_table.csv", "all_camera_annotated.csv"),
    "feature_filtering_and_missing_value_imputation_knn": (
        "feature_table_filtered_imputed.csv",
    ),
    # pca_scores 在 perf() 崩溃前就会写出；必须等 VIP/差异表齐了才算成功，否则失败残留会被跳过
    "statistical_analysis_mixomics": (
        "pca_scores.csv",
        "vip_scores.csv",
        "differential_metabolites.csv",
    ),
    "extract_differential_features": (
        "differential_feature_table.csv",
        "differential_spectra.mgf",
    ),
    "spectral_annotation": (
        "differential_feature_table_library_match_clean&add.csv",
    ),
    "kegg_compound_enrichment": ("kegg_compound_enrich.csv",),
    "sirius_annotation": ("sirius_annotation_result.csv",),
}
_PREFERRED_CSV = {
    "data_preprocessing_xcms": "feature_table.csv",
    "statistical_analysis_mixomics": "pca_scores.csv",
    "sirius_annotation": "sirius_annotation_result.csv",
}


def _csv_has_identity(path: Path) -> bool:
    """谱注释表是否已有化合物名或 KEGG ID（全 NA 的空匹配不算完成）。"""
    try:
        import pandas as pd

        df = pd.read_csv(path)
    except Exception:
        return False
    for col in ("kegg_id", "compound_name"):
        if col not in df.columns:
            continue
        series = df[col].dropna().astype(str).str.strip()
        series = series[~series.str.lower().isin({"", "na", "nan", "none"})]
        if len(series) > 0:
            return True
    return False


def _spectral_annotation_reusable(root: Path) -> bool:
    csv = root / "differential_feature_table_library_match_clean&add.csv"
    if not csv.is_file() or csv.stat().st_size <= 0:
        return False
    if _csv_has_identity(csv):
        return True
    note = root / "libraries_used.txt"
    if not note.is_file():
        return False
    for line in note.read_text(encoding="utf-8").splitlines():
        if line.startswith("FOUND\t"):
            parts = line.split("\t")
            if len(parts) >= 3 and Path(parts[2]).is_file():
                return True
    return False


def _kegg_enrichment_reusable(root: Path) -> bool:
    csv = root / "kegg_compound_enrich.csv"
    if not csv.is_file() or csv.stat().st_size <= 0:
        return False
    note = root / "kegg_enrichment_note.txt"
    if note.is_file():
        return False
    try:
        import pandas as pd

        df = pd.read_csv(csv)
    except Exception:
        return False
    return len(df) > 0


def stage_output_reusable(tool_name: str, output_dir: str) -> bool:
    """已有完整产物时跳过重跑（空目录 / 失败残留不算成功）。"""
    root = Path(output_dir) if output_dir else Path()
    if not output_dir or not root.is_dir():
        return False
    if tool_name in _REUSE_MZML_TOOLS:
        hits = [
            p
            for p in root.iterdir()
            if p.is_file() and p.suffix.lower() == ".mzml" and p.stat().st_size > 0
        ]
        return len(hits) >= 1
    if tool_name == "spectral_annotation":
        return _spectral_annotation_reusable(root)
    if tool_name == "kegg_compound_enrichment":
        return _kegg_enrichment_reusable(root)
    names = _REUSE_NAMED_FILES.get(tool_name)
    if names:
        return all(
            (root / name).is_file() and (root / name).stat().st_size > 0 for name in names
        )
    return False


def scan_output_as_tool_result(tool_name: str, output_dir: str) -> dict[str, Any]:
    """把已有目录扫成 MCP 结构化结果，满足 QC R1–R3（有 CSV 时也填 R4）。"""
    root = Path(output_dir)
    files_created: list[dict[str, Any]] = []
    csv_summaries: dict[str, Any] = {}
    skip = {"_handoff_input", "_abc_handoff", "__pycache__"}
    for path in sorted(root.iterdir()):
        if path.name in skip or not path.is_file():
            continue
        size = path.stat().st_size
        files_created.append(
            {
                "path": path.name,
                "directory": str(root),
                "size_bytes": size,
            }
        )
        if path.suffix.lower() == ".csv" and size > 0:
            header: list[str] = []
            rows = 0
            try:
                with path.open(newline="", encoding="utf-8-sig") as handle:
                    reader = csv.reader(handle)
                    header = next(reader, [])
                    rows = sum(1 for _ in reader)
            except OSError:
                header, rows = [], 0
            csv_summaries[path.name] = {
                "row_count": rows,
                "columns": header,
            }
    if tool_name in _PREFERRED_CSV and _PREFERRED_CSV[tool_name] in csv_summaries:
        key = _PREFERRED_CSV[tool_name]
        csv_summaries = {key: csv_summaries[key]}
    return {
        "tool": tool_name,
        "success": True,
        "files_created": files_created,
        "total_files": len(files_created),
        "total_size_bytes": sum(int(f["size_bytes"]) for f in files_created),
        "csv_summaries": csv_summaries,
        "summary_contents": {},
        "metrics": {"reused_existing_output": True},
        "warnings": ["skipped: existing complete output reused"],
        "errors": [],
    }


def wrap_mcp_text_result(payload: dict[str, Any]) -> Any:
    text = json.dumps(payload, ensure_ascii=False)
    return types.SimpleNamespace(
        isError=False,
        content=[types.SimpleNamespace(type="text", text=text)],
    )


def adopt_legacy_output_dir(
    tool_name: str,
    new_output_dir: str,
    run_output_dir: str,
) -> str:
    """把旧的 <category>/<mcp_tool>/ 迁到 <工具名称>/结果/，便于跳过重跑。"""
    import shutil

    ensure_b_importable()
    from src.output_layout import find_legacy_output_dir

    if not new_output_dir:
        return new_output_dir
    new = Path(new_output_dir)
    if stage_output_reusable(tool_name, str(new)):
        return str(new)
    legacy = find_legacy_output_dir(run_output_dir, tool_name)
    if legacy is None or not stage_output_reusable(tool_name, str(legacy)):
        return str(new)
    new.parent.mkdir(parents=True, exist_ok=True)
    if new.exists():
        try:
            next(new.iterdir())
        except StopIteration:
            new.rmdir()
        except OSError:
            return str(new)
        else:
            return str(new)
    shutil.move(str(legacy), str(new))
    try:
        legacy.parent.rmdir()
    except OSError:
        pass
    print(f"[Agent B] 已迁移旧产物 {legacy} → {new}", flush=True)
    return str(new.resolve())


def inspect_metadata_csv(path: str) -> str:
    """给 Agent A 规划用的 metadata 摘要（组内 n）。"""
    from pathlib import Path as P

    file = P(path)
    if not file.is_file():
        return ""
    try:
        import pandas as pd

        df = pd.read_csv(file)
    except Exception as exc:
        return f"[metadata] 无法读取 {file.name}: {exc}"
    cols = {str(c).strip().lower(): c for c in df.columns}
    if "sample" not in cols or "group" not in cols:
        return f"[metadata] {file.name} 列={list(df.columns)}（需要 Sample, Group）"
    counts = df[cols["group"]].astype(str).value_counts().to_dict()
    min_n = min(counts.values()) if counts else 0
    note = (
        f"[metadata] 文件={file.name} 样本数={len(df)} 分组={counts} 最小组内n={min_n}。"
    )
    if min_n < 2:
        note += (
            " 组内 n<2 时不要规划 PLS-DA/OPLS/mixOmics 监督模型；"
            "可做 PCA。QC 样本若未列入表，请补进 metadata 或不要当生物学组。"
        )
    return note
