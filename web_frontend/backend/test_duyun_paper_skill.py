"""都匀毛尖论文 Skill：触发、注入规划、工具映射。"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "skill_builder"))

from parse_recipes import parse_recipe_file  # noqa: E402
from render_skills import infer_triggers, render_paper_skill  # noqa: E402

from web_frontend.backend.agent_a.massomics_planner import run_massomics_planning
from web_frontend.backend.agent_a.massomics_tool_map import (
    _vip_from_text,
    resolve_web_mcp_tool,
    step_to_executable_task,
)
from web_frontend.backend.skill_match import match_skills

RECIPE = ROOT / "softwares_database" / "repro_recipes" / "recipe_10.1016_j.fochx.2026.103843.txt"


class DuyunPaperSkillTests(unittest.TestCase):
    def test_recipe_triggers_include_paper_aliases(self):
        recipes = parse_recipe_file(RECIPE)
        self.assertEqual(len(recipes), 1)
        r = recipes[0]
        self.assertGreaterEqual(len(r.steps), 8)
        self.assertGreaterEqual(len(r.figures), 5)
        keys = [k.lower() for k in infer_triggers(r)]
        for token in ("都匀毛尖", "duyun maojian", "103843"):
            self.assertTrue(any(token in k for k in keys), msg=token)

    def test_skill_markdown_maps_simca_and_skips_wetlab_as_b(self):
        r = parse_recipe_file(RECIPE)[0]
        md = render_paper_skill(r)
        self.assertIn("statistical_analysis_mixomics", md)
        self.assertIn("湿法", md)
        self.assertIn("VIP>1.2", md)

    def test_match_skills_on_duyun_query(self):
        hit = match_skills("请按都匀毛尖 Food Chemistry X 论文做非靶向分析", project_root=ROOT)
        names = " ".join(hit.get("matched") or []).lower()
        text = (hit.get("text") or "").lower()
        self.assertTrue(
            "103843" in names
            or "duyun" in names
            or "maojian" in names
            or "都匀" in (hit.get("text") or "")
            or "103843" in text,
            msg=hit.get("matched"),
        )

    def test_simca_maps_to_mixomics_with_paper_vip(self):
        registered = {"statistical_analysis_mixomics"}
        self.assertEqual(
            resolve_web_mcp_tool("SIMCA 14.1", registered),
            "statistical_analysis_mixomics",
        )
        task = step_to_executable_task(
            {
                "tools": ["SIMCA"],
                "description": "PLS-DA VIP > 1.2 exclude QC",
                "input_filename": "features",
                "output_filename": "stats",
            },
            paths={"upload": "/data", "outputspace": "/out"},
            registered=registered,
        )
        self.assertIsNotNone(task)
        self.assertIn("vip_threshold=1.2", task or "")

    def test_vip_parser(self):
        self.assertEqual(_vip_from_text("vip_threshold=1.5"), "1.5")
        self.assertEqual(_vip_from_text("筛选 VIP > 1.2"), "1.2")

    def test_planner_accepts_skill_context(self):
        sig = inspect.signature(run_massomics_planning)
        self.assertIn("skill_context", sig.parameters)


if __name__ == "__main__":
    unittest.main()
