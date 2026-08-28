"""Agent C 图像导向报告：数据支撑(E) / Vision(C) / 逐图解读(B) 单测。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from web_frontend.backend.agent_c.figure_data_narrative import (
    build_figure_data_narrative,
    enrich_figures_data_narrative,
    format_data_narrative_markdown,
    resolve_figure_plot_type,
)
from web_frontend.backend.agent_c.figure_vision import (
    attach_vision_to_figures,
    format_vision_markdown,
    vision_enabled,
)
from web_frontend.backend.agent_c.report_builder import build_report_markdown
from web_frontend.backend.agent_c.report_insights import (
    figure_interpretations_index,
    format_figure_interpretation_block,
)


class FigureReportTest(unittest.TestCase):
    def test_data_narrative_volcano(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv = root / "volcano_results.csv"
            csv.write_text(
                "feature,log2FC,p_value,Significant\n"
                "m1,1.2,0.01,True\n"
                "m2,-0.5,0.2,False\n"
                "m3,2.0,0.001,True\n",
                encoding="utf-8",
            )
            narr = build_figure_data_narrative("volcano", root)
            self.assertEqual(narr["stats"].get("n_features"), 3)
            self.assertEqual(narr["stats"].get("n_significant"), 2)
            md = format_data_narrative_markdown(narr, zh=True)
            self.assertIn("#### 数据支撑", md)
            self.assertIn("3", md)

    def test_format_vision_markdown(self) -> None:
        obs = {
            "visible_patterns": ["两组在 PC1 方向分离"],
            "group_separation": "A/B 组颜色簇部分重叠",
            "interpretation_boundary": "不能从本图推断显著性",
        }
        md = format_vision_markdown(obs, zh=True)
        self.assertIn("#### 读图观察", md)
        self.assertIn("两组在 PC1 方向分离", md)
        self.assertEqual(format_vision_markdown({"skipped": True}), "")

    def test_figure_interpretation_block_link_to_objective(self) -> None:
        block = format_figure_interpretation_block(
            {
                "figure_id": "Figure 1",
                "what_it_shows": "展示分组整体代谢轮廓",
                "link_to_objective": "对应方案中的组间差异目标",
                "caveats": "样本量有限",
            },
            zh=True,
        )
        self.assertIn("#### 图意解读", block)
        self.assertIn("与目标关系", block)
        self.assertIn("组间差异目标", block)
        self.assertEqual(block.count("与目标关系"), 1)

    def test_build_report_embeds_e_c_b(self) -> None:
        figures = [
            {
                "figure_id": "Figure 1",
                "plot_type": "volcano",
                "status": "rendered",
                "caption": "火山图",
                "data_narrative": {
                    "bullets": ["火山图数据共 10 个特征。"],
                },
                "vision_observation": {
                    "visible_patterns": ["可见红蓝对称分布"],
                },
            }
        ]
        interp = figure_interpretations_index(
            {
                "figure_interpretations": [
                    {
                        "figure_id": "Figure 1",
                        "what_it_shows": "差异代谢物分布",
                        "link_to_objective": "验证差异假设",
                        "caveats": "需 FDR 复核",
                    }
                ]
            }
        )
        md = build_report_markdown(
            plan={"objective": "差异分析", "workflow": []},
            inventory={"results_dir": "/x", "files": []},
            figures=figures,
            language="zh",
            figure_interpretations=interp,
        )
        idx_data = md.index("#### 数据支撑")
        idx_vision = md.index("#### 读图观察")
        idx_interp = md.index("#### 图意解读")
        self.assertLess(idx_data, idx_vision)
        self.assertLess(idx_vision, idx_interp)

    @patch.dict("os.environ", {"MASSAGENT_FIGURE_VISION": "1"})
    def test_attach_vision_mock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            png = Path(tmp) / "f.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
            mock = MagicMock()
            mock.think_complete.return_value = (
                '{"visible_patterns":["mock"],"group_separation":"N/A",'
                '"notable_features":"axes","interpretation_boundary":"none","confidence":0.8}'
            )
            figures = [
                {
                    "figure_id": "Figure 1",
                    "plot_type": "pca",
                    "status": "rendered",
                    "png": str(png),
                }
            ]
            attach_vision_to_figures(figures, objective="test", llm_client=mock)
            self.assertEqual(figures[0]["vision_observation"].get("source"), "vision_llm")
            mock.think_complete.assert_called_once()

    def test_vision_disabled(self) -> None:
        with patch.dict("os.environ", {"MASSAGENT_FIGURE_VISION": "0"}):
            self.assertFalse(vision_enabled())

    def test_figure_first_section_order(self) -> None:
        md = build_report_markdown(
            plan={"objective": "差异分析", "workflow": [], "reporting_plan": {"figure_first": True}},
            inventory={"results_dir": "/x", "files": []},
            figures=[
                {
                    "figure_id": "Figure 1",
                    "plot_type": "pca",
                    "status": "rendered",
                    "caption": "PCA",
                }
            ],
            language="zh",
        )
        idx_intro = md.index("## 引言")
        idx_fig = md.index("## 图表")
        idx_methods = md.index("## 方法")
        self.assertLess(idx_intro, idx_fig)
        self.assertLess(idx_fig, idx_methods)

    def test_figure_cards_builder(self) -> None:
        from web_frontend.backend.agent_c.figure_cards import build_figure_cards

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            png = root / "pca_plot.png"
            png.write_bytes(b"x")
            cards = build_figure_cards(
                [
                    {
                        "figure_id": "Figure 1",
                        "plot_type": "pca",
                        "status": "rendered",
                        "png": str(png),
                        "data_narrative": {"bullets": ["3 个样本"]},
                        "vision_observation": {"visible_patterns": ["分离"]},
                    }
                ],
                {"Figure 1": {"what_it_shows": "轮廓", "link_to_objective": "目标"}},
                results_root=root,
                zh=True,
            )
            self.assertEqual(cards[0]["figure_id"], "Figure 1")
            self.assertIn("e", cards[0]["blocks"])
            self.assertIn("c", cards[0]["blocks"])
            self.assertIn("b", cards[0]["blocks"])

    def test_resolve_plot_type_from_png(self) -> None:
        fig = {"png": "/out/statistical_results/volcano_plot.png"}
        self.assertEqual(resolve_figure_plot_type(fig), "volcano")
        fig2 = {"png": "/out/agent_c_output/figures/Figure_1__fig01_constituents.png"}
        self.assertEqual(resolve_figure_plot_type(fig2), "constituent_bar")

    def test_data_narrative_tea_and_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tea_constituents.csv").write_text(
                "grade,metric,mean,sd\nSupreme,TPC,100,5\nSupreme,TFC,80,4\n",
                encoding="utf-8",
            )
            narr = build_figure_data_narrative("constituent_bar", root)
            self.assertTrue(any("TPC" in b for b in narr["bullets"]))

            sub = root / "mixomics"
            sub.mkdir()
            (sub / "network_nodes.csv").write_text(
                "id,Family,degree\n1,A,3\n2,A,5\n3,B,1\n",
                encoding="utf-8",
            )
            figs = [
                {
                    "figure_id": "Figure 2",
                    "png": str(sub / "degree_distribution.png"),
                    "status": "copied_existing",
                }
            ]
            enrich_figures_data_narrative(figs, results_dir=root)
            self.assertEqual(figs[0]["plot_type"], "degree_hist")
            self.assertTrue(figs[0]["data_narrative"]["bullets"])

    def test_kegg_bar_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "kegg_compound_enrich.csv").write_text(
                "pathway,p_value,Count\nmap00010,0.01,5\n",
                encoding="utf-8",
            )
            narr = build_figure_data_narrative("kegg_bar", root)
            self.assertTrue(narr["bullets"])


if __name__ == "__main__":
    unittest.main()
