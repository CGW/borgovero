"""Phase 0 configuration."""

# --- Scope -------------------------------------------------------------

COMUNI = ["sansepolcro", "anghiari"]

# Measured live 2026-08-27, Immobiliare only, 25 per page:
#
#   sansepolcro           179      pieve-santo-stefano    67
#   anghiari              111      monterchi              38
#   caprese-michelangelo   82      badia-tedalda          34
#   citerna                60      sestino                31
#                                  ------------------------
#                                  ALL EIGHT             602
#
# Phase 0 (Sansepolcro + Anghiari) = 290 listings in ~12 requests.
# All eight = 602 listings in ~27 requests. Minutes, not hours.
ALL_VALTIBERINA = [
    "sansepolcro", "anghiari", "caprese-michelangelo", "citerna",
    "pieve-santo-stefano", "monterchi", "badia-tedalda", "sestino",
]

MAX_PAGES_PER_COMUNE = 40          # safety ceiling; ~25 listings/page
MAX_LISTINGS_PER_COMUNE = 1200     # hard stop

# --- Politeness --------------------------------------------------------
# These are deliberately conservative. The whole Phase 0 run is a few
# hundred requests. There is no reason to go faster and every reason not to.

REQUEST_DELAY_S = 4.0              # between every request, same host
TIMEOUT_S = 30
MAX_RETRIES = 2

# Identify yourself honestly. A contactable UA is the single cheapest thing
# that turns "hostile bot" into "someone we could just email".
CONTACT_URL = "https://example.org/about"   # <-- CHANGE THIS
USER_AGENT = (
    "ValtiberinaPriceResearch/0.1 (research project; "
    f"contact: {CONTACT_URL})"
)

# --- Storage -----------------------------------------------------------

DB_PATH = "phase0.sqlite"
HTML_CACHE_DIR = "cache/html"      # every fetch is cached; reparse is free

# --- OMI ---------------------------------------------------------------
# Download from Agenzia delle Entrate:
#   https://www1.agenziaentrate.gov.it/servizi/Consultazione/ricerca.htm
# You want the semestral "Quotazioni immobiliari" export (zipped CSV,
# semicolon-delimited). Put the values file here.

OMI_CSV_PATH = "data/omi_valori.csv"
OMI_SEMESTER = "2026-1"

# Column mapping. Run `python omi.py --inspect` first — it prints the
# columns it actually found, then fix these if they differ.
OMI_COLUMNS = {
    "comune":     "Comune_descrizione",
    "zona":       "Zona_Descr",
    "zona_code":  "Zona",
    "fascia":     "Fascia",
    "tipologia":  "Descr_Tipologia",
    "stato":      "Stato_conservativo",
    "min_eur_m2": "Compr_min",
    "max_eur_m2": "Compr_max",
    # OMI states which surface its EUR/m2 refers to: 'N' netta or 'L' lorda.
    # Without this the comparison to an advertised surface is unanchored,
    # so the loader captures it and analyze.py prints it.
    "surface_basis": "Sup_NL_compr",
}

# Which OMI typologies map to which of our typologies.
# OMI's vocabulary is coarse; this is the honest mapping.
OMI_TIPOLOGIA_MAP = {
    "Abitazioni civili":            ["appartamento", "terratetto", "cielo_terra"],
    "Abitazioni di tipo economico": ["appartamento", "terratetto", "cielo_terra"],
    "Ville e Villini":              ["villa"],
    "Abitazioni signorili":         ["appartamento", "villa"],
}

# Known anchors, for sanity-checking the loaded file.
# If the loader disagrees wildly with these, the column mapping is wrong.
OMI_SANITY_ANCHORS = {
    ("sansepolcro", "B1"): (1100, 1400),   # centro storico ~EUR1,245/m2
    ("anghiari", None):    (880, 1410),    # registered range
}

# --- Analysis ----------------------------------------------------------

DOM_BUCKETS = [
    ("under 6 months",  0,    180),
    ("6-12 months",     180,  365),
    ("1-2 years",       365,  730),
    ("2-4 years",       730,  1460),
    ("over 4 years",    1460, 99999),
]

# id_curve.py labels every date estimate with a confidence:
#
#   high        bracketed by anchors less than 8M ids apart
#   medium      bracketed, but by a wide gap
#   bound_old   below the earliest anchor — age is a FLOOR, not an estimate
#   bound_new   above the latest anchor  — age is a CEILING
#
# Bounds are not discarded. A floor of 2,000 days sits entirely inside
# "over 4 years", so the listing belongs there with certainty. A floor that
# straddles two buckets is dropped from the DOM splits instead of guessed.
# That containment test is what keeps the oldest listings — the whole point
# of the project — in the analysis without inventing dates for them.
#
#   "medium"  accept wide-gap interpolations (default)
#   "high"    accept only tightly bracketed ones; stricter, smaller n
DOM_MIN_CONFIDENCE = "medium"

# Decision gate thresholds (percent over OMI band ceiling)
GATE_STRONG   = 35.0   # thesis holds as stated
GATE_MODERATE = 20.0   # thesis holds, weaker
# below GATE_MODERATE -> check the DOM split before concluding anything

# --- Which surface? ----------------------------------------------------
# Immobiliare publishes two figures, e.g. "115 m2 | commerciale 183,2 m2".
# On that listing they differ by 59%, which moves EUR/m2 by the same amount
# and therefore decides the entire result of this test.
#
#   "net"        - the smaller figure. Conservative: produces the HIGHEST
#                  EUR/m2 and the strongest overpricing finding.
#   "commercial" - what agencies quote and justify their price against.
#                  Falls back to net when not published.
#   "both"       - run the analysis twice and print both. Start here.
#
# OMI publishes its own surface basis per row. Whichever you pick has to
# match it or the comparison is meaningless. Check the OMI file's surface
# column before trusting either number.
SURFACE_BASIS = "both"
