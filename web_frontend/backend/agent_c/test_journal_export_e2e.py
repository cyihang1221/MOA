"""投稿导出端到端：PCA / 火山 / VIP / 热图必须产出 600dpi + 矢量 + sidecar。

合成数据始终跑；本机若有会话 60aca071 再对真实 mixOmics 结果跑一遍。
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from web_frontend.backend.agent_c.nature_distill.journal_export import (
    JOURNAL_DPI,
    JOURNAL_PLOT_TYPES,
)
from web_frontend.backend.agent_c.runner import run_agent_c

ROOT = Path(__file__).resolve().parents[3]
REAL_SESSION = ROOT / "outputspace" / "为当前的都匀毛尖数据进行非靶向代谢组分析_60aca071"
REAL_META = ROOT / "inputspace" / "为当前的都匀毛尖数据进行非靶向代谢组分析_60aca071" / "metadata.csv"

_FOUR = (
    ("pca", "pca_scores.csv"),
    ("volcano", "volcano_results.csv"),
    ("vip_bar", "vip_scores.csv"),
    ("heatmap_vip", "heatmap_top_vip_matrix.csv"),
)


def _four_plot_plan() -> dict:
    viz = []
    for i, (ptype, fname) in enumerate(_FOUR, start=1):
        viz.append(
            {
                "figure_id": f"Figure {i}",
                "plot_type": ptype,
                "title": ptype,
                "source_files": [fname],
                "purpose": f"投稿导出验收 {ptype}",
            }
        )
    return {
        "objective": "journal export e2e",
        "required_visualization": viz,
        "reporting_plan": {"language": "zh"},
    }


def _write_synthetic_results(root: Path) -> Path:
    results = root / "results"
    results.mkdir(parents=True)
    (results / "pca_scores.csv").write_text(
        ",PC1,PC2\nS1,1.2,0.3\nS2,0.9,-0.1\nS3,-1.1,0.4\nS4,-0.8,0.2\n",
        encoding="utf-8",
    )
    (results / "volcano_results.csv").write_text(
        "Feature,log2FC,pvalue,padj,neglog10p,Significant\n"
        "FT1,1.8,0.001,0.01,3.0,True\n"
        "FT2,-1.4,0.002,0.02,2.7,True\n"
        "FT3,0.2,0.4,0.8,0.4,False\n",
        encoding="utf-8",
    )
    (results / "vip_scores.csv").write_text(
        "Feature,VIP\nFT1,1.9\nFT2,1.3\nFT3,0.4\nFT4,2.2\n",
        encoding="utf-8",
    )
    (results / "heatmap_top_vip_matrix.csv").write_text(
        ",S1,S2,S3,S4\nFT1,0.1,0.2,-0.3,-0.1\nFT2,-0.4,-0.2,0.5,0.3\nFT3,0.0,0.1,0.2,-0.2\n",
        encoding="utf-8",
    )
    meta = root / "metadata.csv"
    meta.write_text("Sample,Group\nS1,A\nS2,A\nS3,B\nS4,B\n", encoding="utf-8")
    return results


def _assert_journal_bundle(figures: list[dict], captions: list[dict]) -> None:
    by_type = {str(f.get("plot_type")): f for f in figures}
    for ptype, source in _FOUR:
        item = by_type.get(ptype)
        self_msg = f"{ptype} 未出现在 C 产出中；有 {sorted(by_type)}"
        assert item is not None, self_msg
        assert item.get("status") == "rendered", f"{ptype} status={item.get('status')} {item.get('missing_reason')}"
        png = Path(str(item.get("png") or ""))
        assert png.is_file(), f"{ptype} 缺少 PNG"
        sidecar = png.with_name(png.stem + ".journal_export.json")
        assert sidecar.is_file(), f"{ptype} 缺少 {sidecar.name}"
        report = json.loads(sidecar.read_text(encoding="utf-8"))
        assert report.get("dpi") == JOURNAL_DPI, report
        assert report.get("pdf") and Path(str(report["pdf"])).is_file()
        assert report.get("svg") and Path(str(report["svg"])).is_file()
        assert "font_audit" in report
        assert report.get("collision_audit") == "skipped_until_matplotlib_geometry_gate"
        payload = item.get("journal_export") or {}
        cap_item = next((c for c in captions if c.get("plot_type") == ptype), {})
        cap_payload = cap_item.get("journal_export") or {}
        assert payload.get("dpi") == JOURNAL_DPI or cap_payload.get("dpi") == JOURNAL_DPI, (
            ptype,
            payload,
            cap_payload,
        )
        cap = next((c.get("caption") or "") for c in captions if c.get("plot_type") == ptype)
        assert source in cap, f"{ptype} 图注未写文件来源 {source!r}: {cap[:200]}"
        if ptype == "volcano":
            assert "p<0.05" in cap or "阈值" in cap
        if ptype == "vip_bar":
            assert "VIP>1.2" in cap or "VIP>" in cap


class JournalExportPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["MASSAGENT_FIGURE_VISION"] = "0"

    def test_synthetic_four_matplotlib_journal_exports(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = _write_synthetic_results(root)
            out = root / "agent_c_output"
            manifest = run_agent_c(
                plan=_four_plot_plan(),
                results_dir=results,
                output_dir=out,
                metadata_csv=root / "metadata.csv",
                figure_mode="plan",
                language="zh",
                use_llm=False,
                use_literature=False,
            )
            figures = list(manifest.get("figures") or [])
            captions = json.loads((out / "captions.json").read_text(encoding="utf-8"))
            rendered_types = {str(f.get("plot_type")) for f in figures if f.get("status") == "rendered"}
            core = {ptype for ptype, _ in _FOUR}
            self.assertTrue(core.issubset(JOURNAL_PLOT_TYPES))
            self.assertTrue(core.issubset(rendered_types), rendered_types)
            _assert_journal_bundle(figures, captions)

    @unittest.skipUnless(
        REAL_SESSION.is_dir() and (REAL_SESSION / "mixOmics" / "结果" / "volcano_results.csv").is_file(),
        "本机没有会话 60aca071 的 mixOmics 结果",
    )
    def test_real_session_four_journal_exports(self) -> None:
        meta = REAL_META if REAL_META.is_file() else None
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "agent_c_output"
            manifest = run_agent_c(
                plan=_four_plot_plan(),
                results_dir=REAL_SESSION,
                output_dir=out,
                metadata_csv=meta,
                figure_mode="plan",
                language="zh",
                use_llm=False,
                use_literature=False,
            )
            figures = list(manifest.get("figures") or [])
            captions = json.loads((out / "captions.json").read_text(encoding="utf-8"))
            _assert_journal_bundle(figures, captions)


if __name__ == "__main__":
    unittest.main()
