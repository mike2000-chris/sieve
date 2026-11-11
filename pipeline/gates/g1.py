"""Gate G1: physics plausibility (paper Section 4.3).

    uv run python -m pipeline.critique g1 SIEVE-0002 [--dry-run]
    uv run python -m pipeline.gates.g1 backfill SIEVE-0002 SIEVE-0006 --by "name (model)"

The critic redoes the order-of-magnitude estimate and judges observability. G1 writes the card's `physics` block
(verdict, rationale, result per check, revision hints, provenance) through pipeline/cards.py; the full result with the
arithmetic and the estimate stays in the gate log (event `gate`, gate `G1`).

`backfill` fills the `physics` block of cards that were judged before the block existed. It copies the latest G1
gate-log event that carries a result; it makes no model call and adds a `physics` event to the gate log that points
at the source event.
"""
from __future__ import annotations

import argparse
import json
import sys

from pipeline import cards as cards_mod
from pipeline.gates.common import Gate

PROMPT_VERSION = "critique-g1-physics-v0.2"
_S = {"type": "string"}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "reason", "checks", "estimate", "revision_hint"],
    "properties": {
        "verdict": {"enum": ["pass", "revise", "fail"]},
        "reason": _S,
        "checks": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False, "required": ["check", "result", "note"],
                "properties": {"check": {"enum": ["energy_budget", "observability", "internal_consistency", "forbidden_physics"]},
                               "result": {"enum": ["ok", "concern", "fail", "uncertain"]}, "note": _S},
            },
        },
        "estimate": {
            "type": "object", "additionalProperties": False,
            "required": ["pattern_size", "noise_floor", "sample_needed", "assumptions"],
            "properties": {"pattern_size": _S, "noise_floor": _S, "sample_needed": _S, "assumptions": _S},
        },
        "revision_hint": _S,
    },
}


def physics_block(result: dict, judged: dict) -> dict:
    """The card's `physics` block from a G1 result. The prompt returns one hint; the card keeps a list so that a
    human or a later prompt version can add more."""
    hint = (result.get("revision_hint") or "").strip()
    return {"verdict": result["verdict"], "rationale": result["reason"].strip(),
            "checks": {c["check"]: c["result"] for c in result["checks"]},
            "revision_hints": [hint] if hint else [],
            "judged": judged, "audited_by_human": False}


def _apply(card: dict, result: dict, judged: dict) -> list[str]:
    card["physics"] = physics_block(result, judged)
    return ["physics"]


G1 = Gate(name="G1", prompt_version=PROMPT_VERSION, schema=SCHEMA, build_vars=lambda card: {}, apply=_apply,
          verdict_of=lambda r: r["verdict"], fail_verdicts=("fail",), own_fields=("physics",))


def latest_g1_event(card_id: str) -> dict | None:
    _, gate_logs = cards_mod.card_paths(card_id)
    log = gate_logs / f"{card_id}.jsonl"
    if not log.exists():
        return None
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    hits = [e for e in events if e.get("event") == "gate" and e.get("gate") == "G1"
            and isinstance(e.get("result"), dict) and "verdict" in e["result"] and "checks" in e["result"]]
    return hits[-1] if hits else None


def backfill(card_ids: list[str], by: str) -> int:
    rc = 0
    for cid in card_ids:
        ev = latest_g1_event(cid)
        if ev is None:
            print(f"{cid}: no G1 gate-log event with a result; nothing to backfill")
            rc = 1
            continue
        # provenance is that of the original judgement, not of the backfill
        judged = {"model": ev["model"], "prompt_version": ev["prompt_version"], "date": ev.get("date") or ev["ts"][:10],
                  "by": ev["by"]}
        rc |= cards_mod.set_physics(cid, physics_block(ev["result"], judged), by,
                                    {"action": "backfill", "source_event_ts": ev["ts"],
                                     "source_card_version": ev.get("card_version"),
                                     "note": "physics block copied from the existing G1 gate-log event; no model call"})
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="g1")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backfill", help="fill the physics block from the latest G1 gate-log event (no model call)")
    b.add_argument("card_ids", nargs="+")
    b.add_argument("--by", default="agent")
    a = ap.parse_args(argv)
    return backfill(a.card_ids, a.by)


if __name__ == "__main__":
    sys.exit(main())
