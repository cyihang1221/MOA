"""A/B/C 产物交接：峰表/MGF 选型、补 kNN、metadata n=1。"""
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.abc_contract import contract_document
from web_frontend.backend.agent_b.artifact_bridge import inspect_metadata_csv
from web_frontend.backend.agent_b.plan_normalize import (
    normalize_plan_for_b,
    sanitize_execution_parameters,
)
from web_frontend.backend.agent_c.contract import STANDARD_RESULT_FILES
from web_frontend.backend.agent_c.results_inventory import inventory_results
from web_frontend.backend.agent_backends import massomics_b_root


def _write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


class ArtifactResolveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = massomics_b_root()
        cls.b_root = root
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

    def _resolve(self):
        from src.tools._artifact_resolve import (
            materialize_identification_dir,
            materialize_peak_table_dir,
            resolve_feature_table_csv,
            resolve_spectra_mgf,
            supervised_design_ok,
        )

        return (
            resolve_feature_table_csv,
            materialize_peak_table_dir,
            resolve_spectra_mgf,
            materialize_identification_dir,
            supervised_design_ok,
        )

    def test_prefers_feature_table_over_intensity_matrix(self) -> None:
        resolve_feature_table_csv, *_ = self._resolve()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_csv(
                folder / "feature_values_into.csv",
                ["feature_id", "s1.mzML", "s2.mzML"],
                [["FT1", 10, 20]],
            )
            _write_csv(
                folder / "feature_definitions.csv",
                ["feature_id", "mzmed", "rtmed"],
                [["FT1", 100.1, 30.0]],
            )
            _write_csv(
                folder / "feature_table.csv",
                ["feature_id", "mz", "rt_med", "s1.mzML", "s2.mzML"],
                [["FT1", 100.1, 30.0, 10, 20]],
            )
            chosen = resolve_feature_table_csv(str(folder))
            self.assertEqual(Path(chosen).name, "feature_table.csv")

    def test_peak_staging_has_only_mz_table(self) -> None:
        _, materialize_peak_table_dir, *_ = self._resolve()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "xcms"
            dest = Path(tmp) / "staged"
            src.mkdir()
            _write_csv(
                src / "feature_values_into.csv",
                ["feature_id", "A", "B"],
                [["FT1", 1, 2]],
            )
            _write_csv(
                src / "feature_table.csv",
                ["feature_id", "mz", "rt_med", "A", "B"],
                [["FT1", 150.0, 12.0, 1, 2]],
            )
            out = Path(materialize_peak_table_dir(str(src), str(dest)))
            names = {p.name for p in out.glob("*.csv")}
            self.assertIn("feature_table.csv", names)
            self.assertNotIn("feature_values_into.csv", names)

    def test_mgf_falls_back_to_spectra(self) -> None:
        resolve_spectra_mgf = self._resolve()[2]
        materialize_identification_dir = self._resolve()[3]
        with tempfile.TemporaryDirectory() as tmp:
            xcms = Path(tmp) / "xcms"
            mix = Path(tmp) / "mixomics"
            staged = Path(tmp) / "id"
            xcms.mkdir()
            mix.mkdir()
            (xcms / "spectra.mgf").write_text("BEGIN IONS\nEND IONS\n", encoding="utf-8")
            _write_csv(
                xcms / "feature_table.csv",
                ["feature_id", "mz", "rt_med", "A"],
                [["FT1", 100.0, 10.0, 5]],
            )
            mgf = resolve_spectra_mgf(str(mix), extra_roots=[str(Path(tmp))])
            self.assertEqual(Path(mgf).name, "spectra.mgf")
            out = Path(
                materialize_identification_dir(
                    str(mix), str(staged), extra_roots=[str(Path(tmp))]
                )
            )
            self.assertTrue((out / "differential_spectra.mgf").is_file())
            self.assertTrue((out / "differential_feature_table.csv").is_file())

    def test_identification_truncates_large_mgf(self) -> None:
        materialize_identification_dir = self._resolve()[3]
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "xcms"
            dest = Path(tmp) / "id"
            src.mkdir()
            blocks = []
            for i in range(8):
                blocks.append(
                    f"BEGIN IONS\nPEPMASS={100 + i}\n1.0 10\nEND IONS\n"
                )
            (src / "spectra.mgf").write_text("".join(blocks), encoding="utf-8")
            _write_csv(
                src / "feature_table.csv",
                ["feature_id", "mz", "rt_med", "A"],
                [["FT1", 100.0, 10.0, 5]],
            )
            import os

            os.environ["ABC_MAX_ID_SPECTRA"] = "3"
            try:
                out = Path(materialize_identification_dir(str(src), str(dest)))
            finally:
                os.environ.pop("ABC_MAX_ID_SPECTRA", None)
            text = (out / "differential_spectra.mgf").read_text(encoding="utf-8")
            self.assertEqual(text.count("BEGIN IONS"), 3)
            note = (out / "handoff_note.txt").read_text(encoding="utf-8")
            self.assertIn("truncated=True", note)

    def test_n1_groups_not_supervised(self) -> None:
        supervised_design_ok = self._resolve()[4]
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "feature_table.csv"
            meta = Path(tmp) / "metadata.csv"
            _write_csv(
                table,
                ["feature_id", "mz", "rt_med", "DY-1-1.mzML", "DY-2-1.mzML"],
                [["FT1", 100.0, 10.0, 1, 2]],
            )
            _write_csv(meta, ["Sample", "Group"], [["DY-1-1", "DY-1"], ["DY-2-1", "DY-2"]])
            ok, payload = supervised_design_ok(str(table), str(meta))
            self.assertFalse(ok)
            self.assertEqual(payload["min_per_group"], 1)


