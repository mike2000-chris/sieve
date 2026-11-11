"""Refine stage: one revision round for a repairable card, between Critique and Converge.

    uv run python -m pipeline.refine --eligible                        # trigger decision for every catalogue card
    uv run python -m pipeline.refine SIEVE-0006 --dry-run              # decision, prompt and cost estimate; no call
    uv run python -m pipeline.refine SIEVE-0006 --max-run-eur 1.0 --by "name (model)"

Design: paper change proposal `refine-stage-v0.2` (approved 2026-11-11).

Trigger (rule-based, `decide`): G1 `revise`; or G4 robustness <= 1 with named exclusion tests; or G3 `partial` with a
concrete remedy (the judge named a gap on at least one archive and gave an access plan). Never: a BASE card (the
literature baseline is compared on first-pass verdicts only), a card with `operator: refine` or one that already has
a refined copy (one round), G1 `fail`, G2 `done` (rejections, not repair notes), a card that has not been through all
four gates, or a card that is not `raw` or `gated`.

Operation: the reviser (prompts/refine-v0.1.md; its own prompt, neither generator nor critic) gets the card blind
(pipeline.cards.blind_card, and without earlier gate output: `physics`, `novelty`, `scores` and the confounders G4
appended) plus the latest G1, G3 and G4 findings from the gate log. It never sees G2 output, so no reference reaches
it. Its output becomes a new card with the next free SIEVE id, `provenance.operator: refine` and
`provenance.parent_card`; the original is parked through pipeline.cards.set_status with the reason
`refined as SIEVE-NNNN`. Both gate logs get a `refine` event. The new card is `raw` and has to pass G1-G4 again.

Guards in code, each of which rejects the output, writes no card and logs `refine_rejected` on the parent:
  taxonomy   domain, signature_class, observable and timescale must come back exactly as in the parent
  citations  no bibcode, DOI, arXiv number or author-year reference in any card field (CLAUDE.md rule 2)
  schema     the assembled card must validate against schema/card.schema.json
Detection language (CLAUDE.md rule 1) is forbidden by the prompt and reported as `language_flags`, as in the gates.

Budget (CLAUDE.md rule 6): before the call, the worst case (full output budget on the dearest listed model) is checked
against the monthly cap, the call limit and --max-run-eur. Every call, also a rejected or truncated one, leaves a
record in evaluation/costs/llm_runs.jsonl with `stage: refine`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field

import yaml

from pipeline import cards as cards_mod
from pipeline.cards import TAXONOMY_FIELDS
from pipeline.expand import COST_LOG, MODEL, ROOT, _eur, load_prompt, load_yaml, spent_this_month
from pipeline.gates.common import language_flags

PROMPT_VERSION = "refine-v0.1"
EFFORT = "high"
MAX_TOKENS = 24000
OPERATOR = "refine"
REFINABLE_STATUS = ("raw", "gated")
G4_ROBUSTNESS_TRIGGER = 1      # refine when robustness <= this and exclusion tests are named
G4_APPENDED = "[G4 excludable:"  # marker pipeline/gates/g4.py puts on the confounders it appends to a card

# Earlier gate output and bookkeeping inside the card; the reviser gets the findings as a separate block instead.
HIDDEN_FIELDS = ("physics", "novelty", "scores", "status", "anomaly_level", "parked_reason", "preregistration", "report")

_S = {"type": "string"}
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "claim", "mechanism", "data_requirements", "candidate_archives", "method", "confounders",
                 "null_result_value", "domain", "signature_class", "observable", "timescale", "changes",
                 "open_uncertainties"],
    "properties": {
        "title": _S, "claim": _S, "mechanism": _S, "method": _S, "null_result_value": _S,
        "data_requirements": {
            "type": "object",
            "additionalProperties": False,
            "required": ["measured_quantity", "wavelength_um", "spectral_resolution", "cadence", "depth", "sample"],
            "properties": {
                "measured_quantity": _S,
                "wavelength_um": {"type": "array", "items": {"type": "number"}},
                "spectral_resolution": _S, "cadence": _S, "depth": _S, "sample": _S,
            },
        },
        "candidate_archives": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["name", "access"],
                      "properties": {"name": _S, "access": _S}},
        },
        "confounders": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["name", "exclusion"],
                      "properties": {"name": _S, "exclusion": _S}},
        },
        "domain": _S, "signature_class": _S, "observable": _S, "timescale": _S,
        "changes": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["field", "action", "what_changed", "gate", "finding"],
                      "properties": {"field": _S, "action": {"enum": ["changed", "not_adopted"]}, "what_changed": _S,
                                     "gate": {"enum": ["G1", "G3", "G4", "none"]}, "finding": _S}},
        },
        "open_uncertainties": {"type": "array", "items": _S},
    },
}
CARD_FIELDS = ("title", "claim", "mechanism", "data_requirements", "candidate_archives", "method", "confounders",
               "null_result_value")

# References a model could only have written from memory (CLAUDE.md rule 2). Checked on the card fields of the output.
_NOT_AUTHORS = ("Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|June|July|August|"
                "September|October|November|December|Release|Since|Until|Before|After|In|By|From|Epoch|Cycle|Year")
_CITATION = re.compile(
    r"\b[12][0-9]{3}[A-Za-z&.]{2,9}[0-9.]{4,8}[A-Za-z0-9.]{1,6}[A-Z]\b"      # ADS bibcode
    r"|\barXiv\s*:?\s*[0-9]{4}\.[0-9]{4,5}\b"                               # arXiv number
    r"|\b10\.[0-9]{4,9}/[^\s\"']+"                                          # DOI
    r"|\bet al\.?"                                                          # author list
    r"|\b(?!(?:" + _NOT_AUTHORS + r")\b)[A-Z][a-z]+(?: (?:&|and) [A-Z][a-z]+)? \(?(?:19|20)[0-9]{2}[a-z]?\)",
)                                                                           # Name (2018), Name & Name 2018)


# --- gate findings -------------------------------------------------------------------------------------------------

def gate_events(card_id: str) -> list[dict]:
    _, gate_logs = cards_mod.card_paths(card_id)
    log = gate_logs / f"{card_id}.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_findings(card: dict, events: list[dict] | None = None) -> dict:
    """The latest G1, G3 and G4 results for a card: {"G1": {"ts", "prompt_version", "result"} | None, ...}.

    Source is the gate log (it holds the notes, gaps and exclusion tests; the card keeps only a summary). A G1 verdict
    that exists only in the card's `physics` block is used as a fallback.
    """
    events = gate_events(card["id"]) if events is None else events
    needs = {"G1": ("verdict", "checks"), "G3": ("verdict", "archives"), "G4": ("robustness", "confounders")}
    out: dict = {g: None for g in needs}
    for e in events:
        g = e.get("gate")
        r = e.get("result")
        if e.get("event") == "gate" and g in needs and isinstance(r, dict) and all(k in r for k in needs[g]):
            out[g] = {"ts": e.get("ts"), "prompt_version": e.get("prompt_version"), "model": e.get("model"), "result": r}
    ph = card.get("physics")
    if out["G1"] is None and ph:
        out["G1"] = {"ts": None, "prompt_version": (ph.get("judged") or {}).get("prompt_version"),
                     "model": (ph.get("judged") or {}).get("model"),
                     "result": {"verdict": ph["verdict"], "reason": ph.get("rationale", ""),
                                "checks": [{"check": k, "result": v, "note": ""} for k, v in (ph.get("checks") or {}).items()],
                                "revision_hint": " ".join(ph.get("revision_hints") or [])}}
    return out


# --- trigger rule --------------------------------------------------------------------------------------------------

@dataclass
class Decision:
    card_id: str
    eligible: bool
    triggers: list[str] = field(default_factory=list)   # which rule(s) fire
    blockers: list[str] = field(default_factory=list)   # why the card is not refined, whatever the triggers

    def line(self) -> str:
        if self.eligible:
            return f"{self.card_id}: refine  [{'; '.join(self.triggers)}]"
        why = "; ".join(self.blockers) if self.blockers else "no trigger: no gate finding asks for a repair"
        fired = f"  (triggers that fired: {'; '.join(self.triggers)})" if self.triggers and self.blockers else ""
        return f"{self.card_id}: no refine  [{why}]{fired}"


def _g3_remedy(g3: dict) -> bool:
    """`partial` comes with a concrete remedy when the judge named a gap on at least one archive and an access plan."""
    gaps = [a for a in g3.get("archives") or [] if (a.get("gap") or "").strip()]
    return bool(gaps) and bool([s for s in g3.get("access_plan") or [] if s.strip()])


def decide(card: dict, findings: dict, child_ids: tuple | list = ()) -> Decision:
    """The trigger rule of the Refine stage. Pure: card, its latest gate findings, ids of cards that name it as parent."""
    cid = card.get("id", "?")
    prov = card.get("provenance") or {}
    g1, g3, g4 = ((findings.get(g) or {}).get("result") for g in ("G1", "G3", "G4"))
    novelty = (card.get("novelty") or {}).get("status", "unchecked")
    blockers, triggers = [], []

    if cid.startswith("BASE-") or prov.get("generator_model") == "human-literature":
        blockers.append("baseline card: the literature baseline is never refined (compared on first-pass verdicts)")
    if prov.get("operator") == OPERATOR:
        blockers.append("already a refined card (operator: refine); one revision round only")
    if child_ids:
        blockers.append(f"already refined as {', '.join(child_ids)}")
    if card.get("status") not in REFINABLE_STATUS:
        blockers.append(f"status {card.get('status')}: only raw or gated cards are refined")
    missing = [g for g, r in (("G1", g1), ("G3", g3), ("G4", g4)) if r is None] + (["G2"] if novelty == "unchecked" else [])
    if missing:
        blockers.append(f"not through Critique yet: no {', '.join(sorted(missing))} verdict")
    if g1 and g1.get("verdict") == "fail":
        blockers.append("G1 fail: a rejection, not a repair note")
    if novelty == "done":
        blockers.append("G2 done: a rejection, not a repair note")

    if g1 and g1.get("verdict") == "revise":
        triggers.append("G1 revise")
    if g4 and g4.get("robustness") is not None and g4["robustness"] <= G4_ROBUSTNESS_TRIGGER:
        named = [c for c in g4.get("confounders") or [] if (c.get("exclusion_test") or "").strip()]
        if named:
            triggers.append(f"G4 robustness {g4['robustness']} with {len(named)} named exclusion tests")
    if g3 and g3.get("verdict") == "partial" and _g3_remedy(g3):
        triggers.append("G3 partial with a concrete remedy")
    return Decision(cid, eligible=bool(triggers) and not blockers, triggers=triggers, blockers=blockers)


def children_of(card_id: str) -> list[str]:
    return [c["id"] for _, c in cards_mod.iter_cards() if (c.get("provenance") or {}).get("parent_card") == card_id]


def decide_for(card_id: str) -> tuple[Decision, dict | None, dict]:
    card = cards_mod.load_card(card_id)
    if card is None:
        return Decision(card_id, False, blockers=["no such card"]), None, {}
    findings = latest_findings(card)
    return decide(card, findings, children_of(card_id)), card, findings


# --- reviser input -------------------------------------------------------------------------------------------------

def reviser_view(card: dict) -> dict:
    """The card as the reviser sees it: blind to its origin (pipeline.cards.blind_card), without earlier gate output
    and bookkeeping (HIDDEN_FIELDS) and without the confounders G4 appended, which arrive in the findings block."""
    view = {k: v for k, v in cards_mod.blind_card(card).items() if k not in HIDDEN_FIELDS}
    if view.get("confounders"):
        view["confounders"] = [c for c in view["confounders"] if G4_APPENDED not in (c.get("exclusion") or "")]
    if view.get("candidate_archives"):   # licence and volume_estimate are G3 output
        view["candidate_archives"] = [{"name": a["name"], "access": a["access"]} for a in view["candidate_archives"]]
    return view


def _dump(obj) -> str:
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=110).rstrip()


def findings_blocks(findings: dict) -> dict:
    """Prompt text per gate. Only what the design names: G1 verdict, reason, checks and revision hint; G3 verdict,
    reason and gaps; G4 robustness, confounders with exclusion tests, dominant confounder and required cross-matches."""
    none = "(this review has not been run)"
    g1, g3, g4 = ((findings.get(g) or {}).get("result") for g in ("G1", "G3", "G4"))
    out = {"g1_findings": none, "g3_findings": none, "g4_findings": none}
    if g1:
        out["g1_findings"] = _dump({
            "verdict": g1["verdict"], "reason": g1.get("reason", ""),
            "checks": [{"check": c["check"], "result": c["result"], "note": c.get("note", "")} for c in g1.get("checks") or []],
            "revision_hint": g1.get("revision_hint", "")})
    if g3:
        out["g3_findings"] = _dump({
            "verdict": g3["verdict"], "reason": g3.get("reason", ""),
            "gaps": [{"archive": a["name"], "provides": a.get("what_it_provides", ""), "gap": a.get("gap", "")}
                     for a in g3.get("archives") or []],
            "archive_side_access_possible": g3.get("archive_side")})   # the access plan restates the old method
    if g4:
        out["g4_findings"] = _dump({
            "robustness_0_to_3": g4["robustness"], "reason": g4.get("reason", ""),
            "dominant_confounder": g4.get("dominant_confounder", ""),
            "confounders": [{"name": c["name"], "how_it_mimics": c.get("how_it_mimics", ""),
                             "exclusion_test": c.get("exclusion_test", ""), "exclusion_data": c.get("exclusion_data", ""),
                             "excludable": c.get("excludable", "")} for c in g4.get("confounders") or []],
            "required_cross_matches": g4.get("required_cross_matches") or []})
    return out


def build_prompt(card: dict, findings: dict) -> str:
    return load_prompt(f"{PROMPT_VERSION}.md").format(card_yaml=_dump(reviser_view(card)), **findings_blocks(findings))


# --- guards on the output ------------------------------------------------------------------------------------------

def taxonomy_violations(parent: dict, revised: dict) -> list[str]:
    return [f"{f}: reviser returned {revised.get(f)!r}, parent has {parent.get(f)!r}"
            for f in TAXONOMY_FIELDS if revised.get(f) != parent.get(f)]


def citation_hits(revised: dict) -> list[str]:
    text = json.dumps({k: revised.get(k) for k in CARD_FIELDS}, ensure_ascii=False)
    return sorted({m.group(0) for m in _CITATION.finditer(text)})


def to_card(revised: dict, new_id: str, parent: dict, model: str) -> dict:
    """The new card. Taxonomy fields and the taxonomy cell are copied from the parent, never taken from the model."""
    dr = dict(revised["data_requirements"])
    if len(dr.get("wavelength_um") or []) != 2:
        dr.pop("wavelength_um", None)
    return {
        "id": new_id, "version": 1, "title": revised["title"][:160], "claim": revised["claim"],
        **{f: parent[f] for f in TAXONOMY_FIELDS},
        "mechanism": revised["mechanism"], "data_requirements": dr,
        "candidate_archives": revised["candidate_archives"], "method": revised["method"],
        "confounders": revised["confounders"], "novelty": {"status": "unchecked"},
        "null_result_value": revised["null_result_value"], "status": "raw",
        "anomaly_level": None, "parked_reason": None, "preregistration": None, "report": None,
        "provenance": {
            "generator_model": model, "prompt_version": PROMPT_VERSION, "operator": OPERATOR,
            "taxonomy_cell": (parent.get("provenance") or {}).get("taxonomy_cell"),
            "parent_card": parent["id"], "created": dt.date.today().isoformat(), "edited_by_human": False,
        },
    }


# --- budget and model call -----------------------------------------------------------------------------------------

def worst_case_eur(prompt: str, budget: dict) -> float:
    dearest = max(budget["llm"]["pricing"].values(), key=lambda p: p["output_usd_per_mtok"])  # a fallback may answer
    return _eur({"input_tokens": len(prompt) // 3, "output_tokens": MAX_TOKENS}, dearest)


def check_budget(prompt: str, run: dict) -> float:
    llm = run["budget"]["llm"]
    worst = worst_case_eur(prompt, run["budget"])
    if run["calls"] + 1 > llm["max_gate_calls_per_run"]:
        raise SystemExit(f"budget: call {run['calls'] + 1} > max_gate_calls_per_run {llm['max_gate_calls_per_run']}")
    month = spent_this_month()
    if month + worst > llm["max_eur"]:
        raise SystemExit(f"budget: spent {month:.2f} EUR + worst case {worst:.2f} EUR > monthly cap {llm['max_eur']} EUR")
    if run["spent"] + worst > run["cap"]:
        raise SystemExit(f"budget: run spent {run['spent']:.3f} EUR + worst case {worst:.3f} EUR for the next call "
                         f"> --max-run-eur {run['cap']:.2f}; stopping")
    return worst


def call_model(prompt: str):
    """One reviser call. Returns the final message; parsing and stop reasons are handled by the caller so that the
    cost record is written first."""
    import anthropic
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # as in expand.py: on a policy decline a fallback model answers; msg.model records which
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        return stream.get_final_message()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _cost_record(card_id: str, msg, usage: dict, cost: float, by: str, outcome: str, new_id: str | None) -> None:
    now = _now()
    rec = {"date": now.date().isoformat(), "ts": now.isoformat(timespec="seconds"), "stage": "refine", "card": card_id,
           "model": msg.model, "requested_model": MODEL, "effort": EFFORT, "prompt_version": PROMPT_VERSION, "by": by,
           "message_id": msg.id, "stop_reason": msg.stop_reason, "usage": usage, "cost_eur": round(cost, 4),
           "outcome": outcome, "card_written": new_id}
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def _reject(parent: dict, reasons: list[str], prov: dict, decision: Decision, extra: dict | None = None) -> dict:
    cards_mod.append_gate_log(parent["id"], {
        "ts": _now().isoformat(timespec="seconds"), "date": _now().date().isoformat(), "event": "refine_rejected",
        "reasons": reasons, "triggers": decision.triggers, "card_version": parent.get("version", 1), **prov,
        **(extra or {})})
    print(f"{parent['id']}: refine output rejected, no card written, original unchanged: {reasons[:3]}")
    return {"card_id": parent["id"], "outcome": "rejected", "reasons": reasons, "cost_eur": prov.get("cost_eur", 0.0)}


# --- one card ------------------------------------------------------------------------------------------------------

def refine_card(card_id: str, run: dict, dry_run: bool = False) -> dict:
    """Refine one card. Returns {"card_id", "outcome": skipped | dry-run | rejected | refined, ...}."""
    decision, card, findings = decide_for(card_id)
    print(decision.line())
    if not decision.eligible:
        return {"card_id": card_id, "outcome": "skipped", "decision": decision}
    prompt = build_prompt(card, findings)
    if dry_run:
        pricing = run["budget"]["llm"]["pricing"]
        print(prompt)
        print(f"\n[dry-run] refine {card_id}: {len(prompt)} chars; worst case {worst_case_eur(prompt, run['budget']):.3f} EUR "
              f"({MAX_TOKENS} output tokens on the dearest listed model), expected about "
              f"{_eur({'input_tokens': len(prompt) // 3, 'output_tokens': 9000}, pricing[MODEL]):.2f} EUR; "
              f"would write {cards_mod.next_card_id()} and park {card_id}; no call made, nothing written")
        return {"card_id": card_id, "outcome": "dry-run", "decision": decision}

    check_budget(prompt, run)
    msg = call_model(prompt)
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    pricing = run["budget"]["llm"]["pricing"]
    cost = _eur(usage, pricing.get(msg.model, max(pricing.values(), key=lambda p: p["output_usd_per_mtok"])))
    run["spent"] += cost
    run["calls"] += 1
    prov = {"by": run["by"], "model": msg.model, "requested_model": MODEL, "prompt_version": PROMPT_VERSION,
            "effort": EFFORT, "message_id": msg.id, "usage": usage, "cost_eur": round(cost, 4)}
    used = {g: {"ts": f["ts"], "prompt_version": f["prompt_version"]} for g, f in findings.items() if f}

    if msg.stop_reason in ("refusal", "max_tokens"):
        _cost_record(card_id, msg, usage, cost, run["by"], msg.stop_reason, None)
        return _reject(card, [f"model call ended with stop_reason {msg.stop_reason}"], prov, decision)
    revised = json.loads(next(b.text for b in msg.content if b.type == "text"))

    from jsonschema import Draft202012Validator
    reasons = [f"output schema: {'/'.join(map(str, e.path))}: {e.message}"
               for e in Draft202012Validator(OUTPUT_SCHEMA).iter_errors(revised)]
    if not reasons:
        reasons += [f"taxonomy changed: {v}" for v in taxonomy_violations(card, revised)]
        reasons += [f"citation in card text: {h!r}" for h in citation_hits(revised)]
    new_id = cards_mod.next_card_id()
    if not reasons:
        new_card = to_card(revised, new_id, card, msg.model)
        reasons += [f"card schema: {e}" for e in cards_mod.create_card(new_card)]   # validates, refuses to overwrite
    if reasons:
        _cost_record(card_id, msg, usage, cost, run["by"], "rejected", None)
        return _reject(card, reasons, prov, decision,
                       {"findings_used": used, "changes": revised.get("changes"), "language_flags": language_flags(revised)})

    flags = language_flags({k: revised[k] for k in CARD_FIELDS})
    now = _now()
    stamp = {"ts": now.isoformat(timespec="seconds"), "date": now.date().isoformat(), "event": "refine"}
    cards_mod.append_gate_log(new_id, {
        **stamp, "role": "refined_card", "parent_card": card_id, "parent_version": card.get("version", 1),
        "triggers": decision.triggers, "findings_used": used, "changes": revised["changes"],
        "open_uncertainties": revised["open_uncertainties"], "language_flags": flags, "card_version": 1, **prov})
    rc = cards_mod.set_status(card_id, "parked", f"refined as {new_id}", run["by"])   # writes the `status` event
    cards_mod.append_gate_log(card_id, {
        **stamp, "role": "parent", "refined_as": new_id, "triggers": decision.triggers, "findings_used": used,
        "n_changes": len(revised["changes"]), "parked": rc == 0, **prov})
    _cost_record(card_id, msg, usage, cost, run["by"], "refined", new_id)
    print(f"{card_id} -> {new_id}: {len(revised['changes'])} changes, {len(revised['open_uncertainties'])} open "
          f"uncertainties ({usage['input_tokens']} in / {usage['output_tokens']} out, {cost:.3f} EUR, {msg.model})"
          f"{'  language flags: ' + ', '.join(flags) if flags else ''}")
    print(f"next: uv run python -m pipeline.critique all {new_id} && uv run python -m pipeline.critique g2 {new_id}")
    return {"card_id": card_id, "outcome": "refined", "new_id": new_id, "cost_eur": cost, "decision": decision}


# --- command line --------------------------------------------------------------------------------------------------

def list_eligible() -> int:
    n = 0
    for _, card in cards_mod.iter_cards():   # catalogue only; baseline cards are never refined
        d = decide(card, latest_findings(card), children_of(card["id"]))
        n += d.eligible
        print(d.line())
    print(f"{n} eligible")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="refine", description="Refine stage: one revision round for a repairable card")
    ap.add_argument("card_ids", nargs="*")
    ap.add_argument("--eligible", action="store_true", help="list the trigger decision for every catalogue card; no call")
    ap.add_argument("--dry-run", action="store_true", help="print decision, prompt and cost estimate; no call, no write")
    ap.add_argument("--max-run-eur", type=float, default=1.0, help="stop before the call that could exceed this")
    ap.add_argument("--by", default="agent", help="who ran this (recorded in gate logs and the cost log)")
    a = ap.parse_args(argv)
    if a.eligible:
        return list_eligible()
    if not a.card_ids:
        ap.error("give card ids or --eligible")
    base = [c for c in a.card_ids if c.startswith("BASE-")]
    if base:   # refused before anything else, dry run included
        print(f"{', '.join(base)}: baseline cards are never refined; the pipeline-versus-baseline comparison uses "
              "first-pass verdicts only (evaluation/metrics.md)")
        return 1
    run = {"spent": 0.0, "calls": 0, "cap": a.max_run_eur, "budget": load_yaml("config/budget.yaml"), "by": a.by}
    results = [refine_card(cid, run, dry_run=a.dry_run) for cid in a.card_ids]
    if run["calls"]:
        print(f"run total: {run['calls']} calls, {run['spent']:.3f} EUR")
    return 1 if any(r["outcome"] in ("skipped", "rejected") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
