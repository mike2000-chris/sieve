"""Converge stage: portfolio selection under the constraints in config/budget.yaml.

Implemented: constraint-aware greedy selection over scored cards. Scoring itself (prompts/score-v0.2.md) is a Phase 0 task.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def select(cards: list[dict], budget: dict | None = None) -> list[dict]:
    budget = budget or yaml.safe_load((ROOT / "config" / "budget.yaml").read_text(encoding="utf-8"))
    pf = budget["portfolio"]
    scored = [c for c in cards if c.get("status") == "gated" and (c.get("scores") or {}).get("total") is not None]
    scored.sort(key=lambda c: c["scores"]["total"], reverse=True)
    chosen: list[dict] = []
    domains, confounders, ambitious = set(), set(), 0
    for c in scored:
        if len(chosen) >= pf["max_selected_cards_per_cycle"]:
            break
        dom = c["domain"]
        dc = (c.get("scores") or {}).get("dominant_confounder")
        amb = bool((c.get("scores") or {}).get("ambitious"))
        if dc and dc in confounders:
            continue
        if amb and ambitious >= pf["max_ambitious_cards"]:
            continue
        chosen.append(c)
        domains.add(dom)
        if dc:
            confounders.add(dc)
        ambitious += amb
    if len(chosen) >= pf["min_selected_cards_per_cycle"] and len(domains) < pf["min_domains_represented"]:
        # swap the lowest-scored card for the best card from an unrepresented domain
        for c in scored:
            if c["domain"] not in domains and c not in chosen:
                chosen[-1] = c
                break
    quick = sum(bool((c.get("scores") or {}).get("quick")) for c in chosen)
    if quick < pf["min_quick_cards"]:
        print("warning: portfolio has no quick card; review selection by hand")
    return chosen


if __name__ == "__main__":
    cards = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in (ROOT / "catalogue" / "cards").glob("SIEVE-*.yaml")]
    for c in select(cards):
        print(c["id"], c["scores"]["total"], c["title"])
