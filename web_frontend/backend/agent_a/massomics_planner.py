"""MassOmics-Agent 规划适配层：供 Web Agent A 调用。

在 WEB_AGENT_A_BACKEND=massomics 时：
1. 加载 MassOmics KnowledgeBase + 数据探测
2. 用 MassOmics Planner 系统提示 + Web LLM 生成 PlanDocument
3. 写入 plan_<timestamp>.json/.md 供 Agent B（MassOmics-Agent-B）与 Agent C 读取
4. 同步写出 analysis_plan.md 供网页评审；并映射为 local B 可执行任务（WEB_AGENT_B_BACKEND=local 时使用）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from web_frontend.backend.agent_backends import massomics_available, massomics_root
from web_frontend.backend.agent_a.massomics_tool_map import plan_document_to_tasks
from web_frontend.backend.json_parse import extract_first_json_object


class MassOmicsPlannerError(RuntimeError):
    """MassOmics 规划失败。"""


def _join_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value)


def coerce_plan_document(raw: dict[str, Any]) -> dict[str, Any]:
    """把 LLM 偶尔写成 list 的路径字段收成 cyh PlanDocument 需要的字符串。"""
    out = dict(raw)
    out["goal"] = _join_str(out.get("goal"))
    steps_out: list[dict[str, Any]] = []
    for index, step in enumerate(out.get("steps") or []):
        if not isinstance(step, dict):
            continue
        tools = step.get("tools") or []
        if isinstance(tools, str):
            tools = [part.strip() for part in tools.split(",") if part.strip()]
        elif not isinstance(tools, list):
            tools = [str(tools)]
        steps_out.append(
            {
                **step,
                "step_number": int(step.get("step_number") or index + 1),
                "description": _join_str(step.get("description") or step.get("task")),
                "input_filename": _join_str(step.get("input_filename")),
                "output_filename": _join_str(step.get("output_filename")),
                "expected_output": _join_str(step.get("expected_output")),
                "tools": [str(item).strip() for item in tools if str(item).strip()],
            }
        )
    out["steps"] = steps_out
    return out


def _ensure_massomics_path(root: Path) -> None:
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)


def _load_knowledge_base(root: Path):
    _ensure_massomics_path(root)
    from plan.knowledge import KnowledgeBase

    kb_json = root / "data" / "kb" / "workflows.json"
    if not kb_json.is_file():
        raise MassOmicsPlannerError(f"缺少 MassOmics workflows.json: {kb_json}")
    chroma = root / "data" / "chroma"
    skills = root / "skills"
    collections = {
        "application": "lit_app",
        "workflow": "lit_wf",
        "param_kb": "param_kb",
    }
    return KnowledgeBase(
        str(kb_json),
        chroma_path=str(chroma) if chroma.is_dir() else None,
        collections=collections,
        skills_dir=str(skills) if skills.is_dir() else None,
    )


def _inspect_data(upload_dir: str, goal: str) -> str:
    try:
        from plan.inspect_data import build_report, detect, recommend, render
    except ImportError:
        return ""
    path = Path(upload_dir)
    if not path.is_dir():
        return ""
    try:
        files, overall = detect(str(path), recursive=True)
        steps = recommend(overall, goal, files)
        return render(files, overall, steps)
    except Exception:
        try:
            rep = build_report(str(path), goal=goal, recursive=True)
            overall = rep.get("overall") or {}
            return (
                f"[数据探测] 阶段={overall.get('stage')} 平台={overall.get('platform')} "
                f"文件数={overall.get('n_files')}"
            )
        except Exception:
            return ""


def _inspect_metadata(upload_dir: str) -> str:
    from web_frontend.backend.agent_b.artifact_bridge import inspect_metadata_csv

    path = Path(upload_dir)
    candidates = [
        path / "metadata.csv",
        path.parent / "metadata.csv",
        path / "raw" / "metadata.csv",
    ]
    if path.name == "raw":
        candidates.append(path.parent / "metadata.csv")
    for cand in candidates:
        if cand.is_file():
            return inspect_metadata_csv(str(cand))
    return ""


def _planner_system_prompt() -> str:
    _ensure_massomics_path(massomics_root())
    from plan.planner import Planner

    return Planner.SYSTEM_PROMPT


def run_massomics_planning(
    *,
    user_message: str,
    goal: str,
    data_list: str,
    paths: dict[str, str],
    registered_tools: list[str],
    llm_client: Any,
    temperature: float = 0.0,
    project_root: Path | None = None,
    skill_context: str | None = None,
) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    """执行 MassOmics 风格规划。

    Returns:
        tasks: Web B 可执行步骤（Use <tool> to ...）
        plan_doc: PlanDocument dict
        meta: 状态信息（skills/chroma/inspect 等）
    """
    root = massomics_root(project_root)
    if not massomics_available(project_root):
        raise MassOmicsPlannerError(f"MassOmics 规划模块不可用: {root}")

    kb = _load_knowledge_base(root)
    upload = paths.get("upload") or paths.get("inputspace") or "."
    output = paths.get("outputspace") or "."
    goal_text = (goal or user_message or "").strip()
    inspect_txt = _inspect_data(upload, goal_text)
    meta_txt = _inspect_metadata(upload)
    kb_ctx = kb.as_prompt_context(f"{goal_text} {data_list}", goal=goal_text, data_desc=data_list)
    if len(kb_ctx) > 8000:
        kb_ctx = kb_ctx[:8000] + "\n…(知识库上下文已截断，避免规划超时)"

    mem_note = ""
    refs = ""
    insp = (
        f"[数据探测结果 - 依据实际文件内容]\n{inspect_txt}\n"
        if inspect_txt.strip()
        else ""
    )
    skill_txt = (skill_context or "").strip()
    if len(skill_txt) > 7000:
        skill_txt = skill_txt[:7000] + "\n…(skill 已截断)"
    skill_block = ""
    if skill_txt:
        skill_block = (
            "\n[文献参数 Skill — 优先级：用户指令 > 本 Skill > 知识库默认。"
            "必须把文献软件名映射到当前已注册工具，禁止发明未注册工具。"
            "湿法化学、细胞、斑马鱼、国标感官不得写成可执行计算步，除非用户已提供对应结果表。"
            "样本分组以实际 metadata 为准；若与论文五等级设计不一致，按实际分组规划并在 goal 中注明。]\n"
            f"{skill_txt}\n"
        )
    user_prompt = (
        f"数据路径: {upload}\n"
        f"输出目录: {output}\n"
        f"数据描述:\n{data_list}\n"
        f"分析目标: {goal_text}\n\n"
        f"知识库中相关的工作流模板与文献:\n{kb_ctx}\n"
        + (f"\n记忆:\n{mem_note}\n" if mem_note else "")
        + (f"\n{insp}" if insp else "")
        + (f"\n{meta_txt}\n" if meta_txt else "")
        + (f"\n{refs}" if refs else "")
        + skill_block
        + "\n请基于上述信息输出分析计划 JSON。"
    )

    system = _planner_system_prompt()
    resp = llm_client.think_complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=8192,
    )
    if not resp or not str(resp).strip():
        raise MassOmicsPlannerError("MassOmics 规划 LLM 返回为空")

    raw = coerce_plan_document(extract_first_json_object(str(resp)))
    if not raw.get("goal") and not raw.get("steps"):
        raise MassOmicsPlannerError("MassOmics 规划 JSON 缺少 goal/steps")

    _ensure_massomics_path(root)
    from plan.schema import PlanDocument

    try:
        doc = PlanDocument(**raw)
        plan_dict = json.loads(doc.to_json())
    except Exception as exc:
        raise MassOmicsPlannerError(f"PlanDocument 解析失败: {exc}") from exc

    registered = set(registered_tools)
    tasks = plan_document_to_tasks(plan_dict, paths=paths, registered=registered)

    meta = {
        "backend": "massomics",
        "massomics_root": str(root),
        "matched_skills": kb.available_skills()[:8] if hasattr(kb, "available_skills") else [],
        "has_literature_rag": kb.has_literature() if hasattr(kb, "has_literature") else False,
        "data_inspect": bool(inspect_txt.strip()),
        "n_steps": len(plan_dict.get("steps") or []),
        "n_tasks_mapped": len(tasks),
        "injected_skill": bool(skill_txt),
    }
    return tasks, plan_dict, meta


def save_massomics_plan_files(
    output_dir: Path,
    plan_doc: dict[str, Any],
) -> tuple[Path, Path]:
    """写入 plan_<timestamp>.json/.md 到 outputspace。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"plan_{ts}.json"
    md_path = output_dir / f"plan_{ts}.md"

    _ensure_massomics_path(massomics_root())
    from plan.schema import PlanDocument

    doc = PlanDocument(**plan_doc)
    json_path.write_text(doc.to_json(), encoding="utf-8")
    md_path.write_text(doc.to_markdown(), encoding="utf-8")
    return json_path, md_path


def write_web_analysis_plan_from_massomics(
    output_dir: Path,
    *,
    plan_doc: dict[str, Any],
    tasks: list[str],
    data_understanding: str,
    user_message: str = "",
    project_root: Path | None = None,
) -> dict[str, Any]:
    """MassOmics 计划同步写 Web FR-2 analysis_plan.*，保证 B/C 契约不变。"""
    from web_frontend.backend.agent_a.plan_document import write_analysis_plan

    objective = str(plan_doc.get("goal") or "").strip()
    return write_analysis_plan(
        output_dir,
        objective=objective,
        data_understanding=data_understanding,
        tasks=tasks,
        user_message=user_message or objective,
        project_root=project_root,
    )


__all__ = [
    "MassOmicsPlannerError",
    "coerce_plan_document",
    "run_massomics_planning",
    "save_massomics_plan_files",
    "write_web_analysis_plan_from_massomics",
]
