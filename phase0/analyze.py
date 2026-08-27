"""Phase 0 Job A — is the market actually overpriced?

Answers one question with a distribution rather than an anecdote, and
prints an explicit verdict against the decision gate in the spec.

The DOM split is the part that matters. Two very different markets can
produce the same overall median:

  (a) everything is uniformly ~30% over the band
  (b) fresh listings sit near the band and a stale tail sits 80% over,
      dragging the median up

They call for different sites. (a) is "this market is overpriced".
(b) is "stale listings are wildly overpriced and distort what everyone
believes the market is" — narrower, more defensible, and it points the
whole build at long-DOM properties.
"""

import csv
import statistics as st
import sys

import config
import db


# --- helpers -----------------------------------------------------------

def quantile(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    i = q * (len(s) - 1)
    lo, hi = int(i), min(int(i) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def fmt_pct(v):
    return "  n/a" if v is None else f"{v:+6.1f}%"


def band_for(omi_rows, typology, zona, force_tipologia=None):
    """Return (min, max, how) for a listing, or None.

    `force_tipologia` overrides the mapping, used to price the same
    listing against an alternative OMI category — see the rustico span in
    config.RUSTICO_ALT_TIPOLOGIA.

    The fallback here used to be `or list(omi_rows)` — every row for the
    comune. That is catastrophic on a real OMI file, because a comune's
    rows include Capannoni industriali, Magazzini, Box and Negozi. For
    Sansepolcro 2025-2 that fallback spans 280 to 1900 EUR/m2, so an
    unmapped typology gets compared against a band running from an
    industrial shed to a hillside villa, and essentially nothing can
    register as overpriced. Restricted to residential typologies only.
    """
    if force_tipologia:
        tipi = [force_tipologia]
    else:
        tipi = [t for t, ours in config.OMI_TIPOLOGIA_MAP.items()
                if typology in ours]
    rows = [r for r in omi_rows if r["tipologia"] in tipi]
    how = "typology"
    if not rows:
        residential = set(config.OMI_TIPOLOGIA_MAP)
        rows = [r for r in omi_rows if r["tipologia"] in residential]
        how = "residential-fallback"
    if not rows:
        return None

    # Filter to the right band of zones. Only centro storico used to be
    # filtered; everything else collapsed across every zone in the comune,
    # which on real data hands a rural farmhouse the same 1900 ceiling as
    # a hillside villa in C1 and makes it impossible for anything rural to
    # register as overpriced. OMI's own first letter carries the class.
    letters = config.ZONA_TO_FASCIA.get(zona)
    if letters:
        z = [r for r in rows
             if (r["zona_code"] or "").upper().startswith(letters)]
        if z:
            return min(r["min_eur_m2"] for r in z), \
                   max(r["max_eur_m2"] for r in z), f"{how}+zona"

    return min(r["min_eur_m2"] for r in rows), \
           max(r["max_eur_m2"] for r in rows), f"{how}+comune"


def dom_conf(dom_method):
    """'high' | 'medium' | 'bound_old' | 'bound_new' | None.

    id_curve.py writes this as 'immobiliare_id:<conf>'. Until S002 nothing
    read it back, so a fabricated date sat in the same bucket as a tightly
    bracketed one and no table could tell you which was which.
    """
    if not dom_method or ":" not in dom_method:
        return None
    return dom_method.rsplit(":", 1)[1]


def dom_bucket(dom, conf=None):
    """Which DOM bucket a listing belongs in, or None if not determinable.

    For a bracketed estimate this is the ordinary lookup.

    For a BOUND it is a containment test, and that is the point. A floor of
    2,000 days says the true age lies somewhere in [2000, inf). That
    interval sits entirely inside 'over 4 years', so the listing belongs
    there with certainty — no estimate required, nothing to dispute. A
    floor of 900 days spans two buckets and tells us nothing, so it is
    dropped rather than guessed.

    This is what rescues the oldest listings. They are the least precisely
    dated in the set and simultaneously the ones the whole thesis rests on,
    and a bound is enough to place them.
    """
    if dom is None:
        return None

    first_hi = config.DOM_BUCKETS[0][2]
    last_lo = config.DOM_BUCKETS[-1][1]

    if conf == "bound_old":
        # True age is >= dom. Certain only in the open-ended last bucket.
        return config.DOM_BUCKETS[-1][0] if dom >= last_lo else None
    if conf == "bound_new":
        # True age is <= dom. Certain only in the first bucket.
        return config.DOM_BUCKETS[0][0] if dom < first_hi else None
    if conf == "medium" and getattr(config, "DOM_MIN_CONFIDENCE", "medium") == "high":
        return None

    for label, lo, hi in config.DOM_BUCKETS:
        if lo <= dom < hi:
            return label
    return None


# --- core --------------------------------------------------------------

def surface_for(L, basis):
    """Which surface figure to divide the price by.

    Immobiliare publishes two: the net figure and the *commerciale* figure,
    which weights balconies, terraces and garages into the total. On a
    verified live listing they were 115 and 183 m2 — a 59% difference, which
    moves EUR/m2 by 59% and can single-handedly decide this test.

    Agencies quote commerciale because it makes EUR/m2 look lower. That is
    precisely the manipulation this project exists to surface, so the
    honest move is to report both rather than quietly pick one.
    """
    if basis == "commercial":
        return L["mq_commercial"] or L["mq"]
    return L["mq"]


def build_rows(conn, basis="net"):
    listings = db.all_listings(conn)
    omi_by_comune = {
        config.norm_comune(c): db.omi_for(conn, c, config.OMI_SEMESTER)
        for c in config.COMUNI
    }

    stats = {"total": len(listings), "with_mq": 0, "with_price": 0,
             "with_band": 0, "usable": 0, "with_mq_comm": 0,
             "dom_conf": {}, "dom_unbucketable": 0}
    out = []

    for L in listings:
        if L["price"]:
            stats["with_price"] += 1
        if L["mq"]:
            stats["with_mq"] += 1
        if L["mq_commercial"]:
            stats["with_mq_comm"] += 1

        mq = surface_for(L, basis)
        if not (L["price"] and mq and mq > 0):
            continue

        omi_rows = omi_by_comune.get(config.norm_comune(L["comune"]), [])
        band = band_for(omi_rows, L["typology"], L["zona_guess"])
        if not band:
            continue
        stats["with_band"] += 1

        lo, hi, how = band
        eur_m2 = L["price"] / mq

        # Sanity floor/ceiling — a EUR50/m2 or EUR20,000/m2 listing is a
        # parse error or a garage, not a signal.
        if eur_m2 < 150 or eur_m2 > 12000:
            continue
        stats["usable"] += 1

        # The same listing priced against the other defensible reading of
        # its typology. Null except for rustici, where OMI forces a choice.
        pct_alt = None
        if L["typology"] == "rustico":
            alt = band_for(omi_rows, L["typology"], L["zona_guess"],
                           force_tipologia=config.RUSTICO_ALT_TIPOLOGIA)
            if alt:
                pct_alt = round((eur_m2 - alt[1]) / alt[1] * 100, 1)

        conf = dom_conf(L["dom_method"])
        bucket = dom_bucket(L["dom_est"], conf)
        stats["dom_conf"][conf or "none"] = \
            stats["dom_conf"].get(conf or "none", 0) + 1
        if L["dom_est"] is not None and bucket is None:
            stats["dom_unbucketable"] += 1

        mid = (lo + hi) / 2
        out.append({
            "source_id": L["source_id"],
            "comune": L["comune"],
            "typology": L["typology"],
            "zona": L["zona_guess"],
            "agency": L["agency_name"],
            "mq_used": mq,
            "mq_net": L["mq"],
            "mq_commercial": L["mq_commercial"],
            "price": L["price"],
            "eur_m2": round(eur_m2, 1),
            "band_lo": lo,
            "band_hi": hi,
            "band_how": how,
            "pct_over_ceiling": round((eur_m2 - hi) / hi * 100, 1),
            "pct_over_ceiling_alt": pct_alt,
            "pct_over_mid": round((eur_m2 - mid) / mid * 100, 1),
            "dom_est": L["dom_est"],
            "dom_conf": conf,
            "dom_is_bound": {"bound_old": "floor",
                             "bound_new": "ceiling"}.get(conf, ""),
            "dom_bucket": bucket,
            "url": L["url"],
        })

    return out, stats


def summarize(vals, label, n_width=5):
    if not vals:
        print(f"  {label:22} n=—")
        return None
    med = st.median(vals)
    print(f"  {label:22} n={len(vals):<{n_width}} "
          f"median {fmt_pct(med)}   "
          f"IQR {fmt_pct(quantile(vals, .25))} to {fmt_pct(quantile(vals, .75))}   "
          f"p90 {fmt_pct(quantile(vals, .90))}")
    return med


def index_by_id(rows):
    return {r["source_id"]: r for r in rows}


def pair_row(label, net_rows, com_rows, key=None):
    """One line, both surface bases side by side.

    Never pick one silently. The two numbers together are more informative
    than either alone, and publishing both is what makes the finding
    unarguable rather than a choice someone can dispute.
    """
    nv = [r["pct_over_ceiling"] for r in net_rows if key is None or key(r)]
    cv = [r["pct_over_ceiling"] for r in com_rows if key is None or key(r)]
    if not nv and not cv:
        print(f"  {label:22}      —          —")
        return None, None
    nm = st.median(nv) if nv else None
    cm = st.median(cv) if cv else None
    print(f"  {label:22} n={len(nv):<5} {fmt_pct(nm)}     {fmt_pct(cm)}")
    return nm, cm


def pair_header(title):
    print(f"\n{title}")
    print(f"  {'':22} {'':6} {'floor area':>10}  {'commerciale':>12}")


def verdict(rows, overall_med):
    print("\n" + "=" * 72)
    print("DECISION GATE")
    print("=" * 72)

    by_bucket = {}
    for label, _, _ in config.DOM_BUCKETS:
        v = [r["pct_over_ceiling"] for r in rows if r["dom_bucket"] == label]
        if v:
            by_bucket[label] = st.median(v)

    fresh = next((by_bucket[l] for l, _, _ in config.DOM_BUCKETS
                  if l in by_bucket), None)
    stale = next((by_bucket[l] for l, _, _ in reversed(config.DOM_BUCKETS)
                  if l in by_bucket), None)
    spread = (stale - fresh) if (fresh is not None and stale is not None) else None

    if overall_med is None:
        print("\n  NO VERDICT — no usable rows. Fix ingest or OMI mapping.")
        return

    if overall_med >= config.GATE_STRONG:
        print(f"\n  THESIS HOLDS AS STATED.")
        print(f"  Median asking price is {overall_med:+.1f}% over the OMI band")
        print(f"  ceiling. Build the site as specced — every listing, every")
        print(f"  comune, the overpricing claim is general.")
    elif overall_med >= config.GATE_MODERATE:
        print(f"\n  THESIS HOLDS, MODERATELY.")
        print(f"  Median is {overall_med:+.1f}% over ceiling — real, but not the")
        print(f"  40% headline. Lead with the distribution and the tail, not")
        print(f"  with the median. 'Half of listings are more than X% over'")
        print(f"  is the honest framing.")
    else:
        print(f"\n  THESIS NOT SUPPORTED AS STATED.")
        print(f"  Median is only {overall_med:+.1f}% over ceiling.")

    if spread is not None:
        print(f"\n  Fresh listings:  {fresh:+.1f}% over ceiling")
        print(f"  Stale listings:  {stale:+.1f}% over ceiling")
        print(f"  Spread:          {spread:+.1f} percentage points")

        if spread >= 15:
            print(f"\n  >>> THE STALE TAIL IS THE STORY.")
            print(f"      Fresh listings sit near the band; old ones sit far")
            print(f"      above it. The defensible claim is not 'this market is")
            print(f"      overpriced' — it is 'stale listings are wildly")
            print(f"      overpriced and distort what everyone believes the")
            print(f"      market is worth'.")
            print(f"      Narrower, harder to argue with, and it points the")
            print(f"      whole site at long-DOM properties. Tier 7 ranked")
            print(f"      lists become the front page, not a side feature.")
        elif spread <= 5:
            print(f"\n  >>> UNIFORM OVERPRICING.")
            print(f"      Age barely predicts overpricing, so days-on-market is")
            print(f"      a weaker weapon here than assumed. The OMI gap carries")
            print(f"      the argument on its own. Worth rechecking the DOM")
            print(f"      estimates before accepting this — if most listings")
            print(f"      landed in one or two buckets, the bucketing may be")
            print(f"      too coarse to resolve a spread that is really there.")

    print()


def run_one(conn, basis, quiet_quality=False):
    rows, stats = build_rows(conn, basis)
    t = stats["total"] or 1

    if not quiet_quality:
        print("\nDATA QUALITY")
        print(f"  Listings ingested      {stats['total']}")
        print(f"  With price             {stats['with_price']} ({stats['with_price']/t*100:.0f}%)")
        print(f"  With net surface       {stats['with_mq']} ({stats['with_mq']/t*100:.0f}%)")
        print(f"  With commerciale       {stats['with_mq_comm']} ({stats['with_mq_comm']/t*100:.0f}%)")
        print(f"  Matched to OMI band    {stats['with_band']} ({stats['with_band']/t*100:.0f}%)")
        print(f"  Usable                 {stats['usable']} ({stats['usable']/t*100:.0f}%)")

        dc = stats["dom_conf"]
        if dc:
            note = {
                "high":      "bracketed by close anchors",
                "medium":    "bracketed, wide anchor gap",
                "bound_old": "older than the earliest anchor (floor only)",
                "bound_new": "newer than the latest anchor (ceiling only)",
                "none":      "no date estimate",
            }
            print("\n  DOM confidence (usable listings)")
            for k in ("high", "medium", "bound_old", "bound_new", "none"):
                if k in dc:
                    print(f"    {k:<10} {dc[k]:>5}   {note[k]}")
            if stats["dom_unbucketable"]:
                print(f"\n  {stats['dom_unbucketable']} listing(s) have a bound too "
                      f"loose to place in a bucket.")
                print("  They are excluded from every DOM split below and from")
                print("  the gate. They still count in the headline median,")
                print("  which does not depend on dates.")

        if stats["usable"] < 30:
            print("\n  !! Under 30 usable listings. Nothing below is a finding.")
            print("     Check the adapter probe and the OMI column mapping first.")
        elif stats["usable"] / t < 0.4:
            print("\n  !! Under 40% of listings are usable. Directional only —")
            print("     the parser is dropping too much, and what it drops")
            print("     may not be random.")

    return rows, stats


def surface_divergence(rows):
    """How much the two surface figures actually differ, in practice."""
    both = [r for r in rows if r["mq_net"] and r["mq_commercial"]]
    if not both:
        return None
    diffs = [(r["mq_commercial"] - r["mq_net"]) / r["mq_net"] * 100
             for r in both if r["mq_net"] > 0]
    if not diffs:
        return None
    return {
        "n": len(diffs),
        "median": st.median(diffs),
        "p90": quantile(diffs, 0.90),
    }


def main():
    conn = db.connect()

    print("=" * 72)
    print("VALTIBERINA PHASE 0 — HYPOTHESIS TEST")
    print(f"Comuni: {', '.join(config.COMUNI)}   OMI semester: {config.OMI_SEMESTER}")
    print("=" * 72)

    basis = getattr(config, "SURFACE_BASIS", "net")

    if basis != "both":
        rows, stats = run_one(conn, basis)
        return _single_basis_report(conn, rows, basis)

    net_rows, _ = run_one(conn, "net")
    com_rows, _ = run_one(conn, "commercial", quiet_quality=True)

    if not net_rows and not com_rows:
        print("\nNo usable rows. Stopping.")
        sys.exit(1)

    # --- The explanation, before any number ---------------------------
    print("\n" + "=" * 72)
    print("TWO SURFACES, TWO ANSWERS")
    print("=" * 72)
    print("""
  Every Italian listing carries two surface figures:

    superficie              the floor area you can walk on
    superficie commerciale  floor area PLUS a weighted share of
                            balconies, terraces, gardens and garages

  Price per square metre depends entirely on which one you divide by.
  Agencies quote commerciale, because a bigger denominator makes the
  same price look cheaper per metre.""")

    div = surface_divergence(net_rows)
    if div:
        print(f"\n  Across {div['n']} listings here, commerciale exceeds floor")
        print(f"  area by a median of {div['median']:+.0f}% (p90 {div['p90']:+.0f}%).")

    basis_rows = conn.execute(
        "SELECT DISTINCT surface_basis FROM omi_bands WHERE semester=?",
        (config.OMI_SEMESTER,)).fetchall()
    bases = [r["surface_basis"] for r in basis_rows if r["surface_basis"]]
    label = {"N": "NETTA (internal floor area)",
             "L": "LORDA (includes walls)"}
    if bases:
        print(f"\n  OMI quotes its bands on: "
              f"{', '.join(label.get(b, b) for b in bases)}")
        print("  Compare like with like, or the percentage is decoration.")
    else:
        print("\n  !! OMI surface basis unknown — the band's own basis was not")
        print("     captured. Run `python omi.py` again and read the report.")
        print("     Until then neither column below is properly anchored.")

    # --- Both columns, everywhere -------------------------------------
    pair_header("MEDIAN OVER OMI BAND CEILING")
    n_med, c_med = pair_row("all listings", net_rows, com_rows)

    pair_header("BY DAYS ON MARKET")
    n_bound = sum(1 for r in net_rows if r["dom_is_bound"])
    if n_bound:
        print(f"  ({n_bound} of {len(net_rows)} placed by a bound rather than an")
        print("   estimate — certain of the bucket, not of the exact age.)")
    for lbl, _, _ in config.DOM_BUCKETS:
        pair_row(lbl, net_rows, com_rows, lambda r, l=lbl: r["dom_bucket"] == l)

    pair_header("BY COMUNE")
    for c in config.COMUNI:
        pair_row(c, net_rows, com_rows,
                 lambda r, c=c: config.norm_comune(r["comune"])
                 == config.norm_comune(c))

    pair_header("BY TYPOLOGY")
    for typ in sorted({r["typology"] for r in net_rows}):
        pair_row(typ, net_rows, com_rows, lambda r, t=typ: r["typology"] == t)

    nv = [r["pct_over_ceiling"] for r in net_rows]
    print(f"\n  Share above ceiling, floor area:  "
          f"{sum(1 for v in nv if v > 0)/len(nv)*100:.0f}%")
    cv = [r["pct_over_ceiling"] for r in com_rows]
    if cv:
        print(f"  Share above ceiling, commerciale: "
              f"{sum(1 for v in cv if v > 0)/len(cv)*100:.0f}%")

    print("\n" + "-" * 72)
    print("  Publish both columns. Picking one hands an agent the argument")
    print("  that you picked wrong; showing both makes the gap itself the")
    print("  finding, and teaches the buyer the mechanism.")
    print("-" * 72)

    _rustico_span(net_rows)
    _robustness(net_rows, com_rows)
    verdict(net_rows, n_med)
    _write_csv(net_rows)


def _rustico_span(rows):
    """How much of the rural verdict rests on our own classification.

    OMI has no category for a stone farmhouse. We file them under Ville e
    Villini — the most generous band available — precisely so the finding
    cannot be dismissed as a chosen denominator. This block reports what
    the harsher reading would have produced, so the choice is visible
    rather than buried in a config file.

    If the two columns land on the same side of zero, the rural finding
    does not depend on the judgement and can be published flatly. If they
    straddle it, the honest headline is the span.
    """
    rust = [r for r in rows
            if r["typology"] == "rustico" and r["pct_over_ceiling_alt"] is not None]
    if not rust:
        return

    head = st.median([r["pct_over_ceiling"] for r in rust])
    alt = st.median([r["pct_over_ceiling_alt"] for r in rust])

    print("\nRUSTICO CLASSIFICATION — the judgement OMI forced on us")
    print(f"  n = {len(rust)} farmhouse listings")
    print(f"  as Ville e Villini (published):   {head:+.1f}%")
    print(f"  as {config.RUSTICO_ALT_TIPOLOGIA}:{alt:+.1f}%")
    print(f"  span:                             {abs(alt - head):.1f} pp")

    if (head > 0) == (alt > 0):
        side = "above" if head > 0 else "at or below"
        print(f"\n  >>> ROBUST. Both readings put rural listings {side} the")
        print("      band, so the finding does not depend on how a")
        print("      farmhouse is classified. Publish it flatly.")
    else:
        print("\n  >>> CLASSIFICATION-DEPENDENT. The two readings disagree on")
        print("      whether rural listings are overpriced at all. Publish")
        print("      the span, not a point — and say plainly that OMI has")
        print("      no category for the region's characteristic property.")
        print("      That absence is itself worth reporting.")


def _robustness(net_rows, com_rows):
    """Does the age story survive whichever surface you divide by?

    The headline median flips sign between the two bases, so on its own it
    is arguable. If the fresh-to-stale gradient holds in BOTH columns, that
    finding is not arguable — it does not depend on the choice, and an
    agent disputing the surface basis has not touched it.
    """
    def grad(rows):
        b = {}
        for lbl, _, _ in config.DOM_BUCKETS:
            v = [r["pct_over_ceiling"] for r in rows if r["dom_bucket"] == lbl]
            if v:
                b[lbl] = st.median(v)
        if len(b) < 2:
            return None
        keys = [l for l, _, _ in config.DOM_BUCKETS if l in b]
        return b[keys[-1]] - b[keys[0]]

    gn, gc = grad(net_rows), grad(com_rows)
    if gn is None or gc is None:
        return

    print("\nROBUSTNESS — does the finding survive the surface argument?")
    print(f"  Fresh-to-stale gradient, floor area:   {gn:+.1f} pp")
    print(f"  Fresh-to-stale gradient, commerciale:  {gc:+.1f} pp")

    if gn >= 15 and gc >= 15:
        print("\n  >>> HOLDS IN BOTH. The headline median flips sign depending")
        print("      on the surface basis, so on its own it is arguable. This")
        print("      does not: old listings are priced further above the band")
        print("      than fresh ones no matter which figure you divide by.")
        print("      Lead with this. An agent disputing surface has not")
        print("      touched it.")
    elif gn >= 15:
        print("\n  >>> Holds on floor area only. Weaker — an agent can argue")
        print("      the basis and take the finding with them. Say plainly")
        print("      that it is basis-dependent rather than being caught out.")
    else:
        print("\n  >>> No age gradient on either basis. Days-on-market is not")
        print("      the weapon here. Check the DOM confidence mix above")
        print("      before accepting that — if the oldest bucket is thin or")
        print("      carried entirely by bounds, the gradient may be real but")
        print("      unresolved rather than absent.")


def _single_basis_report(conn, rows, basis):
    if not rows:
        print("\nNo usable rows. Stopping.")
        sys.exit(1)
    over = [r["pct_over_ceiling"] for r in rows]
    print(f"\nASKING PRICE vs OMI BAND  (basis: {basis})")
    med = summarize(over, "vs band ceiling")
    summarize([r["pct_over_mid"] for r in rows], "vs band midpoint")
    print("\nBY DAYS ON MARKET")
    for lbl, _, _ in config.DOM_BUCKETS:
        summarize([r["pct_over_ceiling"] for r in rows
                   if r["dom_bucket"] == lbl], lbl)
    verdict(rows, med)
    _write_csv(rows)


def _write_csv(rows):
    out = "phase0_results.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: -r["pct_over_ceiling"]))
    print(f"Per-listing results -> {out} (worst-offender first)")
    print("Eyeball the top 20. If they look like parse errors rather than")
    print("real listings, fix the parser before believing the medians.\n")


if __name__ == "__main__":
    main()
