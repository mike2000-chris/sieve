"""Refine stage: trigger rule, taxonomy guard, one-round guard, baseline refusal, blinding of the reviser input.

No model call and no network. The end-to-end tests run on a temporary copy of the catalogue with a fake model
response; the repository's cards, gate logs and cost log are never written.
"""
import copy
import json
import re
import shutil
from types import SimpleNamespace

import pytest
import yaml

from pipeline import cards, refine

G1_REVISE = {"verdict": "revise", "reason": "method cancels the quantity it measures",
             "checks": [{"check": "internal_consistency", "result": "concern", "note": "n"}], "revision_hint": "h"}
G3_PARTIAL = {"verdict": "partial", "reason": "r", "archive_side": True, "access_plan": ["query the table"],
              "archives": [{"name": "Gaia DR3", "what_it_provides": "parallaxes", "gap": "row cap at 50,000"}]}
G4_ROBUST = {"robustness": 2, "reason": "r", "dominant_confounder": "d", "required_cross_matches": [],
             "confounders": [{"name": "blend", "how_it_mimics": "m", "exclusion_test": "check neighbours",
                              "exclusion_data": "Gaia DR3", "excludable": "partly"}]}


def _card(**over) -> dict:
    card = {"id": "SIEVE-0900", "version": 3, "title": "Test card for the refine trigger", "status": "raw",
            "domain": "technosignature", "signature_class": "thermal_waste_heat", "observable": "spectral_excess",
            "timescale": "snapshot", "novelty": {"status": "open"},
            "provenance": {"generator_model": "m", "prompt_version": "expand-v0.2", "operator": "inversion",
                           "taxonomy_cell": "technosignature/thermal_waste_heat/spectral_excess/snapshot/spherex",
                           "parent_card": None, "created": "2026-11-11"}}
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(card.get(k), dict):
            card[k] = {**card[k], **v}
        else:
            card[k] = v
    return card


def _findings(g1=None, g3=None, g4=None) -> dict:
    wrap = lambda r: None if r is None else {"ts": "t", "prompt_version": "p", "model": "m", "result": r}
    return {"G1": wrap(g1), "G3": wrap(g3), "G4": wrap(g4)}


def _g1(verdict):
    return {**G1_REVISE, "verdict": verdict}


def _g3(verdict, **over):
    return {**G3_PARTIAL, "verdict": verdict, **over}


def _g4(robustness, **over):
    return {**G4_ROBUST, "robustness": robustness, **over}


# --- trigger rule --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("g1, g3, g4, expected", [
    (_g1("revise"), _g3("available"), _g4(3), ["G1 revise"]),
    (_g1("pass"), _g3("available"), _g4(1), ["G4 robustness 1 with 1 named exclusion tests"]),
    (_g1("pass"), _g3("available"), _g4(0), ["G4 robustness 0 with 1 named exclusion tests"]),
    (_g1("pass"), _g3("partial"), _g4(3), ["G3 partial with a concrete remedy"]),
    (_g1("revise"), _g3("partial"), _g4(1), ["G1 revise", "G4 robustness 1 with 1 named exclusion tests",
                                             "G3 partial with a concrete remedy"]),
])
def test_trigger_fires(g1, g3, g4, expected):
    d = refine.decide(_card(), _findings(g1, g3, g4))
    assert d.eligible and d.triggers == expected and not d.blockers


@pytest.mark.parametrize("g1, g3, g4", [
    (_g1("pass"), _g3("available"), _g4(2)),                                  # nothing asks for a repair
    (_g1("pass"), _g3("available"), _g4(3)),
    (_g1("pass"), _g3("available"), _g4(1, confounders=[])),                  # low robustness, no test named
    (_g1("pass"), _g3("available"), _g4(1, confounders=[{"name": "x", "exclusion_test": " "}])),
    (_g1("pass"), _g3("partial", access_plan=[]), _g4(3)),                    # partial without a remedy
    (_g1("pass"), _g3("partial", archives=[{"name": "a", "gap": ""}]), _g4(3)),
    (_g1("pass"), _g3("needs_observations"), _g4(3)),                         # not a repair note
])
def test_trigger_does_not_fire(g1, g3, g4):
    d = refine.decide(_card(), _findings(g1, g3, g4))
    assert not d.eligible and not d.triggers and not d.blockers


