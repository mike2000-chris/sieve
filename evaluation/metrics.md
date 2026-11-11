# Evaluation metrics (paper Section 7)

| Metric | Definition | Target at month 3 | Value | Measured on |
| --- | --- | --- | --- | --- |
| Volume | Raw cards generated in cycle 1 | 300-500 | | |
| Survival per gate | Fraction passing G1, G2, G3, G4; reported twice, first pass and post-Refine (section Refine) | reported | | |
| Refine share | Share of first-pass cards that meet the Refine trigger and are refined | reported | | |
| Refine improvement | Share of refined cards whose gate verdicts improve over the parent's (section Refine) | reported | | |
| Refine audit | Owner audit of a sample of before/after pairs: physics repaired, not critic wording echoed | reported | | |
| Novelty precision | Share of G2 "open" confirmed by human audit (10% sample) | >= 80% | | |
| Rediscovery recall | Share of withheld register entries regenerated blind | >= 50% | | |
| Coverage | Taxonomy cells with >= 1 card passing G1 | reported | | |
| Scorer agreement | Cohen's kappa LLM vs human on the Converge set | reported | | |
| Execution yield | Executed cards with a complete report | 1-3 | | |
| Reproducibility | Executed analyses re-run clean-room | 100% | | |
| Expert review | External researchers rate top 20 cards | 2-3 reviewers | | |
| Cost | Human hours and euros per surviving / executed card; euros per refined card (Refine call plus second gate pass) | reported | | |

## Survival at G2
Owner decisions 2026-11-11, prompts `critique-g2-novelty-v0.3` and `v0.4` (same rules; v0.4 replaced the examples):

| G2 verdict | Meaning | Survival metric |
| --- | --- | --- |
| `open` | No listed work tests the claim, including the case where the card's archive or method measures a quantity earlier searches could not measure | passes |
| `partly_done` | The same measurement exists and the card repeats it on newer or larger data, or a closely related claim was tested | passes |
| `done` | The same claim was tested with equivalent data and method | fails |

- A paper that only proposes the idea is not a test and supports neither `done` nor `partly_done`. This covers white papers, reviews, roadmaps, the card's own source, and forecast or concept papers (owner decision 2026-11-11): a test is an analysis of observational data that could have shown the pattern.
- `done` never parks a card automatically. The verdict is written to the card's `novelty` block and to the gate log; moving a card to `parked` remains a separate `pipeline.cards set-status` step taken by a person. The G2 survival fraction is therefore computed from `novelty.status`, not from `status`.
- Cards without a verdict (`unchecked`, or a run logged as `error` or `unsupported`) are not in the denominator.
- Verdicts from different prompt versions are not pooled. v0.2 sent every new-archive card to `partly_done`. v0.3 illustrated the new-quantity rule with an example from the taxonomy cell of all cards judged with it (SIEVE-0001..0008), so those verdicts are superseded by a v0.4 run. The prompt version is in `novelty.judged.prompt_version`.
- Novelty precision (table above) is unchanged: it is the share of `open` verdicts a human audit confirms.

## Refine
Design: paper change proposal `refine-stage-v0.2` (approved 2026-11-11); code `pipeline/refine.py`, prompt `prompts/refine-v0.1.md`. A refined card is a new card (`provenance.operator: refine`, `provenance.parent_card`); its parent is parked with the reason `refined as SIEVE-NNNN`. One round per card.

Card sets used below, all from the catalogue (`SIEVE-NNNN`):
- *First-pass cards*: cards written by Expand or by hand, i.e. every card whose `provenance.operator` is not `refine`. Parents parked as `refined as ...` stay in this set with the verdicts they received.
- *Refined cards*: cards with `provenance.operator: refine`.
- *Post-Refine set*: first-pass cards that were not refined, plus the refined cards in place of their parents.

