"""Shared machinery for the LLM gates: budget check, structured call, cost record, gate log, card write-back.

Follows the expand-v0.2 pattern (pipeline/expand.py): budget check before every call (CLAUDE.md rule 6), one record per
call in evaluation/costs/llm_runs.jsonl, schema-enforced JSON output. Card files and gate logs are written only through
pipeline.cards (`write_card`, `append_gate_log`). Status transitions are never made here; the optional `park` flag goes
through pipeline.cards.set_status.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

from pipeline import cards as cards_mod
from pipeline.expand import COST_LOG, MODEL, ROOT, _eur, load_prompt, load_yaml, spent_this_month

EFFORT = "high"
MAX_TOKENS = 16000
EST_OUT_TOKENS = 8000   # upper-bound planning figure for the pre-call budget check (thinking + JSON)

# Informational lint only (CLAUDE.md rule 1). The prompts forbid these words; hits are logged, not blocked.
_DETECTION_WORDS = re.compile(r"\b(detect(?:ion|ions|ed|s)?|discover(?:y|ies|ed)|biosignatures?)\b", re.I)


def load_card(card_id: str) -> dict:
    """Catalogue (SIEVE-NNNN) or baseline (BASE-NNNN) card; the id prefix decides the directory."""
    card = cards_mod.load_card(card_id)
    if card is None:
        raise SystemExit(f"no such card: {card_id}")
    return card


def judged_block(model: str, prompt_version: str, by: str) -> dict:
    """Provenance of one gate output as stored in the card (CLAUDE.md rule 7)."""
    return {"model": model, "prompt_version": prompt_version, "date": dt.date.today().isoformat(), "by": by}


def card_yaml(card: dict, drop: tuple = ()) -> str:
    """The card as the critic sees it: blind to its origin (pipeline.cards.blind_card removes id, provenance and
    version), without earlier gate output in `scores` and without the fields in `drop` (a gate's own earlier output)."""
    view = {k: v for k, v in cards_mod.blind_card(card).items() if k != "scores" and k not in drop}
    return yaml.safe_dump(view, sort_keys=False, allow_unicode=True, width=110).rstrip()


def language_flags(obj) -> list[str]:
    text = json.dumps(obj, ensure_ascii=False)
    return sorted({m.group(0).lower() for m in _DETECTION_WORDS.finditer(text)})


class RunBudget:
    """Per-process spending guard on top of the monthly cap in config/budget.yaml."""

    def __init__(self, max_eur: float | None = None):
        self.max_eur = max_eur
        self.spent_eur = 0.0
        self.calls = 0

    def check(self, prompt: str, model: str, budget: dict) -> float:
        llm = budget["llm"]
        est = _eur({"input_tokens": len(prompt) // 3, "output_tokens": EST_OUT_TOKENS}, llm["pricing"][model])
        if self.calls + 1 > llm["max_gate_calls_per_run"]:
            raise SystemExit(f"budget: {self.calls + 1} gate calls > max_gate_calls_per_run {llm['max_gate_calls_per_run']}")
        month = spent_this_month()
        if month + est > llm["max_eur"]:
            raise SystemExit(f"budget: spent {month:.2f} + estimate {est:.2f} EUR > monthly cap {llm['max_eur']} EUR")
        if self.max_eur is not None and self.spent_eur + est > self.max_eur:
            raise SystemExit(f"budget: run spent {self.spent_eur:.3f} + estimate {est:.3f} EUR > --max-eur {self.max_eur}")
        return est


def call_llm(prompt: str, schema: dict, model: str, effort: str = EFFORT):
    import anthropic

    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=model,
        max_tokens=MAX_TOKENS,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise SystemExit(f"model refused: {getattr(msg, 'stop_details', None)}")
    if msg.stop_reason == "max_tokens":
        raise SystemExit("output truncated at max_tokens")
    return json.loads(next(b.text for b in msg.content if b.type == "text")), msg


def validate_output(result: dict, schema: dict) -> list[str]:
    from jsonschema import Draft202012Validator
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in Draft202012Validator(schema).iter_errors(result)]


def log_gate(card: dict, gate: str, verdict: str, result: dict, *, by: str, prompt_version: str, model: str,
             cost_eur: float, usage: dict, extra: dict | None = None) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    entry = {"ts": now.isoformat(timespec="seconds"), "date": now.date().isoformat(), "event": "gate", "gate": gate,
             "verdict": verdict, "by": by, "model": model, "prompt_version": prompt_version,
             "card_version": card.get("version", 1), "cost_eur": round(cost_eur, 4), "usage": usage,
             "language_flags": language_flags(result), "result": result, **(extra or {})}
    cards_mod.append_gate_log(card["id"], entry)


def append_cost_record(gate: str, card: dict, prompt_version: str, model: str, requested: str, msg, usage: dict,
                       cost: float, by: str) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    rec = {"date": now.date().isoformat(), "ts": now.isoformat(timespec="seconds"), "stage": f"critique-{gate.lower()}",
           "card": card["id"], "model": model, "requested_model": requested, "effort": EFFORT,
           "prompt_version": prompt_version, "by": by, "message_id": msg.id, "usage": usage, "cost_eur": round(cost, 4)}
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


@dataclass
class Gate:
    """One gate = prompt file + output schema + how to build prompt variables + how to write back."""
    name: str                 # "G1"
    prompt_version: str       # "critique-g1-physics-v0.2"
    schema: dict
    build_vars: object        # (card) -> dict of prompt placeholders besides card_yaml
    apply: object             # (card, result, judged) -> list of card fields written (empty: card unchanged)
    verdict_of: object        # (result) -> str
    fail_verdicts: tuple = ()
    precheck: object = None   # optional (card) -> dict | None; a non-None return short-circuits the LLM call
    own_fields: tuple = ()    # card fields holding this gate's earlier output; hidden from its own prompt


def build_prompt(gate: Gate, card: dict) -> str:
    return load_prompt(f"{gate.prompt_version}.md").format(card_yaml=card_yaml(card, gate.own_fields),
                                                           **gate.build_vars(card))


def run_gate(gate: Gate, card_id: str, *, by: str, model: str = MODEL, dry_run: bool = False,
             budget: RunBudget | None = None, park: bool = False) -> dict:
    """Run one gate on one card. Returns {"verdict", "cost_eur", "fields", ...}."""
    budget = budget or RunBudget()
    card = load_card(card_id)
    bud = load_yaml("config/budget.yaml")
    pre = gate.precheck(card) if gate.precheck else None
    if pre is not None:  # deterministic short-circuit, no LLM call
        print(f"{card_id} {gate.name}: pre-check short-circuit: {pre['reason']}")
        if not dry_run:
            log_gate(card, gate.name, pre["verdict"], pre, by=by, prompt_version=gate.prompt_version + "+precheck",
                     model="none", cost_eur=0.0, usage={})
        return {"verdict": pre["verdict"], "cost_eur": 0.0, "fields": []}
    prompt = build_prompt(gate, card)
    if dry_run:
        print(prompt)
        est = _eur({"input_tokens": len(prompt) // 3, "output_tokens": EST_OUT_TOKENS}, bud["llm"]["pricing"][model])
        print(f"\n[dry-run] {gate.name} {card_id}: {len(prompt)} chars, estimated cost <= {est:.3f} EUR, no call made")
        return {"verdict": "dry-run", "cost_eur": 0.0, "fields": []}
    budget.check(prompt, model, bud)
    result, msg = call_llm(prompt, gate.schema, model)
    errs = validate_output(result, gate.schema)
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    cost = _eur(usage, bud["llm"]["pricing"].get(msg.model, bud["llm"]["pricing"][model]))
    budget.spent_eur += cost
    budget.calls += 1
    append_cost_record(gate.name, card, gate.prompt_version, msg.model, model, msg, usage, cost, by)
    if errs:
        print(f"{card_id} {gate.name}: output failed validation, card not changed: {errs[:3]}")
        log_gate(card, gate.name, "invalid_output", {"errors": errs[:5]}, by=by, prompt_version=gate.prompt_version,
                 model=msg.model, cost_eur=cost, usage=usage)
        return {"verdict": "invalid_output", "cost_eur": cost, "fields": []}
    verdict = gate.verdict_of(result)
    fields = gate.apply(card, result, judged_block(msg.model, gate.prompt_version, by))
    extra = {"card_fields_written": fields}
    if fields:
        write_errors = cards_mod.write_card(card)   # validates, bumps the version, writes
        if write_errors:
            print(f"{card_id} {gate.name}: card write refused, verdict is in the gate log only: {write_errors[:3]}")
            extra = {"card_fields_written": [], "card_write_refused": write_errors[:5]}
            fields = []
    log_gate(card, gate.name, verdict, result, by=by, prompt_version=gate.prompt_version, model=msg.model,
             cost_eur=cost, usage=usage, extra=extra)
    flags = language_flags(result)
    print(f"{card_id} {gate.name}: {verdict}  ({usage['input_tokens']} in / {usage['output_tokens']} out, "
          f"{cost:.3f} EUR, {msg.model}){'  language flags: ' + ', '.join(flags) if flags else ''}")
    if park and verdict in gate.fail_verdicts:
        cards_mod.set_status(card_id, "parked", f"{gate.name} verdict {verdict}: {result.get('reason', '')[:200]}", by)
    return {"verdict": verdict, "cost_eur": cost, "fields": fields, "result": result}
