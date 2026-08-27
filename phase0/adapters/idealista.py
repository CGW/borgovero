"""Idealista.it adapter.

WHY THIS EXISTS: Idealista publishes a previous asking price and the
percentage cut directly on its search results page —

    Via Pasquale Alienati      EUR 178.000   was EUR 187.000   -5%
    Strada Provinciale 258     EUR 100.000   was EUR 107.000   -7%

Immobiliare does not. The build spec assumed price history had to be
accumulated by watching the market for twelve months; Idealista hands over
a slice of it immediately. Two of the first thirty listings carried a
visible cut, so on the order of 6-7% of the market has published history
available right now.

**Those figures are overwritten on the portal's next update.** Everything
else in Phase 0 can be re-fetched later; this cannot. That is the whole
argument for writing this adapter before the analysis is finished.

Idealista also carries ~5% more Sansepolcro inventory than Immobiliare
(188 vs 179), and prints EUR/m2 computed on its own surface figure, which
sometimes differs from Immobiliare's for the same property — a third
divergence axis at zero cost.

--------------------------------------------------------------------------
UNVERIFIED. READ THIS BEFORE TRUSTING ANYTHING BELOW.

The immobiliare adapter was written against live browser inspection. This
one was NOT — it was written offline, from the structural notes in
bv-site/CROSS-PORTAL-TEST.md, without the ability to fetch a page. The URL
patterns, CSS class names and pagination scheme below are informed guesses.

Two consequences:

1. **Run `python -m adapters.idealista --probe` first.** It is built to
   fail loudly and diagnostically — printing what it did find when the
   selectors miss — rather than returning an empty list that looks like a
   comune with no listings.

2. Idealista serves rendered DOM, not a JSON payload. There is no
   __NEXT_DATA__ equivalent to fall back on, so this adapter is
   structurally more fragile than the Immobiliare one and will break on
   redesigns that Immobiliare's would survive. Every extractor below takes
   a list of candidate selectors and reports which one hit, so repairing it
   is a matter of adding a candidate rather than rereading the parser.
--------------------------------------------------------------------------
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

SOURCE = "idealista"
BASE = "https://www.idealista.it"
PER_PAGE = 30          # Idealista's default page size; verify with --probe

# Idealista slugs carry the province: 'sansepolcro-arezzo'. Immobiliare
# does not. Kept here rather than in config because it is this portal's
# quirk, not project scope.
PROVINCE = {
    "sansepolcro": "arezzo", "anghiari": "arezzo",
    "caprese-michelangelo": "arezzo", "citerna": "arezzo",
    "pieve-santo-stefano": "arezzo", "monterchi": "arezzo",
    "badia-tedalda": "arezzo", "sestino": "arezzo",
}


def search_url(comune, page=1):
    slug = comune.lower()
    prov = PROVINCE.get(slug)
    path = f"{BASE}/vendita-case/{slug}-{prov}/" if prov \
        else f"{BASE}/vendita-case/{slug}/"
    # Idealista paginates as /lista-2.htm rather than a query parameter.
    return path if page <= 1 else f"{path}lista-{page}.htm"


# --- Selector candidates ----------------------------------------------
# Each entry is tried in order. First hit wins, and --probe reports which
# one fired so a silent miss becomes a visible one.

SEL = {
    "item":      ["article.item", "article[data-adid]", "div.item-info-container",
                  "article", "[data-element-id]"],
    "link":      ["a.item-link", "a[href*='/immobile/']", "a[title]"],
    "price":     ["span.item-price", ".item-price", "[class*='price']"],
    "pricedown": ["span.pricedown_price", ".pricedown_price", ".pricedown",
                  "[class*='pricedown']", "[class*='price-down']"],
    "details":   ["span.item-detail", ".item-detail", ".item-detail-char span"],
    "agency":    ["picture.logo-branding img", ".item-branding img",
                  ".logo-branding img", "[class*='branding'] img"],
}


def _first(soup_or_tag, key):
    """(elements, which_selector_hit) for the first candidate that matches."""
    for sel in SEL[key]:
        found = soup_or_tag.select(sel)
        if found:
            return found, sel
    return [], None


# --- Coercion ----------------------------------------------------------


def to_int(v):
    """'178.000 €' -> 178000. Italian thousands separator is '.'."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = re.sub(r"[^\d.,]", "", str(v))
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


