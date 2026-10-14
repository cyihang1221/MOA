"""ggplot 得分图：旋转椭圆留在框内；有数值列时才画点大小图例。"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np

from web_frontend.backend.ggplot_score_plot import (
    ggplot_group_ellipse_bounds,
    padded_axis_limits,
    render_ggplot_score_png,
    resolve_ggplot_point_sizes,
)
from web_frontend.backend.paper_plot_helpers import ellipse_axis_bounds


class EllipseBoundsTest(unittest.TestCase):
    def test_vertical_major_axis_uses_rotated_extent(self) -> None:
        xmin, xmax, ymin, ymax = ellipse_axis_bounds(0.0, 0.0, 20.0, 2.0, 90.0)
        self.assertAlmostEqual(ymax, 10.0, places=5)
        self.assertAlmostEqual(ymin, -10.0, places=5)
        self.assertLess(xmax - xmin, 3.0)

    def test_group_bounds_cover_vertical_cluster(self) -> None:
        xs = np.array([0.0, 0.02, -0.01, 0.01, 0.0, 8.0, 8.02, 7.99, 8.01, 8.0])
        ys = np.array([-4.0, -2.0, 0.0, 2.0, 4.0, 0.1, 0.0, -0.1, 0.05, -0.05])
        groups = ["A"] * 5 + ["B"] * 5
        boxes = ggplot_group_ellipse_bounds(xs, ys, groups)
        self.assertEqual(len(boxes), 2)
        vertical = max(boxes, key=lambda box: box[3] - box[2])
        self.assertGreater(vertical[3], 4.0)
        self.assertLess(vertical[2], -4.0)

    def test_configured_limit_cannot_clip_ellipse(self) -> None:
        lo, hi = padded_axis_limits(-4.0, 6.0, pad_lo=0.1, pad_hi=0.1, cfg_lo=-1.0, cfg_hi=1.0)
        self.assertLess(lo, -4.0)
        self.assertGreater(hi, 6.0)


class PointSizeLegendTest(unittest.TestCase):
    def test_no_numeric_column_skips_size_legend(self) -> None:
        with TemporaryDirectory() as tmp:
            meta = Path(tmp) / "metadata.csv"
            meta.write_text("Sample,Group\nA,BK\nB,DY\nC,QC\n", encoding="utf-8")
            self.assertIsNone(
                resolve_ggplot_point_sizes(["A", "B", "C"], meta, {"color_by": "Group"})
            )

    def test_cd52_column_sizes_points_and_legend(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "metadata.csv"
            meta.write_text(
                "Sample,Group,CD52\n"
                "A,Case,6\nB,Case,8\nC,Case,10\n"
                "D,Control,6\nE,Control,8\nF,Control,10\n",
                encoding="utf-8",
            )
            resolved = resolve_ggplot_point_sizes(
                ["A", "B", "C", "D", "E", "F"],
                meta,
                {"color_by": "Group", "size_by": "CD52"},
            )
            self.assertIsNotNone(resolved)
            _values, title, breaks = resolved
            self.assertEqual(title, "CD52")
            self.assertEqual(breaks, [6.0, 8.0, 10.0])

            scores = np.array(
                [[-1.0, 0.2], [-0.8, 0.0], [-1.1, -0.3], [1.0, 0.2], [0.9, -0.1], [1.2, 0.3]],
                dtype=float,
            )
            out = root / "pca.png"
            render_ggplot_score_png(
                scores=scores,
                groups=["Case", "Case", "Case", "Control", "Control", "Control"],
                sample_names=["A", "B", "C", "D", "E", "F"],
                axis_names=["PC1", "PC2"],
                plot_config={"score_style": "ggplot", "title": "PCA plot", "size_by": "CD52", "show_sample_labels": False},
                output_path=out,
                plot_type="pca",
                metadata_csv=meta,
            )
            svg = out.with_suffix(".svg").read_text(encoding="utf-8")
            self.assertIn("CD52", svg)
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
