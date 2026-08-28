"""Agent C CLI 路径解析单测。"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from web_frontend.backend.agent_c.cli import (
    resolve_agent_c_paths,
    resolve_session_slug,
)


class AgentCCliTest(unittest.TestCase):
    def test_resolve_session_by_short_id(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            slug = "my-analysis_0de4a588"
            (root / "outputspace" / slug).mkdir(parents=True)
            (root / "inputspace" / slug).mkdir(parents=True)
            self.assertEqual(resolve_session_slug(root, "0de4a588"), slug)

    def test_resolve_agent_c_paths_with_explicit_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            slug = "demo-session_abcd1234"
            out_root = root / "outputspace" / slug
            upload_root = root / "inputspace" / slug
            out_root.mkdir(parents=True)
            upload_root.mkdir(parents=True)
            plan = out_root / "plan_20260826_102858.md"
            plan.write_text("# plan\n", encoding="utf-8")
            (upload_root / "metadata.csv").write_text("Sample,Group\nS1,A\n", encoding="utf-8")

            paths = resolve_agent_c_paths(
                project_root=root,
                session="abcd1234",
                plan="plan_20260826_102858.md",
            )
            self.assertEqual(paths["results_dir"], out_root.resolve())
            self.assertEqual(paths["plan"], plan.resolve())
            self.assertEqual(paths["metadata_csv"], (upload_root / "metadata.csv").resolve())
            self.assertEqual(paths["output_dir"], (out_root / "agent_c_output").resolve())


if __name__ == "__main__":
    unittest.main()
