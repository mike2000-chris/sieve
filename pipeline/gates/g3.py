"""Gate G3: data availability and feasibility against the archive map (paper Sections 4.3 and 5).

    uv run python -m pipeline.critique g3 SIEVE-0002 [--dry-run]

Step 1, deterministic and free: every `candidate_archives` entry of the card is matched against config/archives.yaml
(by key aliases) and its access string is classified as archive-side (TAP/ADQL/S3/API) or download. The result is passed
to the LLM judge as context. If the card lists no archive at all the gate short-circuits without a call.
Step 2: the LLM judge returns verdict, per-archive gaps, volume, access plan and licence notes. Writes `licence` and
`volume_estimate` into matching `candidate_archives` entries of the card (never overwrites existing values).
"""
from __future__ import annotations

import re

import yaml

from pipeline.expand import load_yaml
from pipeline.gates.common import Gate

PROMPT_VERSION = "critique-g3-data-v0.2"
_S = {"type": "string"}

# archive-map key -> lower-case aliases looked for in the card's archive name (first match in this order wins,
# so SPHEREx is claimed before the generic IRSA key).
ALIASES = {
    "spherex": ["spherex"],
    "exoplanet_archive": ["exoplanet archive", "nexsci", "pscomppars"],
    "mast": ["mast", "tess", "kepler", "k2", "jwst", "hst", "stpubdata"],
    "gaia": ["gaia"],
    "irsa_ir": ["wise", "allwise", "neowise", "catwise", "2mass", "spitzer", "irsa"],
    "breakthrough_listen": ["breakthrough", "green bank", "gbt", "parkes"],
    "pds": ["planetary data system", "pds", "cassini", "galileo", "juno", "voyager"],
    "ztf": ["ztf", "alerce", "fink", "antares", "lasair"],
    "rubin": ["rubin", "lsst"],
    "optical_spectra": ["sdss", "lamost", "apogee", "rvs"],
    "euclid": ["euclid"],
}
ARCHIVE_SIDE = re.compile(r"\b(tap|adql|s3|boto3|sia2?|sql|cone ?search|cross-?match|api|astroquery|pyvo|casjobs|"
                          r"query|bucket|broker|table|gaiadr\d)\b|nasa-irsa|gaiadr\d\.", re.I)
DOWNLOAD = re.compile(r"\b(download|ftp|wget|bulk|tarball|zip)\b|\.fits|\.tar|\.csv|file ", re.I)


def match_key(name: str) -> str | None:
    low = name.lower()
    for key, words in ALIASES.items():
        if any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z])", low) for w in words):
            return key
    return None


def classify_access(access: str) -> bool | None:
    """True: archive-side language only; False: download language and no archive-side language; None: unclear."""
    side, dl = bool(ARCHIVE_SIDE.search(access)), bool(DOWNLOAD.search(access))
    if side and not dl:
        return True
    if dl and not side:
        return False
    return None if not (side or dl) else None


def precheck_table(card: dict, amap: dict | None = None) -> list[dict]:
    amap = amap or load_yaml("config/archives.yaml")
    by_key = {a["key"]: a for a in amap["archives"]}
    rows = []
    for ca in card.get("candidate_archives") or []:
        key = match_key(ca["name"])
        entry = by_key.get(key) if key else None
        st = (entry or {}).get("smoke_test") or {}
        rows.append({
            "card_archive": ca["name"], "access_stated": ca["access"], "map_key": key, "in_archive_map": entry is not None,
            "map_access": (entry or {}).get("access"), "map_suitability": (entry or {}).get("suitability"),
            "smoke_test_status": st.get("status"), "smoke_test_caveat": st.get("caveat"),
            "archive_side": classify_access(ca["access"]),
        })
    return rows


def precheck(card: dict) -> dict | None:
    if card.get("candidate_archives"):
        return None
    return {"verdict": "no_archives_listed", "reason": "card lists no candidate_archives; G3 needs at least one to assess",
            "table": []}


def _precheck_text(card: dict) -> str:
    rows = precheck_table(card)
    lines = []
    for r in rows:
        where = f"matched to map key `{r['map_key']}`" if r["in_archive_map"] else "NOT in the archive map"
        side = {True: "archive-side access stated", False: "download-style access stated", None: "access path unclear"}[r["archive_side"]]
        extra = f"; smoke test {r['smoke_test_status']}" if r["smoke_test_status"] else ""
        cav = f"; caveat: {r['smoke_test_caveat']}" if r["smoke_test_caveat"] else ""
        lines.append(f"- {r['card_archive']}: {where}; {side}{extra}{cav}")
    return "\n".join(lines) or "(no candidate archives listed)"


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "archives", "volume_estimate", "archive_side", "access_plan", "licence_notes", "scheduled_release",
                 "reason"],
    "properties": {
        "verdict": {"enum": ["available", "partial", "needs_observations", "proprietary"]},
        "archives": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["name", "access", "what_it_provides", "gap", "volume_estimate", "licence"],
                      "properties": {"name": _S, "access": _S, "what_it_provides": _S, "gap": _S,
                                     "volume_estimate": _S, "licence": _S}},
        },
        "volume_estimate": _S,
        "archive_side": {"type": "boolean"},
        "access_plan": {"type": "array", "items": _S},
        "licence_notes": _S,
        "scheduled_release": _S,
        "reason": _S,
    },
}


def _apply(card: dict, result: dict, judged: dict | None = None) -> list[str]:
    """Fill `licence` and `volume_estimate` on candidate_archives entries the judge also names (same map key or name)."""
    written = []
    for ca in card.get("candidate_archives") or []:
        key = match_key(ca["name"])
        for ra in result["archives"]:
            if ra["name"].lower() == ca["name"].lower() or (key and match_key(ra["name"]) == key):
                for fld in ("licence", "volume_estimate"):
                    if not ca.get(fld) and ra.get(fld):
                        ca[fld] = ra[fld]
                        written.append(f"candidate_archives[{ca['name']}].{fld}")
                break
    return written


def _build_vars(card: dict) -> dict:
    amap = load_yaml("config/archives.yaml")
    return {"precheck": _precheck_text(card), "archives_yaml": yaml.safe_dump(amap["archives"], sort_keys=False,
                                                                           allow_unicode=True, width=110).rstrip()}


G3 = Gate(name="G3", prompt_version=PROMPT_VERSION, schema=SCHEMA, build_vars=_build_vars, apply=_apply,
          verdict_of=lambda r: r["verdict"], fail_verdicts=("needs_observations", "proprietary"), precheck=precheck)
