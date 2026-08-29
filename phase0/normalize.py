"""Surface normalisation and comune bands — the index pipeline.

Implements `docs/seo-spec.md` §3 (the standard) and §4.3 (the comune
report), as amended by SOT §17.1's S005 resolution.

THE ONE THING TO UNDERSTAND BEFORE EDITING THIS FILE
----------------------------------------------------
Every normalised surface here is an INTERVAL, not a number, and it stays
an interval all the way to the template. That is not defensive
programming, it is the product. This site's whole argument is that
agencies publish a confident EUR/m2 from a denominator they will not
define; a site that answered with its own confident number from an
estimated denominator would be making the same move with better manners.

So: `sia_lo`/`sia_hi`, never `sia`. `eur_sia_lo`/`eur_sia_hi`, never
`eur_sia`. If you ever find yourself writing `(lo + hi) / 2` to make
something fit a column, stop — that midpoint is the exact number §10.3's
lint exists to fail the build over. The midpoint appears in precisely one
place in this file, `_width_pct`, where it is a denominator for measuring
the interval's own width and never leaves the function.

WHY TIER B IS ENOUGH (the S005 decision, SOT §17.1)
---------------------------------------------------
Tier A needs an itemised decomposition; the only machine-readable source
is `surfaceConstitution` on detail pages that 403. Rather than hand-seed
Tier A, S005 measured what the estimate actually costs:

    deflator uncertainty widens the comune p50 by   14-18%
    the market's own p25-p75 spread of the stock is 55-104%

The fuzziness we would remove by hand is about a fifth of the variation
that is really there and would remain afterwards. Tier A decompositions
are still welcome — a Tier A listing enters the band as a zero-width
interval and narrows it — but they are an improvement, never a gate.
"""

import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import config

# --- The standard ------------------------------------------------------

# seo-spec.md §3.4. Stated surface -> internal habitable area (sia).
# A range, because the input is a single number and a typology and that
# genuinely does not determine the answer.
#
# The villa row is the honest admission and it is deliberate: for the one
# category where surface abuse is worst, inference is worthless, so villas
# take Tier A or they carry no index at all. See the Anghiari exhibit —
# a 2.600 m2 park inside a "commerciale" of 3.150 m2. No deflator range
# narrow enough to publish survives contact with that.
DEFLATORS = {
    "appartamento": (0.78, 0.88),   # apartment, urban
    "terratetto":   (0.72, 0.85),   # terratetto / townhouse
    "cielo_terra":  (0.72, 0.85),   # same structural class
    "rustico":      (0.65, 0.85),   # restored casale / farmhouse
    # "villa":      (0.30, 0.80)    -- range exceeds +/-20%, forced A or C
}

FORCED_TIER_C = {"villa"}

# seo-spec.md §3.2. How accessories weight into BV-commerciale (`bvc_m2`).
#
# READ SOT §17.3 BEFORE QUOTING THESE. This table is a CHOSEN standard,
# not a measurement. Nothing in this repository derived these
# coefficients. That is legitimate — declaring a rule and applying it
# uniformly is exactly what a standard is, and it is the opposite of what
# the agencies do — but this project's recurring failure is assumed
# numbers hardening into findings, so the method page says outright that
# these are published choices. The one measured anchor is §7:
# Immobiliare's own rule is SUM(surface x coefficient) over rows tagged
# `Principale`, with garage at 50% and garden at 10%, applied
# inconsistently by its own agents. Those two rows match observed
# practice; the rest are ours.
#
# NOT YET APPLIED. `bvc_m2` needs an itemised decomposition, which needs
# Tier A, which no listing currently reaches (§17.1). The table is
# published anyway, because an agency is entitled to see the standard it
# is about to be measured against before we can measure it — and because
# the land row is the argument, not a detail.
WEIGHTS = [
    ("Internal habitable area, h &ge; 2,40 m",   "100%", ""),
    ("Sub-height space, 1,50&ndash;2,40 m",       "50%", ""),
    ("Below 1,50 m",                               "0%", ""),
    ("Habitable annex / dependance",             "100%", ""),
    ("Veranda, enclosed and unheated",            "60%", ""),
    ("Covered loggia / portico",                  "35%", ""),
    ("Open balcony / terrace",                    "25%", "&le; 25% of sia"),
    ("Cantina / magazzino, non-habitable",        "25%", "&le; 15% of sia"),
    ("Garage / box",                              "50%", "&le; 40 m&sup2;"),
    ("Covered parking space",                     "30%", "&le; 25 m&sup2;"),
    ("Ruin / unrestorable annex",                  "0%", "reported separately"),
    ("Private garden &le; 1.000 m&sup2;",         "10%", "&le; 15% of sia"),
    ("Land / park &gt; 1.000 m&sup2;",             "0%", "reported as land"),
    ("Pool, tennis court, well, vineyard",         "0%", "reported as amenities"),
]

