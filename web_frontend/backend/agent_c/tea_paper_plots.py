"""都匀毛尖论文（Food Chem X 2026 / main1.pdf）专用图：matplotlib 发表级渲染。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

from web_frontend.backend.paper_plot_helpers import (
    DEFAULT_HEATMAP_MAX_ROWS,
    GRADE_ORDER,
    NPG_COLORS,
    ellipse_enabled,
    grade_sort_key,
    group_color,
    heatmap_figure_inches,
    infer_group_from_sample,
    read_explained_variance,
    show_grid_enabled,
    unique_display_ids,
)
from web_frontend.backend.plot_fonts import cjk_fontproperties, configure_matplotlib_cjk

configure_matplotlib_cjk()

TEA_PAPER_PLOT_TYPES = frozenset(
    {
        "constituent_bar",
        "relative_abundance_heatmap",
        "hca_heatmap",
        "correlation_heatmap",
        "bioactivity_bar",
        "sensory_scores",
        "plsda_permutation",
        "paper_fig2_composite",
        "paper_fig5_composite",
    }
)

_PANEL_LETTERS = "ABCDEFGH"


def _cjk(size: float | int | None = None, *, bold: bool = False):
    return cjk_fontproperties(size=size, bold=bold)


def _read_csv(path: Path):
    return pd.read_csv(path)


def _apply_paper_ax(ax, plot_config: dict[str, Any] | None = None) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#555555")
    ax.spines["bottom"].set_color("#555555")
    ax.tick_params(colors="#333333", length=3, width=0.6)
    if show_grid_enabled(plot_config):
        ax.grid(True, color="#ebebeb", linewidth=0.6)
        ax.set_axisbelow(True)
    else:
        ax.grid(False)


def _panel_letter(ax, letter: str) -> None:
    ax.text(
        -0.12,
        1.08,
        letter,
        transform=ax.transAxes,
        fontproperties=_cjk(12, bold=True),
        va="bottom",
        ha="left",
        color="#111111",
    )


def _save_fig(fig: plt.Figure, output_path: Path) -> None:
    """茶叶论文图全部走投稿导出（600 dpi + PDF + journal.svg）。"""
    from web_frontend.backend.agent_c.nature_distill.journal_export import export_matplotlib_figure

    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_matplotlib_figure(fig, output_path)
    plt.close(fig)


def _title_from_config(plot_config: dict[str, Any], default: str) -> str:
    return str(plot_config.get("title") or default)


def _palette(plot_config: dict[str, Any]) -> dict[str, str]:
    raw = plot_config.get("palette") if isinstance(plot_config.get("palette"), dict) else {}
    return {str(k): str(v) for k, v in raw.items()}


def _finite_or_zero(value: Any) -> float:
    try:
        number = float(value)
        return number if np.isfinite(number) else 0.0
    except (TypeError, ValueError):
        return 0.0


def render_constituent_bar(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "tea_constituents.csv")
    metrics = list(plot_config.get("metrics") or ["TPC", "TFC", "TFAA"])
    present = set(df["metric"].astype(str))
    metrics = [m for m in metrics if m in present] or sorted(present)
    palette = _palette(plot_config)
    fig, axes = plt.subplots(1, len(metrics), figsize=(3.4 * len(metrics), 3.8), squeeze=False)
    y_unit = plot_config.get("y_unit") or "μg/g DM"
    for idx, (ax, metric) in enumerate(zip(axes[0], metrics)):
        sub = df[df["metric"].astype(str) == metric].copy()
        sub["_ord"] = sub["grade"].map(grade_sort_key)
        sub = sub.sort_values("_ord")
        x = np.arange(len(sub))
        colors = [group_color(str(g), palette, i) for i, g in enumerate(sub["grade"])]
        yerr = sub["sd"] if "sd" in sub.columns else None
        ax.bar(
            x,
            sub["mean"],
            yerr=yerr,
            capsize=3,
            color=colors,
            edgecolor="white",
            linewidth=0.6,
            error_kw={"elinewidth": 0.8},
        )
        if "significance_letter" in sub.columns and plot_config.get("show_significance_letters", True):
            for i, (_, row) in enumerate(sub.iterrows()):
                top = float(row["mean"]) + _finite_or_zero(row.get("sd")) * 1.08
                ax.text(
                    i,
                    top,
                    str(row["significance_letter"]),
                    ha="center",
                    va="bottom",
                    fontproperties=_cjk(9, bold=True),
                )
        ax.set_xticks(x)
        ax.set_xticklabels(list(sub["grade"]), rotation=30, ha="right", fontproperties=_cjk(8))
        ax.set_ylabel(y_unit, fontproperties=_cjk(9))
        ax.set_title(metric, fontproperties=_cjk(11, bold=True), pad=2)
        _apply_paper_ax(ax, plot_config)
        _panel_letter(ax, _PANEL_LETTERS[idx])
    fig.suptitle(_title_from_config(plot_config, ""), fontproperties=_cjk(11), y=1.02)
    fig.tight_layout()
    _save_fig(fig, output_path)


def _cluster_order(mat: np.ndarray, axis: int) -> list[int]:
    try:
        from scipy.cluster.hierarchy import leaves_list, linkage
        from scipy.spatial.distance import pdist
    except ImportError:
        return list(range(mat.shape[axis]))
    data = mat if axis == 0 else mat.T
    if data.shape[0] < 2:
        return list(range(data.shape[0]))
    try:
        z = linkage(pdist(data, metric="euclidean"), method="average")
        return list(leaves_list(z))
    except Exception:
        return list(range(data.shape[0]))


def _linkage(mat: np.ndarray, axis: int):
    try:
        from scipy.cluster.hierarchy import linkage
        from scipy.spatial.distance import pdist
    except ImportError:
        return None
    data = mat if axis == 0 else mat.T
    if data.shape[0] < 2:
        return None
    try:
        return linkage(pdist(data, metric="euclidean"), method="average")
    except Exception:
        return None


def _draw_clustered_heatmap(
    ax,
    mat: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
    *,
    cmap: str = "RdBu_r",
    vmin: float | None = None,
    vmax: float | None = None,
    row_dendro_ax=None,
    col_dendro_ax=None,
    col_colors: list[str] | None = None,
    fontsize: int = 7,
):
    row_z = _linkage(mat, 0)
    col_z = _linkage(mat, 1)
    row_order = list(range(mat.shape[0]))
    col_order = list(range(mat.shape[1]))
    if row_z is not None:
        from scipy.cluster.hierarchy import dendrogram, leaves_list

        row_order = list(leaves_list(row_z))
        if row_dendro_ax is not None:
            dendrogram(
                row_z,
                ax=row_dendro_ax,
                orientation="left",
                no_labels=True,
                color_threshold=0,
                above_threshold_color="#888888",
            )
            row_dendro_ax.invert_yaxis()
            row_dendro_ax.axis("off")
    elif row_dendro_ax is not None:
        row_dendro_ax.axis("off")
    if col_z is not None:
        from scipy.cluster.hierarchy import dendrogram, leaves_list

        col_order = list(leaves_list(col_z))
        if col_dendro_ax is not None:
            dendrogram(
                col_z,
                ax=col_dendro_ax,
                orientation="top",
                no_labels=True,
                color_threshold=0,
                above_threshold_color="#888888",
            )
            col_dendro_ax.axis("off")
    elif col_dendro_ax is not None:
        col_dendro_ax.axis("off")

    ordered = mat[np.ix_(row_order, col_order)]
    finite = ordered[np.isfinite(ordered)]
    if vmin is None or vmax is None:
        if finite.size:
            lim = float(np.nanpercentile(np.abs(finite), 98)) or 1.0
            if vmin is None:
                vmin = 0.0 if float(np.nanmin(finite)) >= 0 else -lim
            if vmax is None:
                vmax = lim
        else:
            vmin, vmax = -1.0, 1.0
    im = ax.imshow(ordered, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_yticks(range(len(row_order)))
    ax.set_yticklabels([row_labels[i] for i in row_order], fontproperties=_cjk(fontsize))
    ax.set_xticks(range(len(col_order)))
    ax.set_xticklabels(
        [col_labels[i] for i in col_order],
        rotation=45,
        ha="right",
        fontproperties=_cjk(fontsize),
    )
    if col_colors:
        for i, ci in enumerate(col_order):
            ax.add_patch(
                plt.Rectangle(
                    (i - 0.5, -1.15),
                    1.0,
                    0.35,
                    color=col_colors[ci],
                    clip_on=False,
                    transform=ax.transData,
                )
            )
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return im


def render_relative_abundance_heatmap(
    data_dir: Path,
    output_path: Path,
    plot_config: dict[str, Any],
    *,
    data_file: str = "differential_metabolites_abundance.csv",
) -> None:
    path = data_dir / data_file
    if not path.is_file():
        alt = data_dir / "volatile_differential_abundance.csv"
        path = alt if alt.is_file() else path
    df = _read_csv(path)
    if df.columns[0].lower() in {"compound", "feature", "metabolite", "name"}:
        df = df.set_index(df.columns[0])
    extra_cols = [c for c in ("VIP", "Class", "Name", "vip", "class", "name") if c in df.columns]
    vip_col = next((c for c in ("VIP", "vip") if c in df.columns), None)
    max_rows = int((plot_config.get("marks") or {}).get("top_n") or DEFAULT_HEATMAP_MAX_ROWS)
    if vip_col and len(df) > max_rows:
        order = pd.to_numeric(df[vip_col], errors="coerce").fillna(-1)
        df = df.loc[order.sort_values(ascending=False).index[:max_rows]]
    cols = [c for c in df.columns if c in GRADE_ORDER] or [c for c in df.columns if c not in extra_cols]
    cols = sorted(cols, key=grade_sort_key)
    mat = df[cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if vip_col is None and len(df) > max_rows:
        score = np.nanvar(mat, axis=1)
        keep = np.argsort(score)[::-1][:max_rows]
        mat = mat[keep]
        df = df.iloc[keep]
    labels = unique_display_ids(list(df.index))
    palette = _palette(plot_config)
    col_colors = [group_color(c, palette, i) for i, c in enumerate(cols)]
    fig = plt.figure(figsize=heatmap_figure_inches(len(cols), len(labels)))
    gs = GridSpec(2, 2, width_ratios=[0.18, 1.0], height_ratios=[0.16, 1.0], hspace=0.04, wspace=0.04, figure=fig)
    ax_col = fig.add_subplot(gs[0, 1])
    ax_row = fig.add_subplot(gs[1, 0])
    ax = fig.add_subplot(gs[1, 1])
    raw_cmap = str(plot_config.get("cmap") or "YlOrRd")
    finite = mat[np.isfinite(mat)]
    use_div = finite.size and float(np.nanmin(finite)) < 0
    cmap = "RdBu_r" if use_div else raw_cmap
    im = _draw_clustered_heatmap(
        ax,
        mat,
        labels,
        cols,
        cmap=cmap,
        vmin=None if use_div else 0.0,
        vmax=None,
        row_dendro_ax=ax_row,
        col_dendro_ax=ax_col,
        col_colors=col_colors,
        fontsize=9,
    )
    ax.yaxis.tick_right()
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.12)
    ax.set_title(_title_from_config(plot_config, "Relative abundance"), fontproperties=_cjk(11, bold=True), pad=28)
    _save_fig(fig, output_path)


def render_hca_heatmap(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "hca_matrix.csv")
    if "Sample" in df.columns:
        df = df.set_index("Sample")
    elif str(df.columns[0]).lower() in {"sample", "sample_id"}:
        df = df.set_index(df.columns[0])
    mat = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    samples = [str(i) for i in df.index]
    palette = _palette(plot_config)
    groups = [infer_group_from_sample(s) for s in samples]
    uniq = list(dict.fromkeys(groups))
    row_colors = [group_color(g, palette, uniq.index(g)) for g in groups]
    fig = plt.figure(figsize=(10.5, max(4.5, len(df) * 0.28 + 1.5)))
    gs = GridSpec(2, 2, width_ratios=[0.16, 1.0], height_ratios=[0.12, 1.0], hspace=0.03, wspace=0.03, figure=fig)
    ax_col = fig.add_subplot(gs[0, 1])
    ax_row = fig.add_subplot(gs[1, 0])
    ax = fig.add_subplot(gs[1, 1])
    im = _draw_clustered_heatmap(
        ax,
        mat,
        samples,
        list(df.columns.astype(str)),
        cmap=str(plot_config.get("cmap") or "viridis"),
        vmin=None,
        vmax=None,
        row_dendro_ax=ax_row,
        col_dendro_ax=ax_col,
        fontsize=7,
    )
    for i, color in enumerate(row_colors):
        ax.add_patch(
            plt.Rectangle((-1.2, i - 0.5), 0.35, 1.0, color=color, clip_on=False, transform=ax.transData)
        )
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    ax.set_title(_title_from_config(plot_config, "Hierarchical cluster analysis"), fontproperties=_cjk(11, bold=True), pad=14)
    _save_fig(fig, output_path)


def render_correlation_heatmap(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "correlation_matrix.csv")
    if str(df.columns[0]).lower() in {"variable", "trait", "name", "index"}:
        df = df.set_index(df.columns[0])
    mat = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    labels = [str(i) for i in df.index]
    p_path = data_dir / "correlation_pvalue.csv"
    pmat = None
    if p_path.is_file():
        pdf = _read_csv(p_path)
        if str(pdf.columns[0]).lower() in {"variable", "trait", "name", "index"}:
            pdf = pdf.set_index(pdf.columns[0])
        pmat = pdf.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    fig = plt.figure(figsize=(max(6.2, len(labels) * 0.55 + 1.5), max(5.4, len(labels) * 0.55 + 1.2)))
    gs = GridSpec(2, 2, width_ratios=[0.14, 1.0], height_ratios=[0.14, 1.0], hspace=0.02, wspace=0.02, figure=fig)
    ax_col = fig.add_subplot(gs[0, 1])
    ax_row = fig.add_subplot(gs[1, 0])
    ax = fig.add_subplot(gs[1, 1])
    im = _draw_clustered_heatmap(
        ax,
        mat,
        labels,
        labels,
        cmap="RdBu_r",
        vmin=-1.0,
        vmax=1.0,
        row_dendro_ax=ax_row,
        col_dendro_ax=ax_col,
        fontsize=8,
    )
    if pmat is not None and pmat.shape == mat.shape:
        row_order = _cluster_order(mat, 0)
        col_order = _cluster_order(mat, 1)
        for i, ri in enumerate(row_order):
            for j, ci in enumerate(col_order):
                p = pmat[ri, ci]
                if not np.isfinite(p) or ri == ci:
                    continue
                star = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
                if star:
                    ax.text(j, i, star, ha="center", va="center", color="#111111", fontsize=7)
    fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02, label="Pearson r")
    ax.set_title(_title_from_config(plot_config, "Pearson correlation"), fontproperties=_cjk(11, bold=True), pad=12)
    _save_fig(fig, output_path)


def render_bioactivity_bar(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "bioactivity_assays.csv")
    assays = plot_config.get("assays") or list(dict.fromkeys(df["assay"].astype(str)))
    palette = _palette(plot_config)
    n = max(1, len(assays))
    fig, axes = plt.subplots(1, n, figsize=(3.2 * n, 3.8), squeeze=False)
    for idx, (ax, assay) in enumerate(zip(axes[0], assays)):
        sub = df[df["assay"].astype(str) == str(assay)].copy()
        sub["_ord"] = sub["grade"].map(grade_sort_key)
        sub = sub.sort_values("_ord")
        x = np.arange(len(sub))
        colors = [group_color(str(g), palette, i) for i, g in enumerate(sub["grade"])]
        yerr = sub["sd"] if "sd" in sub.columns else None
        ax.bar(
            x,
            sub["value"],
            yerr=yerr,
            capsize=3,
            color=colors,
            edgecolor="white",
            linewidth=0.6,
            error_kw={"elinewidth": 0.8},
        )
        ax.set_xticks(x)
        ax.set_xticklabels(list(sub["grade"]), rotation=30, ha="right", fontproperties=_cjk(8))
        unit = ""
        if "unit" in sub.columns and len(sub):
            unit = str(sub["unit"].iloc[0] or "")
        ax.set_title(f"{assay}\n({unit})" if unit else str(assay), fontproperties=_cjk(10, bold=True))
        _apply_paper_ax(ax, plot_config)
        _panel_letter(ax, _PANEL_LETTERS[idx])
    fig.suptitle(_title_from_config(plot_config, ""), fontproperties=_cjk(11), y=1.03)
    fig.tight_layout()
    _save_fig(fig, output_path)


def render_sensory_scores(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "sensory_scores.csv")
    attrs = plot_config.get("attributes") or list(dict.fromkeys(df["attribute"].astype(str)))
    grades = sorted(df["grade"].astype(str).unique(), key=grade_sort_key)
    x = np.arange(len(grades))
    width = 0.8 / max(len(attrs), 1)
    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    palette = _palette(plot_config)
    for i, attr in enumerate(attrs):
        sub = df[df["attribute"].astype(str) == str(attr)].copy()
        sub["_ord"] = sub["grade"].map(grade_sort_key)
        sub = sub.sort_values("_ord")
        offset = (i - len(attrs) / 2) * width + width / 2
        color = palette.get(str(attr), NPG_COLORS[i % len(NPG_COLORS)])
        yerr = sub["sd"] if "sd" in sub.columns else None
        ax.bar(
            x + offset,
            sub["score"],
            width=width,
            yerr=yerr,
            label=str(attr),
            capsize=2,
            color=color,
            edgecolor="white",
            linewidth=0.4,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(grades, rotation=20, ha="right", fontproperties=_cjk(9))
    ax.set_ylim(0, 5.5)
    ax.set_ylabel("Score (0–5)", fontproperties=_cjk(10))
    ax.legend(prop=_cjk(8), ncol=2, frameon=False)
    ax.set_title(_title_from_config(plot_config, "Sensory evaluation"), fontproperties=_cjk(12, bold=True))
    _apply_paper_ax(ax, plot_config)
    fig.tight_layout()
    _save_fig(fig, output_path)


def render_plsda_permutation(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "plsda_permutation.csv")
    perm_col = "permutation" if "permutation" in df.columns else df.columns[0]
    r2_col = next((c for c in ("R2", "R2Y", "R2Y(cum)", "r2") if c in df.columns), None)
    q2_col = next((c for c in ("Q2", "Q2(cum)", "q2") if c in df.columns), None)
    if r2_col is None or q2_col is None:
        raise ValueError("plsda_permutation.csv 缺少 R2/Q2 列")
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    colors = plot_config.get("colors") or {}
    r2_color = colors.get("r2_color", "#4C72B0")
    q2_color = colors.get("q2_color", "#C44E52")
    ax.scatter(df[perm_col], df[r2_col], s=18, alpha=0.65, label="R²", color=r2_color, edgecolors="none")
    ax.scatter(df[perm_col], df[q2_col], s=18, alpha=0.65, label="Q²", color=q2_color, edgecolors="none")
    real = df.iloc[0]
    ax.axhline(float(real[r2_col]), color=r2_color, linewidth=1.1, linestyle="--")
    ax.axhline(float(real[q2_col]), color=q2_color, linewidth=1.1, linestyle="--")
    ax.axhline(0, color="#888888", linewidth=0.6)
    ax.set_xlabel("Permutation", fontproperties=_cjk(10))
    ax.set_ylabel("R² / Q²", fontproperties=_cjk(10))
    ax.legend(prop=_cjk(9), frameon=False)
    title = _title_from_config(plot_config, "PLS-DA permutation test")
    ax.set_title(
        f"{title}\nR²={float(real[r2_col]):.3f}, Q²={float(real[q2_col]):.3f}",
        fontproperties=_cjk(11, bold=True),
    )
    _apply_paper_ax(ax, plot_config)
    fig.tight_layout()
    _save_fig(fig, output_path)


def _load_scores_frame(path: Path):
    df = _read_csv(path)
    first = str(df.columns[0])
    if first.lower() in {"sample", "sample_id"} or first == "Sample":
        df = df.set_index(df.columns[0])
    return df


def _draw_score_ax(
    ax,
    data_dir: Path,
    scores_file: str,
    plot_config: dict[str, Any],
    *,
    plot_type: str,
    metadata_csv: Path | None,
    letter: str,
    title: str,
) -> bool:
    path = data_dir / scores_file
    if not path.is_file():
        from web_frontend.backend.plot_edit_registry import resolve_plot_data_file

        alt = resolve_plot_data_file(data_dir, scores_file)
        if alt is not None:
            path = alt
    if not path.is_file() and (data_dir / "_b_contract" / scores_file).is_file():
        path = data_dir / "_b_contract" / scores_file
    if not path.is_file():
        ax.set_axis_off()
        ax.text(0.5, 0.5, f"Missing {scores_file}", ha="center", va="center", fontproperties=_cjk(9), color="#888888")
        _panel_letter(ax, letter)
        return False
    df = _load_scores_frame(path)
    num_cols = [c for c in df.columns if str(c) not in {"Group", "group"}]
    if len(num_cols) < 2:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "Need ≥2 components", ha="center", fontproperties=_cjk(9))
        return False
    xs = pd.to_numeric(df[num_cols[0]], errors="coerce").to_numpy()
    ys = pd.to_numeric(df[num_cols[1]], errors="coerce").to_numpy()
    samples = [str(i) for i in df.index]
    if "Group" in df.columns:
        groups = [str(v) for v in df["Group"]]
    elif metadata_csv and metadata_csv.is_file():
        meta = _read_csv(metadata_csv)
        mmap = {
            str(r["Sample"]).replace(".mzML", ""): str(r["Group"])
            for _, r in meta.iterrows()
            if "Sample" in meta.columns and "Group" in meta.columns
        }
        groups = [mmap.get(s.replace(".mzML", ""), infer_group_from_sample(s)) for s in samples]
    else:
        groups = [infer_group_from_sample(s) for s in samples]
    from web_frontend.backend.simca_score_plot import (
        draw_simca_scores,
        model_tag,
        variance_fraction,
    )

    ratios = read_explained_variance(data_dir, plot_type)
    info = draw_simca_scores(
        ax,
        xs,
        ys,
        groups,
        [s.replace(".mzML", "") for s in samples],
        plot_type=plot_type,
        palette=_palette(plot_config),
        show_labels=True,
        show_ellipse=ellipse_enabled(plot_config),
        compact=True,
    )
    ax.set_title(f"{title} ({model_tag(plot_type)})", fontproperties=_cjk(9), pad=3)
    footer = [
        f"R2X[{i + 1}] = {frac:.3f}"
        for i in (0, 1)
        if i < len(ratios) and (frac := variance_fraction(ratios[i])) is not None
    ]
    if info.get("ellipse"):
        footer.append("Ellipse: Hotelling's T2 (95%)")
    if footer:
        ax.text(
            0.015,
            0.015,
            "   ".join(footer),
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontproperties=_cjk(6),
            zorder=8,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 1.0},
        )
    _panel_letter(ax, letter)
    return True


def _draw_network_ax(ax, data_dir: Path, plot_config: dict[str, Any], letter: str, title: str) -> bool:
    from web_frontend.backend.plot_edit_registry import resolve_plot_data_file
    from web_frontend.backend.semantic_plot_renderer import _network_layout_frame

    nodes_path = resolve_plot_data_file(data_dir, "network_nodes.csv")
    if nodes_path is None:
        for name in ("volatile_network_nodes.csv", "network_nodes.csv"):
            cand = data_dir / name
            if cand.is_file():
                nodes_path = cand
                break
    if nodes_path is None:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "Missing network nodes", ha="center", fontproperties=_cjk(9), color="#888888")
        _panel_letter(ax, letter)
        return False
    nodes = pd.read_csv(nodes_path)
    n_total = len(nodes)
    degree = nodes["degree"] if "degree" in nodes.columns else pd.Series(np.ones(len(nodes)))
    n_iso = int((pd.to_numeric(degree, errors="coerce").fillna(0) <= 0).sum())
    try:
        marks = dict(plot_config.get("marks") or {})
        marks["hide_isolates"] = True
        layout = _network_layout_frame(data_dir, {**plot_config, "hide_isolates": True, "marks": marks})
    except Exception:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "Network layout failed", ha="center", fontproperties=_cjk(9), color="#888888")
        _panel_letter(ax, letter)
        return False
    ax.scatter(layout["x"], layout["y"], s=12, c="#3C5488", alpha=0.85, edgecolors="white", linewidths=0.2)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title(title, fontproperties=_cjk(10, bold=True))
    ax.text(
        0.02,
        0.02,
        f"Isolates hidden: {n_iso}/{n_total}",
        transform=ax.transAxes,
        fontproperties=_cjk(7),
        color="#555555",
    )
    _panel_letter(ax, letter)
    return True


def render_paper_fig2_composite(
    data_dir: Path,
    output_path: Path,
    plot_config: dict[str, Any],
    *,
    metadata_csv: Path | None = None,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.8))
    pca_file = "volatile_pca_scores.csv"
    plsda_file = "volatile_plsda_scores.csv"
    _draw_score_ax(axes[0], data_dir, pca_file, plot_config, plot_type="pca", metadata_csv=metadata_csv, letter="A", title="PCA")
    _draw_score_ax(axes[1], data_dir, plsda_file, plot_config, plot_type="plsda", metadata_csv=metadata_csv, letter="B", title="PLS-DA")
    _draw_network_ax(axes[2], data_dir, plot_config, "C", "Molecular network")
    fig.suptitle(_title_from_config(plot_config, "Volatile profiling"), fontproperties=_cjk(12, bold=True), y=1.04)
    fig.tight_layout()
    _save_fig(fig, output_path)


def render_paper_fig5_composite(
    data_dir: Path,
    output_path: Path,
    plot_config: dict[str, Any],
    *,
    metadata_csv: Path | None = None,
) -> None:
    fig = plt.figure(figsize=(12.2, 8.6))
    gs = GridSpec(2, 3, figure=fig, hspace=0.32, wspace=0.28)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 2])
    ax_d = fig.add_subplot(gs[1, 0])
    ax_e = fig.add_subplot(gs[1, 1:])
    _draw_score_ax(ax_a, data_dir, "pca_scores.csv", plot_config, plot_type="pca", metadata_csv=metadata_csv, letter="A", title="PCA")
    if (data_dir / "hca_matrix.csv").is_file():
        df = _read_csv(data_dir / "hca_matrix.csv")
        if str(df.columns[0]).lower() in {"sample", "sample_id"} or df.columns[0] == "Sample":
            df = df.set_index(df.columns[0])
        mat = df.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        im = ax_b.imshow(mat, aspect="auto", cmap="viridis")
        ax_b.set_yticks(range(min(len(df.index), 20)))
        ax_b.set_yticklabels(list(df.index.astype(str))[:20], fontproperties=_cjk(6))
        ax_b.set_xticks([])
        ax_b.set_title("HCA", fontproperties=_cjk(10, bold=True))
        fig.colorbar(im, ax=ax_b, fraction=0.04)
        _panel_letter(ax_b, "B")
        _apply_paper_ax(ax_b, plot_config)
    else:
        ax_b.set_axis_off()
        ax_b.text(0.5, 0.5, "Missing hca_matrix.csv", ha="center", fontproperties=_cjk(9), color="#888888")
        _panel_letter(ax_b, "B")
    _draw_score_ax(ax_c, data_dir, "plsda_scores.csv", plot_config, plot_type="plsda", metadata_csv=metadata_csv, letter="C", title="PLS-DA")
    if (data_dir / "plsda_permutation.csv").is_file():
        dfp = _read_csv(data_dir / "plsda_permutation.csv")
        pcol = "permutation" if "permutation" in dfp.columns else dfp.columns[0]
        ax_d.scatter(dfp[pcol], dfp["R2"], s=10, alpha=0.6, color="#4C72B0", label="R²")
        ax_d.scatter(dfp[pcol], dfp["Q2"], s=10, alpha=0.6, color="#C44E52", label="Q²")
        ax_d.axhline(float(dfp["R2"].iloc[0]), color="#4C72B0", ls="--", lw=0.9)
        ax_d.axhline(float(dfp["Q2"].iloc[0]), color="#C44E52", ls="--", lw=0.9)
        ax_d.set_title("Permutation", fontproperties=_cjk(10, bold=True))
        ax_d.legend(prop=_cjk(7), frameon=False)
        _apply_paper_ax(ax_d, plot_config)
        _panel_letter(ax_d, "D")
    else:
        ax_d.set_axis_off()
        ax_d.text(0.5, 0.5, "Missing plsda_permutation.csv", ha="center", fontproperties=_cjk(9), color="#888888")
        _panel_letter(ax_d, "D")
    abund = data_dir / "differential_metabolites_abundance.csv"
    if abund.is_file():
        dfa = _read_csv(abund)
        if str(dfa.columns[0]).lower() in {"compound", "feature", "metabolite", "name"}:
            dfa = dfa.set_index(dfa.columns[0])
        cols = [c for c in dfa.columns if c in GRADE_ORDER] or list(dfa.columns)
        mat = dfa[cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
        im = ax_e.imshow(mat, aspect="auto", cmap="YlOrRd")
        ax_e.set_xticks(range(len(cols)))
        ax_e.set_xticklabels(cols, rotation=30, ha="right", fontproperties=_cjk(8))
        ax_e.set_yticks(range(len(dfa)))
        ax_e.set_yticklabels(list(dfa.index.astype(str)), fontproperties=_cjk(6))
        ax_e.set_title("Differential metabolites", fontproperties=_cjk(10, bold=True))
        fig.colorbar(im, ax=ax_e, fraction=0.03)
        _panel_letter(ax_e, "E")
    else:
        ax_e.set_axis_off()
        ax_e.text(0.5, 0.5, "Missing differential abundance", ha="center", fontproperties=_cjk(9), color="#888888")
        _panel_letter(ax_e, "E")
    fig.suptitle(_title_from_config(plot_config, "Non-volatile metabolomics"), fontproperties=_cjk(12, bold=True), y=0.98)
    _save_fig(fig, output_path)


def render_tea_paper_plot(
    plot_type: str,
    data_dir: str | Path,
    output_path: str | Path,
    plot_config: dict[str, Any] | None = None,
    *,
    metadata_csv: str | Path | None = None,
) -> None:
    """渲染论文专用图型；plot_type 须在 TEA_PAPER_PLOT_TYPES 内。"""
    if plot_type not in TEA_PAPER_PLOT_TYPES:
        raise ValueError(f"非 tea 论文图型: {plot_type}")
    cfg = plot_config or {}
    root = Path(data_dir)
    out = Path(output_path)
    meta = Path(metadata_csv) if metadata_csv else None
    if plot_type == "paper_fig2_composite":
        render_paper_fig2_composite(root, out, cfg, metadata_csv=meta)
        return
    if plot_type == "paper_fig5_composite":
        render_paper_fig5_composite(root, out, cfg, metadata_csv=meta)
        return
    dispatch = {
        "constituent_bar": render_constituent_bar,
        "relative_abundance_heatmap": render_relative_abundance_heatmap,
        "hca_heatmap": render_hca_heatmap,
        "correlation_heatmap": render_correlation_heatmap,
        "bioactivity_bar": render_bioactivity_bar,
        "sensory_scores": render_sensory_scores,
        "plsda_permutation": render_plsda_permutation,
    }
    dispatch[plot_type](root, out, cfg)


__all__ = [
    "TEA_PAPER_PLOT_TYPES",
    "render_tea_paper_plot",
]