def parse_details(texts):
    """['3 locali', '115 m²', '2° piano'] -> rooms, surface, floor.

    Idealista packs these into sibling spans with no stable per-field
    class, so they are identified by their unit word rather than position.
    """
    out = {"vani": None, "mq": None, "floor": None}
    for t in texts:
        low = t.lower()
        if out["mq"] is None and ("m²" in low or "m2" in low or " mq" in low):
            out["mq"] = to_int(t)
        elif out["vani"] is None and ("local" in low or "camer" in low):
            out["vani"] = to_float(t)
        elif out["floor"] is None and ("piano" in low or "terra" in low):
            out["floor"] = t.strip()
    return out


ADDRESS_NOISE = re.compile(r"\bNn\b\.?\s*$", re.I)
# Idealista's link title is a sentence, not an address:
#   'Appartamento in vendita in via Roma, 12'
# Everything before the last ' in ' is typology and verb.
TITLE_PREFIX = re.compile(r"^.*?\bin\s+(?:vendita|affitto)\s+(?:in|a)\s+",
                          re.I)


def normalise_address(raw):
    """Title or address string -> comparable street name.

    'Appartamento in vendita in via Roma, 12' -> 'via Roma'
    'Viale Osimo Nn'                          -> 'Viale Osimo'
    'Via Vannocchia, 133'                     -> 'Via Vannocchia'

    Three separate quirks, all of which have to go before an Idealista
    address can be compared to an Immobiliare one: the title is a full
    sentence, 'Nn' is appended where a street has no civico, and a civico
    is sometimes present after a comma. Immobiliare does none of these.
    Address is half the cross-portal join key, so each one left in place
    is a property that fails to match its twin.
    """
    if not raw:
        return None
    s = TITLE_PREFIX.sub("", raw.strip())
    s = s.split(",")[0].strip()
    s = ADDRESS_NOISE.sub("", s).strip()
    return s or None


# Idealista titles read 'Appartamento in vendita in via Roma'. The typology
# is the leading noun. Mapped to the same vocabulary as the Immobiliare
# adapter so the two are directly comparable — the cross-portal test found
# typology to be the MOST commonly contested field, more than price, and it
# decides which OMI band applies.
TYPOLOGY_MAP = {
    "appartamento": "appartamento",
    "attico": "appartamento",
    "mansarda": "appartamento",
    "loft": "appartamento",
    "monolocale": "appartamento",
    "bilocale": "appartamento",
    "trilocale": "appartamento",
    "quadrilocale": "appartamento",
    "casa indipendente": "cielo_terra",
    "casa o chalet indipendente": "cielo_terra",
    "casa o chalet": "cielo_terra",
    "villetta a schiera": "terratetto",
    "terratetto": "terratetto",
    "villa": "villa",
    "villetta": "villa",
    "chalet": "villa",
    "rustico": "rustico",
    "casale": "rustico",
    "cascina": "rustico",
    "masseria": "rustico",
    "palazzo": "cielo_terra",
    "stabile": "cielo_terra",
    "terreno": "terreno",
}


def map_typology(title):
    blob = (title or "").lower()
    for key, ours in TYPOLOGY_MAP.items():
        if key in blob:
            return ours
    if re.search(r"indipendent|cielo[- ]terra", blob):
        return "cielo_terra"
    return "unknown"


def map_zona(address, title):
    """Idealista has no macrozone field, so this is text-only.

    Weaker than the Immobiliare path, which gets a real 'Centro' label.
    Once the OMI zone perimeters (KML) are loaded, both portals should be
    assigned by point-in-polygon on lat/lon instead and this becomes a
    fallback — see SOT section 12.
    """
    blob = f"{address or ''} {title or ''}".lower()
    if "centro storico" in blob or re.search(r"\bcentro\b", blob):
        return "centro_storico"
    if re.search(r"campagna|collina|rurale|podere|localit", blob):
        return "campagna"
    return "periferia"


# --- Parse one search result ------------------------------------------


