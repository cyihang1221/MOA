"""Agent B step8 变体产物 → Agent C 语义改图的对接测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from web_frontend.backend.plot_edit_registry import (
    get_plot_spec,
    list_editable_plots,
    plot_data_files_ready,
    plot_type_from_stem,
)
from web_frontend.backend.plot_theme import normalize_plot_config
from web_frontend.backend.semantic_plot_renderer import build_vegalite_spec


def _touch_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n")


def _spec_for(plot_type: str, data_dir: Path, metadata_csv: Path | None = None) -> dict:
    config = normalize_plot_config(None, plot_type=plot_type, color_keys=[])
    return build_vegalite_spec(
        plot_type=plot_type,
        data_dir=data_dir,
        metadata_csv=metadata_csv,
        plot_config=config,
    )


def _write_metax_result(path: Path) -> None:
    pd.DataFrame(
        {
            "feature_id": ["F1", "F2", "F3"],
            "mz": [100.0, 200.0, 300.0],
            "rt_med": [1.0, 2.0, 3.0],
            "vip": [1.4, 0.8, 2.1],
            "statistic": [3.1, 0.4, 5.0],
            "pvalue": [0.001, 0.4, 0.0001],
            "padj": [0.01, 0.5, 0.001],
            "log2fc": [1.8, 0.1, -2.4],
            "significant": [True, False, True],
        }
    ).to_csv(path, index=False)


def _write_simca_result(path: Path) -> None:
    pd.DataFrame(
        {
            "feature_id": ["F1", "F2", "F3"],
            "vip": [2.2, 1.1, 0.4],
            "loading_p1": [0.31, -0.12, 0.05],
            "pcorr": [0.82, -0.44, 0.10],
            "mz": [100.0, 200.0, 300.0],
            "rt_med": [1.0, 2.0, 3.0],
            "log2fc": [1.5, -0.9, 0.2],
            "pvalue": [0.002, 0.03, 0.6],
            "padj": [0.02, 0.08, 0.7],
            "significant": [True, False, False],
        }
    ).to_csv(path, index=False)


class AgentBStemMappingTest(unittest.TestCase):
    def test_variant_stems_map_to_existing_types(self) -> None:
        cases = {
            "statistical_analysis_metax_pca_plot": "pca",
            "statistical_analysis_metax_volcano_plot": "volcano",
            "statistical_analysis_sklearn_volcano_plot": "volcano",
            "statistical_analysis_simca_vip_plot": "vip_bar",
            "statistical_analysis_simca_permutation_plot": "plsda_permutation",
        }
        for stem, expected in cases.items():
            self.assertEqual(plot_type_from_stem(stem), expected, stem)

    def test_new_specs_registered(self) -> None:
        cases = {
            "statistical_analysis_simca_splot": "splot",
            "statistical_analysis_simca_outlier_plot": "opls_outlier",
            "statistical_analysis_metax_roc_plot": "roc_auc_hist",
            "statistical_analysis_metax_significance_venn": "significance_venn",
            "statistical_analysis_metax_log2fc_hist": "log2fc_hist",
        }
        for stem, expected in cases.items():
            self.assertEqual(plot_type_from_stem(stem), expected, stem)
            self.assertIsNotNone(get_plot_spec(expected))


class AgentBSemanticRenderTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_metax_result_renders_as_volcano(self) -> None:
        _write_metax_result(self.root / "statistical_analysis_metax_result.csv")
        spec = _spec_for("volcano", self.root)
        xs = [item["x"] for item in spec["data"]["values"]]
        self.assertEqual(len(xs), 3)
        self.assertTrue(all("y" in item for item in spec["data"]["values"]))

    def test_simca_result_renders_as_vip_bar(self) -> None:
        _write_simca_result(self.root / "statistical_analysis_simca_result.csv")
        spec = _spec_for("vip_bar", self.root)
        features = [item["feature"] for item in spec["data"]["values"]]
        self.assertEqual(features[0], "F1")

    def test_metax_pca_scores_alias(self) -> None:
        pd.DataFrame(
            {"PC1": [1.0, -1.0], "PC2": [0.5, -0.5]},
            index=["S1.mzML", "S2.mzML"],
        ).to_csv(self.root / "statistical_analysis_metax_pca_scores.csv")
        metadata = self.root / "metadata.csv"
        pd.DataFrame({"Sample": ["S1.mzML", "S2.mzML"], "Group": ["A", "B"]}).to_csv(
            metadata, index=False
        )
        spec = _spec_for("pca", self.root, metadata)
        self.assertEqual(len(spec["data"]["values"]), 2)

    def test_splot(self) -> None:
        _write_simca_result(self.root / "statistical_analysis_simca_result.csv")
        spec = _spec_for("splot", self.root)
        self.assertEqual(len(spec["data"]["values"]), 3)
        self.assertIn("layer", spec)

    def test_outlier_plot(self) -> None:
        pd.DataFrame(
            {
                "sample": ["S1", "S2", "S3"],
                "score_distance": [1.2, 3.5, 0.9],
                "orthogonal_distance": [2.1, 8.0, 1.4],
                "sd_threshold": [2.7, 2.7, 2.7],
                "od_threshold": [5.0, 5.0, 5.0],
                "is_outlier": [False, True, False],
            }
        ).to_csv(self.root / "statistical_analysis_simca_outlier_distances.csv", index=False)
        spec = _spec_for("opls_outlier", self.root)
        statuses = {item["status"] for item in spec["data"]["values"]}
        self.assertEqual(statuses, {"Outlier", "Normal"})

    def test_roc_auc_hist(self) -> None:
        pd.DataFrame(
            {
                "feature_id": ["F1", "F2", "F3"],
                "auroc": [0.91, 0.55, 0.72],
                "ci_low": [0.8, 0.4, 0.6],
                "ci_high": [0.99, 0.7, 0.85],
            }
        ).to_csv(self.root / "statistical_analysis_metax_roc.csv", index=False)
        spec = _spec_for("roc_auc_hist", self.root)
        self.assertEqual(len(spec["data"]["values"]), 3)

    def test_log2fc_hist(self) -> None:
        pd.DataFrame(
            {
                "ID": ["F1", "F2", "F3"],
                "ratio": [2.0, 0.5, 1.0],
                "VIP": [1.2, 0.7, 1.9],
            }
        ).to_csv(self.root / "statistical_analysis_metax_quant_table.csv", index=False)
        spec = _spec_for("log2fc_hist", self.root)
        values = sorted(item["value"] for item in spec["data"]["values"])
        self.assertEqual(values, [-1.0, 0.0, 1.0])

    def test_significance_venn(self) -> None:
        pd.DataFrame(
            {
                "feature_id": ["F1", "F2", "F3", "F4"],
                "t_test_bh_sig": [True, True, False, False],
                "wilcox_bh_sig": [True, False, False, False],
                "vip_sig": [True, False, True, False],
                "intersection": ["t.test+wilcox.test+VIP", "t.test", "VIP", ""],
            }
        ).to_csv(self.root / "statistical_analysis_metax_significance_sets.csv", index=False)
        spec = _spec_for("significance_venn", self.root)
        sets = {item["set"] for item in spec["data"]["values"]}
        self.assertEqual(sets, {"t.test+wilcox.test+VIP", "t.test", "VIP"})

    def test_permutation_from_simca_csv(self) -> None:
        pd.DataFrame(
            {
                "perm_i": [1, 2, 3],
                "R2X(cum)": [0.5, 0.4, 0.45],
                "R2Y(cum)": [0.9, 0.3, 0.35],
                "Q2(cum)": [0.7, 0.1, 0.05],
                "RMSEE": [0.2, 0.4, 0.5],
                "pre": [1, 1, 1],
                "ort": [1, 1, 1],
                "sim": [1.0, 0.2, 0.35],
            }
        ).to_csv(self.root / "statistical_analysis_simca_permutation.csv", index=False)
        spec = _spec_for("plsda_permutation", self.root)
        metrics = {item["metric"] for item in spec["data"]["values"]}
        self.assertEqual(metrics, {"R2Y", "Q2"})

    def test_listing_marks_variant_png_as_semantic(self) -> None:
        _write_simca_result(self.root / "statistical_analysis_simca_result.csv")
        _touch_png(self.root / "statistical_analysis_simca_splot.png")
        _touch_png(self.root / "statistical_analysis_simca_vip_plot.png")
        listed = {item["stem"]: item for item in list_editable_plots(self.root)}
        self.assertEqual(listed["statistical_analysis_simca_splot"]["edit_mode"], "semantic")
        self.assertEqual(listed["statistical_analysis_simca_vip_plot"]["plot_type"], "vip_bar")
        self.assertEqual(listed["statistical_analysis_simca_vip_plot"]["edit_mode"], "semantic")

    def _write_fbmn_tables(self) -> None:
        pd.DataFrame(
            {
                "feature_id": ["FT1", "FT2", "FT3", "FT4"],
                "precursor_mz": [200.1, 214.1, 330.2, 118.0],
                "rt": [1.0, 1.2, 3.4, 0.8],
                "degree": [2, 2, 1, 0],
                "molecular_family": ["F1", "F1", "F2", "singleton"],
                "mean_Case": [1000.0, 1200.0, 400.0, 50.0],
                "mean_Control": [500.0, 700.0, 900.0, 60.0],
            }
        ).to_csv(self.root / "fbmn_nodes.csv", index=False)
        pd.DataFrame(
            {
                "source": ["FT1", "FT1"],
                "target": ["FT2", "FT3"],
                "cosine": [0.92, 0.75],
                "pearson_r": [0.8, 0.3],
                "precursor_delta_da": [14.0, 130.1],
            }
        ).to_csv(self.root / "fbmn_edges.csv", index=False)

    def test_topology_layout_derived_from_fbmn_tables(self) -> None:
        self._write_fbmn_tables()
        spec = _spec_for("network_topology", self.root)
        self.assertTrue(spec.get("layer") or spec.get("mark"))

    def test_group_intensity_derived_from_node_means(self) -> None:
        self._write_fbmn_tables()
        spec = _spec_for("fbmn_group_intensity", self.root)
        groups = {item["group"] for item in spec["data"]["values"]}
        self.assertEqual(groups, {"Case", "Control"})
        families = {item["family"] for item in spec["data"]["values"]}
        self.assertNotIn("singleton", families)

    def test_motif_network_derived_from_scores_matrix(self) -> None:
        pd.DataFrame(
            {
                "Motif_0": [0.6, 0.1, 0.0],
                "Motif_1": [0.2, 0.7, 0.02],
            },
            index=["spec1", "spec2", "spec3"],
        ).to_csv(self.root / "spectra_motif_scores.csv")
        spec = _spec_for("mass2motif_network", self.root)
        self.assertIn("layer", spec)

    def test_network_plots_listed_as_semantic(self) -> None:
        self._write_fbmn_tables()
        for name in ("network_topology", "fbmn_group_intensity", "cosine_distribution"):
            _touch_png(self.root / f"{name}.png")
        listed = {item["stem"]: item for item in list_editable_plots(self.root)}
        for name in ("network_topology", "fbmn_group_intensity", "cosine_distribution"):
            self.assertEqual(listed[name]["edit_mode"], "semantic", name)

    def test_data_readiness_uses_alias(self) -> None:
        _write_metax_result(self.root / "statistical_analysis_metax_result.csv")
        spec = get_plot_spec("volcano")
        assert spec is not None
        self.assertTrue(plot_data_files_ready(self.root, spec.data_files))


if __name__ == "__main__":
    unittest.main()
