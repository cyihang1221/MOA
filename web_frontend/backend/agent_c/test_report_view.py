"""Agent C 报告预览 API 与 B 侧 PNG 清单。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from web_frontend.backend.agent_c.figure_cards import build_figure_cards, write_figure_cards_json
from web_frontend.backend.agent_c.report_view import (
    filter_existing_figures_for_report,
    list_existing_result_pngs,
    load_report_bundle,
    markdown_to_html,
    preferred_png_for_plot_type,
    split_markdown_figure_section,
)


class ReportViewTest(unittest.TestCase):
    def test_markdown_to_html_basic(self) -> None:
        html = markdown_to_html("# Title\n\n**bold**")
        self.assertIn("<h1>", html)
        self.assertIn("<strong>bold</strong>", html)

    def test_list_existing_pngs(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "mixomics" / "volcano_plot.png").parent.mkdir(parents=True)
            (tmp_path / "mixomics" / "volcano_plot.png").write_bytes(b"png")
            c_out = tmp_path / "agent_c_output" / "figures"
            c_out.mkdir(parents=True)
            (c_out / "Figure_1__pca.png").write_bytes(b"png")

            items = list_existing_result_pngs(tmp_path, exclude_under=tmp_path / "agent_c_output")
            rels = {x["rel"] for x in items}
            self.assertIn("mixomics/volcano_plot.png", rels)
            self.assertFalse(any("agent_c_output" in r for r in rels))

    def test_filter_existing_figures_for_report(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            stat = root / "statistical_results"
            stat.mkdir()
            (stat / "pca_plot.png").write_bytes(b"1")
            (stat / "volcano_plot.png").write_bytes(b"2")
            figures = [
                {
                    "png": str((stat / "pca_plot.png").resolve()),
                    "status": "copied_existing",
                }
            ]
            existing = list_existing_result_pngs(root)
            filtered = filter_existing_figures_for_report(
                existing, figures=figures, results_dir=root
            )
            rels = {x["rel"] for x in filtered}
            self.assertNotIn("statistical_results/pca_plot.png", rels)
            self.assertIn("statistical_results/volcano_plot.png", rels)

    def test_filter_existing_by_plot_type_semantic(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            stat = root / "statistical_results"
            stat.mkdir()
            (stat / "pca_plot.png").write_bytes(b"1")
            figures = [
                {
                    "plot_type": "pca",
                    "png": str(root / "agent_c_output" / "figures" / "Figure_1__pca.png"),
                    "status": "copied_existing",
                }
            ]
            existing = list_existing_result_pngs(root)
            filtered = filter_existing_figures_for_report(
                existing, figures=figures, results_dir=root
            )
            rels = {x["rel"] for x in filtered}
            self.assertNotIn("statistical_results/pca_plot.png", rels)

    def test_preferred_png_for_plot_type(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            edited = root / "edited_plots"
            stat = root / "statistical_results"
            edited.mkdir()
            stat.mkdir()
            (edited / "pca_plot_intent.png").write_bytes(b"intent")
            (stat / "pca_plot.png").write_bytes(b"stat")
            picked = preferred_png_for_plot_type(root, "pca")
            self.assertEqual(picked, (edited / "pca_plot_intent.png").resolve())

    def test_split_markdown_figure_section(self) -> None:
        md = "# T\n\n## 引言\n\nobj\n\n## 图表\n\nfig\n\n## 方法\n\nm\n"
        prose, fig_sec = split_markdown_figure_section(md)
        self.assertNotIn("## 图表", prose)
        self.assertIn("## 方法", prose)
        self.assertTrue(fig_sec.startswith("## 图表"))

    def test_load_report_bundle_figure_cards(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            out = tmp_path / "agent_c_output"
            fig = out / "figures"
            fig.mkdir(parents=True)
            png = fig / "Figure_1__pca.png"
            png.write_bytes(b"png")
            md = out / "final_report.md"
            md.write_text(
                "# Report\n\n## 引言\n\nobj\n\n## 图表\n\n![F](figures/Figure_1__pca.png)\n\n## 方法\n\nm\n",
                encoding="utf-8",
            )
            cards = build_figure_cards(
                [
                    {
                        "figure_id": "Figure 1",
                        "plot_type": "pca",
                        "status": "rendered",
                        "png": str(png),
                        "caption": "PCA",
                        "data_narrative": {"bullets": ["PCA 得分 10 行"]},
                    }
                ],
                {},
                results_root=tmp_path,
                zh=True,
            )
            write_figure_cards_json(cards, out)

            bundle = load_report_bundle(session_id="sess-2", results_dir=tmp_path)
            self.assertEqual(bundle["layout"], "figure_first")
            self.assertEqual(len(bundle["figure_cards"]), 1)
            self.assertTrue(bundle["figure_cards"][0]["blocks"]["e"]["bullets"])
            self.assertTrue(bundle["prose_html"])
            self.assertNotIn("## 图表", bundle["prose_html"])

    def test_load_report_bundle_rewrites_images(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            out = tmp_path / "agent_c_output"
            fig = out / "figures"
            fig.mkdir(parents=True)
            (fig / "Figure_1__pca.png").write_bytes(b"png")
            md = out / "final_report.md"
            md.write_text("# Report\n\n![PCA](figures/Figure_1__pca.png)\n", encoding="utf-8")
            (out / "report_insights.json").write_text(
                json.dumps({"summary": "测试摘要"}, ensure_ascii=False),
                encoding="utf-8",
            )

            bundle = load_report_bundle(session_id="sess-1", results_dir=tmp_path)
            self.assertIn("测试摘要", bundle["insights_summary"])
            self.assertIn("/api/sessions/sess-1/workspace-file", bundle["markdown"])
            self.assertTrue(bundle["html"])


if __name__ == "__main__":
    unittest.main()
