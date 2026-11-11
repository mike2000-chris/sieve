"""On-disk cache for raw literature API responses (ADS, OpenAlex).

Raw responses stay out of git (CLAUDE.md rule 5): the default location is `.cache/literature/` in the repository
root, which is gitignored; set SIEVE_CACHE_DIR to move it. What enters the repository is the small result table in
the G2 gate log (bibcode, year, title, rank per card).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def cache_dir() -> Path:
    return Path(os.environ.get("SIEVE_CACHE_DIR") or ROOT / ".cache" / "literature")


def cached_get(service: str, url: str, params: dict, headers: dict | None = None, use_cache: bool = True) -> dict:
    """GET returning parsed JSON; the cache key is service + url + params (never the headers, which hold the API key)."""
    key = hashlib.sha256(json.dumps([service, url, params], sort_keys=True).encode()).hexdigest()[:24]
    path = cache_dir() / service / f"{key}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    r = httpx.get(url, params=params, headers=headers or {}, timeout=30)
    r.raise_for_status()
    body = r.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                "url": url, "params": params, "response": body}), encoding="utf-8")
    return body
