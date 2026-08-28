"""工作流编排：确认闸门、计划文档、阶段路由。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.agent_a.plan_document import (
    load_executable_tasks,
    write_analysis_plan,
)
from web_frontend.backend.agent_c.plan_parser import parse_plan
from web_frontend.backend.workflow import (
    AWAITING_APPROVAL,
    COMPLETED,
    WAITING_INPUT,
    is_plan_confirmation,
    route_chat_action,
)


class WorkflowRoutingTests(unittest.TestCase):
    def test_confirm_phrase(self):
        self.assertTrue(is_plan_confirmation("确认计划"))
        self.assertTrue(is_plan_confirmation("按此执行"))
        self.assertFalse(is_plan_confirmation("开始分析"))

    def test_waiting_input_goes_to_plan(self):
        self.assertEqual(
            route_chat_action(WAITING_INPUT, "比较 Control 与 Treatment 的差异代谢物"),
            "plan",
        )

    def test_start_analysis_without_confirm_is_refused(self):
        self.assertEqual(
            route_chat_action(AWAITING_APPROVAL, "开始分析，跑一遍 XCMS"),
            "refuse_unconfirmed",
        )

    def test_confirm_executes(self):
        self.assertEqual(route_chat_action(AWAITING_APPROVAL, "确认计划"), "execute")

    def test_revision_replans(self):
        self.assertEqual(
            route_chat_action(AWAITING_APPROVAL, "第三步改成 MZmine，不要分子网络"),
            "plan",
        )

    def test_visual_only_after_complete(self):
        self.assertEqual(
            route_chat_action(AWAITING_APPROVAL, "把 PCA 标题改成分组比较"),
            "refuse_visual_early",
        )
        self.assertEqual(
            route_chat_action(COMPLETED, "把 PCA 标题改成分组比较"),
            "visual",
        )
        self.assertEqual(
            route_chat_action(
                WAITING_INPUT,
                "把 PCA 标题改成分组比较",
                has_result_figures=True,
            ),
            "visual",
        )

    def test_maybe_advance_workflow_for_outputs(self):
        from web_frontend.backend.workflow import maybe_advance_workflow_for_outputs

        self.assertEqual(
            maybe_advance_workflow_for_outputs(WAITING_INPUT, has_result_figures=True),
            COMPLETED,
        )
        self.assertIsNone(
            maybe_advance_workflow_for_outputs(COMPLETED, has_result_figures=True),
        )

    def test_completed_report_is_c(self):
        self.assertEqual(route_chat_action(COMPLETED, "写报告"), "report")

    def test_completed_rerun_executes_b(self):
        self.assertEqual(route_chat_action(COMPLETED, "我想重新进行分析"), "execute")
        self.assertEqual(route_chat_action(COMPLETED, "重跑一遍 mixOmics"), "execute")

    def test_awaiting_approval_repeat_analysis_reminds_not_replans(self):
        msg = (
            "请帮我做非靶向 LC-MS 代谢组学分析，比较 Control 与 Treatment 两组差异。"
            "XCMS 预处理；mixOmics PCA 与火山图"
        )
        self.assertEqual(route_chat_action(AWAITING_APPROVAL, msg), "remind_confirm")

    def test_awaiting_approval_revision_still_replans(self):
        self.assertEqual(
            route_chat_action(AWAITING_APPROVAL, "第三步改成 MZmine，不要分子网络"),
            "plan",
        )

    def test_completed_confirm_with_locked_plan_executes(self):
        self.assertEqual(
            route_chat_action(COMPLETED, "确认计划", has_locked_plan=True),
            "execute",
        )

    def test_completed_full_analysis_with_locked_plan_reminds_rerun(self):
        msg = (
            "请帮我做非靶向 LC-MS 代谢组学分析，比较 Control 与 Treatment 两组差异。"
            "XCMS 预处理；mixOmics PCA 与火山图"
        )
        self.assertEqual(
            route_chat_action(COMPLETED, msg, has_locked_plan=True),
            "remind_rerun",
        )

    def test_completed_full_analysis_request_replans_not_report(self):
        msg = (
            "请帮我做非靶向 LC-MS 代谢组学分析，比较 Control 与 Treatment 两组差异。"
            "XCMS 预处理；mixOmics PCA 与火山图"
        )
        self.assertEqual(route_chat_action(COMPLETED, msg), "plan")

    def test_completed_plot_only_still_reports(self):
        self.assertEqual(route_chat_action(COMPLETED, "按方案出图"), "report")
        self.assertEqual(route_chat_action(COMPLETED, "画一张火山图"), "report")

    def test_compute_beats_from_results_intent(self):
        from web_frontend.backend.agent_intent import classify_frontend_intent

        intent = classify_frontend_intent(
            "重新进行分析，比较 Control 与 Treatment，跑 mixOmics 火山图"
        )
        self.assertEqual(intent, "b_analysis")

    def test_deep_report_routes_to_c_not_plan(self):
        self.assertEqual(
            route_chat_action(WAITING_INPUT, "写深度报告并分析科研意义"),
            "report",
        )
        self.assertEqual(
            route_chat_action(AWAITING_APPROVAL, "写深度报告并分析科研意义"),
            "report",
        )

    def test_deep_report_routes_to_c_not_plan(self):
        self.assertEqual(
            route_chat_action(WAITING_INPUT, "写深度报告并分析科研意义"),
            "report",
        )
        self.assertEqual(
            route_chat_action(AWAITING_APPROVAL, "写深度报告并分析科研意义"),
            "report",
        )

    def test_write_plan_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_analysis_plan(
                root,
                objective="找差异代谢物",
                data_understanding="10 个 mzML",
                tasks=[
                    "Use data_preprocessing_xcms to pick peaks",
                    "Use statistical_analysis_mixomics for PCA and volcano",
                    "Use plot_edit to change the title",
                ],
            )
            self.assertTrue((root / "analysis_plan.md").is_file())
            exec_tasks = payload["executable_tasks"]
            self.assertTrue(any("xcms" in t.lower() for t in exec_tasks))
            self.assertFalse(any("plot_edit" in t.lower() for t in exec_tasks))
            self.assertEqual(load_executable_tasks(root), exec_tasks)
            md = (root / "analysis_plan.md").read_text(encoding="utf-8")
            for heading in (
                "# Objective",
                "# Data understanding",
                "# Workflow",
                "# Tools required",
                "# Expected results",
                "# Required visualization",
                "# Interpretation guideline",
                "# Reporting plan",
            ):
                self.assertIn(heading, md)
            self.assertIn("Panel A Purpose", md)
            self.assertIn("Step 1", md)
            self.assertIn("data_preprocessing_xcms", md)
            plan = parse_plan(root / "analysis_plan.json")
            self.assertIn("差异代谢物", plan["objective"])
            types = {f["plot_type"] for f in plan["required_visualization"]}
            self.assertTrue({"pca", "volcano"} & types)
            pca = next(f for f in plan["required_visualization"] if f["plot_type"] == "pca")
            self.assertTrue(pca.get("theme"))
            self.assertTrue(pca.get("panels"))
            self.assertIn("purpose", pca["panels"][0])


if __name__ == "__main__":
    unittest.main()
