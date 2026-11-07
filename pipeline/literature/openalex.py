"""OpenAlex client (no key; set OPENALEX_MAILTO in .env for the polite pool)."""
from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

API = "https://api.openalex.org/works"


def search(query: str, per_page: int = 10) -> list[dict]:
    load_dotenv()
    params = {"search": query, "per-page": per_page, "filter": "concepts.id:C121332964"}  # physics; refine later
    mailto = os.environ.get("OPENALEX_MAILTO")
    if mailto:
        params["mailto"] = mailto
    r = httpx.get(API, params=params, timeout=30)
    r.raise_for_status()
    return [
        {"doi": w.get("doi"), "title": w.get("title"), "year": w.get("publication_year"), "id": w.get("id")}
        for w in r.json().get("results", [])
    ]
