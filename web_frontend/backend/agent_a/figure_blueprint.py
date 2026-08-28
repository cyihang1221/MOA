"""Agent A Phase 1：为 required_visualization 写入论文复现向的 Figure 蓝图。

在规划阶段（写 analysis_plan 前）为每张图补齐：
- source_step / source_files（B→C 数据契约）
- plot_config_hint（发表级基线 + 可选文献 Skill 软样式）
- literature_refs（可追溯的 skill/DOI 摘要）
- reproduction_target（若命中 repro recipe）

不改变 B 可执行步骤列表；只增强 A→C 的可视化契约。
"""
from __future__ import annotations

import re
from typing import Any

from web_frontend.backend.agent_a.plan_catalog import figure_payload, hint_for_plot
from web_frontend.backend.agent_a.plan_document import executable_tasks_for_b
from web_frontend.backend.agent_c.plan_parser import resolve_all_plot_types
from web_frontend.backend.plot_edit_registry import get_plot_spec, stem_prefix_for_plot_type

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\])>,]+", re.IGNORECASE)
_REPRO_KEYWORDS = (
    "复现",
    "reproduce",
    "reproduction",
    "照着",
    "按论文",
    "论文图",
    "figure 1",
    "fig 1",
    "fochx",
    "都匀毛尖",
    "duyun",
    "maojian",
)

# plot_type → 产出该图数据的 B 侧工具名片段（用于 source_step 推断）
_PLOT_TOOL_HINTS: dict[str, tuple[str, ...]] = {
    "pca": ("statistical_analysis_mixomics", "mixomics"),
    "plsda": ("statistical_analysis_mixomics", "mixomics"),
    "volcano": ("statistical_analysis_mixomics", "mixomics"),
    "vip_bar": ("statistical_analysis_mixomics", "mixomics"),
    "heatmap_vip": ("statistical_analysis_mixomics", "mixomics"),
    "kegg_bubble": ("kegg_compound_enrichment", "kegg"),
    "kegg_bar": ("kegg_compound_enrichment", "kegg"),
    "kegg_dotplot": ("kegg_compound_enrichment", "kegg"),
    "cosine_hist": ("molecular_networking", "network"),
    "degree_hist": ("molecular_networking", "network"),
    "family_size": ("molecular_networking", "network"),
    "network_topology": ("molecular_networking", "network"),
    "precursor_mass_diff": ("molecular_networking", "network"),
    "motif_match": ("molecular_networking", "network"),
}


def match_repro_recipe(text: str) -> dict[str, Any] | None:
    """从用户目标文本匹配 agent_c/repro_recipes 中的论文复现配方。"""
    from web_frontend.backend.agent_c.paper_reproduction import list_repro_recipes, load_repro_recipe

    blob = (text or "").strip()
    if not blob:
        return None
    low = blob.lower()
    recipes = list_repro_recipes()
    if not recipes:
        return None

    doi_in_text = {m.group(0).lower().rstrip(".") for m in _DOI_RE.finditer(blob)}

    def _score(item: dict[str, Any]) -> int:
        rid = str(item.get("recipe_id") or "").lower()
        title = str(item.get("title") or "").lower()
        doi = str(item.get("doi") or "").lower().rstrip(".")
        score = 0
        if rid and rid in low:
            score += 100
        if doi and doi in doi_in_text:
            score += 90
        if doi and doi.replace("/", "") in low.replace("/", ""):
            score += 80
        for kw in _REPRO_KEYWORDS:
            if kw in low or kw in title:
                score += 5
        if "都匀" in blob and "毛尖" in blob and "maojian" in rid:
            score += 70
        return score

    ranked = sorted(recipes, key=_score, reverse=True)
    best = ranked[0]
    if _score(best) < 5:
        return None
    try:
        return load_repro_recipe(str(best.get("recipe_id") or ""))
    except (FileNotFoundError, ValueError, OSError):
        return None


def infer_source_step(plot_type: str, tasks: list[str]) -> int:
    """推断产出该图数据的 workflow Step 序号（1-based）。"""
    hints = _PLOT_TOOL_HINTS.get(plot_type) or ()
    b_tasks = executable_tasks_for_b(tasks)
    for i, task in enumerate(b_tasks, start=1):
        low = task.lower()
        if hints and any(h in low for h in hints):
            return i
    for i, task in enumerate(b_tasks, start=1):
        for pt in resolve_all_plot_types(task):
            if pt == plot_type:
                return i
    return 0


