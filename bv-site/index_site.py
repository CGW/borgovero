"""Listing index pages and comune reports — seo-spec.md §4.2 and §4.3.

The build that turns 36 pages into ~700. Two page types:

    /{lang}/immobili/{comune}/{slug}/     one per Tier A/B listing
                                          (Tier C only with a finding or
                                          a price history, §4.2)
    /{lang}/comuni/{comune}/              eight comune reports

EVERY NUMBER COMES FROM normalize.py. This module formats; it does not
compute. The one thing that looks like computation — placing a listing
relative to its comune band — is interval comparison, done conservatively:
a listing is "above p75" only when its whole interval clears the band
quantile's whole interval. Anything overlapping is said to overlap.

THE BAND IS AN INTERVAL END TO END. No midpoint is ever formed here, not
even as a sort key (listings sort on eur_sia_lo, a bound, not a centre).
lint.py's band check wakes up on /comuni/ paths the moment this build
exists; that is by design and this template is written to pass it for the
right reason, not to dodge it.

Languages follow §9's split-by-layer: listing pages are full in Italian
and extraction-paragraph-only in English; comune reports are full IT,
short-form EN. No hreflang between a full page and an extraction stub —
§9 says pairs must be genuine equivalents, so listing pages carry a
visible language link but no alternate declaration.

    python3 index_site.py --db ../phase0/phase0.sqlite --out dist-index
"""

import argparse
import html
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "phase0"))

import normalize as N
import templates as T
from templates import e

import contradictions as C
import contradictions_site as CS

LANGS = ["it", "en"]

STANDING = {
    # §4.2 item 6, verbatim on every listing page. The negation is what
    # keeps lint.py's term check satisfied — see its EXCUSED list.
    "it": "Una normalizzazione delle cifre pubblicate dall'agenzia stessa. "
          "Non è una perizia.",
    "en": "A normalization of the figures the agency itself published. "
          "Not a valuation.",
}

TIER_REASON = {
    # normalize.py's tier_reason strings are its working record, in
    # English. The page needs the reader's language, so the reasons are
    # keyed on how they start — brittle on purpose: a new reason string
    # in normalize.py should fail loudly here rather than publish the
    # wrong explanation.
    "price not published": {
        "it": "l'agenzia pubblica una fascia di prezzo, non un prezzo",
        "en": "the agency publishes a price bracket, not a price",
    },
    "no price published": {
        "it": "nessun prezzo pubblicato",
        "en": "no price published",
    },
    "no surface published": {
        "it": "nessuna superficie pubblicata",
        "en": "no surface published",
    },
    "typology unknown": {
        "it": "tipologia non determinabile, quindi nessuna conversione "
              "possibile",
        "en": "typology cannot be determined, so no conversion is possible",
    },
    "villa with land": {
        "it": "villa con terreno: la conversione andrebbe da 0,30 a 0,80, "
              "un intervallo che non dice nulla",
        "en": "villa with land: the conversion would run 0.30–0.80, "
              "a range too wide to say anything",
    },
}


def reason_text(reason, lang):
    for prefix, tr in TIER_REASON.items():
        if reason.startswith(prefix):
            return tr[lang]
    raise SystemExit(f"untranslated tier_reason: {reason!r} — add it to "
                     f"TIER_REASON before publishing a page around it")


TYPOLOGY_NAME = {
    "appartamento": ("Appartamento", "Apartment"),
    "terratetto":   ("Terratetto", "Terratetto"),
    "cielo_terra":  ("Casa cielo-terra", "Whole-building house"),
    "rustico":      ("Rustico / casale", "Farmhouse"),
    "villa":        ("Villa", "Villa"),
    "":             ("Immobile", "Property"),
}


# --- Formatting --------------------------------------------------------

def num(x, lang, places=1):
    """One number, in the reader's decimal convention.

    Every figure on these pages must be reproducible from the others by a
    reader with a calculator, so values are shown exactly as normalize.py
    rounded them — one decimal — not re-rounded for looks. Re-rounding is
    how S005 shipped arithmetic that did not check out.
    """
    s = f"{float(x):,.{places}f}"
    if lang == "it":
        s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s


def eur0(x, lang):
    return "€" + num(x, lang, 0)


def interval(lo, hi, lang, places=1):
    return f"{num(lo, lang, places)}–{num(hi, lang, places)}"


def ddate(iso, lang):
    d = str(iso or "")[:10].split("-")
    return f"{d[2]}/{d[1]}/{d[0]}" if len(d) == 3 else "—"


def strip_words(html_text):
    txt = re.sub(r"<[^>]+>", " ", html_text)
    return html.unescape(txt).split()


def extraction(p, lang):
    """Wrap the extraction paragraph, enforcing §8.4 at build time.

    40 words, counted the way lint.py will count them. Failing here is
    the point: a paragraph that grows past the limit should stop the
    build, not ship and hope.
    """
    words = strip_words(p)
    if len(words) > 40:
        raise SystemExit(f"extraction paragraph is {len(words)} words "
                         f"(limit 40): {' '.join(words)}")
    return f'<p class="lede estratto">{p}</p>'


# --- Slugs -------------------------------------------------------------

