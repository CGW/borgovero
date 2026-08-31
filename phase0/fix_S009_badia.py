"""One-off: unfile the Badia Petroia listings from Badia Tedalda (S009).

THE BUG THIS CORRECTS

`_COMUNE_ALIASES` carried a bare needle 'badia' for badia-tedalda, and
resolve_comune() matches with startswith(). So Cortesi's BADIA PETROIA
cards — a frazione of Città di Castello, in Umbria, in Perugia province,
60 km from Badia Tedalda and under a different OMI order — were stored as
Badia Tedalda. Four listings, in a comune that has twenty-four.

Why it is worse than its size. §16d publishes comune conflicts as a
finding ("the same Fresciano flat filed under Badia Tedalda by two
agencies and Sestino by a third"). An agency that files a property
correctly would have been printed as contradicting an agency that also
filed it correctly, because WE moved one of them. The report would have
been accusing agencies of our own error, in public, on a page that
invites them to exercise a right of reply.

The alias list is fixed in adapters/agency_sites.py; this script repairs
the rows already on disk. Run the fixed harvester and this is a no-op.

    python3 fix_S009_badia.py --dry-run
    python3 fix_S009_badia.py

Idempotent. Run it on the real database on Christopher's machine — the
sandbox mount cannot journal sqlite.
"""

import argparse
import sqlite3
import sys

sys.path.insert(0, ".")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="phase0.sqlite")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT site, url, ref, comune, comune_raw, price, mq "
        "FROM agency_site_listings "
        "WHERE comune='badiatedalda' AND comune_raw LIKE '%petroia%'"
    ).fetchall()

    if not rows:
        print("nothing to fix — no badiatedalda row carries a petroia raw "
              "value.\n(Either already corrected, or the harvest predates "
              "the alias fix.)")
        return

    print(f"{len(rows)} listing(s) wrongly filed as Badia Tedalda:\n")
    for r in rows:
        print(f"  {r['site']:10} ref {str(r['ref'] or '-'):10} "
              f"raw={r['comune_raw']!r}")
        print(f"      {r['url']}")

    # Badia Petroia is not in config.COMUNI, so the honest destination is
    # its own name — visibly non-corpus — not another Valtiberina comune.
    if args.dry_run:
        print("\n--dry-run: nothing written. Would set comune="
              "'badiapetroia' (non-corpus, so these drop out of scope).")
        return

    conn.execute(
        "UPDATE agency_site_listings SET comune='badiapetroia' "
        "WHERE comune='badiatedalda' AND comune_raw LIKE '%petroia%'")
    conn.commit()
    print(f"\nfixed {len(rows)} row(s) -> comune='badiapetroia' "
          f"(outside config.COMUNI, so they no longer enter any band)")

    left = conn.execute(
        "SELECT COUNT(*) n FROM agency_site_listings "
        "WHERE comune='badiatedalda'").fetchone()["n"]
    print(f"Badia Tedalda now holds {left} agency-site listing(s).")


if __name__ == "__main__":
    main()
