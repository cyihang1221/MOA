"""ggplot2 风格的 PCA / PLS-DA 得分图。

对齐常见 `ggplot + stat_ellipse`：无网格、四边黑框、按组填色的 95% 置信椭圆、
彩色散点、少量样本名、图例在右侧。只改版式，不改得分数据。
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Ellipse  # noqa: E402

from web_frontend.backend.paper_plot_helpers import (
    confidence_ellipse_params,
    ellipse_axis_bounds,
    ellipse_enabled,
    is_qc_label,
    plump_thin_ellipse,
)
from web_frontend.backend.plot_fonts import cjk_fontproperties, configure_matplotlib_cjk

configure_matplotlib_cjk()

GGPLOT_STYLE = "ggplot"
_ELLIPSE_NSTD = math.sqrt(5.991464547107979)  # χ²_0.95, df=2
_DEFAULT_TITLES = {
    "",
    "pca",
    "pca plot",
    "pca score plot",
    "pca scores plot",
    "pls-da",
    "plsda",
    "pls-da score plot",
    "pls-da scores plot",
    "plsda score plot",
    "m1 (pca-x)",
    "m1 (pls-da)",
    "figure",
}


def _font(size: float, *, bold: bool = False):
    return cjk_fontproperties(size=size, bold=bold)


def ggplot_title(plot_config: dict[str, Any], plot_type: str) -> str:
    title = str(plot_config.get("title") or "").strip()
    if title.lower() in _DEFAULT_TITLES or re.fullmatch(r"(figure|fig|图)\s*\d+", title, re.I):
        return "PLS-DA plot" if plot_type == "plsda" else "PCA plot"
    return title


def ggplot_axis_name(index: int, plot_type: str) -> str:
    if plot_type == "plsda":
        return f"t[{index + 1}]"
    return f"PC{index + 1}"


def ggplot_group_ellipse_bounds(
    xs: np.ndarray,
    ys: np.ndarray,
    groups: list[str],
    *,
    n_std: float = _ELLIPSE_NSTD,
) -> list[tuple[float, float, float, float]]:
    """每个非 QC 组的 95% 椭圆外接范围。长轴旋转后仍按真实外接框计算。"""
    bounds: list[tuple[float, float, float, float]] = []
    ordered = list(dict.fromkeys(str(g) for g in groups))
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    for group in ordered:
        if is_qc_label(group):
            continue
        mask = np.array([str(g) == group for g in groups])
        if int(mask.sum()) < 3:
            continue
        params = confidence_ellipse_params(x[mask], y[mask], n_std=n_std)
        if not params:
            continue
        cx, cy, width, height, angle = params
        width, height = plump_thin_ellipse(width, height)
        bounds.append(ellipse_axis_bounds(cx, cy, width, height, angle))
    return bounds


def padded_axis_limits(
    lo: float,
    hi: float,
    *,
    pad_lo: float,
    pad_hi: float,
    cfg_lo: Any = None,
    cfg_hi: Any = None,
) -> tuple[float, float]:
    """先给椭圆留白，再允许用户把坐标放宽，但不能把椭圆切到框外。"""
    span = max(float(hi) - float(lo), 1e-6)
    left = float(lo) - pad_lo * span
    right = float(hi) + pad_hi * span
    if cfg_lo is not None:
        left = min(left, float(cfg_lo))
    if cfg_hi is not None:
        right = max(right, float(cfg_hi))
    return left, right


def _numeric_metadata_columns(frame, *, skip: set[str]) -> list[str]:
    import pandas as pd

    found: list[str] = []
    for col in frame.columns:
        name = str(col)
        if name in skip:
            continue
        numeric = pd.to_numeric(frame[col], errors="coerce")
        if float(numeric.notna().mean()) < 0.8:
            continue
        if int(numeric.nunique(dropna=True)) < 2:
            continue
        found.append(name)
    return found


def resolve_ggplot_point_sizes(
    sample_names: list[str],
    metadata_csv: str | Path | None,
    plot_config: dict[str, Any] | None,
) -> tuple[np.ndarray, str, list[float]] | None:
    """点大小对应 metadata 里的数值列，图例标题就是列名（示例图里的 CD52）。

    没有数值列时返回 None，不编造 CD52。恰好一列数值测量时自动使用；
    ``size_by`` 指定列名时用该列；``size_by`` 为空字符串时关闭。
    """
    import pandas as pd

    from web_frontend.backend.session_metadata import load_metadata_frame, normalize_sample_key

    cfg = plot_config if isinstance(plot_config, dict) else {}
    if cfg.get("size_by") == "":
        return None
    path = Path(metadata_csv) if metadata_csv else None
    if path is None or not path.is_file():
        return None
    try:
        frame = load_metadata_frame(path)
    except (OSError, ValueError):
        return None
    color_by = str(cfg.get("color_by") or "Group")
    skip = {"Sample", color_by}
    columns = _numeric_metadata_columns(frame, skip=skip)
    requested = cfg.get("size_by")
    chosen = ""
    if isinstance(requested, str) and requested.strip():
        wanted = requested.strip().lower()
        for col in frame.columns:
            if str(col).lower() != wanted or str(col) == "Sample":
                continue
            numeric = pd.to_numeric(frame[col], errors="coerce")
            if float(numeric.notna().mean()) >= 0.8 and int(numeric.nunique(dropna=True)) >= 2:
                chosen = str(col)
            break
        if not chosen:
            return None
    else:
        rich = [
            col
            for col in columns
            if int(pd.to_numeric(frame[col], errors="coerce").nunique(dropna=True)) >= 3
        ]
        if len(rich) == 1:
            chosen = rich[0]
        elif len(columns) == 1:
            chosen = columns[0]
        else:
            return None

    series = pd.to_numeric(frame[chosen], errors="coerce")
    by_key: dict[str, float] = {}
    for sample, value in zip(frame["Sample"].astype(str), series):
        if pd.notna(value):
            by_key[normalize_sample_key(sample)] = float(value)
    values = np.array(
        [by_key.get(normalize_sample_key(name), np.nan) for name in sample_names],
        dtype=float,
    )
    finite = values[np.isfinite(values)]
    if finite.size < 2 or float(np.nanmax(finite)) <= float(np.nanmin(finite)):
        return None
    lo, hi = float(np.nanmin(finite)), float(np.nanmax(finite))
    breaks = _size_breaks(lo, hi)
    return values, chosen, breaks


def _size_breaks(lo: float, hi: float) -> list[float]:
    raw = np.linspace(lo, hi, 3)
    span = hi - lo
    if span >= 2:
        rounded = np.unique(np.round(raw).astype(int))
        if rounded.size >= 2:
            raw = rounded.astype(float)
    return [float(v) for v in raw]


def _point_area(value: float, lo: float, hi: float) -> float:
    """散点面积。图例 marker 的直径要和这里的面积一致。"""
    span = max(hi - lo, 1e-9)
    t = 0.5 if not math.isfinite(value) else min(1.0, max(0.0, (value - lo) / span))
    diameter = 6.0 + t * 8.0
    return diameter * diameter


def _format_size_break(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{value:.3g}"


def render_ggplot_score_png(
    *,
    scores: np.ndarray,
    groups: list[str],
    sample_names: list[str],
    axis_names: list[str],
    plot_config: dict[str, Any],
    output_path: str | Path,
    plot_type: str,
    ratios: list[float] | None = None,
    legend_title: str = "Group",
    quantitative: bool = False,
    metadata_csv: str | Path | None = None,
) -> Path:
    del axis_names, ratios
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    comps = plot_config.get("components") or [1, 2]
    ncol = scores.shape[1]
    x_idx = min(max(0, int(comps[0]) - 1), ncol - 1)
    y_idx = min(max(0, int(comps[1]) - 1), ncol - 1)
    if x_idx == y_idx and ncol >= 2:
        y_idx = 1 if x_idx != 1 else 0
    xs = np.asarray(scores[:, x_idx], dtype=float)
    ys = np.asarray(scores[:, y_idx], dtype=float)
    names = [re.sub(r"\.(mzml|mzxml)$", "", str(s), flags=re.I) for s in sample_names]
    groups = [str(g) for g in groups]
    palette = plot_config.get("palette") or {}
    fs = plot_config.get("font_size") or {}
    axes_cfg = plot_config.get("axes") or {}
    show_labels = bool(plot_config.get("show_sample_labels", True))
    draw_ellipse = ellipse_enabled(plot_config) and not quantitative

    fig, ax = plt.subplots(figsize=(6.4, 5.6), facecolor="white")
    ax.set_facecolor("white")
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#111111")
        spine.set_linewidth(1.0)

    ordered = list(dict.fromkeys(groups))
    from web_frontend.backend.plot_renderer import _group_color

    size_spec = None if quantitative else resolve_ggplot_point_sizes(names, metadata_csv, plot_config)
    size_values = size_title = size_breaks = None
    if size_spec is not None:
        size_values, size_title, size_breaks = size_spec
        finite_sizes = size_values[np.isfinite(size_values)]
        size_lo = float(finite_sizes.min())
        size_hi = float(finite_sizes.max())
    else:
        size_lo = size_hi = 0.0

    handles = []
    extent_x = [float(np.nanmin(xs)), float(np.nanmax(xs))]
    extent_y = [float(np.nanmin(ys)), float(np.nanmax(ys))]
    for i, group in enumerate(ordered):
        mask = np.array([g == group for g in groups])
        color = _group_color(palette, group, i)
        qc = is_qc_label(group)
        if draw_ellipse and not qc and int(mask.sum()) >= 3:
            params = confidence_ellipse_params(xs[mask], ys[mask], n_std=_ELLIPSE_NSTD)
            if params:
                cx, cy, w, h, ang = params
                w, h = plump_thin_ellipse(w, h)
                ax.add_patch(
                    Ellipse(
                        (cx, cy),
                        w,
                        h,
                        angle=ang,
                        facecolor=color,
                        edgecolor=color,
                        alpha=0.16,
                        linewidth=1.15,
                        zorder=1,
                    )
                )
                xmin, xmax, ymin, ymax = ellipse_axis_bounds(cx, cy, w, h, ang)
                extent_x += [xmin, xmax]
                extent_y += [ymin, ymax]
        if size_values is None:
            areas = np.full(int(mask.sum()), 54.0 if qc else 78.0)
        else:
            areas = np.array(
                [_point_area(float(v), size_lo, size_hi) for v in size_values[mask]],
                dtype=float,
            )
        ax.scatter(
            xs[mask],
            ys[mask],
            s=areas,
            c=color,
            marker="D" if qc else "o",
            edgecolors="#222222",
            linewidths=0.45,
            zorder=3,
        )
        handles.append(
            Line2D(
                [0],
                [0],
                marker="s",
                linestyle="",
                markersize=8,
                markerfacecolor=color,
                markeredgecolor=color,
                label=group,
            )
        )
        if show_labels and not quantitative:
            for j in np.flatnonzero(mask):
                ax.annotate(
                    names[j],
                    (xs[j], ys[j]),
                    textcoords="offset points",
                    xytext=(5, 4),
                    ha="left",
                    va="bottom",
                    fontproperties=_font(fs.get("label", 8)),
                    color=color,
                    zorder=4,
                )

    if quantitative:
        ax.collections.clear()
        try:
            nums = np.array([float(g) for g in groups], dtype=float)
        except (TypeError, ValueError):
            nums = np.full(len(groups), np.nan)
        sc = ax.scatter(xs, ys, c=nums, cmap="viridis", s=78, edgecolors="#222222", linewidths=0.45, zorder=3)
        cbar = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label(legend_title, fontproperties=_font(10))
        handles = []

    x_lo, x_hi = min(extent_x), max(extent_x)
    y_lo, y_hi = min(extent_y), max(extent_y)
    xlim = padded_axis_limits(
        x_lo,
        x_hi,
        pad_lo=0.12,
        pad_hi=0.16,
        cfg_lo=axes_cfg.get("x_min"),
        cfg_hi=axes_cfg.get("x_max"),
    )
    ylim = padded_axis_limits(
        y_lo,
        y_hi,
        pad_lo=0.12,
        pad_hi=0.14,
        cfg_lo=axes_cfg.get("y_min"),
        cfg_hi=axes_cfg.get("y_max"),
    )
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)

    x_title = str(axes_cfg.get("x_title") or "").strip() or ggplot_axis_name(x_idx, plot_type)
    y_title = str(axes_cfg.get("y_title") or "").strip() or ggplot_axis_name(y_idx, plot_type)
    ax.set_xlabel(x_title, fontproperties=_font(fs.get("axis", 12), bold=True))
    ax.set_ylabel(y_title, fontproperties=_font(fs.get("axis", 12), bold=True))
    ax.tick_params(labelsize=fs.get("axis", 11), colors="#111111", width=0.8, length=3.5)
    ax.set_title(
        ggplot_title(plot_config, plot_type),
        loc="left",
        fontproperties=_font(fs.get("title", 16), bold=True),
        color="#111111",
        pad=10,
    )
    legend_cfg = plot_config.get("legend") if isinstance(plot_config.get("legend"), dict) else {}
    if handles and legend_cfg.get("show", True):
        legend = ax.legend(
            handles=handles,
            title=legend_title or "Group",
            loc="upper left" if size_breaks else "center left",
            bbox_to_anchor=(1.02, 1.0 if size_breaks else 0.55),
            frameon=False,
            prop=_font(fs.get("legend", 11)),
            handletextpad=0.4,
            borderaxespad=0.0,
        )
        if legend.get_title():
            legend.get_title().set_fontproperties(_font(fs.get("legend", 12), bold=True))
        if size_breaks and size_title:
            ax.add_artist(legend)
            size_handles = [
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    linestyle="",
                    markersize=math.sqrt(_point_area(value, size_lo, size_hi)),
                    markerfacecolor="#6e6e6e",
                    markeredgecolor="#4a4a4a",
                    markeredgewidth=0.4,
                    label=_format_size_break(value),
                )
                for value in size_breaks
            ]
            size_legend = ax.legend(
                handles=size_handles,
                title=size_title,
                loc="upper left",
                bbox_to_anchor=(1.02, 0.46),
                frameon=False,
                prop=_font(fs.get("legend", 11)),
                labelspacing=0.9,
                handletextpad=0.6,
                borderaxespad=0.0,
            )
            if size_legend.get_title():
                size_legend.get_title().set_fontproperties(_font(fs.get("legend", 12), bold=True))

    fig.tight_layout()
    from web_frontend.backend.agent_c.nature_distill.journal_export import export_matplotlib_figure

    export_matplotlib_figure(fig, out)
    try:
        fig.savefig(out.with_suffix(".svg"), format="svg", bbox_inches="tight", facecolor="white")
    except Exception:
        pass
    plt.close(fig)
    return out