def test_g1_fail_and_g2_done_are_rejections_not_repair_notes():
    d = refine.decide(_card(), _findings(_g1("fail"), _g3("partial"), _g4(1)))
    assert not d.eligible and d.triggers and any("G1 fail" in b for b in d.blockers)
    d = refine.decide(_card(novelty={"status": "done"}), _findings(_g1("revise"), _g3("partial"), _g4(1)))
    assert not d.eligible and d.triggers and any("G2 done" in b for b in d.blockers)
    for status in ("open", "partly_done"):
        assert refine.decide(_card(novelty={"status": status}), _findings(_g1("revise"), _g3("partial"), _g4(1))).eligible


def test_a_card_that_has_not_been_through_all_gates_waits():
    full = (_g1("revise"), _g3("partial"), _g4(1))
    for missing in range(3):
        partial = [None if i == missing else r for i, r in enumerate(full)]
        d = refine.decide(_card(), _findings(*partial))
        assert not d.eligible and any("not through Critique" in b for b in d.blockers)
    d = refine.decide(_card(novelty={"status": "unchecked"}), _findings(*full))
    assert not d.eligible and any("G2" in b for b in d.blockers)


@pytest.mark.parametrize("status", ["parked", "selected", "preregistered", "executed", "reported"])
def test_only_raw_and_gated_cards_are_refined(status):
    assert not refine.decide(_card(status=status), _findings(_g1("revise"), _g3("partial"), _g4(1))).eligible
    assert refine.decide(_card(status="gated"), _findings(_g1("revise"), _g3("partial"), _g4(1))).eligible


# --- one round -----------------------------------------------------------------------------------------------------

def test_one_round_only():
    f = _findings(_g1("revise"), _g3("partial"), _g4(1))
    refined = _card(provenance={"operator": "refine", "parent_card": "SIEVE-0001"})
    d = refine.decide(refined, f)
    assert not d.eligible and any("one revision round" in b for b in d.blockers)
    d = refine.decide(_card(), f, child_ids=["SIEVE-0901"])   # the parent of an existing refined card
    assert not d.eligible and any("already refined as SIEVE-0901" in b for b in d.blockers)


# --- baseline ------------------------------------------------------------------------------------------------------

def test_baseline_cards_are_never_eligible():
    f = _findings(_g1("revise"), _g3("partial"), _g4(1))
    d = refine.decide(_card(id="BASE-0002", provenance={"generator_model": "human-literature"}), f)
    assert not d.eligible and any("baseline" in b for b in d.blockers)
    d = refine.decide(_card(provenance={"generator_model": "human-literature"}), f)   # whatever the id says
    assert not d.eligible


def test_cli_refuses_base_ids_even_in_a_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(refine, "call_model", lambda prompt: pytest.fail("model called for a baseline card"))
    monkeypatch.setattr(refine, "build_prompt", lambda *a: pytest.fail("prompt built for a baseline card"))
    assert refine.main(["BASE-0002", "--dry-run"]) == 1
    assert refine.main(["SIEVE-0002", "BASE-0002"]) == 1   # one baseline id refuses the whole invocation
    assert "never refined" in capsys.readouterr().out


def test_eligible_listing_covers_the_catalogue_only(capsys):
    assert refine.main(["--eligible"]) == 0
    out = capsys.readouterr().out
    assert "SIEVE-0001" in out and "BASE-" not in out


# --- taxonomy guard ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("fld, value", [("domain", "biosignature"), ("signature_class", "temporal_behaviour"),
                                        ("observable", "photometry"), ("timescale", "years")])
