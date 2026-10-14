"""投稿主图：茶叶 matplotlib 600dpi、VIP 阈值对齐、方案漏写时补画。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from web_frontend.backend.agent_c.figure_data_narrative import build_figure_data_narrative
from web_frontend.backend.agent_c.figure_pipeline import (
    _build_caption,
    extract_figure_facts,
    match_figures,
)
from web_frontend.backend.agent_c.nature_distill.journal_export import JOURNAL_DPI, load_journal_export
from web_frontend.backend.agent_c.results_inventory import inventory_results
from web_frontend.backend.agent_c.tea_paper_plots import render_tea_paper_plot
from web_frontend.backend.plot_renderer import render_network_topology_png


class PublicationGapTest(unittest.TestCase):
    def test_tea_and_network_write_journal_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tea_constituents.csv").write_text(
                "grade,metric,mean,sd,significance_letter\n"
                "Supreme,TPC,1.2,0.1,a\n"
                "Premium,TPC,0.8,0.1,b\n",
                encoding="utf-8",
            )
            (root / "plsda_permutation.csv").write_text(
                "permutation,R2,Q2\n0,0.91,0.72\n1,0.2,0.05\n",
                encoding="utf-8",
            )
            (root / "network_nodes.csv").write_text(
                "node_id,family,degree\nn1,A,2\nn2,A,1\nn3,B,0\n",
                encoding="utf-8",
            )
            (root / "network_edges.csv").write_text(
                "source,target,cosine\nn1,n2,0.8\n",
                encoding="utf-8",
            )
            (root / "network_layout.csv").write_text(
                "node_id,x,y,family,degree\nn1,0,0,A,2\nn2,1,0.2,A,1\nn3,3,3,B,0\n",
                encoding="utf-8",
            )
            bar = root / "constituents.png"
            perm = root / "perm.png"
            net = root / "network.png"
            (root / "hca_matrix.csv").write_text(
                "Sample,m1,m2,m3\nS1,1.0,0.1,0.0\nS2,0.8,0.2,0.1\nS3,0.0,1.1,0.2\nS4,0.1,0.9,0.4\n",
                encoding="utf-8",
            )
            (root / "pca_scores.csv").write_text(
                "Sample,PC1,PC2,Group\n"
                "A1,1.2,0.2,Supreme\nA2,1.0,0.4,Supreme\nA3,1.3,0.1,Supreme\n"
                "B1,-1.1,0.3,Premium\nB2,-0.9,-0.2,Premium\nB3,-1.2,0.1,Premium\n",
                encoding="utf-8",
            )
            (root / "plsda_scores.csv").write_text(
                (root / "pca_scores.csv").read_text(encoding="utf-8").replace("PC1", "Comp1").replace("PC2", "Comp2"),
                encoding="utf-8",
            )
            (root / "differential_metabolites_abundance.csv").write_text(
                "compound,Supreme,Premium\nmet_a,1.2,0.2\nmet_b,0.3,1.1\n",
                encoding="utf-8",
            )
            hca = root / "hca.png"
            fig5 = root / "fig5.png"
            render_tea_paper_plot("constituent_bar", root, bar, {"title": "TPC", "show_significance_letters": True})
            render_tea_paper_plot("plsda_permutation", root, perm, {"title": "Permutation"})
            render_tea_paper_plot("hca_heatmap", root, hca, {"title": "HCA"})
            render_tea_paper_plot("paper_fig5_composite", root, fig5, {"title": "Fig5", "ellipse": True})
            render_network_topology_png(root, {"title": "Network", "hide_isolates": True}, net)
            for png in (bar, perm, hca, fig5, net):
                self.assertTrue(png.is_file(), png.name)
                payload = load_journal_export(png)
                self.assertIsNotNone(payload, png.name)
                self.assertEqual(payload["dpi"], JOURNAL_DPI)
                self.assertTrue(Path(payload["pdf"]).is_file())
                self.assertTrue(str(payload["svg"]).endswith(".journal.svg"))
                with Image.open(png) as image:
                    self.assertGreaterEqual(image.info.get("dpi", (0, 0))[0], JOURNAL_DPI - 1)

    def test_vip_count_uses_same_threshold_as_plot_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vip_scores.csv").write_text(
                "Feature,VIP\na,1.5\nb,1.1\nc,0.4\n",
                encoding="utf-8",
            )
            facts = extract_figure_facts("vip_bar", root)
            joined = " ".join(facts)
            self.assertIn("VIP>1.2", joined)
            self.assertIn("VIP>1.2 共 1 个", joined)
            self.assertNotIn("VIP>1 共", joined)
            narr = build_figure_data_narrative("vip_bar", root)
            self.assertEqual(narr["stats"]["vip_threshold"], 1.2)
            self.assertEqual(narr["stats"]["n_vip_above_threshold"], 1)
            cap = _build_caption(
                {"figure_id": "Figure 1", "title": "VIP", "plot_type": "vip_bar"},
                facts,
                "zh",
                data_narrative=narr,
            )
            self.assertIn("VIP>1.2", cap)
            self.assertNotIn("作图线 VIP>", cap)

    def test_plan_omits_volcano_but_csv_is_still_queued(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pca_scores.csv").write_text("sample,PC1,PC2\nA,0.1,0.2\n", encoding="utf-8")
            (root / "volcano_results.csv").write_text(
                "feature,log2FC,p_value\nx,1.2,0.01\n",
                encoding="utf-8",
            )
            (root / "notes.md").write_text("not a result table\n", encoding="utf-8")
            inv = inventory_results(root)
            plan = {
                "required_visualization": [
                    {"figure_id": "Figure 1", "plot_type": "pca", "title": "PCA", "source_files": ["pca_scores.csv"]}
                ]
            }
            jobs = match_figures(plan, inv, figure_mode="plan")
            by_type = {job["plot_type"]: job for job in jobs}
            self.assertEqual(by_type["pca"]["status"], "ready")
            self.assertEqual(by_type["pca"]["source"], "plan")
            self.assertIn("volcano", by_type)
            self.assertEqual(by_type["volcano"]["status"], "ready")
            self.assertEqual(by_type["volcano"]["source"], "b_csv")
            dumped = json.loads((root / "b_file_map.json").read_text(encoding="utf-8"))
            self.assertEqual(dumped["file_map"]["volcano_results.csv"]["status"], "present")
            self.assertTrue((root / "_b_contract" / "volcano_results.csv").is_file())
            self.assertFalse((root / "_b_contract" / "notes.md").exists())

    def test_plan_report_includes_plots_the_plan_did_not_name(self) -> None:
        from web_frontend.backend.agent_c.report_builder import prepare_report_figures
        from web_frontend.backend.agent_c.report_view import (
            filter_existing_figures_for_report,
            list_existing_result_pngs,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mix = root / "mixOmics" / "结果"
            kegg = root / "KEGG_compound_enrichment" / "结果"
            mix.mkdir(parents=True)
            kegg.mkdir(parents=True)
            (mix / "pca_scores.csv").write_text("sample,PC1,PC2\nA,0.1,0.2\n", encoding="utf-8")
            (mix / "plsda_scores.csv").write_text("sample,comp1,comp2\nA,0.2,0.1\n", encoding="utf-8")
            (mix / "volcano_results.csv").write_text(
                "feature,log2FC,pvalue,neglog10p\nx,1.2,0.01,2\n",
                encoding="utf-8",
            )
            for name in ("pca_plot.png", "plsda_plot.png", "volcano_plot.png"):
                (mix / name).write_bytes(b"\x89PNG\r\n\x1a\n")
            (kegg / "kegg_compound_enrich.csv").write_text(
                "ID,Description,Count,p.adjust\nhsa1,Path,3,0.01\n",
                encoding="utf-8",
            )
            for name in (
                "kegg_compound_bubble.png",
                "kegg_compound_barplot.png",
                "kegg_compound_dotplot.png",
            ):
                (kegg / name).write_bytes(b"\x89PNG\r\n\x1a\n")

            inv = inventory_results(root)
            plan = {
                "required_visualization": [
                    {"figure_id": "Figure 1", "plot_type": "pca", "title": "PCA", "source_files": ["pca_scores.csv"]},
                    {
                        "figure_id": "Figure 2",
                        "plot_type": "kegg_bubble",
                        "title": "KEGG",
                        "source_files": ["kegg_compound_enrich.csv"],
                    },
                    {
                        "figure_id": "Figure 3",
                        "plot_type": "annotation_propagation",
                        "title": "Annotation",
                        "source_files": ["enhanced_nodes.csv"],
                    },
                ]
            }
            jobs = match_figures(plan, inv, figure_mode="plan")
            figures = []
            for job in jobs:
                fig = dict(job)
                if job.get("status") == "ready":
                    png = job.get("existing_png")
                    if not png:
                        png = str(root / f"{job.get('plot_type') or 'fig'}.png")
                        Path(png).write_bytes(b"\x89PNG\r\n\x1a\n")
                    fig["status"] = "rendered"
                    fig["png"] = png
                figures.append(fig)
            existing = filter_existing_figures_for_report(
                list_existing_result_pngs(root),
                figures=figures,
                results_dir=root,
            )
            complete, incomplete = prepare_report_figures(
                figures,
                supplement_existing=existing,
                results_dir=root,
                supplement_mode="all",
            )
            shown = " ".join(
                f"{item.get('plot_type') or ''} {item.get('png') or ''} {item.get('title') or ''}"
                for item in complete
            )
            self.assertIn("pca", shown)
            self.assertIn("plsda", shown)
            self.assertIn("volcano", shown)
            self.assertIn("kegg_bubble", shown)
            self.assertIn("kegg_compound_barplot.png", shown)
            self.assertIn("kegg_compound_dotplot.png", shown)
            self.assertEqual(
                [item.get("plot_type") for item in incomplete],
                ["annotation_propagation"],
            )


if __name__ == "__main__":
    unittest.main()
