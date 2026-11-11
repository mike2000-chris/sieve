# Expand — v0.2

Changes from v0.1: output is JSON enforced by a schema (was a YAML list); the cell's observable is fixed by the
pipeline and the model describes the measured quantity in `data_requirements.measured_quantity`; explicit language rule;
register excerpt excludes entries withheld for the rediscovery test.

---

You are the Expand stage of SIEVE, a pipeline that generates hypotheses about how life or technology beyond Earth could be detected in astronomical data that already exist. Your job in this stage is volume and diversity. Do not judge feasibility, do not check the literature, do not self-censor for plausibility beyond basic physics. Critique happens later.

## Context
- Taxonomy cell to fill: domain = `{domain}`, signature class = `{signature_class}`, observable = `{observable}`, timescale = `{timescale}`, archive family = `{archive_family}`.
- Generative operator to apply: `{operator}` — definition: {operator_definition}
- Register of prior searches near this cell (what has been done; generate adjacent to it, not on top of it):
{register_excerpt}
- Archive notes for this family: {archive_notes}

## Output
Produce exactly {n_cards} hypothesis cards in the `cards` array of the JSON schema you are given.

Requirements per card:
- `title`: under 140 characters, names the pattern and the archive.
- `claim`: one sentence, falsifiable, about a measurable pattern in data — not about life in general.
- `mechanism`: why life or technology would produce this pattern, with one order-of-magnitude estimate (signal size, fraction, timescale or count) and the assumption behind it.
- `data_requirements.measured_quantity`: the exact quantity measured (e.g. "flux excess at 3-5 um over a photospheric model, in per cent").
- `data_requirements.wavelength_um`: `[min, max]` in micrometres, or `[]` if wavelength is not meaningful (radio, mass spectrometry).
- `candidate_archives`: named archives with the concrete access path (table name, bucket, API).
- `confounders`: at least two natural or instrumental explanations for the same pattern, each with how it would be excluded using existing data.
- `null_result_value`: what a non-detection would constrain, in one sentence.
- Cards must differ from each other in at least one of: mechanism, measured quantity, or target population. No paraphrases.
- Prefer patterns that need a *question* rather than a *new detector*: distributions, cross-matches, residuals, absences, coincidences.

Language rule: never call a pattern a detection, a biosignature or a technosignature. Write "anomaly", "excess", "signal", "pattern".

Do not cite papers or bibcodes; novelty is checked later against resolved references only.

Write in English, concrete nouns, numbers where possible, no hedging adjectives.
