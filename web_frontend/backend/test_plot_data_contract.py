"""PLOT_SPECS 数据契约：每个图型都有生产者声明，且都有语义渲染器。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.plot_data_contract import (
    PAPER_ONLY_FILES,
    PLOT_DATA_CONTRACT,
    contract_by_plot_type,
)
from web_frontend.backend.plot_edit_registry import (
    PLOT_SPECS,
    _NETWORK_DATA_ALIASES,
    get_plot_spec,
    plot_spec_data_ready,
)
from web_frontend.backend.plot_theme import normalize_plot_config
from web_frontend.backend.semantic_plot_renderer import build_vegalite_spec


class PlotDataContractTest(unittest.TestCase):
    def test_every_plot_spec_has_contract(self) -> None:
        registered = {spec.plot_type for spec in PLOT_SPECS}
        contracted = {item.plot_type for item in PLOT_DATA_CONTRACT}
        self.assertEqual(registered, contracted)

    def test_contract_plot_types_exist(self) -> None:
        for item in PLOT_DATA_CONTRACT:
            self.assertIsNotNone(get_plot_spec(item.plot_type), item.plot_type)

    def test_every_plot_type_has_semantic_renderer(self) -> None:
        empty = Path(tempfile.mkdtemp())
        config = normalize_plot_config(None, plot_type="pca", color_keys=[])
        missing = []
        for spec in PLOT_SPECS:
            try:
                build_vegalite_spec(
                    plot_type=spec.plot_type,
                    data_dir=empty,
                    metadata_csv=None,
                    plot_config=config,
                )
            except ValueError as exc:
                if "暂不支持语义渲染" in str(exc):
                    missing.append(spec.plot_type)
            except Exception:
                pass
        self.assertEqual(missing, [])

    def test_paper_files_not_aliased_to_mixomics(self) -> None:
        mixomics = {"heatmap_top_vip_matrix.csv", "vip_scores.csv", "pca_scores.csv"}
        for logical, candidates in _NETWORK_DATA_ALIASES.items():
            if logical in PAPER_ONLY_FILES:
                overlap = mixomics.intersection(candidates)
                self.assertFalse(overlap, f"{logical} 不应别名到 {overlap}")
            for name in candidates:
                if name in PAPER_ONLY_FILES:
                    overlap = mixomics.intersection(candidates)
                    self.assertFalse(overlap, f"{logical} 候选含论文文件却指向 {overlap}")

    def test_relative_abundance_any_of_two_files(self) -> None:
        spec = get_plot_spec("relative_abundance_heatmap")
        assert spec is not None
        self.assertEqual(spec.data_mode, "any")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "volatile_differential_abundance.csv").write_text(
                "compound,Supreme\nmet_1,0.2\n", encoding="utf-8"
            )
            self.assertTrue(plot_spec_data_ready(root, spec))
            spec_volcano = get_plot_spec("volcano")
            assert spec_volcano is not None
            self.assertFalse(plot_spec_data_ready(root, spec_volcano))


class TeaPaperSemanticRenderTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _spec(self, plot_type: str) -> dict:
        config = normalize_plot_config(None, plot_type=plot_type, color_keys=[])
        return build_vegalite_spec(
            plot_type=plot_type,
            data_dir=self.root,
            metadata_csv=None,
            plot_config=config,
        )

    def test_constituent_bar(self) -> None:
        (self.root / "tea_constituents.csv").write_text(
            "grade,metric,mean,sd,significance_letter\n"
            "Supreme,TPC,1.0,0.1,a\n"
            "Premium,TPC,0.8,0.1,b\n",
            encoding="utf-8",
        )
        spec = self._spec("constituent_bar")
        self.assertIn("facet", spec)
        self.assertEqual(len(spec["data"]["values"]), 2)

    def test_bioactivity_and_sensory(self) -> None:
        (self.root / "bioactivity_assays.csv").write_text(
            "grade,assay,value,sd,unit\nSupreme,DPPH_IC50,30,2,ug/mL\n",
            encoding="utf-8",
        )
        (self.root / "sensory_scores.csv").write_text(
            "grade,attribute,score,sd\nSupreme,bitterness,2.2,0.3\nPremium,umami,1.1,0.2\n",
            encoding="utf-8",
        )
        bio = self._spec("bioactivity_bar")
        sensory = self._spec("sensory_scores")
        self.assertIn("facet", bio)
        self.assertEqual(len(sensory["data"]["values"]), 2)

    def test_heatmaps_and_permutation(self) -> None:
        (self.root / "hca_matrix.csv").write_text(
            "Sample,feat_1,feat_2\nS1,1,2\nS2,3,4\n", encoding="utf-8"
        )
        (self.root / "correlation_matrix.csv").write_text(
            "variable,TPC,TFC\nTPC,1.0,-0.5\nTFC,-0.5,1.0\n", encoding="utf-8"
        )
        (self.root / "differential_metabolites_abundance.csv").write_text(
            "compound,Supreme,Premium\nmet_1,0.1,0.2\n", encoding="utf-8"
        )
        (self.root / "plsda_permutation.csv").write_text(
            "permutation,R2,Q2\n0,0.9,0.7\n1,0.2,0.1\n", encoding="utf-8"
        )
        hca = self._spec("hca_heatmap")
        corr = self._spec("correlation_heatmap")
        abund = self._spec("relative_abundance_heatmap")
        perm = self._spec("plsda_permutation")
        self.assertEqual(hca["mark"], "rect")
        self.assertEqual(corr["mark"], "rect")
        self.assertEqual(abund["mark"], "rect")
        metrics = {item["metric"] for item in perm["data"]["values"]}
        self.assertEqual(metrics, {"R2Y", "Q2"})

    def test_paper_types_classified(self) -> None:
        by_type = contract_by_plot_type()
        for name in (
            "constituent_bar",
            "relative_abundance_heatmap",
            "hca_heatmap",
            "correlation_heatmap",
            "bioactivity_bar",
            "sensory_scores",
        ):
            self.assertEqual(by_type[name].source, "paper_or_upload", name)


if __name__ == "__main__":
    unittest.main()
