"""抓取新文献全文 / Methods 文本（PubMed → PMC HTML 优先）。"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "MassAgentPaperPipeline/1.0 "
        "(research; contact via NCBI_EMAIL env if set)"
    )
}

METHOD_HEADING_RE = re.compile(
    r"(>Methods</h2>|>METHODS</h2>|>Method</h2>|>METHOD</h2>"
    r"|>Materials and Methods</h2>|>Material and Methods</h2>"
    r"|>Materials and methods</h2>|>MATERIALS AND METHODS</h2>"
    r"|>Experimental Procedures</h2>|>Experimental methods</h2>)",
    re.I,
)


@dataclass
class PaperRecord:
    pmid: str = ""
    pmc: str = ""
    doi: str = ""
    title: str = ""
    journal: str = ""
    year: str = ""
    authors: str = ""
    abstract: str = ""
    citation_count: int = 0
    oa_url: str = ""
    methods_text: str = ""
    html_path: str = ""
    methods_path: str = ""
    source: str = ""
    filter_score: float = 0.0
    filter_reasons: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def source_paper_line(self) -> str:
        bits = []
        if self.authors:
            bits.append(self.authors)
        if self.year:
            bits.append(f"({self.year})")
        if self.journal:
            bits.append(self.journal)
        if self.doi:
            bits.append(f"DOI: {self.doi}")
        if self.pmid:
            bits.append(f"PMID: {self.pmid}")
        return ", ".join(bits) if bits else (self.title or "unknown")

    def dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.lower().strip()}"
        if self.pmid:
            return f"pmid:{self.pmid}"
        if self.pmc:
            return f"pmc:{self.pmc.upper()}"
        return f"title:{(self.title or '').lower().strip()[:120]}"


def _ncbi_params() -> dict[str, str]:
    params: dict[str, str] = {}
    email = (os.environ.get("NCBI_EMAIL") or "").strip()
    api_key = (os.environ.get("NCBI_API_KEY") or "").strip()
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def _get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 30) -> dict:
    p = dict(_ncbi_params())
    if params:
        p.update(params)
    r = requests.get(url, params=p, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _sleep() -> None:
    # 有 API key 可更快；默认保守
    delay = 0.12 if os.environ.get("NCBI_API_KEY") else 0.35
    time.sleep(delay)


def resolve_doi_to_pmid(doi: str) -> str:
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.I)
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    data = _get_json(url, {"db": "pubmed", "term": f"{doi}[doi]", "retmode": "json"})
    ids = data.get("esearchresult", {}).get("idlist") or []
    return ids[0] if ids else ""


def fetch_pubmed_summary(pmid: str) -> dict[str, str]:
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    data = _get_json(url, {"db": "pubmed", "id": pmid, "retmode": "json"})
    result = (data.get("result") or {}).get(pmid) or {}
    authors = result.get("authors") or []
    author_str = ""
    if authors:
        first = authors[0].get("name") or ""
        author_str = f"{first} et al." if len(authors) > 1 else first
    articleids = result.get("articleids") or []
    doi = ""
    for aid in articleids:
        if aid.get("idtype") == "doi":
            doi = aid.get("value") or ""
            break
    return {
        "title": result.get("title") or "",
        "journal": result.get("fulljournalname") or result.get("source") or "",
        "year": str(result.get("pubdate") or "")[:4],
        "authors": author_str,
        "doi": doi,
    }


def pmid_to_pmc(pmid: str) -> str:
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
    data = _get_json(
        url,
        {"dbfrom": "pubmed", "db": "pmc", "id": pmid, "retmode": "json"},
    )
    for linkset in data.get("linksets") or []:
        for db in linkset.get("linksetdbs") or []:
            if db.get("linkname") == "pubmed_pmc":
                links = db.get("links") or []
                if links:
                    return f"PMC{links[0]}"
    return ""


def search_pubmed(
    query: str,
    *,
    max_results: int = 5,
    mindate: str | None = None,
    maxdate: str | None = None,
    require_pmc: bool = True,
) -> list[PaperRecord]:
    """PubMed 检索；默认只要有 PMC 全文的条目。"""
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    term = query.strip()
    if require_pmc and "pmc open access" not in term.lower() and "free full text" not in term.lower():
        # 提高 PMC 命中率
        term = f"({term}) AND (ffrft[Filter] OR pmc open access[Filter])"
    params: dict[str, Any] = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "retmax": max(1, min(max_results * 3, 100)),
        "sort": "pub_date",
    }
    if mindate:
        params["mindate"] = mindate
        params["datetype"] = "pdat"
    if maxdate:
        params["maxdate"] = maxdate
        params["datetype"] = "pdat"

    data = _get_json(url, params)
    ids = data.get("esearchresult", {}).get("idlist") or []
    out: list[PaperRecord] = []
    for pmid in ids:
        _sleep()
        meta = fetch_pubmed_summary(pmid)
        _sleep()
        pmc = pmid_to_pmc(pmid)
        if require_pmc and not pmc:
            continue
        out.append(
            PaperRecord(
                pmid=pmid,
                pmc=pmc,
                doi=meta.get("doi") or "",
                title=meta.get("title") or f"PMID{pmid}",
                journal=meta.get("journal") or "",
                year=meta.get("year") or "",
                authors=meta.get("authors") or "",
                source="pubmed_search",
            )
        )
        if len(out) >= max_results:
            break
    return out


def download_pmc_html(pmc: str, save_path: Path) -> bool:
    pmc = pmc if pmc.upper().startswith("PMC") else f"PMC{pmc}"
    url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc}/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=40)
        if resp.status_code != 200:
            return False
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(resp.content)
        return True
    except Exception:
        return False


def extract_methods_from_html(html: str, max_chars: int = 45000) -> str:
    m = METHOD_HEADING_RE.search(html)
    if not m:
        # 兜底：整页去标签后截断（仍可供 LLM 尝试）
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")
        return text[:max_chars].strip()
    chunk = html[m.start() : m.start() + max_chars]
    soup = BeautifulSoup(chunk, "html.parser")
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def hydrate_record(rec: PaperRecord, cache_dir: Path) -> PaperRecord:
    """补全元数据并下载 Methods。"""
    cache_dir.mkdir(parents=True, exist_ok=True)

    if rec.doi and not rec.pmid:
        try:
            rec.pmid = resolve_doi_to_pmid(rec.doi)
            _sleep()
        except Exception as exc:
            rec.errors.append(f"doi_to_pmid:{exc}")

    if rec.pmid and (not rec.title or rec.title.startswith("PMID")):
        try:
            meta = fetch_pubmed_summary(rec.pmid)
            _sleep()
            rec.title = meta.get("title") or rec.title
            rec.journal = meta.get("journal") or rec.journal
            rec.year = meta.get("year") or rec.year
            rec.authors = meta.get("authors") or rec.authors
            if meta.get("doi"):
                rec.doi = meta["doi"]
        except Exception as exc:
            rec.errors.append(f"esummary:{exc}")

    if rec.pmid and not rec.pmc:
        try:
            rec.pmc = pmid_to_pmc(rec.pmid)
            _sleep()
        except Exception as exc:
            rec.errors.append(f"pmid_to_pmc:{exc}")

    if not rec.pmc:
        rec.errors.append("no_pmc_fulltext")
        return rec

    html_path = cache_dir / "html" / f"{rec.pmc}.html"
    if not html_path.is_file():
        ok = download_pmc_html(rec.pmc, html_path)
        if not ok:
            rec.errors.append("pmc_download_failed")
            return rec
    rec.html_path = str(html_path)
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    methods = extract_methods_from_html(html)
    if not methods or len(methods) < 200:
        rec.errors.append("methods_too_short")
        return rec

    stem = rec.doi.replace("/", "_") if rec.doi else (rec.pmid or rec.pmc)
    methods_path = cache_dir / "methods" / f"{stem}.txt"
    methods_path.parent.mkdir(parents=True, exist_ok=True)
    methods_path.write_text(methods, encoding="utf-8")
    rec.methods_text = methods
    rec.methods_path = str(methods_path)
    return rec


def load_methods_file(
    path: Path,
    *,
    title: str = "",
    doi: str = "",
    pmid: str = "",
) -> PaperRecord:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return PaperRecord(
        title=title or path.stem,
        doi=doi,
        pmid=pmid,
        methods_text=text,
        methods_path=str(path),
        source="local_file",
    )
