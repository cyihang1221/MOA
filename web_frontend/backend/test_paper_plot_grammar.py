"""论文级作图语法：椭圆、孤立点、VIP 联结、BK/DY/QC 诚实边界。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from web_frontend.backend.paper_plot_helpers import (
    ellipse_polyline,
    hide_isolates_enabled,
    join_vip_volcano,
    metabolite_axis_id,
    read_explained_variance,
    study_design_disclaimer,
)
from web_frontend.backend.plot_theme import normalize_plot_config
from web_frontend.backend.semantic_plot_renderer import _derive_network_layout, _vip_bar_spec


class EllipsePolylineTest(unittest.TestCase):
    def test_t_is_sequential_not_sorted_by_x(self) -> None:
        rng = np.random.default_rng(0)
        xs = rng.normal(size=20)
        ys = 0.4 * xs + rng.normal(scale=0.2, size=20)
        pts = ellipse_polyline(xs, ys)
        self.assertGreaterEqual(len(pts), 20)
        ts = [p["t"] for p in pts]
        self.assertEqual(ts, list(range(len(pts))))
        xs_poly = [p["x"] for p in pts]
        self.assertNotEqual(xs_poly, sorted(xs_poly))


class ScoreEllipseTest(unittest.TestCase):
    def test_simca_hotelling_matches_f_distribution(self) -> None:
        from web_frontend.backend.simca_score_plot import f_quantile_2, hotelling_semi_axes

        # F(2, 16) 的 95% 分位数 = 3.6337（查表值）
        self.assertAlmostEqual(f_quantile_2(0.95, 16), 3.6337, places=3)
        rng = np.random.default_rng(1)
        xs = rng.normal(scale=20.0, size=18)
        ys = rng.normal(scale=15.0, size=18)
        cx, cy, ax_x, ax_y = hotelling_semi_axes(xs, ys)
        t2crit = 2 * (18 * 18 - 1) / (18 * 16) * f_quantile_2(0.95, 16)
        self.assertAlmostEqual(ax_x, np.sqrt(t2crit * np.var(xs, ddof=1)), places=6)
        self.assertAlmostEqual(ax_y, np.sqrt(t2crit * np.var(ys, ddof=1)), places=6)
        self.assertAlmostEqual(cx, float(xs.mean()), places=9)

    def test_metabolite_axis_uses_id_not_chemical_name(self) -> None:
        raw = (
            "12899 | NCGC00385387-01_C16H28O7_4-(Hydroxymethyl)-1-isopropyl"
            "-3-cyclohexen-1-yl beta-D-glucopyranoside (VIP=1.330)"
        )
        self.assertEqual(metabolite_axis_id(raw), "12899")
        self.assertEqual(metabolite_axis_id("FT1024"), "FT1024")


class ExplainedVarianceFallbackTest(unittest.TestCase):
    def test_cumulative_diff_when_component_na(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pca_explained_variance.csv").write_text(
                "component,explained_variance,cumulative\nPC1,,0.355\nPC2,,0.465\n",
                encoding="utf-8",
            )
            values = read_explained_variance(root, "pca")
            self.assertAlmostEqual(values[0], 0.355, places=3)
            self.assertAlmostEqual(values[1], 0.110, places=3)


class HideIsolatesTest(unittest.TestCase):
    def test_layout_drops_degree_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "network_nodes.csv").write_text(
                "feature_id,degree,molecular_family\n"
                "a,2,fam1\nb,1,fam1\nc,0,singleton\nd,0,singleton\ne,3,fam1\n",
                encoding="utf-8",
            )
            (root / "network_edges.csv").write_text(
                "source,target,cosine\na,b,0.8\na,e,0.9\n",
                encoding="utf-8",
            )
            cfg = {"hide_isolates": True, "marks": {"top_n": 50}}
            self.assertTrue(hide_isolates_enabled(cfg))
            layout = _derive_network_layout(root, cfg)
            self.assertNotIn("c", set(layout["node_id"].astype(str)))
            self.assertGreaterEqual(len(layout), 3)


class VipJoinTest(unittest.TestCase):
    def test_join_adds_log2fc_and_direction_colors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "vip_scores.csv").write_text(
                "Feature,VIP\nF1,2.1\nF2,1.5\nF3,0.8\n",
                encoding="utf-8",
            )
            (root / "volcano_results.csv").write_text(
                "Feature,log2FC,pvalue,padj,Significant\n"
                "F1,1.2,0.001,0.01,True\n"
                "F2,-0.9,0.02,0.04,True\n"
                "F3,0.1,0.4,0.5,False\n",
                encoding="utf-8",
            )
            joined = join_vip_volcano(root)
            self.assertIn("log2FC", joined.columns)
            spec = _vip_bar_spec(root, normalize_plot_config(None, plot_type="vip_bar", color_keys=[]))
            domain = spec["layer"][0]["encoding"]["color"]["scale"]["domain"]
            self.assertIn("log2FC > 0", domain)
            rule = spec["layer"][1]["data"]["values"][0]["threshold"]
            self.assertAlmostEqual(float(rule), 1.2, places=5)


class HonestyDisclaimerTest(unittest.TestCase):
    def test_bk_dy_qc_not_five_grade(self) -> None:
        text = study_design_disclaimer(groups={"BK", "DY", "QC"})
        self.assertIn("BK / DY / QC", text)
        self.assertIn("不构成", text)
        self.assertIn("五等级", text)

    def test_five_grade_silent(self) -> None:
        text = study_design_disclaimer(groups={"Supreme", "Premium", "Special", "Grade I", "Grade II"})
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
