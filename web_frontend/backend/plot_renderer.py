"""基于 matplotlib 的轻量作图重绘（避免 Plotly 后端开销）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from web_frontend.backend.plot_fonts import cjk_fontproperties, configure_matplotlib_cjk
from web_frontend.backend.plot_theme import (
    DEFAULT_PALETTE,
    echarts_config_path_for_png,
    plot_config_path_for_png,
)

configure_matplotlib_cjk()


def _cjk(size: float | int | None = None, *, bold: bool = False):
    return cjk_fontproperties(size=size, bold=bold)


def _group_color(palette: dict[str, str], group: str, index: int) -> str:
    return palette.get(str(group), DEFAULT_PALETTE[index % len(DEFAULT_PALETTE)])


def build_echarts_option(
    *,
    scores: np.ndarray,
    groups: list[str],
    sample_names: list[str],
    axis_names: list[str],
    plot_config: dict[str, Any],
) -> dict[str, Any]:
    """生成 ECharts option，供前端轻量预览（不依赖 Plotly）。"""
    x_idx = max(0, int(plot_config["components"][0]) - 1)
    y_idx = max(0, int(plot_config["components"][1]) - 1)
    ncol = scores.shape[1]
    x_idx = min(x_idx, ncol - 1)
    y_idx = min(y_idx, ncol - 1)
    if x_idx == y_idx and ncol >= 2:
        y_idx = 1

    palette = plot_config.get("palette") or {}
    legend_title, color_type = score_color_meta(plot_config)
    ordered_groups: list[str] = []
    seen: set[str] = set()
    for group in groups:
        g = str(group)
        if g not in seen:
            seen.add(g)
            ordered_groups.append(g)

    series = []
    if color_type == "quantitative":
        points = []
        for j, group in enumerate(groups):
            try:
                val = float(group)
            except (TypeError, ValueError):
                val = None
            points.append(
                {
                    "name": sample_names[j].replace(".mzML", "").replace(".mzml", ""),
                    "value": [float(scores[j, x_idx]), float(scores[j, y_idx]), val],
                }
            )
        series.append(
            {
                "name": legend_title,
                "type": "scatter",
                "symbolSize": 11,
                "data": points,
            }
        )
    else:
        for i, group in enumerate(ordered_groups):
            mask = np.array([str(g) == group for g in groups], dtype=bool)
            points = [
                {
                    "name": sample_names[j].replace(".mzML", "").replace(".mzml", ""),
                    "value": [float(scores[j, x_idx]), float(scores[j, y_idx])],
                }
                for j, m in enumerate(mask)
                if m
            ]
            series.append(
                {
                    "name": group,
                    "type": "scatter",
                    "symbolSize": 11,
                    "itemStyle": {"color": _group_color(palette, group, i)},
                    "label": {
                        "show": bool(plot_config.get("show_sample_labels", True)),
                        "position": "top",
                        "fontSize": plot_config.get("font_size", {}).get("label", 10),
                    },
                    "data": points,
                }
            )

    fs = plot_config.get("font_size") or {}
    return {
        "title": {
            "text": plot_config.get("title", ""),
            "textStyle": {"fontSize": fs.get("title", 16)},
        },
        "tooltip": {"trigger": "item"},
        "legend": {
            "top": 10,
            "textStyle": {"fontSize": fs.get("legend", 11)},
        },
        "grid": {"left": 60, "right": 30, "top": 70, "bottom": 60},
        "xAxis": {
            "name": axis_names[x_idx],
            "nameTextStyle": {"fontSize": fs.get("axis", 12)},
            "axisLabel": {"fontSize": fs.get("axis", 12)},
            "splitLine": {"lineStyle": {"color": "#ebebeb"}},
        },
        "yAxis": {
            "name": axis_names[y_idx],
            "nameTextStyle": {"fontSize": fs.get("axis", 12)},
            "axisLabel": {"fontSize": fs.get("axis", 12)},
            "splitLine": {"lineStyle": {"color": "#ebebeb"}},
        },
        "series": series,
    }


def render_score_plot_png(
    *,
    scores: np.ndarray,
    groups: list[str],
    sample_names: list[str],
    axis_names: list[str],
    plot_config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """用 matplotlib 重绘 PCA / PLS-DA 得分图并保存 PNG。"""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    x_idx = max(0, int(plot_config["components"][0]) - 1)
    y_idx = max(0, int(plot_config["components"][1]) - 1)
    ncol = scores.shape[1]
    x_idx = min(x_idx, ncol - 1)
    y_idx = min(y_idx, ncol - 1)
    if x_idx == y_idx and ncol >= 2:
        y_idx = 1

    palette = plot_config.get("palette") or {}
    fs = plot_config.get("font_size") or {}
    fig_w, fig_h = plot_config.get("figure_size") or [10.0, 8.0]

    legend_title, color_type = score_color_meta(plot_config)
    fig, ax = plt.subplots(figsize=(float(fig_w), float(fig_h)), facecolor="white")

    if color_type == "quantitative":
        try:
            nums = np.array([float(g) if g == g else np.nan for g in groups], dtype=float)
        except (TypeError, ValueError):
            nums = np.full(len(groups), np.nan)
        sc = ax.scatter(
            scores[:, x_idx],
            scores[:, y_idx],
            c=nums,
            s=70,
            cmap="viridis",
            alpha=0.9,
            edgecolors="white",
            linewidths=0.8,
        )
        cbar = fig.colorbar(sc, ax=ax)
        cbar.set_label(legend_title, fontproperties=_cjk(fs.get("legend", 11)))
        if plot_config.get("show_sample_labels", True):
            for j in range(len(groups)):
                label = sample_names[j].replace(".mzML", "").replace(".mzml", "")
                ax.annotate(
                    label,
                    (scores[j, x_idx], scores[j, y_idx]),
                    textcoords="offset points",
                    xytext=(0, 6),
                    ha="center",
                    fontproperties=_cjk(fs.get("label", 10)),
                    color="#111827",
                )
    else:
        ordered_groups: list[str] = []
        seen: set[str] = set()
        for group in groups:
            g = str(group)
            if g not in seen:
                seen.add(g)
                ordered_groups.append(g)

        for i, group in enumerate(ordered_groups):
            mask = np.array([str(g) == group for g in groups], dtype=bool)
            xs = scores[mask, x_idx]
            ys = scores[mask, y_idx]
            color = _group_color(palette, group, i)
            ax.scatter(
                xs,
                ys,
                s=70,
                c=color,
                alpha=0.9,
                edgecolors="white",
                linewidths=0.8,
                label=group,
            )
            if plot_config.get("show_sample_labels", True):
                for j, m in enumerate(mask):
                    if not m:
                        continue
                    label = sample_names[j].replace(".mzML", "").replace(".mzml", "")
                    ax.annotate(
                        label,
                        (scores[j, x_idx], scores[j, y_idx]),
                        textcoords="offset points",
                        xytext=(0, 6),
                        ha="center",
                        fontproperties=_cjk(fs.get("label", 10)),
                        color="#111827",
                    )
        legend = ax.legend(title=legend_title, prop=_cjk(fs.get("legend", 11)), framealpha=0.9)
        if legend and legend.get_title():
            legend.get_title().set_fontproperties(_cjk(fs.get("legend", 11), bold=True))

    ax.set_title(
        plot_config.get("title", ""),
        fontproperties=_cjk(fs.get("title", 16), bold=True),
    )
    ax.set_xlabel(axis_names[x_idx], fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_ylabel(axis_names[y_idx], fontproperties=_cjk(fs.get("axis", 12)))
    ax.tick_params(labelsize=fs.get("axis", 12))
    ax.grid(True, color="#ebebeb", linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out

def save_plot_sidecars(
    *,
    png_path: str | Path,
    plot_config: dict[str, Any],
    echarts_option: dict[str, Any],
    instruction: str | None = None,
    source_rel: str | None = None,
) -> tuple[Path, Path]:
    png = Path(png_path)
    config_path = Path(plot_config_path_for_png(png))
    echarts_path = Path(echarts_config_path_for_png(png))

    payload = dict(plot_config)
    if instruction:
        payload["last_instruction"] = instruction
    if source_rel:
        payload["source_rel"] = source_rel

    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    echarts_path.write_text(json.dumps(echarts_option, ensure_ascii=False), encoding="utf-8")
    return config_path, echarts_path


def load_scores_and_groups(
    scores_csv: str | Path,
    metadata_csv: str | Path,
    *,
    plot_config: dict[str, Any] | None = None,
) -> tuple[np.ndarray, list[Any], list[str], list[str]]:
    """加载得分矩阵与着色标签。

    着色字段来自 plot_config.color_by（默认 Group）；
    plot_config.cluster = {method: kmeans, n: 3} 时在得分上聚类着色。
    """
    from web_frontend.backend.session_metadata import resolve_color_labels

    df = pd.read_csv(scores_csv, index_col=0)
    if df.empty:
        raise ValueError("scores CSV 为空")

    samples = df.index.astype(str).tolist()
    axis_names = df.columns.astype(str).tolist()
    scores = df.to_numpy(dtype=float)
    cfg = plot_config if isinstance(plot_config, dict) else {}
    cluster = cfg.get("cluster") if isinstance(cfg.get("cluster"), dict) else None

    if cluster and str(cluster.get("method") or "").lower() in {"kmeans", "k-means", "cluster"}:
        n_clusters = int(cluster.get("n") or cluster.get("k") or 3)
        n_clusters = max(2, min(12, n_clusters))
        n_features = min(scores.shape[1], max(2, n_clusters))
        try:
            from sklearn.cluster import KMeans

            model = KMeans(n_clusters=n_clusters, n_init=10, random_state=42)
            labels = model.fit_predict(scores[:, :n_features])
            groups = [f"Cluster_{int(i) + 1}" for i in labels]
            if isinstance(plot_config, dict):
                plot_config["color_by"] = "Cluster"
                plot_config["color_type"] = "nominal"
                plot_config["cluster"] = {"method": "kmeans", "n": n_clusters}
            return scores, groups, samples, axis_names
        except Exception:
            # sklearn 不可用时退回 metadata 列
            pass

    color_by = str(cfg.get("color_by") or "Group")
    groups, resolved_col, ctype = resolve_color_labels(samples, metadata_csv, color_by=color_by)
    if isinstance(plot_config, dict):
        plot_config["color_by"] = resolved_col
        plot_config["color_type"] = ctype
        plot_config["cluster"] = None
    return scores, groups, samples, axis_names


def score_color_meta(plot_config: dict[str, Any] | None) -> tuple[str, str]:
    """返回 (legend_title, color_type)。"""
    cfg = plot_config if isinstance(plot_config, dict) else {}
    cluster = cfg.get("cluster") if isinstance(cfg.get("cluster"), dict) else None
    if cluster and str(cluster.get("method") or "").lower() in {"kmeans", "k-means", "cluster"}:
        return "Cluster", "nominal"
    color_by = str(cfg.get("color_by") or "Group")
    color_type = str(cfg.get("color_type") or "nominal")
    if color_type not in {"nominal", "quantitative"}:
        color_type = "nominal"
    return color_by, color_type

def _color_from_config(plot_config: dict[str, Any], key: str, fallback: str) -> str:
    colors = plot_config.get("colors") or {}
    if key in colors:
        return colors[key]
    palette = plot_config.get("palette") or {}
    if key in palette:
        return palette[key]
    return fallback


def render_volcano_plot_png(
    volcano_csv: str | Path,
    plot_config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    df = pd.read_csv(volcano_csv)
    required = {"log2FC", "neglog10p"}
    if not required.issubset(df.columns):
        raise ValueError("volcano_results.csv 缺少 log2FC / neglog10p 列")

    sig_col = "Significant" if "Significant" in df.columns else None
    sig_color = _color_from_config(plot_config, "significant", "#E64B35")
    nonsig_color = _color_from_config(plot_config, "nonsignificant", "#B0B0B0")
    fs = plot_config.get("font_size") or {}
    fig_w, fig_h = plot_config.get("figure_size") or [8.0, 6.0]

    fig, ax = plt.subplots(figsize=(float(fig_w), float(fig_h)), facecolor="white")
    if sig_col:
        sig_mask = df[sig_col].astype(bool)
        ax.scatter(
            df.loc[~sig_mask, "log2FC"],
            df.loc[~sig_mask, "neglog10p"],
            c=nonsig_color,
            s=18,
            alpha=0.7,
            label="Non-significant",
        )
        ax.scatter(
            df.loc[sig_mask, "log2FC"],
            df.loc[sig_mask, "neglog10p"],
            c=sig_color,
            s=22,
            alpha=0.85,
            label="Significant",
        )
        ax.legend(prop=_cjk(fs.get("legend", 11)))
    else:
        ax.scatter(df["log2FC"], df["neglog10p"], c=sig_color, s=18, alpha=0.8)

    ax.set_title(
        plot_config.get("title", "Volcano Plot"),
        fontproperties=_cjk(fs.get("title", 16), bold=True),
    )
    ax.set_xlabel("log2 Fold Change", fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_ylabel("-log10(p-value)", fontproperties=_cjk(fs.get("axis", 12)))
    ax.tick_params(labelsize=fs.get("axis", 12))
    ax.grid(True, color="#ebebeb", linewidth=0.8)
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def build_echarts_volcano(volcano_csv: str | Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    df = pd.read_csv(volcano_csv)
    sig_col = "Significant" if "Significant" in df.columns else None
    sig_color = _color_from_config(plot_config, "significant", "#E64B35")
    nonsig_color = _color_from_config(plot_config, "nonsignificant", "#B0B0B0")
    fs = plot_config.get("font_size") or {}
    series = []
    if sig_col:
        for label, mask, color in (
            ("Non-significant", ~df[sig_col].astype(bool), nonsig_color),
            ("Significant", df[sig_col].astype(bool), sig_color),
        ):
            points = [
                [float(r.log2FC), float(r.neglog10p)]
                for r in df.loc[mask].itertuples()
            ]
            series.append(
                {
                    "name": label,
                    "type": "scatter",
                    "symbolSize": 8,
                    "itemStyle": {"color": color},
                    "data": points,
                }
            )
    else:
        series.append(
            {
                "name": "Features",
                "type": "scatter",
                "symbolSize": 8,
                "itemStyle": {"color": sig_color},
                "data": [[float(a), float(b)] for a, b in zip(df["log2FC"], df["neglog10p"])],
            }
        )
    return {
        "title": {"text": plot_config.get("title", ""), "textStyle": {"fontSize": fs.get("title", 16)}},
        "tooltip": {"trigger": "item"},
        "legend": {"top": 10},
        "grid": {"left": 60, "right": 30, "top": 70, "bottom": 60},
        "xAxis": {"name": "log2FC", "nameTextStyle": {"fontSize": fs.get("axis", 12)}},
        "yAxis": {"name": "-log10(p)", "nameTextStyle": {"fontSize": fs.get("axis", 12)}},
        "series": series,
    }


def _family_size_payload(nodes_csv: str | Path) -> tuple[list[str], list[int], list[str]]:
    df = pd.read_csv(nodes_csv)
    col = "molecular_family" if "molecular_family" in df.columns else None
    if not col:
        raise ValueError("network_nodes.csv 缺少 molecular_family 列")
    counts: dict[str, int] = {}
    for fam in df[col].astype(str):
        counts[fam] = counts.get(fam, 0) + 1
    n_singletons = counts.pop("singleton", 0)
    sorted_fams = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    labels, sizes, colors = [], [], []
    for i, (fam, size) in enumerate(sorted_fams):
        labels.append(fam)
        sizes.append(size)
        colors.append(DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)])
    if n_singletons > 0:
        labels.append("singleton")
        sizes.append(n_singletons)
        colors.append("#cccccc")
    max_display = 30
    if len(sizes) > max_display:
        others = sum(sizes[max_display:])
        labels = labels[:max_display] + [f"others ({len(sizes) - max_display} families)"]
        sizes = sizes[:max_display] + [others]
        colors = colors[:max_display] + ["#999999"]
    return labels, sizes, colors


def render_family_size_png(
    nodes_csv: str | Path,
    plot_config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    labels, sizes, colors = _family_size_payload(nodes_csv)
    palette = plot_config.get("palette") or {}
    for i, label in enumerate(labels):
        if label in palette:
            colors[i] = palette[label]
    fs = plot_config.get("font_size") or {}
    fig_w, fig_h = plot_config.get("figure_size") or [10.0, 5.0]
    fig, ax = plt.subplots(figsize=(float(fig_w), float(fig_h)), facecolor="white")
    bars = ax.bar(range(len(labels)), sizes, color=colors, edgecolor="white", linewidth=0.5)
    for bar, val in zip(bars, sizes):
        if val > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(sizes) * 0.01,
                str(val),
                ha="center",
                va="bottom",
                fontproperties=_cjk(fs.get("label", 9)),
            )
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontproperties=_cjk(fs.get("label", 8)))
    ax.set_ylabel("Number of Nodes", fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_xlabel("Molecular Family", fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_title(plot_config.get("title", ""), fontproperties=_cjk(fs.get("title", 16), bold=True))
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def build_echarts_bar(labels: list[str], sizes: list[int], colors: list[str], plot_config: dict[str, Any]) -> dict[str, Any]:
    fs = plot_config.get("font_size") or {}
    return {
        "title": {"text": plot_config.get("title", ""), "textStyle": {"fontSize": fs.get("title", 16)}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 60, "right": 20, "top": 70, "bottom": 100},
        "xAxis": {
            "type": "category",
            "data": labels,
            "axisLabel": {"rotate": 45, "fontSize": fs.get("label", 9)},
        },
        "yAxis": {"type": "value", "name": "Count", "nameTextStyle": {"fontSize": fs.get("axis", 12)}},
        "series": [
            {
                "type": "bar",
                "data": [{"value": s, "itemStyle": {"color": c}} for s, c in zip(sizes, colors)],
                "label": {"show": True, "position": "top", "fontSize": fs.get("label", 9)},
            }
        ],
    }


def render_degree_hist_png(
    nodes_csv: str | Path,
    plot_config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    df = pd.read_csv(nodes_csv)
    if "degree" in df.columns:
        degrees = df["degree"].dropna().astype(int).tolist()
    else:
        degrees = [1] * len(df)
    hist_color = _color_from_config(plot_config, "histogram_color", "#2ca02c")
    threshold_color = _color_from_config(plot_config, "threshold_color", "#d62728")
    fs = plot_config.get("font_size") or {}
    fig_w, fig_h = plot_config.get("figure_size") or [8.0, 5.0]
    avg_deg = float(np.mean(degrees)) if degrees else 0.0
    max_deg = max(degrees) if degrees else 0

    fig, ax = plt.subplots(figsize=(float(fig_w), float(fig_h)), facecolor="white")
    bins = range(0, max_deg + 2) if max_deg <= 20 else min(30, max_deg)
    ax.hist(degrees, bins=bins, color=hist_color, edgecolor="white", alpha=0.8, linewidth=0.5)
    ax.axvline(x=avg_deg, color=threshold_color, linestyle="--", linewidth=1.5, label=f"Mean ({avg_deg:.1f})")
    ax.set_xlabel("Degree", fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_ylabel("Number of Nodes", fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_title(plot_config.get("title", ""), fontproperties=_cjk(fs.get("title", 16), bold=True))
    ax.legend(prop=_cjk(fs.get("legend", 10)))
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def build_echarts_histogram(
    values: list[float],
    plot_config: dict[str, Any],
    *,
    x_name: str,
    vlines: list[tuple[float, str, str]] | None = None,
) -> dict[str, Any]:
    fs = plot_config.get("font_size") or {}
    hist_color = _color_from_config(plot_config, "histogram_color", "#4c72b0")
    series: list[dict[str, Any]] = [
        {
            "name": "Distribution",
            "type": "bar",
            "data": list(np.histogram(values, bins=40)[0].astype(int)),
            "itemStyle": {"color": hist_color},
        }
    ]
    # 简化：用 bar 近似直方图 counts
    counts, edges = np.histogram(values, bins=40)
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
    mark_lines = []
    if vlines:
        for x, name, color in vlines:
            mark_lines.append({"xAxis": x, "name": name, "lineStyle": {"color": color, "type": "dashed"}})
    return {
        "title": {"text": plot_config.get("title", ""), "textStyle": {"fontSize": fs.get("title", 16)}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 60, "right": 30, "top": 70, "bottom": 60},
        "xAxis": {"type": "category", "data": [f"{c:.2f}" for c in centers[:20]], "name": x_name},
        "yAxis": {"type": "value"},
        "series": [
            {
                "type": "bar",
                "data": counts.tolist(),
                "itemStyle": {"color": hist_color},
                "markLine": {"data": mark_lines} if mark_lines else None,
            }
        ],
    }


def render_cosine_hist_png(
    edges_csv: str | Path,
    plot_config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    df = pd.read_csv(edges_csv)
    if "cosine" not in df.columns:
        raise ValueError("network_edges.csv 缺少 cosine 列")
    cosines = df["cosine"].dropna().to_numpy(dtype=float)
    hist_color = _color_from_config(plot_config, "histogram_color", "#4c72b0")
    threshold_color = _color_from_config(plot_config, "threshold_color", "#d62728")
    median_color = _color_from_config(plot_config, "median_color", "#ff7f0e")
    fs = plot_config.get("font_size") or {}
    fig_w, fig_h = plot_config.get("figure_size") or [8.0, 5.0]
    median = float(np.median(cosines)) if len(cosines) else 0.0

    fig, ax = plt.subplots(figsize=(float(fig_w), float(fig_h)), facecolor="white")
    ax.hist(cosines, bins=40, color=hist_color, edgecolor="white", alpha=0.8, linewidth=0.5)
    ax.axvline(x=0.7, color=threshold_color, linestyle="--", linewidth=1.5, label="Threshold 0.7")
    ax.axvline(x=median, color=median_color, linestyle=":", linewidth=1.5, label=f"Median ({median:.3f})")
    ax.set_xlabel("Cosine Similarity", fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_ylabel("Frequency", fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_title(plot_config.get("title", ""), fontproperties=_cjk(fs.get("title", 16), bold=True))
    ax.legend(prop=_cjk(fs.get("legend", 10)))
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out
