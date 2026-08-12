"""从文献 Skill（MassOmics skills + phase2_output）提取作图知识，供前端改图 Agent 注入。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from web_frontend.backend.plot_edit_registry import plot_type_from_stem

# plot_type → 在出图清单/正文中检索用的关键词
PLOT_TYPE_TERMS: dict[str, tuple[str, ...]] = {
    "pca": ("pca", "score", "得分", "主成分", "3d pca", "pca score"),
    "plsda": ("pls-da", "plsda", "opls", "opls-da", "偏最小", "s-plot"),
    "volcano": ("volcano", "火山", "volcano plot"),
    "vip_bar": ("vip", "vip bar", "vip 排名", "vip score"),
    "heatmap_vip": ("heatmap", "热图", "heat map"),
    "family_size": ("family size", "分子家族", "家族大小", "molecular family"),
    "degree_hist": ("degree", "度数", "node degree"),
    "cosine_hist": ("cosine", "余弦", "similarity"),
    "network_topology": ("network", "网络", "topology", "拓扑", "cytoscape"),
    "precursor_mass_diff": ("precursor", "mass difference", "质量差"),
    "motif_match": ("motif", "碎片", "fragment"),
    "kegg_bubble": ("kegg", "enrichment", "富集", "pathway", "bubble"),
}

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


def _massomics_skills_root(project_root: Path | None = None) -> Path:
    root = project_root or _project_root()
    return root / "MassOmics-Agent" / "MassOmics-Agent" / "skills"


def _phase2_registry_path(project_root: Path | None = None) -> Path:
    root = project_root or _project_root()
    return root / "phase2_output" / "skill_registry.json"


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
        dm = re.search(r"description:\s*>\s*\n(.*?)(?:\n[a-z_]+:|\n---)", block, re.S)
        if dm:
            desc = dm.group(1).strip()
        else:
            dm2 = re.search(r"description:\s*(.+)$", block, re.M)
            if dm2:
                desc = dm2.group(1).strip()
    keywords = [k.strip() for k in re.split(r"[，,。、；;\n]+", desc) if len(k.strip()) >= 2]
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


def _load_massomics_skills(project_root: Path | None = None) -> list[dict[str, Any]]:
    root = _massomics_skills_root(project_root)
    if not root.is_dir():
        return []
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
        skills.append(
            {
                "source": "massomics",
                "skill_id": skill_md.parent.name,
                "name": name,
                "description": desc,
                "keywords": keywords,
                "file": str(skill_md),
                "branch": branch,
                "doi": _extract_doi(text),
                "visual_block": _extract_visual_block(text),
                "body": text,
            }
        )
    return skills


def _load_phase2_skills(project_root: Path | None = None) -> list[dict[str, Any]]:
    reg_path = _phase2_registry_path(project_root)
    if not reg_path.is_file():
        return []
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


def _score_skill(
    skill: dict[str, Any],
    *,
    goal_tokens: list[str],
    plot_terms: tuple[str, ...],
    instruction: str,
) -> int:
    score = 0
    blob = " ".join(
        [
            skill.get("name", ""),
            skill.get("description", ""),
            skill.get("branch", ""),
            skill.get("visual_block", ""),
            " ".join(skill.get("keywords") or []),
        ]
    ).lower()

    for t in goal_tokens:
        if t in blob:
            score += 2

    for kw in skill.get("keywords") or []:
        k = str(kw).lower()
        if len(k) >= 2 and any(k in g or g in k for g in goal_tokens):
            score += 3

    visual = (skill.get("visual_block") or "").lower()
    for term in plot_terms:
        if term in visual or term in blob:
            score += 4

    if instruction:
        inst = instruction.lower()
        for term in plot_terms:
            if term in inst and term in visual:
                score += 2

    if skill.get("source") == "massomics":
        score += 8
        sid = str(skill.get("skill_id") or "").lower()
        for term in plot_terms:
            if term in visual and term in sid:
                score += 6
        for t in goal_tokens:
            if t in sid:
                score += 4

    return score


def _plot_terms_for_type(plot_type: str) -> tuple[str, ...]:
    return PLOT_TYPE_TERMS.get(plot_type, (plot_type.replace("_", " "),))


def _suggest_instruction(plot_type: str, skill: dict[str, Any], visual: str) -> str:
    """从文献出图清单生成可一键填入的改图建议。"""
    plot_label = {
        "pca": "PCA 得分图",
        "plsda": "PLS-DA 得分图",
        "volcano": "火山图",
        "vip_bar": "VIP 条形图",
        "heatmap_vip": "VIP 热图",
        "cosine_hist": "余弦相似度分布图",
        "degree_hist": "节点度数分布图",
        "family_size": "分子家族大小分布图",
        "network_topology": "分子网络拓扑图",
    }.get(plot_type, plot_type)

    doi = skill.get("doi") or ""
    skill_name = skill.get("skill_id") or skill.get("name") or "文献"
    cite = f"（参考 {skill_name}" + (f", DOI:{doi}" if doi else "") + "）"

    # 从 visual 表格抽第一行相关描述
    purpose = ""
    for ln in visual.splitlines():
        low = ln.lower()
        if any(t in low for t in _plot_terms_for_type(plot_type)):
            purpose = re.sub(r"^\|?\s*[-|]+\s*$", "", ln).strip("| ").strip()
            if purpose and not purpose.startswith("---"):
                break

    base = f"按文献规范优化{plot_label}{cite}："
    if plot_type in {"pca", "plsda"}:
        hint = "标题使用 Score Plot；按 Group 着色；图例放右侧；标题字号 18；展示样本聚类与离群点"
        if "3d" in visual.lower() or "3d pca" in visual.lower():
            hint += "；若支持则强调 PC1/PC2 解释方差"
    elif plot_type == "volcano":
        hint = "显著上调 #E64B35、下调 #4DBBD5、非显著 #B0B0B0；标注 p 与 log2FC 阈值线；标题 Volcano Plot"
    elif plot_type in {"cosine_hist", "degree_hist", "family_size"}:
        hint = "采用 GNPS/FBMN 文献常用展示：清晰轴标题、阈值参考线、标题说明网络质量评估目的"
    elif plot_type == "network_topology":
        hint = "按分子家族或化学类别着色；边灰色 #aaaaaa；标题说明节点=feature、边=MS2 相似性"
    elif plot_type == "vip_bar":
        hint = "突出 VIP>1 特征；柱状主色 #3C5488；标题 VIP Scores"
    elif plot_type == "heatmap_vip":
        hint = "行聚类展示 top VIP 特征；色标对比度适中；标题 Top VIP Heatmap"
    else:
        hint = "标题与轴标签符合代谢组学论文惯例；配色对比清晰、图例完整"

    if purpose:
        hint = f"{purpose}。{hint}"
    return base + hint


def match_plot_literature(
    *,
    goal_text: str = "",
    plot_type: str = "",
    instruction: str = "",
    source_rel: str = "",
    project_root: Path | None = None,
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

    goal_tokens = _tokenize(goal_text)
    plot_terms = _plot_terms_for_type(plot_type) if plot_type else ()

    all_skills = _load_massomics_skills(project_root) + _load_phase2_skills(project_root)
    if not all_skills:
        return {"text": "", "matched": [], "hints": [], "error": "no_skills_loaded"}

    scored: list[tuple[int, dict[str, Any]]] = []
    for sk in all_skills:
        s = _score_skill(sk, goal_tokens=goal_tokens, plot_terms=plot_terms, instruction=instruction)
        if s > 0:
            scored.append((s, sk))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored and plot_type:
        # 仅按图型关键词兜底
        for sk in all_skills:
            visual = (sk.get("visual_block") or "").lower()
            if any(t in visual for t in plot_terms):
                scored.append((1, sk))
        scored.sort(key=lambda x: x[0], reverse=True)

    selected = [sk for _, sk in scored[: max(1, max_skills)]]
    if not selected:
        return {"text": "", "matched": [], "hints": [], "error": None}

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
        visual = sk.get("visual_block") or ""
        if not visual.strip():
            continue
        doi = sk.get("doi") or ""
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

    text = "\n".join(parts).strip() if matched else ""
    return {"text": text, "matched": matched, "hints": hints, "error": None}


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


__all__ = [
    "env_enabled",
    "match_plot_literature",
    "session_goal_text",
    "PLOT_TYPE_TERMS",
]
