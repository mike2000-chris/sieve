"""Minimal NASA ADS client: search and bibcode resolution.

    uv run python -m pipeline.literature.ads 2024MNRAS.531..695S
    uv run python -m pipeline.literature.ads --query "Dyson sphere infrared excess Gaia WISE"

Requires ADS_API_KEY in .env (https://ui.adsabs.harvard.edu/user/settings/token).
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

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
