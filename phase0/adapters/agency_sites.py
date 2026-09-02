"""Agency-site link harvester — the portal agencies' OWN websites.

WHAT THIS IS (SOT §15, S008)

For each agency already in the portal corpus, harvest its own site's
listing INDEX — own-site URL, price, stated surface, ref where shown —
so portal listings can carry an alternate URL (`url_alt`). This is NOT a
new listing source: no new pages, no new typologies, nothing enters a
band. It is a mapping table.

COVERAGE (Christopher's list, 2026-08-30)

First wave, by corpus weight: Leonardi 159, House 127, Romolini 93,
Cortesi 78+9 (two brands). Second wave, same session: NOW 36, SICASA
35, ImmobilInvest 11, Lancisi (ZERO portal rows — the harvest is how
"establish why" gets answered), and **Tiber Immobiliare has NO own
website** (38 portal rows; Facebook and portals only) — an agency whose
only public channel is other people's platforms, recorded here so
nobody goes looking again.

ACCESS — CHECKED PER SITE, BEFORE THE FIRST REQUEST

    leonardiimmobiliare.it   robots.txt empty — everything permitted.
                             Toolset Views pagination on /ricerca/.
    houseimmobiliare.info    robots disallows only WooCommerce
                             housekeeping paths. Listing archives at
                             /localita-immobile/<comune>/page/N/.
    romolini.com             robots DISALLOWS query-param URLs
                             (/*p=, /*refId= …) — so pagination via
                             query strings is off the table. Path-based
                             per-comune index pages are allowed:
                             /it/comune/<comune>.php.
    immobiliarecortesi.net   robots.txt empty. Località archives from
                             the sitemap. Index cards carry NO surface —
                             the matcher may fetch a single detail page
                             for a unique price+comune candidate (§15's
                             "unless a match is impossible without the
                             detail" clause), never in bulk.
    nowestate.it             robots: wp-admin only. CPT `estate`, pages
                             under /proprieta/; /citt/sansepolcro/ is
                             the one città archive. Cards carry price
                             but rarely mq — detail clause as Cortesi.
    sicasaimmobiliare.info   robots.txt empty. House's theme family:
                             /localita-immobile/<comune>/, cards carry
                             "80 mq ca." and "Rif: 0857".
    immobiliarelancisi.it    robots.txt empty. Same family:
                             /localita-immobile/<comune>/, cards carry
                             "94 mq" and "Rif. 4478" — and the price is
                             often "Info in agenzia".
    immobilinvestre.altervista.org
                             robots.txt empty. Static HTML: listings sit
                             INLINE on compravendite.html ("Rif. 687 -
                             Vendesi villetta … di 140 mq - € 200.000"),
                             no per-listing URLs — url_alt points at the
                             catalog page, site_ref carries the Rif.

These are small businesses, not portals. Politeness is the agencies.py
doctrine: long delay, identifiable UA, on-disk cache so a reparse never
refetches, one retry with a hard backoff, and fetcher.robots_status()
consulted per URL — a "disallowed" answer skips the URL and says so, it
does not get worked around.
"""

import re
import sys
import time

sys.path.insert(0, ".")
import config          # noqa: E402
import fetcher         # noqa: E402

# agencies.py's reasoning, unchanged: small businesses get a longer
# delay than the 4 s the portals get. fetcher.get() already throttles at
# config.REQUEST_DELAY_S per host; the extra sleep here brings the
# spacing to ~6 s on uncached fetches and costs nothing on cached ones.
EXTRA_DELAY_S = 2.0

LEONARDI = "https://www.leonardiimmobiliare.it"
HOUSE = "https://www.houseimmobiliare.info"
ROMOLINI = "https://www.romolini.com"
CORTESI = "https://www.immobiliarecortesi.net"
NOW = "https://nowestate.it"
SICASA = "https://www.sicasaimmobiliare.info"
LANCISI = "https://www.immobiliarelancisi.it"
IMMOBILINVEST = "http://www.immobilinvestre.altervista.org"

