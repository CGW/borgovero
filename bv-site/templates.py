"""Borgo Vero page templates.

Design constraints, all downstream of the thesis:

  The page is a negotiation instrument, not a browsing experience.
  A buyer prints it or screenshots it and puts it on the table.

So: one property per page, legible in black and white, no interaction
required to see the numbers, and every claim carries its source.

Legal line (spec section 9): publish the record, never the conclusion.
"Listed by X at EUR172,000, also listed by Y at EUR189,000" is a fact with
both sources linked. "X inflates prices" is an allegation. The two sentences
carry the same information to any reader; only one is a liability.
"""

import html
import json

CSS = """
*{box-sizing:border-box}
:root{
  --ink:#1a1a1a; --mute:#6b6b6b; --line:#d8d4cc; --bg:#faf8f5;
  --card:#fff; --hi:#8a3324; --ok:#2d6a4f; --warn:#9a6700;
}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Georgia,serif;}
.wrap{max-width:820px;margin:0 auto;padding:24px 20px 80px}
a{color:var(--hi)}
header.site{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:28px}
.brand{font-size:20px;font-weight:700;letter-spacing:.02em;text-decoration:none;color:var(--ink)}
.brand span{color:var(--hi)}
.lang a{font-size:13px;margin-left:10px;text-decoration:none}
h1{font-size:26px;line-height:1.25;margin:0 0 4px}
.sub{color:var(--mute);font-size:15px;margin-bottom:26px}
.block{background:var(--card);border:1px solid var(--line);border-radius:6px;
  padding:18px 20px;margin-bottom:16px}
.block h2{font-size:12px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--mute);margin:0 0 12px;font-weight:700}
.big{font-size:34px;font-weight:700;line-height:1}
.rows{width:100%;border-collapse:collapse;font-size:15px}
.rows td{padding:7px 0;border-bottom:1px solid var(--line);vertical-align:top}
.rows tr:last-child td{border-bottom:none}
.rows td.r{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.lbl{color:var(--mute)}
.over{color:var(--hi);font-weight:700}
.under{color:var(--ok);font-weight:700}
.flag{background:#fdf6e3;border-left:3px solid var(--warn);padding:12px 14px;
  margin-top:12px;font-size:14px}
.note{font-size:13px;color:var(--mute);margin-top:10px;line-height:1.5}
.src{font-size:12px;color:var(--mute)}
input[type=text]{width:100%;padding:14px 16px;font-size:16px;
  border:2px solid var(--ink);border-radius:6px;background:#fff}
button{padding:14px 22px;font-size:16px;font-weight:600;background:var(--ink);
  color:#fff;border:0;border-radius:6px;cursor:pointer}
.hero{background:var(--card);border:2px solid var(--ink);border-radius:8px;
  padding:26px;margin-bottom:26px}
.hero h1{font-size:23px;margin-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:6px;
  padding:14px;text-decoration:none;color:inherit;display:block}
.tile b{display:block;font-size:17px;margin-bottom:3px}
.tile small{color:var(--mute)}
footer{margin-top:44px;padding-top:16px;border-top:1px solid var(--line);
  font-size:13px;color:var(--mute)}
@media print{
  body{background:#fff}
  .block,.hero{border:1px solid #999;break-inside:avoid}
  .noprint{display:none}
  a{color:#000;text-decoration:none}
}
"""

