"""Detail-page pass over the eight agency sites — the photos (S009).

WHY

S008 read agency INDEX CARDS only. That gave url, ref, price, mq, comune,
title — and no photographs. `promote_agency_sites.py` then moved those
rows into `listings`, where every matcher can finally see them, but they
arrived blind: `photo_ids` NULL on all of them.

That matters because of one measured fact in SOT §16d. The `price` and
`price+surface` routes use price AS the join key, so they can only ever
find properties whose prices already agree. **Only `ref` and `photo` can
surface a PRICE disagreement**, and `ref` is not a cross-agency key
(measured S009: joining ref across agencies produced 9 hits, all 9
different properties — SICASA 0711 at €95.000/100 m² against Centogambe
0711 at €70.000/40 m²). So photographs are the only route left, and this
script is what supplies them.

WHAT IT COSTS

One fetch per listing, at config.REQUEST_DELAY_S, cached on disk so a
reparse is free. ~890 listings across eight small-business sites. Every
URL is checked against robots.txt through fetcher.robots_status() before
it is requested; a 'disallowed' answer skips the URL and says so.

Resumable: listings that already have photo_ids are skipped before the
fetch, not after. Interrupt it with Ctrl-C and run it again.

WORDPRESS SIZE VARIANTS ARE COLLAPSED AT EXTRACTION

Five of the eight sites are WordPress and serve the same photograph as
`casa-01.jpg`, `casa-01-scaled.jpg` and `casa-01-740x554.jpg`. S004 hit
this inside photomatch, where a single photograph satisfied MIN_SHARED=2
by itself and manufactured a match. photomatch now dedupes hashes within
a listing, but that fix works on the hash AFTER eight thumbnails have
been downloaded — so without collapsing here, a listing's eight photo
slots can be eight renditions of one picture and the listing enters the
match space effectively blind. Canonicalising the filename costs nothing
and makes the eight slots eight actual photographs.

    python3 harvest_agency_details.py --probe          # 2 per site, writes nothing
    python3 harvest_agency_details.py --site romolini
    python3 harvest_agency_details.py                  # everything outstanding

Run it on the real database on Christopher's machine — the sandbox mount
cannot journal sqlite.
"""

import argparse
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, ".")

import config    # noqa: E402
import db        # noqa: E402
import fetcher   # noqa: E402

SITES = ("leonardi", "house", "cortesi", "lancisi", "romolini",
         "sicasa", "now", "immobilinvest")

# Where each site actually keeps listing photographs, measured by sampling
# one live detail page per site on 2026-08-31. ALLOW is matched against the
# absolute URL; DENY wins over ALLOW and strips site furniture — logos,
# agent headshots, QR codes, flags, theme sprites — which would otherwise
# be hashed and, being shared across every listing on the site, would match
# everything to everything.
PHOTO_RULES = {
    "leonardi":      dict(allow=(r"/wp-content/uploads/",), deny=()),
    "house":         dict(allow=(r"/wp-content/uploads/",), deny=()),
    "cortesi":       dict(allow=(r"/wp-content/uploads/",),
                          deny=(r"wpqr-codes",)),
    "lancisi":       dict(allow=(r"/wp-content/uploads/",), deny=()),
    "sicasa":        dict(allow=(r"/wp-content/uploads/",), deny=()),
    # Romolini serves galleries from the Apimo CDN. /user/ is the agent's
    # portrait — the same face on every one of their listings.
    "romolini":      dict(allow=(r"media\.apimo\.pro/",),
                          deny=(r"media\.apimo\.pro/user/",)),
    # NOW serves originals under /uploads/common/ and thumbnails under
    # /resized/. Take the originals; the resized copies are the same
    # photographs and would just consume the eight slots.
    "now":           dict(allow=(r"gest\.nowestate\.it/uploads/",),
                          deny=(r"/resized/",)),
    "immobilinvest": dict(allow=(r"/alterpages/",), deny=()),
}

# Theme, plugin and chrome paths that appear on more than one site, plus
# the specific furniture the S009 probe caught living in the same uploads
# directory as the real photographs:
#   house    cropped-LOGHI-SOCIAL-192x192.jpg  (their logo. 'logo' does not
#            match it — the Italian plural is LOGHI, and an English-only
#            stopword list is exactly how site furniture reaches the hasher)
#   cortesi  numero-verde-cortesi.jpg          (freephone banner, every page)
# photomatch also drops images recurring across >3 listings as furniture,
# but that check runs AFTER the thumbnails have been fetched and hashed.
GLOBAL_DENY = (
    r"/assets/img/", r"/wp-content/themes/", r"/wp-content/plugins/",
    r"log[oh]", r"placeholder", r"avatar", r"/flags?/", r"sprite",
    r"icon", r"favicon", r"\.svg$",
    r"numero-verde", r"banner", r"cropped-", r"whatsapp-?logo",
)

PHOTOS_PER_LISTING = 8      # matches photomatch.PHOTOS_PER_LISTING

IMG_RE = re.compile(
    r'(?:src|href|data-src|data-lazy-src|data-large_image)='
    r'["\']([^"\']+\.(?:jpe?g|png|webp))["\']', re.I)