# NOT Tier C — out of scope entirely. Tier C means "a home we cannot
# measure"; these are not homes. A residential index that published a
# shop or a field, even with no number attached, would be wrong in a way
# no confidence tier repairs.
OUT_OF_SCOPE = {"commerciale", "terreno"}

# Publish gate, §4.3 as amended. The width condition replaces the retired
# "Tier A only" condition: it fails loudly on a comune whose stock is too
# mixed to summarise, rather than silently on one that merely lacks
# decompositions.
GATE_MIN_N = 8
GATE_MIN_AGENCIES = 2

# The width gate is DERIVED, not chosen. An earlier draft of this file put
# it at a flat 25%, which is the kind of number this project keeps having
# to apologise for: rustico's own deflator range is 26,7% wide relative to
# its midpoint, so a 25% gate silently suppresses every comune whose
# median listing is a farmhouse — which is most of the Valtiberina, and
# precisely the market the site is about. It suppressed Monterchi on the
# first run, and it would have read as rigour.
#
# The defensible rule: a band may not be wider than the worst uncertainty
# among its own inputs. If mixing typologies pushes the band wider than
# any single deflator could, the stock really is too mixed to summarise
# and the suppression message is true. The 5% tolerance absorbs the fact
# that p25/p50/p75 interpolate across different listings on each bound.
def _deflator_width_pct(d):
    lo, hi = d
    return (hi - lo) / ((hi + lo) / 2) * 100

GATE_MAX_WIDTH_PCT = round(max(_deflator_width_pct(d) for d in DEFLATORS.values()) * 1.05, 1)


# --- Typology recovery -------------------------------------------------

# 146 listings reach us with no typology and therefore no deflator, which
# would drop them to Tier C. Most are recoverable from fields already in
# the database — no detail page, no new request, no 403. Marcellini
# carries `typology_raw` on all 31 of its rows; Centogambe has titles on
# 83 of its 115.
#
# Order matters in _from_text: "villa" must be tested before generic
# house words, and the commercial terms before everything, because
# "Appartamento di 120 mq - uso ufficio" is a commercial listing wearing
# a residential noun.

_RAW_MAP = {
    "coloniche":          "rustico",
    "appartamenti":       "appartamento",
    "ville":              "villa",
    "negozi":             "commerciale",
    "terreniedificabili": "terreno",
    "terreniagricoli":    "terreno",
    "capannoni":          "commerciale",
    "uffici":             "commerciale",
}

_TEXT_RULES = [
    ("commerciale", ("locale commerciale", "negozio", "capannone", "ufficio",
                     "fondo commerciale", "attivit")),
    ("terreno",     ("terreno", "lotto edificabile", "terreni")),
    ("villa",       ("villa", "villino", "villetta")),
    ("rustico",     ("colonica", "casale", "rustico", "casolare", "podere",
                     "fienile", "annesso")),
    ("terratetto",  ("terratetto", "casa singola", "casa indipendente",
                     "porzione di casa", "schiera")),
    ("appartamento", ("appartamento", "bilocale", "trilocale", "quadrilocale",
                      "monolocale", "attico", "mansarda")),
]


def _from_text(*fields):
    """First matching typology across the given free-text fields.

    Checked in _TEXT_RULES order, not in field order, so a listing whose
    title says 'locale commerciale' and whose description mentions an
    'appartamento' upstairs resolves commercial. Under-claiming scope is
    the safe direction.
    """
    blob = " ".join(str(f or "") for f in fields).lower()
    if not blob.strip():
        return None
    for typ, needles in _TEXT_RULES:
        if any(n in blob for n in needles):
            return typ
    return None


def recover_typology(row):
    """(typology, provenance). Never invents; returns (None, 'none')."""
    if row["typology"] and row["typology"] not in ("unknown", "progetto"):
        return row["typology"], "source"

    raw = str(row["typology_raw"] or "").strip().lower().replace(" ", "")
    if raw in _RAW_MAP:
        return _RAW_MAP[raw], "typology_raw"

    guess = _from_text(row["title"], row["description"])
    if guess:
        return guess, "text"

    return None, "none"


