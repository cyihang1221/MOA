"""都匀毛尖论文（Food Chem X 2026）专用图型：matplotlib 渲染。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

TEA_PAPER_PLOT_TYPES = frozenset(
    {
        "constituent_bar",
        "relative_abundance_heatmap",
        "hca_heatmap",
        "correlation_heatmap",
        "bioactivity_bar",
        "sensory_scores",
        "plsda_permutation",
    }
)

_GRADE_ORDER = ["Supreme", "Premium", "Special", "Grade I", "Grade II"]


def _read_csv(path: Path):
    import pandas as pd

    return pd.read_csv(path)


def _grade_sort_key(label: str) -> int:
    try:
        return _GRADE_ORDER.index(label)
    except ValueError:
        return len(_GRADE_ORDER)


def _save_fig(fig: plt.Figure, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _title_from_config(plot_config: dict[str, Any], default: str) -> str:
    return str(plot_config.get("title") or default)


def render_constituent_bar(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "tea_constituents.csv")
    metrics = plot_config.get("metrics") or ["TPC", "TFC", "TFAA"]
    fig, axes = plt.subplots(1, len(metrics), figsize=(4 * len(metrics), 4), squeeze=False)
    for ax, metric in zip(axes[0], metrics):
        sub = df[df["metric"] == metric].copy()
        sub["_ord"] = sub["grade"].map(_grade_sort_key)
        sub = sub.sort_values("_ord")
        x = np.arange(len(sub))
        bars = ax.bar(x, sub["mean"], yerr=sub.get("sd"), capsize=3, color="#4C72B0", edgecolor="white")
        if "significance_letter" in sub.columns and plot_config.get("show_significance_letters", True):
            for i, (_, row) in enumerate(sub.iterrows()):
                ax.text(i, row["mean"] + (row.get("sd") or 0) * 1.05, str(row["significance_letter"]), ha="center", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(sub["grade"], rotation=30, ha="right")
        ax.set_title(metric)
        ax.set_ylabel(plot_config.get("y_unit") or "μg/g DM")
        _ = bars
    fig.suptitle(_title_from_config(plot_config, "Constituent contents by grade"))
    _save_fig(fig, output_path)


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
    cols = [c for c in df.columns if c in _GRADE_ORDER] or list(df.columns)
    cols = sorted(cols, key=_grade_sort_key)
    mat = df[cols].astype(float).values
    fig, ax = plt.subplots(figsize=(max(6, len(cols) * 0.8), max(5, len(df) * 0.15)))
    im = ax.imshow(mat, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=30, ha="right")
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df.index, fontsize=7)
    ax.set_title(_title_from_config(plot_config, "Relative abundance"))
    fig.colorbar(im, ax=ax, fraction=0.03)
    _save_fig(fig, output_path)


def render_hca_heatmap(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "hca_matrix.csv")
    if "Sample" in df.columns:
        df = df.set_index("Sample")
    elif df.columns[0].lower() in {"sample", "sample_id"}:
        df = df.set_index(df.columns[0])
    mat = df.astype(float).values
    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.35)))
    im = ax.imshow(mat, aspect="auto", cmap="viridis")
    ax.set_yticks(range(len(df.index)))
    ax.set_yticklabels(df.index, fontsize=8)
    ax.set_xticks([])
    ax.set_title(_title_from_config(plot_config, "Hierarchical cluster analysis"))
    fig.colorbar(im, ax=ax, fraction=0.02)
    _save_fig(fig, output_path)


def render_correlation_heatmap(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "correlation_matrix.csv")
    if df.columns[0].lower() in {"variable", "trait", "name", "index"}:
        df = df.set_index(df.columns[0])
    mat = df.astype(float).values
    labels = list(df.index)
    fig, ax = plt.subplots(figsize=(max(6, len(labels) * 0.5), max(5, len(labels) * 0.5)))
    im = ax.imshow(mat, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_title(_title_from_config(plot_config, "Pearson correlation"))
    fig.colorbar(im, ax=ax, fraction=0.03)
    _save_fig(fig, output_path)


def render_bioactivity_bar(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "bioactivity_assays.csv")
    assays = plot_config.get("assays") or sorted(df["assay"].unique())
    n = len(assays)
    fig, axes = plt.subplots(1, n, figsize=(3.5 * n, 4), squeeze=False)
    for ax, assay in zip(axes[0], assays):
        sub = df[df["assay"] == assay].copy()
        sub["_ord"] = sub["grade"].map(_grade_sort_key)
        sub = sub.sort_values("_ord")
        x = np.arange(len(sub))
        ax.bar(x, sub["value"], yerr=sub.get("sd"), capsize=3, color="#55A868")
        ax.set_xticks(x)
        ax.set_xticklabels(sub["grade"], rotation=30, ha="right", fontsize=8)
        unit = sub["unit"].iloc[0] if "unit" in sub.columns and len(sub) else ""
        ax.set_title(f"{assay}\n({unit})" if unit else assay)
    fig.suptitle(_title_from_config(plot_config, "Bioactivity assays"))
    _save_fig(fig, output_path)


def render_sensory_scores(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "sensory_scores.csv")
    attrs = plot_config.get("attributes") or sorted(df["attribute"].unique())
    grades = sorted(df["grade"].unique(), key=_grade_sort_key)
    x = np.arange(len(grades))
    width = 0.8 / max(len(attrs), 1)
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, attr in enumerate(attrs):
        sub = df[df["attribute"] == attr].copy()
        sub["_ord"] = sub["grade"].map(_grade_sort_key)
        sub = sub.sort_values("_ord")
        offset = (i - len(attrs) / 2) * width + width / 2
        ax.bar(x + offset, sub["score"], width=width, yerr=sub.get("sd"), label=attr, capsize=2)
    ax.set_xticks(x)
    ax.set_xticklabels(grades, rotation=20, ha="right")
    ax.set_ylim(0, 5.5)
    ax.set_ylabel("Score (0–5)")
    ax.legend(fontsize=8, ncol=2)
    ax.set_title(_title_from_config(plot_config, "Sensory evaluation"))
    _save_fig(fig, output_path)


def render_plsda_permutation(data_dir: Path, output_path: Path, plot_config: dict[str, Any]) -> None:
    df = _read_csv(data_dir / "plsda_permutation.csv")
    perm_col = "permutation" if "permutation" in df.columns else df.columns[0]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(df[perm_col], df["R2"], s=20, alpha=0.6, label="R²", color="#4C72B0")
    ax.scatter(df[perm_col], df["Q2"], s=20, alpha=0.6, label="Q²", color="#C44E52")
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_xlabel("Permutation")
    ax.set_ylabel("R² / Q²")
    ax.legend()
    ax.set_title(_title_from_config(plot_config, "PLS-DA permutation test"))
    _save_fig(fig, output_path)


def render_tea_paper_plot(
    plot_type: str,
    data_dir: str | Path,
    output_path: str | Path,
    plot_config: dict[str, Any] | None = None,
) -> None:
    """渲染论文专用图型；plot_type 须在 TEA_PAPER_PLOT_TYPES 内。"""
    if plot_type not in TEA_PAPER_PLOT_TYPES:
        raise ValueError(f"非 tea 论文图型: {plot_type}")
    cfg = plot_config or {}
    root = Path(data_dir)
    out = Path(output_path)
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
