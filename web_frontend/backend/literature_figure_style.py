"""首次出图的文献样式层：发表级基线 + 文献证据软样式。

与改图路径共用 EvidenceCard，但这里作用于 **初次渲染**，让 Agent C 第一版图
就接近文献风格。仍遵守软约束：只改样式，不改统计阈值与数据列。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ggsci 常用期刊配色（代谢组学论文高频）
JOURNAL_PALETTES: dict[str, tuple[str, ...]] = {
    "npg": ("#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F", "#8491B4", "#91D1C2", "#DC0000"),
    "aaas": ("#3B4992", "#EE0000", "#008B45", "#631879", "#008280", "#BB0021", "#5F559B", "#A20056"),
    "lancet": ("#00468B", "#ED0000", "#42B540", "#0099B4", "#925E9F", "#FDAF91", "#AD002A", "#ADB6B6"),
    "jama": ("#374E55", "#DF8F44", "#00A1D5", "#B24745", "#79AF97", "#6A6599", "#80796B"),
}

DEFAULT_JOURNAL = "npg"

# 期刊/配色关键词 → palette 名
_JOURNAL_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("npg", ("npg", "nature", "nature publishing", "ggsci")),
    ("aaas", ("aaas", "science", "sci_aaas")),
    ("lancet", ("lancet",)),
    ("jama", ("jama",)),
)

# 发表级基线：字号更大、图例统一、点更清晰。仅用于首次出图，不改全局默认。
_BASELINE_FONT = {"title": 18, "axis": 13, "legend": 12, "label": 10}

PUBLICATION_BASELINE: dict[str, dict[str, Any]] = {
    "pca": {
        "font_size": _BASELINE_FONT,
        "figure_size": [8.0, 6.5],
        "legend": {"show": True, "position": "right"},
        "marks": {"size": 90, "opacity": 0.85},
        "show_sample_labels": False,
        "title_align": "center",
    },
    "plsda": {
        "font_size": _BASELINE_FONT,
        "figure_size": [8.0, 6.5],
        "legend": {"show": True, "position": "right"},
        "marks": {"size": 90, "opacity": 0.85},
        "show_sample_labels": False,
        "title_align": "center",
    },
    "volcano": {
        "font_size": _BASELINE_FONT,
        "figure_size": [8.0, 6.5],
        "legend": {"show": True, "position": "right"},
        "marks": {"size": 55, "opacity": 0.85, "top_n": 8},
        "colors": {
            "upregulated": "#E64B35",
            "downregulated": "#4DBBD5",
            "nonsignificant": "#B0B0B0",
            "threshold_color": "#666666",
        },
        "title_align": "center",
    },
    "vip_bar": {
        "font_size": _BASELINE_FONT,
        "figure_size": [8.0, 6.0],
        "colors": {"bar_color": "#3C5488"},
        "title_align": "center",
    },
    "heatmap_vip": {
        "font_size": _BASELINE_FONT,
        "figure_size": [9.0, 7.0],
        "title_align": "center",
    },
    "cosine_hist": {
        "font_size": _BASELINE_FONT,
        "figure_size": [8.0, 5.5],
        "colors": {"histogram_color": "#4DBBD5", "threshold_color": "#E64B35"},
        "title_align": "center",
    },
    "degree_hist": {
        "font_size": _BASELINE_FONT,
        "figure_size": [8.0, 5.5],
        "colors": {"histogram_color": "#4DBBD5", "threshold_color": "#E64B35"},
        "title_align": "center",
    },
    "family_size": {
        "font_size": _BASELINE_FONT,
        "figure_size": [9.0, 5.5],
        "title_align": "center",
    },
    "network_topology": {
        "font_size": _BASELINE_FONT,
        "figure_size": [9.0, 8.0],
        "colors": {"edge_color": "#c8c8c8"},
        "title_align": "center",
    },
    "kegg_bubble": {
        "font_size": _BASELINE_FONT,
        "figure_size": [8.0, 6.5],
        "title_align": "center",
    },
}

# 文献常用标题措辞（弱建议：方案已给标题时不覆盖）
_TITLE_SUGGESTIONS: dict[str, str] = {
    "pca": "PCA Score Plot",
    "plsda": "PLS-DA Score Plot",
    "volcano": "Volcano Plot",
    "vip_bar": "VIP Scores",
    "heatmap_vip": "Top VIP Heatmap",
    "cosine_hist": "Cosine Similarity Distribution",
    "degree_hist": "Node Degree Distribution",
    "family_size": "Molecular Family Size Distribution",
    "network_topology": "Molecular Network Topology",
}

_LEGEND_POS_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("right", ("图例在右", "右侧", "legend right", "right legend")),
    ("bottom", ("图例在下", "下方", "legend bottom", "bottom legend")),
    ("top", ("图例在上", "上方", "legend top", "top legend")),
    ("left", ("图例在左", "左侧", "legend left")),
)

_THRESHOLD_MENTION_RE = re.compile(
    r"阈值|threshold|cutoff|p\s*[<＜]|fdr|padj|log2fc|logfc", re.IGNORECASE
)

_STYLE_CACHE: dict[tuple, dict[str, Any]] = {}


def env_enabled() -> bool:
    """沿用文献注入总开关。"""
    from web_frontend.backend.literature_plot_knowledge import env_enabled as _base_enabled

    return _base_enabled()


def _detect_journal(text: str) -> str | None:
    low = (text or "").lower()
    for name, hints in _JOURNAL_HINTS:
        if any(h in low for h in hints):
            return name
    return None


def _detect_legend_position(text: str) -> str | None:
    low = (text or "").lower()
    for pos, hints in _LEGEND_POS_HINTS:
        if any(h in low or h in (text or "") for h in hints):
            return pos
    return None


def _merge_style(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """浅层字典按 section 合并，extra 覆盖 base。"""
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for key, val in extra.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key].update(val)
        else:
            out[key] = dict(val) if isinstance(val, dict) else val
    return out


# 只有「分组/类别语义」的图型能按序列重排 palette；
# volcano 等图型的 palette 键是固定语义色（upregulated/threshold_color…），重排会串色。
_JOURNAL_PALETTE_TYPES = frozenset(
    {"pca", "plsda", "network_topology", "family_size", "heatmap_vip"}
)


def apply_journal_palette(
    plot_config: dict[str, Any],
    journal: str = DEFAULT_JOURNAL,
    *,
    plot_type: str = "",
) -> dict[str, Any]:
    """按 palette 现有键顺序赋期刊配色（键在 normalize 后才已知）。"""
    ptype = plot_type or str(plot_config.get("plot_type") or "")
    if ptype and ptype not in _JOURNAL_PALETTE_TYPES:
        return plot_config
    palette = plot_config.get("palette")
    if not isinstance(palette, dict) or not palette:
        return plot_config

    from web_frontend.backend.plot_theme import DEFAULT_COLORS

    if any(str(key) in DEFAULT_COLORS for key in palette):
        return plot_config

    colors = JOURNAL_PALETTES.get(journal) or JOURNAL_PALETTES[DEFAULT_JOURNAL]
    out = dict(plot_config)
    out["palette"] = {
        str(key): colors[i % len(colors)] for i, key in enumerate(palette.keys())
    }
    return out


def _style_from_evidence(
    plot_type: str,
    cards: list[dict[str, Any]],
    *,
    metadata_columns: list[str] | None = None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """从证据卡抽样式 patch。返回 (patch, applied_fields, warnings)。"""
    from web_frontend.backend.literature_evidence import build_style_patch_from_evidence

    return build_style_patch_from_evidence(
        plot_type, cards, metadata_columns=metadata_columns
    )


def resolve_figure_style(
    *,
    plot_type: str,
    goal_text: str = "",
    instruction: str = "",
    project_root: Path | None = None,
    use_literature: bool = True,
    max_cards: int = 4,
    sticky_skill_ids: list[str] | None = None,
    metadata_columns: list[str] | None = None,
) -> dict[str, Any]:
    """解析某图型的首次出图样式。

    Returns:
        patch: 可合并进 plot_config 的样式（不含 title）
        journal: 期刊配色名
        title_suggestion: 弱标题建议（方案已给标题时不应覆盖）
        evidence_refs / matched / warnings / applied_fields / source
    """
    if not plot_type:
        return _empty_style()

    cache_key = (
        plot_type,
        (goal_text or "")[:400],
        (instruction or "")[:200],
        str(project_root) if project_root else "",
        bool(use_literature),
        tuple(sticky_skill_ids or ()),
        tuple(metadata_columns or ()),
    )
    cached = _STYLE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    baseline = PUBLICATION_BASELINE.get(plot_type, {"font_size": _BASELINE_FONT})
    style: dict[str, Any] = {
        "patch": {k: (dict(v) if isinstance(v, dict) else v) for k, v in baseline.items()},
        "journal": DEFAULT_JOURNAL,
        "title_suggestion": _TITLE_SUGGESTIONS.get(plot_type, ""),
        "evidence_refs": [],
        "matched": [],
        "warnings": [],
        "applied_fields": ["publication_baseline"],
        "source": "baseline",
    }

    if not use_literature or not env_enabled():
        _STYLE_CACHE[cache_key] = style
        return style

    try:
        from web_frontend.backend.literature_evidence import collect_evidence_cards

        cards = collect_evidence_cards(
            plot_type=plot_type,
            goal_text=goal_text,
            instruction=instruction,
            project_root=project_root,
            max_cards=max_cards,
            sticky_skill_ids=sticky_skill_ids,
        )
    except Exception as exc:
        style["warnings"].append(f"文献样式未启用（证据加载失败）：{exc}")
        _STYLE_CACHE[cache_key] = style
        return style

    if not cards:
        _STYLE_CACHE[cache_key] = style
        return style

    lit_patch, applied, warnings = _style_from_evidence(
        plot_type, cards, metadata_columns=metadata_columns
    )
    journal = lit_patch.pop("_journal", None) or DEFAULT_JOURNAL

    style["patch"] = _merge_style(style["patch"], lit_patch)
    style["journal"] = journal
    style["applied_fields"] = style["applied_fields"] + applied
    style["warnings"] = style["warnings"] + warnings
    style["matched"] = sorted({str(c.get("skill_id") or "") for c in cards if c.get("skill_id")})
    style["evidence_refs"] = [
        {
            "evidence_id": c.get("evidence_id"),
            "skill_id": c.get("skill_id"),
            "doi": c.get("doi"),
            "claim_type": c.get("claim_type"),
            "quote": (c.get("quote") or "")[:200],
        }
        for c in cards
    ]
    style["source"] = "literature" if style["matched"] else "baseline"

    _STYLE_CACHE[cache_key] = style
    return style


def _empty_style() -> dict[str, Any]:
    return {
        "patch": {},
        "journal": DEFAULT_JOURNAL,
        "title_suggestion": "",
        "evidence_refs": [],
        "matched": [],
        "warnings": [],
        "applied_fields": [],
        "source": "none",
    }


def _is_placeholder_title(title: str, weak_titles: list[str] | None) -> bool:
    """方案常把 figure_id / plot_type 当标题占位，这类标题可被文献措辞替换。"""
    t = (title or "").strip().lower()
    if not t:
        return True
    if re.fullmatch(r"(figure|fig|图)\s*\d+", t):
        return True
    return any(t == str(w).strip().lower() for w in (weak_titles or []) if w)


def build_initial_plot_config(
    *,
    plot_type: str,
    plan_hint: dict[str, Any] | None = None,
    title: str = "",
    color_keys: list[str] | None = None,
    goal_text: str = "",
    project_root: Path | None = None,
    use_literature: bool = True,
    weak_titles: list[str] | None = None,
    sticky_skill_ids: list[str] | None = None,
    metadata_columns: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """构造首次出图的 plot_config。

    优先级：方案 hint > 文献/基线样式 > 系统默认。
    ``weak_titles`` 中的标题视为占位符，允许被文献标题措辞替换。
    Returns: (plot_config, style)
    """
    from web_frontend.backend.plot_theme import normalize_plot_config

    style = resolve_figure_style(
        plot_type=plot_type,
        goal_text=goal_text,
        project_root=project_root,
        use_literature=use_literature,
        sticky_skill_ids=sticky_skill_ids,
        metadata_columns=metadata_columns,
    )
    hint = dict(plan_hint or {})
    raw = _merge_style(style.get("patch") or {}, hint)

    # 方案显式标题优先；占位式标题（Figure 1 / plot_type）让位给文献措辞
    hint_title = str(hint.get("title") or "").strip()
    effective_title = hint_title or (title or "").strip()
    suggestion = str(style.get("title_suggestion") or "")
    if suggestion and not hint_title and _is_placeholder_title(effective_title, weak_titles):
        effective_title = suggestion
    if effective_title:
        raw["title"] = effective_title

    config = normalize_plot_config(raw, plot_type=plot_type, color_keys=color_keys or [])
    if "palette" not in hint and style.get("journal"):
        config = apply_journal_palette(config, str(style["journal"]), plot_type=plot_type)

    # palette 与 colors 同名键必须一致，否则前端色板会显示与实际渲染不同的颜色
    colors = config.get("colors") if isinstance(config.get("colors"), dict) else {}
    palette = config.get("palette") if isinstance(config.get("palette"), dict) else {}
    for key in list(palette):
        if key in colors:
            palette[key] = colors[key]

    if style.get("matched") or style.get("applied_fields"):
        config["literature_style"] = {
            "source": style.get("source"),
            "journal": style.get("journal"),
            "matched": style.get("matched") or [],
            "applied_fields": style.get("applied_fields") or [],
            "evidence_refs": style.get("evidence_refs") or [],
            "warnings": style.get("warnings") or [],
        }
    return config, style


def style_provenance_line(style: dict[str, Any] | None, *, language: str = "zh") -> str:
    """一行来源说明，供图注/报告标注文献依据。"""
    if not style:
        return ""
    zh = (language or "zh").lower().startswith("zh")
    matched = [m for m in (style.get("matched") or []) if m]
    journal = style.get("journal") or DEFAULT_JOURNAL
    if style.get("source") == "literature" and matched:
        dois = sorted({str(r.get("doi")) for r in (style.get("evidence_refs") or []) if r.get("doi")})
        cite = "、".join(matched[:2])
        doi_part = f"，DOI:{'; '.join(dois[:2])}" if dois else ""
        return (
            f"作图规范：参考文献 Skill {cite}{doi_part}；配色 {journal}。"
            if zh
            else f"Figure style: literature skills {cite}{doi_part}; palette {journal}."
        )
    return (
        f"作图规范：发表级基线样式，配色 {journal}（未匹配到针对性文献）。"
        if zh
        else f"Figure style: publication baseline, palette {journal} (no literature match)."
    )


def clear_style_cache() -> None:
    _STYLE_CACHE.clear()


__all__ = [
    "JOURNAL_PALETTES",
    "DEFAULT_JOURNAL",
    "PUBLICATION_BASELINE",
    "resolve_figure_style",
    "build_initial_plot_config",
    "apply_journal_palette",
    "style_provenance_line",
    "clear_style_cache",
    "env_enabled",
]
