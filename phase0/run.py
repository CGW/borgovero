"""Phase 0 ingest orchestrator."""

import argparse
import sys
from datetime import datetime, timezone

import config
import db
import fetcher
from adapters import immobiliare


def ingest(conn, comuni, refetch=False):
    """Harvest straight from search pages.

    Everything Phase 0 needs is embedded in the search results JSON, so
    this costs one request per 25 listings rather than one per listing.
    See the adapter docstring.
    """
    total_new = 0

    for comune in comuni:
        print(f"\n=== {comune.upper()} ===")
        surl = immobiliare.search_url(comune)
        print(f"robots.txt: {fetcher.robots_status(surl)}")

        n_new = n_err = 0
        for rec in immobiliare.harvest(comune):
            try:
                rec["fetched_at"] = datetime.now(timezone.utc).isoformat()
                db.upsert_listing(conn, rec)
                n_new += 1
            except Exception as e:
                print(f"  store error on {rec.get('source_id')}: {e}")
                n_err += 1

        conn.commit()
        print(f"  stored {n_new}" + (f", {n_err} errors" if n_err else ""))
        total_new += n_new

    return total_new


def health(conn):
    """Field yield. Spec section 3 — never trust a partial crawl."""
    row = conn.execute("""
        SELECT COUNT(*) n,
               SUM(price IS NOT NULL) p,
               SUM(mq IS NOT NULL) m,
               SUM(mq_commercial IS NOT NULL) mc,
               SUM(vani IS NOT NULL) v,
               SUM(macrozone IS NOT NULL) z,
               SUM(agency_name IS NOT NULL) a,
               SUM(typology != 'unknown') t
        FROM listings
    """).fetchone()

    n = row["n"] or 0
    if not n:
        print("\nNo listings stored.")
        return False

    def pct(x):
        return (x or 0) / n * 100

    print(f"\nFIELD YIELD  (n={n})")
    checks = [
        # 95% was aspirational. Measured across 844 real listings, price
        # yield is 93.7% and the missing ~6% are 'prezzo su richiesta' —
        # genuinely absent from the page, not lost by the parser. A
        # threshold that always trips teaches you to ignore it, and it
        # sent the last run chasing a deep_find() bug that did not exist.
        ("price", pct(row["p"]), 90),
        ("mq", pct(row["m"]), 80),
        ("mq_commercial", pct(row["mc"]), 0),
        ("vani", pct(row["v"]), 50),
        ("macrozone", pct(row["z"]), 0),
        ("agency", pct(row["a"]), 0),
        ("typology", pct(row["t"]), 70),
    ]
    ok = True
    for name, got, floor in checks:
        flag = "" if got >= floor else f"  <-- below {floor}% threshold"
        if got < floor:
            ok = False
        print(f"  {name:10} {got:5.1f}%{flag}")

    if not ok:
        print("\n  !! Yield below threshold. Run:")
        print("       python3 -m adapters.immobiliare --probe")
        print("     and check the JSON key names before analysing.")
        print("     Note: some absences are real. 'prezzo su richiesta'")
        print("     listings carry no price, and mq_commercial is not in")
        print("     the search payload at all — detail pages return 403.")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Phase 0 ingest")
    ap.add_argument("--comuni", nargs="*", default=config.COMUNI)
    ap.add_argument("--refetch", action="store_true",
                    help="ignore the HTML cache")
    ap.add_argument("--health-only", action="store_true")
    args = ap.parse_args()

    conn = db.connect()

    if not args.health_only:
        if config.CONTACT_URL == "https://example.org/about":
            print("!! Set CONTACT_URL in config.py before running.")
            print("   An identifiable user agent is the cheapest protection")
            print("   you have. Takes ten seconds.\n")
            sys.exit(1)
        ingest(conn, args.comuni, refetch=args.refetch)

    health(conn)

    print("\nNext:")
    print("  python3 omi.py --inspect        # check columns")
    print("  python3 omi.py                  # load bands")
    print("  python3 id_curve.py --backfill  # estimate listing dates")
    print("  python3 analyze.py              # the answer")


if __name__ == "__main__":
    main()