def parse_result(art, comune):
    link_els, _ = _first(art, "link")
    link = link_els[0] if link_els else None
    href = (link.get("href") or "") if link else ""
    title = (link.get("title") or link.get_text(" ", strip=True)) if link else ""

    adid = art.get("data-adid") or art.get("data-element-id") or ""
    if not adid:
        m = re.search(r"/immobile/(\d+)", href)
        adid = m.group(1) if m else ""

    price_els, _ = _first(art, "price")
    price = to_int(price_els[0].get_text(" ", strip=True)) if price_els else None

    # The expiring bit. Absent on most listings; that is expected, not a
    # parse failure — only a minority of listings carry a published cut.
    down_els, _ = _first(art, "pricedown")
    price_prev = to_int(down_els[0].get_text(" ", strip=True)) if down_els else None
    cut_pct = None
    if price and price_prev and price_prev > 0:
        cut_pct = round((price - price_prev) / price_prev * 100, 1)

    detail_els, _ = _first(art, "details")
    det = parse_details([d.get_text(" ", strip=True) for d in detail_els])

    agency_els, _ = _first(art, "agency")
    agency_name = None
    if agency_els:
        agency_name = (agency_els[0].get("alt")
                       or agency_els[0].get("title") or None)

    address_raw = normalise_address(title)
    mq = det["mq"]
    eur_m2_stated = round(price / mq, 1) if (price and mq) else None

    return {
        "source": SOURCE,
        "source_id": str(adid),
        "url": href if href.startswith("http") else f"{BASE}{href}",
        "comune": comune,
        "zona_guess": map_zona(address_raw, title),
        "macrozone": None,              # Idealista publishes no zone label
        "typology": map_typology(title),
        "typology_raw": title,
        "address_raw": address_raw,
        "mq": mq,
        # Idealista publishes ONE surface figure and does not say which
        # basis it uses. Left null rather than guessed — see SOT section 7,
        # where the basis question is already the largest open risk.
        "mq_commercial": None,
        "surface_raw": f"{mq} m²" if mq else None,
        "vani": det["vani"],
        "bathrooms": None,
        "floor": det["floor"],
        "condition": None,
        "epc": None,
        "price": price,
        "price_previous": price_prev,
        "price_cut_pct": cut_pct,
        "eur_m2_stated": eur_m2_stated,
        "description": None,
        "caption": title or None,
        "lat": None,                    # detail page only on this portal
        "lon": None,
        "agency_id": None,
        "agency_name": agency_name,
        "photo_ids": [],
        "photo_count": 0,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def result_count(html):
    """'188 case in vendita' -> 188."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    m = re.search(r"([\d.]+)\s*(?:case|immobili|annunci|risultat)", text, re.I)
    return int(m.group(1).replace(".", "")) if m else None


# --- Discovery ---------------------------------------------------------


def harvest(comune, max_pages=None):
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
                print(f"  {total} listings reported")

        soup = BeautifulSoup(html, "html.parser")
        items, sel = _first(soup, "item")
        if not items:
            print(f"  page {page}: no listing elements matched.")
            print("     Run --probe. The DOM has moved.")
            break

        new = 0
        for art in items:
            rec = parse_result(art, comune)
            if not rec["source_id"] or rec["source_id"] in seen:
                continue
            if not rec["price"]:
                continue          # navigation card, promo tile, not a listing
            seen.add(rec["source_id"])
            new += 1
            yield rec

        cuts = "—"
        print(f"  page {page}: {new} new ({len(seen)} total) via {sel}"
              f"{' [cached]' if cached else ''}  cuts:{cuts}")

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
        print("\n  A 403 here usually means the portal served a challenge")
        print("  page rather than blocking outright. Check the cached HTML")
        print("  in cache/html/ before assuming the URL is wrong.")
        return

    print(f"Reported result count: {result_count(html)}")
    soup = BeautifulSoup(html, "html.parser")

    items, sel = _first(soup, "item")
    print(f"Listing elements:      {len(items)} via {sel!r}")

    if not items:
        print("\n!! No candidate selector matched. The page fetched fine, so")
        print("   this is a selector problem, not a network one.")
        print("\n   Most common containers on the page:")
        from collections import Counter
        c = Counter()
        for t in soup.find_all(["article", "div", "section"]):
            cls = " ".join(t.get("class") or [])
            if cls:
                c[f"{t.name}.{cls.split()[0]}"] += 1
        for name, n in c.most_common(15):
            print(f"     {n:>4}  {name}")
        print("\n   Add the right one to SEL['item'] and re-probe.")
        return

    for key in ("link", "price", "pricedown", "details", "agency"):
        found, hit = _first(items[0], key)
        state = f"{len(found)} via {hit!r}" if found else "NOT FOUND"
        note = ""
        if key == "pricedown" and not found:
            note = "   (expected on a minority of listings only)"
        print(f"  {key:10} {state}{note}")

    rec = parse_result(items[0], comune)
    print("\n--- FIRST LISTING ---")
    for k in ("source_id", "price", "price_previous", "price_cut_pct",
              "eur_m2_stated", "mq", "vani", "floor", "typology",
              "zona_guess", "address_raw", "agency_name", "url"):
        print(f"  {k:16} {rec.get(k)}")

    parsed = [parse_result(a, comune) for a in items]
    parsed = [r for r in parsed if r["price"]]
    n = len(parsed) or 1
    print(f"\n--- YIELD ACROSS {len(parsed)} LISTINGS ON PAGE 1 ---")
    for k in ("price", "mq", "vani", "typology", "address_raw", "agency_name"):
        have = sum(1 for r in parsed if r.get(k) and r.get(k) != "unknown")
        print(f"  {k:16} {have:>3}/{len(parsed)}  ({have / n * 100:5.1f}%)")

    with_cut = [r for r in parsed if r["price_previous"]]
    print(f"\n--- PRICE HISTORY (the part that expires) ---")
    print(f"  Listings with a published cut: {len(with_cut)}/{len(parsed)}"
          f"  ({len(with_cut) / n * 100:.0f}%)")
    if with_cut:
        for r in with_cut[:5]:
            print(f"    {r['address_raw']:32} {r['price']:>9,} "
                  f"was {r['price_previous']:>9,}  {r['price_cut_pct']:+.0f}%")
    else:
        print("  None on this page. The cross-portal test saw ~2 in 30, so")
        print("  zero on one page is plausible — but zero across several")
        print("  pages means the pricedown selector is wrong, not that the")
        print("  market stopped cutting prices. Check a page you know has one.")

    unknown = [r["typology_raw"] for r in parsed if r["typology"] == "unknown"]
    if unknown:
        print(f"\n  Unmapped typologies: {sorted(set(unknown))[:5]}")

    ok = sum(1 for r in parsed if r["price"]) == len(parsed) and \
        sum(1 for r in parsed if r["mq"]) > len(parsed) * 0.7
    print("\nOK — safe to ingest." if ok else
          "\n!! Yield too low. Fix parse_result() before ingesting.")


# --- Offline self-check ------------------------------------------------

# A card shaped like the two real listings recorded in
# bv-site/CROSS-PORTAL-TEST.md (Via Pasquale Alienati, 178.000 was 187.000,
# -5%). This proves the PARSING is right even though the SELECTORS cannot
# be verified without fetching a page — which is the whole risk with this
# adapter. If --probe later shows the class names have moved, fix SEL and
# this check confirms nothing else broke on the way past.
FIXTURE = """
<article class="item" data-adid="12345678">
  <a class="item-link" href="/immobile/12345678/"
     title="Appartamento in vendita in via Pasquale Alienati, 4">x</a>
  <span class="item-price">178.000<span>&euro;</span></span>
  <span class="pricedown_price">187.000 &euro;</span>
  <div class="item-detail-char">
    <span class="item-detail">3 locali</span>
    <span class="item-detail">115 m&sup2;</span>
    <span class="item-detail">2&deg; piano</span>
  </div>
  <picture class="logo-branding"><img alt="Agenzia Alfa" src="x.png"></picture>
</article>
"""

EXPECTED = {
    "source_id": "12345678",
    "price": 178000,
    "price_previous": 187000,
    "price_cut_pct": -4.8,
    "mq": 115,
    "vani": 3.0,
    "typology": "appartamento",
    "address_raw": "via Pasquale Alienati",
    "agency_name": "Agenzia Alfa",
}


def selftest():
    art = BeautifulSoup(FIXTURE, "html.parser").select("article.item")[0]
    rec = parse_result(art, "sansepolcro")
    bad = {k: (v, rec.get(k)) for k, v in EXPECTED.items() if rec.get(k) != v}
    for k, v in EXPECTED.items():
        flag = "  <-- got " + repr(rec.get(k)) if k in bad else ""
        print(f"  {k:16} {v!r}{flag}")
    if bad:
        print(f"\n!! {len(bad)} field(s) wrong. Parsing logic is broken.")
        sys.exit(1)
    print("\nOK — parsing logic sound. Selectors still need --probe against")
    print("the live site; this check cannot tell you whether they match.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="parse a known fixture offline; no network")
    ap.add_argument("--dump", metavar="COMUNE",
                    help="parse one page and print records as JSON")
    args = ap.parse_args()
    if args.probe:
        probe()
    elif args.selftest:
        selftest()
    elif args.dump:
        recs = list(harvest(args.dump, max_pages=1))
        print(json.dumps(recs, indent=2, ensure_ascii=False))
    else:
        ap.print_help()