# WordPress '-740x554', '-scaled', and NOW's '-1024x768' renditions.
VARIANT_RE = re.compile(r"-(?:\d{2,5}x\d{2,5}|scaled)(?=\.[a-z]{3,4}$)", re.I)


def canonical_key(url):
    """The photograph a URL is a rendition of. Strips the size suffix so
    'casa-01-740x554.jpg' and 'casa-01-scaled.jpg' collapse onto
    'casa-01.jpg' and occupy one slot between them, not two."""
    path = urllib.parse.urlsplit(url).path
    return VARIANT_RE.sub("", path).lower()


def segment_for(site, html, url):
    """The slice of the page that belongs to THIS listing.

    ImmobilInvest has no per-listing pages: every property sits inline on
    compravendite.html and url_alt points at the catalog with a '#rif-NNN'
    fragment. Reading the whole page gave refs 244 and 369 the SAME eight
    photographs in the S009 probe — which photomatch would have read as
    eighteen listings sharing eight images each, merged transitively into
    one enormous false cluster. Exactly the failure §16d records as
    'union-find needs an equivalence relation'.

    So the catalog is cut at its anchors and each ref keeps only its own
    block. If the anchor cannot be found, the listing gets NO photos —
    a listing with none is inert, a listing with someone else's is a
    fabricated match.
    """
    frag = urllib.parse.urlsplit(url).fragment
    if site != "immobilinvest" or not frag:
        return html

    # The '#rif-244' fragment is OURS — S008 synthesised it to give each
    # inline listing a distinct url_alt. The page has no such anchor (its
    # only ids are AlterVista's 'title-48688912'), so matching the fragment
    # as markup finds nothing. What the page does carry is the printed
    # reference, 'Rif. 244', in the same block as that listing's images.
    ref = frag.split("-")[-1]
    marks = [m.start() for m in
             re.finditer(r"[Rr]if[.:]?\s*n?[.°]?\s*\d{2,6}", html)]
    here = re.search(r"[Rr]if[.:]?\s*n?[.°]?\s*" + re.escape(ref) + r"\b", html)
    if not here:
        return ""
    after = [p for p in marks if p > here.start()]
    return html[here.start():after[0]] if after else html[here.start():]


def extract_photos(site, html, base_url):
    rules = PHOTO_RULES.get(site, dict(allow=(), deny=()))
    html = segment_for(site, html, base_url)
    seen = {}

    for raw in IMG_RE.findall(html):
        url = urllib.parse.urljoin(base_url, raw.strip())

        # A URL ending '.jpg' can still be a PAGE. Romolini's gallery links
        # read gallery_immobile.php?refid=1840&foto=https://media.apimo.pro/
        # ....jpg — the regex matches on the query string, the fetch returns
        # HTML, and PIL fails on it after the request has already been made.
        # No listing photograph on any of the eight sites carries a query.
        if urllib.parse.urlsplit(url).query:
            continue
        if any(re.search(p, url, re.I) for p in GLOBAL_DENY):
            continue
        if any(re.search(p, url, re.I) for p in rules["deny"]):
            continue
        if rules["allow"] and not any(re.search(p, url, re.I)
                                      for p in rules["allow"]):
            continue

        key = canonical_key(url)
        # Prefer the SHORTEST url for a photograph, which after the size
        # strip is the unsuffixed original. The longest is a rendition like
        # '-154x154', and WordPress crops those SQUARE from a 4:3 original.
        # dHash is resolution-independent but not aspect-independent, so
        # hashing a square crop from one site against a full frame from
        # another is a false NEGATIVE — the quiet kind, that looks like
        # honest absence of a match.
        if key not in seen or len(url) < len(seen[key]):
            seen[key] = url

    return list(seen.values())[:PHOTOS_PER_LISTING]


# Only ever used to FILL a NULL — never to overwrite a figure the index
# card already gave us. Cortesi and NOW cards carry no surface at all
# (18 of 74 and 1 of 48 priced+sized), which is why they are worth a look.
MQ_RE = (
    re.compile(r"superficie[^0-9]{0,40}?([\d.]{2,7})\s*(?:mq|m²|m2)", re.I),
    re.compile(r"\b([\d.]{2,7})\s*(?:mq|m²|m2)\s*(?:commerciali|calpestabili)",
               re.I),
)


def extract_mq(html):
    text = re.sub(r"<[^>]+>", " ", html)
    for rx in MQ_RE:
        m = rx.search(text)
        if m:
            try:
                v = int(m.group(1).replace(".", ""))
            except ValueError:
                continue
            # A four-digit-plus figure here is usually a land area or a
            # price fragment, not a habitable surface. Bounds, not guesses.
            if 15 <= v <= 3000:
                return v
    return None


