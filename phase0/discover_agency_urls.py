"""Sitemap enumeration for the agency sites — finding the orphans (S009).

THE CASE THAT FORCED THIS

Romolini ref 1594 is a live listing: €140.000, 171 m² interni, an
apartment on Piazza Torre di Berta in Sansepolcro, 2.955 views on their
counter. CasaZebra's search box answered "no matching listing in our
archive", and it was right — the listing had never been seen.

S008 harvested Romolini by walking /it/comune/<comune>.php, because their
robots.txt disallows query-string pagination and those path-based index
pages were the way in. But 1594 is not linked from the Sansepolcro index.
It is an ORPHAN: reachable, indexed by Google, selling — and invisible to
a crawler that only follows the agency's own navigation.

An index built by following a site's menus inherits that site's decisions
about what to show. The sitemap is the site's own list of what exists,
which is a different and better question to ask.

    romolini    /sitemap.xml, ADVERTISED IN THEIR robots.txt
                8.626 <loc>, 2.875 italian, 1.044 listing-shaped
                against 40 harvested from the comune indexes
    wordpress   leonardi, house, cortesi, lancisi, sicasa, now all
                publish sitemap_index.xml with an immobile-sitemap.xml
    immobilinvest   no sitemap (404). It has one catalog page and the
                existing harvest already reads all of it.

WHAT THIS COSTS, AND THE PART THAT IS NOT FREE

Enumerating a sitemap is one or two requests. But a sitemap URL carries
no price and no surface, so deciding whether a listing is even IN SCOPE
means fetching it. Romolini's slugs name the comune often enough to
triage (54 sansepolcro, 47 caprese, 36 anghiari, 5 citerna, 4 monterchi,
3 pieve) but 895 of 1.044 name no comune at all, and those are only
knowable by reading them.

So --ingest fetches, at config.REQUEST_DELAY_S, through fetcher (robots
consulted per URL, everything cached on disk). Default is the slug-triaged
set; --all takes the untriaged remainder too and is much slower.

    python3 discover_agency_urls.py --report
    python3 discover_agency_urls.py --site romolini --ingest --dry-run
    python3 discover_agency_urls.py --site romolini --ingest

Run --ingest on Christopher's machine — the sandbox mount cannot journal
sqlite, and its calls cap at 120s.
"""

import argparse
import re
import sys
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, ".")

import config    # noqa: E402
import db        # noqa: E402
import fetcher   # noqa: E402
from adapters.agency_sites import resolve_comune  # noqa: E402

SITEMAPS = {
    "romolini":      "https://www.romolini.com/sitemap.xml",
    "leonardi":      "https://www.leonardiimmobiliare.it/sitemap.xml",
    "house":         "https://www.houseimmobiliare.info/sitemap.xml",
    "cortesi":       "https://www.immobiliarecortesi.net/sitemap_index.xml",
    "lancisi":       "https://www.immobiliarelancisi.it/sitemap_index.xml",
    "sicasa":        "https://www.sicasaimmobiliare.info/sitemap.xml",
    "now":           "https://nowestate.it/wp-sitemap.xml",
    # immobilinvest deliberately absent: no sitemap, one catalog page,
    # already fully harvested. Its absence here is a finding, not a gap.
}

# What a listing URL looks like on each site. Romolini ends every listing
# slug with the reference id, joined by '_' on older pages and '-' on
# newer ones — 1594 is an '_' and 3018 is a '-', which is the same agency
# changing its slug format and keeping both live.
LISTING_RE = {
    "romolini":  re.compile(r"/it/[a-z0-9_\-]+[_-]\d{3,5}$"),
    "leonardi":  re.compile(r"/immobile/"),
    "house":     re.compile(r"/immobile/"),
    "cortesi":   re.compile(r"/immobile/"),
    "lancisi":   re.compile(r"/immobile/"),
    "sicasa":    re.compile(r"/immobile/"),
    "now":       re.compile(r"/proprieta/"),
}

COMUNE_TOKENS = ("sansepolcro", "anghiari", "citerna", "monterchi",
                 "sestino", "badia-tedalda", "badiatedalda",
                 "caprese", "pieve-santo-stefano", "pievesantostefano",
                 "pieve")


def fetch_xml(url):
    try:
        body, _, _ = fetcher.get(url)
        return body or ""
    except Exception as e:
        print(f"  [sitemap {type(e).__name__}] {url}")
        return ""


def enumerate_sitemap(url, depth=0, seen=None):
    """All <loc> values, following one level of sitemap index nesting."""
    seen = seen if seen is not None else set()
    if url in seen or depth > 2:
        return []
    seen.add(url)
    body = fetch_xml(url)
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
    if not locs:
        return []
    # A sitemap index lists sitemaps; a urlset lists pages. Telling them
    # apart by the tag is more reliable than by the filename, since
    # 'sitemap.xml' is used for both across these seven sites.
    if "<sitemapindex" in body:
        out = []
        for s in locs:
            out += enumerate_sitemap(s, depth + 1, seen)
        return out
    return locs


def slug_comune(url):
    """The comune a URL's own slug names, or None. Triage only — a slug
    that names nothing is not out of scope, it is merely unknown, and the
    two must not be collapsed."""
    low = url.lower()
    for tok in COMUNE_TOKENS:
        if tok in low:
            c = resolve_comune(tok)
            for known in config.COMUNI:
                if config.norm_comune(known) == c:
                    return known
    return None


