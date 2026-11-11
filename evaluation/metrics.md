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

## Baseline
`evaluation/baseline/`: literature baseline (owner decision 2026-11-11, replaces the two-hour brainstorm). Published search ideas from white papers, reviews and workshop reports, found through documented ADS queries and transcribed as raw cards `BASE-NNNN` (`provenance.generator_model: human-literature`), gated with the same prompts. Selection rule, how to read the comparison (no volume lift; G2 as "tested", not "proposed") and open decisions: `evaluation/baseline/README.md`.

## Rediscovery test protocol
Register entries with `withheld_for_rediscovery_test: true` are hidden from Expand. Matches are judged on claim + observable by an LLM judge, then confirmed by the owner. Output: recall and the list of what the pipeline could not think of (`evaluation/rediscovery/misses.md`).
