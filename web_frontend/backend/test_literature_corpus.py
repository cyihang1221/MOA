"""文献语料（repro_recipes / figure_index）与规划/作图检索单测。"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from web_frontend.backend.literature_corpus import (
    clear_corpus_cache,
    detect_journal_from_source,
    parse_recipe_text,
    retrieve_corpus,
    search_figure_hits,
    search_plan_recipes,
    short_title_from_caption,
)
from web_frontend.backend.literature_paths import resolve_literature_dirs
from web_frontend.backend.literature_rag import retrieve_literature

_ROOT = Path(__file__).resolve().parents[2]
_REAL_DB = _ROOT / "softwares_database"

_RECIPE = """========== reproducibility_recipe entry ==========
paper_title: Evaluating urinary metabolomics normalization.
source_paper: Brix F et al. (2024), Analytical chemistry, DOI: 10.1021/acs.analchem.3c01380, PMID: 1
overall_reproducibility_score: 87/100

workflow_steps: 3
  Step 1: Feature detection
    tool: OpenMS
    parameters: mass_tolerance_ppm=2
  Step 2: Statistical analysis
    tool: mixOmics
    algorithm: PCA
  Step 3: Differential metabolites
    tool: R
    algorithm: t-test

figure_recipes: 3
  Figure 1: [workflow_diagram]
    caption: Schematic of merging strategies.
  Figure 2: [pca_scores]
    caption: PCA score plots of QC samples after PQN.
    visualization_tool: ggplot2
  Figure 3: [volcano_plot]
    caption: Volcano plots highlighting differentially abundant metabolites.
    visualization_tool: EnhancedVolcano
    statistical_test: t-test p<0.05, FDR<0.1
"""

_FIG_INDEX = """========== figure_index entry ==========
figure_id: fig_2
paper_title: GNPS molecular networking tutorial
source_paper: Wang M et al. (2016), Nature biotechnology, DOI: 10.1038/nbt.3597
figure_caption: Fig. 2: Molecular network of a bacterial extract visualized in Cytoscape.

