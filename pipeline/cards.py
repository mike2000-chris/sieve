"""Load, validate and list hypothesis cards and register entries.

Usage:
    uv run python -m pipeline.cards validate      # all cards + register entries against the schemas
    uv run python -m pipeline.cards list          # table of cards with status and scores
    uv run python -m pipeline.cards set-status SIEVE-0001 gated --reason "G1-G4 complete" --by human

Status transitions are only allowed through `set_status`, which writes a gate log entry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "catalogue" / "cards"
GATE_LOGS = ROOT / "catalogue" / "gate_logs"
REGISTER = ROOT / "register"
SCHEMAS = ROOT / "schema"

ALLOWED_TRANSITIONS = {
    "raw": {"gated", "parked"},
    "gated": {"parked", "selected"},
    "parked": {"gated", "selected"},
    "selected": {"preregistered", "parked"},
    "preregistered": {"executed"},
    "executed": {"reported"},
    "reported": set(),
}


def _normalize(obj):
    """PyYAML turns unquoted ISO dates into date objects; the schemas expect ISO strings."""
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    return obj


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return _normalize(yaml.safe_load(fh))


def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / name).read_text(encoding="utf-8")))


def iter_cards():
    for p in sorted(CARDS.glob("SIEVE-*.yaml")):
        yield p, _load_yaml(p)


def iter_register():
    for p in sorted(REGISTER.glob("REG-*.yaml")):
        yield p, _load_yaml(p)


def validate() -> int:
    errors = 0
    card_v, reg_v = _validator("card.schema.json"), _validator("register.schema.json")
    for p, doc in iter_cards():
        for err in sorted(card_v.iter_errors(doc), key=lambda e: list(e.path)):
            errors += 1
            print(f"CARD {p.name}: {'/'.join(map(str, err.path))}: {err.message}")
        if doc.get("id") != p.stem:
            errors += 1
            print(f"CARD {p.name}: id {doc.get('id')} does not match filename")
    for p, doc in iter_register():
        for err in sorted(reg_v.iter_errors(doc), key=lambda e: list(e.path)):
            errors += 1
            print(f"REGISTER {p.name}: {'/'.join(map(str, err.path))}: {err.message}")
        if doc.get("id") != p.stem:
            errors += 1
            print(f"REGISTER {p.name}: id {doc.get('id')} does not match filename")
    n_cards, n_reg = len(list(CARDS.glob("SIEVE-*.yaml"))), len(list(REGISTER.glob("REG-*.yaml")))
    print(f"{n_cards} cards, {n_reg} register entries, {errors} errors")
    return 1 if errors else 0


def list_cards() -> int:
    rows = []
    for _, c in iter_cards():
        s = c.get("scores") or {}
        rows.append((c["id"], c["status"], c["domain"], c.get("novelty", {}).get("status", "-"), s.get("total", "-"), c["title"][:60]))
    w = [max(len(str(r[i])) for r in rows + [("id", "status", "domain", "novelty", "total", "title")]) for i in range(6)]
    hdr = ("id", "status", "domain", "novelty", "total", "title")
    print("  ".join(str(h).ljust(w[i]) for i, h in enumerate(hdr)))
    for r in rows:
        print("  ".join(str(v).ljust(w[i]) for i, v in enumerate(r)))
    return 0


def set_status(card_id: str, new_status: str, reason: str, by: str) -> int:
    path = CARDS / f"{card_id}.yaml"
    if not path.exists():
        print(f"no such card: {card_id}")
        return 1
    card = _load_yaml(path)
    old = card["status"]
    if new_status not in ALLOWED_TRANSITIONS.get(old, set()):
        print(f"transition {old} -> {new_status} not allowed")
        return 1
    card["status"] = new_status
    card["version"] = int(card.get("version", 1)) + 1
    path.write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    GATE_LOGS.mkdir(parents=True, exist_ok=True)
    log = GATE_LOGS / f"{card_id}.jsonl"
    entry = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": "status", "from": old, "to": new_status, "reason": reason, "by": by}
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    print(f"{card_id}: {old} -> {new_status} (logged)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sieve")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("list")
    st = sub.add_parser("set-status")
    st.add_argument("card_id")
    st.add_argument("status", choices=sorted({s for v in ALLOWED_TRANSITIONS.values() for s in v} | set(ALLOWED_TRANSITIONS)))
    st.add_argument("--reason", required=True)
    st.add_argument("--by", default="agent")
    a = ap.parse_args(argv)
    if a.cmd == "validate":
        return validate()
    if a.cmd == "list":
        return list_cards()
    if a.cmd == "set-status":
        return set_status(a.card_id, a.status, a.reason, a.by)
    return 2


if __name__ == "__main__":
    sys.exit(main())
