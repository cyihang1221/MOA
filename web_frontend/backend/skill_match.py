"""从 phase2_output/skill_registry.json 匹配场景 Skill，供 Web Agent 规划注入。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    # web_frontend/backend/skill_match.py → repo root
    return Path(__file__).resolve().parents[2]


def _registry_path(project_root: Path | None = None) -> Path:
    root = project_root or _project_root()
    return root / "phase2_output" / "skill_registry.json"


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
    if not path.is_file():
        return {"text": "", "matched": [], "error": f"missing:{path}"}

    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"text": "", "matched": [], "error": str(exc)}

    goal_lower = (goal_text or "").lower()
    if not goal_lower.strip():
        return {"text": "", "matched": [], "error": None}

    hits: list[tuple[dict, str, list[str], int]] = []
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
        # 优先级：共识 > 参数步数/分数 > 命中词数
        stype = skill.get("skill_type") or ""
        priority = 0
        if prefer_consensus and stype == "multi_paper_consensus":
            priority += 100
        priority += min(len(matched_kw), 8)
        priority += int(skill.get("reproducibility_score") or 0) // 20
        priority += min(int(skill.get("n_param_steps") or 0), 10)
        hits.append((skill, content, matched_kw, priority))

    if not hits:
        return {"text": "", "matched": [], "error": None}

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

    return {"text": "\n".join(parts).strip(), "matched": names, "error": None}


def env_enabled() -> bool:
    """WEB_SKILL_MATCH=0/false/off 可关闭。"""
    v = (os.environ.get("WEB_SKILL_MATCH") or "1").strip().lower()
    return v not in {"0", "false", "off", "no"}
