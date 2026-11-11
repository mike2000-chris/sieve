"""Critique stage: run gates G1-G4 on raw cards, append gate logs, update novelty/confounders fields.

Order: G2 fast path against the register first (cheap), then G1, G3, G4, then G2 against ADS/OpenAlex.

Implemented: the G2 register fast path, the full G2 gate (`g2`), and G1, G3, G4 (pipeline/gates/); `all` runs
G2-fast, G1, G3, G4 (full G2 is run separately with `g2`).

    uv run python -m pipeline.critique g2-fast SIEVE-0002 SIEVE-0003
    uv run python -m pipeline.critique g2-fast --all-raw [--dry-run]
    uv run python -m pipeline.critique g2 SIEVE-0002 [--dry-run] [--max-run-eur 3]
    uv run python -m pipeline.critique g2 --all-unchecked --by "name (model)"

Full G2 (prompt critique-g2-novelty-v0.2): the model writes 3-5 queries; pipeline/literature/retrieve.py runs them
against NASA ADS and OpenAlex and keeps the 10 best papers, all with ADS-resolved bibcodes; the model judges
done | partly_done | open over those papers and the closest register entries. Rule 2 is enforced in code: a bibcode in
the judge's output that is neither in the retrieved list nor a resolved register bibcode is dropped and logged, and a
done/partly_done verdict left without any resolved bibcode is logged as `unsupported` and does not reach the card.
The verdict is written through pipeline/cards.py `set_novelty` (card + `G2` gate-log event); `status` is untouched.
Every model call is preceded by the budget checks (monthly cap, calls per run, --max-run-eur against the call's
worst case) and followed by a record in evaluation/costs/llm_runs.jsonl.

The fast path ranks register entries by taxonomy match (domain, signature class, observable) and term overlap between
the card (title, claim, mechanism, method, archives) and the entry (name, hypothesis, method, data used). It writes a
gate-log event `G2-register` with the top hits; it does NOT set `novelty.status` -- that verdict belongs to the LLM
judge over ADS-resolved papers (paper Section 4.3). Entries with `bibcodes.status: to_resolve` are listed but marked
`evidence: false` (CLAUDE.md rule 2). Withheld entries are included: G2 is the novelty oracle, not the generator.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

from pipeline.gates import cli as gate_cli

ROOT = Path(__file__).resolve().parents[1]
GATE_LOGS = ROOT / "catalogue" / "gate_logs"
CARDS = ROOT / "catalogue" / "cards"
FAST_PATH_VERSION = "g2-register-v0.1"
TOP_K = 5
HIT_THRESHOLD = 4.0   # taxonomy alone gives at most 4; a hit needs term overlap on top of a same-cell match

STOP = set("""a an and are as at be been by can could do does for from has have if in into is it its may might more most
must no not of on or our per such than that the their them then there these they this those through to under up use used
using was we were what when where which while who will with within without would star stars data search searches survey
surveys signal signals sample samples per cent percent each other only also both any all one two three new""".split())


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9\-]{2,}", text.lower())
    return {w for w in words if w not in STOP}


def card_terms(card: dict) -> set[str]:
    parts = [card.get("title", ""), card.get("claim", ""), card.get("mechanism", ""), card.get("method", "")]
    parts += [a.get("name", "") for a in card.get("candidate_archives") or []]
    return _terms(" ".join(parts))


def entry_terms(e: dict) -> set[str]:
    parts = [e.get("name", ""), e.get("hypothesis", ""), e.get("method", ""), e.get("signature_class", ""),
             " ".join(e.get("data_used") or [])]
    return _terms(" ".join(parts))


def load_register() -> list[dict]:
    return [yaml.safe_load(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "register").glob("REG-*.yaml"))]


def register_fast_path(card: dict, register: list[dict] | None = None, k: int = TOP_K) -> list[dict]:
    """Top-k register entries for a card, with a transparent score.

    score = 2*[same signature_class] + 1*[same domain] + 1*[same observable] + 10*Jaccard(card terms, entry terms)
    """
    register = register if register is not None else load_register()
    ct = card_terms(card)
    hits = []
    for e in register:
        et = entry_terms(e)
        shared = ct & et
        jac = len(shared) / len(ct | et) if ct | et else 0.0
        tax = 2 * (e.get("signature_class") == card["signature_class"]) + (e.get("domain") == card["domain"]) \
            + (e.get("observable") == card["observable"])
        score = round(tax + 10 * jac, 2)
        hits.append({"register_id": e["id"], "score": score, "taxonomy": tax, "jaccard": round(jac, 3),
                     "shared_terms": sorted(shared)[:12], "outcome": e["outcome"],
                     "bibcodes": e["bibcodes"].get("values") or [],
                     "evidence": e["bibcodes"]["status"] == "resolved"})
    hits.sort(key=lambda h: (-h["score"], h["register_id"]))
    return hits[:k]


def log_gate(card_id: str, gate: str, verdict: str, payload: dict, by: str = "agent", prompt_version: str = "v0.1") -> None:
    GATE_LOGS.mkdir(parents=True, exist_ok=True)
    entry = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": "gate", "gate": gate,
             "verdict": verdict, "by": by, "prompt_version": prompt_version, **payload}
    with (GATE_LOGS / f"{card_id}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def g2_fast(card_ids: list[str], by: str, dry_run: bool) -> int:
    register = load_register()
    for cid in card_ids:
        card = yaml.safe_load((CARDS / f"{cid}.yaml").read_text(encoding="utf-8"))
        hits = register_fast_path(card, register)
        strong = [h for h in hits if h["score"] >= HIT_THRESHOLD and h["evidence"]]
        verdict = "register_hit" if strong else "no_register_hit"
        top = ", ".join(f"{h['register_id']} ({h['score']})" for h in hits[:3])
        print(f"{cid}: {verdict:16s} top: {top}")
        if not dry_run:
            log_gate(cid, "G2-register", verdict,
                     {"hits": hits, "threshold": HIT_THRESHOLD, "card_version": card.get("version", 1),
                      "note": "fast path only; novelty status is set by the ADS-backed G2 judge"},
                     by=by, prompt_version=FAST_PATH_VERSION)
    return 0


# --- G2: ADS/OpenAlex retrieval + LLM judge ---------------------------------------------------------------------

G2_PROMPT_VERSION = "critique-g2-novelty-v0.2"
G2_EFFORT = {"queries": "low", "judge": "high"}       # query writing is routine; the verdict is the judgement
G2_MAX_TOKENS = {"queries": 4000, "judge": 12000}     # hard per-call output ceilings; they bound the cost check
G2_MAX_PAPERS = 10
G2_MAX_QUERIES = 5
G2_CARD_FIELDS = ("id", "title", "claim", "domain", "signature_class", "observable", "timescale", "mechanism",
                  "data_requirements", "candidate_archives", "method", "confounders")

_S = {"type": "string"}
G2_QUERIES_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["queries"],
                     "properties": {"queries": {"type": "array", "items": _S}}}
G2_JUDGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["status", "confidence", "rationale", "closest_prior", "what_would_make_it_open"],
    "properties": {
        "status": {"type": "string", "enum": ["done", "partly_done", "open"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "rationale": _S,
        "closest_prior": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["bibcode", "relation"],
            "properties": {"bibcode": _S, "relation": _S}}},
        "what_would_make_it_open": _S,
    },
}


class G2Error(RuntimeError):
    """A card could not be judged (refusal, truncation, no queries); the run continues with the next card."""


def card_for_prompt(card: dict) -> str:
    """The card as the model sees it: content only, without an earlier novelty block, status or provenance."""
    return yaml.safe_dump({k: card[k] for k in G2_CARD_FIELDS if k in card}, sort_keys=False, allow_unicode=True,
                          width=110)


def g2_prompts() -> tuple[str, str]:
    from pipeline.expand import load_prompt
    task_a, task_b = load_prompt(f"{G2_PROMPT_VERSION}.md").split("\n---\n")
    return task_a.strip(), task_b.strip()


def register_block(hits: list[dict], register: list[dict]) -> str:
    by_id = {e["id"]: e for e in register}
    lines = []
    for h in hits:
        e = by_id[h["register_id"]]
        cite = ", ".join(h["bibcodes"]) if h["evidence"] and h["bibcodes"] else "none resolved; cannot be cited"
        lines.append(f"- {e['id']} | {e['name']} ({e['year']}) | bibcodes: {cite}\n"
                     f"  tested: {e['hypothesis']}\n  data: {', '.join(e.get('data_used') or [])}\n"
                     f"  method: {e.get('method', '')}\n  result: {e.get('result', '')} (outcome: {e['outcome']})")
    return "\n".join(lines) or "(no register entry near this card)"


def papers_block(papers: list[dict]) -> str:
    out = []
    for p in papers:
        who = (p["first_author"] or "unknown") + (" et al." if p["n_authors"] > 1 else "")
        out.append(f"[{p['rank']}] bibcode: {p['bibcode']} | {p['year']} | {who} | {p['pub'] or ''}\n"
                   f"Title: {p['title']}\nAbstract: {p['abstract'] or '(no abstract in ADS)'}")
    return "\n\n".join(out) or "(no papers retrieved)"


def citable_bibcodes(papers: list[dict], register: list[dict]) -> dict[str, str | None]:
    """Bibcodes the judge may cite -> register id (or None). CLAUDE.md rule 2: retrieved through the ADS API in
    this run, or held by a register entry whose bibcodes are marked resolved."""
    allowed: dict[str, str | None] = {p["bibcode"]: None for p in papers}
    for e in register:
        if e["bibcodes"]["status"] == "resolved":
            for b in e["bibcodes"].get("values") or []:
                allowed[b] = e["id"]
    return allowed


def enforce_resolved(closest_prior: list[dict], allowed: dict[str, str | None]) -> tuple[list[dict], list[dict]]:
    """Split the judge's citations into kept (bibcode in `allowed`) and dropped (anything else)."""
    kept, dropped, seen = [], [], set()
    for item in closest_prior:
        b = (item.get("bibcode") or "").strip()
        if b in seen:
            continue
        seen.add(b)
        if b in allowed:
            entry = {"bibcode": b}
            if allowed[b]:
                entry["register_id"] = allowed[b]
            kept.append({**entry, "relation": item.get("relation", "").strip()})
        else:
            dropped.append({"bibcode": b, "relation": item.get("relation", ""),
                            "reason": "not in the retrieved list or the register's resolved bibcodes"})
    return kept, dropped


