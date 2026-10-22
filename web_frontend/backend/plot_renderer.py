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
    resolve_volcano_thresholds,
)

configure_matplotlib_cjk()


def _cjk(size: float | int | None = None, *, bold: bool = False):
    return cjk_fontproperties(size=size, bold=bold)


def _savefig(fig, out: Path, *, plot_type: str = "") -> None:
    """普通预览 300 dpi；PCA/火山/VIP/热图走投稿导出（600 dpi + 矢量）。"""
    from web_frontend.backend.agent_c.nature_distill.journal_export import (
        export_matplotlib_figure,
        is_journal_plot,
    )

    if is_journal_plot(plot_type):
        export_matplotlib_figure(fig, out)
        return
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")


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
            "splitLine": {"show": False},
        },
        "yAxis": {
            "name": axis_names[y_idx],
            "nameTextStyle": {"fontSize": fs.get("axis", 12)},
            "axisLabel": {"fontSize": fs.get("axis", 12)},
            "splitLine": {"show": False},
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
    data_dir: str | Path | None = None,
    plot_type: str = "",
    metadata_csv: str | Path | None = None,
) -> Path:
    """PCA / PLS-DA 得分图。有 R 时用 ggplot2，score_style 只作为参数。"""
    from web_frontend.backend.ggplot_score_plot import GGPLOT_STYLE, render_ggplot_score_png
    from web_frontend.backend.paper_plot_helpers import read_explained_variance
    from web_frontend.backend.r_plot_backend import render_score_r
    from web_frontend.backend.simca_score_plot import render_simca_score_png

    inferred = plot_type or ("pca" if str(axis_names[0]).upper().startswith("PC") else "plsda")
    try:
        return render_score_r(
            output_path=output_path,
            data_dir=data_dir,
            metadata_csv=metadata_csv,
            plot_config=plot_config,
            plot_type=inferred,
        )
    except FileNotFoundError:
        pass
    try:
        ratios = read_explained_variance(Path(data_dir) if data_dir else Path(output_path).parent, inferred)
    except Exception:
        ratios = []
    legend_title, color_type = score_color_meta(plot_config)
    style = str(plot_config.get("score_style") or "simca").strip().lower()
    use_ggplot = style in {GGPLOT_STYLE, "ggplot2"}
    renderer = render_ggplot_score_png if use_ggplot else render_simca_score_png
    extra: dict[str, Any] = {"metadata_csv": metadata_csv} if use_ggplot else {}
    return renderer(
        scores=scores,
        groups=[str(g) for g in groups],
        sample_names=sample_names,
        axis_names=axis_names,
        plot_config=plot_config,
        output_path=output_path,
        plot_type=inferred,
        ratios=ratios,
        legend_title=legend_title,
        quantitative=color_type == "quantitative",
        **extra,
    )


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
    from web_frontend.backend.r_plot_backend import render_volcano_r

    try:
        return render_volcano_r(volcano_csv, plot_config, output_path)
    except FileNotFoundError:
        pass
    df = pd.read_csv(volcano_csv)
    required = {"log2FC", "neglog10p"}
    if not required.issubset(df.columns):
        raise ValueError("volcano_results.csv 缺少 log2FC / neglog10p 列")

    thresholds = resolve_volcano_thresholds(plot_config)
    p_cut = float(thresholds["p"]) if thresholds.get("p") is not None else None
    if thresholds.get("padj") is not None and p_cut is None:
        p_cut = float(thresholds["padj"])
    fc_cut = float(thresholds["log2fc"]) if thresholds.get("log2fc") is not None else None
    if p_cut is not None or fc_cut is not None:
        p_mask = pd.Series(True, index=df.index)
        fc_mask = pd.Series(True, index=df.index)
        if p_cut is not None:
            if "pvalue" in df.columns:
                p_mask = pd.to_numeric(df["pvalue"], errors="coerce").lt(p_cut)
            elif "padj" in df.columns:
                p_mask = pd.to_numeric(df["padj"], errors="coerce").lt(p_cut)
            else:
                p_mask = pd.to_numeric(df["neglog10p"], errors="coerce").ge(
                    -np.log10(max(p_cut, 1e-300))
                )
        if fc_cut is not None:
            fc_mask = pd.to_numeric(df["log2FC"], errors="coerce").abs().ge(fc_cut)
        sig_mask = (p_mask & fc_mask).fillna(False)
    elif "Significant" in df.columns:
        sig_mask = df["Significant"].astype(bool)
    else:
        sig_mask = pd.Series(True, index=df.index)

    up_mask = sig_mask & df["log2FC"].gt(0)
    down_mask = sig_mask & df["log2FC"].lt(0)
    nonsig_mask = ~sig_mask
    up_color = _color_from_config(
        plot_config,
        "upregulated",
        _color_from_config(plot_config, "significant", "#E64B35"),
    )
    down_color = _color_from_config(plot_config, "downregulated", "#4DBBD5")
    nonsig_color = _color_from_config(plot_config, "nonsignificant", "#B0B0B0")
    threshold_color = _color_from_config(plot_config, "threshold_color", "#666666")
    fs = plot_config.get("font_size") or {}
    marks = plot_config.get("marks") or {}
    fig_w, fig_h = plot_config.get("figure_size") or [8.0, 6.5]
    size_sig = max(20, int(marks.get("size") or 55))
    size_ns = max(10, size_sig - 20)
    alpha_sig = float(marks.get("opacity") or 0.85)
    top_n = max(0, int(marks.get("top_n") or 8))

    fig, ax = plt.subplots(figsize=(float(fig_w), float(fig_h)), facecolor="white")
    if nonsig_mask.any():
        ax.scatter(
            df.loc[nonsig_mask, "log2FC"],
            df.loc[nonsig_mask, "neglog10p"],
            c=nonsig_color,
            s=size_ns,
            alpha=0.55,
            linewidths=0,
            label=f"Not significant ({int(nonsig_mask.sum())})",
            zorder=1,
        )
    if up_mask.any():
        ax.scatter(
            df.loc[up_mask, "log2FC"],
            df.loc[up_mask, "neglog10p"],
            c=up_color,
            s=size_sig,
            alpha=alpha_sig,
            linewidths=0.4,
            edgecolors="white",
            label=f"Upregulated ({int(up_mask.sum())})",
            zorder=3,
        )
    if down_mask.any():
        ax.scatter(
            df.loc[down_mask, "log2FC"],
            df.loc[down_mask, "neglog10p"],
            c=down_color,
            s=size_sig,
            alpha=alpha_sig,
            linewidths=0.4,
            edgecolors="white",
            label=f"Downregulated ({int(down_mask.sum())})",
            zorder=3,
        )
    if fc_cut is not None:
        ax.axvline(-fc_cut, color=threshold_color, linestyle="--", linewidth=1.2, zorder=2)
        ax.axvline(fc_cut, color=threshold_color, linestyle="--", linewidth=1.2, zorder=2)
    if p_cut is not None:
        y_thr = -np.log10(max(p_cut, 1e-300))
        ax.axhline(y_thr, color=threshold_color, linestyle="--", linewidth=1.2, zorder=2)

    # 标注 top 显著特征（代谢物 ID）
    label_col = next(
        (c for c in ("Feature", "feature_id", "name", "metabolite") if c in df.columns),
        None,
    )
    if top_n > 0 and label_col and sig_mask.any():
        label_df = df.loc[sig_mask].nlargest(top_n, "neglog10p")
        for _, row in label_df.iterrows():
            ax.annotate(
                str(row[label_col]),
                (float(row["log2FC"]), float(row["neglog10p"])),
                textcoords="offset points",
                xytext=(4, 4),
                fontsize=max(8, int(fs.get("label") or 10)),
                fontproperties=_cjk(fs.get("label", 10)),
                color="#333333",
                zorder=4,
            )

    thr_parts: list[str] = []
    if p_cut is not None:
        thr_parts.append(f"p<{p_cut:g}")
    if fc_cut is not None:
        thr_parts.append(f"|log2FC|≥{fc_cut:g}")
    if thr_parts:
        ax.text(
            0.02,
            0.02,
            "Thresholds: " + ", ".join(thr_parts),
            transform=ax.transAxes,
            fontsize=max(9, int(fs.get("label") or 10)),
            fontproperties=_cjk(fs.get("label", 10)),
            color="#555555",
            va="bottom",
        )

    ax.legend(
        prop=_cjk(fs.get("legend", 11)),
        frameon=True,
        framealpha=0.92,
        edgecolor="#dddddd",
        loc="upper right",
    )
    ax.set_title(
        plot_config.get("title", "Volcano Plot"),
        fontproperties=_cjk(fs.get("title", 16), bold=True),
        pad=12,
    )
    ax.set_xlabel("log2 Fold Change", fontproperties=_cjk(fs.get("axis", 12)))
    ax.set_ylabel("-log10(P value)", fontproperties=_cjk(fs.get("axis", 12)))
    ax.tick_params(labelsize=fs.get("axis", 12))
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#888888")
    ax.spines["bottom"].set_color("#888888")
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _savefig(fig, out, plot_type="volcano")
    plt.close(fig)
    return out


