"""Backfill missing .plotly.json sidecars for existing PNG outputs."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from src.platform_utils import resolve_rscript
from src.tools.plotly_export import (
    build_pca_plsda_scatter_figure,
    build_precursor_mass_diff_figure,
    maybe_save_plotly,
    plotly_json_path,
)

_NATIVE_PLOTLY_STEMS = frozenset({
    "pca_plot",
    "plsda_plot",
    "precursor_mass_diff",
})


def _missing_plotly_sidecars(directory: str | Path) -> list[Path]:
    root = Path(directory)
    if not root.is_dir():
        return []
    missing: list[Path] = []
    for png in sorted(root.glob("*.png")):
        if not plotly_json_path(png).is_file():
            missing.append(png)
    return missing


def _rewrite_native_plotly_sidecars(directory: str | Path) -> list[Path]:
    """Force-regenerate sidecars that should use native Plotly builders."""
    root = Path(directory)
    rewritten: list[Path] = []
    for png in sorted(root.glob("*.png")):
        if png.stem in _NATIVE_PLOTLY_STEMS and plotly_json_path(png).is_file():
            plotly_json_path(png).unlink(missing_ok=True)
            rewritten.append(png)
    return rewritten


def _write_pca_sidecar(
    out: Path,
    meta: Path,
    *,
    scores_name: str,
    png_name: str,
    title: str,
) -> Path | None:
    scores_path = out / scores_name
    png_path = out / png_name
    if not scores_path.is_file() or not png_path.is_file():
        return None

    df = pd.read_csv(scores_path, index_col=0)
    if df.empty:
        return None

    meta_df = pd.read_csv(meta)
    group_map = meta_df.set_index("Sample")["Group"].astype(str).to_dict()
    samples = df.index.astype(str).tolist()
    groups = [group_map.get(sample, "Unknown") for sample in samples]
    y_idx = 1 if df.shape[1] >= 2 else 0

    fig = build_pca_plsda_scatter_figure(
        scores=df.to_numpy(dtype=float),
        groups=groups,
        sample_names=samples,
        title=title,
        x_idx=0,
        y_idx=y_idx,
        axis_names=df.columns.astype(str).tolist(),
    )
    maybe_save_plotly(fig, png_path)
    return plotly_json_path(png_path)


def backfill_statistical_plotly_sidecars(
    output_dir: str | Path,
    metadata_csv: str | Path,
) -> list[Path]:
    """Create Plotly JSON for statistical PNGs using existing CSV outputs."""
    out = Path(output_dir).resolve()
    meta = Path(metadata_csv).resolve()
    if not out.is_dir() or not meta.is_file():
        return []

    _rewrite_native_plotly_sidecars(out)
    missing = _missing_plotly_sidecars(out)
    created: list[Path] = []

    for path in (
        _write_pca_sidecar(out, meta, scores_name="pca_scores.csv", png_name="pca_plot.png", title="PCA"),
        _write_pca_sidecar(
            out,
            meta,
            scores_name="plsda_scores.csv",
            png_name="plsda_plot.png",
            title="PLS-DA",
        ),
    ):
        if path and path.is_file():
            created.append(path)

    volcano_csv = out / "volcano_results.csv"
    volcano_png = out / "volcano_plot.png"
    if (
        volcano_csv.is_file()
        and volcano_png.is_file()
        and not plotly_json_path(volcano_png).is_file()
    ):
        tools_dir = Path(__file__).resolve().parent
        r_helpers = tools_dir / "r_plotly_export.R"
        rscript = resolve_rscript()
        script = f"""
source("{r_helpers.as_posix()}", local = FALSE, encoding = "UTF-8")
library(ggplot2)
outdir <- "{out.as_posix()}"
volcano_df <- read.csv(file.path(outdir, "volcano_results.csv"), check.names = FALSE)
if (!"Significant" %in% colnames(volcano_df)) {{
  volcano_df$Significant <- !is.na(volcano_df$pvalue) & abs(volcano_df$log2FC) >= 0.58
}}
p <- ggplot(volcano_df, aes(x = log2FC, y = neglog10p, color = Significant)) +
  geom_point(size = 1.5) +
  theme_bw() +
  ggtitle("Volcano Plot")
