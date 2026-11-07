"""Phase 0 archive smoke tests (tasks/PHASE0.md, gate G3 map).

    uv run python -m pipeline.archives.smoke            # all tests
    uv run python -m pipeline.archives.smoke gaia wise  # selected tests

Each test runs archive-side where possible, times itself and writes one record to
analyses/smoke-tests-phase0/results/smoke.json. Only counts and small summary tables are kept;
intermediate tables go to analyses/smoke-tests-phase0/data/ (git-ignored).
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analyses" / "smoke-tests-phase0"
RESULTS = OUT / "results"
DATA = OUT / "data"

GAIA_SAMPLE_ADQL = """
SELECT source_id, ra, dec, pmra, pmdec, parallax, phot_g_mean_mag
FROM gaiadr3.gaia_source
WHERE phot_g_mean_mag < 12 AND parallax > 10 AND parallax_over_error > 10
"""

GAIA_COUNT_ADQL = """
SELECT COUNT(*) AS n
FROM gaiadr3.gaia_source
WHERE phot_g_mean_mag < 12 AND parallax > 10 AND parallax_over_error > 10
"""

# Gaia's own precomputed cross-match, used as an independent check of the IRSA positional match.
GAIA_ALLWISE_NEIGHBOUR_ADQL = """
SELECT COUNT(*) AS n
FROM gaiadr3.gaia_source AS g
JOIN gaiadr3.allwise_best_neighbour AS x USING (source_id)
WHERE g.phot_g_mean_mag < 12 AND g.parallax > 10 AND g.parallax_over_error > 10
"""

IRSA_TAP = "https://irsa.ipac.caltech.edu/TAP"
ALLWISE_EPOCH = 2010.5  # approximate AllWISE mean epoch
GAIA_EPOCH = 2016.0
MATCH_RADIUS_ARCSEC = 3.0

EXOARCHIVE_TAP = "https://exoplanetarchive.ipac.caltech.edu/TAP"
EXO_ADQL = """
SELECT pl_name, hostname, pl_eqt, pl_rade, pl_bmasse, sy_dist, discoverymethod
FROM pscomppars
WHERE pl_eqt >= 200 AND pl_eqt <= 350
ORDER BY pl_eqt
"""

TESS_TARGET = "pi Mensae"  # bright, many SPOC sectors
TESS_TIC = 261136679
SPHEREX_BUCKET = "nasa-irsa-spherex"


def _record(name: str, t0: float, **fields) -> dict:
    return {"test": name, "runtime_s": round(time.time() - t0, 2), **fields}


def gaia() -> dict:
    from astroquery.gaia import Gaia

    from astropy.table import vstack

    # Anonymous async jobs are cut at 50,000 rows without an error (Gaia.ROW_LIMIT = -1 does not lift it),
    # so the sample is fetched in RA quadrants and checked against COUNT(*).
    Gaia.ROW_LIMIT = -1
    t0 = time.time()
    n_count = int(Gaia.launch_job_async(GAIA_COUNT_ADQL).get_results()["n"][0])
    parts = [Gaia.launch_job_async(GAIA_SAMPLE_ADQL + f" AND ra >= {lo} AND ra < {lo + 90}").get_results()
             for lo in (0, 90, 180, 270)]
    if any(len(p) >= 50_000 for p in parts):
        raise RuntimeError("a Gaia chunk hit the 50,000-row cap; use smaller chunks")
    tab = vstack(parts)
    if len(tab) != n_count:
        raise RuntimeError(f"Gaia result incomplete: {len(tab)} rows vs COUNT(*) = {n_count}")
    DATA.mkdir(parents=True, exist_ok=True)
    tab.write(DATA / "gaia_g12_100pc.ecsv", overwrite=True)
    return _record("gaia", t0, access="astroquery.gaia ADQL async (gea.esac.esa.int/tap-server)",
                   query=GAIA_SAMPLE_ADQL.strip() + " (in 4 RA chunks)", n_rows=len(tab), n_count_check=n_count,
                   note="anonymous async results capped at 50,000 rows without error; chunk and check COUNT(*)",
                   licence="public (ESA Gaia, CC BY-SA 3.0 IGO)")


def wise() -> dict:
    import pyvo
    from astropy.table import Table
    from astroquery.gaia import Gaia

    src = DATA / "gaia_g12_100pc.ecsv"
    if not src.exists():
        raise SystemExit("run the gaia test first")
    g = Table.read(src)
    # Propagate Gaia J2016.0 positions to the AllWISE epoch; nearby stars move several arcsec in 5.5 yr.
    dt_yr = ALLWISE_EPOCH - GAIA_EPOCH
    pmra = np.nan_to_num(np.asarray(g["pmra"], float))
    pmdec = np.nan_to_num(np.asarray(g["pmdec"], float))
    dec = np.asarray(g["dec"], float)
    up = Table({
        "source_id": g["source_id"],
        "ra_w": np.asarray(g["ra"], float) + pmra * dt_yr / 3.6e6 / np.cos(np.radians(dec)),
        "dec_w": dec + pmdec * dt_yr / 3.6e6,
    })
    adql = f"""
