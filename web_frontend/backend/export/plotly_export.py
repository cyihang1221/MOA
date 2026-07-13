"""Export Plotly JSON alongside PNG figures for the web chart editor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def plotly_json_path(png_path: str | Path) -> Path:
    png = Path(png_path)
    return png.with_name(f"{png.stem}.plotly.json")


def save_plotly_json(fig: Any, png_path: str | Path) -> Path:
    out = plotly_json_path(png_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(fig.to_json())
    layout = payload.get("layout") or {}
    layout.pop("template", None)
    layout.pop("width", None)
    layout.pop("height", None)
    layout["autosize"] = True
    payload["layout"] = layout
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return out


def _base_layout(title: str, x_title: str, y_title: str) -> dict:
    return dict(
        title=dict(text=title),
        xaxis=dict(title=x_title),
        yaxis=dict(title=y_title),
        legend=dict(x=0, y=1, bgcolor="rgba(255,255,255,0.85)"),
        margin=dict(l=60, r=30, t=80, b=60),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )


def build_cosine_distribution_figure(
    cosines: np.ndarray,
    title: str,
    median: float,
) -> Any:
    import plotly.graph_objects as go

    counts, _ = np.histogram(cosines, bins=40)
    ymax = float(max(counts.max(), 1) * 1.15)

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=cosines,
            nbinsx=40,
            name="Cosine Similarity",
            marker=dict(color="#4c72b0", line=dict(color="white", width=0.5)),
            opacity=0.8,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[0.7, 0.7],
            y=[0, ymax],
            mode="lines",
            line=dict(color="#d62728", dash="dash", width=2),
            name="GNPS default threshold (0.7)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[median, median],
            y=[0, ymax],
            mode="lines",
            line=dict(color="#ff7f0e", dash="dot", width=2),
            name=f"Median ({median:.3f})",
        )
    )
    fig.update_layout(
        **_base_layout(
            title=(
                f"{title}<br>n={len(cosines):,} edges, "
                f"mean={float(np.mean(cosines)):.3f}, median={median:.3f}"
            ),
            x_title="Cosine Similarity",
            y_title="Frequency",
        )
    )
    return fig


def build_degree_distribution_figure(
    degrees: list[int],
    title: str,
    avg_deg: float,
    max_deg: int,
    isolated: int,
    n_nodes: int,
) -> Any:
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=degrees,
            name="Degree",
            marker=dict(color="#2ca02c", line=dict(color="white", width=0.5)),
            opacity=0.8,
        )
    )
    counts, _ = np.histogram(degrees, bins=min(30, max_deg + 1) if max_deg <= 20 else 30)
    ymax = float(max(counts.max(), 1) * 1.15)
    fig.add_trace(
        go.Scatter(
            x=[avg_deg, avg_deg],
            y=[0, ymax],
            mode="lines",
            line=dict(color="#d62728", dash="dash", width=2),
            name=f"Mean degree ({avg_deg:.1f})",
        )
    )
    fig.update_layout(
        **_base_layout(
            title=(
                f"{title}<br>n={n_nodes} nodes, mean={avg_deg:.2f}, "
                f"max={max_deg}, isolated={isolated}"
            ),
            x_title="Degree (number of connections)",
            y_title="Number of Nodes",
        )
    )
    return fig


def build_family_size_distribution_figure(
    labels: list[str],
    sizes: list[int],
    colors: list[str],
    title: str,
    n_families: int,
    n_singletons: int,
) -> Any:
    import plotly.graph_objects as go

    fig = go.Figure()
    for label, size, color in zip(labels, sizes, colors):
        fig.add_trace(
            go.Bar(
                x=[label],
                y=[size],
                name=label,
                marker=dict(color=color),
                showlegend=True,
                text=[str(size) if size > 0 else ""],
                textposition="outside",
            )
        )
    layout = _base_layout(
        title=f"{title}<br>({n_families} families, {n_singletons} singletons)",
        x_title="Molecular Family",
        y_title="Number of Nodes",
    )
    layout["xaxis"] = {**layout["xaxis"], "tickangle": -45}
    fig.update_layout(**layout, barmode="group")
    return fig


def build_pca_plsda_scatter_figure(
    scores: np.ndarray,
    groups: list[str],
    sample_names: list[str],
    title: str,
    *,
    x_idx: int = 0,
    y_idx: int = 1,
    axis_names: list[str] | None = None,
) -> Any:
    """Native Plotly PCA / PLS-DA score plot (clean JSON for web editor)."""
    import plotly.graph_objects as go

    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 2 or scores.shape[0] == 0:
        raise ValueError("scores must be a non-empty 2D array")

    ncol = scores.shape[1]
    x_idx = min(x_idx, ncol - 1)
    y_idx = min(y_idx, ncol - 1)
    if x_idx == y_idx and ncol >= 2:
        y_idx = 1

    axis_names = axis_names or [f"Comp{i + 1}" for i in range(ncol)]
    palette = ["#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F", "#8491B4"]

    fig = go.Figure()
    seen: set[str] = set()
    ordered_groups: list[str] = []
    for group in groups:
        g = str(group)
        if g not in seen:
            seen.add(g)
            ordered_groups.append(g)

    for i, group in enumerate(ordered_groups):
        mask = np.array([str(g) == group for g in groups], dtype=bool)
        xs = scores[mask, x_idx]
        ys = scores[mask, y_idx]
        labels = [sample_names[j] for j, m in enumerate(mask) if m]
        short_labels = [name.replace(".mzML", "").replace(".mzml", "") for name in labels]
        color = palette[i % len(palette)]

        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers+text",
                name=group,
                marker=dict(size=11, opacity=0.9, color=color, line=dict(color="white", width=1)),
                text=short_labels,
                textposition="top center",
                textfont=dict(size=10, color="#111827"),
                hovertemplate=(
                    "%{text}<br>"
                    f"{axis_names[x_idx]}: %{{x:.3f}}<br>"
                    f"{axis_names[y_idx]}: %{{y:.3f}}"
                    "<extra>%{fullData.name}</extra>"
                ),
            )
        )

    fig.update_layout(
        title=dict(text=title),
        xaxis=dict(
            title=axis_names[x_idx],
            showgrid=True,
            gridcolor="#ebebeb",
            zeroline=True,
            zerolinecolor="#cccccc",
        ),
        yaxis=dict(
            title=axis_names[y_idx],
            showgrid=True,
            gridcolor="#ebebeb",
            zeroline=True,
            zerolinecolor="#cccccc",
        ),
        autosize=True,
        margin=dict(l=60, r=30, t=70, b=60),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend=dict(title=dict(text="Group")),
    )
    return fig


def build_precursor_mass_diff_figure(
    mass_diffs: np.ndarray,
    title: str,
    annotated_transforms: list[tuple[str, float, int]],
) -> Any:
    """Native Plotly dual-panel precursor mass difference plot."""
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    mass_diffs = np.asarray(mass_diffs, dtype=float)
    if mass_diffs.size < 5:
        raise ValueError("not enough mass differences")

    median = float(np.median(mass_diffs))
    n_edges = int(mass_diffs.size)
    tab10 = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            f"Precursor Mass Differences<br>n={n_edges} edges, median={median:.2f} Da",
            "Annotated with Known Transformations",
        ),
        horizontal_spacing=0.08,
    )
    fig.add_trace(
        go.Histogram(
            x=mass_diffs,
            nbinsx=60,
            name="Δm/z",
            marker=dict(color="#4c72b0", line=dict(color="white", width=0.5)),
            opacity=0.8,
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Histogram(
            x=mass_diffs,
            nbinsx=80,
            name="Δm/z annotated",
            marker=dict(color="#888888", line=dict(color="white", width=0.3)),
            opacity=0.3,
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    counts, _ = np.histogram(mass_diffs, bins=80)
    y_max = float(max(counts.max(), 1))
    for i, (name, delta, count) in enumerate(annotated_transforms[:15]):
        color = tab10[i % len(tab10)]
        fig.add_vline(
            x=float(delta),
            line=dict(color=color, dash="dash", width=1.2),
            row=1,
            col=2,
        )
        fig.add_annotation(
            x=float(delta) + 8,
            y=y_max * max(0.12, 0.95 - i * 0.07),
            text=f"{name}<br>({delta:.1f} Da, n={count})",
            showarrow=True,
            arrowhead=2,
            arrowcolor=color,
            font=dict(size=9, color=color),
            xref="x2",
            yref="y2",
            ax=24,
            ay=0,
        )

    fig.update_xaxes(title_text="Δm/z (Da)", row=1, col=1)
    fig.update_xaxes(title_text="Δm/z (Da)", row=1, col=2)
    fig.update_yaxes(title_text="Frequency", row=1, col=1)
    fig.update_yaxes(title_text="Frequency", row=1, col=2)
    fig.update_layout(
        title=dict(text=title),
        autosize=True,
        margin=dict(l=60, r=30, t=90, b=60),
        paper_bgcolor="white",
        plot_bgcolor="white",
        bargap=0.05,
    )
    return fig


def maybe_save_plotly(fig: Any, png_path: str | Path) -> None:
    try:
        out = save_plotly_json(fig, png_path)
        print(f"    ✅ Plotly JSON: {out}")
    except Exception as exc:
        print(f"    ⚠️ Plotly JSON 未保存 ({png_path}): {exc}")


def maybe_save_plotly_from_matplotlib(fig: Any, png_path: str | Path) -> None:
    """Best-effort Matplotlib → Plotly JSON for the web editor."""
    try:
        from plotly.tools import mpl_to_plotly

        pfig = mpl_to_plotly(fig)
        maybe_save_plotly(pfig, png_path)
    except Exception as exc:
        print(f"    ⚠️ Plotly JSON (matplotlib) 未保存 ({png_path}): {exc}")
