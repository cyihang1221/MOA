"""会话工作流状态机：网页编排 A → 确认 → B → C。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from web_frontend.backend.agent_intent import (
    B_RERUN_RE,
    classify_frontend_intent,
    intent_text,
    looks_like_agent_request,
    looks_like_c_visual_request,
)

WAITING_INPUT = "WAITING_INPUT"
PLANNING = "PLANNING"
AWAITING_APPROVAL = "AWAITING_APPROVAL"
EXECUTING = "EXECUTING"
REPORTING = "REPORTING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

WorkflowStatus = Literal[
    "WAITING_INPUT",
    "PLANNING",
    "AWAITING_APPROVAL",
    "EXECUTING",
    "REPORTING",
    "COMPLETED",
    "FAILED",
]

ChatAction = Literal[
    "chat",
    "plan",
    "execute",
    "report",
    "visual",
    "refuse_unconfirmed",
    "refuse_visual_early",
    "clarify",
    "remind_confirm",
    "remind_rerun",
]

STATUS_LABELS_ZH = {
    WAITING_INPUT: "等待输入",
    PLANNING: "正在规划",
    AWAITING_APPROVAL: "待确认计划",
    EXECUTING: "正在执行分析",
    REPORTING: "正在出图/写报告",
    COMPLETED: "已完成",
    FAILED: "执行失败",
}

_CONFIRM_RE = re.compile(
    r"(?:"
    r"确认计划|同意(?:本|该|此)?计划|按此执行|按这个执行|批准执行|"
    r"可以执行|开始执行|"
    r"confirm(?:\s+the)?\s+plan|approve(?:\s+the)?\s+plan"
    r")",
    re.IGNORECASE,
)

_START_WITHOUT_CONFIRM_RE = re.compile(
    r"(?:开始分析|执行分析|跑一遍|运行工具|跑\s*XCMS|run analysis|start agent)",
    re.IGNORECASE,
)

_PLAN_REQUEST_RE = re.compile(
    r"(?:制定计划|生成计划|分析计划|帮我分析|做一次分析|差异代谢|分析目标|"
    r"非靶向|代谢组|比较.{0,20}(?:组|对照|处理)|Control|Treatment)",
    re.IGNORECASE,
)

_REVISION_RE = re.compile(
    r"(?:"
    r"修改计划|改用|换成|增加一步|少做|"
    r"第.{0,4}步|"
    r"不要(?:做|跑|用|分子)|"
    r"MZmine|MS-?DIAL"
    r")",
    re.IGNORECASE,
)

_REPLAN_EXPLICIT_RE = re.compile(
    r"(?:重新(?:制定|生成|规划)|重新规划|(?:再|重)写(?:一份|个)?计划)",
    re.IGNORECASE,
)


def normalize_status(value: str | None) -> WorkflowStatus:
    raw = (value or "").strip() or WAITING_INPUT
    if raw in STATUS_LABELS_ZH:
        return raw  # type: ignore[return-value]
    return WAITING_INPUT


def is_plan_confirmation(user_message: str) -> bool:
    text = intent_text(user_message)
    if not text:
        return False
    if not _CONFIRM_RE.search(text):
        return False
    if len(text) > 120 and _START_WITHOUT_CONFIRM_RE.search(text):
        return False
    return True


def session_has_result_figures(project_root: Path, storage_slug: str) -> bool:
    """会话 outputspace 是否已有可展示/可改图的结果 PNG（含子目录，不含 merged 目录内源图）。"""
    from web_frontend.backend.image_merge_registry import list_mergeable_images
    from web_frontend.backend.session_storage import session_work_dir

    output_root = session_work_dir(project_root, storage_slug)
    return bool(list_mergeable_images(output_root, limit=1))


def session_has_locked_plan(project_root: Path, storage_slug: str) -> bool:
    """是否已有可执行的锁定计划（analysis_plan.json executable_tasks）。"""
    from web_frontend.backend.agent_a.plan_document import load_executable_tasks
    from web_frontend.backend.session_storage import session_work_dir

    output_root = session_work_dir(project_root, storage_slug)
    return bool(load_executable_tasks(output_root))


def maybe_advance_workflow_for_outputs(
    status: str | None,
    *,
    has_result_figures: bool,
) -> WorkflowStatus | None:
    """已有结果图但状态仍停在规划前阶段时，同步为 COMPLETED 供改图/拼图。"""
    if not has_result_figures:
        return None
    st = normalize_status(status)
    if st in {COMPLETED, REPORTING, EXECUTING}:
        return None
    return COMPLETED


def route_chat_action(
    status: str | None,
    user_message: str,
    *,
    has_result_figures: bool = False,
    has_locked_plan: bool = False,
) -> ChatAction:
    """按会话阶段决定走 A / B / C / 拒绝 / 闲聊。"""
    st = normalize_status(status)
    text = intent_text(user_message)
    intent = classify_frontend_intent(user_message)
    visual = looks_like_c_visual_request(user_message)

    if st == AWAITING_APPROVAL:
        if is_plan_confirmation(user_message):
            return "execute"
        if _START_WITHOUT_CONFIRM_RE.search(text):
            return "refuse_unconfirmed"
        if intent == "c_report":
            return "report"
        if _REVISION_RE.search(text) or _REPLAN_EXPLICIT_RE.search(text):
            return "plan"
        if intent in {"b_analysis", "c_from_results"}:
            return "remind_confirm"
        if looks_like_agent_request(user_message) and not visual:
            if _PLAN_REQUEST_RE.search(text):
                return "remind_confirm"
            return "plan"
        if visual:
            if has_result_figures:
                return "visual"
            return "refuse_visual_early"
        return "chat"

    if visual:
        if st in {COMPLETED, REPORTING} or has_result_figures:
            return "visual"
        return "refuse_visual_early"

    if st in {WAITING_INPUT, PLANNING, FAILED}:
        if is_plan_confirmation(user_message):
            return "chat"
        if intent == "c_report":
            return "report"
        if (
            intent in {"b_analysis", "c_from_results"}
            or looks_like_agent_request(user_message)
            or _PLAN_REQUEST_RE.search(text)
        ):
            return "plan"
        return "chat"

    if st == EXECUTING:
        return "chat"

    if st in {REPORTING, COMPLETED, FAILED}:
        if is_plan_confirmation(user_message) and has_locked_plan:
            return "execute"
        if intent == "b_analysis":
            if B_RERUN_RE.search(text) or _START_WITHOUT_CONFIRM_RE.search(text):
                return "execute"
            if has_locked_plan and _PLAN_REQUEST_RE.search(text):
                return "remind_rerun"
            return "plan"
        if intent == "c_report":
            return "report"
        if intent == "c_from_results":
            if _PLAN_REQUEST_RE.search(text):
                return "plan"
            return "report"
        if _PLAN_REQUEST_RE.search(text):
            return "plan"
        return "chat"

    return "chat"
