"""Archive helpers for gate G3 and Execute. Archive-side first: ADQL/TAP and S3 range reads before downloads.

Planned modules (Phase 0 smoke tests fill them in):
    gaia.py      - ADQL via astroquery.gaia; DR4 day-one queries
    irsa.py      - AllWISE/2MASS TAP via astroquery.ipac.irsa; SPHEREx S3 (boto3, unsigned)
    mast.py      - TESS/Kepler light curves via lightkurve; JWST spectra via astroquery.mast
    exoarchive.py- NASA Exoplanet Archive TAP
    pds.py       - PDS node access for Cassini CDA/INMS and others
"""