T = {
    "it": {
        "tagline": "Prezzi immobiliari della Valtiberina, verificati.",
        "ask": "Prezzo richiesto",
        "band": "Fascia OMI",
        "dom": "Da quanto è in vendita",
        "listed_by": "Pubblicato da",
        "comps": "Immobili comparabili",
        "days": "giorni",
        "floor_area": "superficie calpestabile",
        "commercial": "superficie commerciale",
        "above": "sopra il massimo della fascia",
        "below": "sotto il minimo della fascia",
        "method": "Come calcoliamo questi numeri",
        "spread": "Stesso immobile, due prezzi.",
        "spread_agency": "Stesso immobile, agenzie diverse, prezzi diversi.",
        "cheapest": "Prezzo più basso",
        "self_conflict": "pubblica dati diversi su portali diversi",
        "disagree_on": "Gli annunci non concordano su",
        "each_linked": "Ogni valore è collegato alla sua fonte.",
        "numbers_say": "Cosa dicono i numeri",
        # NOT "una valutazione indipendente". That phrasing shipped on all
        # 36 pages and it was the site calling itself, affirmatively, the
        # one regulated word seo-spec §3.5 forbids — while the method page
        # two blocks below said "non è una perizia". The site was
        # contradicting itself about its own nature on every page it
        # published, which is the exact class of thing it publishes other
        # people for. "Indice indipendente" is both accurate and the term
        # the whole standard is built on.
        "declaration": "Borgo Vero è un indice indipendente e senza scopo "
                       "di lucro dei prezzi immobiliari in Valtiberina. "
                       "Non è una perizia.",
        "about": "Chi siamo",
        "corrections": "Segnala un errore",
        "sources_line": "Fasce OMI: Agenzia delle Entrate. Annunci: portali "
                        "pubblici, con link alla fonte. Nessun compenso da "
                        "agenzie, venditori o portali.",
        "bv_price": "Prezzo Borgo Vero",
        "vs_ask": "rispetto alla richiesta di",
        "confidence": "affidabilità",
        "computed_from": "Calcolato da:",
        "supporting": "I numeri sotto",
        "at_omi_max": "Al massimo della fascia OMI",
        "at_omi_min": "Al minimo della fascia OMI",
        "at_comp_median": "Alla mediana dei comparabili",
        "comparables": "comparabili",
        "value_range": "Intervallo di valore",
        "decay_intro": "Gli immobili comparabili usciti dal mercato avevano "
                       "ridotto il prezzo del",
        "decay_tail": "rispetto alla prima richiesta",
        "properties": "immobili",
        "not_absolute": "Il prezzo Borgo Vero non tiene conto dei giorni in "
                        "vendita: quello è un dato separato, che riguarda la "
                        "pressione sul venditore, non il valore dell'immobile.",
        "not_advice": "Cifra calcolata da fascia OMI e comparabili in zona, "
                      "senza mai guardare il prezzo richiesto. Non è una "
                      "stima né una perizia né una raccomandazione: è "
                      "aritmetica su dati pubblici, con la formula indicata "
                      "sopra. Da verificare sempre.",
        "lookup": "Incolla il link di un annuncio",
        "lookup_btn": "Cerca",
        "lookup_help": "Immobiliare, Idealista o il sito di un'agenzia. "
                       "Ti mostriamo ogni altro annuncio dello stesso immobile.",
        "manual_title": "Oppure inserisci i dati di un immobile",
        "manual_help": "Funziona per qualsiasi immobile della Valtiberina, "
                       "anche se non è ancora nel nostro indice. "
                       "Il calcolo avviene nel tuo browser: non inviamo nulla.",
        "f_comune": "Comune", "f_zona": "Zona", "f_typ": "Tipologia",
        "f_mq": "Superficie m²", "f_price": "Prezzo richiesto €",
        "z_centro": "Centro storico", "z_peri": "Periferia",
        "z_camp": "Campagna",
        "calc_btn": "Calcola",
        "c_high": "alta", "c_med": "media", "c_low": "bassa",
        "need_mq": "Inserisci almeno la superficie in m².",
        "no_data": "Dati insufficienti per questa combinazione. "
                   "Prova un'altra zona o tipologia.",
        "not_found": "Non trovato nel nostro indice — copre la Valtiberina "
                     "(8 comuni) e si aggiorna ogni settimana. "
                     "Inserisci i dati qui sotto per calcolarlo comunque.",
    },
    "en": {
        "tagline": "Valtiberina property prices, checked.",
        "ask": "Asking price",
        "band": "OMI band",
        "dom": "Days on market",
        "listed_by": "Listed by",
        "comps": "Comparable properties",
        "days": "days",
        "floor_area": "floor area",
        "commercial": "commercial surface",
        "above": "above the band ceiling",
        "below": "below the band floor",
        "method": "How these numbers are calculated",
        "spread": "Same property, two prices.",
        "spread_agency": "Same property, different agencies, different prices.",
        "cheapest": "Lowest price",
        "self_conflict": "publishes different details on different portals",
        "disagree_on": "The listings disagree on",
        "each_linked": "Every value links to its source.",
        "numbers_say": "What the numbers say",
        # See the IT note above. "Assessment" carries the same implication
        # in English that "valutazione" does in Italian.
        "declaration": "Borgo Vero is an independent, non-profit index of "
                       "property prices in the Valtiberina. "
                       "It is not an appraisal.",
        "about": "About",
        "corrections": "Report an error",
        "sources_line": "OMI bands: Agenzia delle Entrate. Listings: public "
                        "portals, linked to source. No payment from agencies, "
                        "sellers or portals.",
        "bv_price": "Borgo Vero price",
        "vs_ask": "against the asking price of",
        "confidence": "confidence",
        "computed_from": "Computed from:",
        "supporting": "The figures beneath it",
        "at_omi_max": "At the OMI band ceiling",
        "at_omi_min": "At the OMI band floor",
        "at_comp_median": "At the comparable median",
        "comparables": "comparables",
        "value_range": "Value range",
        "decay_intro": "Comparable properties that left the market had cut "
                       "their price by",
        "decay_tail": "from first asking price",
        "properties": "properties",
        "not_absolute": "The Borgo Vero price ignores days on market — that "
                        "is a separate figure, about pressure on the seller "
                        "rather than the value of the property.",
        "not_advice": "Computed from the OMI band and local comparables, "
                      "never looking at the asking price. Not a valuation, "
                      "not an appraisal, not a recommendation: arithmetic on "
                      "public data, by the formula shown above. Always verify.",
        "lookup": "Paste a listing link",
        "lookup_btn": "Look up",
        "lookup_help": "Immobiliare, Idealista or an agency site. "
                       "We show every other listing of the same property.",
        "manual_title": "Or enter a property's details",
        "manual_help": "Works for any Valtiberina property, even one not yet "
                       "in our index. The calculation runs in your browser — "
                       "nothing is sent anywhere.",
        "f_comune": "Comune", "f_zona": "Area", "f_typ": "Type",
        "f_mq": "Surface m²", "f_price": "Asking price €",
        "z_centro": "Historic centre", "z_peri": "Outskirts",
        "z_camp": "Countryside",
        "calc_btn": "Calculate",
        "c_high": "high", "c_med": "medium", "c_low": "low",
        "need_mq": "Enter at least the surface in m².",
        "no_data": "Not enough data for this combination. "
                   "Try another area or property type.",
        "not_found": "Not in our index — it covers the Valtiberina "
                     "(8 comuni) and updates weekly. "
                     "Enter the details below to calculate it anyway.",
    },
}


def e(s):
    return html.escape(str(s if s is not None else ""))


def eur(n):
    return f"€{n:,.0f}".replace(",", ".") if n is not None else "—"


def pct_span(v, t):
    if v is None:
        return "—"
    cls = "over" if v > 0 else "under"
    word = t["above"] if v > 0 else t["below"]
    return f'<span class="{cls}">{v:+.0f}%</span> <span class="lbl">{word}</span>'


def shell(title, body, lang, alt_href, desc="", schema=None):
    t = T[lang]
    ld = (f'<script type="application/ld+json">{json.dumps(schema)}</script>'
          if schema else "")
    other = "en" if lang == "it" else "it"
    data_label = "Dati aperti" if lang == "it" else "Open data"
    data_href = "/dati/" if lang == "it" else "/en/dati.html"
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="alternate" hreflang="{other}" href="{e(alt_href)}">
<style>{CSS}</style>
{ld}
</head>
<body>
<div class="wrap">
<header class="site">
  <a class="brand" href="/{lang}/">Borgo <span>Vero</span></a>
  <div class="lang noprint">
    <a href="{e(alt_href)}">{other.upper()}</a>
  </div>