class PlanHandoffTest(unittest.TestCase):
    def test_inserts_knn_before_mixomics(self) -> None:
        catalog = {
            "schema_version": 1,
            "stages": {},
            "tools": [
                {
                    "keyword": "XCMS-Centwave",
                    "stage": "feature_detection",
                    "aliases": [],
                    "support_status": "supported",
                    "mcp_tools": ["data_preprocessing_xcms"],
                },
                {
                    "keyword": "kNN",
                    "stage": "missing_value_imputation",
                    "aliases": ["KNN"],
                    "support_status": "supported",
                    "mcp_tools": ["feature_filtering_and_missing_value_imputation_knn"],
                },
                {
                    "keyword": "mixOmics",
                    "stage": "statistical_analysis",
                    "aliases": [],
                    "support_status": "supported",
                    "mcp_tools": ["statistical_analysis_mixomics"],
                },
            ],
        }
        plan = {
            "goal": "demo",
            "steps": [
                {"step_number": 1, "description": "peaks", "tools": ["xcms"]},
                {"step_number": 2, "description": "stats", "tools": ["mixomics"]},
            ],
        }
        out, warnings = normalize_plan_for_b(plan, catalog)
        tools = [step["tools"][0] for step in out["steps"]]
        self.assertEqual(tools, ["XCMS-Centwave", "kNN", "mixOmics"])
        self.assertTrue(any("kNN" in w for w in warnings))
        self.assertEqual(out["steps"][1]["input_filename"], out["steps"][0]["output_filename"])
        self.assertEqual(out["steps"][2]["input_filename"], out["steps"][1]["output_filename"])

    def test_fbmn_keeps_explicit_mgf_and_feature_table(self) -> None:
        catalog = {
            "tools": [
                {
                    "keyword": "Cosine",
                    "stage": "library_matching",
                    "support_status": "supported",
                    "mcp_tools": ["library_match_cosine"],
                    "primary_input": {"parameter": "input_dir"},
                },
                {
                    "keyword": "FBMN",
                    "stage": "network_analysis",
                    "support_status": "supported",
                    "mcp_tools": ["molecular_networking_fbmn"],
                    "primary_input": {"parameter": "input_mgf"},
                },
            ]
        }
        plan = {
            "goal": "demo",
            "steps": [
                {
                    "step_number": 1,
                    "stage": "library_matching",
                    "tools": ["Cosine"],
                    "input_filename": "/data/spectra.mgf",
                    "output_filename": "/data/library_matching_results",
                },
                {
                    "step_number": 2,
                    "stage": "network_analysis",
                    "tools": ["molecular_networking_fbmn"],
                    "input_filename": "/data/spectra.mgf",
                    "output_filename": "/data/network",
                    "tool_parameters": {
                        "molecular_networking_fbmn": {
                            "input_mgf": "/data/spectra.mgf",
                            "input_feature_table": "/data/feature_table.csv",
                            "output_dir": "/data/network",
                            "top_k": 10,
                        }
                    },
                },
            ],
        }
        out, _warnings = normalize_plan_for_b(plan, catalog)
        self.assertEqual(out["steps"][1]["input_filename"], "/data/spectra.mgf")
        registry = {
            "library_match_cosine": {
                "params": {"input_dir": {}, "output_dir": {}},
                "required": ["input_dir", "output_dir"],
            },
            "molecular_networking_fbmn": {
                "params": {
                    "input_mgf": {},
                    "input_feature_table": {},
                    "output_dir": {},
                    "top_k": {"type": "integer"},
                },
                "required": ["input_mgf", "input_feature_table", "output_dir"],
            },
        }
        sanitize_execution_parameters(out, catalog, registry)
        self.assertEqual(
            out["steps"][1]["input_filename"],
            ["/data/spectra.mgf", "/data/feature_table.csv"],
        )
        params = out["steps"][1]["tool_parameters"]["FBMN"]
        self.assertNotIn("input_feature_table", params)
        self.assertNotIn("input_mgf", params)
        self.assertEqual(params["top_k"], 10)

    def test_fbmn_puts_mgf_before_feature_table(self) -> None:
        catalog = {
            "tools": [
                {
                    "keyword": "FBMN",
                    "stage": "network_analysis",
                    "support_status": "supported",
                    "mcp_tools": ["molecular_networking_fbmn"],
                    "primary_input": {"parameter": "input_mgf"},
                }
            ]
        }
        plan = {
            "steps": [
                {
                    "step_number": 6,
                    "stage": "network_analysis",
                    "tools": ["FBMN"],
                    "input_filename": "/data/feature_table.csv, /data/spectra.mgf",
                    "output_filename": "/data/network",
                    "tool_parameters": {"FBMN": {"top_k": 10}},
                }
            ]
        }
        out, _warnings = normalize_plan_for_b(plan, catalog)
        registry = {
            "molecular_networking_fbmn": {
                "params": {
                    "input_mgf": {},
                    "input_feature_table": {},
                    "output_dir": {},
                    "top_k": {"type": "integer"},
                },
                "required": ["input_mgf", "input_feature_table", "output_dir"],
            }
        }
        sanitize_execution_parameters(out, catalog, registry)
        self.assertEqual(
            out["steps"][0]["input_filename"],
            ["/data/spectra.mgf", "/data/feature_table.csv"],
        )

    def test_mummichog_enables_mass_mapping_when_unset(self) -> None:
        catalog = {
            "tools": [
                {
                    "keyword": "mummichog",
                    "stage": "enrichment_analysis",
                    "support_status": "supported",
                    "mcp_tools": ["enrichment_analysis_mummichog"],
                    "primary_input": {"parameter": "input_dir"},
                }
            ]
        }
        plan = {
            "steps": [
                {
                    "step_number": 7,
                    "stage": "enrichment_analysis",
                    "tools": ["mummichog"],
                    "input_filename": "/data/differential_metabolites.csv",
                    "output_filename": "/data/enrichment",
                    "tool_parameters": {"mummichog": {}},
                }
            ]
        }
        out, _warnings = normalize_plan_for_b(plan, catalog)
        registry = {
            "enrichment_analysis_mummichog": {
                "params": {
                    "input_dir": {},
                    "output_dir": {},
                    "use_network_kegg": {"type": "boolean"},
                },
                "required": ["input_dir", "output_dir"],
            }
        }
        sanitize_execution_parameters(out, catalog, registry)
        params = out["steps"][0]["tool_parameters"]["mummichog"]
        self.assertTrue(params["use_network_kegg"])

    def test_peakwidth_comma_string_becomes_array(self) -> None:
        catalog = {
            "tools": [
                {
                    "keyword": "XCMS-Centwave",
                    "stage": "feature_detection",
                    "support_status": "supported",
                    "mcp_tools": ["data_preprocessing_xcms"],
                    "primary_input": {"parameter": "input_dir"},
                }
            ]
        }
        plan = {
            "steps": [
                {
                    "step_number": 2,
                    "stage": "feature_detection",
                    "tools": ["XCMS-Centwave"],
                    "input_filename": "/data/mzml",
                    "output_filename": "/data/peaks",
                    "tool_parameters": {"XCMS-Centwave": {"peakwidth": "5,20", "ppm": 15}},
                }
            ]
        }
        out, _warnings = normalize_plan_for_b(plan, catalog)
        registry = {
            "data_preprocessing_xcms": {
                "params": {
                    "input_dir": {},
                    "output_dir": {},
                    "peakwidth": {"type": "array", "default": [5, 20]},
                    "ppm": {"type": "number"},
                },
                "required": ["input_dir", "output_dir"],
            }
        }
        sanitize_execution_parameters(out, catalog, registry)
        params = out["steps"][0]["tool_parameters"]["XCMS-Centwave"]
        self.assertEqual(params["peakwidth"], [5, 20])
        self.assertEqual(params["ppm"], 15)


class RelocateMgfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = massomics_b_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

    def test_missing_mgf_is_not_replaced_by_previous_directory(self) -> None:
        from src.quality_engine import _relocate

        with tempfile.TemporaryDirectory() as tmp:
            mix = Path(tmp) / "mixOmics"
            xcms = Path(tmp) / "XCMS"
            mix.mkdir()
            xcms.mkdir()
            (xcms / "spectra.mgf").write_text("BEGIN IONS\nEND IONS\n", encoding="utf-8")
            stages = [
                {"output_dir": str(xcms)},
                {"output_dir": str(mix)},
            ]
            found = _relocate(stages, "input_dir", str(Path(tmp) / "peak_detection_results" / "spectra.mgf"))
            self.assertEqual(Path(found).name, "spectra.mgf")
            self.assertTrue(str(found).startswith(str(xcms)))

    def test_missing_statistics_csv_is_not_replaced_by_latest_directory(self) -> None:
        from src.quality_engine import _relocate

        with tempfile.TemporaryDirectory() as tmp:
            mix = Path(tmp) / "mixOmics"
            conv = Path(tmp) / "ThermoRawFileParser"
            mix.mkdir()
            conv.mkdir()
            _write_csv(
                mix / "differential_feature_table.csv",
                ["feature_id", "mz", "pvalue", "log2fc"],
                [["FT1", 100.0, 0.01, 1.2]],
            )
            stages = [
                {"output_dir": str(mix)},
                {"output_dir": str(conv)},
            ]
            found = _relocate(
                stages,
                "input_dir",
                str(Path(tmp) / "statistical_results" / "differential_metabolites.csv"),
            )
            self.assertEqual(Path(found).name, "differential_feature_table.csv")


