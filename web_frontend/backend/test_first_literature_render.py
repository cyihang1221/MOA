"""首次出图即文献样式：嵌套仓路径、执行口令、不复制 B 的 ggplot。"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from web_frontend.backend.literature_corpus import clear_corpus_cache
from web_frontend.backend.literature_evidence import collect_evidence_cards
from web_frontend.backend.literature_figure_style import (
    build_initial_plot_config,
    clear_style_cache,
    first_plot_style_instruction,
)
from web_frontend.backend.literature_paths import resolve_literature_dirs, resolve_phase2_registry
from web_frontend.backend.literature_plot_knowledge import effective_plot_goal_text


_PCA_INDEX = """========== figure_index entry ==========
figure_id: fig_4
paper_title: Pseudotargeted metabolomics
source_paper: Zheng F et al. (2020), Nature protocols, DOI: 10.1038/s41596-020-0341-5
figure_caption: Fig. 4: PCA score plot of plasma samples colored by group (NPG palette).
"""


class FirstLiteratureRenderTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_style_cache()
        clear_corpus_cache()

    def tearDown(self) -> None:
        clear_style_cache()
        clear_corpus_cache()

    def test_nested_repo_walks_up_to_parent_literature_db(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "softwares_database"
            src.mkdir()
            (src / "figure_index.txt").write_text(_PCA_INDEX, encoding="utf-8")
            (src / "pipeline_overview.md").write_text("# pca volcano\n", encoding="utf-8")
            nested = root / "MassOmics-Agent" / "MassOmics-Agent"
            nested.mkdir(parents=True)
            persist, source = resolve_literature_dirs(nested, allow_install_fallback=False)
            self.assertEqual(Path(source), src)
            self.assertTrue(persist)

            cards = collect_evidence_cards(
                plot_type="pca",
                goal_text="非靶向代谢组学",
                project_root=nested,
            )
            ids = {str(c.get("skill_id") or "") for c in cards}
            self.assertIn("literature_corpus", ids)

            config, style = build_initial_plot_config(
                plot_type="pca",
                title="Figure 1",
                weak_titles=["Figure 1", "pca"],
                goal_text="非靶向代谢组学 PCA",
                project_root=nested,
                use_literature=True,
            )
            self.assertEqual(style.get("source"), "literature")
            self.assertIn("literature_corpus", style.get("matched") or [])
            self.assertTrue(config.get("title"))

    def test_temp_project_root_does_not_fall_back_to_install_db(self) -> None:
        with TemporaryDirectory() as tmp:
            isolated = Path(tmp) / "nested"
            isolated.mkdir()
            persist, source = resolve_literature_dirs(isolated, allow_install_fallback=False)
            self.assertEqual(Path(source), isolated / "softwares_database")
            self.assertFalse(Path(source).is_dir())
            cards = collect_evidence_cards(plot_type="pca", project_root=isolated)
            ids = {str(c.get("skill_id") or "") for c in cards}
            self.assertNotIn("literature_corpus", ids)

    def test_effective_goal_prefers_plan_over_confirmation(self) -> None:
        goal = effective_plot_goal_text(
            user_message="确认计划",
            plan={
                "objective": "非靶向代谢组学比较 Control 与 Treatment",
                "required_visualization": [{"title": "PCA Score Plot", "plot_type": "pca"}],
            },
        )
        self.assertIn("非靶向代谢组学", goal)
        self.assertNotIn("确认计划", goal)

    def test_phase2_registry_walks_up(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg = root / "phase2_output"
            reg.mkdir()
            (reg / "skill_registry.json").write_text('{"skills":[]}', encoding="utf-8")
            nested = root / "MassOmics-Agent" / "MassOmics-Agent"
            nested.mkdir(parents=True)
            found = resolve_phase2_registry(nested)
            self.assertEqual(found, (reg / "skill_registry.json").resolve())

    def test_run_agent_c_does_not_copy_existing_when_literature_on(self) -> None:
        import inspect

        from web_frontend.backend.agent_c.runner import run_agent_c

        src = inspect.getsource(run_agent_c)
        self.assertIn("insights_enabled and not use_literature", src)

    def test_first_plot_instruction_is_style_and_admits_literature(self) -> None:
        from web_frontend.backend.plot_edit_contract import EDIT_STYLE, classify_plot_edit, guard_nl_edit
        from web_frontend.backend.plot_edit_registry import looks_like_literature_plot_restyle

        instruction = first_plot_style_instruction("pca")
        self.assertTrue(looks_like_literature_plot_restyle(instruction))
        self.assertEqual(classify_plot_edit(instruction, "pca"), EDIT_STYLE)
        guarded = guard_nl_edit(
            "pca",
            instruction,
            model_patch={"legend": {"position": "bottom"}, "thresholds": {"p": 0.01}},
            literature_patch={"font_size": {"title": 14}, "thresholds": {"p": 0.05}},
        )
        self.assertFalse(guarded["blocked"])
        self.assertTrue(guarded["used_literature"])
        self.assertEqual(guarded["patch"]["legend"]["position"], "bottom")
        self.assertEqual(guarded["patch"]["font_size"]["title"], 14)
        self.assertNotIn("thresholds", guarded["patch"])

    def test_ai_style_applies_model_reading_but_plan_hint_wins(self) -> None:
        from unittest.mock import patch

        def fake_parse(**kwargs):
            self.assertIn("文献", kwargs["instruction"])
            self.assertIn("改图规范", kwargs["literature_context"])
            return {
                "legend": {"position": "bottom"},
                "title": "AI PCA Score Plot",
                "thresholds": {"p": 0.01},
                "font_size": {"title": 20},
            }

        with (
            patch(
                "web_frontend.backend.literature_evidence.collect_evidence_cards",
                return_value=[{
                    "evidence_id": "score#yaml",
                    "skill_id": "score-plot-pca-plsda",
                    "doi": "10.1371/journal.pcbi.1005752",
                    "claim_type": "structured_spec",
                    "quote": "legend_position=right",
                    "field_hints": ["legend.position"],
                }],
            ),
            patch(
                "web_frontend.backend.literature_plot_knowledge.match_plot_literature",
                return_value={"text": "### Figure convention skill\n改图规范：图例在右。", "matched": ["score-plot-pca-plsda"]},
            ),
            patch(
                "web_frontend.backend.plot_edit_agent.parse_plot_edit_instruction",
                side_effect=fake_parse,
            ),
        ):
            config, style = build_initial_plot_config(
                plot_type="pca",
                title="Figure 1",
                weak_titles=["Figure 1", "pca"],
                plan_hint={"legend": {"position": "left", "show": True}, "colors": {"upregulated": "#112233"}},
                goal_text="PCA",
                project_root=Path("/tmp/no-such-plot-root"),
                use_literature=True,
                use_ai_style=True,
                color_keys=["GroupA"],
                metadata_columns=["Sample", "Group"],
            )
        self.assertEqual(style.get("source"), "literature_ai")
        self.assertEqual(config["legend"]["position"], "left")
        self.assertEqual(config["font_size"]["title"], 20)
        self.assertEqual(config["title"], "AI PCA Score Plot")
        self.assertFalse(config.get("thresholds"))
        self.assertIn("ai_style", style.get("applied_fields") or [])

    def test_ai_style_failure_keeps_skill_style(self) -> None:
        from unittest.mock import patch

        with (
            patch(
                "web_frontend.backend.literature_evidence.collect_evidence_cards",
                return_value=[],
            ),
            patch(
                "web_frontend.backend.literature_plot_knowledge.match_plot_literature",
                return_value={"text": "", "matched": []},
            ),
            patch(
                "web_frontend.backend.plot_edit_agent.parse_plot_edit_instruction",
                side_effect=RuntimeError("no api"),
            ),
        ):
            config, style = build_initial_plot_config(
                plot_type="pca",
                title="PCA Score Plot",
                goal_text="PCA",
                project_root=Path(__file__).resolve().parents[2],
                use_literature=True,
                use_ai_style=True,
            )
        self.assertTrue(any("未完成" in item for item in (style.get("warnings") or [])))
        self.assertNotEqual(style.get("source"), "literature_ai")
        self.assertEqual(config["legend"]["position"], "right")
        self.assertEqual(config["font_size"]["title"], 14)


if __name__ == "__main__":
    unittest.main()
