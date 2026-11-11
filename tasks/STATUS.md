# Status notes

Newest first. One entry per agent session or weekly review. Questions for the owner go under **Open questions**, not into chat.

## 2026-11-11 (later) — owner review: decisions, merges, four agent work packages
Operator: Claude Code (claude-opus-5-5), dialogue with the owner. PRs #4, #5, #6 merged by the agent at the owner's request.
**Owner decisions**
- Register: `REG-boyajian-star-kepler-dips-2016-2018` and `REG-alh84001-1996` → `outcome: contested`; Zackrisson 2018 stays `artificial_structure_geometry`/`astrometry`; Viking LR stays `time_series`.
- `REG-cody-tess-dyson-transits-2024` rewritten against the AAS 243 abstracts 2024AAS...24335603G (Giles, Cody et al.) and 2024AAS...24310902Y (Yaptangco, Cody, Giles); the unsourced Hephaistos II claim is dropped; outcome `candidates_unconfirmed`, confounders taken from the abstract. Register now 50/50 resolved.
- Empty `confounders_found` stay empty with a `source names none` comment (3 entries); not filled from memory.
- `expand-v0.2` accepted as is; owner inspection ticked.
- Gaia archive account: owner creates it (ESA Cosmos) and adds `GAIA_USER`/`GAIA_PASSWORD` to `.env`; login support being built.
- `eur_per_usd` stays at the 0.87 assumption until a bill arrives.
- **Baseline**: the two-hour brainstorm is replaced by a literature baseline (published human-proposed hypotheses, resolved bibcodes only). Paper Section 7 / 9.1 change proposed for v0.2, not edited. Note: Expand already ran before any baseline, so a brainstorm baseline would have been contaminated for the SPHEREx waste-heat cell.
- Sub-agent models: Fable 5.2 for judgement-heavy work, Sonnet 5.5 for scaffolding.

**Agent work packages started (one branch + PR each)**
- `critique/g2-ads-judge` (Fable 5.2): G2 with ADS/OpenAlex retrieval and LLM judge, G2 prompt review, cost per card; cap 3 EUR.
- `critique/g1-g3-g4-scaffold` (Sonnet 5.5): G1/G3/G4 in `pipeline/gates/`, prompt review v0.2, smoke run on 2 cards; cap 2 EUR.
- `archives/gaia-login` + `prompts/score-v0.2` (Sonnet 5.5): optional authenticated Gaia login in `adql_run.py`; score prompt review.
- `evaluation/literature-baseline` (Fable 5.2): selection rule, baseline cards in `evaluation/baseline/cards/`, paper change note; no API spend.

### Open questions
- Literature baseline vs G2: published ideas may be judged "not novel" if G2 asks "proposed?" rather than "tested?". The baseline agent documents how to read the comparison; owner to confirm the definition.

## 2026-11-11 — register at 50, DR4 day-one queries, Expand + G2 fast path
Operator: Claude Code (claude-opus-5-5). Three PRs, to be merged in this order: #4 → #5 → #6 (#6 is built on #4).
- **PR #4 `register/phase0-expansion`**: 39 new entries, register at 50 (M0 target). Written by three parallel sub-agents from ADS abstracts; all 91 register bibcodes re-resolved via ADS in one batch afterwards (0 missing). No detection language found.
- **PR #5 `analyses/dr4-day-one-queries`**: three DR4 queries against the draft DR4 data model (CU9, 2026-05-20), DR3 dry runs (35,142 / 4,460 / 17,285 rows), new runner `pipeline/archives/adql_run.py` (COUNT → random_index chunks < 40k → rows == COUNT). Key fact: DR4 epoch astrometry/photometry are DataLink products, not TAP tables. Release-day checklist in `analyses/dr4-day-one/README.md`. Gaia archive maintenance 12 Nov 16:00 CET (1 h); sync queue was saturated today (503), async worked.
- **PR #6 `pipeline/expand-one-cell`**: `pipeline/expand.py` end to end with prompt `expand-v0.2` (structured JSON output; v0.1 kept). Budget check before every call, run log `evaluation/costs/llm_runs.jsonl`. 10 cards SIEVE-0002..0011 in technosignature/thermal_waste_heat/spectral_excess/snapshot/spherex: **0.498 EUR total, 0.050 EUR/card** (Expand only). First call returned 7 of 10 cards, one with empty claim/mechanism (rejected by the schema check) → top-up logic added; the prompt now lists cards already in the cell to avoid repeats.
- G2 register fast path (`uv run python -m pipeline.critique g2-fast --all-raw`): all 11 cards hit Hephaistos II / Ĝ / Carrigan, as expected for this cell. Logged as `G2-register`; `novelty.status` untouched (ADS judge still to build).
- Withheld register entries (2020+) are never shown to Expand (`evaluation/metrics.md`); hence Hephaistos I/II do not appear in the prompt for this cell.

