"""改图后的参数记录写入配置，并给出可核对的原表版本。"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from web_frontend.backend.plot_parameter_record import (
    attach_parameter_record,
    enrich_caption,
    parameter_record_line,
    score_plot_method_sentence,
)
from web_frontend.backend.semantic_plot_renderer import write_semantic_outputs


class PlotParameterRecordTest(unittest.TestCase):
    def test_caption_names_ggplot2_only_when_score_plot_was_redrawn(self) -> None:
        record = {
            "edit_kind": "style",
            "source_unchanged": True,
            "source_name": "pca_scores.csv",
            "source_sha256": "abc123def4567890",
            "exports": {"png": True, "svg": True, "pdf": True},
            "detail": {"score_style": "simca", "x_name": "PC1", "y_name": "PC2"},
        }
        caption = enrich_caption("**Figure 1.** PCA", "pca", record)
        self.assertIn("ggplot2", caption)
        self.assertIn("不是 SIMCA 软件", caption)
        self.assertIn("参数记录", caption)
        self.assertIn("PC1", caption)
        ggplot = enrich_caption("PCA", "pca", {**record, "detail": {"score_style": "ggplot"}})
        self.assertIn("theme_classic", ggplot)
        self.assertEqual(score_plot_method_sentence("pca", "simca", has_record=False), "")
        network = enrich_caption("网络", "network_topology", record)
        self.assertNotIn("ggplot2", network)
        self.assertIn("参数记录", network)
        volcano = enrich_caption(
            "火山",
            "volcano",
            {**record, "detail": {"n_up": 2, "n_down": 1}, "edit_kind": "analysis_param"},
        )
        self.assertNotIn("ggplot2", volcano)
        self.assertIn("上调 2", volcano)
    def test_record_keeps_source_hash_and_exports(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "volcano_results.csv"
            src.write_text("Feature,log2FC\na,1\n", encoding="utf-8")
            png = root / "volcano.png"
            png.write_bytes(b"png")
            png.with_suffix(".svg").write_text("<svg/>", encoding="utf-8")
            png.with_suffix(".pdf").write_bytes(b"%PDF")
            png.with_suffix(".edit_record.json").write_text(
                json.dumps(
                    {
                        "edit_kind": "analysis_param",
                        "source_unchanged": True,
                        "source_csv": str(src),
                        "n_up": 1,
                        "n_down": 0,
                    }
                ),
                encoding="utf-8",
            )
            config = root / "volcano.plot_config.json"
            config.write_text(json.dumps({"plot_type": "volcano", "title": "V"}), encoding="utf-8")
            before = src.read_text(encoding="utf-8")
            record = attach_parameter_record(png, config)
            self.assertEqual(src.read_text(encoding="utf-8"), before)
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record["source_sha256"], hashlib.sha256(src.read_bytes()).hexdigest())
            self.assertTrue(record["source_unchanged"])
            self.assertTrue(record["exports"]["pdf"])
            saved = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(saved["title"], "V")
            self.assertEqual(saved["parameter_record"]["detail"]["n_up"], 1)
            line = parameter_record_line(record)
            self.assertIn("按原表重算筛选", line)
            self.assertIn("上调 1，下调 0", line)
            self.assertIn("PDF/SVG", line)
            self.assertNotIn(str(src), line)

    def test_semantic_writer_attaches_record_for_r_plots(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "vip_scores.csv"
            src.write_text("Feature,VIP\na,2\n", encoding="utf-8")
            png = root / "vip.png"

            def render(path: Path) -> None:
                Path(path).write_bytes(b"png")
                Path(path).with_suffix(".edit_record.json").write_text(
                    json.dumps(
                        {
                            "edit_kind": "style",
                            "source_unchanged": True,
                            "source_csv": str(src),
                            "n_plotted": 1,
                        }
                    ),
                    encoding="utf-8",
                )

            write_semantic_outputs(
                png_path=png,
                plot_config={"plot_type": "vip_bar", "title": "VIP"},
                vega_spec={"mark": "bar"},
                png_renderer=render,
            )
            saved = json.loads((root / "vip.plot_config.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["parameter_record"]["edit_kind"], "style")
            self.assertEqual(saved["parameter_record"]["source_name"], "vip_scores.csv")
            self.assertTrue(saved["parameter_record"]["source_unchanged"])


if __name__ == "__main__":
    unittest.main()