</header>
{body}
<footer>
  <p><b>{e(t['declaration'])}</b></p>
  <p><a href="/{lang}/chi-siamo.html">{e(t['about'])}</a> ·
     <a href="/{lang}/metodologia.html">{e(t['method'])}</a> ·
     <a href="/{lang}/comuni/">Comuni</a> ·
     <a href="{data_href}">{data_label}</a> ·
     <a href="/{lang}/correzioni/">{e(t['corrections'])}</a></p>
  <p>{e(t['sources_line'])}</p>
</footer>
</div>
</body>
</html>"""


# --- Source comparison -------------------------------------------------

# Fields worth contrasting, in the order a buyer cares about them.
# `fmt` renders the value; `key` normalises it for the disagreement check
# so that "1°" and "1" don't read as a contradiction when they aren't.
COMPARE_FIELDS = [
    ("price",         "Prezzo",                  lambda v: eur(v),          lambda v: v),
    ("mq",            "Superficie calpestabile", lambda v: f"{v} m²" if v else "—", lambda v: v),
    ("mq_commercial", "Superficie commerciale",  lambda v: f"{v} m²" if v else "—", lambda v: v),
    ("vani",          "Vani",                    lambda v: f"{v:g}" if v else "—",  lambda v: v),
    ("bathrooms",     "Bagni",                   lambda v: str(v) if v else "—",    lambda v: v),
    ("floor",         "Piano",                   lambda v: str(v) if v else "—",
     lambda v: str(v).lower().strip("°º ") if v else None),
    ("condition",     "Stato",                   lambda v: str(v) if v else "—",
     lambda v: str(v).lower()[:6] if v else None),
    ("typology_raw",  "Tipologia",               lambda v: str(v) if v else "—",
     lambda v: str(v).lower() if v else None),
]


def norm_agency(name):
    """Collapse the same agency written slightly differently.

    Portals let agencies type their own display name, so the same firm
    appears as 'House Immobiliare', 'HOUSE IMMOBILIARE' and
    'House Immobiliare Sansepolcro'. Grouping on the raw string would
    invent extra agencies and manufacture disagreements that aren't real.
    """
    if not name:
        return None
    s = str(name).lower()
    for junk in ("immobiliare", "agenzia", "studio", "s.r.l.", "srl",
                 "s.a.s.", "sas", "snc", "& c.", "gruppo", "real estate",
                 "sansepolcro", "anghiari", "arezzo"):
        s = s.replace(junk, " ")
    return " ".join(s.split()) or str(name).lower().strip()


def group_by_agency(sources):
    """One column per AGENCY, not per portal.

    The portal is a distribution channel; the agency is the actor. A buyer
    negotiates with an agency, and it is the agency that sets the price.
    So the question that matters is not 'do Immobiliare and Idealista
    disagree' but 'do Leonardi and Cortesi disagree about the same house'
    — because if they do, the buyer can walk into the cheaper one.

    Two distinct findings fall out of this grouping:

      cross-agency  two firms selling one property at different prices
      intra-agency  ONE firm publishing different prices for the same
                    property on different portals
    """
    groups = {}
    for s in sources:
        key = norm_agency(s.get("agency_name")) or f'__{s.get("source")}'
        g = groups.setdefault(key, {
            "name": s.get("agency_name") or s.get("source"),
            "portals": [], "sources": [], "self_conflict": [],
        })
        g["portals"].append(s.get("source"))
        g["sources"].append(s)

    for g in groups.values():
        # Does this agency contradict itself across portals?
        for field, label, _fmt, norm in COMPARE_FIELDS:
            keys = {norm(x.get(field)) for x in g["sources"]
                    if x.get(field) not in (None, "")}
            if len(keys) > 1:
                g["self_conflict"].append(label)
        # Representative record: the most complete one this agency filed.
        g["rec"] = max(g["sources"], key=lambda r: sum(
            1 for k, _l, _f, _n in COMPARE_FIELDS if r.get(k)))
    return list(groups.values())


def thumb(url, alt, source, w=110):
    """One hotlinked thumbnail. Never a copy, never the full set.

    WHY ONE, AND WHY HOTLINKED:

    The photo is evidence, not decoration. When two agencies list "the same
    property", a shared photo is how a reader verifies the match without
    taking our word for it — which is the whole posture of the site.

    Hotlinking means no reproduction is made on our server: we point at the
    portal's own CDN, exactly as a link does. That keeps this far away from
    republication, costs nothing to host, and if a portal blocks hotlinking
    the page degrades to alt text instead of breaking.

    One image, thumbnail size, credited. Mirroring a 45-photo set would be
    republishing their inventory, which is the line in spec section 9.
    """
    if not url:
        return ""
    return (f'<figure style="margin:0"><img src="{e(url)}" alt="{e(alt)}" '
            f'width="{w}" loading="lazy" referrerpolicy="no-referrer" '
            f'style="width:{w}px;height:{int(w*0.72)}px;object-fit:cover;'
            f'border-radius:4px;border:1px solid var(--line);display:block">'
            f'<figcaption class="src" style="margin-top:3px">'
            f'{e(source)}</figcaption></figure>')


def build_columns(sources):
    """One column per distinct CLAIM, not per agency.

    An agency whose listings agree gets one merged column — two identical
    columns would be noise.

    An agency whose listings CONTRADICT each other gets one column per
    listing. Collapsing those into a single cell reading
    "EUR363.000 / EUR402.930" makes a contradiction look like ambiguity. Two
    columns headed by the same firm's name, one per portal, is structural:
    the reader sees two listings from one agency that cannot both be true.

    So the column count reflects how many different stories are being told
    about this property, which is the thing worth counting.
    """
    columns = []
    for g in group_by_agency(sources):
        if g["self_conflict"] and len(g["sources"]) > 1:
            for s in g["sources"]:
                columns.append({
                    "name": g["name"], "portals": [s.get("source")],
                    "sources": [s], "rec": s,
                    "split": True, "conflict_fields": g["self_conflict"],
                })
        else:
            g["split"] = False
            g["conflict_fields"] = []
            columns.append(g)
    return columns


def compare_agencies(sources, t):
    """Every distinct claim about the same property, side by side."""
    if not sources:
        return '<p class="lbl">—</p>'

    groups = group_by_agency(sources)
    columns = build_columns(sources)

    if len(groups) < 2 and len(sources) < 2:
        s = sources[0]
        return (f'<table class="rows"><tr><td>{e(s["agency_name"] or s["source"])}'
                f'<div class="src">{e(s["source"])}</div></td>'
                f'<td class="r">{eur(s["price"])}</td>'
                f'<td class="r noprint"><a href="{e(s["url"])}" rel="nofollow '
                f'noopener" target="_blank">→</a></td></tr></table>')

    head = ""
    for col in columns:
        portals = ", ".join(sorted(set(p for p in col["portals"] if p)))
        warn = (' <span class="over" title="questa agenzia pubblica dati '
                'diversi su portali diversi">≠</span>') if col["split"] else ""
        # Each column's own lead photo. Matching images across columns are
        # the reader's own proof that this really is one property.
        pic = next((s.get("photo_url") for s in col["sources"]
                    if s.get("photo_url")), None)
        head += (f'<th style="text-align:right;padding:7px 0 7px 14px;'
                 f'font-size:13px;vertical-align:top">'
                 f'<div style="display:flex;justify-content:flex-end">'
                 f'{thumb(pic, col["name"], portals, 96)}</div>'
                 f'<div style="margin-top:4px">{e(col["name"])}{warn}</div>'
                 f'<div class="src" style="font-weight:400">{e(portals)}</div></th>')

    rows, disagreements = "", []
    for field, label, fmt, norm in COMPARE_FIELDS:
        vals = [c["rec"].get(field) for c in columns]
        if all(v in (None, "") for v in vals):
            continue
        keys = {norm(v) for v in vals if v not in (None, "")}
        clash = len(keys) > 1
        if clash:
            disagreements.append(label)

        cells = ""
        for col in columns:
            style = "padding-left:14px"
            if clash:
                style += ";color:var(--hi);font-weight:700"
            cells += (f'<td class="r" style="{style}">'
                      f'{e(fmt(col["rec"].get(field)))}</td>')
        mark = ' <span class="over">≠</span>' if clash else ""
        rows += f'<tr><td class="lbl">{e(label)}{mark}</td>{cells}</tr>'

    links = ""
    for col in columns:
        ls = " ".join(
            f'<a href="{e(x["url"])}" rel="nofollow noopener" target="_blank">'
            f'{e((x.get("source") or "")[:3])}→</a>'
            for x in col["sources"] if x.get("url"))
        links += f'<td class="r noprint" style="padding-left:14px">{ls}</td>'
    rows += f'<tr><td class="lbl">Fonte</td>{links}</tr>'

    # --- The two findings, stated as record, never as accusation -------
    flag = ""
    prices = [c["rec"]["price"] for c in columns if c["rec"].get("price")]
    if len(set(prices)) > 1:
        lo, hi = min(prices), max(prices)
        cheapest = min(columns, key=lambda c: c["rec"].get("price") or 1e12)
        flag += (f'<div class="flag"><b>{e(t["spread_agency"])}</b> '
                 f'{eur(lo)} – {eur(hi)}, una differenza di {eur(hi-lo)} '
                 f'({(hi-lo)/lo*100:.1f}%). '
                 f'{e(t["cheapest"])}: <b>{e(cheapest["name"])}</b>.</div>')

    for g in groups:
        if not g["self_conflict"]:
            continue
        ps = {x.get("price") for x in g["sources"] if x.get("price")}
        detail = (f' {eur(min(ps))} / {eur(max(ps))}.' if len(ps) > 1 else "")
        flag += (f'<div class="flag"><b>{e(g["name"])}</b> '
                 f'{e(t["self_conflict"])}: '
                 f'<b>{e(", ".join(g["self_conflict"]))}</b>.{detail}</div>')

    if disagreements:
        flag += (f'<div class="note">{e(t["disagree_on"])}: '
                 f'<b>{e(", ".join(disagreements))}</b>. '
                 f'{e(t["each_linked"])}</div>')

    return (f'<div style="overflow-x:auto"><table class="rows">'
            f'<tr><td></td>{head}</tr>{rows}</table></div>{flag}')


# --- What the numbers say ----------------------------------------------


def borgo_vero_price(L, comps):
    """The single number. Returns (price, confidence, basis) or (None,..).

    WHY A SINGLE NUMBER, and why it is safe to publish one:

    A range does not survive a negotiation — "EUR161,000 to EUR258,000" is a
    shrug, and a buyer facing an agent needs one figure to say out loud.
    One named number is also the thing that spreads: people repeat it,
    search it, and argue about it, and being the number the whole valley
    argues about IS market saturation.

    Critically, it is built from OMI and comparables — it never references
    the asking price. So padding the ask does not move it; the gap simply
    widens and looks worse. A fixed rule off the ask ("minus 30%") would
    get gamed within a year. This cannot be.

    DOM is deliberately NOT an input. Days on market does not change what a
    property is worth, it changes what the seller will accept. Those are two
    different arguments and blending them produces a number that is wrong
    about both. DOM sits beside the price as separate leverage.

    Rounded to EUR1,000: precision it does not have would be a lie.
    """
    mq, lo, hi = L.get("mq"), L.get("band_lo"), L.get("band_hi")
    if not mq:
        return None, None, None

    cm2 = sorted(c["price"] / c["mq"] for c in comps
                 if c.get("price") and c.get("mq"))
    n = len(cm2)
    comp_med = cm2[n // 2] if n else None
    omi_mid = (lo + hi) / 2 if lo and hi else None

    # Weight toward comparables when there are enough of them to trust,
    # toward OMI when there are not.
    if n >= 5 and omi_mid:
        w, conf = 0.65, "alta"
    elif n >= 3 and omi_mid:
        w, conf = 0.50, "media"
    elif omi_mid and n:
        w, conf = 0.25, "bassa"
    elif omi_mid:
        w, conf = 0.0, "bassa"
    elif n >= 4:
        w, conf = 1.0, "bassa"
    else:
        # Not enough to say anything. Publishing no number beats
        # publishing a number that can be dismantled.
        return None, None, None

    m2 = (w * (comp_med or 0)) + ((1 - w) * (omi_mid or 0))
    if not m2:
        return None, None, None

    basis = []
    if w:
        basis.append(f"mediana di {n} comparabili ({eur(comp_med)}/m²)")
    if w < 1:
        basis.append(f"punto medio fascia OMI ({eur(omi_mid)}/m²)")
    basis_txt = " e ".join(basis)
    if 0 < w < 1:
        basis_txt += f", pesati {int(w*100)}/{int((1-w)*100)}"
    basis_txt += f", × {mq} m²"

    return int(round(m2 * mq / 1000) * 1000), conf, basis_txt


def valuation_block(L, comps, t):
    """The Borgo Vero price, with the supporting arithmetic beneath it."""
    price, mq = L.get("price"), L.get("mq")
    lo, hi = L.get("band_lo"), L.get("band_hi")
    if not (price and mq):
        return ""

    rows, marks = [], []

    def add(label, value, note=""):
        if not value:
            return
        delta = (value - price) / price * 100
        cls = "under" if delta < 0 else "over"
        rows.append(
            f'<tr><td class="lbl">{e(label)}'
            + (f'<div class="src">{e(note)}</div>' if note else "")
            + f'</td><td class="r">{eur(value)}</td>'
              f'<td class="r"><span class="{cls}">{delta:+.0f}%</span></td></tr>')
        marks.append(value)

    if hi:
        add(t["at_omi_max"], hi * mq,
            f"{eur(hi)}/m² × {mq} m²")
    if lo:
        add(t["at_omi_min"], lo * mq, f"{eur(lo)}/m² × {mq} m²")

    cm2 = [c["price"] / c["mq"] for c in comps if c.get("price") and c.get("mq")]
    if cm2:
        med = sorted(cm2)[len(cm2) // 2]
        add(t["at_comp_median"], med * mq,
            f"{eur(med)}/m² · {len(cm2)} {t['comparables']}")

    bv, conf, basis = borgo_vero_price(L, comps)
    if not bv and not rows:
        return ""

    hero = ""
    if bv:
        delta = (bv - price) / price * 100
        cls = "under" if delta < 0 else "over"
        hero = f"""
  <div class="big" style="font-size:40px">{eur(bv)}</div>
  <div style="margin:6px 0 14px">
    <span class="{cls}" style="font-size:17px">{delta:+.0f}%</span>
    <span class="lbl">{e(t['vs_ask'])} {eur(price)}</span>
    <span class="lbl"> · {e(t['confidence'])}: {e(conf)}</span>
  </div>
  <div class="note" style="margin-bottom:16px">{e(t['computed_from'])}
    {e(basis)}.</div>"""

    decay = ""
    if L.get("decay_pct") and L.get("decay_n"):
        decay = (f'<div class="flag">{e(t["decay_intro"])} '
                 f'<b>{L["decay_pct"]:.0f}%</b> {e(t["decay_tail"])} '
                 f'({L["decay_n"]} {e(t["properties"])}).</div>')

    detail = ""
    if rows:
        detail = (f'<h2 style="margin-top:22px">{e(t["supporting"])}</h2>'
                  f'<table class="rows">{"".join(rows)}</table>')

    return f"""
