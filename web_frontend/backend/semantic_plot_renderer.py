"""Data-driven Vega-Lite rendering for semantically editable plots."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from web_frontend.backend.plot_renderer import _family_size_payload, load_scores_and_groups
from web_frontend.backend.plot_theme import DEFAULT_PALETTE, plot_config_path_for_png

VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"
FONT_FAMILY = "Noto Sans CJK SC, Noto Sans CJK, Arial, sans-serif"


def vega_config_path_for_png(png_path: str | Path) -> Path:
    png = Path(png_path)
    return png.with_name(f"{png.stem}.vl.json")


def svg_path_for_png(png_path: str | Path) -> Path:
    return Path(png_path).with_suffix(".svg")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _dimensions(plot_config: dict[str, Any]) -> tuple[int, int]:
    width, height = plot_config.get("figure_size") or [10.0, 8.0]
    return (
        max(360, min(1600, int(float(width) * 90))),
        max(280, min(1200, int(float(height) * 90))),
    )


def _axis(
    plot_config: dict[str, Any],
    axis_name: str,
    default_title: str,
    *,
    axis_type: str = "quantitative",
    zero: bool = False,
) -> dict[str, Any]:
    axes = plot_config.get("axes") or {}
    fs = plot_config.get("font_size") or {}
    title = axes.get(f"{axis_name}_title") or default_title
    scale: dict[str, Any] = {"zero": zero}
    lower = _finite(axes.get(f"{axis_name}_min"))
    upper = _finite(axes.get(f"{axis_name}_max"))
    if lower is not None:
        scale["domainMin"] = lower
    if upper is not None:
        scale["domainMax"] = upper
    result: dict[str, Any] = {
        "type": axis_type,
        "title": title,
        "axis": {
            "titleFontSize": fs.get("axis", 12),
            "labelFontSize": fs.get("axis", 12),
        },
    }
    if axis_type == "quantitative":
        result["scale"] = scale
    return result


def _legend(plot_config: dict[str, Any], *, title: str | None = None) -> dict[str, Any] | None:
    legend = plot_config.get("legend") or {}
    if not legend.get("show", True):
        return None
    fs = plot_config.get("font_size") or {}
    orient = legend.get("position", "right")
    return {
        "title": title,
        "orient": orient,
        "labelFontSize": fs.get("legend", 11),
        "titleFontSize": fs.get("legend", 11),
    }


def _title_block(plot_config: dict[str, Any]) -> dict[str, Any]:
    fs = plot_config.get("font_size") or {}
    align = plot_config.get("title_align", "center")
    anchor_map = {"left": "start", "center": "middle", "right": "end"}
    return {
        "text": plot_config.get("title", ""),
        "font": FONT_FAMILY,
        "fontSize": fs.get("title", 16),
        "fontWeight": "bold",
        "anchor": anchor_map.get(align, "middle"),
        "align": align if align in {"left", "center", "right"} else "center",
    }


def _base_spec(plot_config: dict[str, Any], values: list[dict[str, Any]]) -> dict[str, Any]:
    width, height = _dimensions(plot_config)
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "width": width,
        "height": height,
        "background": "white",
        "padding": 12,
        "title": _title_block(plot_config),
        "data": {"values": values},
        "config": {
            "font": FONT_FAMILY,
            "axis": {
                "labelFont": FONT_FAMILY,
                "titleFont": FONT_FAMILY,
                "gridColor": "#e5e7eb",
                "domainColor": "#6b7280",
            },
            "legend": {
                "labelFont": FONT_FAMILY,
                "titleFont": FONT_FAMILY,
            },
            "view": {"stroke": None},
        },
    }


def _score_spec(
    plot_type: str,
    data_dir: Path,
    metadata_csv: Path,
    plot_config: dict[str, Any],
) -> dict[str, Any]:
    scores_file = "pca_scores.csv" if plot_type == "pca" else "plsda_scores.csv"
    scores, groups, samples, axis_names = load_scores_and_groups(data_dir / scores_file, metadata_csv)
    x_index = max(0, min(scores.shape[1] - 1, int(plot_config["components"][0]) - 1))
    y_index = max(0, min(scores.shape[1] - 1, int(plot_config["components"][1]) - 1))
    if x_index == y_index and scores.shape[1] > 1:
        y_index = 1 if x_index != 1 else 0
    values = [
        {
            "x": float(scores[i, x_index]),
            "y": float(scores[i, y_index]),
            "group": str(groups[i]),
            "sample": str(samples[i]).replace(".mzML", "").replace(".mzml", ""),
        }
        for i in range(len(samples))
    ]
    ordered_groups = list(dict.fromkeys(str(group) for group in groups))
    palette = plot_config.get("palette") or {}
    colors = [palette.get(group, DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)]) for i, group in enumerate(ordered_groups)]
    marks = plot_config.get("marks") or {}
    point_encoding = {
        "x": {"field": "x", **_axis(plot_config, "x", axis_names[x_index])},
        "y": {"field": "y", **_axis(plot_config, "y", axis_names[y_index])},
        "color": {
            "field": "group",
            "type": "nominal",
            "scale": {"domain": ordered_groups, "range": colors},
            "legend": _legend(plot_config, title="Group"),
        },
        "tooltip": [
            {"field": "sample", "type": "nominal", "title": "Sample"},
            {"field": "group", "type": "nominal", "title": "Group"},
            {"field": "x", "type": "quantitative", "format": ".4g"},
            {"field": "y", "type": "quantitative", "format": ".4g"},
        ],
    }
    layers: list[dict[str, Any]] = [
        {
            "mark": {
                "type": "point",
                "filled": True,
                "size": marks.get("size", 70),
                "opacity": marks.get("opacity", 0.85),
                "stroke": "white",
                "strokeWidth": 0.8,
            },
            "encoding": point_encoding,
        }
    ]
    if plot_config.get("show_sample_labels", True):
        layers.append(
            {
                "mark": {
                    "type": "text",
                    "dy": -9,
                    "font": FONT_FAMILY,
                    "fontSize": (plot_config.get("font_size") or {}).get("label", 10),
                },
                "encoding": {
                    "x": {"field": "x", "type": "quantitative"},
                    "y": {"field": "y", "type": "quantitative"},
                    "text": {"field": "sample", "type": "nominal"},
                },
            }
        )
    spec = _base_spec(plot_config, values)
    spec["layer"] = layers
    return spec


def _volcano_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    frame = pd.read_csv(data_dir / "volcano_results.csv")
    required = {"log2FC", "neglog10p"}
    if not required.issubset(frame.columns):
        raise ValueError("volcano_results.csv 缺少 log2FC / neglog10p 列")
    significant = (
        frame["Significant"].astype(bool)
        if "Significant" in frame.columns
        else pd.Series([True] * len(frame))
    )
    values = []
    for index, row in frame.iterrows():
        x = _finite(row["log2FC"])
        y = _finite(row["neglog10p"])
        if x is None or y is None:
            continue
        values.append(
            {
                "x": x,
                "y": y,
                "status": "Significant" if bool(significant.iloc[index]) else "Non-significant",
            }
        )
    colors = plot_config.get("colors") or {}
    marks = plot_config.get("marks") or {}
    spec = _base_spec(plot_config, values)
    spec["mark"] = {
        "type": "point",
        "filled": True,
        "size": marks.get("size", 70),
        "opacity": marks.get("opacity", 0.85),
    }
    spec["encoding"] = {
        "x": {"field": "x", **_axis(plot_config, "x", "log2 Fold Change")},
        "y": {"field": "y", **_axis(plot_config, "y", "-log10(p-value)")},
        "color": {
            "field": "status",
            "type": "nominal",
            "scale": {
                "domain": ["Significant", "Non-significant"],
                "range": [
                    colors.get("significant", "#E64B35"),
                    colors.get("nonsignificant", "#B0B0B0"),
                ],
            },
            "legend": _legend(plot_config, title=None),
        },
        "tooltip": [
            {"field": "x", "type": "quantitative", "format": ".4g"},
            {"field": "y", "type": "quantitative", "format": ".4g"},
            {"field": "status", "type": "nominal"},
        ],
    }
    return spec


def _family_size_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    labels, sizes, defaults = _family_size_payload(data_dir / "network_nodes.csv")
    palette = plot_config.get("palette") or {}
    values = [
        {"family": label, "count": int(size), "color": palette.get(label, defaults[i]), "order": i}
        for i, (label, size) in enumerate(zip(labels, sizes))
    ]
    spec = _base_spec(plot_config, values)
    spec["layer"] = [
        {
            "mark": {"type": "bar", "opacity": (plot_config.get("marks") or {}).get("opacity", 0.85)},
            "encoding": {
                "x": {
                    "field": "family",
                    **_axis(plot_config, "x", "Molecular Family", axis_type="nominal"),
                    "sort": {"field": "order", "order": "ascending"},
                    "axis": {
                        "titleFontSize": (plot_config.get("font_size") or {}).get("axis", 12),
                        "labelFontSize": (plot_config.get("font_size") or {}).get("label", 10),
                        "labelAngle": -45,
                    },
                },
                "y": {"field": "count", **_axis(plot_config, "y", "Number of Nodes", zero=True)},
                "color": {"field": "color", "type": "nominal", "scale": None, "legend": None},
                "tooltip": [
                    {"field": "family", "type": "nominal"},
                    {"field": "count", "type": "quantitative"},
                ],
            },
        },
        {
            "mark": {
                "type": "text",
                "dy": -5,
                "font": FONT_FAMILY,
                "fontSize": (plot_config.get("font_size") or {}).get("label", 10),
            },
            "encoding": {
                "x": {"field": "family", "type": "nominal", "sort": {"field": "order"}},
                "y": {"field": "count", "type": "quantitative"},
                "text": {"field": "count", "type": "quantitative"},
            },
        },
    ]
    return spec


def _histogram_spec(
    plot_type: str,
    data_dir: Path,
    plot_config: dict[str, Any],
) -> dict[str, Any]:
    if plot_type == "degree_hist":
        frame = pd.read_csv(data_dir / "network_nodes.csv")
        raw = frame["degree"] if "degree" in frame.columns else pd.Series([1] * len(frame))
        values_array = raw.dropna().astype(float).tolist()
        x_title, y_title = "Degree", "Number of Nodes"
        rules = [("Mean", float(np.mean(values_array)) if values_array else 0.0, "threshold_color")]
    else:
        frame = pd.read_csv(data_dir / "network_edges.csv")
        if "cosine" not in frame.columns:
            raise ValueError("network_edges.csv 缺少 cosine 列")
        values_array = frame["cosine"].dropna().astype(float).tolist()
        x_title, y_title = "Cosine Similarity", "Number of Edges"
        rules = [
            ("Threshold", 0.7, "threshold_color"),
            ("Median", float(np.median(values_array)) if values_array else 0.0, "median_color"),
        ]
    values = [{"value": value} for value in values_array if _finite(value) is not None]
    colors = plot_config.get("colors") or {}
    bins = (plot_config.get("histogram") or {}).get("bins", 40)
    layers: list[dict[str, Any]] = [
        {
            "mark": {
                "type": "bar",
                "color": colors.get("histogram_color", "#4c72b0"),
                "opacity": (plot_config.get("marks") or {}).get("opacity", 0.85),
            },
            "encoding": {
                "x": {
                    "field": "value",
                    "bin": {"maxbins": bins},
                    **_axis(plot_config, "x", x_title),
                },
                "y": {
                    "aggregate": "count",
                    **_axis(plot_config, "y", y_title, zero=True),
                },
                "tooltip": [{"aggregate": "count", "type": "quantitative", "title": "Count"}],
            },
        }
    ]
    for label, value, color_key in rules:
        layers.append(
            {
                "data": {"values": [{"rule": value, "label": f"{label} ({value:.2f})"}]},
                "mark": {
                    "type": "rule",
                    "strokeDash": [6, 4],
                    "strokeWidth": 2,
                    "color": colors.get(color_key, "#d62728"),
                },
                "encoding": {
                    "x": {"field": "rule", "type": "quantitative"},
                    "tooltip": [{"field": "label", "type": "nominal"}],
                },
            }
        )
    spec = _base_spec(plot_config, values)
    spec["layer"] = layers
    return spec


def build_vegalite_spec(
    *,
    plot_type: str,
    data_dir: str | Path,
    metadata_csv: str | Path | None,
    plot_config: dict[str, Any],
) -> dict[str, Any]:
    """Build a self-contained Vega-Lite spec from source data and plot config."""
    data_path = Path(data_dir)
    if plot_type in {"pca", "plsda"}:
        if metadata_csv is None:
            raise ValueError("PCA/PLS-DA 缺少 metadata.csv")
        return _score_spec(plot_type, data_path, Path(metadata_csv), plot_config)
    if plot_type == "volcano":
        return _volcano_spec(data_path, plot_config)
    if plot_type == "family_size":
        return _family_size_spec(data_path, plot_config)
    if plot_type in {"degree_hist", "cosine_hist"}:
        return _histogram_spec(plot_type, data_path, plot_config)
    raise ValueError(f"暂不支持语义渲染: {plot_type}")


def write_semantic_metadata_files(
    *,
    png_path: str | Path,
    plot_config: dict[str, Any],
    vega_spec: dict[str, Any],
    instruction: str | None = None,
    source_rel: str | None = None,
) -> tuple[Path, Path]:
    """Persist plot_config and Vega-Lite sidecars without raster export."""
    png = Path(png_path)
    png.parent.mkdir(parents=True, exist_ok=True)
    config_path = Path(plot_config_path_for_png(str(png)))
    vega_path = vega_config_path_for_png(png)

    payload = dict(plot_config)
    if instruction:
        payload["last_instruction"] = instruction
    if source_rel:
        payload["source_rel"] = source_rel

    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    vega_path.write_text(json.dumps(vega_spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_path, vega_path


def is_vl_convert_available() -> bool:
    try:
        import vl_convert as vlc  # noqa: F401
    except ImportError:
        return False
    return True


def write_semantic_outputs(
    *,
    png_path: str | Path,
    plot_config: dict[str, Any],
    vega_spec: dict[str, Any],
    instruction: str | None = None,
    source_rel: str | None = None,
    png_renderer: Any | None = None,
) -> tuple[Path, Path, Path | None, Path]:
    """Write plot config, Vega-Lite JSON, SVG and PNG from one semantic spec."""
    png = Path(png_path)
    config_path, vega_path = write_semantic_metadata_files(
        png_path=png,
        plot_config=plot_config,
        vega_spec=vega_spec,
        instruction=instruction,
        source_rel=source_rel,
    )
    svg_path = svg_path_for_png(png)

    try:
        import vl_convert as vlc

        spec_json = json.dumps(vega_spec, ensure_ascii=False, allow_nan=False)
        svg_text = vlc.vegalite_to_svg(spec_json)
        png_bytes = vlc.vegalite_to_png(spec_json, scale=2)
        svg_path.write_text(svg_text, encoding="utf-8")
        png.write_bytes(png_bytes)
        return config_path, vega_path, svg_path, png
    except ImportError as exc:
        if png_renderer is None:
            raise RuntimeError("缺少 vl-convert-python，无法导出语义图表") from exc
    except Exception as exc:
        if png_renderer is None:
            raise RuntimeError(f"语义图表导出失败: {exc}") from exc

    if png_renderer is None:
        raise RuntimeError("缺少 vl-convert-python，无法导出语义图表")

    png_renderer(png)
    return config_path, vega_path, None, png
