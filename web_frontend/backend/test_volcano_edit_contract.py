"""火山图：样式只重绘，阈值按原表重算分类，分析方法拒绝。"""
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
    classify_plot_edit,
)
from web_frontend.backend.r_plot_backend import find_rscript, render_volcano_r


class VolcanoEditContractTest(unittest.TestCase):
    def test_color_is_style_and_threshold_recomputes(self) -> None:
        color = apply_instruction_contract("volcano", "上调用 #112233，下调 #445566", {})
        self.assertEqual(color["edit_kind"], EDIT_STYLE)
        self.assertFalse(color["blocked"])
        self.assertEqual(color["patch"]["colors"]["upregulated"], "#112233")
        self.assertNotIn("thresholds", color["patch"])

        param = apply_instruction_contract(
            "volcano",
            "把火山图的显著性阈值改为 P 小于 0.01，log2fc 大于 1.5",
            {},
        )
        self.assertEqual(param["edit_kind"], EDIT_ANALYSIS_PARAM)
        self.assertEqual(param["patch"]["thresholds"]["p"], 0.01)
        self.assertEqual(param["patch"]["thresholds"]["log2fc"], 1.5)
        self.assertEqual(param["patch"]["p_stat"], "pvalue")

    def test_method_change_is_blocked(self) -> None:
        blocked = apply_instruction_contract("volcano", "改用 t 检验重新分析火山图", {})
        self.assertEqual(blocked["edit_kind"], EDIT_ANALYSIS_METHOD)
        self.assertTrue(blocked["blocked"])
        self.assertEqual(classify_plot_edit("把 QC 样本改成红色", "pca"), EDIT_STYLE)

    @unittest.skipUnless(find_rscript(), "需要 Rscript 与 ggplot2")
    def test_threshold_rewrites_classes_without_touching_source(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "volcano_results.csv"
            src.write_text(
                "Feature,log2FC,pvalue,neglog10p\n"
                "a,2,0.001,3\n"
                "b,2,0.04,1.4\n"
                "c,-2,0.001,3\n"
                "d,0.2,0.2,0.7\n",
                encoding="utf-8",
            )
            before = src.read_text(encoding="utf-8")
            loose = root / "loose.png"
            tight = root / "tight.png"
            render_volcano_r(
                src,
                {"title": "Volcano", "edit_kind": "analysis_param", "thresholds": {"p": 0.05, "log2fc": 1}},
                loose,
            )
            render_volcano_r(
                src,
                {"title": "Volcano tight", "edit_kind": "analysis_param", "thresholds": {"p": 0.01, "log2fc": 1}},
                tight,
            )
            self.assertEqual(src.read_text(encoding="utf-8"), before)
            for png in (loose, tight):
                self.assertTrue(png.with_suffix(".pdf").is_file())
                self.assertTrue(png.with_suffix(".svg").is_file())
            loose_rec = json.loads(loose.with_suffix(".edit_record.json").read_text(encoding="utf-8"))
            tight_rec = json.loads(tight.with_suffix(".edit_record.json").read_text(encoding="utf-8"))
            self.assertTrue(loose_rec["source_unchanged"])
            self.assertGreater(loose_rec["n_up"], tight_rec["n_up"])
            self.assertEqual(tight_rec["n_up"], 1)
            self.assertEqual(tight_rec["n_down"], 1)


if __name__ == "__main__":
    unittest.main()