<div class="block" style="border:2px solid var(--ink)">
  <h2>{e(t['bv_price'])}</h2>
  {hero}
  {detail}
  {decay}
  <div class="note">{e(t['not_absolute'])}</div>
  <div class="note">{e(t['not_advice'])}</div>
</div>"""


# --- Listing page ------------------------------------------------------


def listing_page(L, sources, comps, lang):
    t = T[lang]
    net, com = L["mq"], L.get("mq_commercial")
    price = L["price"]
    m2_net = price / net if net else None
    m2_com = price / com if com else None

    surf_rows = f"""
      <tr><td class="lbl">{eur(m2_net)}/m² · {e(t['floor_area'])} ({net} m²)</td>
          <td class="r">{pct_span(L.get('pct_net'), t)}</td></tr>"""
    if com:
        surf_rows += f"""
      <tr><td class="lbl">{eur(m2_com)}/m² · {e(t['commercial'])} ({com} m²)</td>
          <td class="r">{pct_span(L.get('pct_com'), t)}</td></tr>"""

    comparison = compare_agencies(sources, t)
    n_agencies = len(group_by_agency(sources))

    comp_rows = ""
    for c in comps:
        cm2 = c["price"] / c["mq"] if c["mq"] else None
        href = f'/{lang}/immobile/{c["cluster_id"]}.html'
        comp_rows += (f'<tr><td><a href="{e(href)}">{e(c["address_raw"])}</a>'
                      f'<div class="src">{c["mq"]} m² · {e(c["typology"])}</div></td>'
                      f'<td class="r">{eur(c["price"])}<div class="src">'
                      f'{eur(cm2)}/m²</div></td>'
                      f'<td class="r">{c["dom_est"] or "—"}<div class="src">'
                      f'{e(t["days"])}</div></td></tr>')

    dom = L.get("dom_est")
    conf = (L.get("dom_method") or "").split(":")[-1]

    lead = thumb(L.get("photo_url"), L.get("address_raw") or "",
                 (L.get("source") or ""), 150)

    body = f"""
