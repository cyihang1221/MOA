"""拼图源图解析与复合消息拆分单测。"""
from __future__ import annotations

import unittest
from pathlib import Path

from web_frontend.backend.image_merge_registry import (
    list_mergeable_images,
    resolve_merge_image_rels,
)
from web_frontend.backend.visual_message_router import split_compound_visual_message


class ImageMergeRegistryTests(unittest.TestCase):
    def test_resolve_pca_and_volcano_one_each(self):
        images = [
            {
                "rel": "edited_plots/pca_plot_intent.png",
                "name": "pca_plot_intent.png",
                "stem": "pca_plot_intent",
                "modified": 200.0,
                "in_edited": True,
            },
            {
                "rel": "statistical_results/pca_plot.png",
                "name": "pca_plot.png",
                "stem": "pca_plot",
                "modified": 100.0,
                "in_edited": False,
            },
            {
                "rel": "statistical_results/volcano_plot.png",
                "name": "volcano_plot.png",
                "stem": "volcano_plot",
                "modified": 150.0,
                "in_edited": False,
            },
        ]
        rels = resolve_merge_image_rels("合并 PCA 和火山图", images)
        self.assertEqual(len(rels), 2)
        self.assertIn("edited_plots/pca_plot_intent.png", rels)
        self.assertIn("statistical_results/volcano_plot.png", rels)

    def test_user_outputspace_merge_selection(self):
        root = Path(
            "outputspace/（dbj）对上传的mzml文件进行分析，包括xc…_0de4a588"
        )
        if not root.is_dir():
            self.skipTest("user output session not present")
        images = list_mergeable_images(root)
        rels = resolve_merge_image_rels("合并 PCA 和火山图", images)
        self.assertEqual(len(rels), 2)
        stems = {Path(r).stem for r in rels}
        self.assertTrue(any(s.startswith("pca_plot") for s in stems))
        self.assertTrue(any(s.startswith("volcano_plot") for s in stems))


class VisualMessageRouterTests(unittest.TestCase):
    def test_split_labeled_compound_message(self):
        msg = (
            "改图：把火山图标题改大或按文献规范调整配色\n"
            "拼图：「合并 PCA 和火山图」"
        )
        plot_msg, merge_msg = split_compound_visual_message(msg)
        self.assertIn("火山图", plot_msg or "")
        self.assertIn("合并 PCA", merge_msg or "")

    def test_split_single_merge_only(self):
        plot_msg, merge_msg = split_compound_visual_message("合并 PCA 和火山图")
        self.assertIsNone(plot_msg)
        self.assertIn("合并", merge_msg or "")


if __name__ == "__main__":
    unittest.main()
