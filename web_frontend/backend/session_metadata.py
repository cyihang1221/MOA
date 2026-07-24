"""解析/补全会话 metadata.csv；支持按任意列解析着色标签与自动对齐。"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from src.platform_utils import PROJECT_ROOT, normalize_display_path

# 自然语言别名 → 优先匹配的列名关键词（大小写不敏感）
_COLOR_BY_ALIASES: dict[str, tuple[str, ...]] = {
    "group": ("group", "分组", "组别", "class", "类别", "treatment", "处理"),
    "time": ("time", "timepoint", "time_point", "day", "days", "时间", "时点", "时间点"),
    "batch": ("batch", "批次", "run", "plate"),
    "cluster": ("cluster", "聚类", "kmeans"),
    "sample": ("sample", "样本"),
}

_FEATURE_META_COLS = frozenset(
    {
        "feature_id",
        "mz",
        "rt",
        "rt_med",
        "mz_med",
        "feature",
        "row_id",
        "id",
    }
)
_SAMPLE_EXT_RE = re.compile(r"\.(mzml|mzXML|mzxml|raw|mgf|MSP|msp)$", re.IGNORECASE)


def resolve_metadata_csv(upload_dir: str | Path) -> str:
    """
    优先使用会话 inputspace 下的 metadata.csv；
    若不存在则回退到项目根 inputspace/metadata.csv 并复制到会话目录。

    注意：复制全局 metadata 后，若样本与当前特征表不一致，
    应再调用 ensure_aligned_metadata_csv 做自动对齐。
    """
    upload = Path(upload_dir).resolve()
    session_meta = upload / "metadata.csv"
    if session_meta.is_file():
        return normalize_display_path(session_meta)

    global_meta = PROJECT_ROOT / "inputspace" / "metadata.csv"
    if global_meta.is_file():
        upload.mkdir(parents=True, exist_ok=True)
        shutil.copy2(global_meta, session_meta)
        return normalize_display_path(session_meta)

    raise FileNotFoundError(
        f"未找到 metadata.csv。请在上传目录放置 metadata.csv（Sample,Group 列）：{upload}"
    )


def normalize_sample_key(name: str) -> str:
    """统一样本匹配键：去路径、去扩展名、小写。"""
    stem = Path(str(name).strip()).name
    stem = _SAMPLE_EXT_RE.sub("", stem)
    return stem.lower()


def sample_ids_from_feature_table(feature_table: str | Path) -> list[str]:
    """从特征表列名提取样本 ID（排除 feature_id/mz/rt 等元数据列）。"""
    path = Path(feature_table)
    if not path.is_file():
        return []
    frame = pd.read_csv(path, nrows=0)
    samples: list[str] = []
    for col in frame.columns:
        name = str(col).strip()
        if not name or name.lower() in _FEATURE_META_COLS:
            continue
        samples.append(name)
    return samples


def infer_group_label(sample: str) -> str:
    """从样本文件名启发式推断 Group（如 GJ1→GJ，HY2→HY，QC01→QC）。"""
    stem = Path(str(sample).strip()).name
    stem = _SAMPLE_EXT_RE.sub("", stem)
    if re.search(r"(^|[^A-Za-z0-9])QC([^A-Za-z0-9]|$)", stem, re.IGNORECASE) or stem.upper().startswith(
        "QC"
    ):
        return "QC"
    last = stem.split("-")[-1]
    m = re.match(r"^([A-Za-z]+)(\d*)$", last)
    if m and m.group(1):
        token = m.group(1)
        return token.upper() if len(token) <= 4 else token
    m2 = re.match(r"^(.*?)[_-]?(\d+)$", stem)
    if m2 and m2.group(1):
        prefix = m2.group(1).rstrip("-_")
        if prefix:
            return prefix
    return "Unknown"


def _lookup_group(
    sample: str,
    group_by_key: dict[str, str],
) -> str | None:
    key = normalize_sample_key(sample)
    if key in group_by_key:
        return group_by_key[key]
    # metadata 可能带扩展名 / 特征表也可能带扩展名
    for candidate in (
        sample,
        Path(sample).name,
        _SAMPLE_EXT_RE.sub("", Path(sample).name),
    ):
        ck = normalize_sample_key(candidate)
        if ck in group_by_key:
            return group_by_key[ck]
    return None


def _group_map_from_frame(frame: pd.DataFrame) -> dict[str, str]:
    if "Sample" not in frame.columns:
        return {}
    group_col = "Group" if "Group" in frame.columns else None
    if group_col is None:
        for col in frame.columns:
            if str(col) != "Sample":
                group_col = str(col)
                break
    if group_col is None:
        return {}
    mapping: dict[str, str] = {}
    for _, row in frame.iterrows():
        sample = str(row["Sample"]).strip()
        if not sample or sample.lower() == "nan":
            continue
        group = row[group_col]
        if pd.isna(group) or str(group).strip() == "":
            continue
        mapping[normalize_sample_key(sample)] = str(group).strip()
    return mapping


def ensure_aligned_metadata_csv(
    upload_dir: str | Path,
    sample_ids: list[str],
    *,
    write_back: bool = True,
    backup_stale: bool = True,
) -> tuple[str, dict[str, Any]]:
    """
    将会话 metadata.csv 与特征表样本名自动对齐。

    - 零交集（旧实验残留 metadata）：按文件名推断 Group 并重写
    - 部分匹配：保留已知分组，缺失样本自动推断
    - 全匹配：按特征表顺序重写 Sample 列（统一扩展名）
    """
    upload = Path(upload_dir).resolve()
    upload.mkdir(parents=True, exist_ok=True)
    session_meta = upload / "metadata.csv"
    samples = [str(s).strip() for s in sample_ids if str(s).strip()]
    if not samples:
        raise ValueError("ensure_aligned_metadata_csv: sample_ids 为空")

    existing_map: dict[str, str] = {}
    source = "none"
    if session_meta.is_file():
        try:
            existing_map = _group_map_from_frame(pd.read_csv(session_meta))
            source = "session"
        except Exception:
            existing_map = {}
            source = "session_unreadable"
    if not existing_map:
        global_meta = PROJECT_ROOT / "inputspace" / "metadata.csv"
        if global_meta.is_file():
            try:
                existing_map = _group_map_from_frame(pd.read_csv(global_meta))
                source = "global"
            except Exception:
                existing_map = {}

    matched = 0
    rows: list[dict[str, str]] = []
    inferred: list[str] = []
    for sample in samples:
        group = _lookup_group(sample, existing_map)
        if group is None:
            group = infer_group_label(sample)
            inferred.append(sample)
        else:
            matched += 1
        rows.append({"Sample": sample, "Group": group})

    action = "reuse"
    if matched == 0:
        action = "regenerate"
    elif inferred:
        action = "partial_fill"
    else:
        # 即便全匹配，也按特征表列名写回，避免扩展名不一致
        action = "normalize"

    report: dict[str, Any] = {
        "action": action,
        "source": source,
        "n_samples": len(samples),
        "n_matched": matched,
        "n_inferred": len(inferred),
        "inferred_samples": inferred,
        "groups": sorted({r["Group"] for r in rows}),
    }

    if write_back:
        if (
            backup_stale
            and action == "regenerate"
            and session_meta.is_file()
            and source in {"session", "session_unreadable"}
        ):
            bak = upload / "metadata.stale.bak.csv"
            try:
                shutil.copy2(session_meta, bak)
                report["backup"] = normalize_display_path(bak)
            except OSError:
                pass
        out = pd.DataFrame(rows, columns=["Sample", "Group"])
        out.to_csv(session_meta, index=False)
        note = upload / "metadata_alignment_note.txt"
        note.write_text(
            "metadata auto-alignment\n"
            f"action={action}\n"
            f"source={source}\n"
            f"matched={matched}/{len(samples)}\n"
            f"inferred={len(inferred)}\n"
            f"groups={','.join(report['groups'])}\n"
            + (
                "inferred_samples:\n" + "\n".join(inferred) + "\n"
                if inferred
                else ""
            ),
            encoding="utf-8",
        )
        report["note"] = normalize_display_path(note)

    return normalize_display_path(session_meta), report


def load_metadata_frame(metadata_csv: str | Path) -> pd.DataFrame:
    path = Path(metadata_csv)
    if not path.is_file():
        raise FileNotFoundError(f"metadata 不存在：{path}")
    frame = pd.read_csv(path)
    if "Sample" not in frame.columns:
        raise ValueError("metadata.csv 需包含 Sample 列")
    return frame


def list_metadata_columns(metadata_csv: str | Path) -> list[dict[str, Any]]:
    """列出可用于着色的 metadata 列（排除 Sample）。"""
    frame = load_metadata_frame(metadata_csv)
    columns: list[dict[str, Any]] = []
    for name in frame.columns:
        if str(name) == "Sample":
            continue
        series = frame[name]
        nunique = int(series.nunique(dropna=True))
        color_type = infer_color_type(series)
        columns.append(
            {
                "name": str(name),
                "color_type": color_type,
                "n_unique": nunique,
            }
        )
    return columns


def infer_color_type(series: pd.Series) -> str:
    """推断着色类型：离散 nominal / 连续 quantitative。"""
    cleaned = series.dropna()
    if cleaned.empty:
        return "nominal"
    nunique = int(cleaned.nunique())
    if pd.api.types.is_bool_dtype(cleaned):
        return "nominal"
    if pd.api.types.is_numeric_dtype(cleaned):
        # 少量离散水平仍按类别着色（如 1/2/3 处理组）
        if nunique <= 12 and set(cleaned.astype(float)) <= set(range(-50, 51)):
            return "nominal"
        return "quantitative"
    if nunique > max(20, int(len(cleaned) * 0.6)):
        # 接近每样本一个值：仍按 nominal，但调用方可选用 continuous 若可转数值
        try:
            numeric = pd.to_numeric(cleaned, errors="coerce")
            if numeric.notna().mean() >= 0.8:
                return "quantitative"
        except Exception:
            pass
    return "nominal"


def match_color_by_column(
    requested: str | None,
    metadata_csv: str | Path | None = None,
    *,
    default: str = "Group",
    columns: list[str] | None = None,
    fallback: bool = True,
) -> str | None:
    """将用户/意图中的着色字段解析为 metadata 真实列名。

    fallback=False 时：无法匹配则返回 None（不静默退回 Group）。
    """
    if columns is None:
        if metadata_csv is None or (isinstance(metadata_csv, str) and not str(metadata_csv).strip()):
            if not (requested and str(requested).strip()):
                return default if fallback else None
            return str(requested).strip()
        frame = load_metadata_frame(metadata_csv)
        columns = [str(c) for c in frame.columns if str(c) != "Sample"]
    else:
        columns = [str(c) for c in columns if str(c) != "Sample"]

    if not columns:
        return default if fallback else None

    if not requested or not str(requested).strip():
        if default in columns:
            return default
        if "Group" in columns:
            return "Group"
        return columns[0] if fallback else None

    req = str(requested).strip()
    # 精确匹配
    for col in columns:
        if col == req:
            return col
    # 大小写不敏感
    lower_map = {c.lower(): c for c in columns}
    if req.lower() in lower_map:
        return lower_map[req.lower()]

    # 别名表
    req_lower = req.lower()
    for _canon, aliases in _COLOR_BY_ALIASES.items():
        if req_lower in aliases or any(a in req_lower for a in aliases):
            for alias in aliases:
                for col in columns:
                    if alias.lower() == col.lower() or alias.lower() in col.lower():
                        return col

    # 子串模糊
    for col in columns:
        if req_lower in col.lower() or col.lower() in req_lower:
            return col

    # 中文别名直接出现在请求中
    cn_hints = [
        ("时间", ("time", "day", "timepoint")),
        ("批次", ("batch",)),
        ("类别", ("class", "group", "category")),
        ("分组", ("group",)),
        ("聚类", ("cluster",)),
    ]
    for hint, keys in cn_hints:
        if hint in req:
            for col in columns:
                cl = col.lower()
                if any(k in cl for k in keys):
                    return col

    if not fallback:
        return None
    if default in columns:
        return default
    return columns[0]


def resolve_color_labels(
    sample_ids: list[str],
    metadata_csv: str | Path,
    *,
    color_by: str | None = "Group",
) -> tuple[list[Any], str, str]:
    """
    按 Sample 对齐着色值。

    Returns:
        values: 与 sample_ids 等长的标签或数值列表
        resolved_column: 实际使用的列名
        color_type: nominal | quantitative
    """
    frame = load_metadata_frame(metadata_csv)
    column = match_color_by_column(color_by, metadata_csv)
    if not column or column not in frame.columns:
        raise ValueError(f"metadata 中不存在着色列：{color_by}")

    series = frame.set_index(frame["Sample"].astype(str))[column]
    color_type = infer_color_type(series)
    values: list[Any] = []
    for sample in sample_ids:
        key = str(sample)
        if key not in series.index:
            # 尝试去掉扩展名再匹配
            stem = re.sub(r"\.(mzML|mzml|raw)$", "", key)
            if stem in series.index:
                key = stem
            else:
                values.append("Unknown" if color_type == "nominal" else float("nan"))
                continue
        raw = series.loc[key]
        if isinstance(raw, pd.Series):
            raw = raw.iloc[0]
        if pd.isna(raw):
            values.append("Unknown" if color_type == "nominal" else float("nan"))
        elif color_type == "quantitative":
            try:
                values.append(float(raw))
            except (TypeError, ValueError):
                values.append(float("nan"))
        else:
            values.append(str(raw))
    return values, column, color_type


__all__ = [
    "resolve_metadata_csv",
    "load_metadata_frame",
    "list_metadata_columns",
    "infer_color_type",
    "match_color_by_column",
    "resolve_color_labels",
    "normalize_sample_key",
    "sample_ids_from_feature_table",
    "infer_group_label",
    "ensure_aligned_metadata_csv",
]
