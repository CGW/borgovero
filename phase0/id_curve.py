"""Job B — Immobiliare ID to date interpolation.

Listing IDs are broadly sequential over time, so a curve fitted through
known (id, date) pairs estimates the listing date of any ID.

WHY THIS RUNS IN WEEK ONE: it is the only route to days-on-market for
anything listed before your ingest starts. If access ends — block,
cease-and-desist, layout change you cannot follow — every property listed
before that day becomes permanently unmeasurable. The archive can only ever
grow forward from the moment access stops.

STATE AS OF S002: 23 measured anchors spanning 86,260,004 (2021-03-07) to
131,271,614 (2026-08-23), harvested from Internet Archive captures of the
Sansepolcro search page. Measured issuance averages 681k ids/month with a
69% spread between segments — non-linear, so interpolation is piecewise and
never a single line across the range.

The curve's weak end has MOVED. S001's problem was that 77% of the dataset
sat above the last anchor; that is fixed (dataset max 131,983,778 against a
131,271,614 anchor). What remains unanchored is the BOTTOM: nothing below
86,260,004, while the dataset reaches down to 56,648,574 and Anghiari's
lowest live ID is 69,315,424. The stale tail — the entire point of the
project — lives in exactly that unanchored region, which is why those
listings now get a bound rather than a fabricated date.

Priority for new pairs: pre-2021 (ids below 86M) first, everything else
second.
"""

import argparse
import bisect
import json
from datetime import date, datetime
from pathlib import Path

import config
import db

ANCHORS_PATH = "data/id_anchors.json"

# MEASURED from Internet Archive captures of the Sansepolcro search page,
# 2026-08-27. The largest listing ID visible in a snapshot is a hard lower
# bound on ID issuance at that date. See wayback_anchors.py.
#
# These SUPERSEDE the earlier working assumption of 47M = end-2018, which
# implied ~958k ids/month against a measured ~660k. That assumption made
# every listing look roughly a third newer than it is.
SEED_ANCHORS = [
    {"id": 86_260_004,  "date": "2021-03-07", "method": "wayback:sansepolcro"},
    {"id": 96_021_698,  "date": "2022-05-27", "method": "wayback:sansepolcro"},
    {"id": 102_604_630, "date": "2023-04-20", "method": "wayback:sansepolcro"},
    {"id": 112_185_785, "date": "2024-06-02", "method": "wayback:sansepolcro"},
    {"id": 131_271_614, "date": "2026-08-23", "method": "wayback:sansepolcro"},
]


def load_anchors():
    p = Path(ANCHORS_PATH)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(SEED_ANCHORS, indent=2))
        print(f"Seeded {ANCHORS_PATH} with {len(SEED_ANCHORS)} measured anchors.")
    return json.loads(p.read_text())


def add_anchor(listing_id, iso_date, method="manual"):
    anchors = load_anchors()
    anchors = [a for a in anchors if a["id"] != listing_id]
    anchors.append({"id": int(listing_id), "date": iso_date, "method": method})
    anchors.sort(key=lambda a: a["id"])
    Path(ANCHORS_PATH).write_text(json.dumps(anchors, indent=2))
    print(f"Added {listing_id} -> {iso_date} ({method}). "
          f"{len(anchors)} anchors total.")


def _to_ord(iso):
    return datetime.strptime(iso, "%Y-%m-%d").date().toordinal()


def estimate_date(listing_id, anchors=None):
    """Piecewise-linear interpolation. Returns (date, confidence).

    Confidence is one of:

        high        bracketed by two anchors less than 8M ids apart
        medium      bracketed, but by a wide gap
        bound_old   BELOW the earliest anchor. The date returned is the
                    earliest anchor's date, and the listing is at least
                    that old. DOM is a FLOOR, not an estimate.
        bound_new   ABOVE the latest anchor. The date returned is the
                    latest anchor's date, and the listing is at most that
                    old. DOM is a CEILING, not an estimate.

    The two bound cases used to extrapolate the nearest anchor pair's slope
    outwards, which invented a precise-looking date from nothing. ID
    issuance grew over time, so projecting the 2021-22 rate backwards makes
    pre-2021 listings look far NEWER than they are — the same direction as
    the 47M-anchor error this file already corrected once.

    Clamping instead gives up the fake precision and keeps a fact: an ID
    below the earliest anchor was issued before that anchor's date. That
    is weaker per-listing and much stronger in aggregate, because it cannot
    be wrong. See is_certain_bucket() in analyze.py for how a bound still
    lands a listing in the right bucket.
    """
    anchors = anchors or load_anchors()
    if len(anchors) < 2:
        return None, "none"

    pts = sorted((int(a["id"]), _to_ord(a["date"])) for a in anchors)
    ids = [p[0] for p in pts]
    lid = int(listing_id)

    if lid <= ids[0]:
        # Listed on or before the earliest anchor. Age is a lower bound.
        return date.fromordinal(pts[0][1]), "bound_old"
    if lid >= ids[-1]:
        # Listed on or after the latest anchor. Age is an upper bound.
        return date.fromordinal(pts[-1][1]), "bound_new"

    i = bisect.bisect_right(ids, lid)
    (x0, y0), (x1, y1) = pts[i - 1], pts[i]
    span = x1 - x0
    # Confidence is a function of how far apart the bracketing anchors
    # are. Tight brackets mean a trustworthy estimate.
    conf = "high" if span < 8_000_000 else "medium"

    if x1 == x0:
        return date.fromordinal(y0), conf

    frac = (lid - x0) / (x1 - x0)
    est = y0 + frac * (y1 - y0)
    est = max(min(est, date.today().toordinal()), date(2005, 1, 1).toordinal())
    return date.fromordinal(int(est)), conf


