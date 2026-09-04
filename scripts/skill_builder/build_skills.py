#!/usr/bin/env python3
"""从 softwares_database/repro_recipes 构建 phase2_output Skill 注册表。

用法（项目根目录）:
  python scripts/skill_builder/build_skills.py
  python scripts/skill_builder/build_skills.py --min-score 85 --max-paper-skills 30
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from parse_recipes import load_recipes  # noqa: E402
from render_skills import (  # noqa: E402
    build_consensus_skill,
    infer_domain,
    infer_triggers,
    pick_scenario_groups,
    render_paper_skill,
    slugify,
)


SCENARIO_TRIGGERS = {
    "statistical_analysis": [
        "统计分析",
        "PCA",
        "PLS-DA",
        "火山图",
        "VIP",
        "差异代谢物",
        "mixOmics",
        "volcano",
    ],
    "molecular_networking": [
        "分子网络",
        "GNPS",
        "FBMN",
        "MS2LDA",
        "molecular networking",
        "motif",
        "余弦",
    ],
    "pathway_enrichment": [
        "通路",
        "KEGG",
        "富集",
        "pathway",
        "enrichment",
        "MetaboAnalyst",
    ],
    "lcms_preprocessing": [
        "峰检测",
        "XCMS",
        "预处理",
        "peak picking",
        "alignment",
        "mzML",
    ],
    "general_metabolomics": ["代谢组", "metabolomics", "LC-MS", "完整流程"],
}

# 低于 min_score 仍写入单篇 Skill（用户点名复现的论文）
PINNED_RECIPE_MARKERS = (
    "10.1016_j.fochx.2026.103843",
    "j.fochx.2026.103843",
)


def _recipe_pinned(recipe) -> bool:
    blob = f"{recipe.path} {recipe.source_paper} {recipe.paper_title}".lower()
    return any(m.lower() in blob for m in PINNED_RECIPE_MARKERS)


def build(
    *,
    recipes_dir: Path,
    out_dir: Path,
    min_score: int,
    require_params: bool,
    max_paper_skills: int,
    min_consensus_papers: int,
) -> dict:
    recipes = load_recipes(recipes_dir)
    print(f"[skill_builder] loaded recipes: {len(recipes)}")

    filtered = []
    for r in recipes:
        if r.reproducibility_score < min_score:
            continue
        if require_params and not r.param_steps:
            continue
        if not r.steps:
            continue
        filtered.append(r)
    # 高分优先，其次参数步数
    filtered.sort(
        key=lambda r: (r.reproducibility_score, len(r.param_steps), len(r.figures)),
        reverse=True,
    )
    print(
        f"[skill_builder] filtered (score>={min_score}, params={require_params}): {len(filtered)}"
    )

    # 通路场景高分样本少：额外纳入略低分但含参数的配方，仅用于共识
    pathway_extra = []
    pathway_floor = max(50, min_score - 20)
    for r in recipes:
        if r.reproducibility_score < pathway_floor:
            continue
        if require_params and not r.param_steps:
            continue
        if not r.steps:
            continue
        if infer_domain(r) != "pathway_enrichment":
            continue
        pathway_extra.append(r)
    pathway_extra.sort(
        key=lambda r: (r.reproducibility_score, len(r.param_steps)),
        reverse=True,
    )

    skills_dir = out_dir / "skills"
    paper_dir = out_dir / "paper_skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    paper_dir.mkdir(parents=True, exist_ok=True)

    registry = {"version": "1.0", "skills": [], "tool_cards": [], "built_from": str(recipes_dir)}

    # 1) 单篇高质量 Skill
    paper_pick = filtered[:max_paper_skills]
    pinned = [r for r in recipes if _recipe_pinned(r) and r.steps]
    seen_paths = {r.path for r in paper_pick}
    for r in pinned:
        if r.path not in seen_paths:
            paper_pick.append(r)
            seen_paths.add(r.path)
            print(
                f"[skill_builder] pinned paper skill: {r.paper_title[:60]} "
                f"(score={r.reproducibility_score})"
            )
    for r in paper_pick:
        domain = infer_domain(r)
        stem = slugify(
            f"{domain}_{r.paper_title or Path(r.path).stem}",
            max_len=70,
        )
        rel = f"paper_skills/{stem}.md"
        path = out_dir / rel
        path.write_text(render_paper_skill(r), encoding="utf-8")
        registry["skills"].append(
            {
                "skill_name": stem,
                "skill_type": "paper_recipe",
                "functional_domain": domain,
                "file": rel,
                "trigger_keywords": infer_triggers(r),
                "reproducibility_score": r.reproducibility_score,
                "source_paper": r.source_paper,
                "n_param_steps": len(r.param_steps),
                "n_figures": len(r.figures),
            }
        )

    # 2) 场景共识 Skill
    groups = pick_scenario_groups(filtered)
    if pathway_extra:
        groups["pathway_enrichment"] = pathway_extra
    for domain, group in groups.items():
        need = min_consensus_papers
        # 通路类文献偏少，降低门槛以便产出共识卡
        if domain == "pathway_enrichment":
            need = min(3, min_consensus_papers)
        if len(group) < need:
            continue
        # 每个场景取 top N 参与共识
        top = sorted(
            group,
            key=lambda r: (r.reproducibility_score, len(r.param_steps)),
            reverse=True,
        )[:40]
        name = f"consensus_{domain}"
        rel = f"skills/{name}.md"
        triggers = SCENARIO_TRIGGERS.get(domain, [domain])
        (out_dir / rel).write_text(
            build_consensus_skill(
                name=name.replace("_", " "),
                domain=domain,
                recipes=top,
                trigger_keywords=triggers,
            ),
            encoding="utf-8",
        )
        registry["skills"].append(
            {
                "skill_name": name,
                "skill_type": "multi_paper_consensus",
                "functional_domain": domain,
                "file": rel,
                "trigger_keywords": triggers,
                "n_papers": len(top),
            }
        )

    registry_path = out_dir / "skill_registry.json"
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[skill_builder] wrote {len(registry['skills'])} skills → {registry_path}")
    return registry


def main() -> None:
    ap = argparse.ArgumentParser(description="Build MOA skills from repro_recipes")
    ap.add_argument(
        "--recipes-dir",
        type=Path,
        default=ROOT / "softwares_database" / "repro_recipes",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "phase2_output",
    )
    ap.add_argument("--min-score", type=int, default=80)
    ap.add_argument("--require-params", action="store_true", default=True)
    ap.add_argument("--no-require-params", action="store_false", dest="require_params")
    ap.add_argument("--max-paper-skills", type=int, default=25)
    ap.add_argument("--min-consensus-papers", type=int, default=5)
    args = ap.parse_args()

    if not args.recipes_dir.is_dir():
        raise SystemExit(f"recipes dir not found: {args.recipes_dir}")
    build(
        recipes_dir=args.recipes_dir,
        out_dir=args.out_dir,
        min_score=args.min_score,
        require_params=args.require_params,
        max_paper_skills=args.max_paper_skills,
        min_consensus_papers=args.min_consensus_papers,
    )


if __name__ == "__main__":
    main()
