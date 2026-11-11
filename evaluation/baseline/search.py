"""Run the ADS queries that define the literature baseline and write the raw result log.

    uv run python -m evaluation.baseline.search                      # writes evaluation/baseline/search_log.json
    uv run python -m evaluation.baseline.search --abstracts FILE     # also dumps abstracts for screening
    uv run python -m evaluation.baseline.search --verify             # re-resolve included sources, write nothing

Reads queries.yaml, sends each query to the ADS API with the common filter, sort and row cut, and records what
ADS returned: bibcode, year, first author, title, doctype, citation count and rank. Abstracts are not stored in
the repository (write the dump outside it). Citation counts drift, so the log is dated; the committed log is the
frozen selection.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import httpx
import yaml

from pipeline.literature.ads import ADS, _headers

HERE = Path(__file__).resolve().parent
FIELDS = "bibcode,title,year,author,doctype,citation_count,abstract"


def run() -> tuple[dict, str]:
    cfg = yaml.safe_load((HERE / "queries.yaml").read_text(encoding="utf-8"))
    out = {"version": cfg["version"], "retrieved": dt.date.today().isoformat(), "common_filter": cfg["common_filter"],
           "sort": cfg["sort"], "rows": cfg["rows"], "queries": []}
    abstracts = []
    for q in cfg["queries"]:
        full = f"({q['q']}) AND {cfg['common_filter']}"
        r = httpx.get(ADS, params={"q": full, "fl": FIELDS, "rows": cfg["rows"], "sort": cfg["sort"]},
                      headers=_headers(), timeout=30)
        r.raise_for_status()
        resp = r.json()["response"]
        rows = []
        for rank, d in enumerate(resp["docs"], 1):
            rows.append({"rank": rank, "bibcode": d["bibcode"], "year": int(d["year"]),
                         "first_author": (d.get("author") or ["?"])[0], "title": (d.get("title") or [""])[0],
                         "doctype": d.get("doctype"), "citation_count": d.get("citation_count", 0)})
            abstracts.append(f"[{q['id']} #{rank}] {d['bibcode']} {rows[-1]['first_author']} | {rows[-1]['title']}\n"
                             f"{d.get('abstract', '(no abstract)')}\n")
        out["queries"].append({"id": q["id"], "domain": q["domain"], "source_type": q["source_type"], "q": full,
                               "num_found": resp["numFound"], "results": rows})
        print(f"{q['id']}: {resp['numFound']} found, {len(rows)} kept")
    return out, "\n".join(abstracts)


def verify() -> int:
    """Re-resolve every included source in sources.yaml through ADS and compare first author, year and title."""
    sources = yaml.safe_load((HERE / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    bad = 0
    for s in (x for x in sources if x["decision"] == "included"):
        r = httpx.get(ADS, params={"q": f'bibcode:"{s["bibcode"]}"', "fl": "bibcode,title,year,author", "rows": 1},
                      headers=_headers(), timeout=30)
        r.raise_for_status()
        docs = r.json()["response"]["docs"]
        ok = bool(docs) and docs[0]["bibcode"] == s["bibcode"] and int(docs[0]["year"]) == s["year"] \
            and (docs[0].get("author") or ["?"])[0] == s["first_author"] and (docs[0].get("title") or [""])[0] == s["title"]
        bad += not ok
        print("resolved " if ok else "MISMATCH ", s["bibcode"], s["first_author"], s["year"])
    print(f"{bad} mismatches")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--abstracts", metavar="FILE", help="dump titles and abstracts to FILE (keep it outside the repository)")
    ap.add_argument("--verify", action="store_true", help="re-resolve included sources in sources.yaml; writes nothing")
    a = ap.parse_args()
    if a.verify:
        return verify()
    log, abstracts = run()
    (HERE / "search_log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if a.abstracts:
        Path(a.abstracts).write_text(abstracts, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