def listing_slug(r):
    """Deterministic, ordinal-free (§10.2): typology-surface-source-id.

    Derived only from the listing's own stable fields. Centogambe ids are
    already slugs; numeric ids pass through. Uniqueness comes from the
    (source, source_id) tail, which is the ingest's own primary key.
    """
    src = {"immobiliare": "imm", "centogambe": "cen", "marcellini": "mar"}
    parts = []
    if r["typology"]:
        parts.append(r["typology"].replace("_", "-"))
    if r["stated_m2"]:
        parts.append(f"{int(r['stated_m2'])}mq")
    sid = re.sub(r"[^a-z0-9-]+", "-",
                 str(r["source_id"]).lower()).strip("-")
    parts.append(f"{src.get(r['source'], r['source'][:3])}-{sid}")
    return "-".join(parts) if parts else sid


def listing_url(r, lang):
    return f"/{lang}/immobili/{r['comune']}/{listing_slug(r)}/"


def comune_url(comune, lang):
    return f"/{lang}/comuni/{comune}/"


def comune_title(comune):
    return comune.replace("-", " ").title()


# --- Band position (interval comparison, §4.2 item 3) ------------------

def band_position(r, band, lang):
    if not band or not band.get("published") or not r["eur_sia_lo"]:
        return ""
    lo, hi = r["eur_sia_lo"], r["eur_sia_hi"]
    it = lang == "it"
    if lo > band["p75_hi"]:
        s = ("sopra il 75º percentile del suo comune, su base "
             "normalizzata" if it else
             "above its comune's 75th percentile on a normalized basis")
    elif hi < band["p25_lo"]:
        s = ("sotto il 25º percentile del suo comune, su base "
             "normalizzata" if it else
             "below its comune's 25th percentile on a normalized basis")
    elif lo > band["p50_hi"]:
        s = ("sopra la mediana del suo comune, su base normalizzata"
             if it else "above its comune's median on a normalized basis")
    elif hi < band["p50_lo"]:
        s = ("sotto la mediana del suo comune, su base normalizzata"
             if it else "below its comune's median on a normalized basis")
    else:
        # Overlap is stated as overlap. Forcing every listing into
        # above/below would manufacture precision the intervals do not
        # contain — the exact move this site exists to object to.
        s = ("nella parte centrale della fascia del suo comune, o a "
             "cavallo di essa" if it else
             "within or straddling the central part of its comune's band")
    return s


# --- Listing pages (§4.2) ----------------------------------------------

def listing_extraction(r, lang):
    it = lang == "it"
    d = ddate(r["_fetched_at"], lang)
    if r["tier"] == "B":
        if it:
            p = (f"{eur0(r['price_eur'], lang)} per {num(r['stated_m2'], lang, 0)} m² "
                 f"dichiarati («{e(r['stated_label'])}»). Superficie interna "
                 f"abitabile {interval(r['sia_lo_m2'], r['sia_hi_m2'], lang)} m²: "
                 f"€{interval(r['eur_sia_lo'], r['eur_sia_hi'], lang)}/m² contro "
                 f"€{num(r['eur_stated'], lang)}/m² dell'agenzia. "
                 f"Livello B. Letto il {d}.")
        else:
            p = (f"{eur0(r['price_eur'], lang)} for a stated {num(r['stated_m2'], lang, 0)} m² "
                 f"(“{e(r['stated_label'])}”). Internal habitable area "
                 f"{interval(r['sia_lo_m2'], r['sia_hi_m2'], lang)} m²: "
                 f"€{interval(r['eur_sia_lo'], r['eur_sia_hi'], lang)}/m² against the "
                 f"agency's €{num(r['eur_stated'], lang)}/m². "
                 f"Tier B. Retrieved {d}.")
        return extraction(p, lang)

    # Tier C: the number's absence is the content.
    why = reason_text(r["tier_reason"], lang)
    head = ""
    if r["price_eur"] and r["stated_m2"]:
        head = (f"{eur0(r['price_eur'], lang)} per {num(r['stated_m2'], lang, 0)} m² "
                f"dichiarati. " if it else
                f"{eur0(r['price_eur'], lang)} for a stated {num(r['stated_m2'], lang, 0)} m². ")
    elif r["price_eur"]:
        head = (f"{eur0(r['price_eur'], lang)}. " if r["price_eur"] else "")
    if it:
        p = f"{head}Nessun indice CasaZebra: {why}. Livello C. Letto il {d}."
    else:
        p = f"{head}No CasaZebra index: {why}. Tier C. Retrieved {d}."
    return extraction(p, lang)


def cross_listing_block(r, finding, lang):
    it = lang == "it"
    if finding:
        sid, group = finding
        others = [g for g in group
                  if not (g["source"] == r["source"]
                          and str(g["source_id"]) == str(r["source_id"]))]
        lines = []
        for g in sorted(others, key=lambda x: (str(x["agency_name"] or
                                                   x["source"]),
                                               str(x["source_id"]))):
            who = e(g["agency_name"] or g["source"])
            pr = T.eur(g["price"]) if g["price"] else ("non pubblicato"
                                                       if it else
                                                       "not published")
            mq = f"{g['mq']} m²" if g["mq"] else "—"
            lines.append(f"<li><b>{who}</b>: {pr}, {mq}</li>")
        head = ("Questo immobile risulta pubblicato anche da:" if it else
                "This property is also listed by:")
        link = (f'<p><a href="/{lang}/confronti/{sid}.html">'
                + ("Il confronto completo →" if it else
                   "The full comparison →") + "</a></p>")
        return (f'<div class="block"><h2>'
                + ("Altri annunci dello stesso immobile" if it else
                   "Other listings of this property")
                + f'</h2><p style="margin-top:0">{head}</p>'
                  f'<ul style="margin:0;padding-left:18px">{"".join(lines)}</ul>'
                  f'{link}</div>')
    txt = ("Nessun altro annuncio di questo immobile risulta collegato nel "
           "nostro archivio alla data di lettura." if it else
           "No other listing of this property is linked in our archive as "
           "of the retrieval date.")
    return f'<p class="note">{txt}</p>'


