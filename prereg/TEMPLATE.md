# Pre-registration — SIEVE-XXXX — <title>

**Status:** draft | committed (immutable after merge; later changes go into `## Addendum` at the end)
**Card:** `catalogue/cards/SIEVE-XXXX.yaml` (version N) · **Committed on:** YYYY-MM-DD · **Author:** 

## 1. Claim under test
One falsifiable sentence, copied from the card.

## 2. Data
Exact archives, tables, releases and selection criteria. Paste the exact queries (ADQL/TAP/S3 paths) or link to the query files under `analyses/SIEVE-XXXX/queries/`.

## 3. Analysis plan
Steps in order; statistics to be computed; software and versions.

## 4. Success and failure criteria
- Detection threshold (e.g. significance, effect size) decided now.
- False-positive budget and how it is spent (e.g. number of tests, correction).
- What result would count as a null result, and what upper limit it would yield.

## 5. Confounders and the checks that exclude them
From gate G4. Each confounder with its exclusion test and data.

## 6. Anomaly handling
Which checks move an outlier from L0 to L1 and from L1 to L2 (credibility ladder). Who decides.

## 7. Resources
Estimated human hours, compute, cost against `config/budget.yaml`.

## Addendum
Dated entries only; never edit sections 1-7 after merge.