try(save_ggplot_plotly_sidecar(p, file.path(outdir, "volcano_plot.png")), silent = TRUE)
"""
        proc = subprocess.run(
            [rscript, "--encoding=UTF-8", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0 and proc.stderr:
            print(f"    ⚠️ Plotly sidecar backfill (volcano): {proc.stderr[:500]}")
        sidecar = plotly_json_path(volcano_png)
        if sidecar.is_file():
            created.append(sidecar)

    for path in created:
        print(f"    ✅ Plotly JSON (backfill): {path}")

    for png in missing:
        sidecar = plotly_json_path(png)
        if sidecar.is_file() and sidecar not in created:
            created.append(sidecar)
    return created


def backfill_png_directory_plotly_sidecars(directory: str | Path) -> list[Path]:
    """List PNG files in a directory that still lack Plotly sidecars."""
    return _missing_plotly_sidecars(directory)


def backfill_molecular_network_plotly_sidecars(
    output_dir: str | Path,
    *,
    title_prefix: str = "GNPS",
    color_by: str = "molecular_family",
) -> list[Path]:
    """Re-run network plot exporters for PNGs missing native Plotly sidecars."""
    out = Path(output_dir).resolve()
    if not out.is_dir():
        return []

    _rewrite_native_plotly_sidecars(out)
    topology_sidecar = out / "network_topology.plotly.json"
    if topology_sidecar.is_file():
        topology_sidecar.unlink()

    missing_before = _missing_plotly_sidecars(out)
    if not missing_before:
        return []

    graphml = out / "molecular_network.graphml"
    edges_csv = out / "network_edges.csv"
    if not graphml.is_file() or not edges_csv.is_file():
        return []

    import networkx as nx

    from src.tools.molecular_networking import (
        _plot_cosine_distribution,
        _plot_degree_distribution,
        _plot_family_size_distribution,
        _precursor_mass_diff_payload,
        _plot_precursor_mass_difference,
    )

    G = nx.read_graphml(graphml)
    edges_df = pd.read_csv(edges_csv)
    prefix = title_prefix or "GNPS"
    targets = {p.name for p in missing_before}
    created: list[Path] = []

    if G.number_of_nodes() > 0:
        if "family_size_distribution.png" in targets:
            _plot_family_size_distribution(
                G,
                output_path=str(out / "family_size_distribution.png"),
                title=f"{prefix} — Molecular Family Size Distribution",
                color_by=color_by,
            )
        if G.number_of_edges() > 0:
            if "degree_distribution.png" in targets:
                _plot_degree_distribution(
                    G,
                    output_path=str(out / "degree_distribution.png"),
                    title=f"{prefix} — Node Degree Distribution",
                )
            precursor_png = out / "precursor_mass_diff.png"
            if precursor_png.is_file() and (
                "precursor_mass_diff.png" in targets
                or precursor_png.stem in _NATIVE_PLOTLY_STEMS
            ):
                payload = _precursor_mass_diff_payload(G)
                if payload is not None:
                    mass_diffs, transforms = payload
                    try:
                        fig = build_precursor_mass_diff_figure(
                            mass_diffs=np.asarray(mass_diffs, dtype=float),
                            title=f"{prefix} — Precursor Mass Differences",
                            annotated_transforms=transforms,
                        )
                        maybe_save_plotly(fig, precursor_png)
                    except Exception as exc:
                        print(f"    ⚠️ Plotly sidecar (precursor): {exc}")
                elif "precursor_mass_diff.png" in targets:
                    _plot_precursor_mass_difference(
                        G,
                        output_path=str(precursor_png),
                        title=f"{prefix} — Precursor Mass Differences",
                    )

    if len(edges_df) > 0 and "cosine" in edges_df.columns:
        if "cosine_distribution.png" in targets:
            _plot_cosine_distribution(
                edges_df,
                output_path=str(out / "cosine_distribution.png"),
                title=f"{prefix} — Cosine Similarity Distribution",
            )

    for png in missing_before:
        sidecar = plotly_json_path(png)
        if sidecar.is_file():
            created.append(sidecar)
            print(f"    ✅ Plotly JSON (backfill): {sidecar}")
    return created
