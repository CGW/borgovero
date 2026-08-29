"""Phase 1 pages — seo-spec.md §8 and §11, the small pages that make the
index citable and correctable.

    /llms.txt                     §8.2 — generated, never hand-maintained
    /dati/                        §8.3 — CSV+JSON export, CC BY 4.0
    /it/correzioni/               §11.3 — public corrections log
    /it/diritto-di-replica/       §11.2 — right-of-reply route
    /it/guide/prezzi-non-pubblicati/   the opacity finding (SOT §16e)

EVERY COUNT ON THESE PAGES COMES FROM THE BUILD'S OWN DATA. A hand-typed
corpus count in llms.txt is the drift §8.2 warns about — it is the same
mistake as the method page carrying a deflator table one revision behind
the code, on the file whose whole audience is machines that quote it.

The corrections log is the one deliberately hand-maintained content on
the site (CORRECTIONS below): a correction is an editorial act with a
date and a named change, and generating it would mean pretending the
build knows when we were wrong. The page around the entries is still
templated; only the entries are human.
"""

import csv
import io
import json
import os

import templates as T
from templates import e


# One entry per published correction, newest first. Append; never delete.
# (date, IT text, EN text)
CORRECTIONS = [
    # Mind the lint when writing entries: name the old wording by
    # description, not by quoting it, or the log of the fix re-commits the
    # error it records.
    ("2026-08-30",
     "La dichiarazione a piè di pagina descriveva il sito, su tutte le 36 "
     "pagine pubblicate, con la parola regolamentata che il nostro stesso "
     "metodo vieta — mentre due righe sotto il metodo diceva «non è una "
     "perizia». Corretta in «indice indipendente» ovunque. Trovata dal "
     "nostro controllo automatico; nessun dato era errato, la parola sì.",
     "The footer declaration described the site, on all 36 published "
     "pages, with the regulated word our own method forbids — while two "
     "lines below, the method said it is not a perizia. Corrected to "
     "“independent index” everywhere. Caught by our own build "
     "check; no figure was wrong, the word was."),
]


def _flat_words(html_text):
    import html as _h
    import re
    return _h.unescape(re.sub(r"<[^>]+>", " ", html_text)).split()


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# --- llms.txt (§8.2) ---------------------------------------------------

def llms_txt(rows, bands, n_findings, data_date):
    n_b = sum(1 for r in rows if r["tier"] == "B")
    n_pub = sum(1 for b in bands.values() if b.get("published"))
    return f"""# CasaZebra — llms.txt

> Independent, non-profit index of asking prices in the Valtiberina
> (upper Tiber valley, Italy). One written surface standard applied to
> every listing; every normalized figure is an interval, never a point.
> Not a valuation. Data as of {str(data_date)[:10]}.

Corpus: {n_b} listings with a normalized index (Tier B), {n_findings}
documented cross-agency contradictions, {n_pub} comuni with a published
price band. Every page's first paragraph is self-contained: price, stated
surface with the agency's own label, our interval, tier, retrieval date.

## Method
- /it/metodologia.html : the standard — deflators, weighting table, tiers, band gate (IT)
- /en/metodologia.html : the same, in English

## Data
- /dati/ : full dataset, CSV and JSON, licence CC BY 4.0 (attribution = a link)

## Page types
- /it/immobili/{{comune}}/{{slug}}/ : one page per listing
- /it/comuni/{{comune}}/ : comune report with the interval band
- /it/confronti/ : same property, different published numbers
- /it/correzioni/ : public corrections log
- /it/diritto-di-replica/ : right of reply
"""


# --- /dati/ (§8.3) -----------------------------------------------------

