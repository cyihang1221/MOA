"""Web 编排器 Agent A/B 后端路由配置。

默认策略：
- Agent A（规划）：MassOmics-Agent cyh（知识库 + PlanDocument）
- Agent B（执行）：同仓 src/executor，或独立的 origin/B worktree
- Agent C（出图/报告）：web_frontend.backend.agent_c

支持两种布局：
1. 本仓库就是 MassOmics-Agent（cyh：plan/ 与 src/ 与 web_frontend/ 同根）
2. 网页在上级单仓，A 在 MassOmics-Agent/MassOmics-Agent，B 在 MassOmics-Agent-B

A/B/C 保持三个独立智能体；网页只编排交接。

环境变量：
  WEB_AGENT_A_BACKEND=local|massomics   （默认 massomics）
  WEB_AGENT_B_BACKEND=local|massomics   （默认 massomics）
  WEB_MASSOMICS_ROOT=<path>             （A：未设则自动探测）
  WEB_MASSOMICS_B_ROOT=<path>           （B：未设则自动探测）
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_VALID_A = frozenset({"local", "massomics"})
_VALID_B = frozenset({"local", "massomics"})


def _looks_like_massomics_a(root: Path) -> bool:
    return (root / "plan" / "knowledge.py").is_file() and (root / "plan" / "schema.py").is_file()


def _looks_like_massomics_b(root: Path) -> bool:
    return (
        (root / "src" / "executor.py").is_file()
        and (root / "src" / "massomics_adapter.py").is_file()
        and (root / "src" / "mcp_server" / "server.py").is_file()
        and (root / "src" / "tool_catalog.json").is_file()
    )


def massomics_root(project_root: Path | None = None) -> Path:
    env = (os.environ.get("WEB_MASSOMICS_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    base = (project_root or ROOT).resolve()
    if _looks_like_massomics_a(base):
        return base
    return (base / "MassOmics-Agent" / "MassOmics-Agent").resolve()


def massomics_b_root(project_root: Path | None = None) -> Path:
    env = (os.environ.get("WEB_MASSOMICS_B_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    base = (project_root or ROOT).resolve()
    nested_b = (base / "MassOmics-Agent-B").resolve()
    if _looks_like_massomics_b(nested_b):
        return nested_b
    if _looks_like_massomics_b(base):
        return base
    return nested_b


def agent_a_backend() -> str:
    v = (os.environ.get("WEB_AGENT_A_BACKEND") or "massomics").strip().lower()
    return v if v in _VALID_A else "massomics"


def agent_b_backend() -> str:
    v = (os.environ.get("WEB_AGENT_B_BACKEND") or "massomics").strip().lower()
    return v if v in _VALID_B else "massomics"


def massomics_available(project_root: Path | None = None) -> bool:
    root = massomics_root(project_root)
    return (root / "plan" / "knowledge.py").is_file() and (root / "plan" / "schema.py").is_file()


def massomics_b_available(project_root: Path | None = None) -> bool:
    root = massomics_b_root(project_root)
    return (
        (root / "src" / "executor.py").is_file()
        and (root / "src" / "massomics_adapter.py").is_file()
        and (root / "src" / "mcp_server" / "server.py").is_file()
        and (root / "src" / "tool_catalog.json").is_file()
    )


def backend_status(project_root: Path | None = None) -> dict[str, Any]:
    mo_root = massomics_root(project_root)
    b_root = massomics_b_root(project_root)
    a = agent_a_backend()
    b = agent_b_backend()
    mo_ok = massomics_available(project_root)
    b_ok = massomics_b_available(project_root)
    workflows = mo_root / "data" / "kb" / "workflows.json"
    skills_dir = mo_root / "skills"
    chroma = mo_root / "data" / "chroma"
    warnings: list[str] = []
    if a == "massomics" and not mo_ok:
        warnings.append("WEB_AGENT_A_BACKEND=massomics 但 MassOmics plan 模块不可用，将回退 local")
    if b == "massomics" and not b_ok:
        warnings.append(
            "WEB_AGENT_B_BACKEND=massomics 但未找到执行器（src/executor.py）。"
            "请在 MassOmics-Agent cyh 仓库根启动网页，或设置 WEB_MASSOMICS_B_ROOT。"
        )
    if a == "local" and b == "massomics":
        warnings.append("Agent A 为 local 时通常没有 plan_*.json，MassOmics B 可能无法执行")
    if a == "massomics" and not workflows.is_file():
        warnings.append("MassOmics workflows.json 缺失，规划将仅依赖 skills 子集")
    return {
        "agent_a_backend": a,
        "agent_b_backend": b,
        "massomics_root": str(mo_root),
        "massomics_b_root": str(b_root),
        "massomics_available": mo_ok,
        "massomics_b_available": b_ok,
        "massomics_workflows": workflows.is_file(),
        "massomics_skills_dir": skills_dir.is_dir(),
        "massomics_chroma": chroma.is_dir(),
        "local_b_mcp": "src/mcp_server/server.py（仅 WEB_AGENT_B_BACKEND=local）",
        "local_a_module": "web_frontend/backend/agent_runner.py (WebLLM + FR-2)",
        "warnings": warnings,
        "description": {
            "agent_a": (
                "massomics: MassOmics KnowledgeBase + PlanDocument 规划 → analysis_plan.json + plan_*.json"
                if a == "massomics"
                else "local: softwares_database RAG + Web LLM JSON 步骤规划"
            ),
            "agent_b": (
                "massomics: MassOmics 执行器（adapt_massomics_plan + execute_plan + B 侧 MCP）"
                if b == "massomics"
                else "local: 本仓库 src/mcp_server + mixomics/xcms 专用 runner"
            ),
            "agent_c": "web_frontend.backend.agent_c：出图与报告，不跑分析工具",
        },
        "abc_contract": "/api/abc/contract",
    }


__all__ = [
    "agent_a_backend",
    "agent_b_backend",
    "massomics_root",
    "massomics_b_root",
    "massomics_available",
    "massomics_b_available",
    "backend_status",
]
