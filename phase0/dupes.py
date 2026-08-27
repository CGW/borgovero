"""Duplicate listing detector.

THE PROBLEM: the same property can be listed by several agencies at once,
each with its own listing ID. Nothing upstream deduplicates — `harvest()`
only skips repeats of the same `source_id` — so a property advertised by
three agencies casts three votes in every median, quantile and bucket.

That is not a tidiness problem. There is good reason to expect the
multiply-listed properties to be the hard-to-sell ones: a seller who
cannot shift a property adds agencies. If overpriced properties are
duplicated more than fairly-priced ones, duplication inflates the
overpricing finding in exactly the direction the project claims — which
makes it the first thing a critic should reach for.

This tool reports the scale and, more usefully, prints what the headline
numbers become once each property counts once.

    python3 dupes.py              # report
    python3 dupes.py --csv        # write dupes.csv for eyeballing

It changes nothing. Deduplication is a Phase 1 decision; this exists so
that decision is made against a measured number.
"""

import argparse
import csv
import re
import statistics as st
from collections import defaultdict

import config
import db


def norm_address(s):
    """Loose key: lowercase, drop punctuation, civici and filler words.

    'Via Roma, 12' and 'via roma 12/A' should collide. Deliberately
    aggressive — this is a candidate generator, not a decision.
    """
    s = (s or "").lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(via|viale|piazza|piazzale|strada|localita|loc|corso|"
               r"vicolo|largo|borgo|str|prov|provinciale)\b", " ", s)
    s = re.sub(r"\b\d+\w?\b", " ", s)      # civici: '12', '12a'
    # '12/A' has already lost its slash above, so the letter survives as a
    # lone token and would keep 'Viale Osimo 12/A' apart from 'Viale
    # Osimo'. No Italian street name is one character, so drop them.
    s = re.sub(r"\b\w\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def key_price_surface(r, mq_tol=0.03):
    """Exact price plus surface rounded to a tolerance band.

    The cross-portal test found exact price and approximate surface gave
    unambiguous matches across 165 listings — collisions are rare enough
    in a market this small to resolve by inspection.
    """
    if not r["price"] or not r["mq"]:
        return None
    bucket = round(r["mq"] / (r["mq"] * mq_tol)) if r["mq"] else 0
    return (r["price"], bucket)


def clusters(rows):
    """Group on price + surface band, then require address agreement."""
    by_key = defaultdict(list)
    for r in rows:
        k = key_price_surface(r)
        if k:
            by_key[k].append(r)

    out = []
    for k, group in by_key.items():
        if len(group) < 2:
            continue
        # Same price and size but genuinely different streets is a
        # coincidence, not a duplicate. Split on the address key.
        by_addr = defaultdict(list)
        for r in group:
            by_addr[norm_address(r["address_raw"])].append(r)
        for addr, sub in by_addr.items():
            if len(sub) > 1:
                out.append(sub)
    return sorted(out, key=len, reverse=True)


def collapsed_median(rows, cl):
    """Median EUR/m2 with each cluster counted once."""
    dupe_ids = {r["source_id"] for c in cl for r in c[1:]}
    vals = [r["price"] / r["mq"] for r in rows
            if r["price"] and r["mq"] and r["source_id"] not in dupe_ids]
    return (st.median(vals) if vals else None), len(vals)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true", help="write dupes.csv")
    args = ap.parse_args()

    conn = db.connect()
    rows = [r for r in db.all_listings(conn)
            if r["typology"] not in getattr(config, "EXCLUDE_TYPOLOGIES", ())]
    if not rows:
        print("No listings. Run run.py first.")
        return

    cl = clusters(rows)
    dupe_rows = sum(len(c) for c in cl)
    extra = dupe_rows - len(cl)

    print("=" * 68)
    print("DUPLICATE LISTINGS")
    print("=" * 68)
    print(f"  Listings                 {len(rows)}")
    print(f"  Clusters of 2+           {len(cl)}")
    print(f"  Listings inside them     {dupe_rows}")
    print(f"  Surplus votes            {extra} "
          f"({extra / len(rows) * 100:.1f}% of the dataset)")

    if not cl:
        print("\n  None found. Each property votes once; the medians are")
        print("  not weighted by how many agencies hold the mandate.")
        return

    base = [r["price"] / r["mq"] for r in rows if r["price"] and r["mq"]]
    med_before = st.median(base) if base else None
    med_after, n_after = collapsed_median(rows, cl)

    print(f"\n  Median EUR/m2, as ingested   {med_before:,.0f}  (n={len(base)})")
    print(f"  Median EUR/m2, deduplicated  {med_after:,.0f}  (n={n_after})")
    shift = (med_after - med_before) / med_before * 100
    print(f"  Shift                        {shift:+.1f}%")

    if abs(shift) < 1:
        print("\n  >>> Duplication does not move the headline. Note it and")
        print("      move on; dedup stays a Phase 1 concern.")
    else:
        direction = "DOWN" if shift < 0 else "UP"
        print(f"\n  >>> Deduplicating moves the median {direction} by "
              f"{abs(shift):.1f}%.")
        print("      Large enough to matter. The multiply-listed properties")
        print("      are not a random sample — a seller who cannot shift a")
        print("      property adds agencies — so this is a confound in the")
        print("      direction of the claim, and a critic will find it.")

    print(f"\n  Largest clusters:")
    for c in cl[:8]:
        r = c[0]
        agencies = sorted({x["agency_name"] or "?" for x in c})
        print(f"    {len(c)}x  EUR{r['price']:>9,}  {r['mq'] or 0:>4}m2  "
              f"{(r['address_raw'] or '?')[:30]:32}")
        print(f"        {', '.join(agencies)[:76]}")

    if args.csv:
        with open("dupes.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["cluster", "source_id", "price", "mq", "address",
                        "agency", "url"])
            for i, c in enumerate(cl):
                for r in c:
                    w.writerow([i, r["source_id"], r["price"], r["mq"],
                                r["address_raw"], r["agency_name"], r["url"]])
        print(f"\n  Wrote dupes.csv — {dupe_rows} rows in {len(cl)} clusters.")
        print("  Eyeball a few before trusting the number above; the key is")
        print("  deliberately loose and will occasionally pair two genuinely")
        print("  different flats that share a price and a street.")


if __name__ == "__main__":
    main()
