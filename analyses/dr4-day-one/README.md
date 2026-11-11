# Gaia DR4 day-one queries (release: 2026-12-02, 12:00 CET)

Prepared before release so that specific questions reach the data in the first days. Each query is a text file with a
header comment stating the card it serves, the schema basis, the expected row count and the known confounders.

**These are data pulls, not analyses.** No card is pre-registered for them yet. Any hypothesis test on the resulting
tables needs a card and a pre-registration in `prereg/` first (CLAUDE.md, paper Section 4.5).

## Files

| File | Question | Tables (draft DR4 data model) | DR3 dry run |
| --- | --- | --- | --- |
| `astrometric_anomalies.adql` | High RUWE within 100 pc without any DPAC non-single-star solution | `gaia_source`, `all_source_flags` | 35,142 rows, COUNT 4 s, rows 22 s |
| `periodic_photometry.adql` | Significant, low-amplitude (< 10 mmag) periodicity in sources outside every class-specific variability table, within 200 pc | `vari_classifier_feature`, `vari_summary`, `gaia_source` | not possible (no DR3 equivalent of `ls_frequency`) |
| `anomalous_acceleration.adql` | (a) DPAC acceleration solutions within 100 pc; (b) Hipparcos-to-DR4 proper-motion anomaly computed archive-side | `nss_acceleration_astro`, `hipparcos2_best_neighbour`, `dr3_neighbourhood`, `public.hipparcos_newreduction` | (a) 4,460 rows; (b) 17,285 rows, 11 s |

DR3 dry runs are in `dr3-dryrun/` (queries plus run records `results/*.json`; the result tables are regenerable and not
committed). Plausibility check of part (b) on DR3: median |pm_Gaia - pm_HG| = 0.08 mas/yr, 90th percentile 0.63 mas/yr,
1,293 of 17,285 stars above 1 mas/yr, so the archive-side formula behaves as expected.

## Running on release day

```bash
uv run python -m pipeline.archives.adql_run analyses/dr4-day-one/astrometric_anomalies.adql --list
uv run python -m pipeline.archives.adql_run analyses/dr4-day-one/astrometric_anomalies.adql \
    --chunked 1 --count-stmt 0 --out analyses/dr4-day-one/results/astrometric_anomalies.ecsv
```

The runner runs the COUNT, splits the chunked statement over `random_index` so that every chunk stays under 40,000 rows
(anonymous Gaia results are silently cut at 50,000), and fails unless the rows add up to the COUNT.

## Checklist for 2 December (before the first run)

1. Confirm the schema name (`gaiadr4` is assumed) and that the tables above exist: `SELECT table_name FROM tap_schema.tables WHERE table_name LIKE 'gaiadr4.%'`.
2. Check the columns used against the final data model (draft dated 2026-05-20 may change without notice).
3. Read `ref_epoch` from `gaiadr4.gaia_source` and replace the 26.25-yr Hipparcos baseline in query 3 if it is not J2017.5.
4. Set `RANDOM_INDEX_MAX["gaiadr4"]` in `pipeline/archives/adql_run.py` or let the runner query `MAX(random_index)`.
5. Check whether `vari_classifier_feature` covers all sources or only variability candidates (query 2 header).
6. Expect archive load on release day; the async queue was saturated on 2026-11-11 already (sync jobs rejected with 503).

## Facts from the DR4 documentation (pre-release, read 2026-11-11)

- Epoch astrometry (62 TB, 1.3e11 records) and epoch photometry (7.2 TB) are **DataLink products, not TAP tables**:
  they cannot be filtered with ADQL. Select sources via TAP first, then fetch epoch data per source_id.
- Total DR4 volume ~400 TB; data span 2014-07-25 to 2020-01-20 (66 months).
- `gaia_source` holds only sources with high-quality astrometry and photometry; `all_source_*` tables hold the rest.
- Sources: https://www.cosmos.esa.int/web/gaia/dr4, https://www.cosmos.esa.int/en/web/gaia/dr4-prerelease, draft data
  model PDF `gaia-dr4-prerelease-draft-data-model_2026-06-26.zip` (not committed; licence: Gaia data licence).
