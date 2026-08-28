"""Match the same property across agencies by its photographs.

THE BLOCKING PROBLEM THIS SOLVES

The product (SOT S1) is calling out the variance when Leonardi, Now,
Cortesi and Marcellini list the SAME property at different prices and
different square footage. That requires knowing two listings are the same
property. Every obvious join key fails:

  coordinates   UNUSABLE. Agencies geocode to a fallback point. SICASA
                pins 28 different properties -- Gricignano, Via del
                Tevere, Via Petrarca, Piazza della Repubblica -- to one
                coordinate at Sansepolcro's centre. An exact-coordinate
                match finds agency habits, not properties.
  photo IDs     UNUSABLE. Zero overlap across listings; each agency's
                upload gets its own id.
  address       WEAK. 100% populated but street-level: only 5% carry a
                house number and 105 are blank.
  price         USELESS FOR OUR CASE. It works only when the prices
                agree, and a price disagreement is the thing we are
                looking for.

Photographs are the exception. Agencies re-upload the same photographer's
images, so the FILES differ (re-encoded, different ids) while the IMAGES
are identical. A perceptual hash sees through the re-encoding.

VALIDATED 2026-08-28 on a five-agency auction cluster (Via della
Ginestra area, identical price to the euro, surfaces 178/178/178/177/178):

    131979314 vs 131983778   hamming  0    definitive same image
    131979314 vs 131647030   hamming  5
    131983778 vs 131647030   hamming  5
    ...the other two          17-26        different photo sets

Three of five matched.

A SINGLE SHARED IMAGE IS NOT PROOF — corrected 2026-08-28 after the first
real run produced two false positives:

    House Immobiliare  EUR 520.000  420 m2 villa       Frazione Montedoglio
    House Immobiliare  EUR 195.000  250 m2 terratetto  Via Santa Croce

    House Immobiliare  EUR 170.000  120 m2 appartamento  Trebbio
    House Immobiliare  EUR 190.000  130 m2 appartamento  Trebbio
    House Immobiliare  EUR 135.000   90 m2 appartamento  Trebbio

The first pair are unrelated properties sharing a reused agency photo.
The second are three DIFFERENT UNITS in one building sharing an exterior
shot — a correct image match and a wrong property match. So a shared
image means one of:

    (a) the same property                      <- what we want
    (b) the same building, a different unit
    (c) a reused stock / exterior / aerial / logo photo

Two defences, both applied below:

  MIN_SHARED   require several matching images, not one. A reused
               exterior is usually a single frame; a genuinely
               duplicated listing shares most of its set.
  MAX_LISTINGS_PER_IMAGE
               ignore any image that turns up across many listings.
               That is by definition agency furniture — a logo, a
               townscape, a building facade — and it carries no
               identifying information. This is the stronger of the two.

Even with both, treat output as CANDIDATES to eyeball, never as
automatic publication. And the asymmetry still holds in the other
direction: a non-match is not evidence of difference (an earlier auction
triple with identical prices shared no photos at all — best hamming 22
against a control of 22).

A CAUTION FROM THE SAME TEST: an earlier attempt on a DIFFERENT auction
triple (identical price, surfaces 133/90/97) found nothing -- best 22,
against a control of 22, i.e. no signal at all. Those agencies used
genuinely different photographs. So:

    a match is strong evidence of sameness
    a non-match is NOT evidence of difference

Never present "no match" as "different properties". Photo matching finds
a subset, and that subset is enough -- one proven cluster with a 48%
surface disagreement is a story; exhaustiveness is not required.

Sampling depth matters: photo sets do not align in order, so comparing
only the first few images misses real matches. PHOTOS_PER_LISTING is the
knob that trades requests against recall.

POLITENESS: thumbnails come from pic.im-cdn.it, not the listing site.
`small.jpg` returns 403; `thumb.jpg` (100x75, ~2.7 KB) is served. At the
default depth this is a few thousand small requests -- run it once, store
the hashes, and only hash listings that are new on later runs.

Usage:
    python3 photomatch.py --harvest        # fetch + hash (slow, once)
    python3 photomatch.py --harvest --limit 50
    python3 photomatch.py --cluster        # find matches from stored hashes
    python3 photomatch.py --report         # the variance table -- the product
"""

import argparse
import io
import json
import sys
import time
import urllib.parse
import urllib.request

import config
import db

THUMB = "https://pic.im-cdn.it/image/{pid}/thumb.jpg"
PHOTOS_PER_LISTING = 8
DELAY_S = 0.4      # a CDN thumbnail, not a page render; 2.7 KB each

# Hash the densest market first. Sansepolcro has 365 of the 844 listings
# and the most agencies competing over the same stock, so cross-agency
# duplicates surface there long before a full harvest finishes.
PRIORITY_COMUNI = ("sansepolcro", "anghiari")
# 64-bit dHash. <=10 is the conventional "same image" threshold; 0-5 is
# what the validated cluster produced.
MATCH_THRESHOLD = 10

