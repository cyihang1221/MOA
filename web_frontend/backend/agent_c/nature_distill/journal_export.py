"""投稿导出：matplotlib 终稿 600 dpi + 矢量 PDF + 字号检查。

对齐/碰撞审计只在 matplotlib 终稿几何门可用后才接；Vega 预览阶段不做 PDF 几何检查。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 代谢组学主图 + 茶叶论文 matplotlib 终稿。Vega 只保留可编辑预览，不进这张清单。
JOURNAL_PLOT_TYPES = frozenset(
    {
        "pca",
        "plsda",
        "volcano",
        "vip_bar",
        "heatmap_vip",
        "network_topology",
        "constituent_bar",
        "relative_abundance_heatmap",
        "hca_heatmap",
        "correlation_heatmap",
        "bioactivity_bar",
        "sensory_scores",
        "plsda_permutation",
        "paper_fig2_composite",
        "paper_fig5_composite",
    }
)
JOURNAL_DPI = 600
MIN_FONT_PT = 6.0


def is_journal_plot(plot_type: str) -> bool:
    return str(plot_type or "").strip() in JOURNAL_PLOT_TYPES


def collect_font_sizes(fig) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def _add(role: str, artist: Any) -> None:
        if artist is None:
            return
        try:
            text = str(artist.get_text() or "")
            size = float(artist.get_fontsize())
        except Exception:
            return
        items.append({"role": role, "text": text[:48], "pt": size})

    for ax in fig.get_axes():
        _add("title", ax.title)
        _add("xlabel", ax.xaxis.label)
        _add("ylabel", ax.yaxis.label)
        for tick in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
            _add("tick", tick)
        for text in ax.texts:
            _add("text", text)
        legend = ax.get_legend()
        if legend is not None:
            for text in legend.get_texts():
                _add("legend", text)
            title = legend.get_title()
            if title is not None and str(title.get_text() or "").strip():
                _add("legend_title", title)
    for text in fig.texts:
        _add("figtext", text)
    return items


def audit_font_sizes(fig, *, min_pt: float = MIN_FONT_PT) -> dict[str, Any]:
    """字号下限检查。不拦截出图，只落盘警告。"""
    items = collect_font_sizes(fig)
    below = [row for row in items if row["pt"] + 1e-9 < min_pt]
    return {
        "min_pt": min_pt,
        "n_checked": len(items),
        "n_below": len(below),
        "below": below[:24],
        "ok": not below,
    }


def sidecar_path_for(png: str | Path) -> Path:
    path = Path(png)
    return path.with_name(path.stem + ".journal_export.json")


def load_journal_export(png: str | Path) -> dict[str, Any] | None:
    sidecar = sidecar_path_for(png)
    if not sidecar.is_file():
        return None
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def export_matplotlib_figure(fig, png_path: str | Path) -> dict[str, Any]:
    """PNG@600dpi + PDF 矢量；matplotlib SVG 另存为 *.journal.svg，避免盖掉 Vega 预览 SVG。"""
    png = Path(png_path)
    png.parent.mkdir(parents=True, exist_ok=True)
    audit = audit_font_sizes(fig)
    fig.savefig(png, dpi=JOURNAL_DPI, bbox_inches="tight", facecolor="white")
    pdf = png.with_suffix(".pdf")
    fig.savefig(pdf, format="pdf", bbox_inches="tight", facecolor="white")
    mpl_svg = png.with_name(png.stem + ".journal.svg")
    svg_ok = False
    try:
        fig.savefig(mpl_svg, format="svg", bbox_inches="tight", facecolor="white")
        svg_ok = mpl_svg.is_file()
    except Exception:
        svg_ok = False
    report = {
        "dpi": JOURNAL_DPI,
        "png": str(png),
        "pdf": str(pdf) if pdf.is_file() else None,
        "svg": str(mpl_svg) if svg_ok else None,
        "font_audit": audit,
        "collision_audit": "skipped_until_matplotlib_geometry_gate",
        "alignment_audit": "skipped_vega_preview_not_applicable",
    }
    sidecar = sidecar_path_for(png)
    sidecar.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


__all__ = [
    "JOURNAL_DPI",
    "JOURNAL_PLOT_TYPES",
    "MIN_FONT_PT",
    "audit_font_sizes",
    "collect_font_sizes",
    "export_matplotlib_figure",
    "is_journal_plot",
    "load_journal_export",
    "sidecar_path_for",
]
