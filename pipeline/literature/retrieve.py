"""Literature retrieval for gate G2: queries -> up to k papers, every one with an ADS-resolved bibcode.

    uv run python -m pipeline.literature.retrieve "Dyson sphere infrared excess" "mid-infrared excess main-sequence stars"

NASA ADS is the primary source (relevance-sorted, relaxed when the strict all-terms form finds too little). OpenAlex
is secondary: its hits enter the pool only if their DOI resolves to an ADS record, so every paper handed to the
judge carries a bibcode that resolved through the ADS API (CLAUDE.md rule 2). arXiv preprints are covered through
ADS, which indexes them as `eprint` records.

Ranking has two halves, equally weighted:
- rank fusion over the per-query result lists (sum of 1/(RRF_K + rank); a paper near the top of several lists wins;
  lists from an ADS query relaxed by two terms count half);
- coverage of the combined query vocabulary by the paper's title and abstract, weighted by how rare each term is in
  the pool. This pushes down papers that match one relaxed query on generic words only.
"""
from __future__ import annotations

import math
import re
import sys

from pipeline.literature import ads, openalex

RRF_K = 2
ROWS_PER_QUERY = 10
MAX_ABSTRACT_CHARS = 4000   # longer abstracts are cut with a visible marker; ADS abstracts are rarely above 2,500


def _paper(doc: dict) -> dict:
    abstract = (doc.get("abstract") or "").strip()
    if len(abstract) > MAX_ABSTRACT_CHARS:
        abstract = abstract[:MAX_ABSTRACT_CHARS] + " [abstract cut by the pipeline]"
    authors = doc.get("author") or []
    return {"bibcode": doc["bibcode"], "year": doc.get("year"), "title": (doc.get("title") or [""])[0],
            "first_author": authors[0] if authors else None, "n_authors": len(authors), "pub": doc.get("pub"),
            "abstract": abstract}


_STOP = set("a an and are as at by for from in into is of on or the to with without using via search searches".split())


def _vocabulary(queries: list[str]) -> list[str]:
    words = {w.rstrip("s") for q in queries for w in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", q.lower())}
    return sorted(w for w in words if w not in _STOP)


def _coverage(pool: dict[str, dict], queries: list[str]) -> dict[str, float]:
    """Per paper: idf-weighted share of the query vocabulary found in title + abstract (0..1)."""
    vocab = _vocabulary(queries)
    texts = {b: f"{p['title']} {p['abstract']}".lower() for b, p in pool.items()}
    idf = {w: math.log(1 + len(pool) / (1 + sum(w in t for t in texts.values()))) for w in vocab}
    total = sum(idf.values()) or 1.0
    return {b: sum(idf[w] for w in vocab if w in t) / total for b, t in texts.items()}


def retrieve(queries: list[str], k: int = 10, rows: int = ROWS_PER_QUERY, use_cache: bool = True) -> dict:
    """Run the queries and return {"papers": [...], "per_query": [...], "openalex_unresolved": n}.

    Each paper: bibcode, year, title, first_author, n_authors, pub, abstract, rank, score, found_by (query indices),
    sources (subset of {"ads", "openalex"}).
    """
    pool: dict[str, dict] = {}
    per_query, unresolved = [], 0

    def add(doc: dict, rank: int, weight: float, qi: int, source: str) -> None:
        p = pool.setdefault(doc["bibcode"], {**_paper(doc), "score": 0.0, "found_by": [], "sources": []})
        p["score"] += weight / (RRF_K + rank)
        if qi not in p["found_by"]:
            p["found_by"].append(qi)
        if source not in p["sources"]:
            p["sources"].append(source)

    for qi, query in enumerate(queries):
        docs, form = ads.search_relaxed(query, rows=rows, use_cache=use_cache)
        for rank, doc in enumerate(docs, 1):
            add(doc, rank, 0.5 if form == "all_but_2" else 1.0, qi, "ads")
        oa = [w for w in openalex.search(query, per_page=rows, use_cache=use_cache) if w.get("doi")]
        resolved = ads.resolve_dois([w["doi"] for w in oa], use_cache=use_cache)
        n_res = 0
        for rank, w in enumerate(oa, 1):
            doc = resolved.get(w["doi"].lower().removeprefix("https://doi.org/"))
            if doc:
                n_res += 1
                add(doc, rank, 1.0, qi, "openalex")
        unresolved += len(oa) - n_res
        per_query.append({"query": query, "ads_hits": len(docs), "ads_form": form, "openalex_hits": len(oa),
                          "openalex_resolved_in_ads": n_res})

    coverage = _coverage(pool, queries)
    top = max((p["score"] for p in pool.values()), default=1.0)
    for b, p in pool.items():
        p["score"] = 0.5 * p["score"] / top + 0.5 * coverage[b]
    papers = sorted(pool.values(), key=lambda p: (-p["score"], -int(p["year"] or 0), p["bibcode"]))[:k]
    for rank, p in enumerate(papers, 1):
        p["rank"], p["score"] = rank, round(p["score"], 4)
    return {"papers": papers, "per_query": per_query, "pool_size": len(pool), "openalex_unresolved": unresolved}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    res = retrieve(sys.argv[1:])
    for q in res["per_query"]:
        print(q)
    for p in res["papers"]:
        print(f"{p['rank']:2d} {p['score']:.4f} {p['bibcode']} {p['year']} {'+'.join(p['sources']):12s} {p['title'][:80]}")
    print(f"pool {res['pool_size']}, OpenAlex DOIs without an ADS record: {res['openalex_unresolved']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
