# Prompts

Versioned prompt files. A card's `provenance.prompt_version` points at the file that generated or judged it, so bump the version in the filename on every change and keep old versions. Placeholders in `{braces}` are filled by `pipeline/`.

## Current versions

| Stage | Current | Kept for reference |
| --- | --- | --- |
| Expand | `expand-v0.2.md` | `expand-v0.1.md` |
| Critique G1, G3, G4 | `critique-g1-physics-v0.2.md`, `critique-g3-data-v0.2.md`, `critique-g4-confounders-v0.2.md` | `critique-g*-v0.1.md` |
| Critique G2 | `critique-g2-novelty-v0.4.md` | `critique-g2-novelty-v0.3.md`, `critique-g2-novelty-v0.2.md`, `critique-g2-novelty-v0.1.md` |
| Refine | `refine-v0.1.md` | |
| Converge (scoring) | `score-v0.2.md` | `score-v0.1.md` |

`critique-g2-novelty-v0.3` (2026-11-11, owner decisions): `open` when the card's archive or method measures a quantity earlier searches could not measure, `partly_done` when the same measurement is repeated on newer or larger data or a closely related claim was tested, `done` when the same claim was tested with equivalent data and method; a paper that only proposes the idea is not a test; no verdict parks a card. The version is set in `pipeline/critique.py` (`G2_PROMPT_VERSION`).

`critique-g2-novelty-v0.4` (2026-11-11, owner decision on PR #14): rules as in v0.3; the examples for "new quantity" versus "same measurement on newer data" now come from radio transmissions, atmospheric chemistry and in-situ composition, so the prompt names no instrument or signature class of the current catalogue.

`score-v0.2` (2026-11-11, review without LLM calls): adds the language and no-citation rules; novelty only from the G2 verdict; feasibility and cost thresholds tied to `config/budget.yaml`; returns estimated human hours, compute and LLM cost as numbers; defines `cost_inverted` 1-2; normalised `dominant_confounder` label; `scored_by: llm` and `flags`. No score-prompt version is hard-coded in `pipeline/`; the scorer that will call it must write `v0.2` into `provenance.prompt_version`.

`refine-v0.1` (2026-11-11, paper change proposal `refine-stage-v0.2`): reviser prompt, separate from generator and critics. Input: the card blind and without earlier gate output, plus the latest G1, G3 and G4 findings; no G2 output. May repair method, measured quantity, sample, stated sensitivity, archives and confounder plan; may not change the subject of the claim or the taxonomy cell (the cell is also enforced in `pipeline/refine.py`). Returns the revised card fields, a `changes` list (field, what changed, which finding it answers, or `not_adopted` with a reason) and `open_uncertainties`. The version is set in `pipeline/refine.py` (`PROMPT_VERSION`).
