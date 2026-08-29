"""Agency-site adapters — Centogambe and Marcellini.

WHY THESE TWO SPECIFICALLY

Of the nine agencies Christopher named, seven are on Immobiliare and
these two are not (SOT S16b). Without them the cross-agency variance
table has holes exactly where a local would expect to see names.

WHY THEY MATTER MORE THAN "TWO MORE SOURCES"

They publish the AGENCY REFERENCE NUMBER — Centogambe `rif. 0383`,
Marcellini `Rif: 11175`. Portals print the same reference inside the
listing description ("Riferimento: 5258" was visible on an Immobiliare
detail page). That is a **second join key, and a better one than
photographs**: exact, agency-issued, and needing no eyeballing. Photo
matching (photomatch.py) finds candidates a human must confirm; a
matching reference number is decisive.

ACCESS — CLEANER THAN THE PORTALS, AND CHECKED BEFORE WRITING A LINE

    centogambe   robots.txt = "User-agent: * / Disallow:" (empty
                 Disallow = everything permitted), and it publishes
                 sitemap_index.xml. 256 listings enumerable directly,
                 no crawling of search pages at all.
    marcellini   no robots.txt (404), so nothing is disallowed.
                 Enumerated via Elenco.asp?Pagina=Elenco&Cat=<category>.

Neither refuses a script, unlike Immobiliare's detail pages and
Idealista's search (both 403). There is nothing here to work around,
which is the whole reason these are pleasant to build against.

Still polite: config.REQUEST_DELAY_S between requests, identifiable UA.
These are small businesses running WordPress and classic ASP on modest
hosting — a hammering is far more noticeable to them than to a portal.

WHAT EACH SITE GIVES

    Centogambe   price, surface, rif, zone, title, comune, photos
                 "€ 165.000 - rif. 0383", "Appartamento di 120 mq."
    Marcellini   Zona / Rif / Mq / Vani / Prezzo / Categoria, as a
                 clean label-value block. NOTE: many carry
                 "Prezzo: trattativa riservata" — price withheld.
                 That is itself worth counting: an agency that hides
                 prices cannot be compared on price, and how often that
                 happens is a finding about market opacity.
"""

import re
import sys
import time
import urllib.request

sys.path.insert(0, "..")
import config

UA = {"User-Agent": config.USER_AGENT}

CENTOGAMBE = "https://www.immobiliarecentogambe.it"
MARCELLINI = "http://www.immobiliaremarcellini.it"

MARCELLINI_CATEGORIES = [
    "Appartamenti", "Ville", "Coloniche", "Poderi", "Negozi",
    "Capannoni", "Esercizi", "TerreniAgricoli", "TerreniEdificabili",
]


# These are small businesses on modest shared hosting, not portals with
# a CDN in front, so they get their own, longer delay.
#
# NOTE ON THE CENTOGAMBE 403s — diagnosed 2026-08-28, and the first two
# diagnoses were WRONG. They looked like throttling (31% of pages, and
# raising the delay was the obvious response). They are not. The SAME 79
# URLs fail every time at any delay, and opening one in a real browser
# gives:
#
#     "Accesso negato. Inserisci la password per continuare."
#
# They are PASSWORD-PROTECTED listings that Centogambe nevertheless
# publishes in its public sitemap. There is nothing to retry and nothing
# to work around — the agency gated them deliberately, and a password
# wall is a closed door. They are recorded as GATED, not failed, and
# counted, because 79 of 255 (31%) of an agency's inventory being behind
# a password is a finding about market opacity, not a bug (SOT S16e).
AGENCY_DELAY_S = 8.0

# On a throttle, back off hard before trying again. One retry only —
# if it still refuses, record the failure and move on rather than
# pressing.
BACKOFF_S = 30.0


def fetch(url, tries=2):
    for n in range(tries):
        try:
            r = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(r, timeout=30).read().decode(
                "utf-8", "replace")
        except Exception as e:
            if n == tries - 1:
                return None
            code = getattr(e, "code", None)
            # 403/429 here means "you are going too fast", so wait
            # properly rather than retrying straight into the same wall.
            time.sleep(BACKOFF_S if code in (403, 429) else 2)
    return None


