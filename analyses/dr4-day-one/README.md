# Gaia DR4 day-one queries (release: 2026-12-02, 12:00 CET)

Prepared before release so that specific questions reach the data in the first days. Each query is a text file with a
header comment stating the card it serves and the expected row count. Adjust table names to the final DR4 data model
(draft in the June 2026 pre-release: https://www.cosmos.esa.int/en/web/gaia/dr4-prerelease).

Planned:
1. `astrometric_anomalies.adql` — sources with anomalous epoch-astrometry residuals not explained by binarity flags.
2. `periodic_photometry.adql` — epoch photometry with strictly periodic, low-amplitude signatures outside known variable classes.
3. `anomalous_acceleration.adql` — proper-motion anomalies against DR3 and Hipparcos baselines.
