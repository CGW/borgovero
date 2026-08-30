"""Run the agency-site link harvest and build the url_alt mapping table.

    python3 harvest_links.py                 # harvest all four + match
    python3 harvest_links.py --site leonardi # one site
    python3 harvest_links.py --match-only    # re-match from stored harvest
    python3 harvest_links.py --db phase0.sqlite

WHAT COMES OUT

    agency_site_listings   every index card harvested (incl. rents and
                           withheld prices) — kept so unmatched rows are
                           data, not discards
    url_alt                the mapping table: portal listing -> own-site
                           URL, with provenance and match route
    data/url_alt.json      tracked export the site build consumes — the
                           build must never need the network
    data/agency_site_index.json  tracked export of the full harvest

MATCH ROUTES, IN ORDER (SOT §15)

    ref                    the agency's own reference printed on BOTH
                           channels. Checked per agency, not assumed —
                           today every portal row carries agency_ref
                           NULL, so this route reports itself idle
                           rather than silently doing nothing.
    price+surface+comune   exact price, same comune, surfaces within
                           15%. THE NO-COIN-FLIP RULE: if a site row
                           matches two portal rows this way — or two
                           site rows claim one portal row — NO match is
                           recorded for any of them. S004's five false
                           clusters all came from weak joins that
                           looked obvious.
    price+surface+comune (detail)
                           Cortesi's index cards carry no surface, so a
                           UNIQUE price+comune candidate earns ONE
                           detail-page fetch to read the mq, and the
                           surface test then decides. §15's "unless a
                           match is impossible without the detail".
    price+comune           what remains when no surface exists on
                           either side of a unique price+comune pair.
                           CANDIDATE-GRADE ONLY: consumers must apply
                           the §16d unconfirmed labelling discipline.
                           Stored because a lead is data; never render
                           it as a fact.

THE MATCH TABLE IS DATA, NOT A VERDICT. Nothing here publishes anything;
§16d still gates any same-property claim that names an agency.
"""

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, ".")
import config                                  # noqa: E402
from adapters import agency_sites              # noqa: E402

SURFACE_TOL = 0.15  # same tolerance §16d's price+surface route uses


