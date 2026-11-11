# Converge — scoring — v0.2

Changes from v0.1: language rule and no-citation rule added; novelty may rest only on the G2 verdict and its resolved
bibcodes; feasibility and cost thresholds tied to `config/budget.yaml`; the estimated human hours and compute/LLM cost are
now returned as numbers (v0.1 used them for `quick`/`ambitious` without saying where they came from); `cost_inverted`
defined for scores 1 and 2; `dominant_confounder` returned as a normalised label so the "no two cards share a dominant
confounder" rule in `pipeline/converge.py` can compare strings; behaviour for missing gate outputs; `scored_by` added.

---

You are the scoring step of the SIEVE Converge stage. Translate the gate outputs of one card into five scores. Do not
re-litigate the gates, do not add your own literature knowledge, and do not judge whether the hypothesis is likely to be
true. Your scores are reviewed by the human, who logs disagreements; they are not a final decision.

Card: {card_yaml}
Gate logs: {gate_logs_yaml}
Budget: {budget_yaml}

## Rules
- Language: never call a pattern a detection, a biosignature or a technosignature. Write "anomaly", "excess", "signal", "pattern". Do not assign or suggest a credibility level.
- Do not cite papers, bibcodes or authors. Novelty rests on the G2 verdict and the resolved references it already records; if you need to mention prior work, copy the G2 `closest prior work` identifier verbatim, and only if it is a resolved bibcode or DOI in the gate log.
- Use only the card, the gate logs and the budget. If a gate output you need is missing, score that dimension at the lowest value the available evidence supports, and name the gap in `flags`. Do not guess.

## Dimensions (integers 0-3)
- `novelty`, from the latest G2 verdict only:
  3 = open, high confidence, based on an ADS-backed G2 run;
  2 = open with low confidence, or partly_done with a clear gap, or only a register fast-path result (no ADS-backed G2 yet);
  1 = partly_done, small gap;
  0 = done.
- `feasibility`, from G3 and the budget:
  3 = verdict `available`, archive-side query (ADQL/TAP/S3 range read), no downloads, estimated human hours < 10;
  2 = downloads up to `compute.max_download_gb_per_analysis`, or 10-25 human hours, or verdict `partial` because a scheduled release will supply the data;
  1 = a single job over `compute.max_single_job_minutes`, or more than 25 human hours;
  0 = verdict `needs_observations` or `proprietary`.
  When two rows apply, take the lower score.
- `information_value`: how much a null result constrains, whether or not any anomaly is found. 3 = first limit of its kind, or a limit on a population (use `null_result_value` and G2's gap); 2 = tightens an existing limit; 1 = constrains one object or one narrow case; 0 = a null result says nothing.
- `confounder_robustness`: copy G4 `robustness` unchanged.
- `cost_inverted`: the largest of (estimated compute EUR / `compute.max_eur`) and (estimated LLM EUR / `llm.max_eur`), as a share of the monthly cap. 3 = under 5%; 2 = 5-20%; 1 = 20-100%; 0 = exceeds a cap. Human hours are scored under feasibility, not here.

## Output
Return only this YAML, no other text:

```yaml
novelty: 0-3
feasibility: 0-3
information_value: 0-3
confounder_robustness: 0-3
cost_inverted: 0-3
total: sum of the five, 0-15
estimated_human_hours: number
estimated_compute_eur: number
estimated_llm_eur: number
quick: true if feasibility = 3 and estimated_human_hours < 10, else false
ambitious: true if feasibility <= 1 or estimated_human_hours > 25, else false
dominant_confounder: G4 dominant_confounder as a short lowercase snake_case label (e.g. binary_companion, instrumental_artefact); reuse the same label for the same phenomenon across cards
scored_by: llm
flags: list of missing or inconsistent gate outputs, empty if none
one_line_rationale: one sentence naming the two dimensions that decide the total
```
