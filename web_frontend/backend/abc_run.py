"""命令行编排 A → B → C（三个独立入口依次调用，不合成一个 Agent）。"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from web_frontend.backend.agent_a.cli import default_project_root, main as agent_a_main
from web_frontend.backend.agent_b.massomics_executor import stream_massomics_b_execution
from web_frontend.backend.agent_c.cli import main as agent_c_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="依次调用独立的 Agent A、B、C（确认闸门由调用方保证；本 CLI 用于联调）"
    )
    parser.add_argument("--data", required=True, help="inputspace 目录")
    parser.add_argument("--outputspace", required=True, help="结果与计划目录")
    parser.add_argument(
        "--goal",
        default="对上传的质谱数据进行代谢组学全流程分析",
    )
    parser.add_argument(
        "--stop-after",
        choices=("a", "b", "c"),
        default="c",
        help="跑完指定智能体后停止（默认 c=全程）",
    )
    parser.add_argument("--skip-a", action="store_true", help="已有 plan_*.json 时跳过 A")
    parser.add_argument("--project-root", default="")
    args = parser.parse_args(argv)

    project_root = (
        Path(args.project_root).expanduser().resolve()
        if str(args.project_root).strip()
        else default_project_root()
    )
    env_path = project_root / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(find_dotenv(), override=False)

    data = Path(args.data)
    output = Path(args.outputspace)
    if not data.is_absolute():
        data = (project_root / data).resolve()
    if not output.is_absolute():
        output = (project_root / output).resolve()

    if not args.skip_a:
        print("\n======== Agent A ========\n", flush=True)
        code = agent_a_main(
            [
                "--data",
                str(data),
                "--outputspace",
                str(output),
                "--goal",
                args.goal,
                "--project-root",
                str(project_root),
            ]
        )
        if code != 0:
            return code
    else:
        print("跳过 Agent A（--skip-a）", flush=True)

    if args.stop_after == "a":
        return 0

    print("\n======== Agent B ========\n", flush=True)

    async def _run_b() -> tuple[int, bool]:
        had_error = False
        execute_done = False
        async for event in stream_massomics_b_execution(
            paths={"upload": str(data), "inputspace": str(data), "outputspace": str(output)},
            session_id="abc-cli",
            project_root=project_root,
        ):
            if "delta" in event:
                sys.stdout.write(str(event["delta"]))
                sys.stdout.flush()
            if event.get("execute_done"):
                execute_done = True
            if event.get("error") and not execute_done:
                had_error = True
                print(f"\n❌ {event['error']}", file=sys.stderr)
            if event.get("had_tool_failure"):
                had_error = True
        return (1 if had_error else 0), execute_done

    b_code, b_done = asyncio.run(_run_b())
    if args.stop_after == "b":
        return b_code
    if not b_done:
        return b_code if b_code != 0 else 1

    print("\n======== Agent C ========\n", flush=True)
    c_args = [
        "--results-dir",
        str(output),
        "--project-root",
        str(project_root),
        "--figure-mode",
        "plan_then_available",
    ]
    meta = data / "metadata.csv"
    if meta.is_file():
        c_args.extend(["--metadata-csv", str(meta)])
    analysis = [
        p
        for p in (output / "analysis_plan.md", output / "analysis_plan.json")
        if p.is_file()
    ]
    md_plans = sorted(output.glob("plan_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    json_plans = sorted(output.glob("plan_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if analysis:
        c_args.extend(["--plan", str(analysis[0])])
    elif md_plans:
        c_args.extend(["--plan", str(md_plans[0])])
    elif json_plans:
        c_args.extend(["--plan", str(json_plans[0])])
    c_code = agent_c_main(c_args)
    if b_code != 0 and c_code == 0:
        print("Agent B 有失败阶段，Agent C 已按可用结果出图。", flush=True)
        return 0
    return c_code


if __name__ == "__main__":
    raise SystemExit(main())
