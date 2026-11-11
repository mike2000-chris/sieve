# Evaluation metrics (paper Section 7)

| Metric | Definition | Target at month 3 | Value | Measured on |
| --- | --- | --- | --- | --- |
| Volume | Raw cards generated in cycle 1 | 300-500 | | |
| Survival per gate | Fraction passing G1, G2, G3, G4 | reported | | |
| Novelty precision | Share of G2 "open" confirmed by human audit (10% sample) | >= 80% | | |
| Rediscovery recall | Share of withheld register entries regenerated blind | >= 50% | | |
| Coverage | Taxonomy cells with >= 1 card passing G1 | reported | | |
| Scorer agreement | Cohen's kappa LLM vs human on the Converge set | reported | | |
| Execution yield | Executed cards with a complete report | 1-3 | | |
| Reproducibility | Executed analyses re-run clean-room | 100% | | |
| Expert review | External researchers rate top 20 cards | 2-3 reviewers | | |
| Cost | Human hours and euros per surviving / executed card | reported | | |

## Survival at G2
Owner decision 2026-11-11, prompt `critique-g2-novelty-v0.3`:

| G2 verdict | Meaning | Survival metric |
| --- | --- | --- |
| `open` | No listed work tests the claim, including the case where the card's archive or method measures a quantity earlier searches could not measure | passes |
| `partly_done` | The same measurement exists and the card repeats it on newer or larger data, or a closely related claim was tested | passes |
| `done` | The same claim was tested with equivalent data and method | fails |

- A paper that only proposes the idea (white paper, review, the card's own source) is not a test and supports neither `done` nor `partly_done`.
- `done` never parks a card automatically. The verdict is written to the card's `novelty` block and to the gate log; moving a card to `parked` remains a separate `pipeline.cards set-status` step taken by a person. The G2 survival fraction is therefore computed from `novelty.status`, not from `status`.
- Cards without a verdict (`unchecked`, or a run logged as `error` or `unsupported`) are not in the denominator.
- Verdicts from v0.2 and v0.3 are not pooled: v0.2 sent every new-archive card to `partly_done`. The prompt version is in `novelty.judged.prompt_version`.
- Novelty precision (table above) is unchanged: it is the share of `open` verdicts a human audit confirms.

## Baseline
`evaluation/baseline/`: literature baseline (owner decision 2026-11-11, replaces the two-hour brainstorm). Published search ideas from white papers, reviews and workshop reports, found through documented ADS queries and transcribed as raw cards `BASE-NNNN` (`provenance.generator_model: human-literature`), gated with the same prompts. Selection rule, how to read the comparison (no volume lift; G2 as "tested", not "proposed") and open decisions: `evaluation/baseline/README.md`.

## Rediscovery test protocol
Register entries with `withheld_for_rediscovery_test: true` are hidden from Expand. Matches are judged on claim + observable by an LLM judge, then confirmed by the owner. Output: recall and the list of what the pipeline could not think of (`evaluation/rediscovery/misses.md`).
