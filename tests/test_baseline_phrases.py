"""Baseline cards carry no transcription filler that tells a judge they were transcribed from a publication.

Rule and variant list: evaluation/baseline/README.md, "Blinding: normalisation of transcription phrases". A field
the source does not address is absent (or an empty string where the schema requires the field); it is never filled
with a sentence saying that the source is silent.
"""
import re

import pytest

from pipeline import cards

FILLER = [
    # "not stated in source", "not stated; ...", "Not specified.", "(sampling not stated)", "(not named individually)"
    r"\bnot (?:stated|specified|given|named|provided|quantified)\b",
    # "The source gives no ... estimate", "The abstract gives no ...", "the sources do not say ..."
    r"\b(?:sources?|abstract|passages?|paper|review|report|authors?) (?:gives?|provides?|states?|names?) no\b",
    r"\b(?:sources?|abstract|passages?|paper|review|report) (?:does|do|did) not (?:say|state|give|specify|name|provide|address)\b",
    # "No signal-size estimate is given", "No flux estimate is given in the passages used", "No expected number is given"
    r"\bno\b[^.;]{0,80}\b(?:is|are|was|were) (?:given|stated|provided|specified)\b",
    # references to the act of transcription
    r"\bpassages? used\b",
    r"\btranscri(?:ber|bed|ption)\b",
]
_FILLER = [re.compile(p, re.I) for p in FILLER]


def _strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not path and k == "provenance":   # provenance never reaches a gate prompt (cards.blind_card)
                continue
            yield from _strings(v, f"{path}/{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def test_baseline_cards_have_no_transcription_filler():
    hits = []
    for p, card in cards.iter_baseline_cards():
        for path, text in _strings(card):
            hits += [f"{p.stem} {path}: {m.group(0)!r}" for rx in _FILLER if (m := rx.search(text))]
    assert not hits, "transcription filler in baseline cards:\n" + "\n".join(hits)


@pytest.mark.parametrize("phrase", [
    "The source gives no abundance or signal-size estimate.", "not stated in source", "Not specified.",
    "No flux estimate is given in the passages used.", "No expected number is given.",
    "the sources do not say how the network would be derived", "The abstract gives no further mechanism or estimate.",
    "reflected light curves (sampling not stated)", "(converted to wavelength by the transcriber)",
    "Not specified in the passage used; the source stresses context.", "The source does not specify a threshold.",
])
def test_filler_patterns_catch_the_known_variants(phrase):
    assert any(rx.search(phrase) for rx in _FILLER)


@pytest.mark.parametrize("phrase", [
    "a pipeline for dispersed pulses that the standard transient technique does not cover",
    "absorption bands such as the 15 um CO2 band do not vary linearly with abundance if saturated",
    "Westall et al. do not consider bulk fractionation robust where sources and sinks are poorly known",
    "co-orbital objects have not yet been pinged or imaged by planetary radar",
])
def test_filler_patterns_leave_stated_content_alone(phrase):
    assert not any(rx.search(phrase) for rx in _FILLER)
