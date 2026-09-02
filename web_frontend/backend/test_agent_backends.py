"""Agent A/B 后端路由、B 计划规范化与定位单测。"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from web_frontend.backend.abc_contract import CONTRACT_ID, contract_document
from web_frontend.backend.agent_a.massomics_planner import coerce_plan_document
from web_frontend.backend.agent_a.massomics_tool_map import (
    plan_document_to_tasks,
    resolve_web_mcp_tool,
)
from web_frontend.backend.agent_b.plan_locate import find_massomics_plan_json
from web_frontend.backend.agent_b.plan_normalize import (
    normalize_plan_for_b,
    resolve_catalog_entry,
)
from web_frontend.backend.agent_backends import (
    agent_a_backend,
    agent_b_backend,
    backend_status,
    massomics_b_available,
    massomics_b_root,
    massomics_root,
)

MINI_CATALOG = {
    "schema_version": 1,
    "stages": {
        "statistical_analysis": {},
        "feature_detection": {},
        "enrichment_analysis": {},
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
            "keyword": "extract_differential_features",
            "stage": "statistical_analysis",
            "aliases": ["extract differential features"],
            "support_status": "supported",
            "mcp_tools": ["extract_differential_features"],
        },
        {
            "keyword": "XCMS-Centwave",
            "stage": "feature_detection",
            "aliases": ["XCMS-CentWave"],
            "support_status": "supported",
            "mcp_tools": ["data_preprocessing_xcms"],
        },
        {
            "keyword": "spectral_annotation",
            "stage": "library_matching",
            "aliases": ["spectral annotation"],
            "support_status": "supported",
            "mcp_tools": ["spectral_annotation"],
        },
        {
            "keyword": "KEGG compound enrichment",
            "stage": "enrichment_analysis",
            "aliases": ["kegg_compound_enrichment"],
            "support_status": "supported",
            "mcp_tools": ["kegg_compound_enrichment"],
        },
        {
            "keyword": "KEGG",
            "stage": "pathway_analysis",
            "aliases": [],
            "support_status": "supported",
            "mcp_tools": ["pathway_analysis_kegg"],
        },
    ],
}


class AgentBackendsTest(unittest.TestCase):
    def test_default_backends(self) -> None:
        for key in ("WEB_AGENT_A_BACKEND", "WEB_AGENT_B_BACKEND"):
            os.environ.pop(key, None)
        self.assertEqual(agent_a_backend(), "massomics")
        self.assertEqual(agent_b_backend(), "massomics")

    def test_massomics_root_exists(self) -> None:
        root = massomics_root()
        self.assertTrue((root / "plan" / "schema.py").is_file())

    def test_massomics_b_worktree(self) -> None:
        root = massomics_b_root()
        self.assertEqual(root.name, "MassOmics-Agent-B")
        if massomics_b_available():
            self.assertTrue((root / "src" / "executor.py").is_file())
            self.assertTrue((root / "src" / "massomics_adapter.py").is_file())

    def test_backend_status_shape(self) -> None:
        st = backend_status()
        self.assertIn("agent_b_backend", st)
        self.assertIn("massomics_root", st)
        self.assertIn("massomics_b_root", st)
        self.assertIn("massomics_b_available", st)
        self.assertTrue(st["massomics_available"] or not st["massomics_available"])

    def test_abc_contract_keeps_three_agents(self) -> None:
        doc = contract_document()
        self.assertEqual(doc["contract_id"], CONTRACT_ID)
        self.assertIn("A", doc["agents"])
        self.assertIn("B", doc["agents"])
        self.assertIn("C", doc["agents"])
        self.assertIn("不把三者合成一个 Agent", doc["principle"])

    def test_resolve_web_mcp_tool(self) -> None:
        registered = {"statistical_analysis_mixomics", "data_preprocessing_xcms"}
        self.assertEqual(
            resolve_web_mcp_tool("mixomics", registered),
            "statistical_analysis_mixomics",
        )
        self.assertEqual(
            resolve_web_mcp_tool("xcms", registered),
            "data_preprocessing_xcms",
        )

    def test_coerce_list_filenames(self) -> None:
        raw = {
            "goal": "g",
            "steps": [
                {
                    "step_number": 1,
                    "description": "x",
                    "input_filename": ["a.raw", "b.raw"],
                    "output_filename": ["out/"],
                    "tools": "xcms",
                }
            ],
        }
        out = coerce_plan_document(raw)
        self.assertEqual(out["steps"][0]["input_filename"], "a.raw, b.raw")
        self.assertEqual(out["steps"][0]["output_filename"], "out/")
        self.assertEqual(out["steps"][0]["tools"], ["xcms"])

    def test_plan_document_to_tasks(self) -> None:
        plan = {
            "goal": "test",
            "steps": [
                {
                    "step_number": 1,
                    "description": "PCA and diff",
                    "input_filename": "feature_table.csv",
                    "output_filename": "statistical_results",
                    "tools": ["mixomics"],
                }
            ],
        }
        paths = {"upload": "/data/in", "outputspace": "/data/out"}
        registered = {"statistical_analysis_mixomics"}
        tasks = plan_document_to_tasks(plan, paths=paths, registered=registered)
        self.assertEqual(len(tasks), 1)
        self.assertIn("statistical_analysis_mixomics", tasks[0])


class AgentBPlanNormalizeTest(unittest.TestCase):
    def test_alias_and_stage_fill(self) -> None:
        plan = {
            "goal": "demo",
            "steps": [
                {
                    "step_number": 1,
                    "description": "peak picking",
                    "tools": ["xcms"],
                    "input_filename": "mzml",
                    "output_filename": "peaks",
                },
                {
                    "step_number": 2,
                    "description": "stats",
                    "tools": ["mixomics"],
                },
            ],
        }
        out, warnings = normalize_plan_for_b(plan, MINI_CATALOG)
        self.assertEqual(out["steps"][0]["tools"], ["XCMS-Centwave"])
        self.assertEqual(out["steps"][0]["stage"], "feature_detection")
        self.assertEqual(out["steps"][1]["tools"], ["mixOmics"])
        self.assertEqual(out["steps"][1]["stage"], "statistical_analysis")
        self.assertEqual(out["steps"][0]["mode"], "sequential")
        self.assertFalse(warnings)

    def test_mcp_name_reverse_map(self) -> None:
        entry = resolve_catalog_entry("statistical_analysis_mixomics", MINI_CATALOG)
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry["keyword"], "mixOmics")

    def test_downstream_mcp_tools_map_and_not_pathway_kegg(self) -> None:
        extract = resolve_catalog_entry("extract_differential_features", MINI_CATALOG)
        annot = resolve_catalog_entry("spectral_annotation", MINI_CATALOG)
        kegg = resolve_catalog_entry("kegg_compound_enrichment", MINI_CATALOG)
        pathway = resolve_catalog_entry("KEGG", MINI_CATALOG)
        self.assertEqual(extract["keyword"], "extract_differential_features")
        self.assertEqual(annot["keyword"], "spectral_annotation")
        self.assertEqual(kegg["keyword"], "KEGG compound enrichment")
        self.assertEqual(kegg["mcp_tools"], ["kegg_compound_enrichment"])
        self.assertEqual(pathway["mcp_tools"], ["pathway_analysis_kegg"])

    def test_unknown_stage_still_maps(self) -> None:
        plan = {
            "goal": "demo",
            "steps": [
                {
                    "step_number": 5,
                    "description": "extract",
                    "stage": "differential_feature_extraction",
                    "tools": ["extract_differential_features"],
                },
                {
                    "step_number": 6,
                    "description": "annotate",
                    "stage": "Step 6",
                    "tools": ["spectral_annotation"],
                },
        {
            "step_number": 7,
            "description": "enrich",
            "stage": "pathway_analysis",
            "tools": ["kegg_compound_enrichment"],
        },
            ],
        }
        out, warnings = normalize_plan_for_b(plan, MINI_CATALOG)
        self.assertFalse(warnings)
        self.assertEqual(out["steps"][0]["tools"], ["extract_differential_features"])
        self.assertEqual(out["steps"][1]["tools"], ["spectral_annotation"])
        self.assertEqual(out["steps"][2]["tools"], ["KEGG compound enrichment"])
        self.assertEqual(out["steps"][2]["stage"], "enrichment_analysis")

    def test_real_b_catalog_maps_skipped_tools(self) -> None:
        from web_frontend.backend.agent_b.plan_normalize import load_tool_catalog
        from web_frontend.backend.agent_backends import massomics_b_available, massomics_b_root

        if not massomics_b_available():
            self.skipTest("MassOmics-Agent-B catalog 不可用")
        catalog = load_tool_catalog(massomics_b_root() / "src" / "tool_catalog.json")
        for name, keyword in (
            ("extract_differential_features", "extract_differential_features"),
            ("spectral_annotation", "spectral_annotation"),
            ("kegg_compound_enrichment", "KEGG compound enrichment"),
        ):
            entry = resolve_catalog_entry(name, catalog)
            self.assertIsNotNone(entry, name)
            assert entry is not None
            self.assertEqual(entry["keyword"], keyword)
            self.assertEqual(entry["mcp_tools"][0], name)

    def test_find_latest_plan_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "agent_b_adapted_plan.json").write_text(
                json.dumps({"goal": "no", "steps": []}), encoding="utf-8"
            )
            older = folder / "plan_20260101_000000.json"
            newer = folder / "plan_20260102_000000.json"
            older.write_text(json.dumps({"goal": "a", "steps": [{"step_number": 1}]}), encoding="utf-8")
            newer.write_text(json.dumps({"goal": "b", "steps": [{"step_number": 1}]}), encoding="utf-8")
            found = find_massomics_plan_json(folder)
            self.assertEqual(found, newer)


if __name__ == "__main__":
    unittest.main()
