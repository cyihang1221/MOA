"""解析 softwares_database 中的 figure_catalog / figure_index / repro_recipes。

网页默认读项目根这两份目录。Agent B 的同名目录应同步覆盖到此处，而不是改路径去指 B。
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

_DOI_RE = re.compile(r"DOI:\s*([0-9]{2}\.\d{4,9}/[^\s,;]+)", re.I)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_FIG_HEAD_RE = re.compile(
    r"^\s*(Figure|Fig\.?|Table)\s+([0-9A-Za-z]+):\s*\[([^\]]+)\]\s*$",
    re.I,
)
_SCORE_RE = re.compile(r"overall_reproducibility_score:\s*(\d+)\s*/\s*100", re.I)

# 文献 recipe 图标签 → 前端 plot_type
FIGURE_TAG_TO_PLOTS: dict[str, tuple[str, ...]] = {
    "pca_scores": ("pca",),
    "pls_da_scores": ("plsda",),
    "t_sne_scores": ("pca",),
    "volcano_plot": ("volcano",),
    "heatmap": ("heatmap_vip", "hca_heatmap", "relative_abundance_heatmap", "correlation_heatmap"),
    "clustergram": ("heatmap_vip", "hca_heatmap"),
    "network": ("network_topology", "mass2motif_network"),
    "network_visualization": ("network_topology",),
    "bar_chart": ("vip_bar", "kegg_barplot", "constituent_bar", "bioactivity_bar"),
    "pathway_map": ("kegg_bubble", "kegg_dotplot", "kegg_barplot"),
    "boxplot": ("sensory_scores",),
    "scatter_plot": ("pca", "plsda"),
    "roc_curve": ("roc_auc_hist", "plsda_permutation"),
    "cross_validation_plot": ("plsda_permutation",),
    "distribution_plot": ("cosine_hist", "degree_hist", "pearson_hist", "log2fc_hist", "roc_auc_hist"),
    "venn_diagram": ("significance_venn",),
    "s_plot": ("splot",),
}

# 非分析图：作图检索默认跳过（caption 命中图型词时仍保留）
_NON_ANALYTICAL_TAGS = frozenset(
    {
        "workflow_diagram",
        "microscopy_image",
        "western_blots",
        "photograph_diagram",
        "equipment_diagram",
        "screenshot",
        "schematic",
        "conceptual_diagram",
        "troubleshooting_table",
        "table",
        "other",
        "structural_analysis",
        "protein_structure",
        "protein_complex_structure",
        "subcellular_distribution_map",
    }
)

_PLOT_CAPTION_TERMS: dict[str, tuple[str, ...]] = {
    "pca": ("pca", "score plot", "principal component", "得分图"),
    "plsda": ("pls-da", "plsda", "opls", "s-plot", "偏最小二乘"),
    "volcano": ("volcano", "火山", "differentially abundant", "log2fc"),
    "vip_bar": ("vip", "variable importance"),
    "heatmap_vip": ("heatmap", "heat map", "热图", "clustergram"),
    "hca_heatmap": ("hca", "hierarchical cluster", "层次聚类"),
    "cosine_hist": ("cosine", "spectral similarity"),
    "degree_hist": ("degree distribution", "node degree"),
    "network_topology": ("molecular network", "molecular networking", "cytoscape", "分子网络"),
    "kegg_bubble": ("enrichment", "kegg", "pathway", "气泡"),
    "kegg_dotplot": ("enrichment", "kegg", "dotplot"),
    "kegg_barplot": ("enrichment", "kegg", "bar"),
    "family_size": ("molecular family", "family size"),
    "splot": ("s-plot", "s plot", "opls", "loading", "p(corr)"),
    "opls_outlier": ("outlier", "score distance", "orthogonal distance", "离群"),
    "roc_auc_hist": ("roc", "auc", "auroc", "receiver operating"),
    "significance_venn": ("venn", "韦恩", "维恩", "intersection"),
    "log2fc_hist": ("fold change", "log2fc", "倍数变化"),
    "plsda_permutation": ("permutation", "置换", "r2y", "q2"),
}

# MassOmics-Agent-B figure_catalog 的 figure_type → 前端 plot_type
_CATALOG_TYPE_HINTS: dict[str, tuple[str, ...]] = {
    "pca": ("pca", "pls-da", "plsda", "散点"),
    "plsda": ("pls-da", "plsda", "opls", "散点"),
    "volcano": ("volcano", "火山"),
    "heatmap_vip": ("热图", "heatmap"),
    "hca_heatmap": ("热图", "heatmap"),
    "network_topology": ("分子网络", "network"),
    "kegg_bubble": ("富集", "气泡", "dotplot"),
    "kegg_dotplot": ("富集", "气泡", "dotplot"),
    "kegg_barplot": ("柱状", "条形", "富集"),
    "vip_bar": ("柱状", "条形", "vip"),
    "cosine_hist": ("分子网络",),
    "splot": ("s-plot", "散点", "opls"),
    "opls_outlier": ("散点", "离群"),
    "roc_auc_hist": ("roc", "直方", "分布"),
    "significance_venn": ("venn", "韦恩", "维恩", "柱状"),
    "log2fc_hist": ("直方", "分布"),
    "plsda_permutation": ("置换", "散点"),
}

_SKIP_CATALOG_TYPES = ("工作流", "软件界面", "截图", "分子结构")

_JOURNAL_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("npg", ("nature", "npg", "scientific reports")),
    ("aaas", ("science", "aaas")),
    ("lancet", ("lancet",)),
    ("jama", ("jama",)),
)

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"key": None, "recipes": [], "figures": []}


def clear_corpus_cache() -> None:
    with _cache_lock:
        _cache["key"] = None
        _cache["recipes"] = []
        _cache["figures"] = []


def extract_doi(text: str) -> str:
    m = _DOI_RE.search(text or "")
    if not m:
        return ""
    return m.group(1).rstrip(").]")


def _plain(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "").strip()


def detect_journal_from_source(text: str) -> str | None:
    low = (text or "").lower()
    for name, hints in _JOURNAL_HINTS:
        if any(h in low for h in hints):
            return name
    return None


def short_title_from_caption(plot_type: str, caption: str) -> str:
    """图注过长时不用作标题；短且像图名的才采用。"""
    raw = (caption or "").strip()
    raw = re.sub(r"^(fig(?:ure)?\.?\s*\d+[A-Za-z]?\s*[:：]\s*)", "", raw, flags=re.I)
    if not raw or len(raw) > 72:
        return ""
    if raw.endswith(".") and len(raw) > 40:
        return ""
    low = raw.lower()
    terms = _PLOT_CAPTION_TERMS.get(plot_type) or (plot_type.replace("_", " "),)
    if any(t in low for t in terms):
        return raw.rstrip(".")
    return ""


def _split_entries(text: str, marker: str) -> list[str]:
    parts = text.split(marker)
    return [p.strip() for p in parts if p.strip()]


def _parse_figure_index_text(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in _split_entries(text, "========== figure_index entry =========="):
        rec: dict[str, str] = {}
        for ln in block.splitlines():
            if ":" not in ln:
                continue
            key, val = ln.split(":", 1)
            rec[key.strip()] = val.strip()
        caption = rec.get("figure_caption") or ""
        if not caption:
            continue
        source_paper = rec.get("source_paper") or ""
        out.append(
            {
                "kind": "figure_index",
                "figure_id": rec.get("figure_id") or "",
                "paper_title": _plain(rec.get("paper_title") or ""),
                "source_paper": _plain(source_paper),
                "doi": extract_doi(source_paper),
                "caption": _plain(caption),
                "rel": "figure_index.txt",
            }
        )
    return out


def _parse_figure_catalog_text(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in _split_entries(text, "========== figure_catalog entry =========="):
        rec: dict[str, str] = {}
        for ln in block.splitlines():
            if ":" not in ln:
                continue
            key, val = ln.split(":", 1)
            rec[key.strip()] = val.strip()
        caption = rec.get("figure_caption") or ""
        if not caption:
            continue
        source_paper = rec.get("source_paper") or ""
        research = (rec.get("is_research_plot") or "").strip().lower() in {"true", "1", "yes"}
        out.append(
            {
                "kind": "figure_catalog",
                "figure_id": rec.get("figure_id") or "",
                "paper_title": _plain(rec.get("paper_title") or ""),
                "source_paper": _plain(source_paper),
                "doi": extract_doi(source_paper),
                "caption": _plain(caption),
                "figure_type": rec.get("figure_type") or "",
                "viz_tool": rec.get("plot_tool_hint") or "",
                "visual_description": _plain(rec.get("visual_description") or ""),
                "stat_test": rec.get("statistical_test") or rec.get("statistical_markers") or "",
                "is_research_plot": research,
                "rel": "figure_catalog.txt",
            }
        )
    return out


def _parse_recipe_figures(lines: list[str], start: int) -> tuple[list[dict[str, Any]], int]:
    figures: list[dict[str, Any]] = []
    i = start
    current: dict[str, Any] | None = None
    while i < len(lines):
        ln = lines[i]
        if ln and not ln.startswith(" ") and not ln.startswith("\t"):
            break
        head = _FIG_HEAD_RE.match(ln)
        if head:
            if current:
                figures.append(current)
            current = {
                "id": f"{head.group(1)} {head.group(2)}",
                "tag": head.group(3).strip().lower(),
                "caption": "",
                "viz_tool": "",
                "stat_test": "",
            }
            i += 1
            continue
        if current is not None:
            stripped = ln.strip()
            if stripped.lower().startswith("caption:"):
                current["caption"] = _plain(stripped.split(":", 1)[1].strip())
            elif stripped.lower().startswith("visualization_tool:"):
                current["viz_tool"] = stripped.split(":", 1)[1].strip()
            elif stripped.lower().startswith("statistical_test:"):
                current["stat_test"] = stripped.split(":", 1)[1].strip()
        i += 1
    if current:
        figures.append(current)
    return figures, i


def parse_recipe_text(text: str, *, rel: str = "") -> dict[str, Any] | None:
    if "reproducibility_recipe" not in text[:400] and "paper_title:" not in text[:400]:
        # 允许测试夹具不写 banner
        if "paper_title:" not in text:
            return None
    lines = text.splitlines()
    paper_title = ""
    source_paper = ""
    workflow_steps = 0
    repro_score = 0
    figures: list[dict[str, Any]] = []
    workflow_blob_parts: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("paper_title:"):
            paper_title = ln.split(":", 1)[1].strip()
        elif ln.startswith("source_paper:"):
            source_paper = ln.split(":", 1)[1].strip()
        elif ln.startswith("overall_reproducibility_score:"):
            m = _SCORE_RE.search(ln)
            if m:
                repro_score = int(m.group(1))
        elif ln.startswith("workflow_steps:"):
            try:
                workflow_steps = int(ln.split(":", 1)[1].strip().split()[0])
            except (ValueError, IndexError):
                workflow_steps = 0
        elif ln.startswith("figure_recipes:"):
            figures, i = _parse_recipe_figures(lines, i + 1)
            continue
        elif ln.startswith("  Step ") or ln.strip().startswith("tool:"):
            workflow_blob_parts.append(ln.strip())
        i += 1
    return {
        "kind": "recipe",
        "rel": rel,
        "paper_title": _plain(paper_title),
        "source_paper": _plain(source_paper),
        "doi": extract_doi(source_paper),
        "workflow_steps": workflow_steps,
        "repro_score": repro_score,
        "figures": figures,
        "tools_blob": " ".join(workflow_blob_parts).lower(),
    }


def _corpus_key(source_dir: Path) -> tuple:
    recipes = source_dir / "repro_recipes"
    fig_idx = source_dir / "figure_index.txt"
    n_recipes = 0
    recipes_mtime = 0.0
    if recipes.is_dir():
        try:
            n_recipes = sum(1 for _ in recipes.glob("recipe_*.txt"))
            recipes_mtime = recipes.stat().st_mtime
        except OSError:
            n_recipes = 0
    fig_mtime = fig_idx.stat().st_mtime if fig_idx.is_file() else 0.0
    catalog = source_dir / "figure_catalog.txt"
    cat_mtime = catalog.stat().st_mtime if catalog.is_file() else 0.0
    return (str(source_dir.resolve()), n_recipes, recipes_mtime, fig_mtime, cat_mtime)


def load_corpus(source_dir: str | Path) -> dict[str, Any]:
    root = Path(source_dir)
    key = _corpus_key(root)
    with _cache_lock:
        if _cache["key"] == key:
            return {"recipes": _cache["recipes"], "figures": _cache["figures"]}

    figures: list[dict[str, Any]] = []
    fig_idx = root / "figure_index.txt"
    if fig_idx.is_file():
        try:
            figures.extend(_parse_figure_index_text(fig_idx.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass
    catalog = root / "figure_catalog.txt"
    if catalog.is_file():
        try:
            figures.extend(_parse_figure_catalog_text(catalog.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            pass

    recipes: list[dict[str, Any]] = []
    recipes_dir = root / "repro_recipes"
    if recipes_dir.is_dir():
        for path in recipes_dir.glob("recipe_*.txt"):
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            parsed = parse_recipe_text(raw, rel=f"repro_recipes/{path.name}")
            if parsed:
                recipes.append(parsed)

    with _cache_lock:
        _cache["key"] = key
        _cache["recipes"] = recipes
        _cache["figures"] = figures
    return {"recipes": recipes, "figures": figures}


def _query_terms(query: str) -> list[str]:
    q = (query or "").lower()
    terms = set(re.findall(r"[a-z0-9_]{3,}|[\u4e00-\u9fff]{2,}", q))
    return [t for t in terms if t not in {"the", "and", "for", "with", "from", "this"}]


def _caption_matches_plot(caption: str, plot_type: str) -> bool:
    if not plot_type:
        return False
    low = (caption or "").lower()
    terms = _PLOT_CAPTION_TERMS.get(plot_type) or (plot_type.replace("_", " "),)
    return any(t in low for t in terms)


def _catalog_type_matches(figure_type: str, plot_type: str) -> bool:
    if not plot_type or not figure_type:
        return False
    ft = figure_type.lower()
    hints = _CATALOG_TYPE_HINTS.get(plot_type) or (plot_type.replace("_", " "),)
    return any(h in ft for h in hints)


def _score_figure(
    *,
    tag: str,
    caption: str,
    paper_title: str,
    plot_type: str,
    terms: list[str],
    figure_type: str = "",
    is_research_plot: bool | None = None,
    visual_description: str = "",
) -> int:
    score = 0
    blob = f"{tag} {figure_type} {caption} {paper_title} {visual_description}".lower()
    if plot_type:
        mapped = FIGURE_TAG_TO_PLOTS.get(tag, ())
        if plot_type in mapped:
            score += 24
        elif _catalog_type_matches(figure_type, plot_type):
            score += 26
        elif _caption_matches_plot(caption, plot_type) or _caption_matches_plot(visual_description, plot_type):
            score += 16
        elif tag in _NON_ANALYTICAL_TAGS and not _caption_matches_plot(caption, plot_type):
            return 0
        elif figure_type and any(s in figure_type for s in _SKIP_CATALOG_TYPES):
            return 0
        elif is_research_plot is False and score <= 0:
            return 0
    for t in terms:
        if t in blob:
            score += 2
    if is_research_plot is True:
        score += 2
    return score


def _score_recipe_plan(recipe: dict[str, Any], terms: list[str]) -> int:
    if int(recipe.get("workflow_steps") or 0) <= 0:
        return 0
    blob = (
        f"{recipe.get('paper_title') or ''} {recipe.get('tools_blob') or ''} "
        f"{recipe.get('source_paper') or ''}"
    ).lower()
    score = sum(2 for t in terms if t in blob)
    if score <= 0:
        return 0
    score += min(8, int(recipe.get("repro_score") or 0) // 12)
    score += min(6, int(recipe.get("workflow_steps") or 0))
    return score


def search_figure_hits(
    *,
    source_dir: str | Path,
    plot_type: str = "",
    query: str = "",
    max_hits: int = 6,
) -> list[dict[str, Any]]:
    """按图型/查询从 figure_index + recipe figure_recipes 取命中。"""
    corpus = load_corpus(source_dir)
    terms = _query_terms(query)
    scored: list[tuple[int, dict[str, Any]]] = []

    for fig in corpus["figures"]:
        score = _score_figure(
            tag=str(fig.get("tag") or ""),
            caption=str(fig.get("caption") or ""),
            paper_title=str(fig.get("paper_title") or ""),
            plot_type=plot_type,
            terms=terms,
            figure_type=str(fig.get("figure_type") or ""),
            is_research_plot=fig.get("is_research_plot"),
            visual_description=str(fig.get("visual_description") or ""),
        )
        if score <= 0:
            continue
        item = dict(fig)
        item["score"] = score
        scored.append((score, item))

    for recipe in corpus["recipes"]:
        for fig in recipe.get("figures") or []:
            tag = str(fig.get("tag") or "")
            caption = str(fig.get("caption") or "")
            score = _score_figure(
                tag=tag,
                caption=caption,
                paper_title=str(recipe.get("paper_title") or ""),
                plot_type=plot_type,
                terms=terms,
            )
            if score <= 0:
                continue
            item = {
                "kind": "recipe_figure",
                "rel": recipe.get("rel") or "",
                "figure_id": fig.get("id") or "",
                "tag": tag,
                "caption": caption,
                "viz_tool": fig.get("viz_tool") or "",
                "stat_test": fig.get("stat_test") or "",
                "paper_title": recipe.get("paper_title") or "",
                "source_paper": recipe.get("source_paper") or "",
                "doi": recipe.get("doi") or "",
                "score": score,
            }
            scored.append((score, item))

    scored.sort(key=lambda x: (-x[0], str(x[1].get("doi") or "")))
    uniq: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for score, item in scored:
        key = (item.get("doi") or "", item.get("caption") or "", item.get("figure_id") or "")
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
        if len(uniq) >= max_hits:
            break
    return uniq


def search_plan_recipes(
    *,
    source_dir: str | Path,
    query: str,
    max_hits: int = 3,
) -> list[dict[str, Any]]:
    corpus = load_corpus(source_dir)
    terms = _query_terms(query)
    if not terms:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for recipe in corpus["recipes"]:
        score = _score_recipe_plan(recipe, terms)
        if score <= 0:
            continue
        scored.append((score, recipe))
    scored.sort(key=lambda x: (-x[0], -int(x[1].get("repro_score") or 0)))
    out: list[dict[str, Any]] = []
    for score, recipe in scored[:max_hits]:
        item = dict(recipe)
        item["score"] = score
        out.append(item)
    return out


def hits_to_markdown(hits: list[dict[str, Any]], *, max_chars: int = 2400) -> str:
    if not hits:
        return ""
    parts = [
        "## Published figures (figure_catalog / repro_recipes / figure_index)",
        "Use captions and visual_description for title wording, panel purpose, and tool conventions.",
        "Do not copy statistical thresholds into plot_config unless the user asked.",
        "",
    ]
    budget = max_chars
    for hit in hits:
        doi = hit.get("doi") or ""
        tag = hit.get("figure_type") or hit.get("tag") or hit.get("kind") or ""
        header = f"- {hit.get('figure_id') or tag}"
        if doi:
            header += f" (DOI:{doi})"
        lines = [header, f"  caption: {hit.get('caption') or ''}"]
        if hit.get("figure_type"):
            lines.append(f"  figure_type: {hit['figure_type']}")
        if hit.get("viz_tool"):
            lines.append(f"  visualization_tool: {hit['viz_tool']}")
        desc = str(hit.get("visual_description") or "").strip()
        if desc:
            lines.append(f"  visual_description: {desc[:280]}")
        if hit.get("stat_test"):
            lines.append(f"  statistical_test (do not auto-apply): {hit['stat_test']}")
        paper = hit.get("paper_title") or ""
        if paper:
            lines.append(f"  paper: {paper}")
        chunk = "\n".join(lines) + "\n"
        if len(chunk) > budget and len(parts) > 4:
            break
        parts.append(chunk)
        budget -= len(chunk)
    return "\n".join(parts).strip()


def plan_recipes_to_markdown(recipes: list[dict[str, Any]], *, max_chars: int = 2800) -> str:
    if not recipes:
        return ""
    parts = [
        "## Reproducibility recipes (softwares_database/repro_recipes)",
        "Prefer published tool order and named parameters that map onto available MCP tools.",
        "",
    ]
    budget = max_chars
    for rec in recipes:
        doi = rec.get("doi") or ""
        header = f"### {rec.get('paper_title') or rec.get('rel')}"
        if doi:
            header += f" (DOI:{doi})"
        figs = rec.get("figures") or []
        fig_bits = [
            f"{f.get('id')} [{f.get('tag')}] {f.get('caption')}"
            for f in figs[:4]
            if f.get("caption")
        ]
        tools = (rec.get("tools_blob") or "")[:700]
        body = (
            f"{header}\n"
            f"workflow_steps={rec.get('workflow_steps')} "
            f"reproducibility_score={rec.get('repro_score')}/100\n"
        )
        if tools:
            body += f"tools: {tools}\n"
        if fig_bits:
            body += "figures:\n- " + "\n- ".join(fig_bits) + "\n"
        body += "\n"
        if len(body) > budget and len(parts) > 3:
            break
        parts.append(body)
        budget -= len(body)
    return "\n".join(parts).strip()


def retrieve_corpus(
    query: str,
    source_dir: str | Path,
    *,
    intent: str = "plan",
    plot_type: str = "",
    max_chars: int = 2800,
) -> dict[str, Any]:
    """规划或作图用的结构化语料检索。"""
    root = Path(source_dir)
    if not root.is_dir():
        return {"text": "", "sources": [], "hits": []}

    if intent == "plot":
        hits = search_figure_hits(
            source_dir=root,
            plot_type=plot_type,
            query=query,
            max_hits=6,
        )
        text = hits_to_markdown(hits, max_chars=max_chars)
        sources = sorted({str(h.get("rel") or "figure_index.txt") for h in hits})
        return {"text": text, "sources": sources, "hits": hits}

    recipes = search_plan_recipes(source_dir=root, query=query, max_hits=3)
    fig_hits: list[dict[str, Any]] = []
    qlow = (query or "").lower()
    if any(k in qlow for k in ("图", "plot", "pca", "volcano", "heatmap", "网络", "network")):
        fig_hits = search_figure_hits(source_dir=root, query=query, max_hits=3)
    parts = [
        plan_recipes_to_markdown(recipes, max_chars=max_chars),
        hits_to_markdown(fig_hits, max_chars=max(400, max_chars // 3)) if fig_hits else "",
    ]
    text = "\n\n".join(p for p in parts if p).strip()
    sources = [str(r.get("rel") or "") for r in recipes if r.get("rel")]
    sources.extend(str(h.get("rel") or "") for h in fig_hits)
    return {"text": text, "sources": [s for s in sources if s], "hits": recipes + fig_hits}


def evidence_cards_from_hits(
    hits: list[dict[str, Any]],
    *,
    plot_type: str,
    max_cards: int = 4,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for i, hit in enumerate(hits[:max_cards]):
        caption = str(hit.get("caption") or "").strip()
        if not caption:
            continue
        extra = " ".join(
            x
            for x in (
                hit.get("figure_type") or "",
                hit.get("viz_tool") or "",
                (hit.get("visual_description") or "")[:180],
                hit.get("stat_test") or "",
                hit.get("source_paper") or "",
            )
            if x
        )
        quote = caption if not extra else f"{caption} ({extra})"
        cards.append(
            {
                "evidence_id": f"corpus:{hit.get('rel') or 'figure_index'}#{hit.get('figure_id') or i}",
                "skill_id": "literature_corpus",
                "doi": hit.get("doi") or "",
                "source": hit.get("rel") or "figure_index.txt",
                "quote": quote[:400],
                "caption": caption,
                "field_hints": ["title", "style"],
                "claim_type": "literature_example",
                "plot_type": plot_type,
                "confidence": 0.62,
                "journal_hint": detect_journal_from_source(
                    f"{hit.get('source_paper') or ''} {hit.get('paper_title') or ''}"
                )
                or (
                    "npg"
                    if "ggplot" in str(hit.get("viz_tool") or "").lower()
                    else None
                ),
            }
        )
    return cards


__all__ = [
    "FIGURE_TAG_TO_PLOTS",
    "clear_corpus_cache",
    "detect_journal_from_source",
    "evidence_cards_from_hits",
    "extract_doi",
    "load_corpus",
    "parse_recipe_text",
    "retrieve_corpus",
    "search_figure_hits",
    "search_plan_recipes",
    "short_title_from_caption",
]