def test_taxonomy_guard_names_the_changed_field(fld, value):
    parent = _card()
    same = {f: parent[f] for f in cards.TAXONOMY_FIELDS}
    assert refine.taxonomy_violations(parent, same) == []
    v = refine.taxonomy_violations(parent, {**same, fld: value})
    assert len(v) == 1 and v[0].startswith(f"{fld}:")
    assert refine.taxonomy_violations(parent, {k: x for k, x in same.items() if k != fld})   # missing counts as changed


def test_new_card_takes_its_taxonomy_from_the_parent_not_from_the_model():
    parent = cards.load_card("SIEVE-0006")
    revised = _revised(parent, domain="biosignature", observable="photometry")
    new = refine.to_card(revised, "SIEVE-0999", parent, "some-model")
    assert all(new[f] == parent[f] for f in cards.TAXONOMY_FIELDS)
    assert new["provenance"] == {**new["provenance"], "operator": "refine", "parent_card": "SIEVE-0006",
                                 "prompt_version": refine.PROMPT_VERSION, "generator_model": "some-model",
                                 "taxonomy_cell": parent["provenance"]["taxonomy_cell"]}
    assert new["status"] == "raw" and new["novelty"] == {"status": "unchecked"} and new["version"] == 1
    assert "physics" not in new and "scores" not in new   # the refined card is gated from scratch


def test_citation_guard():
    clean = {"claim": "Flux excess at 3-5 um above 5 per cent in 2 of 10^5 dwarfs within 200 pc (Gaia DR3, APOGEE DR17)",
             "method": "Fit MIST and PARSEC isochrones; W1-W2 from CatWISE2020; LAMOST DR10; 2MASS J/H",
             "mechanism": "T_d ~ 300 K at 1 AU; full-sky release expected (Nov 2026) or by July 2027)"}
    assert refine.citation_hits(clean) == []
    for text in ("as in 2018ApJ...862...21Z", "Zackrisson et al. measured", "following Wright (2014)",
                 "see arXiv:2409.11447", "doi 10.3847/1538-4357/aac386", "Suazo & Zackrisson 2024)"):
        assert refine.citation_hits({**clean, "method": text}), text


# --- blinding of the reviser input ---------------------------------------------------------------------------------

BIBCODE = re.compile(r"[0-9]{4}[A-Za-z&.]{5}[A-Za-z0-9.]{9}[A-Z]")


@pytest.mark.parametrize("card_id", ["SIEVE-0002", "SIEVE-0006"])
def test_reviser_prompt_is_blind(card_id):
    card = cards.load_card(card_id)
    prompt = refine.build_prompt(card, refine.latest_findings(card))
    prov = card["provenance"]
    assert card["title"][:40] in prompt and "{" not in prompt.split("## Card")[0]   # content there, placeholders filled
    for s in (card["id"], "SIEVE-", "provenance:", "generator_model", prov["prompt_version"], prov["taxonomy_cell"],
              prov["generator_model"], "parent_card", "edited_by_human"):
        assert s not in prompt, f"reviser prompt for {card_id} contains {s!r}"
    assert "\nid:" not in prompt and "\nversion:" not in prompt
    # no G2 output and so no reference: the novelty block with its bibcodes stays out
    for s in ("novelty:", "closest_prior", "queries_run", "what_would_make_it_open", "et al"):
        assert s not in prompt, f"reviser prompt for {card_id} contains {s!r}"
    assert not BIBCODE.search(prompt)
    # no bookkeeping, no earlier gate output inside the card part
    card_part = prompt.split("## Card")[1].split("## Reviewer findings")[0]
    for s in ("physics:", "scores:", "status:", "anomaly_level", "parked_reason", refine.G4_APPENDED, "licence:"):
        assert s not in card_part, f"card part for {card_id} contains {s!r}"


