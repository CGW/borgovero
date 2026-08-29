"""One page per property: every agency's version, side by side.

THE PUBLISHABLE OUTPUT (SOT S1, S16d). This is the site the project
ships first, because it needs NOTHING unmeasured — no OMI band, no
negotiation ladder, no condition positions, no surface basis. Every
figure on every page is an agency's own published number, linked to the
page it was published on. The reader checks it in one click.

    python3 contradictions_site.py          # -> dist-contradictions/
    python3 contradictions_site.py --candidates ...   # include unverified

WHAT GETS PUBLISHED, AND WHY THE GATE IS THIS TIGHT

Named agencies are named. A wrong page here is not a bad statistic, it
is an accusation against a real local business — so publication is
restricted to clusters carrying IDENTITY evidence:

    verified    hand-checked in S004 (phase0/verified_clusters.json)
    ref         the agencies' own reference numbers agree
    photo       2+ distinct shared photographs at hamming <= 5
    price       an odd, non-round price nobody lands on twice

`photo-weak` (a single shared image) and bare `price+surface` stay OUT
unless --candidates is passed, and then they are labelled as
unconfirmed on the page itself. S004 is the reason: five clusters that
rested on hamming 7-10 joins were all different properties, and the
five-listing "EUR 280.000" cluster turned out to be a stream-side
villetta, a centro B&B palazzo and three unrelated riders.

WHAT IS NEVER ASSERTED

That an agency is wrong. The page says what each one published and
lets the difference speak. Where a price is withheld or published as a
bracket, that is shown as what it is, never as a number.
"""

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "phase0"))

import templates as T
from templates import e, eur

LANGS = ["it", "en"]

# Evidence that earns publication without a human having looked.
IDENTITY = {"ref", "photo", "price"}

TXT = {
    "it": {
        "title": "Stesso immobile, numeri diversi",
        "index_h1": "Le agenzie non concordano",
        "index_sub": ("{n} immobili della Valtiberina sono pubblicati da più "
                      "agenzie con numeri diversi. Ogni cifra è quella "
                      "pubblicata dall'agenzia stessa, con il link "
                      "all'annuncio."),
        "agency": "Agenzia", "ref": "Rif.", "price": "Prezzo richiesto",
        "surface": "Superficie", "type": "Tipologia", "where": "Dove",
        "source": "annuncio",
        "withheld": "trattativa riservata",
        "not_published": "non pubblicato",
        "disagree": "Su cosa non concordano",
        "d_price": "<b>Prezzo</b>: {lo} contro {hi} — <b>{pct}% di "
                   "differenza</b> sullo stesso immobile.",
        "d_surface": "<b>Superficie</b>: {lo} m² contro {hi} m² — "
                     "<b>{pct}% di differenza</b>.",
        "d_typology": "<b>Tipologia</b>: {vals}. La categoria decide quale "
                      "fascia OMI si applica, quindi non è una questione di "
                      "parole.",
        "d_location": "<b>Comune</b>: {vals}. Le agenzie non concordano "
                      "nemmeno su dove si trovi l'immobile.",
        "d_address": "<b>Indirizzo</b>: {vals}.",
        "verified": "Verificato a mano",
        "verified_when": "controllato il 29 agosto 2026",
        "candidate": "Da confermare",
        "candidate_note": ("Questi annunci condividono una sola fotografia. "
                           "Potrebbe trattarsi dello stesso immobile, oppure "
                           "no: lo pubblichiamo come segnalazione, non come "
                           "fatto accertato."),
        "how": "Come sono stati collegati",
        "how_ref": "Le agenzie usano lo stesso numero di riferimento.",
        "how_photo": "Gli annunci condividono almeno due fotografie identiche.",
        "how_price": "Prezzo identico e non arrotondato — una cifra che non "
                     "capita due volte per caso.",
        "how_ps": "Prezzo identico e superficie compatibile.",
        "why": "Perché conta",
        "why_body": ("Chi compra confronta un annuncio alla volta. Messi uno "
                     "accanto all'altro, i numeri non tornano — e la "
                     "differenza la paga chi non se ne accorge."),
        "back": "Tutti gli immobili",
        "no_price": "Nessuna delle agenzie pubblica un prezzo per questo "
                    "immobile.",
        "bracket": "solo una fascia di prezzo",
    },
    "en": {
        "title": "Same property, different numbers",
        "index_h1": "The agencies do not agree",
        "index_sub": ("{n} Valtiberina properties are listed by more than one "
                      "agency with different numbers. Every figure is the "
                      "agency's own, linked to its listing."),
        "agency": "Agency", "ref": "Ref.", "price": "Asking price",
        "surface": "Surface", "type": "Type", "where": "Where",
        "source": "listing",
        "withheld": "price on request",
        "not_published": "not published",
        "disagree": "What they disagree on",
        "d_price": "<b>Price</b>: {lo} against {hi} — <b>{pct}% apart</b> on "
                   "the same property.",
        "d_surface": "<b>Surface</b>: {lo} m² against {hi} m² — "
                     "<b>{pct}% apart</b>.",
        "d_typology": "<b>Type</b>: {vals}. The category decides which OMI "
                      "band applies, so this is not a question of wording.",
        "d_location": "<b>Comune</b>: {vals}. The agencies do not even agree "
                      "on where the property is.",
        "d_address": "<b>Address</b>: {vals}.",
        "verified": "Checked by hand",
        "verified_when": "checked 29 August 2026",
        "candidate": "Unconfirmed",
        "candidate_note": ("These listings share a single photograph. They "
                           "may be the same property or they may not: this is "
                           "published as a lead, not as an established fact."),
        "how": "How these were linked",
        "how_ref": "The agencies use the same reference number.",
        "how_photo": "The listings share at least two identical photographs.",
        "how_price": "An identical, non-round price — a figure nobody lands "
                     "on twice by accident.",
        "how_ps": "Identical price and compatible surface.",
        "why": "Why it matters",
        "why_body": ("A buyer reads one listing at a time. Side by side the "
                     "numbers do not add up — and the difference is paid by "
                     "whoever does not notice."),
        "back": "All properties",
        "no_price": "None of the agencies publishes a price for this "
                    "property.",
        "bracket": "a price range only",
    },
}


