# Literature baseline (baseline-literature-v0.1)

The baseline answers one question for the evaluation in paper Section 7: what do the four gates say about ideas that people have already published, compared with ideas from the Expand stage? It replaces the two-hour brainstorm by the owner (decision of 2026-11-11). Reasons: no second person is available, a literature baseline can be re-derived by anyone, and it is not influenced by the Expand run that has already produced SIEVE-0002..0011.

Status: 23 sources, 40 raw cards, no gate has been run. Proposed text for the paper is in `paper-change-v0.2.md`. Points that need the owner are listed under "Decision points".

## Files

| File | Content |
| --- | --- |
| `queries.yaml` | The six ADS queries, common filter, sort order and row cut. Frozen for v0.1. |
| `search.py` | Runs the queries (`search_log.json`); `--verify` re-resolves the included sources. |
| `search_log.json` | What ADS returned on 2026-11-11: 109 rows, 104 distinct records, with rank and citation count. |
| `sources.yaml` | Screening decision for each of the 104 records; for included sources the text that was read and the cards derived, with a locator per card. |
| `cards/BASE-NNNN.yaml` | The baseline cards, `status: raw`. |
| `paper-change-v0.2.md` | Proposed changes to paper Sections 7 and 9.1. |

Gate logs for baseline cards go to `evaluation/baseline/gate_logs/` (written by `pipeline.cards set-status BASE-NNNN ...` and by the gate runner, see "Gating the baseline").

## Selection rule

**Source types.** Community white papers (Astro2020 and the Planetary Science and Astrobiology decadal survey, published in BAAS), review articles, and workshop or roadmap reports. Their purpose is to survey or recommend search ideas, which is what a brainstorm would have produced. Research articles that report or propose a single study, instrument papers, conference abstracts, and laboratory or analogue studies do not qualify. Executed searches belong in `register/`.

**Search.** Six queries, one white-paper query and one review/report query per domain, written out in `queries.yaml`. Each is sent to the ADS API as `(<q>) AND collection:astronomy year:2015-2025`, sorted by `citation_count desc, bibcode asc`, first 20 rows. No source enters by any other route.

**Date window.** Publication years 2015 to 2025. The lower bound keeps the proposals in the era of the archives the project uses (Gaia, TESS, WISE, JWST). The upper bound is the last complete calendar year, so the result set does not change with late indexing, and every source predates the first SIEVE card (2026-11-07).

**Screening.** Each query's rows are walked in rank order.

1. Stage 1, on title and abstract: source type, duplicates, and whether the record is in the register.
2. Stage 2, on the accessible text: the source must name a specific signature (a named compound, a compound class with a distinguishing property, a pattern or a structure) together with the observable in which it would be seen. Generic class names such as "biosignatures", "organic biomarkers" or "radio SETI" do not pass.
3. The walk stops for a query once five sources are included. Later rows are marked `Q`.

Accessible text means, in this order: the open full text behind an e-source link of the ADS record (arXiv eprint, open publisher PDF, PubMed Central); the arXiv eprint of an ADS eprint record with the same title and first author; otherwise the ADS abstract. A record with neither abstract nor open full text is excluded (`X8`). Exclusion codes are defined in the header of `sources.yaml`.

**From source to cards.** One card per distinct idea, where an idea is a claim plus an observable for a stated target. Ideas are taken in the order the source presents them, at most one per section or bullet at the level where the source enumerates signature types, up to two cards for a white paper and three for a review or report. If an idea is already carded from an earlier source (same claim, observable and target), the later source's bibcode is added to that card and the next idea in that section is taken. Where a long source was read in parts, `sources.yaml` says which parts.

**Transcription.** The card states what the source states.

