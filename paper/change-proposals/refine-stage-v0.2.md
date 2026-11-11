# Paper change proposal for v0.2: a Refine stage between Critique and Converge

Status: approved by the owner on 2026-11-11 as a design; paper text not yet edited. Proposed by Claude Code (claude-opus-5-5).

## Why

Paper v0.1 runs one way: Expand → Critique (G1–G4) → Converge → Execute. Section 4.3 keeps failing cards "with the reason attached", and G1 returns `revise` with a concrete hint, but nothing acts on that hint. The provenance field `parent_card` and the phrase "applied to a cell or to an existing card" (Section 4.2) point at revision, yet no step is specified. Section 2.3 cites Co-Scientist's cycle of generation, critique and refinement without adopting it.

The gap showed up on the first gated cards. Both cards run through G1 so far (SIEVE-0002, SIEVE-0006) received `revise`. SIEVE-0006 has a fixable method error: it builds the observed luminosity from Gaia XP + 2MASS + SPHEREx, which adds the re-radiated heat back in and cancels the deficit it is meant to measure. The error was found only because the owner picked that card for a closer look. Repair by hand on selected cards is not a method and breaks comparability between cards.

## Proposed text (new Section 4.4, Converge becomes 4.5)

### 4.4 Stage 3: Refine

Refine gives each repairable card exactly one revision round before Converge.

- **Trigger (rule-based).** G1 `revise`; or G4 confounder robustness ≤ 1 with named exclusion tests; or G3 `partial` with a concrete remedy. Cards with G1 `fail` or G2 `done` are not refined; those verdicts are rejections, not repair notes.
- **Operation.** An LLM with its own prompt (`refine-vX`), different from the generator and the gate critics, receives the card and its gate logs and writes a new card with `provenance.parent_card` set to the original and `operator: refine`. The original is parked with the reason `refined as SIEVE-NNNN`.
- **Constraint.** Refine may repair the method, the measured quantity, the sample, the stated sensitivity and the confounder plan. It may not change the core claim or the taxonomy cell; a card that needs that is a new idea for the next Expand pass, not a repair.
- **Re-gating.** The refined card runs through all four gates again, including G2, because a changed method can change novelty.
- **Limit.** One round per card. A refined card that still gets `revise` goes to Converge with its verdicts or is parked; it is not refined again.

## Changes elsewhere

- **Section 3, RQ1.** Survival is reported twice: first-pass survival (G1–G4 on the Expand output) and post-Refine survival. The difference, and the share of cards that needed Refine, are results in their own right.
- **Section 7 (evaluation).** The pipeline-versus-baseline comparison uses first-pass verdicts only; literature-baseline cards are not refined. Refine adds metrics: share of cards refined, share of refined cards whose verdicts improve, cost per refined card, and an owner audit of a sample of before/after pairs.
- **Section 10 (risks).** New risk: *gate gaming*. A reviser that sees the critics' wording can learn to satisfy the critics rather than fix the physics. Mitigation: a separate prompt, one round only, a constraint on claim and cell, and a human audit of before/after pairs on a sample.
- **Section 9.3 (budget).** Measured 2026-11-11: about 0.05 EUR per Expand card and about 0.42 EUR per card for G1–G4. A refined card costs about 0.47 EUR more. At 400 cards with half refined that adds about 95 EUR, which fits under the 150 EUR monthly cap only if Refine and the first gate pass are not in the same month as other large runs; measure the refine share on the first 50 cards before scaling.
- **Section 9.1 (plan).** Weeks 3–4 become Expand + Critique + Refine.
- **Appendix A (schema).** `provenance.operator` gains `refine`; parked reason convention `refined as SIEVE-NNNN`.

## First test

SIEVE-0002 and SIEVE-0006 (both G1 `revise`). The owner-facing explanation of SIEVE-0006 written on 2026-11-11 names the fix (measure the deficit from the photosphere only; state that 1–5 µm sees only hot envelopes; exclude starspots and isochrone systematics first). It serves as a check on whether Refine finds the same repair on its own; it is not given to the reviser.
