# Status notes

Newest first. One entry per agent session or weekly review. Questions for the owner go under **Open questions**, not into chat.

## 2026-11-07 (later) — archive smoke tests
Operator: Claude Code (claude-opus-5-5). Branch `archives/smoke-tests`.
- All five Phase 0 smoke tests pass: `pipeline/archives/smoke.py`, records in `analyses/smoke-tests-phase0/results/smoke.json`, access paths/latency/licence in `config/archives.yaml` (`smoke_test` blocks).
- Gaia: anonymous async results are silently capped at 50,000 rows (first run returned 50,000 of 60,235). Now chunked by RA and checked against COUNT(*). **Relevant for the DR4 day-one queries**: every large query needs a count check, or an authenticated Gaia archive account (limits not tested).
- IRSA: `JOIN ... ON CONTAINS` with TAP_UPLOAD is rejected; `DISTANCE()` returns arcsec, not degrees. Upload cross-match of 60k positions took 18 min, Gaia's precomputed `allwise_best_neighbour` 3 s.
- MAST: portal search failed/hung (34 min) today; S3 mirror `stpubdata` works in 1.5 s and is now the primary path.
- Public status page (claude.ai artifact, private until shared): https://claude.ai/artifact/HYHzpNwzBB73bM1ZDKyVaR

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
