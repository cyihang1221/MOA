"""从 phase2_output/skill_registry.json 匹配场景 Skill，供 Web Agent 规划注入。"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    # web_frontend/backend/skill_match.py → repo root
    return Path(__file__).resolve().parents[2]


def _registry_path(project_root: Path | None = None) -> Path:
    root = project_root or _project_root()
    return root / "phase2_output" / "skill_registry.json"


def _massomics_skills_root(project_root: Path | None = None) -> Path:
    root = project_root or _project_root()
    return root / "MassOmics-Agent" / "MassOmics-Agent" / "skills"


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
        keywords = [k.strip() for k in re.split(r"[，,。、；;\n]+", desc) if len(k.strip()) >= 2]
        matched_kw = [kw for kw in keywords if str(kw).lower() in goal_lower]
        name = skill_md.parent.name
        blob = f"{name} {desc} {content[:400]}".lower()
        extra = [kw for kw in ("xcms", "gnps", "fbmn", "mzmine", "metaboanalyst", "pca", "volcano")
                 if kw in goal_lower and kw in blob]
        matched_kw = list(dict.fromkeys(matched_kw + extra))
        if not matched_kw:
            continue
        skill = {
            "skill_name": name,
            "functional_domain": skill_md.parent.parent.name,
            "file": str(skill_md),
            "skill_type": "massomics_literature",
        }
        priority = min(len(matched_kw), 8) + 5  # 手工文献卡略加权
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
            matched_kw = [kw for kw in keywords if str(kw).lower() in goal_lower]
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