def index_table(r, lang):
    it = lang == "it"
    L = {
        "stated": ("Superficie dichiarata", "Stated surface"),
        "sia": ("Superficie interna abitabile", "Internal habitable area"),
        "eur_stated": ("€/m² dell'agenzia", "Agency's €/m²"),
        "eur_sia": ("€/m² normalizzato", "Normalized €/m²"),
        "tier": ("Livello", "Tier"),
        "price": ("Prezzo richiesto", "Asking price"),
    }
    i = 0 if it else 1
    rows = [
        (L["price"][i], f"<b>{T.eur(r['price_eur'])}</b>" if r["price_eur"]
         else "—"),
        (L["stated"][i], f"{num(r['stated_m2'], lang, 0)} m² "
         f'<span class="lbl">(«{e(r["stated_label"])}»)</span>'
         if r["stated_m2"] else "—"),
    ]
    if r["tier"] == "B":
        d_lo, d_hi = N.DEFLATORS[r["typology"]]
        conv = (f"superficie dichiarata × {num(d_lo, lang, 2)}–"
                f"{num(d_hi, lang, 2)} ({e(r['typology'])})" if it else
                f"stated surface × {num(d_lo, lang, 2)}–"
                f"{num(d_hi, lang, 2)} ({e(r['typology'])})")
        rows += [
            (L["sia"][i], f"{interval(r['sia_lo_m2'], r['sia_hi_m2'], lang)} m²"),
            (("Conversione applicata" if it else "Conversion applied"), conv),
            (L["eur_stated"][i], f"€{num(r['eur_stated'], lang)}/m²"),
            (L["eur_sia"][i],
             f"<b>€{interval(r['eur_sia_lo'], r['eur_sia_hi'], lang)}/m²</b>"),
            (L["tier"][i], "B — " + ("dedotto da superficie e tipologia"
                                          if it else
                                          "inferred from surface and typology")),
        ]
    else:
        rows += [
            (L["eur_stated"][i], f"€{num(r['eur_stated'], lang)}/m²"
             if r["eur_stated"] else "—"),
            (L["eur_sia"][i], "<b>—</b> "
             + ('<span class="lbl">('
                + reason_text(r["tier_reason"], lang) + ")</span>")),
            (L["tier"][i], "C — " + ("nessun indice" if it else
                                          "no index")),
        ]
    body = "".join(f'<tr><td class="lbl">{k}</td><td class="r">{v}</td></tr>'
                   for k, v in rows)
    return f'<table class="rows">{body}</table>'


def source_block(r, lang):
    it = lang == "it"
    d = ddate(r["_fetched_at"], lang)
    who = e(r["agency_name"] or r["source"])
    link = (f'<a href="{e(r["url"])}" rel="nofollow noopener" '
            f'target="_blank">' + ("annuncio originale ↷" if it else
                                   "original listing ↷") + "</a>"
            if r["url"] else "")
    reply = (f'<a href="/{lang}/metodologia.html#replica">'
             + ("Diritto di replica" if it else "Right of reply") + "</a>")
    corr = (f'<a href="/{lang}/chi-siamo.html#correzioni">'
            + ("Segnala un errore" if it else "Report an error") + "</a>")
    read = ("Letto il" if it else "Retrieved") + f" {d}"
    return (f'<div class="block"><h2>' + ("Fonte" if it else "Source")
            + f'</h2><p style="margin-top:0"><b>{who}</b> — {link} '
              f'<span class="lbl">· {read}</span></p>'
              f'<p><b>{e(STANDING[lang])}</b></p>'
              f'<p class="note">{reply} · {corr}</p></div>')


def dom_block(r, lang):
    if not r["_dom_est"]:
        return ""
    it = lang == "it"
    txt = (f"In vendita da almeno <b>{int(r['_dom_est'])}</b> giorni, "
           f"dedotto dalla progressione degli identificativi del portale "
           f"(vedi metodo)." if it else
           f"On the market for at least <b>{int(r['_dom_est'])}</b> days, "
           f"inferred from the portal's ID progression (see method).")
    return f'<p class="note">{txt}</p>'


