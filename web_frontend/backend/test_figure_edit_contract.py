"""PCA、VIP、热图、KEGG：样式只重绘，阈值按原表重筛，分析方法拒绝。"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("MPLBACKEND", "Agg")

from web_frontend.backend.plot_edit_contract import (
    EDIT_ANALYSIS_METHOD,
    EDIT_ANALYSIS_PARAM,
    EDIT_STYLE,
    apply_instruction_contract,
)
from web_frontend.backend.plot_theme import merge_plot_config, normalize_plot_config
from web_frontend.backend.r_plot_backend import (
    find_rscript,
    render_heatmap_r,
    render_kegg_r,
    render_score_r,
    render_vip_bar_r,
)


class FigureEditContractTest(unittest.TestCase):
    def test_style_param_and_method_stay_separate(self) -> None:
        color = apply_instruction_contract("pca", "把 QC 样本改成红色", {})
        self.assertEqual(color["edit_kind"], EDIT_STYLE)
        self.assertFalse(color["blocked"])
        self.assertEqual(color["patch"]["palette"]["QC"], "#E64B35")
        self.assertNotIn("components", color["patch"])

        comps = apply_instruction_contract("pca", "改用第 1 和 3 主成分", {})
        self.assertEqual(comps["edit_kind"], EDIT_ANALYSIS_PARAM)
        self.assertEqual(comps["patch"]["components"], [1, 3])

        blocked = apply_instruction_contract("pca", "重新做 PCA，换一种归一化", {})
        self.assertEqual(blocked["edit_kind"], EDIT_ANALYSIS_METHOD)
        self.assertTrue(blocked["blocked"])

        vip = apply_instruction_contract("vip_bar", "把 VIP 阈值改为 1.5", {})
        self.assertEqual(vip["edit_kind"], EDIT_ANALYSIS_PARAM)
        self.assertEqual(vip["patch"]["vip_threshold"], 1.5)

        heat = apply_instruction_contract("heatmap_vip", "热图只显示前 8 行", {})
        self.assertEqual(heat["edit_kind"], EDIT_ANALYSIS_PARAM)
        self.assertEqual(heat["patch"]["marks"]["top_n"], 8)

        kegg = apply_instruction_contract("kegg_bubble", "只保留 FDR 小于 0.05 的通路", {})
        self.assertEqual(kegg["edit_kind"], EDIT_ANALYSIS_PARAM)
        self.assertEqual(kegg["patch"]["fdr_cut"], 0.05)

        kept = normalize_plot_config(
            merge_plot_config({"plot_type": "kegg_bubble"}, kegg["patch"]),
            plot_type="kegg_bubble",
        )
        self.assertEqual(kept["fdr_cut"], 0.05)

    @unittest.skipUnless(find_rscript(), "需要 Rscript")
    def test_renders_do_not_rewrite_source_tables(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            scores = root / "pca_scores.csv"
            scores.write_text(
                "sample,PC1,PC2,PC3\n"
                "A,1,2,9\n"
                "B,1.1,2.1,8\n"
                "C,-1,-2,1\n"
                "D,-1.1,-1.8,1.2\n"
                "E,0.1,0.2,4\n",
                encoding="utf-8",
            )
            meta = root / "metadata.csv"
            meta.write_text("Sample,Group\nA,BK\nB,BK\nC,DY\nD,DY\nE,QC\n", encoding="utf-8")
            scores_before = scores.read_text(encoding="utf-8")
            red = root / "pca_red.png"
            blue = root / "pca_blue.png"
            pc13 = root / "pca_pc13.png"
            render_score_r(
                output_path=red,
                data_dir=root,
                metadata_csv=meta,
                plot_config={"title": "PCA", "edit_kind": "style", "palette": {"QC": "#E64B35"}, "score_style": "ggplot"},
                plot_type="pca",
            )
            render_score_r(
                output_path=blue,
                data_dir=root,
                metadata_csv=meta,
                plot_config={"title": "PCA", "edit_kind": "style", "palette": {"QC": "#4DBBD5"}, "score_style": "ggplot"},
                plot_type="pca",
            )
            render_score_r(
                output_path=pc13,
                data_dir=root,
                metadata_csv=meta,
                plot_config={"title": "PCA", "edit_kind": "analysis_param", "components": [1, 3], "score_style": "ggplot"},
                plot_type="pca",
            )
            self.assertEqual(scores.read_text(encoding="utf-8"), scores_before)
            self.assertNotEqual(red.read_bytes(), blue.read_bytes())
            red_rec = json.loads(red.with_suffix(".edit_record.json").read_text(encoding="utf-8"))
            pc_rec = json.loads(pc13.with_suffix(".edit_record.json").read_text(encoding="utf-8"))
            self.assertFalse(red_rec["coordinates_recomputed"])
            self.assertEqual(red_rec["x_name"], "PC1")
            self.assertEqual(red_rec["y_name"], "PC2")
            self.assertEqual(pc_rec["y_name"], "PC3")
            self.assertTrue(red.with_suffix(".pdf").is_file())
            self.assertTrue(red.with_suffix(".svg").is_file())

            vip = root / "vip_scores.csv"
            vip.write_text("Feature,VIP\na,2\nb,1.2\nc,0.4\n", encoding="utf-8")
            vip_before = vip.read_text(encoding="utf-8")
            style = root / "vip_style.png"
            tight = root / "vip_tight.png"
            render_vip_bar_r(root, {"title": "VIP", "edit_kind": "style", "colors": {"bar_color": "#112233"}}, style)
            render_vip_bar_r(
                root,
                {"title": "VIP", "edit_kind": "analysis_param", "vip_threshold": 1.5},
                tight,
            )
            self.assertEqual(vip.read_text(encoding="utf-8"), vip_before)
            style_rec = json.loads(style.with_suffix(".edit_record.json").read_text(encoding="utf-8"))
            tight_rec = json.loads(tight.with_suffix(".edit_record.json").read_text(encoding="utf-8"))
            self.assertFalse(style_rec["apply_filter"])
            self.assertEqual(style_rec["n_plotted"], 3)
            self.assertTrue(tight_rec["apply_filter"])
            self.assertEqual(tight_rec["n_pass"], 1)
            self.assertEqual(tight_rec["n_plotted"], 1)
            self.assertTrue(tight_rec["source_unchanged"])
            self.assertTrue(tight.with_suffix(".filtered.csv").is_file())

            matrix = root / "heatmap_top_vip_matrix.csv"
            matrix.write_text(
                "Feature,S1,S2\na,1,2\nb,3,1\nc,0,0\n",
                encoding="utf-8",
            )
            matrix_before = matrix.read_text(encoding="utf-8")
            heat = root / "heat.png"
            render_heatmap_r(
                root,
                {"title": "Heat", "edit_kind": "analysis_param", "vip_threshold": 1.5, "marks": {"top_n": 10}},
                heat,
                None,
            )
            self.assertEqual(matrix.read_text(encoding="utf-8"), matrix_before)
            heat_rec = json.loads(heat.with_suffix(".edit_record.json").read_text(encoding="utf-8"))
            self.assertEqual(heat_rec["n_after_vip"], 1)
            self.assertEqual(heat_rec["n_plotted"], 1)
            self.assertTrue(heat.with_suffix(".pdf").is_file())

            kegg_csv = root / "kegg_compound_enrich.csv"
            kegg_csv.write_text(
                "ID,Description,Count,pvalue,p.adjust\n"
                "a,pathA,4,0.001,0.001\n"
                "b,pathB,3,0.02,0.04\n"
                "c,pathC,2,0.1,0.2\n"
                "d,pathD,1,0.4,0.5\n",
                encoding="utf-8",
            )
            kegg_before = kegg_csv.read_text(encoding="utf-8")
            bubble = root / "kegg.png"
            render_kegg_r(
                root,
                {"title": "KEGG", "edit_kind": "analysis_param", "fdr_cut": 0.05},
                bubble,
                "kegg_bubble",
            )
            self.assertEqual(kegg_csv.read_text(encoding="utf-8"), kegg_before)
            kegg_rec = json.loads(bubble.with_suffix(".edit_record.json").read_text(encoding="utf-8"))
            self.assertEqual(kegg_rec["n_after_fdr"], 2)
            self.assertEqual(kegg_rec["n_plotted"], 2)
            self.assertTrue(bubble.with_suffix(".svg").is_file())
            self.assertTrue(bubble.with_suffix(".pdf").is_file())


if __name__ == "__main__":
    unittest.main()