<div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:22px">
  {lead}
  <div>
    <h1>{e(L['address_raw'])}, {e(L['comune']).title()}</h1>
    <div class="sub" style="margin-bottom:0">{e(L['typology'])} · {net} m²
      · {e(L.get('vani') or '—')} vani · {e(L.get('floor') or '—')}</div>
  </div>
</div>

<div class="block">
  <h2>{e(t['ask'])}</h2>
  <div class="big">{eur(price)}</div>
  <table class="rows" style="margin-top:14px">{surf_rows}</table>
  <div class="note">{e(t['band'])}: {eur(L.get('band_lo'))}–{eur(L.get('band_hi'))}/m²
    — {e(L['comune']).title()}, {e(L.get('zona_guess'))},
    OMI {e(L.get('omi_semester') or '')}.</div>
</div>

{valuation_block(L, comps, t)}

<div class="block">
  <h2>{e(t['dom'])}</h2>
  <div class="big">{dom if dom else '—'} <span
     style="font-size:16px;font-weight:400">{e(t['days'])}</span></div>
  <div class="note">Stimato da: {e(L.get('dom_method') or '—')}
     · affidabilità {e(conf)}</div>
</div>

<div class="block">
  <h2>{e(t['listed_by'])} — {n_agencies} · {len(sources)} annunci</h2>
  {comparison}
