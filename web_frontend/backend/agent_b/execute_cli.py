"""Agent B 独立入口：必须在 MassOmics-Agent-B 的 PYTHONPATH 下运行。

网页编排器通过子进程调用本文件，避免与本仓库 ``src/`` 以及 Agent A/C 抢同一解释器路径。
不调用 ``src.agent.Agent.run()``（那会重做规划并写报告）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _b_root() -> Path:
    env = (os.environ.get("MASSOMICS_B_ROOT") or os.environ.get("WEB_MASSOMICS_B_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    raise SystemExit("MASSOMICS_B_ROOT 未设置：请由网页编排器注入 MassOmics-Agent-B 路径")


def _bind_b_src(b_root: Path) -> None:
    root = str(b_root)
    if root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)
    _stub_optional_b_rag()


def _stub_optional_b_rag() -> None:
    """B 的 src.prompt 在 import 时拉 llama_index；缺依赖时跳过 RAG，不挡住执行。"""
    try:
        import llama_index.core  # noqa: F401
        return
    except ImportError:
        pass
    if "src.build_RAG_private" in sys.modules:
        return
    import types

    stub = types.ModuleType("src.build_RAG_private")
    stub.preload_retriever = lambda *args, **kwargs: None
    stub.retrive = lambda *args, **kwargs: []
    sys.modules["src.build_RAG_private"] = stub
    print("[Agent B] ⚠️ 当前解释器没有 llama_index，已跳过 B 侧 RAG 导入", flush=True)


def _inject_database_dir(b_root: Path) -> None:
    """让 B 子进程能找到工作区根的 database_file（谱库 / compound_pathway.tsv）。"""
    if (os.environ.get("MASSOMICS_DATABASE_DIR") or "").strip():
        return
    here = Path(__file__).resolve()
    candidates = [b_root / "database_file"]
    if len(here.parents) >= 4:
        candidates.append(here.parents[3] / "database_file")
    candidates.append(Path.cwd() / "database_file")
    for cand in candidates:
        if cand.is_dir() and any(cand.iterdir()):
            os.environ["MASSOMICS_DATABASE_DIR"] = str(cand.resolve())
            print(f"[Agent B] database_file: {cand.resolve()}", flush=True)
            return


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _receipt_status(run: Any) -> str:
    if getattr(run, "aborted", False):
        return "aborted"
    results = list(getattr(run, "results", None) or [])
    if any(getattr(r, "status", "") == "failed" for r in results):
        return "failed"
    if not results:
        return "failed"
    return "success"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent B：执行已确认的 MassOmics PlanDocument")
    parser.add_argument("--plan", required=True, help="A 产出的 plan_*.json")
    parser.add_argument("--data", required=True, help="会话 inputspace")
    parser.add_argument("--outputspace", required=True, help="会话 outputspace（即 C 的 results_dir）")
    parser.add_argument("--receipt", required=True, help="回执 JSON 路径")
    parser.add_argument("--metadata", default="", help="可选 metadata.csv")
    parser.add_argument("--adapted-plan", default="", help="规范化后的计划落盘路径")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    b_root = _b_root()
    _bind_b_src(b_root)
    _inject_database_dir(b_root)

    plan_path = Path(args.plan).expanduser().resolve()
    data_path = Path(args.data).expanduser().resolve()
    outputspace = Path(args.outputspace).expanduser().resolve()
    receipt_path = Path(args.receipt).expanduser().resolve()
    adapted_path = (
        Path(args.adapted_plan).expanduser().resolve()
        if str(args.adapted_plan).strip()
        else outputspace / "agent_b_adapted_plan.json"
    )
    metadata = str(Path(args.metadata).expanduser().resolve()) if str(args.metadata).strip() else ""
    if not metadata:
        fallback_meta = data_path / "metadata.csv"
        if fallback_meta.is_file():
            metadata = str(fallback_meta)

    outputspace.mkdir(parents=True, exist_ok=True)
    print(f"[Agent B] MassOmics 执行器: {b_root}", flush=True)
    print(f"[Agent B] 计划: {plan_path}", flush=True)
    print(f"[Agent B] 数据: {data_path}", flush=True)
    print(f"[Agent B] 结果目录: {outputspace}", flush=True)

    if not metadata:
        print("[Agent B] ⚠️ 未找到 metadata.csv；需要分组的步骤可能会失败", flush=True)
    else:
        print(f"[Agent B] metadata: {metadata}", flush=True)

    from plan_locate import load_plan_document
    from plan_normalize import load_tool_catalog, normalize_plan_for_b

    try:
        document = load_plan_document(plan_path)
        catalog = load_tool_catalog(b_root / "src" / "tool_catalog.json")
        normalized, warnings = normalize_plan_for_b(document, catalog)
        _write_json(adapted_path, normalized)
        for warn in warnings:
            print(f"[Agent B] ⚠️ {warn}", flush=True)
        print(f"[Agent B] 已写入规范化计划: {adapted_path}", flush=True)

        from src.executor import RunConfig, execute_plan
        from src.massomics_adapter import adapt_massomics_plan
        from src.artifact_manifest import ArtifactManifest
        from artifact_bridge import (
            adopt_legacy_output_dir,
            inspect_metadata_csv,
            prepare_tool_args,
            scan_output_as_tool_result,
            stage_output_reusable,
            wrap_mcp_text_result,
        )

        if metadata:
            design = inspect_metadata_csv(metadata)
            if design:
                print(f"[Agent B] {design}", flush=True)

        try:
            stages = adapt_massomics_plan(
                normalized,
                data_path=str(data_path),
                metadata_path=metadata,
            )
        except ValueError as exc:
            msg = str(exc)
            if "metadata_csv" in msg:
                raise ValueError(
                    f"{msg}。请在会话 inputspace 放置 metadata.csv（含 Sample、Group 列）。"
                ) from exc
            raise
        print(f"[Agent B] 适配为 {len(stages)} 个执行阶段，开始调用 B 侧 MCP …", flush=True)
        for stage in stages:
            tool = getattr(stage, "tool", None) or ""
            print(f"[Agent B]  - {getattr(stage, 'stage', '')}  tool={tool}", flush=True)

        manifest = ArtifactManifest()

        async def _run() -> Any:
            from mcp import ClientSession, StdioServerParameters, stdio_client

            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "src.mcp_server.server"],
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    async def _call(name: str, args: dict[str, Any]) -> Any:
                        out_dir = adopt_legacy_output_dir(
                            name,
                            str(args.get("output_dir") or ""),
                            str(outputspace),
                        )
                        args["output_dir"] = out_dir
                        prepared = prepare_tool_args(
                            name, dict(args), run_output_dir=str(outputspace)
                        )
                        prepared["output_dir"] = out_dir
                        if stage_output_reusable(name, out_dir):
                            payload = scan_output_as_tool_result(name, out_dir)
                            print(
                                f"[Agent B] ⏭ 复用已有产物 {name}: {out_dir}",
                                flush=True,
                            )
                            return wrap_mcp_text_result(payload)
                        return await session.call_tool(name, prepared)

                    return await execute_plan(
                        stages,
                        config=RunConfig(
                            run_output_dir=str(outputspace),
                            metadata_csv_path=metadata,
                            artifact_manifest=manifest,
                        ),
                        call_tool=_call,
                    )

        run = asyncio.run(_run())
    except Exception as exc:
        payload = {
            "agent": "B",
            "backend": "massomics",
            "status": "failed",
            "had_tool_failure": True,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "plan_path": str(plan_path),
            "results_dir": str(outputspace),
            "b_root": str(b_root),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
        _write_json(receipt_path, payload)
        print(f"[Agent B] ❌ 执行失败: {exc}", flush=True)
        traceback.print_exc()
        return 2

    status = _receipt_status(run)
    results = [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in (run.results or [])]
    payload = {
        "agent": "B",
        "backend": "massomics",
        "status": status,
        "had_tool_failure": status != "success",
        "plan_path": str(plan_path),
        "adapted_plan_path": str(adapted_path),
        "results_dir": str(outputspace),
        "b_root": str(b_root),
        "n_stages": len(results),
        "stats": getattr(run, "stats", None) or {},
        "aborted": bool(getattr(run, "aborted", False)),
        "abort_reason": getattr(run, "abort_reason", None),
        "stages": results,
        "stage_output_dirs": getattr(run, "stage_output_dirs", None) or [],
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(receipt_path, payload)
    print(
        f"[Agent B] 回执: status={status} stages={len(results)} → {receipt_path}",
        flush=True,
    )
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
