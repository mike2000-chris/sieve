"""Gaia archive helper. Example smoke test for Phase 0:

    uv run python -m pipeline.archives.gaia

Counts DR3 sources with G < 12 within 100 pc (parallax > 10 mas) archive-side. Replace `gaiadr3` with the DR4
table names after 2026-12-02.
"""
from __future__ import annotations

import time

SMOKE_QUERY = """
SELECT COUNT(*) AS n
FROM gaiadr3.gaia_source
WHERE phot_g_mean_mag < 12 AND parallax > 10 AND parallax_over_error > 10
"""


def run(adql: str = SMOKE_QUERY):
    from astroquery.gaia import Gaia

    t0 = time.time()
    job = Gaia.launch_job_async(adql)
    table = job.get_results()
    print(table)
    print(f"{time.time() - t0:.1f} s")
    return table


if __name__ == "__main__":
    run()
