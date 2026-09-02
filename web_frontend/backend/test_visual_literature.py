"""VisualIR / 文献证据 / 校验 / 日志 单元测试。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.literature_evidence import (
    evidence_cards_to_markdown,
    suggest_soft_style_patch,
)
from web_frontend.backend.visual_edit_journal import append_journal_event, apply_reverse_patch
from web_frontend.backend.visual_ir import attach_evidence, figure_ir_from_config, merge_ir_from_meta
from web_frontend.backend.visual_validation import validate_merge_options, validate_plot_patch


class VisualLiteratureTests(unittest.TestCase):
    def test_figure_ir_and_evidence_attach(self):
        ir = figure_ir_from_config(
            plot_type="volcano",
            source_rel="volcano_plot.png",
            plot_config={"title": "Volcano", "palette": {"A": "#111111"}},
        )
        cards = [
            {
                "evidence_id": "skill#L1",
                "skill_id": "demo",
                "doi": "10.0/1",
                "claim_type": "literature_example",
                "field_hints": ["colors.significant"],
                "quote": "上调红色下调蓝色",
            }
        ]
        out = attach_evidence(ir, cards)
        self.assertEqual(out["kind"], "figure")
        self.assertEqual(len(out["evidence_refs"]), 1)
        self.assertEqual(out["evidence_refs"][0]["skill_id"], "demo")

    def test_merge_ir_panels(self):
        ir = merge_ir_from_meta(
            sources=["a/pca.png", "b/volcano.png"],
            options={"cols": 2, "label_mode": "upper", "gap": 12},
        )
        self.assertEqual(len(ir["panels"]), 2)
        self.assertEqual(ir["layout"]["cols"], 2)

    def test_validate_plot_patch_strips_thresholds_soft(self):
        result = validate_plot_patch(
            patch={"axes": {"y_min": 0.01, "y_max": 1.0}, "title": "New"},
            current_config={"title": "Old"},
            color_keys=["G1", "G2"],
            metadata_columns=["batch"],
            evidence_cards=[],
            user_instruction="把标题改大一点",
        )
        self.assertFalse(result["errors"])
        axes = (result["accepted_patch"] or {}).get("axes") or {}
        self.assertNotIn("y_min", axes)
        self.assertEqual(result["accepted_patch"].get("title"), "New")
        self.assertTrue(any("阈值" in w for w in result["warnings"]))

    def test_validate_plot_patch_rejects_bad_color_by(self):
        result = validate_plot_patch(
            patch={"color_by": "not_a_column"},
            current_config={},
            color_keys=[],
            metadata_columns=["batch", "group"],
            evidence_cards=[],
            user_instruction="按 not_a_column 着色",
        )
        self.assertTrue(result["errors"])
        self.assertEqual(result["accepted_patch"], {})

    def test_validate_merge_options(self):
        ok = validate_merge_options(options={"cols": 2, "label_mode": "upper"}, sources=["a.png", "b.png"])
        self.assertFalse(ok["errors"])
        bad = validate_merge_options(options={"cols": 0}, sources=["a.png"])
        self.assertTrue(bad["errors"])

    def test_journal_append_and_reverse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = {"title": "A", "font_size": {"title": 12}}
            after = {"title": "B", "font_size": {"title": 14}}
            path = append_journal_event(
                output_root=root,
                subdir="edited_plots",
                event_type="plot_edit",
                before=before,
                after=after,
                user_instruction="改标题",
                evidence_refs=[{"evidence_id": "x"}],
            )
            self.assertTrue(path.is_file())
            line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
            event = json.loads(line)
            self.assertEqual(event["type"], "plot_edit")
            rev = event.get("reverse_patch") or []
            if rev:
                restored = apply_reverse_patch(after, rev)
                self.assertEqual(restored.get("title"), "A")

    def test_normalize_volcano_defaults_thresholds(self):
        from web_frontend.backend.plot_theme import normalize_plot_config, resolve_volcano_thresholds

        cfg = normalize_plot_config(None, plot_type="volcano")
        thr = resolve_volcano_thresholds(cfg)
        self.assertEqual(thr["p"], 0.05)
        self.assertEqual(thr["log2fc"], 1.0)
        self.assertEqual(cfg.get("color_by"), "")
        self.assertIsInstance(cfg.get("thresholds"), dict)

    def test_sanitize_volcano_patch_strips_color_by(self):
        from web_frontend.backend.plot_theme import sanitize_volcano_plot_patch

        out = sanitize_volcano_plot_patch(
            {"color_by": "文献规范调整", "title": "Volcano", "colors": {"significant": "#E64B35"}}
        )
        self.assertNotIn("color_by", out)
        self.assertEqual(out["colors"]["upregulated"], "#E64B35")
        cards = [
            {
                "evidence_id": "v1",
                "claim_type": "literature_example",
                "field_hints": ["colors.significant"],
                "quote": "significant upregulated red",
            }
        ]
        md = evidence_cards_to_markdown(cards)
        self.assertIn("Literature evidence cards", md)
        patch, warnings = suggest_soft_style_patch("volcano", cards)
        self.assertIn("upregulated", patch.get("colors", {}))


if __name__ == "__main__":
    unittest.main()
