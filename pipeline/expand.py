"""Expand stage: walk the taxonomy grid, apply an operator, ask the model for cards, write raw cards.

Phase 0 task: implement for one taxonomy cell (10 cards) and inspect by hand. Skeleton only.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_taxonomy() -> dict:
    return yaml.safe_load((ROOT / "config" / "taxonomy.yaml").read_text(encoding="utf-8"))


def load_prompt(name: str) -> str:
    return (ROOT / "prompts" / name).read_text(encoding="utf-8")


def next_card_id() -> str:
    existing = sorted(p.stem for p in (ROOT / "catalogue" / "cards").glob("SIEVE-*.yaml"))
    n = int(existing[-1].split("-")[1]) + 1 if existing else 1
    return f"SIEVE-{n:04d}"


def build_prompt(cell: dict, operator: str, register_excerpt: str, archive_notes: str, n_cards: int = 10) -> str:
    tmpl = load_prompt("expand-v0.1.md")
    ops = {
        "cross_archive_transfer": "take a known signature and ask what it would look like in an archive where nobody has looked for it",
        "inversion": "search for a conspicuous absence rather than a presence",
        "population_statistics": "replace the single anomalous object with a distributional test over thousands of objects",
        "coincidence": "two independent, individually weak signatures on the same target or region",
        "earth_as_template": "use Earth observed as an exoplanet (the only positive case) to define the signature and its weakness",
        "negative_space": "generate what is adjacent to, but not covered by, the prior-search register",
        "cross_disciplinary_analogy": "apply anomaly and outbreak detection methods from ecology, epidemiology or finance to catalogue data",
        "pipeline_shadow": "ask which signal classes survey pipelines systematically discard and whether a signature hides there",
    }
    return tmpl.format(
        domain=cell["domain"], signature_class=cell["signature_class"], observable=cell["observable"],
        timescale=cell["timescale"], archive_family=cell["archive_family"], operator=operator,
        operator_definition=ops[operator], register_excerpt=register_excerpt, archive_notes=archive_notes,
        n_cards=n_cards,
    )


def run_cell(cell: dict, operator: str, n_cards: int = 10) -> list[dict]:
    """Call the model and return parsed cards. TODO(Phase 0): anthropic client, parse YAML, attach provenance, write files."""
    raise NotImplementedError("Phase 0 task: implement model call and card writing for one cell")


if __name__ == "__main__":
    tax = load_taxonomy()
    cell = {"domain": "technosignature", "signature_class": "thermal_waste_heat", "observable": "spectral_excess",
            "timescale": "snapshot", "archive_family": "spherex"}
    print(build_prompt(cell, "cross_archive_transfer", "(register excerpt)", "(archive notes)")[:1200])
