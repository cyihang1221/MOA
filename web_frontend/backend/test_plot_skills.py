"""Agent C 改图规范 Skill：覆盖、文献核对、检索名额、结构化规格与 R 参数。"""
from __future__ import annotations

import json
import os
import re
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("MPLBACKEND", "Agg")

import yaml

from web_frontend.backend.literature_evidence import build_style_patch_from_evidence
from web_frontend.backend.literature_plot_knowledge import (
    _load_plot_skills,
    _plot_skills_root,
    rank_skills_for_plot,
)
from web_frontend.backend.plot_edit_registry import PLOT_SPECS

_REPO = Path(__file__).resolve().parents[2]
_PLOT_SKILLS = _plot_skills_root(_REPO)


def _frontmatter(text: str) -> dict:
    return yaml.safe_load(re.search(r"^---\n(.*?)\n---", text, re.S).group(1))


def _figure_entries(text: str) -> list[dict]:
    entries: list[dict] = []
    for m in re.finditer(r"```ya?ml\s*\n(.*?)```", text, re.S):
        entries.extend(yaml.safe_load(m.group(1)).get("figures") or [])
    return entries


class PlotSkillCatalogTest(unittest.TestCase):
    def test_each_registered_plot_type_has_exactly_one_skill(self) -> None:
        owner: dict[str, str] = {}
        for skill in _load_plot_skills(_REPO):
            for plot_type in skill["plot_types"]:
                self.assertNotIn(plot_type, owner, f"{plot_type} 同时属于 {owner.get(plot_type)} 和 {skill['skill_id']}")
                owner[plot_type] = skill["skill_id"]
        self.assertEqual(set(owner), {spec.plot_type for spec in PLOT_SPECS})

    def test_every_declared_plot_type_has_a_yaml_spec(self) -> None:
        for md in _PLOT_SKILLS.rglob("SKILL.md"):
            text = md.read_text(encoding="utf-8")
            declared = set(_frontmatter(text)["plot_types"])
            specced = {e["plot_type"] for e in _figure_entries(text)}
            self.assertEqual(declared, specced, md)

    def test_cited_dois_are_the_verified_reference_list(self) -> None:
        refs = json.loads((_PLOT_SKILLS / "references.json").read_text(encoding="utf-8"))["references"]
        verified = {r["doi"] for r in refs}
        cited: set[str] = set()
        for md in _PLOT_SKILLS.rglob("SKILL.md"):
            text = md.read_text(encoding="utf-8")
            listed = set(_frontmatter(text)["references"])
            self.assertEqual(listed, set(re.findall(r"DOI (10\.\S+)", text)), md)
            self.assertTrue(listed <= verified, f"{md}: {listed - verified}")
            cited |= listed
        self.assertEqual(cited, verified)
        for ref in refs:
            self.assertTrue(ref["title"] and ref["journal"] and ref["year"], ref["doi"])
            self.assertTrue(ref["supports"], ref["doi"])

    def test_pairs_with_point_to_existing_analysis_skills(self) -> None:
        skills_root = _REPO / "MassOmics-Agent-B" / "skills"
        registry = _REPO / "phase2_output" / "skill_registry.json"
        if not skills_root.is_dir() or not registry.is_file():
            self.skipTest("测试目录缺少 MassOmics-Agent-B/skills 或 phase2_output")
        known = {p.parent.name for p in skills_root.rglob("SKILL.md")}
        known |= {s["skill_name"] for s in json.loads(registry.read_text(encoding="utf-8"))["skills"]}
        branches = {p.name for p in skills_root.iterdir() if p.is_dir()}
        for skill in _load_plot_skills(_REPO):
            for pair in skill["pairs_with"]:
                if pair.startswith("branch:"):
                    self.assertIn(pair[len("branch:"):], branches, skill["skill_id"])
                else:
                    self.assertIn(pair, known, skill["skill_id"])

    def test_plot_skills_stay_out_of_agent_a_skill_tree(self) -> None:
        from web_frontend.backend.skill_match import _massomics_skills_root

        a_root = _massomics_skills_root(_REPO).resolve()
        self.assertFalse(_PLOT_SKILLS.resolve().is_relative_to(a_root))