# site key -> portal agency_name values it must match against. The
# spellings are the PORTAL'S, verified against the database — "Now
# Immobilare srl" really is missing an i there.
PORTAL_AGENCIES = {
    "leonardi": ["Leonardi Immobiliare"],
    "house": ["House Immobiliare"],
    "romolini": ["Agenzia Romolini Immobiliare S.r.l."],
    "cortesi": ["Agenzia Immobiliare Cortesi", "Cortesi Luxury Real Estate"],
    "now": ["Now Immobilare srl"],
    "sicasa": ["SICASA Immobiliare"],
    "lancisi": [],   # zero portal rows — the harvest itself is the answer
    "immobilinvest": ["Immobilinvest Real Estate"],
}

# No own website (checked 2026-08-30): Tiber Immobiliare (38 portal
# rows) — Facebook and portals only. Not a harvester bug; a fact.
NO_OWN_SITE = {"Tiberimmobiliare": "tiberimmobiliare — no own website"}

# Anything under €10.000 on an agency index is a rent (Leonardi shows
# "€ 650" monthly beside €250.000 sales). Kept in the harvest, flagged,
# excluded from matching — the portal corpus is sales only.
RENT_CEILING = 10_000

# Site spellings of the corpus comuni. Leonardi writes "Pieve S.
# Stefano" and "Caprese Michel."; norm_comune() alone cannot bridge an
# abbreviation, and a card whose comune fails to resolve never matches —
# silently. Substring rules, applied to the normalized string.
_COMUNE_ALIASES = [
    ("pieve-santo-stefano", ("pievesantostefano", "pievesstefano",
                             "pievesantoste")),
    ("caprese-michelangelo", ("capresemichel", "caprese")),
    # 'badia' alone was a needle here until S009. startswith() then filed
    # Cortesi's BADIA PETROIA — a frazione of Città di Castello, in Umbria,
    # 60 km and one region away — as Badia Tedalda, on 4 listings against a
    # comune that has only 24. Same shape as the `rif` regex that matched
    # inside pe·rif·eria (§16c): an unanchored needle. It matters more here
    # because §16d PUBLISHES comune conflicts as a finding, so the bug
    # manufactures a contradiction out of our own error, in the one comune
    # small enough for four rows to move the band.
    ("badia-tedalda", ("badiatedalda",)),
    ("badia-petroia", ("badiapetroia",)),   # NOT corpus — as Città di
    # Castello below: resolves to a name that is visibly not one of ours.
    ("sansepolcro", ("sansepolcro", "sanseplocro")),
    ("citta-di-castello", ("cittadicastello",)),  # NOT corpus — kept so
    # a Città di Castello card resolves to a name that visibly is not
    # one of ours, rather than half-matching something.
    ("anghiari", ("anghiari",)),
    ("citerna", ("citerna",)),
    ("monterchi", ("monterchi",)),
    ("sestino", ("sestino",)),
]


def resolve_comune(raw):
    """Corpus slug for a site's comune string, else the normalized
    string itself (visibly non-corpus, never a silent half-match)."""
    n = config.norm_comune(raw)
    if not n:
        return None
    for slug, needles in _COMUNE_ALIASES:
        for needle in needles:
            if n.startswith(needle):
                return config.norm_comune(slug)
    return n


def comune_in_text(s):
    """The corpus comune a free-text phrase names, or None. Substring
    search over the normalized text ('APPARTAMENTO PIEVE SANTO STEFANO'
    → pieve-santo-stefano); non-corpus places resolve to None, never to
    a half-match."""
    n = config.norm_comune(s)
    if not n:
        return None
    corpus = {config.norm_comune(c) for c in config.COMUNI}
    for slug, needles in _COMUNE_ALIASES:
        target = config.norm_comune(slug)
        if target not in corpus:
            continue
        for needle in needles:
            if needle in n:
                return slug if "-" in slug else slug
    return None


def _get(url):
    """Polite fetch: robots first, cache-aware, extra delay when live."""
    status = fetcher.robots_status(url)
    if status == "disallowed":
        print(f"  [robots] DISALLOWED, skipping: {url}")
        return None
    html, code, cached = fetcher.get(url)
    if not cached:
        time.sleep(EXTRA_DELAY_S)
    return html


