"""Agent C 报告在线查看：Markdown → HTML，图片路径转 workspace URL。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_SKIP_DIRS = {
    "agent_c_output",
    "edited_plots",
    "merged_figures",
    "_abc_handoff",
    "_handoff_input",
    "__pycache__",
    ".git",
}

_PLOT_STEM_ALIASES = {
    "pca_plot": "pca",
    "plsda_plot": "plsda",
    "volcano_plot": "volcano",
    "vip_scores": "vip",
    "heatmap_top_vip": "heatmap_vip",
}


def _plot_semantic_key(stem: str) -> str:
    s = stem.lower()
    for prefix, key in _PLOT_STEM_ALIASES.items():
        if s == prefix or s.endswith(f"__{prefix}") or prefix in s:
            return key
    return s


def _png_path_priority(rel: str) -> int:
    score = 0
    if rel.startswith("edited_plots/") or "_intent" in rel:
        score += 100
    if "statistical_results/" in rel:
        score += 50
    if rel.startswith("agent_c_output/"):
        score += 5
    if "/" not in rel:
        score += 8
    return score


def _rel_to_session(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return path.name


def find_agent_c_output_dir(results_dir: Path) -> Path | None:
    direct = results_dir / "agent_c_output"
    if direct.is_dir() and (direct / "final_report.md").is_file():
        return direct
    for hit in results_dir.rglob("final_report.md"):
        if "agent_c_output" in hit.parts:
            return hit.parent
    return None


def list_existing_result_pngs(
    results_dir: Path,
    *,
    exclude_under: Path | None = None,
) -> list[dict[str, Any]]:
    """B 侧已产出的 PNG（供报告引用，不含 C 本轮 agent_c_output/figures）。"""
    root = Path(results_dir)
    if not root.is_dir():
        return []
    exclude = Path(exclude_under) if exclude_under else None
    seen: set[str] = set()
    by_semantic: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*.png")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if exclude:
            try:
                path.relative_to(exclude)
                continue
            except ValueError:
                pass
        rel = _rel_to_session(root, path)
        if rel in seen:
            continue
        seen.add(rel)
        item = {
            "rel": rel,
            "name": path.name,
            "title": path.stem.replace("_", " "),
            "source": "analysis_result",
        }
        sem = _plot_semantic_key(path.stem)
        prev = by_semantic.get(sem)
        if not prev or _png_path_priority(rel) > _png_path_priority(str(prev.get("rel") or "")):
            by_semantic[sem] = item
    out = list(by_semantic.values())
    out.sort(key=lambda x: str(x.get("rel") or ""))
    return out


def preferred_png_for_plot_type(
    results_root: Path,
    plot_type: str,
    *,
    fallback: str | Path | None = None,
) -> Path | None:
    """优先 ``edited_plots/*_intent.png``，再回退 B 侧统计图或其它 PNG。"""
    from web_frontend.backend.plot_edit_registry import get_plot_spec

    spec = get_plot_spec(plot_type)
    if not spec:
        if fallback and Path(fallback).is_file():
            return Path(fallback).resolve()
        return None

    root = Path(results_root).resolve()
    stem = spec.stem_prefix
    candidates: list[Path] = [
        root / "edited_plots" / f"{stem}_intent.png",
        root / "edited_plots" / f"{stem}.png",
    ]
    for edited_dir in sorted(root.rglob("edited_plots")):
        if not edited_dir.is_dir():
            continue
        candidates.extend(
            [
                edited_dir / f"{stem}_intent.png",
                edited_dir / f"{stem}.png",
            ]
        )
    if fallback:
        candidates.append(Path(fallback))

    sem = _plot_semantic_key(stem)
    best_other: Path | None = None
    best_score = -1
    for item in list_existing_result_pngs(root, exclude_under=root / "agent_c_output"):
        rel = str(item.get("rel") or "")
        if _plot_semantic_key(Path(rel).stem) != sem:
            continue
        score = _png_path_priority(rel)
        if score > best_score:
            best_score = score
            best_other = root / rel
    if best_other:
        candidates.append(best_other)

    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def apply_preferred_png_to_figures(
    figures: list[dict[str, Any]],
    results_dir: str | Path,
) -> None:
    """就地更新每张方案图的 ``png``；``missing_data`` 仅在 CSV 齐备时才用 B 侧 PNG 挽救。"""
    from web_frontend.backend.agent_c.figure_data_narrative import plot_data_files_available

    root = Path(results_dir)
    for fig in figures:
        plot_type = str(fig.get("plot_type") or "").strip()
        if not plot_type:
            continue
        if fig.get("status") == "missing_data" and not plot_data_files_available(root, plot_type):
            continue
        preferred = preferred_png_for_plot_type(
            root,
            plot_type,
            fallback=fig.get("png") or fig.get("existing_png"),
        )
        if not preferred:
            continue
        fig["png"] = str(preferred)
        if fig.get("status") == "missing_data":
            fig["status"] = "copied_existing"
            fig["missing_reason"] = None


def filter_existing_figures_for_report(
    existing: list[dict[str, Any]],
    *,
    figures: list[dict[str, Any]],
    results_dir: str | Path,
) -> list[dict[str, Any]]:
    """去掉已在 figures 中引用或与方案图语义重复的 B 侧 PNG。"""
    from web_frontend.backend.plot_edit_registry import stem_prefix_for_plot_type

    root = Path(results_dir).resolve()
    used_paths: set[Path] = set()
    used_keys: set[str] = set()
    for fig in figures:
        plot_type = str(fig.get("plot_type") or "").strip()
        if plot_type:
            stem = stem_prefix_for_plot_type(plot_type)
            if stem:
                used_keys.add(_plot_semantic_key(stem))
        for key in ("png", "existing_png"):
            val = fig.get(key)
            if not val:
                continue
            p = Path(val).resolve()
            used_paths.add(p)
            used_keys.add(_plot_semantic_key(p.stem))
    out: list[dict[str, Any]] = []
    for item in existing:
        rel = str(item.get("rel") or "")
        if not rel:
            continue
        p = (root / rel).resolve()
        if p in used_paths:
            continue
        if _plot_semantic_key(p.stem) in used_keys:
            continue
        out.append(item)
    return out


def _rewrite_markdown_images(md: str, *, session_id: str) -> str:
    """把报告内图片路径改成 workspace-file API URL。"""

    def _repl(match: re.Match) -> str:
        alt = match.group(1)
        src = match.group(2).strip()
        if src.startswith(("http://", "https://", "/api/")):
            return match.group(0)
        if src.startswith("figures/"):
            rel = f"agent_c_output/{src}"
        else:
            rel = src.lstrip("/")
        url = f"/api/sessions/{session_id}/workspace-file?rel={rel}"
        return f"![{alt}]({url})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _repl, md)


def markdown_to_html(md: str) -> str:
    try:
        from markdown_it import MarkdownIt

        md_parser = MarkdownIt("commonmark", {"html": False, "breaks": True}).enable(
            "table",
            "strikethrough",
        )
        return md_parser.render(md)
    except Exception:
        escaped = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre>{escaped}</pre>"


def split_markdown_figure_section(md: str) -> tuple[str, str]:
    """拆分 Markdown：返回 (不含图表章节的正文, 图表章节)。"""
    pattern = re.compile(r"^## (图表|Figures)\s*$", re.MULTILINE)
    match = pattern.search(md)
    if not match:
        return md, ""
    start = match.start()
    tail = md[match.end() :]
    next_heading = re.search(r"^## [^\n]+", tail, re.MULTILINE)
    if next_heading:
        end = match.end() + next_heading.start()
        prose = (md[:start].rstrip() + "\n\n" + md[end:].lstrip()).strip() + "\n"
        figures_section = md[start:end].strip() + "\n"
        return prose, figures_section
    prose = md[:start].rstrip() + "\n"
    figures_section = md[start:].strip() + "\n"
    return prose, figures_section


def _attach_figure_card_urls(cards: list[dict[str, Any]], *, session_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for card in cards:
        item = dict(card)
        rel = str(item.get("rel") or "").strip()
        if rel:
            item["image_url"] = f"/api/sessions/{session_id}/workspace-file?rel={rel}"
        out.append(item)
    return out


def _load_figure_cards_bundle(
    *,
    out_dir: Path,
    results_root: Path,
    manifest: dict[str, Any],
    insights: dict[str, Any],
    zh: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    from web_frontend.backend.agent_c.figure_cards import build_figure_cards
    from web_frontend.backend.agent_c.figure_ecb import ECB_LAYOUT_VERSION
    from web_frontend.backend.agent_c.report_insights import figure_interpretations_index

    cards_path = out_dir / "figure_cards.json"
    if cards_path.is_file():
        try:
            raw = json.loads(cards_path.read_text(encoding="utf-8"))
            layout = str(raw.get("layout") or "figure_first")
            version = int(raw.get("ecb_layout_version") or 0)
            cached = list(raw.get("figure_cards") or [])
            if version >= ECB_LAYOUT_VERSION and cached:
                return layout, cached
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    report_figures = manifest.get("report_figures") or []
    if not report_figures:
        return "classic", []

    insights_enabled = bool((manifest.get("report") or {}).get("insights_enabled"))
    figure_interp = figure_interpretations_index(insights)

    rebuilt: list[dict[str, Any]] = []
    for item in report_figures:
        png = item.get("png")
        fig = dict(item)
        if png and not fig.get("rel"):
            fig["png"] = png
        rebuilt.append(fig)

    cards = build_figure_cards(
        rebuilt,
        figure_interp,
        results_root=results_root,
        zh=zh,
        insights_enabled=insights_enabled,
    )
    return "figure_first", cards


def load_report_bundle(*, session_id: str, results_dir: Path) -> dict[str, Any]:
    root = Path(results_dir)
    out_dir = find_agent_c_output_dir(root)
    if not out_dir:
        raise FileNotFoundError("未找到 agent_c_output/final_report.md")

    md_path = out_dir / "final_report.md"
    md_raw = md_path.read_text(encoding="utf-8")
    md_for_api = _rewrite_markdown_images(md_raw, session_id=session_id)

    pdf_path = out_dir / "final_report.pdf"
    insights_path = out_dir / "report_insights.json"
    manifest_path = out_dir / "agent_c_manifest.json"
    insights: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    if insights_path.is_file():
        try:
            insights = json.loads(insights_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            insights = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}

    c_figures: list[dict[str, Any]] = []
    figures_dir = out_dir / "figures"
    if figures_dir.is_dir():
        for png in sorted(figures_dir.glob("*.png")):
            c_figures.append(
                {
                    "rel": _rel_to_session(root, png),
                    "name": png.name,
                    "source": "agent_c",
                }
            )

    existing = list_existing_result_pngs(root, exclude_under=out_dir)

    layout, figure_cards = _load_figure_cards_bundle(
        out_dir=out_dir,
        results_root=root,
        manifest=manifest,
        insights=insights,
        zh=True,
    )
    figure_cards = _attach_figure_card_urls(figure_cards, session_id=session_id)

    prose_md = md_for_api
    prose_html: str | None = None
    if layout == "figure_first" and figure_cards:
        prose_md, _ = split_markdown_figure_section(md_for_api)
        prose_html = markdown_to_html(prose_md)

    return {
        "session_id": session_id,
        "markdown": md_for_api,
        "html": markdown_to_html(md_for_api),
        "prose_html": prose_html,
        "layout": layout,
        "figure_cards": figure_cards,
        "pdf_rel": _rel_to_session(root, pdf_path) if pdf_path.is_file() else None,
        "insights_rel": _rel_to_session(root, insights_path) if insights_path.is_file() else None,
        "insights_summary": str(insights.get("summary") or "").strip(),
        "insights": {
            k: insights.get(k)
            for k in (
                "summary",
                "key_findings",
                "analysis_role",
                "scientific_value",
                "application_value",
                "limitations",
                "next_steps",
            )
            if insights.get(k)
        },
        "manifest_status": manifest.get("status"),
        "n_rendered": manifest.get("n_rendered"),
        "figures": c_figures,
        "existing_figures": existing,
        "report_rel": _rel_to_session(root, md_path),
        "output_dir_rel": _rel_to_session(root, out_dir),
    }


__all__ = [
    "apply_preferred_png_to_figures",
    "filter_existing_figures_for_report",
    "find_agent_c_output_dir",
    "list_existing_result_pngs",
    "load_report_bundle",
    "markdown_to_html",
    "preferred_png_for_plot_type",
    "split_markdown_figure_section",
]
