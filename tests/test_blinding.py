"""Gate prompts are blind to a card's origin: no id, no provenance block, for catalogue and baseline cards alike.

No model call and no network: prompts are built, not sent.
"""
import datetime as dt

import pytest

from pipeline import cards, critique
from pipeline.gates import common
from pipeline.gates.cli import GATES

SIEVE_ID, BASE_ID = "SIEVE-0002", "BASE-0002"   # both list candidate archives, so G3 builds a prompt


def _origin_strings(card: dict) -> list[str]:
    prov = card["provenance"]
    out = [card["id"], "provenance:", "generator_model", "source_bibcodes", "transcribed_by", prov["prompt_version"]]
    out += prov.get("source_bibcodes", [])
    if prov.get("taxonomy_cell"):
        out.append(prov["taxonomy_cell"])
    return out


def test_blind_card_removes_origin_and_keeps_the_rest():
    card = cards.load_card(BASE_ID)
    view = cards.blind_card(card)
    assert not set(view) & set(cards.ORIGIN_FIELDS)
    assert set(view) == set(card) - set(cards.ORIGIN_FIELDS)
    assert "provenance" in card and "id" in card   # the original is untouched


@pytest.mark.parametrize("card_id", [SIEVE_ID, BASE_ID])
@pytest.mark.parametrize("gate", sorted(GATES))
def test_gate_prompts_are_blind(card_id, gate):
    card = common.load_card(card_id)
    prompt = common.build_prompt(GATES[gate], card)
    assert card["title"][:40] in prompt   # the content is still there
    for s in _origin_strings(card):
        assert s not in prompt, f"{gate} prompt for {card_id} contains {s!r}"
    assert "\nid:" not in prompt and "\nversion:" not in prompt


@pytest.mark.parametrize("card_id", [SIEVE_ID, BASE_ID])
def test_g2_prompts_are_blind(card_id):
    card = critique.load_card(card_id)
    register = critique.load_register()
    task_a, task_b = critique.g2_prompts()
    card_yaml = critique.card_for_prompt(card)
    hits = critique.register_fast_path(card, register)
    prompts = [task_a.format(card_yaml=card_yaml),
               task_b.format(card_yaml=card_yaml, today=dt.date.today().isoformat(), queries="q",
                             register_block=critique.register_block(hits, register), papers_block="(none)")]
    for prompt in prompts:
        for s in _origin_strings(card):
            # a baseline card's source may legitimately be a register entry or a retrieved paper; it is then listed
            # like any other work, never marked as the card's source
            if s in card["provenance"].get("source_bibcodes", []):
                continue
            assert s not in prompt, f"G2 prompt for {card_id} contains {s!r}"
        assert "\nid:" not in prompt and "novelty:" not in prompt


def test_baseline_ids_route_to_the_baseline_directories():
    path, logs = cards.card_paths(BASE_ID)
    assert path.parent == cards.BASELINE_CARDS and logs == cards.BASELINE_GATE_LOGS
    path, logs = cards.card_paths(SIEVE_ID)
    assert path.parent == cards.CARDS and logs == cards.GATE_LOGS


def test_real_run_on_baseline_needs_explicit_flag():
    with pytest.raises(SystemExit):
        critique.check_baseline_ids([BASE_ID], dry_run=False, baseline_ok=False)
    critique.check_baseline_ids([BASE_ID], dry_run=True, baseline_ok=False)
    critique.check_baseline_ids([SIEVE_ID], dry_run=False, baseline_ok=False)


def test_g2_stops_cleanly_when_retrieval_is_down(monkeypatch, capsys):
    """A literature API failure is logged for the card and ends the run; later cards are not attempted."""
    logged, attempted = [], []

    def fake_g2_card(card, register, run, use_cache=True):
        attempted.append(card["id"])
        raise critique.G2RetrievalError("retrieval: api.openalex.org failed (429)")

    monkeypatch.setattr(critique, "g2_card", fake_g2_card)
    monkeypatch.setattr(critique.cards_mod, "append_gate_log", lambda cid, entry: logged.append((cid, entry)))
    rc = critique.g2(["SIEVE-0009", "SIEVE-0010"], "test", dry_run=False, max_run_eur=0.0, force=True)
    assert rc == 1 and attempted == ["SIEVE-0009"]
    assert [(c, e["verdict"]) for c, e in logged] == [("SIEVE-0009", "error")]
    assert "not attempted: SIEVE-0010" in capsys.readouterr().out
