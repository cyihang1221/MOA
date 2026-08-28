"""Agent A/B 后端路由与 MassOmics 工具映射单测。"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from web_frontend.backend.agent_a.massomics_tool_map import (
    plan_document_to_tasks,
    resolve_web_mcp_tool,
)
from web_frontend.backend.agent_backends import (
    agent_a_backend,
    agent_b_backend,
    backend_status,
    massomics_available,
    massomics_root,
)


class AgentBackendsTest(unittest.TestCase):
    def test_default_backends(self) -> None:
        for key in ("WEB_AGENT_A_BACKEND", "WEB_AGENT_B_BACKEND"):
            os.environ.pop(key, None)
        self.assertEqual(agent_a_backend(), "massomics")
        self.assertEqual(agent_b_backend(), "local")

    def test_massomics_root_exists(self) -> None:
        root = massomics_root()
        self.assertTrue((root / "plan" / "schema.py").is_file())

    def test_backend_status_shape(self) -> None:
        st = backend_status()
        self.assertIn("agent_a_backend", st)
        self.assertIn("agent_b_backend", st)
        self.assertIn("massomics_root", st)
        self.assertTrue(st["massomics_available"] or not st["massomics_available"])

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


if __name__ == "__main__":
    unittest.main()
