"""聊天改图：结果路径与预览事件。"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from web_frontend.backend.plot_edit_chat import (
    _file_rel_from_result,
    plot_type_for_edit_rel,
    redraw_engine_phrase,
    stream_chat_plot_edit_deltas,
)
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
            "parameter_record": {
                "edit_kind": "style",
                "source_unchanged": True,
                "source_name": "heatmap_top_vip_matrix.csv",
                "source_sha256": "abc123def456",
                "exports": {"png": True, "svg": True, "pdf": False},
                "detail": {},
            },
        }
        with TemporaryDirectory() as tmp, patch(
            "web_frontend.backend.plot_edit_chat.resolve_chat_plot_edit_tasks",
            return_value=([("heatmap_top_vip.png", "按文献改热图")], [{"rel": "heatmap_top_vip.png"}]),
        ), patch(
            "web_frontend.backend.plot_edit_chat.agent_apply_plot_edit",
            return_value=fake,
        ), patch(
            "web_frontend.backend.plot_edit_chat.session_work_dir",
            return_value=Path(tmp),
        ):
            events = list(
                stream_chat_plot_edit_deltas(
                    project_root=Path(tmp),
                    session_id="s",
                    storage_slug="slug",
                    message="热图按知识库论文那种来改",
                )
            )
        text = "".join(str(e.get("delta") or "") for e in events)
        self.assertIn("正在检索文献作图知识并重绘（R（pheatmap））", text)
        self.assertNotIn("matplotlib", text)
        self.assertIn("参数记录：样式重绘", text)
        self.assertIn("heatmap_top_vip_matrix.csv", text)
        images = [e.get("chat_image") for e in events if e.get("chat_image")]
        self.assertTrue(images)
        self.assertEqual(images[0]["file"], "edited_plots/heatmap_top_vip_intent.png")
        done = next(e for e in events if e.get("plot_edit_done"))
        self.assertEqual(done.get("chat_images"), ["edited_plots/heatmap_top_vip_intent.png"])

    def test_redraw_label_matches_the_engine(self) -> None:
        self.assertEqual(plot_type_for_edit_rel("pca_plot.png"), "pca")
        self.assertEqual(plot_type_for_edit_rel("Figure_2__pca_plot.png"), "pca")
        self.assertEqual(redraw_engine_phrase("pca"), "R（ggplot2）")
        self.assertEqual(redraw_engine_phrase("plsda"), "R（ggplot2）")
        self.assertEqual(redraw_engine_phrase("volcano"), "R（ggplot2）")
        self.assertEqual(redraw_engine_phrase("heatmap_vip"), "R（pheatmap）")
        self.assertEqual(redraw_engine_phrase("network_topology"), "matplotlib")
        self.assertEqual(redraw_engine_phrase("unknown"), "")


if __name__ == "__main__":
    unittest.main()
