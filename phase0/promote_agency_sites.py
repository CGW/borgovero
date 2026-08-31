"""Promote agency_site_listings into `listings` (SOT §16c's missing step).

WHY THIS EXISTS

S008 harvested eight agency sites into `agency_site_listings` and used
them only as a mapping table — `url_alt` on portal rows. That decision is
why the site publishes 764 pages while 1.165 harvested agency listings
produce none, and why the search box answers "no matching listing" for a
property that is plainly for sale (Romolini ref 1594, the case that
started S009).

A side table is also invisible to every matcher. `photomatch.py`,
`contradictions.py` and the index all read `listings`. Until these rows
live there they cannot be compared to anything, which is the whole
product.

WHAT THIS DOES NOT DO

It adds no network traffic and reads no new pages. It moves rows that
were already fetched and parsed. Everything it writes was already on
disk.

WHAT IT CANNOT GIVE THEM, AND WHY THAT MATTERS

  photos   `agency_site_listings` has no photo column — the S008 harvest
           read index cards, never detail pages. So these rows enter the
           corpus OUTSIDE the photo-match space, and photo is the only
           route that finds PRICE disagreements (§16d). Fixing that needs
           harvest_agency_details.py, which does fetch.
  dom      Days-on-market is derived from Immobiliare's ID curve (§6).
           An agency-site row has no portal id, so it has no DOM and must
           not be given a fabricated one. `dom_method` stays NULL.

Both are recorded per row rather than papered over: a listing that cannot
carry a figure should say so, not average one in.

REF IS NOT A CROSS-AGENCY KEY — measured S009

`agency_ref` is carried through because it is decisive WITHIN one agency
(their site ↔ their own portal listings). It is NOT unique across
agencies: joining agency_site_listings.ref to listings.agency_ref
produces 9 hits and all 9 are different properties — SICASA ref 0711
(€95.000, 100 m²) against Centogambe ref 0711 (€70.000, 40 m²), and so
on. Any matcher using this column must compare agency to itself first.

    python3 promote_agency_sites.py --dry-run
    python3 promote_agency_sites.py

Idempotent: a second run reports every row 'unchanged'. Run it on the
real database on Christopher's machine — the sandbox mount cannot
journal sqlite.
"""

import argparse
import hashlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

import config          # noqa: E402
import db              # noqa: E402
import run_agencies    # noqa: E402
from adapters.immobiliare import map_typology  # noqa: E402

# The display names the site already prints. Kept identical to the
# strings in agency_site_index / cerca.json so a promoted listing and its
# url_alt mapping do not disagree about who is selling it.
AGENCY_NAME = {
    "leonardi":      "Leonardi Immobiliare",
    "house":         "House Immobiliare",
    "cortesi":       "Immobiliare Cortesi",
    "lancisi":       "Immobiliare Lancisi",
    "now":           "NOW Estate",
    "romolini":      "Agenzia Romolini Immobiliare S.r.l.",
    "sicasa":        "SI CASA Immobiliare",
    "immobilinvest": "ImmobilInvest",
}


def source_id_for(row):
    """The agency's own reference is the natural id and survives a
    re-harvest that changes the URL slug — which Romolini demonstrably
    does (ref 1594 lives at an '_'-joined slug, ref 3018 at a '-'-joined
    one). Fall back to a URL digest only when there is no ref, and mark
    it so nobody later mistakes the digest for an agency reference."""
    ref = (row["ref"] or "").strip()
    if ref:
        return ref
    return "u" + hashlib.sha1(row["url"].encode()).hexdigest()[:10]


def build(conn, verbose=False):
    rows = conn.execute(
        "SELECT * FROM agency_site_listings "
        "WHERE COALESCE(is_rent,0)=0"
    ).fetchall()

    recs, skipped = [], {"no_comune": 0, "no_price_and_no_mq": 0}
    for r in rows:
        # A row with neither a price nor a surface cannot be published
        # and cannot be matched on anything but its ref. It is still a
        # real listing, so it is counted, not silently dropped.
        if r["price"] is None and r["mq"] is None and not r["price_withheld"]:
            skipped["no_price_and_no_mq"] += 1
            continue

        title = r["title"] or ""
        recs.append({
            "source": r["site"],
            "source_id": source_id_for(r),
            "url": r["url"],
            "comune": r["comune"] or r["comune_raw"],
            "typology": map_typology(None, title),
            "typology_raw": None,
            "title": title or None,
            "caption": title or None,
            "price": r["price"],
            "price_withheld": 1 if r["price_withheld"] else 0,
            "mq": r["mq"],
            "agency_ref": (r["ref"] or "").strip() or None,
            "agency_name": AGENCY_NAME.get(r["site"], r["site"]),
            "photo_ids": None,       # index cards only — see module docstring
            "dom_est": None,         # no portal id, so no ID-curve date
            "dom_method": None,
        })
    return recs, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    conn = db.connect()
    conn.row_factory = __import__("sqlite3").Row
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    recs, skipped = build(conn, args.verbose)

    # in_scope() is applied inside store(), which also reports what fell
    # outside config.COMUNI — Leonardi and Cortesi both carry comuni well
    # beyond the Valtiberina and that count is worth seeing every run.
    by_site = {}
    for rec in recs:
        by_site.setdefault(rec["source"], []).append(rec)

    print(f"{len(recs)} sale listings to promote, from "
          f"{len(by_site)} agency sites")
    if skipped["no_price_and_no_mq"]:
        print(f"  {skipped['no_price_and_no_mq']} skipped: no price, no "
              f"surface, price not marked withheld")

    if args.dry_run:
        print("\n--dry-run: nothing written\n")
        for site, rs in sorted(by_site.items(), key=lambda kv: -len(kv[1])):
            in_scope = sum(1 for r in rs if run_agencies.in_scope(r["comune"]))
            pub = sum(1 for r in rs
                      if run_agencies.in_scope(r["comune"])
                      and r["price"] and r["mq"])
            print(f"  {site:14} {len(rs):4} rows   "
                  f"{in_scope:4} in scope   {pub:4} price+surface")
        return

    for site, rs in sorted(by_site.items()):
        run_agencies.store(conn, rs, run_at, f"{site} (promoted)")

    print("\nPromoted. These rows carry NO photos and NO days-on-market "
          "by construction —\nrun harvest_agency_details.py to give them "
          "photos, which is what lets\nphotomatch find price "
          "disagreements against the portal corpus.")


if __name__ == "__main__":
    main()
