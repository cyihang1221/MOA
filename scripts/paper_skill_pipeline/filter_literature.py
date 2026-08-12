"""文献筛选：优先保留「可能含详细软件参数、可开放获取全文」的文章。"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Iterable

from fetch_papers import PaperRecord


# 工具/参数线索（标题+摘要）
TOOL_PATTERNS = [
    r"\bXCMS\b",
    r"\bMZmine\b",
    r"\bOpenMS\b",
    r"\bMS-?DIAL\b",
    r"\bGNPS\b",
    r"\bFBMN\b",
    r"\bMS2LDA\b",
    r"\bMetaboAnalyst\b",
    r"\bmixOmics\b",
    r"\bSIRIUS\b",
    r"\bCAMERA\b",
    r"\bIPO\b",
    r"\bmummichog\b",
    r"\bKEGG\b",
]

PARAM_HINT_PATTERNS = [
    r"\bppm\b",
    r"peak\s*width",
    r"snthresh|S/N|signal[- ]to[- ]noise",
    r"prefilter",
    r"cosine",
    r"VIP",
    r"FDR|Benjamini",
    r"parameter[s]?",
    r"workflow|protocol|pipeline",
    r"centWave|obiwarp",
    r"alignment|peak picking|preprocessing",
]

METHODS_RICH_PATTERNS = [
    r"\bppm\s*=?\s*\d+",
    r"peakwidth\s*=?\s*[\[\(]?\s*\d+",
    r"snthresh\s*=?\s*\d+",
    r"cosine\s*(score)?\s*[≥>=]?\s*0\.\d+",
    r"n\.?tree\s*=?\s*\d+",
    r"m/z\s*tolerance",
    r"retention time",
]


PREFERRED_JOURNALS = [
    "nature methods",
    "nature protocols",
    "nature communications",
    "analytical chemistry",
    "metabolomics",
    "bioinformatics",
    "nucleic acids research",
    "gigascience",
    "scientific reports",
    "journal of proteome research",
    "anal chem",
]


def _blob(rec: PaperRecord) -> str:
    return f"{rec.title}\n{rec.abstract}\n{rec.journal}".lower()


def score_metadata(rec: PaperRecord) -> tuple[float, list[str]]:
    """仅用元数据打分（检索后、下载 Methods 前）。"""
    score = 0.0
    reasons: list[str] = []
    text = _blob(rec)

    if rec.pmc:
        score += 25
        reasons.append("+pmc_fulltext")
    elif rec.oa_url:
        score += 10
        reasons.append("+oa_url")

    tool_hits = [p for p in TOOL_PATTERNS if re.search(p, text, re.I)]
    if tool_hits:
        score += min(30, 8 * len(tool_hits))
        reasons.append(f"+tools:{len(tool_hits)}")

    param_hits = [p for p in PARAM_HINT_PATTERNS if re.search(p, text, re.I)]
    if param_hits:
        score += min(25, 5 * len(param_hits))
        reasons.append(f"+param_hints:{len(param_hits)}")

    j = (rec.journal or "").lower()
    if any(p in j for p in PREFERRED_JOURNALS):
        score += 10
        reasons.append("+preferred_journal")

    try:
        year = int(rec.year) if rec.year else 0
    except ValueError:
        year = 0
    if year >= 2020:
        score += 5
        reasons.append("+recent")
    if year >= 2023:
        score += 3
        reasons.append("+very_recent")

    if rec.citation_count >= 20:
        score += 5
        reasons.append("+cited>=20")
    elif rec.citation_count >= 5:
        score += 2
        reasons.append("+cited>=5")

    if len(rec.abstract) >= 400:
        score += 5
        reasons.append("+long_abstract")

    # 明显无关惩罚
    if not tool_hits and "metabol" not in text and "mass spectrom" not in text and "lc-ms" not in text:
        score -= 20
        reasons.append("-weak_metabolomics_signal")

    rec.filter_score = score
    rec.filter_reasons = list(dict.fromkeys((rec.filter_reasons or []) + reasons))
    return score, rec.filter_reasons


def score_methods_richness(methods_text: str) -> tuple[float, list[str]]:
    """下载 Methods 后，用启发式估计「是否像含详细参数」。"""
    if not methods_text:
        return 0.0, ["-empty_methods"]
    score = 0.0
    reasons: list[str] = []
    n = len(methods_text)
    if n >= 3000:
        score += 15
        reasons.append("+methods_len>=3k")
    elif n >= 1000:
        score += 8
        reasons.append("+methods_len>=1k")

    hits = 0
    for p in METHODS_RICH_PATTERNS:
        if re.search(p, methods_text, re.I):
            hits += 1
    if hits:
        score += min(40, 10 * hits)
        reasons.append(f"+numeric_param_patterns:{hits}")

    # key=value 或参数列表密度
    kv = len(re.findall(r"\b[A-Za-z_][A-Za-z0-9_\.]*\s*=\s*[-+]?\d", methods_text))
    if kv >= 5:
        score += 20
        reasons.append(f"+kv_assignments:{kv}")
    elif kv >= 2:
        score += 10
        reasons.append(f"+kv_assignments:{kv}")

    return score, reasons


def filter_candidates(
    records: Iterable[PaperRecord],
    *,
    min_meta_score: float = 35.0,
    top_k: int = 10,
    require_pmc: bool = True,
) -> list[PaperRecord]:
    scored: list[PaperRecord] = []
    for rec in records:
        score_metadata(rec)
        if require_pmc and not rec.pmc:
            rec.filter_reasons.append("-dropped_no_pmc")
            continue
        if rec.filter_score < min_meta_score:
            rec.filter_reasons.append(f"-below_meta_score<{min_meta_score}")
            continue
        scored.append(rec)

    scored.sort(
        key=lambda r: (r.filter_score, r.citation_count, len(r.abstract)),
        reverse=True,
    )
    return scored[: max(1, top_k)]


def records_to_dicts(records: list[PaperRecord]) -> list[dict]:
    out = []
    for r in records:
        d = asdict(r)
        # 不把超长 methods 默认塞进筛选清单
        if len(d.get("methods_text") or "") > 500:
            d["methods_text"] = d["methods_text"][:500] + "...(truncated)"
        out.append(d)
    return out
