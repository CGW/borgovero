"""Harvest the two agency sites into the database.

    python3 run_agencies.py              # both, everything
    python3 run_agencies.py --limit 20   # a taste
    python3 run_agencies.py --centogambe
    python3 run_agencies.py --marcellini

Companion to run.py, which does Immobiliare. Same store, same
`listings` table — rows are distinguished by `source`, and the primary
key is (source, source_id), so the three sources coexist without
colliding.

Two things this does that the adapters deliberately do not:

  COMUNE FILTER   Marcellini sells outside the Valtiberina (Verghereto,
                  and Citerna which is in Perugia province). The
                  adapters return whatever the site says; scope is
                  applied here, once, visibly, and the out-of-scope
                  count is reported rather than silently dropped.

  OBSERVATION     goes through db.observe() exactly like run.py, so
                  price changes on agency sites accumulate in
                  price_history from the first run. Agency sites are
                  where a price cut is likely to show up FIRST — a
                  portal listing is updated when someone gets round to
                  it; the agency's own site is their shop window.
"""

import argparse
from datetime import datetime, timezone

import config
import db
from adapters import agencies


def in_scope(comune):
    """Map a site's comune string onto config.COMUNI, or None."""
    if not comune:
        return None
    key = config.norm_comune(comune)
    for c in config.COMUNI:
        if config.norm_comune(c) == key:
            return c
    # Sites write 'sansepolcro - porta fiorentina', 'Caprese Michel...'.
    for c in config.COMUNI:
        ck = config.norm_comune(c)
        if key.startswith(ck) or ck.startswith(key[:12]):
            return c
    return None


def store(conn, recs, run_at, label):
    tally = {"new": 0, "price_change": 0, "unchanged": 0}
    out_of_scope, withheld, stored = {}, 0, 0

    for rec in recs:
        comune = in_scope(rec.get("comune"))
        if not comune:
            k = (rec.get("comune") or "?")[:24]
            out_of_scope[k] = out_of_scope.get(k, 0) + 1
            continue
        rec["comune"] = comune
        rec["fetched_at"] = run_at
        rec["price_withheld"] = 1 if rec.get("price_withheld") else 0
        if rec["price_withheld"]:
            withheld += 1
        rec.setdefault("typology", None)
        rec.setdefault("photo_ids", rec.pop("photo_urls", None))

        what = db.observe(conn, rec, run_at)
        tally[what] += 1
        db.upsert_listing(conn, rec)
        stored += 1
        if stored % 20 == 0:
            conn.commit()
    conn.commit()

    print(f"\n=== {label} ===")
    print(f"  stored {stored}   new {tally['new']}   "
          f"price changes {tally['price_change']}   unchanged {tally['unchanged']}")
    if withheld:
        print(f"  price WITHHELD on {withheld} of {stored} "
              f"({withheld/stored*100:.0f}%) — 'trattativa riservata'")
    if out_of_scope:
        n = sum(out_of_scope.values())
        print(f"  {n} listing(s) outside config.COMUNI, not stored:")
        for k, v in sorted(out_of_scope.items(), key=lambda kv: -kv[1])[:8]:
            print(f"      {v:>4}  {k}")
    return tally


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--centogambe", action="store_true")
    ap.add_argument("--marcellini", action="store_true")
    a = ap.parse_args()
    both = not (a.centogambe or a.marcellini)

    conn = db.connect()
    run_at = datetime.now(timezone.utc).isoformat()

    if a.centogambe or both:
        store(conn, agencies.harvest_centogambe(a.limit), run_at, "CENTOGAMBE")
    if a.marcellini or both:
        store(conn, agencies.harvest_marcellini(a.limit), run_at, "MARCELLINI")

    print("\n=== TOTAL BY SOURCE ===")
    for r in conn.execute(
            "SELECT source, COUNT(*) n, SUM(price IS NULL) nullprice "
            "FROM listings GROUP BY source ORDER BY n DESC"):
        print(f"  {r['source']:14} {r['n']:>5}   ({r['nullprice']} without a price)")


if __name__ == "__main__":
    main()
