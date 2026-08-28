"""LLM 聊天路由 + 规则兜底单测。"""
from __future__ import annotations

import unittest

from web_frontend.backend.chat_router import (
    CONFIDENCE_FALLBACK,
    RouterResult,
    adjudicate_router_suggestion,
    parse_router_response,
    resolve_chat_action,
)
from web_frontend.backend.workflow import AWAITING_APPROVAL, COMPLETED, route_chat_action


class ChatRouterTests(unittest.TestCase):
    def test_parse_router_response(self) -> None:
        raw = """{"suggested_action":"report","intent_summary":"写报告","confidence":0.91}"""
        r = parse_router_response(raw)
        self.assertIsNotNone(r)
        assert r is not None
        self.assertEqual(r.suggested_action, "report")
        self.assertAlmostEqual(r.confidence, 0.91)

    def test_low_confidence_falls_back_to_rules(self) -> None:
        rule = route_chat_action(COMPLETED, "写报告")
        router = RouterResult(suggested_action="plan", confidence=0.5, intent_summary="x")
        action, clarify = adjudicate_router_suggestion(
            router,
            rule_action=rule,
            workflow_status=COMPLETED,
            user_message="写报告",
            has_result_figures=True,
        )
        self.assertEqual(action, rule)
        self.assertIsNone(clarify)
        self.assertLess(0.5, CONFIDENCE_FALLBACK)

    def test_execute_blocked_at_awaiting_approval(self) -> None:
        router = RouterResult(
            suggested_action="execute",
            confidence=0.95,
            intent_summary="执行",
        )
        action, _ = adjudicate_router_suggestion(
            router,
            rule_action="plan",
            workflow_status=AWAITING_APPROVAL,
            user_message="开始跑 XCMS",
            has_result_figures=False,
        )
        self.assertEqual(action, "refuse_unconfirmed")

    def test_execute_allowed_on_confirm(self) -> None:
        router = RouterResult(
            suggested_action="execute",
            confidence=0.95,
            intent_summary="确认",
        )
        action, _ = adjudicate_router_suggestion(
            router,
            rule_action="execute",
            workflow_status=AWAITING_APPROVAL,
            user_message="确认计划",
            has_result_figures=False,
        )
        self.assertEqual(action, "execute")

    def test_rerun_rule_wins_over_llm_report(self) -> None:
        router = RouterResult(
            suggested_action="report",
            confidence=0.92,
            intent_summary="写报告",
        )
        action, _ = adjudicate_router_suggestion(
            router,
            rule_action="execute",
            workflow_status=COMPLETED,
            user_message="重新进行分析",
            has_result_figures=True,
        )
        self.assertEqual(action, "execute")

    def test_needs_clarification(self) -> None:
        router = RouterResult(
            suggested_action="chat",
            confidence=0.75,
            needs_clarification=True,
            clarification_prompt="你要 B 还是 C？",
        )
        action, msg = adjudicate_router_suggestion(
            router,
            rule_action="chat",
            workflow_status=COMPLETED,
            user_message="帮我处理一下结果",
            has_result_figures=True,
        )
        self.assertEqual(action, "clarify")
        self.assertIn("B 还是 C", msg or "")

    def test_resolve_without_llm_matches_rules(self) -> None:
        action, clarify, meta = resolve_chat_action(
            COMPLETED,
            "写报告",
            has_result_figures=True,
            use_llm_router=False,
        )
        self.assertEqual(action, route_chat_action(COMPLETED, "写报告", has_result_figures=True))
        self.assertIsNone(clarify)
        self.assertFalse(meta["router_used"])

    def test_high_confidence_report_overrides_ambiguous_rule(self) -> None:
        router = RouterResult(
            suggested_action="report",
            confidence=0.88,
            intent_summary="生成分析报告",
        )
        action, clarify, meta = resolve_chat_action(
            COMPLETED,
            "帮我整理一下结果",
            has_result_figures=True,
            router_result=router,
            use_llm_router=True,
        )
        self.assertEqual(action, "report")
        self.assertIsNone(clarify)
        self.assertEqual(meta["final_action"], "report")


if __name__ == "__main__":
    unittest.main()