# How many matching images two listings must share before we call them a
# candidate pair. 1 produced false positives on reused exteriors.
MIN_SHARED = 2

# An image appearing in more than this many listings is agency furniture
# — a logo, a townscape, a building facade shared by every unit inside
# it — and is excluded as a join key entirely.
MAX_LISTINGS_PER_IMAGE = 3


def dhash(img, size=8):
    """64-bit difference hash. Survives re-encoding and rescaling."""
    from PIL import Image
    g = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for r in range(size):
        for c in range(size):
            bits = (bits << 1) | (px[r * (size + 1) + c] < px[r * (size + 1) + c + 1])
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def ensure_table(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS photo_hashes (
            source    TEXT NOT NULL,
            source_id TEXT NOT NULL,
            photo_id  TEXT NOT NULL,
            -- HEX TEXT, not INTEGER. A 64-bit dHash with the top bit set
            -- exceeds SQLite's SIGNED 64-bit INTEGER and raises
            -- OverflowError — which silently discarded half of every
            -- harvest until it was caught.
            dhash     TEXT,
            PRIMARY KEY (source, source_id, photo_id)
        );
        CREATE INDEX IF NOT EXISTS idx_ph_listing
            ON photo_hashes(source, source_id);
    """)
    conn.commit()


def harvest(conn, limit=None):
    from PIL import Image
    ensure_table(conn)
    ua = {"User-Agent": config.USER_AGENT}

    rows = conn.execute(
        "SELECT source, source_id, photo_ids, comune FROM listings "
        "WHERE photo_ids IS NOT NULL AND photo_ids != '[]' "
        "ORDER BY CASE comune " +
        " ".join(f"WHEN '{c}' THEN {i}" for i, c in enumerate(PRIORITY_COMUNI)) +
        f" ELSE {len(PRIORITY_COMUNI)} END, comune").fetchall()
    done = {(r["source"], r["source_id"]) for r in
            conn.execute("SELECT DISTINCT source, source_id FROM photo_hashes")}
    todo = [r for r in rows if (r["source"], r["source_id"]) not in done]
    if limit:
        todo = todo[:limit]

    print(f"{len(rows)} listings with photos, {len(done)} already hashed, "
          f"{len(todo)} to do")
    print(f"~{len(todo) * PHOTOS_PER_LISTING} thumbnails at {DELAY_S}s "
          f"= ~{len(todo) * PHOTOS_PER_LISTING * DELAY_S / 60:.0f} min")

    n_ok = n_err = 0
    errs = {}
    for i, r in enumerate(todo, 1):
        try:
            ids = json.loads(r["photo_ids"] or "[]")[:PHOTOS_PER_LISTING]
        except Exception:
            continue
        for pid in ids:
            try:
                # Sources store photos differently and BOTH must be
                # hashed into the same space, or agency-site listings can
                # never match portal listings — which is the whole point
                # (SOT S16b): the same property sits on Centogambe's site,
                # on Leonardi's, and on Immobiliare under a third name.
                #   immobiliare  numeric id -> CDN thumbnail URL
                #   agency sites full URL, already absolute
                url = str(pid) if str(pid).startswith("http") \
                    else THUMB.format(pid=pid)
                # Agency filenames are human-typed and contain spaces and
                # accents — 'foto/10091/facciata-terrazzo superiore.JPG'.
                # urllib raises InvalidURL on those rather than encoding
                # them, which failed 660 of 851 Marcellini thumbnails.
                # Encode the path only; leave scheme/host/query alone.
                parts = urllib.parse.urlsplit(url)
                url = urllib.parse.urlunsplit((
                    parts.scheme, parts.netloc,
                    urllib.parse.quote(parts.path, safe="/%"),
                    parts.query, parts.fragment))
                req = urllib.request.Request(url, headers=ua)
                data = urllib.request.urlopen(req, timeout=20).read()
                h = dhash(Image.open(io.BytesIO(data)))
                conn.execute(
                    "INSERT OR REPLACE INTO photo_hashes "
                    "(source, source_id, photo_id, dhash) VALUES (?,?,?,?)",
                    (r["source"], r["source_id"], str(pid), format(h, "016x")))
                n_ok += 1
            except Exception as e:
                n_err += 1
                errs[type(e).__name__ + str(getattr(e, "code", ""))] = \
                    errs.get(type(e).__name__ + str(getattr(e, "code", "")), 0) + 1
            time.sleep(DELAY_S)
        # Commit often. A long harvest WILL be interrupted, and losing an
        # hour of thumbnails to an uncommitted transaction is the kind of
        # avoidable waste that makes people not re-run it.
        if i % 5 == 0:
            conn.commit()
        if i % 25 == 0:
            print(f"  {i}/{len(todo)} listings  {n_ok} hashed  {n_err} failed"
                  + (f"  {errs}" if errs else ""))
    conn.commit()
    print(f"done: {n_ok} thumbnails hashed, {n_err} failed  {errs}")


def clusters(conn):
    """Union-find over listings whose photo sets contain a matching image."""
    rows = conn.execute("SELECT source_id, dhash FROM photo_hashes").fetchall()
    by_listing = {}
    for r in rows:
        by_listing.setdefault(r["source_id"], []).append(int(r["dhash"], 16))

    ids = list(by_listing)
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Drop agency furniture first: any image that shows up across more
    # than MAX_LISTINGS_PER_IMAGE listings identifies a brand or a
    # building, not a property. Without this, one shared facade merges
    # every flat in the block into a single bogus "same property".
    spread = {}
    for lid, hs in by_listing.items():
        for h in hs:
            key = next((k for k in spread
                        if hamming(k, h) <= MATCH_THRESHOLD), h)
            spread.setdefault(key, set()).add(lid)
    common = {k for k, v in spread.items() if len(v) > MAX_LISTINGS_PER_IMAGE}
    if common:
        print(f"  ignoring {len(common)} image(s) that recur across "
              f">{MAX_LISTINGS_PER_IMAGE} listings (logos, facades, views)")
    filtered = {lid: [h for h in hs
                      if not any(hamming(h, c) <= MATCH_THRESHOLD
                                 for c in common)]
                for lid, hs in by_listing.items()}

    # O(n^2) over listings, but n is ~800 and the inner test short-circuits.
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if find(a) == find(b):
                continue
            shared = 0
            for ha in filtered[a]:
                if any(hamming(ha, hb) <= MATCH_THRESHOLD
                       for hb in filtered[b]):
                    shared += 1
                    if shared >= MIN_SHARED:
                        union(a, b)
                        break

    out = {}
    for i in ids:
        out.setdefault(find(i), []).append(i)
    return {k: v for k, v in out.items() if len(v) > 1}


def report(conn):
    cl = clusters(conn)
    if not cl:
        print("No photo clusters. Run --harvest first.")
        return

    print("=" * 74)
    print("SAME PROPERTY, DIFFERENT NUMBERS")
    print("=" * 74)
    print("\n  CANDIDATES, not conclusions. Matched on sharing "
          f"{MIN_SHARED}+ photographs")
    print("  after excluding images that recur across listings (logos,")
    print("  facades). Eyeball each before publishing: a shared image can")
    print("  still mean the same BUILDING rather than the same property.")
    print("  A non-match proves nothing — some agencies shoot their own.\n")

    n_multi_agency = n_price_var = n_surface_var = 0
    for root, members in sorted(cl.items(), key=lambda kv: -len(kv[1])):
        q = ",".join("?" * len(members))
        rows = conn.execute(
            f"SELECT source, source_id, agency_name, agency_ref, price, mq, "
            f"typology, address_raw, comune, url FROM listings "
            f"WHERE source_id IN ({q}) ORDER BY price DESC", members).fetchall()
        agencies = {r["agency_name"] for r in rows}
        sources = {r["source"] for r in rows}
        prices = {r["price"] for r in rows if r["price"]}
        mqs = {r["mq"] for r in rows if r["mq"]}
        if len(agencies) < 2:
            continue
        n_multi_agency += 1
        if len(prices) > 1:
            n_price_var += 1
        if len(mqs) > 1:
            n_surface_var += 1

        head = rows[0]
        tag = "  [CROSS-SOURCE]" if len(sources) > 1 else ""
        print(f"\n  {head['comune']} — {head['address_raw'] or 'no address'}{tag}")
        for r in rows:
            ref = f" rif.{r['agency_ref']}" if r["agency_ref"] else ""
            print(f"    {str(r['agency_name'] or r['source'])[:26]:28}"
                  f"{ref:12} EUR {str(r['price'] or 'withheld'):>9}  "
                  f"{str(r['mq'] or '?'):>5} m²  {str(r['typology'] or '')[:11]:12}"
                  f"  [{r['source'][:11]}]")
        if len(prices) > 1:
            lo, hi = min(prices), max(prices)
            print(f"    -> PRICE VARIES  EUR {lo:,} to {hi:,}  "
                  f"({(hi-lo)/lo*100:+.0f}%)")
        if len(mqs) > 1:
            lo, hi = min(mqs), max(mqs)
            print(f"    -> SURFACE VARIES  {lo} to {hi} m²  "
                  f"({(hi-lo)/lo*100:+.0f}%)")

    print(f"\n  photo clusters: {len(cl)}   multi-agency: {n_multi_agency}")
    print(f"  with a price disagreement:   {n_price_var}")
    print(f"  with a surface disagreement: {n_surface_var}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harvest", action="store_true")
    ap.add_argument("--cluster", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    conn = db.connect()
    ensure_table(conn)
    if a.harvest:
        harvest(conn, a.limit)
    if a.cluster:
        cl = clusters(conn)
        print(f"{len(cl)} clusters of 2+ listings sharing an image")
    if a.report or not (a.harvest or a.cluster):
        report(conn)


if __name__ == "__main__":
    main()
