"""Borgo Vero static site generator.

Reads the clustered listing database, writes a complete static site.
No server, no build step, no framework. At Valtiberina scale the whole
index fits in a JSON blob the browser can search, so the paste-a-URL
lookup runs client-side and hosting stays at zero.

    python generate.py --db ../phase0/phase0.sqlite --out dist
"""

import argparse
import json
import os
import shutil
import sqlite3
import statistics as st
from collections import defaultdict

import templates as T

LANGS = ["it", "en"]


# --- Loading -----------------------------------------------------------


def load(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM listings")]
    bands = [dict(r) for r in conn.execute("SELECT * FROM omi_bands")]
    conn.close()
    return rows, bands


ADDR_NOISE = ("via", "viale", "piazza", "strada", "vicolo", "largo",
              "corso", "localita", "loc", "frazione", "fraz", "nn",
              "comunale", "provinciale", "statale")


def norm_address(a):
    """Street name reduced to its distinguishing words.

    Portals write the same street differently: case varies, Idealista
    appends 'Nn' when there is no house number, and civici appear on one
    portal but not the other. Strip the furniture and compare what is left.
    """
    if not a:
        return ""
    s = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in a.lower())
    words = [w for w in s.split() if w not in ADDR_NOISE and not w.isdigit()]
    return " ".join(words)


MATCH_THRESHOLD = 3


def match_score(a, b):
    """How much evidence that two listings are the same property.

    Scoring rather than keying, because no single field is safe:

      - `vani` and `typology` are the fields portals most often disagree
        about, so requiring them misses the matches worth publishing
      - surface alone merges different flats on the same street
      - price alone would miss the price divergence that is the point

    Identical price is the strongest single signal — an agency enters one
    figure and it propagates — but it is evidence, not a requirement, so a
    genuine price disagreement can still clear the bar on surface alone.
    """
    s = 0
    pa, pb = a.get("price"), b.get("price")
    if pa and pb:
        d = abs(pa - pb) / max(pa, pb)
        s += 3 if d < 0.005 else (1 if d < 0.05 else 0)

    ma, mb = a.get("mq"), b.get("mq")
    if ma and mb:
        d = abs(ma - mb) / max(ma, mb)
        s += 2 if d <= 0.03 else (1 if d <= 0.15 else -1)

    if a.get("vani") and b.get("vani") and a["vani"] == b["vani"]:
        s += 1
    if a.get("typology") and a["typology"] == b.get("typology"):
        s += 1
    if a.get("floor") and a["floor"] == b.get("floor"):
        s += 1
    return s


def cluster(rows):
    """Group source listings into properties.

    TOLERANCES MATTER MORE THAN THEY LOOK. An earlier version keyed on
    exact `vani` and surface rounded to 10 m2 — and on real cross-portal
    data it clustered 1 of 4 known matches.

    The reason is the whole point of the project: the portals disagree
    about rooms and surface. So keying on those fields misses exactly the
    properties where agencies contradict each other, which are the ones
    worth publishing. A strict matcher silently deletes the story.

    Address plus surface within 15%, rooms ignored. Photo embeddings
    (spec section 4, layer 2) slot in here later as the real decider.
    """
    groups = []
    for r in rows:
        addr = norm_address(r.get("address_raw"))
        placed = False
        for g in groups:
            if g["comune"] != r.get("comune") or g["addr"] != addr:
                continue
            if match_score(g["rows"][0], r) >= MATCH_THRESHOLD:
                g["rows"].append(r)
                placed = True
                break
        if not placed:
            groups.append({"comune": r.get("comune"), "addr": addr,
                           "rows": [r]})
    buckets = {i: g["rows"] for i, g in enumerate(groups)}

    clusters = []
    for i, (_, group) in enumerate(sorted(buckets.items(), key=lambda x: str(x[0]))):
        # Canonical record = the source with the most complete data.
        canon = max(group, key=lambda r: sum(
            1 for k in ("price", "mq", "mq_commercial", "vani", "condition")
            if r.get(k)))
        c = dict(canon)
        c["cluster_id"] = f"vt{i:05d}"
        c["sources"] = group
        clusters.append(c)
    return clusters


SIZE_BUCKETS = [(0, 80), (80, 130), (130, 200), (200, 10000)]


def size_bucket(mq):
    """Must stay identical to sizeBucket() in the homepage JS."""
    for lo, hi in SIZE_BUCKETS:
        if lo <= mq < hi:
            return f"{lo}-{hi}"
    return "200-10000"


def band_for(bands, comune, zona):
    rel = [b for b in bands if (b["comune"] or "").lower() == (comune or "").lower()]
    if not rel:
        return None, None, None
    if zona == "centro_storico":
        z = [b for b in rel if "centro" in (b["zona_descr"] or "").lower()]
        rel = z or rel
    return (min(b["min_eur_m2"] for b in rel),
            max(b["max_eur_m2"] for b in rel),
            rel[0].get("semester"))


def enrich(clusters, bands):
    for c in clusters:
        lo, hi, sem = band_for(bands, c["comune"], c["zona_guess"])
        c["band_lo"], c["band_hi"], c["omi_semester"] = lo, hi, sem
        price, net, com = c.get("price"), c.get("mq"), c.get("mq_commercial")
        c["pct_net"] = c["pct_com"] = None
        if price and hi:
            if net:
                c["pct_net"] = (price / net - hi) / hi * 100
            if com:
                c["pct_com"] = (price / com - hi) / hi * 100
    return clusters


