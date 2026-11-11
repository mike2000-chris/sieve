"""Baseline cards carry no transcription filler that tells a judge they were transcribed from a publication.

Rule and variant list: evaluation/baseline/README.md, "Blinding: normalisation of transcription phrases". A field
the source does not address is absent (or an empty string where the schema requires the field); it is never filled
with a sentence saying that the source is silent. What the source says is written as a direct statement, not as
"The source states that ..."; the attribution is in provenance.source_bibcodes.
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
_VERBS = (r"(?:states?|lists?|notes?|suggests?|argues?|reports?|adds?|cautions?|expects?|names?|mentions?|cites?|calls?|"
          r"presents?|frames?|sets?|anticipates?|refers?|quotes?|says?|stress(?:es)?|shows?|gives?|proposes?|describes?|"
          r"discuss(?:es)?|recommends?|claims?|points?|considers?|includes?|finds?|concludes?)")
ATTRIBUTION = [
    # "The source states that ...", "the source lists ...", "the sources report ..."
    rf"\b(?:the|this|these|each|one|a) sources? (?:also |further |then )?{_VERBS}\b",
    # "the source's example", "named by the source", "as reported by the sources", "in the source"
    r"\bsource's\b",
    r"\b(?:by|in|from) the sources?\b",
    # the publication under another name: "The abstract states", "The NASA report notes", "(NASA report)"
    r"\bthe abstract\b",
    r"\b(?:NASA|workshop|roadmap) report\b",
    rf"\b(?:the|this) (?:white paper|review|report|paper|study|authors?) (?:also )?{_VERBS}\b",
    # the publication's authors as the subject: "Fujii et al. state that ...", "Westall et al. do not consider ..."
    rf"\bet al\. (?:also )?(?:{_VERBS}|do not|did not)\b",
    # follow-on sentences: "It states that", "It also notes that", "its table of ..."
    r"\bIt (?:also )?(?:states|notes|lists|adds|cautions|argues|reports) that\b",
    r"\bits (?:table|figure|abstract|section)\b",
    r"\bciting\b",
]
_FILLER = [re.compile(p, re.I) for p in FILLER]
_ATTRIBUTION = [re.compile(p) if p.startswith(r"\bIt") else re.compile(p, re.I) for p in ATTRIBUTION]


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


def test_baseline_cards_have_no_attribution_to_the_source():
    """Content is stated directly; who said it is in provenance.source_bibcodes, which no gate prompt contains."""
    hits = []
    for p, card in cards.iter_baseline_cards():
        for path, text in _strings(card):
            hits += [f"{p.stem} {path}: {m.group(0)!r}" for rx in _ATTRIBUTION if (m := rx.search(text))]
    assert not hits, "attribution wording in baseline cards:\n" + "\n".join(hits)


@pytest.mark.parametrize("phrase", [
    "The source states that artificial materials appear different.", "Besides the red edge, the source lists the purple edge",
    "the source expects any transmission to be modulated", "It also notes that spectropolarimetry suggests disequilibrium",
    "The source's example is an old elliptical", "Three tasks named by the source: (1)", "The abstract states that oxygen",
    "The NASA report notes that such compounds", "Fujii et al. state that direct imaging will", "(citing Kissell 1974)",
    "The sources suggest a survey", "its table of technosignatures names starshades",
])
def test_attribution_patterns_catch_the_known_variants(phrase):
    assert any(rx.search(phrase) for rx in _ATTRIBUTION)


@pytest.mark.parametrize("phrase", [
    "Some sources emit narrowband X-ray emission centred at 0.5-2 keV",
    "readily distinguished from natural sources", "for the same source flux", "Non-technological sources of NO2",
    "It has been proposed (Hippke and Forgan 2017) that narrowband X-ray emission is optimal",
    "ten classes of transit anomaly (Wright et al. 2016) express these properties",
])
def test_attribution_patterns_leave_content_alone(phrase):
    assert not any(rx.search(phrase) for rx in _ATTRIBUTION)


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
