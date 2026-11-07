# Phase 0 archive smoke tests (2026-11-07)

Run: `uv run python -m pipeline.archives.smoke [gaia wise tess exoplanets spherex]` (code: `pipeline/archives/smoke.py`).
Records with access path, runtime, row counts and licence: `results/smoke.json`; summary in `config/archives.yaml` (`smoke_test` blocks).
Small result table: `results/exoplanets_teq_200_350.csv` (495 planets, 200 K <= T_eq <= 350 K, NASA Exoplanet Archive `pscomppars`).
Intermediate tables (Gaia sample, AllWISE match, TESS light curve) go to `data/`, which is git-ignored.

Operator: Claude Code (claude-opus-5-5). These are access tests, not analyses; no card is attached and nothing here is a scientific result.

| Test | Status | Runtime | Key number |
|---|---|---|---|
| Gaia DR3 ADQL, G < 12 within 100 pc | ok | 21 s (4 RA chunks) | 60,235 sources |
| IRSA AllWISE TAP upload cross-match | ok | 18 min | 59,603 matched, median sep 0.06 arcsec |
| TESS light curve (pi Men, sector 1) | ok via MAST S3 | 1.5 s | 18,279 cadences |
| NASA Exoplanet Archive TAP, 200-350 K | ok | 1.7 s | 495 planets |
| SPHEREx QR S3 list + range read | ok | 0.6 s | qr2/, qr3/; 2,880-byte FITS header read |

Pitfalls found (details in `config/archives.yaml`): Gaia anonymous async results are cut at 50,000 rows without an error;
IRSA does not accept `JOIN ... ON CONTAINS` with uploads and returns `DISTANCE()` in arcsec; the MAST portal search hung for 34 min.