def bound_kind(conf):
    """'floor' | 'ceiling' | None — what a DOM figure with this conf means."""
    return {"bound_old": "floor", "bound_new": "ceiling"}.get(conf)


def curve_health(anchors=None):
    """Where the curve is trustworthy and where it is not."""
    anchors = anchors or load_anchors()
    pts = sorted((int(a["id"]), a["date"]) for a in anchors)
    gaps = [(pts[i][0], pts[i + 1][0], pts[i][1], pts[i + 1][1],
             pts[i + 1][0] - pts[i][0])
            for i in range(len(pts) - 1)]
    return {
        "n": len(pts),
        "lo_id": pts[0][0] if pts else None,
        "lo_date": pts[0][1] if pts else None,
        "hi_id": pts[-1][0] if pts else None,
        "hi_date": pts[-1][1] if pts else None,
        "wide_gaps": [g for g in gaps if g[4] >= 8_000_000],
    }


def backfill(conn):
    """Apply estimates to every stored listing."""
    anchors = load_anchors()
    rows = conn.execute(
        "SELECT source, source_id FROM listings WHERE source='immobiliare'"
    ).fetchall()

    today = date.today()
    n = 0
    tally = {}
    for r in rows:
        try:
            lid = int(r["source_id"])
        except (TypeError, ValueError):
            continue
        est, conf = estimate_date(lid, anchors)
        if not est:
            continue
        conn.execute(
            """UPDATE listings
               SET listed_date_est=?, dom_est=?, dom_method=?
               WHERE source=? AND source_id=?""",
            (est.isoformat(), (today - est).days,
             f"immobiliare_id:{conf}", r["source"], r["source_id"]),
        )
        tally[conf] = tally.get(conf, 0) + 1
        n += 1
    conn.commit()
    print(f"Estimated listing dates for {n} listings "
          f"from {len(anchors)} anchors.")

    if tally:
        note = {
            "high":      "bracketed, anchors <8M ids apart",
            "medium":    "bracketed, wide gap",
            "bound_old": "below earliest anchor — DOM is a FLOOR",
            "bound_new": "above latest anchor — DOM is a CEILING",
        }
        print("\n  By confidence:")
        for k in ("high", "medium", "bound_old", "bound_new"):
            if k in tally:
                print(f"    {k:<10} {tally[k]:>5}   {note[k]}")


def report(conn):
    anchors = load_anchors()
    print(f"\nAnchors ({len(anchors)}):")
    for a in sorted(anchors, key=lambda x: x["id"]):
        print(f"  {a['id']:>12,}  {a['date']}  ({a['method']})")

    h = curve_health(anchors)
    if h["n"] >= 2:
        print(f"\nCURVE COVERAGE")
        print(f"  Anchored range   {h['lo_id']:,} ({h['lo_date']})")
        print(f"                to {h['hi_id']:,} ({h['hi_date']})")
        print(f"  Below {h['lo_id']:,}: no anchor beneath. Those listings get a")
        print(f"    FLOOR only — 'listed on or before {h['lo_date']}'.")
        print(f"  Above {h['hi_id']:,}: no anchor above. Those get a CEILING")
        print(f"    only — 'listed on or after {h['hi_date']}'.")
        if h["wide_gaps"]:
            print(f"\n  Wide gaps (>8M ids — estimates inside these are 'medium'):")
            for lo, hi, d0, d1, span in h["wide_gaps"]:
                print(f"    {lo:,} .. {hi:,}   {d0} .. {d1}   ({span:,} ids)")
        else:
            print(f"\n  No gap wider than 8M ids. Every bracketed estimate is 'high'.")

    if len(anchors) < 4:
        print("\n  Only a straight line between these. ID issuance is not")
        print("  linear, so mid-range estimates are the weakest. Add pairs:")
        print("    python id_curve.py --add ID YYYY-MM-DD --method wayback")
        print("\n  Cheapest sources of real pairs:")
        print("    - Wayback CDX first-capture for any listing URL")
        print("    - Any listing whose text states when it was published")
        print("    - Agency pages that date their own listings")

    rows = conn.execute(
        "SELECT dom_method, COUNT(*) n, MIN(dom_est) lo, MAX(dom_est) hi "
        "FROM listings WHERE dom_est IS NOT NULL GROUP BY dom_method"
    ).fetchall()
    if rows:
        print("\nEstimated DOM by confidence:")
        for r in rows:
            print(f"  {r['dom_method']:28} n={r['n']:<5} "
                  f"range {r['lo']}-{r['hi']} days")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", nargs=2, metavar=("ID", "YYYY-MM-DD"))
    ap.add_argument("--method", default="manual")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    conn = db.connect()
    if args.add:
        add_anchor(int(args.add[0]), args.add[1], args.method)
    if args.backfill:
        backfill(conn)
    if args.report or not (args.add or args.backfill):
        report(conn)


if __name__ == "__main__":
    main()
