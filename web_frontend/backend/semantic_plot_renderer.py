"""Data-driven Vega-Lite rendering for semantically editable plots."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from web_frontend.backend.plot_edit_registry import resolve_plot_data_file
from web_frontend.backend.plot_renderer import _family_size_payload, load_scores_and_groups
from web_frontend.backend.plot_theme import DEFAULT_PALETTE, plot_config_path_for_png, resolve_volcano_thresholds

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
    from web_frontend.backend.plot_renderer import score_color_meta

    scores_file = "pca_scores.csv" if plot_type == "pca" else "plsda_scores.csv"
    scores, groups, samples, axis_names = load_scores_and_groups(
        data_dir / scores_file,
        metadata_csv,
        plot_config=plot_config,
    )
    x_index = max(0, min(scores.shape[1] - 1, int(plot_config["components"][0]) - 1))
    y_index = max(0, min(scores.shape[1] - 1, int(plot_config["components"][1]) - 1))
    if x_index == y_index and scores.shape[1] > 1:
        y_index = 1 if x_index != 1 else 0
    legend_title, color_type = score_color_meta(plot_config)
    values = []
    for i in range(len(samples)):
        row: dict[str, Any] = {
            "x": float(scores[i, x_index]),
            "y": float(scores[i, y_index]),
            "sample": str(samples[i]).replace(".mzML", "").replace(".mzml", ""),
        }
        if color_type == "quantitative":
            try:
                row["color_value"] = float(groups[i])
            except (TypeError, ValueError):
                row["color_value"] = None
        else:
            row["group"] = str(groups[i])
        values.append(row)

    marks = plot_config.get("marks") or {}
    if color_type == "quantitative":
        color_encoding: dict[str, Any] = {
            "field": "color_value",
            "type": "quantitative",
            "scale": {"scheme": "viridis"},
            "legend": _legend(plot_config, title=legend_title),
        }
        tooltip = [
            {"field": "sample", "type": "nominal", "title": "Sample"},
            {"field": "color_value", "type": "quantitative", "title": legend_title, "format": ".4g"},
            {"field": "x", "type": "quantitative", "format": ".4g"},
            {"field": "y", "type": "quantitative", "format": ".4g"},
        ]
    else:
        ordered_groups = list(dict.fromkeys(str(group) for group in groups))
        palette = plot_config.get("palette") or {}
        colors = [
            palette.get(group, DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)])
            for i, group in enumerate(ordered_groups)
        ]
        color_encoding = {
            "field": "group",
            "type": "nominal",
            "scale": {"domain": ordered_groups, "range": colors},
            "legend": _legend(plot_config, title=legend_title),
        }
        tooltip = [
            {"field": "sample", "type": "nominal", "title": "Sample"},
            {"field": "group", "type": "nominal", "title": legend_title},
            {"field": "x", "type": "quantitative", "format": ".4g"},
            {"field": "y", "type": "quantitative", "format": ".4g"},
        ]

    point_encoding = {
        "x": {"field": "x", **_axis(plot_config, "x", axis_names[x_index])},
        "y": {"field": "y", **_axis(plot_config, "y", axis_names[y_index])},
        "color": color_encoding,
        "tooltip": tooltip,
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

    thr = resolve_volcano_thresholds(plot_config)
    p_cut = float(thr["p"]) if thr.get("p") is not None else None
    if thr.get("padj") is not None and p_cut is None:
        p_cut = float(thr["padj"])
    fc_cut = float(thr["log2fc"]) if thr.get("log2fc") is not None else None
    channel = str(plot_config.get("color_channel") or "").strip()
    color_type = str(plot_config.get("color_type") or "nominal")

    values = []
    for _, row in frame.iterrows():
        x = _finite(row["log2FC"])
        y = _finite(row["neglog10p"])
        if x is None or y is None:
            continue
        # 按阈值重算显著性。用户指定的是 p 值时应优先使用原始
        # pvalue；此前优先 padj 会把部分下调点错误归为不显著。
        if p_cut is not None or fc_cut is not None:
            p_ok = True
            fc_ok = True
            if p_cut is not None:
                if "pvalue" in frame.columns and pd.notna(row.get("pvalue")):
                    p_ok = float(row["pvalue"]) < p_cut
                elif "padj" in frame.columns and pd.notna(row.get("padj")):
                    p_ok = float(row["padj"]) < p_cut
                else:
                    p_ok = y >= -np.log10(max(p_cut, 1e-300))
            if fc_cut is not None:
                fc_ok = abs(x) >= fc_cut
            is_sig = bool(p_ok and fc_ok)
        elif "Significant" in frame.columns:
            is_sig = bool(row["Significant"])
        else:
            is_sig = True
        if is_sig:
            status = "Upregulated" if x > 0 else "Downregulated"
        else:
            status = "Not significant"
        item: dict[str, Any] = {
            "x": x,
            "y": y,
            "status": status,
            "log2FC": x,
            "neglog10p": y,
        }
        values.append(item)

    colors = plot_config.get("colors") or {}
    marks = plot_config.get("marks") or {}
    spec = _base_spec(plot_config, values)
    point_mark = {
        "type": "point",
        "filled": True,
        "size": marks.get("size", 70),
        "opacity": marks.get("opacity", 0.85),
    }
    use_quant = color_type == "quantitative" or channel in {"log2FC", "neglog10p", "log2fc"}
    if use_quant:
        field = "neglog10p" if channel in {"neglog10p", "neglog10", ""} else "log2FC"
        if channel in {"log2FC", "log2fc", "fc"}:
            field = "log2FC"
        elif channel in {"neglog10p", "neglog10"}:
            field = "neglog10p"
        point_encoding = {
            "x": {"field": "x", **_axis(plot_config, "x", "log2 Fold Change")},
            "y": {"field": "y", **_axis(plot_config, "y", "-log10(p-value)")},
            "color": {
                "field": field,
                "type": "quantitative",
                "scale": {"scheme": "redyellowblue"},
                "legend": _legend(plot_config, title=field),
            },
            "tooltip": [
                {"field": "x", "type": "quantitative", "format": ".4g"},
                {"field": "y", "type": "quantitative", "format": ".4g"},
                {"field": "status", "type": "nominal"},
            ],
        }
    else:
        point_encoding = {
            "x": {"field": "x", **_axis(plot_config, "x", "log2 Fold Change")},
            "y": {"field": "y", **_axis(plot_config, "y", "-log10(p-value)")},
            "color": {
                "field": "status",
                "type": "nominal",
                "scale": {
                    "domain": ["Upregulated", "Downregulated", "Not significant"],
                    "range": [
                        colors.get("upregulated", colors.get("significant", "#E64B35")),
                        colors.get("downregulated", "#4DBBD5"),
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
    layers: list[dict[str, Any]] = []
    threshold_color = colors.get("threshold_color", "#d62728")
    if fc_cut is not None:
        layers.append(
            {
                "data": {"values": [{"threshold": -fc_cut}, {"threshold": fc_cut}]},
                "mark": {
                    "type": "rule",
                    "strokeDash": [6, 4],
                    "strokeWidth": 1.5,
                    "color": threshold_color,
                },
                "encoding": {"x": {"field": "threshold", "type": "quantitative"}},
            }
        )
    if p_cut is not None:
        layers.append(
            {
                "data": {"values": [{"threshold": -np.log10(max(p_cut, 1e-300))}]},
                "mark": {
                    "type": "rule",
                    "strokeDash": [6, 4],
                    "strokeWidth": 1.5,
                    "color": threshold_color,
                },
                "encoding": {"y": {"field": "threshold", "type": "quantitative"}},
            }
        )
    layers.append({"mark": point_mark, "encoding": point_encoding})
    spec["layer"] = layers
    return spec


def _family_size_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    nodes = resolve_plot_data_file(data_dir, "network_nodes.csv")
    if nodes is None:
        raise ValueError("缺少 network_nodes.csv / fbmn_nodes.csv")
    labels, sizes, defaults = _family_size_payload(nodes)
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


def _precursor_mass_diff_values(data_dir: Path) -> list[float]:
    nodes_path = resolve_plot_data_file(data_dir, "network_nodes.csv")
    edges_path = resolve_plot_data_file(data_dir, "network_edges.csv")
    if nodes_path is None or edges_path is None:
        raise ValueError("缺少 network/fbmn nodes 或 edges CSV，无法计算前体质量差")
    nodes = pd.read_csv(nodes_path)
    edges = pd.read_csv(edges_path)
    if "feature_id" not in nodes.columns or "precursor_mz" not in nodes.columns:
        raise ValueError("nodes CSV 缺少 feature_id / precursor_mz")
    if "source" not in edges.columns or "target" not in edges.columns:
        raise ValueError("edges CSV 缺少 source / target")
    mz_map = {
        str(row["feature_id"]): float(row["precursor_mz"])
        for _, row in nodes.iterrows()
        if pd.notna(row.get("precursor_mz")) and float(row["precursor_mz"]) > 0
    }
    diffs: list[float] = []
    for _, row in edges.iterrows():
        a = mz_map.get(str(row["source"]))
        b = mz_map.get(str(row["target"]))
        if a is None or b is None:
            continue
        delta = abs(a - b)
        if 0.1 <= delta <= 600:
            diffs.append(delta)
    if len(diffs) < 5:
        raise ValueError("有效前体质量差不足 5 个，无法语义编辑")
    return diffs


def _histogram_spec(
    plot_type: str,
    data_dir: Path,
    plot_config: dict[str, Any],
) -> dict[str, Any]:
    if plot_type == "degree_hist":
        nodes = resolve_plot_data_file(data_dir, "network_nodes.csv")
        if nodes is None:
            raise ValueError("缺少 network_nodes.csv / fbmn_nodes.csv")
        frame = pd.read_csv(nodes)
        raw = frame["degree"] if "degree" in frame.columns else pd.Series([1] * len(frame))
        values_array = raw.dropna().astype(float).tolist()
        x_title, y_title = "Degree", "Number of Nodes"
        rules = [("Mean", float(np.mean(values_array)) if values_array else 0.0, "threshold_color")]
    elif plot_type == "precursor_mass_diff":
        values_array = _precursor_mass_diff_values(data_dir)
        x_title, y_title = "Δm/z (Da)", "Frequency"
        rules = [
            ("Median", float(np.median(values_array)) if values_array else 0.0, "median_color"),
        ]
    else:
        edges = resolve_plot_data_file(data_dir, "network_edges.csv")
        if edges is None:
            raise ValueError("缺少 network_edges.csv / fbmn_edges.csv")
        frame = pd.read_csv(edges)
        if "cosine" not in frame.columns:
            raise ValueError("edges CSV 缺少 cosine 列")
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


def _vip_bar_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    frame = pd.read_csv(data_dir / "vip_scores.csv")
    if "Feature" not in frame.columns or "VIP" not in frame.columns:
        raise ValueError("vip_scores.csv 缺少 Feature / VIP 列")
    top_n = int((plot_config.get("marks") or {}).get("top_n") or 30)
    top = frame.dropna(subset=["VIP"]).sort_values("VIP", ascending=False).head(max(5, top_n))
    values = [
        {"feature": str(row["Feature"]), "vip": float(row["VIP"]), "order": index}
        for index, (_, row) in enumerate(top.iterrows())
    ]
    colors = plot_config.get("colors") or {}
    bar_color = colors.get("bar_color", "#3C5488")
    spec = _base_spec(plot_config, values)
    spec["mark"] = {
        "type": "bar",
        "color": bar_color,
        "opacity": (plot_config.get("marks") or {}).get("opacity", 0.85),
    }
    spec["encoding"] = {
        "y": {
            "field": "feature",
            **_axis(plot_config, "y", "Feature", axis_type="nominal"),
            "sort": {"field": "order", "order": "ascending"},
        },
        "x": {"field": "vip", **_axis(plot_config, "x", "VIP", zero=True)},
        "tooltip": [
            {"field": "feature", "type": "nominal"},
            {"field": "vip", "type": "quantitative", "format": ".3f"},
        ],
    }
    return spec


def _heatmap_vip_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    matrix_path = data_dir / "heatmap_top_vip_matrix.csv"
    if not matrix_path.is_file():
        raise ValueError("缺少 heatmap_top_vip_matrix.csv，无法语义渲染热图")
    frame = pd.read_csv(matrix_path, index_col=0)
    if frame.empty:
        raise ValueError("heatmap_top_vip_matrix.csv 为空")
    values: list[dict[str, Any]] = []
    for feature, row in frame.iterrows():
        for sample, value in row.items():
            number = _finite(value)
            if number is None:
                continue
            values.append(
                {
                    "feature": str(feature),
                    "sample": str(sample),
                    "value": number,
                }
            )
    if not values:
        raise ValueError("热图矩阵无有效数值")
    spec = _base_spec(plot_config, values)
    width, height = _dimensions(plot_config)
    spec["width"] = max(width, min(1400, 24 * max(8, frame.shape[1])))
    spec["height"] = max(height, min(1200, 18 * max(8, frame.shape[0])))
    spec["mark"] = "rect"
    spec["encoding"] = {
        "x": {
            "field": "sample",
            **_axis(plot_config, "x", "Sample", axis_type="nominal"),
            "axis": {
                "titleFontSize": (plot_config.get("font_size") or {}).get("axis", 12),
                "labelFontSize": (plot_config.get("font_size") or {}).get("label", 9),
                "labelAngle": -45,
            },
        },
        "y": {
            "field": "feature",
            **_axis(plot_config, "y", "Feature", axis_type="nominal"),
            "axis": {
                "titleFontSize": (plot_config.get("font_size") or {}).get("axis", 12),
                "labelFontSize": (plot_config.get("font_size") or {}).get("label", 9),
            },
        },
        "color": {
            "field": "value",
            "type": "quantitative",
            "scale": {"scheme": "viridis"},
            "legend": _legend(plot_config, title="Intensity"),
        },
        "tooltip": [
            {"field": "feature", "type": "nominal"},
            {"field": "sample", "type": "nominal"},
            {"field": "value", "type": "quantitative", "format": ".4g"},
        ],
    }
    return spec


def _join_topology_node_attrs(data_dir: Path, layout: pd.DataFrame) -> pd.DataFrame:
    """将 fbmn_nodes / enhanced_nodes / network_nodes 属性 join 到 layout。"""
    out = layout.copy()
    out["node_id"] = out["node_id"].astype(str)
    candidates = [
        resolve_plot_data_file(data_dir, "network_nodes.csv"),
        data_dir / "enhanced_nodes.csv",
        data_dir / "fbmn_nodes.csv",
        data_dir / "network_nodes.csv",
    ]
    for path in candidates:
        if path is None or not Path(path).is_file():
            continue
        try:
            nodes = pd.read_csv(path)
        except Exception:
            continue
        id_col = None
        for cand in ("feature_id", "node_id", "id"):
            if cand in nodes.columns:
                id_col = cand
                break
        if not id_col:
            continue
        nodes = nodes.copy()
        nodes["_join_id"] = nodes[id_col].astype(str)
        keep_cols = [c for c in (
            "chemical_category",
            "category_confidence",
            "log2FC",
            "log2fc",
            "molecular_family",
            "degree",
        ) if c in nodes.columns]
        if not keep_cols:
            continue
        sub = nodes[["_join_id", *keep_cols]].drop_duplicates("_join_id")
        out = out.merge(sub, left_on="node_id", right_on="_join_id", how="left", suffixes=("", "_n"))
        out = out.drop(columns=["_join_id"], errors="ignore")
        # 统一 log2FC 列名
        if "log2fc" in out.columns and "log2FC" not in out.columns:
            out = out.rename(columns={"log2fc": "log2FC"})
        break
    return out


def _network_topology_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    layout_path = data_dir / "network_layout.csv"
    if not layout_path.is_file():
        raise ValueError("缺少 network_layout.csv，无法语义渲染拓扑图")
    layout = pd.read_csv(layout_path)
    required = {"node_id", "x", "y"}
    if not required.issubset(layout.columns):
        raise ValueError("network_layout.csv 缺少 node_id / x / y 列")
    layout = _join_topology_node_attrs(data_dir, layout)

    color_by = str(plot_config.get("color_by") or "family").strip()
    if color_by in {"molecular_family", "Family"}:
        color_by = "family"
    if color_by == "family" and "family" not in layout.columns and "molecular_family" in layout.columns:
        layout = layout.rename(columns={"molecular_family": "family"})
    if color_by not in layout.columns:
        # 回退 family → all
        if color_by != "family" and "family" in layout.columns:
            raise ValueError(
                f"拓扑图着色列「{color_by}」不存在。可用列："
                + ", ".join(str(c) for c in layout.columns if c not in {"x", "y", "node_id"})
            )
        color_by = "family" if "family" in layout.columns else None

    color_type = str(plot_config.get("color_type") or "nominal")
    if color_by in {"degree", "log2FC"}:
        color_type = "quantitative"

    degree_col = "degree" if "degree" in layout.columns else None
    palette = plot_config.get("palette") or {}

    pos = {
        str(row["node_id"]): (_finite(row["x"]), _finite(row["y"]))
        for _, row in layout.iterrows()
    }
    edge_values: list[dict[str, Any]] = []
    edges_path = resolve_plot_data_file(data_dir, "network_edges.csv")
    if edges_path is not None:
        edges = pd.read_csv(edges_path)
        for _, row in edges.iterrows():
            source = str(row.get("source", ""))
            target = str(row.get("target", ""))
            p1 = pos.get(source)
            p2 = pos.get(target)
            if not p1 or not p2 or p1[0] is None or p1[1] is None or p2[0] is None or p2[1] is None:
                continue
            edge_values.append({"x": p1[0], "y": p1[1], "x2": p2[0], "y2": p2[1]})

    node_values = []
    for _, row in layout.iterrows():
        x = _finite(row["x"])
        y = _finite(row["y"])
        if x is None or y is None:
            continue
        degree = _finite(row[degree_col]) if degree_col else 1.0
        size = max(20, min(220, (degree or 1.0) * 25 + 15))
        item: dict[str, Any] = {
            "x": x,
            "y": y,
            "degree": degree or 1.0,
            "size": size,
            "node_id": str(row["node_id"]),
        }
        if color_by:
            raw_val = row.get(color_by)
            if color_type == "quantitative":
                item["color_value"] = _finite(raw_val)
            else:
                item["color_group"] = "unknown" if pd.isna(raw_val) else str(raw_val)
        else:
            item["color_group"] = "all"
        node_values.append(item)

    marks = plot_config.get("marks") or {}
    layers: list[dict[str, Any]] = []
    if edge_values:
        layers.append(
            {
                "data": {"values": edge_values},
                "mark": {
                    "type": "rule",
                    "color": "#9ca3af",
                    "opacity": 0.35,
                    "strokeWidth": 0.6,
                },
                "encoding": {
                    "x": {"field": "x", "type": "quantitative", "axis": None},
                    "y": {"field": "y", "type": "quantitative", "axis": None},
                    "x2": {"field": "x2"},
                    "y2": {"field": "y2"},
                },
            }
        )

    if color_type == "quantitative":
        color_encoding: dict[str, Any] = {
            "field": "color_value",
            "type": "quantitative",
            "scale": {"scheme": "viridis"},
            "legend": _legend(plot_config, title=color_by or "value"),
        }
        tooltip_extra = [
            {"field": "color_value", "type": "quantitative", "title": color_by or "value", "format": ".4g"}
        ]
    else:
        groups = list(dict.fromkeys(str(v.get("color_group", "all")) for v in node_values))
        colors = [palette.get(g, DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)]) for i, g in enumerate(groups)]
        color_encoding = {
            "field": "color_group",
            "type": "nominal",
            "scale": {"domain": groups, "range": colors},
            "legend": _legend(plot_config, title=color_by or "Group"),
        }
        tooltip_extra = [{"field": "color_group", "type": "nominal", "title": color_by or "group"}]

    layers.append(
        {
            "data": {"values": node_values},
            "mark": {
                "type": "point",
                "filled": True,
                "opacity": marks.get("opacity", 0.85),
                "stroke": "white",
                "strokeWidth": 0.4,
            },
            "encoding": {
                "x": {"field": "x", "type": "quantitative", "axis": None},
                "y": {"field": "y", "type": "quantitative", "axis": None},
                "size": {"field": "size", "type": "quantitative", "legend": None},
                "color": color_encoding,
                "tooltip": [
                    {"field": "node_id", "type": "nominal"},
                    *tooltip_extra,
                    {"field": "degree", "type": "quantitative"},
                ],
            },
        }
    )
    width, height = _dimensions(plot_config)
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": _title_block(plot_config),
        "background": "white",
        "padding": 12,
        "width": max(width, 640),
        "height": max(height, 640),
        "config": {"font": FONT_FAMILY, "view": {"stroke": None}},
        "layer": layers,
    }


def _pearson_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    edges = resolve_plot_data_file(data_dir, "network_edges.csv")
    if edges is None:
        raise ValueError("缺少 network_edges.csv / fbmn_edges.csv")
    frame = pd.read_csv(edges)
    if "pearson_r" not in frame.columns:
        raise ValueError("edges CSV 缺少 pearson_r 列")
    mask = frame["pearson_r"].notna() & (frame["pearson_r"] != 0)
    subset = frame.loc[mask]
    if subset.empty:
        raise ValueError("无有效 pearson_r（非零）边，无法语义渲染")
    colors = plot_config.get("colors") or {}
    bins = (plot_config.get("histogram") or {}).get("bins", 30)
    hist_values = [{"value": float(v)} for v in subset["pearson_r"].tolist() if _finite(v) is not None]
    median = float(np.median(subset["pearson_r"].astype(float)))
    hist_layer = {
        "data": {"values": hist_values},
        "width": 360,
        "height": 280,
        "layer": [
            {
                "mark": {
                    "type": "bar",
                    "color": colors.get("histogram_color", "#9467bd"),
                    "opacity": (plot_config.get("marks") or {}).get("opacity", 0.85),
                },
                "encoding": {
                    "x": {
                        "field": "value",
                        "bin": {"maxbins": bins},
                        **_axis(plot_config, "x", "Pearson r"),
                    },
                    "y": {
                        "aggregate": "count",
                        **_axis(plot_config, "y", "Frequency", zero=True),
                    },
                },
            },
            {
                "data": {"values": [{"rule": 0.5, "label": "r = 0.5"}]},
                "mark": {
                    "type": "rule",
                    "strokeDash": [6, 4],
                    "color": colors.get("threshold_color", "#d62728"),
                },
                "encoding": {"x": {"field": "rule", "type": "quantitative"}},
            },
            {
                "data": {"values": [{"rule": median, "label": f"Median ({median:.3f})"}]},
                "mark": {
                    "type": "rule",
                    "strokeDash": [2, 3],
                    "color": colors.get("median_color", "#ff7f0e"),
                },
                "encoding": {"x": {"field": "rule", "type": "quantitative"}},
            },
        ],
    }
    panels: list[dict[str, Any]] = [hist_layer]
    if "cosine" in subset.columns:
        scatter_values = []
        for _, row in subset.iterrows():
            cos = _finite(row.get("cosine"))
            pr = _finite(row.get("pearson_r"))
            if cos is None or pr is None:
                continue
            scatter_values.append({"cosine": cos, "pearson_r": pr})
        if scatter_values:
            panels.append(
                {
                    "data": {"values": scatter_values},
                    "width": 360,
                    "height": 280,
                    "mark": {
                        "type": "point",
                        "filled": True,
                        "size": 18,
                        "opacity": 0.35,
                        "color": colors.get("scatter_color", "#4c72b0"),
                    },
                    "encoding": {
                        "x": {"field": "cosine", **_axis(plot_config, "x", "Cosine Similarity")},
                        "y": {"field": "pearson_r", **_axis(plot_config, "y", "Pearson r")},
                        "tooltip": [
                            {"field": "cosine", "type": "quantitative", "format": ".3f"},
                            {"field": "pearson_r", "type": "quantitative", "format": ".3f"},
                        ],
                    },
                }
            )
    width, height = _dimensions(plot_config)
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": {
            "text": plot_config.get("title") or "Pearson Correlation Distribution",
            "font": FONT_FAMILY,
            "fontSize": (plot_config.get("font_size") or {}).get("title", 16),
            "anchor": plot_config.get("title_align") or "middle",
        },
        "background": "white",
        "config": {"font": FONT_FAMILY},
        "hconcat": panels,
        "width": width,
        "height": height,
    }


def _parse_top_fragments(raw: Any) -> list[dict[str, float]]:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return []
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, float]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        mz = _finite(item.get("mz"))
        prob = _finite(item.get("probability"))
        if mz is None or prob is None:
            continue
        out.append({"mz": mz, "probability": prob})
    return out


def _mass2motif_overview_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_plot_data_file(data_dir, "mass2motifs.csv")
    if path is None:
        raise ValueError("缺少 mass2motifs.csv")
    frame = pd.read_csv(path)
    if "motif_id" not in frame.columns or "total_load" not in frame.columns:
        raise ValueError("mass2motifs.csv 缺少 motif_id / total_load")
    top_n = int((plot_config.get("marks") or {}).get("top_n") or 30)
    sub = frame.dropna(subset=["total_load"]).sort_values("total_load", ascending=False).head(max(5, top_n))
    values = []
    for index, (_, row) in enumerate(sub.iterrows()):
        values.append(
            {
                "motif": str(row["motif_id"]).replace("Motif_", "M"),
                "load": float(row["total_load"]),
                "n_spectra": float(row["n_top_spectra"]) if "n_top_spectra" in row and pd.notna(row["n_top_spectra"]) else 0.0,
                "order": index,
            }
        )
    spec = _base_spec(plot_config, values)
    width, height = _dimensions(plot_config)
    spec["width"] = max(width, 520)
    spec["height"] = max(height, min(900, 18 * max(8, len(values))))
    spec["mark"] = {"type": "bar", "opacity": (plot_config.get("marks") or {}).get("opacity", 0.9)}
    channel = str(plot_config.get("color_channel") or "n_spectra").strip().lower()
    if channel in {"load", "total_load"}:
        color_field, color_title, scheme = "load", "Total Load", "blues"
    else:
        color_field, color_title, scheme = "n_spectra", "N spectra", "yelloworangered"
    spec["encoding"] = {
        "y": {
            "field": "motif",
            **_axis(plot_config, "y", "Mass2Motif", axis_type="nominal"),
            "sort": {"field": "order", "order": "ascending"},
        },
        "x": {"field": "load", **_axis(plot_config, "x", "Total Load", zero=True)},
        "color": {
            "field": color_field,
            "type": "quantitative",
            "scale": {"scheme": scheme},
            "legend": _legend(plot_config, title=color_title),
        },
        "tooltip": [
            {"field": "motif", "type": "nominal"},
            {"field": "load", "type": "quantitative", "format": ".3f"},
            {"field": "n_spectra", "type": "quantitative"},
        ],
    }
    return spec


def _mass2motif_fragments_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_plot_data_file(data_dir, "mass2motifs.csv")
    if path is None:
        raise ValueError("缺少 mass2motifs.csv")
    frame = pd.read_csv(path)
    if "top_fragments" not in frame.columns:
        raise ValueError("mass2motifs.csv 缺少 top_fragments")
    top_n = int((plot_config.get("marks") or {}).get("top_n") or 6)
    frag_n = int((plot_config.get("marks") or {}).get("top_frags") or 12)
    colors = plot_config.get("colors") or {}
    frag_color = colors.get("fragment_color", "#c0392b")
    values: list[dict[str, Any]] = []
    for _, row in frame.head(max(1, top_n)).iterrows():
        motif = str(row.get("motif_id") or "Motif")
        frags = _parse_top_fragments(row.get("top_fragments"))[:frag_n]
        if not frags:
            continue
        max_prob = max(f["probability"] for f in frags) or 1.0
        for frag in frags:
            values.append(
                {
                    "motif": motif.replace("Motif_", "M"),
                    "mz": frag["mz"],
                    "probability": frag["probability"] / max_prob,
                }
            )
    if not values:
        raise ValueError("无法解析 top_fragments JSON")
    width, height = _dimensions(plot_config)
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": _title_block(plot_config),
        "background": "white",
        "padding": 12,
        "config": {
            "font": FONT_FAMILY,
            "axis": {"labelFont": FONT_FAMILY, "titleFont": FONT_FAMILY},
            "view": {"stroke": None},
        },
        "data": {"values": values},
        "facet": {
            "field": "motif",
            "type": "nominal",
            "columns": min(3, top_n),
            "header": {"titleFontSize": 11, "labelFontSize": 10},
        },
        "spec": {
            "width": max(180, width // max(1, min(3, top_n))),
            "height": max(140, height // max(1, (top_n + 2) // 3)),
            "mark": {
                "type": "bar",
                "color": frag_color,
                "width": 2,
                "opacity": (plot_config.get("marks") or {}).get("opacity", 0.85),
            },
            "encoding": {
                "x": {"field": "mz", **_axis(plot_config, "x", "m/z")},
                "y": {"field": "probability", **_axis(plot_config, "y", "Rel. probability", zero=True)},
                "tooltip": [
                    {"field": "mz", "type": "quantitative", "format": ".3f"},
                    {"field": "probability", "type": "quantitative", "format": ".3f"},
                ],
            },
        },
    }


def _motif_spectrum_heatmap_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_plot_data_file(data_dir, "spectra_motif_scores.csv")
    if path is None:
        raise ValueError("缺少 spectra_motif_scores.csv")
    frame = pd.read_csv(path, index_col=0)
    motif_cols = [c for c in frame.columns if str(c).startswith("Motif_")]
    if not motif_cols:
        raise ValueError("spectra_motif_scores.csv 无 Motif_* 列")
    top_motifs = int((plot_config.get("marks") or {}).get("top_motifs") or 20)
    top_spectra = int((plot_config.get("marks") or {}).get("top_spectra") or 40)
    motif_sums = frame[motif_cols].sum(axis=0).sort_values(ascending=False)
    top_m = motif_sums.head(max(5, top_motifs)).index.tolist()
    score = frame[top_m].sum(axis=1)
    top_s = score.nlargest(max(5, top_spectra)).index.tolist()
    values: list[dict[str, Any]] = []
    for spectrum in top_s:
        for motif in top_m:
            number = _finite(frame.at[spectrum, motif])
            if number is None:
                continue
            values.append(
                {
                    "spectrum": str(spectrum),
                    "motif": str(motif).replace("Motif_", "M"),
                    "value": number,
                }
            )
    if not values:
        raise ValueError("Motif–spectrum 热图无有效数值")
    spec = _base_spec(plot_config, values)
    width, height = _dimensions(plot_config)
    spec["width"] = max(width, min(1400, 28 * len(top_m)))
    spec["height"] = max(height, min(1200, 16 * len(top_s)))
    spec["mark"] = "rect"
    spec["encoding"] = {
        "x": {
            "field": "motif",
            **_axis(plot_config, "x", "Mass2Motif", axis_type="nominal"),
            "axis": {
                "titleFontSize": (plot_config.get("font_size") or {}).get("axis", 12),
                "labelFontSize": (plot_config.get("font_size") or {}).get("label", 8),
                "labelAngle": -90,
            },
        },
        "y": {
            "field": "spectrum",
            **_axis(plot_config, "y", "Spectrum", axis_type="nominal"),
            "axis": {
                "titleFontSize": (plot_config.get("font_size") or {}).get("axis", 12),
                "labelFontSize": (plot_config.get("font_size") or {}).get("label", 7),
            },
        },
        "color": {
            "field": "value",
            "type": "quantitative",
            "scale": {"scheme": "yelloworangered"},
            "legend": _legend(plot_config, title="P(motif|spectrum)"),
        },
        "tooltip": [
            {"field": "spectrum", "type": "nominal"},
            {"field": "motif", "type": "nominal"},
            {"field": "value", "type": "quantitative", "format": ".4g"},
        ],
    }
    return spec


def _chemical_category_counts(data_dir: Path) -> pd.DataFrame:
    path = resolve_plot_data_file(data_dir, "chemical_class_distribution.csv")
    if path is None:
        raise ValueError("缺少 chemical_class_distribution.csv / enhanced_nodes.csv")
    frame = pd.read_csv(path)
    if "chemical_category" in frame.columns and "count_in_family" in frame.columns:
        grouped = (
            frame.groupby("chemical_category", as_index=False)["count_in_family"]
            .sum()
            .rename(columns={"count_in_family": "count"})
        )
        return grouped.sort_values("count", ascending=False)
    if "chemical_category" in frame.columns:
        counts = frame["chemical_category"].fillna("unknown").astype(str).value_counts().reset_index()
        counts.columns = ["chemical_category", "count"]
        return counts
    raise ValueError("化学类别数据缺少 chemical_category 列")


def _chemical_class_distribution_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    counts = _chemical_category_counts(data_dir)
    top_n = int((plot_config.get("marks") or {}).get("top_n") or 20)
    counts = counts.head(max(3, top_n))
    palette = plot_config.get("palette") or {}
    values = []
    for index, row in counts.iterrows():
        label = str(row["chemical_category"])
        values.append(
            {
                "category": label,
                "count": int(row["count"]),
                "color": palette.get(label, DEFAULT_PALETTE[len(values) % len(DEFAULT_PALETTE)]),
                "order": len(values),
            }
        )
    spec = _base_spec(plot_config, values)
    spec["mark"] = {
        "type": "bar",
        "opacity": (plot_config.get("marks") or {}).get("opacity", 0.9),
    }
    spec["encoding"] = {
        "x": {
            "field": "category",
            **_axis(plot_config, "x", "Chemical Class", axis_type="nominal"),
            "sort": {"field": "order", "order": "ascending"},
            "axis": {
                "titleFontSize": (plot_config.get("font_size") or {}).get("axis", 12),
                "labelFontSize": (plot_config.get("font_size") or {}).get("label", 9),
                "labelAngle": -35,
            },
        },
        "y": {"field": "count", **_axis(plot_config, "y", "Count", zero=True)},
        "color": {"field": "color", "type": "nominal", "scale": None, "legend": None},
        "tooltip": [
            {"field": "category", "type": "nominal"},
            {"field": "count", "type": "quantitative"},
        ],
    }
    return spec


def _family_chemical_consensus_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_plot_data_file(data_dir, "chemical_class_distribution.csv")
    if path is None:
        raise ValueError("缺少 chemical_class_distribution.csv")
    frame = pd.read_csv(path)
    if not {"chemical_category", "molecular_family", "count_in_family"}.issubset(frame.columns):
        # enhanced_nodes 回退：按家族×类别计数
        if "chemical_category" in frame.columns and "molecular_family" in frame.columns:
            frame = (
                frame.groupby(["molecular_family", "chemical_category"], as_index=False)
                .size()
                .rename(columns={"size": "count_in_family"})
            )
        else:
            raise ValueError("化学共识数据缺少 molecular_family / chemical_category")
    top_families = (
        frame.groupby("molecular_family")["count_in_family"].sum().sort_values(ascending=False).head(15).index
    )
    sub = frame[frame["molecular_family"].isin(top_families)].copy()
    palette = plot_config.get("palette") or {}
    categories = list(dict.fromkeys(str(c) for c in sub["chemical_category"].tolist()))
    values = []
    for _, row in sub.iterrows():
        cat = str(row["chemical_category"])
        values.append(
            {
                "family": str(row["molecular_family"]),
                "category": cat,
                "count": int(row["count_in_family"]),
                "color": palette.get(cat, DEFAULT_PALETTE[categories.index(cat) % len(DEFAULT_PALETTE)]),
            }
        )
    spec = _base_spec(plot_config, values)
    spec["mark"] = {"type": "bar", "opacity": (plot_config.get("marks") or {}).get("opacity", 0.9)}
    spec["encoding"] = {
        "x": {
            "field": "family",
            **_axis(plot_config, "x", "Molecular Family", axis_type="nominal"),
            "axis": {
                "titleFontSize": (plot_config.get("font_size") or {}).get("axis", 12),
                "labelFontSize": (plot_config.get("font_size") or {}).get("label", 8),
                "labelAngle": -40,
            },
        },
        "y": {"field": "count", **_axis(plot_config, "y", "Nodes", zero=True), "stack": "zero"},
        "color": {
            "field": "category",
            "type": "nominal",
            "scale": {
                "domain": categories,
                "range": [palette.get(c, DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)]) for i, c in enumerate(categories)],
            },
            "legend": _legend(plot_config, title="Chemical Class"),
        },
        "tooltip": [
            {"field": "family", "type": "nominal"},
            {"field": "category", "type": "nominal"},
            {"field": "count", "type": "quantitative"},
        ],
    }
    return spec


def _annotation_propagation_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_plot_data_file(data_dir, "enhanced_nodes.csv")
    if path is None:
        raise ValueError("缺少 enhanced_nodes.csv")
    frame = pd.read_csv(path)
    if "chemical_category" not in frame.columns:
        raise ValueError("enhanced_nodes.csv 缺少 chemical_category")
    colors = plot_config.get("colors") or {}
    if "category_confidence" in frame.columns:
        direct = frame["category_confidence"].isin(["medium", "high", "direct"]).sum()
        propagated = (frame["category_confidence"].astype(str) == "propagated").sum()
        unknown = len(frame) - int(direct) - int(propagated)
    elif "has_direct_annotation" in frame.columns:
        direct = int(frame["has_direct_annotation"].astype(bool).sum())
        propagated = int((~frame["has_direct_annotation"].astype(bool) & frame["chemical_category"].notna()).sum())
        unknown = len(frame) - direct - propagated
    else:
        known = int(frame["chemical_category"].notna().sum())
        direct, propagated, unknown = known, 0, len(frame) - known
    values = [
        {"source": "Direct", "count": int(direct), "color": colors.get("direct", "#2CA02C")},
        {"source": "Propagated", "count": int(propagated), "color": colors.get("propagated", "#FF7F0E")},
        {"source": "Unknown", "count": max(0, int(unknown)), "color": colors.get("unknown", "#B0B0B0")},
    ]
    spec = _base_spec(plot_config, values)
    spec["mark"] = {"type": "bar", "opacity": (plot_config.get("marks") or {}).get("opacity", 0.9)}
    spec["encoding"] = {
        "x": {
            "field": "source",
            **_axis(plot_config, "x", "Annotation Source", axis_type="nominal"),
        },
        "y": {"field": "count", **_axis(plot_config, "y", "Nodes", zero=True)},
        "color": {"field": "color", "type": "nominal", "scale": None, "legend": None},
        "tooltip": [
            {"field": "source", "type": "nominal"},
            {"field": "count", "type": "quantitative"},
        ],
    }
    return spec


def _kegg_enrich_frame(data_dir: Path) -> pd.DataFrame:
    path = resolve_plot_data_file(data_dir, "kegg_compound_enrich.csv")
    if path is None:
        raise ValueError("缺少 kegg_compound_enrich.csv")
    frame = pd.read_csv(path)
    if frame.empty:
        raise ValueError("kegg_compound_enrich.csv 为空")
    if "Description" not in frame.columns:
        raise ValueError("kegg_compound_enrich.csv 缺少 Description")
    padj_col = "p.adjust" if "p.adjust" in frame.columns else ("p_adjust" if "p_adjust" in frame.columns else None)
    if padj_col is None:
        raise ValueError("kegg_compound_enrich.csv 缺少 p.adjust")
    count_col = "Count" if "Count" in frame.columns else ("count" if "count" in frame.columns else None)
    if count_col is None:
        frame["Count"] = 1
        count_col = "Count"
    out = frame.copy()
    out["_padj"] = pd.to_numeric(out[padj_col], errors="coerce")
    out["_count"] = pd.to_numeric(out[count_col], errors="coerce").fillna(1)
    out = out.dropna(subset=["_padj"])
    out["_neglog10"] = -np.log10(out["_padj"].clip(lower=1e-300))
    return out.sort_values("_padj", ascending=True)


def _kegg_enrich_spec(data_dir: Path, plot_config: dict[str, Any], *, mode: str) -> dict[str, Any]:
    frame = _kegg_enrich_frame(data_dir)
    top_n = int((plot_config.get("marks") or {}).get("top_n") or 20)
    top = frame.head(max(5, top_n))
    values = [
        {
            "pathway": str(row["Description"])[:80],
            "count": float(row["_count"]),
            "neglog10": float(row["_neglog10"]),
            "padj": float(row["_padj"]),
            "order": index,
        }
        for index, (_, row) in enumerate(top.iterrows())
    ]
    colors = plot_config.get("colors") or {}
    spec = _base_spec(plot_config, values)
    width, height = _dimensions(plot_config)
    spec["width"] = max(width, 520)
    spec["height"] = max(height, min(1000, 22 * max(8, len(values))))
    if mode == "bar":
        bar_color = colors.get("bar_color", "#3C5488")
        spec["mark"] = {
            "type": "bar",
            "color": bar_color,
            "opacity": (plot_config.get("marks") or {}).get("opacity", 0.85),
        }
        spec["encoding"] = {
            "y": {
                "field": "pathway",
                **_axis(plot_config, "y", "Pathway", axis_type="nominal"),
                "sort": {"field": "order", "order": "ascending"},
            },
            "x": {"field": "count", **_axis(plot_config, "x", "Count", zero=True)},
            "tooltip": [
                {"field": "pathway", "type": "nominal"},
                {"field": "count", "type": "quantitative"},
                {"field": "padj", "type": "quantitative", "format": ".3g"},
            ],
        }
        return spec

    # bubble / dot
    channel = str(plot_config.get("color_channel") or "neglog10").strip().lower()
    if channel in {"count", "Count"}:
        color_field, color_title = "count", "Count"
    else:
        color_field, color_title = "neglog10", "-log10(FDR)"
    spec["mark"] = {
        "type": "point",
        "filled": True,
        "opacity": (plot_config.get("marks") or {}).get("opacity", 0.85),
    }
    spec["encoding"] = {
        "y": {
            "field": "pathway",
            **_axis(plot_config, "y", "Pathway", axis_type="nominal"),
            "sort": {"field": "order", "order": "ascending"},
        },
        "x": {"field": "count", **_axis(plot_config, "x", "Count", zero=True)},
        "size": {
            "field": "count",
            "type": "quantitative",
            "legend": _legend(plot_config, title="Count"),
            "scale": {"range": [40, 400] if mode == "bubble" else [30, 300]},
        },
        "color": {
            "field": color_field,
            "type": "quantitative",
            "scale": {
                "scheme": "blues" if mode == "dot" or color_field == "count" else "redyellowblue",
                "reverse": mode != "dot" and color_field != "count",
            },
            "legend": _legend(plot_config, title=color_title),
        },
        "tooltip": [
            {"field": "pathway", "type": "nominal"},
            {"field": "count", "type": "quantitative"},
            {"field": "padj", "type": "quantitative", "format": ".3g"},
            {"field": "neglog10", "type": "quantitative", "format": ".2f"},
        ],
    }
    return spec


def _fbmn_group_intensity_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    path = resolve_plot_data_file(data_dir, "fbmn_group_intensity.csv")
    if path is None:
        raise ValueError("缺少 fbmn_group_intensity.csv")
    frame = pd.read_csv(path)
    required = {"molecular_family", "group", "mean_intensity"}
    if not required.issubset(frame.columns):
        raise ValueError("fbmn_group_intensity.csv 缺少 molecular_family / group / mean_intensity")
    palette = plot_config.get("palette") or {}
    groups = list(dict.fromkeys(str(g) for g in frame["group"].tolist()))
    values = []
    for _, row in frame.iterrows():
        group = str(row["group"])
        values.append(
            {
                "family": str(row["molecular_family"]),
                "group": group,
                "mean": float(row["mean_intensity"]),
                "std": float(row["std_intensity"]) if "std_intensity" in row and pd.notna(row.get("std_intensity")) else 0.0,
                "rank": int(row["rank"]) if "rank" in row and pd.notna(row.get("rank")) else 0,
                "color": palette.get(group, DEFAULT_PALETTE[groups.index(group) % len(DEFAULT_PALETTE)]),
            }
        )
    spec = _base_spec(plot_config, values)
    spec["mark"] = {
        "type": "bar",
        "opacity": (plot_config.get("marks") or {}).get("opacity", 0.85),
    }
    spec["encoding"] = {
        "x": {
            "field": "family",
            **_axis(plot_config, "x", "Molecular Family", axis_type="nominal"),
            "sort": {"field": "rank", "order": "ascending"},
            "axis": {
                "titleFontSize": (plot_config.get("font_size") or {}).get("axis", 12),
                "labelFontSize": (plot_config.get("font_size") or {}).get("label", 9),
                "labelAngle": -30,
            },
        },
        "y": {"field": "mean", **_axis(plot_config, "y", "Mean Intensity", zero=True)},
        "xOffset": {"field": "group", "type": "nominal"},
        "color": {
            "field": "group",
            "type": "nominal",
            "scale": {
                "domain": groups,
                "range": [palette.get(g, DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)]) for i, g in enumerate(groups)],
            },
            "legend": _legend(plot_config, title="Group"),
        },
        "tooltip": [
            {"field": "family", "type": "nominal"},
            {"field": "group", "type": "nominal"},
            {"field": "mean", "type": "quantitative", "format": ".3g"},
            {"field": "std", "type": "quantitative", "format": ".3g"},
        ],
    }
    return spec


def _mass2motif_network_spec(data_dir: Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    nodes_path = resolve_plot_data_file(data_dir, "mass2motif_network_nodes.csv")
    edges_path = resolve_plot_data_file(data_dir, "mass2motif_network_edges.csv")
    if nodes_path is None or edges_path is None:
        raise ValueError("缺少 mass2motif_network_nodes.csv / mass2motif_network_edges.csv")
    nodes = pd.read_csv(nodes_path)
    edges = pd.read_csv(edges_path)
    if nodes.empty:
        raise ValueError("mass2motif_network_nodes.csv 为空")
    colors = plot_config.get("colors") or {}
    motif_color = colors.get("motif_color", "#E64B35")
    spectrum_color = colors.get("spectrum_color", "#4c72b0")
    edge_color = colors.get("edge_color", "#aaaaaa")

    node_values = []
    for _, row in nodes.iterrows():
        ntype = str(row.get("node_type") or "spectrum")
        load = _finite(row.get("total_load")) or 1.0
        node_values.append(
            {
                "node_id": str(row["node_id"]),
                "label": str(row.get("label") or row["node_id"]),
                "node_type": ntype,
                "x": float(row["x"]),
                "y": float(row["y"]),
                "size": max(40, min(500, load * 40)) if ntype == "motif" else 20,
                "color": motif_color if ntype == "motif" else spectrum_color,
            }
        )
    pos = {str(r["node_id"]): (float(r["x"]), float(r["y"])) for _, r in nodes.iterrows()}
    edge_values = []
    for _, row in edges.iterrows():
        src = f"spec:{row['spectrum_id']}"
        tgt = f"motif:{row['motif_id']}"
        if src not in pos or tgt not in pos:
            continue
        x0, y0 = pos[src]
        x1, y1 = pos[tgt]
        score = _finite(row.get("score")) or 0.0
        edge_values.append(
            {
                "x": x0,
                "y": y0,
                "x2": x1,
                "y2": y1,
                "score": score,
            }
        )
    width, height = _dimensions(plot_config)
    layers: list[dict[str, Any]] = []
    if edge_values:
        layers.append(
            {
                "data": {"values": edge_values},
                "mark": {
                    "type": "rule",
                    "color": edge_color,
                    "opacity": 0.35,
                    "strokeWidth": 0.5,
                },
                "encoding": {
                    "x": {"field": "x", "type": "quantitative", "axis": None},
                    "y": {"field": "y", "type": "quantitative", "axis": None},
                    "x2": {"field": "x2"},
                    "y2": {"field": "y2"},
                },
            }
        )
    layers.append(
        {
            "data": {"values": node_values},
            "mark": {"type": "point", "filled": True, "opacity": 0.9},
            "encoding": {
                "x": {"field": "x", "type": "quantitative", "axis": None},
                "y": {"field": "y", "type": "quantitative", "axis": None},
                "size": {"field": "size", "type": "quantitative", "legend": None},
                "color": {"field": "color", "type": "nominal", "scale": None, "legend": None},
                "shape": {
                    "field": "node_type",
                    "type": "nominal",
                    "scale": {"domain": ["motif", "spectrum"], "range": ["circle", "square"]},
                    "legend": _legend(plot_config, title="Node"),
                },
                "tooltip": [
                    {"field": "label", "type": "nominal"},
                    {"field": "node_type", "type": "nominal"},
                ],
            },
        }
    )
    # motif labels
    motif_labels = [v for v in node_values if v["node_type"] == "motif"]
    if motif_labels:
        layers.append(
            {
                "data": {"values": motif_labels},
                "mark": {
                    "type": "text",
                    "fontSize": (plot_config.get("font_size") or {}).get("label", 9),
                    "fontWeight": "bold",
                },
                "encoding": {
                    "x": {"field": "x", "type": "quantitative"},
                    "y": {"field": "y", "type": "quantitative"},
                    "text": {"field": "label", "type": "nominal"},
                },
            }
        )
    return {
        "$schema": VEGA_LITE_SCHEMA,
        "title": _title_block(plot_config),
        "background": "white",
        "padding": 12,
        "width": max(width, 640),
        "height": max(height, 640),
        "config": {"font": FONT_FAMILY, "view": {"stroke": None}},
        "layer": layers,
    }


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
    if plot_type == "vip_bar":
        return _vip_bar_spec(data_path, plot_config)
    if plot_type == "heatmap_vip":
        return _heatmap_vip_spec(data_path, plot_config)
    if plot_type == "family_size":
        return _family_size_spec(data_path, plot_config)
    if plot_type in {"degree_hist", "cosine_hist", "precursor_mass_diff"}:
        return _histogram_spec(plot_type, data_path, plot_config)
    if plot_type == "network_topology":
        return _network_topology_spec(data_path, plot_config)
    if plot_type == "pearson_hist":
        return _pearson_spec(data_path, plot_config)
    if plot_type == "mass2motif_overview":
        return _mass2motif_overview_spec(data_path, plot_config)
    if plot_type == "mass2motif_fragments":
        return _mass2motif_fragments_spec(data_path, plot_config)
    if plot_type == "motif_spectrum_heatmap":
        return _motif_spectrum_heatmap_spec(data_path, plot_config)
    if plot_type == "chemical_class_distribution":
        return _chemical_class_distribution_spec(data_path, plot_config)
    if plot_type == "family_chemical_consensus":
        return _family_chemical_consensus_spec(data_path, plot_config)
    if plot_type == "annotation_propagation":
        return _annotation_propagation_spec(data_path, plot_config)
    if plot_type == "kegg_bubble":
        return _kegg_enrich_spec(data_path, plot_config, mode="bubble")
    if plot_type == "kegg_dotplot":
        return _kegg_enrich_spec(data_path, plot_config, mode="dot")
    if plot_type == "kegg_barplot":
        return _kegg_enrich_spec(data_path, plot_config, mode="bar")
    if plot_type == "fbmn_group_intensity":
        return _fbmn_group_intensity_spec(data_path, plot_config)
    if plot_type == "mass2motif_network":
        return _mass2motif_network_spec(data_path, plot_config)
    raise ValueError(f"暂不支持语义渲染: {plot_type}")


def write_svg_sidecar(vega_spec: dict[str, Any], png_path: str | Path) -> Path | None:
    """仅写出与 PNG 同名的 .svg / .vl.json，不覆盖 PNG。"""
    png = Path(png_path)
    svg_path = svg_path_for_png(png)
    vega_path = vega_config_path_for_png(png)
    vega_path.write_text(json.dumps(vega_spec, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        import vl_convert as vlc

        svg_text = vlc.vegalite_to_svg(json.dumps(vega_spec, ensure_ascii=False, allow_nan=False))
        svg_path.write_text(svg_text, encoding="utf-8")
        return svg_path
    except Exception:
        return None


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
