"""Minimal NASA ADS client: search and bibcode resolution.

    uv run python -m pipeline.literature.ads 2024MNRAS.531..695S
    uv run python -m pipeline.literature.ads --query "Dyson sphere infrared excess Gaia WISE"

Requires ADS_API_KEY in .env (https://ui.adsabs.harvard.edu/user/settings/token).

`search_relaxed` and `resolve_dois` serve gate G2 (pipeline/critique.py); their raw responses are cached outside git
(pipeline/literature/cache.py).
"""
from __future__ import annotations

import argparse
import itertools
import os
import re
import sys

import httpx
from dotenv import load_dotenv

from pipeline.literature.cache import cached_get

ADS = "https://api.adsabs.harvard.edu/v1/search/query"
FIELDS = "bibcode,title,year,author,abstract,doi,pub"


def _headers() -> dict:
    load_dotenv()
    key = os.environ.get("ADS_API_KEY")
    if not key:
        raise SystemExit("ADS_API_KEY missing; copy .env.example to .env and fill it in")
    return {"Authorization": f"Bearer {key}"}


def search(query: str, rows: int = 10, years: str | None = None) -> list[dict]:
    q = query if not years else f"({query}) AND year:{years}"
    r = httpx.get(ADS, params={"q": q, "fl": FIELDS, "rows": rows, "sort": "citation_count desc"}, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()["response"]["docs"]


def resolve(bibcode: str) -> dict | None:
    docs = search(f"bibcode:{bibcode}", rows=1)
    return docs[0] if docs else None


def _relevance(q: str, rows: int, use_cache: bool = True) -> tuple[list[dict], int]:
    body = cached_get("ads", ADS, {"q": q, "fl": FIELDS, "rows": rows, "sort": "score desc",
                                   "fq": "doctype:(article OR eprint OR inproceedings)"}, _headers(), use_cache)
    return body["response"]["docs"], body["response"]["numFound"]


def search_relaxed(query: str, rows: int = 10, min_hits: int = 3, use_cache: bool = True) -> tuple[list[dict], str]:
    """Relevance-sorted search that degrades gracefully.

    ADS requires every term of an unfielded query to match (title, abstract, keywords), so a six-word query often
    returns nothing. If the strict form yields fewer than `min_hits` papers, retry requiring any k-1 of the k terms,
    then any k-2. Returns (docs, form) with form in {"all_terms", "all_but_1", "all_but_2", "none"}.
    """
    terms = [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-\.']*", query) if t.upper() not in {"AND", "OR", "NOT"}]
    if not terms:
        return [], "none"
    best: tuple[list[dict], str] = ([], "none")
    for drop, form in ((0, "all_terms"), (1, "all_but_1"), (2, "all_but_2")):
        if len(terms) - drop < 2 and drop:
            break
        subsets = list(itertools.combinations(terms, len(terms) - drop))
        q = " OR ".join("(" + " ".join(s) + ")" for s in subsets) if drop else " ".join(terms)
        docs, _ = _relevance(q, rows, use_cache)
        if len(docs) > len(best[0]):
            best = (docs, form)
        if len(docs) >= min_hits:
            break
    return best


def resolve_dois(dois: list[str], use_cache: bool = True) -> dict[str, dict]:
    """Map DOIs to ADS records (with bibcode). DOIs unknown to ADS are absent from the result."""
    out: dict[str, dict] = {}
    clean = sorted({d.lower().removeprefix("https://doi.org/") for d in dois if d})
    for i in range(0, len(clean), 20):
        chunk = clean[i:i + 20]
        q = " OR ".join(f'doi:"{d}"' for d in chunk)
        body = cached_get("ads", ADS, {"q": q, "fl": FIELDS, "rows": 2 * len(chunk)}, _headers(), use_cache)
        for doc in body["response"]["docs"]:
            for d in doc.get("doi") or []:
                if d.lower() in chunk:
                    out[d.lower()] = doc
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bibcode", nargs="?")
    ap.add_argument("--query")
    ap.add_argument("--rows", type=int, default=10)
    a = ap.parse_args()
    if a.query:
        for d in search(a.query, rows=a.rows):
            print(d["bibcode"], d.get("year"), (d.get("title") or [""])[0][:90])
        return 0
    if a.bibcode:
        d = resolve(a.bibcode)
        print("resolved:" if d else "NOT FOUND:", a.bibcode, (d or {}).get("title", [""])[0] if d else "")
        return 0 if d else 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
