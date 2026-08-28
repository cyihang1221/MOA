"""Agent C 文献改图：检索分池 + 证据应用单测。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from web_frontend.backend.literature_evidence import (
    apply_data_contract_to_patch,
    build_style_patch_from_evidence,
    collect_evidence_cards,
)
from web_frontend.backend.literature_figure_style import clear_style_cache
from web_frontend.backend.literature_plot_knowledge import (
    load_sticky_literature_skills,
    rank_skills_for_plot,
    skill_plot_relevance,
)


class LiteraturePlotRetrievalTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_style_cache()

    def _write_skill(self, root: Path, rel_parts: tuple[str, ...], body: str) -> None:
        skill_dir = root.joinpath(*rel_parts)
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")

    def test_software_params_excluded_from_volcano_rank(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "MassOmics-Agent" / "MassOmics-Agent" / "skills"
            self._write_skill(
                base,
                ("software-params", "xcms", "centwave-2008",),
                "---\nname: centwave\ndescription: xcms centWave ppm peakwidth\n---\n"
                "## 关键参数\nppm=30\n",
            )
            self._write_skill(
                base,
                ("lcms-untargeted", "volcano-demo",),
                "---\nname: volcano-demo\ndescription: 火山图 volcano plot\n---\n"
                "DOI: 10.1038/demo\n\n## 出图清单\n| 图 | 说明 |\n| Volcano plot | NPG 配色 |\n",
            )
            ranked = rank_skills_for_plot(
                plot_type="volcano",
                goal_text="差异代谢物 volcano",
                project_root=root,
                max_skills=3,
            )
            ids = [s["skill_id"] for s in ranked]
            self.assertIn("volcano-demo", ids)
            self.assertNotIn("centwave", ids)

    def test_sticky_skill_boosted(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "MassOmics-Agent" / "MassOmics-Agent" / "skills" / "lcms-untargeted"
            for name, desc in (
                ("gnps-fbmn-2020", "GNPS FBMN molecular network cosine"),
                ("keemun-tea", "祁门红茶 PCA 得分图"),
            ):
                self._write_skill(
                    base,
                    (name,),
                    f"---\nname: {name}\ndescription: {desc}\n---\n"
                    f"## 出图清单\n| network | cosine distribution |\n",
                )
            ranked = rank_skills_for_plot(
                plot_type="cosine_hist",
                goal_text="分子网络",
                project_root=root,
                sticky_skill_ids=["gnps-fbmn-2020"],
                max_skills=2,
            )
            self.assertTrue(ranked)
            self.assertEqual(ranked[0]["skill_id"], "gnps-fbmn-2020")

    def test_load_sticky_from_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "agent_c_output"
            out.mkdir()
            manifest = {
                "literature_style": {"matched_skills": ["metaboanalyst5-protocol-2022"]},
                "report_figures": [
                    {"literature_style": {"matched": ["gnps-fbmn-2020"]}},
                ],
            }
            (out / "agent_c_manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            sticky = load_sticky_literature_skills(root)
            self.assertEqual(
                sticky,
                ["metaboanalyst5-protocol-2022", "gnps-fbmn-2020"],
            )

    def test_data_contract_blocks_missing_color_by(self) -> None:
        patch = {"color_by": "Batch"}
        fixed, warns = apply_data_contract_to_patch(
            "pca", patch, metadata_columns=["Group", "Sample"]
        )
        self.assertNotIn("color_by", fixed)
        self.assertTrue(any("Batch" in w for w in warns))

    def test_build_style_patch_applies_group_color_when_metadata_ok(self) -> None:
        cards = [
            {
                "evidence_id": "t#L1",
                "skill_id": "demo",
                "quote": "按 Group 着色，图例在右侧",
                "field_hints": ["color_by", "legend.position"],
                "claim_type": "literature_example",
            }
        ]
        patch, applied, _ = build_style_patch_from_evidence(
            "pca", cards, metadata_columns=["Group", "Sample"]
        )
        self.assertEqual(patch.get("color_by"), "Group")
        self.assertEqual(patch.get("legend", {}).get("position"), "right")
        self.assertTrue(any("color_by" in a for a in applied))

    def test_software_params_zero_plot_relevance(self) -> None:
        skill = {"skill_pool": "software_params", "visual_block": "ppm=30", "skill_id": "xcms"}
        self.assertEqual(skill_plot_relevance(skill, "pca"), 0)

    def test_collect_evidence_respects_sticky(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "MassOmics-Agent" / "MassOmics-Agent" / "skills" / "lcms-untargeted"
            self._write_skill(
                base,
                ("gnps-fbmn-2020",),
                "---\nname: gnps-fbmn-2020\ndescription: GNPS FBMN network\n---\n"
                "## 出图清单\n| cosine_hist | 余弦相似度分布 |\n",
            )
            cards = collect_evidence_cards(
                plot_type="cosine_hist",
                goal_text="network",
                project_root=root,
                sticky_skill_ids=["gnps-fbmn-2020"],
            )
            self.assertTrue(cards)
            self.assertEqual(cards[0]["skill_id"], "gnps-fbmn-2020")

    def test_match_plot_literature_falls_back_when_visual_block_empty(self) -> None:
        from unittest.mock import patch

        from web_frontend.backend.literature_plot_knowledge import match_plot_literature

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "MassOmics-Agent" / "MassOmics-Agent" / "skills" / "lcms-untargeted"
            self._write_skill(
                base,
                ("pca-paper",),
                "---\nname: pca-paper\ndescription: PCA score plot metabolomics\n---\n"
                "Figure 2 shows PCA score plot colored by treatment group.\n",
            )
            with patch(
                "web_frontend.backend.literature_plot_knowledge.supplement_plot_literature_rag",
                return_value={"text": "", "mode": "empty", "sources": [], "error": None},
            ):
                payload = match_plot_literature(
                    plot_type="pca",
                    goal_text="PCA 得分图",
                    project_root=root,
                )
            self.assertIn("pca-paper", payload.get("matched") or [])
            self.assertIn("Figure 2", payload.get("text") or "")

    def test_match_plot_literature_appends_rag_snippet(self) -> None:
        from unittest.mock import patch

        from web_frontend.backend.literature_plot_knowledge import match_plot_literature

        with patch(
            "web_frontend.backend.literature_plot_knowledge.rank_skills_for_plot",
            return_value=[],
        ), patch(
            "web_frontend.backend.literature_plot_knowledge.supplement_plot_literature_rag",
            return_value={
                "text": "Use NPG palette for volcano plots.",
                "mode": "lexical",
                "sources": ["softwares_database"],
                "error": None,
            },
        ):
            payload = match_plot_literature(plot_type="volcano", goal_text="差异代谢")
        self.assertIn("Supplementary literature", payload.get("text") or "")
        self.assertIn("NPG palette", payload.get("text") or "")
        self.assertEqual(payload.get("rag_mode"), "lexical")


if __name__ == "__main__":
    unittest.main()