def test_reviser_view_keeps_the_generated_card_and_drops_gate_output():
    card = cards.load_card("SIEVE-0006")
    before = copy.deepcopy(card)
    view = refine.reviser_view(card)
    assert card == before                                        # the card itself is untouched
    assert not set(view) & (set(cards.ORIGIN_FIELDS) | set(refine.HIDDEN_FIELDS))
    for k in ("title", "claim", "mechanism", "method", "data_requirements", "null_result_value", *cards.TAXONOMY_FIELDS):
        assert view[k] == card[k]
    assert 0 < len(view["confounders"]) <= len(card["confounders"])
    assert all(set(a) == {"name", "access"} for a in view["candidate_archives"])


def test_findings_come_from_the_latest_gate_event():
    events = [{"event": "gate", "gate": "G1", "ts": "1", "result": _g1("fail")},
              {"event": "gate", "gate": "G1", "ts": "2", "result": {"errors": ["invalid output"]}},   # no verdict
              {"event": "gate", "gate": "G1", "ts": "3", "result": _g1("revise")},
              {"event": "physics", "gate": "G1", "ts": "4", "verdict": "pass"},                       # backfill event
              {"event": "gate", "gate": "G2", "ts": "5", "result": {"verdict": "open", "checks": []}},
              {"event": "gate", "gate": "G4", "ts": "6", "result": _g4(1)}]
    f = refine.latest_findings(_card(), events)
    assert f["G1"]["ts"] == "3" and f["G1"]["result"]["verdict"] == "revise"
    assert f["G3"] is None and f["G4"]["result"]["robustness"] == 1
    block = {"verdict": "revise", "rationale": "r", "checks": {"observability": "concern"}, "revision_hints": ["h"],
             "judged": {"model": "m", "prompt_version": "p", "date": "2026-11-11", "by": "b"}}
    f = refine.latest_findings(_card(physics=block), [])   # verdict known from the card only
    assert f["G1"]["result"]["verdict"] == "revise" and f["G1"]["result"]["revision_hint"] == "h"


# --- end to end on a temporary catalogue, fake model ---------------------------------------------------------------

def _revised(parent: dict, **over) -> dict:
    out = {"title": "Revised: " + parent["title"][:100], "claim": parent["claim"], "mechanism": parent["mechanism"],
           "method": "Repaired method: fit the photosphere on the optical bands alone, then compare.",
           "null_result_value": parent["null_result_value"],
           "data_requirements": {"measured_quantity": "q", "wavelength_um": [0.33, 5.0], "spectral_resolution": "R~40",
                                 "cadence": "single epoch", "depth": "G<13", "sample": "K dwarfs within 200 pc"},
           "candidate_archives": [{"name": "Gaia DR3", "access": "TAP gaiadr3.gaia_source"}],
           "confounders": [{"name": "starspots", "exclusion": "activity flags"}, {"name": "blends", "exclusion": "Gaia neighbours"}],
           **{f: parent[f] for f in cards.TAXONOMY_FIELDS},
           "changes": [{"field": "method", "action": "changed", "what_changed": "deficit from the photosphere only",
                        "gate": "G1", "finding": "heat added back"}],
           "open_uncertainties": ["SPHEREx saturation limit to verify"]}
    out.update(over)
    return out


