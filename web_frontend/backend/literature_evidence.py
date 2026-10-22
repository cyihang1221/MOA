"""从文献 Skill 抽取结构化证据卡（EvidenceCard）并生成可落地的样式 patch。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from web_frontend.backend.literature_plot_knowledge import (
    _SKILL_POOL_PLOT,
    _plot_terms_for_type,
    rank_skills_for_plot,
)

# plot_config 字段 ← 文献描述关键词
_FIELD_HINT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("title", ("标题", "title", "score plot", "volcano plot", "heatmap")),
    ("font_size.title", ("字号", "font size", "字体", "font_size")),
    ("title_align", ("靠左", "居中", "靠右", "left", "center", "right")),
    ("palette", ("着色", "颜色", "palette", "colour", "color", "ggsci", "npg")),
    ("colors.significant", ("显著", "上调", "下调", "significant", "upregulated", "downregulated")),
    ("colors.bar_color", ("柱状", "bar color", "bar_color")),
    ("colors.histogram_color", ("直方", "histogram")),
    ("colors.edge_color", ("边", "edge", "灰色")),
    ("legend.position", ("图例", "legend")),
    ("legend.show", ("显示图例", "show legend")),
    ("axes", ("坐标", "轴", "axis", "log2", "p value", "阈值", "threshold")),
    ("cluster", ("聚类", "cluster", "kmeans")),
    ("color_by", ("按", "分组", "group", "batch", "metadata", "着色")),
    ("show_sample_labels", ("样本标签", "sample label")),
    ("marks.size", ("点大小", "marker size", "散点")),
]

_CLAIM_INFERRED = "inferred"
_CLAIM_PROTOCOL = "protocol_start"
_CLAIM_LITERATURE = "literature_example"
_CLAIM_STRUCTURED = "structured_spec"

_COLOR_BY_ALIASES: tuple[tuple[str, str], ...] = (
    ("batch", "Batch"),
    ("group", "Group"),
    ("time", "Time"),
    ("class", "Class"),
)

_THRESHOLD_MENTION_RE = re.compile(
    r"阈值|threshold|cutoff|p\s*[<＜]|fdr|padj|log2fc|logfc", re.IGNORECASE
)

_JOURNAL_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("okabe_ito", ("okabe", "色盲", "色觉", "colorblind", "color-blind", "colour-blind", "color blind")),
    ("npg", ("npg", "nature", "ggsci")),
    ("aaas", ("aaas", "science")),
    ("lancet", ("lancet",)),
    ("jama", ("jama",)),
)

_LEGEND_POS_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("right", ("图例在右", "右侧", "legend right", "right legend")),
    ("bottom", ("图例在下", "下方", "legend bottom", "bottom legend")),
    ("top", ("图例在上", "上方", "legend top", "top legend")),
    ("left", ("图例在左", "左侧", "legend left")),
)


def _infer_claim_type(line: str) -> str:
    low = line.lower()
    if any(k in low for k in ("示例", "example", "文中", "table", "figure")):
        return _CLAIM_LITERATURE
    if any(k in low for k in ("起点", "起步", "建议", "recommended", "protocol")):
        return _CLAIM_PROTOCOL
    return _CLAIM_INFERRED


def _field_hints_from_text(text: str) -> list[str]:
    low = text.lower()
    hints: list[str] = []
    for field, keys in _FIELD_HINT_PATTERNS:
        if any(k in low or k in text for k in keys):
            hints.append(field)
    return hints


def _parse_yaml_figure_blocks(body: str, plot_type: str) -> list[dict[str, Any]]:
    """解析 Skill 内可选 ```yaml figures: ... ``` 结构化出图规格。"""
    blocks: list[dict[str, Any]] = []
    for m in re.finditer(r"```ya?ml\s*\n(.*?)```", body, re.S | re.I):
        raw = m.group(1)
        if "figures:" not in raw and "plot_type:" not in raw:
            continue
        entries: list[dict[str, Any]] = []
        try:
            import yaml  # type: ignore

            parsed = yaml.safe_load(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("figures"), list):
                entries = [e for e in parsed["figures"] if isinstance(e, dict)]
        except Exception:
            current: dict[str, Any] = {}
            for ln in raw.splitlines():
                stripped = ln.strip()
                if stripped.startswith("- ") and "plot_type:" in stripped:
                    if current:
                        entries.append(current)
                    current = {}
                    stripped = stripped[2:].strip()
                if ":" not in stripped:
                    continue
                key, _, val = stripped.partition(":")
                current[key.strip()] = val.strip().strip('"').strip("'")
            if current:
                entries.append(current)
        for entry in entries:
            pt = str(entry.get("plot_type") or "").strip()
            if pt and pt != plot_type:
                continue
            blocks.append(entry)
    return blocks


def _cards_from_structured_spec(
    skill: dict[str, Any],
    plot_type: str,
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    sid = str(skill.get("skill_id") or skill.get("name") or "skill")
    doi = str(skill.get("doi") or "")
    quote_parts = [f"{k}={v}" for k, v in spec.items() if v is not None]
    quote = "; ".join(quote_parts)[:400]
    hints = _field_hints_from_text(quote)
    for key in (
        "title",
        "color_by",
        "legend_position",
        "title_align",
        "journal",
        "font_size",
        "colors",
        "cmap",
        "ellipse",
        "hide_isolates",
    ):
        if spec.get(key) is not None and spec.get(key) != "":
            mapped = {
                "title": "title",
                "color_by": "color_by",
                "legend_position": "legend.position",
                "title_align": "title_align",
                "journal": "palette",
                "font_size": "font_size.title",
            }.get(key, key)
            if mapped not in hints:
                hints.append(mapped)
    return [
        {
            "evidence_id": f"{sid}#yaml",
            "skill_id": sid,
            "doi": doi,
            "source": skill.get("source"),
            "quote": quote,
            "field_hints": hints or ["style"],
            "claim_type": _CLAIM_STRUCTURED,
            "plot_type": plot_type,
            "confidence": 0.9,
            "structured": dict(spec),
        }
    ]


def _line_matches_plot(line: str, plot_type: str, plot_terms: tuple[str, ...]) -> bool:
    low = line.lower()
    if plot_type and plot_type.replace("_", " ") in low:
        return True
    if any(t in low for t in plot_terms):
        return True
    return False


def _cards_from_skill(skill: dict[str, Any], plot_type: str) -> list[dict[str, Any]]:
    body = str(skill.get("body") or "")
    visual = (skill.get("visual_block") or "").strip()
    if not visual and not body:
        return []
    sid = str(skill.get("skill_id") or skill.get("name") or "skill")
    doi = str(skill.get("doi") or "")
    plot_terms = _plot_terms_for_type(plot_type)
    cards: list[dict[str, Any]] = []

    for spec in _parse_yaml_figure_blocks(body, plot_type):
        cards.extend(_cards_from_structured_spec(skill, plot_type, spec))
    if skill.get("skill_pool") == _SKILL_POOL_PLOT:
        # 改图规范 Skill 只给结构化规格；逐行卡会挤掉论文 Skill 与语料图注。
        return cards

    for i, line in enumerate(visual.splitlines()):
        line = line.strip()
        if not line or line.startswith("|---") or (line.count("|") >= 3 and "---" in line):
            continue
        if not _line_matches_plot(line, plot_type, plot_terms):
            continue
        hints = _field_hints_from_text(line)
        if not hints:
            hints = ["style"]
        cards.append(
            {
                "evidence_id": f"{sid}#L{i}",
                "skill_id": sid,
                "doi": doi,
                "source": skill.get("source"),
                "quote": line[:400],
                "field_hints": hints,
                "claim_type": _infer_claim_type(line),
                "plot_type": plot_type,
                "confidence": 0.55 if _infer_claim_type(line) == _CLAIM_INFERRED else 0.75,
            }
        )

    if not cards and visual and _line_matches_plot(visual, plot_type, plot_terms):
        cards.append(
            {
                "evidence_id": f"{sid}#block",
                "skill_id": sid,
                "doi": doi,
                "source": skill.get("source"),
                "quote": visual.splitlines()[0][:400],
                "field_hints": _field_hints_from_text(visual) or ["style"],
                "claim_type": _CLAIM_INFERRED,
                "plot_type": plot_type,
                "confidence": 0.45,
            }
        )
    return cards


def collect_evidence_cards(
    *,
    plot_type: str,
    goal_text: str = "",
    instruction: str = "",
    project_root=None,
    sticky_skill_ids: list[str] | None = None,
    max_cards: int = 6,
) -> list[dict[str, Any]]:
    if not plot_type:
        return []
    ranked = rank_skills_for_plot(
        plot_type=plot_type,
        goal_text=goal_text,
        instruction=instruction,
        project_root=project_root,
        sticky_skill_ids=sticky_skill_ids,
        max_skills=4,
    )
    cards: list[dict[str, Any]] = []
    for sk in ranked:
        cards.extend(_cards_from_skill(sk, plot_type))
    try:
        from web_frontend.backend.literature_corpus import (
            evidence_cards_from_hits,
            search_figure_hits,
        )
        from web_frontend.backend.literature_paths import resolve_literature_dirs

        _persist, source_dir = resolve_literature_dirs(
            project_root,
            allow_install_fallback=project_root is None,
        )
        if source_dir and Path(source_dir).is_dir():
            q = " ".join(x for x in (goal_text, instruction, plot_type) if x).strip()
            hits = search_figure_hits(
                source_dir=source_dir,
                plot_type=plot_type,
                query=q,
                max_hits=4,
            )
            cards.extend(evidence_cards_from_hits(hits, plot_type=plot_type, max_cards=4))
    except Exception:
        pass
    cards.sort(key=lambda c: float(c.get("confidence") or 0), reverse=True)
    return cards[:max_cards]


def evidence_cards_to_markdown(cards: list[dict[str, Any]], max_chars: int = 3500) -> str:
    if not cards:
        return ""
    parts = [
        "## Literature evidence cards",
        "Use only for style/layout hints supported by quote; never invent thresholds or columns.",
        "",
    ]
    budget = max_chars
    for c in cards:
        header = f"### {c.get('evidence_id')} ({c.get('claim_type')})"
        if c.get("doi"):
            header += f" DOI:{c['doi']}"
        body = f"{header}\nFields: {', '.join(c.get('field_hints') or [])}\n> {c.get('quote', '')}\n\n"
        if len(body) > budget and parts:
            break
        parts.append(body)
        budget -= len(body)
    return "\n".join(parts).strip()


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


def _resolve_color_by_column(blob: str, metadata_columns: list[str] | None) -> str | None:
    if not metadata_columns:
        return None
    cols = {str(c).strip(): str(c).strip() for c in metadata_columns if str(c).strip()}
    lower_map = {k.lower(): v for k, v in cols.items()}
    for alias, canonical in _COLOR_BY_ALIASES:
        if alias in blob.lower() and canonical.lower() in lower_map:
            return lower_map[canonical.lower()]
    for col in cols.values():
        if col.lower() in blob.lower():
            return col
    return None


def apply_data_contract_to_patch(
    plot_type: str,
    patch: dict[str, Any],
    *,
    metadata_columns: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """应用前校验：metadata 列、图型是否支持 color_by 等。"""
    out = dict(patch)
    warnings: list[str] = []
    color_by = str(out.get("color_by") or "").strip()
    if color_by and metadata_columns is not None:
        allowed = {str(c).strip() for c in metadata_columns}
        if color_by not in allowed:
            out.pop("color_by", None)
            warnings.append(
                f"文献建议按 `{color_by}` 着色，但 metadata 无此列（可用: {', '.join(sorted(allowed)[:6])}）"
            )
    if plot_type == "volcano" and out.get("color_by"):
        out.pop("color_by", None)
        warnings.append("火山图不使用 metadata 着色，已忽略文献 color_by 建议")
    return out, warnings


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")
_FONT_KEYS = ("title", "axis", "legend", "label")


def _spec_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    return None


def _apply_structured_spec(
    patch: dict[str, Any],
    spec: dict[str, Any],
    plot_type: str,
    applied: list[str],
    seen: set[str],
) -> None:
    """Skill 的 yaml 出图规格只放行样式字段，阈值类键在这里不读。"""
    title = str(spec.get("title") or "").strip()
    if title and "title" not in seen:
        patch["title"] = title
        seen.add("title")
        applied.append("title=structured")
    align = str(spec.get("title_align") or "").strip()
    if align in {"left", "center", "right"}:
        patch["title_align"] = align
        applied.append(f"title_align={align}")
    pos = str(spec.get("legend_position") or "").strip()
    if pos in {"left", "right", "top", "bottom"}:
        patch.setdefault("legend", {})["position"] = pos
        applied.append(f"legend.position={pos}")
    font = spec.get("font_size")
    if isinstance(font, dict):
        sizes = {
            key: int(font[key])
            for key in _FONT_KEYS
            if isinstance(font.get(key), (int, float)) and font[key] > 0
        }
        if sizes:
            patch.setdefault("font_size", {}).update(sizes)
            applied.append("font_size")
    colors = spec.get("colors")
    if isinstance(colors, dict):
        valid = {
            str(key): val.strip()
            for key, val in colors.items()
            if isinstance(val, str) and _HEX_COLOR_RE.fullmatch(val.strip())
        }
        if valid:
            patch.setdefault("colors", {}).update(valid)
            applied.append("colors=" + ",".join(sorted(valid)))
    cmap = str(spec.get("cmap") or "").strip()
    if cmap:
        patch["cmap"] = cmap
        applied.append(f"cmap={cmap}")
    ellipse = _spec_bool(spec.get("ellipse"))
    if ellipse is not None and plot_type in {"pca", "plsda"}:
        patch["ellipse"] = ellipse
        patch.setdefault("marks", {})["ellipse"] = ellipse
        applied.append(f"ellipse={str(ellipse).lower()}")
    isolates = _spec_bool(spec.get("hide_isolates"))
    if isolates is not None and plot_type == "network_topology":
        patch["hide_isolates"] = isolates
        applied.append(f"hide_isolates={str(isolates).lower()}")
    color_by = str(spec.get("color_by") or "").strip()
    if color_by and plot_type in {"pca", "plsda"}:
        patch["color_by"] = color_by
        applied.append(f"color_by={color_by}")
    journal = str(spec.get("journal") or "").strip()
    if journal:
        patch["_journal"] = journal
        applied.append(f"palette={journal}")


def build_style_patch_from_evidence(
    plot_type: str,
    cards: list[dict[str, Any]],
    *,
    metadata_columns: list[str] | None = None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    """从证据卡生成样式 patch。返回 (patch, applied_fields, warnings)。"""
    patch: dict[str, Any] = {}
    applied: list[str] = []
    warnings: list[str] = []
    if not cards:
        return patch, applied, warnings

    # 关键词启发式只读自由文本卡；结构化规格的 "k=v" 文本里有 sample、threshold_color 等词，
    # 拿去匹配会误判 color_by=Sample 或误报"文献提及统计阈值"。
    free_cards = [c for c in cards if not isinstance(c.get("structured"), dict)]
    specs = [c["structured"] for c in cards if isinstance(c.get("structured"), dict)]
    blob = "\n".join(str(c.get("quote") or "") for c in free_cards)
    hints = {h for c in free_cards for h in (c.get("field_hints") or [])}

    for card in cards:
        hint = card.get("journal_hint")
        if hint and "_journal" not in patch:
            patch["_journal"] = str(hint)
            applied.append(f"palette={hint}")

    journal = _detect_journal(blob)
    if journal and "_journal" not in patch:
        patch["_journal"] = journal
        applied.append(f"palette={journal}")

    legend_pos = _detect_legend_position(blob)
    if legend_pos:
        patch.setdefault("legend", {})["position"] = legend_pos
        applied.append(f"legend.position={legend_pos}")

    if plot_type == "volcano" and ("colors.significant" in hints or "上调" in blob):
        patch.setdefault("colors", {})
        patch["colors"].update(
            {
                "upregulated": "#E64B35",
                "downregulated": "#4DBBD5",
                "nonsignificant": "#B0B0B0",
            }
        )
        applied.append("colors=volcano_npg")

    if plot_type in {"pca", "plsda"}:
        if "title" in hints and not patch.get("title"):
            patch["title"] = "Score Plot"
            applied.append("title=Score Plot")
        color_col = _resolve_color_by_column(blob, metadata_columns)
        if color_col and "color_by" not in patch:
            patch["color_by"] = color_col
            applied.append(f"color_by={color_col}")
        if re.search(r"标签|label", blob, re.I) and "show_sample_labels" in hints:
            patch["show_sample_labels"] = False

    if plot_type == "network_topology" and ("colors.edge_color" in hints or "边" in blob):
        patch.setdefault("colors", {})["edge_color"] = "#c8c8c8"
        applied.append("colors.edge_color")

    if plot_type in {"cosine_hist", "degree_hist", "family_size"}:
        patch.setdefault("colors", {})["histogram_color"] = "#4DBBD5"
        applied.append("colors.histogram_color")

    if plot_type == "vip_bar":
        patch.setdefault("colors", {})["bar_color"] = "#3C5488"
        patch.setdefault("colors", {})["upregulated"] = "#E64B35"
        patch.setdefault("colors", {})["downregulated"] = "#4DBBD5"
        applied.append("colors.bar_color")

    if plot_type == "heatmap_vip":
        patch["cmap"] = "RdBu_r"
        applied.append("cmap=RdBu_r")

    if plot_type == "volcano":
        patch.setdefault("colors", {})
        patch["colors"].setdefault("upregulated", "#E64B35")
        patch["colors"].setdefault("downregulated", "#4DBBD5")
        patch["colors"].setdefault("nonsignificant", "#B0B0B0")
        applied.append("volcano colors")

    if plot_type in {"pca", "plsda"} and re.search(r"椭圆|ellipse|置信", blob, re.IGNORECASE):
        patch["ellipse"] = True
        patch.setdefault("marks", {})["ellipse"] = True
        applied.append("ellipse")

    seen: set[str] = set()
    for spec in specs:
        _apply_structured_spec(patch, spec, plot_type, applied, seen)

    for banned in ("thresholds", "vip_threshold", "fdr_cut", "components", "p_stat"):
        patch.pop(banned, None)
    if _THRESHOLD_MENTION_RE.search(blob):
        warnings.append("文献提及统计阈值；未写入绘图配置。要改阈值请在指令里写明数字。")

    if "cluster" in hints and plot_type in {"pca", "plsda"}:
        warnings.append("文献提及聚类着色；未自动改变着色维度（需用户确认）")

    patch, contract_warn = apply_data_contract_to_patch(
        plot_type, patch, metadata_columns=metadata_columns
    )
    warnings.extend(contract_warn)
    return patch, applied, warnings


def suggest_soft_style_patch(
    plot_type: str,
    cards: list[dict[str, Any]],
    *,
    metadata_columns: list[str] | None = None,
    current_config: dict[str, Any] | None = None,
    user_instruction: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """从证据卡生成可选软样式 patch（不碰 thresholds 数值）。"""
    patch, _applied, warnings = build_style_patch_from_evidence(
        plot_type, cards, metadata_columns=metadata_columns
    )
    journal = patch.pop("_journal", None)
    invite = False
    inst = (user_instruction or "").strip()
    if inst:
        try:
            from web_frontend.backend.plot_edit_registry import looks_like_literature_plot_restyle

            invite = looks_like_literature_plot_restyle(inst)
        except Exception:
            invite = False
        if not journal:
            journal = _detect_journal(inst)
    if invite and not journal:
        journal = "npg"
    if journal and current_config:
        try:
            from web_frontend.backend.literature_figure_style import apply_journal_palette
            from web_frontend.backend.plot_theme import merge_plot_config

            merged = merge_plot_config(current_config, patch)
            styled = apply_journal_palette(merged, journal, plot_type=plot_type)
            pal = styled.get("palette")
            if isinstance(pal, dict) and pal != (merged.get("palette") or {}):
                patch["palette"] = pal
        except Exception:
            pass
    if not invite:
        # 普通改标题/字号时不要顺手改椭圆
        if "椭圆" not in inst.lower() and "ellipse" not in inst.lower():
            patch.pop("ellipse", None)
            marks = patch.get("marks")
            if isinstance(marks, dict):
                marks.pop("ellipse", None)
                if not marks:
                    patch.pop("marks", None)
    return patch, warnings


__all__ = [
    "apply_data_contract_to_patch",
    "build_style_patch_from_evidence",
    "collect_evidence_cards",
    "evidence_cards_to_markdown",
    "suggest_soft_style_patch",
]
