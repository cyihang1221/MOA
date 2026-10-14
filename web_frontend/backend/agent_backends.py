"""网页编排器对接的 A / B 代码根。

师兄 ``complete``（``MOA_completeV0.1``）把 **A 与 B 放在同一棵仓库树**：

- A = ``plan/``（规划，不跑 MCP）
- B = ``src/`` + ``agent_b/``（执行；工具走同仓库 MCP stdio）
- C 仍由本目录 ``web_frontend.backend.agent_c`` 出图/报告，不跑 XCMS

网页 **不**调用 complete 的 ``python main.py`` / ``agent_a.py``（那些会在同进程里
把 A→B→C 串起来）。网页只编排三个独立智能体。

默认探测顺序（可用环境变量覆盖）：

1. ``WEB_MASSOMICS_ROOT`` / ``WEB_MASSOMICS_B_ROOT``
2. 同时具备 A+B 的 **complete 同根**：优先干净 worktree ``MassOmics-Agent-B``
   （当前为 ``origin/complete``），其次嵌套 ``MassOmics-Agent/MassOmics-Agent``
3. 仅 A 或仅 B 的旧布局回退

区块说明见 ``web_frontend/LAYOUT.md``。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

_VALID_A = frozenset({"local", "massomics"})
_VALID_B = frozenset({"local", "massomics"})


def _looks_like_massomics_a(root: Path) -> bool:
    return all((root / "plan" / name).is_file() for name in (
        "knowledge.py", "schema.py", "planner.py",
    ))


def _looks_like_massomics_b(root: Path) -> bool:
    return (
        (root / "src" / "executor.py").is_file()
        and (root / "src" / "massomics_adapter.py").is_file()
        and (root / "src" / "mcp_server" / "server.py").is_file()
        and (root / "src" / "tool_catalog.json").is_file()
    )


def _is_git_lfs_pointer(path: Path) -> bool:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:80]
    except OSError:
        return False
    return head.startswith("version https://git-lfs.github.com/spec/v1")


def tool_catalog_path(root: Path) -> Path:
    return root / "src" / "tool_catalog.json"


def tool_catalog_usable(root: Path | None = None) -> bool:
    """complete 把 tool_catalog.json 放进 Git LFS；skip-smudge 时只剩指针，B 无法规范化计划。"""
    path = tool_catalog_path(root if root is not None else massomics_b_root())
    if not path.is_file() or _is_git_lfs_pointer(path):
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and isinstance(data.get("tools"), list) and bool(data["tools"])


def _looks_like_complete_abc(root: Path) -> bool:
    """complete：A（plan/）与 B（src/executor.py + adapter）同根。"""
    return _looks_like_massomics_a(root) and _looks_like_massomics_b(root)


def complete_abc_candidates(project_root: Path | None = None) -> list[Path]:
    """可能的 complete 同根目录（先干净 worktree，再嵌套工作区）。"""
    base = (project_root or ROOT).resolve()
    nested = (base / "MassOmics-Agent" / "MassOmics-Agent").resolve()
    return [
        (base / "MassOmics-Agent-B").resolve(),
        nested,
        (base / "MassOmics-Agent").resolve(),
        base,
    ]


def complete_abc_root(project_root: Path | None = None) -> Path | None:
    """第一棵同时具备 plan/ + B 执行器的树；没有则 None。"""
    seen: set[Path] = set()
    for candidate in complete_abc_candidates(project_root):
        if candidate in seen:
            continue
        seen.add(candidate)
        if _looks_like_complete_abc(candidate):
            return candidate
    return None


def massomics_root(project_root: Path | None = None) -> Path:
    """Agent A 代码根：complete 同根优先，否则旧嵌套 ``plan/``。"""
    env = (os.environ.get("WEB_MASSOMICS_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    unified = complete_abc_root(project_root)
    if unified is not None:
        return unified
    base = (project_root or ROOT).resolve()
    nested = (base / "MassOmics-Agent" / "MassOmics-Agent").resolve()
    if _looks_like_massomics_a(nested):
        return nested
    if _looks_like_massomics_a(base):
        return base
    return nested


def massomics_b_root(project_root: Path | None = None) -> Path:
    """Agent B 代码根：与 A 同一 complete 树；否则旧 ``MassOmics-Agent-B``。"""
    env = (os.environ.get("WEB_MASSOMICS_B_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    unified = complete_abc_root(project_root)
    if unified is not None:
        return unified
    base = (project_root or ROOT).resolve()
    sibling = (base / "MassOmics-Agent-B").resolve()
    if _looks_like_massomics_b(sibling):
        return sibling
    if _looks_like_massomics_b(base):
        return base
    nested = (base / "MassOmics-Agent" / "MassOmics-Agent").resolve()
    if _looks_like_massomics_b(nested):
        return nested
    return sibling


def agent_a_backend() -> str:
    v = (os.environ.get("WEB_AGENT_A_BACKEND") or "massomics").strip().lower()
    return v if v in _VALID_A else "massomics"


def agent_b_backend() -> str:
    v = (os.environ.get("WEB_AGENT_B_BACKEND") or "massomics").strip().lower()
    return v if v in _VALID_B else "massomics"


def massomics_available(project_root: Path | None = None) -> bool:
    root = massomics_root(project_root)
    return _looks_like_massomics_a(root)


def massomics_b_available(project_root: Path | None = None) -> bool:
    root = massomics_b_root(project_root)
    return _looks_like_massomics_b(root)


def backend_status(project_root: Path | None = None) -> dict[str, Any]:
    mo_root = massomics_root(project_root)
    b_root = massomics_b_root(project_root)
    unified = complete_abc_root(project_root)
    a = agent_a_backend()
    b = agent_b_backend()
    mo_ok = massomics_available(project_root)
    b_ok = massomics_b_available(project_root)
    same_tree = mo_root.resolve() == b_root.resolve()
    layout = (
        "complete_unified"
        if unified is not None and same_tree
        else "split_or_override"
    )
    workflows = mo_root / "data" / "kb" / "workflows.json"
    skills_dir = mo_root / "skills"
    chroma = mo_root / "data" / "chroma"
    warnings: list[str] = []
    if a == "massomics" and not mo_ok:
        warnings.append("WEB_AGENT_A_BACKEND=massomics 但 MassOmics plan 模块不完整（需要 knowledge.py、schema.py、planner.py）")
    if b == "massomics" and not b_ok:
        warnings.append(
            "WEB_AGENT_B_BACKEND=massomics 但未找到执行器（src/executor.py + massomics_adapter）。"
            "请检出 origin/complete（本仓常用 MassOmics-Agent-B），或设置 WEB_MASSOMICS_B_ROOT。"
        )
    if a == "local" and b == "massomics":
        warnings.append("Agent A 为 local 时通常没有 plan_*.json，MassOmics B 可能无法执行")
    if a == "massomics" and (not workflows.is_file() or _is_git_lfs_pointer(workflows)):
        warnings.append(
            "MassOmics workflows.json 缺失或仍是 Git LFS 指针，规划将仅依赖 skills 子集。"
            "需要时：git lfs pull --include='data/kb/workflows.json,src/tool_catalog.json'"
        )
    if b == "massomics" and b_ok and not tool_catalog_usable(b_root):
        warnings.append(
            "complete 的 src/tool_catalog.json 不可用（常见原因：worktree 创建时 GIT_LFS_SKIP_SMUDGE=1）。"
            "Agent B 规范化计划会失败。请拉取："
            "git -C MassOmics-Agent-B lfs pull --include='src/tool_catalog.json,data/kb/workflows.json'"
        )
    if layout == "split_or_override" and a == "massomics" and b == "massomics":
        warnings.append(
            "A 与 B 不在同一棵 complete 树。complete 布局下二者应同根；"
            "可用 WEB_MASSOMICS_ROOT / WEB_MASSOMICS_B_ROOT 指向同一目录。"
        )
    return {
        "agent_a_backend": a,
        "agent_b_backend": b,
        "massomics_root": str(mo_root),
        "massomics_b_root": str(b_root),
        "complete_abc_root": str(unified) if unified is not None else None,
        "same_tree": same_tree,
        "layout": layout,
        "massomics_available": mo_ok,
        "massomics_b_available": b_ok,
        "massomics_workflows": workflows.is_file(),
        "massomics_skills_dir": skills_dir.is_dir(),
        "massomics_chroma": chroma.is_dir(),
        "tool_catalog_usable": tool_catalog_usable(b_root),
        "local_b_mcp": "src/mcp_server/server.py（仅 WEB_AGENT_B_BACKEND=local）",
        "local_a_module": "web_frontend/backend/agent_runner.py (WebLLM + FR-2)",
        "warnings": warnings,
        "description": {
            "agent_a": (
                "massomics: complete plan/ KnowledgeBase + PlanDocument → analysis_plan + plan_*.json"
                if a == "massomics"
                else "local: softwares_database RAG + Web LLM JSON 步骤规划"
            ),
            "agent_b": (
                "massomics: complete src/executor（adapt_massomics_plan + execute_plan + 同仓 MCP）"
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
    "complete_abc_candidates",
    "complete_abc_root",
    "tool_catalog_usable",
    "massomics_root",
    "massomics_b_root",
    "massomics_available",
    "massomics_b_available",
    "backend_status",
]
