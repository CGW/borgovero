"""The one number: what a buyer should actually pay.

This is the product, not the hypothesis test. `analyze.py` answers "is
this market overpriced" as a distribution; this answers "what is THIS
house worth, and what should I offer" as a single euro figure per
listing.

Two quantities are deliberately kept apart, because conflating them is
how you get a number that cannot be defended:

  FAIR VALUE     what the property is worth, from the state's own
                 registered transaction band for its exact zone and
                 typology, positioned by condition and specs.
                 Days on market does NOT enter here. A house is not
                 worth less because it has been advertised for four
                 years; nothing about the building changed.

  TARGET OFFER   what you should pay. Fair value, but also capped by
                 what the seller has demonstrably been unable to
                 refuse. A listing unsold for four years has revealed
                 that its asking price is unachievable, and that is
                 information about the seller's position, not the
                 property's worth.

The published single number is TARGET OFFER. Fair value is carried
alongside it so the two can never be silently merged.

    target = min(fair_value, asking x (1 - negotiation_discount))

Taking the minimum is the whole logic. On an overpriced listing the
fair value binds and you are told not to pay more than the property is
worth. On an underpriced one the negotiation term binds and you are
still told to negotiate. Neither branch ever recommends paying above
the state's own valuation.

WHAT IS MEASURED AND WHAT IS ASSUMED — read this before quoting output.

  MEASURED  the OMI band (registered sale contracts, 2025-2), the zone
            (point-in-polygon, zones.py), the surface (search payload,
            rule confirmed in SOT S7), the national negotiation norm
            (Banca d'Italia, 7-8% through 2025, selling time 5.5 months).

  ASSUMED   CONDITION_POSITION and the DOM_DISCOUNT ladder below. Both
            are ours. Neither is measured. They are the direct
            descendants of the placeholder OMI bands that S001 turned
            into a "finding", so they are named, isolated at the top of
            this file, and printed with every run. Do not let them
            harden.
"""

import statistics as st
import sys

import config
import db
import analyze


# --- the assumed parameters, quarantined --------------------------------

# Where a property sits inside its OMI band, by condition.
#
# OMI publishes a min and a max for each zone/typology. For this
# province it publishes essentially only the NORMALE conservation state
# (107 of 108 rows), so condition CANNOT be taken from the state's data
# and has to be expressed as a position within the band instead.
#
# Positioning inside the band rather than multiplying outside it is a
# deliberate constraint: every number this engine publishes stays within
# a range the Agenzia delle Entrate itself printed. An agent can dispute
# our placement; they cannot dispute the range.
#
# 0.0 = band floor, 1.0 = band ceiling.
CONDITION_POSITION = {
    "Nuovo / In costruzione":  0.90,
    "Ottimo / Ristrutturato":  0.72,
    "Buono / Abitabile":       0.50,
    "Da ristrutturare":        0.18,
    None:                      0.50,   # 82 listings; the neutral default
}

# How far below asking a sale actually closes, by how long it has sat.
#
# ANCHORED AT THE TOP, EXTRAPOLATED BELOW IT. Banca d'Italia's quarterly
# survey of estate agents puts the national average discount at 7-8%
# through 2025 (Q1 7.0, Q3 7.5, Q4 ~8.0) with an average selling time of
# 5.5 months, and states the discount runs LARGER for older homes in
# slower inland towns. The Valtiberina is exactly that, and its stock
# sits for years rather than months, so the national figure is a FLOOR
# for this market, not an estimate of it.
#
# The first row is therefore the measured national norm applied to
# listings that are still inside the national selling time. Every row
# below it is an extrapolation with no measurement behind it.
#
# To replace these with something real: observe first_seen over time and
# record what listings actually close at. That is the same accumulate-
# forward problem as relist detection (SOT S8) and the reason to start
# accumulating now.
DOM_DISCOUNT = {
    "under 6 months": 0.08,   # anchored: national norm, within normal selling time
    "6-12 months":    0.12,   # assumed
    "1-2 years":      0.16,   # assumed
    "2-4 years":      0.20,   # assumed
    "over 4 years":   0.25,   # assumed
    None:             0.08,   # no date estimate -> the conservative floor
}

