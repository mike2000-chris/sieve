# Prompts

Versioned prompt files. A card's `provenance.prompt_version` points at the file that generated or judged it, so bump the version in the filename on every change and keep old versions. Placeholders in `{braces}` are filled by `pipeline/`.

## Current versions

| Stage | Current | Kept for reference |
| --- | --- | --- |
| Expand | `expand-v0.2.md` | `expand-v0.1.md` |
| Critique G1-G4 | `critique-g*-v0.1.md` | |
| Converge (scoring) | `score-v0.2.md` | `score-v0.1.md` |

`score-v0.2` (2026-11-11, review without LLM calls): adds the language and no-citation rules; novelty only from the G2 verdict; feasibility and cost thresholds tied to `config/budget.yaml`; returns estimated human hours, compute and LLM cost as numbers; defines `cost_inverted` 1-2; normalised `dominant_confounder` label; `scored_by: llm` and `flags`. No score-prompt version is hard-coded in `pipeline/`; the scorer that will call it must write `v0.2` into `provenance.prompt_version`.
