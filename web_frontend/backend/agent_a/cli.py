"""Agent A 命令行：根据数据与目标写出 plan_*.json / analysis_plan.md（不执行）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from web_frontend.backend.agent_a.massomics_planner import (
    save_massomics_plan_files,
    run_massomics_planning,
    write_web_analysis_plan_from_massomics,
)
from web_frontend.backend.constants import ALLOWED_TOOL_NAMES
from web_frontend.backend.session_storage import (
    inputspace_root,
    outputspace_root,
    session_upload_dir,
    session_work_dir,
)
from web_frontend.backend.web_llm import WebLLMClient


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_env(project_root: Path) -> None:
    env_path = project_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(find_dotenv(), override=False)


def _data_list(upload: Path) -> str:
    if not upload.is_dir():
        return f"(目录不存在: {upload})"
    lines: list[str] = []
    for path in sorted(upload.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(upload).as_posix()
        size = path.stat().st_size
        if size >= 1024 * 1024:
            size_s = f"{size / (1024 * 1024):.1f} MiB"
        else:
            size_s = f"{size} B"
        lines.append(f"{rel} ({size_s})")
        if len(lines) >= 80:
            lines.append("…")
            break
    return "\n".join(lines) if lines else f"(空目录: {upload})"


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agent A：规划代谢组学分析（写出 plan_*.json，不执行工具）"
    )
    parser.add_argument("--session", default="", help="会话 id / storage_slug")
    parser.add_argument("--data", default="", help="inputspace；默认会话上传目录")
    parser.add_argument("--outputspace", default="", help="计划写入目录；默认会话 outputspace")
    parser.add_argument(
        "--goal",
        default="对上传的质谱数据进行代谢组学全流程分析",
        help="分析目标",
    )
    parser.add_argument("--project-root", default="", help="MassAgent 仓库根")
    args = parser.parse_args(argv)

    project_root = (
        Path(args.project_root).expanduser().resolve()
        if str(args.project_root).strip()
        else default_project_root()
    )
    _load_env(project_root)

    if args.session:
        slug = resolve_session_slug(project_root, args.session)
        upload = session_upload_dir(project_root, slug)
        output = session_work_dir(project_root, slug)
    elif args.data and args.outputspace:
        upload = Path(args.data).expanduser()
        output = Path(args.outputspace).expanduser()
        if not upload.is_absolute():
            upload = (project_root / upload).resolve()
        else:
            upload = upload.resolve()
        if not output.is_absolute():
            output = (project_root / output).resolve()
        else:
            output = output.resolve()
    else:
        parser.error("请提供 --session，或同时提供 --data 与 --outputspace")
        return 2

    if not upload.is_dir():
        print(f"数据目录不存在: {upload}", file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)

    paths = {
        "upload": str(upload),
        "inputspace": str(upload),
        "outputspace": str(output),
    }
    data_list = _data_list(upload)
    print("Agent A 规划", flush=True)
    print(f"  data         : {upload}", flush=True)
    print(f"  outputspace  : {output}", flush=True)
    print(f"  goal         : {args.goal}", flush=True)
    print(f"  files        : {data_list.count(chr(10)) + 1} 条", flush=True)

    try:
        llm = WebLLMClient()
        tasks, plan_doc, meta = run_massomics_planning(
            user_message=args.goal,
            goal=args.goal,
            data_list=data_list,
            paths=paths,
            registered_tools=sorted(ALLOWED_TOOL_NAMES),
            llm_client=llm,
            temperature=0.0,
            project_root=project_root,
        )
    except Exception as exc:
        print(f"Agent A 失败: {exc}", file=sys.stderr, flush=True)
        return 1
    json_path, md_path = save_massomics_plan_files(output, plan_doc)
    write_web_analysis_plan_from_massomics(
        output,
        plan_doc=plan_doc,
        tasks=tasks,
        data_understanding=data_list,
        user_message=args.goal,
        project_root=project_root,
    )
    print(f"  plan_json    : {json_path}")
    print(f"  plan_md      : {md_path}")
    print(f"  analysis_plan: {output / 'analysis_plan.md'}")
    print(f"  n_steps      : {meta.get('n_steps')}")
    print(f"  n_tasks_map  : {meta.get('n_tasks_mapped')}")
    steps = plan_doc.get("steps") or []
    for step in steps:
        if not isinstance(step, dict):
            continue
        tools = step.get("tools") or []
        print(
            f"    Step {step.get('step_number')}: {step.get('description', '')[:80]}"
            f"  tools={tools}"
        )
    print(json.dumps({"plan": str(json_path), "n_steps": len(steps)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
