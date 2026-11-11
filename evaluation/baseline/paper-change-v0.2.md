# Proposed paper change for v0.2: literature baseline instead of the brainstorm baseline

Status: proposal for the owner, 2026-11-11. `paper/sieve-v0.1.md` is not edited by this PR. Method and data: `evaluation/baseline/README.md`.

## What changes

### Section 7, paragraph "Baseline"

Current text:

> **Baseline.** A two-hour human-only brainstorm by the author before the pipeline runs, scored with the same gates. The comparison is the pipeline's lift in volume, novelty and coverage.

Proposed text:

> **Baseline.** A literature baseline: search ideas that people have already published in community white papers, review articles and workshop reports, found through six documented ADS queries (publication years 2015–2025), screened by a written rule and transcribed into raw cards without adding to them (v0.1: 104 records screened, 23 sources, 40 cards across the three domains). The cards pass through the same four gates, blind to their origin. The comparison is made on coverage of taxonomy cells, on the pass rates at G1, G3 and G4, and on G2 under its definition "tested with equivalent data and method". Two readings are excluded in advance. The size of the baseline is fixed by the selection rule, so no lift in volume is claimed. And because every baseline idea has by construction been *proposed*, G2 results are comparable only as "tested or not"; for pipeline cards we report in addition whether the idea had been proposed before.

### Section 7, metrics table

| Row | Change |
| --- | --- |
| Volume | Keep as an absolute count for the pipeline. Remove the implied comparison with the baseline. |
| Survival per gate | Add: "reported for pipeline cards and for the literature baseline". |
| Novelty precision | Unchanged for pipeline cards. Add a second quantity: share of pipeline cards whose idea had been proposed before (judged against ADS and the baseline cards). |
| Rediscovery recall | Unchanged (register-based). Optional second measure: share of baseline cards that Expand regenerates at the level of claim + observable. |
| Coverage | Add: "compared with the cells filled by the literature baseline". |

### Section 9.1, table row for weeks 1–2

| Column | Current | Proposed |
| --- | --- | --- |
| Human work | Approve schema, seed register entries, obtain ADS API key, two-hour baseline brainstorm | Approve schema (including the `BASE` id prefix), seed register entries, obtain ADS API key, review the baseline selection rule and audit a sample of its screening decisions and cards |
| Agent work | Repository scaffold, card schema and validators, … | add: literature baseline (ADS queries, screening record, transcribed cards) |
| Milestone | M0: repository public, 50 register entries, baseline cards scored | unchanged |

The human time moves from two hours of brainstorming to roughly one hour of audit.

### Appendix B

`baseline/ # two-hour human brainstorm, scored` becomes `baseline/ # literature baseline: queries, screening record, cards, gate logs`.

### Elsewhere in the repository (owner or a later PR)

`tasks/PHASE0.md`, section "Baseline", still describes the brainstorm. `evaluation/metrics.md` and the `evaluation/` row in `README.md` are updated in this PR.

## Why

- **No second person.** A brainstorm by the author alone measures the author. The published literature is the work of many groups.
- **Reproducible.** The queries, the row cut, the screening decision for every record and the passage behind every card are in the repository. Anyone with an ADS key can re-derive the set or challenge a decision.
- **Not contaminated by the pipeline.** See the next section.
- **A stronger comparison.** The question "does the pipeline add anything to what the field has already written down?" is closer to the claim of the paper than "does it beat one person for two hours".

## Contamination note

The first Expand run took place on 2026-11-11 and produced SIEVE-0002..0011 in the cell technosignature / thermal waste heat / spectral excess / snapshot / SPHEREx. The brainstorm had not been done by then. A brainstorm held afterwards by the person who inspects those cards would no longer be independent of the pipeline, and the paper's wording "before the pipeline runs" could not be met.

The literature baseline avoids this: all sources were published between 2015 and 2022, before any SIEVE card existed, and the baseline cards are kept in `evaluation/baseline/cards/`, which Expand does not read.

Two weaker dependencies remain and should be stated in the paper:

1. **The transcriber is an LLM.** The ideas are human, the card text was written by an agent (`transcribed_by` on each card). The rule was to restate the source and add nothing; each card has a locator so that this can be checked. An audit of a sample by the owner is still open.
2. **The generator has read the literature.** The model behind Expand was trained on text that includes these sources, so pipeline cards may re-derive baseline ideas. This does not bias the baseline, but it limits what "novel" means for a pipeline card, which is why the proposal above adds the "proposed before" quantity.

## Open points that affect the wording

The decision points in `evaluation/baseline/README.md` (G2 definition for the baseline, treatment of missing order-of-magnitude estimates at G1, blinding, balance across domains) should be settled before this text goes into the paper.
