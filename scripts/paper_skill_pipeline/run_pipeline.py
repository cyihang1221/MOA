#!/usr/bin/env python3
"""新文献抓取 → 参数级 reproducibility_recipe →（可选）重建 Skill。

示例：
  # 按 DOI（需 PMC 全文）
  python scripts/paper_skill_pipeline/run_pipeline.py --doi 10.1038/s41592-025-02813-0

  # 按 PMID
  python scripts/paper_skill_pipeline/run_pipeline.py --pmid 38294426

  # 按检索式抓新文
  python scripts/paper_skill_pipeline/run_pipeline.py \\
      --query "XCMS AND metabolomics" --max-papers 3 --mindate 2024 --build-skills

  # 本地 Methods 文本
  python scripts/paper_skill_pipeline/run_pipeline.py \\
      --methods-file /path/to/methods.txt --title "My paper" --doi 10.xxxx/yyyy
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from dotenv import find_dotenv, load_dotenv

from extract_recipe import extract_recipe_from_methods
from fetch_papers import (
    PaperRecord,
    hydrate_record,
    load_methods_file,
    search_pubmed,
)
from recipe_format import doi_to_stem, recipe_has_explicit_params, render_recipe


def _write_recipe(
    data: dict,
    *,
    recipes_dir: Path,
    doi: str,
    pmid: str,
    json_dir: Path | None,
    overwrite: bool,
) -> Path | None:
    recipes_dir.mkdir(parents=True, exist_ok=True)
    stem = doi_to_stem(doi) if doi else (f"PMID_{pmid}" if pmid else "unknown")
    out_path = recipes_dir / f"recipe_{stem}.txt"
    if out_path.exists() and not overwrite:
        print(f"[skip] exists (use --overwrite): {out_path.name}")
        return None
    out_path.write_text(render_recipe(data), encoding="utf-8")
    if json_dir is not None:
        json_dir.mkdir(parents=True, exist_ok=True)
        (json_dir / f"recipe_{stem}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return out_path


def _process_record(
    rec: PaperRecord,
    *,
    cache_dir: Path,
    recipes_dir: Path,
    json_dir: Path,
    skip_llm: bool,
    overwrite: bool,
) -> Path | None:
    if not rec.methods_text:
        rec = hydrate_record(rec, cache_dir)
    if not rec.methods_text:
        print(f"[skip] no methods: pmid={rec.pmid} doi={rec.doi} errors={rec.errors}")
        return None

    print(f"[methods] {rec.title[:80]} ({len(rec.methods_text)} chars)")
    if skip_llm:
        print("[dry-run] skip LLM extract")
        return None

    data = extract_recipe_from_methods(
        rec.methods_text,
        paper_title=rec.title,
        source_paper=rec.source_paper_line(),
    )
    path = _write_recipe(
        data,
        recipes_dir=recipes_dir,
        doi=rec.doi,
        pmid=rec.pmid,
        json_dir=json_dir,
        overwrite=overwrite,
    )
    if path is None:
        return None
    score = data.get("overall_reproducibility_score")
    n_steps = len(data.get("workflow_steps") or [])
    has_p = recipe_has_explicit_params(data)
    print(
        f"[recipe] {path.name} score={score} steps={n_steps} "
        f"explicit_params={has_p}"
    )
    return path


def main() -> None:
    load_dotenv(find_dotenv(str(ROOT / ".env")), override=False)
    load_dotenv(find_dotenv(), override=False)

    ap = argparse.ArgumentParser(description="Fetch papers → parameter-level recipes → skills")
    ap.add_argument("--doi", default="", help="DOI of a paper")
    ap.add_argument("--pmid", default="", help="PubMed ID")
    ap.add_argument("--query", default="", help="PubMed query for new papers")
    ap.add_argument("--methods-file", type=Path, help="Local Methods plain text")
    ap.add_argument("--title", default="", help="Title override (with --methods-file)")
    ap.add_argument("--max-papers", type=int, default=3)
    ap.add_argument("--mindate", default=None, help="PubMed mindate, e.g. 2024")
    ap.add_argument("--maxdate", default=None)
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
    ap.add_argument("--build-skills", action="store_true", help="Run skill_builder after")
    ap.add_argument("--min-score", type=int, default=80)
    ap.add_argument("--skip-llm", action="store_true", help="Only fetch Methods")
    ap.add_argument("--no-require-pmc", action="store_true")
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing recipe_*.txt with the same DOI/PMID stem",
    )
    args = ap.parse_args()

    modes = sum(
        bool(x)
        for x in (args.doi, args.pmid, args.query, args.methods_file)
    )
    # methods-file 可同时带 doi/pmid 作元数据；其余入口互斥
    if args.methods_file:
        pass
    elif modes != 1:
        raise SystemExit("请指定其一：--doi / --pmid / --query / --methods-file")

    written: list[Path] = []

    if args.methods_file:
        rec = load_methods_file(
            args.methods_file,
            title=args.title,
            doi=args.doi or "",
            pmid=args.pmid or "",
        )
        p = _process_record(
            rec,
            cache_dir=args.cache_dir,
            recipes_dir=args.recipes_dir,
            json_dir=args.json_dir,
            skip_llm=args.skip_llm,
            overwrite=args.overwrite,
        )
        if p:
            written.append(p)
    elif args.query:
        print(f"[search] {args.query!r} max={args.max_papers}")
        records = search_pubmed(
            args.query,
            max_results=args.max_papers,
            mindate=args.mindate,
            maxdate=args.maxdate,
            require_pmc=not args.no_require_pmc,
        )
        print(f"[search] hit {len(records)} papers with usable PMC filter")
        for rec in records:
            p = _process_record(
                rec,
                cache_dir=args.cache_dir,
                recipes_dir=args.recipes_dir,
                json_dir=args.json_dir,
                skip_llm=args.skip_llm,
                overwrite=args.overwrite,
            )
            if p:
                written.append(p)
    else:
        rec = PaperRecord(doi=args.doi or "", pmid=args.pmid or "")
        p = _process_record(
            rec,
            cache_dir=args.cache_dir,
            recipes_dir=args.recipes_dir,
            json_dir=args.json_dir,
            skip_llm=args.skip_llm,
            overwrite=args.overwrite,
        )
        if p:
            written.append(p)

    print(f"[done] recipes written: {len(written)}")
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


if __name__ == "__main__":
    main()