- Claim and mechanism are restated from the source. Numbers appear only if the source gives them. No estimate was added, and a missing estimate is not commented on in the card (see "Blinding: normalisation of transcription phrases").
- `data_requirements`, `candidate_archives`, `method`, `confounders` and `null_result_value` are filled only where the source addresses them, otherwise left out. Archive access paths are empty strings, because no source states one and the schema requires the field.
- `domain`, `signature_class`, `observable` and `timescale` are assigned by the transcriber from `config/taxonomy.yaml`. They are a classification, not part of the source.
- `novelty.status` is `unchecked` and `closest_prior` stays empty. The source bibcodes are provenance, not novelty evidence.

**Provenance on each card.** `generator_model: human-literature`, `operator: manual`, `prompt_version: baseline-literature-v0.1` (this document), `source_bibcodes` (resolved through ADS), `transcribed_by: claude-fable-5-2`, `created: 2026-11-11`, `edited_by_human: false`. `taxonomy_cell` is omitted because the sources do not fix an archive family.

## Result

| Query | Rows | Included sources | New cards |
| --- | --- | --- | --- |
| T-WP technosignature white papers | 16 | 4 | 5 |
| T-REV technosignature reviews and reports | 20 | 5 | 15 |
| B-WP biosignature white papers | 20 | 4 | 4 |
| B-REV biosignature reviews | 13 | 4 | 7 |
| S-WP solar-system white papers | 20 | 3 | 2 |
| S-REV solar-system reviews | 20 | 3 | 7 |
| Total | 109 (104 distinct) | 23 | 40 |

Only T-REV reached the quota of five; one row was left unscreened. Nine cards carry more than one source. Two included sources (2019BAAS...51g.238S, 2021BAAS...53d.243M) contribute only to shared cards.

| Domain | Cards | Signature classes (cards) |
| --- | --- | --- |
| technosignature | 20 | em_transmission 7, artificial_structure_geometry 6, atmospheric_chemistry 3, thermal_waste_heat 2, population_statistics 2 |
| biosignature | 11 | atmospheric_chemistry 7, surface_albedo 3, temporal_behaviour 1 |
| solar_system_insitu | 9 | insitu_composition 9 |

Coverage: 9 of the 22 valid domain × signature-class cells, 18 distinct cells on the four axes domain × class × observable × timescale. 35 of 40 cards are `snapshot`.

Exclusions: 32 not a qualifying source type, 22 without a specific signature in the accessible text, 9 laboratory or analogue studies, 5 frameworks or methods, 4 programme or facility status, 4 executed searches, 2 duplicates, 2 without accessible text, 1 beyond quota.

## Why about 40 cards

- The rule bounds the size: 6 queries × 5 sources × 2 or 3 cards gives at most 75. The realised 40 sits inside the 30 to 60 band that was set as the target.
- It is the size of what it replaces. A person writing full cards for two hours produces a few tens.
- It is about two cards per valid domain × class cell (22 cells), enough to show which cells the published literature fills and which it leaves empty.
- A pass rate measured on 40 cards has a standard error of at most 8 percentage points. That resolves differences of 20 points or more against the pipeline's rates; it does not resolve small ones, and the comparison should not be read more finely.
- Gating 40 cards is 160 gate calls, inside the `max_gate_calls_per_run` cap of 600.

## Separation from the catalogue

The schema's id pattern was `^SIEVE-[0-9]{4}$`. Baseline cards use `BASE-NNNN` and live in `evaluation/baseline/cards/`. This PR changes the schema to `^(SIEVE|BASE)-[0-9]{4}$` and adds two optional provenance fields, `source_bibcodes` and `transcribed_by`. Checked on this branch:

- `pipeline/expand.py` reads only `catalogue/cards/SIEVE-*.yaml` (existing titles, next card number) and `register/`. A dry run contains no baseline text.
- `pipeline/critique.py g2-fast --all-raw` reads only `catalogue/cards/`.
- `pipeline.cards validate` now also validates `evaluation/baseline/cards/`, requires the baseline provenance fields, checks every source bibcode against the included sources in `sources.yaml`, and fails if a `BASE` file sits in `catalogue/cards/` or a `SIEVE` file in the baseline directory.
- `pipeline.cards set-status BASE-NNNN ...` writes to the baseline card and to `evaluation/baseline/gate_logs/`. `pipeline.cards list --baseline` lists the set.

