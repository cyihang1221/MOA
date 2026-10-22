"""Agent A Figure 蓝图（Phase 1）单测。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.agent_a.figure_blueprint import (
    enrich_figure_blueprints,
    infer_source_step,
    match_repro_recipe,
)
from web_frontend.backend.agent_a.plan_catalog import figure_payload
from web_frontend.backend.agent_c.figure_checklist import (
    checklist_from_jobs,
    format_checklist_markdown,
)


class FigureBlueprintTests(unittest.TestCase):
    def test_infer_source_step_mixomics(self):
        tasks = [
            "Use data_preprocessing_xcms to pick peaks",
            "Use statistical_analysis_mixomics for PCA and volcano",
        ]
        self.assertEqual(infer_source_step("pca", tasks), 2)
        self.assertEqual(infer_source_step("volcano", tasks), 2)

    def test_enrich_adds_source_files_and_hint(self):
        figures = [figure_payload("pca", 1, "PCA")]
        tasks = ["Use statistical_analysis_mixomics for PCA"]
        enriched, meta = enrich_figure_blueprints(
            figures,
            tasks,
            objective="Control vs Treatment PCA",
        )
        self.assertEqual(len(enriched), 1)
        fig = enriched[0]
        self.assertEqual(fig["source_step"], 1)
        self.assertIn("pca_scores.csv", fig["source_files"])
        self.assertIn("plot_config_hint", fig)
        self.assertIn("journal_palette", fig["plot_config_hint"])
        self.assertIsInstance(meta, dict)

    def test_match_duyun_recipe_by_keywords(self):
        recipe = match_repro_recipe("复现都匀毛尖 fochx 2026 论文 Figure 1-8")
        if recipe:
            self.assertIn("duyun", str(recipe.get("recipe_id") or "").lower())

    def test_generic_analysis_does_not_match_tea_paper(self):
        recipe = match_repro_recipe("请对上传的质谱数据做分组差异分析：先评估数据质量")
        self.assertIsNone(recipe)

    def test_generic_pca_keeps_its_title(self):
        figures = [figure_payload("pca", 1, "PCA Score Plot")]
        enriched, meta = enrich_figure_blueprints(
            figures,
            ["Use statistical_analysis_mixomics for PCA"],
            objective="Control vs Treatment PCA",
        )
        self.assertEqual(enriched[0]["title"], "PCA Score Plot")
        self.assertFalse(meta.get("reproduction_target"))
        self.assertIsNot(enriched[0]["plot_config_hint"].get("show_sample_labels"), False)

    def test_checklist_missing_data(self):
        jobs = [
            {
                "figure_id": "Figure 1",
                "plot_type": "pca",
                "source_step": 4,
                "source_files": ["pca_scores.csv"],
                "status": "missing_data",
                "missing_reason": "缺少 pca_scores.csv",
            }
        ]
        cl = checklist_from_jobs(jobs, plan={"reproduction_target": {"doi": "10.0/1"}})
        self.assertEqual(cl["n_missing"], 1)
        md = format_checklist_markdown(cl)
        self.assertIn("Figure 1", md)
        self.assertIn("pca_scores.csv", md)


class DisplayedScorePlotTests(unittest.TestCase):
    def test_report_pca_uses_the_file_panel_style(self):
        from web_frontend.backend.agent_c.figure_pipeline import (
            align_score_figure_with_displayed_plot,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edited = root / "edited_plots"
            edited.mkdir()
            (edited / "pca_plot_intent.plot_config.json").write_text(
                json.dumps(
                    {
                        "title": "PCA Score Plot",
                        "score_style": "ggplot",
                        "show_sample_labels": True,
                        "show_grid": False,
                        "ellipse": True,
                    }
                ),
                encoding="utf-8",
            )
            item = {
                "plot_type": "pca",
                "title": "Non-volatile PCA",
                "plot_config_hint": {"show_sample_labels": False, "ellipse": True},
            }
            align_score_figure_with_displayed_plot(item, root)
            self.assertEqual(item["title"], "PCA Score Plot")
            self.assertEqual(item["plot_config_hint"]["score_style"], "ggplot")
            self.assertTrue(item["plot_config_hint"]["show_sample_labels"])


if __name__ == "__main__":
    unittest.main()