# --- Per-listing normalisation -----------------------------------------

def normalise(row):
    """One listing -> its published index row, or None if out of scope.

    Returns a dict whose surface and EUR/m2 fields are always intervals.
    `tier` is A, B or C; a C row carries stated figures and explicitly
    null normalised ones, because §3.3 requires the page to exist and say
    why it has no number rather than quietly omit the listing.
    """
    typ, prov = recover_typology(row)

    if typ in OUT_OF_SCOPE:
        return None

    price = row["price"]
    stated = row["mq"]
    has_price = price is not None and price > 0
    has_surface = stated is not None and stated > 0

    out = {
        "source": row["source"],
        "source_id": row["source_id"],
        "comune": row["comune"],
        "url": row["url"],
        "agency_name": row["agency_name"] or "",
        "typology": typ or "",
        "typology_provenance": prov,
        "price_eur": price if has_price else "",
        "price_bracket": row["price_bracket"] or "",
        "stated_m2": stated if has_surface else "",
        "stated_label": row["surface_raw"] or "",
        "tier": "C",
        "tier_reason": "",
        "sia_lo_m2": "", "sia_hi_m2": "",
        "eur_stated": "", "eur_sia_lo": "", "eur_sia_hi": "",
    }

    if not has_price:
        out["tier_reason"] = ("price not published — Marcellini states a "
                              "bracket, not a price" if row["price_bracket"]
                              else "no price published")
        return out
    if not has_surface:
        out["tier_reason"] = "no surface published"
        return out

    # eur_stated is the agency's OWN arithmetic and is published for every
    # priced listing with a surface, including Tier C. It is not our
    # number and carries no confidence claim from us — it is the thing the
    # index is measured against, and withholding it would remove the
    # comparison the page exists to make.
    out["eur_stated"] = round(price / stated, 1)

    if typ is None:
        out["tier_reason"] = "typology unknown — no deflator can be chosen"
        return out
    if typ in FORCED_TIER_C:
        out["tier_reason"] = ("villa with land — §3.4 deflator range "
                              "0,30-0,80 exceeds ±20%; requires an itemised "
                              "decomposition or no index")
        return out

    d_lo, d_hi = DEFLATORS[typ]

    # Round the surface FIRST, then divide by the rounded surface.
    #
    # Rounding sia and eur_sia independently off the same unrounded float
    # leaves them inconsistent by a euro or two — and a reader who divides
    # our published price by our published surface then gets a different
    # number from our published EUR/m2. On any other site that is a
    # rounding artefact nobody would notice. Here it is the whole
    # proposition: the page invites an agent or a journalist to check the
    # arithmetic, and the first thing they will do is exactly this
    # division. Every published figure must be reproducible from the other
    # published figures.
    sia_lo = round(stated * d_lo, 1)
    sia_hi = round(stated * d_hi, 1)

    out["tier"] = "B"
    out["tier_reason"] = f"inferred from stated surface and typology ({typ})"
    out["sia_lo_m2"] = sia_lo
    out["sia_hi_m2"] = sia_hi
    # Larger area -> lower EUR/m2. The bounds cross over; keep them straight.
    out["eur_sia_lo"] = round(price / sia_hi, 1)
    out["eur_sia_hi"] = round(price / sia_lo, 1)
    return out


# --- Bands -------------------------------------------------------------

def _pct(values, q):
    """Linear-interpolated percentile on a sorted copy.

    Written out rather than imported so the band figures do not change
    under us when a numpy or statistics version changes its interpolation
    default. Byte-identical rebuilds are a contract (§10.2).
    """
    v = sorted(values)
    if not v:
        return None
    k = (len(v) - 1) * q
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def _width_pct(lo, hi):
    """Interval width as a percentage of its own midpoint.

    The only midpoint in this module. It is a measure of the interval, not
    a summary of it, and it does not leave this function.
    """
    mid = (lo + hi) / 2
    return (hi - lo) / mid * 100 if mid else float("inf")