</div>

<div class="block">
  <h2>{e(t['comps'])}</h2>
  <table class="rows">{comp_rows or '<tr><td class="lbl">—</td></tr>'}</table>
</div>
"""
    schema = {
        "@context": "https://schema.org",
        "@type": "RealEstateListing",
        "name": f"{L['address_raw']}, {str(L['comune']).title()}",
        "url": L.get("canonical", ""),
        "datePosted": L.get("listed_date_est"),
        "offers": {"@type": "Offer", "price": price, "priceCurrency": "EUR"},
    }
    alt = f"/{'en' if lang=='it' else 'it'}/immobile/{L['cluster_id']}.html"
    title = (f"{L['address_raw']}, {str(L['comune']).title()} — "
             f"{eur(price)} — Borgo Vero")
    desc = (f"{eur(price)}, {net} m², {dom or '?'} giorni in vendita. "
            f"Confronto con la fascia OMI e immobili comparabili.")
    return shell(title, body, lang, alt, desc, schema)


# --- Comune page -------------------------------------------------------


def comune_page(comune, rows, stats, lang):
    t = T[lang]
    tiles = ""
    for r in rows[:60]:
        m2 = r["price"] / r["mq"] if r["mq"] else None
        badge = ""
        if r.get("pct_net") is not None and r["pct_net"] > 0:
            badge = f'<span class="over">{r["pct_net"]:+.0f}%</span> '
        tiles += (f'<a class="tile" href="/{lang}/immobile/{r["cluster_id"]}.html">'
                  f'<b>{eur(r["price"])}</b>'
                  f'<small>{e(r["address_raw"])}<br>'
                  f'{r["mq"]} m² · {eur(m2)}/m² · {badge}'
                  f'{r["dom_est"] or "?"} {e(t["days"])}</small></a>')

    body = f"""
<h1>{e(comune).title()}</h1>
<div class="sub">{stats['n']} immobili in vendita ·
  mediana {eur(stats['median_price'])} ·
  {stats['median_dom']} {e(t['days'])} in mediana</div>

<div class="block">
  <h2>Fascia OMI</h2>
  <table class="rows">
    <tr><td class="lbl">Centro storico</td>
        <td class="r">{eur(stats['band_lo'])}–{eur(stats['band_hi'])}/m²</td></tr>
    <tr><td class="lbl">Richiesta mediana ({e(t['floor_area'])})</td>
        <td class="r">{eur(stats['median_m2'])}/m²</td></tr>
  </table>
  <div class="note">Le richieste sono prezzi domandati, non prezzi di vendita.
    Le fasce OMI derivano da compravendite registrate.</div>
</div>

<div class="grid">{tiles}</div>
"""
    alt = f"/{'en' if lang=='it' else 'it'}/{comune}.html"
    return shell(f"Prezzi case {str(comune).title()} — Borgo Vero", body, lang,
                 alt, f"Prezzi, fasce OMI e giorni in vendita a "
                      f"{str(comune).title()}.")


# --- Lookup front door -------------------------------------------------


def index_page(comuni_stats, index_json, lang, bands_json="{}", comps_json="{}",
               comuni=(), typologies=()):
    t = T[lang]
    tiles = "".join(
        f'<a class="tile" href="/{lang}/{c}.html"><b>{str(c).title()}</b>'
        f'<small>{s["n"]} immobili · {eur(s["median_price"])}</small></a>'
        for c, s in comuni_stats.items())

    opt_c = "".join(f'<option value="{e(c)}">{e(str(c).title())}</option>'
                    for c in comuni)
    opt_t = "".join(f'<option value="{e(k)}">{e(v)}</option>'
                    for k, v in typologies)

    body = f"""
<div class="hero">
  <h1>{e(t['lookup'])}</h1>
  <p class="sub" style="margin-bottom:14px">{e(t['lookup_help'])}</p>
  <form onsubmit="return lookup(event)">
    <input type="text" id="q" placeholder="https://www.immobiliare.it/annunci/…"
           autocomplete="off">
    <div style="margin-top:12px"><button type="submit">{e(t['lookup_btn'])}</button></div>
  </form>
  <div id="out" style="margin-top:14px"></div>
</div>

<div class="block">
  <h2>{e(t['manual_title'])}</h2>
  <p class="note" style="margin:0 0 14px">{e(t['manual_help'])}</p>
  <form onsubmit="return calc(event)">
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px">
      <label>{e(t['f_comune'])}<br><select id="f_comune">{opt_c}</select></label>
      <label>{e(t['f_zona'])}<br><select id="f_zona">
        <option value="centro_storico">{e(t['z_centro'])}</option>
        <option value="periferia">{e(t['z_peri'])}</option>
        <option value="campagna">{e(t['z_camp'])}</option>
      </select></label>
      <label>{e(t['f_typ'])}<br><select id="f_typ">{opt_t}</select></label>
      <label>{e(t['f_mq'])}<br><input type="number" id="f_mq" min="10" max="2000"
             placeholder="125"></label>
      <label>{e(t['f_price'])}<br><input type="number" id="f_price" min="1000"
             step="1000" placeholder="180000"></label>
    </div>
    <div style="margin-top:14px"><button type="submit">{e(t['calc_btn'])}</button></div>
  </form>
  <div id="calcout" style="margin-top:18px"></div>
</div>

<div class="grid">{tiles}</div>

<script>
// Everything runs in the browser. The whole index, the OMI bands and the
// comparable medians together are a few tens of KB, so there is no backend,
// no API and no hosting cost — and it keeps working offline.
const IDX   = {index_json};
const BANDS = {bands_json};
const COMPS = {comps_json};

function eur(n){{ return '€' + Math.round(n).toLocaleString('it-IT'); }}