class MetadataInspectTest(unittest.TestCase):
    def test_warns_n1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "metadata.csv"
            _write_csv(meta, ["Sample", "Group"], [["A", "g1"], ["B", "g2"]])
            text = inspect_metadata_csv(str(meta))
            self.assertIn("最小组内n=1", text)
            self.assertIn("PLS-DA", text)


class ContractAndCTest(unittest.TestCase):
    def test_abc_contract_lists_canonical_files(self) -> None:
        doc = contract_document()
        self.assertIn("canonical_files", doc)
        self.assertIn("feature_table_directory", doc["canonical_files"])

    def test_c_inventory_maps_nested_b_outputs(self) -> None:
        self.assertIn("feature_table.csv", STANDARD_RESULT_FILES)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "mixOmics" / "结果"
            nested.mkdir(parents=True)
            (nested / "pca_scores.csv").write_text("sample,PC1\nA,0.1\n", encoding="utf-8")
            (nested / "differential_metabolites.csv").write_text(
                "Feature,log2FC\nFT1,1.2\n", encoding="utf-8"
            )
            inv = inventory_results(root)
            self.assertEqual(inv["standard_files"].get("embeddings.csv"), "pca_scores.csv")
            self.assertEqual(
                inv["standard_files"].get("statistics.csv"), "differential_metabolites.csv"
            )


