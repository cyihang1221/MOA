"""Agent B 命令行：按会话或路径执行已确认计划（独立于 A/C）。"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_b.massomics_executor import stream_massomics_b_execution
from web_frontend.backend.agent_b.plan_locate import find_massomics_plan_json
from web_frontend.backend.session_storage import (
    inputspace_root,
    outputspace_root,
    session_upload_dir,
    session_work_dir,
)


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_session_slug(project_root: Path, hint: str) -> str:
    text = (hint or "").strip()
    if not text:
        raise ValueError("session hint 不能为空")
    for root_fn in (outputspace_root, inputspace_root):
        if (root_fn(project_root) / text).is_dir():
            return text
    matches: list[str] = []
    seen: set[str] = set()
    for root_fn in (outputspace_root, inputspace_root):
        root = root_fn(project_root)
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name in seen:
                continue
            name = child.name
            if name == text or name.endswith(f"_{text}") or text in name:
                matches.append(name)
                seen.add(name)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        preview = "\n  - ".join(matches[:8])
        raise ValueError(f"session 提示词 {text!r} 匹配到多个目录：\n  - {preview}")
    raise FileNotFoundError(f"未找到 session {text!r}")


async def _print_stream(paths: dict[str, str], project_root: Path, plan: Path | None) -> int:
    had_error = False
    async for event in stream_massomics_b_execution(
        paths=paths,
        session_id="cli",
        project_root=project_root,
        plan_path=plan,
    ):
        if "delta" in event:
            sys.stdout.write(str(event["delta"]))
            sys.stdout.flush()
        if event.get("error"):
            had_error = True
            print(f"\n❌ {event['error']}", file=sys.stderr)
        if event.get("had_tool_failure"):
            had_error = True
    return 1 if had_error else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent B：读取 A 的 plan_*.json，调用 MassOmics-Agent-B 执行器"
    )
    parser.add_argument("--session", default="", help="会话 id / storage_slug")
    parser.add_argument("--plan", default="", help="覆盖自动查找的 plan_*.json")
    parser.add_argument("--data", default="", help="inputspace；默认会话上传目录")
    parser.add_argument("--outputspace", default="", help="结果目录；默认会话 outputspace")
    parser.add_argument("--project-root", default="", help="MassAgent 仓库根")
    args = parser.parse_args(argv)

    project_root = (
        Path(args.project_root).expanduser().resolve()
        if str(args.project_root).strip()
        else default_project_root()
    )

    if args.session:
        slug = resolve_session_slug(project_root, args.session)
        upload = session_upload_dir(project_root, slug)
        output = session_work_dir(project_root, slug)
    elif args.data and args.outputspace:
        upload = Path(args.data).expanduser().resolve()
        output = Path(args.outputspace).expanduser().resolve()
    else:
        parser.error("请提供 --session，或同时提供 --data 与 --outputspace")
        return 2

    plan: Path | None = None
    if args.plan:
        plan = Path(args.plan).expanduser()
        if not plan.is_absolute():
            for base in (output, upload, project_root):
                cand = (base / plan).resolve()
                if cand.is_file():
                    plan = cand
                    break
            else:
                plan = plan.resolve()
        if not plan.is_file():
            print(f"未找到计划: {args.plan}", file=sys.stderr)
            return 2
    else:
        plan = find_massomics_plan_json(output, upload)
        if plan is None:
            print("未找到 plan_*.json；请先跑 Agent A 或用 --plan 指定。", file=sys.stderr)
            return 2

    paths: dict[str, Any] = {
        "upload": str(upload),
        "inputspace": str(upload),
        "outputspace": str(output),
    }
    return asyncio.run(_print_stream(paths, project_root, plan))


if __name__ == "__main__":
    raise SystemExit(main())
