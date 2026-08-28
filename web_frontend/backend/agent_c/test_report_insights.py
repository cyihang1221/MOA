"""Agent C 报告深度解读单测（不调用真实 LLM）。"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from web_frontend.backend.agent_c.report_builder import (
    _format_file_size,
    build_report_markdown,
    merge_supplement_figures,
    prepare_report_figures,
)
from web_frontend.backend.agent_c.report_insights import (
    collect_report_context,
    format_insights_markdown,
    generate_report_insights,
    merge_insights_into_report,
    should_enable_insights,
)
from web_frontend.backend.agent_c.session_chat import _use_report_insights, _wants_deep_report


class ReportInsightsTest(unittest.TestCase):
    def test_should_enable_insights(self) -> None:
        self.assertTrue(should_enable_insights(use_llm=True, repro_recipe_id=None))
        self.assertFalse(should_enable_insights(use_llm=True, repro_recipe_id="duyun_maojian_fochx_2026"))
        self.assertFalse(should_enable_insights(use_llm=False, repro_recipe_id=None))

    def test_wants_deep_report_trigger(self) -> None:
        self.assertTrue(_wants_deep_report("请写深度报告并分析科研意义"))
        self.assertFalse(_wants_deep_report("按方案出图"))

    def test_use_report_insights_on_c_report(self) -> None:
        self.assertTrue(_use_report_insights("写报告", "c_report"))
        self.assertFalse(_use_report_insights("按方案出图", "c_from_results"))

    def test_format_file_size(self) -> None:
        self.assertEqual(_format_file_size(500), "500 B")
        self.assertEqual(_format_file_size(12710), "12.4 KB")
        self.assertEqual(_format_file_size(1024**2), "1.0 MB")

    def test_merge_supplement_figures_unified_numbering(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stat = root / "statistical_results"
            stat.mkdir()
            (stat / "pca_plot.png").write_bytes(b"1")
            (stat / "volcano_plot.png").write_bytes(b"2")
            figures = [
                {
                    "figure_id": "Figure 1",
                    "png": str(stat / "pca_plot.png"),
                    "status": "copied_existing",
                    "caption": "PCA",
                }
            ]
            extra = [{"rel": "statistical_results/volcano_plot.png", "title": "volcano plot"}]
            merged = merge_supplement_figures(figures, extra, results_dir=root)
            self.assertEqual(len(merged), 2)
            self.assertEqual(merged[1]["figure_id"], "Figure 2")

    def test_prepare_report_figures_renumbers_and_splits_incomplete(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stat = root / "statistical_results"
            stat.mkdir()
            (stat / "pca_plot.png").write_bytes(b"1")
            (stat / "volcano_plot.png").write_bytes(b"2")
            figures = [
                {
                    "figure_id": "Figure 1",
                    "plot_type": "pca",
                    "png": str(stat / "pca_plot.png"),
                    "status": "copied_existing",
                },
                {
                    "figure_id": "Figure 2",
                    "plot_type": "annotation_propagation",
                    "status": "missing_data",
                    "missing_reason": "缺少 enhanced_nodes.csv",
                },
                {
                    "figure_id": "Figure 3",
                    "plot_type": "volcano",
                    "png": str(stat / "volcano_plot.png"),
                    "status": "copied_existing",
                },
            ]
            extra = [{"rel": "statistical_results/volcano_plot.png", "title": "volcano plot"}]
            complete, incomplete = prepare_report_figures(
                figures,
                supplement_existing=extra,
                results_dir=root,
                supplement_mode="none",
            )
            self.assertEqual(len(complete), 2)
            self.assertEqual(complete[0]["figure_id"], "Figure 1")
            self.assertEqual(complete[1]["figure_id"], "Figure 2")
            self.assertEqual(len(incomplete), 1)
            self.assertEqual(incomplete[0].get("plan_figure_id"), "Figure 2")

            md = build_report_markdown(
                plan={"objective": "test", "workflow": []},
                inventory={"results_dir": str(root), "files": []},
                figures=complete,
                incomplete_figures=incomplete,
                language="zh",
            )
            self.assertIn("### 未完成图表（方案）", md)
            self.assertIn("enhanced_nodes.csv", md)
            fig_section = md.split("## 图表")[1].split("## 方法")[0]
            self.assertEqual(fig_section.count("### Figure"), 2)
            self.assertNotIn("enhanced_nodes", fig_section)

    def test_missing_data_not_promoted_by_orphan_png(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stat = root / "molecular_network_results" / "fbmn"
            stat.mkdir(parents=True)
            (stat / "fbmn_group_intensity.png").write_bytes(b"orphan")
            kegg_png = root / "kegg.png"
            kegg_png.write_bytes(b"1")
            figures = [
                {
                    "figure_id": "Figure 2",
                    "plot_type": "fbmn_group_intensity",
                    "status": "missing_data",
                    "missing_reason": "缺少 fbmn_group_intensity.csv",
                },
                {
                    "figure_id": "Figure 3",
                    "plot_type": "kegg_bubble",
                    "png": str(kegg_png),
                    "status": "copied_existing",
                },
            ]
            complete, incomplete = prepare_report_figures(figures, results_dir=root)
            self.assertEqual(len(complete), 1)
            self.assertEqual(complete[0]["figure_id"], "Figure 1")
            self.assertEqual(len(incomplete), 1)
            self.assertEqual(incomplete[0].get("plan_figure_id"), "Figure 2")

    def test_report_appendix_file_size_units(self) -> None:
        md = build_report_markdown(
            plan={"objective": "test", "workflow": []},
            inventory={
                "results_dir": "/x",
                "files": [{"rel": "analysis_plan.json", "size": 12710}],
            },
            figures=[],
            language="zh",
        )
        self.assertIn("12.4 KB", md)
        self.assertNotIn("| 12710 |", md)

    def test_collect_report_context(self) -> None:
        plan = {
            "objective": "比较两组差异代谢物",
            "workflow": [{"stage": "统计", "task": "mixOmics"}],
        }
        inventory = {
            "results_dir": "/tmp/out",
            "files": [{"name": "volcano_results.csv", "rel": "volcano_results.csv", "size": 100}],
            "plottable": [{"plot_type": "volcano"}],
            "standard_files": {"statistics.csv": "volcano_results.csv"},
        }
        figures = [
            {
                "figure_id": "Figure 1",
                "plot_type": "volcano",
                "status": "rendered",
                "facts": ["火山表 120 行"],
            }
        ]
        ctx = collect_report_context(plan=plan, inventory=inventory, figures=figures)
        self.assertIn("差异代谢物", ctx["objective"])
        self.assertEqual(ctx["figures"][0]["plot_type"], "volcano")

    def test_format_and_merge_insights(self) -> None:
        insights = {
            "summary": "总体概述。",
            "key_findings": ["发现 A", "发现 B"],
            "analysis_role": "用于验证分组差异。",
            "scientific_value": "提示潜在标志物。",
            "application_value": "暂无临床转化。",
            "limitations": ["样本量小"],
            "next_steps": ["扩大队列"],
        }
        md = format_insights_markdown(insights, zh=True)
        self.assertIn("结果解读与科研意义", md)
        self.assertNotIn("Demo", md)
        self.assertIn("主要发现", md)

        base = build_report_markdown(
            plan={"objective": "test", "workflow": []},
            inventory={"results_dir": "/x", "files": []},
            figures=[],
            language="zh",
        )
        merged = merge_insights_into_report(base, md, zh=True)
        self.assertIn("结果解读与科研意义", merged)
        self.assertIn("## 科学解读", merged)

    def test_generate_with_mock_llm(self) -> None:
        mock = MagicMock()
        mock.think_complete.return_value = """{
            "summary": "Mock 总结",
            "key_findings": ["k1"],
            "analysis_role": "role",
            "scientific_value": "sci",
            "application_value": "app",
            "limitations": ["lim"],
            "next_steps": ["next"]
        }"""
        out = generate_report_insights(
            plan={"objective": "o"},
            inventory={"results_dir": str(Path.cwd()), "files": []},
            figures=[],
            llm_client=mock,
        )
        self.assertIn("Mock 总结", out.get("markdown") or "")
        self.assertNotIn("error", out)


if __name__ == "__main__":
    unittest.main()