class PlotSkillRankingTest(unittest.TestCase):
    def _project_with_paper_skill(self, tmp: str) -> Path:
        root = Path(tmp)
        shutil.copytree(_PLOT_SKILLS, _plot_skills_root(root))
        paper = root / "MassOmics-Agent" / "MassOmics-Agent" / "skills" / "lcms-untargeted" / "tea-paper"
        paper.mkdir(parents=True)
        (paper / "SKILL.md").write_text(
            "---\nname: tea-paper\ndescription: 茶叶 LC-MS PCA 得分图\n---\n"
            "## 出图清单\n| PCA | 分组着色 score plot |\n",
            encoding="utf-8",
        )
        return root

    def test_plot_skill_takes_last_slot(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._project_with_paper_skill(tmp)
            ids = [s["skill_id"] for s in rank_skills_for_plot(plot_type="pca", goal_text="PCA", project_root=root, max_skills=2)]
            self.assertEqual(ids, ["tea-paper", "score-plot-pca-plsda"])

    def test_plot_skill_only_for_declared_types(self) -> None:
        with TemporaryDirectory() as tmp:
            root = self._project_with_paper_skill(tmp)
            ids = [s["skill_id"] for s in rank_skills_for_plot(plot_type="volcano", project_root=root, max_skills=3)]
            self.assertIn("volcano-plot", ids)
            self.assertNotIn("score-plot-pca-plsda", ids)
            untyped = rank_skills_for_plot(plot_type="", goal_text="PCA 得分图", project_root=root, max_skills=3)
            self.assertEqual([s["skill_id"] for s in untyped], ["tea-paper"])


class StructuredSpecTest(unittest.TestCase):
    def test_structured_spec_whitelist_and_priority(self) -> None:
        cards = [
            {
                "evidence_id": "score#yaml",
                "skill_id": "score-plot-pca-plsda",
                "quote": "basis=sample plot; colors threshold_color",
                "claim_type": "structured_spec",
                "structured": {
                    "plot_type": "pca",
                    "legend_position": "right",
                    "font_size": {"title": 14, "axis": "big"},
                    "colors": {"upregulated": "#E64B35", "bad": "red"},
                    "ellipse": False,
                    "thresholds": {"p": 0.01},
                },
            },
            {
                "evidence_id": "paper#L1",
                "skill_id": "paper",
                "quote": "PCA score plot，图例在下方",
                "field_hints": ["legend.position"],
                "claim_type": "literature_example",
            },
        ]
        patch_, applied, warnings = build_style_patch_from_evidence(
            "pca", cards, metadata_columns=["Sample", "Group"]
        )
        self.assertEqual(patch_["legend"]["position"], "right")
        self.assertEqual(patch_["font_size"], {"title": 14})
        self.assertEqual(patch_["colors"], {"upregulated": "#E64B35"})
        self.assertIs(patch_["ellipse"], False)
        self.assertNotIn("thresholds", patch_)
        self.assertNotEqual(patch_.get("color_by"), "Sample")
        self.assertFalse(any("阈值" in w for w in warnings))
        self.assertIn("ellipse=false", applied)


class RSpecFieldsTest(unittest.TestCase):
    def test_style_fields_reach_r_spec(self) -> None:
        from web_frontend.backend import r_plot_backend

        captured: list[dict] = []
        with TemporaryDirectory() as tmp, patch.object(
            r_plot_backend, "render_r_plot", side_effect=lambda spec: captured.append(spec) or Path(spec["output_png"])
        ):
            root = Path(tmp)
            (root / "pca_scores.csv").write_text("sample,PC1,PC2\nA,1,2\n", encoding="utf-8")
            (root / "kegg_compound_enrich.csv").write_text("ID,Description,Count,p.adjust\nm,P,2,0.01\n", encoding="utf-8")
            cfg = {
                "title_align": "center",
                "legend": {"position": "bottom", "show": True},
                "font_size": {"title": 18, "axis": 12, "legend": 10, "label": 9},
                "ellipse": {"show": False},
                "colors": {"enrich_high": "#D55E00", "enrich_low": "#56B4E9"},
            }
            r_plot_backend.render_score_r(output_path=root / "p.png", data_dir=root, metadata_csv=None, plot_config=cfg, plot_type="pca")
            r_plot_backend.render_kegg_r(root, cfg, root / "k.png", "kegg_bubble")
        score, kegg = captured
        self.assertEqual(score["legend_position"], "bottom")
        self.assertEqual(score["title_align"], "center")
        self.assertEqual(score["font_size"]["title"], 18.0)
        self.assertIs(score["ellipse"], False)
        self.assertEqual(kegg["colors"]["enrich_high"], "#D55E00")
        self.assertEqual(kegg["legend_position"], "bottom")


@unittest.skipUnless(
    __import__("web_frontend.backend.r_plot_backend", fromlist=["find_rscript"]).find_rscript(),
    "需要 Rscript、ggplot2 与 pheatmap",
)
class RRenderStyleTest(unittest.TestCase):
    def test_ellipse_off_and_heatmap_centered_on_zero(self) -> None:
        from web_frontend.backend.r_plot_backend import render_heatmap_r, render_score_r

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pca_scores.csv").write_text(
                "sample,PC1,PC2\nA,-1.2,0.2\nB,-1.0,0.1\nC,-0.8,-0.2\nD,1.0,0.3\nE,1.1,-0.1\nF,0.9,0.2\n",
                encoding="utf-8",
            )
            (root / "metadata.csv").write_text("Sample,Group\nA,BK\nB,BK\nC,BK\nD,DY\nE,DY\nF,DY\n", encoding="utf-8")
            out = root / "pca.png"
            render_score_r(
                output_path=out,
                data_dir=root,
                metadata_csv=root / "metadata.csv",
                plot_config={"ellipse": False, "legend": {"position": "bottom"}, "show_sample_labels": False},
                plot_type="pca",
            )
            record = json.loads(out.with_name("pca.edit_record.json").read_text(encoding="utf-8"))
            self.assertIs(record["ellipse"], False)
            self.assertEqual(record["legend_position"], "bottom")

            (root / "heatmap_top_vip_matrix.csv").write_text(
                ",A,B,C,D\nf1,-1.5,-0.5,0.5,2.5\nf2,1.0,-1.0,0.2,-0.2\n", encoding="utf-8"
            )
            heat = root / "heat.png"
            render_heatmap_r(root, {"cmap": "RdBu_r"}, heat, root / "metadata.csv")
            record = json.loads(heat.with_name("heat.edit_record.json").read_text(encoding="utf-8"))
            self.assertIs(record["color_center_zero"], True)


if __name__ == "__main__":
    unittest.main()