def _strip(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "",
               html or "", flags=re.S)
    t = re.sub(r"<svg.*?</svg>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "|", t)
    t = t.replace("&nbsp;", " ").replace("&euro;", "€").replace("&#8364;", "€")
    return re.sub(r"(\|\s*)+", "|", t)


def _price(seg):
    m = re.search(r"€\s*([\d.]{4,})", seg)
    return int(m.group(1).replace(".", "")) if m else None


def _merge_windows(html, urls, u, parse):
    """Parse EVERY window a card's link opens, and merge the fields.

    These themes render one card as two or three anchors to the same
    listing — photo wrapper, info block, "dettaglio immobile" button —
    and the figures do not all live behind the same one. House's data
    sits behind the last, SICASA splits price/Rif from title/mq across
    two, and NOW puts everything behind the MIDDLE anchor with empty
    windows either side. Picking one occurrence is a guess that silently
    yields all-None rows (NOW harvested 50 cards and 0 prices that way);
    merging field-by-field lets the decoy windows contribute nothing and
    costs one extra regex pass over text already in memory.
    """
    merged = None
    for m in re.finditer(re.escape(u), html):
        pos = m.start()
        nxt = len(html)
        for v in urls:
            p = html.find(v, pos + 1)
            if p != -1 and p > pos:
                nxt = min(nxt, p)
        got = parse(_strip(html[pos:min(nxt, pos + 9000)]))
        if merged is None:
            merged = got
            continue
        for k, val in got.items():
            if merged.get(k) in (None, 0) and val not in (None, 0):
                merged[k] = val
    return merged or {}


def _row(site, url, ref=None, price=None, mq=None, comune=None, title=None,
         price_withheld=0):
    return {
        "site": site,
        "url": url,
        "ref": ref,
        "price": price,
        "price_withheld": price_withheld,
        "mq": mq,
        "comune": resolve_comune(comune) if comune else None,
        "comune_raw": comune,
        "title": (title or "").strip()[:160] or None,
        "is_rent": 1 if (price and price < RENT_CEILING) else 0,
    }


# --- Leonardi ----------------------------------------------------------

def harvest_leonardi(max_pages=60):
    """Toolset Views pagination. The wpv_view_count value is read off
    page 1 rather than hardcoded — it is a view id, not a session token,
    but reading it costs nothing and hardcoding it is folklore-in-waiting.
    """
    first = _get(f"{LEONARDI}/ricerca/")
    if not first:
        return []
    m = re.search(r"wpv_view_count=(\d+)", first)
    view = m.group(1) if m else None
    pages = [int(n) for n in re.findall(r"wpv_paged=(\d+)", first)]
    last = min(max(pages) if pages else 1, max_pages)

    rows = {}
    for n in range(1, last + 1):
        if n == 1:
            html = first
        else:
            html = _get(f"{LEONARDI}/ricerca/?wpv_view_count={view}"
                        f"&wpv_paged={n}")
        if not html:
            continue
        got = _parse_leonardi_page(html)
        for r in got:
            rows[r["url"]] = r
        print(f"  leonardi page {n}/{last}: {len(got)} cards, "
              f"{len(rows)} total")
    return list(rows.values())


def _parse_leonardi_page(html):
    """Cards are delimited by their '#<ref>' marker; each card's fields
    and its /immobile/ link sit between one marker and the next."""
    out = []
    marks = [(m.start(), m.group(1))
             for m in re.finditer(r">\s*#(\d{3,6})\s*<", html)]
    for i, (pos, ref) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(html)
        seg = html[pos:end]
        mu = re.search(r'href="(' + re.escape(LEONARDI) +
                       r'/immobile/[^"]+)"', seg)
        if not mu:
            continue
        t = _strip(seg)
        mt = re.search(r"\|([A-ZÀ-Ù][^|]{4,120})\|", t)
        mc = re.search(r"Località:\|?\s*\|?([^|(]+)\(", t)
        ms = re.search(r"Superficie:\|?\s*\|?(\d+)", t)
        out.append(_row(
            "leonardi", mu.group(1), ref=ref,
            price=_price(t),
            mq=int(ms.group(1)) if ms else None,
            comune=mc.group(1).strip() if mc else None,
            title=mt.group(1) if mt else None,
        ))
    return out


# --- The localita-immobile family: House, SICASA, Lancisi --------------
#
# Three agencies, one WordPress theme family, one archive shape:
# /localita-immobile/<comune>/page/N/. Card details differ slightly
# ('88 m²' vs '80 mq ca.', 'Rif. 6346' vs 'Rif: 0857') and the regexes
# below accept all of them.

def _harvest_localita(site, base, max_pages=30):
    rows = {}
    for comune in config.COMUNI:
        for n in range(1, max_pages + 1):
            url = (f"{base}/localita-immobile/{comune}/" if n == 1 else
                   f"{base}/localita-immobile/{comune}/page/{n}/")
            html = _get(url)
            if not html:
                break
            got = _parse_localita_page(site, base, html, comune)
            new = [r for r in got if r["url"] not in rows]
            for r in got:
                rows[r["url"]] = r
            print(f"  {site} {comune} page {n}: {len(got)} cards "
                  f"({len(new)} new), {len(rows)} total")
            if not got or not new:
                break
    return list(rows.values())


def _parse_localita_page(site, base, html, comune):
    """One card per /immobile/ link; fields merged across every window
    that link opens (see _merge_windows — the themes disagree about
    which anchor carries the figures)."""
    out = []
    urls = list(dict.fromkeys(re.findall(
        r'href="(' + re.escape(base) + r'/immobile/[^"]+)"', html)))

    def parse(t):
        mr = re.search(r"Rif\.?\s*[:.]?\s*([\w/-]+)", t)
        # '88 m²' collapses to '88|m|2' once tags become pipes; SICASA
        # and Lancisi write '80 mq ca.' / '94 mq' instead. Accept both.
        ms = re.search(r"(\d+)[\s|]*m[\s|]*[²2]|(\d+)\s*mq", t)
        mt = re.search(r'([A-ZÀ-Ù][^|]{4,140}?)\s*\|', t.replace("\n", " "))
        return {
            "ref": mr.group(1) if mr else None,
            "price": _price(t),
            "price_withheld": 1 if "Info in agenzia" in t else 0,
            "mq": int(ms.group(1) or ms.group(2)) if ms else None,
            "title": mt.group(1) if mt else None,
        }

    for u in urls:
        out.append(_row(site, u, comune=comune,
                        **_merge_windows(html, urls, u, parse)))
    return out


def harvest_house(max_pages=30):
    return _harvest_localita("house", HOUSE, max_pages)


def harvest_sicasa(max_pages=30):
    return _harvest_localita("sicasa", SICASA, max_pages)


def harvest_lancisi(max_pages=30):
    """Lancisi has ZERO portal rows, so nothing here can ever match —
    the harvest exists to answer WHY an agency with a full catalog is
    absent from the portal corpus (SOT §15). Count the withheld prices:
    the first card read said 'Info in agenzia'."""
    return _harvest_localita("lancisi", LANCISI, max_pages)


# --- Romolini ----------------------------------------------------------

ROMOLINI_COMUNI = [
    "sansepolcro", "anghiari", "caprese_michelangelo", "citerna",
    "pieve_santo_stefano", "monterchi", "badia_tedalda", "sestino",
]


def harvest_romolini():
    """Per-comune index pages (path-based — the robots.txt disallows
    query-string pagination, so those are never requested). The ref is
    also the URL's id suffix, which is what associates card to link."""
    rows = {}
    for comune in ROMOLINI_COMUNI:
        html = _get(f"{ROMOLINI}/it/comune/{comune}.php")
        if not html:
            print(f"  romolini {comune}: no page")
            continue
        got = _parse_romolini_page(html, comune)
        for r in got:
            rows[r["url"]] = r
        print(f"  romolini {comune}: {len(got)} cards, {len(rows)} total")
    return list(rows.values())


def _parse_romolini_page(html, comune):
    out = []
    marks = [(m.start(), m.group(1))
             for m in re.finditer(r"Rif\.\s*(\d+)", html)]
    for i, (pos, ref) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(html)
        seg = html[max(0, pos - 3000):end]
        # Older slugs join the id with '_', newer ones with '-'.
        mu = (re.search(r'href="(https://www\.romolini\.com/it/'
                        r'[a-z0-9_\-]+[_-]' + ref + r')"', seg)
              or re.search(r'href="(/it/[a-z0-9_\-]+[_-]' + ref + r')"',
                           seg))
        if not mu:
            continue
        url = mu.group(1)
        if url.startswith("/"):
            url = ROMOLINI + url
        t = _strip(html[pos:end])
        ms = re.search(r"Interni:\|?\s*\|?([\d.]+)\s*mq", t)
        mt = re.search(r"\|([A-ZÀ-Ù][A-ZÀ-Ù' ,\-0-9]{8,140})\|", t)
        withheld = 1 if re.search(r"su richiesta|riservata", t, re.I) else 0
        out.append(_row(
            "romolini", url, ref=ref,
            price=_price(t), price_withheld=withheld,
            mq=int(ms.group(1).replace(".", "")) if ms else None,
            comune=comune.replace("_", " "),
            title=mt.group(1) if mt else None,
        ))
    return out


# --- Cortesi -----------------------------------------------------------

def harvest_cortesi(max_pages=30):
    """Cortesi's località tree is organized by AGENCY BRANCH, not by
    comune: /localita-immobile/sansepolcro/anghiari/ is the Sansepolcro
    branch's Anghiari archive, and Citerna lives under san-giustino.
    So the archive list comes from their localita sitemap: a leaf that
    resolves to a corpus comune is harvested under that comune; a
    Sansepolcro-branch frazione leaf (gricignano, santa-fiora …) is
    Sansepolcro; the bare branch page mixes comuni and is harvested
    with comune=None — unknown, honestly, rather than mislabelled."""
    corpus = {config.norm_comune(c) for c in config.COMUNI}
    archives = []
    sm = _get(f"{CORTESI}/localita-immobile-sitemap.xml")
    for u in re.findall(r"<loc>([^<]+)</loc>", sm or ""):
        parts = u.rstrip("/").split("/")
        leaf, parent = parts[-1], parts[-2]
        r = resolve_comune(leaf)
        if r in corpus:
            archives.append((u, leaf))
        elif parent == "sansepolcro":
            archives.append((u, "sansepolcro"))
        elif leaf == "sansepolcro":
            archives.append((u, None))       # branch page, mixed comuni
    archives.append((f"{CORTESI}/case-in-vendita-a-sansepolcro/",
                     "sansepolcro"))

    rows = {}
    for base, comune in archives:
        for n in range(1, max_pages + 1):
            url = base if n == 1 else f"{base}page/{n}/"
            html = _get(url)
            if not html:
                break
            got = _parse_cortesi_page(html, comune)
            new = [r for r in got if r["url"] not in rows]
            for r in got:
                # A comune-labelled archive outranks the mixed branch
                # page for the same listing.
                if r["url"] not in rows or (
                        r["comune"] and not rows[r["url"]]["comune"]):
                    rows[r["url"]] = r
            print(f"  cortesi {base.split('/localita-immobile/')[-1] or base} "
                  f"page {n}: {len(got)} cards ({len(new)} new), "
                  f"{len(rows)} total")
            if not got or not new:
                break
    return list(rows.values())


def _parse_cortesi_page(html, comune):
    """Cortesi index cards carry title, zone, price and ref — NO surface.
    The matcher compensates; see harvest_links.py."""
    out = []
    urls = list(dict.fromkeys(re.findall(
        r'href="(' + re.escape(CORTESI) + r'/immobile/[^"]+)"', html)))
    for u in urls:
        pos = html.rfind(u)
        nxt = len(html)
        for v in urls:
            if v == u:
                continue
            p = html.find(v, pos + 1)
            if p != -1:
                nxt = min(nxt, p)
        t = _strip(html[pos:min(nxt, pos + 9000)])
        mr = re.search(r"\|([A-Z]{1,4}[A-Z/]*/\d+)\|", t)
        ms = re.search(r"(\d+)[\s|]*m[\s|]*[²2]|(\d+)\s*mq", t)
        mt = re.search(r"\|([A-ZÀ-Ù][^|]{4,140})\|", t)
        out.append(_row(
            "cortesi", u, ref=mr.group(1) if mr else None,
            price=_price(t),
            mq=int(ms.group(1) or ms.group(2)) if ms else None,
            comune=comune,
            title=mt.group(1) if mt else None,
        ))
    return out


def cortesi_detail_mq(url):
    """The sanctioned single-detail-page exception (SOT §15): fetch ONE
    detail page to read the surface for a unique price+comune candidate.
    Never called in bulk — the matcher gates it. Named for Cortesi,
    where the need first arose; NOW's cards have the same gap."""
    html = _get(url)
    if not html:
        return None
    t = _strip(html)
    m = re.search(r"(\d+)[\s|]*m[\s|]*[²2]|Superficie\D{0,20}(\d+)|"
                  r"(\d+)\s*mq", t)
    return int(next(g for g in m.groups() if g)) if m else None


# --- NOW (nowestate.it) -------------------------------------------------

def harvest_now(max_pages=30):
    """NOW's only server-rendered index is the HOMEPAGE.

    Checked 2026-08-30: /properties/ and /citt/sansepolcro/ each return
    ~117 KB of chrome with ZERO listing links — those archives are built
    client-side — and the estate sitemap holds a single loc. The
    homepage carries ~50 real cards, so that is what gets harvested.
    Rendering JS to reach the rest is the line this project has already
    declined at Immobiliare's detail pages and Idealista (§9, §12.4):
    partial coverage, said out loud, is the honest outcome."""
    rows = {}
    html = _get(f"{NOW}/")
    if html:
        for r in _parse_now_page(html):
            rows[r["url"]] = r
    print(f"  now: {len(rows)} cards off the homepage — /properties/ and "
          f"/citt/ render client-side and serve none")
    return list(rows.values())


# S010: NOW PUBLISHES A LABELLED RECORD, AND IT PRINTS ITS OWN REF.
#
#   Codice Rif:|2026025|Città:|San Giustino|Provincia:|Perugia|
#   Metri Quadri:|70|Vani:|5|Camere da letto:|2|Bagni:|1
#
# Structured fields, not prose. `_strip` turns tags into pipes, which is
# why the label and its value are separated by one.
_NOW_BLOCK = re.compile(
    r"Codice Rif:\s*\|\s*(\d{4,9})\s*\|(.{0,400}?)"
    r"(?:dettaglio immobile|Codice Rif)", re.S | re.I)
_NOW_CITTA = re.compile(r"Citt[àa]:\s*\|\s*([^|]{2,40})\|", re.I)
_NOW_MQ = re.compile(r"Metri Quadri:\s*\|\s*(\d{2,6})\s*\|", re.I)
_NOW_SLUG_REF = re.compile(r"[-_](\d{6,9})$")


def _now_blocks(txt):
    """{ref: {comune, mq}} from NOW's card records. S010.

    The route this replaces read the anchors' `title` attributes and
    resolved 1 of 48 rows, so NOW contributed a single listing to a site
    holding fifty of its cards. The attributes exist; they carry the
    typology and sometimes a place, and `comune_in_text` on them almost
    never matched. Surface came out of the card body and landed on 14.

    The record sits BEFORE the card's links, and `_merge_windows` only
    ever looks forward from an occurrence — so both fields read as absent
    rather than as unparsed. THE FAILURE WAS A WINDOW DIRECTION, NOT A
    MISSING FIELD, and it is the same shape as S009's regex that could
    never match: nothing in the output distinguishes "the site does not
    publish this" from "we never looked where it is".

    Binding is by ref, not position. Pairing the Nth record with the Nth
    link works on today's page and is an assumption about DOM order that
    dies the day the theme reflows; matching the slug's trailing number
    against the ref the record PRINTS is a claim the page confirms
    itself. On this site §16d publishes a comune disagreement as a
    finding, so a comune guessed from layout and got wrong is published
    as an agency contradicting itself.

    It costs two rows of fifty, where the slug says 23026001 and the
    record says 2026002. Those stay None. The ~20 further Nones are not
    misses at all: NOW sells across Tuscany, Umbria and Romagna — San
    Giustino, Castrocaro Terme, Novafeltria, Gubbio, Rovereto — and out
    of scope resolving to None is this working.
    """
    out = {}
    for m in _NOW_BLOCK.finditer(txt):
        body = m.group(2)
        c = _NOW_CITTA.search(body)
        q = _NOW_MQ.search(body)
        out[m.group(1)] = {
            "comune": comune_in_text(c.group(1).strip()) if c else None,
            "mq": int(q.group(1)) if q else None,
        }
    return out


def _parse_now_page(html):
    out = []
    txt = _strip(html)
    urls = list(dict.fromkeys(re.findall(
        r'href="(' + re.escape(NOW) + r'/proprieta/[^"]+)"', html)))
    def parse(t):
        ms = re.search(r"(\d+)[\s|]*m[\s|]*[²2]|(\d+)\s*mq", t)
        mt = re.search(r"\|(?:Vendita|Affitto)\|([^|]{4,140})\|", t)
        return {
            "ref": None,
            "price": _price(t),
            "price_withheld": 0,
            "mq": int(ms.group(1) or ms.group(2)) if ms else None,
            "title": mt.group(1) if mt else None,
        }

    blocks = _now_blocks(txt)
    n_comune = n_mq = 0
    for u in urls:
        fields = _merge_windows(html, urls, u, parse)
        m = _NOW_SLUG_REF.search(u.rstrip("/").split("/")[-1])
        ref = m.group(1) if m else None
        rec = blocks.get(ref) or {}
        comune = rec.get("comune")
        # The ref was hardcoded None, so NOW rows carried no identity at
        # all — the one join key §16d calls decisive WITHIN an agency.
        # Safe to populate now that S010 stopped cross-agency ref from
        # forming clusters on its own.
        if fields.get("ref") is None:
            fields["ref"] = ref
        # The record's surface beats the card body's: the body yielded 14
        # of 50, the record 47. Only fill a gap — never overwrite a figure
        # the card actually printed.
        if fields.get("mq") is None and rec.get("mq"):
            fields["mq"] = rec["mq"]
        n_comune += bool(comune)
        n_mq += bool(fields.get("mq"))
        rent = bool(re.search(re.escape(u) + r'[\s\S]{0,400}?Affitto', html))
        out.append(_row("now", u, comune=comune, **fields)
                   | ({"is_rent": 1} if rent else {}))
    print(f"  now: {n_comune} of {len(urls)} cards in a corpus comune, "
          f"{n_mq} with a surface (the rest sell outside the eight comuni)")
    return out


# --- ImmobilInvest (static altervista pages) ---------------------------

def harvest_immobilinvest():
    """Listings sit INLINE on compravendite.html — no per-listing URLs
    exist, so every row's url is the catalog page and the Rif is the
    identity. The €-sign arrives mojibake'd ('â¬') from the host's
    charset mismatch; normalized before parsing."""
    url = f"{IMMOBILINVEST}/compravendite.html"
    html = _get(url)
    if not html:
        return []
    # UTF-8 '€' (e2 82 ac) read as latin-1 arrives as 'â\x82¬'.
    html = (html.replace("â¬", "€")
                .replace("â¬", "€").replace("&euro;", "€"))
    t = _strip(html)
    out = []
    marks = list(re.finditer(r"Rif\.?\s*(\d+)\s*[-–]\s*", t))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(t)
        seg = t[m.start():end]
        ms = re.search(r"di\s+(\d+)\s*mq|(\d+)\s*mq", seg)
        comune = comune_in_text(seg[:200])
        rent = bool(re.search(r"affitt", seg.lower()[:80]))
        # All inline listings share one page; the fragment keeps each
        # row unique in the (site, url) primary key and is harmless in
        # a browser. No such anchor exists on the page — the Rif column
        # is the real identity.
        out.append(_row(
            "immobilinvest", f"{url}#rif-{m.group(1)}", ref=m.group(1),
            price=_price(seg),
            mq=int(ms.group(1) or ms.group(2)) if ms else None,
            comune=comune,
            title=seg[m.end() - m.start():][:80].split("|")[0].strip()
                  or None,
        ) | ({"is_rent": 1} if rent else {}))
    print(f"  immobilinvest: {len(out)} inline listings on "
          f"compravendite.html")
    return out


HARVESTERS = {
    "leonardi": harvest_leonardi,
    "house": harvest_house,
    "romolini": harvest_romolini,
    "cortesi": harvest_cortesi,
    "now": harvest_now,
    "sicasa": harvest_sicasa,
    "lancisi": harvest_lancisi,
    "immobilinvest": harvest_immobilinvest,
}
