"""Phase 0 configuration."""

# --- Scope -------------------------------------------------------------

def norm_comune(s):
    """Comparable key for a comune name across sources.

    OMI writes Sansepolcro as 'SAN SEPOLCRO' — with a space. Immobiliare
    and this config write it 'sansepolcro'. A plain lower() comparison
    matches neither, and the failure is SILENT: every Sansepolcro band is
    skipped at load, every Sansepolcro listing then fails to match a band
    and is dropped from the analysis, and the run still reports success on
    a dataset that has quietly lost its larger comune.

    Strips case, accents and every non-alphanumeric character, so
    'SAN SEPOLCRO', 'Sansepolcro' and "Sant'Angelo" all reduce cleanly.
    """
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())

# MEASURED by full ingest 2026-08-27 (844 listings, 44 requests). The
# earlier figures were counted from page-one estimates and were wrong for
# the two largest comuni — Sansepolcro is 365, not 179, and Anghiari 167,
# not 111. The other six were right to the listing.
#
#   sansepolcro           365      pieve-santo-stefano    67
#   anghiari              167      monterchi              38
#   caprese-michelangelo   82      badia-tedalda          34
#   citerna                60      sestino                31
#                                  ------------------------
#                                  ALL EIGHT             844
#
# Every listing was checked against its comune centre by lat/lon: the
# furthest is 10.1 km (Anghiari, a large rural comune) and none exceeds
# 15 km, so the counts are real and not neighbouring-comune bleed.
ALL_VALTIBERINA = [
    "sansepolcro", "anghiari", "caprese-michelangelo", "citerna",
    "pieve-santo-stefano", "monterchi", "badia-tedalda", "sestino",
]

# All eight. The two-comune Phase 0 scope was a request-budget decision
# and the budget turned out to be 44 requests for the lot. analyze.py
# loads OMI bands only for the comuni listed here, so this MUST match
# what was ingested or the rest silently match no band and drop out.
COMUNI = ALL_VALTIBERINA

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
#
# A domain, deliberately not an email address. This string is sent to the
# site being crawled on every request; a mailto: would be broadcasting a
# personal address to a party you have not chosen to contact. A domain is
# equally traceable to whoever wants to reach you, and no more.
CONTACT_URL = "https://dreamtechbff.com"
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

# The scope spans TWO provinces, so the bands arrive as two separate AdE
# orders and both must be loaded or a comune silently has no bands:
# seven comuni are in Arezzo, Citerna is in Perugia (SOT S2). Passing one
# path dropped Citerna's 53 listings for two sessions without an error.
#
#     python3 omi.py $(python3 -c "import config;print(' '.join('--path '+p for p in config.OMI_CSV_PATHS))")
#
# NOTE the Perugia order is QI_, not QIP_ — quotations WITHOUT zone
# perimeters. So Citerna gets bands but cannot be zoned by
# point-in-polygon (zones.py), and its listings fall back to the fascia
# guess that S003 replaced everywhere else. Re-order as QIP to fix.
# RE-ORDERED 2026-08-29 after `phase0/data/` was deleted. **The AdE order
# number changes on every order**, so these paths are not stable across a
# re-download: Arezzo 2025-2 came back as 1422173, not the 1421390 this
# list named for three sessions. The files were sitting on disk, intact,
# while `omi.py` exited 1 and the SOT recorded the data as missing — the
# fault was three stale path strings, not an absent download.
#
# If omi.py reports a missing file again, check `ls phase0/data/` BEFORE
# re-ordering. The directory is the truth; this list is a pointer to it.
OMI_CSV_PATHS = [
    "data/QIP1422173_WRDCRS77S02Z404C/QIP_1422173_1_20252_VALORI.csv",  # Arezzo 2025-2
    "data/QI1422048_WRDCRS77S02Z404C/QI_1422048_1_20252_VALORI.csv",    # Perugia (Citerna) 2025-2
]