def listing_page(r, band, finding, lang):
    it = lang == "it"
    typ = TYPOLOGY_NAME.get(r["typology"], TYPOLOGY_NAME[""])[0 if it else 1]
    place = comune_title(r["comune"])
    title = f"{typ} — {place}"
    other = "en" if it else "it"

    pos = band_position(r, band, lang)
    pos_html = ""
    if pos and r["tier"] == "B":
        pos_html = (f'<div class="block"><h2>'
                    + ("Posizione nella fascia" if it else
                       "Position within the band")
                    + f'</h2><p style="margin:0">'
                    + ("Questo annuncio sta " if it else "This listing sits ")
                    + f'{pos} — <a href="{comune_url(r["comune"], lang)}">'
                    + (f"la fascia di {place}" if it else
                       f"the {place} band") + "</a>.</p></div>")

    if it:
        body = (f"<h1>{e(title)}</h1>"
                f'<p class="sub">' + e(STANDING["it"]) + "</p>"
                + listing_extraction(r, lang)
                + f'<div class="block">{index_table(r, lang)}'
                + dom_block(r, lang) + "</div>"
                + pos_html
                + cross_listing_block(r, finding, lang)
                + source_block(r, lang)
                + f'<p class="noprint"><a href="{comune_url(r["comune"], lang)}">'
                  f"← Tutti gli immobili di {e(place)}</a> · "
                  f'<a href="{listing_url(r, other)}">EN</a></p>')
    else:
        # §9: extraction paragraph only, plus the §4.2 items lint requires
        # on every listing page (source link, retrieval date, standing
        # line). Not a translation of the IT page and not hreflang-paired
        # with it.
        body = (f"<h1>{e(title)}</h1>"
                f'<p class="sub">' + e(STANDING["en"]) + "</p>"
                + listing_extraction(r, lang)
                + source_block(r, lang)
                + f'<p class="noprint"><a href="{listing_url(r, "it")}">'
                  f"Full page (IT) →</a></p>")

    schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "citation": r["url"] or "",
        "mainEntity": {
            "@type": "Place",
            "name": f"{typ}, {place}",
            "additionalProperty": [{
                "@type": "PropertyValue",
                "name": "stated surface m2",
                "value": r["stated_m2"] or None,
            }] + ([{
                "@type": "PropertyValue",
                "name": "internal habitable area m2 (interval)",
                "minValue": r["sia_lo_m2"], "maxValue": r["sia_hi_m2"],
            }] if r["tier"] == "B" else []),
        },
    }
    desc_words = strip_words(listing_extraction(r, lang))
    return shell_nolang(f"{title} | CasaZebra", body, lang,
                        " ".join(desc_words), schema)


def shell_nolang(title, body, lang, desc, schema=None):
    """templates.shell minus the hreflang pair — §9 forbids declaring a
    full IT page and an EN extraction stub as equivalents. The visible
    language link inside the body is navigation, not a declaration."""
    page = T.shell(title, body, lang, "", desc, schema)
    return page.replace('<link rel="alternate" hreflang='
                        f'"{"en" if lang == "it" else "it"}" href="">\n', "")


# --- Comune reports (§4.3) ---------------------------------------------

def comune_extraction(comune, b, data_date, lang):
    it = lang == "it"
    place = comune_title(comune)
    if not b.get("published"):
        p = ((f"{place}: nessuna fascia pubblicata — "
              f"{e(b.get('suppressed_because', ''))}. Dati al "
              f"{ddate(data_date, lang)}.") if it else
             (f"{place}: no band published — "
              f"{e(b.get('suppressed_because', ''))}. Data as of "
              f"{ddate(data_date, lang)}."))
        return extraction(p, lang)
    if it:
        p = (f"{place}, fascia normalizzata: "
             f"€{interval(b['p50_lo'], b['p50_hi'], lang)}/m² (mediana, "
             f"intervallo). {b['n']} annunci, {b['n_agencies']} agenzie; "
             f"livello A {b['tier_split']['A']}, B {b['tier_split']['B']}. "
             f"Conversione {num(b['p50_width_pct'], lang)}%, mercato "
             f"{num(b['market_spread_pct'], lang)}%. Dati al "
             f"{ddate(data_date, lang)}.")
    else:
        p = (f"{place}, normalized band: "
             f"€{interval(b['p50_lo'], b['p50_hi'], lang)}/m² (median, "
             f"interval). {b['n']} listings, {b['n_agencies']} agencies; "
             f"tier A {b['tier_split']['A']}, B {b['tier_split']['B']}. "
             f"Conversion {num(b['p50_width_pct'], lang)}%, market "
             f"{num(b['market_spread_pct'], lang)}%. Data as of "
             f"{ddate(data_date, lang)}.")
    return extraction(p, lang)


SORT_JS = """
<script>
document.querySelectorAll("table.sortable th[data-c]").forEach(function(h){
  h.style.cursor="pointer";
  h.addEventListener("click",function(){
    var t=h.closest("table"),b=t.tBodies[0],i=+h.dataset.c,
        asc=h.dataset.a!=="1";
    t.querySelectorAll("th").forEach(function(x){delete x.dataset.a});
    h.dataset.a=asc?"1":"0";
    Array.from(b.rows).sort(function(r1,r2){
      var a=r1.cells[i].dataset.v??r1.cells[i].textContent,
          c=r2.cells[i].dataset.v??r2.cells[i].textContent,
          n1=parseFloat(a),n2=parseFloat(c);
      if(!isNaN(n1)&&!isNaN(n2))return asc?n1-n2:n2-n1;
      return asc?a.localeCompare(c):c.localeCompare(a);
    }).forEach(function(r){b.appendChild(r)});
  });
});
</script>
"""


def two_widths_block(b, lang):
    it = lang == "it"
    head = ("Quanta parte dell'intervallo siamo noi" if it else
            "How much of the range is us")
    ours = ("Incertezza della nostra conversione" if it else
            "Our conversion's uncertainty")
    market = ("Variabilità del mercato stesso (p25–p75)" if it else
              "The market's own spread (p25–p75)")
    note = (("Le due larghezze, una accanto all'altra, come richiede il "
             "metodo: la prima è quanto è incerta la conversione "
             "che applichiamo noi, la seconda è quanto variano davvero "
             "i prezzi normalizzati in questo comune. Qui la seconda è "
             "molto più grande: l'intervallo è il mercato, non il "
             "metodo.") if it else
            ("The two widths side by side, as the method requires: the "
             "first is how uncertain our conversion is, the second is how "
             "much normalized prices in this comune genuinely vary. Here "
             "the second is far larger: the interval is the market, not "
             "the method."))
    return (f'<div class="block"><h2>{head}</h2><table class="rows">'
            f'<tr><td class="lbl">{ours}</td>'
            f'<td class="r"><b>{num(b["p50_width_pct"], lang)}%</b></td></tr>'
            f'<tr><td class="lbl">{market}</td>'
            f'<td class="r"><b>{num(b["market_spread_pct"], lang)}%</b></td></tr>'
            f'</table><p class="note">{note}</p></div>')