function lookup(ev){{
  ev.preventDefault();
  const raw = document.getElementById('q').value.trim();
  const out = document.getElementById('out');
  const m = raw.match(/(\\d{{6,}})/);
  let hit = null;
  if(m) hit = IDX.find(r => r.ids.includes(m[1]));
  if(!hit && raw) hit = IDX.find(r => r.urls.some(u => u && raw.includes(u)));
  if(hit){{ location.href = '/{lang}/immobile/' + hit.cid + '.html'; return false; }}
  out.innerHTML = '<div class="flag">{e(t["not_found"])}</div>';
  document.getElementById('f_price').focus();
  return false;
}}

// Mirrors borgo_vero_price() + comps_for() in the generator exactly:
// same +/-25% surface filter, same weighting, same rounding. If these
// two ever drift, the same property gets two different Borgo Vero
// prices depending which page you read — so they must not drift.
function borgoVero(comune, zona, typ, mq){{
  const band = (BANDS[comune]||{{}})[zona] || (BANDS[comune]||{{}})['periferia'];
  const pool = COMPS[comune+'|'+typ] || [];
  const near = pool.filter(p => Math.abs(p[0]-mq)/mq <= 0.25)
                   .sort((a,b) => Math.abs(a[0]-mq) - Math.abs(b[0]-mq))
                   .slice(0, 5)                       // same cap as comps_for()
                   .map(p => p[1]).sort((a,b) => a-b);
  const omiMid = band ? (band[0]+band[1])/2 : null;
  const n = near.length;
  const compMed = n ? near[Math.floor(n/2)] : null;
  let w, conf;
  if(n >= 5 && omiMid){{ w = 0.65; conf = '{e(t["c_high"])}'; }}
  else if(n >= 3 && omiMid){{ w = 0.50; conf = '{e(t["c_med"])}'; }}
  else if(omiMid && n){{ w = 0.25; conf = '{e(t["c_low"])}'; }}
  else if(omiMid){{ w = 0.0;  conf = '{e(t["c_low"])}'; }}
  else if(n >= 4){{ w = 1.0;  conf = '{e(t["c_low"])}'; }}
  else return null;
  const m2 = w*(compMed||0) + (1-w)*(omiMid||0);
  if(!m2) return null;
  return {{ price: Math.round(m2*mq/1000)*1000, conf: conf, band: band,
           compMed: compMed, n: n, omiMid: omiMid, w: w }};
}}

function calc(ev){{
  ev.preventDefault();
  const comune = document.getElementById('f_comune').value;
  const zona   = document.getElementById('f_zona').value;
  const typ    = document.getElementById('f_typ').value;
  const mq     = +document.getElementById('f_mq').value;
  const ask    = +document.getElementById('f_price').value;
  const out    = document.getElementById('calcout');
  if(!mq){{ out.innerHTML = '<div class="flag">{e(t["need_mq"])}</div>'; return false; }}

  const r = borgoVero(comune, zona, typ, mq);
  if(!r){{ out.innerHTML = '<div class="flag">{e(t["no_data"])}</div>'; return false; }}

  let html = '<div class="block" style="border:2px solid var(--ink)">'
    + '<h2>{e(t["bv_price"])}</h2>'
    + '<div class="big" style="font-size:40px">' + eur(r.price) + '</div>';

  if(ask){{
    const d = (r.price-ask)/ask*100;
    html += '<div style="margin:6px 0 12px"><span class="'
      + (d<0?'under':'over') + '" style="font-size:17px">'
      + (d>0?'+':'') + d.toFixed(0) + '%</span> <span class="lbl">'
      + '{e(t["vs_ask"])} ' + eur(ask) + '</span></div>';
  }}
  html += '<div class="note">{e(t["confidence"])}: ' + r.conf + '. ';
  const parts = [];
  if(r.w > 0 && r.compMed) parts.push(r.n + ' {e(t["comparables"])} (' + eur(r.compMed) + '/m²)');
  if(r.w < 1 && r.omiMid)  parts.push('OMI ' + eur(r.omiMid) + '/m²');
  html += '{e(t["computed_from"])} ' + parts.join(' + ') + ', × ' + mq + ' m².</div>';

  if(r.band){{
    html += '<table class="rows" style="margin-top:12px">'
      + '<tr><td class="lbl">{e(t["at_omi_max"])}</td><td class="r">'
      + eur(r.band[1]*mq) + '</td></tr>'
      + '<tr><td class="lbl">{e(t["at_omi_min"])}</td><td class="r">'
      + eur(r.band[0]*mq) + '</td></tr></table>';
  }}
  html += '<div class="note">{e(t["not_advice"])}</div></div>';
  out.innerHTML = html;
  return false;
}}
</script>
"""
    alt = f"/{'en' if lang=='it' else 'it'}/"
    return shell("Borgo Vero — " + t["tagline"], body, lang, alt, t["tagline"])


# --- Chi siamo / About -------------------------------------------------

ABOUT = {
    "it": """
<h1>Chi siamo</h1>

<div class="block">
  <p style="font-size:18px;margin-top:0"><b>Borgo Vero è un indice
  indipendente e senza scopo di lucro dei prezzi immobiliari in
  Valtiberina.</b></p>
  <p>L'obiettivo è incoraggiare trasparenza, coerenza e accuratezza nei
  prezzi, nelle descrizioni e nella comunicazione immobiliare della zona.</p>
</div>

<div class="block">
  <h2>Indipendenza</h2>
  <p>Non riceviamo compensi da agenzie, venditori, acquirenti o portali.
  Non vendiamo contatti né pubblicità. Non esiste alcun modo di pagare per
  comparire, per non comparire, o per cambiare una cifra.</p>
  <p>Nessun immobile è ordinato, evidenziato o nascosto in base a chi lo
  pubblica. Non c'è nulla da comprare, quindi non c'è nulla da corrompere.</p>
</div>

<div class="block">
  <h2>Cosa pubblichiamo</h2>
  <p>Numeri e le loro fonti: il prezzo richiesto, la fascia OMI
  dell'Agenzia delle Entrate, gli immobili comparabili in zona, da quanto
  tempo un annuncio è pubblicato, e le differenze fra annunci dello stesso
  immobile.</p>
  <p>Ogni valore è collegato alla fonte da cui proviene. Non pubblichiamo
  giudizi sulle persone o sulle agenzie: pubblichiamo ciò che è stato
  scritto, e chi legge trae le proprie conclusioni.</p>
