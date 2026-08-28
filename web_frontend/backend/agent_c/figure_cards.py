"""结构化 figure card payload，供 API 与前端 Figure-first 报告。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_c.figure_ecb import ECB_LAYOUT_VERSION, build_ecb_blocks


def _png_rel(fig: dict[str, Any], results_root: Path) -> str | None:
    png = fig.get("png")
    if not png:
        return None
    path = Path(str(png)).resolve()
    root = results_root.resolve()
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return path.name


def figure_card_from_figure(
    fig: dict[str, Any],
    *,
    interpretation: dict[str, Any] | None = None,
    results_root: Path,
    zh: bool = True,
    insights_enabled: bool = False,
) -> dict[str, Any]:
    fid = str(fig.get("figure_id") or "")
    blocks = build_ecb_blocks(
        fig,
        interpretation,
        insights_enabled=insights_enabled,
        zh=zh,
    )

    return {
        "figure_id": fid,
        "plot_type": fig.get("plot_type") or "",
        "status": fig.get("status") or "",
        "rel": _png_rel(fig, results_root),
        "caption": str(fig.get("caption") or "").strip(),
        "source": fig.get("source") or "agent_c",
        "blocks": blocks,
    }


def build_figure_cards(
    report_figures: list[dict[str, Any]],
    figure_interpretations: dict[str, dict[str, Any]],
    *,
    results_root: Path,
    zh: bool = True,
    insights_enabled: bool = False,
) -> list[dict[str, Any]]:
    return [
        figure_card_from_figure(
            fig,
            interpretation=figure_interpretations.get(str(fig.get("figure_id") or "")),
            results_root=results_root,
            zh=zh,
            insights_enabled=insights_enabled,
        )
        for fig in report_figures
    ]


def normalize_figure_card_blocks(
    card: dict[str, Any],
    fig: dict[str, Any],
    *,
    interpretation: dict[str, Any] | None = None,
    insights_enabled: bool = False,
    zh: bool = True,
) -> dict[str, Any]:
    """将旧版 figure_card 规范为固定 E/C/B 三模块。"""
    out = dict(card)
    blocks = build_ecb_blocks(
        fig,
        interpretation,
        insights_enabled=insights_enabled,
        zh=zh,
    )
    out["blocks"] = blocks
    return out


def write_figure_cards_json(
    cards: list[dict[str, Any]],
    output_dir: Path,
    *,
    layout: str = "figure_first",
) -> Path:
    path = Path(output_dir) / "figure_cards.json"
    path.write_text(
        json.dumps(
            {
                "layout": layout,
                "ecb_layout_version": ECB_LAYOUT_VERSION,
                "figure_cards": cards,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


__all__ = [
    "build_figure_cards",
    "figure_card_from_figure",
    "normalize_figure_card_blocks",
    "write_figure_cards_json",
]