| Metric | Definition |
| --- | --- |
| First-pass survival | Survival per gate (G1 `pass`; G2 `open` or `partly_done`; G3 `available` or `partial`; G4 reported as the robustness distribution) over first-pass cards, from the verdicts given to the Expand output. A parent's verdicts are read from its own card and gate log, never from its refined copy. |
| Post-Refine survival | The same fractions over the post-Refine set. Reported next to first-pass survival; the difference is a result in its own right. |
| Share refined | Refined cards / first-pass cards that went through all four gates. Also reported: the share that met the trigger (`python -m pipeline.refine --eligible`) and, per trigger rule, how often it fired (gate-log event `refine`, field `triggers`). |
| Share improved | Share of refined cards for which at least one of these holds against the parent's latest verdicts and none got worse: G1 `revise` → `pass`; G4 robustness higher; G3 `partial` → `available`. Worse means G1 → `fail`, G4 robustness lower, G3 → `needs_observations` or `proprietary`, or G2 → `done`. Reported with the full before/after table, not only the share. |
| Rejected outputs | Refine calls whose output was rejected by a code guard (taxonomy cell changed, citation in the card text, schema), from gate-log events `refine_rejected`. Reported as a count and as cost. |
| Cost per refined card | Euros for the Refine call (`stage: refine` in `evaluation/costs/llm_runs.jsonl`, rejected calls included) plus the second pass through G1-G4 of the refined card, divided by the number of refined cards. Human hours for the audit are reported separately. |
| Owner audit of before/after pairs | The owner reads a sample of parent/refined pairs (all pairs up to 10, then 20 per cent) with the `changes` and `open_uncertainties` lists from the refined card's gate log and answers per pair: (a) is the fault the gates named repaired in the physics, or does the card only repeat the critics' wording (*gate gaming*, proposal Section 10)? (b) is the subject of the claim unchanged? (c) did the revision invent a number? Result: share of pairs judged a real repair. |

Rules:
- **Baseline comparison on first pass only.** The pipeline-versus-baseline comparison uses first-pass verdicts on both sides. Literature-baseline cards (`BASE-NNNN`) are never refined: `pipeline.refine` refuses BASE ids, also in a dry run, and `pipeline.cards validate` fails on a baseline card with `operator: refine`.
- **Trigger.** G1 `revise`; or G4 robustness <= 1 with named exclusion tests; or G3 `partial` with a concrete remedy (the judge named a gap on at least one archive and gave an access plan). Not refined: G1 `fail`, G2 `done`, cards without all four verdicts, refined cards and their parents.
- **What Refine may not change** is enforced in code for the taxonomy cell (domain, signature class, observable, timescale: the output is rejected if they come back changed, and the new card copies them from the parent). The subject of the claim cannot be checked by a rule; it is question (b) of the owner audit.
- **Re-gating.** A refined card starts as `raw` with `novelty: unchecked` and no `physics` or `scores` block and runs through all four gates again, G2 included. Gate prompts see it blind like any other card (no id, no provenance), so the critics cannot tell a refined card from a first-pass card.
- **Not pooled.** Verdicts of a refined card are never added to the first-pass numbers, and a parent parked as `refined as ...` is not counted as a gate failure in `status`-based counts.

## Baseline
`evaluation/baseline/`: literature baseline (owner decision 2026-11-11, replaces the two-hour brainstorm). Published search ideas from white papers, reviews and workshop reports, found through documented ADS queries and transcribed as raw cards `BASE-NNNN` (`provenance.generator_model: human-literature`), gated with the same prompts. Selection rule, how to read the comparison (no volume lift; G2 as "tested", not "proposed") and open decisions: `evaluation/baseline/README.md`.

## Rediscovery test protocol
Register entries with `withheld_for_rediscovery_test: true` are hidden from Expand. Matches are judged on claim + observable by an LLM judge, then confirmed by the owner. Output: recall and the list of what the pipeline could not think of (`evaluation/rediscovery/misses.md`).
