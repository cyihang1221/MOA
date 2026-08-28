"""LLM 语义路由 + 规则兜底：决定 chat/plan/execute/report/visual/clarify。"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from web_frontend.backend.agent_intent import (
    B_RERUN_RE,
    classify_frontend_intent,
    intent_text,
    looks_like_c_visual_request,
)
from web_frontend.backend.json_parse import extract_first_json_object
from web_frontend.backend.workflow import (
    AWAITING_APPROVAL,
    COMPLETED,
    EXECUTING,
    FAILED,
    PLANNING,
    REPORTING,
    WAITING_INPUT,
    ChatAction,
    is_plan_confirmation,
    normalize_status,
    route_chat_action,
)

RouterAction = Literal["plan", "execute", "report", "visual", "chat"]

CONFIDENCE_FALLBACK = 0.7
CONFIDENCE_CLARIFY_MAX = 0.85

DEFAULT_CLARIFY_ZH = (
    "我不太确定您的目标。您是希望：\n"
    "① **重新跑分析**（Agent B，如 XCMS / mixOmics）\n"
    "② **写/更新报告或按方案出图**（Agent C）\n"
    "③ **改图/拼图**（已完成分析后）\n"
    "请用一句话说明，例如「重跑 mixOmics」或「写报告」。"
)

ROUTER_SYSTEM = """你是 MassAgent 网页编排器的路由助手。根据用户消息和会话上下文，建议下一步应进入的动作。

动作含义（只输出 JSON，不要 markdown 代码块）：
- plan：需要 Agent A 制定/修订 analysis_plan（新分析诉求、改方案、尚未确认计划）
- execute：启动 Agent B 执行 MCP 分析（用户已确认计划，或明确「重新分析/重跑」且上下文允许）
- report：Agent C 按已有结果出图/写 final_report（写报告、深度解读、按方案出图）
- visual：改图/拼图/改 merged 图（仅当已有结果图或会话已完成）
- chat：纯闲聊、概念问答、与流水线无关

硬性提示：
1. workflow_status=AWAITING_APPROVAL 时，除非用户明确「确认计划」，否则不要 suggested_action=execute。
2. workflow_status=EXECUTING 时，建议 chat（等待执行结束）。
3. 用户同时像「分析」又像「写报告」且语义模糊时，needs_clarification=true 并给出简短 clarification_prompt。
4. confidence 0~1：非常确定 ≥0.85；模糊 0.5~0.7；不确定 <0.5。

