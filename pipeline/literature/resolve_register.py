"""Resolve register bibcodes through the ADS API.

    uv run python -m pipeline.literature.resolve_register                      # dry run: all to_resolve entries
    uv run python -m pipeline.literature.resolve_register --write              # write identifier-based matches
    uv run python -m pipeline.literature.resolve_register --set REG-x BIB1 BIB2 --write

Identifier mode reads arXiv IDs and DOIs from each entry's `urls` and asks ADS for the
canonical bibcode. `--set` takes bibcodes chosen by a person or agent from ADS search
results; each one is re-resolved before it is written. Nothing reaches a register file
unless ADS returned it in this run (CLAUDE.md rule 2).

Every match is printed with first author and year next to the entry's `authors` and
`year`, so mismatches are visible before `--write`.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from pipeline.literature.ads import resolve, search

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "register"

ARXIV_RE = re.compile(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5}|[a-z\-]+/[0-9]{7})", re.I)
DOI_RE = re.compile(r"doi\.org/(10\.[^\s?#]+)", re.I)
BIB_LINE_RE = re.compile(r"^bibcodes:.*$", re.M)


def identifiers(entry: dict) -> list[tuple[str, str]]:
    out = []
    for url in entry.get("urls") or []:
        if m := ARXIV_RE.search(url):
            out.append(("arXiv", m.group(1)))
        elif m := DOI_RE.search(url):
            out.append(("doi", m.group(1)))
    return out


def lookup(kind: str, value: str) -> dict | None:
    q = f'identifier:"arXiv:{value}"' if kind == "arXiv" else f'doi:"{value}"'
    docs = search(q, rows=2)
    return docs[0] if len(docs) == 1 else (docs[0] if docs else None)


def describe(doc: dict) -> str:
    first = (doc.get("author") or ["?"])[0]
    return f"{doc['bibcode']}  {doc.get('year')}  {first}  | {(doc.get('title') or [''])[0][:70]}"


def plausible(entry: dict, doc: dict) -> bool:
    surname = (doc.get("author") or [""])[0].split(",")[0].strip().lower()
    authors = (entry.get("authors") or "").lower()
    year_ok = abs(int(doc.get("year") or 0) - int(entry["year"])) <= 2
    return bool(surname) and surname in authors and year_ok


def write_bibcodes(path: Path, bibcodes: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    values = ", ".join(f'"{b}"' for b in bibcodes)
    new, n = BIB_LINE_RE.subn(f"bibcodes: {{ status: resolved, values: [{values}] }}", text, count=1)
    if n != 1:
        raise SystemExit(f"{path.name}: no single-line bibcodes field to replace")
    path.write_text(new, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write results (default: dry run)")
    ap.add_argument("--set", nargs="+", metavar=("REG_ID", "BIBCODE"), help="explicit bibcodes for one entry")
    ap.add_argument("--allow-mismatch", action="store_true", help="write even if author/year check fails")
    a = ap.parse_args()

    if a.set:
        reg_id, bibs = a.set[0], a.set[1:]
        path = REGISTER / f"{reg_id}.yaml"
        entry = yaml.safe_load(path.read_text(encoding="utf-8"))
        docs = []
        for b in bibs:
            d = resolve(b)
            if not d:
                print(f"NOT FOUND {b}; nothing written")
                return 1
            print(("ok        " if plausible(entry, d) else "MISMATCH  ") + describe(d))
            docs.append(d)
        if a.write:
            write_bibcodes(path, [d["bibcode"] for d in docs])
            print(f"wrote {path.name}")
        return 0

    bad = 0
    for path in sorted(REGISTER.glob("REG-*.yaml")):
        entry = yaml.safe_load(path.read_text(encoding="utf-8"))
        if entry["bibcodes"]["status"] != "to_resolve":
            continue
        ids = identifiers(entry)
        print(f"\n{entry['id']}  ({entry['year']}, {entry.get('authors', '')[:50]})")
        if not ids:
            print("  no arXiv/DOI in urls -> search ADS and use --set")
            continue
        found, ok = [], True
        for kind, value in ids:
            d = lookup(kind, value)
            if not d:
                print(f"  NOT FOUND {kind}:{value}")
                ok = False
                continue
            p = plausible(entry, d)
            ok &= p or a.allow_mismatch
            print(f"  {'ok      ' if p else 'MISMATCH'} {kind}:{value} -> {describe(d)}")
            found.append(d["bibcode"])
        if a.write and found and ok:
            write_bibcodes(path, found)
            print(f"  wrote {len(found)} bibcode(s)")
        elif a.write:
            bad += 1
            print("  not written (see above)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