def _msg(payload: dict, stop_reason: str = "end_turn"):
    return SimpleNamespace(id="msg_test", model=refine.MODEL, stop_reason=stop_reason,
                           usage=SimpleNamespace(input_tokens=9000, output_tokens=7000),
                           content=[SimpleNamespace(type="text", text=json.dumps(payload))])


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A copy of SIEVE-0006 with its gate log in a temporary catalogue; cost log redirected."""
    cdir, ldir = tmp_path / "cards", tmp_path / "gate_logs"
    cdir.mkdir()
    ldir.mkdir()
    shutil.copy(cards.CARDS / "SIEVE-0006.yaml", cdir)
    shutil.copy(cards.GATE_LOGS / "SIEVE-0006.jsonl", ldir)
    monkeypatch.setattr(cards, "CARDS", cdir)
    monkeypatch.setattr(cards, "GATE_LOGS", ldir)
    monkeypatch.setattr(refine, "COST_LOG", tmp_path / "llm_runs.jsonl")
    monkeypatch.setattr(refine, "spent_this_month", lambda: 0.0)
    return SimpleNamespace(cards=cdir, logs=ldir, costs=tmp_path / "llm_runs.jsonl")


def _events(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_refine_writes_the_new_card_parks_the_parent_and_logs_both(sandbox, monkeypatch):
    parent = cards.load_card("SIEVE-0006")
    seen = {}
    monkeypatch.setattr(refine, "call_model", lambda prompt: seen.setdefault("prompt", prompt) and _msg(_revised(parent)))
    assert refine.main(["SIEVE-0006", "--by", "pytest", "--max-run-eur", "1.0"]) == 0
    assert "SIEVE-0006" not in seen["prompt"]

    new = cards.load_card("SIEVE-0007")   # next free id in the temporary catalogue
    assert new["provenance"]["operator"] == "refine" and new["provenance"]["parent_card"] == "SIEVE-0006"
    assert new["provenance"]["prompt_version"] == "refine-v0.1" and new["provenance"]["generator_model"] == refine.MODEL
    assert new["status"] == "raw" and new["version"] == 1 and new["method"].startswith("Repaired method")
    assert all(new[f] == parent[f] for f in cards.TAXONOMY_FIELDS)
    assert cards.refine_lineage_problems(new) == []

    old = cards.load_card("SIEVE-0006")
    assert old["status"] == "parked" and old["parked_reason"] == "refined as SIEVE-0007"
    assert old["method"] == parent["method"] and old["version"] == parent["version"] + 1   # content untouched

    child_log, parent_log = _events(sandbox.logs / "SIEVE-0007.jsonl"), _events(sandbox.logs / "SIEVE-0006.jsonl")
    ev = child_log[-1]
    assert ev["event"] == "refine" and ev["parent_card"] == "SIEVE-0006" and ev["changes"][0]["gate"] == "G1"
    assert ev["open_uncertainties"] and ev["by"] == "pytest" and ev["model"] == refine.MODEL
    assert ev["prompt_version"] == "refine-v0.1" and ev["date"] and set(ev["findings_used"]) == {"G1", "G3", "G4"}
    status, pev = parent_log[-2], parent_log[-1]
    assert status["event"] == "status" and status["to"] == "parked" and status["reason"] == "refined as SIEVE-0007"
    assert pev["event"] == "refine" and pev["refined_as"] == "SIEVE-0007" and pev["by"] == "pytest"

    cost = _events(sandbox.costs)
    assert len(cost) == 1 and cost[0]["stage"] == "refine" and cost[0]["card"] == "SIEVE-0006"
    assert cost[0]["card_written"] == "SIEVE-0007" and cost[0]["cost_eur"] > 0 and cost[0]["prompt_version"] == "refine-v0.1"

    # one round: neither the parked parent nor the refined card can be refined again
    monkeypatch.setattr(refine, "call_model", lambda prompt: pytest.fail("second round"))
    assert refine.main(["SIEVE-0006"]) == 1 and refine.main(["SIEVE-0007"]) == 1
    assert len(list(sandbox.cards.glob("*.yaml"))) == 2


@pytest.mark.parametrize("over, why", [
    ({"signature_class": "temporal_behaviour"}, "taxonomy changed"),
    ({"timescale": "years"}, "taxonomy changed"),
    ({"method": "Repeat the measurement of Zackrisson et al. on the new sample."}, "citation"),
    ({"title": "short"}, "card schema"),
])
def test_rejected_output_writes_no_card_and_leaves_the_parent_alone(sandbox, monkeypatch, over, why):
    parent = cards.load_card("SIEVE-0006")
    monkeypatch.setattr(refine, "call_model", lambda prompt: _msg(_revised(parent, **over)))
    assert refine.main(["SIEVE-0006", "--by", "pytest"]) == 1
    assert [p.name for p in sandbox.cards.glob("*.yaml")] == ["SIEVE-0006.yaml"]
    assert cards.load_card("SIEVE-0006") == parent
    ev = _events(sandbox.logs / "SIEVE-0006.jsonl")[-1]
    assert ev["event"] == "refine_rejected" and any(why in r for r in ev["reasons"]) and ev["by"] == "pytest"
    cost = _events(sandbox.costs)
    assert len(cost) == 1 and cost[0]["outcome"] == "rejected" and cost[0]["card_written"] is None   # the call is still paid for


def test_truncated_call_is_recorded_and_rejected(sandbox, monkeypatch):
    monkeypatch.setattr(refine, "call_model", lambda prompt: _msg({}, stop_reason="max_tokens"))
    assert refine.main(["SIEVE-0006"]) == 1
    assert _events(sandbox.costs)[0]["outcome"] == "max_tokens"
    assert _events(sandbox.logs / "SIEVE-0006.jsonl")[-1]["event"] == "refine_rejected"
    assert cards.load_card("SIEVE-0006")["status"] == "raw"


def test_budget_is_checked_before_the_call(sandbox, monkeypatch):
    monkeypatch.setattr(refine, "call_model", lambda prompt: pytest.fail("called despite the cap"))
    with pytest.raises(SystemExit, match="max-run-eur"):
        refine.main(["SIEVE-0006", "--max-run-eur", "0.05"])
    monkeypatch.setattr(refine, "spent_this_month", lambda: 149.9)
    with pytest.raises(SystemExit, match="monthly cap"):
        refine.main(["SIEVE-0006", "--max-run-eur", "5"])
    assert not sandbox.costs.exists() and cards.load_card("SIEVE-0006")["status"] == "raw"


def test_dry_run_writes_nothing(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(refine, "call_model", lambda prompt: pytest.fail("dry run called the model"))
    before = (sandbox.cards / "SIEVE-0006.yaml").read_bytes(), (sandbox.logs / "SIEVE-0006.jsonl").read_bytes()
    assert refine.main(["SIEVE-0006", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "SIEVE-0006: refine  [G1 revise" in out and "## Reviewer findings" in out and "no call made" in out
    assert before == ((sandbox.cards / "SIEVE-0006.yaml").read_bytes(), (sandbox.logs / "SIEVE-0006.jsonl").read_bytes())
    assert not sandbox.costs.exists() and len(list(sandbox.cards.glob("*.yaml"))) == 1


# --- cards.py invariants -------------------------------------------------------------------------------------------

def test_validate_checks_refine_lineage(sandbox):
    parent = cards.load_card("SIEVE-0006")
    child = refine.to_card(_revised(parent), "SIEVE-0007", parent, "m")
    assert cards.refine_lineage_problems(child) == []
    assert cards.refine_lineage_problems(parent) == []                              # not a refined card
    assert cards.refine_lineage_problems({**child, "observable": "photometry"})     # left the parent's cell
    orphan = {**child, "provenance": {**child["provenance"], "parent_card": None}}
    assert cards.refine_lineage_problems(orphan)
    assert cards.refine_lineage_problems({**child, "id": "BASE-0001"})              # baseline is never refined
    assert cards.create_card(child) == []
    grandchild = refine.to_card(_revised(child), "SIEVE-0008", child, "m")          # a second round
    assert any("one revision round" in p for p in cards.create_card(grandchild))
    assert cards.create_card(child) == ["SIEVE-0007 already exists"]                # never overwrites
    assert yaml.safe_load((sandbox.cards / "SIEVE-0007.yaml").read_text())["version"] == 1
