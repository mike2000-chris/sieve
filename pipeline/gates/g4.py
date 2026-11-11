"""Gate G4: confounders and artefacts (paper Section 4.3).

    uv run python -m pipeline.critique g4 SIEVE-0002 [--dry-run]

The prompt carries the `confounders_found` lists of the register entries nearest to the card (same taxonomy score as the
Expand excerpt). Entries withheld for the rediscovery test are included: like G2, G4 is a critique oracle, not the
generator, and the withholding only applies to what Expand sees (owner decision 2026-11-11). The judge returns an adversarial confounder
list with exclusion tests and a 0-3 robustness. Writes: new confounders appended to `card.confounders` (existing ones
kept), `scores.confounder_robustness`, and `scores.scored_by` (llm, or both if a human scored before). `scores.total` is
not touched; the Converge stage owns it.
"""
from __future__ import annotations

import yaml

from pipeline.expand import ROOT
from pipeline.gates.common import Gate

PROMPT_VERSION = "critique-g4-confounders-v0.2"
_S = {"type": "string"}
MAX_ENTRIES = 8


def register_confounders(card: dict, limit: int = MAX_ENTRIES) -> str:
    rows = []
    for p in sorted((ROOT / "register").glob("REG-*.yaml")):
        e = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not e.get("confounders_found"):
            continue
        score = 2 * (e.get("signature_class") == card["signature_class"]) + (e.get("domain") == card["domain"]) \
            + (e.get("observable") == card["observable"])
        if score >= 2:
            rows.append((score, e))
    rows.sort(key=lambda r: (-r[0], r[1]["id"]))
    lines = [f"  - {e['name']} ({e['id']}): {'; '.join(e['confounders_found'])}" for _, e in rows[:limit]]
    return "\n".join(lines) or "  (no register entry with recorded confounders near this card)"


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["confounders", "dominant_confounder", "robustness", "required_cross_matches", "reason"],
    "properties": {
        "confounders": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["name", "how_it_mimics", "exclusion_test", "exclusion_data", "excludable"],
                      "properties": {"name": _S, "how_it_mimics": _S, "exclusion_test": _S, "exclusion_data": _S,
                                     "excludable": {"enum": ["yes", "partly", "no"]}}},
        },
        "dominant_confounder": _S,
        "robustness": {"enum": [0, 1, 2, 3]},
        "required_cross_matches": {"type": "array", "items": _S},
        "reason": _S,
    },
}


def _apply(card: dict, result: dict) -> list[str]:
    written = []
    existing = {c["name"].strip().lower() for c in card.get("confounders") or []}
    for c in result["confounders"]:
        if c["name"].strip().lower() in existing:
            continue
        card.setdefault("confounders", []).append({
            "name": c["name"],
            "exclusion": f"{c['exclusion_test']} Data: {c['exclusion_data']} [G4 excludable: {c['excludable']}]"})
        existing.add(c["name"].strip().lower())
        written.append(f"confounders[{c['name']}]")
    sc = card.setdefault("scores", {})
    sc["confounder_robustness"] = result["robustness"]
    sc["scored_by"] = "both" if sc.get("scored_by") in ("human", "both") else "llm"
    written.append("scores.confounder_robustness")
    return written


G4 = Gate(name="G4", prompt_version=PROMPT_VERSION, schema=SCHEMA,
          build_vars=lambda card: {"register_confounders": register_confounders(card)}, apply=_apply,
          verdict_of=lambda r: f"robustness_{r['robustness']}")
