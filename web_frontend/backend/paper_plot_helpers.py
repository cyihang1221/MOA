"""论文级作图共享工具：椭圆、解释率、VIP 联结、坐标轴语法。

C 侧只读 B 的 CSV，不重跑 mixOmics。供 matplotlib 与 Vega-Lite 共用。
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

GRADE_ORDER = ["Supreme", "Premium", "Special", "Grade I", "Grade II"]
FIVE_GRADE = frozenset(GRADE_ORDER)
BK_DY_QC = frozenset({"BK", "DY", "QC"})

# ggsci NPG，等级/组别在同一复合图内固定
NPG_COLORS = (
    "#E64B35",
    "#4DBBD5",
    "#00A087",
    "#3C5488",
    "#F39B7F",
    "#8491B4",
    "#91D1C2",
    "#DC0000",
)
GRADE_COLORS = {grade: NPG_COLORS[i] for i, grade in enumerate(GRADE_ORDER)}
DEFAULT_VIP_THRESHOLD = 1.2
DEFAULT_VOLATILE_VIP_THRESHOLD = 1.5


def is_qc_label(label: Any) -> bool:
    text = str(label or "").strip().upper()
    return text == "QC" or text.endswith("-QC") or text.startswith("QC") or "_QC" in text or "-QC-" in text


def grade_sort_key(label: str) -> int:
    try:
        return GRADE_ORDER.index(str(label))
    except ValueError:
        return len(GRADE_ORDER)


def group_color(label: str, palette: dict[str, str] | None = None, index: int = 0) -> str:
    if palette and str(label) in palette:
        return str(palette[str(label)])
    if str(label) in GRADE_COLORS:
        return GRADE_COLORS[str(label)]
    return NPG_COLORS[index % len(NPG_COLORS)]


def infer_group_from_sample(sample: str) -> str:
    name = str(sample).replace(".mzML", "").replace(".mzml", "")
    if is_qc_label(name) or "QC" in name.upper():
        return "QC"
    for grade in GRADE_ORDER:
        if name.startswith(grade) or grade in name:
            return grade
    if name.startswith("BK"):
        return "BK"
    if name.startswith("DY"):
        return "DY"
    return name.split("-")[0] if "-" in name else name


def vip_threshold_from_config(plot_config: dict[str, Any] | None, default: float = DEFAULT_VIP_THRESHOLD) -> float:
    cfg = plot_config or {}
    raw = cfg.get("vip_threshold")
    if isinstance(raw, (int, float)):
        return float(raw)
    marks = cfg.get("marks") if isinstance(cfg.get("marks"), dict) else {}
    raw = marks.get("vip_threshold")
    if isinstance(raw, (int, float)):
        return float(raw)
    return float(default)


def ellipse_enabled(plot_config: dict[str, Any] | None) -> bool:
    cfg = plot_config or {}
    if "ellipse" in cfg:
        val = cfg["ellipse"]
        if isinstance(val, dict):
            return bool(val.get("show", True))
        return bool(val)
    marks = cfg.get("marks") if isinstance(cfg.get("marks"), dict) else {}
    if "ellipse" in marks:
        return bool(marks["ellipse"])
    return True


def hide_isolates_enabled(plot_config: dict[str, Any] | None) -> bool:
    cfg = plot_config or {}
    if "hide_isolates" in cfg:
        return bool(cfg["hide_isolates"])
    marks = cfg.get("marks") if isinstance(cfg.get("marks"), dict) else {}
    if "hide_isolates" in marks:
        return bool(marks["hide_isolates"])
    return True


def show_grid_enabled(plot_config: dict[str, Any] | None) -> bool:
    cfg = plot_config or {}
    if "show_grid" in cfg:
        return bool(cfg["show_grid"])
    return False


def ellipse_core_mask(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """只保留聚在一起的主体。离群、和主体之间空出一大段的点不进椭圆。

    按到组中位数的距离由近到远看。某一跳比已经纳入的半径还大，后面的点就不再圈进去。
    点本身仍要画，只是不参与椭圆。
    """
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    mask = np.zeros(x.size, dtype=bool)
    finite = np.flatnonzero(np.isfinite(x) & np.isfinite(y))
    if finite.size < 3:
        return mask
    xf = x[finite]
    yf = y[finite]
    dist = np.hypot(xf - float(np.median(xf)), yf - float(np.median(yf)))
    order = np.argsort(dist)
    ordered = dist[order]
    keep_n = int(ordered.size)
    if ordered.size >= 4:
        for i in range(2, ordered.size - 1):
            radius = float(ordered[i])
            gap = float(ordered[i + 1] - ordered[i])
            # 主体几乎叠在一起时，只要下一点离开这个点就算另一处。
            separated = gap > 1e-6 if radius <= 1e-8 else gap > radius
            if separated:
                keep_n = i + 1
                break
    if keep_n < 3:
        return mask
    mask[finite[order[:keep_n]]] = True
    return mask


def confidence_ellipse_params(
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    n_std: float = 1.96,
) -> tuple[float, float, float, float, float] | None:
    """返回 (cx, cy, width, height, angle_deg)；样本不足或协方差退化时 None。

    没有和主体聚在一起的点不参与拟合，避免椭圆被拉去圈住零散点。
    """
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    mask = ellipse_core_mask(x, y)
    x, y = x[mask], y[mask]
    if x.size < 3:
        return None
    cov = np.cov(x, y)
    if cov.shape != (2, 2) or not np.isfinite(cov).all():
        return None
    vals, vecs = np.linalg.eigh(cov)
    if np.any(vals < 0):
        vals = np.maximum(vals, 0.0)
    if float(vals.sum()) <= 0:
        return None
    order = vals.argsort()[::-1]
    vals, vecs = vals[order], vecs[:, order]
    theta = math.degrees(math.atan2(vecs[1, 0], vecs[0, 0]))
    width = 2.0 * n_std * math.sqrt(max(float(vals[0]), 0.0))
    height = 2.0 * n_std * math.sqrt(max(float(vals[1]), 0.0))
    if width <= 0 or height <= 0:
        return None
    return float(x.mean()), float(y.mean()), width, height, theta


def plump_thin_ellipse(width: float, height: float, *, min_ratio: float = 0.38) -> tuple[float, float]:
    """一维聚成一条线时，把短轴抬到长轴的一定比例，避免椭圆变成针。"""
    major = max(float(width), float(height), 1e-9)
    w, h = float(width), float(height)
    if min(w, h) < min_ratio * major:
        if w <= h:
            w = min_ratio * major
        else:
            h = min_ratio * major
    return w, h


def ellipse_axis_bounds(
    cx: float,
    cy: float,
    width: float,
    height: float,
    angle_deg: float,
) -> tuple[float, float, float, float]:
    """旋转椭圆在数据坐标里的外接范围 (xmin, xmax, ymin, ymax)。

    不能用未旋转的 width/2、height/2：长轴转到竖直方向时，图会把椭圆切到框外。
    """
    a = float(width) / 2.0
    b = float(height) / 2.0
    rad = math.radians(float(angle_deg))
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    dx = math.sqrt((a * cos_a) ** 2 + (b * sin_a) ** 2)
    dy = math.sqrt((a * sin_a) ** 2 + (b * cos_a) ** 2)
    return cx - dx, cx + dx, cy - dy, cy + dy


DEFAULT_HEATMAP_MAX_ROWS = 24
_VIP_TAIL_RE = re.compile(r"\s*\(VIP\s*=.*$", re.IGNORECASE)
_LEADING_ID_RE = re.compile(r"^(\d+)\b")
_NCGC_RE = re.compile(r"\b(NCGC\d+)\b", re.IGNORECASE)
_TOKEN_ID_RE = re.compile(r"^([A-Za-z]{0,8}\d+)\b")


def ellipse_polyline(
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    n_std: float = 1.96,
    n_points: int = 72,
) -> list[dict[str, float]]:
    params = confidence_ellipse_params(xs, ys, n_std=n_std)
    if params is None:
        return []
    return ellipse_polyline_from_params(params, n_points=n_points)


def ellipse_polyline_from_params(
    params: tuple[float, float, float, float, float],
    *,
    n_points: int = 72,
) -> list[dict[str, float]]:
    cx, cy, width, height, angle = params
    t = np.linspace(0.0, 2.0 * math.pi, n_points, endpoint=False)
    a, b = width / 2.0, height / 2.0
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    px = a * np.cos(t)
    py = b * np.sin(t)
    xr = cx + px * cos_a - py * sin_a
    yr = cy + px * sin_a + py * cos_a
    # 闭合，方便填色
    xr = np.append(xr, xr[0])
    yr = np.append(yr, yr[0])
    return [{"x": float(x), "y": float(y), "t": i} for i, (x, y) in enumerate(zip(xr, yr))]


def metabolite_axis_id(label: Any) -> str:
    """热图行名只用短 ID，不把化合物全名、分子式和 VIP 拼进坐标轴。"""
    text = _VIP_TAIL_RE.sub("", str(label or "").strip())
    head = _VIP_TAIL_RE.sub("", text.split("|")[0].strip())
    if head and len(head) <= 22 and " " not in head:
        return head
    match = _LEADING_ID_RE.match(text) or _LEADING_ID_RE.match(head)
    if match:
        return match.group(1)
    match = _NCGC_RE.search(text)
    if match:
        return match.group(1)
    match = _TOKEN_ID_RE.match(head or text)
    if match and 1 < len(match.group(1)) <= 18:
        return match.group(1)
    compact = head or text
    if len(compact) > 18:
        return compact[:16] + "…"
    return compact or "NA"


def unique_display_ids(labels: list[Any]) -> list[str]:
    raw = [metabolite_axis_id(item) for item in labels]
    counts: dict[str, int] = {}
    for item in raw:
        counts[item] = counts.get(item, 0) + 1
    seen: dict[str, int] = {}
    out: list[str] = []
    for item in raw:
        if counts[item] == 1:
            out.append(item)
            continue
        seen[item] = seen.get(item, 0) + 1
        out.append(f"{item}-{seen[item]}")
    return out


def heatmap_figure_inches(n_col: int, n_row: int) -> tuple[float, float]:
    """按格子给足宽度，避免样本列被长标签挤成细条。"""
    cell_w, cell_h = 0.52, 0.46
    width = 1.8 + max(1, n_col) * cell_w + 2.4
    height = 1.6 + max(1, n_row) * cell_h
    return min(width, 22.0), min(max(height, 5.2), 16.0)


def read_explained_variance(data_dir: str | Path, plot_type: str) -> list[float]:
    """读取 PC/LV 分量解释率；缺失或全 NA 时返回空列表。"""
    root = Path(data_dir)
    name = "pca_explained_variance.csv" if plot_type == "pca" else "plsda_explained_variance.csv"
    path = root / name
    if not path.is_file():
        return []
    try:
        frame = pd.read_csv(path)
    except Exception:
        return []
    col = None
    for candidate in ("explained_variance", "explainedVariance", "var"):
        if candidate in frame.columns:
            col = candidate
            break
    values: list[float] = []
    if col:
        raw = pd.to_numeric(frame[col], errors="coerce")
        if raw.notna().any():
            values = [float(v) for v in raw.tolist()]
    if (not values or all(not math.isfinite(v) for v in values)) and "cumulative" in frame.columns:
        cum = pd.to_numeric(frame["cumulative"], errors="coerce").fillna(0.0).tolist()
        if cum:
            values = [float(cum[0])] + [float(cum[i] - cum[i - 1]) for i in range(1, len(cum))]
    return [v if math.isfinite(v) else 0.0 for v in values]


def axis_title_with_variance(base: str, ratio: float | None) -> str:
    if ratio is None or not math.isfinite(ratio) or ratio <= 0:
        return base
    pct = ratio * 100.0 if ratio <= 1.5 else ratio
    return f"{base} ({pct:.1f}%)"


def join_vip_volcano(data_dir: str | Path) -> pd.DataFrame:
    """vip_scores.csv 左连 volcano_results.csv 与 network_nodes（m/z、RT）。"""
    from web_frontend.backend.plot_edit_registry import resolve_plot_data_file
    from web_frontend.backend.semantic_plot_renderer import read_plot_frame

    root = Path(data_dir)
    frame = read_plot_frame(root, "vip_scores.csv")
    frame["Feature"] = frame["Feature"].astype(str)
    volcano_path = resolve_plot_data_file(root, "volcano_results.csv")
    if volcano_path is None:
        parent = root.parent
        volcano_path = resolve_plot_data_file(parent, "volcano_results.csv") if parent.is_dir() else None
    if volcano_path is not None:
        try:
            volcano = read_plot_frame(Path(volcano_path).parent, "volcano_results.csv")
            volcano["Feature"] = volcano["Feature"].astype(str)
            keep = [c for c in ("Feature", "log2FC", "pvalue", "padj", "Significant") if c in volcano.columns]
            frame = frame.merge(volcano[keep], on="Feature", how="left")
        except Exception:
            pass
    nodes_path = resolve_plot_data_file(root, "network_nodes.csv")
    if nodes_path is None and root.parent.is_dir():
        nodes_path = resolve_plot_data_file(root.parent, "network_nodes.csv")
    if nodes_path is not None:
        try:
            nodes = pd.read_csv(nodes_path)
            id_col = next((c for c in ("feature_id", "Feature", "node_id") if c in nodes.columns), None)
            if id_col:
                extra = nodes[[id_col] + [c for c in ("precursor_mz", "rt", "chemical_category", "name") if c in nodes.columns]].copy()
                extra["Feature"] = extra[id_col].astype(str)
                extra = extra.drop(columns=[id_col])
                frame = frame.merge(extra.drop_duplicates("Feature"), on="Feature", how="left")
        except Exception:
            pass
    return frame


def direction_from_log2fc(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if not math.isfinite(number) or number == 0:
        return "unknown"
    return "up" if number > 0 else "down"


def detect_groups_from_metadata(metadata_csv: str | Path | None) -> set[str]:
    if not metadata_csv:
        return set()
    path = Path(metadata_csv)
    if not path.is_file():
        return set()
    try:
        frame = pd.read_csv(path)
    except Exception:
        return set()
    col = "Group" if "Group" in frame.columns else None
    if not col:
        return set()
    return {str(v).strip() for v in frame[col].dropna().tolist() if str(v).strip()}


def study_design_disclaimer(
    *,
    groups: set[str] | None = None,
    metadata_csv: str | Path | None = None,
    reproduction_target: dict[str, Any] | None = None,
    language: str = "zh",
) -> str:
    """五等级论文 vs 当前 BK/DY/QC：缺字段时明确不宣称复现。"""
    found = set(groups or ()) or detect_groups_from_metadata(metadata_csv)
    zh = (language or "zh").lower().startswith("zh")
    paper = bool(reproduction_target and (reproduction_target.get("recipe_id") or reproduction_target.get("doi")))
    if found & FIVE_GRADE and not (found & BK_DY_QC):
        return ""
    if found & BK_DY_QC or any(g.upper().startswith("DY") or g.upper().startswith("BK") for g in found):
        if zh:
            return (
                "当前实验设计为 **BK / DY / QC**（质控与两类比较），"
                "不是论文五等级（Supreme–Grade II）。"
                "下列图按现有分组出图，**不构成** Food Chem X 2026 复现。"
            )
        return (
            "Current design is BK/DY/QC, not the paper's five tea grades. "
            "Figures are not a reproduction of Food Chem X 2026."
        )
    if paper and found and not (found & FIVE_GRADE):
        if zh:
            return (
                "方案命中都匀毛尖论文配方，但 metadata 分组不是五等级，"
                "缺 TPC/活性/感官等湿实验表的图将标为缺失，不伪造。"
            )
        return "Paper recipe matched, but metadata groups are not the five grades; missing assay figures are not fabricated."
    return ""
