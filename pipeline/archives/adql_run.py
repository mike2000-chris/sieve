"""Run a SIEVE .adql query file against the Gaia archive with the count-then-chunk discipline.

    uv run python -m pipeline.archives.adql_run analyses/dr4-day-one/dr3-dryrun/astrometric_anomalies_dr3.adql --list
    uv run python -m pipeline.archives.adql_run FILE --count 0            # run statement 0 (a COUNT) only
    uv run python -m pipeline.archives.adql_run FILE --chunked 1 --count-stmt 0 --out results/x.ecsv
    uv run python -m pipeline.archives.adql_run FILE --run 2 --out results/y.ecsv   # unchunked, checked against cap

Optional login: if GAIA_USER and GAIA_PASSWORD are set (environment or .env) the runner logs in via astroquery
before the first query; otherwise it stays anonymous. The password is never printed. The authenticated row limit is
read from config/archives.yaml (gaia.authenticated_row_limit; null = not yet measured, chunking then stays at the
anonymous size). The COUNT check (rows must equal COUNT) applies in both modes.

Statements in a file are separated by ';'. Lines starting with '--' are comments. A chunked statement must contain
`random_index BETWEEN :lo AND :hi`; the runner picks chunk bounds so that each chunk's expected size stays under
CHUNK_TARGET, then checks that the rows add up to the COUNT. Anonymous Gaia results are silently cut at 50,000 rows
(Phase 0 smoke test), so any unchunked result of exactly 50,000 rows is treated as an error.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
ROW_CAP = 50_000
CHUNK_TARGET = 40_000
CHUNK_HEADROOM = 0.8  # authenticated chunks are sized at 80 % of the measured limit
RANDOM_INDEX_MAX = {"gaiadr3": 1_811_709_770, "gaiadr4": None}  # DR4: read MAX(random_index) on release day


def statements(path: Path) -> list[str]:
    body = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def authenticated_row_limit(config_path: Path | None = None) -> int | None:
    """Row limit for authenticated Gaia jobs from config/archives.yaml, or None while it is unmeasured."""
    cfg = yaml.safe_load((config_path or ROOT / "config" / "archives.yaml").read_text(encoding="utf-8"))
    for a in cfg.get("archives", []):
        if a.get("key") == "gaia":
            v = a.get("authenticated_row_limit")
            return int(v) if v else None
    return None


def gaia_login(env=None) -> str | None:
    """Log in if GAIA_USER and GAIA_PASSWORD are set; return the user name, or None (anonymous).

    Never prints or returns the password. A failed login falls back to anonymous with a warning.
    """
    from dotenv import load_dotenv

    if env is None:
        load_dotenv(ROOT / ".env")
        env = os.environ
    user, pw = env.get("GAIA_USER"), env.get("GAIA_PASSWORD")
    if not (user and pw):
        print("Gaia archive: anonymous")
        return None
    from astroquery.gaia import Gaia

    try:
        Gaia.login(user=user, password=pw)
    except Exception as e:  # do not echo the message: it may contain request details
        print(f"Gaia archive: login failed ({type(e).__name__}); continuing anonymous")
        return None
    print(f"Gaia archive: authenticated as {user}")
    return user


def limits(authenticated: bool, config_path: Path | None = None) -> tuple[int, int]:
    """(row_cap, chunk_target). Authenticated with a measured limit: cap = limit, chunks = 80 % of it."""
    lim = authenticated_row_limit(config_path) if authenticated else None
    if lim is None:
        return ROW_CAP, CHUNK_TARGET
    return lim, int(lim * CHUNK_HEADROOM)


def _launch(adql: str):
    from astroquery.gaia import Gaia

    t0 = time.time()
    table = Gaia.launch_job_async(adql).get_results()
    return table, time.time() - t0


def run_count(adql: str) -> int:
    table, dt = _launch(adql)
    n = int(table[table.colnames[0]][0])
    print(f"COUNT = {n:,}  ({dt:.1f} s)")
    return n


def random_index_max(adql: str) -> int:
    schema = "gaiadr4" if "gaiadr4." in adql else "gaiadr3"
    if RANDOM_INDEX_MAX.get(schema):
        return RANDOM_INDEX_MAX[schema]
    n = run_count(f"SELECT MAX(random_index) FROM {schema}.gaia_source")
    RANDOM_INDEX_MAX[schema] = n
    return n


def run_chunked(adql: str, total: int, row_cap: int = ROW_CAP, chunk_target: int = CHUNK_TARGET):
    from astropy.table import vstack

    if ":lo" not in adql or ":hi" not in adql:
        raise SystemExit("chunked statement needs 'random_index BETWEEN :lo AND :hi'")
    rmax = random_index_max(adql)
    n_chunks = max(1, math.ceil(total / chunk_target))
    edges = [round(i * (rmax + 1) / n_chunks) for i in range(n_chunks + 1)]
    parts, log = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        t, dt = _launch(adql.replace(":lo", str(lo)).replace(":hi", str(hi - 1)))
        if len(t) >= row_cap:
            raise SystemExit(f"chunk {lo}-{hi - 1} hit the {row_cap:,}-row cap; use more chunks")
        print(f"  chunk {lo:>13,}-{hi - 1:<13,} {len(t):>7,} rows  {dt:.1f} s")
        log.append({"lo": lo, "hi": hi - 1, "rows": len(t), "seconds": round(dt, 1)})
        parts.append(t)
    table = vstack(parts) if parts else None
    got = len(table) if table is not None else 0
    status = "ok" if got == total else "MISMATCH"
    print(f"rows {got:,} vs COUNT {total:,}: {status}")
    if got != total:
        raise SystemExit(1)
    return table, log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--list", action="store_true", help="print the statements with their index")
    ap.add_argument("--count", type=int, metavar="I", help="run statement I as a COUNT")
    ap.add_argument("--chunked", type=int, metavar="I", help="run statement I in random_index chunks")
    ap.add_argument("--count-stmt", type=int, metavar="J", help="COUNT statement used to size and check --chunked")
    ap.add_argument("--run", type=int, metavar="I", help="run statement I unchunked (fails at the row cap)")
    ap.add_argument("--out", type=Path, help="write the result table (ecsv) and a .json run record next to it")
    a = ap.parse_args()

    stmts = statements(a.file)
    if a.list or all(v is None for v in (a.count, a.chunked, a.run)):
        for i, s in enumerate(stmts):
            print(f"[{i}] {s[:160].replace(chr(10), ' ')}{'...' if len(s) > 160 else ''}")
        return 0

    user = gaia_login()
    row_cap, chunk_target = limits(user is not None)
    if user and row_cap == ROW_CAP:
        print("authenticated_row_limit is null in config/archives.yaml: keeping anonymous chunk size; measure the limit")
    record = {"file": str(a.file), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "gaia_user": user or "anonymous", "row_cap": row_cap, "chunk_target": chunk_target}
    table = None
    if a.count is not None:
        record["count"] = run_count(stmts[a.count])
    if a.chunked is not None:
        if a.count_stmt is None:
            raise SystemExit("--chunked needs --count-stmt")
        total = run_count(stmts[a.count_stmt])
        table, record["chunks"] = run_chunked(stmts[a.chunked], total, row_cap, chunk_target)
        record["count"] = total
    if a.run is not None:
        table, dt = _launch(stmts[a.run])
        if len(table) >= row_cap:
            raise SystemExit(f"result hit the {row_cap:,}-row cap; chunk this statement")
        record.update(rows=len(table), seconds=round(dt, 1))
        print(f"{len(table):,} rows ({dt:.1f} s)")
    if a.out and table is not None:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        table.write(a.out, format="ascii.ecsv", overwrite=True)
        a.out.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(json.dumps(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