def build_echarts_volcano(volcano_csv: str | Path, plot_config: dict[str, Any]) -> dict[str, Any]:
    df = pd.read_csv(volcano_csv)
    thresholds = resolve_volcano_thresholds(plot_config)
    p_cut = float(thresholds["p"]) if thresholds.get("p") is not None else None
    if thresholds.get("padj") is not None and p_cut is None:
        p_cut = float(thresholds["padj"])
    fc_cut = float(thresholds["log2fc"]) if thresholds.get("log2fc") is not None else None
    if p_cut is not None or fc_cut is not None:
        p_mask = pd.Series(True, index=df.index)
        fc_mask = pd.Series(True, index=df.index)
        if p_cut is not None:
            if "pvalue" in df.columns:
                p_mask = pd.to_numeric(df["pvalue"], errors="coerce").lt(p_cut)
            elif "padj" in df.columns:
                p_mask = pd.to_numeric(df["padj"], errors="coerce").lt(p_cut)
            else:
                p_mask = pd.to_numeric(df["neglog10p"], errors="coerce").ge(
                    -np.log10(max(p_cut, 1e-300))
                )
        if fc_cut is not None:
            fc_mask = pd.to_numeric(df["log2FC"], errors="coerce").abs().ge(fc_cut)
        sig_mask = (p_mask & fc_mask).fillna(False)
    elif "Significant" in df.columns:
        sig_mask = df["Significant"].astype(bool)
    else:
        sig_mask = pd.Series(True, index=df.index)

    up_color = _color_from_config(
        plot_config,
        "upregulated",
        _color_from_config(plot_config, "significant", "#E64B35"),
    )
    down_color = _color_from_config(plot_config, "downregulated", "#4DBBD5")
    nonsig_color = _color_from_config(plot_config, "nonsignificant", "#B0B0B0")
    threshold_color = _color_from_config(plot_config, "threshold_color", "#d62728")
    fs = plot_config.get("font_size") or {}
    series = []
    for label, mask, color in (
        ("Not significant", ~sig_mask, nonsig_color),
        ("Upregulated", sig_mask & df["log2FC"].gt(0), up_color),
        ("Downregulated", sig_mask & df["log2FC"].lt(0), down_color),
    ):
        if mask.any():
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
    mark_lines = []
    if fc_cut is not None:
        mark_lines.extend([{"xAxis": -fc_cut}, {"xAxis": fc_cut}])
    if p_cut is not None:
        mark_lines.append({"yAxis": float(-np.log10(max(p_cut, 1e-300)))})
    if mark_lines and series:
        series[0]["markLine"] = {
            "silent": True,
            "symbol": ["none", "none"],
            "lineStyle": {"color": threshold_color, "type": "dashed", "width": 1.5},
            "label": {"show": False},
            "data": mark_lines,
        }
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
    # 每个家族都只有 1 个节点时，不要画几十根高度为 1 的柱，再把尾巴加成一根高柱。
    if sorted_fams and all(size == 1 for _, size in sorted_fams):
        n = len(sorted_fams) + n_singletons
        return [f"{n} singleton families"], [n], ["#bdbdbd"]
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
        head = max_display - 1
        tail = sizes[head:]
        if tail and all(size == 1 for size in tail):
            labels = labels[:head] + [f"{len(tail)} singleton families"]
            sizes = sizes[:head] + [len(tail)]
            colors = colors[:head] + ["#bdbdbd"]
        else:
            labels = labels[:max_display]
            sizes = sizes[:max_display]
            colors = colors[:max_display]
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
    if len(labels) == 1 and "singleton families" in labels[0]:
        # 家族大小分布：横轴是家族里有几个节点，纵轴是有多少个这样的家族。
        n_families = int(sizes[0])
        ax.bar([1], [n_families], width=0.45, color="#3C5488", edgecolor="white")
        ax.text(1, n_families, str(n_families), ha="center", va="bottom", fontproperties=_cjk(fs.get("label", 9)))
        ax.set_xlim(0.2, 3.2)
        ax.set_xticks([1, 2, 3])
        ax.set_xlabel("Nodes in a family", fontproperties=_cjk(fs.get("axis", 12)))
        ax.set_ylabel("Number of families", fontproperties=_cjk(fs.get("axis", 12)))
        title = str(plot_config.get("title") or "Molecular Family Size Distribution")
        ax.set_title(f"{title}\nEvery family contains one node", fontproperties=_cjk(fs.get("title", 14), bold=True))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        return out
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
    title = str(plot_config.get("title") or "Molecular Family Size Distribution")
    if len(labels) == 1 and "singleton families" in labels[0]:
        title = f"{title}\nEach family has 1 node"
    ax.set_title(title, fontproperties=_cjk(fs.get("title", 16), bold=True))
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