def audit(conn):
    """Which photographs are shared between listings, per site. Reads the
    database; fetches nothing.

    A high count means PHOTO_RULES let site furniture through — a logo, a
    banner, an agent's portrait — and every listing carrying it will match
    every other one. photomatch drops images recurring across more than 3
    listings for exactly this reason, but that guard fires after the
    thumbnails have been downloaded and hashed, and it cannot tell a
    genuinely reused agency photograph from a rule that is simply wrong.
    Run this after a harvest and before trusting any cluster.
    """
    print(f"{'site':14} {'listings':>9} {'w/photos':>9} {'distinct':>9} "
          f"{'shared':>7}  most-shared image")
    for site in SITES:
        rows = conn.execute(
            "SELECT source_id, photo_ids FROM listings WHERE source=?",
            (site,)).fetchall()
        counts, withp = {}, 0
        for r in rows:
            try:
                ids = json.loads(r["photo_ids"] or "[]")
            except Exception:
                continue
            if ids:
                withp += 1
            for u in set(ids):
                counts[u] = counts.get(u, 0) + 1
        shared = {u: n for u, n in counts.items() if n > 1}
        worst = max(shared.items(), key=lambda kv: kv[1]) if shared else None
        print(f"{site:14} {len(rows):>9} {withp:>9} {len(counts):>9} "
              f"{len(shared):>7}  "
              + (f"x{worst[1]} {worst[0].split('/')[-1][:40]}"
                 if worst else "-"))
    print("\nA shared count in the high single digits or more is a "
          "PHOTO_RULES problem,\nnot a finding. Fix the rule and re-run "
          "with --refetch before clustering.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=SITES)
    ap.add_argument("--audit", action="store_true",
                    help="report photo sharing per site; reads only")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--probe", action="store_true",
                    help="sample 2 listings per site, print, write nothing")
    ap.add_argument("--refetch", action="store_true",
                    help="re-read listings that already have photos")
    args = ap.parse_args()

    conn = db.connect()
    conn.row_factory = __import__("sqlite3").Row

    if args.audit:
        audit(conn)
        return

    sites = [args.site] if args.site else list(SITES)
    q = ("SELECT source, source_id, url, mq FROM listings "
         f"WHERE source IN ({','.join('?' * len(sites))}) ")
    if not args.refetch:
        q += "AND (photo_ids IS NULL OR photo_ids IN ('', '[]')) "
    q += "ORDER BY source, source_id"
    rows = conn.execute(q, sites).fetchall()

    if args.probe:
        by_site, picked = {}, []
        for r in rows:
            by_site.setdefault(r["source"], []).append(r)
        for s in sites:
            picked += by_site.get(s, [])[:2]
        rows = picked
    elif args.limit:
        rows = rows[:args.limit]

    mins = len(rows) * config.REQUEST_DELAY_S / 60
    print(f"{len(rows)} listing(s) to read across {len(sites)} site(s)")
    print(f"~{mins:.0f} min at {config.REQUEST_DELAY_S}s between requests "
          f"(cached pages are free)\n")

    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n_ok = n_none = n_blocked = n_fail = n_mq = 0
    done = 0

    for r in rows:
        url = r["url"]
        status = fetcher.robots_status(url)
        if status == "disallowed":
            n_blocked += 1
            print(f"  [robots: disallowed] {url[:88]}")
            continue

        try:
            html, code, cached = fetcher.get(url)
        except Exception as e:
            n_fail += 1
            print(f"  [fetch {type(e).__name__}] {url[:80]}")
            continue
        if not html:
            n_fail += 1
            continue

        photos = extract_photos(r["source"], html, url)
        mq = None
        if r["mq"] is None:
            mq = extract_mq(html)

        if args.probe:
            print(f"  {r['source']:14} {r['source_id']:12} "
                  f"{len(photos)} photo(s)"
                  + (f"  mq->{mq}" if mq else "")
                  + ("  [cache]" if cached else ""))
            for p in photos[:3]:
                print(f"        {p[:100]}")
            continue

        if photos:
            conn.execute(
                "UPDATE listings SET photo_ids=?, photo_count=?, "
                "last_seen=? WHERE source=? AND source_id=?",
                (json.dumps(photos), len(photos), run_at,
                 r["source"], r["source_id"]))
            n_ok += 1
        else:
            n_none += 1

        if mq:
            conn.execute(
                "UPDATE listings SET mq=? WHERE source=? AND source_id=? "
                "AND mq IS NULL",
                (mq, r["source"], r["source_id"]))
            n_mq += 1

        done += 1
        # A long harvest WILL be interrupted. Losing an hour of polite
        # fetching to an uncommitted transaction is what makes people
        # decline to re-run it.
        if done % 10 == 0:
            conn.commit()
            print(f"  {done}/{len(rows)}  {n_ok} with photos  "
                  f"{n_none} without  {n_blocked} blocked  {n_fail} failed")
    conn.commit()

    if args.probe:
        print("\n--probe: nothing written")
        return

    print(f"\ndone: {n_ok} listing(s) got photos, {n_none} had none, "
          f"{n_blocked} robots-blocked, {n_fail} failed")
    if n_mq:
        print(f"      {n_mq} surface(s) recovered from detail pages")
    print("\nNext: python3 photomatch.py --harvest   (hashes the new "
          "thumbnails)\n      python3 photomatch.py --cluster\n"
          "      python3 contradictions.py --md")


if __name__ == "__main__":
    main()
