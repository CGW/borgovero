"""Immobiliare.it adapter.

VERIFIED against the live site on 2026-08-27 via browser inspection.

THE KEY FINDING: the *search results* page embeds complete listing data for
all 25 results in its <script id="__NEXT_DATA__"> blob. Price, surface,
rooms, floor, typology, coordinates, macrozone, condition, photo IDs and the
selling agency are all there.

Consequence: Phase 0 does not need to fetch individual listing pages at all.

    Sansepolcro:  179 listings =  8 requests, not 179
    All 8 comuni: 602 listings = 27 requests, not 602

That is a ~22x reduction in request volume, which cuts run time from hours
to minutes and cuts ToS exposure proportionally. Detail pages are only
needed for EPC class and full description — neither of which Phase 0 uses.

Shape of each result (confirmed):

    {
      "realEstate": {
        "id": 128457332,
        "price": {"value": 280000, "formattedValue": "EUR 280.000"},
        "advertiser": {"agency": {"id": "165322",
                                  "displayName": "House Immobiliare"}},
        "properties": [{
          "surface": "115 m2",
          "rooms": "5",
          "bathrooms": "2",
          "floor": {"value": "1o", "floorOnlyValue": "1"},
          "typology": {"id": "14", "name": "Appartamento"},
          "ga4Condition": "Buono / Abitabile",
          "caption": "Villetta a schiera con giardino",
          "location": {"address": "Viale Osimo", "city": "Sansepolcro",
                       "macrozone": "Centro", "microzone": null,
                       "latitude": 43.5763, "longitude": 12.1281},
          "multimedia": {"photos": [{"id": "1909212598", ...}]}
        }]
      },
      "seo": {"url": "https://www.immobiliare.it/annunci/128457332/"}
    }

The result array is located by recursive search rather than a fixed path,
so a Next.js reorganisation does not break it.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone

from bs4 import BeautifulSoup

sys.path.insert(0, "..")
import config
import fetcher

SOURCE = "immobiliare"
BASE = "https://www.immobiliare.it"
PER_PAGE = 25


def search_url(comune, page=1):
    url = f"{BASE}/vendita-case/{comune}/"
    if page > 1:
        url += f"?pag={page}"
    return url


# --- JSON extraction ---------------------------------------------------


def extract_next_data(html):
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            pass
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def find_results(obj, _d=0):
    """The array of search results, wherever Next.js has put it."""
    if _d > 14 or obj is None:
        return None
    if isinstance(obj, list) and len(obj) > 2:
        first = obj[0]
        if isinstance(first, dict) and "realEstate" in first:
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = find_results(v, _d + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_results(v, _d + 1)
            if r:
                return r
    return None


def result_count(html):
    """'179 risultati' -> 179. Used to size pagination without guessing."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    m = re.search(r"([\d.]+)\s*risultat", text, re.I)
    return int(m.group(1).replace(".", "")) if m else None


# --- Coercion ----------------------------------------------------------


