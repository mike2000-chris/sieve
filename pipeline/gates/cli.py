"""Command-line glue for the LLM gates, registered into pipeline/critique.py's argparse.

    uv run python -m pipeline.critique g1 SIEVE-0002 SIEVE-0006 [--dry-run] [--max-eur 1.0]
    uv run python -m pipeline.critique g3 --all-raw
    uv run python -m pipeline.critique g4 SIEVE-0002
    uv run python -m pipeline.critique all SIEVE-0002      # G2-fast -> G1 -> G3 -> G4

`--dry-run` prints the prompt and a cost estimate without calling the API. `--park` moves a card to `parked` through
pipeline.cards.set_status when G1 says fail or G3 says needs_observations/proprietary (default: verdicts are only logged).
`all` stops a card after a G1 `fail` unless `--continue-on-fail`. The ADS-backed G2 judge is not part of `all` yet.
"""
from __future__ import annotations

from pipeline import cards as cards_mod
from pipeline.expand import MODEL
from pipeline.gates.common import RunBudget, run_gate
from pipeline.gates.g1 import G1
from pipeline.gates.g3 import G3
from pipeline.gates.g4 import G4

GATES = {"g1": G1, "g3": G3, "g4": G4}
COMMANDS = set(GATES) | {"all"}


def add_subparsers(sub) -> None:
    for name in [*GATES, "all"]:
        p = sub.add_parser(name, help="run gates G1, G3 and G4 (then stop)" if name == "all" else f"run gate {name.upper()}")
        p.add_argument("card_ids", nargs="*")
        p.add_argument("--all-raw", action="store_true")
        p.add_argument("--by", default="agent")
        p.add_argument("--model", default=MODEL)
        p.add_argument("--max-eur", type=float, default=None, help="hard cap for this invocation, on top of config/budget.yaml")
        p.add_argument("--park", action="store_true")
        p.add_argument("--dry-run", action="store_true")
        if name == "all":
            p.add_argument("--continue-on-fail", action="store_true")


def _ids(a) -> list[str]:
    ids = list(a.card_ids)
    if a.all_raw:
        ids += [c["id"] for _, c in cards_mod.iter_cards() if c["status"] == "raw" and c["id"] not in ids]
    return ids


def run(a, g2_fast=None) -> int:
    ids = _ids(a)
    if not ids:
        raise SystemExit("give card ids or --all-raw")
    budget = RunBudget(a.max_eur)
    for cid in ids:
        if a.cmd != "all":
            run_gate(GATES[a.cmd], cid, by=a.by, model=a.model, dry_run=a.dry_run, budget=budget, park=a.park)
            continue
        if g2_fast is not None:
            g2_fast([cid], a.by, a.dry_run)
        for key in ("g1", "g3", "g4"):
            out = run_gate(GATES[key], cid, by=a.by, model=a.model, dry_run=a.dry_run, budget=budget, park=a.park)
            if out["verdict"] == "fail" and not a.continue_on_fail:
                print(f"{cid}: stopping after G1 fail (use --continue-on-fail to run the rest)")
                break
    if not a.dry_run and budget.calls:
        print(f"run total: {budget.calls} calls, {budget.spent_eur:.3f} EUR")
    return 0
