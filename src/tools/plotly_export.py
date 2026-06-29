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
    out.write_text(fig.to_json(), encoding="utf-8")
    return out


def _base_layout(title: str, x_title: str, y_title: str) -> dict:
    return dict(
        title=dict(text=title),
        xaxis=dict(title=x_title),
        yaxis=dict(title=y_title),
        legend=dict(x=0, y=1, bgcolor="rgba(255,255,255,0.85)"),
        template="plotly_white",
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
