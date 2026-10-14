"""SIMCA 14 风格的 PCA / PLS-DA 得分图（matplotlib 重绘，不调用 SIMCA）。

版式对齐 SIMCA「Scores scatter plot」：两行居中标题、t[1]/t[2] 轴、浅灰网格与四边框、
以原点为中心的 Hotelling's T2 (95%) 灰色椭圆、样本名同色标在点旁、右侧色块图例、
底部 R2X[1] / R2X[2] / Ellipse 说明。SIMCA 软件水印不画。
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
from matplotlib.colors import to_rgb  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Ellipse  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from web_frontend.backend.plot_fonts import cjk_fontproperties, configure_matplotlib_cjk

configure_matplotlib_cjk()

# SIMCA 14 默认类别色（按类别顺序），取自 SIMCA 导出图的色块。
SIMCA_CLASS_COLORS = (
    "#2E9E3A",
    "#3A4FC0",
    "#A31F24",
    "#F5D21B",
    "#1F86E0",
    "#F28C1E",
    "#17BECF",
    "#C2379B",
    "#8C564B",
    "#7F7F7F",
)
SIMCA_GRID = "#D9D9D9"
SIMCA_FRAME = "#7F7F7F"
SIMCA_ELLIPSE = "#9A9A9A"
SIMCA_FIGSIZE = (6.6, 4.4)
SIMCA_STYLE = "simca"

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
    "figure",
}


def _font(size: float, *, bold: bool = False):
    return cjk_fontproperties(size=size, bold=bold)


def _auto_palette_colors() -> set[str]:
    colors: set[str] = set()
    try:
        from web_frontend.backend.plot_theme import DEFAULT_PALETTE

        colors.update(c.lower() for c in DEFAULT_PALETTE)
    except Exception:
        pass
    try:
        from web_frontend.backend.literature_figure_style import JOURNAL_PALETTES

        for pal in JOURNAL_PALETTES.values():
            colors.update(c.lower() for c in pal)
    except Exception:
        pass
    try:
        from web_frontend.backend.paper_plot_helpers import GRADE_COLORS, NPG_COLORS

        colors.update(c.lower() for c in NPG_COLORS)
        colors.update(c.lower() for c in GRADE_COLORS.values())
    except Exception:
        pass
    return colors


def simca_group_colors(groups: list[str], palette: dict[str, str] | None) -> dict[str, str]:
    """默认用 SIMCA 类别色；只有用户改过的颜色（不在自动配色表里）才保留。"""
    auto = _auto_palette_colors()
    palette = palette or {}
    out: dict[str, str] = {}
    for i, group in enumerate(groups):
        user = str(palette.get(group) or "").strip()
        if user and user.lower() not in auto:
            out[group] = user
        else:
            out[group] = SIMCA_CLASS_COLORS[i % len(SIMCA_CLASS_COLORS)]
    return out


def _darken(color: str, factor: float) -> tuple[float, float, float]:
    r, g, b = to_rgb(color)
    return (r * factor, g * factor, b * factor)


def _label_color(color: str) -> tuple[float, float, float]:
    r, g, b = to_rgb(color)
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return _darken(color, 0.78) if luminance > 0.62 else (r, g, b)


def f_quantile_2(alpha: float, df2: int) -> float:
    """F(2, df2) 的上分位数；p=2 时 F 分布 CDF 有闭式解，不依赖 scipy。"""
    d = float(df2)
    return d / 2.0 * ((1.0 - alpha) ** (-2.0 / d) - 1.0)


def hotelling_semi_axes(
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    alpha: float = 0.95,
) -> tuple[float, float, float, float] | None:
    """SIMCA 得分图椭圆：中心为得分均值，轴对齐，半轴 = sqrt(T2crit · s²)。"""
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    n = int(x.size)
    a = 2
    if n <= a + 1:
        return None
    t2crit = a * (n * n - 1) / (n * (n - a)) * f_quantile_2(alpha, n - a)
    sx = float(np.var(x, ddof=1))
    sy = float(np.var(y, ddof=1))
    if not (sx > 0 and sy > 0 and t2crit > 0):
        return None
    return float(x.mean()), float(y.mean()), math.sqrt(t2crit * sx), math.sqrt(t2crit * sy)


def variance_fraction(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 0:
        return None
    return v / 100.0 if v > 1.5 else v


def component_axis_label(index: int, plot_type: str) -> str:
    return f"t[{index + 1}]"


def model_tag(plot_type: str) -> str:
    return "PLS-DA" if plot_type == "plsda" else "PCA-X"


def simca_title_lines(plot_config: dict[str, Any], plot_type: str, legend_title: str) -> tuple[str, str]:
    title = str(plot_config.get("title") or "").strip()
    model = str(plot_config.get("model_name") or "M1").strip() or "M1"
    tag = model_tag(plot_type)
    if title.lower() in _DEFAULT_TITLES:
        line1 = f"{model} ({tag})"
    elif re.search(r"\((?:PCA-X|PLS-DA|OPLS-DA)\)\s*$", title, re.I):
        line1 = title
    else:
        line1 = f"{title} ({tag})"
    color_by = str(legend_title or "").strip()
    if color_by.lower() in {"", "group", "class", "classes"}:
        line2 = f"Colored according to classes in {model}"
    else:
        line2 = f"Colored according to {color_by}"
    return line1, line2


def _nice_limits(lo: float, hi: float) -> tuple[float, float]:
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return lo - 1.0, hi + 1.0
    ticks = MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]).tick_values(lo, hi)
    below = [t for t in ticks if t <= lo + 1e-12]
    above = [t for t in ticks if t >= hi - 1e-12]
    return (below[-1] if below else lo), (above[0] if above else hi)


def _place_labels(ax, points: list[dict[str, Any]], size: float) -> None:
    """SIMCA 把样本名放在点右侧；撞字时依次试左、上、下。"""
    if not points:
        return
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    candidates = (
        (4.0, 0.0, "left", "center"),
        (-4.0, 0.0, "right", "center"),
        (0.0, 4.5, "center", "bottom"),
        (0.0, -4.5, "center", "top"),
        (4.0, 5.0, "left", "bottom"),
        (4.0, -5.0, "left", "top"),
        (-4.0, 5.0, "right", "bottom"),
        (-4.0, -5.0, "right", "top"),
    )
    marker_boxes = []
    for p in points:
        px, py = ax.transData.transform((p["x"], p["y"]))
        r = p.get("radius_px", 4.0)
        marker_boxes.append((px - r, py - r, px + r, py + r))
    placed: list[tuple[float, float, float, float]] = []

    def _overlaps(box, others) -> bool:
        x0, y0, x1, y1 = box
        for ox0, oy0, ox1, oy1 in others:
            if x0 < ox1 and x1 > ox0 and y0 < oy1 and y1 > oy0:
                return True
        return False

    for idx, p in enumerate(points):
        ann = ax.annotate(
            p["text"],
            (p["x"], p["y"]),
            textcoords="offset points",
            xytext=candidates[0][:2],
            ha=candidates[0][2],
            va=candidates[0][3],
            fontproperties=_font(size),
            color=p["color"],
            zorder=6,
            annotation_clip=False,
        )
        others_markers = [b for j, b in enumerate(marker_boxes) if j != idx]
        chosen = None
        for dx, dy, ha, va in candidates:
            ann.set_position((dx, dy))
            ann.set_ha(ha)
            ann.set_va(va)
            ext = ann.get_window_extent(renderer)
            box = (ext.x0, ext.y0, ext.x1, ext.y1)
            if not _overlaps(box, placed) and not _overlaps(box, others_markers):
                chosen = box
                break
        if chosen is None:
            dx, dy, ha, va = candidates[0]
            ann.set_position((dx, dy))
            ann.set_ha(ha)
            ann.set_va(va)
            ext = ann.get_window_extent(renderer)
            chosen = (ext.x0, ext.y0, ext.x1, ext.y1)
        placed.append(chosen)


def draw_simca_scores(
    ax,
    xs: np.ndarray,
    ys: np.ndarray,
    groups: list[str],
    sample_names: list[str],
    *,
    plot_type: str,
    palette: dict[str, str] | None = None,
    x_index: int = 0,
    y_index: int = 1,
    show_labels: bool = True,
    show_ellipse: bool = True,
    show_legend: bool = True,
    compact: bool = False,
    axes_cfg: dict[str, Any] | None = None,
    quantitative: bool = False,
    legend_title: str = "",
) -> dict[str, Any]:
    """在已有 axes 上画 SIMCA 风格得分图主体，返回图例句柄与椭圆信息。"""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    tick_size = 7 if compact else 8
    axis_size = 8 if compact else 9
    label_size = 6 if compact else 7
    point_size = 24 if compact else 40

    ax.set_facecolor("white")
    ax.grid(True, color=SIMCA_GRID, linewidth=0.6, linestyle="-")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(SIMCA_FRAME)
        spine.set_linewidth(0.8)
    ax.tick_params(
        axis="both",
        direction="out",
        length=3,
        width=0.6,
        colors="#000000",
        labelsize=tick_size,
    )

    ellipse = hotelling_semi_axes(xs, ys) if show_ellipse else None
    if ellipse:
        cx, cy, ax_x, ax_y = ellipse
        ax.add_patch(
            Ellipse(
                (cx, cy),
                2 * ax_x,
                2 * ax_y,
                angle=0.0,
                facecolor="none",
                edgecolor=SIMCA_ELLIPSE,
                linewidth=0.9,
                zorder=2,
            )
        )

    handles: list[Any] = []
    label_points: list[dict[str, Any]] = []
    radius_px = math.sqrt(point_size) / 2.0 * ax.figure.dpi / 72.0
    if quantitative:
        try:
            values = np.array([float(g) for g in groups], dtype=float)
        except (TypeError, ValueError):
            values = np.full(len(groups), np.nan)
        sc = ax.scatter(
            xs,
            ys,
            c=values,
            cmap="viridis",
            s=point_size,
            edgecolors="#333333",
            linewidths=0.5,
            zorder=4,
        )
        cbar = ax.figure.colorbar(sc, ax=ax, fraction=0.04, pad=0.02)
        cbar.set_label(legend_title, fontproperties=_font(axis_size))
        cbar.ax.tick_params(labelsize=tick_size)
        for j in range(len(xs)):
            label_points.append(
                {"x": xs[j], "y": ys[j], "text": sample_names[j], "color": "#1f1f1f", "radius_px": radius_px}
            )
    else:
        ordered = list(dict.fromkeys(str(g) for g in groups))
        colors = simca_group_colors(ordered, palette)
        for group in ordered:
            mask = np.array([str(g) == group for g in groups], dtype=bool)
            color = colors[group]
            ax.scatter(
                xs[mask],
                ys[mask],
                s=point_size,
                c=[color],
                edgecolors=[_darken(color, 0.62)],
                linewidths=0.6,
                zorder=4,
            )
            handles.append(
                Line2D(
                    [0],
                    [0],
                    marker="s",
                    linestyle="",
                    markersize=7 if not compact else 5.5,
                    markerfacecolor=color,
                    markeredgecolor=_darken(color, 0.62),
                    markeredgewidth=0.5,
                    label=group,
                )
            )
            for j in np.flatnonzero(mask):
                label_points.append(
                    {
                        "x": xs[j],
                        "y": ys[j],
                        "text": sample_names[j],
                        "color": _label_color(color),
                        "radius_px": radius_px,
                    }
                )

    xs_ext = [float(np.nanmin(xs)), float(np.nanmax(xs))]
    ys_ext = [float(np.nanmin(ys)), float(np.nanmax(ys))]
    if ellipse:
        cx, cy, ax_x, ax_y = ellipse
        xs_ext += [cx - ax_x, cx + ax_x]
        ys_ext += [cy - ax_y, cy + ax_y]
    x_lo, x_hi = min(xs_ext), max(xs_ext)
    y_lo, y_hi = min(ys_ext), max(ys_ext)
    pad_x = 0.04 * (x_hi - x_lo or 1.0)
    pad_y = 0.06 * (y_hi - y_lo or 1.0)
    xlim = _nice_limits(x_lo - pad_x, x_hi + pad_x)
    ylim = _nice_limits(y_lo - pad_y, y_hi + pad_y)
    axes_cfg = axes_cfg or {}
    if axes_cfg.get("x_min") is not None:
        xlim = (float(axes_cfg["x_min"]), xlim[1])
    if axes_cfg.get("x_max") is not None:
        xlim = (xlim[0], float(axes_cfg["x_max"]))
    if axes_cfg.get("y_min") is not None:
        ylim = (float(axes_cfg["y_min"]), ylim[1])
    if axes_cfg.get("y_max") is not None:
        ylim = (ylim[0], float(axes_cfg["y_max"]))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]))

    x_title = str(axes_cfg.get("x_title") or "").strip() or component_axis_label(x_index, plot_type)
    y_title = str(axes_cfg.get("y_title") or "").strip() or component_axis_label(y_index, plot_type)
    ax.set_xlabel(x_title, fontproperties=_font(axis_size), labelpad=2)
    ax.set_ylabel(y_title, fontproperties=_font(axis_size), labelpad=2)
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontproperties(_font(tick_size))

    if show_legend and handles:
        if compact:
            # 拼图里右侧紧挨着别的面板，图例收进框内。
            legend = ax.legend(
                handles=handles,
                loc="upper right",
                frameon=True,
                framealpha=0.9,
                edgecolor="#cccccc",
                fancybox=False,
                prop=_font(6),
                handlelength=0.8,
                handletextpad=0.4,
                labelspacing=0.3,
                borderpad=0.35,
            )
        else:
            legend = ax.legend(
                handles=handles,
                loc="upper left",
                bbox_to_anchor=(1.015, 1.0),
                frameon=False,
                prop=_font(tick_size),
                handlelength=0.9,
                handletextpad=0.5,
                labelspacing=0.55,
                borderaxespad=0.0,
            )
        legend.set_zorder(7)

    if show_labels:
        _place_labels(ax, label_points, label_size)
    return {"ellipse": ellipse, "handles": handles}


def _labels_enabled(plot_config: dict[str, Any]) -> bool:
    if plot_config.get("show_sample_labels", True):
        return True
    last = str(plot_config.get("last_instruction") or "")
    return not re.search(r"标签|样本名|label", last, re.I)


def render_simca_score_png(
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
) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    comps = plot_config.get("components") or [1, 2]
    ncol = scores.shape[1]
    x_idx = min(max(0, int(comps[0]) - 1), ncol - 1)
    y_idx = min(max(0, int(comps[1]) - 1), ncol - 1)
    if x_idx == y_idx and ncol >= 2:
        y_idx = 1 if x_idx != 1 else 0

    names = [re.sub(r"\.(mzml|mzxml)$", "", str(s), flags=re.I) for s in sample_names]
    fig = plt.figure(figsize=SIMCA_FIGSIZE, facecolor="white")
    ax = fig.add_axes((0.105, 0.175, 0.745, 0.655))
    ellipse_on = plot_config.get("ellipse") is not False and not (
        isinstance(plot_config.get("ellipse"), dict) and plot_config["ellipse"].get("show") is False
    )
    info = draw_simca_scores(
        ax,
        scores[:, x_idx],
        scores[:, y_idx],
        [str(g) for g in groups],
        names,
        plot_type=plot_type,
        palette=plot_config.get("palette") or {},
        x_index=x_idx,
        y_index=y_idx,
        show_labels=_labels_enabled(plot_config),
        show_ellipse=ellipse_on,
        show_legend=(plot_config.get("legend") or {}).get("show", True),
        axes_cfg=plot_config.get("axes") or {},
        quantitative=quantitative,
        legend_title=legend_title,
    )

    line1, line2 = simca_title_lines(plot_config, plot_type, legend_title)
    box = ax.get_position()
    center_x = box.x0 + box.width / 2.0
    fig.text(center_x, 0.905, line1, ha="center", va="bottom", fontproperties=_font(10))
    fig.text(center_x, 0.852, line2, ha="center", va="bottom", fontproperties=_font(9.5))

    ratios = ratios or []
    footer_y = 0.035
    r2x = []
    for slot, idx in ((1, x_idx), (2, y_idx)):
        frac = variance_fraction(ratios[idx]) if idx < len(ratios) else None
        if frac is not None:
            r2x.append((slot, idx, frac))
    positions = (box.x0 - 0.075, box.x0 + 0.30)
    for (slot, idx, frac), xpos in zip(r2x, positions):
        fig.text(
            max(0.01, xpos),
            footer_y,
            f"R2X[{idx + 1}] = {frac:.3f}",
            ha="left",
            va="bottom",
            fontproperties=_font(8),
        )
    if info.get("ellipse"):
        fig.text(
            0.985,
            footer_y,
            "Ellipse: Hotelling's T2 (95%)",
            ha="right",
            va="bottom",
            fontproperties=_font(8),
        )

    from web_frontend.backend.agent_c.nature_distill.journal_export import export_matplotlib_figure

    export_matplotlib_figure(fig, out)
    try:
        fig.savefig(out.with_suffix(".svg"), format="svg", bbox_inches="tight", facecolor="white")
    except Exception:
        pass
    plt.close(fig)
    return out


__all__ = [
    "SIMCA_CLASS_COLORS",
    "SIMCA_STYLE",
    "component_axis_label",
    "draw_simca_scores",
    "f_quantile_2",
    "hotelling_semi_axes",
    "model_tag",
    "render_simca_score_png",
    "simca_group_colors",
    "simca_title_lines",
    "variance_fraction",
]
