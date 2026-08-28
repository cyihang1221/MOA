"""PDF 导出：图片路径与排版。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.agent_c.pdf_export import (
    markdown_file_to_pdf,
    resolve_report_image_path,
)


class PdfExportTest(unittest.TestCase):
    def test_resolve_agent_c_output_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "agent_c_output" / "figures"
            out.mkdir(parents=True)
            png = out / "Figure_3__volcano_plot.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n")

            rel = "agent_c_output/figures/Figure_3__volcano_plot.png"
            resolved = resolve_report_image_path(
                rel,
                md_dir=root / "agent_c_output",
                results_dir=root,
            )
            self.assertEqual(resolved, png.resolve())

    def test_pdf_embeds_image_from_outputspace_rel(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fig_dir = root / "agent_c_output" / "figures"
            fig_dir.mkdir(parents=True)
            png = fig_dir / "Figure_1__pca.png"
            Image.new("RGB", (320, 240), (40, 120, 200)).save(png)
            md = root / "agent_c_output" / "final_report.md"
            md.write_text(
                "# 分析报告\n\n## 图表\n\n"
                "![Figure 1](agent_c_output/figures/Figure_1__pca.png)\n\n"
                "#### 数据支撑\n\n- PCA 得分 10 行\n",
                encoding="utf-8",
            )
            pdf = markdown_file_to_pdf(md, results_dir=root)
            self.assertTrue(pdf.is_file())
            self.assertGreater(pdf.stat().st_size, 8000)


if __name__ == "__main__":
    unittest.main()
