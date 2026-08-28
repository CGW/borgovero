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


def fetch(url, tries=2):
    for n in range(tries):
        try:
            r = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(r, timeout=30).read().decode(
                "utf-8", "replace")
        except Exception:
            if n == tries - 1:
                return None
            time.sleep(2)
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
    """'165.000' -> 165000. Italian thousands separator is a dot."""
    if not s:
        return None
    s = re.sub(r"[^\d.,]", "", str(s))
    s = s.replace(".", "").split(",")[0]
    try:
        return int(s)
    except ValueError:
        return None


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
        time.sleep(config.REQUEST_DELAY_S)
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
    rec["price"] = None if (price_raw and "riservat" in price_raw.lower()) \
        else to_int(price_raw)
    rec["price_withheld"] = bool(price_raw and "riservat" in price_raw.lower())

    m = re.search(r"Categoria:\s*([^|]+)\|", t)
    rec["typology_raw"] = m.group(1).strip() if m else None

    z = (rec["zona_raw"] or "").lower()
    rec["comune"] = z.strip() or None

    m = re.search(rf"RIF:\s*{re.escape(str(rec['agency_ref'] or lid))}\s*([^|]{{20,600}})", t)
    rec["description"] = m.group(1).strip() if m else None
    return rec


# --- harvest ------------------------------------------------------------

def harvest_centogambe(limit=None):
    urls = centogambe_urls()
    print(f"centogambe: {len(urls)} listing URLs from sitemap")
    for u in (urls[:limit] if limit else urls):
        html = fetch(u)
        time.sleep(config.REQUEST_DELAY_S)
        if html:
            yield parse_centogambe(html, u)


def harvest_marcellini(limit=None):
    ids = marcellini_ids()
    print(f"marcellini: {len(ids)} listing ids from Elenco.asp")
    for lid in (ids[:limit] if limit else ids):
        u = f"{MARCELLINI}/ImmDettagli.asp?Pagina=ImmDettagli&ID={lid}"
        html = fetch(u)
        time.sleep(config.REQUEST_DELAY_S)
        if html:
            yield parse_marcellini(html, u, lid)


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
