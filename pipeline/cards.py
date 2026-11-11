"""Load, validate and list hypothesis cards and register entries.

Usage:
    uv run python -m pipeline.cards validate      # all cards + register entries + baseline cards against the schemas
    uv run python -m pipeline.cards list          # table of cards with status and scores (--baseline: baseline cards)
    uv run python -m pipeline.cards set-status SIEVE-0001 gated --reason "G1-G4 complete" --by human

Status transitions are only allowed through `set_status`, which writes a gate log entry.
Gate output reaches a card only through this module as well: `write_card` (validate, version bump, write) and
`append_gate_log` are what the gate runner uses; `set_novelty` (G2) and `set_physics` (G1) write one block each.

Two card sets share one schema and are kept apart by id prefix and directory:
  SIEVE-NNNN  catalogue/cards/            pipeline cards (Expand, human edits); gate logs in catalogue/gate_logs/
  BASE-NNNN   evaluation/baseline/cards/  literature baseline (evaluation/baseline/README.md); gate logs in
                                          evaluation/baseline/gate_logs/. Expand and the catalogue never read them.
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
BASELINE = ROOT / "evaluation" / "baseline"
BASELINE_CARDS = BASELINE / "cards"
BASELINE_GATE_LOGS = BASELINE / "gate_logs"
BASELINE_SOURCES = BASELINE / "sources.yaml"

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


def iter_baseline_cards():
    for p in sorted(BASELINE_CARDS.glob("BASE-*.yaml")):
        yield p, _load_yaml(p)


def card_paths(card_id: str) -> tuple[Path, Path]:
    """Card file and gate-log directory for an id; the prefix decides the card set."""
    if card_id.startswith("BASE-"):
        return BASELINE_CARDS / f"{card_id}.yaml", BASELINE_GATE_LOGS
    return CARDS / f"{card_id}.yaml", GATE_LOGS


def baseline_source_bibcodes() -> set[str] | None:
    """Bibcodes of included baseline sources (and their full-text twins); None if sources.yaml is absent."""
    if not BASELINE_SOURCES.exists():
        return None
    out = set()
    for s in (_load_yaml(BASELINE_SOURCES).get("sources") or []):
        if s.get("decision") == "included":
            out.add(s["bibcode"])
    return out


def _validate_baseline(card_v) -> tuple[int, int]:
    errors, n = 0, 0
    known = baseline_source_bibcodes()
    for p, doc in iter_baseline_cards():
        n += 1
        problems = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in sorted(card_v.iter_errors(doc), key=lambda e: list(e.path))]
        if doc.get("id") != p.stem:
            problems.append(f"id {doc.get('id')} does not match filename")
        prov = doc.get("provenance") or {}
        if prov.get("generator_model") != "human-literature":
            problems.append("provenance/generator_model must be 'human-literature' for baseline cards")
        if not prov.get("transcribed_by"):
            problems.append("provenance/transcribed_by missing")
        bibs = prov.get("source_bibcodes") or []
        if not bibs:
            problems.append("provenance/source_bibcodes missing")
        if known is not None:
            problems += [f"source bibcode {b} is not an included source in sources.yaml" for b in bibs if b not in known]
        if (doc.get("novelty") or {}).get("closest_prior") and doc.get("status") == "raw":
            problems.append("novelty/closest_prior must stay empty on raw baseline cards (gate G2 fills it)")
        for msg in problems:
            errors += 1
            print(f"BASELINE {p.name}: {msg}")
    # a card in the wrong directory would leak into Expand prompts or out of the baseline
    for stray in sorted(set(BASELINE_CARDS.glob("*.yaml")) - set(BASELINE_CARDS.glob("BASE-*.yaml"))):
        errors += 1
        print(f"BASELINE {stray.name}: only BASE-NNNN.yaml files belong in evaluation/baseline/cards/")
    for stray in sorted(set(CARDS.glob("*.yaml")) - set(CARDS.glob("SIEVE-*.yaml"))):
        errors += 1
        print(f"CARD {stray.name}: only SIEVE-NNNN.yaml files belong in catalogue/cards/")
    return errors, n


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
        if (doc.get("provenance") or {}).get("generator_model") == "human-literature":
            errors += 1
            print(f"CARD {p.name}: literature-baseline cards belong in evaluation/baseline/cards/ with a BASE id")
    for p, doc in iter_register():
        for err in sorted(reg_v.iter_errors(doc), key=lambda e: list(e.path)):
            errors += 1
            print(f"REGISTER {p.name}: {'/'.join(map(str, err.path))}: {err.message}")
        if doc.get("id") != p.stem:
            errors += 1
            print(f"REGISTER {p.name}: id {doc.get('id')} does not match filename")
    base_errors, n_base = _validate_baseline(card_v)
    errors += base_errors
    n_cards, n_reg = len(list(CARDS.glob("SIEVE-*.yaml"))), len(list(REGISTER.glob("REG-*.yaml")))
    print(f"{n_cards} cards, {n_reg} register entries, {n_base} baseline cards, {errors} errors")
    return 1 if errors else 0


def list_cards(baseline: bool = False) -> int:
    rows = []
    for _, c in (iter_baseline_cards() if baseline else iter_cards()):
        s = c.get("scores") or {}
        rows.append((c["id"], c["status"], c["domain"], c.get("novelty", {}).get("status", "-"), s.get("total", "-"), c["title"][:60]))
    w = [max(len(str(r[i])) for r in rows + [("id", "status", "domain", "novelty", "total", "title")]) for i in range(6)]
    hdr = ("id", "status", "domain", "novelty", "total", "title")
    print("  ".join(str(h).ljust(w[i]) for i, h in enumerate(hdr)))
    for r in rows:
        print("  ".join(str(v).ljust(w[i]) for i, v in enumerate(r)))
    return 0


def set_status(card_id: str, new_status: str, reason: str, by: str) -> int:
    path, gate_logs = card_paths(card_id)
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
    gate_logs.mkdir(parents=True, exist_ok=True)
    log = gate_logs / f"{card_id}.jsonl"
    entry = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": "status", "from": old, "to": new_status, "reason": reason, "by": by}
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    print(f"{card_id}: {old} -> {new_status} (logged)")
    return 0


def write_card(card: dict) -> list[str]:
    """Validate a changed card, bump its version and write it to its set's directory.

    The only way gate output enters a card file. Returns the schema errors; if there are any, nothing is written and
    the version is not bumped.
    """
    errors = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in _validator("card.schema.json").iter_errors(card)]
    if errors:
        return errors
    card["version"] = int(card.get("version", 1)) + 1
    path, _ = card_paths(card["id"])
    path.write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    return []


def append_gate_log(card_id: str, entry: dict) -> None:
    """Append one event to the card's gate log (catalogue or baseline, by id prefix)."""
    _, gate_logs = card_paths(card_id)
    gate_logs.mkdir(parents=True, exist_ok=True)
    with (gate_logs / f"{card_id}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def set_physics(card_id: str, physics: dict, by: str, gate_log: dict) -> int:
    """Write a G1 verdict into the card's `physics` block outside a gate run and log it.

    Used to backfill the block from an existing G1 gate-log event (`python -m pipeline.gates.g1 backfill`); a live G1
    run writes the same block through `write_card` and logs its usual `gate` event. Leaves `status` alone. The log
    event is `physics`, not `gate`, so that G1 runs are not counted twice.
    """
    path, _ = card_paths(card_id)
    if not path.exists():
        print(f"no such card: {card_id}")
        return 1
    card = _load_yaml(path)
    previous = card.get("physics")
    card["physics"] = physics
    errors = write_card(card)
    if errors:
        print(f"{card_id}: physics block refused: {errors[:3]}")
        return 1
    append_gate_log(card_id, {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": "physics",
                              "gate": "G1", "verdict": physics["verdict"], "by": by, "card_version": card["version"],
                              "previous_physics": previous, **gate_log})
    print(f"{card_id}: physics {(previous or {}).get('verdict')} -> {physics['verdict']} (logged)")
    return 0


def set_novelty(card_id: str, novelty: dict, by: str, gate_log: dict) -> int:
    """Write a G2 verdict into the card's `novelty` block and append the `G2` gate-log event.

    Called by pipeline/critique.py. Leaves `status` alone: a novelty verdict is evidence for the raw -> gated/parked
    decision, which still goes through `set_status`. The card is validated before it is written; an invalid novelty
    block (e.g. a malformed bibcode) is refused and nothing changes.
    """
    path = CARDS / f"{card_id}.yaml"
    if not path.exists():
        print(f"no such card: {card_id}")
        return 1
    card = _load_yaml(path)
    previous = card.get("novelty") or {"status": "unchecked"}
    card["novelty"] = novelty
    card["version"] = int(card.get("version", 1)) + 1
    errors = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in _validator("card.schema.json").iter_errors(card)]
    if errors:
        print(f"{card_id}: novelty block refused: {errors[:3]}")
        return 1
    path.write_text(yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    GATE_LOGS.mkdir(parents=True, exist_ok=True)
    entry = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": "gate", "gate": "G2",
             "verdict": novelty["status"], "by": by, "card_version": card["version"], "previous_novelty": previous,
             **gate_log}
    with (GATE_LOGS / f"{card_id}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"{card_id}: novelty {previous.get('status')} -> {novelty['status']} (logged)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sieve")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    ls = sub.add_parser("list")
    ls.add_argument("--baseline", action="store_true", help="list evaluation/baseline/cards instead of the catalogue")
    st = sub.add_parser("set-status")
    st.add_argument("card_id")
    st.add_argument("status", choices=sorted({s for v in ALLOWED_TRANSITIONS.values() for s in v} | set(ALLOWED_TRANSITIONS)))
    st.add_argument("--reason", required=True)
    st.add_argument("--by", default="agent")
    a = ap.parse_args(argv)
    if a.cmd == "validate":
        return validate()
    if a.cmd == "list":
        return list_cards(a.baseline)
    if a.cmd == "set-status":
        return set_status(a.card_id, a.status, a.reason, a.by)
    return 2


if __name__ == "__main__":
    sys.exit(main())
