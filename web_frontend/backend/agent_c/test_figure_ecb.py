"""Figure E/C/B 三模块统一构建单测。"""
from __future__ import annotations

import unittest

from web_frontend.backend.agent_c.figure_cards import build_figure_cards
from web_frontend.backend.agent_c.figure_ecb import build_ecb_blocks


class FigureEcbTest(unittest.TestCase):
    def test_always_three_blocks_without_llm(self) -> None:
        fig = {
            "figure_id": "Figure 3",
            "plot_type": "volcano",
            "status": "rendered",
            "caption": "目的：展示差异代谢物\n总体主题：volcano 显著性",
            "data_narrative": {
                "bullets": ["火山表 315 行", "Significant=True 72 行"],
            },
        }
        blocks = build_ecb_blocks(fig, insights_enabled=False, zh=True)
        self.assertEqual(set(blocks.keys()), {"e", "c", "b"})
        self.assertEqual(blocks["e"]["status"], "ready")
        self.assertEqual(blocks["c"]["status"], "placeholder")
        self.assertEqual(blocks["b"]["status"], "plan_fallback")
        self.assertIn("方案目的", blocks["b"]["what_it_shows"])

    def test_llm_blocks_when_present(self) -> None:
        fig = {
            "figure_id": "Figure 1",
            "plot_type": "pca",
            "status": "rendered",
            "data_narrative": {"bullets": ["PCA 10 行"]},
            "vision_observation": {
                "visible_patterns": ["组间分离"],
                "group_separation": "Group A/B 可区分",
            },
        }
        interp = {
            "what_it_shows": "样本在 PC1 上分离",
            "link_to_objective": "验证分组差异",
            "caveats": "样本量有限",
        }
        blocks = build_ecb_blocks(fig, interp, insights_enabled=True, zh=True)
        self.assertEqual(blocks["c"]["status"], "ready")
        self.assertEqual(blocks["b"]["status"], "ready")
        self.assertEqual(blocks["b"]["source"], "llm")

    def test_build_figure_cards_has_all_blocks(self) -> None:
        cards = build_figure_cards(
            [
                {
                    "figure_id": "Figure 3",
                    "plot_type": "volcano",
                    "status": "rendered",
                    "data_narrative": {"bullets": ["315 行"]},
                    "caption": "目的：火山图",
                }
            ],
            {},
            results_root=__import__("pathlib").Path("/tmp"),
            insights_enabled=False,
        )
        self.assertEqual(set(cards[0]["blocks"].keys()), {"e", "c", "b"})


if __name__ == "__main__":
    unittest.main()
