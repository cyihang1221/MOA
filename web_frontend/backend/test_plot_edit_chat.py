"""聊天改图：结果路径与预览事件。"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from web_frontend.backend.plot_edit_chat import _file_rel_from_result, stream_chat_plot_edit_deltas
from web_frontend.backend.webapp import _append_chat_images_marker, _chat_file_rel


class PlotEditChatPreviewTest(unittest.TestCase):
    def test_file_rel_from_result(self) -> None:
        self.assertEqual(
            _file_rel_from_result({"file": {"name": "edited_plots/heatmap_top_vip_intent.png"}}),
            "edited_plots/heatmap_top_vip_intent.png",
        )
        self.assertEqual(
            _file_rel_from_result({"effective_rel": "pca_plot.png"}),
            "pca_plot.png",
        )
        self.assertEqual(_file_rel_from_result({}), "")

    def test_chat_file_rel_and_marker(self) -> None:
        self.assertEqual(_chat_file_rel({"file": "edited_plots/a.png"}), "edited_plots/a.png")
        self.assertEqual(_chat_file_rel("b.png"), "b.png")
        marked = _append_chat_images_marker("改图完成", ["edited_plots/a.png"])
        self.assertIn("massagent:chat_images", marked)
        self.assertIn("edited_plots/a.png", marked)

    def test_stream_emits_chat_image(self) -> None:
        fake = {
            "file": {"name": "edited_plots/heatmap_top_vip_intent.png"},
            "agent_patch": {"cmap": "RdBu_r"},
            "config_diff": {"summary": "cmap"},
            "plot_config": {"name": "edited_plots/heatmap_top_vip_intent.plot_config.json"},
        }
        with patch(
            "web_frontend.backend.plot_edit_chat.resolve_chat_plot_edit_tasks",
            return_value=([("heatmap_top_vip.png", "按文献改热图")], [{"rel": "heatmap_top_vip.png"}]),
        ), patch(
            "web_frontend.backend.plot_edit_chat.agent_apply_plot_edit",
            return_value=fake,
        ):
            events = list(
                stream_chat_plot_edit_deltas(
                    project_root=".",
                    session_id="s",
                    storage_slug="slug",
                    message="热图按知识库论文那种来改",
                )
            )
        images = [e.get("chat_image") for e in events if e.get("chat_image")]
        self.assertTrue(images)
        self.assertEqual(images[0]["file"], "edited_plots/heatmap_top_vip_intent.png")
        done = next(e for e in events if e.get("plot_edit_done"))
        self.assertEqual(done.get("chat_images"), ["edited_plots/heatmap_top_vip_intent.png"])


if __name__ == "__main__":
    unittest.main()
