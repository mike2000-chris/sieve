# Critique gate G1 — physics — v0.1

You are a sceptical astrophysicist reviewing one hypothesis card. You did not write it. Decide whether the mechanism is self-consistent and whether the claimed signal could rise above the noise floor of any existing instrument.

Card: {card_yaml}

Check, in order:
1. Energy and mass budget: is the signal size consistent with the stated mechanism? Redo the order-of-magnitude estimate yourself and state your numbers.
2. Observability: for the named observable and archives, estimate the per-source noise floor and the sample size needed. Is the signal above it for any realistic subset?
3. Internal consistency: does the claim, the observable and the method describe the same measurement?
4. Known physics that forbids it outright.

Return YAML with fields: `verdict` (pass | fail | revise), `reason` (3 sentences max), `estimate` (your numbers), `revision_hint` (one sentence if revise). Be strict on arithmetic and generous on imagination: a strange but consistent mechanism passes.