The bibcode pattern in the schema rejected arXiv bibcodes such as `2018arXiv181208681N` (a digit in the qualifier position). It is loosened by one character class in both places it occurs, including `novelty.closest_prior`, where gate G2 would have hit the same problem.

## How to read the comparison

**Volume.** The baseline's size is set by the quota, so "lift in volume" no longer measures anything. Report instead what the literature search yielded: 104 screened records gave 40 cards.

**Coverage.** Compare the cells filled by the baseline with the cells in which Expand has at least one card passing G1, on domain × class and on the four axes. The cells the baseline leaves empty are a finding about the literature as sampled here, in particular population statistics and temporal behaviour.

**G1, G3, G4 pass rates.** Comparable in principle, with two caveats that follow from faithful transcription. First, a baseline mechanism has an order-of-magnitude estimate only if the source gave one, so a G1 failure for a missing estimate is a property of the source text, not of the idea. Second, sources rarely name access paths or confounders; per paper Section 4.1 those fields are filled by G3 and G4 anyway, so the gates should be run on what the claim needs, not on whether the field was pre-filled. The nine solar-system cards describe measurements on samples that mostly need a new mission; they are expected to fail G3 unless an archive such as PDS holds an equivalent measurement.

**G2 novelty.** This is the point that needs a decision rather than a default.

- If G2 asked "has this been proposed?", every baseline card would be `done` by construction and the comparison would be empty.
- G2 in this repository asks whether the claim was *tested* with equivalent data and method (`prompts/critique-g2-novelty-v0.1.md`). Under that definition baseline cards can be `open`, `partly_done` or `done`, and the comparison has content: it says how much of what the field proposed is still untested.
- Three biases remain under the "tested" definition. (a) Time: the sources date from 2015 to 2022, so the field has had 4 to 11 years to act on them; a fresh pipeline card has had none. The baseline's `done` share is therefore an upper reference, not a like-for-like rate. (b) Retrieval: the G2 queries will return the card's own source and papers citing it. A judge that treats a proposal as a test would mark the card `done` wrongly. The judge needs the rule that a paper which only proposes the idea, including the source, has `relation: proposes, not tested` and cannot support `done`. (c) Meaning of `open`: a pipeline card judged `open` may still be a re-derivation of a published proposal, since the generator was trained on this literature. "Open under the tested definition" is not the same as "new idea".
- Suggested reading: report G2 under the "tested" definition for both sets, and add for pipeline cards a second label, proposed before or not, judged against ADS and against the baseline cards. The share of baseline cards that Expand regenerates is then a second rediscovery measure beside the register-based one.

**Blinding.** The gate prompts take the card as YAML. `provenance` (and the id prefix) should be removed before the card reaches a judge, for both sets, so that the judge does not know whether a card is from the literature or from the pipeline and does not see the source bibcodes.

## Gating the baseline

Owner decisions of 2026-11-11 on decision points 2 and 4 below, as implemented:

- **Blind prompts.** `pipeline.cards.blind_card` removes `id`, `version` and the whole `provenance` block (with `source_bibcodes` and `transcribed_by`) before a card enters any gate prompt: G1, G3 and G4 through `pipeline/gates/common.py`, the G2 query writer and judge through `pipeline/critique.py`. This holds for both card sets. `tests/test_blinding.py` checks it on one card of each set.
- **Runner.** `python -m pipeline.critique g1|g2|g2-fast|g3|g4|all` accepts `BASE-NNNN` ids, reads and writes `evaluation/baseline/cards/` and logs to `evaluation/baseline/gate_logs/`. `--all-raw` and `--all-unchecked` stay catalogue-only. A real run on a baseline card is refused unless `--baseline-ok` is given; `--dry-run` works without it.
- **G2.** From `critique-g2-novelty-v0.3` on, a paper that only proposes the idea, the card's own source included, is not a test and cannot support `done`. The judge is not told which listed paper is the source.
- **Not done yet.** No gate has been run on a baseline card. The owner audits a sample of the screening and the cards first.