def _g2_call(task: str, prompt: str, schema: dict, card_id: str, run: dict) -> tuple[dict, dict]:
    """One model call with the budget check before it and the run record after it (CLAUDE.md rules 6 and 7)."""
    import anthropic
    from dotenv import load_dotenv

    from pipeline.expand import COST_LOG, MODEL, _eur, spent_this_month

    llm = run["budget"]["llm"]
    dearest = max(llm["pricing"].values(), key=lambda p: p["output_usd_per_mtok"])  # a fallback model may answer
    worst = _eur({"input_tokens": len(prompt) // 3, "output_tokens": G2_MAX_TOKENS[task]}, dearest)
    if run["calls"] + 1 > llm["max_gate_calls_per_run"]:
        raise SystemExit(f"budget: gate call {run['calls'] + 1} > max_gate_calls_per_run {llm['max_gate_calls_per_run']}")
    month = spent_this_month()
    if month + worst > llm["max_eur"]:
        raise SystemExit(f"budget: spent {month:.2f} EUR + worst case {worst:.2f} EUR > monthly cap {llm['max_eur']} EUR")
    if run["spent"] + worst > run["cap"]:
        raise SystemExit(f"budget: run spent {run['spent']:.3f} EUR + worst case {worst:.3f} EUR for the next call "
                         f"({card_id} {task}) > run cap {run['cap']:.2f} EUR; stopping")

    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=G2_MAX_TOKENS[task],
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # as in expand.py: on a policy decline a fallback model answers; msg.model records which
        output_config={"effort": G2_EFFORT[task], "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    cost = _eur(usage, llm["pricing"].get(msg.model, dearest))
    run["spent"] += cost
    run["calls"] += 1
    call = {"task": task, "model": msg.model, "message_id": msg.id, **usage, "cost_eur": round(cost, 4)}
    record = {"date": dt.date.today().isoformat(), "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "stage": f"critique-g2-{task}", "model": msg.model, "requested_model": MODEL, "effort": G2_EFFORT[task],
              "prompt_version": G2_PROMPT_VERSION, "card": card_id, "by": run["by"], "message_id": msg.id,
              "stop_reason": msg.stop_reason, "usage": usage, "cost_eur": round(cost, 4)}
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    if msg.stop_reason == "refusal":
        raise G2Error(f"{task}: model refused ({getattr(msg, 'stop_details', None)})")
    if msg.stop_reason == "max_tokens":
        raise G2Error(f"{task}: output truncated at {G2_MAX_TOKENS[task]} tokens")
    return json.loads(next(b.text for b in msg.content if b.type == "text")), call


def g2_card(card: dict, register: list[dict], run: dict, use_cache: bool = True) -> dict:
    """Queries -> retrieval -> judge -> rule-2 filter for one card. Returns the result; writes nothing but run records."""
    from pipeline.literature.retrieve import retrieve

    task_a, task_b = g2_prompts()
    card_yaml = card_for_prompt(card)
    calls = []
    out, call = _g2_call("queries", task_a.format(card_yaml=card_yaml), G2_QUERIES_SCHEMA, card["id"], run)
    calls.append(call)
    queries = list(dict.fromkeys(q.strip() for q in out["queries"] if q.strip()))[:G2_MAX_QUERIES]
    if not queries:
        raise G2Error("queries: model returned no query")
    found = retrieve(queries, k=G2_MAX_PAPERS, use_cache=use_cache)
    hits = register_fast_path(card, register)
    prompt = task_b.format(card_yaml=card_yaml, today=dt.date.today().isoformat(), queries="; ".join(queries),
                           register_block=register_block(hits, register), papers_block=papers_block(found["papers"]))
    verdict, call = _g2_call("judge", prompt, G2_JUDGE_SCHEMA, card["id"], run)
    calls.append(call)
    kept, dropped = enforce_resolved(verdict["closest_prior"], citable_bibcodes(found["papers"], register))
    return {"queries": queries, "found": found, "register_hits": hits, "verdict": verdict, "kept": kept,
            "dropped": dropped, "calls": calls, "cost_eur": round(sum(c["cost_eur"] for c in calls), 4)}


def g2(card_ids: list[str], by: str, dry_run: bool, max_run_eur: float, force: bool, use_cache: bool = True) -> int:
    from pipeline import cards as cards_mod
    from pipeline.expand import MODEL, _eur, load_yaml

    register = load_register()
    budget = load_yaml("config/budget.yaml")
    run = {"spent": 0.0, "calls": 0, "cap": max_run_eur, "budget": budget, "by": by}
    done, failed = [], []
    for cid in card_ids:
        card = yaml.safe_load((CARDS / f"{cid}.yaml").read_text(encoding="utf-8"))
        previous = (card.get("novelty") or {}).get("status", "unchecked")
        if previous != "unchecked" and not force:
            print(f"{cid}: novelty already {previous}; skipped (use --force to judge again)")
            continue
        if dry_run:
            prompt = g2_prompts()[0].format(card_yaml=card_for_prompt(card))
            dearest = max(budget["llm"]["pricing"].values(), key=lambda p: p["output_usd_per_mtok"])
            worst = _eur({"input_tokens": len(prompt) // 3 + 12000, "output_tokens": sum(G2_MAX_TOKENS.values())}, dearest)
            print(f"--- {cid}: Task A prompt ---\n{prompt}\n--- worst case for both calls <= {worst:.2f} EUR ---")
            continue
        try:
            res = g2_card(card, register, run, use_cache)
        except G2Error as err:
            print(f"{cid}: not judged: {err}")
            log_gate(cid, "G2", "error", {"error": str(err), "requested_model": MODEL}, by=by,
                     prompt_version=G2_PROMPT_VERSION)
            failed.append(cid)
            continue
        v = res["verdict"]
        payload = {
            "prompt_version": G2_PROMPT_VERSION, "model": res["calls"][-1]["model"], "requested_model": MODEL,
            "effort": G2_EFFORT, "date": dt.date.today().isoformat(), "confidence": v["confidence"],
            "queries": res["queries"], "retrieval": res["found"]["per_query"],
            "retrieval_pool_size": res["found"]["pool_size"],
            "openalex_dois_without_ads_record": res["found"]["openalex_unresolved"],
            "retrieved": [{k: p[k] for k in ("rank", "bibcode", "year", "title", "sources", "score")}
                          for p in res["found"]["papers"]],
            "register_hits_shown": [h["register_id"] for h in res["register_hits"]],
            "judge_output": v, "closest_prior_kept": res["kept"], "dropped_bibcodes": res["dropped"],
            "calls": res["calls"], "cost_eur": res["cost_eur"],
        }
        for d in res["dropped"]:
            print(f"{cid}: dropped unresolved bibcode {d['bibcode']!r} from the judge's output (rule 2)")
        if v["status"] != "open" and not res["kept"]:
            # a "tested before" verdict with no resolved reference is not evidence; the card stays as it was
            print(f"{cid}: verdict {v['status']} has no resolved bibcode left; novelty stays {previous}")
            log_gate(cid, "G2", "unsupported", payload, by=by, prompt_version=G2_PROMPT_VERSION)
            failed.append(cid)
            continue
        novelty = {"status": v["status"], "confidence": v["confidence"], "rationale": v["rationale"].strip()}
        if res["kept"]:
            novelty["closest_prior"] = res["kept"]
        if v["status"] != "open" and v["what_would_make_it_open"].strip():
            novelty["what_would_make_it_open"] = v["what_would_make_it_open"].strip()
        novelty.update({"queries_run": res["queries"],
                        "judged": {"model": res["calls"][-1]["model"], "prompt_version": G2_PROMPT_VERSION,
                                   "date": dt.date.today().isoformat(), "by": by},
                        "audited_by_human": False})
        if cards_mod.set_novelty(cid, novelty, by, payload):
            failed.append(cid)
            continue
        done.append((cid, v["status"], v["confidence"], res["cost_eur"]))
        print(f"{cid}: {v['status']} ({v['confidence']}), {len(res['kept'])} prior, {len(res['found']['papers'])} papers "
              f"retrieved, {res['cost_eur']:.3f} EUR")
    if not dry_run:
        n = len(done) + len(failed)
        print(f"G2 run: {len(done)} judged, {len(failed)} not judged, {run['calls']} calls, {run['spent']:.3f} EUR"
              + (f", {run['spent'] / n:.3f} EUR per card" if n else ""))
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="critique")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("g2-fast", help="G2 register fast path")
    g.add_argument("card_ids", nargs="*")
    g.add_argument("--all-raw", action="store_true")
    g.add_argument("--by", default="agent")
    g.add_argument("--dry-run", action="store_true")
    g2p = sub.add_parser("g2", help="G2 novelty: LLM queries, ADS/OpenAlex retrieval, LLM judge")
    g2p.add_argument("card_ids", nargs="*")
    g2p.add_argument("--all-unchecked", action="store_true", help="every card with novelty.status unchecked")
    g2p.add_argument("--force", action="store_true", help="judge again cards that already have a verdict")
    g2p.add_argument("--max-run-eur", type=float, default=3.0, help="stop before the call that could exceed this")
    g2p.add_argument("--no-cache", action="store_true", help="ignore cached ADS/OpenAlex responses")
    g2p.add_argument("--by", default="agent")
    g2p.add_argument("--dry-run", action="store_true")
    gate_cli.add_subparsers(sub)
    a = ap.parse_args(argv)
    if a.cmd == "g2":
        ids = list(a.card_ids)
        if a.all_unchecked:
            ids += [p.stem for p in sorted(CARDS.glob("SIEVE-*.yaml")) if p.stem not in ids and
                    (yaml.safe_load(p.read_text(encoding="utf-8")).get("novelty") or {}).get("status", "unchecked")
                    == "unchecked"]
        if not ids:
            ap.error("give card ids or --all-unchecked")
        return g2(ids, a.by, a.dry_run, a.max_run_eur, a.force, use_cache=not a.no_cache)
    if a.cmd == "g2-fast":
        ids = list(a.card_ids)
        if a.all_raw:
            ids += [p.stem for p in sorted(CARDS.glob("SIEVE-*.yaml"))
                    if yaml.safe_load(p.read_text(encoding="utf-8")).get("status") == "raw" and p.stem not in ids]
        if not ids:
            ap.error("give card ids or --all-raw")
        return g2_fast(ids, a.by, a.dry_run)
    if a.cmd in gate_cli.COMMANDS:
        return gate_cli.run(a, g2_fast=g2_fast)
    return 2


if __name__ == "__main__":
    sys.exit(main())