def dataset_files(rows, bands, findings_export):
    """(relpath, bytes) for everything under /dati/. Deterministic."""
    out = []

    ab = [r for r in rows if r["tier"] in ("A", "B")]
    buf = io.StringIO()
    cols = ["source", "source_id", "comune", "url", "agency_name",
            "typology", "typology_provenance", "price_eur", "stated_m2",
            "stated_label", "tier", "sia_lo_m2", "sia_hi_m2",
            "eur_stated", "eur_sia_lo", "eur_sia_hi"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(ab)
    out.append(("dati/listings.csv", buf.getvalue()))
    out.append(("dati/listings.json", json.dumps(
        [{k: r[k] for k in cols} for r in ab],
        ensure_ascii=False, indent=1, sort_keys=True) + "\n"))

    out.append(("dati/comune_bands.json", json.dumps(
        bands, ensure_ascii=False, indent=2, sort_keys=True) + "\n"))

    out.append(("dati/findings.json", json.dumps(
        findings_export, ensure_ascii=False, indent=1, sort_keys=True) + "\n"))
    return out


def dati_page(rows, bands, n_findings, data_date, lang):
    it = lang == "it"
    n_ab = sum(1 for r in rows if r["tier"] in ("A", "B"))
    n_pub = sum(1 for b in bands.values() if b.get("published"))
    d = str(data_date)[:10]
    files = [
        ("listings.csv", "CSV", ("tutti gli annunci di livello A/B, "
                                 "normalizzati" if it else
                                 "all Tier A/B listings, normalized")),
        ("listings.json", "JSON", ("gli stessi dati, per le macchine" if it
                                   else "the same data, for machines")),
        ("comune_bands.json", "JSON", ("le fasce per comune, come intervalli"
                                       if it else
                                       "the comune bands, as intervals")),
        ("findings.json", "JSON", ("le contraddizioni documentate" if it else
                                   "the documented contradictions")),
    ]
    frows = "".join(
        f'<tr><td><a href="/dati/{f}">{f}</a></td><td class="r">{k}</td>'
        f"<td>{d_}</td></tr>" for f, k, d_ in files)
    if it:
        body = f"""
<h1>Dati aperti</h1>
<p class="sub">L'intero indice, scaricabile. Licenza CC BY 4.0:
usalo per qualsiasi scopo, cita CasaZebra con un link.</p>
<div class="block">
  <p style="margin-top:0">{n_ab} annunci normalizzati, {n_findings}
  contraddizioni documentate, {n_pub} comuni con fascia pubblicata.
  Dati al {d}. Ogni valore normalizzato è un intervallo
  (<code>lo</code>/<code>hi</code>), mai un numero singolo — il perché è
  nel <a href="/it/metodologia.html">metodo</a>.</p>
  <table class="rows">{frows}</table>
  <p class="note">Gli identificativi sono stabili fra le versioni. I campi
  <code>eur_stated</code> (l'aritmetica dell'agenzia) e
  <code>eur_sia_lo/hi</code> (la nostra normalizzazione) compaiono sempre
  insieme; pubblicarne uno solo travisa il dato.</p>
</div>"""
    else:
        body = f"""
<h1>Open data</h1>
<p class="sub">The whole index, downloadable. Licence CC BY 4.0:
use it for anything, credit CasaZebra with a link.</p>
<div class="block">
  <p style="margin-top:0">{n_ab} normalized listings, {n_findings}
  documented contradictions, {n_pub} comuni with a published band.
  Data as of {d}. Every normalized value is an interval
  (<code>lo</code>/<code>hi</code>), never a single number — the reasons
  are in <a href="/en/metodologia.html">the method</a>.</p>
  <table class="rows">{frows}</table>
  <p class="note">IDs are stable across releases. <code>eur_stated</code>
  (the agency's own arithmetic) and <code>eur_sia_lo/hi</code> (our
  normalization) always travel together; publishing only one of them
  misrepresents the data.</p>
</div>"""
    schema = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "CasaZebra — Valtiberina asking-price index",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "temporalCoverage": d,
        "creator": {"@type": "Organization", "name": "CasaZebra"},
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "text/csv",
             "contentUrl": "/dati/listings.csv"},
            {"@type": "DataDownload", "encodingFormat": "application/json",
             "contentUrl": "/dati/listings.json"},
        ],
    }
    title = "Dati aperti | CasaZebra" if it else "Open data | CasaZebra"
    other = "en" if it else "it"
    return T.shell(title, body, lang, f"/{other}/dati.html",
                   " ".join(_flat_words(body))[:150], schema)