def render_vip_bar_png(
    data_dir: str | Path,
    plot_config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """VIP 条形图：有 R 时用 ggplot2，否则回退 matplotlib。"""
    from web_frontend.backend.paper_plot_helpers import (
        direction_from_log2fc,
        join_vip_volcano,
        show_grid_enabled,
        vip_threshold_from_config,
    )
    from web_frontend.backend.r_plot_backend import render_vip_bar_r

    try:
        return render_vip_bar_r(data_dir, plot_config, output_path)
    except FileNotFoundError:
        pass

    frame = join_vip_volcano(data_dir)
    if "Feature" not in frame.columns or "VIP" not in frame.columns:
        raise ValueError("vip_scores.csv 缺少 Feature / VIP 列")
    top_n = int((plot_config.get("marks") or {}).get("top_n") or 30)
    top = frame.dropna(subset=["VIP"]).sort_values("VIP", ascending=True).tail(max(5, top_n))
    colors = plot_config.get("colors") or {}
    up_color = colors.get("upregulated", "#E64B35")
    down_color = colors.get("downregulated", "#4DBBD5")
    unk_color = colors.get("bar_color", "#3C5488")
    threshold = vip_threshold_from_config(plot_config)
    bar_colors = []
    labels = []
    for _, row in top.iterrows():
        direction = direction_from_log2fc(row.get("log2FC"))
        bar_colors.append({"up": up_color, "down": down_color}.get(direction, unk_color))
        label = str(row["Feature"])
        mz = row.get("precursor_mz")
        if pd.notna(mz):
            try:
                label = f"{label} ({float(mz):.4f})"
            except (TypeError, ValueError):
                pass
        labels.append(label)
    fs = plot_config.get("font_size") or {}
    fig_w, fig_h = plot_config.get("figure_size") or [7.5, max(4.5, 0.22 * len(top) + 1.6)]
    fig, ax = plt.subplots(figsize=(float(fig_w), float(fig_h)), facecolor="white")
    ax.barh(range(len(top)), top["VIP"].to_numpy(dtype=float), color=bar_colors, edgecolor="white", height=0.72)
    ax.axvline(threshold, color=colors.get("threshold_color", "#666666"), linestyle="--", linewidth=1.1)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(labels, fontproperties=_cjk(fs.get("label", 8)))
    ax.set_xlabel("VIP", fontproperties=_cjk(fs.get("axis", 11)))
    ax.set_title(plot_config.get("title") or "VIP Scores", fontproperties=_cjk(fs.get("title", 14), bold=True))
    ax.text(
        0.99,
        0.02,
        f"VIP = {threshold:g}  |  red: log2FC>0  blue: log2FC<0",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontproperties=_cjk(8),
        color="#555555",
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if show_grid_enabled(plot_config):
        ax.grid(True, axis="x", color="#ebebeb", linewidth=0.6)
        ax.set_axisbelow(True)
    else:
        ax.grid(False)
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _savefig(fig, out, plot_type="vip_bar")
    plt.close(fig)
    return out


def render_heatmap_vip_png(
    data_dir: str | Path,
    plot_config: dict[str, Any],
    output_path: str | Path,
    *,
    metadata_csv: str | Path | None = None,
) -> Path:
    """VIP 热图：有 R 时用 pheatmap，否则回退 matplotlib。"""
    from web_frontend.backend.r_plot_backend import render_heatmap_r

    try:
        return render_heatmap_r(data_dir, plot_config, output_path, metadata_csv)
    except FileNotFoundError:
        pass

    from matplotlib.gridspec import GridSpec

    from web_frontend.backend.agent_c.tea_paper_plots import _draw_clustered_heatmap
    from web_frontend.backend.paper_plot_helpers import (
        DEFAULT_HEATMAP_MAX_ROWS,
        group_color,
        heatmap_figure_inches,
        infer_group_from_sample,
        unique_display_ids,
    )
    from web_frontend.backend.plot_edit_registry import resolve_plot_data_file

    matrix_path = resolve_plot_data_file(Path(data_dir), "heatmap_top_vip_matrix.csv")
    if matrix_path is None:
        raise ValueError("缺少 heatmap_top_vip_matrix.csv")
    frame = pd.read_csv(matrix_path, index_col=0)
    if frame.empty:
        raise ValueError("heatmap_top_vip_matrix.csv 为空")
    mat = frame.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    samples = [str(c) for c in frame.columns]
    features = [str(i) for i in frame.index]
    max_rows = int((plot_config.get("marks") or {}).get("top_n") or DEFAULT_HEATMAP_MAX_ROWS)
    if len(features) > max_rows:
        score = np.nanvar(mat, axis=1)
        keep = np.argsort(np.nan_to_num(score, nan=-1.0))[::-1][:max_rows]
        mat = mat[keep]
        features = [features[i] for i in keep]
    features = unique_display_ids(features)
    group_map: dict[str, str] = {}
    if metadata_csv and Path(metadata_csv).is_file():
        try:
            meta = pd.read_csv(metadata_csv)
            sample_col = "Sample" if "Sample" in meta.columns else meta.columns[0]
            group_col = "Group" if "Group" in meta.columns else None
            if group_col:
                for _, row in meta.iterrows():
                    group_map[str(row[sample_col]).replace(".mzML", "").replace(".mzml", "")] = str(row[group_col])
        except Exception:
            group_map = {}
    groups = []
    for sample in samples:
        key = str(sample).replace(".mzML", "").replace(".mzml", "")
        groups.append(group_map.get(key) or infer_group_from_sample(key))
    uniq = list(dict.fromkeys(groups))
    palette = plot_config.get("palette") or {}
    col_colors = [group_color(g, palette, uniq.index(g) if g in uniq else 0) for g in groups]
    cmap = str(plot_config.get("cmap") or "RdBu_r")
    fig = plt.figure(figsize=heatmap_figure_inches(len(samples), len(features)))
    gs = GridSpec(2, 2, width_ratios=[0.16, 1.0], height_ratios=[0.14, 1.0], hspace=0.03, wspace=0.04, figure=fig)
    ax_col = fig.add_subplot(gs[0, 1])
    ax_row = fig.add_subplot(gs[1, 0])
    ax = fig.add_subplot(gs[1, 1])
    im = _draw_clustered_heatmap(
        ax,
        mat,
        features,
        samples,
        cmap=cmap,
        vmin=None,
        vmax=None,
        row_dendro_ax=ax_row,
        col_dendro_ax=ax_col,
        col_colors=col_colors,
        fontsize=9,
    )
    ax.yaxis.tick_right()
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.12, label="Z-score")
    ax.set_title(plot_config.get("title") or "Top VIP heatmap", fontproperties=_cjk(12, bold=True), pad=28)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _savefig(fig, out, plot_type="heatmap_vip")
    plt.close(fig)
    return out


_GROUP_COLORS = {
    "BK": "#E64B35",
    "DY": "#4DBBD5",
    "QC": "#00A087",
    "Control": "#4DBBD5",
    "Case": "#E64B35",
}
_GROUP_EXTRA = ["#3C5488", "#F39B7F", "#8491B4", "#91D1C2", "#7E6148", "#DC0000"]


def _group_color(name: str, index: int) -> str:
    return _GROUP_COLORS.get(name) or _GROUP_EXTRA[index % len(_GROUP_EXTRA)]


def _add_intensity_pie(ax, x: float, y: float, radius: float, fractions, colors) -> None:
    """节点饼图：各组平均强度占比。单组占满时画实心圆，避免 360° 扇形消失。"""
    from matplotlib.patches import Circle, Wedge

    vals = np.asarray(list(fractions), dtype=float)
    vals = np.where(np.isfinite(vals) & (vals > 0), vals, 0.0)
    total = float(vals.sum())
    if total <= 0 or radius <= 0:
        ax.add_patch(Circle((x, y), radius, facecolor="#d9d9d9", edgecolor="#333333", linewidth=0.4, zorder=3))
        return
    vals = vals / total
    if float(vals.max()) >= 0.995:
        color = colors[int(np.argmax(vals))]
        ax.add_patch(Circle((x, y), radius, facecolor=color, edgecolor="#333333", linewidth=0.45, zorder=3))
        return
    theta = 90.0
    for frac, color in zip(vals, colors):
        if frac <= 0.004:
            continue
        sweep = 360.0 * float(frac)
        ax.add_patch(
            Wedge(
                (x, y),
                radius,
                theta - sweep,
                theta,
                facecolor=color,
                edgecolor="white",
                linewidth=0.3,
                zorder=3,
            )
        )
        theta -= sweep
    ax.add_patch(Circle((x, y), radius, fill=False, edgecolor="#333333", linewidth=0.45, zorder=4))


def render_network_topology_png(
    data_dir: str | Path,
    plot_config: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """期刊式分子网络：饼图表示各组强度占比，面积表示强度，边按余弦。没有边时按 m/z 排列，不画圆环。"""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    from web_frontend.backend.paper_plot_helpers import hide_isolates_enabled
    from web_frontend.backend.plot_edit_registry import resolve_plot_data_file

    root = Path(data_dir)
    nodes_path = resolve_plot_data_file(root, "network_nodes.csv")
    if nodes_path is None:
        raise FileNotFoundError("缺少 network_nodes.csv / fbmn_nodes.csv")
    nodes = pd.read_csv(nodes_path)
    id_col = next((c for c in ("feature_id", "node_id", "id") if c in nodes.columns), None)
    if id_col is None:
        raise ValueError("节点表缺少 feature_id")
    nodes = nodes.copy()
    nodes["_id"] = nodes[id_col].astype(str)
    mz_col = next((c for c in ("precursor_mz", "mz", "mz_med") if c in nodes.columns), None)
    if mz_col:
        nodes["_mz"] = pd.to_numeric(nodes[mz_col], errors="coerce")
    else:
        nodes["_mz"] = np.arange(len(nodes), dtype=float)
    group_cols = [c for c in nodes.columns if str(c).startswith("mean_")]
    groups = [str(c)[len("mean_") :] for c in group_cols]
    palette = plot_config.get("palette") or {}
    colors = [palette.get(g) or _group_color(g, i) for i, g in enumerate(groups)]
    means = (
        nodes[group_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).clip(lower=0.0)
        if group_cols
        else pd.DataFrame(np.ones((len(nodes), 1)), index=nodes.index)
    )
    if not group_cols:
        groups, colors = ["feature"], ["#3C5488"]
    totals = means.sum(axis=1).to_numpy(dtype=float)
    logs = np.log10(totals + 1.0)
    log_span = float(logs.max() - logs.min()) if len(logs) else 1.0
    if log_span < 1e-9:
        log_span = 1.0
    norm = (logs - logs.min()) / log_span

    edges = pd.DataFrame(columns=["source", "target", "cosine"])
    edges_path = resolve_plot_data_file(root, "network_edges.csv")
    if edges_path is not None:
        loaded = pd.read_csv(edges_path)
        if {"source", "target"}.issubset(loaded.columns) and len(loaded):
            edges = loaded.copy()
            edges["source"] = edges["source"].astype(str)
            edges["target"] = edges["target"].astype(str)
    keep_ids = set(nodes["_id"])
    if len(edges) and hide_isolates_enabled(plot_config):
        linked = set(edges["source"]).union(set(edges["target"]))
        linked &= keep_ids
        if len(linked) >= 3:
            nodes = nodes[nodes["_id"].isin(linked)].copy()
            means = means.loc[nodes.index]
            totals = means.sum(axis=1).to_numpy(dtype=float)
            logs = np.log10(totals + 1.0)
            log_span = float(max(logs.max() - logs.min(), 1e-9))
            norm = (logs - logs.min()) / log_span
            keep_ids = set(nodes["_id"])
            edges = edges[edges["source"].isin(keep_ids) & edges["target"].isin(keep_ids)]
    n_nodes = len(nodes)
    n_edges = len(edges)
    n_hidden = 0
    if nodes_path is not None:
        n_hidden = max(0, sum(1 for _ in open(nodes_path)) - 1 - n_nodes)

    pos: dict[str, tuple[float, float]] = {}
    ordered = nodes.sort_values("_mz", kind="mergesort")
    if n_edges == 0:
        ncol = 8 if n_nodes > 12 else max(1, int(np.ceil(np.sqrt(n_nodes))))
        for i, (_, row) in enumerate(ordered.iterrows()):
            pos[row["_id"]] = (float(i % ncol), float(-(i // ncol) * 1.35))
        radius_unit = 0.34
    else:
        import networkx as nx

        graph = nx.Graph()
        graph.add_nodes_from(nodes["_id"])
        for _, row in edges.iterrows():
            graph.add_edge(str(row["source"]), str(row["target"]))
        raw_pos = nx.spring_layout(graph, seed=42, k=1.6 / max(n_nodes ** 0.5, 1), iterations=80)
        pos = {node: (float(xy[0]), float(xy[1])) for node, xy in raw_pos.items()}
        span = max(
            max(p[0] for p in pos.values()) - min(p[0] for p in pos.values()),
            max(p[1] for p in pos.values()) - min(p[1] for p in pos.values()),
            1e-6,
        )
        radius_unit = 0.055 * span

    fig_w, fig_h = plot_config.get("figure_size") or [9.2, 7.2]
    fig, ax = plt.subplots(figsize=(float(fig_w), float(fig_h)), facecolor="white")
    for _, row in edges.iterrows():
        p1 = pos.get(str(row["source"]))
        p2 = pos.get(str(row["target"]))
        if not p1 or not p2:
            continue
        try:
            cosine = float(row["cosine"]) if "cosine" in edges.columns else 0.7
        except (TypeError, ValueError):
            cosine = 0.7
        width = 0.6 + max(0.0, min(cosine, 1.0)) * 1.8
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#bdbdbd", lw=width, solid_capstyle="round", zorder=1)
    id_to_i = {node_id: i for i, node_id in enumerate(nodes["_id"])}
    for _, row in nodes.iterrows():
        node_id = row["_id"]
        xy = pos.get(node_id)
        if xy is None:
            continue
        i = id_to_i[node_id]
        radius = radius_unit * (0.62 + 0.55 * float(norm[list(nodes.index).index(row.name)]))
        fracs = means.loc[row.name].to_numpy(dtype=float)
        _add_intensity_pie(ax, xy[0], xy[1], radius, fracs, colors)
        if n_edges == 0 and pd.notna(row["_mz"]):
            ax.text(
                xy[0],
                xy[1] - radius - 0.10,
                f"{float(row['_mz']):.1f}",
                ha="center",
                va="top",
                fontsize=6,
                color="#555555",
                zorder=5,
            )
    xs = [p[0] for p in pos.values()] or [0.0]
    ys = [p[1] for p in pos.values()] or [0.0]
    pad = 0.72 if n_edges == 0 else radius_unit * 3
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad * (1.15 if n_edges == 0 else 1), max(ys) + pad * 0.85)
    ax.set_aspect("equal")
    ax.axis("off")
    title = str(plot_config.get("title") or "Molecular network")
    ax.set_title(title, loc="left", fontproperties=_cjk(13, bold=True), pad=8)
    note = f"{n_nodes} nodes, {n_edges} edges"
    if n_hidden:
        note += f"; {n_hidden} isolates not shown"
    if n_edges == 0:
        note += ". No pair passed the similarity cut-off; nodes are ordered by precursor m/z"
    note += ". Pie: share of mean intensity. Area scales with log intensity."
    ax.text(0.0, -0.04, note, transform=ax.transAxes, ha="left", va="top", fontsize=8, color="#444444")
    handles = [Patch(facecolor=color, edgecolor="#333333", label=group) for group, color in zip(groups, colors)]
    if n_edges:
        handles.append(Line2D([0], [0], color="#bdbdbd", lw=2.0, label="spectral edge"))
    ax.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        frameon=False,
        prop=_cjk(9),
        title="Group",
        title_fontproperties=_cjk(9, bold=True),
    )
    fig.tight_layout()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    _savefig(fig, out, plot_type="network_topology")
    plt.close(fig)
    return out