# Arezzo 2021-1, the historical comparison behind S003's finding that
# Valtiberina bands barely moved (71% identical, mean +1,6%) while Cortona
# ran +7,7% over the same period. Not loaded by the default run — pass it
# explicitly when re-testing that.
OMI_CSV_PATH_2021 = "data/QIP1422174_WRDCRS77S02Z404C/QIP_1422174_1_20211_VALORI.csv"
# 2025-2 is the latest published semester (confirmed against the web
# consultation for Sansepolcro B1 on 2026-08-27). There is no 2026-1 yet.
OMI_SEMESTER = "2025-2"

# Column mapping. Run `python omi.py --inspect` first — it prints the
# columns it actually found, then fix these if they differ.
OMI_COLUMNS = {
    "comune":     "Comune_descrizione",
    # Zona_Descr does NOT exist in the valori file — it lives in the ZONE
    # file and joins on LinkZona. Left as None so the loader degrades to
    # zona_code instead of storing empty strings it thinks are real.
    # For Sansepolcro, B1 is confirmed to be the centro storico
    # ("INTERO CENTRO STORICO, VIALE ARMANDO DIAZ, ..."), so the
    # zona_code.startswith("B") path in analyze.band_for() is sound here.
    # Load the zone file too if per-zone labels are ever published.
    "zona":       None,
    "zona_code":  "Zona",
    "fascia":     "Fascia",
    "tipologia":  "Descr_Tipologia",
    "stato":      "Stato",
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
    # 'rustico' is deliberately here and not under economico. OMI has NO
    # category for a stone farmhouse, which is the region's characteristic
    # property, so the classification is ours to make and it decides the
    # answer: the same 92 rural listings come out at -1% over ceiling as
    # Ville e Villini and +45% as economico. Same properties, same prices.
    #
    # Conservative on purpose. If overpricing survives the most GENEROUS
    # band available, no agent can dispute it. If it only appears under
    # the harshest band, we have done exactly what this project accuses
    # agencies of — choosing the denominator that flatters the number.
    "Ville e Villini":              ["villa", "rustico"],
    "Abitazioni signorili":         ["appartamento", "villa"],
}

# The other defensible reading of a rustico, reported as a span alongside
# the headline rather than chosen. Same principle as SURFACE_BASIS="both":
# publish both or neither. The gap between them is itself a finding — it
# measures how much the verdict depends on a judgement OMI forced on us.
#
# Revisit per-listing once ingest reports the yield on `condition`:
# restored -> Ville e Villini, to-renovate -> economico. Until then the
# unpopulated ones would need this default anyway.
RUSTICO_ALT_TIPOLOGIA = "Abitazioni di tipo economico"

# OMI's zone codes carry their class in the first letter — B1, C1, D1,
# E1, R2 — following the standard fascia taxonomy:
#
#   B  centrale        C  semicentrale    D  periferica
#   E  suburbana       R  rurale
#
# Our coarser zona_guess maps onto it as below. This matters more than it
# looks: without it, band_for() takes the min and max across EVERY zone in
# the comune, so a rural farmhouse is measured against a ceiling set by
# hillside villas in C1 (1900 in Sansepolcro 2025-2) and nothing rural can
# ever read as overpriced.
#
# Note what the real data says about C1 — 'zona collinare a nord del
# centro storico' runs 1200-1700 for abitazioni civili against the centro
# storico's 1000-1400. The premium zone is NOT the historic centre.
# Stock that is not comparable to a second-hand house and must not sit in
# the same distribution:
#
#   progetto  off-plan new-build developments. Priced as a project, often
#             without a real surface, and not a property anyone can buy
#             and move into. Seen live on the Sansepolcro search page.
#   terreno   land. EUR/m2 on a field is not EUR/m2 on a house, and OMI
#             prices agricultural land separately from dwellings.
#
# These are still ingested and stored — the raw crawl stays complete — and
# dropped at analysis, where the exclusion is visible in the data-quality
# block rather than silent.
EXCLUDE_TYPOLOGIES = {"progetto", "terreno"}

