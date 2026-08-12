"""在 inputspace / outputspace 中解析会话可用数据文件，供 Agent 工具参数归一化使用。"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Optional

from src.platform_utils import normalize_display_path


def _path(value: str | Path) -> Path:
    return Path(str(value).replace("\\", "/"))


def session_search_roots(paths: dict[str, str], upload_dir: str) -> list[Path]:
    """按优先级列出可搜索的目录（去重、仅保留存在的目录）。"""
    upload = _path(upload_dir)
    raw = _path(paths.get("raw") or upload / "raw")
    roots: list[Path] = []
    for candidate in (
        _path(paths.get("converted_mzml", "")),
        _path(paths.get("peaks", "")),
        _path(paths.get("filtered", "")),
        _path(paths.get("statistical", "")),
        _path(paths.get("differential", "")),
        _path(paths.get("annotated", "")),
        _path(paths.get("kegg", "")),
        _path(paths.get("molecular_network", "")),
        _path(paths.get("deepmass", "")),
        _path(paths.get("outputspace", "")),
        upload,
        raw,
    ):
        if not candidate or not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        if resolved not in roots:
            roots.append(resolved)
    return roots


def _glob_unique(directory: Path, patterns: Iterable[str]) -> list[Path]:
    if not directory.is_dir():
        return []
    seen: set[str] = set()
    found: list[Path] = []
    for pattern in patterns:
        for item in sorted(directory.glob(pattern)):
            key = item.name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(item)
    return found


def collect_mzml_files(paths: dict[str, str], upload_dir: str) -> list[Path]:
    """收集 converted_mzml、upload、raw 中的 mzML（按文件名去重）。"""
    converted = _path(paths["converted_mzml"])
    upload = _path(upload_dir)
    raw = _path(paths.get("raw") or upload / "raw")
    ordered_dirs = [converted, upload, raw]
    seen: set[str] = set()
    found: list[Path] = []
    for directory in ordered_dirs:
        for item in _glob_unique(directory, ("*.mzML", "*.mzml")):
            key = item.name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(item)
    return found


def mzml_stems(paths: dict[str, str], upload_dir: str) -> set[str]:
    return {p.stem.lower() for p in collect_mzml_files(paths, upload_dir)}


def mzml_ready_for_xcms(paths: dict[str, str], upload_dir: str) -> bool:
    return bool(collect_mzml_files(paths, upload_dir))


def ensure_mzml_input_dir(paths: dict[str, str], upload_dir: str) -> Optional[str]:
    """
    将 upload/raw 中的 mzML 同步到 converted_mzml，返回 XCMS 可用的 input_dir。
    若没有任何 mzML 则返回 None。
    """
    files = collect_mzml_files(paths, upload_dir)
    if not files:
        return None
    converted = _path(paths["converted_mzml"])
    converted.mkdir(parents=True, exist_ok=True)
    for src in files:
        dest = converted / src.name
        try:
            if src.resolve() == dest.resolve():
                continue
        except OSError:
            pass
        if not dest.is_file():
            shutil.copy2(src, dest)
            continue
        if src.stat().st_size != dest.stat().st_size:
            shutil.copy2(src, dest)
    try:
        from web_frontend.backend.xcms_patched_run import sanitize_mzml_for_msnbase

        sanitize_mzml_for_msnbase(converted)
    except Exception:
        pass
    return normalize_display_path(converted)


def resolve_existing_path(
    candidate: Optional[str],
    *,
    must_exist: bool = True,
    is_file: bool = False,
) -> Optional[str]:
    if not candidate:
        return None
    path = _path(candidate)
    if is_file and path.is_file():
        return normalize_display_path(path)
    if not is_file and path.is_dir():
        return normalize_display_path(path)
    if must_exist:
        return None
    return normalize_display_path(path)


def resolve_dir_with_file(
    candidate_dir: Optional[str],
    filename: str,
    *fallback_dirs: str,
    search_roots: Optional[list[Path]] = None,
) -> Optional[str]:
    """在候选目录、回退目录及 search_roots 中查找包含 filename 的目录。"""
    checks: list[Path] = []
    if candidate_dir:
        checks.append(_path(candidate_dir))
    for item in fallback_dirs:
        if item:
            checks.append(_path(item))
    if search_roots:
        checks.extend(search_roots)

    seen: set[Path] = set()
    for directory in checks:
        if not directory.is_dir():
            continue
        try:
            resolved = directory.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if (_path(resolved) / filename).is_file():
            return normalize_display_path(resolved)

    if search_roots:
        for root in search_roots:
            if not root.is_dir():
                continue
            try:
                for match in root.rglob(filename):
                    if match.is_file():
                        return normalize_display_path(match.parent)
            except OSError:
                continue
    return None


def find_first_file(
    *candidates: Optional[str],
    search_roots: Optional[list[Path]] = None,
    patterns: Iterable[str] = ("*",),
) -> Optional[str]:
    for candidate in candidates:
        if candidate and _path(candidate).is_file():
            return normalize_display_path(candidate)
    if not search_roots:
        return None
    for root in search_roots:
        if not root.is_dir():
            continue
        for pattern in patterns:
            try:
                hits = sorted(root.rglob(pattern))
            except OSError:
                continue
            for hit in hits:
                if hit.is_file():
                    return normalize_display_path(hit)
    return None


def find_session_mgf(paths: dict[str, str], upload_dir: str) -> Optional[str]:
    roots = session_search_roots(paths, upload_dir)
    return find_first_file(
        search_roots=roots,
        patterns=("*.mgf", "*.MGF"),
    )


def find_differential_csv(paths: dict[str, str], upload_dir: str) -> Optional[str]:
    statistical = _path(paths.get("statistical", ""))
    roots = session_search_roots(paths, upload_dir)
    return find_first_file(
        str(statistical / "differential_metabolites.csv"),
        str(statistical / "differential_metabolites_up.csv"),
        search_roots=roots,
        patterns=(
            "differential_metabolites.csv",
            "differential_metabolites_up.csv",
        ),
    )


def summarize_session_files(
    paths: dict[str, str],
    upload_dir: str,
    *,
    meta_report: dict | None = None,
) -> list[str]:
    """生成供 Agent 计划参考的输入/输出文件摘要。"""
    lines: list[str] = []
    upload = _path(upload_dir)
    if upload.is_dir():
        for item in sorted(upload.iterdir()):
            if item.is_file():
                lines.append(
                    f"{normalize_display_path(item)}: 用户上传 ({item.name})"
                )
    raw = _path(paths.get("raw") or upload / "raw")
    if raw.is_dir():
        for item in sorted(raw.iterdir()):
            if item.is_file():
                lines.append(
                    f"{normalize_display_path(item)}: 质谱 raw ({item.name})"
                )

    mzml_files = collect_mzml_files(paths, upload_dir)
    if mzml_files:
        lines.append(
            f"{paths['converted_mzml']}: mzML 输入目录（含 upload 同步；共 {len(mzml_files)} 个文件）"
        )
        for item in mzml_files[:12]:
            lines.append(f"  - {normalize_display_path(item)}")
        if len(mzml_files) > 12:
            lines.append(f"  - ... 另有 {len(mzml_files) - 12} 个 mzML")

    meta = upload / "metadata.csv"
    if meta.is_file():
        detail = "metadata.csv（Sample, Group）"
        if meta_report:
            groups = meta_report.get("groups") or []
            if groups:
                detail += f"；分组: {', '.join(groups)}"
            action = meta_report.get("action")
            if action == "regenerate":
                detail += "；已根据文件名自动生成"
        lines.append(f"{normalize_display_path(meta)}: {detail}")

    artifact_checks: list[tuple[str, str]] = [
        (str(_path(paths["peaks"]) / "feature_table.csv"), "XCMS feature_table.csv"),
        (str(_path(paths["peaks"]) / "spectra.mgf"), "XCMS spectra.mgf"),
        (
            str(_path(paths["filtered"]) / "feature_table_filtered_imputed.csv"),
            "KNN 填补后特征表",
        ),
        (
            str(_path(paths["statistical"]) / "differential_metabolites.csv"),
            "差异代谢物表",
        ),
        (
            str(_path(paths["differential"]) / "differential_spectra.mgf"),
            "差异物谱图 MGF",
        ),
    ]
    for path_str, label in artifact_checks:
        if _path(path_str).is_file():
            lines.append(f"{normalize_display_path(path_str)}: 已有产物 — {label}")

    mgf = find_session_mgf(paths, upload_dir)
    if mgf:
        lines.append(f"{mgf}: 可用 MGF")

    lines.append(f"{paths['upload']}: 会话输入根目录（inputspace）")
    lines.append(f"{paths['outputspace']}: 会话输出根目录（outputspace）")
    return lines