def band_block(b, lang):
    it = lang == "it"
    qn = (("25º percentile", "Mediana (p50)", "75º percentile")
          if it else
          ("25th percentile", "Median (p50)", "75th percentile"))
    rows = "".join(
        f'<tr><td class="lbl">{name}</td>'
        f'<td class="r"><b>€{interval(b[q + "_lo"], b[q + "_hi"], lang)}'
        f"/m²</b></td></tr>"
        for q, name in zip(("p25", "p50", "p75"), qn))
    note = (("Ogni riga è un intervallo, non un numero: ogni annuncio "
             "entra nella fascia come intervallo e la fascia lo resta fino "
             "a questa pagina. Da X a Y, mai la loro media.") if it else
            ("Each row is an interval, not a number: every listing enters "
             "the band as an interval and the band stays one all the way "
             "to this page. X to Y, never their midpoint."))
    head = ("La fascia normalizzata" if it else "The normalized band")
    return (f'<div class="block"><h2>{head}</h2>'
            f'<table class="rows">{rows}</table>'
            f'<p class="note">{note}</p></div>')


def agencies_block(rows, lang):
    """Per-agency table over ALL in-scope rows of the comune, not only
    the Tier A/B ones — the 'with a published price' column exists
    precisely to count the listings the index cannot use, and computing
    it over the usable subset would define the problem away (a bracket
    agency would show 100% of its zero priced listings)."""
    it = lang == "it"
    per = {}
    for r in rows:
        a = r["agency_name"] or r["source"]
        per.setdefault(a, {"n": 0, "priced": 0, "labels": set()})
        per[a]["n"] += 1
        if r["price_eur"]:
            per[a]["priced"] += 1
        lab = re.sub(r"[\d.,\s]+", " ", str(r["stated_label"])).strip()
        if lab:
            per[a]["labels"].add(lab)
    body_rows = []
    for a, d in sorted(per.items()):
        pct = ("" if d["priced"] == d["n"] else
               f' <b>({round(d["priced"] / d["n"] * 100)}%)</b>')
        body_rows.append(
            f'<tr><td>{e(a)}</td><td class="r">{d["n"]}</td>'
            f'<td class="r">{d["priced"]}{pct}</td>'
            f'<td class="r">{e(", ".join(sorted(d["labels"])) or "—")}</td>'
            f"</tr>")
    body = "".join(body_rows)
    head = ("Agenzie attive: prezzi pubblicati e convenzioni di superficie"
            if it else
            "Active agencies: published prices and surface conventions")
    cols = (("Agenzia", "Annunci", "Con prezzo", "Etichetta superficie")
            if it else
            ("Agency", "Listings", "With a price", "Surface label"))
    note = (("Un annuncio senza prezzo pubblicato non è confrontabile e "
             "non entra nell'indice — il conteggio completo per operatore "
             "è in <a href=\"/it/guide/prezzi-non-pubblicati/\">chi "
             "pubblica i prezzi</a>. Nessuna agenzia definisce la base "
             "della superficie che pubblica: una cifra sola, con "
             "l'etichetta indicata. È il motivo per cui la conversione "
             "qui sopra esiste.") if it else
            ("A listing without a published price cannot be compared and "
             "does not enter the index — the full per-operator count is "
             "in <a href=\"/en/guide/prezzi-non-pubblicati/\">who "
             "publishes prices</a>. No agency defines the basis of the "
             "surface it publishes: a single figure, with the label "
             "shown. That is why the conversion above exists."))
    ths = "".join(f'<th style="text-align:{"left" if i == 0 else "right"}">'
                  f"{c}</th>" for i, c in enumerate(cols))
    return (f'<div class="block"><h2>{head}</h2><table class="rows">'
            f"<tr>{ths}</tr>{body}</table>"
            f'<p class="note">{note}</p></div>')


def findings_block(comune, findings, lang):
    it = lang == "it"
    local = [(sid, item) for sid, item in findings
             if CS.comune_of(item["group"]) == comune]
    head = ("Contraddizioni documentate" if it else "Documented contradictions")
    if not local:
        txt = ("Nessuna contraddizione fra agenzie è al momento "
               "documentata in questo comune." if it else
               "No contradiction between agencies is currently documented "
               "in this comune.")
        return f'<div class="block"><h2>{head}</h2><p style="margin:0">{txt}</p></div>'
    worst = 0
    items = []
    for sid, item in sorted(local, key=lambda x: x[0]):
        d = item["d"]
        spread = max(d.get("price", (0, 0, 0))[2], d.get("surface", (0, 0, 0))[2])
        worst = max(worst, spread)
        label = C.best_label(item["group"])
        what = []
        if "price" in d:
            what.append((f"{d['price'][2]:.0f}% sul prezzo") if it else
                        (f"{d['price'][2]:.0f}% on price"))
        if "surface" in d:
            what.append((f"{d['surface'][2]:.0f}% sulla superficie") if it else
                        (f"{d['surface'][2]:.0f}% on surface"))
        items.append(f'<li><a href="/{lang}/confronti/{sid}.html">{e(label)}'
                     f"</a> — {e(', '.join(what) or '—')}</li>")
    lead = ((f"{len(local)} immobili di questo comune sono pubblicati da "
             f"più agenzie con numeri diversi; lo scarto peggiore "
             f"documentato è del {worst:.0f}%.") if it else
            (f"{len(local)} properties in this comune are listed by more "
             f"than one agency with different figures; the worst "
             f"documented spread is {worst:.0f}%."))
    return (f'<div class="block"><h2>{head}</h2>'
            f'<p style="margin-top:0">{lead}</p>'
            f'<ul style="margin:0;padding-left:18px">{"".join(items)}</ul></div>')