def comps_for(c, all_clusters, n=5):
    same = [o for o in all_clusters
            if o["cluster_id"] != c["cluster_id"]
            and o["comune"] == c["comune"]
            and o["typology"] == c["typology"]
            and o.get("mq") and c.get("mq")
            and abs(o["mq"] - c["mq"]) / c["mq"] <= 0.25]
    same.sort(key=lambda o: abs((o.get("mq") or 0) - (c.get("mq") or 0)))
    return same[:n]


# --- Writing -----------------------------------------------------------


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build(db_path, out):
    rows, bands = load(db_path)
    if not rows:
        raise SystemExit("No listings in the database. Run the ingest first.")

    clusters = enrich(cluster(rows), bands)
    print(f"{len(rows)} source listings -> {len(clusters)} properties")

    multi = [c for c in clusters if len(c["sources"]) > 1]
    print(f"{len(multi)} appear on more than one source")

    if os.path.isdir(out):
        shutil.rmtree(out)

    # Client-side lookup index: ids and urls per property.
    index = [{
        "cid": c["cluster_id"],
        "ids": [str(s.get("source_id")) for s in c["sources"]],
        "urls": [s.get("url") for s in c["sources"] if s.get("url")],
    } for c in clusters]
    index_json = json.dumps(index, separators=(",", ":"))
    print(f"lookup index: {len(index_json)/1024:.0f} KB")

    by_comune = defaultdict(list)
    for c in clusters:
        by_comune[c["comune"]].append(c)

    stats = {}
    for comune, cs in by_comune.items():
        prices = [c["price"] for c in cs if c.get("price")]
        m2 = [c["price"] / c["mq"] for c in cs if c.get("price") and c.get("mq")]
        doms = [c["dom_est"] for c in cs if c.get("dom_est")]
        lo, hi, _ = band_for(bands, comune, "centro_storico")
        stats[comune] = {
            "n": len(cs),
            "median_price": st.median(prices) if prices else None,
            "median_m2": st.median(m2) if m2 else None,
            "median_dom": int(st.median(doms)) if doms else "—",
            "band_lo": lo, "band_hi": hi,
        }

    # --- Data for the client-side calculator -------------------------
    # Small enough to inline: a handful of bands per comune plus one
    # median per comune x typology. Lets the homepage price a property
    # the index has never seen, with no backend.
    bands_js = {}
    for comune in by_comune:
        for zona in ("centro_storico", "periferia", "campagna"):
            lo, hi, _ = band_for(bands, comune, zona)
            if lo and hi:
                bands_js.setdefault(comune, {})[zona] = [round(lo), round(hi)]

    # Ship the raw [surface, EUR/m2] pairs rather than a precomputed median,
    # so the browser can apply the SAME +/-25% surface filter a listing page
    # uses. Bucketing was close but not close enough — it left divergences
    # up to 62% between the calculator and the property's own page, and a
    # "Borgo Vero price" that changes depending which page you read it on
    # is not a number anyone can quote.
    #
    # Cost of exactness: two integers per property. At 602 properties that
    # is a few KB, which is nothing.
    comps_js = defaultdict(list)
    for c in clusters:
        if c.get("price") and c.get("mq"):
            comps_js[f'{c["comune"]}|{c["typology"]}'].append(
                [c["mq"], round(c["price"] / c["mq"])])
    comps_js = dict(comps_js)

    typologies = [
        ("terratetto", "Terratetto"), ("appartamento", "Appartamento"),
        ("cielo_terra", "Casa indipendente"), ("villa", "Villa"),
        ("rustico", "Rustico / Casale"),
    ]

    bands_json = json.dumps(bands_js, separators=(",", ":"))
    comps_json = json.dumps(comps_js, separators=(",", ":"))
    print(f"calculator data: {(len(bands_json)+len(comps_json))/1024:.1f} KB")

    n_pages = 0
    for lang in LANGS:
        write(f"{out}/{lang}/index.html",
              T.index_page(stats, index_json, lang, bands_json, comps_json,
                           sorted(by_comune), typologies))
        write(f"{out}/{lang}/chi-siamo.html", T.about_page(lang))
        n_pages += 1
        write(f"{out}/{lang}/metodologia.html", T.methodology_page(lang))
        n_pages += 2

        for comune, cs in by_comune.items():
            cs.sort(key=lambda c: -(c.get("dom_est") or 0))
            write(f"{out}/{lang}/{comune}.html",
                  T.comune_page(comune, cs, stats[comune], lang))
            n_pages += 1

        for c in clusters:
            c["canonical"] = f"/{lang}/immobile/{c['cluster_id']}.html"
            write(f"{out}/{lang}/immobile/{c['cluster_id']}.html",
                  T.listing_page(c, c["sources"], comps_for(c, clusters), lang))
            n_pages += 1

    write(f"{out}/index.html",
          '<!doctype html><meta charset="utf-8">'
          '<meta http-equiv="refresh" content="0;url=/it/">'
          '<link rel="canonical" href="/it/">')

    urls = []
    for lang in LANGS:
        urls += [f"/{lang}/", f"/{lang}/metodologia.html"]
        urls += [f"/{lang}/{c}.html" for c in by_comune]
        urls += [f"/{lang}/immobile/{c['cluster_id']}.html" for c in clusters]
    write(f"{out}/sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
          + "</urlset>\n")
    write(f"{out}/robots.txt", "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n")

    print(f"{n_pages} pages -> {out}/")
    return clusters, multi


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="../phase0/phase0.sqlite")
    ap.add_argument("--out", default="dist")
    a = ap.parse_args()
    build(a.db, a.out)
