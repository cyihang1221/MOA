"""从文献 Skill（MassOmics skills + phase2_output）提取作图知识，供前端改图 Agent 注入。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from web_frontend.backend.plot_edit_registry import PLOT_SPECS, plot_type_from_stem
from web_frontend.backend.skill_match import (
    _massomics_skills_root,
    _trigger_keywords_from_description,
)

# plot_type → 在出图清单/正文中检索用的关键词（由 registry 扩展 + 手工补充）
_PLOT_TYPE_TERMS_EXTRA: dict[str, tuple[str, ...]] = {
    "pca": ("3d pca", "pca score", "得分图", "score plot"),
    "plsda": ("s-plot", "偏最小二乘", "opls-da"),
    "volcano": ("火山图", "log2fc", "差异代谢"),
    "vip_bar": ("vip 排名", "variable importance"),
    "heatmap_vip": ("heat map", "top vip"),
    "motif_match": ("motif", "碎片", "fragment"),
    "kegg_bubble": ("bubble", "气泡", "富集气泡"),
    "kegg_dotplot": ("dotplot", "点图"),
    "kegg_barplot": ("barplot", "条形", "kegg bar"),
    "fbmn_group_intensity": ("fbmn", "group intensity", "组强度"),
    "annotation_propagation": ("annotation propagation", "注释传播"),
    "mass2motif_network": ("mass2motif network", "motif network"),
    "pearson_hist": ("pearson", "皮尔逊", "correlation distribution"),
    "plsda_permutation": ("permutation", "置换检验"),
    "constituent_bar": ("tpc", "tfc", "constituent"),
    "relative_abundance_heatmap": ("relative abundance", "相对丰度"),
    "hca_heatmap": ("hca", "层次聚类"),
    "correlation_heatmap": ("correlation heatmap", "相关热图"),
    "bioactivity_bar": ("bioactivity", "生物活性"),
    "sensory_scores": ("sensory", "感官"),
    "splot": ("s-plot", "s plot", "opls-da", "loading", "p(corr)"),
    "opls_outlier": ("outlier", "离群", "score distance", "orthogonal distance", "hotelling"),
    "roc_auc_hist": ("roc", "auc", "auroc", "受试者工作特征"),
    "significance_venn": ("venn", "韦恩", "维恩", "intersection", "交集"),
    "log2fc_hist": ("log2fc", "fold change", "倍数变化"),
}


def _build_plot_type_terms() -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for spec in PLOT_SPECS:
        parts = {
            spec.plot_type,
            spec.plot_type.replace("_", " "),
            spec.stem_prefix,
            spec.stem_prefix.replace("_", " "),
            spec.default_title.lower(),
        }
        for token in re.split(r"[\s/\-–]+", spec.default_title.lower()):
            if len(token) >= 3:
                parts.add(token)
        extra = _PLOT_TYPE_TERMS_EXTRA.get(spec.plot_type, ())
        out[spec.plot_type] = tuple(sorted({p.lower() for p in parts if p} | {e.lower() for e in extra}))
    return out


PLOT_TYPE_TERMS: dict[str, tuple[str, ...]] = _build_plot_type_terms()

# 图型族 → 可匹配的上游 Skill 主题词（跨 plot_type 关联 GNPS/KEGG 等）
_PLOT_FAMILY_SKILL_HINTS: dict[str, frozenset[str]] = {
    "network": frozenset(
        {
            "cosine_hist",
            "degree_hist",
            "network_topology",
            "family_size",
            "precursor_mass_diff",
            "pearson_hist",
            "annotation_propagation",
            "fbmn_group_intensity",
        }
    ),
    "kegg": frozenset({"kegg_bubble", "kegg_dotplot", "kegg_barplot"}),
    "stats": frozenset({"pca", "plsda", "volcano", "vip_bar", "heatmap_vip"}),
    "ms2lda": frozenset(
        {
            "mass2motif_overview",
            "mass2motif_fragments",
            "motif_spectrum_heatmap",
            "mass2motif_network",
            "motif_match",
        }
    ),
}

_FAMILY_BLOB_HINTS: dict[str, tuple[str, ...]] = {
    "network": ("gnps", "fbmn", "molecular network", "分子网络", "cytoscape", "cosine", "topology"),
    "kegg": ("kegg", "pathway", "富集", "enrichment", "mummichog"),
    "ms2lda": ("ms2lda", "mass2motif", "motif", "碎片"),
    "stats": ("mixomics", "metaboanalyst", "pls-da", "volcano", "heatmap", "vip", "pca score"),
}

# 这些图优先用带出图清单的文献 Skill；少数软件参数卡只在点名图型时放行。
_PREFERRED_FIGURE_SKILLS: dict[str, tuple[str, ...]] = {
    "pca": (
        "rohart-2017-mixomics",
        "consensus_statistical_analysis",
        "statistical_analysis_using_metaboanalyst",
        "duyun-maojian",
    ),
    "plsda": (
        "rohart-2017-mixomics",
        "szymanska-2012-plsda",
        "consensus_statistical_analysis",
        "duyun-maojian",
    ),
    "volcano": (
        "consensus_statistical_analysis",
        "statistical_analysis_using_metaboanalyst",
        "general_metabolomics_expanding_the_landscape",
        "pathway_enrichment_comparative_metabolomics",
    ),
    "vip_bar": (
        "duyun-maojian",
        "consensus_statistical_analysis",
        "rohart-2017-mixomics",
    ),
    "heatmap_vip": (
        "consensus_statistical_analysis",
        "statistical_analysis_using_metaboanalyst",
        "general_metabolomics_expanding_the_landscape",
    ),
    "kegg_bubble": (
        "kanehisa-2017-kegg",
        "consensus_pathway_enrichment",
        "statistical_analysis_using_metaboanalyst",
    ),
    "kegg_dotplot": (
        "kanehisa-2017-kegg",
        "consensus_pathway_enrichment",
        "pathway_enrichment_comparative_metabolomics",
    ),
    "kegg_barplot": (
        "kanehisa-2017-kegg",
        "consensus_pathway_enrichment",
    ),
}

_RAG_FIGURE_FOCUS: dict[str, str] = {
    "pca": "figure type pca_scores; PCA score plot; plotIndiv or ggplot2; group colors; 95% ellipse; legend outside",
    "plsda": "PLS-DA score plot; plotIndiv; confidence ellipse; class colors; not OPLS S-plot",
    "volcano": "figure type volcano_plot; ggplot2 theme_bw; log2 fold change; -log10 p; dashed threshold lines",
    "vip_bar": "VIP bar plot; VIP threshold line; ggplot2; upregulated red downregulated blue",
    "heatmap_vip": "figure type heatmap; pheatmap; group annotation bar; hierarchical clustering; short metabolite IDs",
    "kegg_bubble": "KEGG pathway enrichment bubble plot; ggplot2; Count; -log10 FDR; theme_minimal",
    "kegg_dotplot": "KEGG enrichment dotplot; ggplot2; point size Count; color FDR",
    "kegg_barplot": "KEGG enrichment barplot; ggplot2; pathway Count",
}

_SKILL_POOL_SOFTWARE_PARAMS = "software_params"
_SKILL_POOL_LITERATURE = "literature_workflow"
_SKILL_POOL_PLOT = "plot_figure"
# Agent C 自有的改图规范 Skill。放在 web_frontend 下而不是 MassOmics skills/，
# Agent A 的 skill_match 扫不到，不会混进分析规划。
_SKILL_POOL_PLOT = "plot_figure"

_VISUAL_SECTION_MARKERS = (
    "出图清单",
    "出图",
    "figures",
    "visualization",
    "figure",
    "产出图",
    "required visualization",
)

_DOI_RE = re.compile(r"DOI[:\s]*[`']?([0-9./a-z\-]+)[`']?", re.I)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def env_enabled() -> bool:
    v = (os.environ.get("WEB_LITERATURE_PLOT") or os.environ.get("WEB_SKILL_MATCH") or "1").strip().lower()
    return v not in {"0", "false", "off", "no"}


def plot_rag_enabled() -> bool:
    """改图是否追加 softwares_database(_RAG) 检索片段。"""
    v = (os.environ.get("WEB_LITERATURE_PLOT_RAG") or "1").strip().lower()
    return env_enabled() and v not in {"0", "false", "off", "no"}


def _rag_database_paths(project_root: Path | None = None) -> tuple[str, str]:
    from web_frontend.backend.literature_paths import resolve_literature_dirs

    return resolve_literature_dirs(project_root or _project_root())


def build_plot_literature_query(
    *,
    plot_type: str,
    goal_text: str = "",
    instruction: str = "",
) -> str:
    from web_frontend.backend.literature_rag import build_tool_literature_query

    terms = ", ".join(PLOT_TYPE_TERMS.get(plot_type, (plot_type.replace("_", " "),))[:8])
    task_bits = [
        f"Published metabolomics figure captions and styling for plot type `{plot_type}`",
        "Search figure_index captions and repro_recipes figure_recipes "
        "(pca_scores, volcano_plot, heatmap, network), not peak-picking parameters.",
    ]
    if terms:
        task_bits.append(f"Related terms: {terms}")
    focus = _RAG_FIGURE_FOCUS.get(plot_type)
    if focus:
        task_bits.append(f"Prefer papers whose Expected Figures match: {focus}")
    if instruction.strip():
        task_bits.append(f"User edit request: {instruction.strip()[:200]}")
    task_bits.append(
        "Focus on chart purpose, title wording, axis labels, color semantics, legend layout, "
        "and panel arrangement. Ignore ppm/peakwidth/centWave unless the user asked about them."
    )
    return build_tool_literature_query(goal_description=goal_text, task=" ".join(task_bits))


def supplement_plot_literature_rag(
    *,
    plot_type: str,
    goal_text: str = "",
    instruction: str = "",
    project_root: Path | None = None,
    top_k: int = 3,
    max_chars: int = 2200,
) -> dict[str, Any]:
    """向量/关键词 RAG 补充作图语境（与 Skill 检索并行，不替代 rank）。"""
    if not plot_rag_enabled() or not plot_type:
        return {"text": "", "mode": "disabled", "sources": [], "error": None}
    persist_dir, source_dir = _rag_database_paths(project_root)
    if not Path(source_dir).is_dir():
        return {"text": "", "mode": "empty", "sources": [], "error": "missing source_dir"}
    try:
        from web_frontend.backend.literature_rag import retrieve_literature

        query = build_plot_literature_query(
            plot_type=plot_type,
            goal_text=goal_text,
            instruction=instruction,
        )
        payload = retrieve_literature(
            query,
            persist_dir=persist_dir,
            source_dir=source_dir,
            top_k=top_k,
            intent="plot",
            plot_type=plot_type,
        )
        text = str(payload.get("text") or "").strip()
        if len(text) > max_chars:
            text = text[: max(0, max_chars - 20)].rstrip() + "\n…[truncated]"
        return {
            "text": text,
            "mode": payload.get("mode") or "empty",
            "sources": list(payload.get("sources") or []),
            "error": payload.get("error"),
        }
    except Exception as exc:
        return {"text": "", "mode": "empty", "sources": [], "error": str(exc)}


def _phase2_registry_path(project_root: Path | None = None) -> Path:
    from web_frontend.backend.literature_paths import resolve_phase2_registry

    return resolve_phase2_registry(project_root if project_root is not None else _project_root())


def _parse_skill_frontmatter(text: str) -> tuple[str, str, list[str]]:
    """返回 (name, description, trigger_keywords)。"""
    name = ""
    desc = ""
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.S)
    if m:
        block = m.group(1)
        nm = re.search(r"^name:\s*(.+)$", block, re.M)
        if nm:
            name = nm.group(1).strip()
        dm = re.search(r"description:\s*[>|]-?\s*\n(.*)", block, re.S)
        if dm:
            desc = re.split(r"\n[a-z_]+:\s*", dm.group(1), maxsplit=1)[0].strip()
        else:
            dm2 = re.search(r"description:\s*(.+)$", block, re.M)
            if dm2:
                desc = dm2.group(1).strip()
    keywords = _trigger_keywords_from_description(desc)
    if not name:
        m_title = re.search(r"^#\s+(.+)$", text, re.M)
        name = (m_title.group(1).strip() if m_title else "skill")[:80]
    return name, desc, keywords


def _extract_doi(text: str) -> str:
    m = _DOI_RE.search(text)
    return m.group(1).strip() if m else ""


def _extract_visual_block(body: str, max_chars: int = 1200) -> str:
    """抽取出图相关章节（表格与列表）。"""
    lines = body.splitlines()
    blocks: list[list[str]] = []
    cur: list[str] = []
    in_visual = False
    in_code = False

    for ln in lines:
        if ln.strip().startswith("```"):
            in_code = not in_code
            if in_visual and not in_code:
                cur.append(ln)
            continue
        if in_code:
            if in_visual:
                cur.append(ln)
            continue
        if ln.startswith("## "):
            header = ln[3:].strip().lower()
            if cur and in_visual:
                blocks.append(cur)
            cur = []
            in_visual = any(m.lower() in header for m in _VISUAL_SECTION_MARKERS)
            if in_visual:
                cur.append(ln)
            continue
        if in_visual:
            cur.append(ln)
            # 遇到下一无关大节则结束
            if ln.startswith("## ") and not any(m.lower() in ln.lower() for m in _VISUAL_SECTION_MARKERS):
                blocks.append(cur[:-1])
                cur = []
                in_visual = False

    if cur and in_visual:
        blocks.append(cur)

    if not blocks:
        # 回退：在全文中找含常见图型的行
        fig_lines = []
        for ln in lines:
            low = ln.lower()
            if any(
                tok in low
                for tok in (
                    "pca", "volcano", "heatmap", "score", "s-plot", "vip",
                    "network", "cosine", "degree", "enrichment", "火山", "热图", "得分",
                )
            ):
                fig_lines.append(ln)
        text = "\n".join(fig_lines)
    else:
        text = "\n\n".join("\n".join(b) for b in blocks)

    text = text.strip()
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…[truncated]"
    return text


def _dir_signature(root: Path, pattern: str = "SKILL.md") -> tuple:
    """目录内匹配文件的 (路径, mtime, size) 指纹，用于缓存失效判断。"""
    try:
        return tuple(
            sorted(
                (p.as_posix(), int(st.st_mtime), st.st_size)
                for p in root.rglob(pattern)
                if (st := p.stat()) is not None
            )
        )
    except OSError:
        return ()


_SKILL_CACHE: dict[str, tuple[tuple, list[dict[str, Any]]]] = {}


def _load_massomics_skills(project_root: Path | None = None) -> list[dict[str, Any]]:
    root = _massomics_skills_root(project_root)
    if not root.is_dir():
        return []
    cache_key = f"massomics:{root.as_posix()}"
    signature = _dir_signature(root)
    cached = _SKILL_CACHE.get(cache_key)
    if cached and cached[0] == signature:
        return cached[1]
    skills: list[dict[str, Any]] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except Exception:
            continue
        if not text.strip():
            continue
        name, desc, keywords = _parse_skill_frontmatter(text)
        rel = skill_md.relative_to(root).as_posix()
        branch = skill_md.parent.parent.name if skill_md.parent.parent != root else ""
        rel_norm = rel.replace("\\", "/")
        skill_pool = (
            _SKILL_POOL_SOFTWARE_PARAMS
            if rel_norm.startswith("software-params/") or "/software-params/" in rel_norm
            else _SKILL_POOL_LITERATURE
        )
        skills.append(
            {
                "source": "massomics",
                "skill_id": skill_md.parent.name,
                "skill_pool": skill_pool,
                "name": name,
                "description": desc,
                "keywords": keywords,
                "file": str(skill_md),
                "branch": branch,
                "doi": _extract_doi(text),
                "visual_block": _extract_visual_block(text) or _extract_figure_mentions(text),
                "body": text,
            }
        )
    _SKILL_CACHE[cache_key] = (signature, skills)
    return skills


def _load_phase2_skills(project_root: Path | None = None) -> list[dict[str, Any]]:
    reg_path = _phase2_registry_path(project_root)
    if not reg_path.is_file():
        return []
    cache_key = f"phase2:{reg_path.as_posix()}"
    try:
        reg_stat = reg_path.stat()
        signature = ((reg_path.as_posix(), int(reg_stat.st_mtime), reg_stat.st_size),)
    except OSError:
        signature = ()
    cached = _SKILL_CACHE.get(cache_key)
    if cached and cached[0] == signature:
        return cached[1]
    try:
        registry = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    skills: list[dict[str, Any]] = []
    for item in registry.get("skills", []) or []:
        rel = item.get("file") or ""
        skill_file = reg_path.parent / rel
        if not skill_file.is_file():
            continue
        try:
            text = skill_file.read_text(encoding="utf-8")
        except Exception:
            continue
        name = item.get("skill_name") or skill_file.stem
        keywords = list(item.get("trigger_keywords") or [])
        skills.append(
            {
                "source": "phase2",
                "skill_id": name,
                "skill_pool": _SKILL_POOL_LITERATURE,
                "name": name,
                "description": item.get("source_paper") or "",
                "keywords": keywords,
                "file": str(skill_file),
                "branch": item.get("functional_domain") or "",
                "doi": _extract_doi(text),
                "visual_block": _extract_visual_block(text) or _extract_figure_mentions(text),
                "body": text,
                "skill_type": item.get("skill_type"),
            }
        )
    _SKILL_CACHE[cache_key] = (signature, skills)
    return skills


def _plot_skills_root(project_root: Path | None = None) -> Path:
    base = project_root if project_root is not None else _project_root()
    return Path(base) / "web_frontend" / "backend" / "agent_c" / "plot_skills"


def _plot_skill_meta(text: str) -> dict[str, Any]:
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    try:
        import yaml  # type: ignore

        meta = yaml.safe_load(m.group(1))
    except Exception:
        return {}
    return meta if isinstance(meta, dict) else {}


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _load_plot_skills(project_root: Path | None = None) -> list[dict[str, Any]]:
    """Agent C 自己的改图规范 Skill。

    放在 web_frontend 下而不是 MassOmics skills 目录，Agent A 规划检索不到它们。
    """
    root = _plot_skills_root(project_root)
    if not root.is_dir():
        return []
    cache_key = f"plot:{root.as_posix()}"
    signature = _dir_signature(root)
    cached = _SKILL_CACHE.get(cache_key)
    if cached and cached[0] == signature:
        return cached[1]
    skills: list[dict[str, Any]] = []
    for skill_md in sorted(root.rglob("SKILL.md")):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = _plot_skill_meta(text)
        plot_types = _str_list(meta.get("plot_types"))
        if not plot_types:
            continue
        sid = str(meta.get("name") or skill_md.parent.name).strip()
        desc = str(meta.get("description") or "").strip()
        refs = _str_list(meta.get("references"))
        skills.append(
            {
                "source": "plot_skill",
                "skill_id": sid,
                "skill_pool": _SKILL_POOL_PLOT,
                "name": str(meta.get("display_name") or sid),
                "description": desc,
                "keywords": _trigger_keywords_from_description(desc),
                "file": str(skill_md),
                "branch": skill_md.parent.parent.name,
                "doi": refs[0] if refs else "",
                "references": refs,
                "plot_types": plot_types,
                "pairs_with": _str_list(meta.get("pairs_with")),
                "suggest": str(meta.get("suggest") or "").strip(),
                "visual_block": _extract_visual_block(text, max_chars=2400),
                "body": text,
            }
        )
    _SKILL_CACHE[cache_key] = (signature, skills)
    return skills


def _extract_figure_mentions(text: str, max_chars: int = 800) -> str:
    lines = []
    for ln in text.splitlines():
        if re.search(r"\b(fig\.?|figure|panel|图)\b", ln, re.I) or "出图" in ln:
            lines.append(ln)
    out = "\n".join(lines).strip()
    return out[:max_chars] if len(out) > max_chars else out


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,，。、/;；()（）\-]+", (text or "").lower()) if len(t) >= 2]


_GENERIC_SKILL_NAME_TOKENS = frozenset(
    {
        "流水线",
        "非靶向",
        "出图",
        "得分图",
        "热图",
        "分子",
        "网络",
        "文献",
        "步骤",
        "代谢组",
        "统计分析",
        "pca",
        "volcano",
        "heatmap",
        "plot",
        "figure",
    }
)


def _instruction_skill_bonus(instruction: str, skill: dict[str, Any]) -> int:
    """用户点名论文 / DOI / skill 时抬升排序。"""
    inst = (instruction or "").strip()
    if not inst:
        return 0
    inst_l = inst.lower()
    bonus = 0
    doi = str(skill.get("doi") or "").strip().lower()
    if doi and doi in inst_l:
        bonus += 80
    sid = str(skill.get("skill_id") or "")
    for part in re.split(r"[-_]", sid):
        if len(part) >= 4 and part.lower() not in _GENERIC_SKILL_NAME_TOKENS and part.lower() in inst_l:
            bonus += 24
    blob = " ".join(
        [
            str(skill.get("name") or ""),
            str(skill.get("description") or ""),
            str(skill.get("visual_block") or ""),
            sid,
        ]
    )
    for run in re.findall(r"[\u4e00-\u9fff]{2,6}", blob):
        if run in _GENERIC_SKILL_NAME_TOKENS:
            continue
        if run in inst:
            bonus += 50 + min(len(run) * 4, 24)
            break
    for kw in skill.get("keywords") or []:
        k = str(kw).strip()
        if len(k) < 4 or k.lower() in _GENERIC_SKILL_NAME_TOKENS:
            continue
        if k.lower() in inst_l or k in inst:
            bonus += 20
            break
    return min(bonus, 120)


def _plot_terms_for_type(plot_type: str) -> tuple[str, ...]:
    if not plot_type:
        return ()
    return PLOT_TYPE_TERMS.get(plot_type, (plot_type.replace("_", " "), plot_type))


def _skill_blob(skill: dict[str, Any]) -> str:
    return " ".join(
        [
            str(skill.get("name") or ""),
            str(skill.get("description") or ""),
            str(skill.get("branch") or ""),
            str(skill.get("visual_block") or ""),
            str(skill.get("skill_id") or ""),
            " ".join(str(k) for k in (skill.get("keywords") or [])),
        ]
    ).lower()


def _plot_family_for_type(plot_type: str) -> str | None:
    for family, members in _PLOT_FAMILY_SKILL_HINTS.items():
        if plot_type in members:
            return family
    return None


def _skill_is_preferred(skill_id: str, plot_type: str) -> bool:
    sid = (skill_id or "").lower()
    if not sid or not plot_type:
        return False
    return any(token in sid for token in _PREFERRED_FIGURE_SKILLS.get(plot_type, ()))


def skill_plot_relevance(skill: dict[str, Any], plot_type: str) -> int:
    """硬筛：Skill 与图型的相关度（0=不应进入改图样式池）。"""
    if skill.get("skill_pool") == _SKILL_POOL_PLOT:
        return 8 if plot_type and plot_type in (skill.get("plot_types") or ()) else 0
    if not plot_type:
        return 1
    if _skill_is_preferred(str(skill.get("skill_id") or ""), plot_type):
        return 8
    if skill.get("skill_pool") == _SKILL_POOL_SOFTWARE_PARAMS:
        return 0
    blob = _skill_blob(skill)
    visual = (skill.get("visual_block") or "").lower()
    terms = _plot_terms_for_type(plot_type)
    hits = sum(1 for t in terms if t and (t in visual or t in blob))
    if hits:
        return hits
    family = _plot_family_for_type(plot_type)
    if family:
        fam_hints = _FAMILY_BLOB_HINTS.get(family, ())
        if any(h in blob or h in visual for h in fam_hints):
            return 2
    return 0


def load_sticky_literature_skills(results_dir: str | Path) -> list[str]:
    """从 Agent C manifest / 已出图 metadata 读取本会话已匹配的文献 Skill。"""
    root = Path(results_dir)
    sticky: list[str] = []
    manifest_path = root / "agent_c_output" / "agent_c_manifest.json"
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            lit = data.get("literature_style") or {}
            sticky.extend(str(s) for s in (lit.get("matched_skills") or []) if s)
            for fig in data.get("report_figures") or data.get("figures") or []:
                if not isinstance(fig, dict):
                    continue
                style = fig.get("literature_style")
                if isinstance(style, dict):
                    sticky.extend(str(s) for s in (style.get("matched") or []) if s)
        except Exception:
            pass
    # 去重保序
    return list(dict.fromkeys(sticky))


def _score_skill(
    skill: dict[str, Any],
    *,
    goal_tokens: list[str],
    plot_terms: tuple[str, ...],
    instruction: str,
    plot_type: str = "",
    sticky_skill_ids: list[str] | None = None,
) -> int:
    score = 0
    blob = _skill_blob(skill)
    visual = (skill.get("visual_block") or "").lower()
    sid = str(skill.get("skill_id") or "").lower()

    if skill.get("skill_pool") == _SKILL_POOL_PLOT and not plot_type:
        return 0
    rel = skill_plot_relevance(skill, plot_type) if plot_type else 1
    if plot_type and rel <= 0:
        return 0
    score += rel * 5
    if plot_type and (
        _skill_is_preferred(sid, plot_type) or skill.get("skill_pool") == _SKILL_POOL_PLOT
    ):
        score += 60

    sticky = {str(s).lower() for s in (sticky_skill_ids or []) if s}
    if sid and sid in sticky:
        score += 120
    for st in sticky:
        if st and (st in sid or sid in st):
            score += 80

    for t in goal_tokens:
        if t in blob:
            score += 2

    for kw in skill.get("keywords") or []:
        k = str(kw).lower()
        if len(k) >= 2 and any(k in g or g in k for g in goal_tokens):
            score += 3

    for term in plot_terms:
        if term in visual:
            score += 6
        elif term in blob:
            score += 3

    if instruction:
        inst = instruction.lower()
        for term in plot_terms:
            if term in inst and term in visual:
                score += 2
        score += _instruction_skill_bonus(instruction, skill)

    if skill.get("source") == "massomics" and skill.get("skill_pool") == _SKILL_POOL_LITERATURE:
        score += 4
        for term in plot_terms:
            if term in visual and term in sid:
                score += 8

    if (skill.get("visual_block") or "").strip():
        score += 3

    return score


def rank_skills_for_plot(
    *,
    plot_type: str = "",
    goal_text: str = "",
    instruction: str = "",
    project_root: Path | None = None,
    sticky_skill_ids: list[str] | None = None,
    max_skills: int = 3,
    include_software_params: bool = False,
) -> list[dict[str, Any]]:
    """统一检索排序：图型硬筛 + 目标词 + 会话 sticky Skill。"""
    goal_tokens = _tokenize(goal_text)
    plot_terms = _plot_terms_for_type(plot_type) if plot_type else ()
    all_skills = (
        _load_massomics_skills(project_root)
        + _load_phase2_skills(project_root)
        + _load_plot_skills(project_root)
    )
    if not all_skills:
        return []

    pool = all_skills
    if not include_software_params:
        pool = [
            sk
            for sk in pool
            if sk.get("skill_pool") != _SKILL_POOL_SOFTWARE_PARAMS
            or _skill_is_preferred(str(sk.get("skill_id") or ""), plot_type)
        ]

    scored: list[tuple[int, dict[str, Any]]] = []
    for sk in pool:
        s = _score_skill(
            sk,
            goal_tokens=goal_tokens,
            plot_terms=plot_terms,
            instruction=instruction,
            plot_type=plot_type,
            sticky_skill_ids=sticky_skill_ids,
        )
        if s > 0:
            scored.append((s, sk))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored and plot_type:
        for sk in pool:
            rel = skill_plot_relevance(sk, plot_type)
            if rel > 0:
                scored.append((rel, sk))
        scored.sort(key=lambda x: x[0], reverse=True)

    ranked = [sk for _, sk in scored]
    limit = max(1, max_skills)
    plot_skill = next((sk for sk in ranked if sk.get("skill_pool") == _SKILL_POOL_PLOT), None)
    if plot_skill is None:
        return ranked[:limit]
    # 改图规范 Skill 固定排在最后一个名额：注入 LLM 时论文 Skill 在前，预算不够时先截它。
    others = [sk for sk in ranked if sk.get("skill_pool") != _SKILL_POOL_PLOT]
    return others[: limit - 1] + [plot_skill]


def _suggest_instruction(plot_type: str, skill: dict[str, Any], visual: str) -> str:
    """从文献出图清单生成可直接发到聊天里的改图话术（口语，不填表格）。"""
    if skill.get("skill_pool") == _SKILL_POOL_PLOT and skill.get("suggest"):
        return str(skill["suggest"])
    skill_name = skill.get("skill_id") or skill.get("name") or "知识库里那篇"
    paper = str(skill_name).replace("-", " ")
    if plot_type in {"pca", "plsda"}:
        return (
            f"{'PCA' if plot_type == 'pca' else 'PLS-DA'} 按知识库里{paper}那篇改一下，"
            "分组色用期刊常用的 NPG，加上置信椭圆，样本名就别标了，图例放右边。"
        )
    if plot_type == "volcano":
        return (
            f"火山图按{paper}那种来：上调红下调蓝，灰点别那么抢，阈值线留着，别改 p 和 fold change。"
        )
    if plot_type == "vip_bar":
        return f"VIP 图按{paper}收一下，柱子用深蓝，VIP 线留着，看起来像论文附图就行。"
    if plot_type == "heatmap_vip":
        return f"热图按{paper}那种红蓝发散色标，行聚类留着，别把统计阈值改掉。"
    if plot_type == "network_topology":
        return f"网络图按{paper}来，按分子家族着色，边淡一点，孤立点可以藏掉。"
    if plot_type in {"cosine_hist", "degree_hist", "family_size"}:
        return f"这张分布图按{paper}的网络质控图来改，轴标题写清楚，阈值线留着。"
    return f"这张图按知识库里{paper}的画法收一收，配色和图例跟论文附图靠近就行，数据别动。"


def match_plot_literature(
    *,
    goal_text: str = "",
    plot_type: str = "",
    instruction: str = "",
    source_rel: str = "",
    project_root: Path | None = None,
    sticky_skill_ids: list[str] | None = None,
    max_skills: int = 2,
    max_chars: int = 4000,
) -> dict[str, Any]:
    """匹配与当前图型相关的文献作图知识。

    Returns:
        text: 注入 LLM 的 Markdown
        matched: skill_id 列表
        hints: 前端展示用 [{skill_id, doi, summary, instruction, source}]
    """
    if not env_enabled():
        return {"text": "", "matched": [], "hints": [], "error": None}

    if not plot_type and source_rel:
        stem = Path(source_rel).stem
        plot_type = plot_type_from_stem(stem) or ""

    try:
        from web_frontend.backend.plot_edit_registry import looks_like_literature_plot_restyle

        if looks_like_literature_plot_restyle(instruction):
            max_skills = max(max_skills, 3)
    except Exception:
        pass

    selected = rank_skills_for_plot(
        plot_type=plot_type,
        goal_text=goal_text,
        instruction=instruction,
        project_root=project_root,
        sticky_skill_ids=sticky_skill_ids,
        max_skills=max_skills,
    )

    parts = [
        "## Literature figure guidance (from curated skills)",
        "Apply ONLY when consistent with user instruction and current plot data.",
        "Use for: chart purpose, title wording, axis labels, color semantics, legend layout.",
        "Do NOT invent data series or thresholds not supported by the result files.",
        "",
    ]
    hints: list[dict[str, Any]] = []
    matched: list[str] = []
    budget = max_chars

    for sk in selected:
        sid = str(sk.get("skill_id") or "")
        visual = (sk.get("visual_block") or "").strip()
        if not visual:
            body = str(sk.get("body") or "")
            visual = _extract_figure_mentions(body) or str(sk.get("description") or "")[:400]
        if not visual.strip():
            continue
        doi = sk.get("doi") or ""
        if sk.get("skill_pool") == _SKILL_POOL_PLOT:
            refs = "; ".join((sk.get("references") or [])[:4])
            header = f"### Figure convention skill: `{sid}` ({sk.get('name') or sid})"
            if refs:
                header += f" DOI:{refs}"
        else:
            header = f"### Skill: `{sid}`"
            if doi:
                header += f" (DOI:{doi})"
        chunk = f"{header}\n{visual.strip()}\n\n---\n"
        if len(chunk) > budget and matched:
            break
        if len(chunk) > budget:
            chunk = chunk[: max(0, budget - 30)] + "\n…[truncated]\n---\n"
        parts.append(chunk)
        matched.append(sid)
        budget -= len(chunk)

        summary = visual.splitlines()[0][:120] if visual else sk.get("description", "")[:120]
        hints.append(
            {
                "skill_id": sid,
                "source": sk.get("source"),
                "doi": doi,
                "summary": summary.strip("| ").strip(),
                "instruction": _suggest_instruction(plot_type or "pca", sk, visual),
            }
        )

    rag_mode = ""
    rag_sources: list[str] = []
    rag_budget = min(2200, max(0, budget))
    if rag_budget > 200 and plot_type:
        rag = supplement_plot_literature_rag(
            plot_type=plot_type,
            goal_text=goal_text,
            instruction=instruction,
            project_root=project_root,
            max_chars=rag_budget,
        )
        rag_text = str(rag.get("text") or "").strip()
        rag_mode = str(rag.get("mode") or "")
        rag_sources = [str(s) for s in (rag.get("sources") or []) if s]
        if rag_text:
            rag_section = (
                "## Supplementary literature (repro_recipes / figure_index / RAG)\n"
                "Use captions and visual conventions only; do not override user instruction or actual data.\n"
                "Do not copy peak-picking or statistical thresholds into plot_config.\n\n"
                f"{rag_text}\n"
            )
            parts.append(rag_section)
            budget -= len(rag_section)
            if not hints:
                preview = next((ln.strip() for ln in rag_text.splitlines() if ln.strip()), "")[:120]
                hints.append(
                    {
                        "skill_id": "literature_rag",
                        "source": "rag",
                        "doi": "",
                        "summary": preview or "知识库 figure captions",
                        "instruction": _suggest_instruction(
                            plot_type or "pca",
                            {"skill_id": "知识库文献", "doi": ""},
                            rag_text,
                        ),
                    }
                )

    text = "\n".join(parts).strip()
    if not matched and not rag_mode:
        return {
            "text": "",
            "matched": [],
            "hints": [],
            "error": None,
            "rag_mode": "",
            "rag_sources": [],
        }
    return {
        "text": text,
        "matched": matched,
        "hints": hints,
        "error": None,
        "rag_mode": rag_mode,
        "rag_sources": rag_sources,
    }


def session_goal_text(session: dict | None, messages: list[dict] | None) -> str:
    """从会话标题与近期用户消息拼分析目标上下文。"""
    parts: list[str] = []
    if session and (session.get("title") or "").strip():
        parts.append(str(session["title"]).strip())
    for msg in messages or []:
        if str(msg.get("role") or "").lower() != "user":
            continue
        content = str(msg.get("content") or "").strip()
        if content:
            parts.append(content[:600])
    # 取最近几条，避免过长
    return "\n".join(parts[-6:])


def _is_weak_plot_goal(text: str) -> bool:
    """执行口令（确认计划等）不能当文献匹配上下文。"""
    msg = (text or "").strip()
    if not msg:
        return True
    try:
        from web_frontend.backend.workflow import is_plan_confirmation

        if is_plan_confirmation(msg):
            return True
    except Exception:
        pass
    weak = {
        "确认计划",
        "开始执行",
        "开始分析",
        "执行分析",
        "写报告",
        "按方案出图",
        "出图",
    }
    return msg in weak or msg.lower() in {"execute", "run", "report"}


def effective_plot_goal_text(
    *,
    user_message: str = "",
    plan: dict[str, Any] | None = None,
    session: dict | None = None,
    messages: list[dict] | None = None,
) -> str:
    """首次出图用的文献匹配上下文：方案目标优先，忽略「确认计划」口令。"""
    parts: list[str] = []
    if isinstance(plan, dict):
        objective = str(plan.get("objective") or "").strip()
        if objective:
            parts.append(objective)
        for fig in (plan.get("required_visualization") or [])[:6]:
            if not isinstance(fig, dict):
                continue
            for key in ("title", "theme", "purpose"):
                val = str(fig.get(key) or "").strip()
                if val:
                    parts.append(val)
    sess = session_goal_text(session, messages)
    if sess.strip():
        parts.append(sess.strip())
    msg = (user_message or "").strip()
    if msg and not _is_weak_plot_goal(msg):
        parts.append(msg)
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        key = part[:120]
        if key in seen:
            continue
        seen.add(key)
        ordered.append(part)
    return "\n".join(ordered)[:1200]


__all__ = [
    "build_plot_literature_query",
    "env_enabled",
    "load_sticky_literature_skills",
    "match_plot_literature",
    "plot_rag_enabled",
    "rank_skills_for_plot",
    "session_goal_text",
    "effective_plot_goal_text",
    "skill_plot_relevance",
    "supplement_plot_literature_rag",
    "PLOT_TYPE_TERMS",
]
