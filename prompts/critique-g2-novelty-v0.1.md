# Critique gate G2 — novelty — v0.1

Task A (query generation). From the card below, write 3 to 5 literature search queries (each 3-8 words, no quotes, no boolean operators) that would find prior work testing the same claim with the same or similar observable. Include one query phrased in the vocabulary of the SETI/technosignature community and one in the vocabulary of mainstream astrophysics for the same phenomenon.

Card: {card_yaml}

Return YAML: `queries: [..]`.

---

Task B (judgement). You receive the card, the closest register entries, and up to 10 papers retrieved from NASA ADS / OpenAlex for the queries (title, year, abstract, bibcode). Decide:
- `done`: the same claim was tested with equivalent data and method.
- `partly_done`: the same claim was tested, but with different data, a different observable, a smaller sample, or an older release; or a closely related claim was tested.
- `open`: no retrieved work tests this claim.

Rules: only papers with a bibcode in the retrieved list may be cited; never add a reference from memory. For each cited paper state the `relation` in one clause. If the retrieved list is empty or irrelevant, say so and return `open` with `confidence: low`.

Return YAML: `status`, `confidence` (low | medium | high), `closest_prior: [{bibcode, relation}]`, `what_would_make_it_open` (one sentence, if partly_done or done).