========== figure_index entry ==========
figure_id: fig_4
paper_title: Pseudotargeted metabolomics
source_paper: Zheng F et al. (2020), Nature protocols, DOI: 10.1038/s41596-020-0341-5
figure_caption: Fig. 4: PCA score plot of plasma samples colored by group.
"""


class LiteratureCorpusTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_corpus_cache()
        self._old_vector = os.environ.get("WEB_LITERATURE_VECTOR")
        os.environ["WEB_LITERATURE_VECTOR"] = "0"

    def tearDown(self) -> None:
        clear_corpus_cache()
        if self._old_vector is None:
            os.environ.pop("WEB_LITERATURE_VECTOR", None)
        else:
            os.environ["WEB_LITERATURE_VECTOR"] = self._old_vector

    def _write_db(self, root: Path) -> Path:
        src = root / "softwares_database"
        recipes = src / "repro_recipes"
        recipes.mkdir(parents=True)
        (recipes / "recipe_10.1021_acs.analchem.3c01380.txt").write_text(
            _RECIPE, encoding="utf-8"
        )
        (src / "figure_index.txt").write_text(_FIG_INDEX, encoding="utf-8")
        (src / "pipeline_overview.md").write_text(
            "# pipeline\nmetabolomics PCA PLS-DA volcano\n", encoding="utf-8"
        )
        (src / "all.txt").write_text("this dump should not be preferred\n" * 50, encoding="utf-8")
        (src / "mixOmics.txt").write_text(
            "mixOmics PCA PLS-DA statistical analysis score plot\n", encoding="utf-8"
        )
        persist = root / "softwares_database_RAG"
        persist.mkdir()
        return src

    def test_parse_recipe_extracts_figure_tags_and_doi(self) -> None:
        parsed = parse_recipe_text(_RECIPE, rel="repro_recipes/demo.txt")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["doi"], "10.1021/acs.analchem.3c01380")
        self.assertEqual(parsed["workflow_steps"], 3)
        tags = {f["tag"] for f in parsed["figures"]}
        self.assertEqual(tags, {"workflow_diagram", "pca_scores", "volcano_plot"})
        pca = next(f for f in parsed["figures"] if f["tag"] == "pca_scores")
        self.assertIn("QC samples", pca["caption"])
        self.assertEqual(pca["viz_tool"], "ggplot2")

    def test_plot_search_prefers_pca_scores_over_workflow_diagram(self) -> None:
        with TemporaryDirectory() as tmp:
            src = self._write_db(Path(tmp))
            hits = search_figure_hits(source_dir=src, plot_type="pca", query="PCA 得分图")
        tags = [h.get("tag") or "" for h in hits]
        self.assertIn("pca_scores", tags)
        self.assertNotIn("workflow_diagram", tags)
        captions = " ".join(h.get("caption") or "" for h in hits)
        self.assertIn("PCA score", captions)

    def test_volcano_search_keeps_stat_test_but_search_is_caption_based(self) -> None:
        with TemporaryDirectory() as tmp:
            src = self._write_db(Path(tmp))
            hits = search_figure_hits(source_dir=src, plot_type="volcano", query="火山图")
        self.assertTrue(hits)
        self.assertEqual(hits[0].get("tag"), "volcano_plot")
        self.assertIn("FDR", hits[0].get("stat_test") or "")

    def test_plan_search_skips_zero_workflow_reviews(self) -> None:
        with TemporaryDirectory() as tmp:
            src = self._write_db(Path(tmp))
            (src / "repro_recipes" / "recipe_10.0_review.txt").write_text(
                "paper_title: A review\nsource_paper: DOI: 10.0/review\n"
                "overall_reproducibility_score: 0/100\nworkflow_steps: 0\n"
                "figure_recipes: 0\n",
                encoding="utf-8",
            )
            hits = search_plan_recipes(source_dir=src, query="OpenMS mixOmics PCA metabolomics")
        self.assertTrue(hits)
        self.assertGreater(hits[0]["workflow_steps"], 0)

    def test_retrieve_plot_markdown_mentions_corpus(self) -> None:
        with TemporaryDirectory() as tmp:
            src = self._write_db(Path(tmp))
            payload = retrieve_corpus(
                "PCA score plot", src, intent="plot", plot_type="pca"
            )
        self.assertIn("Published figures", payload["text"])
        self.assertIn("ggplot2", payload["text"])
        self.assertTrue(payload["sources"])

    def test_lexical_skips_all_txt_dump(self) -> None:
        with TemporaryDirectory() as tmp:
            src = self._write_db(Path(tmp))
            hit = retrieve_literature(
                "mixOmics PCA statistical analysis",
                persist_dir=str(Path(tmp) / "softwares_database_RAG"),
                source_dir=str(src),
                intent="plan",
            )
        self.assertNotEqual(hit["mode"], "empty")
        self.assertFalse(any(str(s).endswith("all.txt") for s in hit.get("sources") or []))

    def test_resolve_dirs_prefers_repro_recipes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "MassOmics-Agent"
            nested.mkdir()
            src = self._write_db(root)
            persist, source = resolve_literature_dirs(nested)
        self.assertEqual(Path(source), src)

    def test_catalog_figure_type_used_for_pca(self) -> None:
        catalog = (
            "========== figure_catalog entry ==========\n"
            "figure_id: fig_2\n"
            "paper_title: Demo PCA paper\n"
            "source_paper: Xiao Y et al. (2022), Cell research, DOI: 10.1038/s41422-022-00614-0\n"
            "figure_caption: Fig. 2: PCA score plot of tumor versus normal.\n"
            "figure_type: PCA/PLS-DA 散点图\n"
            "plot_tool_hint: ggplot2/R\n"
            "visual_description: 按 Group 着色的得分图，图例在右侧。\n"
            "is_research_plot: True\n"
        )
        with TemporaryDirectory() as tmp:
            src = self._write_db(Path(tmp))
            (src / "figure_catalog.txt").write_text(catalog, encoding="utf-8")
            hits = search_figure_hits(source_dir=src, plot_type="pca", query="PCA")
        self.assertTrue(any(h.get("kind") == "figure_catalog" for h in hits))
        self.assertTrue(any("ggplot" in str(h.get("viz_tool") or "").lower() for h in hits))

    def test_short_title_and_journal(self) -> None:
        self.assertEqual(
            short_title_from_caption("pca", "Fig. 4: PCA score plot of plasma samples"),
            "PCA score plot of plasma samples",
        )
        self.assertEqual(short_title_from_caption("pca", "A" * 90), "")
        self.assertEqual(
            detect_journal_from_source("Wang M, Nature biotechnology"),
            "npg",
        )

    @unittest.skipUnless(
        (_REAL_DB / "repro_recipes").is_dir(),
        "softwares_database not present",
    )
    def test_real_library_pca_and_volcano_hits(self) -> None:
        pca = search_figure_hits(
            source_dir=_REAL_DB, plot_type="pca", query="PCA score plot", max_hits=5
        )
        volcano = search_figure_hits(
            source_dir=_REAL_DB, plot_type="volcano", query="volcano plot", max_hits=5
        )
        self.assertTrue(pca, "expected PCA figure hits in repro_recipes/figure_index")
        self.assertTrue(volcano, "expected volcano figure hits")
        pca_blob = " ".join(
            f"{h.get('tag')} {h.get('figure_type')} {h.get('caption')}" for h in pca
        ).lower()
        self.assertTrue("pca" in pca_blob or "score plot" in pca_blob)


if __name__ == "__main__":
    unittest.main()