# Judicial auctions. Measured in the 844-listing ingest: 37 of them, at a
# median EUR414/m2 against the market's EUR1.143 — roughly a third of
# market value, because a court sets the base price, not a seller.
#
# They must come out for two reasons, and the second matters more:
#
#   1. They are not asking prices, so they cannot be over or under an
#      asking-price band. Including them dragged the median down 2%.
#   2. They sit in the LOW tail of the distribution, and the project's
#      flagship claim is that the IQR spans 73 points — that this market
#      has no consensus price. If part of that spread is simply auctions
#      mixed in with ordinary sales, the claim is measuring two markets
#      rather than disagreement within one.
#
# Detected on the selling agency's name first, which catches most of
# them, and on listing text for the rest.
AUCTION_AGENCY_RE = r"\b(aste|asta)\b"
AUCTION_TEXT_RE = (r"asta (giudiziari|telematic)|vendita giudiziari|"
                   r"procedura esecutiva|\bR\.?G\.?E\.?\b|tribunale di")

# S011: AUCTION_AGENCY_RE MISSES THE ONES WITHOUT 'ASTE' IN THE NAME.
# 'Simplex Domus S.R.L.', 'Astissima' and 'Ipn Castello srl' are auction
# intermediaries whose names the regex cannot see — 'Astissima' has no
# word boundary after 'Ast', and the other two say nothing about auctions
# at all. That was harmless while this list only filtered price
# statistics. It is not harmless in the contradictions pipeline, where
# missing one means publishing it as an ordinary estate agency
# disagreeing with the market.
AUCTION_RESELLER_NAMES = {
    "aste florio",
    "aste preaste investimenti srl",
    "astissima",
    "centro aste arezzo",
    "ipn castello srl",
    "professione aste",
    "simplex domus s.r.l.",
    "valerio pisano - aste&investimenti",
}


def is_auction_reseller(agency_name):
    """True for an intermediary that republishes court auctions.

    These are not estate agencies competing over the same stock. They are
    resellers of one court procedure, all quoting the same base d'asta
    from the same perizia, and several of them state outright that their
    photographs are not of the property:

        Valerio Pisano  'le immagini presenti nell'annuncio sono solo
                         indicative e non rappresentano le foto reali'
        Centro Aste     'le foto pubblicate potrebbero non corrispondere
                         all'immobile specifico'

    That kills photo matching in BOTH directions for this class — a
    non-match is meaningless, and so is a match.
    """
    import re
    n = (agency_name or "").strip().lower()
    # bool() around the whole thing, not just the guard: re.search returns
    # a match object or None, and `x and (a or re.search(...))` hands that
    # None straight back. It is falsy, so every call site behaves — until
    # one of them writes the value to JSON or compares it with `is False`.
    return bool(n and (n in AUCTION_RESELLER_NAMES
                       or re.search(AUCTION_AGENCY_RE, n)))


# A surface disagreement between two resellers of ONE auction is a
# transcription difference, not two agencies valuing a property
# differently — they are copying one perizia and choosing different
# bases. Below this spread it is noise and must not be published as a
# contradiction. Measured on the five clusters the price route produced:
# 0.6%, 0%, 0% and 5.4% were noise; Via della Ginestra's 47.8% was not.
AUCTION_MIN_SURFACE_SPREAD = 0.15

ZONA_TO_FASCIA = {
    "centro_storico": ("B",),
    "periferia":      ("C", "D", "E"),
    "campagna":       ("R",),
}

# Known anchors, for sanity-checking the loaded file.
# If the loader disagrees wildly with these, the column mapping is wrong.
# MEASURED from the OMI web consultation, 2026-08-27, Sansepolcro B1,
# anno 2025 semestre 2. Abitazioni civili NORMALE: 1000-1400 EUR/m2, on
# surface basis L (lorda). This REPLACES the earlier 1100-1400 placeholder,
# which would have made a correctly loaded file look like a mapping error.
OMI_SANITY_ANCHORS = {
    ("sansepolcro", "B1"): (1000, 1400),   # centro storico, verified
    ("anghiari", None):    (880, 1410),    # still a prior, not verified
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
