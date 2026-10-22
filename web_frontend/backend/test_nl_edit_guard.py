"""自然语言改图：文献只给样式，统计数字只来自用户写明的指令。"""
from __future__ import annotations

import unittest

from web_frontend.backend.plot_edit_contract import (
    EDIT_ANALYSIS_METHOD,
    EDIT_ANALYSIS_PARAM,
    EDIT_STYLE,
    classify_plot_edit,
    guard_nl_edit,
)


class NlEditGuardTest(unittest.TestCase):
    def test_model_threshold_does_not_override_a_style_edit(self) -> None:
        guarded = guard_nl_edit(
            "volcano",
            "标题改为 Volcano style",
            model_patch={"title": "Volcano style", "thresholds": {"p": 0.001, "log2fc": 2}},
            literature_patch={"colors": {"upregulated": "#111111"}, "vip_threshold": 1.2},
        )
        self.assertEqual(guarded["edit_kind"], EDIT_STYLE)
        self.assertFalse(guarded["blocked"])
        self.assertNotIn("thresholds", guarded["patch"])
        self.assertNotIn("colors", guarded["patch"])
        self.assertEqual(guarded["patch"]["title"], "Volcano style")

    def test_do_not_change_threshold_stays_style_and_keeps_literature_colors(self) -> None:
        self.assertEqual(
            classify_plot_edit("按知识库文献重绘火山图，不要改统计阈值", "volcano"),
            EDIT_STYLE,
        )
        guarded = guard_nl_edit(
            "volcano",
            "按知识库文献重绘火山图，不要改统计阈值",
            model_patch={"thresholds": {"p": 0.01}},
            literature_patch={
                "colors": {"upregulated": "#E64B35", "downregulated": "#4DBBD5"},
                "thresholds": {"p": 0.001},
                "fdr_cut": 0.05,
            },
        )
        self.assertEqual(guarded["edit_kind"], EDIT_STYLE)
        self.assertTrue(guarded["used_literature"])
        self.assertEqual(guarded["patch"]["colors"]["upregulated"], "#E64B35")
        self.assertNotIn("thresholds", guarded["patch"])
        self.assertNotIn("fdr_cut", guarded["patch"])

    def test_explicit_threshold_beats_literature_and_model(self) -> None:
        guarded = guard_nl_edit(
            "vip_bar",
            "把 VIP 阈值改为 1.5，并按文献配色",
            model_patch={"vip_threshold": 2.0, "colors": {"bar_color": "#000000"}},
            literature_patch={"vip_threshold": 1.2, "colors": {"upregulated": "#E64B35"}},
        )
        self.assertEqual(guarded["edit_kind"], EDIT_ANALYSIS_PARAM)
        self.assertEqual(guarded["patch"]["vip_threshold"], 1.5)
        self.assertEqual(guarded["patch"]["colors"]["upregulated"], "#E64B35")
        self.assertEqual(guarded["patch"]["colors"]["bar_color"], "#000000")
        self.assertTrue(any("VIP≥1.5" in w for w in guarded["warnings"]))

    def test_method_edit_stays_blocked(self) -> None:
        guarded = guard_nl_edit(
            "pca",
            "重新做 PCA，换一种归一化",
            model_patch={"palette": {"QC": "#E64B35"}},
            literature_patch={"palette": {"BK": "#111111"}},
        )
        self.assertEqual(guarded["edit_kind"], EDIT_ANALYSIS_METHOD)
        self.assertTrue(guarded["blocked"])
        self.assertNotIn("palette", guarded["patch"])


if __name__ == "__main__":
    unittest.main()