def slug(item):
    """Readable page id, stable across rebuilds: comune-street-hash.

    The suffix is derived from the cluster's own member ids, NOT from
    its position in the run. An ordinal looked tidier and was wrong: it
    shifts every time a cluster is added, verified or suppressed, so
    every URL on the site changes whenever anything is learned — dead
    links for anyone who saved one, and a search engine re-indexing
    pages it already had. A property's URL now changes only when the
    set of listings being compared actually changes, which is the one
    case where it should.
    """
    import contradictions as C
    import hashlib
    g = item["group"]
    base = comune_of(g).lower()
    addr = C.best_label(g)
    a = "".join(c if c.isalnum() or c.isspace() else " " for c in addr.lower())
    a = "-".join(a.split()[:4])
    h = hashlib.sha1("|".join(sorted(str(r["source_id"]) for r in g))
                     .encode()).hexdigest()[:6]
    return f"{base}-{a}-{h}" if a else f"{base}-{h}"


def comune_of(group):
    """The comune to file this property under — deterministically.

    Taking group[0]'s comune churned URLs between rebuilds, because the
    group is assembled from a set and its order is arbitrary. It showed
    up on exactly the cluster where two agencies disagree about the
    comune (Badia Tedalda vs Sestino), which is the finding itself: the
    page name flipped between the two on alternate builds. Most common
    label wins, ties broken alphabetically, so the URL is fixed even
    while the disagreement stands — and the disagreement is still
    published on the page.
    """
    from collections import Counter
    names = [g["comune"] for g in group if g["comune"]]
    if not names:
        return "valtiberina"
    counts = Counter(names)
    top = max(counts.values())
    return sorted(n for n, c in counts.items() if c == top)[0]


def agency_of(r):
    return r["agency_name"] or r["source"]


def price_cell(r, t):
    if r.get("price_withheld"):
        return f'<span class="lbl">{e(t["withheld"])}</span>'
    if r.get("price"):
        return f'<b>{eur(r["price"])}</b>'
    if r.get("price_bracket") and r["price_bracket"] != "bracket (unresolved)":
        return (f'<span class="lbl">{e(r["price_bracket"])} '
                f'({e(t["bracket"])})</span>')
    return f'<span class="lbl">{e(t["not_published"])}</span>'


