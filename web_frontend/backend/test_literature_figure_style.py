"""首次出图的文献样式层测试。"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from web_frontend.backend.literature_figure_style import (
    DEFAULT_JOURNAL,
    JOURNAL_PALETTES,
    apply_journal_palette,
    build_initial_plot_config,
    clear_style_cache,
    resolve_figure_style,
    style_provenance_line,
)
from web_frontend.backend.plot_theme import DEFAULT_FONT_SIZES


class LiteratureFigureStyleTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_style_cache()

    def test_baseline_raises_font_and_keeps_publication_defaults(self) -> None:
        style = resolve_figure_style(plot_type="pca", use_literature=False)
        patch = style["patch"]
        self.assertGreater(patch["font_size"]["title"], DEFAULT_FONT_SIZES["title"])
        self.assertEqual(patch["legend"]["position"], "right")
        self.assertFalse(patch["show_sample_labels"])
        self.assertEqual(style["source"], "baseline")
        self.assertIn("publication_baseline", style["applied_fields"])

    def test_unknown_plot_type_still_gets_font_baseline(self) -> None:
        style = resolve_figure_style(plot_type="some_new_plot", use_literature=False)
        self.assertIn("font_size", style["patch"])

    def test_empty_plot_type_returns_no_style(self) -> None:
        style = resolve_figure_style(plot_type="", use_literature=False)
        self.assertEqual(style["source"], "none")
        self.assertEqual(style["patch"], {})

    def test_initial_config_uses_plan_hint_over_literature(self) -> None:
        config, _style = build_initial_plot_config(
            plot_type="pca",
            plan_hint={"font_size": {"title": 26}, "legend": {"position": "bottom"}},
            title="My PCA",
            color_keys=["Case", "Control"],
            use_literature=False,
        )
        self.assertEqual(config["title"], "My PCA")
        self.assertEqual(config["font_size"]["title"], 26)
        self.assertEqual(config["legend"]["position"], "bottom")

    def test_title_suggestion_only_when_no_title_given(self) -> None:
        config, _ = build_initial_plot_config(plot_type="volcano", use_literature=False)
        self.assertEqual(config["title"], "Volcano Plot")

        config2, _ = build_initial_plot_config(
            plot_type="volcano", title="差异代谢物", use_literature=False
        )
        self.assertEqual(config2["title"], "差异代谢物")

    def test_placeholder_plan_title_yields_to_literature_wording(self) -> None:
        """方案常用 Figure 1 / plot_type 占位，这类标题应换成文献措辞。"""
        for placeholder in ("Figure 1", "figure 2", "pca", "PCA", "图 3"):
            config, _ = build_initial_plot_config(
                plot_type="pca",
                title=placeholder,
                weak_titles=["Figure 1", "pca", "PCA"],
                use_literature=False,
            )
            self.assertEqual(config["title"], "PCA Score Plot", f"failed for {placeholder!r}")

    def test_explicit_plan_title_survives(self) -> None:
        config, _ = build_initial_plot_config(
            plot_type="pca",
            plan_hint={"title": "Control vs Treatment"},
            title="Figure 1",
            weak_titles=["Figure 1", "pca"],
            use_literature=False,
        )
        self.assertEqual(config["title"], "Control vs Treatment")

    def test_palette_matches_colors_for_semantic_keys(self) -> None:
        """palette 与 colors 同名键不一致会让前端色板显示错色。"""
        config, _ = build_initial_plot_config(
            plot_type="volcano",
            color_keys=["upregulated", "downregulated", "nonsignificant", "threshold_color"],
            use_literature=False,
        )
        for key, value in config["palette"].items():
            self.assertEqual(value, config["colors"][key], f"palette/colors mismatch on {key}")

    def test_volcano_initial_config_keeps_thresholds_and_three_colors(self) -> None:
        config, _ = build_initial_plot_config(plot_type="volcano", use_literature=False)
        self.assertEqual(config["thresholds"]["p"], 0.05)
        self.assertEqual(config["thresholds"]["log2fc"], 1.0)
        self.assertEqual(config["colors"]["upregulated"], "#E64B35")
        self.assertEqual(config["colors"]["downregulated"], "#4DBBD5")
        self.assertEqual(config["colors"]["nonsignificant"], "#B0B0B0")
        # 火山图不按 metadata 着色
        self.assertEqual(config["color_by"], "")

    def test_journal_palette_applied_to_group_plots(self) -> None:
        config, _ = build_initial_plot_config(
            plot_type="pca",
            color_keys=["Case", "Control", "QC"],
            use_literature=False,
        )
        expected = JOURNAL_PALETTES[DEFAULT_JOURNAL]
        self.assertEqual(config["palette"]["Case"], expected[0])
        self.assertEqual(config["palette"]["Control"], expected[1])
        self.assertEqual(config["palette"]["QC"], expected[2])

    def test_journal_palette_skips_semantic_color_keys(self) -> None:
        """volcano 的 palette 键是语义色，重排会串色。"""
        before = {
            "plot_type": "volcano",
            "palette": {"upregulated": "#E64B35", "threshold_color": "#666666"},
        }
        after = apply_journal_palette(before, "lancet", plot_type="volcano")
        self.assertEqual(after["palette"], before["palette"])

    def test_journal_palette_respects_explicit_plan_palette(self) -> None:
        config, _ = build_initial_plot_config(
            plot_type="pca",
            plan_hint={"palette": {"Case": "#123456"}},
            color_keys=["Case", "Control"],
            use_literature=False,
        )
        self.assertEqual(config["palette"]["Case"], "#123456")

    def test_config_records_literature_provenance(self) -> None:
        config, style = build_initial_plot_config(plot_type="pca", use_literature=False)
        lit = config.get("literature_style")
        self.assertIsInstance(lit, dict)
        self.assertEqual(lit["journal"], DEFAULT_JOURNAL)
        self.assertIn("publication_baseline", lit["applied_fields"])
        self.assertTrue(style_provenance_line(style))

    def test_provenance_line_mentions_matched_skill(self) -> None:
        line = style_provenance_line(
            {
                "source": "literature",
                "matched": ["fbmn-gnps"],
                "journal": "npg",
                "evidence_refs": [{"doi": "10.1038/x"}],
            }
        )
        self.assertIn("fbmn-gnps", line)
        self.assertIn("10.1038/x", line)

    def test_literature_style_from_evidence_cards(self) -> None:
        """带 Nature/图例位置线索的 Skill 应被解析成样式。"""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "MassOmics-Agent" / "MassOmics-Agent" / "skills" / "volcano-demo"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: volcano-demo\n"
                "description: 差异代谢物火山图 volcano plot 出图规范\n"
                "---\n"
                "DOI: 10.1038/demo123\n\n"
                "## 出图清单\n"
                "| 图 | 说明 |\n"
                "| --- | --- |\n"
                "| Volcano plot | 使用 ggsci NPG 配色，图例在下方，标注 p<0.05 阈值 |\n",
                encoding="utf-8",
            )
            style = resolve_figure_style(
                plot_type="volcano",
                goal_text="差异代谢物 volcano 分析",
                project_root=root,
            )

        self.assertEqual(style["source"], "literature")
        self.assertIn("volcano-demo", style["matched"])
        self.assertEqual(style["patch"]["legend"]["position"], "bottom")
        self.assertTrue(any("阈值" in w for w in style["warnings"]))
        self.assertTrue(style["evidence_refs"])

    def test_style_cache_reuses_result(self) -> None:
        a = resolve_figure_style(plot_type="pca", goal_text="g", use_literature=False)
        b = resolve_figure_style(plot_type="pca", goal_text="g", use_literature=False)
        self.assertIs(a, b)


if __name__ == "__main__":
    unittest.main()
