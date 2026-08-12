"""多源文献检索：PubMed / Europe PMC / OpenAlex（开放学术接口，非 Sci-Hub）。"""
from __future__ import annotations

import html
import os
import re
import time
from typing import Iterable

import requests

from fetch_papers import HEADERS, PaperRecord, _sleep, pmid_to_pmc, search_pubmed


DEFAULT_METABOLOMICS_QUERIES = [
    '(XCMS OR "MS-DIAL" OR MZmine OR OpenMS) AND (metabolomics OR "LC-MS") AND (parameters OR preprocessing OR "peak picking")',
    '(GNPS OR FBMN OR MS2LDA) AND (metabolomics OR "molecular networking")',
    '(MetaboAnalyst OR mixOmics OR "PLS-DA" OR volcano) AND metabolomics AND (workflow OR protocol)',
    '(KEGG OR enrichment OR mummichog) AND metabolomics AND (pathway OR enrichment)',
]


def _get(url: str, params: dict | None = None, timeout: int = 40) -> requests.Response:
    r = requests.get(url, params=params or {}, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r


def search_europe_pmc(
    query: str,
    *,
    max_results: int = 20,
    mindate: str | None = None,
    require_fulltext: bool = True,
) -> list[PaperRecord]:
    """Europe PMC 检索（含开放全文标记）。"""
    q = query.strip()
    # Europe PMC 查询语法与 PubMed 略有不同；去掉过严括号组合时尽量保留原样
    if require_fulltext:
        q = f"({q}) AND OPEN_ACCESS:Y"
    if mindate and mindate.isdigit():
        q = f"({q}) AND FIRST_PDATE:[{mindate}-01-01 TO 3000-12-31]"

    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": q,
        "format": "json",
        "pageSize": max(1, min(max_results, 100)),
        "resultType": "core",
        # 注意：部分 Europe PMC 部署对 sort=DATE_DESC 会返回空结果，故不传 sort
    }
    data = _get(url, params).json()
    results = ((data.get("resultList") or {}).get("result")) or []
    out: list[PaperRecord] = []
    for item in results:
        pmid = str(item.get("pmid") or "")
        pmcid = str(item.get("pmcid") or "")
        doi = str(item.get("doi") or "")
        year = str(item.get("pubYear") or "")
        title = html.unescape((item.get("title") or "").strip())
        journal = ""
        jinfo = item.get("journalInfo")
        if isinstance(jinfo, dict):
            j = jinfo.get("journal")
            if isinstance(j, dict):
                journal = j.get("title") or ""
            if not journal:
                journal = jinfo.get("journalTitle") or ""
        if not journal:
            journal = item.get("journalTitle") or ""
        authors = ""
        al = item.get("authorString") or ""
        if al:
            authors = al.split(",")[0].strip() + (" et al." if "," in al else "")
        abstract = (item.get("abstractText") or "").strip()
        cited = int(item.get("citedByCount") or 0)
        is_oa = str(item.get("isOpenAccess") or "").upper() == "Y"
        out.append(
            PaperRecord(
                pmid=pmid,
                pmc=pmcid if pmcid.upper().startswith("PMC") else (f"PMC{pmcid}" if pmcid else ""),
                doi=doi,
                title=title or (f"PMID{pmid}" if pmid else doi),
                journal=journal or "",
                year=year,
                authors=authors,
                abstract=abstract,
                citation_count=cited,
                source="europe_pmc",
                filter_reasons=["europe_pmc_oa" if is_oa else "europe_pmc_ft"],
            )
        )
        if len(out) >= max_results:
            break
        time.sleep(0.15)
    return out