def ensure_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS agency_site_listings (
        site TEXT NOT NULL, url TEXT NOT NULL, ref TEXT, price INTEGER,
        price_withheld INTEGER DEFAULT 0, mq INTEGER, comune TEXT,
        comune_raw TEXT, title TEXT, is_rent INTEGER DEFAULT 0,
        harvested_on TEXT, PRIMARY KEY (site, url))""")
    db.execute("""CREATE TABLE IF NOT EXISTS url_alt (
        source TEXT NOT NULL, source_id TEXT NOT NULL, site TEXT NOT NULL,
        url_alt TEXT NOT NULL, match_route TEXT NOT NULL,
        site_ref TEXT, site_price INTEGER, site_mq INTEGER,
        site_comune TEXT, site_title TEXT, matched_on TEXT,
        PRIMARY KEY (source, source_id, site))""")


def store_harvest(db, site, rows):
    db.execute("DELETE FROM agency_site_listings WHERE site=?", (site,))
    for r in rows:
        db.execute(
            "INSERT OR REPLACE INTO agency_site_listings VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?)",
            (r["site"], r["url"], r["ref"], r["price"], r["price_withheld"],
             r["mq"], r["comune"], r["comune_raw"], r["title"], r["is_rent"],
             date.today().isoformat()))
    db.commit()


def portal_rows(db, site):
    names = agency_sites.PORTAL_AGENCIES[site]
    q = ",".join("?" * len(names))
    return db.execute(
        f"SELECT source, source_id, url, comune, price, mq, agency_ref, "
        f"typology, typology_raw FROM listings WHERE source='immobiliare' "
        f"AND agency_name IN ({q})", names).fetchall()


def surfaces_close(a, b):
    if not a or not b:
        return False
    return abs(a - b) <= SURFACE_TOL * max(a, b)


def match_site(db, site, site_rows, allow_detail=False):
    """Returns (matches, report). A match is a dict ready for url_alt."""
    portal = portal_rows(db, site)
    rep = {"site": site, "harvested": len(site_rows), "portal": len(portal),
           "rents_skipped": 0, "withheld_skipped": 0, "matches": [],
           "ambiguous_dropped": 0, "detail_fetches": 0}

    # --- ref route: checked, not assumed ------------------------------
    portal_refs = {p[6] for p in portal if p[6]}
    if not portal_refs:
        rep["ref_route"] = ("idle — every portal row for this agency "
                            "carries agency_ref NULL")
    ref_matched_pids = set()
    matches = []
    if portal_refs:
        by_ref = defaultdict(list)
        for p in portal:
            if p[6]:
                by_ref[str(p[6]).strip().lower()].append(p)
        for r in site_rows:
            if not r["ref"]:
                continue
            cands = by_ref.get(str(r["ref"]).strip().lower(), [])
            if len(cands) == 1:
                p = cands[0]
                matches.append(_match(p, r, "ref"))
                ref_matched_pids.add(p[1])

    # --- price(+surface)+comune under the no-coin-flip rule -----------
    sale_rows = []
    for r in site_rows:
        if r["is_rent"]:
            rep["rents_skipped"] += 1
        elif not r["price"]:
            rep["withheld_skipped"] += 1
        else:
            sale_rows.append(r)

    pairs = []  # (portal_row, site_row, route)
    for r in sale_rows:
        for p in portal:
            if p[1] in ref_matched_pids or not p[4]:
                continue
            if r["comune"] and p[3] and \
                    config.norm_comune(p[3]) != r["comune"]:
                continue
            if p[4] != r["price"]:
                continue
            pairs.append([p, r, None])

    # Resolve surfaces; a unique price+comune Cortesi candidate may
    # spend one detail fetch here.
    by_site_url = defaultdict(list)
    by_portal_id = defaultdict(list)
    for pr in pairs:
        by_site_url[pr[1]["url"]].append(pr)
        by_portal_id[pr[0][1]].append(pr)

    kept = []
    for pr in pairs:
        p, r, _ = pr
        unique = (len(by_site_url[r["url"]]) == 1 and
                  len(by_portal_id[p[1]]) == 1)
        mq = r["mq"]
        route = None
        if mq and p[5]:
            if surfaces_close(mq, p[5]):
                route = "price+surface+comune"
        elif allow_detail and unique and not mq:
            mq = agency_sites.cortesi_detail_mq(r["url"])
            rep["detail_fetches"] += 1
            if mq and p[5] and surfaces_close(mq, p[5]):
                route = "price+surface+comune (detail)"
            elif mq and p[5]:
                route = None          # detail surface CONTRADICTS: no match
            else:
                route = "price+comune" if unique else None
        elif unique:
            route = "price+comune"
        if route:
            pr[2] = route
            pr[1] = dict(r, mq=mq)
            kept.append(pr)

    # No-coin-flip, applied to what survived the surface test: any site
    # row or portal row still claimed twice drops ALL its pairs — with
    # ONE principled exception. The rule bans choosing between two
    # candidates at the same price and surface. When surfaces inside an
    # ambiguity group differ and EXACT equality picks a unique pairing
    # on both sides (site 211 m² ↔ portal 211 m² while site 240 ↔
    # portal 240 beside it), that is not a coin flip — it is the
    # surface doing exactly the discriminating the route name promises.
    # Anything short of unique-exact still drops.
    by_site_url = defaultdict(list)
    by_portal_id = defaultdict(list)
    for pr in kept:
        by_site_url[pr[1]["url"]].append(pr)
        by_portal_id[pr[0][1]].append(pr)

    def exact(pr):
        return (pr[1]["mq"] and pr[0][5] and pr[1]["mq"] == pr[0][5])

    for pr in kept:
        p, r, route = pr
        site_claims = by_site_url[r["url"]]
        portal_claims = by_portal_id[p[1]]
        if len(site_claims) > 1 or len(portal_claims) > 1:
            exact_here = exact(pr)
            unique_exact = (
                exact_here
                and sum(1 for q in site_claims if exact(q)) == 1
                and sum(1 for q in portal_claims if exact(q)) == 1)
            if not unique_exact:
                rep["ambiguous_dropped"] += 1
                continue
        matches.append(_match(p, r, route))

    rep["matches"] = matches
    return matches, rep


def _match(p, r, route):
    return {
        "source": p[0], "source_id": p[1], "site": r["site"],
        "url_alt": r["url"], "match_route": route,
        "site_ref": r["ref"], "site_price": r["price"], "site_mq": r["mq"],
        "site_comune": r["comune"], "site_title": r["title"],
        "portal_url": p[2], "portal_price": p[4], "portal_mq": p[5],
        "portal_typology": p[7], "portal_typology_raw": p[8],
    }


def store_matches(db, site, matches):
    db.execute("DELETE FROM url_alt WHERE site=?", (site,))
    for m in matches:
        db.execute(
            "INSERT OR REPLACE INTO url_alt VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (m["source"], m["source_id"], m["site"], m["url_alt"],
             m["match_route"], m["site_ref"], m["site_price"], m["site_mq"],
             m["site_comune"], m["site_title"], date.today().isoformat()))
    db.commit()


def export_json(db):
    """Deterministic tracked exports — the site build's only input."""
    rows = db.execute(
        "SELECT source, source_id, site, url_alt, match_route, site_ref, "
        "site_price, site_mq, site_comune, site_title FROM url_alt "
        "ORDER BY source, source_id, site").fetchall()
    keys = ["source", "source_id", "site", "url_alt", "match_route",
            "site_ref", "site_price", "site_mq", "site_comune",
            "site_title"]
    with open("data/url_alt.json", "w") as f:
        json.dump([dict(zip(keys, r)) for r in rows], f,
                  ensure_ascii=False, indent=1)
    rows = db.execute(
        "SELECT site, url, ref, price, price_withheld, mq, comune, title, "
        "is_rent FROM agency_site_listings ORDER BY site, url").fetchall()
    keys = ["site", "url", "ref", "price", "price_withheld", "mq",
            "comune", "title", "is_rent"]
    with open("data/agency_site_index.json", "w") as f:
        json.dump([dict(zip(keys, r)) for r in rows], f,
                  ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="phase0.sqlite")
    ap.add_argument("--site", choices=list(agency_sites.HARVESTERS))
    ap.add_argument("--match-only", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    ensure_tables(db)
    sites = [args.site] if args.site else list(agency_sites.HARVESTERS)

    for site in sites:
        print(f"== {site} ==")
        if not args.match_only:
            rows = agency_sites.HARVESTERS[site]()
            store_harvest(db, site, rows)
        stored = db.execute(
            "SELECT site, url, ref, price, price_withheld, mq, comune, "
            "comune_raw, title, is_rent FROM agency_site_listings "
            "WHERE site=?", (site,)).fetchall()
        site_rows = [dict(zip(
            ["site", "url", "ref", "price", "price_withheld", "mq",
             "comune", "comune_raw", "title", "is_rent"], r))
            for r in stored]
        matches, rep = match_site(db, site, site_rows,
                                  allow_detail=(site == "cortesi"))
        store_matches(db, site, matches)

        by_route = defaultdict(int)
        for m in matches:
            by_route[m["match_route"]] += 1
        print(f"  harvested {rep['harvested']} index cards "
              f"({rep['rents_skipped']} rents, "
              f"{rep['withheld_skipped']} without price)")
        print(f"  portal rows: {rep['portal']}   matched: {len(matches)} "
              f"{dict(by_route)}   ambiguous dropped: "
              f"{rep['ambiguous_dropped']}")
        if "ref_route" in rep:
            print(f"  ref route: {rep['ref_route']}")
        if rep["detail_fetches"]:
            print(f"  detail fetches spent: {rep['detail_fetches']}")

    export_json(db)
    total = db.execute("SELECT count(*) FROM url_alt").fetchone()[0]
    print(f"\nurl_alt total: {total} — exported to data/url_alt.json")
    print("The match table is data, not a verdict (SOT §15/§16d).")


if __name__ == "__main__":
    main()
