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
    "palazzo": "cielo_terra",
    "stabile": "cielo_terra",
}


def map_typology(name, caption=""):
    blob = f"{name or ''} {caption or ''}".lower()
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    probe() if args.probe else ap.print_help()