# --- /it/correzioni/ (§11.3) -------------------------------------------

def correzioni_page(lang):
    it = lang == "it"
    entries = "".join(
        f'<tr><td class="lbl" style="white-space:nowrap">{d}</td>'
        f"<td>{e(txt_it if it else txt_en)}</td></tr>"
        for d, txt_it, txt_en in CORRECTIONS)
    if it:
        body = f"""
<h1>Correzioni</h1>
<p class="sub">Ogni correzione pubblicata resta qui, con la data.
Un sito che misura la cura degli altri registra i propri errori.</p>
<div class="block">
  <p style="margin-top:0"><b>La regola:</b> chi segnala un errore riceve
  risposta entro 7 giorni. Se il dato è sbagliato, viene corretto e la
  correzione viene registrata in questa pagina. Se l'annuncio di origine è
  cambiato dopo la nostra lettura, la pagina viene aggiornata con la nuova
  data di lettura.</p>
  <p>Scrivi a <b>correzioni@casazebra.it</b>, oppure usa il
  <a href="/it/diritto-di-replica/">diritto di replica</a> se rappresenti
  un'agenzia nominata.</p>
</div>
<div class="block">
  <h2>Registro</h2>
  <table class="rows">{entries}</table>
</div>"""
    else:
        body = f"""
<h1>Corrections</h1>
<p class="sub">Every published correction stays here, dated.
A site that measures other people's care records its own mistakes.</p>
<div class="block">
  <p style="margin-top:0"><b>The rule:</b> anyone reporting an error gets
  an answer within 7 days. If the figure is wrong it is corrected and the
  correction is logged on this page. If the source listing changed after
  our retrieval, the page is updated with a new retrieval date.</p>
  <p>Write to <b>correzioni@casazebra.it</b>, or use the
  <a href="/it/diritto-di-replica/">right of reply</a> if you represent a
  named agency.</p>
</div>
<div class="block">
  <h2>Log</h2>
  <table class="rows">{entries}</table>
</div>"""
    title = "Correzioni | CasaZebra" if it else "Corrections | CasaZebra"
    other = "en" if it else "it"
    return T.shell(title, body, lang, f"/{other}/correzioni/",
                   "Registro pubblico delle correzioni" if it else
                   "Public corrections log")


# --- /it/diritto-di-replica/ (§11.2) -----------------------------------

def replica_page(lang):
    it = lang == "it"
    if it:
        body = """
<h1>Diritto di replica</h1>
<p class="sub">Per le agenzie nominate su queste pagine.</p>
<div class="block">
  <p style="margin-top:0">Ogni pagina che nomina un'agenzia riporta solo
  cifre che l'agenzia stessa ha pubblicato, con il link all'annuncio.
  Se ritieni che un accostamento sia sbagliato — due annunci che non sono
  lo stesso immobile, un dato cambiato dopo la nostra lettura, un numero
  trascritto male — <b>scrivici e ricontrolliamo entro 7 giorni</b>.</p>
  <ul style="padding-left:18px">
    <li>Se hai ragione, la pagina viene rimossa o corretta, e la
    correzione è registrata nel <a href="/it/correzioni/">registro
    pubblico</a>.</li>
    <li>Se chiedi una replica, la pubblichiamo integralmente accanto alla
    pagina a cui si riferisce, con la tua firma.</li>
  </ul>
  <p>Scrivi a: <b>replica@casazebra.it</b></p>
</div>"""
    else:
        body = """
<h1>Right of reply</h1>
<p class="sub">For agencies named on these pages.</p>
<div class="block">
  <p style="margin-top:0">Every page that names an agency carries only
  figures the agency itself published, linked to the listing. If you
  believe a pairing is wrong — two listings that are not the same
  property, a figure that changed after our retrieval, a transcription
  error — <b>write to us and we re-check within 7 days</b>.</p>
  <ul style="padding-left:18px">
    <li>If you are right, the page is removed or corrected, and the
    correction is logged in the <a href="/it/correzioni/">public
    corrections log</a>.</li>
    <li>If you ask for a reply, we publish it in full beside the page it
    concerns, under your name.</li>
  </ul>
  <p>Write to: <b>replica@casazebra.it</b></p>
</div>"""
    title = ("Diritto di replica | CasaZebra" if it else
             "Right of reply | CasaZebra")
    other = "en" if it else "it"
    return T.shell(title, body, lang, f"/{other}/diritto-di-replica/",
                   "Come chiedere una correzione o una replica" if it else
                   "How to request a correction or a reply")