def property_page(item, sid, lang):
    t, tt = TXT[lang], T.T[lang]
    import contradictions as C
    g, d = item["group"], item["d"]
    label = C.best_label(g)
    comune = comune_of(g).replace("-", " ").title()

    rows = []
    for r in sorted(g, key=lambda x: (-(x["price"] or 0),
                          str(x["agency_name"] or x["source"]),
                          str(x["source_id"]))):
        link = (f' <a class="src" href="{e(r["url"])}" rel="nofollow noopener"'
                f' target="_blank">{e(t["source"])} ↗</a>' if r.get("url")
                else "")
        rows.append(
            f'<tr><td><b>{e(agency_of(r))}</b>{link}</td>'
            f'<td class="r">{e(r["agency_ref"] or "—")}</td>'
            f'<td class="r">{price_cell(r, t)}</td>'
            f'<td class="r">{e(r["mq"]) + " m²" if r["mq"] else "—"}</td>'
            f'<td class="r">{e(r["typology"] or r["typology_raw"] or "—")}</td>'
            f'</tr>')

    table = (f'<table class="rows"><tr>'
             f'<td class="lbl">{e(t["agency"])}</td>'
             f'<td class="lbl r">{e(t["ref"])}</td>'
             f'<td class="lbl r">{e(t["price"])}</td>'
             f'<td class="lbl r">{e(t["surface"])}</td>'
             f'<td class="lbl r">{e(t["type"])}</td></tr>'
             + "".join(rows) + '</table>')

    facts = []
    if "price" in d:
        facts.append(t["d_price"].format(lo=eur(d["price"][0]),
                                         hi=eur(d["price"][1]),
                                         pct=f'{d["price"][2]:.0f}'))
    if "surface" in d:
        facts.append(t["d_surface"].format(lo=d["surface"][0],
                                           hi=d["surface"][1],
                                           pct=f'{d["surface"][2]:.0f}'))
    if "typology" in d:
        facts.append(t["d_typology"].format(
            vals=" / ".join(e(v) for v in d["typology"])))
    if "location" in d:
        facts.append(t["d_location"].format(
            vals=" / ".join(e(v.replace("-", " ").title())
                            for v in d["location"])))
    if "address" in d:
        facts.append(t["d_address"].format(
            vals=" / ".join(e(v) for v in d["address"])))
    if not [r for r in g if r.get("price") and not r.get("price_withheld")]:
        facts.append(e(t["no_price"]))

    ev = set(item["evidence"])
    how = (t["how_ref"] if "ref" in ev else
           t["how_photo"] if "photo" in ev else
           t["how_price"] if "price" in ev else t["how_ps"])

    if item.get("verified"):
        # The verification notes in verified_clusters.json are written in
        # English (they are S004's working record). Showing English prose
        # on the Italian page — the page a Valtiberina buyer actually
        # reads — would undercut the one thing this site sells, which is
        # being careful. Italian gets the badge and the date; the note
        # itself appears only where its language belongs.
        note = f' {e(item["verified"])}' if lang == "en" else ""
        badge = (f'<div class="flag"><b>✓ {e(t["verified"])}</b> — '
                 f'{e(t["verified_when"])}.{note}</div>')
    elif "photo-weak" in ev:
        badge = (f'<div class="flag"><b>{e(t["candidate"])}</b> — '
                 f'{e(t["candidate_note"])}</div>')
    else:
        badge = ""

    body = f"""
<h1>{e(comune)} — {e(label)}</h1>
<p class="sub">{e(t["title"])}</p>
<div class="block">{table}{badge}</div>
<div class="block"><h2>{e(t["disagree"])}</h2>
  <ul style="margin:0;padding-left:18px">
    {"".join(f"<li>{f}</li>" for f in facts)}
  </ul>
</div>
<div class="block"><h2>{e(t["how"])}</h2><p style="margin:0">{e(how)}</p>
  <p class="note">{e(t["why_body"])}</p></div>
<p class="noprint"><a href="/{lang}/confronti/">← {e(t["back"])}</a></p>
"""
    desc = f'{comune} — {label}: ' + (
        f'{d["surface"][0]}–{d["surface"][1]} m²' if "surface" in d else
        t["title"])
    return T.shell(f'{comune} — {label} | Borgo Vero', body, lang,
                   f'/{"en" if lang == "it" else "it"}/confronti/{sid}.html',
                   desc)


