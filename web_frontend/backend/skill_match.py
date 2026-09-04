"""从 phase2_output/skill_registry.json 匹配场景 Skill，供 Web Agent 规划注入。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_backends import massomics_root


# 场景共识触发词：命中这些不足以压过「点名某篇论文」的 paper_recipe。
_GENERIC_SKILL_TRIGGERS = {
    "统计分析",
    "pca",
    "pls-da",
    "火山图",
    "vip",
    "差异代谢物",
    "mixomics",
    "volcano",
    "分子网络",
    "gnps",
    "fbmn",
    "ms2lda",
    "molecular networking",
    "motif",
    "余弦",
    "通路",
    "kegg",
    "富集",
    "pathway",
    "enrichment",
    "metaboanalyst",
    "峰检测",
    "xcms",
    "预处理",
    "peak picking",
    "alignment",
    "mzml",
    "代谢组",
    "metabolomics",
    "lc-ms",
    "完整流程",
}


def _project_root() -> Path:
    # web_frontend/backend/skill_match.py → repo root
    return Path(__file__).resolve().parents[2]


def _registry_path(project_root: Path | None = None) -> Path:
    from web_frontend.backend.literature_paths import resolve_phase2_registry

    return resolve_phase2_registry(project_root or _project_root())


def _massomics_skills_root(project_root: Path | None = None) -> Path:
    return massomics_root(project_root or _project_root()) / "skills"


def _paper_specific_hits(matched_kw: list[str]) -> bool:
    """中文专名、带空格品种名、DOI 尾号才算点名论文。"""
    for kw in matched_kw:
        t = str(kw).strip()
        tl = t.lower()
        if tl in _GENERIC_SKILL_TRIGGERS:
            continue
        if re.search(r"[\u4e00-\u9fff]", t):
            return True
        if " " in t:
            return True
        if t.isdigit() and len(t) >= 5:
            return True
        if tl in {"fochx", "maojian"}:
            return True
    return False


def _in_goal(token: str, goal_lower: str) -> bool:
    """短英文 id 用词界匹配，避免 kpic 命中 peakpicking、ms 命中 openms。"""
    t = (token or "").strip().lower()
    if len(t) < 2:
        return False
    if re.search(r"[\u4e00-\u9fff]", t) or " " in t:
        return t in goal_lower
    return re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", goal_lower) is not None


def _trigger_keywords_from_description(desc: str) -> list[str]:
    """YAML description 触发词：整句切片 +「当提到 A、B 时触发」里的短名。"""
    keywords = [k.strip() for k in re.split(r"[，,。、；;\n]+", desc) if len(k.strip()) >= 2]
    m = re.search(r"当提到(.+?)时触发", desc, re.S)
    if m:
        keywords.extend(
            k.strip()
            for k in re.split(r"[，,、/]+", m.group(1))
            if len(k.strip()) >= 2
        )
    return list(dict.fromkeys(keywords))


# 同一 software-id 多篇时，按 MCP/模块名把分数加到对应 paper-slug
_SLUG_GOAL_HINTS: dict[str, tuple[str, ...]] = {
    "tautenhahn-2008-centwave": (
        "centwave",
        "xcms-centwave",
        "snthresh",
        "peakwidth",
        "prefilter",
    ),
    "mclean-2020-autotuner": ("autotuner",),
    "naser-2019-credentialing": (
        "credential",
        "credentialing",
        "obiwarp",
        "loess",
        "xcms-obiwarp",
        "xcms-loess",
    ),
    "pluskal-2010-mzmine2": (
        "gridmass",
        "girdmass",
        "mzmine-girdmass",
        "mzmine-gridmass",
    ),
    "heuckeroth-2024-reproducible-processing": (
        "adap",
        "mzmine-adap",
        "jointaligner",
        "joint aligner",
        "mzmine-jointaligner",
    ),
    "schmid-2023-mzmine3": ("mzmine 3", "mzmine3"),
    "kenar-2014-featurefindermetabo": (
        "featurefinder",
        "featurefindermetabo",
        "openms-featurefindermetabo",
    ),
    "sturm-2008-openms": (
        "fileconverter",
        "peakpicking",
        "peak picking",
        "openms-peakpicking",
        "openms fileconverter",
    ),
    "rost-2016-openms2": (
        "isotopetools",
        "peakgroup",
        "openms-isotopetools",
        "openms-peakgroup",
        "mapaligner",
    ),
}


def _software_param_needles(software_id: str) -> tuple[str, ...]:
    """software-id 与 catalog keyword 的小写别名（goal 用词界匹配）。"""
    extra = {
        "msbert": ("ms-bert", "ms_bert"),
        "csu-ms2": ("csums2", "csu_ms2"),
        "e-sgmn": ("esgmn", "e_sgmn"),
        "ms-dial": ("msdial", "ms_dial"),
        "kpic": ("kpic2",),
        "fft": ("fft-based",),
        "dtw": ("dtw-based",),
        "bpca": ("bayesian pca", "bayesian-pca"),
        "deeplearning": ("deeplearning-based", "deep learning", "deep learning-based"),
        "spectral-entropy": ("spectral entropy", "谱熵"),
        "missforest": ("miss-forest",),
        "knn": ("k-nn",),
        "cfm-id": ("cfmid", "cfm_id"),
        "ramclust": ("ramclustr",),
        "scikit-learn": ("sklearn",),
        "cosine": ("modified cosine",),
        "mzannotation": ("xmsannotator",),
        "peakonly": ("neatms",),
        "deepmass": ("deepmass2",),
        "mixomics": ("mixomics",),
        "metax": ("metax",),
    }
    compact = software_id.replace("-", "").replace("_", "")
    needles = [software_id, compact, software_id.replace("-", " ")]
    needles.extend(extra.get(software_id, ()))
    return tuple(dict.fromkeys(n.lower() for n in needles if n))


def _load_massomics_skill_hits(goal_lower: str, project_root: Path | None = None) -> list[tuple[dict, str, list[str], int]]:
    """从 MassOmics-Agent/skills 目录关键词匹配文献流程 Skill。"""
    skills_root = _massomics_skills_root(project_root)
    if not skills_root.is_dir():
        return []
    hits: list[tuple[dict, str, list[str], int]] = []
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        try:
            content = skill_md.read_text(encoding="utf-8")
        except Exception:
            continue
        if not content.strip():
            continue
        # 从 YAML description 提取触发词
        desc = ""
        m = re.search(r"description:\s*>\s*\n(.*?)\n---", content, re.S)
        if m:
            desc = m.group(1)
        else:
            m2 = re.search(r"description:\s*(.+)$", content, re.M)
            if m2:
                desc = m2.group(1)
        keywords = _trigger_keywords_from_description(desc)
        matched_kw = [kw for kw in keywords if _in_goal(str(kw), goal_lower)]
        name = skill_md.parent.name
        blob = f"{name} {desc} {content[:400]}".lower()
        extra = [
            kw
            for kw in (
                "xcms",
                "gnps",
                "fbmn",
                "mzmine",
                "ms-dial",
                "msdial",
                "openms",
                "metaboanalyst",
                "pca",
                "volcano",
            )
            if _in_goal(kw, goal_lower) and _in_goal(kw, blob)
        ]
        try:
            rel_parts = skill_md.relative_to(skills_root).parts
        except ValueError:
            rel_parts = skill_md.parts
        # software-params/<software-id>/<paper-slug>/SKILL.md
        is_software_params = len(rel_parts) >= 4 and rel_parts[0] == "software-params"
        software_id = rel_parts[1] if is_software_params else ""
        parent_kind = rel_parts[0] if len(rel_parts) >= 2 else skill_md.parent.parent.name
        slug_boost = 0
        if is_software_params:
            needles = _software_param_needles(software_id)
            if not any(_in_goal(n, goal_lower) for n in needles):
                continue
            extra.extend(n for n in needles if _in_goal(n, goal_lower))
            if any(_in_goal(hint, goal_lower) for hint in _SLUG_GOAL_HINTS.get(name, ())):
                slug_boost = 25
        matched_kw = list(dict.fromkeys(matched_kw + extra))
        if not matched_kw:
            continue
        skill = {
            "skill_name": name,
            "functional_domain": software_id if is_software_params else parent_kind,
            "file": str(skill_md),
            "skill_type": "software_params" if is_software_params else "massomics_literature",
        }
        priority = min(len(matched_kw), 8) + 5  # 手工卡略加权
        if is_software_params:
            # 点名软件时优先注入参数卡，避免被冗长共识挤出 3 卡名额
            priority += 110 + slug_boost
        hits.append((skill, content, matched_kw, priority))
    return hits


def match_skills(
    goal_text: str,
    *,
    project_root: Path | None = None,
    max_skills: int = 3,
    max_chars: int = 12000,
    max_chars_per_skill: int = 4000,
    prefer_consensus: bool = True,
) -> dict[str, Any]:
    """关键词触发匹配 Skill。

    Returns:
        {
          "text": str,           # 可注入 prompt 的 Markdown
          "matched": list[str],  # skill_name 列表
          "error": str | None,
        }
    """
    path = _registry_path(project_root)
    goal_lower = (goal_text or "").lower()
    if not goal_lower.strip():
        return {"text": "", "matched": [], "error": None}

    hits: list[tuple[dict, str, list[str], int]] = []
    registry_error = None
    if path.is_file():
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            registry = {"skills": []}
            registry_error = str(exc)
        for skill in registry.get("skills", []) or []:
            keywords = skill.get("trigger_keywords") or []
            matched_kw = [kw for kw in keywords if _in_goal(str(kw), goal_lower)]
            if not matched_kw:
                continue
            rel = skill.get("file") or ""
            skill_file = path.parent / rel
            if not skill_file.is_file():
                continue
            try:
                content = skill_file.read_text(encoding="utf-8")
            except Exception:
                continue
            stype = skill.get("skill_type") or ""
            priority = 0
            if prefer_consensus and stype == "multi_paper_consensus":
                priority += 100
            if stype == "paper_recipe" and _paper_specific_hits(matched_kw):
                # 点名论文/品种时压过场景共识；MSConvert 等通用工具名不加分
                priority += 200
            priority += min(len(matched_kw), 8)
            priority += int(skill.get("reproducibility_score") or 0) // 20
            priority += min(int(skill.get("n_param_steps") or 0), 10)
            hits.append((skill, content, matched_kw, priority))
    else:
        registry_error = f"missing:{path}"

    hits.extend(_load_massomics_skill_hits(goal_lower, project_root))

    if not hits:
        return {"text": "", "matched": [], "error": registry_error}

    hits.sort(key=lambda x: x[3], reverse=True)
    # 按 functional_domain 去重，保证「预处理 + 统计」等组合都能注入
    selected: list[tuple[dict, str, list[str], int]] = []
    seen_domains: set[str] = set()
    for item in hits:
        domain = str(item[0].get("functional_domain") or item[0].get("skill_name") or "")
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        selected.append(item)
        if len(selected) >= max(1, max_skills):
            break

    parts = [
        "## Scenario Skills (literature-parameter evidence)",
        "The following curated skills were matched by research-scenario keywords. "
        "Prefer their tool order and explicit software parameters when mapping onto available_tools. "
        "USER instruction still wins; do not invent unregistered tools.",
        "",
    ]
    names: list[str] = []
    budget = max_chars
    for skill, content, matched_kw, _ in selected:
        name = skill.get("skill_name") or skill.get("file") or "unknown"
        domain = skill.get("functional_domain") or ""
        header = (
            f"### Skill: {domain} (`{name}`)\n"
            f"*Triggered by: {', '.join(matched_kw[:6])}*\n\n"
        )
        body = content.strip()
        if len(body) > max_chars_per_skill:
            body = body[: max_chars_per_skill - 40] + "\n...(truncated)"
        chunk = header + body + "\n\n---\n"
        if len(chunk) > budget and names:
            break
        if len(chunk) > budget:
            chunk = chunk[: max(0, budget - 40)] + "\n...(truncated)\n---\n"
        parts.append(chunk)
        names.append(name)
        budget -= len(chunk)
        if budget <= 0:
            break

    return {"text": "\n".join(parts).strip(), "matched": names, "error": registry_error if not names else None}


def env_enabled() -> bool:
    """WEB_SKILL_MATCH=0/false/off 可关闭。"""
    v = (os.environ.get("WEB_SKILL_MATCH") or "1").strip().lower()
    return v not in {"0", "false", "off", "no"}