class ReuseStageTest(unittest.TestCase):
    def test_reuse_mzml_and_xcms_sentinels(self) -> None:
        from web_frontend.backend.agent_b.artifact_bridge import (
            scan_output_as_tool_result,
            stage_output_reusable,
        )

        with tempfile.TemporaryDirectory() as tmp:
            conv = Path(tmp) / "convert"
            xcms = Path(tmp) / "xcms"
            empty = Path(tmp) / "camera"
            conv.mkdir()
            xcms.mkdir()
            empty.mkdir()
            (conv / "a.mzML").write_text("mzml", encoding="utf-8")
            _write_csv(
                xcms / "feature_table.csv",
                ["feature_id", "mz", "rt_med", "A"],
                [["FT1", 100.0, 10.0, 1]],
            )
            self.assertTrue(
                stage_output_reusable("convert_raw_to_mzml_ThermoRawFileParser", str(conv))
            )
            self.assertTrue(stage_output_reusable("data_preprocessing_xcms", str(xcms)))
            self.assertFalse(
                stage_output_reusable(
                    "data_preprocessing_xcms", str(xcms), {"extract_ms2": True}
                )
            )
            (xcms / "spectra.mgf").write_text("BEGIN IONS\nEND IONS\n", encoding="utf-8")
            self.assertTrue(
                stage_output_reusable(
                    "data_preprocessing_xcms", str(xcms), {"extract_ms2": True}
                )
            )
            self.assertFalse(
                stage_output_reusable("redundant_feature_filtering_camera", str(empty))
            )
            payload = scan_output_as_tool_result("data_preprocessing_xcms", str(xcms))
            self.assertTrue(payload["success"])
            self.assertIn("feature_table.csv", payload["csv_summaries"])
            self.assertGreaterEqual(
                payload["csv_summaries"]["feature_table.csv"]["row_count"], 1
            )


class OutputLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = massomics_b_root()
        cls.b_root = root
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

    def test_canonical_dir_is_tool_then_results(self) -> None:
        from src.output_layout import canonical_output_dir, tool_folder_name

        self.assertEqual(tool_folder_name("CAMERA"), "CAMERA")
        mapped = tool_folder_name("", mcp_tool="statistical_analysis_mixomics")
        # catalog 已 lfs pull 时应为 mixOmics；仍是 LFS 指针时退回 MCP 名
        self.assertIn(mapped, {"mixOmics", "statistical_analysis_mixomics"})
        folder = "mixOmics" if mapped == "mixOmics" else mapped
        path = Path(canonical_output_dir("/tmp/会话", folder))
        self.assertEqual(path.name, "结果")
        self.assertEqual(path.parent.name, folder)

    def test_adopt_moves_legacy_category_dir(self) -> None:
        from web_frontend.backend.agent_b.artifact_bridge import adopt_legacy_output_dir

        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp)
            legacy = session / "data_preprocessing" / "data_preprocessing_xcms"
            legacy.mkdir(parents=True)
            _write_csv(
                legacy / "feature_table.csv",
                ["feature_id", "mz", "rt_med", "A"],
                [["FT1", 100.0, 10.0, 1]],
            )
            dest = session / "XCMS-Centwave" / "结果"
            moved = Path(
                adopt_legacy_output_dir(
                    "data_preprocessing_xcms",
                    str(dest),
                    str(session),
                )
            )
            self.assertEqual(moved, dest.resolve())
            self.assertTrue((dest / "feature_table.csv").is_file())
            self.assertFalse(legacy.exists())


if __name__ == "__main__":
    unittest.main()