# Small nudges within the band for things the band does not resolve.
# Kept small on purpose: these are within-band variation, and the band
# is already only ~400 EUR/m2 wide. Anything bigger would be inventing
# precision the source data does not carry.
SPEC_NUDGE_MAX = 0.12

# OMI states its bands on surface basis L (lorda, walls included). The
# advertised Superficie is the sum of Principale rows (SOT S7) and it is
# NOT established whether those room surfaces are wall-inclusive. If they
# are wall-EXCLUSIVE, every EUR/m2 here is overstated by the wall factor
# (typically 5-10%) and every fair value is understated by the same.
#
# Left at 1.0 deliberately. Inventing a factor here would repeat exactly
# what S001 did with the rural bands. Measure it, then set it.
NET_TO_LORDA = 1.0
NET_TO_LORDA_MEASURED = False


# --- the engine ---------------------------------------------------------

def spec_position(L):
    """Nudge within the band for floor, bathrooms and lift, in [-1, 1].

    Deliberately crude. These are the fields with high yield in the
    search payload (floor 801/844, bathrooms 767/844) and they capture
    the obvious within-zone differences a buyer would notice.
    """
    score = 0.0
    n = 0

    floor = (L["floor"] or "").lower()
    if floor:
        n += 1
        if "terra" in floor and "piani" not in floor:
            score -= 0.5           # ground floor, single level
        elif "piani" in floor:
            score += 0.5           # multi-level, whole building
        elif any(d in floor for d in ("3", "4", "5")):
            score -= 0.2           # high floor, and lifts are rare here

    b = L["bathrooms"]
    if b:
        n += 1
        score += 0.5 if b >= 2 else -0.25

    return score / n if n else 0.0


def publishable(L, band, asking, surface, bucket):
    """Is this estimate fit to show a buyer? ('high'|'medium'|'suppress').

    This gate exists because of the single most dangerous failure mode
    this product has. The first run's headline "worst offender" was a
    EUR 6,75M luxury estate in Pieve Santo Stefano measured against R1
    ordinary-rural bands of 670-980 EUR/m2 — producing a fair value of
    EUR 1,2M and a EUR 5,5M "gap". That is not a finding. OMI publishes
    no band for a luxury estate (the same gap as the missing farmhouse
    category, SOT S8), so the comparison is meaningless, and it would
    have been the first number any journalist or agent looked at.

    A wrong number on the flagship listing discredits the 700 correct
    ones behind it. Suppress, never guess.
    """
    lo, hi, how = band
    eur_m2 = asking / surface

    if "zone-exact" not in how:
        return "suppress", "no exact OMI zone for this listing"
    if eur_m2 > 3 * hi:
        return "suppress", "asking EUR/m2 more than 3x band ceiling — OMI " \
                           "almost certainly publishes no band for this stock"
    if surface > 500:
        return "suppress", "surface over 500 m2 — outside ordinary " \
                           "residential stock OMI bands describe"
    if L["typology"] == "rustico":
        # OMI has no farmhouse category at all; we file these under Ville
        # e Villini by decision (SOT S8), and the alternative reading moves
        # them 14 pp. Honest to show, dishonest to show as precise.
        return "medium", "no OMI category for a farmhouse — banded by our " \
                         "choice, not the state's"
    if bucket is None:
        return "medium", "no reliable age estimate; negotiation term is the " \
                         "national floor"
    return "high", ""


def band_mid_lo_hi(omi_rows, L):
    """The OMI band for this listing, exact zone first. See analyze."""
    zp = L["zona_poly"] if "zona_poly" in L.keys() else None
    return analyze.band_for(omi_rows, L["typology"], L["zona_guess"],
                            zona_code=zp)


def fair_value(L, band, surface):
    """What the property is worth. No DOM term — see the module docstring."""
    lo, hi, how = band
    pos = CONDITION_POSITION.get(L["condition"], 0.50)
    pos += spec_position(L) * SPEC_NUDGE_MAX
    pos = max(0.0, min(1.0, pos))
    eur_m2 = lo + pos * (hi - lo)
    return eur_m2 * surface * NET_TO_LORDA, eur_m2, pos


