"""改图终稿走 R：ggplot2 / pheatmap，风格只作为参数。"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("MPLBACKEND", "Agg")

from web_frontend.backend.r_plot_backend import find_rscript, render_kegg_r, render_score_r, render_volcano_r


@unittest.skipUnless(find_rscript(), "需要 Rscript、ggplot2 与 pheatmap")
class RPlotBackendTest(unittest.TestCase):
    def test_score_style_changes_png(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pca_scores.csv").write_text(
                "sample,PC1,PC2\n"
                "A,-1.2,0.2\nB,-1.0,0.1\nC,-0.8,-0.2\nD,-1.1,0.0\n"
                "E,1.0,0.3\nF,1.1,-0.1\nG,0.9,0.2\nH,1.2,0.0\n",
                encoding="utf-8",
            )
            (root / "metadata.csv").write_text(
                "Sample,Group\nA,BK\nB,BK\nC,BK\nD,BK\nE,DY\nF,DY\nG,DY\nH,DY\n",
                encoding="utf-8",
            )
            simca = root / "simca.png"
            ggplot = root / "ggplot.png"
            common = dict(
                data_dir=root,
                metadata_csv=root / "metadata.csv",
                plot_type="pca",
            )
            render_score_r(output_path=simca, plot_config={"score_style": "simca", "title": "PCA", "show_sample_labels": False}, **common)
            render_score_r(output_path=ggplot, plot_config={"score_style": "ggplot", "title": "PCA", "show_sample_labels": False}, **common)
            self.assertTrue(simca.read_bytes().startswith(b"\x89PNG"))
            self.assertNotEqual(simca.read_bytes(), ggplot.read_bytes())

    def test_volcano_and_kegg_write_png(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            vol = root / "volcano_results.csv"
            vol.write_text(
                "Feature,log2FC,pvalue,neglog10p,Significant\n"
                "a,2,0.001,3,True\nb,-2,0.001,3,True\nc,0.1,0.5,0.3,False\n",
                encoding="utf-8",
            )
            out = root / "volcano.png"
            render_volcano_r(vol, {"title": "Volcano", "thresholds": {"p": 0.05, "log2fc": 1}}, out)
            self.assertGreater(out.stat().st_size, 1000)
            kegg = root / "kegg_compound_enrich.csv"
            kegg.write_text(
                "ID,Description,Count,p.adjust\nmap1,Path A,5,0.01\nmap2,Path B,2,0.2\n",
                encoding="utf-8",
            )
            bubble = root / "bubble.png"
            render_kegg_r(root, {"title": "KEGG"}, bubble, "kegg_bubble")
            self.assertTrue(bubble.read_bytes().startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
