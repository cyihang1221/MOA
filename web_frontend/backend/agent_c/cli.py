"""Agent C 命令行：手动跑 ``run_agent_c``，便于本地调试与回归。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_c.plan_parser import parse_plan
from web_frontend.backend.agent_c.results_inventory import find_metadata_csv, inventory_results
from web_frontend.backend.agent_c.runner import run_agent_c
from web_frontend.backend.agent_c.session_chat import find_session_plan
from web_frontend.backend.session_storage import (
    inputspace_root,
    outputspace_root,
    session_upload_dir,
    session_work_dir,
)


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_path(raw: str | Path, *, project_root: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (project_root / path).resolve()
    else:
        path = path.resolve()
    return path


def resolve_session_slug(project_root: Path, hint: str) -> str:
    """用 storage_slug、短 session id（如 ``0de4a588``）或目录名片段定位会话。"""
    text = (hint or "").strip()
    if not text:
        raise ValueError("session hint 不能为空")

    for root_fn in (outputspace_root, inputspace_root):
        direct = root_fn(project_root) / text
        if direct.is_dir():
            return text

    matches: list[str] = []
    seen: set[str] = set()
    for root_fn in (outputspace_root, inputspace_root):
        root = root_fn(project_root)
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if name in seen:
                continue
            if name == text or name.endswith(f"_{text}") or text in name:
                matches.append(name)
                seen.add(name)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preview = "\n  - ".join(matches[:8])
        extra = f"\n  …共 {len(matches)} 个" if len(matches) > 8 else ""
        raise ValueError(f"session 提示词 {text!r} 匹配到多个目录，请改用完整 slug：\n  - {preview}{extra}")
    raise FileNotFoundError(
        f"未在 inputspace/outputspace 找到 session {text!r}；"
        f"请改用 --results-dir 传入完整路径。"
    )


def resolve_plan_path(
    *,
    plan_hint: str | None,
    results_dir: Path,
    upload_root: Path,
    project_root: Path,
) -> Path:
    if plan_hint:
        raw = Path(plan_hint).expanduser()
        candidates: list[Path] = []
        if raw.is_absolute():
            candidates.append(raw.resolve())
        else:
            for base in (results_dir, upload_root, project_root):
                candidates.append((base / raw).resolve())
        for cand in candidates:
            if cand.is_file():
                return cand
        raise FileNotFoundError(f"未找到方案文件: {plan_hint}")

    found = find_session_plan(results_dir, upload_root)
    if found is None:
        raise FileNotFoundError(
            "未找到 analysis_plan.* 或 plan_*.*；请用 --plan 指定，例如 plan_20260826_102858.md"
        )
    if isinstance(found, Path):
        return found
    raise TypeError("find_session_plan 应返回 Path")


def resolve_metadata_path(
    *,
    metadata_hint: str | None,
    results_dir: Path,
    upload_root: Path,
    project_root: Path,
) -> Path | None:
    if metadata_hint:
        path = resolve_path(metadata_hint, project_root=project_root)
        if not path.is_file():
            raise FileNotFoundError(f"未找到 metadata: {path}")
        return path

    try:
        from web_frontend.backend.session_metadata import resolve_metadata_csv

        return Path(resolve_metadata_csv(upload_root))
    except Exception:
        pass

    found = find_metadata_csv(results_dir, upload_root / "metadata.csv")
    return Path(found) if found else None


def resolve_agent_c_paths(
    *,
    project_root: Path | None = None,
    session: str | None = None,
    results_dir: str | Path | None = None,
    plan: str | Path | None = None,
    metadata_csv: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Path | None]:
    """解析 CLI / 脚本调用所需的目录与文件路径。"""
    root = (project_root or default_project_root()).resolve()

    if results_dir:
        out_root = resolve_path(results_dir, project_root=root)
    elif session:
        slug = resolve_session_slug(root, session)
        out_root = session_work_dir(root, slug)
    else:
        raise ValueError("必须提供 --session 或 --results-dir")

    if not out_root.is_dir():
        raise FileNotFoundError(f"results_dir 不存在: {out_root}")

    slug = out_root.name
    upload_root = session_upload_dir(root, slug)
    plan_path = resolve_plan_path(
        plan_hint=str(plan) if plan else None,
        results_dir=out_root,
        upload_root=upload_root,
        project_root=root,
    )
    meta_path = resolve_metadata_path(
        metadata_hint=str(metadata_csv) if metadata_csv else None,
        results_dir=out_root,
        upload_root=upload_root,
        project_root=root,
    )
    if output_dir:
        agent_out = resolve_path(output_dir, project_root=root)
    else:
        agent_out = out_root / "agent_c_output"

    return {
        "project_root": root,
        "storage_slug": Path(slug),
        "results_dir": out_root,
        "upload_root": upload_root,
        "plan": plan_path,
        "metadata_csv": meta_path,
        "output_dir": agent_out,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m web_frontend.backend.agent_c",
        description="手动运行 Agent C：按方案出图并写 final_report.md",
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default="",
        help="仓库根目录（默认自动推断）",
    )
    loc = parser.add_argument_group("路径（二选一）")
    loc.add_argument(
        "--session",
        type=str,
        default="",
        help="会话 storage_slug 或短 id（如 0de4a588），在 outputspace 下定位目录",
    )
    loc.add_argument(
        "--results-dir",
        type=str,
        default="",
        help="B 的结果目录（outputspace 会话根）；可相对 project-root",
    )
    loc.add_argument(
        "--plan",
        type=str,
        default="",
        help="方案路径；默认自动找 analysis_plan.* 或最新 plan_*.*",
    )
    loc.add_argument(
        "--metadata-csv",
        type=str,
        default="",
        help="metadata.csv；默认从 inputspace 同会话目录查找",
    )
    loc.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="C 产出目录；默认 <results-dir>/agent_c_output",
    )
    run = parser.add_argument_group("运行选项")
    run.add_argument(
        "--figure-mode",
        choices=("plan", "available", "plan_then_available"),
        default="plan",
        help="出图范围（默认 plan：仅方案图）",
    )
    run.add_argument(
        "--language",
        choices=("zh", "en"),
        default="zh",
    )
    run.add_argument(
        "--use-llm",
        action="store_true",
        help="启用 AI 深度解读（较慢，需 LLM 配置）",
    )
    run.add_argument(
        "--no-literature",
        action="store_true",
        help="关闭文献作图样式",
    )
    run.add_argument(
        "--goal-text",
        type=str,
        default="",
        help="分析目标上下文（文献匹配）；空则用方案 objective",
    )
    run.add_argument(
        "--repro-recipe-id",
        type=str,
        default="",
        help="论文复现配方 ID（指定时可不传 --plan）",
    )
    run.add_argument(
        "--inventory-only",
        action="store_true",
        help="只清点 B 侧可出图数据，不运行 C",
    )
    run.add_argument(
        "--parse-plan-only",
        action="store_true",
        help="只解析方案 JSON 到 stdout，不运行 C",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="打印将使用的路径与 inventory 摘要，不运行 C",
    )
    run.add_argument(
        "--json",
        action="store_true",
        help="manifest / inventory 以 JSON 打印（默认人类可读摘要）",
    )
    return parser


def _print_summary(paths: dict[str, Path | None], inv: dict[str, Any] | None = None) -> None:
    print("Agent C 路径")
    print(f"  project_root : {paths['project_root']}")
    print(f"  storage_slug : {paths['storage_slug']}")
    print(f"  results_dir  : {paths['results_dir']}")
    print(f"  upload_root  : {paths['upload_root']}")
    print(f"  plan         : {paths['plan']}")
    print(f"  metadata_csv : {paths['metadata_csv'] or '(未找到)'}")
    print(f"  output_dir   : {paths['output_dir']}")
    if inv is not None:
        plottable = inv.get("plottable") or []
        print(f"  plottable    : {len(plottable)} 种图型")
        for item in plottable[:12]:
            print(f"    - {item.get('plot_type')}: {item.get('primary_file') or item.get('files')}")
        warns = inv.get("warnings") or []
        if warns:
            print(f"  warnings     : {len(warns)}")
            for w in warns[:5]:
                print(f"    ! {w}")


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = Path(args.project_root).expanduser().resolve() if args.project_root else default_project_root()

    if not args.repro_recipe_id and not args.session and not args.results_dir:
        build_arg_parser().error("请指定 --session 或 --results-dir（使用 --repro-recipe-id 时也必须提供 --results-dir）")

    paths: dict[str, Path | None]
    if args.repro_recipe_id and not args.plan and not args.session:
        if not args.results_dir:
            build_arg_parser().error("使用 --repro-recipe-id 时需指定 --results-dir")
        paths = {
            "project_root": root,
            "storage_slug": None,
            "results_dir": resolve_path(args.results_dir, project_root=root),
            "upload_root": None,
            "plan": None,
            "metadata_csv": resolve_path(args.metadata_csv, project_root=root)
            if args.metadata_csv
            else None,
            "output_dir": resolve_path(args.output_dir, project_root=root)
            if args.output_dir
            else resolve_path(args.results_dir, project_root=root) / "agent_c_output",
        }
    else:
        paths = resolve_agent_c_paths(
            project_root=root,
            session=args.session or None,
            results_dir=args.results_dir or None,
            plan=args.plan or None,
            metadata_csv=args.metadata_csv or None,
            output_dir=args.output_dir or None,
        )

    meta = paths.get("metadata_csv")
    inv: dict[str, Any] | None = None
    if paths.get("results_dir") is not None:
        inv = inventory_results(
            paths["results_dir"],
            metadata_csv=str(meta) if meta else None,
        )

    if args.parse_plan_only:
        if args.repro_recipe_id:
            from web_frontend.backend.agent_c.paper_reproduction import (
                load_repro_recipe,
                recipe_to_canonical_plan,
            )

            parsed = recipe_to_canonical_plan(load_repro_recipe(args.repro_recipe_id))
        else:
            parsed = parse_plan(paths["plan"])
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
        return 0

    if args.dry_run or args.inventory_only:
        if args.json and inv is not None:
            print(json.dumps({"paths": {k: str(v) for k, v in paths.items()}, "inventory": inv}, ensure_ascii=False, indent=2))
        else:
            _print_summary(paths, inv)
        return 0

    if args.repro_recipe_id:
        if not paths.get("results_dir"):
            build_arg_parser().error("使用 --repro-recipe-id 时需指定 --results-dir")
        manifest = run_agent_c(
            repro_recipe_id=args.repro_recipe_id,
            results_dir=paths["results_dir"],
            output_dir=paths.get("output_dir"),
            metadata_csv=str(meta) if meta else None,
            figure_mode=args.figure_mode,
            language=args.language,
            use_llm=args.use_llm,
            goal_text=args.goal_text,
            project_root=root,
            use_literature=not args.no_literature,
        )
    else:
        manifest = run_agent_c(
            plan=paths["plan"],
            results_dir=paths["results_dir"],
            output_dir=paths["output_dir"],
            metadata_csv=str(meta) if meta else None,
            figure_mode=args.figure_mode,
            language=args.language,
            use_llm=args.use_llm,
            goal_text=args.goal_text,
            project_root=root,
            use_literature=not args.no_literature,
        )

    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        _print_summary(paths, inv)
        print()
        print(f"status      : {manifest.get('status')}")
        print(f"n_rendered  : {manifest.get('n_rendered')}")
        print(f"n_incomplete: {manifest.get('n_incomplete')}")
        report = (manifest.get("report") or {}).get("markdown")
        if report:
            print(f"report      : {report}")
        print(f"manifest    : {manifest.get('manifest')}")
        for w in (manifest.get("warnings") or [])[:8]:
            print(f"warning     : {w}")
    return 0 if manifest.get("status") in {"ok", "partial"} else 1


if __name__ == "__main__":
    sys.exit(main())