def _text(html):
    """Tag-stripped text with '|' separators, so label:value survives."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "",
               html, flags=re.S)
    t = re.sub(r"<[^>]+>", "|", t)
    t = re.sub(r"&nbsp;", " ", t)
    t = re.sub(r"(\|\s*)+", "|", t)
    return t


def to_int(s):
    """'165.000' -> 165000. Italian thousands separator is a dot.

    Takes the FIRST complete number, never a concatenation. Marcellini
    publishes price RANGES on some listings ('200.000 - 300.000'), and
    stripping separators across the whole string produced 200000300000
    — which then reported one property as 74.074.085% apart from
    another. Grab one number and stop.
    """
    if not s:
        return None
    m = re.search(r"\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?", str(s))
    if not m:
        return None
    try:
        return int(m.group(0).replace(".", "").split(",")[0])
    except ValueError:
        return None


def is_range(s):
    """True when the raw field carries two numbers — a price range."""
    return len(re.findall(r"\d{1,3}(?:\.\d{3})+|\d{4,}", str(s or ""))) > 1


# --- Centogambe (WordPress) --------------------------------------------

def centogambe_urls():
    """Every listing URL, straight from the sitemap they publish."""
    xml = fetch(f"{CENTOGAMBE}/immobile-sitemap.xml")
    if not xml:
        return []
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    return [u for u in urls if u.rstrip("/").split("/")[-1] != "immobile"]


def parse_centogambe(html, url):
    t = _text(html)
    rec = {"source": "centogambe", "url": url, "agency_name": "Centogambe"}

    m = re.search(r"immobile/(.+?)-(\d+)/?$", url)
    rec["source_id"] = m.group(2) if m else url.rstrip("/").split("/")[-1]

    m = re.search(r"€\s*([\d.]+)\s*-\s*\brif\.?\s*([\w-]+)", t, re.I)
    if m:
        rec["price"] = to_int(m.group(1))
        rec["agency_ref"] = m.group(2).strip()
    else:
        m = re.search(r"€\s*([\d.]+)", t)
        rec["price"] = to_int(m.group(1)) if m else None
        m = re.search(r"\brif\.?\s*[:.]?\s*([\w-]+)", t, re.I)
        rec["agency_ref"] = m.group(1).strip() if m else None

    m = re.search(r"(\d+)\s*mq", t, re.I)
    rec["mq"] = int(m.group(1)) if m else None

    m = re.search(r"\|([^|]{5,90}?)\|([^|]*?\(Comune di ([^)]+)\))", t)
    if m:
        rec["title"] = m.group(1).strip()
        rec["zona_raw"] = m.group(2).split("(")[0].strip()
        rec["comune"] = m.group(3).strip().lower()
    else:
        mm = re.search(r"Comune di ([^)|]+)", t)
        rec["comune"] = mm.group(1).strip().lower() if mm else None

    rec["photo_urls"] = list(dict.fromkeys(
        re.findall(r'https://www\.immobiliarecentogambe\.it/wp-content/'
                   r'uploads/[^"\']+\.(?:jpg|jpeg|png)', html)))[:12]
    return rec


# --- Marcellini (classic ASP) ------------------------------------------

def marcellini_ids():
    ids = set()
    for cat in MARCELLINI_CATEGORIES:
        html = fetch(f"{MARCELLINI}/Elenco.asp?Pagina=Elenco&Cat={cat}")
        time.sleep(AGENCY_DELAY_S)
        if not html:
            continue
        ids |= set(re.findall(r"ImmDettagli\.asp\?[^\"']*ID=(\d+)", html))
    return sorted(ids)


def parse_marcellini(html, url, lid):
    t = _text(html)
    rec = {"source": "marcellini", "url": url, "source_id": str(lid),
           "agency_name": "Marcellini"}

    def field(label):
        m = re.search(rf"\|{label}\s*:\s*([^|]+)\|", t, re.I)
        return m.group(1).strip() if m else None

    rec["zona_raw"] = field("Zona")
    rec["agency_ref"] = field("Rif")
    rec["mq"] = to_int(field("Mq"))
    rec["vani"] = to_int(field("Vani"))

    price_raw = field("Prezzo")
    rec["price_raw"] = price_raw
    # "trattativa riservata" = withheld. Do NOT coerce to 0 or drop the
    # listing — how often price is hidden is itself a finding.
    rec["price_withheld"] = bool(price_raw and "riservat" in price_raw.lower())

    # THE PRICE FIELD IS A BRACKET, NOT A PRICE (found S004, the hard
    # way: every one of 152 "prices" was a 100k multiple). Live pages
    # read "meno di € 100.000" / "tra € 200.000 ed € 300.000" / a bare
    # range. to_int() on that returns the first bound, which is how a
    # €29.000 flat got recorded as a €100.000 asking price and printed
    # as a +245% cross-agency contradiction. Never store a bracket
    # bound in `price`.
    is_bracket = bool(price_raw) and (
        is_range(price_raw)
        or re.search(r"\bmeno\s+di\b|\btra\b|\boltre\b|\bfino\s+a\b",
                     price_raw, re.I))
    rec["price_bracket"] = price_raw.strip() if is_bracket else None
    if rec["price_withheld"] or is_bracket:
        rec["price"] = None
    else:
        rec["price"] = to_int(price_raw)

    m = re.search(r"Categoria:\s*([^|]+)\|", t)
    rec["typology_raw"] = m.group(1).strip() if m else None

    z = (rec["zona_raw"] or "").lower()
    rec["comune"] = z.strip() or None

    m = re.search(rf"RIF:\s*{re.escape(str(rec['agency_ref'] or lid))}\s*([^|]{{20,600}})", t)
    rec["description"] = m.group(1).strip() if m else None

    # The description often prints the REAL asking price even when the
    # field is a bracket or "riservata" — "Prezzo 214.000,00",
    # "Prezzo80.000,00" (no space; both seen live, S004). 31 of 229
    # stored descriptions carried one. That figure is the agency's own
    # published number on the same page, so it belongs in `price`.
    if rec["price"] is None and rec["description"]:
        m = re.search(r"[Pp]rezzo\s*:?\s*€?\s*"
                      r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?)",
                      rec["description"])
        if m:
            p = to_int(m.group(1))
            if p and p >= 5000:
                rec["price"] = p

    # Property photos live at foto/<id>/<name>.jpg. Site chrome lives at
    # img/ — excluded, or every listing would "match" every other one on
    # the agency logo (exactly the false positive photomatch.py already
    # had to defend against).
    rec["photo_urls"] = [
        f"{MARCELLINI}/{u.lstrip('/')}" if not u.startswith("http") else u
        for u in dict.fromkeys(
            re.findall(r'<img[^>]+src="([^"]*foto/[^"]+\.(?:jpg|jpeg|png|JPG|JPEG|PNG))"',
                       html))
    ][:12]
    return rec


# --- harvest ------------------------------------------------------------

def url_id(u):
    """The numeric id at the end of a Centogambe listing URL."""
    m = re.search(r"-(\d+)/?$", u)
    return m.group(1) if m else u.rstrip("/").split("/")[-1]


def harvest_centogambe(limit=None, skip=()):
    """`skip` is applied BEFORE fetching, which is the entire point of a
    resume. An earlier version filtered after the fetch, so it re-
    downloaded all 255 pages and discarded most of them — no faster, and
    it hit their server for nothing.

    Failed fetches are COUNTED and REPORTED, not silently dropped. The
    first full run stored 173 of 255 and the missing 79 were invisible;
    a silent drop looks exactly like a small market.
    """
    urls = centogambe_urls()
    todo = [u for u in urls if url_id(u) not in skip]
    print(f"centogambe: {len(urls)} listing URLs from sitemap"
          + (f", {len(urls) - len(todo)} already stored, {len(todo)} to fetch"
             if skip else ""))
    failed = []
    for i, u in enumerate(todo[:limit] if limit else todo, 1):
        html = fetch(u)
        time.sleep(AGENCY_DELAY_S)
        if html:
            yield parse_centogambe(html, u)
        else:
            failed.append(u)
        if i % 20 == 0:
            print(f"  ...{i}/{len(todo)} fetched", flush=True)
    if failed:
        # Denominator is what we ATTEMPTED, not the whole sitemap. The
        # earlier version divided by len(urls) and reported "79 of 255
        # (31%)" on a run that only tried 82 — flattering and wrong.
        print(f"  !! {len(failed)} of {len(todo)} attempted pages did not "
              f"load ({len(failed)/max(len(todo),1)*100:.0f}%)")
        for u in failed[:5]:
            print(f"       {u}")
        print("     These are PASSWORD-PROTECTED listings "
              "('Accesso negato. Inserisci la password'),")
        print("     published in the sitemap but gated. Not retryable, and")
        print("     not to be worked around. Re-running will not recover them.")


def harvest_marcellini(limit=None, skip=()):
    ids = marcellini_ids()
    todo = [i for i in ids if str(i) not in skip]
    print(f"marcellini: {len(ids)} listing ids from Elenco.asp"
          + (f", {len(ids) - len(todo)} already stored, {len(todo)} to fetch"
             if skip else ""))
    failed = []
    for n, lid in enumerate(todo[:limit] if limit else todo, 1):
        u = f"{MARCELLINI}/ImmDettagli.asp?Pagina=ImmDettagli&ID={lid}"
        html = fetch(u)
        time.sleep(AGENCY_DELAY_S)
        if html:
            yield parse_marcellini(html, u, lid)
        else:
            failed.append(lid)
        if n % 20 == 0:
            print(f"  ...{n}/{len(todo)} fetched", flush=True)
    if failed:
        print(f"  !! {len(failed)} of {len(ids)} pages FAILED to fetch "
              f"({len(failed)/len(ids)*100:.0f}%): {failed[:8]}")
        print("     Re-run to pick them up — the harvest is resumable.")


def probe():
    print("=" * 70)
    print("AGENCY ADAPTER PROBE")
    print("=" * 70)
    for name, gen in (("CENTOGAMBE", harvest_centogambe(3)),
                      ("MARCELLINI", harvest_marcellini(3))):
        print(f"\n--- {name} ---")
        got = 0
        for rec in gen:
            got += 1
            print(f"  ref={str(rec.get('agency_ref')):8} "
                  f"price={str(rec.get('price')):>9} "
                  f"mq={str(rec.get('mq')):>5} "
                  f"comune={str(rec.get('comune'))[:18]:20} "
                  f"{str(rec.get('title') or rec.get('typology_raw'))[:34]}")
        if not got:
            print("  NOTHING PARSED — selectors or enumeration have moved.")


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        print("usage: python3 -m adapters.agencies --probe")
