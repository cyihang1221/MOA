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
    complete_abc_root,
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
            "keyword": "XCMS-Centwave",
            "stage": "feature_detection",
            "aliases": ["XCMS-CentWave"],
            "support_status": "supported",
            "mcp_tools": ["data_preprocessing_xcms"],
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

    def test_complete_unifies_a_and_b(self) -> None:
        unified = complete_abc_root()
        self.assertIsNotNone(unified)
        self.assertEqual(unified.name, "MassOmics-Agent-B")
        self.assertEqual(massomics_root().resolve(), massomics_b_root().resolve())
        st = backend_status()
        self.assertEqual(st["layout"], "complete_unified")
        self.assertTrue(st["same_tree"])
        self.assertEqual(Path(st["complete_abc_root"]).name, "MassOmics-Agent-B")

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
        self.assertIn("complete_abc_root", st)
        self.assertIn("layout", st)
        self.assertIn("tool_catalog_usable", st)
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
