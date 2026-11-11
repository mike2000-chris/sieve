"""Critique stage: run gates G1-G4 on raw cards, append gate logs, update novelty/confounders fields.

Order: G2 fast path against the register first (cheap), then G1, G3, G4, then G2 against ADS/OpenAlex.

Implemented so far: the G2 register fast path; G1, G3, G4 (pipeline/gates/); `all` runs G2-fast, G1, G3, G4.

    uv run python -m pipeline.critique g2-fast SIEVE-0002 SIEVE-0003
    uv run python -m pipeline.critique g2-fast --all-raw [--dry-run]

The fast path ranks register entries by taxonomy match (domain, signature class, observable) and term overlap between
the card (title, claim, mechanism, method, archives) and the entry (name, hypothesis, method, data used). It writes a
gate-log event `G2-register` with the top hits; it does NOT set `novelty.status` -- that verdict belongs to the LLM
judge over ADS-resolved papers (paper Section 4.3). Entries with `bibcodes.status: to_resolve` are listed but marked
`evidence: false` (CLAUDE.md rule 2). Withheld entries are included: G2 is the novelty oracle, not the generator.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

from pipeline.gates import cli as gate_cli

ROOT = Path(__file__).resolve().parents[1]
GATE_LOGS = ROOT / "catalogue" / "gate_logs"
CARDS = ROOT / "catalogue" / "cards"
FAST_PATH_VERSION = "g2-register-v0.1"
TOP_K = 5
HIT_THRESHOLD = 4.0   # taxonomy alone gives at most 4; a hit needs term overlap on top of a same-cell match

STOP = set("""a an and are as at be been by can could do does for from has have if in into is it its may might more most
must no not of on or our per such than that the their them then there these they this those through to under up use used
using was we were what when where which while who will with within without would star stars data search searches survey
surveys signal signals sample samples per cent percent each other only also both any all one two three new""".split())


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9\-]{2,}", text.lower())
    return {w for w in words if w not in STOP}


def card_terms(card: dict) -> set[str]:
    parts = [card.get("title", ""), card.get("claim", ""), card.get("mechanism", ""), card.get("method", "")]
    parts += [a.get("name", "") for a in card.get("candidate_archives") or []]
    return _terms(" ".join(parts))


def entry_terms(e: dict) -> set[str]:
    parts = [e.get("name", ""), e.get("hypothesis", ""), e.get("method", ""), e.get("signature_class", ""),
             " ".join(e.get("data_used") or [])]
    return _terms(" ".join(parts))


def load_register() -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "register").glob("REG-*.yaml"))]


def register_fast_path(card: dict, register: list[dict] | None = None, k: int = TOP_K) -> list[dict]:
    """Top-k register entries for a card, with a transparent score.

    score = 2*[same signature_class] + 1*[same domain] + 1*[same observable] + 10*Jaccard(card terms, entry terms)
    """
    register = register if register is not None else load_register()
    ct = card_terms(card)
    hits = []
    for e in register:
        et = entry_terms(e)
        shared = ct & et
        jac = len(shared) / len(ct | et) if ct | et else 0.0
        tax = 2 * (e.get("signature_class") == card["signature_class"]) + (e.get("domain") == card["domain"]) \
            + (e.get("observable") == card["observable"])
        score = round(tax + 10 * jac, 2)
        hits.append({"register_id": e["id"], "score": score, "taxonomy": tax, "jaccard": round(jac, 3),
                     "shared_terms": sorted(shared)[:12], "outcome": e["outcome"],
                     "bibcodes": e["bibcodes"].get("values") or [],
                     "evidence": e["bibcodes"]["status"] == "resolved"})
    hits.sort(key=lambda h: (-h["score"], h["register_id"]))
    return hits[:k]


def log_gate(card_id: str, gate: str, verdict: str, payload: dict, by: str = "agent", prompt_version: str = "v0.1") -> None:
    GATE_LOGS.mkdir(parents=True, exist_ok=True)
    entry = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": "gate", "gate": gate,
             "verdict": verdict, "by": by, "prompt_version": prompt_version, **payload}
    with (GATE_LOGS / f"{card_id}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def g2_fast(card_ids: list[str], by: str, dry_run: bool) -> int:
    register = load_register()
    for cid in card_ids:
        card = yaml.safe_load((CARDS / f"{cid}.yaml").read_text(encoding="utf-8"))
        hits = register_fast_path(card, register)
        strong = [h for h in hits if h["score"] >= HIT_THRESHOLD and h["evidence"]]
        verdict = "register_hit" if strong else "no_register_hit"
        top = ", ".join(f"{h['register_id']} ({h['score']})" for h in hits[:3])
        print(f"{cid}: {verdict:16s} top: {top}")
        if not dry_run:
            log_gate(cid, "G2-register", verdict,
                     {"hits": hits, "threshold": HIT_THRESHOLD, "card_version": card.get("version", 1),
                      "note": "fast path only; novelty status is set by the ADS-backed G2 judge"},
                     by=by, prompt_version=FAST_PATH_VERSION)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="critique")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("g2-fast", help="G2 register fast path")
    g.add_argument("card_ids", nargs="*")
    g.add_argument("--all-raw", action="store_true")
    g.add_argument("--by", default="agent")
    g.add_argument("--dry-run", action="store_true")
    gate_cli.add_subparsers(sub)
    a = ap.parse_args(argv)
    if a.cmd == "g2-fast":
        ids = list(a.card_ids)
        if a.all_raw:
            ids += [p.stem for p in sorted(CARDS.glob("SIEVE-*.yaml"))
                    if yaml.safe_load(p.read_text(encoding="utf-8")).get("status") == "raw" and p.stem not in ids]
        if not ids:
            ap.error("give card ids or --all-raw")
        return g2_fast(ids, a.by, a.dry_run)
    if a.cmd in gate_cli.COMMANDS:
        return gate_cli.run(a, g2_fast=g2_fast)
    return 2


if __name__ == "__main__":
    sys.exit(main())
