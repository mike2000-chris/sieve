"""Critique stage: run gates G1-G4 on raw cards, append gate logs, update novelty/confounders fields.

Order: G2 fast path against the register first (cheap), then G1, G3, G4, then G2 against ADS/OpenAlex.
Skeleton only; see prompts/critique-g*-v0.1.md and tasks/PHASE0.md.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GATE_LOGS = ROOT / "catalogue" / "gate_logs"


def register_fast_path(card: dict) -> list[dict]:
    """Return register entries sharing domain and signature class with the card (candidate 'closest prior')."""
    hits = []
    for p in sorted((ROOT / "register").glob("REG-*.yaml")):
        e = yaml.safe_load(p.read_text(encoding="utf-8"))
        if e.get("domain") == card["domain"] and e.get("signature_class") == card["signature_class"]:
            hits.append({"register_id": e["id"], "name": e["name"], "outcome": e["outcome"], "lesson": e["lesson"]})
    return hits


def log_gate(card_id: str, gate: str, verdict: str, payload: dict, by: str = "agent", prompt_version: str = "v0.1") -> None:
    GATE_LOGS.mkdir(parents=True, exist_ok=True)
    entry = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": "gate", "gate": gate,
             "verdict": verdict, "by": by, "prompt_version": prompt_version, **payload}
    with (GATE_LOGS / f"{card_id}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    card = yaml.safe_load((ROOT / "catalogue" / "cards" / "SIEVE-0001.yaml").read_text(encoding="utf-8"))
    print(json.dumps(register_fast_path(card), indent=2))