def compute(conn):
    listings = db.all_listings(conn)
    omi_by_comune = {
        config.norm_comune(c): db.omi_for(conn, c, config.OMI_SEMESTER)
        for c in config.COMUNI
    }

    out, skipped = [], {}

    def skip(why):
        skipped[why] = skipped.get(why, 0) + 1

    for L in listings:
        if L["typology"] in getattr(config, "EXCLUDE_TYPOLOGIES", ()):
            skip("not comparable stock"); continue
        if analyze.is_auction(L):
            skip("judicial auction"); continue
        if not L["price"]:
            skip("no price"); continue
        surface = L["mq"]
        if not surface or surface <= 0:
            skip("no surface"); continue

        omi_rows = omi_by_comune.get(config.norm_comune(L["comune"]), [])
        band = band_mid_lo_hi(omi_rows, L)
        if not band:
            skip("no OMI band (Citerna is Perugia)"); continue

        fv, eur_m2_fair, pos = fair_value(L, band, surface)

        conf = analyze.dom_conf(L["dom_method"])
        bucket = analyze.dom_bucket(L["dom_est"], conf)
        disc = DOM_DISCOUNT.get(bucket, DOM_DISCOUNT[None])

        asking = L["price"]
        negotiated = asking * (1 - disc)
        target = min(fv, negotiated)
        binding = "value" if fv <= negotiated else "negotiation"

        conf_pub, why_not = publishable(L, band, asking, surface, bucket)

        out.append({
            "source_id": L["source_id"],
            "comune": L["comune"],
            "zona": (L["zona_poly"] if "zona_poly" in L.keys() else None)
                    or L["zona_guess"],
            "typology": L["typology"],
            "condition": L["condition"],
            "mq": surface,
            "asking": asking,
            "asking_eur_m2": round(asking / surface),
            "band_lo": band[0],
            "band_hi": band[1],
            "band_how": band[2],
            "pos_in_band": round(pos, 3),
            "fair_eur_m2": round(eur_m2_fair),
            "fair_value": round(fv),
            "dom_bucket": bucket,
            "dom_conf": conf,
            "discount_applied": disc,
            "target_offer": round(target),
            "binding": binding,
            "gap_eur": round(asking - target),
            "gap_pct": round((asking - target) / asking * 100, 1),
            "confidence": conf_pub,
            "confidence_note": why_not,
            "url": L["url"],
        })

    return out, skipped


# --- reporting ----------------------------------------------------------

