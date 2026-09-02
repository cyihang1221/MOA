"""software-params：注入匹配、YAML 折叠解析、证据列与双份副本。"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from web_frontend.backend.literature_plot_knowledge import _parse_skill_frontmatter
from web_frontend.backend.skill_match import _in_goal, _massomics_skills_root, match_skills


ROOT = Path(__file__).resolve().parents[2]
SKILLS = _massomics_skills_root() / "software-params"
PDF_SKILLS = ROOT / "softwares" / "pdf"
EVIDENCE = {"literature_example", "protocol_start", "not_reported"}

KEYWORD_CASES: list[tuple[str, str, str | None]] = [
    ("ProteoWizard", "proteowizard", None),
    ("ThermoRawFileParser", "thermorawfileparser", None),
    ("msconvert", "msconvert", None),
    ("OpenMS FileConverter", "openms", "sturm-2008-openms"),
    ("OpenMS-PeakPicking", "openms", "sturm-2008-openms"),
    ("OpenMS-FeatureFinderMetabo", "openms", "kenar-2014-featurefindermetabo"),
    ("OpenMS-IsotopeTools", "openms", "rost-2016-openms2"),
    ("OpenMS-PeakGroup", "openms", "rost-2016-openms2"),
    ("XCMS-Centwave", "xcms", "tautenhahn-2008-centwave"),
    ("XCMS-Obiwarp", "xcms", "naser-2019-credentialing"),
    ("XCMS-LOESS", "xcms", "naser-2019-credentialing"),
    ("MZMine-GirdMass", "mzmine", "pluskal-2010-mzmine2"),
    ("MZMine-ADAP", "mzmine", "heuckeroth-2024-reproducible-processing"),
    ("MZMine-JointAligner", "mzmine", "heuckeroth-2024-reproducible-processing"),
    ("KPIC", "kpic", "wang-2011-ckmeans"),
    ("KPIC2", "kpic", "wang-2011-ckmeans"),
    ("PITracer", "pitracer", None),
    ("TracMass", "tracmass", None),
    ("PeakOnly", "peakonly", None),
    ("CAMERA", "camera", None),
    ("RAMClust", "ramclust", None),
    ("mzAnnotation", "mzannotation", None),
    ("IsoXpress", "isoxpress", None),
    ("TarMet", "tarmet", None),
    ("AssayR", "assayr", None),
    ("FFT-based", "fft", None),
    ("DTW-based", "dtw", None),
    ("kNN", "knn", None),
    ("MissForest", "missforest", None),
    ("Bayesian PCA", "bpca", None),
    ("WaveICA", "waveica", None),
    ("MetNormalizer", "metnormalizer", None),
    ("MetaboGroupS", "metabogroups", None),
    ("metaX", "metax", None),
    ("mixOmics", "mixomics", None),
    ("scikit-learn", "scikit-learn", None),
    ("SIMCA", "simca", None),
    ("DeepLearning-based", "deeplearning", None),
    ("Jaccard", "jaccard", None),
    ("Cosine", "cosine", None),
    ("Spectral entropy", "spectral-entropy", None),
    ("Spec2Vec", "spec2vec", None),
    ("MS2DeepScore", "ms2deepscore", None),
    ("BLINK", "blink", None),
    ("MS-BERT", "msbert", None),
    ("CFM-ID", "cfm-id", None),
    ("SIRIUS", "sirius", None),
    ("DeepMASS", "deepmass", None),
    ("CSU-MS2", "csu-ms2", None),
    ("MetDNA", "metdna", None),
    ("E-SGMN", "e-sgmn", None),
    ("NEIMS", "neims", None),
    ("GNPS", "gnps", None),
    ("FBMN", "fbmn", None),
    ("MS2LDA", "ms2lda", None),
    ("MolNetEnhancer", "molnetenhancer", None),
    ("MetaboAnalyst", "metaboanalyst", None),
    ("mummichog", "mummichog", None),
    ("GSEA", "gsea", None),
    ("ChemRICH", "chemrich", None),
    ("HMDB", "hmdb", None),
    ("KEGG", "kegg", None),
    ("Reactome", "reactome", None),
    ("BioCyc", "biocyc", None),
]


def _skill_files() -> list[Path]:
    return sorted(SKILLS.rglob("SKILL.md"))


class SoftwareParamsSkillTest(unittest.TestCase):
    def test_kpic_does_not_steal_openms_peakpicking(self) -> None:
        self.assertFalse(_in_goal("kpic", "请使用 openms-peakpicking"))
        matched = match_skills("请使用 OpenMS-PeakPicking", max_skills=8)["matched"]
        self.assertNotIn("wang-2011-ckmeans", matched)
        self.assertIn("sturm-2008-openms", matched)

    def test_kpic_and_kpic2_still_hit(self) -> None:
        for goal in ("请使用 KPIC 做峰检测", "请使用 KPIC2"):
            matched = match_skills(goal, max_skills=8)["matched"]
            self.assertIn("wang-2011-ckmeans", matched, goal)

    def test_catalog_keywords_inject_param_card(self) -> None:
        self.assertGreaterEqual(len(_skill_files()), 62)
        for keyword, software_id, slug in KEYWORD_CASES:
            goal = f"请使用 {keyword} 完成分析"
            matched = match_skills(goal, max_skills=8)["matched"]
            self.assertTrue(matched, f"{keyword}: empty match")
            if slug:
                self.assertIn(slug, matched, f"{keyword} -> {slug}, got {matched}")
            else:
                hits = list(SKILLS.joinpath(software_id).glob("*/SKILL.md"))
                names = {p.parent.name for p in hits}
                self.assertTrue(
                    names.intersection(matched),
                    f"{keyword} ({software_id}) not in {matched}; expected one of {names}",
                )

    def test_folded_yaml_has_trigger_phrase(self) -> None:
        missing = []
        for path in _skill_files():
            text = path.read_text(encoding="utf-8")
            _name, desc, keywords = _parse_skill_frontmatter(text)
            if "当提到" not in desc:
                missing.append(path.parent.name)
            self.assertTrue(
                any(len(k) >= 2 for k in keywords),
                f"{path.parent.name} has no trigger keywords",
            )
        self.assertEqual(missing, [])

    def test_evidence_column_is_token_only(self) -> None:
        bad: list[str] = []
        for path in _skill_files():
            in_ev = False
            for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if ln.startswith("|") and "证据" in ln and "----" not in ln:
                    cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                    in_ev = bool(cells) and cells[-1] == "证据"
                    continue
                if in_ev:
                    if not ln.startswith("|"):
                        in_ev = False
                        continue
                    if re.match(r"^\|\s*-+", ln):
                        continue
                    cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                    if len(cells) < 6:
                        continue
                    if cells[-1] not in EVIDENCE:
                        bad.append(f"{path.parent.name}:{i}:{cells[-1]}")
        self.assertEqual(bad, [])

    def test_dual_skill_copies_exist(self) -> None:
        if not PDF_SKILLS.is_dir():
            self.skipTest("softwares/pdf 不在本仓库")
        missing = []
        for path in _skill_files():
            rel = path.relative_to(SKILLS).as_posix()
            if not (PDF_SKILLS / rel).is_file():
                missing.append(rel)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