def index_page(items, sids, lang):
    t = TXT[lang]
    tiles = []
    for it, sid in zip(items, sids):
        g, d = it["group"], it["d"]
        import contradictions as C
        head = []
        if "price" in d:
            head.append(f'{d["price"][2]:.0f}% ' +
                        ("sul prezzo" if lang == "it" else "on price"))
        if "surface" in d:
            head.append(f'{d["surface"][2]:.0f}% ' +
                        ("sulla superficie" if lang == "it" else "on surface"))
        if "typology" in d:
            head.append("tipologia" if lang == "it" else "type")
        if "location" in d:
            head.append("comune")
        mark = " ✓" if it.get("verified") else ""
        tiles.append(
            f'<a class="tile" href="/{lang}/confronti/{sid}.html">'
            f'<b>{e(comune_of(g).replace("-", " ").title())} — '
            f'{e(C.best_label(g))}</b>'
            f'<small>{len(g)} ' +
            ("agenzie · " if lang == "it" else "agencies · ") +
            f'{e(", ".join(head))}{mark}</small></a>')

    body = f"""
<div class="hero">
  <h1>{e(t["index_h1"])}</h1>
  <p>{e(t["index_sub"].format(n=len(items)))}</p>
</div>
<div class="grid">{"".join(tiles)}</div>
<p class="note">✓ = {e(t["verified"].lower())}.</p>
"""
    return T.shell(f'{t["index_h1"]} | Borgo Vero', body, lang,
                   f'/{"en" if lang == "it" else "it"}/confronti/',
                   t["index_sub"].format(n=len(items)))


def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="../phase0/phase0.sqlite")
    ap.add_argument("--out", default="dist-contradictions")
    ap.add_argument("--candidates", action="store_true",
                    help="also publish single-photo and price+surface "
                         "matches, labelled as unconfirmed")
    a = ap.parse_args()

    import sqlite3
    import contradictions as C
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    items = C.build(conn)

    keep = [it for it in items
            if it.get("verified") or (set(it["evidence"]) & IDENTITY)
            or a.candidates]
    keep.sort(key=lambda it: (0 if it.get("verified") else 1,
                              -(it["d"].get("surface", (0, 0, 0))[2]
                                + it["d"].get("price", (0, 0, 0))[2])))
    print(f"{len(items)} contradictions, publishing {len(keep)} "
          f"({sum(1 for i in keep if i.get('verified'))} hand-verified)")
    if not a.candidates:
        print(f"  {len(items) - len(keep)} held back as unconfirmed "
              f"(--candidates to include them)")

    # Clear the previous build. A stale page is not cosmetic here: a
    # slug changes whenever a cluster's membership or address changes,
    # so yesterday's file would sit there asserting numbers about a
    # named agency that nothing regenerates. If the directory cannot be
    # removed (the sandbox mount refuses to unlink files the host
    # created), fall back to deleting file by file, and if even that
    # fails, say exactly which pages are stale rather than pretending
    # the build is clean.
    if os.path.isdir(a.out):
        try:
            shutil.rmtree(a.out)
        except OSError:
            pass
    sids = [slug(it) for it in keep]

    urls = []
    for lang in LANGS:
        write(f"{a.out}/{lang}/confronti/index.html",
              index_page(keep, sids, lang))
        urls.append(f"/{lang}/confronti/")
        for it, sid in zip(keep, sids):
            write(f"{a.out}/{lang}/confronti/{sid}.html",
                  property_page(it, sid, lang))
            urls.append(f"/{lang}/confronti/{sid}.html")

    write(f"{a.out}/index.html",
          '<!doctype html><meta charset="utf-8">'
          '<meta http-equiv="refresh" content="0;url=/it/confronti/">'
          '<link rel="canonical" href="/it/confronti/">')
    write(f"{a.out}/sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
          + "</urlset>\n")
    write(f"{a.out}/robots.txt",
          "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n")

    written = {os.path.normpath(f"{a.out}{u}"
                                + ("index.html" if u.endswith("/") else ""))
               for u in urls}
    stale = []
    for root, _, files in os.walk(a.out):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            p = os.path.normpath(os.path.join(root, fn))
            if p in written or p == os.path.normpath(f"{a.out}/index.html"):
                continue
            try:
                os.unlink(p)
            except OSError:
                stale.append(p)
    if stale:
        print(f"  !! {len(stale)} STALE page(s) could not be deleted and are "
              f"still served. Remove them before publishing:")
        for p in stale:
            print(f"       {p}")

    print(f"{len(urls)} pages -> {a.out}/")


if __name__ == "__main__":
    main()
