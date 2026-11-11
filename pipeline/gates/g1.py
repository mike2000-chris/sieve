"""Gate G1: physics plausibility (paper Section 4.3).

    uv run python -m pipeline.critique g1 SIEVE-0002 [--dry-run]

The critic redoes the order-of-magnitude estimate and judges observability. The card schema has no physics field, so G1
writes nothing into the card: verdict, estimate and revision hint live in the gate log (event `G1`).
"""
from __future__ import annotations

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


def _apply(card: dict, result: dict) -> list[str]:
    return []


G1 = Gate(name="G1", prompt_version=PROMPT_VERSION, schema=SCHEMA, build_vars=lambda card: {}, apply=_apply,
          verdict_of=lambda r: r["verdict"], fail_verdicts=("fail",))
