"""PDF 导出：图片路径与排版。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.agent_c.pdf_export import (
    markdown_file_to_pdf,
    resolve_report_image_path,
    _split_caption,
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

    def test_split_caption_fields(self) -> None:
        lead, fields, notes = _split_caption(
            "**Figure 1.** PCA\n来源步骤：Step 4\n目的：看分组\n图注只陈述文件计数。"
        )
        self.assertIn("Figure 1", lead)
        keys = [k for k, _ in fields]
        self.assertEqual(keys, ["来源步骤", "目的"])
        self.assertTrue(any("文件计数" in n for n in notes))

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

    def test_pdf_renders_figure_cards_and_ecb_modules(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fig_dir = root / "agent_c_output" / "figures"
            fig_dir.mkdir(parents=True)
            png = fig_dir / "Figure_1__pca.png"
            Image.new("RGB", (320, 240), (40, 120, 200)).save(png)
            out = root / "agent_c_output"
            (out / "figure_cards.json").write_text(
                '{"layout":"figure_first","figure_cards":[{'
                '"figure_id":"Figure 1","plot_type":"pca","rel":"agent_c_output/figures/Figure_1__pca.png",'
                '"caption":"PCA 得分图。","blocks":{'
                '"e":{"title":"数据支撑","status":"ready","bullets":["10 个样本，2 组"]},'
                '"c":{"title":"读图观察（AI，供参考）","status":"placeholder",'
                '"placeholder_reason":"未启用 AI 深度解读"},'
                '"b":{"title":"图意解读","status":"ready","what_it_shows":"两组沿 PC1 分开。",'
                '"link_to_objective":"对应分组比较。","caveats":"仅描述分离，不断言机制。"}'
                "}}]}",
                encoding="utf-8",
            )
            (out / "report_insights.json").write_text(
                '{"summary":"完成分组比较与 PCA。"}',
                encoding="utf-8",
            )
            md = out / "final_report.md"
            md.write_text(
                "# 分析报告\n\n## 图表\n\n### Figure 1\n\n## 方法\n\n采用 PCA。\n",
                encoding="utf-8",
            )
            pdf = markdown_file_to_pdf(md, results_dir=root)
            self.assertTrue(pdf.is_file())
            self.assertGreater(pdf.stat().st_size, 8000)


if __name__ == "__main__":
    unittest.main()
