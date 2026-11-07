# Prior-search register

One YAML file per prior archival search for life or technology. The register is (1) the fast path and ground truth for gate G2 (novelty), (2) the seed for the *negative space* operator in Expand, and (3) the test set for the rediscovery test (paper Section 7): entries with `withheld_for_rediscovery_test: true` (published 2020 or later) are hidden from the generator during the blind run.

Schema: `schema/register.schema.json`. Validate with `uv run python -m pipeline.cards validate`.

`bibcodes.status` must become `resolved` through the ADS API before an entry counts as evidence in gate G2; `to_resolve` entries are usable as prompts but not as novelty verdicts.
