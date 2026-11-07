# CLAUDE.md — working conventions for Claude Code and Cowork in the SIEVE repository

## What this project is
SIEVE generates life-detection hypotheses with an LLM pipeline (Expand → Critique → Converge → Execute) and filters them against the literature, the public astronomical archives and feasibility. Read `paper/sieve-v0.1.md` Sections 4, 5 and 9 before changing the pipeline. The owner is Carsten Mielke; talk to him in German, write code, comments, cards and reports in English.

## Non-negotiable rules
1. **No detection language.** Nothing produced here calls anything a detection, a biosignature or a technosignature. Use the credibility ladder in `README.md`: *anomaly* up to L2, *candidate* from L4, and only the owner moves a card above L1.
2. **Novelty evidence = resolved bibcodes only.** A reference counts in gate G2 only if it resolved through the ADS API (or a DOI through OpenAlex). Never write a citation from memory into a card, a register entry or the paper.
3. **Pre-registration is immutable.** Files in `prereg/` are not edited after merge; changes go into a dated `## Addendum` section appended at the end.
4. **Cards change status only through `pipeline/cards.py`**, which writes a gate log. Do not hand-edit `status`.
5. **Archive-side first.** Prefer ADQL/TAP queries and S3 range reads to downloads. Nothing larger than result tables lands in the repository; raw data stay out (`.gitignore`).
6. **Budget caps** in `config/budget.yaml` are hard limits. Stop and report when a run would exceed them.
7. **Provenance on everything.** Every card and gate log records model, prompt version, operator and date.
8. **Null results are first-class.** An executed card without a report is unfinished; a null result gets the same two-page report as an anomaly (`reports/TEMPLATE.md`).

## How to work
- Start a session by reading `tasks/PHASE*.md` for the current phase; tick items there as they finish.
- Agents open branches and pull requests; the owner merges. Commit messages: `area: what changed` (e.g. `register: add Tellis & Marcy 2017 laser search`).
- Run `uv run python -m pipeline.cards validate` before every commit; CI runs it too.
- Secrets live in `.env` (never committed). `ADS_API_KEY` is required for gate G2.
- Human time is ~4 h/week. Leave status notes in `tasks/STATUS.md` rather than questions; batch questions for the weekly review slot.
- When something cannot be done here (telescope time, proprietary data, a judgement about anomaly level), say so in the status note and park the card with the reason.

## Layout (see README for the table)
`config/` taxonomy + archives + budget · `schema/` JSON schemas · `register/` prior searches · `catalogue/` cards, gate logs, scores · `prompts/` versioned prompts · `pipeline/` code · `prereg/` `analyses/` `reports/` per executed card · `evaluation/` metrics · `paper/` the paper.

## Current phase
Phase 0 (Setup), weeks 1–2 (16–29 Nov 2026). Milestone M0: repository public, 50 register entries, baseline cards scored. Checklist: `tasks/PHASE0.md`.
