"""论文文件名 ↔ B 目录契约，以及 Skill 参数进入 tool_parameters。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from web_frontend.backend.agent_b.plan_normalize import normalize_plan_for_b
from web_frontend.backend.agent_b.skill_param_inject import apply_skill_parameters, parse_skill_parameters
from web_frontend.backend.agent_c.figure_pipeline import match_figures
from web_frontend.backend.agent_c.paper_reproduction import load_repro_recipe
from web_frontend.backend.agent_c.results_inventory import inventory_results
from web_frontend.backend.b_paper_contract import (
    collect_skill_parameters,
    resolve_logical_file,
    resolve_logical_record,
)

CATALOG = {
    "schema_version": 1,
    "stages": {
        "feature_detection": {},
        "statistical_analysis": {},
        "missing_value_imputation": {},
    },
    "tools": [
        {
            "keyword": "mixOmics",
            "stage": "statistical_analysis",
            "aliases": [],
            "support_status": "supported",
            "mcp_tools": ["statistical_analysis_mixomics"],
        },
        {
            "keyword": "XCMS-Centwave",
            "stage": "feature_detection",
            "aliases": [],
            "support_status": "supported",
            "mcp_tools": ["data_preprocessing_xcms"],
        },
        {
            "keyword": "MZMine-Pipeline",
            "stage": "feature_detection",
            "aliases": ["MZmine"],
            "support_status": "supported",
            "mcp_tools": ["data_preprocessing_mzmine"],
        },
        {
            "keyword": "kNN",
            "stage": "missing_value_imputation",
            "aliases": [],
            "support_status": "supported",
            "mcp_tools": ["feature_filtering_and_missing_value_imputation_knn"],
        },
        {
            "keyword": "SIMCA",
            "stage": "statistical_analysis",
            "aliases": [],
            "support_status": "supported",
            "mcp_tools": ["statistical_analysis_simca"],
        },
    ],
}


class BPaperFileMapTest(unittest.TestCase):
    def test_mixomics_pca_maps_and_does_not_fill_volatile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "mixOmics" / "结果"
            nested.mkdir(parents=True)
            (nested / "pca_scores.csv").write_text("sample,PC1\nA,0.1\n", encoding="utf-8")
            pca = resolve_logical_file(root, "pca_scores.csv")
            self.assertIsNotNone(pca)
            self.assertEqual(pca.name, "pca_scores.csv")
            self.assertIn("mixOmics", pca.as_posix())
            vol = resolve_logical_record(root, "volatile_pca_scores.csv")
            self.assertEqual(vol["status"], "missing")
            self.assertIn("不能用", vol["notes"])
            tea = resolve_logical_record(root, "tea_constituents.csv")
            self.assertEqual(tea["status"], "missing")

    def test_permutation_from_simca_not_from_pca(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            simca = root / "SIMCA" / "结果"
            simca.mkdir(parents=True)
            (simca / "statistical_analysis_simca_permutation.csv").write_text(
                "perm_i,R2Y(cum),Q2(cum)\n1,0.9,0.7\n", encoding="utf-8"
            )
            (root / "mixOmics" / "结果").mkdir(parents=True)
            (root / "mixOmics" / "结果" / "pca_scores.csv").write_text(
                "sample,PC1\nA,0.1\n", encoding="utf-8"
            )
            rec = resolve_logical_record(root, "plsda_permutation.csv")
            self.assertEqual(rec["status"], "present")
            self.assertIn("simca_permutation", rec["rel"])
            self.assertNotIn("pca_scores", rec["rel"])

    def test_inventory_and_match_figures_do_not_reuse_lcms_pca_for_fig2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "mixOmics" / "结果"
            nested.mkdir(parents=True)
            (nested / "pca_scores.csv").write_text("sample,PC1,PC2\nA,0.1,0.2\n", encoding="utf-8")
            inv = inventory_results(root)
            self.assertEqual(inv["file_map"]["pca_scores.csv"]["status"], "present")
            self.assertEqual(inv["file_map"]["volatile_pca_scores.csv"]["status"], "missing")
            plan = {
                "required_visualization": [
                    {
                        "figure_id": "Fig 2A",
                        "plot_type": "pca",
                        "source_files": ["volatile_pca_scores.csv"],
                    },
                    {
                        "figure_id": "Fig 5A",
                        "plot_type": "pca",
                        "source_files": ["pca_scores.csv"],
                    },
                ]
            }
            jobs = match_figures(plan, inv, figure_mode="plan")
            by_id = {j["figure_id"]: j for j in jobs}
            self.assertEqual(by_id["Fig 2A"]["status"], "missing_data")
            self.assertEqual(by_id["Fig 5A"]["status"], "ready")
            contract = Path(inv["contract_dir"])
            self.assertTrue((contract / "pca_scores.csv").is_file())
            self.assertFalse((contract / "volatile_pca_scores.csv").is_file())


class SkillParamInjectTest(unittest.TestCase):
    def test_parse_vip_and_uv(self) -> None:
        parsed = parse_skill_parameters("GC-MS UV-scaling；PLS-DA VIP>1.5；MZmine 预处理")
        self.assertEqual(parsed.get("vip_threshold"), 1.5)
        self.assertEqual(parsed.get("scale_method"), "autoscale")
        self.assertEqual(parsed.get("prefer_preprocess"), "mzmine")

    def test_recipe_lcms_vip_wins_and_rewrites_mzmine(self) -> None:
        recipe = load_repro_recipe("duyun_maojian_fochx_2026")
        params = collect_skill_parameters(recipe=recipe)
        self.assertEqual(params.get("vip_threshold"), 1.2)
        self.assertEqual(params.get("volatile_vip_threshold"), 1.5)
        self.assertEqual(params.get("prefer_preprocess"), "mzmine")
        self.assertTrue(params.get("rewrite_preprocess"))
        self.assertEqual(params.get("scale_method"), "autoscale")

        plan = {
            "goal": "复现都匀毛尖",
            "steps": [
                {
                    "step_number": 1,
                    "description": "peak picking",
                    "tools": ["XCMS-Centwave"],
                    "stage": "feature_detection",
                    "input_filename": "mzml",
                    "output_filename": "features",
                },
                {
                    "step_number": 2,
                    "description": "stats",
                    "tools": ["mixomics"],
                    "stage": "statistical_analysis",
                    "input_filename": "features",
                    "output_filename": "stats",
                },
            ],
        }
        normalized, _ = normalize_plan_for_b(plan, CATALOG)
        with patch(
            "web_frontend.backend.agent_b.skill_param_inject.mzmine_headless_ready",
            return_value=(True, "test"),
        ):
            apply_skill_parameters(normalized, CATALOG, sidecar=params)
        tools = [step["tools"][0] for step in normalized["steps"] if step["tools"][0] != "kNN"]
        self.assertIn("MZMine-Pipeline", tools)
        stats = next(s for s in normalized["steps"] if "mixOmics" in s["tools"])
        slot = stats["tool_parameters"]["mixOmics"]
        self.assertEqual(slot.get("vip_threshold"), 1.2)
        self.assertEqual(slot.get("scale_method"), "autoscale")
        self.assertEqual(
            stats["tool_parameters"]["statistical_analysis_mixomics"]["vip_threshold"],
            1.2,
        )
        self.assertTrue(params.get("rewrite_preprocess"))
        self.assertNotIn("n_permutations", slot)

    def test_mzmine4_without_user_file_keeps_xcms(self) -> None:
        plan = {
            "goal": "复现都匀毛尖",
            "steps": [
                {
                    "step_number": 1,
                    "description": "peak picking",
                    "tools": ["XCMS-Centwave"],
                    "stage": "feature_detection",
                    "input_filename": "mzml",
                    "output_filename": "features",
                }
            ],
        }
        normalized, _ = normalize_plan_for_b(plan, CATALOG)
        with patch(
            "web_frontend.backend.agent_b.skill_param_inject.mzmine_headless_ready",
            return_value=(False, "当前 MZmine 是 4.x，需要 .mzuser"),
        ):
            warnings = apply_skill_parameters(
                normalized,
                CATALOG,
                sidecar={"prefer_preprocess": "mzmine", "rewrite_preprocess": True},
            )
        self.assertEqual(normalized["steps"][0]["tools"], ["XCMS-Centwave"])
        self.assertTrue(any("R 作图" in w for w in warnings))

    def test_missing_mzmine_records_substitution(self) -> None:
        catalog = {
            "tools": [t for t in CATALOG["tools"] if t["keyword"] != "MZMine-Pipeline"]
        }
        plan = {
            "goal": "g",
            "steps": [
                {
                    "step_number": 1,
                    "description": "xcms",
                    "tools": ["XCMS-Centwave"],
                    "stage": "feature_detection",
                    "input_filename": "a",
                    "output_filename": "b",
                }
            ],
        }
        normalized, _ = normalize_plan_for_b(plan, catalog)
        warnings = apply_skill_parameters(
            normalized,
            catalog,
            sidecar={"prefer_preprocess": "mzmine", "rewrite_preprocess": True},
        )
        self.assertEqual(normalized["steps"][0]["tools"], ["XCMS-Centwave"])
        self.assertTrue(any("MZmine" in w for w in warnings))
        self.assertEqual(
            normalized["steps"][0].get("software_substitution", {}).get("requested"),
            "MZmine",
        )

    def test_remap_mixomics_params_across_alias(self) -> None:
        plan = {
            "goal": "g",
            "steps": [
                {
                    "step_number": 1,
                    "description": "VIP > 1.2",
                    "tools": ["mixomics"],
                    "stage": "statistical_analysis",
                    "input_filename": "a",
                    "output_filename": "b",
                    "tool_parameters": {"mixomics": {"vip_threshold": 1.2}},
                }
            ],
        }
        normalized, _ = normalize_plan_for_b(plan, CATALOG)
        stats = next(s for s in normalized["steps"] if "mixOmics" in s["tools"])
        self.assertEqual(stats["tool_parameters"]["mixOmics"]["vip_threshold"], 1.2)
        self.assertEqual(
            stats["tool_parameters"]["statistical_analysis_mixomics"]["vip_threshold"],
            1.2,
        )


if __name__ == "__main__":
    unittest.main()