def band_for(rows):
    """Interval band over Tier A+B rows, with the §4.3 gate applied.

    Each listing contributes an interval; a Tier A listing contributes one
    of zero width. p25/p50/p75 are each computed twice — once over the
    lower bounds, once over the upper — so every published quantile is
    itself an interval.
    """
    usable = [r for r in rows if r["tier"] in ("A", "B")]
    los = [r["eur_sia_lo"] for r in usable]
    his = [r["eur_sia_hi"] for r in usable]
    agencies = {r["agency_name"] for r in usable if r["agency_name"]}

    band = {
        "n": len(usable),
        "n_agencies": len(agencies),
        "tier_split": {
            "A": sum(1 for r in rows if r["tier"] == "A"),
            "B": sum(1 for r in rows if r["tier"] == "B"),
            "C": sum(1 for r in rows if r["tier"] == "C"),
        },
        "published": False,
        "suppressed_because": "",
    }

    if len(usable) < GATE_MIN_N:
        band["suppressed_because"] = f"n={len(usable)} below gate of {GATE_MIN_N}"
        return band
    if len(agencies) < GATE_MIN_AGENCIES:
        band["suppressed_because"] = (f"{len(agencies)} agency — gate requires "
                                      f"{GATE_MIN_AGENCIES}")
        return band

    for q, name in ((0.25, "p25"), (0.50, "p50"), (0.75, "p75")):
        band[name + "_lo"] = round(_pct(los, q), 1)
        band[name + "_hi"] = round(_pct(his, q), 1)

    band["p50_width_pct"] = round(_width_pct(band["p50_lo"], band["p50_hi"]), 1)

    # The stock's own spread, measured on the lower bounds only so it is a
    # like-for-like number and not contaminated by our interval. Published
    # beside the band width so a reader can see how much of the range is
    # the market and how much is us — §4.3 requires exactly this.
    p25l, p50l, p75l = (_pct(los, q) for q in (0.25, 0.50, 0.75))
    band["market_spread_pct"] = round((p75l - p25l) / p50l * 100, 1) if p50l else None

    if band["p50_width_pct"] > GATE_MAX_WIDTH_PCT:
        band["suppressed_because"] = (
            f"p50 interval {band['p50_width_pct']}% wide, gate is "
            f"{GATE_MAX_WIDTH_PCT}% — wider than any single deflator, so the "
            f"stock is genuinely too mixed to summarise")
        return band

    band["published"] = True
    return band


# --- Run ---------------------------------------------------------------

def run(db_path=None, out_dir=None):
    db_path = db_path or config.DB_PATH
    out_dir = Path(out_dir or Path(db_path).parent)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    raw = conn.execute("SELECT * FROM listings ORDER BY source, source_id").fetchall()
    conn.close()

    rows, out_of_scope = [], 0
    for r in raw:
        n = normalise(r)
        if n is None:
            out_of_scope += 1
        else:
            rows.append(n)

    by_comune = defaultdict(list)
    for r in rows:
        by_comune[r["comune"]].append(r)

    bands = {c: band_for(by_comune[c]) for c in sorted(by_comune)}

    # Deterministic: fixed key order, sorted rows, no run ordinals, no
    # timestamps. Two runs over the same database are byte-identical.
    csv_path = out_dir / "normalized.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    json_path = out_dir / "comune_bands.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(bands, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")

    return rows, bands, out_of_scope


def _report(rows, bands, out_of_scope):
    tiers = defaultdict(int)
    for r in rows:
        tiers[r["tier"]] += 1
    recovered = sum(1 for r in rows if r["typology_provenance"] in ("typology_raw", "text"))

    print(f"in scope {len(rows)}   out of scope (shops, land) {out_of_scope}")
    print(f"tiers    A {tiers['A']}   B {tiers['B']}   C {tiers['C']}"
          f"   (typology recovered for {recovered})")
    print()
    hdr = (f"{'comune':<22}{'n':>4}{'ag':>4}  {'p50 interval':>19}"
           f"{'width':>7}{'market':>8}  publish")
    print(hdr); print("-" * len(hdr))
    for c, b in bands.items():
        if b["published"]:
            iv = f"{b['p50_lo']:>8,.0f} -{b['p50_hi']:>8,.0f}"
            print(f"{c:<22}{b['n']:>4}{b['n_agencies']:>4}  {iv}"
                  f"{b['p50_width_pct']:>6.1f}%{b['market_spread_pct']:>7.1f}%  yes")
        else:
            print(f"{c:<22}{b['n']:>4}{b['n_agencies']:>4}  "
                  f"{'—':>19}{'':>7}{'':>8}  no: {b['suppressed_because']}")


if __name__ == "__main__":
    _report(*run())
