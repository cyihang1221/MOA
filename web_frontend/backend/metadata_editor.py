"""会话 metadata.csv 的读取、保存与样本推断（供 Web 编辑器使用）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from web_frontend.backend.session_metadata import (
    collect_sample_ids_from_session,
    ensure_aligned_metadata_csv,
    ensure_metadata_from_inputs,
    infer_group_label,
    list_metadata_columns,
    load_metadata_frame,
    normalize_sample_key,
)
from web_frontend.backend.session_storage import session_upload_dir

USER_LOCKED_MARKER = "metadata.user_locked"
REQUIRED_SAMPLE_COL = "Sample"
DEFAULT_GROUP_COL = "Group"


class MetadataEditorError(ValueError):
    pass


def _marker_path(upload: Path) -> Path:
    return upload / USER_LOCKED_MARKER


def is_user_locked(upload_dir: str | Path) -> bool:
    return _marker_path(Path(upload_dir)).is_file()


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        raise MetadataEditorError("metadata 至少需要一行样本")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        sample = str(raw.get(REQUIRED_SAMPLE_COL) or raw.get("sample") or "").strip()
        if not sample:
            continue
        key = normalize_sample_key(sample)
        if key in seen:
            raise MetadataEditorError(f"样本名重复：{sample}")
        seen.add(key)
        row = {REQUIRED_SAMPLE_COL: sample}
        group = str(raw.get(DEFAULT_GROUP_COL) or raw.get("group") or "").strip()
        row[DEFAULT_GROUP_COL] = group or "Unknown"
        for k, v in raw.items():
            kn = str(k).strip()
            if kn in {REQUIRED_SAMPLE_COL, DEFAULT_GROUP_COL, "sample", "group"}:
                continue
            if v is None or (isinstance(v, float) and pd.isna(v)):
                row[kn] = ""
            else:
                row[kn] = str(v).strip()
        out.append(row)
    if not out:
        raise MetadataEditorError("请至少填写一列 Sample（样本名）")
    return out


def _rows_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        item: dict[str, Any] = {}
        for col in frame.columns:
            val = row[col]
            if pd.isna(val):
                item[str(col)] = ""
            else:
                item[str(col)] = str(val).strip()
        rows.append(item)
    return rows


def _column_order(rows: list[dict[str, Any]]) -> list[str]:
    cols: list[str] = []
    if rows:
        for key in rows[0]:
            if key not in cols:
                cols.append(key)
        for row in rows[1:]:
            for key in row:
                if key not in cols:
                    cols.append(key)
    if REQUIRED_SAMPLE_COL not in cols:
        cols.insert(0, REQUIRED_SAMPLE_COL)
    if DEFAULT_GROUP_COL not in cols:
        cols.insert(1, DEFAULT_GROUP_COL)
    return cols


def get_metadata_editor_state(
    *,
    project_root: Path,
    storage_slug: str,
    paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    upload = session_upload_dir(project_root, storage_slug)
    upload.mkdir(parents=True, exist_ok=True)
    meta_path = upload / "metadata.csv"
    suggested = collect_sample_ids_from_session(upload, paths=paths)

    rows: list[dict[str, Any]] = []
    columns: list[str] = [REQUIRED_SAMPLE_COL, DEFAULT_GROUP_COL]
    source = "empty"

    if meta_path.is_file():
        try:
            frame = load_metadata_frame(meta_path)
            rows = _rows_from_frame(frame)
            columns = [str(c) for c in frame.columns]
            source = "session"
        except Exception:
            rows = []
            source = "session_unreadable"

    if not rows and suggested:
        rows = [
            {REQUIRED_SAMPLE_COL: s, DEFAULT_GROUP_COL: infer_group_label(s)}
            for s in suggested
        ]
        source = "inferred_preview"

    groups = sorted(
        {
            str(r.get(DEFAULT_GROUP_COL) or "").strip()
            for r in rows
            if str(r.get(DEFAULT_GROUP_COL) or "").strip()
        }
    )
    color_columns: list[dict[str, Any]] = []
    if meta_path.is_file():
        try:
            color_columns = list_metadata_columns(meta_path)
        except Exception:
            pass

    return {
        "path": str(meta_path),
        "exists": meta_path.is_file(),
        "user_locked": is_user_locked(upload),
        "source": source,
        "columns": columns or [REQUIRED_SAMPLE_COL, DEFAULT_GROUP_COL],
        "rows": rows,
        "suggested_samples": suggested,
        "groups": groups,
        "color_columns": color_columns,
    }


def save_metadata_rows(
    *,
    project_root: Path,
    storage_slug: str,
    rows: list[dict[str, Any]],
    paths: dict[str, str] | None = None,
    align_to_inputs: bool = True,
    user_locked: bool = True,
) -> dict[str, Any]:
    upload = session_upload_dir(project_root, storage_slug)
    upload.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_rows(rows)
    columns = _column_order(normalized)
    frame = pd.DataFrame(normalized, columns=columns)
    meta_path = upload / "metadata.csv"
    frame.to_csv(meta_path, index=False)

    if user_locked:
        _marker_path(upload).write_text("user_edited=1\n", encoding="utf-8")

    report: dict[str, Any] = {
        "path": str(meta_path),
        "n_samples": len(normalized),
        "groups": sorted(
            {
                str(r.get(DEFAULT_GROUP_COL) or "").strip()
                for r in normalized
                if str(r.get(DEFAULT_GROUP_COL) or "").strip()
            }
        ),
        "columns": columns,
        "user_locked": user_locked,
    }

    if align_to_inputs:
        try:
            _, align_report = ensure_metadata_from_inputs(
                upload,
                paths=paths,
                write_back=True,
            )
            report["alignment"] = align_report
            frame = load_metadata_frame(meta_path)
            report["rows"] = _rows_from_frame(frame)
            report["columns"] = [str(c) for c in frame.columns]
        except Exception as exc:
            report["alignment_error"] = str(exc)
            report["rows"] = normalized
    else:
        report["rows"] = normalized

    return report


def infer_metadata_from_inputs(
    *,
    project_root: Path,
    storage_slug: str,
    paths: dict[str, str] | None = None,
    preserve_user_locked: bool = True,
) -> dict[str, Any]:
    upload = session_upload_dir(project_root, storage_slug)
    if preserve_user_locked and is_user_locked(upload):
        meta_path = upload / "metadata.csv"
        existing_rows: list[dict[str, Any]] = []
        existing_map: dict[str, str] = {}
        if meta_path.is_file():
            try:
                frame = load_metadata_frame(meta_path)
                existing_rows = _rows_from_frame(frame)
                for r in existing_rows:
                    s = str(r.get(REQUIRED_SAMPLE_COL) or "").strip()
                    g = str(r.get(DEFAULT_GROUP_COL) or "").strip()
                    if s:
                        existing_map[normalize_sample_key(s)] = g or "Unknown"
            except Exception:
                existing_rows = []

        samples = collect_sample_ids_from_session(upload, paths=paths)
        if not samples:
            raise MetadataEditorError("未找到可推断的样本，请先上传 mzML/raw 文件")

        rows: list[dict[str, Any]] = []
        key_to_row = {normalize_sample_key(str(r[REQUIRED_SAMPLE_COL])): r for r in existing_rows}
        for sample in samples:
            key = normalize_sample_key(sample)
            if key in key_to_row:
                row = dict(key_to_row[key])
                row[REQUIRED_SAMPLE_COL] = sample
                rows.append(row)
            else:
                rows.append(
                    {
                        REQUIRED_SAMPLE_COL: sample,
                        DEFAULT_GROUP_COL: infer_group_label(sample),
                    }
                )
        return save_metadata_rows(
            project_root=project_root,
            storage_slug=storage_slug,
            rows=rows,
            paths=paths,
            align_to_inputs=False,
            user_locked=True,
        )

    meta_path, report = ensure_metadata_from_inputs(upload, paths=paths)
    frame = load_metadata_frame(meta_path)
    return {
        "path": meta_path,
        "rows": _rows_from_frame(frame),
        "columns": [str(c) for c in frame.columns],
        "groups": report.get("groups") or [],
        "alignment": report,
        "user_locked": is_user_locked(upload),
    }


__all__ = [
    "MetadataEditorError",
    "USER_LOCKED_MARKER",
    "get_metadata_editor_state",
    "save_metadata_rows",
    "infer_metadata_from_inputs",
    "is_user_locked",
]
