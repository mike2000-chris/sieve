"""Expand stage: fill one taxonomy cell with raw cards using one generative operator.

    uv run python -m pipeline.expand --dry-run                                 # print prompt + cost estimate, no call
    uv run python -m pipeline.expand --domain technosignature --signature-class thermal_waste_heat \
        --observable spectral_excess --timescale snapshot --archive-family spherex \
        --operator cross_archive_transfer --n 10

Every run checks the caps in config/budget.yaml before calling the model (CLAUDE.md rule 6), validates each card
against schema/card.schema.json, writes valid cards as `status: raw`, and appends a run record (tokens, cost,
model, prompt version, operator) to evaluation/costs/llm_runs.jsonl. Register entries withheld for the rediscovery
test never reach the prompt (evaluation/metrics.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "catalogue" / "cards"
COST_LOG = ROOT / "evaluation" / "costs" / "llm_runs.jsonl"
PROMPT_VERSION = "expand-v0.2"
MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 64000
MAX_TOP_UPS = 2

OPERATORS = {
    "cross_archive_transfer": "take a known signature and ask what it would look like in an archive where nobody has looked for it",
    "inversion": "search for a conspicuous absence rather than a presence",
    "population_statistics": "replace the single anomalous object with a distributional test over thousands of objects",
    "coincidence": "two independent, individually weak signatures on the same target or region",
    "earth_as_template": "use Earth observed as an exoplanet (the only positive case) to define the signature and its weakness",
    "negative_space": "generate what is adjacent to, but not covered by, the prior-search register",
    "cross_disciplinary_analogy": "apply anomaly and outbreak detection methods from ecology, epidemiology or finance to catalogue data",
    "pipeline_shadow": "ask which signal classes survey pipelines systematically discard and whether a signature hides there",
}

# JSON schema for the model's output (structured outputs). The pipeline adds id, status, taxonomy fields, provenance.
_STR = {"type": "string"}
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cards"],
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "claim", "mechanism", "data_requirements", "candidate_archives", "method",
                             "confounders", "null_result_value"],
                "properties": {
                    "title": _STR, "claim": _STR, "mechanism": _STR, "method": _STR, "null_result_value": _STR,
                    "data_requirements": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["measured_quantity", "wavelength_um", "spectral_resolution", "cadence", "depth", "sample"],
                        "properties": {
                            "measured_quantity": _STR,
                            "wavelength_um": {"type": "array", "items": {"type": "number"}},
                            "spectral_resolution": _STR, "cadence": _STR, "depth": _STR, "sample": _STR,
                        },
                    },
                    "candidate_archives": {
                        "type": "array",
                        "items": {"type": "object", "additionalProperties": False, "required": ["name", "access"],
                                  "properties": {"name": _STR, "access": _STR}},
                    },
                    "confounders": {
                        "type": "array",
                        "items": {"type": "object", "additionalProperties": False, "required": ["name", "exclusion"],
                                  "properties": {"name": _STR, "exclusion": _STR}},
                    },
                },
            },
        }
    },
}


def load_yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def load_prompt(name: str) -> str:
    text = (ROOT / "prompts" / name).read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[1] if "\n---\n" in text else text  # drop the changelog header


def next_card_number() -> int:
    existing = sorted(int(p.stem.split("-")[1]) for p in CARDS.glob("SIEVE-*.yaml"))
    return existing[-1] + 1 if existing else 1


def register_excerpt(cell: dict, limit: int = 12) -> tuple[str, list[str]]:
    """Register entries closest to the cell, never those withheld for the rediscovery test."""
    rows = []
    for p in sorted((ROOT / "register").glob("REG-*.yaml")):
        e = yaml.safe_load(p.read_text(encoding="utf-8"))
        if e.get("withheld_for_rediscovery_test"):
            continue
        score = 2 * (e.get("signature_class") == cell["signature_class"]) + (e.get("domain") == cell["domain"]) \
            + (e.get("observable") == cell["observable"])
        if score:
            rows.append((score, e))
    rows.sort(key=lambda r: (-r[0], r[1]["id"]))
    if sum(s >= 2 for s, _ in rows) >= 3:  # domain-only matches only when the cell is sparsely covered
        rows = [r for r in rows if r[0] >= 2]
    lines, ids = [], []
    for _, e in rows[:limit]:
        ids.append(e["id"])
        lines.append(f"  - {e['name']} ({e['year']}): tested '{e['hypothesis']}' with {', '.join(e['data_used'])}; "
                     f"outcome {e['outcome']}. Lesson: {e['lesson']}")
    return ("\n".join(lines) or "  (no non-withheld entries near this cell)"), ids


def archive_notes(family: str) -> str:
    for a in load_yaml("config/archives.yaml")["archives"]:
        if a["key"] == family:
            st = a.get("smoke_test") or {}
            parts = [a["name"], f"content: {a['content']}", f"scale: {a['scale']}"]
            if st.get("access_path"):
                parts.append(f"tested access path: {st['access_path']}")
            if st.get("caveat"):
                parts.append(f"caveat: {st['caveat']}")
            return "; ".join(parts)
    return f"(no entry for '{family}' in config/archives.yaml)"


def existing_titles(cell: dict) -> list[str]:
    key = "/".join(cell[k] for k in ("domain", "signature_class", "observable", "timescale", "archive_family"))
    out = []
    for p in sorted(CARDS.glob("SIEVE-*.yaml")):
        c = yaml.safe_load(p.read_text(encoding="utf-8"))
        if (c.get("provenance") or {}).get("taxonomy_cell") == key:
            out.append(c["title"])
    return out


def build_prompt(cell: dict, operator: str, n_cards: int) -> tuple[str, list[str]]:
    excerpt, ids = register_excerpt(cell)
    titles = existing_titles(cell)
    if titles:
        excerpt += "\n- Cards already in the SIEVE catalogue for this cell (do not repeat or paraphrase them):\n" + \
            "\n".join(f"  - {t}" for t in titles)
    text = load_prompt(f"{PROMPT_VERSION}.md").format(
        **cell, operator=operator, operator_definition=OPERATORS[operator], register_excerpt=excerpt,
        archive_notes=archive_notes(cell["archive_family"]), n_cards=n_cards)
    return text, ids


# --- budget -----------------------------------------------------------------------------------------------------

def _eur(usage: dict, pricing: dict) -> float:
    usd = (usage.get("input_tokens", 0) * pricing["input_usd_per_mtok"]
           + usage.get("output_tokens", 0) * pricing["output_usd_per_mtok"]) / 1e6
    return usd * pricing["eur_per_usd"]


def spent_this_month() -> float:
    if not COST_LOG.exists():
        return 0.0
    month = dt.date.today().strftime("%Y-%m")
    return sum(r.get("cost_eur", 0.0) for r in map(json.loads, COST_LOG.read_text().splitlines())
               if r.get("date", "").startswith(month))


def check_budget(n_cards: int, est_eur: float, budget: dict) -> None:
    llm = budget["llm"]
    if n_cards > llm["max_cards_per_expand_run"]:
        raise SystemExit(f"budget: {n_cards} cards > max_cards_per_expand_run {llm['max_cards_per_expand_run']}")
    spent = spent_this_month()
    if spent + est_eur > llm["max_eur"]:
        raise SystemExit(f"budget: spent {spent:.2f} EUR + estimate {est_eur:.2f} EUR > monthly cap {llm['max_eur']} EUR")
    print(f"budget ok: spent {spent:.2f} EUR this month, run estimate <= {est_eur:.2f} EUR, cap {llm['max_eur']} EUR")


# --- model call ---------------------------------------------------------------------------------------------------

def call_model(prompt: str):
    import anthropic

    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # on a policy decline the API re-runs on a fallback model; response.model records which
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise SystemExit(f"model refused: {getattr(msg, 'stop_details', None)}")
    if msg.stop_reason == "max_tokens":
        raise SystemExit("output truncated at max_tokens; lower --n")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)["cards"], msg


def to_card(raw: dict, number: int, cell: dict, operator: str, model: str) -> dict:
    dr = dict(raw["data_requirements"])
    if len(dr.get("wavelength_um") or []) != 2:
        dr.pop("wavelength_um", None)
    return {
        "id": f"SIEVE-{number:04d}", "version": 1, "title": raw["title"][:160], "claim": raw["claim"],
        "domain": cell["domain"], "signature_class": cell["signature_class"], "observable": cell["observable"],
        "timescale": cell["timescale"], "mechanism": raw["mechanism"], "data_requirements": dr,
        "candidate_archives": raw["candidate_archives"], "method": raw["method"], "confounders": raw["confounders"],
        "novelty": {"status": "unchecked"}, "null_result_value": raw["null_result_value"], "status": "raw",
        "anomaly_level": None, "parked_reason": None, "preregistration": None, "report": None,
        "provenance": {
            "generator_model": model, "prompt_version": PROMPT_VERSION, "operator": operator,
            "taxonomy_cell": "/".join(cell[k] for k in ("domain", "signature_class", "observable", "timescale", "archive_family")),
            "parent_card": None, "created": dt.date.today().isoformat(), "edited_by_human": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    tax = load_yaml("config/taxonomy.yaml")
    ap = argparse.ArgumentParser(prog="expand")
    ap.add_argument("--domain", default="technosignature", choices=tax["domains"])
    ap.add_argument("--signature-class", default="thermal_waste_heat", choices=tax["signature_classes"])
    ap.add_argument("--observable", default="spectral_excess", choices=tax["observables"])
    ap.add_argument("--timescale", default="snapshot", choices=tax["timescales"])
    ap.add_argument("--archive-family", default="spherex", choices=tax["archive_families"])
    ap.add_argument("--operator", default="cross_archive_transfer", choices=sorted(OPERATORS))
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--by", default="agent", help="who ran this (recorded in the run log)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    cell = {"domain": a.domain, "signature_class": a.signature_class, "observable": a.observable,
            "timescale": a.timescale, "archive_family": a.archive_family}
    budget = load_yaml("config/budget.yaml")
    pricing = budget["llm"]["pricing"][MODEL]
    prompt, reg_ids = build_prompt(cell, a.operator, a.n)
    # upper bound: prompt ~ chars/3 tokens in, ~1,500 output tokens per card incl. thinking
    est = _eur({"input_tokens": len(prompt) // 3, "output_tokens": 1500 * a.n + 8000}, pricing)
    if a.dry_run:
        print(prompt)
        print(f"\nregister entries in prompt: {reg_ids}\nestimated cost <= {est:.2f} EUR")
        return 0
    check_budget(a.n, est, budget)

    validator = Draft202012Validator(json.loads((ROOT / "schema" / "card.schema.json").read_text(encoding="utf-8")))
    all_written: list[str] = []
    for attempt in range(1 + MAX_TOP_UPS):
        missing = a.n - len(all_written)
        if missing <= 0:
            break
        if attempt:  # top-up: re-check budget, show the model what this cell already holds
            prompt, reg_ids = build_prompt(cell, a.operator, missing)
            est = _eur({"input_tokens": len(prompt) // 3, "output_tokens": 1500 * missing + 8000}, pricing)
            check_budget(missing, est, budget)
            print(f"top-up {attempt}: requesting {missing} more cards")
        raw_cards, msg = call_model(prompt)
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        cost = _eur(usage, budget["llm"]["pricing"].get(msg.model, pricing))
        number, written, rejected = next_card_number(), [], []
        for raw in raw_cards[:missing]:
            card = to_card(raw, number, cell, a.operator, msg.model)
            errs = [e.message for e in validator.iter_errors(card)]
            if errs:
                rejected.append({"title": raw.get("title"), "errors": errs[:3]})
                continue
            (CARDS / f"{card['id']}.yaml").write_text(
                yaml.safe_dump(card, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
            written.append(card["id"])
            number += 1
        all_written += written
        record = {"date": dt.date.today().isoformat(),
                  "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                  "stage": "expand", "model": msg.model, "requested_model": MODEL, "effort": EFFORT,
                  "prompt_version": PROMPT_VERSION, "operator": a.operator, "cell": cell, "by": a.by,
                  "message_id": msg.id, "top_up": attempt, "usage": usage, "cost_eur": round(cost, 4),
                  "cards_requested": missing, "cards_returned": len(raw_cards), "cards_written": written,
                  "cards_rejected": rejected, "register_ids_in_prompt": reg_ids,
                  "cost_per_card_eur": round(cost / len(written), 4) if written else None}
        COST_LOG.parent.mkdir(parents=True, exist_ok=True)
        with COST_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        print(f"call {attempt}: returned {len(raw_cards)}, wrote {len(written)} {written}, rejected {len(rejected)}; "
              f"{usage['input_tokens']} in / {usage['output_tokens']} out tokens, {cost:.3f} EUR, model {msg.model}")
    if len(all_written) < a.n:
        print(f"warning: {len(all_written)} of {a.n} cards after {MAX_TOP_UPS} top-ups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