SELECT u.source_id, a.designation, a.w1mpro, a.w2mpro, a.w3mpro, a.w4mpro, a.cc_flags, a.ext_flg,
       DISTANCE(POINT('ICRS', u.ra_w, u.dec_w), POINT('ICRS', a.ra, a.dec)) AS sep
FROM allwise_p3as_psd a, TAP_UPLOAD.gaia u
WHERE CONTAINS(POINT('ICRS', a.ra, a.dec), CIRCLE('ICRS', u.ra_w, u.dec_w, {MATCH_RADIUS_ARCSEC / 3600}))=1
"""
    # IRSA rejects JOIN ... ON CONTAINS(...) with uploads ("Invalid or unsupported ADQL"); use comma join + WHERE.
    t0 = time.time()
    res = pyvo.dal.TAPService(IRSA_TAP).run_async(adql, uploads={"gaia": up}).to_table()
    runtime = time.time() - t0
    res.write(DATA / "gaia_allwise_match.ecsv", overwrite=True)
    ids = np.asarray(res["source_id"])
    n_matched = len(np.unique(ids))
    n_multi = int(np.sum(np.unique(ids, return_counts=True)[1] > 1))
    # ADQL says DISTANCE returns degrees; IRSA returns arcsec (column unit "arcsec"). Trust the unit metadata.
    from astropy import units as u
    sep = (np.asarray(res["sep"], float) * (res["sep"].unit or u.deg)).to_value(u.arcsec)

    t1 = time.time()
    n_gaia_xm = int(Gaia.launch_job_async(GAIA_ALLWISE_NEIGHBOUR_ADQL).get_results()["n"][0])
    rec = _record("wise", t0, access="pyvo TAP async with TAP_UPLOAD (irsa.ipac.caltech.edu/TAP), table allwise_p3as_psd",
                  query=adql.strip(), n_uploaded=len(up), n_matched=n_matched, n_with_multiple_matches=n_multi,
                  match_radius_arcsec=MATCH_RADIUS_ARCSEC, epoch_propagation=f"J{GAIA_EPOCH} -> J{ALLWISE_EPOCH}",
                  sep_arcsec_median=round(float(np.median(sep)), 3), sep_arcsec_p95=round(float(np.percentile(sep, 95)), 3),
                  check_gaiadr3_allwise_best_neighbour=n_gaia_xm, licence="public (IPAC/IRSA, NASA)")
    rec["runtime_s"] = round(runtime, 2)
    rec["check_runtime_s"] = round(time.time() - t1, 2)
    return rec


def tess() -> dict:
    """Primary path: MAST public S3 mirror (fast, archive-side, rule 5). The MAST portal search via
    lightkurve hung for 34 min on 2026-11-07 despite astroquery timeouts, so it is only a fallback."""
    import boto3
    import lightkurve as lk
    from botocore import UNSIGNED
    from botocore.config import Config

    t0 = time.time()
    s3 = boto3.client("s3", region_name="us-east-1", config=Config(signature_version=UNSIGNED))
    tic = f"{TESS_TIC:016d}"  # SPOC paths: tess/public/tid/sNNNN/<TIC in 4-digit groups>/
    prefix = f"tess/public/tid/s0001/{tic[0:4]}/{tic[4:8]}/{tic[8:12]}/{tic[12:16]}/"
    try:
        keys = [o["Key"] for o in s3.list_objects_v2(Bucket="stpubdata", Prefix=prefix).get("Contents", [])]
        key = next(k for k in keys if k.endswith("_lc.fits"))
        DATA.mkdir(parents=True, exist_ok=True)
        dest = DATA / key.rsplit("/", 1)[1]
        s3.download_file("stpubdata", key, str(dest))
        lc = lk.read(dest)
        return _record("tess", t0, access="MAST S3 mirror s3://stpubdata/tess/public/tid/ (unsigned), read with lightkurve",
                       target=f"{TESS_TARGET} (TIC {TESS_TIC})", downloaded=key, sector=int(lc.sector),
                       n_cadences=len(lc), licence="public (MAST, NASA)")
    except Exception as exc:
        s3_error = f"{type(exc).__name__}: {exc}"[:200]

    sr = lk.search_lightcurve(TESS_TARGET, mission="TESS", author="SPOC", exptime=120)
    lc = sr[0].download()  # cached under ~/.lightkurve, not in the repository
    return _record("tess", t0, access="lightkurve -> MAST portal (astroquery.mast)", target=TESS_TARGET,
                   s3_error=s3_error, n_spoc_120s_products=len(sr), downloaded=str(sr[0].table["productFilename"][0]),
                   sector=int(lc.sector), n_cadences=len(lc), licence="public (MAST, NASA)")


def exoplanets() -> dict:
    import pyvo

    t0 = time.time()
    tab = pyvo.dal.TAPService(EXOARCHIVE_TAP).search(EXO_ADQL).to_table()
    RESULTS.mkdir(parents=True, exist_ok=True)
    tab.write(RESULTS / "exoplanets_teq_200_350.csv", format="ascii.csv", overwrite=True)
    meth = {}
    for m in tab["discoverymethod"]:
        meth[str(m)] = meth.get(str(m), 0) + 1
    return _record("exoplanets", t0, access="pyvo TAP sync (exoplanetarchive.ipac.caltech.edu/TAP), table pscomppars",
                   query=EXO_ADQL.strip(), n_rows=len(tab), by_discovery_method=meth,
                   result_table="analyses/smoke-tests-phase0/results/exoplanets_teq_200_350.csv",
                   licence="public (NASA Exoplanet Archive)")


def spherex() -> dict:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    s3 = boto3.client("s3", region_name="us-east-1", config=Config(signature_version=UNSIGNED))
    t0 = time.time()
    top = s3.list_objects_v2(Bucket=SPHEREX_BUCKET, Delimiter="/")
    prefixes = [p["Prefix"] for p in top.get("CommonPrefixes", [])]
    t_list = time.time() - t0
    # Walk down to the first FITS file and read only its primary header block (range read).
    key, prefix, steps = None, "", 0
    while key is None and steps < 12:
        r = s3.list_objects_v2(Bucket=SPHEREX_BUCKET, Prefix=prefix, Delimiter="/", MaxKeys=50)
        fits = [o for o in r.get("Contents", []) if o["Key"].endswith((".fits", ".fits.gz", ".fits.fz"))]
        if fits:
            key, size = fits[0]["Key"], fits[0]["Size"]
            break
        sub = [p["Prefix"] for p in r.get("CommonPrefixes", [])]
        if not sub:
            break
        prefix, steps = sub[0], steps + 1
    rec = {"top_level_prefixes": prefixes}
    if key:
        t1 = time.time()
        body = s3.get_object(Bucket=SPHEREX_BUCKET, Key=key, Range="bytes=0-2879")["Body"].read()
        cards = [body[i:i + 80].decode("ascii", "replace").rstrip() for i in range(0, len(body), 80)]
        rec.update(range_read_key=key, object_size_bytes=size, bytes_read=len(body),
                   range_read_s=round(time.time() - t1, 2), header_first_cards=[c for c in cards if c][:6])
    else:
        rec["range_read_key"] = None
    return _record("spherex", t0, access="boto3 S3 unsigned (s3://nasa-irsa-spherex/, us-east-1)",
                   list_s=round(t_list, 2), licence="public (IPAC/IRSA, NASA)", **rec)


TESTS = {"gaia": gaia, "wise": wise, "tess": tess, "exoplanets": exoplanets, "spherex": spherex}


def main(argv: list[str]) -> int:
    names = argv or list(TESTS)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "smoke.json"
    log = json.loads(out.read_text()) if out.exists() else {"runs": {}}
    failed = 0
    for n in names:
        print(f"== {n}", flush=True)
        try:
            rec = TESTS[n]()
            rec["status"] = "ok"
        except Exception as exc:  # record failures; a failed smoke test is a result too
            rec = {"test": n, "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:500]}
            failed += 1
        rec["date"] = dt.date.today().isoformat()
        rec["operator"] = "claude-code (claude-opus-5-5)"
        rec["host"] = f"{platform.system()} {platform.machine()}, python {platform.python_version()}"
        log["runs"][n] = rec
        print(json.dumps({k: v for k, v in rec.items() if k != "query"}, indent=1, default=str), flush=True)
    out.write_text(json.dumps(log, indent=1, default=str) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