def listings_table(rows_b, lang):
    it = lang == "it"
    cols = (("Tipologia", "Agenzia", "m² dich.", "€/m² agenzia",
             "€/m² normalizzato", "Livello") if it else
            ("Type", "Agency", "Stated m²", "Agency €/m²",
             "Normalized €/m²", "Tier"))
    ths = "".join(f'<th data-c="{i}" style="text-align:'
                  f'{"left" if i < 2 else "right"}">{c}</th>'
                  for i, c in enumerate(cols))
    trs = []
    for r in sorted(rows_b, key=lambda r: (r["eur_sia_lo"], r["source"],
                                           str(r["source_id"]))):
        typ = TYPOLOGY_NAME.get(r["typology"], TYPOLOGY_NAME[""])[0 if it else 1]
        trs.append(
            f'<tr><td><a href="{listing_url(r, lang)}">{e(typ)}</a></td>'
            f'<td>{e(r["agency_name"] or r["source"])}</td>'
            f'<td class="r" data-v="{r["stated_m2"]}">{num(r["stated_m2"], lang, 0)}</td>'
            f'<td class="r" data-v="{r["eur_stated"]}">{num(r["eur_stated"], lang)}</td>'
            f'<td class="r" data-v="{r["eur_sia_lo"]}">'
            f"{interval(r['eur_sia_lo'], r['eur_sia_hi'], lang)}</td>"
            f'<td class="r">{r["tier"]}</td></tr>')
    head = ("Gli annunci, in ordine di €/m² normalizzato" if it else
            "The listings, ordered by normalized €/m²")
    note = ("Clic su una colonna per riordinare. Ogni riga è un "
            "annuncio; il valore normalizzato è sempre un intervallo."
            if it else
            "Click a column to re-sort. One row per listing; the "
            "normalized value is always an interval.")
    return (f'<div class="block"><h2>{head}</h2>'
            f'<div style="overflow-x:auto"><table class="rows sortable">'
            f"<thead><tr>{ths}</tr></thead><tbody>{''.join(trs)}</tbody>"
            f"</table></div>"
            f'<p class="note">{note}</p></div>' + SORT_JS)


def comune_page(comune, rows, b, findings, data_date, lang):
    it = lang == "it"
    place = comune_title(comune)
    rows_ab = [r for r in rows if r["tier"] in ("A", "B")]
    n_c = sum(1 for r in rows if r["tier"] == "C")

    title = ((f"Indice dei prezzi — {place}") if it else
             (f"Price index — {place}"))
    tier_c_note = ((f"Altri {n_c} annunci del comune sono di livello C e "
                    f"non contribuiscono né alla fascia né "
                    f"all'indice: ciascuno, se pubblicato, dice perché.")
                   if it else
                   (f"A further {n_c} listings in this comune are Tier C "
                    f"and contribute neither to the band nor to the index."))

    if not b.get("published"):
        stub = (("Questo comune non ha una fascia pubblicata: " +
                 e(b.get("suppressed_because", "")) +
                 ". Nessuna fascia e nessun indice, e lo diciamo.") if it else
                ("This comune has no published band: " +
                 e(b.get("suppressed_because", "")) +
                 ". No band and no index claims."))
        body = (f"<h1>{e(title)}</h1>"
                + comune_extraction(comune, b, data_date, lang)
                + f'<div class="block"><p style="margin:0">{stub}</p></div>')
    else:
        parts = [f"<h1>{e(title)}</h1>",
                 comune_extraction(comune, b, data_date, lang),
                 band_block(b, lang),
                 two_widths_block(b, lang)]
        if it:
            parts += [agencies_block(rows, lang),
                      findings_block(comune, findings, lang),
                      listings_table([r for r in rows_ab if r["tier"] == "B"],
                                     lang),
                      f'<p class="note">{tier_c_note}</p>']
        else:
            # §9: EN short form — band, widths, findings; the full listing
            # table stays on the IT page.
            parts += [findings_block(comune, findings, lang),
                      f'<p class="note">{tier_c_note}</p>']
        body = "".join(parts)

    other = "en" if it else "it"
    desc = " ".join(strip_words(comune_extraction(comune, b, data_date, lang)))
    schema = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": title,
        "description": desc,
        "temporalCoverage": str(data_date or "")[:10],
        "license": "https://creativecommons.org/licenses/by/4.0/",
    }
    # Comune reports exist fully in both languages: genuine equivalents,
    # so these DO get the hreflang pair.
    return T.shell(f"{title} | CasaZebra", body, lang,
                   comune_url(comune, other), desc, schema)


