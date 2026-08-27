"""Harvest ID-to-date anchors from the Internet Archive.

THE IDEA, and why it is better than dating listings one at a time:

Archived copies of the *search results* page are far more numerous than
archived copies of individual listings — 113 snapshots of the Sansepolcro
page exist, spanning 2021 to 2026. Each one shows ~25 listing IDs that were
live on that date. The largest ID in a snapshot is therefore a hard fact:
IDs at least that high existed by then.

Plot max-ID against snapshot date across many snapshots and you have the ID
issuance curve measured directly, rather than interpolated between two
guesses. One CDX query plus a few dozen page fetches replaces the entire
anchor problem.

    python wayback_anchors.py --comune sansepolcro --max-snapshots 25
    python id_curve.py --report

VERIFIED 2026-08-27. Five snapshots gave:

    2021-03-07     86.260.004
    2022-05-27     96.021.698
    2023-04-20    102.604.630
    2024-06-02    112.185.785
    2026-08-23    131.271.614

Issuance is close to linear at 610k-715k IDs/month across the whole range,
which is what makes interpolation safe once the anchors are real.

THE CORRECTION THIS PRODUCED: the previously assumed anchor of 47M = end of
2018 implied ~958k IDs/month. The measured rate is ~30% slower, so every
listing looked far newer than it is — which is why the first DOM pass
returned a median of 0,9 years for a market known to run 2-4.
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

CDX = "https://web.archive.org/cdx/search/cdx"
WB = "https://web.archive.org/web/{ts}/{url}"
UA = "ValtiberinaPriceResearch/0.1 (research; contact: set CONTACT_URL)"


def cdx_snapshots(target_url, limit=200):
    """Every archived capture of a page, oldest first."""
    q = urllib.parse.urlencode({
        "url": target_url, "output": "json", "limit": limit,
        "fl": "timestamp,statuscode", "filter": "statuscode:200",
        "collapse": "timestamp:6",     # at most one per month
    })
    req = urllib.request.Request(f"{CDX}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        rows = json.loads(r.read().decode())
    return [x[0] for x in rows[1:]] if len(rows) > 1 else []


def ids_in_snapshot(target_url, ts, delay=3.0):
    """Listing IDs present in one archived capture."""
    time.sleep(delay)
    url = WB.format(ts=ts, url=target_url)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"  {ts}: {e}")
        return None
    ids = {int(m) for m in re.findall(r"/annunci/(\d{6,})", html)}
    return sorted(ids) or None


def harvest(comune, max_snapshots, delay):
    target = f"https://www.immobiliare.it/vendita-case/{comune}/"
    snaps = cdx_snapshots(target)
    print(f"{len(snaps)} archived captures of the {comune} search page")
    if not snaps:
        return []

    # Spread the sample across the whole span rather than clustering.
    if len(snaps) > max_snapshots:
        step = len(snaps) / max_snapshots
        snaps = [snaps[int(i * step)] for i in range(max_snapshots)]

    anchors = []
    for ts in snaps:
        ids = ids_in_snapshot(target, ts, delay)
        if not ids:
            continue
        d = datetime.strptime(ts[:8], "%Y%m%d").date()
        anchors.append({"id": max(ids), "date": d.isoformat(),
                        "method": f"wayback:{comune}", "n_ids": len(ids)})
        print(f"  {d}  max_id={max(ids):>12,}  ({len(ids)} ids)")
    return anchors


def report(anchors):
    """Issuance rate between consecutive anchors — the linearity check."""
    if len(anchors) < 2:
        return
    a = sorted(anchors, key=lambda x: x["date"])
    print("\nISSUANCE RATE BETWEEN ANCHORS")
    rates = []
    for x, y in zip(a, a[1:]):
        d0 = datetime.fromisoformat(x["date"]).date()
        d1 = datetime.fromisoformat(y["date"]).date()
        months = (d1 - d0).days / 30.44
        if months < 1:
            continue
        rate = (y["id"] - x["id"]) / months
        rates.append(rate)
        print(f"  {x['date']} -> {y['date']}   "
              f"{rate:>10,.0f} ids/month  ({months:.1f} mo)")
    if rates:
        spread = (max(rates) - min(rates)) / (sum(rates) / len(rates)) * 100
        print(f"\n  mean {sum(rates)/len(rates):,.0f}/month, "
              f"spread {spread:.0f}%")
        if spread < 40:
            print("  Close to linear — interpolation between these is safe.")
        else:
            print("  Non-linear. Use piecewise interpolation, never a "
                  "single straight line across the whole range.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comune", default="sansepolcro")
    ap.add_argument("--max-snapshots", type=int, default=20)
    ap.add_argument("--delay", type=float, default=3.0,
                    help="seconds between archive.org fetches")
    ap.add_argument("--write", action="store_true",
                    help="merge into data/id_anchors.json")
    args = ap.parse_args()

    anchors = harvest(args.comune, args.max_snapshots, args.delay)
    report(anchors)

    if args.write and anchors:
        import id_curve
        existing = id_curve.load_anchors()
        # Drop the prior estimates once real measurements exist.
        existing = [a for a in existing if a.get("method") != "prior_estimate"]
        seen = {a["id"] for a in existing}
        merged = existing + [a for a in anchors if a["id"] not in seen]
        from pathlib import Path
        Path(id_curve.ANCHORS_PATH).write_text(json.dumps(merged, indent=2))
        print(f"\nWrote {len(merged)} anchors to {id_curve.ANCHORS_PATH}")
        print("Prior estimates removed — measured values supersede them.")
        print("Now run: python id_curve.py --backfill && python analyze.py")
    elif anchors:
        print("\nRe-run with --write to merge these into the curve.")


if __name__ == "__main__":
    main()
