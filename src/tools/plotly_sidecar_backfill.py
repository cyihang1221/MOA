"""Backfill missing .plotly.json sidecars for existing PNG outputs."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from src.platform_utils import resolve_rscript
from src.tools.plotly_export import plotly_json_path


def _missing_plotly_sidecars(directory: str | Path) -> list[Path]:
    root = Path(directory)
    if not root.is_dir():
        return []
    missing: list[Path] = []
    for png in sorted(root.glob("*.png")):
        if not plotly_json_path(png).is_file():
            missing.append(png)
    return missing


def backfill_statistical_plotly_sidecars(
    output_dir: str | Path,
    metadata_csv: str | Path,
) -> list[Path]:
    """Create Plotly JSON for statistical PNGs using existing CSV outputs."""
    out = Path(output_dir).resolve()
    meta = Path(metadata_csv).resolve()
    missing = _missing_plotly_sidecars(out)
    if not missing or not meta.is_file():
        return []

    tools_dir = Path(__file__).resolve().parent
    r_helpers = tools_dir / "r_plotly_export.R"
    pca_scores = out / "pca_scores.csv"
    volcano_csv = out / "volcano_results.csv"

    rscript = resolve_rscript()
    script = f"""
source("{r_helpers.as_posix()}", local = FALSE, encoding = "UTF-8")
library(readr)
outdir <- "{out.as_posix()}"
metadata <- read_csv("{meta.as_posix()}", show_col_types = FALSE)
Y <- factor(metadata$Group[match(metadata$Sample, metadata$Sample)])

if (file.exists(file.path(outdir, "pca_scores.csv")) &&
    file.exists(file.path(outdir, "pca_plot.png")) &&
    !file.exists(file.path(outdir, "pca_plot.plotly.json"))) {{
  scores <- as.matrix(read.csv(file.path(outdir, "pca_scores.csv"), row.names = 1, check.names = FALSE))
  groups <- metadata$Group[match(rownames(scores), metadata$Sample)]
  comps <- if (ncol(scores) >= 2) c(1, 2) else c(1, 1)
  try(save_pca_plsda_plotly_sidecar(scores, groups, file.path(outdir, "pca_plot.png"), "PCA", comps), silent = TRUE)
}}

if (file.exists(file.path(outdir, "plsda_scores.csv")) &&
    file.exists(file.path(outdir, "plsda_plot.png")) &&
    !file.exists(file.path(outdir, "plsda_plot.plotly.json"))) {{
  scores <- as.matrix(read.csv(file.path(outdir, "plsda_scores.csv"), row.names = 1, check.names = FALSE))
  groups <- metadata$Group[match(rownames(scores), metadata$Sample)]
  comps <- if (ncol(scores) >= 2) c(1, 2) else c(1, 1)
  try(save_pca_plsda_plotly_sidecar(scores, groups, file.path(outdir, "plsda_plot.png"), "PLS-DA", comps), silent = TRUE)
}}

if (file.exists(file.path(outdir, "volcano_results.csv")) &&
    file.exists(file.path(outdir, "volcano_plot.png")) &&
    !file.exists(file.path(outdir, "volcano_plot.plotly.json"))) {{
  library(ggplot2)
  volcano_df <- read.csv(file.path(outdir, "volcano_results.csv"), check.names = FALSE)
  if (!"Significant" %in% colnames(volcano_df)) {{
    volcano_df$Significant <- !is.na(volcano_df$pvalue) & abs(volcano_df$log2FC) >= 0.58
  }}
  p <- ggplot(volcano_df, aes(x = log2FC, y = neglog10p, color = Significant)) +
    geom_point(size = 1.5) +
    theme_bw() +
    ggtitle("Volcano Plot")
  try(save_ggplot_plotly_sidecar(p, file.path(outdir, "volcano_plot.png")), silent = TRUE)
}}
"""
    if not pca_scores.is_file() and not volcano_csv.is_file():
        return []

    proc = subprocess.run(
        [rscript, "--encoding=UTF-8", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0 and proc.stderr:
        print(f"    ⚠️ Plotly sidecar backfill (statistical): {proc.stderr[:500]}")

    created = [plotly_json_path(p) for p in missing if plotly_json_path(p).is_file()]
    for path in created:
        print(f"    ✅ Plotly JSON (backfill): {path}")
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
    """Re-run standard network plot exporters for PNGs missing .plotly.json."""
    out = Path(output_dir).resolve()
    if not out.is_dir():
        return []

    missing_before = _missing_plotly_sidecars(out)
    if not missing_before:
        return []

    graphml = out / "molecular_network.graphml"
    edges_csv = out / "network_edges.csv"
    if not graphml.is_file() or not edges_csv.is_file():
        return []

    import networkx as nx
    import pandas as pd

    from src.tools.molecular_networking import (
        _plot_cosine_distribution,
        _plot_degree_distribution,
        _plot_family_size_distribution,
        _plot_network_topology,
        _plot_precursor_mass_difference,
    )

    G = nx.read_graphml(graphml)
    edges_df = pd.read_csv(edges_csv)
    prefix = title_prefix or "GNPS"
    targets = {p.name for p in missing_before}

    if G.number_of_nodes() > 0:
        if "network_topology.png" in targets:
            _plot_network_topology(
                G,
                output_path=str(out / "network_topology.png"),
                title=f"{prefix} — Network Topology",
                color_by=color_by,
            )
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
            if "precursor_mass_diff.png" in targets:
                _plot_precursor_mass_difference(
                    G,
                    output_path=str(out / "precursor_mass_diff.png"),
                    title=f"{prefix} — Precursor Mass Differences",
                )

    if len(edges_df) > 0 and "cosine" in edges_df.columns:
        if "cosine_distribution.png" in targets:
            _plot_cosine_distribution(
                edges_df,
                output_path=str(out / "cosine_distribution.png"),
                title=f"{prefix} — Cosine Similarity Distribution",
            )

    created = [
        plotly_json_path(p)
        for p in missing_before
        if plotly_json_path(p).is_file()
    ]
    for path in created:
        print(f"    ✅ Plotly JSON (backfill): {path}")
    return created