G3 short-circuits without a model call on a card that lists no archive (`no_archives_listed`), which applies to 34 baseline cards.

## Blinding: normalisation of transcription phrases

Stripping `id` and `provenance` does not help if the card text itself says that it was transcribed. The first version of the cards filled gaps with sentences such as "The source gives no abundance or signal-size estimate". Owner decision of 2026-11-11: such filler is replaced by the schema's empty or absent value, so that a field the source does not address looks the same as on a pipeline card that leaves it out. 42 fields in 27 cards were changed and one emptied `data_requirements` block removed (cards at version 2); nothing a source states was removed.

**Rule.**

1. A sentence that only says something is absent is deleted. The rest of the field is unchanged.
2. A field that consists only of filler becomes absent if the schema allows it (`data_requirements.depth`; an emptied `data_requirements` block is removed) and an empty string if the schema requires it (`candidate_archives[].access`, `confounders[].exclusion`).
3. Where filler stands in front of stated content, the filler clause and an attribution lead-in directly after it ("the source says", "the source stresses", "the source names") are deleted and the stated content is kept word for word.
4. A parenthesis that only reports a gap or the act of transcription is deleted.

**Variants found.**

| Variant | Where | Fields | Replacement |
| --- | --- | --- | --- |
| "The source gives no … estimate / threshold." | `mechanism` | 2 | sentence deleted |
| "The abstract gives no … estimate." | `mechanism` | 2 | sentence deleted |
| "No … estimate / number / signal size is given." with or without "in the source", "in the passage used", "in the passages used" | `mechanism` | 13 | sentence deleted |
| "not stated in source" | `candidate_archives[].access` | 11 | empty string |
| "Not specified." | `confounders[].exclusion` | 3 | empty string |
| "Not specified; …", "Not specified in the passage used; …", "Not specified beyond …" | `confounders[].exclusion` | 5 | clause deleted, content kept |
| "not stated; …" | `data_requirements.depth` | 3 | clause deleted, content kept; field removed where the rest was "the sources do not say …" (BASE-0029) |
| "(sampling not stated)" | `data_requirements.cadence` | 1 | parenthesis deleted |
| "(not named individually)", "(not named individually in the passage used)" | `candidate_archives[].name` | 2 | parenthesis deleted |
| "(converted to wavelength by the transcriber)" | `data_requirements.depth` | 1 | parenthesis deleted (same field as one "not stated; …") |

**Attribution wording (owner decision of 2026-11-11, second step).** Sentences that reported content as what the source says were rewritten as direct statements of the same content: 59 passages in 36 cards.

5. The attribution is deleted and the content stands as a statement: "The source states that X" becomes "X". This covers "the source" with any reporting verb (states, lists, notes, reports, adds, mentions, cites, names, refers to), "the source's example / Figure", "named by the source", "as reported by the source(s)", follow-on sentences ("It states that", "It also notes that", "its table of …"), and the same forms with the publication named another way ("The abstract states", "The NASA report notes", "(NASA report)", "Fujii et al. state that", "Li et al. give").
6. No claim is added, removed or strengthened. Hedges stay as written ("may", "could", "might", "potentially", "in principle"). Where the verb itself carried the hedge, an impersonal form keeps it: "the source argues that X is" becomes "X is argued to be", "expects" becomes "is expected", "proposes" becomes "is proposed", "presents X as the best potential" becomes "X is put forward as the best potential", "cautions that" becomes "However,", "anticipates" becomes "is anticipated".
7. Citations of other works inside such a sentence are kept as plain citations: "(citing Kissell 1974)" becomes "(Kissell 1974)".
8. Who said what remains recoverable from `provenance.source_bibcodes`, the locators in `sources.yaml` and the git history of the card.

`tests/test_baseline_phrases.py` fails if a filler phrase or an attribution of these kinds, or a close variant ("the source does not specify …", "transcribed", "the sources suggest …"), appears in a baseline card outside `provenance`.

**What remains visible (limitation for the paper).**