SEARCH_TXT = {
    "it": {
        "h": "Cerca un annuncio",
        "ph": "Incolla il link di un annuncio — Immobiliare o il sito "
              "dell'agenzia — o una sua parte",
        "btn": "Cerca",
        "help": "Troviamo la pagina CasaZebra dello stesso annuncio. "
                "La ricerca avviene nel tuo browser: non inviamo nulla.",
        "none": "Nessun annuncio corrispondente nel nostro archivio. "
                "Copre gli otto comuni della Valtiberina; un annuncio "
                "nuovo entra al primo aggiornamento dopo la pubblicazione.",
        "nopage": "è in archivio ma senza pagina (livello C: nessun "
                  "prezzo o superficie utilizzabile)",
        "many": "annunci trovati:",
    },
    "en": {
        "h": "Look up a listing",
        "ph": "Paste a listing link — Immobiliare or an agency site — "
              "or part of one",
        "btn": "Search",
        "help": "We find the CasaZebra page for the same listing. The "
                "search runs in your browser: nothing is sent anywhere.",
        "none": "No matching listing in our archive. It covers the eight "
                "Valtiberina comuni; a new listing enters at the first "
                "update after it is published.",
        "nopage": "is in the archive but has no page (Tier C: no usable "
                  "price or surface)",
        "many": "listings found:",
    },
}

# Plain string, not an f-string: this is JavaScript, and every brace in
# it would otherwise need doubling. %s slots are filled below.
SEARCH_JS = """
<script>
(function(){
var f=document.getElementById("cerca-f"),q=document.getElementById("cerca-q"),
    out=document.getElementById("cerca-out"),DB=null;
function norm(s){return s.toLowerCase().replace(/^https?:\\/\\//,"")
  .replace(/^www\\./,"").split("?")[0].split("#")[0].replace(/\\/+$/,"");}
function digits(s){var m=s.match(/\\d{6,}/);return m?m[0]:null;}
function render(hits){
  if(!hits.length){out.innerHTML='<p class="note">%NONE%</p>';return;}
  var h='<p class="note">'+hits.length+' %MANY%</p><ul style="padding-left:18px">';
  hits.slice(0,10).forEach(function(e){
    h+= e[1] ? '<li><a href="'+e[1]+'">'+e[2]+'</a></li>'
             : '<li>'+e[2]+' — %NOPAGE%</li>';});
  out.innerHTML=h+'</ul>';}
function search(){
  var v=norm(q.value.trim());if(!v)return;
  var id=digits(v);
  var hits=DB.filter(function(e){
    return e[0].indexOf(v)>-1||v.indexOf(e[0])>-1||(id&&e[0].indexOf(id)>-1);});
  render(hits);}
f.addEventListener("submit",function(ev){ev.preventDefault();
  if(DB){search();return;}
  out.innerHTML='<p class="note">…</p>';
  fetch("/cerca.json").then(function(r){return r.json()})
    .then(function(d){DB=d;search();})
    .catch(function(){out.innerHTML='<p class="note">%NONE%</p>';});});
})();
</script>
"""


def search_block(lang):
    t = SEARCH_TXT[lang]
    js = (SEARCH_JS.replace("%NONE%", e(t["none"]))
                   .replace("%NOPAGE%", e(t["nopage"]))
                   .replace("%MANY%", e(t["many"])))
    return (f'<div class="block"><h2>{e(t["h"])}</h2>'
            f'<form id="cerca-f" class="noprint" '
            f'style="display:flex;gap:10px;flex-wrap:wrap">'
            f'<input type="text" id="cerca-q" placeholder="{e(t["ph"])}" '
            f'style="flex:1;min-width:240px">'
            f'<button type="submit">{e(t["btn"])}</button></form>'
            f'<div id="cerca-out"></div>'
            f'<p class="note">{e(t["help"])}</p></div>' + js)


def lookup_entry(r, has_page):
    """One /cerca.json row: [normalized source url, our path or "", label].

    The source URL is pre-normalized at build time so the browser does
    string containment and nothing else.
    """
    if not r["url"]:
        return None
    u = re.sub(r"^https?://(www\.)?", "", str(r["url"]).lower())
    u = u.split("?")[0].split("#")[0].rstrip("/")
    typ = TYPOLOGY_NAME.get(r["typology"], TYPOLOGY_NAME[""])[0]
    label = f"{typ} — {comune_title(r['comune'])}"
    if r["agency_name"]:
        label += f" ({r['agency_name']})"
    return [u, listing_url(r, "it") if has_page else "", label]


