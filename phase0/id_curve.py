"""Job B — Immobiliare ID to date interpolation.

Listing IDs are broadly sequential over time, so a curve fitted through
known (id, date) pairs estimates the listing date of any ID.

WHY THIS RUNS IN WEEK ONE: it is the only route to days-on-market for
anything listed before your ingest starts. If access ends — block,
cease-and-desist, layout change you cannot follow — every property listed
before that day becomes permanently unmeasurable. The archive can only ever
grow forward from the moment access stops.

Known anchors (from prior work, approximate):
    ~47,000,000  ~= 2018-2019
    ~116,000,000 ~= 2024-2025

Two points give you a straight line. More points give you a curve, and ID
issuance is not linear — volume grew, so the curve bends. Every extra pair
materially improves estimates in the middle years, which is exactly where
the Valtiberina stale tail sits.
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
        print(f"Seeded {ANCHORS_PATH} with 2 prior estimates.")
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
    """Piecewise-linear interpolation. Returns (date, confidence)."""
    anchors = anchors or load_anchors()
    if len(anchors) < 2:
        return None, "none"

    pts = sorted((int(a["id"]), _to_ord(a["date"])) for a in anchors)
    ids = [p[0] for p in pts]
    lid = int(listing_id)

    if lid <= ids[0]:
        (x0, y0), (x1, y1) = pts[0], pts[1]
        conf = "low"          # extrapolating below the earliest anchor
    elif lid >= ids[-1]:
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        conf = "low"          # extrapolating beyond the latest anchor
    else:
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


def backfill(conn):
    """Apply estimates to every stored listing."""
    anchors = load_anchors()
    rows = conn.execute(
        "SELECT source, source_id FROM listings WHERE source='immobiliare'"
    ).fetchall()

    today = date.today()
    n = 0
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
        n += 1
    conn.commit()
    print(f"Estimated listing dates for {n} listings "
          f"from {len(anchors)} anchors.")


def report(conn):
    anchors = load_anchors()
    print(f"\nAnchors ({len(anchors)}):")
    for a in sorted(anchors, key=lambda x: x["id"]):
        print(f"  {a['id']:>12,}  {a['date']}  ({a['method']})")

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
