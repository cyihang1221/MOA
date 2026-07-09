"""作图主题与 plot_config 结构（Web Agent 改图闭环）。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from web_frontend.backend.plot_edit_registry import (
    agent_editable_stems,
    get_plot_spec,
    plot_type_from_stem,
)

DEFAULT_PALETTE = [
    "#E64B35",
    "#4DBBD5",
    "#00A087",
    "#3C5488",
    "#F39B7F",
    "#8491B4",
]

AGENT_EDITABLE_STEMS = agent_editable_stems()

DEFAULT_FONT_SIZES = {
    "title": 16,
    "axis": 12,
    "legend": 11,
    "label": 10,
}

DEFAULT_FIGURE_SIZE = [10.0, 8.0]

DEFAULT_COLORS = {
    "histogram_color": "#4c72b0",
    "threshold_color": "#d62728",
    "median_color": "#ff7f0e",
    "significant": "#E64B35",
    "nonsignificant": "#B0B0B0",
}


def scores_filename(plot_type: str) -> str:
    if plot_type == "pca":
        return "pca_scores.csv"
    if plot_type == "plsda":
        return "plsda_scores.csv"
    return ""


def default_title(plot_type: str) -> str:
    spec = get_plot_spec(plot_type)
    return spec.default_title if spec else plot_type


def plot_config_path_for_png(png_path: str) -> str:
    from pathlib import Path

    p = Path(png_path)
    return str(p.with_name(f"{p.stem}.plot_config.json"))


def echarts_config_path_for_png(png_path: str) -> str:
    from pathlib import Path

    p = Path(png_path)
    return str(p.with_name(f"{p.stem}.echarts.json"))


def normalize_plot_config(
    raw: dict[str, Any] | None,
    *,
    plot_type: str,
    color_keys: list[str] | None = None,
) -> dict[str, Any]:
    """合并默认值与用户/Agent 提供的 plot_config。"""
    color_keys = color_keys or []
    palette_in = (raw or {}).get("palette") if isinstance(raw, dict) else None
    palette: dict[str, str] = {}
    if isinstance(palette_in, dict):
        for key, val in palette_in.items():
            if isinstance(val, str) and val.strip():
                palette[str(key)] = val.strip()

    for i, key in enumerate(color_keys):
        palette.setdefault(str(key), DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)])

    colors = dict(DEFAULT_COLORS)
    colors_in = (raw or {}).get("colors") if isinstance(raw, dict) else None
    if isinstance(colors_in, dict):
        for key, val in colors_in.items():
            if isinstance(val, str) and val.strip():
                colors[str(key)] = val.strip()

    font_in = (raw or {}).get("font_size") if isinstance(raw, dict) else None
    font_size = dict(DEFAULT_FONT_SIZES)
    if isinstance(font_in, dict):
        for key in font_size:
            val = font_in.get(key)
            if isinstance(val, (int, float)) and val > 0:
                font_size[key] = int(val)

    figsize_in = (raw or {}).get("figure_size") if isinstance(raw, dict) else None
    figure_size = list(DEFAULT_FIGURE_SIZE)
    if (
        isinstance(figsize_in, (list, tuple))
        and len(figsize_in) >= 2
        and float(figsize_in[0]) > 0
        and float(figsize_in[1]) > 0
    ):
        figure_size = [float(figsize_in[0]), float(figsize_in[1])]

    components = [1, 2]
    comp_in = (raw or {}).get("components") if isinstance(raw, dict) else None
    if isinstance(comp_in, (list, tuple)) and len(comp_in) >= 2:
        try:
            components = [int(comp_in[0]), int(comp_in[1])]
        except (TypeError, ValueError):
            pass

    title = default_title(plot_type)
    if isinstance(raw, dict) and isinstance(raw.get("title"), str) and raw["title"].strip():
        title = raw["title"].strip()

    show_labels = True
    if isinstance(raw, dict) and "show_sample_labels" in raw:
        show_labels = bool(raw["show_sample_labels"])

    return {
        "version": 1,
        "plot_type": plot_type,
        "title": title,
        "palette": palette,
        "colors": colors,
        "font_size": font_size,
        "figure_size": figure_size,
        "components": components,
        "show_sample_labels": show_labels,
    }


def merge_plot_config(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    if not patch:
        return merged
    if isinstance(patch.get("title"), str) and patch["title"].strip():
        merged["title"] = patch["title"].strip()
    if isinstance(patch.get("palette"), dict):
        merged.setdefault("palette", {})
        for key, val in patch["palette"].items():
            if isinstance(val, str) and val.strip():
                merged["palette"][str(key)] = val.strip()
    if isinstance(patch.get("colors"), dict):
        merged.setdefault("colors", dict(DEFAULT_COLORS))
        for key, val in patch["colors"].items():
            if isinstance(val, str) and val.strip():
                merged["colors"][str(key)] = val.strip()
    if isinstance(patch.get("font_size"), dict):
        merged.setdefault("font_size", dict(DEFAULT_FONT_SIZES))
        for key, val in patch["font_size"].items():
            if isinstance(val, (int, float)) and val > 0:
                merged["font_size"][str(key)] = int(val)
    if isinstance(patch.get("figure_size"), (list, tuple)) and len(patch["figure_size"]) >= 2:
        merged["figure_size"] = [float(patch["figure_size"][0]), float(patch["figure_size"][1])]
    if isinstance(patch.get("components"), (list, tuple)) and len(patch["components"]) >= 2:
        merged["components"] = [int(patch["components"][0]), int(patch["components"][1])]
    if "show_sample_labels" in patch:
        merged["show_sample_labels"] = bool(patch["show_sample_labels"])
    return merged
