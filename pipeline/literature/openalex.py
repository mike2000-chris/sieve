"""OpenAlex client (no key; set OPENALEX_MAILTO in .env for the polite pool)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

from pipeline.literature.cache import cached_get

API = "https://api.openalex.org/works"


def _polite_headers() -> dict:
    """Polite pool via the User-Agent, so the contact address stays out of the cached request parameters."""
    mailto = os.environ.get("OPENALEX_MAILTO")
    return {"User-Agent": f"python-httpx (mailto:{mailto})"} if mailto else {}


def search(query: str, per_page: int = 10, use_cache: bool = True) -> list[dict]:
    load_dotenv()
    params = {"search": query, "per-page": per_page, "filter": "concepts.id:C121332964"}  # physics; refine later
    body = cached_get("openalex", API, params, _polite_headers(), use_cache)
    return [
        {"doi": w.get("doi"), "title": w.get("title"), "year": w.get("publication_year"), "id": w.get("id")}
        for w in body.get("results", [])
    ]