def search_openalex(
    query: str,
    *,
    max_results: int = 20,
    mindate: str | None = None,
    require_oa: bool = True,
) -> list[PaperRecord]:
    """OpenAlex 检索（开放元数据；可筛 OA）。

    说明：这里的「SCI/科学文献」指开放学术图谱检索，不是 Web of Science 付费接口，也不是 Sci-Hub。
    """
    filters = ["type:article"]
    if require_oa:
        filters.append("is_oa:true")
    if mindate and mindate.isdigit():
        filters.append(f"from_publication_date:{mindate}-01-01")

    params = {
        "search": query,
        "filter": ",".join(filters),
        "per_page": max(1, min(max_results, 50)),
        "sort": "publication_date:desc",
        "mailto": (os.environ.get("NCBI_EMAIL") or os.environ.get("OPENALEX_EMAIL") or "massagent@local"),
    }
    url = "https://api.openalex.org/works"
    data = _get(url, params).json()
    out: list[PaperRecord] = []
    for item in data.get("results") or []:
        ids = item.get("ids") or {}
        doi = (ids.get("doi") or item.get("doi") or "")
        doi = re.sub(r"^https?://doi\.org/", "", str(doi), flags=re.I)
        pmid = ""
        pmc = ""
        # OpenAlex 有时在 ids 里给 pmid
        raw_pmid = ids.get("pmid") or ""
        if raw_pmid:
            m = re.search(r"(\d+)$", str(raw_pmid))
            if m:
                pmid = m.group(1)
        raw_pmc = ids.get("pmcid") or ""
        if raw_pmc:
            m = re.search(r"(PMC\d+|\d+)$", str(raw_pmc), re.I)
            if m:
                pmc = m.group(1)
                if not pmc.upper().startswith("PMC"):
                    pmc = f"PMC{pmc}"

        title = (item.get("display_name") or item.get("title") or "").strip()
        year = str(item.get("publication_year") or "")
        cited = int(item.get("cited_by_count") or 0)
        abstract = ""
        # OpenAlex inverted abstract
        inv = item.get("abstract_inverted_index")
        if isinstance(inv, dict) and inv:
            try:
                pairs = []
                for word, positions in inv.items():
                    for pos in positions:
                        pairs.append((pos, word))
                pairs.sort()
                abstract = " ".join(w for _, w in pairs)
            except Exception:
                abstract = ""

        primary = item.get("primary_location") or {}
        source = primary.get("source") or {}
        journal = (source.get("display_name") or "") if isinstance(source, dict) else ""
        oa = item.get("open_access") or {}
        oa_url = (oa.get("oa_url") or primary.get("landing_page_url") or "") if isinstance(oa, dict) else ""

        authorships = item.get("authorships") or []
        authors = ""
        if authorships:
            a0 = (authorships[0].get("author") or {}).get("display_name") or ""
            authors = f"{a0} et al." if len(authorships) > 1 else a0

        out.append(
            PaperRecord(
                pmid=pmid,
                pmc=pmc,
                doi=doi,
                title=title or doi,
                journal=journal,
                year=year,
                authors=authors,
                abstract=abstract,
                citation_count=cited,
                oa_url=oa_url or "",
                source="openalex",
                filter_reasons=["openalex_oa"] if require_oa else ["openalex"],
            )
        )
        if len(out) >= max_results:
            break
    return out


def enrich_pmc_if_missing(records: Iterable[PaperRecord]) -> list[PaperRecord]:
    from fetch_papers import resolve_doi_to_pmid

    out = []
    for rec in records:
        if rec.doi and not rec.pmid:
            try:
                rec.pmid = resolve_doi_to_pmid(rec.doi)
                _sleep()
            except Exception as exc:
                rec.errors.append(f"doi_to_pmid:{exc}")
        if rec.pmid and not rec.pmc:
            try:
                rec.pmc = pmid_to_pmc(rec.pmid)
                _sleep()
            except Exception as exc:
                rec.errors.append(f"pmid_to_pmc:{exc}")
        out.append(rec)
    return out


def merge_records(*groups: list[PaperRecord]) -> list[PaperRecord]:
    """按 DOI/PMID 去重，保留信息更全的一条。"""
    best: dict[str, PaperRecord] = {}

    def richness(r: PaperRecord) -> tuple:
        return (
            1 if r.pmc else 0,
            1 if r.abstract else 0,
            1 if r.pmid else 0,
            1 if r.doi else 0,
            r.citation_count,
            len(r.abstract),
        )

    for group in groups:
        for r in group:
            key = r.dedupe_key()
            if key not in best or richness(r) > richness(best[key]):
                # 合并来源标记
                if key in best and best[key].source and r.source and best[key].source != r.source:
                    r.source = f"{best[key].source}+{r.source}"
                    r.filter_reasons = list(dict.fromkeys(best[key].filter_reasons + r.filter_reasons))
                    if not r.abstract:
                        r.abstract = best[key].abstract
                    if not r.pmc:
                        r.pmc = best[key].pmc
                    if not r.pmid:
                        r.pmid = best[key].pmid
                best[key] = r
    return list(best.values())


def multi_source_search(
    query: str,
    *,
    sources: list[str] | None = None,
    max_per_source: int = 15,
    mindate: str | None = None,
    require_fulltext: bool = True,
) -> list[PaperRecord]:
    sources = sources or ["pubmed", "europe_pmc", "openalex"]
    groups: list[list[PaperRecord]] = []
    print(f"[search] query={query!r} sources={sources} max_per_source={max_per_source}")

    if "pubmed" in sources:
        try:
            hits = search_pubmed(
                query,
                max_results=max_per_source,
                mindate=mindate,
                require_pmc=require_fulltext,
            )
            print(f"  - pubmed: {len(hits)}")
            groups.append(hits)
        except Exception as exc:
            print(f"  - pubmed ERROR: {exc}")

    if "europe_pmc" in sources or "epmc" in sources:
        try:
            hits = search_europe_pmc(
                query,
                max_results=max_per_source,
                mindate=mindate,
                require_fulltext=require_fulltext,
            )
            print(f"  - europe_pmc: {len(hits)}")
            groups.append(hits)
        except Exception as exc:
            print(f"  - europe_pmc ERROR: {exc}")

    if "openalex" in sources or "sci" in sources:
        try:
            hits = search_openalex(
                query,
                max_results=max_per_source,
                mindate=mindate,
                require_oa=require_fulltext,
            )
            print(f"  - openalex: {len(hits)}")
            groups.append(hits)
        except Exception as exc:
            print(f"  - openalex ERROR: {exc}")

    merged = merge_records(*groups)
    merged = enrich_pmc_if_missing(merged)
    print(f"[search] merged unique: {len(merged)}")
    return merged
