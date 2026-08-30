"""Agency-site link harvester — the four portal agencies' OWN websites.

WHAT THIS IS (SOT §15, S008)

For each agency already in the portal corpus, harvest its own site's
listing INDEX — own-site URL, price, stated surface, ref where shown —
so portal listings can carry an alternate URL (`url_alt`). This is NOT a
new listing source: no new pages, no new typologies, nothing enters a
band. It is a mapping table.

WHY THESE FOUR

Corpus weight on Immobiliare: Leonardi 159, House 127, Romolini 93,
Cortesi 78+9 (two brands). itcasa/NOW/SICASA only if these go fast.
Lancisi has ZERO portal rows — establish why before adding it anywhere.

ACCESS — CHECKED 2026-08-30, BEFORE THE FIRST REQUEST

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
    immobiliarecortesi.net   robots.txt empty. Per-comune pages
                             /case-in-vendita-a-<comune>/ + /page/N/.
                             NOTE: index cards carry NO surface — the
                             matcher may fetch a single detail page for
                             a unique price+comune candidate (the §15
                             "unless a match is impossible without the
                             detail" clause), never in bulk.

These are four small businesses, not portals. Politeness is the
agencies.py doctrine: long delay, identifiable UA, on-disk cache so a
reparse never refetches, one retry with a hard backoff, and
fetcher.robots_status() consulted per URL — a "disallowed" answer skips
the URL and says so, it does not get worked around.

WHAT EACH INDEX CARD GIVES (verified on live pages, 2026-08-30)

    leonardi   #7893 | VILLETTA SINGOLA CON GIARDINO | Località:
               San Giustino (Provincia di Perugia) | Prezzo: € 250.000 |
               Superficie: 150 mq  → ref, price, mq, comune
    house      Appartamento ristrutturato … | Rif. 6346 - Sansepolcro -
               … | € 168.000 or "Info in agenzia" | 88 m²
    romolini   Rif. 2253 | Casale | Baldaccio | € 560.000 | Interni:
               230 mq | Esterni: 7,60 ha  (ref == the URL's id suffix)
    cortesi    Casa Singola con Giardino. | Sansepolcro zona Aboca |
               € 100.000 | BCS/265 | categories | camere/bagni — NO mq
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

# site key -> portal agency_name values it must match against
PORTAL_AGENCIES = {
    "leonardi": ["Leonardi Immobiliare"],
    "house": ["House Immobiliare"],
    "romolini": ["Agenzia Romolini Immobiliare S.r.l."],
    "cortesi": ["Agenzia Immobiliare Cortesi", "Cortesi Luxury Real Estate"],
}

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
    ("badia-tedalda", ("badiatedalda", "badia")),
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


# --- House -------------------------------------------------------------

def harvest_house(max_pages=30):
    rows = {}
    for comune in config.COMUNI:
        for n in range(1, max_pages + 1):
            url = (f"{HOUSE}/localita-immobile/{comune}/" if n == 1 else
                   f"{HOUSE}/localita-immobile/{comune}/page/{n}/")
            html = _get(url)
            if not html:
                break
            got = _parse_house_page(html, comune)
            new = [r for r in got if r["url"] not in rows]
            for r in got:
                rows[r["url"]] = r
            print(f"  house {comune} page {n}: {len(got)} cards "
                  f"({len(new)} new), {len(rows)} total")
            if not got or not new:
                break
    return list(rows.values())


def _parse_house_page(html, comune):
    out = []
    urls = list(dict.fromkeys(re.findall(
        r'href="(' + re.escape(HOUSE) + r'/immobile/[^"]+)"', html)))
    for u in urls:
        # The info card is the LAST occurrence of the link — earlier
        # ones wrap the photo and the favourites widget.
        pos = html.rfind(u)
        nxt = len(html)
        for v in urls:
            if v == u:
                continue
            p = html.find(v, pos + 1)
            if p != -1:
                nxt = min(nxt, p)
        t = _strip(html[pos:min(nxt, pos + 9000)])
        mr = re.search(r"Rif\.?\s*[:.]?\s*([\w/-]+)", t)
        # The theme renders '88 m²' as '88|m|2' once tags collapse to
        # pipes — allow pipe or space between the number and the unit.
        ms = re.search(r"(\d+)[\s|]*m[\s|]*[²2]", t)
        mt = re.search(r'([A-ZÀ-Ù][^|]{4,140}?)\s*\|\s*Rif',
                       t.replace("\n", " "))
        withheld = 1 if "Info in agenzia" in t else 0
        out.append(_row(
            "house", u, ref=mr.group(1) if mr else None,
            price=_price(t), price_withheld=withheld,
            mq=int(ms.group(1)) if ms else None,
            comune=comune,
            title=mt.group(1) if mt else None,
        ))
    return out


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
    Cortesi detail page to read the surface for a unique price+comune
    candidate. Never called in bulk — the matcher gates it."""
    html = _get(url)
    if not html:
        return None
    t = _strip(html)
    m = re.search(r"(\d+)\s*m\s*[²2]|Superficie\D{0,20}(\d+)|(\d+)\s*mq", t)
    return int(next(g for g in m.groups() if g)) if m else None


HARVESTERS = {
    "leonardi": harvest_leonardi,
    "house": harvest_house,
    "romolini": harvest_romolini,
    "cortesi": harvest_cortesi,
}