输出 JSON 结构：
{
  "suggested_action": "plan|execute|report|visual|chat",
  "intent_summary": "一句话概括用户意图",
  "confidence": 0.0,
  "needs_clarification": false,
  "clarification_prompt": ""
}
"""


@dataclass
class RouterResult:
    suggested_action: RouterAction = "chat"
    intent_summary: str = ""
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_prompt: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RouterResult:
        action = str(data.get("suggested_action") or "chat").strip().lower()
        if action not in {"plan", "execute", "report", "visual", "chat"}:
            action = "chat"
        try:
            conf = float(data.get("confidence") or 0)
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        return cls(
            suggested_action=action,  # type: ignore[arg-type]
            intent_summary=str(data.get("intent_summary") or "").strip(),
            confidence=conf,
            needs_clarification=bool(data.get("needs_clarification")),
            clarification_prompt=str(data.get("clarification_prompt") or "").strip(),
        )


@dataclass
class SessionRouterContext:
    workflow_status: str = WAITING_INPUT
    has_result_figures: bool = False
    has_analysis_plan: bool = False
    n_result_files: int = 0
    plottable_types: list[str] = field(default_factory=list)
    frontend_intent: str = "chat"

    def to_prompt_block(self) -> str:
        plottable = ", ".join(self.plottable_types[:8]) or "无"
        return (
            f"workflow_status={self.workflow_status}\n"
            f"has_analysis_plan={self.has_analysis_plan}\n"
            f"has_result_figures={self.has_result_figures}\n"
            f"n_result_files={self.n_result_files}\n"
            f"plottable_types={plottable}\n"
            f"regex_intent={self.frontend_intent}\n"
        )


def llm_router_enabled() -> bool:
    return os.getenv("MASSAGENT_USE_LLM_ROUTER", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def build_session_router_context(
    *,
    workflow_status: str | None,
    user_message: str,
    has_result_figures: bool,
    project_root: Any,
    storage_slug: str,
) -> SessionRouterContext:
    """汇总路由 LLM 需要的会话事实（不编造）。"""
    from pathlib import Path

    from web_frontend.backend.agent_c.results_inventory import inventory_results
    from web_frontend.backend.agent_c.session_chat import find_session_plan
    from web_frontend.backend.session_storage import session_upload_dir, session_work_dir

    root = Path(project_root)
    output_root = session_work_dir(root, storage_slug)
    upload_root = session_upload_dir(root, storage_slug)
    plan = find_session_plan(output_root, upload_root)
    inv = inventory_results(output_root) if output_root.is_dir() else {}
    return SessionRouterContext(
        workflow_status=normalize_status(workflow_status),
        has_result_figures=has_result_figures,
        has_analysis_plan=plan is not None,
        n_result_files=len(inv.get("files") or []),
        plottable_types=[
            str(p.get("plot_type") or "")
            for p in (inv.get("plottable") or [])
            if p.get("plot_type")
        ],
        frontend_intent=classify_frontend_intent(user_message),
    )


def parse_router_response(raw: str) -> RouterResult | None:
    data = extract_first_json_object(raw or "")
    if not data.get("suggested_action"):
        return None
    return RouterResult.from_dict(data)


def suggest_action_with_llm(
    *,
    user_message: str,
    context: SessionRouterContext,
    llm_client: Any,
) -> RouterResult | None:
    """调用轻量 LLM 得到路由建议；失败返回 None。"""
    text = intent_text(user_message)
    if not text:
        return None
    user_block = (
        "【会话上下文】\n"
        + context.to_prompt_block()
        + "\n【用户消息】\n"
        + text[:2000]
    )
    messages = [
        {"role": "system", "content": ROUTER_SYSTEM},
        {"role": "user", "content": user_block},
    ]
    raw = llm_client.think_complete(messages, temperature=0)
    return parse_router_response(str(raw or ""))


def _start_without_confirm(text: str) -> bool:
    from web_frontend.backend.workflow import _START_WITHOUT_CONFIRM_RE

    return bool(_START_WITHOUT_CONFIRM_RE.search(text))


def context_allows_report_early(
    st: str,
    has_result_figures: bool,
    user_message: str,
) -> bool:
    """尚无完整流程但已有结果文件时允许 C 写报告。"""
    if has_result_figures or st in {COMPLETED, REPORTING, AWAITING_APPROVAL}:
        return True
    intent = classify_frontend_intent(user_message)
    return intent == "c_report"


def adjudicate_router_suggestion(
    router: RouterResult | None,
    *,
    rule_action: ChatAction,
    workflow_status: str | None,
    user_message: str,
    has_result_figures: bool,
) -> tuple[ChatAction, str | None]:
    """LLM 建议经状态机硬规则裁决；返回 (action, clarify_message)。"""
    if router is None:
        return rule_action, None

    text = intent_text(user_message)

    # 安全网：规则层已明确的硬闸门，LLM 不可覆盖
    if rule_action in {
        "refuse_unconfirmed",
        "refuse_visual_early",
        "remind_confirm",
        "remind_rerun",
    }:
        return rule_action, None
    if rule_action == "execute" and (
        B_RERUN_RE.search(text)
        or _start_without_confirm(text)
        or is_plan_confirmation(user_message)
    ):
        return "execute", None

    if router.confidence < CONFIDENCE_FALLBACK:
        return rule_action, None

    if router.needs_clarification and router.confidence < CONFIDENCE_CLARIFY_MAX:
        prompt = router.clarification_prompt.strip() or DEFAULT_CLARIFY_ZH
        return "clarify", prompt

    st = normalize_status(workflow_status)
    proposed = router.suggested_action

    if proposed == "execute":
        if st == AWAITING_APPROVAL:
            if is_plan_confirmation(user_message):
                return "execute", None
            return "refuse_unconfirmed", None
        if st == EXECUTING:
            return "chat", None
        if st in {WAITING_INPUT, PLANNING}:
            return "refuse_unconfirmed", None
        if st in {COMPLETED, FAILED, REPORTING}:
            if (
                B_RERUN_RE.search(text)
                or _start_without_confirm(text)
                or is_plan_confirmation(user_message)
            ):
                return "execute", None
            return rule_action, None
        return rule_action, None

    if proposed == "visual":
        if looks_like_c_visual_request(user_message):
            if has_result_figures or st in {COMPLETED, REPORTING}:
                return "visual", None
            return "refuse_visual_early", None
        return rule_action, None

    if proposed == "report":
        if st == EXECUTING:
            return "chat", None
        if st in {WAITING_INPUT, PLANNING, FAILED}:
            if context_allows_report_early(st, has_result_figures, user_message):
                return "report", None
            return rule_action, None
        return "report", None

    if proposed == "plan":
        if st == EXECUTING:
            return "chat", None
        return "plan", None

    if proposed == "chat":
        return "chat", None

    return rule_action, None


def resolve_chat_action(
    workflow_status: str | None,
    user_message: str,
    *,
    has_result_figures: bool = False,
    has_locked_plan: bool = False,
    project_root: Any = None,
    storage_slug: str = "",
    llm_client: Any | None = None,
    router_result: RouterResult | None = None,
    use_llm_router: bool | None = None,
) -> tuple[ChatAction, str | None, dict[str, Any]]:
    """规则路由 + 可选 LLM 路由；返回 (action, clarify_text, debug_meta)。"""
    rule_action = route_chat_action(
        workflow_status,
        user_message,
        has_result_figures=has_result_figures,
        has_locked_plan=has_locked_plan,
    )
    meta: dict[str, Any] = {
        "rule_action": rule_action,
        "router_used": False,
        "final_action": rule_action,
    }

    enabled = llm_router_enabled() if use_llm_router is None else bool(use_llm_router)
    if not enabled:
        return rule_action, None, meta

    router = router_result
    if router is None and llm_client is not None and project_root is not None and storage_slug:
        ctx = build_session_router_context(
            workflow_status=workflow_status,
            user_message=user_message,
            has_result_figures=has_result_figures,
            project_root=project_root,
            storage_slug=storage_slug,
        )
        meta["router_context"] = asdict(ctx)
        try:
            router = suggest_action_with_llm(
                user_message=user_message,
                context=ctx,
                llm_client=llm_client,
            )
            meta["router_used"] = True
        except Exception as exc:
            meta["router_error"] = str(exc)
            return rule_action, None, meta

    if router:
        meta["router_suggestion"] = asdict(router)

    action, clarify = adjudicate_router_suggestion(
        router,
        rule_action=rule_action,
        workflow_status=workflow_status,
        user_message=user_message,
        has_result_figures=has_result_figures,
    )
    meta["final_action"] = action
    return action, clarify, meta
