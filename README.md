# SIEVE — Systematic Ideation and Evaluation of hypotheses against Existing data

SIEVE treats the search for extraterrestrial life as a **hypothesis-generation problem over data that already exists**. An LLM-based ideation pipeline (Expand–Critique–Converge) generates life-detection hypotheses without regard to data availability, then filters them against the literature (novelty), the public archives (data availability), feasibility and confounders. Survivors are executed as pre-registered analyses with explicit null-result reporting.

The method, the rationale and the three-month plan are in the working paper: [`paper/sieve-v0.1.md`](paper/sieve-v0.1.md) (living version: https://claude.ai/artifact/PwyNvKFqN9Ne1z1AqNLBG7).

## What this repository holds

| Path | Content |
| --- | --- |
| `paper/` | The working paper, versioned (v0.1 = this scaffold; v0.2 after evaluation) |
| `schema/` | JSON schemas for hypothesis cards and register entries, enforced in CI |
| `config/` | Taxonomy grid, archive map (gate G3), budget caps |
| `register/` | Prior archival life searches, one YAML per entry — the novelty oracle for gate G2 |
| `catalogue/cards/` | Hypothesis cards, one YAML each, all statuses (raw → gated → parked/selected → preregistered → executed → reported) |
| `catalogue/gate_logs/`, `catalogue/scores/` | Gate verdicts with reasons; Converge scores, LLM vs human |
| `prompts/` | Versioned prompts for Expand, the four Critique gates and scoring |
| `pipeline/` | Python package: card validation, literature clients, archive helpers, stage runners |
| `prereg/` | One pre-registration per selected card, committed before any data access; immutable after merge |
| `analyses/` | One folder per executed card: scripts, queries as text, environment lock |
| `reports/` | Two-page reports per executed card (null result, limit or anomaly) |
| `evaluation/` | Baseline brainstorm, rediscovery test, metrics (paper Section 7) |
| `tasks/` | Phase checklists for Claude Code / Cowork sessions |

## Credibility ladder (public language is tied to the level)

| Level | Condition | Public term |
| --- | --- | --- |
| L0 | Statistical outlier in one analysis | nothing public |
| L1 | Survives instrument and pipeline artefact checks | nothing public |
| L2 | No known natural explanation after all-wavelength cross-match | *anomaly* (repository only) |
| L3 | Independent group re-analyses and confirms | *anomaly* (preprint) |
| L4 | Independent physical channel shows a coincident signature | *candidate* |
| L5 | Community-reviewed, re-observed, no natural model fits | *candidate biosignature / technosignature* |

**Current status: no anomalies logged above L0.** Nothing in this repository is a detection claim.

## Getting started

```bash
uv sync                                   # creates .venv from pyproject.toml
cp .env.example .env                      # add ADS_API_KEY (https://ui.adsabs.harvard.edu/user/settings/token)
uv run python -m pipeline.cards validate  # validates all cards and register entries against the schemas
uv run python -m pipeline.cards list      # tabular overview of the catalogue
```

Then open `tasks/PHASE0.md` and work the checklist with Claude Code. Conventions for agents are in `CLAUDE.md`.

## Licences

Code: MIT (see `LICENSE`). Catalogue, register, prompts and paper: CC BY 4.0 (see `LICENSE-CC-BY.md`).