def report(rows, skipped):
    print("=" * 72)
    print("BORGO VERO — TARGET OFFER")
    print("=" * 72)

    print("\n  !! CONTAINS ASSUMED PARAMETERS. Not all of this is measured.")
    print("     Condition positions and the DOM discount ladder below the")
    print("     first row are OURS, not the state's. See the module")
    print("     docstring before quoting any single number publicly.")
    if not NET_TO_LORDA_MEASURED:
        print("     Surface basis mismatch UNRESOLVED (OMI is lorda) — every")
        print("     fair value here may be understated by the wall factor.")

    print(f"\n  Priced: {len(rows)} listings")
    for why, n in sorted(skipped.items(), key=lambda kv: -kv[1]):
        print(f"    skipped {n:>4}  {why}")

    gaps = [r["gap_pct"] for r in rows]
    eur = [r["gap_eur"] for r in rows]
    print("\nHOW FAR ABOVE THE TARGET OFFER IS THE ASKING PRICE?")
    print(f"  median      {st.median(gaps):+.1f}%   (EUR {st.median(eur):,.0f})")
    print(f"  IQR         {analyze.quantile(gaps, .25):+.1f}% to "
          f"{analyze.quantile(gaps, .75):+.1f}%")
    print(f"  p90         {analyze.quantile(gaps, .90):+.1f}%")
    print(f"  total gap   EUR {sum(eur):,.0f} across {len(rows)} listings")

    nb = sum(1 for r in rows if r["binding"] == "value")
    print(f"\n  Which term binds?")
    print(f"    fair value  {nb:>4} ({nb/len(rows)*100:.0f}%)  asking exceeds "
          f"what the property is worth")
    print(f"    negotiation {len(rows)-nb:>4} ({(len(rows)-nb)/len(rows)*100:.0f}%)"
          f"  priced within value; still negotiate")

    print("\nBY DAYS ON MARKET")
    for label, _, _ in config.DOM_BUCKETS:
        v = [r["gap_pct"] for r in rows if r["dom_bucket"] == label]
        if v:
            print(f"  {label:18} n={len(v):<4} median {st.median(v):+.1f}%")

    print("\nBY CONDITION")
    for c in sorted(set(r["condition"] for r in rows), key=lambda x: str(x)):
        v = [r["gap_pct"] for r in rows if r["condition"] == c]
        if v:
            print(f"  {str(c):26} n={len(v):<4} median {st.median(v):+.1f}%")

    print("\n  !! The DOM table above is NOT a finding. Where the")
    print("     negotiation term binds (57%), the gap IS the assumed")
    print("     discount, so this table largely echoes DOM_DISCOUNT back.")
    print("     It becomes evidence only once the ladder is measured.")

    pub = [r for r in rows if r["confidence"] != "suppress"]
    sup = [r for r in rows if r["confidence"] == "suppress"]
    print(f"\nPUBLISHABILITY GATE")
    print(f"  publishable   {len(pub):>4} ({len(pub)/len(rows)*100:.0f}%)")
    print(f"    high        {sum(1 for r in pub if r['confidence']=='high'):>4}")
    print(f"    medium      {sum(1 for r in pub if r['confidence']=='medium'):>4}")
    print(f"  SUPPRESSED    {len(sup):>4} ({len(sup)/len(rows)*100:.0f}%)")
    reasons = {}
    for r in sup:
        reasons[r["confidence_note"]] = reasons.get(r["confidence_note"], 0) + 1
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {n:>4}  {why}")
    if pub:
        g = [r["gap_pct"] for r in pub]
        print(f"\n  Median gap, PUBLISHABLE listings only: {st.median(g):+.1f}%"
              f"   (EUR {st.median([r['gap_eur'] for r in pub]):,.0f})")
        print(f"  Total gap, publishable only: "
              f"EUR {sum(r['gap_eur'] for r in pub):,.0f}")

    print("\nWORST 10 PUBLISHABLE — largest euro gap between asking and target")
    for r in sorted(pub, key=lambda r: -r["gap_eur"])[:10]:
        print(f"  EUR {r['gap_eur']:>9,}  ({r['gap_pct']:+5.1f}%)  "
              f"{r['comune'][:14]:14} {r['typology'][:11]:11} "
              f"ask {r['asking']:>9,} -> {r['target_offer']:>9,}")

    print("\n  A worked example, as a buyer would read it:")
    ex = sorted(pub, key=lambda r: -r["gap_eur"])[0]
    print(f"    Asking            EUR {ex['asking']:,}")
    print(f"    OMI band          EUR {ex['band_lo']:.0f}-{ex['band_hi']:.0f}/m2"
          f"  ({ex['zona']}, {ex['band_how']})")
    print(f"    Condition         {ex['condition']} -> position {ex['pos_in_band']}")
    print(f"    Fair value        EUR {ex['fair_value']:,}  "
          f"({ex['fair_eur_m2']}/m2 x {ex['mq']} m2)")
    print(f"    On market         {ex['dom_bucket']} -> "
          f"{ex['discount_applied']*100:.0f}% negotiation")
    print(f"    TARGET OFFER      EUR {ex['target_offer']:,}   "
          f"({ex['binding']} binds)")
    print(f"    You are being asked EUR {ex['gap_eur']:,} more.")


def main():
    conn = db.connect()
    rows, skipped = compute(conn)
    if not rows:
        print("No priced rows. Run omi.py and zones.py first.")
        return
    report(rows, skipped)

    if "--csv" in sys.argv:
        import csv
        rows.sort(key=lambda r: -r["gap_eur"])
        with open("fairprice.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("\n  -> fairprice.csv")


if __name__ == "__main__":
    main()