def to_int(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = re.sub(r"[^\d,.]", "", str(v))
    if not s:
        return None
    s = s.replace(".", "").split(",")[0]
    return int(s) if s.isdigit() else None


def to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v)).replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_surface(v):
    """'115 m²' -> 115.

    NOTE: on the search payload this is the smaller, non-commercial figure.
    See parse_surface_commercial() and the warning in the module docstring
    of analyze.py — the distinction is load-bearing.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"(\d[\d.]*)", str(v).split("|")[0])
    if not m:
        return None
    return int(float(m.group(1).replace(".", "")))


def parse_surface_commercial(v):
    """'115 m² | commerciale 183,2 m²' -> 183.

    Agencies quote *commerciale* — which weights balconies, terraces and
    garages into the total — because it makes EUR/m2 look lower. On this
    listing the two figures differ by 59%. Capturing both is the only way
    to know which one a given price is being justified against.
    """
    if not isinstance(v, str) or "commerc" not in v.lower():
        return None
    m = re.search(r"commerciale\s*(\d[\d.,]*)", v, re.I)
    if not m:
        return None
    return int(float(m.group(1).replace(".", "").replace(",", ".")))


# Immobiliare typology.name -> ours. Verified names seen live:
# Appartamento, Villetta a schiera, Villa unifamiliare, Rustico/Casale,
# Terratetto unifamiliare, Attico, Mansarda, Loft, Terreno
TYPOLOGY_MAP = {
    "appartamento": "appartamento",
    "attico": "appartamento",
    "mansarda": "appartamento",
    "loft": "appartamento",
    "open space": "appartamento",
    # Room-count names. Immobiliare uses these instead of 'Appartamento'
    # on a large minority of flats — 49 listings in the 844-row ingest
    # fell through to 'unknown' without them.
    "monolocale": "appartamento",
    "bilocale": "appartamento",
    "trilocale": "appartamento",
    "quadrilocale": "appartamento",
    "plurilocale": "appartamento",
    # A colonica is a farmhouse. 16 in the ingest, and they belong with
    # the rustici — they are the characteristic rural stock this project
    # is about, not an unknown.
    "casa colonica": "rustico",
    "colonica": "rustico",
    "terratetto": "terratetto",
    "villetta a schiera": "terratetto",
    "casa indipendente": "cielo_terra",
    "villa unifamiliare": "villa",
    "villa bifamiliare": "villa",
    "villa plurifamiliare": "villa",
    "villa": "villa",
    "villetta": "villa",
    "rustico": "rustico",
    "casale": "rustico",
    "cascina": "rustico",
    "terreno": "terreno",
    # Off-plan developments. Seen live on the Sansepolcro search page and
    # previously falling through to 'unknown', which handed them a
    # residential fallback band. Named so they can be excluded knowingly —
    # see config.EXCLUDE_TYPOLOGIES.
    "progetto": "progetto",
    "nuova costruzione": "progetto",
    "palazzo": "cielo_terra",
    "stabile": "cielo_terra",
}


def map_typology(name, caption=""):
    """Portal's structured field FIRST; caption only as a fallback.

    S008: the old version scanned field+caption as one blob in dict
    order, so an agency headline ("APPARTAMENTO INGRESSO INDIPENDENTE")
    overrode Immobiliare's own field ("Terratetto unifamiliare") on 45
    of 844 rows — and one of them was about to be published as a
    cross-channel typology contradiction that was really our artifact.
    The field is the portal's claim; the caption is the agency's prose.
    When they disagree, that is self_contradictions.py's axis, not a
    reason to silently prefer whichever word sorts first in the map.
    """
    for blob in (f"{name or ''}".lower(), f"{caption or ''}".lower()):
        if not blob.strip():
            continue
        for key, ours in TYPOLOGY_MAP.items():
            if key in blob:
                return ours
        if re.search(r"terra[- ]tetto|cielo[- ]terra|indipendent", blob):
            return "cielo_terra"
    return "unknown"


def map_zona(macrozone, microzone, address, caption):
    """Immobiliare gives a real macrozone ('Centro'), far better than
    keyword-guessing from free text. Fall back to text only if absent."""
    mz = f"{macrozone or ''} {microzone or ''}".lower()
    if mz.strip():
        if "centro" in mz:
            return "centro_storico"
        if re.search(r"campagna|collin|rural|periferi", mz):
            return "campagna" if "campagn" in mz or "collin" in mz else "periferia"
        return "periferia"
    blob = f"{address or ''} {caption or ''}".lower()
    if "centro storico" in blob or "centro" in blob:
        return "centro_storico"
    if re.search(r"campagna|collina|rurale", blob):
        return "campagna"
    return "periferia"


# --- Parse one search result ------------------------------------------


def parse_result(item, comune):
    re_ = item.get("realEstate") or {}
    props = re_.get("properties") or [{}]
    p = props[0] if props else {}
    loc = p.get("location") or {}
    agency = ((re_.get("advertiser") or {}).get("agency")) or {}

    surface_raw = p.get("surface")
    photos = ((p.get("multimedia") or {}).get("photos")) or []
    typ_name = ((p.get("typology") or {}).get("name")
                or (re_.get("typology") or {}).get("name"))

    url = ((item.get("seo") or {}).get("url")
           or f"{BASE}/annunci/{re_.get('id')}/")

    return {
        "source": SOURCE,
        "source_id": str(re_.get("id") or ""),
        "url": url,
        "comune": comune,
        "zona_guess": map_zona(loc.get("macrozone"), loc.get("microzone"),
                               loc.get("address"), p.get("caption")),
        "macrozone": loc.get("macrozone"),
        "typology": map_typology(typ_name, p.get("caption")),
        "typology_raw": typ_name,
        "address_raw": loc.get("address"),
        "mq": parse_surface(surface_raw),
        "mq_commercial": parse_surface_commercial(surface_raw),
        "surface_raw": surface_raw,
        "vani": to_float(p.get("rooms")),
        "bathrooms": to_int(p.get("bathrooms")),
        "floor": str((p.get("floor") or {}).get("value") or "") or None,
        "condition": p.get("ga4Condition"),
        "epc": None,                      # detail page only; unused in Phase 0
        "price": to_int((re_.get("price") or {}).get("value")),
        "description": p.get("description"),
        "caption": p.get("caption"),
        "lat": to_float(loc.get("latitude")),
        "lon": to_float(loc.get("longitude")),
        "agency_id": str(agency.get("id") or "") or None,
        "agency_name": agency.get("displayName"),
        "photo_ids": [str(ph.get("id")) for ph in photos if ph.get("id")],
        "photo_count": len(photos),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# --- Discovery ---------------------------------------------------------


def harvest(comune, max_pages=None):
    """Yield fully-parsed listing records, straight from search pages."""
    max_pages = max_pages or config.MAX_PAGES_PER_COMUNE
    seen = set()
    total = None

    for page in range(1, max_pages + 1):
        url = search_url(comune, page)
        html, status, cached = fetcher.get(url)
        if not html:
            print(f"  page {page}: HTTP {status}, stopping")
            break

        if total is None:
            total = result_count(html)
            if total:
                pages = -(-total // PER_PAGE)
                print(f"  {total} listings reported -> ~{pages} pages")

        data = extract_next_data(html)
        results = find_results(data) if data else None
        if not results:
            print(f"  page {page}: no results array in __NEXT_DATA__")
            print("     Run --probe. The JSON shape has moved.")
            break

        new = 0
        for item in results:
            rec = parse_result(item, comune)
            if not rec["source_id"] or rec["source_id"] in seen:
                continue
            seen.add(rec["source_id"])
            new += 1
            yield rec

        print(f"  page {page}: {new} new ({len(seen)} total)"
              f"{' [cached]' if cached else ''}")

        if new == 0:
            break
        if total and len(seen) >= total:
            break
        if len(seen) >= config.MAX_LISTINGS_PER_COMUNE:
            print("  hit MAX_LISTINGS_PER_COMUNE")
            break


# --- Probe -------------------------------------------------------------


def probe():
    comune = config.COMUNI[0]
    url = search_url(comune)
    print(f"robots.txt: {fetcher.robots_status(url)}")
    print(f"Fetching {url}\n")

    html, status, cached = fetcher.get(url)
    if not html:
        print(f"FAILED — HTTP {status}")
        return

    total = result_count(html)
    print(f"Reported result count: {total}")

    data = extract_next_data(html)
    print(f"__NEXT_DATA__ present:  {data is not None}")
    results = find_results(data) if data else None
    print(f"Results array found:    {results is not None} "
          f"({len(results) if results else 0} items)")

    if not results:
        print("\n!! Could not locate the results array.")
        print("   find_results() looks for a list whose items have a")
        print("   'realEstate' key. If Immobiliare renamed that, update it.")
        return

    rec = parse_result(results[0], comune)
    print("\n--- FIRST LISTING ---")
    for k in ("source_id", "price", "mq", "mq_commercial", "surface_raw",
              "vani", "floor", "typology", "typology_raw", "zona_guess",
              "macrozone", "condition", "address_raw", "agency_name",
              "photo_count"):
        print(f"  {k:16} {rec.get(k)}")

    parsed = [parse_result(r, comune) for r in results]
    have = lambda k: sum(1 for r in parsed if r.get(k))  # noqa: E731
    n = len(parsed)
    print(f"\n--- YIELD ACROSS {n} LISTINGS ON PAGE 1 ---")
    for k in ("price", "mq", "mq_commercial", "vani", "typology",
              "macrozone", "condition", "agency_name"):
        pct = have(k) / n * 100
        print(f"  {k:16} {have(k):>3}/{n}  ({pct:5.1f}%)")

    unknown = [r["typology_raw"] for r in parsed if r["typology"] == "unknown"]
    if unknown:
        print(f"\n  Unmapped typologies: {sorted(set(unknown))}")
        print("  Add them to TYPOLOGY_MAP.")

    if have("price") == n and have("mq") > n * 0.7:
        print("\nOK — safe to run the full ingest.")
    else:
        print("\n!! Yield too low. Fix parse_result() before ingesting.")


# --- Detail-page survey ------------------------------------------------

# What a detail page might carry that the search payload does not. Each
# entry is (label, regex) and is SURVEYED, not parsed — the point is to
# measure availability before deciding whether the fetches are worth it,
# not to build a parser for fields that may turn out to be absent.
#
# The expensive question this answers: capturing anything here costs one
# request per listing (602) instead of one per 25 (27). That is worth
# paying for a field that exists on most listings and worthless for one
# that appears on three.
DETAIL_FIELDS = [
    # The known gap. A live listing showed '115 m2 | commerciale 183,2 m2',
    # but the search payload carries zero, so it must come from here.
    ("commerciale",   re.compile(r"commerciale[\s:]*([\d.,]+)\s*m", re.I)),
    # The one that would change the project. If listings state their own
    # publication date, days-on-market stops being an estimate off the ID
    # curve and becomes a fact — and the curve becomes a cross-check
    # rather than the foundation. Worth far more than commerciale.
    # NB: '.{0,40}?' and not '[^\\d]{0,40}'. The label is usually
    # 'Riferimento e Data annuncio 4820A - 15/03/2021', so the agency
    # reference sits between the label and the date and it contains
    # digits — a non-digit skip can never reach past it.
    ("data_annuncio", re.compile(
        r"(?:riferimento e data annuncio|data annuncio|inserito il)"
        r".{0,40}?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I)),
    ("riferimento",   re.compile(
        r"riferimento(?:\s+e\s+data\s+annuncio)?[\s:]*"
        r"([A-Za-z0-9._/-]{3,24})", re.I)),
    ("classe_energ",  re.compile(
        r"classe energetica[\s:]*([A-G][1-4]?\+?)", re.I)),
    ("anno_costr",    re.compile(r"anno di costruzione[\s:]*(\d{4})", re.I)),
    ("spese_cond",    re.compile(
        r"spese condominio[^\d]{0,20}([\d.,]+)", re.I)),
    ("stato_imm",     re.compile(
        r"stato[\s:]*(ottimo|buono|nuovo|da ristrutturare|ristrutturato)",
        re.I)),
]


def survey_details(n=10):
    """Fetch n detail pages and report which fields actually appear.

    Costs n requests, not 602, and replaces speculation about what is on
    a detail page with a measured rate.
    """
    comune = config.COMUNI[0]
    html, status, _ = fetcher.get(search_url(comune))
    if not html:
        print(f"Search page failed — HTTP {status}")
        return
    data = extract_next_data(html)
    results = find_results(data) if data else None
    if not results:
        print("No results array; run --probe first.")
        return

    urls = [parse_result(r, comune)["url"] for r in results][:n]
    print(f"Sampling {len(urls)} detail pages "
          f"({config.REQUEST_DELAY_S:.0f}s apart, "
          f"~{len(urls) * config.REQUEST_DELAY_S / 60:.1f} min)\n")

    hits = {label: [] for label, _ in DETAIL_FIELDS}
    fetched = 0
    for u in urls:
        dhtml, dstatus, cached = fetcher.get(u)
        if not dhtml:
            print(f"  {u.rsplit('/', 2)[-2]:>12}  HTTP {dstatus}")
            continue
        fetched += 1
        text = BeautifulSoup(dhtml, "html.parser").get_text(" ", strip=True)
        found = []
        for label, rx in DETAIL_FIELDS:
            m = rx.search(text)
            if m:
                hits[label].append(m.group(1))
                found.append(label)
        print(f"  {u.rsplit('/', 2)[-2]:>12}  "
              f"{', '.join(found) if found else '(nothing matched)'}"
              f"{' [cached]' if cached else ''}")

    if not fetched:
        print("\nNo pages fetched. Nothing can be concluded.")
        return

    print(f"\n--- FIELD AVAILABILITY ACROSS {fetched} DETAIL PAGES ---")
    for label, _ in DETAIL_FIELDS:
        got = hits[label]
        pct = len(got) / fetched * 100
        sample = f"  e.g. {got[0]}" if got else ""
        print(f"  {label:16} {len(got):>2}/{fetched}  ({pct:5.1f}%){sample}")

    full = 602
    cost = full * config.REQUEST_DELAY_S / 60
    print(f"\n  A full detail crawl is ~{full} requests, ~{cost:.0f} minutes,")
    print(f"  against {27} for search pages alone — a ~22x increase in")
    print("  request volume and in whatever exposure that carries.")
    print("\n  Judge each field on its rate above. A field present on most")
    print("  listings may justify it; one present on a handful will not.")
    if hits["data_annuncio"]:
        print("\n  >>> NOTE: listings state their own publication date.")
        print("      That is a measured DOM rather than an estimate off the")
        print("      ID curve, and it is worth more than commerciale — it")
        print("      turns the project's weakest number into its firmest.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--survey-details", nargs="?", type=int, const=10,
                    metavar="N",
                    help="fetch N detail pages (default 10) and report "
                         "which fields are actually present")
    args = ap.parse_args()
    if args.probe:
        probe()
    elif args.survey_details:
        survey_details(args.survey_details)
    else:
        ap.print_help()