def parse_romolini_detail(html, url):
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))

    def grab(rx, cast=str):
        m = re.search(rx, t)
        if not m:
            return None
        v = m.group(1)
        return cast(v.replace(".", "")) if cast is int else v

    price = grab(r"Prezzo richiesto:?\s*€\s*([\d.]+)", int)
    # 'Interni' is Romolini's own habitable figure and is the one that
    # belongs in mq. 'Esterni' is land and must never land in the same
    # column — SOT §7 is entirely about not merging those two.
    mq = grab(r"Interni:?\s*([\d.]+)\s*mq", int)
    ref = grab(r"Rif\.\s*(\d+)")

    # The breadcrumb is region - province - comune, which is stronger than
    # guessing from the slug: it is the agency's own filing.
    # Anchored on 'Prezzo richiesto', which is what follows the breadcrumb
    # in the flattened text. An earlier version ended the capture on \s{2,}
    # — impossible, because the line above collapses all whitespace to
    # single spaces. It matched nothing, silently, and every one of the 888
    # listings whose slug names no comune would have been discarded as out
    # of scope. A regex that cannot match looks exactly like a site that
    # does not publish the field.
    comune = None
    bc = re.search(r"(?:Toscana|Umbria)\s*-\s*[A-Za-zÀ-ù' ]+?\s*-\s*"
                   r"([A-Za-zÀ-ù' ]{3,40}?)\s+Prezzo\b", t)
    if bc:
        comune = bc.group(1).strip()
    if not comune:
        comune = slug_comune(url)

    # WITHHELD ONLY WHEN THERE IS NO PRICE. Matching 'riservat' anywhere on
    # the page marked ref 1594 withheld while '€ 140.000' sat in the same
    # document — the word also appears in their privacy boilerplate
    # ('riservatezza') and in unrelated cross-sell cards. A flag that fires
    # next to the figure it denies is worse than no flag.
    withheld = price is None and bool(
        re.search(r"prezzo\s*(?:su richiesta|riservat)", t, re.I))

    # 'Rif. 1594 Appartamento Torre di Berta SANSEPOLCRO, TOSCANA: ...' —
    # the agency's short name, then their ALL-CAPS headline. Stop at the
    # caps. Same \s{2,} defect as the breadcrumb above; title is not
    # cosmetic, promote_agency_sites infers typology from it and typology
    # picks the surface deflator, so an empty title moves the band.
    title = grab(r"Rif\.\s*\d+\s+([A-Za-zÀ-ù0-9'’, \-]{4,90}?)"
                 r"(?=\s+[A-ZÀ-Ù]{2,}[A-ZÀ-Ù,' ]{5,})")
    return dict(ref=ref, price=price, mq=mq, comune=comune,
                title=title, price_withheld=1 if withheld else 0)


DETAIL_PARSERS = {"romolini": parse_romolini_detail}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=sorted(SITEMAPS))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="also read listings whose slug names no comune")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = db.connect()
    conn.row_factory = __import__("sqlite3").Row
    sites = [args.site] if args.site else sorted(SITEMAPS)

    for site in sites:
        locs = enumerate_sitemap(SITEMAPS[site])
        rx = LISTING_RE[site]
        cand = sorted({u.split("#")[0].rstrip("/") for u in locs
                       if rx.search(urllib.parse.urlsplit(u).path)})
        known = {r[0].rstrip("/") for r in conn.execute(
            "SELECT url FROM agency_site_listings WHERE site=?", (site,))}
        new = [u for u in cand if u not in known]
        triaged = [u for u in new if slug_comune(u)]

        print(f"\n=== {site}")
        print(f"  {len(locs):6} urls in sitemap")
        print(f"  {len(cand):6} listing-shaped")
        print(f"  {len(known):6} already harvested")
        print(f"  {len(new):6} NEW  ({len(triaged)} name an in-scope comune "
              f"in the slug, {len(new) - len(triaged)} unknown)")

        if not args.ingest:
            continue
        if site not in DETAIL_PARSERS:
            print(f"  no detail parser for {site} yet — enumeration only")
            continue

        queue = new if args.all else triaged
        if args.limit:
            queue = queue[:args.limit]
        print(f"  reading {len(queue)} page(s) "
              f"~{len(queue) * config.REQUEST_DELAY_S / 60:.0f} min")
        if args.dry_run:
            for u in queue[:10]:
                print(f"     {u}")
            continue

        run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        n_in = n_out = n_bad = 0
        for i, u in enumerate(queue, 1):
            if fetcher.robots_status(u) == "disallowed":
                print(f"  [robots] {u}")
                continue
            try:
                html, _, _ = fetcher.get(u)
            except Exception:
                n_bad += 1
                continue
            if not html:
                n_bad += 1
                continue
            rec = DETAIL_PARSERS[site](html, u)
            comune = resolve_comune(rec["comune"] or "")
            in_scope = any(config.norm_comune(c) == comune
                           for c in config.COMUNI)
            if not in_scope:
                n_out += 1
                continue
            conn.execute(
                "INSERT OR REPLACE INTO agency_site_listings "
                "(site,url,ref,price,price_withheld,mq,comune,comune_raw,"
                " title,is_rent,harvested_on) VALUES (?,?,?,?,?,?,?,?,?,0,?)",
                (site, u, rec["ref"], rec["price"], rec["price_withheld"],
                 rec["mq"], comune, rec["comune"], rec["title"], run_at))
            n_in += 1
            if i % 10 == 0:
                conn.commit()
                print(f"    {i}/{len(queue)}  {n_in} in scope  "
                      f"{n_out} out  {n_bad} failed")
        conn.commit()
        print(f"  done: {n_in} stored, {n_out} out of scope, {n_bad} failed")

    if args.ingest and not args.dry_run:
        print("\nNext: python3 promote_agency_sites.py"
              "\n      python3 harvest_agency_details.py")


if __name__ == "__main__":
    main()
