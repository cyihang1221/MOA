#!/usr/bin/env python3
"""网站检索 → 筛选 → 抽取参数级 recipe → 构建 Skill。

合法开放接口（不做 Sci-Hub / 付费站破解）：
  - PubMed / PMC（NCBI E-utilities）
  - Europe PMC
  - OpenAlex（开放科学文献图谱；对应「SCI/科学文献」元数据检索）

示例：
  # 默认代谢组查询，多源检索，筛 top5，抽 recipe 并建 Skill
  python scripts/paper_skill_pipeline/crawl_filter_build.py --build-skills

  # 自定义检索
  python scripts/paper_skill_pipeline/crawl_filter_build.py \\
      --query "XCMS peak picking metabolomics" \\
      --sources pubmed,europe_pmc,openalex \\
      --max-per-source 10 --top-k 5 --mindate 2022 --build-skills

  # 只检索+筛选，不调用 LLM
  python scripts/paper_skill_pipeline/crawl_filter_build.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from dotenv import find_dotenv, load_dotenv

from extract_recipe import extract_recipe_from_methods
from fetch_papers import hydrate_record
from filter_literature import (
    filter_candidates,
    records_to_dicts,
    score_methods_richness,
)
from recipe_format import doi_to_stem, recipe_has_explicit_params, render_recipe
from search_sources import DEFAULT_METABOLOMICS_QUERIES, multi_source_search


def _write_recipe(data: dict, *, recipes_dir: Path, doi: str, pmid: str, json_dir: Path, overwrite: bool) -> Path | None:
    recipes_dir.mkdir(parents=True, exist_ok=True)
    stem = doi_to_stem(doi) if doi else (f"PMID_{pmid}" if pmid else "unknown")
    out_path = recipes_dir / f"recipe_{stem}.txt"
    if out_path.exists() and not overwrite:
        print(f"  [skip] recipe exists: {out_path.name}")
        return None
    out_path.write_text(render_recipe(data), encoding="utf-8")
    json_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / f"recipe_{stem}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path


def main() -> None:
    load_dotenv(find_dotenv(str(ROOT / ".env")), override=False)
    load_dotenv(find_dotenv(), override=False)

    ap = argparse.ArgumentParser(
        description="Crawl PubMed/EuropePMC/OpenAlex → filter → recipe → skills"
    )
    ap.add_argument(
        "--query",
        action="append",
        default=None,
        help="检索式（可重复）；默认使用内置代谢组工具查询集",
    )
    ap.add_argument(
        "--sources",
        default="pubmed,europe_pmc,openalex",
        help="逗号分隔：pubmed,europe_pmc,openalex（openalex 可用别名 sci）",
    )
    ap.add_argument("--max-per-source", type=int, default=12)
    ap.add_argument("--top-k", type=int, default=5, help="筛选后最多处理多少篇")
    ap.add_argument("--min-meta-score", type=float, default=35.0)
    ap.add_argument("--min-methods-score", type=float, default=20.0)
    ap.add_argument("--mindate", default="2020")
    ap.add_argument("--no-require-pmc", action="store_true")
    ap.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "softwares_database" / "paper_fetch_cache",
    )
    ap.add_argument(
        "--recipes-dir",
        type=Path,
        default=ROOT / "softwares_database" / "repro_recipes",
    )
    ap.add_argument(
        "--json-dir",
        type=Path,
        default=ROOT / "softwares_database" / "paper_fetch_cache" / "recipes_json",
    )
    ap.add_argument(
        "--report-dir",
        type=Path,
        default=ROOT / "softwares_database" / "paper_fetch_cache" / "crawl_reports",
    )
    ap.add_argument("--build-skills", action="store_true")
    ap.add_argument("--min-score", type=int, default=80, help="skill_builder 最低 recipe 分")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只检索筛选，不下载/不 LLM")
    ap.add_argument("--skip-llm", action="store_true", help="下载 Methods 并打分，不抽 recipe")
    args = ap.parse_args()

    queries = args.query or DEFAULT_METABOLOMICS_QUERIES
    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    # 别名
    sources = ["openalex" if s == "sci" else s for s in sources]

    all_hits = []
    for q in queries:
        all_hits.extend(
            multi_source_search(
                q,
                sources=sources,
                max_per_source=args.max_per_source,
                mindate=args.mindate,
                require_fulltext=not args.no_require_pmc,
            )
        )

    # 二次去重
    from search_sources import merge_records

    merged = merge_records(all_hits)
    print(f"[merge] after all queries: {len(merged)}")

    selected = filter_candidates(
        merged,
        min_meta_score=args.min_meta_score,
        top_k=args.top_k,
        require_pmc=not args.no_require_pmc,
    )
    print(f"[filter] selected {len(selected)} / {len(merged)} (min_meta={args.min_meta_score})")
    for i, rec in enumerate(selected, 1):
        print(
            f"  {i}. [{rec.filter_score:.0f}] {rec.year} | {rec.source} | "
            f"{(rec.title or '')[:70]} | pmc={rec.pmc or '-'} doi={rec.doi or '-'}"
        )
        print(f"     reasons: {', '.join(rec.filter_reasons[:8])}")

    args.report_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.report_dir / "last_crawl_selection.json"
    report_path.write_text(
        json.dumps(
            {
                "queries": queries,
                "sources": sources,
                "n_merged": len(merged),
                "n_selected": len(selected),
                "selected": records_to_dicts(selected),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[report] {report_path}")

    if args.dry_run:
        print("[dry-run] stop before Methods download / LLM")
        return

    written: list[Path] = []
    rejected_methods = []

    for rec in selected:
        print(f"\n[hydrate] {rec.title[:80]}")
        rec = hydrate_record(rec, args.cache_dir)
        if not rec.methods_text:
            print(f"  [skip] no methods: {rec.errors}")
            rejected_methods.append({"title": rec.title, "errors": rec.errors})
            continue

        m_score, m_reasons = score_methods_richness(rec.methods_text)
        rec.filter_score += m_score
        rec.filter_reasons.extend(m_reasons)
        print(
            f"  methods={len(rec.methods_text)} chars, methods_score={m_score:.0f}, "
            f"total={rec.filter_score:.0f}"
        )
        if m_score < args.min_methods_score:
            print(f"  [skip] methods not parameter-rich enough (<{args.min_methods_score})")
            rejected_methods.append(
                {
                    "title": rec.title,
                    "methods_score": m_score,
                    "reasons": m_reasons,
                }
            )
            continue

        if args.skip_llm:
            print("  [skip-llm] keep methods only")
            continue

        try:
            data = extract_recipe_from_methods(
                rec.methods_text,
                paper_title=rec.title,
                source_paper=rec.source_paper_line(),
            )
        except Exception as exc:
            print(f"  [error] LLM extract failed: {exc}")
            continue

        path = _write_recipe(
            data,
            recipes_dir=args.recipes_dir,
            doi=rec.doi,
            pmid=rec.pmid,
            json_dir=args.json_dir,
            overwrite=args.overwrite,
        )
        if not path:
            continue
        print(
            f"  [recipe] {path.name} score={data.get('overall_reproducibility_score')} "
            f"params={recipe_has_explicit_params(data)}"
        )
        written.append(path)

    (args.report_dir / "last_crawl_rejected.json").write_text(
        json.dumps(rejected_methods, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[done] recipes written: {len(written)}")
    for p in written:
        print(f"  - {p}")

    if args.build_skills and written:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "skill_builder" / "build_skills.py"),
            "--recipes-dir",
            str(args.recipes_dir),
            "--min-score",
            str(args.min_score),
        ]
        print("[skills]", " ".join(cmd))
        subprocess.check_call(cmd, cwd=str(ROOT))
    elif args.build_skills and not written:
        print("[skills] skipped: no new recipes")


if __name__ == "__main__":
    main()
