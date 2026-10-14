"""PCA / PLS-DA 换风格时覆盖同一张 intent 图，不要求先删旧文件。"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("MPLBACKEND", "Agg")

from web_frontend.backend.plot_edit_service import apply_plot_config


def _write_session(root: Path) -> None:
    slug = "style_switch"
    out = root / "outputspace" / slug / "mixOmics" / "结果"
    upload = root / "inputspace" / slug
    out.mkdir(parents=True)
    upload.mkdir(parents=True)
    (upload / "metadata.csv").write_text(
        "Sample,Group\n"
        "A,BK\nB,BK\nC,BK\nD,BK\n"
        "E,DY\nF,DY\nG,DY\nH,DY\n",
        encoding="utf-8",
    )
    (out / "pca_scores.csv").write_text(
        ",PC1,PC2\n"
        "A,-1.2,0.2\nB,-1.0,-0.1\nC,-0.8,0.3\nD,-1.1,0.0\n"
        "E,1.0,0.4\nF,1.2,-0.2\nG,0.9,0.1\nH,1.1,-0.3\n",
        encoding="utf-8",
    )
    (out / "pca_explained_variance.csv").write_text(
        "component,variance,cumulative\nPC1,0.42,0.42\nPC2,0.18,0.60\n",
        encoding="utf-8",
    )
    (out / "pca_plot.png").write_bytes(b"\x89PNG\r\n\x1a\nplaceholder")


class ScoreStyleSwitchTest(unittest.TestCase):
    def test_switch_style_overwrites_same_png(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_session(root)
            common = dict(
                project_root=root,
                session_id="s1",
                storage_slug="style_switch",
                source_rel="mixOmics/结果/pca_plot.png",
                filename="pca_plot_intent.png",
                overwrite_intent=True,
            )
            first = apply_plot_config(
                **common,
                plot_config_patch={"score_style": "simca", "title": "Score Plot"},
                instruction="按 SIMCA 重绘",
            )
            intent = root / "outputspace" / "style_switch" / first["file"]["name"]
            self.assertTrue(intent.is_file())
            simca_bytes = intent.read_bytes()
            self.assertTrue(simca_bytes.startswith(b"\x89PNG"))
            cfg_path = intent.with_name(intent.stem + ".plot_config.json")
            self.assertEqual(json.loads(cfg_path.read_text(encoding="utf-8"))["score_style"], "simca")

            second = apply_plot_config(
                **common,
                plot_config_patch={"score_style": "ggplot", "title": "Score Plot"},
                instruction="按 ggplot 重绘",
            )
            self.assertEqual(second["file"]["name"], first["file"]["name"])
            self.assertTrue(intent.is_file())
            ggplot_bytes = intent.read_bytes()
            self.assertNotEqual(ggplot_bytes, simca_bytes)
            saved = json.loads(cfg_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["score_style"], "ggplot")
            self.assertEqual(second["plot_config"]["data"]["score_style"], "ggplot")

            third = apply_plot_config(
                **common,
                plot_config_patch={"score_style": "simca", "title": "Score Plot"},
                instruction="再改回 SIMCA",
            )
            self.assertEqual(third["file"]["name"], first["file"]["name"])
            self.assertNotEqual(intent.read_bytes(), ggplot_bytes)
            self.assertEqual(
                json.loads(cfg_path.read_text(encoding="utf-8"))["score_style"],
                "simca",
            )

    def test_title_edit_keeps_saved_style(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_session(root)
            common = dict(
                project_root=root,
                session_id="s1",
                storage_slug="style_switch",
                source_rel="mixOmics/结果/pca_plot.png",
                filename="pca_plot_intent.png",
                overwrite_intent=True,
            )
            apply_plot_config(
                **common,
                plot_config_patch={"score_style": "ggplot", "title": "Score Plot"},
            )
            kept = apply_plot_config(
                **common,
                plot_config_patch={"title": "PCA by group"},
            )
            self.assertEqual(kept["plot_config"]["data"]["score_style"], "ggplot")
            self.assertEqual(kept["plot_config"]["data"]["title"], "PCA by group")


if __name__ == "__main__":
    unittest.main()
