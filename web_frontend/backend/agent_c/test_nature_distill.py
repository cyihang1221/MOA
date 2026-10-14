"""nature-skills 蒸馏：图注主张、统计缺项、解读边界、投稿导出。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from web_frontend.backend.agent_c.figure_data_narrative import build_figure_data_narrative
from web_frontend.backend.agent_c.figure_ecb import _plan_interpretation_fallback
from web_frontend.backend.agent_c.figure_pipeline import _build_caption, extract_figure_facts
from web_frontend.backend.agent_c.figure_vision import _VISION_SYSTEM
from web_frontend.backend.agent_c.nature_distill import (
    CAPTION_CONTRACT_PROMPT,
    MISSING,
    attach_reporting_checklist,
    evidence_role_from_job,
    figure_claim_from_job,
    kegg_gap_markdown,
    resolve_kegg_status,
    strip_false_enrichment_claims,
)
from web_frontend.backend.agent_c.report_builder import build_report_markdown
from web_frontend.backend.agent_c.report_insights import INSIGHTS_SYSTEM, generate_report_insights


class NatureDistillCaptionTest(unittest.TestCase):
    def test_claim_prefers_purpose_not_expected_observation(self) -> None:
        job = {
            "purpose": "看 BK 与 DY 能否分开",
            "expected_observation": "两组在 PC1 上分开",
            "plot_type": "pca",
        }
        self.assertEqual(figure_claim_from_job(job), "看 BK 与 DY 能否分开")
        self.assertEqual(evidence_role_from_job(job), "质量/整体分离（无监督）")

    def test_caption_marks_claim_and_planned_observation(self) -> None:
        cap = _build_caption(
            {
                "figure_id": "Figure 1",
                "title": "PCA",
                "plot_type": "pca",
                "purpose": "看分组轮廓",
                "expected_observation": "两组在 PC1 上分开",
            },
            ["得分数 12 行"],
            "zh",
        )
        self.assertIn("图件主张（方案，非已证实）：看分组轮廓", cap)
        self.assertIn("方案预期观察：两组在 PC1 上分开", cap)
        self.assertIn("不是已证实结论", cap)
        self.assertIn("不得把分组分离或相关写成机制", cap)
        self.assertEqual(cap.count("目的："), 0)

    def test_volcano_caption_writes_threshold_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "volcano_results.csv").write_text(
                "feature,log2FC,p_value,Significant\n"
                "m1,1.2,0.01,True\n"
                "m2,-0.5,0.2,False\n",
                encoding="utf-8",
            )
            facts = extract_figure_facts("volcano", root)
            cap = _build_caption(
                {
                    "figure_id": "Figure 2",
                    "title": "Volcano",
                    "plot_type": "volcano",
                    "source_files": ["volcano_results.csv"],
                },
                facts,
                "zh",
            )
            self.assertIn("volcano_results.csv", cap)
            self.assertIn("p<0.05", cap)
            self.assertIn("|log2FC|≥1", cap)

    def test_vip_caption_writes_threshold_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vip_scores.csv").write_text(
                "Feature,VIP\na,1.5\nb,0.4\nc,2.1\n",
                encoding="utf-8",
            )
            facts = extract_figure_facts("vip_bar", root)
            cap = _build_caption(
                {
                    "figure_id": "Figure 3",
                    "title": "VIP",
                    "plot_type": "vip_bar",
                    "source_files": ["vip_scores.csv"],
                },
                facts,
                "zh",
            )
            self.assertIn("vip_scores.csv", cap)
            self.assertIn("VIP>1.2", cap)
            self.assertNotIn("VIP>1（", cap)

    def test_volcano_narrative_marks_missing_multiplicity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "volcano_results.csv").write_text(
                "feature,log2FC,p_value,Significant\n"
                "m1,1.2,0.01,True\n"
                "m2,-0.5,0.2,False\n",
                encoding="utf-8",
            )
            narr = build_figure_data_narrative("volcano", root)
            blob = " ".join(narr["bullets"])
            self.assertIn("图注统计：", blob)
            self.assertIn(f"多重校正：{MISSING}", blob)
            self.assertIn("检验：缺", blob)
            self.assertIn("文件来源：volcano_results.csv", blob)
            self.assertIn("p<0.05", blob)
            self.assertEqual(narr["stats"].get("n_features"), 2)

    def test_pca_qc_not_a_treatment(self) -> None:
        out = {"stats": {"n_samples": 10, "groups": {"BK": 4, "DY": 4, "QC": 2}}, "bullets": []}
        attach_reporting_checklist("pca", out)
        blob = " ".join(out["bullets"])
        self.assertIn("QC 是质控", blob)

    def test_insights_and_vision_prompts_bound_mechanism(self) -> None:
        self.assertIn("不得把 PCA/PLS-DA 分离", INSIGHTS_SYSTEM)
        self.assertIn("QC 是质控样本", INSIGHTS_SYSTEM)
        self.assertIn("统计清单", INSIGHTS_SYSTEM)
        self.assertIn("volcano_results.csv", INSIGHTS_SYSTEM)
        self.assertIn("可见分离不等于生物学机制", _VISION_SYSTEM)
        self.assertIn("文件来源", CAPTION_CONTRACT_PROMPT)

    def test_plan_fallback_caveats(self) -> None:
        text = _plan_interpretation_fallback({"purpose": "看分离"}, zh=True)["caveats"]
        self.assertIn("不等于机制", text)

    def test_kegg_missing_report_marks_gap_not_enrichment(self) -> None:
        md = build_report_markdown(
            plan={
                "objective": "通路分析",
                "required_visualization": [
                    {"figure_id": "Figure 4", "plot_type": "kegg_bubble", "title": "KEGG"}
                ],
            },
            inventory={
                "results_dir": "/x",
                "files": [],
                "standard_files": {"enrichment_results.csv": None},
            },
            figures=[
                {
                    "figure_id": "Figure 4",
                    "plot_type": "kegg_bubble",
                    "status": "missing_data",
                    "caption": "缺数据",
                    "missing_reason": "没有对应数据文件",
                }
            ],
            incomplete_figures=[
                {
                    "figure_id": "Figure 4",
                    "plot_type": "kegg_bubble",
                    "status": "missing_data",
                    "missing_reason": "没有对应数据文件",
                }
            ],
            language="zh",
        )
        self.assertIn("标缺", md)
        self.assertNotIn("显著富集", md)
        kegg = resolve_kegg_status(
            plan={"required_visualization": [{"plot_type": "kegg_bubble"}]},
            inventory={"files": [], "standard_files": {}},
            figures=[{"plot_type": "kegg_bubble", "status": "missing_data"}],
        )
        self.assertFalse(kegg["allow_enrichment_claim"])
        gap = kegg_gap_markdown(kegg, zh=True)
        self.assertIn("标缺", gap)
        self.assertNotIn("显著富集", gap)

    def test_strip_false_enrichment_claims(self) -> None:
        text = "KEGG 显示显著富集于糖酵解。"
        cleaned = strip_false_enrichment_claims(text, kegg_missing=True)
        self.assertIn("通路结果标缺", cleaned)
        self.assertNotIn("显著富集", cleaned)
        self.assertEqual(strip_false_enrichment_claims(text, kegg_missing=False), text)

    def test_insights_llm_cannot_claim_enrichment_when_kegg_missing(self) -> None:
        mock = MagicMock()
        mock.think_complete.return_value = """{
            "summary": "通路显著富集。",
            "key_findings": ["KEGG 显著富集"],
            "analysis_role": "role",
            "scientific_value": "sci",
            "application_value": "app",
            "limitations": ["lim"],
            "next_steps": ["next"]
        }"""
        out = generate_report_insights(
            plan={"objective": "o", "required_visualization": [{"plot_type": "kegg_bubble"}]},
            inventory={"results_dir": "/no/such/dir", "files": [], "standard_files": {}},
            figures=[{"figure_id": "Figure 1", "plot_type": "kegg_bubble", "status": "missing_data"}],
            llm_client=mock,
        )
        blob = " ".join(
            [
                str(out.get("summary") or ""),
                str(out.get("markdown") or ""),
                " ".join(str(x) for x in (out.get("key_findings") or [])),
            ]
        )
        self.assertNotIn("显著富集", blob)
        user_prompt = mock.think_complete.call_args[0][0][1]["content"]
        self.assertIn("标缺", user_prompt)


class JournalExportTest(unittest.TestCase):
    def test_matplotlib_journal_export_dpi_vector_font(self) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from web_frontend.backend.agent_c.nature_distill.journal_export import (
            JOURNAL_DPI,
            export_matplotlib_figure,
            is_journal_plot,
        )

        for ptype in (
            "pca",
            "plsda",
            "volcano",
            "vip_bar",
            "heatmap_vip",
            "network_topology",
            "constituent_bar",
            "hca_heatmap",
            "correlation_heatmap",
            "plsda_permutation",
            "paper_fig2_composite",
            "paper_fig5_composite",
        ):
            self.assertTrue(is_journal_plot(ptype), ptype)
        self.assertFalse(is_journal_plot("kegg_bubble"))

        fig, ax = plt.subplots(figsize=(4, 3))
        ax.set_title("PCA", fontsize=12)
        ax.set_xlabel("PC1", fontsize=10)
        ax.plot([0, 1], [0, 1])
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "pca.png"
            report = export_matplotlib_figure(fig, png)
            plt.close(fig)
            self.assertEqual(report["dpi"], JOURNAL_DPI)
            self.assertTrue(png.is_file())
            self.assertTrue(Path(report["pdf"]).is_file())
            self.assertTrue(Path(report["svg"]).is_file())
            self.assertTrue(report["font_audit"]["ok"])
            self.assertEqual(report["collision_audit"], "skipped_until_matplotlib_geometry_gate")
            sidecar = png.with_name("pca.journal_export.json")
            self.assertTrue(sidecar.is_file())


if __name__ == "__main__":
    unittest.main()
