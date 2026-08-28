"""Web 编排器 Agent A/B 后端路由配置。

默认策略（与用户约定）：
- Agent A（规划）：MassOmics-Agent（师兄路径）— 知识库 + PlanDocument 规划
- Agent B（执行）：本地 web MCP（agent_runner + src/mcp_server）— 工具最全、已有 bypass

环境变量：
  WEB_AGENT_A_BACKEND=local|massomics   （默认 massomics）
  WEB_AGENT_B_BACKEND=local|massomics   （默认 local；massomics 执行尚未完整，仅预留）
  WEB_MASSOMICS_ROOT=<path>             （默认 <project>/MassOmics-Agent/MassOmics-Agent）
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_VALID_A = frozenset({"local", "massomics"})
_VALID_B = frozenset({"local", "massomics"})


def massomics_root(project_root: Path | None = None) -> Path:
    env = (os.environ.get("WEB_MASSOMICS_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    base = project_root or ROOT
    return (base / "MassOmics-Agent" / "MassOmics-Agent").resolve()


def agent_a_backend() -> str:
    v = (os.environ.get("WEB_AGENT_A_BACKEND") or "massomics").strip().lower()
    return v if v in _VALID_A else "massomics"


def agent_b_backend() -> str:
    v = (os.environ.get("WEB_AGENT_B_BACKEND") or "local").strip().lower()
    return v if v in _VALID_B else "local"


def massomics_available(project_root: Path | None = None) -> bool:
    root = massomics_root(project_root)
    return (root / "plan" / "knowledge.py").is_file() and (root / "plan" / "schema.py").is_file()


def backend_status(project_root: Path | None = None) -> dict[str, Any]:
    mo_root = massomics_root(project_root)
    a = agent_a_backend()
    b = agent_b_backend()
    mo_ok = massomics_available(project_root)
    workflows = mo_root / "data" / "kb" / "workflows.json"
    skills_dir = mo_root / "skills"
    chroma = mo_root / "data" / "chroma"
    warnings: list[str] = []
    if a == "massomics" and not mo_ok:
        warnings.append("WEB_AGENT_A_BACKEND=massomics 但 MassOmics plan 模块不可用，将回退 local")
    if b == "massomics":
        warnings.append("Agent B 的 MassOmics 执行适配尚未完整，建议保持 WEB_AGENT_B_BACKEND=local")
    if a == "massomics" and not workflows.is_file():
        warnings.append("MassOmics workflows.json 缺失，规划将仅依赖 skills 子集")
    return {
        "agent_a_backend": a,
        "agent_b_backend": b,
        "massomics_root": str(mo_root),
        "massomics_available": mo_ok,
        "massomics_workflows": workflows.is_file(),
        "massomics_skills_dir": skills_dir.is_dir(),
        "massomics_chroma": chroma.is_dir(),
        "local_b_mcp": "src/mcp_server/server.py",
        "local_a_module": "web_frontend/backend/agent_runner.py (WebLLM + FR-2)",
        "warnings": warnings,
        "description": {
            "agent_a": (
                "massomics: MassOmics KnowledgeBase + PlanDocument 规划 → analysis_plan.json + plan_*.json"
                if a == "massomics"
                else "local: softwares_database RAG + Web LLM JSON 步骤规划"
            ),
            "agent_b": (
                "local: MCP 工具白名单 + mixomics/xcms 专用 runner（推荐）"
                if b == "local"
                else "massomics: 预留；MassOmics tools/ 与 Web MCP 映射未完整"
            ),
        },
    }


__all__ = [
    "agent_a_backend",
    "agent_b_backend",
    "massomics_root",
    "massomics_available",
    "backend_status",
]