</div>

<div class="block" id="correzioni">
  <h2>Correzioni</h2>
  <p>Se un dato è sbagliato, vogliamo saperlo e lo correggiamo.</p>
  <ul>
    <li>Chiunque può segnalare un errore: agenzie, proprietari, acquirenti.</li>
    <li>Verifichiamo e correggiamo entro <b>7 giorni</b>.</li>
    <li>Ogni correzione viene registrata con la data e cosa è cambiato.</li>
    <li>Non rimuoviamo dati corretti su richiesta — ma correggiamo
        immediatamente qualsiasi dato inesatto.</li>
    <li>Se un immobile non è più in vendita, segnalacelo e lo marchiamo
        come tale.</li>
  </ul>
  <p>Scrivi a: <b>correzioni@borgovero.it</b></p>
</div>

<div class="block">
  <h2>Limiti</h2>
  <p>I prezzi richiesti non sono prezzi di vendita. Le fasce OMI derivano
  da compravendite registrate e si aggiornano ogni sei mesi. I giorni in
  vendita sono stimati, e ogni pagina indica con quale metodo e con quale
  affidabilità.</p>
  <p>Il Prezzo Borgo Vero è aritmetica su dati pubblici, non una perizia.
  Per una valutazione formale serve un tecnico abilitato.</p>
</div>
""",
    "en": """
<h1>About</h1>

<div class="block">
  <p style="font-size:18px;margin-top:0"><b>Borgo Vero is an independent,
  non-profit index of property prices in the Valtiberina.</b></p>
  <p>The goal is to encourage transparency, consistency and accuracy in
  property pricing, descriptions and marketing in the area.</p>
</div>

<div class="block">
  <h2>Independence</h2>
  <p>We take no money from agencies, sellers, buyers or portals. We sell no
  leads and no advertising. There is no way to pay to appear, to not appear,
  or to change a figure.</p>
  <p>No property is ranked, highlighted or hidden based on who lists it.
  There is nothing to buy, so there is nothing to corrupt.</p>
</div>

<div class="block">
  <h2>What we publish</h2>
  <p>Numbers and their sources: the asking price, the Agenzia delle Entrate
  OMI band, local comparable properties, how long a listing has been up, and
  the differences between listings of the same property.</p>
  <p>Every value links to where it came from. We do not publish judgements
  about people or agencies — we publish what was written, and readers draw
  their own conclusions.</p>
</div>

<div class="block" id="correzioni">
  <h2>Corrections</h2>
  <p>If something is wrong, we want to know, and we fix it.</p>
  <ul>
    <li>Anyone can report an error: agencies, owners, buyers.</li>
    <li>We verify and correct within <b>7 days</b>.</li>
    <li>Every correction is logged with the date and what changed.</li>
    <li>We do not remove accurate data on request — but we correct
        inaccurate data immediately.</li>
    <li>If a property is no longer for sale, tell us and we mark it so.</li>
  </ul>
  <p>Write to: <b>correzioni@borgovero.it</b></p>
</div>

<div class="block">
  <h2>Limits</h2>
  <p>Asking prices are not sale prices. OMI bands come from registered
  transactions and update twice a year. Days on market are estimated, and
  every page states the method and its confidence.</p>
  <p>The Borgo Vero price is arithmetic on public data, not a formal
  valuation. For that you need a qualified surveyor.</p>
</div>
""",
}


def about_page(lang):
    alt = f"/{'en' if lang=='it' else 'it'}/chi-siamo.html"
    t = T[lang]
    return shell(f"{t['about']} — Borgo Vero", ABOUT[lang], lang, alt,
                 t["declaration"])


# --- Methodology -------------------------------------------------------


def methodology_page(lang):
    body = """
<h1>Come calcoliamo questi numeri</h1>

<div class="block">
  <h2>Due superfici</h2>
  <p>Ogni annuncio italiano riporta due superfici: la
  <b>superficie calpestabile</b> e la <b>superficie commerciale</b>, che
  aggiunge una quota ponderata di balconi, terrazzi, giardini e garage.</p>
  <p>Il prezzo al metro quadro dipende interamente da quale delle due si usa.
  Su un annuncio reale della zona le due cifre erano 115 m² e 183 m² — una
  differenza del 59%, che sposta il prezzo al m² della stessa percentuale.</p>
  <p><b>Mostriamo entrambe.</b> Sceglierne una significherebbe scegliere una
  conclusione.</p>
</div>

<div class="block">
  <h2>Le fasce OMI</h2>
  <p>Sono pubblicate dall'Agenzia delle Entrate e derivano da compravendite
  effettivamente registrate. Confrontiamo i prezzi richiesti con il valore
  dichiarato al fisco per quella zona e tipologia.</p>
  <p>È il dato ufficiale dello Stato. Se risulta basso, quello è un fatto su
  ciò che questo mercato ha scelto di dichiarare.</p>
</div>

<div class="block">
  <h2>Giorni in vendita</h2>
  <p>Nessun portale lo pubblica. Lo ricostruiamo da tre fonti: gli
  identificativi progressivi degli annunci, le prime catture dell'Internet
  Archive, e la nostra osservazione diretta dal lancio.</p>
  <p>Ogni pagina indica il metodo usato e la sua affidabilità.</p>
</div>

<div class="block">
  <h2>Cosa non facciamo</h2>
  <p>Non riceviamo compensi da agenzie, venditori o portali. Non vendiamo
  contatti. Non ordiniamo nulla in base a chi paga, perché nessuno paga.</p>
  <p>Pubblichiamo numeri e le loro fonti. Le conclusioni le trae chi legge.</p>
</div>
"""
    alt = f"/{'en' if lang=='it' else 'it'}/metodologia.html"
    return shell("Metodologia — Borgo Vero", body, lang, alt,
                 "Come Borgo Vero calcola prezzi al m², fasce OMI e "
                 "giorni in vendita.")
