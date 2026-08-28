"""Agent C 接口：解析方案、清点结果、配图（不依赖 LLM / vl-convert）。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.agent_c.figure_pipeline import match_figures
from web_frontend.backend.agent_c.plan_parser import parse_plan, resolve_plot_type
from web_frontend.backend.agent_c.report_builder import build_report_markdown
from web_frontend.backend.agent_c.results_inventory import inventory_results
from web_frontend.backend.agent_c.session_chat import stream_session_agent_c
from web_frontend.backend.agent_intent import (
    classify_frontend_intent,
    looks_like_agent_request,
)


SAMPLE_MD = """# Objective
比较 Control 与 Treatment 的差异代谢物。

# Data understanding
10 个 mzML 样本，两组各 5 重复。

# Workflow
1. 预处理
2. 统计

# Required visualization

| 图号 | 图型 | 用途 | 预期观察 |
|------|------|------|----------|
| Figure 1 | PCA | 样本分离 | 两组在 PC1 上分开 |
| Figure 2 | 火山图 | 差异显著性 | 显著上调/下调点分布 |

# Interpretation guideline
PCA 分离只说明组间方差结构，不单独等于生物标志物。

# Reporting plan
中文；结论必须引用图号。
"""


class AgentCInterfaceTests(unittest.TestCase):
    def test_resolve_plot_type(self):
        self.assertEqual(resolve_plot_type("PCA 得分图"), "pca")
        self.assertEqual(resolve_plot_type("火山图"), "volcano")
        self.assertEqual(resolve_plot_type("volcano_plot"), "volcano")
        self.assertEqual(resolve_plot_type("kegg 气泡"), "kegg_bubble")

    def test_parse_markdown_plan(self):
        plan = parse_plan(SAMPLE_MD)
        self.assertIn("差异代谢物", plan["objective"])
        figs = plan["required_visualization"]
        self.assertEqual(len(figs), 2)
        self.assertEqual(figs[0]["plot_type"], "pca")
        self.assertEqual(figs[1]["plot_type"], "volcano")
        self.assertEqual(figs[0]["expected_observation"], "两组在 PC1 上分开")

    def test_parse_canonical_json(self):
        plan = parse_plan(
            {
                "objective": "找差异代谢物",
                "required_visualization": [
                    {"figure_id": "Figure 1", "plot_type": "pca", "theme": "分组分离"}
                ],
                "interpretation_guideline": "勿过读",
                "reporting_plan": {"language": "zh"},
            }
        )
        self.assertEqual(plan["required_visualization"][0]["plot_type"], "pca")
        self.assertEqual(plan["required_visualization"][0]["stem"], "pca_plot")

    def test_parse_massomics_plan_document(self):
        plan = parse_plan(
            {
                "goal": "比较两组差异代谢物",
                "steps": [
                    {
                        "step_number": 1,
                        "description": "XCMS 预处理",
                        "input_filename": "mzML/",
                        "output_filename": "peak_matrix.csv",
                        "tools": ["data_preprocessing_xcms"],
                        "expected_output": "峰表",
                    },
                    {
                        "step_number": 2,
                        "description": "mixOmics 统计",
                        "input_filename": "peak_matrix.csv",
                        "output_filename": "pca_scores.csv volcano_results.csv",
                        "tools": ["statistical_analysis_mixomics"],
                        "expected_output": "PCA 与火山图数据",
                    },
                ],
                "visualizations": [
                    {
                        "name": "PCA 分组",
                        "chart_type": "PCA得分图",
                        "source_step": 2,
                        "description": "看两组是否分离",
                    },
                    {
                        "name": "火山图",
                        "chart_type": "火山图",
                        "source_step": 2,
                        "description": "显著差异特征",
                    },
                ],
                "interpretations": [
                    {"target": "pca_scores.csv", "criteria": "同组聚集", "note": "不等于生物标志物"}
                ],
                "report": {
                    "audience": "课题组",
                    "sections": ["引言", "方法", "结果"],
                    "decision_to_report": "从火山图导出候选名单",
                },
                "risks": ["MS2 不足"],
                "assumptions": ["10 个 mzML"],
            }
        )
        self.assertEqual(plan["plan_format"], "massomics")
        self.assertIn("差异代谢物", plan["objective"])
        types = {f["plot_type"] for f in plan["required_visualization"]}
        self.assertIn("pca", types)
        self.assertIn("volcano", types)
        pca = next(f for f in plan["required_visualization"] if f["plot_type"] == "pca")
        self.assertEqual(pca["source_step"], 2)
        self.assertIn("pca_scores.csv", pca.get("source_files") or [])
        self.assertTrue(plan["interpretations"])
        self.assertIn("同组聚集", plan["interpretation_guideline"])
        self.assertEqual(plan["reporting_plan"]["audience"], "课题组")

    def test_parse_massomics_markdown(self):
        md = """# 代谢组学分析计划

## 分析目标

比较 Control 与 Treatment。

## 分析工作流

### Step 1: XCMS 预处理

- **输入**: `mzML/`
- **输出**: `peak_matrix.csv`
- **工具**: data_preprocessing_xcms
- **预期结果**: 峰表

### Step 2: 多元统计

- **输入**: `peak_matrix.csv`
- **输出**: `pca_scores.csv`
- **工具**: statistical_analysis_mixomics
- **预期结果**: PCA 坐标

## 可视化方案

- **PCA 分组** (来源 Step2): PCA得分图 — 两组分离

## 结果解读要点

- **pca_scores.csv**: 同组宜聚集 | 解读: 不等于标志物