# --- /it/guide/prezzi-non-pubblicati/ (SOT §16e) -----------------------

# Portal listings with no agency name are a real group, but they are not
# an agency called "immobiliare" — labelling them as one would put a
# made-up operator in a table whose whole value is naming real ones.
_UNNAMED = {
    "immobiliare": "Senza agenzia indicata (portale Immobiliare)",
    "centogambe": "Centogambe",
    "marcellini": "Marcellini",
}


def opacity_stats(rows):
    """Per-agency price publication, from the build's own rows.

    Computed per source (the agency's own site or the portal), because
    that is where the choice to publish a price is made. Only agencies
    with 20+ in-scope listings appear by name: below that a percentage is
    an anecdote wearing a denominator.
    """
    per = {}
    for r in rows:
        a = r["agency_name"] or _UNNAMED.get(r["source"], r["source"])
        d = per.setdefault(a, {"n": 0, "priced": 0, "bracket": 0})
        d["n"] += 1
        if r["price_eur"]:
            d["priced"] += 1
        elif r["price_bracket"]:
            d["bracket"] += 1
    return {a: d for a, d in per.items() if d["n"] >= 20}


def opacity_page(rows, data_date, lang):
    it = lang == "it"
    stats = opacity_stats(rows)
    d = str(data_date)[:10]
    if it:
        d = "/".join(reversed(d.split("-")))
    trows = []
    for a, s in sorted(stats.items(), key=lambda x: (x[1]["priced"] / x[1]["n"],
                                                     x[0])):
        pct = round(s["priced"] / s["n"] * 100)
        extra = ""
        if s["bracket"]:
            extra = (f' <span class="lbl">({s["bracket"]} '
                     + ("solo fascia di prezzo" if it else
                        "price bracket only") + ")</span>")
        trows.append(f"<tr><td>{e(a)}</td>"
                     f'<td class="r">{s["n"]}</td>'
                     f'<td class="r"><b>{s["priced"]}</b>{extra}</td>'
                     f'<td class="r">{pct}%</td></tr>')
    table = ('<table class="rows"><tr>'
             + ("<th style='text-align:left'>Agenzia</th>"
                "<th style='text-align:right'>Annunci</th>"
                "<th style='text-align:right'>Con prezzo pubblicato</th>"
                "<th style='text-align:right'>Quota</th>" if it else
                "<th style='text-align:left'>Agency</th>"
                "<th style='text-align:right'>Listings</th>"
                "<th style='text-align:right'>With a published price</th>"
                "<th style='text-align:right'>Share</th>")
             + "</tr>" + "".join(trows) + "</table>")

    if it:
        body = f"""
<h1>Chi pubblica i prezzi, e chi no</h1>
<p class="sub">Un annuncio senza prezzo non è confrontabile con niente.
Questa pagina registra quanto spesso ogni operatore con almeno 20 annunci
in Valtiberina pubblica un prezzo. Dati al {d}.</p>
<div class="block">
  <p style="margin-top:0">Alcuni operatori pubblicano un prezzo su quasi
  ogni annuncio. Altri pubblicano una <b>fascia</b> («meno di
  € 100.000») o nessuna cifra. La fascia non è un prezzo: non permette un
  confronto al metro quadro, e non entra nel nostro indice — non
  trasformiamo mai una fascia in un numero.</p>
  {table}
  <p class="note">Ogni riga è ricalcolata a ogni aggiornamento dai dati
  della pagina <a href="/dati/">dati aperti</a>; i singoli annunci sono
  raggiungibili dalle <a href="/it/comuni/sansepolcro/">pagine dei
  comuni</a>. Un operatore che inizia a pubblicare i prezzi vedrà questa
  tabella cambiare al primo aggiornamento successivo.</p>
</div>
<div class="block">
  <h2>Perché lo registriamo</h2>
  <p style="margin-top:0">Il nostro indice esiste per rendere confrontabili
  cifre pubblicate con basi diverse. Dove la cifra non viene pubblicata
  affatto, non c'è niente da normalizzare: possiamo solo dire che manca,
  e quanto spesso. È un dato di fatto verificabile su ogni annuncio
  collegato, non un giudizio sulle ragioni commerciali di ciascun
  operatore.</p>
  <p class="note"><a href="/it/diritto-di-replica/">Diritto di replica</a>
  · <a href="/it/correzioni/">Segnala un errore</a></p>
</div>"""
    else:
        body = f"""
<h1>Who publishes prices, and who does not</h1>
<p class="sub">A listing without a price cannot be compared with anything.
This page records how often each operator with 20+ Valtiberina listings
publishes one. Data as of {d}.</p>
<div class="block">
  <p style="margin-top:0">Some operators publish a price on nearly every
  listing. Others publish a <b>bracket</b> (“under €100,000”)
  or nothing. A bracket is not a price: it permits no per-square-metre
  comparison, and it does not enter our index — we never turn a bracket
  into a number.</p>
  {table}
  <p class="note">Every row is recomputed on each update from the
  <a href="/dati/">open data</a>; individual listings are reachable from
  the <a href="/it/comuni/sansepolcro/">comune pages</a>. An operator that
  starts publishing prices will see this table change at the next
  update.</p>
</div>
<div class="block">
  <h2>Why we record it</h2>
  <p style="margin-top:0">Our index exists to make figures published on
  different bases comparable. Where the figure is not published at all,
  there is nothing to normalize: we can only say that it is missing, and
  how often. That is a verifiable fact about each linked listing, not a
  judgement about any operator's commercial reasons.</p>
  <p class="note"><a href="/it/diritto-di-replica/">Right of reply</a>
  · <a href="/it/correzioni/">Report an error</a></p>
</div>"""
    title = ("Chi pubblica i prezzi | CasaZebra" if it else
             "Who publishes prices | CasaZebra")
    other = "en" if it else "it"
    return T.shell(title, body, lang,
                   f"/{other}/guide/prezzi-non-pubblicati/",
                   "Quota di annunci con prezzo pubblicato, per agenzia"
                   if it else
                   "Share of listings with a published price, per agency")


# --- Build entry -------------------------------------------------------

def build(out, rows, bands, n_findings, findings_export, data_date):
    """Writes all Phase 1 files under `out`. Returns advertised URLs."""
    urls = []
    write(f"{out}/llms.txt", llms_txt(rows, bands, n_findings, data_date))

    for rel, content in dataset_files(rows, bands, findings_export):
        write(f"{out}/{rel}", content)
    for lang in ("it", "en"):
        # /dati/ is one page; the language pages live beside the files.
        p = f"{out}/dati/index.html" if lang == "it" else f"{out}/en/dati.html"
        write(p, dati_page(rows, bands, n_findings, data_date, lang))
        write(f"{out}/{lang}/correzioni/index.html", correzioni_page(lang))
        write(f"{out}/{lang}/diritto-di-replica/index.html",
              replica_page(lang))
        write(f"{out}/{lang}/guide/prezzi-non-pubblicati/index.html",
              opacity_page(rows, data_date, lang))
        urls += [f"/{lang}/correzioni/", f"/{lang}/diritto-di-replica/",
                 f"/{lang}/guide/prezzi-non-pubblicati/"]
    urls += ["/dati/", "/en/dati.html"]
    return urls
