"""都匀毛尖论文复现：配方、图型、demo 集成测试。"""
from __future__ import annotations

import unittest
from pathlib import Path

from web_frontend.backend.agent_c.paper_reproduction import (
    checklist_inventory,
    load_repro_recipe,
    list_repro_recipes,
    recipe_to_canonical_plan,
)
from web_frontend.backend.agent_c.runner import run_agent_c
from web_frontend.backend.agent_c.tea_paper_plots import TEA_PAPER_PLOT_TYPES, render_tea_paper_plot

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "duyun_maojian_demo"
RECIPE_ID = "duyun_maojian_fochx_2026"


class PaperReproductionTest(unittest.TestCase):
    def test_list_recipes(self) -> None:
        recipes = list_repro_recipes()
        self.assertTrue(any(r["recipe_id"] == RECIPE_ID for r in recipes))

    def test_recipe_plan_has_figures(self) -> None:
        recipe = load_repro_recipe(RECIPE_ID)
        plan = recipe_to_canonical_plan(recipe)
        self.assertEqual(plan["plan_format"], "paper_reproduction")
        self.assertGreaterEqual(len(plan["required_visualization"]), 10)
        self.assertIn("10.1016/j.fochx.2026.103843", plan["objective"])

    def test_tea_plot_types_registered(self) -> None:
        self.assertIn("constituent_bar", TEA_PAPER_PLOT_TYPES)
        self.assertIn("correlation_heatmap", TEA_PAPER_PLOT_TYPES)

    def test_render_constituent_bar(self) -> None:
        out = FIXTURES / "_test_constituent.png"
        render_tea_paper_plot("constituent_bar", FIXTURES, out, {"title": "Test"})
        self.assertTrue(out.is_file())
        out.unlink(missing_ok=True)

    def test_checklist_partial(self) -> None:
        from web_frontend.backend.agent_c.results_inventory import inventory_results

        recipe = load_repro_recipe(RECIPE_ID)
        inv = inventory_results(FIXTURES)
        chk = checklist_inventory(recipe, inv)
        self.assertGreater(chk["completion_rate"], 0.3)
        self.assertGreater(chk["n_ready_figures"], 0)

    def test_run_agent_c_demo_partial(self) -> None:
        out = FIXTURES / "agent_c_output_test"
        if out.is_dir():
            import shutil
            shutil.rmtree(out)
        manifest = run_agent_c(
            results_dir=FIXTURES,
            output_dir=out,
            metadata_csv=FIXTURES / "metadata.csv",
            repro_recipe_id=RECIPE_ID,
            figure_mode="plan",
            use_literature=False,
        )
        self.assertIn(manifest["status"], {"ok", "partial"})
        self.assertIn("reproduction_checklist", manifest)
        rendered = [f for f in manifest["figures"] if f.get("status") == "rendered"]
        self.assertGreaterEqual(len(rendered), 5)
        report = out / "final_report.md"
        self.assertTrue(report.is_file())


if __name__ == "__main__":
    unittest.main()
