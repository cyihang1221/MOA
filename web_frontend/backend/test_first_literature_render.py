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


if __name__ == "__main__":
    unittest.main()