def _default_source_files(plot_type: str) -> list[str]:
    spec = get_plot_spec(plot_type)
    if not spec:
        return []
    return [str(f) for f in spec.data_files]


def _recipe_figure_index(recipe: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not recipe:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for fig in recipe.get("figures") or []:
        if not isinstance(fig, dict):
            continue
        pt = str(fig.get("plot_type") or "")
        if pt:
            out[pt] = fig
        fid = str(fig.get("figure_id") or "")
        if fid:
            out[fid.lower()] = fig
    return out


def build_plot_config_hint(
    plot_type: str,
    *,
    goal_text: str,
    recipe_figure: dict[str, Any] | None = None,
    project_root: Any = None,
) -> dict[str, Any]:
    """规划阶段写入 C 的样式 hint（不含运行时 palette 键）。"""
    hint: dict[str, Any] = {}
    if recipe_figure:
        hint.update(dict(recipe_figure.get("plot_config_hint") or {}))
        params = recipe_figure.get("parameters") or {}
        if isinstance(params, dict):
            for k, v in params.items():
                if k.endswith("_threshold") or k in {"pca_scaling", "hca_euclidean_cutoff"}:
                    hint.setdefault("parameters", {})[k] = v

    from web_frontend.backend.literature_figure_style import (
        DEFAULT_JOURNAL,
        PUBLICATION_BASELINE,
        resolve_figure_style,
    )

    baseline = PUBLICATION_BASELINE.get(plot_type) or {}
    if baseline:
        hint.setdefault("font_size", dict(baseline.get("font_size") or {}))
        if baseline.get("figure_size"):
            hint["figure_size"] = list(baseline["figure_size"])
        if baseline.get("legend"):
            hint["legend"] = dict(baseline["legend"])
        if baseline.get("marks"):
            hint["marks"] = dict(baseline["marks"])
        if baseline.get("colors"):
            hint["colors"] = dict(baseline["colors"])

    style = resolve_figure_style(
        plot_type=plot_type,
        goal_text=goal_text,
        project_root=project_root,
        use_literature=True,
    )
    patch = style.get("patch") or {}
    if patch:
        for key in ("font_size", "figure_size", "legend", "marks", "colors", "title_align"):
            if key in patch and patch[key] is not None:
                hint[key] = patch[key]
    hint["journal_palette"] = style.get("journal") or DEFAULT_JOURNAL
    hint["style_source"] = style.get("source") or "baseline"
    if style.get("matched"):
        hint["matched_skills"] = list(style["matched"])[:5]
    return hint


def _literature_refs_from_hint(hint: dict[str, Any], recipe: dict[str, Any] | None) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    paper = (recipe or {}).get("paper") or {}
    doi = str(paper.get("doi") or "").strip()
    if doi:
        refs.append({"type": "paper", "doi": doi, "title": str(paper.get("short_title") or "")[:120]})
    for sid in hint.get("matched_skills") or []:
        refs.append({"type": "skill", "skill_id": str(sid)})
    return refs


def enrich_figure_blueprints(
    figures: list[dict[str, Any]],
    tasks: list[str],
    *,
    user_message: str = "",
    objective: str = "",
    project_root: Any = None,
    recipe: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """增强 Figure 列表并返回 blueprint 元信息。"""
    goal = "\n".join(x for x in (objective, user_message) if x).strip()
    if recipe is None:
        recipe = match_repro_recipe(goal)
    recipe_idx = _recipe_figure_index(recipe)
    meta: dict[str, Any] = {
        "reproduction_target": None,
        "matched_recipe_id": "",
        "n_figures": len(figures),
        "warnings": [],
    }
    if recipe:
        paper = recipe.get("paper") or {}
        meta["matched_recipe_id"] = str(recipe.get("recipe_id") or "")
        meta["reproduction_target"] = {
            "recipe_id": meta["matched_recipe_id"],
            "doi": paper.get("doi") or "",
            "short_title": paper.get("short_title") or paper.get("title") or "",
            "journal": paper.get("journal") or "",
        }

    enriched: list[dict[str, Any]] = []
    for fig in figures:
        item = dict(fig)
        plot_type = str(item.get("plot_type") or "")
        if not plot_type:
            enriched.append(item)
            continue

        rf = recipe_idx.get(plot_type) or recipe_idx.get(str(item.get("figure_id") or "").lower())
        if rf:
            if rf.get("figure_id") and not item.get("figure_id"):
                item["figure_id"] = rf["figure_id"]
            if rf.get("title"):
                item["title"] = rf["title"]
            if rf.get("panels"):
                item["panels"] = list(rf["panels"])
            if rf.get("theme"):
                item["theme"] = rf["theme"]
            item["paper_ref"] = (recipe.get("paper") or {}).get("doi") or item.get("paper_ref") or ""

        step = infer_source_step(plot_type, tasks)
        if step:
            item["source_step"] = step
        elif rf and rf.get("source_step"):
            item["source_step"] = rf["source_step"]

        sfiles = list(item.get("source_files") or [])
        if rf and rf.get("source_files"):
            sfiles = list(rf["source_files"])
        elif not sfiles:
            sfiles = _default_source_files(plot_type)
        item["source_files"] = sfiles

        if not item.get("stem"):
            item["stem"] = (
                (rf or {}).get("stem")
                or stem_prefix_for_plot_type(plot_type)
                or plot_type
            )

        hint = build_plot_config_hint(
            plot_type,
            goal_text=goal,
            recipe_figure=rf,
            project_root=project_root,
        )
        item["plot_config_hint"] = hint
        item["literature_refs"] = _literature_refs_from_hint(hint, recipe)

        if not item.get("theme"):
            h = hint_for_plot(plot_type)
            item["theme"] = h.get("theme") or ""
        enriched.append(item)

    if recipe and not enriched:
        meta["warnings"].append("命中论文配方但未从步骤解析到图型；请检查 workflow 是否含统计/网络步骤。")

    return enriched, meta


def figures_from_tasks_with_blueprints(
    tasks: list[str],
    *,
    user_message: str = "",
    objective: str = "",
    project_root: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """从 B 步骤推断图型并写入完整 Figure 蓝图。"""
    figures: list[dict[str, Any]] = []
    seen: set[str] = set()
    for plot_type in resolve_all_plot_types("\n".join(tasks)):
        if plot_type in seen:
            continue
        seen.add(plot_type)
        spec = get_plot_spec(plot_type)
        figures.append(
            figure_payload(
                plot_type,
                len(figures) + 1,
                spec.default_title if spec else plot_type,
            )
        )
    return enrich_figure_blueprints(
        figures,
        tasks,
        user_message=user_message,
        objective=objective,
        project_root=project_root,
    )


def blueprint_summary_markdown(meta: dict[str, Any], figures: list[dict[str, Any]]) -> str:
    """Agent A 规划完成后展示的 Figure 蓝图摘要。"""
    lines = ["### 📐 Figure 蓝图（Phase 1 · 论文复现向）", ""]
    target = meta.get("reproduction_target")
    if target:
        lines.append(
            f"- **论文复现目标**：{target.get('short_title') or target.get('recipe_id')} "
            f"（DOI `{target.get('doi') or '—'}`）"
        )
    elif meta.get("matched_recipe_id"):
        lines.append(f"- **论文配方**：`{meta['matched_recipe_id']}`")
    else:
        lines.append("- **模式**：常规分析；已写入发表级样式 hint + 文献 Skill（若命中）。")
    lines.append(f"- **计划图数**：{len(figures)}")
    lines.append("")
    for fig in figures[:8]:
        fid = fig.get("figure_id") or "Figure"
        pt = fig.get("plot_type") or "?"
        step = fig.get("source_step") or "—"
        sfiles = ", ".join(fig.get("source_files") or []) or "—"
        hint = fig.get("plot_config_hint") or {}
        journal = hint.get("journal_palette") or "npg"
        src = hint.get("style_source") or "baseline"
        lines.append(
            f"- **{fid}** `{pt}` → Step {step}；数据：`{sfiles}`；样式：{journal}（{src}）"
        )
    if len(figures) > 8:
        lines.append(f"- … 另有 {len(figures) - 8} 张图，详见 `analysis_plan.json`。")
    lines.append("")
    lines.append(
        "C 出图时将优先使用上述 `plot_config_hint`；缺数据时会给出逐步补齐 checklist。"
    )
    return "\n".join(lines)


__all__ = [
    "blueprint_summary_markdown",
    "build_plot_config_hint",
    "enrich_figure_blueprints",
    "figures_from_tasks_with_blueprints",
    "infer_source_step",
    "match_repro_recipe",
]