- Absent fields. 34 of 40 baseline cards have no `candidate_archives`, 28 no `confounders`, 22 no `data_requirements` and 19 no `method`; six cards have archives with an empty access path and three have a confounder with an empty exclusion. Every pipeline card so far fills all of these. A judge can still tell the two sets apart by how complete a card is, and a difference in gate outcomes between the sets is confounded with completeness.
- Citations. Baseline cards cite works by author, e.g. "(Wright et al. 2016)"; in seven cards with more than one source, 19 parentheses of the form "(Li et al.)" say which source a statement comes from. Pipeline cards cite nothing, because Expand may not write references from memory. Citations were kept: they are content, and removing them would detach numbers from their origin.
- Direct statements read more assertive than the attributed originals, although no claim was changed. A G1 judge may weigh "X is" differently from "the source states that X is".
- Missing order-of-magnitude estimates in `mechanism` are no longer announced, but they are still missing (decision point 3).

## Limitations

- Screening and transcription were done by one LLM agent in one session; nothing has been audited by a person.
- Publisher PDFs of BAAS white papers could not be retrieved automatically. Twenty-three white papers were judged at stage 2 on a two- or three-sentence abstract; nineteen of them were excluded for lack of a specific signature (`X7`), and four were included on the abstract alone. Full texts would probably move several into the baseline, mostly in the solar-system domain.
- Two reviews were excluded because ADS has no abstract and no open full text (2020ChRv..120.4660G, 2021NRvEE...2..490B).
- Long reviews were read in the sections named in `sources.yaml`, not cover to cover. The cap of three cards per review means that large sources (the NASA workshop report, Schwieterman et al.) are sampled, not exhausted.
- Rank order by citation count is close to arbitrary for white papers with 0 to 10 citations, and counts drift. `search_log.json` is the frozen selection.
- "Same idea" for merging cards and "specific signature" for stage 2 are judgement calls; each is recorded per record in `sources.yaml`.
- Morphological signatures have no class in the taxonomy. BASE-0034 is filed under `insitu_composition` with observable `imaging`.

## Decision points for the owner

1. **Schema.** Approve the `BASE` id prefix, the two provenance fields, and the loosened bibcode pattern.
2. **G2 for the baseline.** Confirm the "tested" definition, the rule that proposal-only papers (including the card's source) cannot support `done`, and whether to add a "proposed before" label for pipeline cards.
3. **G1 and missing estimates.** Judge baseline cards as transcribed, or report failures for a missing order-of-magnitude estimate separately.
4. **Blinding.** Strip `provenance` and id from the card before gate prompts for both card sets. The gate runner also needs to accept the baseline directory and write its logs to `evaluation/baseline/gate_logs/`.
5. **Balance.** 20 technosignature, 11 biosignature, 9 solar-system cards. Accept, or add a v0.2 query file; the cheapest gain is to supply the BAAS PDFs so the nineteen abstract-only exclusions can be re-screened.
6. **Audit.** Second-screen a sample of the exclusions (about 10 records) and check about five cards against their sources. Set `edited_by_human` where a card is corrected.
7. **Volume metric.** Drop "lift in volume" from Section 7 or replace it as proposed in `paper-change-v0.2.md`.
8. **Fate of baseline cards.** Evaluation only, or eligible for Converge. If a baseline card is worth executing, the clean route is a new SIEVE card with `parent_card` pointing to it.
9. **Taxonomy.** Add a class for morphological signatures, or keep them under `insitu_composition`.

## Reproduce

```bash
uv run python -m evaluation.baseline.search --abstracts /path/outside/repo/abstracts.txt   # rewrites search_log.json
uv run python -m evaluation.baseline.search --verify    # 23 included sources resolve through ADS
uv run python -m pipeline.cards validate                # 40 baseline cards against the schema and sources.yaml
uv run python -m pipeline.cards list --baseline
```

Re-running the search at a later date can reorder rows with equal or changed citation counts. Compare against the committed `search_log.json` before drawing conclusions from a difference.