### Open questions
- Please inspect SIEVE-0002..0011 by hand (checklist item); tone/constraints of `expand-v0.2` ok?
- Register judgement calls: Boyajian dips `confirmed_natural` vs `contested`; ALH84001 `confirmed_natural`; Zackrisson 2018 as `artificial_structure_geometry`/`astrometry`; Viking LR observable `time_series`; 4 entries without `confounders_found`.
- EUR/USD rate in `config/budget.yaml` (`eur_per_usd: 0.87`) is an assumption; replace with the billed rate.
- Still open from 2026-11-07: Gaia archive account for DR4 day one; `REG-cody-tess-dyson-transits-2024`.

## 2026-11-07 (later) — archive smoke tests
Operator: Claude Code (claude-opus-5-5). Branch `archives/smoke-tests`.
- All five Phase 0 smoke tests pass: `pipeline/archives/smoke.py`, records in `analyses/smoke-tests-phase0/results/smoke.json`, access paths/latency/licence in `config/archives.yaml` (`smoke_test` blocks).
- Gaia: anonymous async results are silently capped at 50,000 rows (first run returned 50,000 of 60,235). Now chunked by RA and checked against COUNT(*). **Relevant for the DR4 day-one queries**: every large query needs a count check, or an authenticated Gaia archive account (limits not tested).
- IRSA: `JOIN ... ON CONTAINS` with TAP_UPLOAD is rejected; `DISTANCE()` returns arcsec, not degrees. Upload cross-match of 60k positions took 18 min, Gaia's precomputed `allwise_best_neighbour` 3 s.
- MAST: portal search failed/hung (34 min) today; S3 mirror `stpubdata` works in 1.5 s and is now the primary path.
- Public status page (claude.ai artifact, private until shared): https://claude.ai/artifact/HYHzpNwzBB73bM1ZDKyVaR
- `main` protected by ruleset `protect-main` (no force push/deletion, PR + `validate` check required, admin bypass). Owner: dismiss the GitHub banner.

### Open questions
- Should SIEVE register a Gaia archive account (higher row limits, persistent user tables for DR4 day one)? Needs the owner's credentials.

## 2026-11-07 — repo live, seed bibcodes resolved
Operator: Claude Code (claude-opus-5-5), session with owner. Branch `register/resolve-seed-bibcodes`.
- Repository public at https://github.com/mike2000-chris/sieve; gh token needed the `workflow` scope for the first push. CI `validate` green on `main`.
- `uv` installed via Homebrew; `uv sync` done; `.env` created; ADS key works (resolve, search and NOT FOUND path tested).
- New tool `pipeline/literature/resolve_register.py`: resolves arXiv IDs / DOIs from `urls` through ADS, or re-resolves explicitly chosen bibcodes (`--set`); dry run by default; prints first author/year against the entry for a plausibility check.
- 10 of 11 seed entries now `bibcodes.status: resolved`. Bibcodes for Ma 2023, Madhusudhan 2023/2025, Greaves 2021, Mogul 2021 were chosen from ADS search results (author + year + title), not from identifiers in `urls`.
- Flagged by the year check but accepted (multi-paper entries, author and title match): VASCO `2022MNRAS.515.1380S` (entry year 2019), Venus `2024arXiv240913438C` (entry year 2020; still an arXiv record, no journal version in ADS).
- Note: Venus phosphine primary paper is `2021NatAs...5..655G` (online 2020, issue 2021).

### Open questions
- `REG-cody-tess-dyson-transits-2024`: no ADS record of a Cody TESS variability analysis of the seven Hephaistos II objects. Closest ADS hits are 2024AAS...24335603G (TESS megastructure anomaly search, Cody co-author) and 2024AAS...24310902Y; neither states the claimed result. The only source is a Physics World article. Keep as `to_resolve` (not usable in G2), rewrite against one of the AAS abstracts, or drop?
- `REG-ren-2024-contamination` resolves to the RNAAS note `2024RNAAS...8..145R`. The entry also cites e-MERLIN/e-VLBI follow-up of candidate G, which may be in a later paper; check whether a second bibcode belongs here.
- `REG-k2-18b-dms-2025` lists "Jordan et al. (2026) and others": only Jordan 2026 is resolved among the rebuttals. Add further rebuttal papers?

## 2026-11-07 — scaffold created
- Repository scaffold generated from paper v0.1 (Appendix A/B): schema, config, 11 register seeds, example card, prompts v0.1, pipeline skeleton, templates, CI.
- Next: `tasks/PHASE0.md`, starting with git init / GitHub repo, `uv sync`, ADS key.

### Open questions
- ~~GitHub owner/repository name~~ resolved: `mike2000-chris/sieve`.