## 报告撰写方案

- **目标读者**: 课题组
"""
        plan = parse_plan(md)
        self.assertIn("Control", plan["objective"])
        self.assertTrue(any(f.get("plot_type") == "pca" for f in plan["required_visualization"]))
        self.assertIn("同组宜聚集", plan["interpretation_guideline"])

    def test_parse_legacy_stage_list(self):
        plan = parse_plan(
            [
                {
                    "stage": "Stage 3",
                    "task": "use statistical_analysis_mixomics for PCA and volcano",
                    "expected_output": "pca_scores.csv volcano_results.csv",
                }
            ]
        )
        types = {f["plot_type"] for f in plan["required_visualization"]}
        self.assertIn("pca", types)
        self.assertIn("volcano", types)

    def test_inventory_and_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pca_scores.csv").write_text("sample,PC1,PC2\nA,0.1,0.2\n", encoding="utf-8")
            (root / "volcano_results.csv").write_text(
                "feature,log2FC,neglog10p,pvalue\nx,1.2,3.0,0.001\n",
                encoding="utf-8",
            )
            inv = inventory_results(root)
            self.assertTrue(inv["exists"])
            types = {p["plot_type"] for p in inv["plottable"]}
            self.assertIn("pca", types)
            self.assertIn("volcano", types)

            plan = parse_plan(SAMPLE_MD)
            jobs = match_figures(plan, inv, figure_mode="plan")
            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs[0]["status"], "ready")
            self.assertEqual(jobs[1]["status"], "ready")

            md = build_report_markdown(plan=plan, inventory=inv, figures=jobs)
            self.assertIn("Figure 1", md)
            self.assertIn("方案预期", md)

    def test_missing_data_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            inv = inventory_results(tmp)
            plan = parse_plan(SAMPLE_MD)
            jobs = match_figures(plan, inv, figure_mode="plan")
            self.assertEqual(jobs[0]["status"], "missing_data")
            self.assertTrue(jobs[0].get("missing_reason"))

    def test_markdown_to_pdf_embeds_image(self):
        from PIL import Image

        from web_frontend.backend.agent_c.pdf_export import markdown_file_to_pdf

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            png = root / "fig.png"
            Image.new("RGB", (48, 24), (180, 60, 60)).save(png)
            md = root / "final_report.md"
            md.write_text(
                "# 分析报告\n\n引言：差异代谢物。\n\n![fig](fig.png)\n",
                encoding="utf-8",
            )
            pdf = markdown_file_to_pdf(md)
            self.assertTrue(pdf.is_file())
            self.assertGreater(pdf.stat().st_size, 200)


class FrontendIntentTests(unittest.TestCase):
    def test_plot_edit_is_c_visual(self):
        self.assertEqual(
            classify_frontend_intent("把 PCA 标题改成分组比较"),
            "c_visual",
        )

    def test_write_report_is_c_report(self):
        self.assertEqual(classify_frontend_intent("写报告"), "c_report")
        self.assertEqual(classify_frontend_intent("按方案出图"), "c_report")
        self.assertEqual(
            classify_frontend_intent("写深度报告并分析科研意义"),
            "c_report",
        )

    def test_pca_from_results(self):
        self.assertEqual(classify_frontend_intent("做 PCA"), "c_from_results")
        self.assertEqual(classify_frontend_intent("画一张火山图"), "c_from_results")

    def test_xcms_and_start_analysis_are_b(self):
        self.assertEqual(classify_frontend_intent("跑 XCMS"), "b_analysis")
        self.assertEqual(classify_frontend_intent("开始分析"), "b_analysis")
        self.assertEqual(classify_frontend_intent("峰检测并对齐"), "b_analysis")

    def test_upload_alone_is_not_agent(self):
        msg = (
            "已上传文件到本会话。本前端是 Agent C，只消费已有结果。\n\n"
            "[已上传附件]\n- sample.raw\n\n"
            "请补充你要对结果做什么；质谱计算请交给 Agent B。"
        )
        self.assertEqual(classify_frontend_intent(msg), "chat")
        self.assertFalse(looks_like_agent_request(msg))
        self.assertFalse(looks_like_agent_request("[已上传附件]\n- a.csv"))
        self.assertEqual(
            classify_frontend_intent("跑 XCMS\n\n[已上传附件]\n- sample.raw"),
            "b_analysis",
        )

    def test_b_analysis_handoff_even_if_old_pca_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slug = "sess1"
            out = root / "outputspace" / slug
            out.mkdir(parents=True)
            (out / "pca_scores.csv").write_text(
                "sample,PC1,PC2\nA,0.1,0.2\n", encoding="utf-8"
            )
            events = list(
                stream_session_agent_c(
                    project_root=root,
                    session_id="sess1",
                    storage_slug=slug,
                    user_message="开始分析，跑一遍 XCMS",
                    intent="b_analysis",
                )
            )
            text = "".join(str(e.get("delta") or "") for e in events)
            self.assertIn("Agent B", text)
            self.assertNotIn("正在渲染图表", text)

    def test_pca_request_without_scores_handoffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slug = "sess2"
            (root / "outputspace" / slug).mkdir(parents=True)
            events = list(
                stream_session_agent_c(
                    project_root=root,
                    session_id="sess2",
                    storage_slug=slug,
                    user_message="做 PCA",
                    intent="c_from_results",
                )
            )
            text = "".join(str(e.get("delta") or "") for e in events)
            self.assertIn("仍缺", text)
            self.assertIn("pca", text.lower())


if __name__ == "__main__":
    unittest.main()