def comuni_index(bands, by_comune, data_date, lang):
    """/{lang}/comuni/ — the eight reports, one tile each. Lives under
    the /comuni/ path, so lint's band check applies: every € on this page
    is an interval, same as the reports it links."""
    it = lang == "it"
    tiles = []
    for comune in sorted(by_comune):
        b = bands.get(comune, {})
        place = comune_title(comune)
        if b.get("published"):
            line = (f"€{interval(b['p50_lo'], b['p50_hi'], lang)}/m² "
                    + ("(mediana, intervallo)" if it else "(median, interval)")
                    + f" · {b['n']} " + ("annunci" if it else "listings"))
        else:
            line = ("nessuna fascia pubblicata" if it else
                    "no band published")
        tiles.append(f'<a class="tile" href="{comune_url(comune, lang)}">'
                     f"<b>{e(place)}</b><small>{line}</small></a>")
    h1 = ("I comuni della Valtiberina" if it else "The Valtiberina comuni")
    sub = (("Una fascia per comune, sempre come intervallo, mai come "
            "numero singolo. Dati al " if it else
            "One band per comune, always an interval, never a single "
            "number. Data as of ") + ddate(data_date, lang) + ".")
    n_b = sum(len([r for r in rs if r["tier"] == "B"])
              for rs in by_comune.values())
    # This page is also the site's landing page (build.py points the root
    # redirect here): the index is the product, so the front door shows
    # the eight comuni — with the evidence one click away, not hidden and
    # not in front.
    evidence = (
        f'<div class="hero" style="margin-top:26px"><h1 style="font-size:20px">'
        + ("Le agenzie non concordano" if it else "The agencies do not agree")
        + f'</h1><p style="margin:6px 0 0">'
        + ((f"{n_b} annunci normalizzati con un solo metro. Dove più "
            f"agenzie pubblicano numeri diversi per lo stesso immobile, "
            f"lo documentiamo: ") if it else
           (f"{n_b} listings normalized to one measure. Where several "
            f"agencies publish different figures for the same property, "
            f"we document it: "))
        + f'<a href="/{lang}/confronti/">'
        + ("i confronti, uno per immobile →" if it else
           "the comparisons, one per property →")
        + "</a></p></div>")
    body = (f"<h1>{e(h1)}</h1><p class=\"sub\">{e(sub)}</p>"
            + search_block(lang)
            + f'<div class="grid">{"".join(tiles)}</div>' + evidence)
    other = "en" if it else "it"
    return T.shell(f"{h1} | CasaZebra", body, lang, f"/{other}/comuni/",
                   sub)


# --- Build -------------------------------------------------------------

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def build(db_path, out):
    rows, bands, _ = N.run(db_path=db_path,
                           out_dir=os.path.dirname(os.path.abspath(db_path)))

    # Fields §4.2 needs that the normalized row does not carry.
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    raw = {(r["source"], str(r["source_id"])): r
           for r in conn.execute("SELECT * FROM listings")}
    items = C.build(conn)
    conn.close()

    for r in rows:
        rr = raw[(r["source"], str(r["source_id"]))]
        r["_fetched_at"] = rr["fetched_at"]
        r["_dom_est"] = rr["dom_est"]
        r["_price_previous"] = rr["price_previous"]

    # Findings, same publication filter as the contradictions build —
    # a listing page must never link a cluster that site holds back.
    keep = [it for it in items
            if it.get("verified") or (set(it["evidence"]) & CS.IDENTITY)]
    findings = sorted(((CS.slug(it), it) for it in keep), key=lambda x: x[0])
    member_of = {}
    for sid, item in findings:
        for g in item["group"]:
            member_of[(g["source"], str(g["source_id"]))] = (sid, item["group"])

    data_date = max((r["_fetched_at"] or "") for r in rows)

    by_comune = {}
    for r in rows:
        by_comune.setdefault(r["comune"], []).append(r)

    # §4.2 publish gate: Tier A/B always; Tier C only with a finding or a
    # price history. (No listing currently has a recorded price history;
    # the condition is written anyway so the first one gets its page.)
    def has_page(r):
        if r["tier"] in ("A", "B"):
            return True
        return ((r["source"], str(r["source_id"])) in member_of
                or bool(r["_price_previous"]))

    pages = []
    n_listing = {"it": 0, "en": 0}
    n_c_published = 0
    for comune in sorted(by_comune):
        band = bands.get(comune, {})
        for r in sorted(by_comune[comune],
                        key=lambda r: (r["source"], str(r["source_id"]))):
            if not has_page(r):
                continue
            if r["tier"] == "C":
                n_c_published += 1
            f = member_of.get((r["source"], str(r["source_id"])))
            for lang in LANGS:
                p = f"{out}{listing_url(r, lang)}index.html"
                write(p, listing_page(r, band, f, lang))
                pages.append(listing_url(r, lang))
                n_listing[lang] += 1
        for lang in LANGS:
            p = f"{out}{comune_url(comune, lang)}index.html"
            write(p, comune_page(comune, by_comune[comune], band,
                                 findings, data_date, lang))
            pages.append(comune_url(comune, lang))

    for lang in LANGS:
        write(f"{out}/{lang}/comuni/index.html",
              comuni_index(bands, by_comune, data_date, lang))
        pages.append(f"/{lang}/comuni/")

    # The paste-a-URL lookup index. Every in-scope listing, page or not:
    # a listing without a page answers with the reason, which is §3.3's
    # honesty applied to search results. Sorted for determinism.
    entries = []
    for comune in sorted(by_comune):
        for r in sorted(by_comune[comune],
                        key=lambda r: (r["source"], str(r["source_id"]))):
            en = lookup_entry(r, has_page(r))
            if en:
                entries.append(en)
    entries.sort()
    with open(f"{out}/cerca.json", "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")

    # Sitemap fragment only. This build merges into the same web root as
    # dist-contradictions at deploy; robots.txt and the root redirect
    # belong to that build, and duplicating them here would make the
    # deploy order decide which copy wins.
    write(f"{out}/sitemap-immobili.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{u}</loc></url>\n" for u in sorted(pages))
          + "</urlset>\n")

    n_b = sum(1 for r in rows if r["tier"] == "B")
    print(f"listing pages: {n_listing['it']} IT + {n_listing['en']} EN "
          f"({n_b} Tier B, {n_c_published} Tier C with a finding)")
    print(f"comune reports: {sum(1 for b in bands.values() if b['published'])}"
          f" published of {len(bands)}")
    print(f"{len(pages)} URLs -> {out}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="../phase0/phase0.sqlite")
    ap.add_argument("--out", default="dist-index")
    a = ap.parse_args()
    build(a.db, a.out)
