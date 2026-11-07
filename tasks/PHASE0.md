# Phase 0 — Setup (weeks 1–2, 16–29 Nov 2026)

Milestone **M0**: repository public, 50 register entries, baseline cards scored. Paper reference: Section 9.1.

## Repository and tooling
- [x] `git init`, first commit of this scaffold, create the public GitHub repository (`gh repo create sieve --public --source=. --push`)
- [x] `uv sync`; `uv run python -m pipeline.cards validate` passes
- [x] Obtain an ADS API key, put it in `.env`, run `uv run python -m pipeline.literature.ads 2024MNRAS.531..695S` to confirm bibcode resolution works
- [x] Enable the GitHub Actions workflow (`.github/workflows/validate.yml`) and confirm it passes on `main`
- [x] Add `tasks/STATUS.md` and write the first status note

## Register (novelty oracle)
- [ ] Resolve bibcodes for the 11 seed entries (`bibcodes.status: to_resolve` → `resolved`)
  - 10/11 resolved via `pipeline/literature/resolve_register.py`; `REG-cody-tess-dyson-transits-2024` open (no ADS record found, see STATUS 2026-11-07)
- [ ] Add the "entries to add in week 1–2" from paper Section 6 (laser searches, Boyajian's star, Clarke exobelt, lunar/Martian artefact searches, Galileo Earth-as-exoplanet, Gaia astrometric anomaly searches, Kepler artificial-transit searches, pollutant biosignatures) — target 50 entries
- [ ] For each entry fill `lesson` and `confounders_found`; these feed the negative-space operator

## Archive access smoke tests (gate G3 map)
- [x] Gaia DR3 ADQL query via `astroquery.gaia` (count sources with G < 12 within 100 pc) — record runtime
  - all five smoke tests: `pipeline/archives/smoke.py`, results in `analyses/smoke-tests-phase0/` (2026-11-07)
- [x] IRSA AllWISE TAP query for the same sample; cross-match by position
- [x] `lightkurve` download of one TESS light curve
- [x] NASA Exoplanet Archive TAP query (planets with equilibrium temperature 200–350 K)
- [x] SPHEREx QR S3 range read (`aws s3 ls --no-sign-request s3://nasa-irsa-spherex/`)
- [x] Record each archive's actual access path, latency and licence in `config/archives.yaml`
- [ ] Prepare 3 Gaia DR4 queries (astrometric anomalies, periodic photometry, anomalous accelerations) as text files in `analyses/dr4-day-one/` for 2 Dec 2026

## Baseline
- [ ] Owner: two-hour human-only brainstorm, write results as raw cards with `provenance.generator_model: human`
- [ ] Run the four gates on the baseline cards; keep the gate logs as `evaluation/baseline/`

## Prompts and pipeline
- [ ] Review `prompts/*-v0.1.md`; adjust tone and constraints; bump versions on change
- [ ] Implement `pipeline/expand.py` end to end for one taxonomy cell (10 cards) and inspect output by hand
- [ ] Implement gate G2 against the register first (fast path), then ADS/OpenAlex queries
- [ ] Measure cost per card (tokens, €) and write it into `config/budget.yaml` as `measured_cost_per_card`

## Exit criteria
- [ ] M0 reached; owner signs off in `tasks/STATUS.md`; Phase 1 checklist (`tasks/PHASE1.md`) created from paper Section 9.1
