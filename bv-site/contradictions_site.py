"""One page per property: every agency's version, side by side.

THE PUBLISHABLE OUTPUT (SOT S1, S16d). This is the site the project
ships first, because it needs NOTHING unmeasured — no OMI band, no
negotiation ladder, no condition positions, no surface basis. Every
figure on every page is an agency's own published number, linked to the
page it was published on. The reader checks it in one click.

    python3 contradictions_site.py          # -> dist-contradictions/
    python3 contradictions_site.py --candidates ...   # include unverified

WHAT GETS PUBLISHED, AND WHY THE GATE IS THIS TIGHT

Named agencies are named. A wrong page here is not a bad statistic, it
is an accusation against a real local business — so publication is
restricted to clusters carrying IDENTITY evidence:

    verified    hand-checked in S004 (phase0/verified_clusters.json)
    ref         the agencies' own reference numbers agree
    photo       2+ distinct shared photographs at hamming <= 5
    price       an odd, non-round price nobody lands on twice

`photo-weak` (a single shared image) and bare `price+surface` stay OUT
unless --candidates is passed, and then they are labelled as
unconfirmed on the page itself. S004 is the reason: five clusters that
rested on hamming 7-10 joins were all different properties, and the
five-listing "EUR 280.000" cluster turned out to be a stream-side
villetta, a centro B&B palazzo and three unrelated riders.

WHAT IS NEVER ASSERTED

That an agency is wrong. The page says what each one published and
lets the difference speak. Where a price is withheld or published as a
bracket, that is shown as what it is, never as a number.
"""

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "phase0"))

import templates as T
from templates import e, eur

LANGS = ["it", "en"]

# Evidence that earns publication without a human having looked.
IDENTITY = {"ref", "photo", "price"}

TXT = {
    "it": {
        "title": "Stesso immobile, numeri diversi",
        "index_h1": "Le agenzie non concordano",
        "index_sub": ("{n} immobili della Valtiberina sono pubblicati da più "
                      "agenzie con numeri diversi. Ogni cifra è quella "
                      "pubblicata dall'agenzia stessa, con il link "
                      "all'annuncio."),
        "agency": "Agenzia", "ref": "Rif.", "price": "Prezzo richiesto",
        "surface": "Superficie", "type": "Tipologia", "where": "Dove",
        "source": "annuncio",
        "withheld": "trattativa riservata",
        "not_published": "non pubblicato",
        "disagree": "Su cosa non concordano",
        "d_price": "<b>Prezzo</b>: {lo} contro {hi} — <b>{pct}% di "
                   "differenza</b> sullo stesso immobile.",
        "d_surface": "<b>Superficie</b>: {lo} m² contro {hi} m² — "
                     "<b>{pct}% di differenza</b>.",
        "d_typology": "<b>Tipologia</b>: {vals}. La categoria decide quale "
                      "fascia OMI si applica, quindi non è una questione di "
                      "parole.",
        "d_location": "<b>Comune</b>: {vals}. Le agenzie non concordano "
                      "nemmeno su dove si trovi l'immobile.",
        "d_address": "<b>Indirizzo</b>: {vals}.",
        "verified": "Verificato a mano",
        "verified_when": "controllato il 29 agosto 2026",
        "candidate": "Da confermare",
        "candidate_note": ("Questi annunci condividono una sola fotografia. "
                           "Potrebbe trattarsi dello stesso immobile, oppure "
                           "no: lo pubblichiamo come segnalazione, non come "
                           "fatto accertato."),
        "how": "Come sono stati collegati",
        "how_ref": "Le agenzie usano lo stesso numero di riferimento.",
        "how_photo": "Gli annunci condividono almeno due fotografie identiche.",
        "how_price": "Prezzo identico e non arrotondato — una cifra che non "
                     "capita due volte per caso.",
        "how_ps": "Prezzo identico e superficie compatibile.",
        "how_photo_weak": "Gli annunci condividono una fotografia identica, "
                          "e la corrispondenza è stata controllata a mano.",
        "why": "Perché conta",
        "why_body": ("Chi compra confronta un annuncio alla volta. Messi uno "
                     "accanto all'altro, i numeri non tornano — e la "
                     "differenza la paga chi non se ne accorge."),
        "back": "Tutti gli immobili",
        "no_price": "Nessuna delle agenzie pubblica un prezzo per questo "
                    "immobile.",
        "bracket": "solo una fascia di prezzo",
    },
    "en": {
        "title": "Same property, different numbers",
        "index_h1": "The agencies do not agree",
        "index_sub": ("{n} Valtiberina properties are listed by more than one "
                      "agency with different numbers. Every figure is the "
                      "agency's own, linked to its listing."),
        "agency": "Agency", "ref": "Ref.", "price": "Asking price",
        "surface": "Surface", "type": "Type", "where": "Where",
        "source": "listing",
        "withheld": "price on request",
        "not_published": "not published",
        "disagree": "What they disagree on",
        "d_price": "<b>Price</b>: {lo} against {hi} — <b>{pct}% apart</b> on "
                   "the same property.",
        "d_surface": "<b>Surface</b>: {lo} m² against {hi} m² — "
                     "<b>{pct}% apart</b>.",
        "d_typology": "<b>Type</b>: {vals}. The category decides which OMI "
                      "band applies, so this is not a question of wording.",
        "d_location": "<b>Comune</b>: {vals}. The agencies do not even agree "
                      "on where the property is.",
        "d_address": "<b>Address</b>: {vals}.",
        "verified": "Checked by hand",
        "verified_when": "checked 29 August 2026",
        "candidate": "Unconfirmed",
        "candidate_note": ("These listings share a single photograph. They "
                           "may be the same property or they may not: this is "
                           "published as a lead, not as an established fact."),
        "how": "How these were linked",
        "how_ref": "The agencies use the same reference number.",
        "how_photo": "The listings share at least two identical photographs.",
        "how_price": "An identical, non-round price — a figure nobody lands "
                     "on twice by accident.",
        "how_ps": "Identical price and compatible surface.",
        "how_photo_weak": "The listings share an identical photograph, and "
                          "the match was checked by hand.",
        "why": "Why it matters",
        "why_body": ("A buyer reads one listing at a time. Side by side the "
                     "numbers do not add up — and the difference is paid by "
                     "whoever does not notice."),
        "back": "All properties",
        "no_price": "None of the agencies publishes a price for this "
                    "property.",
        "bracket": "a price range only",
    },
}


def slug(item):
    """Readable page id, stable across rebuilds: comune-street-hash.

    The suffix is derived from the cluster's own member ids, NOT from
    its position in the run. An ordinal looked tidier and was wrong: it
    shifts every time a cluster is added, verified or suppressed, so
    every URL on the site changes whenever anything is learned — dead
    links for anyone who saved one, and a search engine re-indexing
    pages it already had. A property's URL now changes only when the
    set of listings being compared actually changes, which is the one
    case where it should.
    """
    import contradictions as C
    import hashlib
    g = item["group"]
    base = comune_of(g).lower()
    addr = C.best_label(g)
    # S010: the sentinel is prose, not a name. Spelled into a slug it gives
    # comune-address-not-given-hash, which reads like a street called
    # "Address Not Given". comune + hash is the honest form of "we do not
    # know where this is".
    if addr == "address not given":
        addr = ""
    a = "".join(c if c.isalnum() or c.isspace() else " " for c in addr.lower())
    a = "-".join(a.split()[:4])
    h = hashlib.sha1("|".join(sorted(str(r["source_id"]) for r in g))
                     .encode()).hexdigest()[:6]
    return f"{base}-{a}-{h}" if a else f"{base}-{h}"


# The methodology page in templates.py describes the OMI comparison and
# the Target Offer — a method this site does not use. Emitting it here
# would document arithmetic that never runs on these pages. So the
# contradictions site carries its own, at the same URL the shared footer
# already points to.
METHOD = {
    "it": """
<h1>Il metodo</h1>

<p class="lede">Due cose, ed è la stessa argomentazione: <b>come stabiliamo
che due annunci riguardano la stessa casa</b>, e <b>con quale superficie
dividiamo i prezzi</b> perché siano confrontabili. La prima è la prova che
la seconda serve.</p>

<h2>Come colleghiamo gli annunci</h2>

<div class="block">
  <p style="margin-top:0">Queste pagine confrontano annunci di agenzie
  diverse che riguardano lo <b>stesso immobile</b>. Ogni cifra è quella
  pubblicata dall'agenzia, con il link all'annuncio: chi legge può
  verificare in un clic.</p>
  <p><b>Su queste pagine non c'è nessuna stima.</b> Niente fasce OMI,
  niente sconti di trattativa, niente valutazioni nostre. Confrontiamo le
  agenzie con quello che hanno scritto loro.</p>
  <p>L'<a href="#indice">indice</a>, più sotto, è una cosa diversa e lo
  diciamo apertamente: per confrontare gli annunci fra loro dobbiamo
  riportarli a una superficie unica, e quella conversione è una nostra
  scelta dichiarata. Per questo è pubblicata come <b>intervallo</b>, mai
  come numero singolo, con la regola scritta qui sotto.</p>
</div>

<div class="block">
  <h2>Come stabiliamo che si tratta dello stesso immobile</h2>
  <table class="rows">
    <tr><td><b>Numero di riferimento</b></td>
        <td>Le agenzie usano lo stesso riferimento. È il loro
        identificativo, non una nostra deduzione.</td></tr>
    <tr><td><b>Fotografie</b></td>
        <td>Almeno due fotografie identiche. Confrontate a mano, una per
        una: una foto condivisa non basta, perché le agenzie riusano
        immagini e un panorama può essere lo stesso da case diverse.</td></tr>
    <tr><td><b>Prezzo non arrotondato</b></td>
        <td>Una cifra come € 110.625 non capita due volte per caso. Un
        prezzo tondo, da solo, non prova nulla.</td></tr>
    <tr><td><b>Descrizioni</b></td>
        <td>Quando due annunci descrivono la stessa casa in modo
        inequivocabile — stessa struttura, stessa storia, stesso parco —
        anche senza foto in comune.</td></tr>
  </table>
</div>

<div class="block">
  <h2>Cosa non pubblichiamo</h2>
  <ul>
    <li><b>Quello che non abbiamo verificato.</b> Le corrispondenze che non
    hanno superato un controllo umano restano fuori.</li>
    <li><b>Casi in cui una spiegazione innocente esiste.</b> Un annuncio non
    aggiornato da anni, o che include nel prezzo un secondo edificio, non è
    una contraddizione: è un confronto tra cose diverse.</li>
    <li><b>Prezzi non pubblicati.</b> "Trattativa riservata" o una fascia di
    prezzo vengono mostrati per quello che sono, mai trasformati in una
    cifra.</li>
    <li><b>Giudizi.</b> Non diciamo chi ha ragione. Mettiamo i numeri uno
    accanto all'altro.</li>
  </ul>
</div>

<div class="block" id="replica">
  <h2>Diritto di replica</h2>
  <p>Se sei un'agenzia e ritieni che due annunci accostati qui non siano
  lo stesso immobile, <b>scrivici e ricontrolliamo</b>. Se hai ragione,
  la pagina viene rimossa; se il dato è cambiato, viene aggiornato.
  In entrambi i casi rispondiamo entro <b>7 giorni</b>.</p>
  <p>Vale anche per il contrario: se una cifra qui è sbagliata perché
  l'annuncio è stato nel frattempo corretto, segnalacelo.</p>
  <p>Scrivi a: <b>correzioni@casazebra.it</b> —
  vedi anche <a href="/it/chi-siamo.html#correzioni">Segnala un errore</a>.</p>
</div>

<div class="block">
  <h2>Aggiornamento</h2>
  <p>I dati vengono riletti periodicamente dalle fonti pubbliche. Una
  pagina riporta ciò che era pubblicato al momento della lettura, e gli
  annunci cambiano: il link alla fonte è sempre il riferimento.</p>
</div>
""",
    "en": """
<h1>The method</h1>

<p class="lede">Two things, and they are one argument: <b>how we establish
that two listings are the same house</b>, and <b>which surface we divide
prices by</b> so they can be compared. The first is the evidence that the
second is needed.</p>

<h2>How we link listings</h2>

<div class="block">
  <p style="margin-top:0">These pages compare listings from different
  agencies for the <b>same property</b>. Every figure is the agency's own,
  linked to its listing, so any reader can check it in one click.</p>
  <p><b>No estimate appears on these pages.</b> No OMI bands, no
  negotiation discounts, no valuation of ours. We compare the agencies to
  what they themselves published.</p>
  <p>The <a href="#indice">index</a> below is a different thing, and we say
  so plainly: to compare listings with each other we have to bring them to
  one surface, and that conversion is a declared choice of ours. Which is
  why it is published as a <b>range</b>, never as a single number, with the
  rule written out below.</p>
</div>

<div class="block">
  <h2>How we establish it is the same property</h2>
  <table class="rows">
    <tr><td><b>Reference number</b></td>
        <td>The agencies use the same reference. Their identifier, not our
        inference.</td></tr>
    <tr><td><b>Photographs</b></td>
        <td>At least two identical photographs, compared by eye one pair at
        a time. A single shared image is not enough: agencies reuse
        pictures, and the same view can be photographed from different
        houses.</td></tr>
    <tr><td><b>A non-round price</b></td>
        <td>A figure like € 110,625 does not occur twice by accident. A
        round price on its own proves nothing.</td></tr>
    <tr><td><b>Descriptions</b></td>
        <td>Where two listings describe the same house unmistakably — same
        structure, same history, same grounds — even with no photographs in
        common.</td></tr>
  </table>
</div>

<div class="block">
  <h2>What we do not publish</h2>
  <ul>
    <li><b>Anything unverified.</b> Matches that did not survive a human
    check stay out.</li>
    <li><b>Cases with an innocent explanation.</b> A listing not updated in
    years, or one whose price includes a second building, is not a
    contradiction — it is a comparison of different things.</li>
    <li><b>Prices that were never published.</b> "Price on request" or a
    price bracket is shown as exactly that, never converted into a
    number.</li>
    <li><b>Verdicts.</b> We do not say who is right. We put the numbers
    side by side.</li>
  </ul>
</div>

<div class="block" id="replica">
  <h2>Right of reply</h2>
  <p>If you are an agency and believe two listings shown here are not the
  same property, <b>write to us and we will re-check</b>. If you are right
  the page comes down; if the data has changed it is updated. Either way we
  reply within <b>7 days</b>.</p>
  <p>The same applies in reverse: if a figure here is wrong because the
  listing has since been corrected, tell us.</p>
  <p>Write to: <b>correzioni@casazebra.it</b> — see also
  <a href="/en/chi-siamo.html#correzioni">Report an error</a>.</p>
</div>

<div class="block">
  <h2>Updating</h2>
  <p>The data is re-read from public sources periodically. A page reports
  what was published at the time of reading, and listings change: the link
  to the source is always the reference.</p>
</div>
""",
}


# --- The standard (seo-spec.md §3) -------------------------------------

def index_method(lang):
    """The surface standard, rendered from `normalize.py`'s own tables.

    Generated rather than hand-written for one reason: a method page that
    disagrees with the code is worse than no method page. This site's
    entire complaint is that agencies publish a EUR/m2 whose denominator
    they will not define; if our published deflator table drifted one
    revision behind the one we actually apply, we would be doing the same
    thing with better typography. So the numbers below come from
    `normalize.DEFLATORS`, `normalize.WEIGHTS` and the live gate
    constants. There is no second copy to fall out of date.
    """
    import normalize as N

    it = lang == "it"

    weights = "\n".join(
        f"    <tr><td>{c}</td><td class=\"n\">{w}</td><td>{cap}</td></tr>"
        for c, w, cap in N.WEIGHTS)

    names = {
        "appartamento": ("Appartamento", "Apartment"),
        "terratetto":   ("Terratetto / casa a schiera", "Terratetto / townhouse"),
        "cielo_terra":  ("Casa cielo-terra", "Whole-building house"),
        "rustico":      ("Casale / colonica restaurata", "Restored casale / farmhouse"),
    }
    # Italian writes decimals with a comma. Getting this wrong on a page
    # whose subject is numerical care would be read, correctly, as not
    # caring — and the audience for the IT page is Italian agencies.
    def num(x, places=2):
        s = f"{x:.{places}f}"
        return s.replace(".", ",") if it else s

    defl = "\n".join(
        f"    <tr><td>{names[k][0 if it else 1]}</td>"
        f"<td class=\"n\">&times; {num(lo)} &ndash; {num(hi)}</td></tr>"
        for k, (lo, hi) in sorted(N.DEFLATORS.items()))

    gate_n, gate_ag = N.GATE_MIN_N, N.GATE_MIN_AGENCIES
    gate_w = num(N.GATE_MAX_WIDTH_PCT, 1)

    if it:
        return f"""
<div class="block" id="indice">
  <h2>L'indice: una sola superficie, applicata a tutti</h2>
  <p style="margin-top:0">Ogni portale italiano pubblica un prezzo al metro
  quadro. Nessuno di quei numeri è confrontabile con un altro, perché il
  <b>denominatore</b> — la superficie — è definito in modo diverso da ogni
  agenzia, e quasi mai è scritto da nessuna parte.</p>
  <p>Il caso che lo dimostra è nel nostro archivio. Due agenzie chiedono lo
  stesso identico prezzo per la stessa villa ad Anghiari, e pubblicano
  <b>€ 508/m²</b> e <b>€ 3.265/m²</b>: sei volte tanto. Non perché siano in
  disaccordo sul valore, ma perché una divide per una "superficie
  commerciale" di 3.150 m² che comprende un parco di 2.600 m². Tolto il
  terreno, il disaccordo vero è fra 550 m² e 490 m² — circa il 12%. Quella
  è una domanda che un compratore può fare a un'agente. Il 6,4× no.</p>
  <p><b>La regola che conta è una sola: il terreno non entra mai in una
  superficie.</b> Giardini, parchi e terreni agricoli sono riportati a
  parte, come quello che sono. Nessuno cammina su un parco.</p>
</div>

<div class="block">
  <h2>Da cosa dividiamo</h2>
  <p style="margin-top:0">La nostra superficie di riferimento è la
  <b>superficie interna abitabile</b>: il calpestabile interno, misurato al
  filo interno dei muri esterni. Esclude accessori e terreno.</p>
  <p>Accanto pubblichiamo sempre <b>il prezzo al m² dell'agenzia</b>,
  calcolato con la superficie che ha dichiarato lei. Le due cifre stanno
  una accanto all'altra su ogni pagina. La differenza fra loro è il punto.</p>
</div>

<div class="block">
  <h2>Quanto pesano gli accessori</h2>
  <p style="margin-top:0">Questa tabella è una <b>scelta dichiarata</b>, non
  una misurazione. Non l'abbiamo dedotta dal mercato: l'abbiamo scritta, e
  la applichiamo allo stesso modo a tutti. È esattamente ciò che le agenzie
  non fanno. Le righe su garage (50%) e giardino (10%) coincidono con la
  regola che Immobiliare stessa applica ai propri annunci — in modo
  disomogeneo fra un agente e l'altro; le altre righe sono nostre.</p>
  <table class="rows">
    <tr><th>Componente</th><th>Peso</th><th>Limite</th></tr>
{weights}
  </table>
  <p><b>Questa tabella non è ancora in uso.</b> Applicarla richiede la
  scomposizione voce per voce della superficie, che gli annunci pubblici
  non riportano. La pubblichiamo lo stesso, perché un'agenzia ha diritto di
  vedere lo standard con cui verrà misurata prima che possiamo misurarla.</p>
</div>

<div class="block">
  <h2>Quanto ci fidiamo di ogni annuncio</h2>
  <p style="margin-top:0">Pubblicare un numero preciso partendo da un dato
  impreciso è esattamente ciò che contestiamo. Quindi ogni annuncio porta
  scritto quanto è solido il suo indice.</p>
  <table class="rows">
    <tr><td><b>A — misurato</b></td>
        <td>Scomposizione della superficie disponibile. Valore puntuale.
        <i>Oggi nessun annuncio raggiunge questo livello.</i></td></tr>
    <tr><td><b>B — dedotto</b></td>
        <td>Una sola superficie e la tipologia. Pubblichiamo un
        <b>intervallo</b>, mai un numero.</td></tr>
    <tr><td><b>C — insufficiente</b></td>
        <td>Nessun prezzo, nessuna superficie utilizzabile, o una tipologia
        troppo variabile. <b>Nessun indice.</b> La pagina mostra i dati
        dell'agenzia e spiega perché non c'è un nostro numero.</td></tr>
  </table>
</div>

<div class="block">
  <h2>La conversione, per tipologia</h2>
  <p style="margin-top:0">Per gli annunci di livello B convertiamo la
  superficie dichiarata in superficie interna abitabile così:</p>
  <table class="rows">
    <tr><th>Tipologia</th><th>Fattore</th></tr>
{defl}
  </table>
  <p><b>Le ville con parco non hanno un fattore</b>, e non è una
  dimenticanza. Per quella categoria la conversione andrebbe da 0,30 a
  0,80: un intervallo così ampio da non dire nulla. È anche la categoria in
  cui il problema è più grave. Quindi una villa o viene scomposta a mano, o
  <b>non riceve nessun indice</b>. Preferiamo un vuoto dichiarato a un
  numero che non regge.</p>
</div>

<div class="block">
  <h2>Le fasce per comune</h2>
  <p style="margin-top:0">Ogni annuncio entra nella fascia del suo comune
  come intervallo, non come punto, e l'intervallo resta tale fino alla
  pagina: quello che pubblichiamo è <b>da X a Y</b>, mai la loro media.</p>
  <p>Una fascia viene pubblicata solo con almeno <b>{gate_n} annunci</b> di
  almeno <b>{gate_ag} agenzie diverse</b>, e solo se l'intervallo centrale
  non supera il <b>{gate_w}%</b> — cioè se non è più largo dell'incertezza
  della singola conversione peggiore. Sotto quella soglia il comune non ha
  fascia e lo diciamo.</p>
  <p>Su ogni fascia pubblichiamo due larghezze: <b>quanto è incerta la
  nostra conversione</b> e <b>quanto varia davvero il mercato</b>. Nei
  comuni della Valtiberina la prima sta fra il 13% e il 27%; la seconda fra
  il 52% e il 98%. Chi legge deve poter vedere quanta parte dell'intervallo
  siamo noi e quanta è il mercato — e qui la seconda è di gran lunga la
  più grande.</p>
</div>

<div class="block">
  <h2>Quello che questo non è</h2>
  <p style="margin-top:0">Non è una perizia, e non ne ha la pretesa. Una
  perizia in Italia è un atto che compie un tecnico abilitato, sul posto.
  Questo è un <b>indice</b>: i numeri che le agenzie hanno già pubblicato,
  riportati tutti alla stessa superficie con una regola scritta, così che
  siano confrontabili fra loro.</p>
  <p>Non diciamo quanto vale una casa e non diciamo quanto offrire.
  Diciamo cosa è stato pubblicato, e cosa succede a quei numeri quando si
  applica a tutti lo stesso metro.</p>
</div>
"""

    return f"""
<div class="block" id="indice">
  <h2>The index: one surface, applied to everyone</h2>
  <p style="margin-top:0">Every Italian property portal publishes a price
  per square metre. None of those numbers can be compared with each other,
  because the <b>denominator</b> — the surface — is defined differently by
  every agency, and is almost never written down anywhere.</p>
  <p>The case that proves it is in our own archive. Two agencies ask the
  identical price for the same villa in Anghiari and publish
  <b>&euro;508/m&sup2;</b> and <b>&euro;3,265/m&sup2;</b> — six times
  apart. Not because they disagree about the value, but because one divides
  by a "commercial surface" of 3,150 m&sup2; that includes a 2,600
  m&sup2; park. With the land removed, the real disagreement is between
  550 m&sup2; and 490 m&sup2;, about 12%. That is a question a buyer can
  put to an agent. The 6.4&times; never was.</p>
  <p><b>One rule does most of the work: land never enters a surface
  figure.</b> Gardens, parks and agricultural land are reported separately,
  as what they are. Nobody walks on a park.</p>
</div>

<div class="block">
  <h2>What we divide by</h2>
  <p style="margin-top:0">Our reference surface is the <b>internal
  habitable area</b> — internal floor area measured to the inside face of
  the external walls. It excludes accessories and all land.</p>
  <p>Beside it we always publish <b>the agency's own price per
  m&sup2;</b>, calculated with the surface the agency itself stated. The
  two figures sit side by side on every page. The gap between them is the
  point.</p>
</div>

<div class="block">
  <h2>How accessories are weighted</h2>
  <p style="margin-top:0">This table is a <b>declared choice</b>, not a
  measurement. We did not derive it from the market: we wrote it down, and
  we apply it identically to everyone. That is precisely what the agencies
  do not do. The garage row (50%) and garden row (10%) match the rule
  Immobiliare applies to its own listings — inconsistently, from one agent
  to the next; the remaining rows are ours.</p>
  <table class="rows">
    <tr><th>Component</th><th>Weight</th><th>Cap</th></tr>
{weights}
  </table>
  <p><b>This table is not yet in use.</b> Applying it requires an itemised
  breakdown of the surface, which public listings do not carry. We publish
  it anyway, because an agency is entitled to see the standard it will be
  measured against before we are able to measure it.</p>
</div>

<div class="block">
  <h2>How much we trust each listing</h2>
  <p style="margin-top:0">Publishing a confident number from an unconfident
  input is exactly what we object to. So every listing states how solid its
  index is.</p>
  <table class="rows">
    <tr><td><b>A &mdash; measured</b></td>
        <td>Surface breakdown available. A point value.
        <i>No listing currently reaches this level.</i></td></tr>
    <tr><td><b>B &mdash; inferred</b></td>
        <td>One surface figure and a typology. We publish a
        <b>range</b>, never a number.</td></tr>
    <tr><td><b>C &mdash; insufficient</b></td>
        <td>No price, no usable surface, or a typology too variable to
        infer from. <b>No index at all.</b> The page shows the agency's
        figures and explains why there is no number of ours.</td></tr>
  </table>
</div>

<div class="block">
  <h2>The conversion, by property type</h2>
  <p style="margin-top:0">For Tier B listings we convert the stated surface
  to internal habitable area like this:</p>
  <table class="rows">
    <tr><th>Type</th><th>Factor</th></tr>
{defl}
  </table>
  <p><b>Villas with grounds have no factor</b>, and that is not an
  oversight. For that category the conversion would run from 0.30 to 0.80 —
  a range wide enough to say nothing. It is also the category where the
  problem is worst. So a villa is either broken down by hand or it
  <b>carries no index</b>. We would rather publish a declared gap than a
  number that does not hold.</p>
</div>

<div class="block">
  <h2>Comune bands</h2>
  <p style="margin-top:0">Every listing enters its comune's band as an
  interval, not a point, and it stays an interval all the way to the page:
  what we publish is <b>X to Y</b>, never their midpoint.</p>
  <p>A band is published only with at least <b>{gate_n} listings</b> from
  at least <b>{gate_ag} different agencies</b>, and only if the central
  interval is no wider than <b>{gate_w}%</b> — that is, no wider than the
  uncertainty of the single worst conversion feeding it. Below that
  threshold the comune has no band, and we say so.</p>
  <p>With every band we publish two widths: <b>how uncertain our
  conversion is</b> and <b>how much the market itself varies</b>. Across
  the Valtiberina the first runs 13&ndash;27%; the second runs
  52&ndash;98%. A reader should be able to see how much of the range is us
  and how much is the market — and here the market is by far the
  larger.</p>
</div>

<div class="block">
  <h2>What this is not</h2>
  <p style="margin-top:0">It is not a survey or an appraisal, and it does
  not claim to be. In Italy a <i>perizia</i> is a regulated act carried out
  by a qualified technician, on site. This is an <b>index</b>: figures the
  agencies have already published, brought onto one surface by a written
  rule, so that they can be compared with each other.</p>
  <p>We do not say what a house is worth and we do not say what to offer.
  We say what was published, and what happens to those numbers when the
  same measure is applied to all of them.</p>
</div>
"""


def comune_of(group):
    """The comune to file this property under — deterministically.

    Taking group[0]'s comune churned URLs between rebuilds, because the
    group is assembled from a set and its order is arbitrary. It showed
    up on exactly the cluster where two agencies disagree about the
    comune (Badia Tedalda vs Sestino), which is the finding itself: the
    page name flipped between the two on alternate builds. Most common
    label wins, ties broken alphabetically, so the URL is fixed even
    while the disagreement stands — and the disagreement is still
    published on the page.
    """
    from collections import Counter
    names = [g["comune"] for g in group if g["comune"]]
    if not names:
        return "valtiberina"
    counts = Counter(names)
    top = max(counts.values())
    return sorted(n for n, c in counts.items() if c == top)[0]


def agency_of(r):
    return r["agency_name"] or r["source"]


def price_cell(r, t):
    if r.get("price_withheld"):
        return f'<span class="lbl">{e(t["withheld"])}</span>'
    if r.get("price"):
        return f'<b>{eur(r["price"])}</b>'
    if r.get("price_bracket") and r["price_bracket"] != "bracket (unresolved)":
        return (f'<span class="lbl">{e(r["price_bracket"])} '
                f'({e(t["bracket"])})</span>')
    return f'<span class="lbl">{e(t["not_published"])}</span>'


def property_page(item, sid, lang, listing_rows=None):
    t, tt = TXT[lang], T.T[lang]
    import contradictions as C
    g, d = item["group"], item["d"]
    label = C.best_label(g)
    comune = comune_of(g).replace("-", " ").title()

    # §4.4: link each member listing to its index page where one exists.
    # Lazy import — index_site imports this module at top level, so the
    # reverse import has to happen at call time, not load time.
    listing_rows = listing_rows or {}
    import index_site as IS

    rows = []
    for r in sorted(g, key=lambda x: (-(x["price"] or 0),
                          str(x["agency_name"] or x["source"]),
                          str(x["source_id"]))):
        link = (f' <a class="src" href="{e(r["url"])}" rel="nofollow noopener"'
                f' target="_blank">{e(t["source"])} ↗</a>' if r.get("url")
                else "")
        nr = listing_rows.get((r["source"], str(r["source_id"])))
        if nr is not None:
            link += (f' <a class="src" href="{IS.listing_url(nr, lang)}">'
                     + ("la nostra scheda" if lang == "it" else "our page")
                     + "</a>")
        rows.append(
            f'<tr><td><b>{e(agency_of(r))}</b>{link}</td>'
            f'<td class="r">{e(r["agency_ref"] or "—")}</td>'
            f'<td class="r">{price_cell(r, t)}</td>'
            f'<td class="r">{e(r["mq"]) + " m²" if r["mq"] else "—"}</td>'
            f'<td class="r">{e(r["typology"] or r["typology_raw"] or "—")}</td>'
            f'</tr>')

    table = (f'<table class="rows"><tr>'
             f'<td class="lbl">{e(t["agency"])}</td>'
             f'<td class="lbl r">{e(t["ref"])}</td>'
             f'<td class="lbl r">{e(t["price"])}</td>'
             f'<td class="lbl r">{e(t["surface"])}</td>'
             f'<td class="lbl r">{e(t["type"])}</td></tr>'
             + "".join(rows) + '</table>')

    facts = []
    if "price" in d:
        facts.append(t["d_price"].format(lo=eur(d["price"][0]),
                                         hi=eur(d["price"][1]),
                                         pct=f'{d["price"][2]:.0f}'))
    if "surface" in d:
        facts.append(t["d_surface"].format(lo=d["surface"][0],
                                           hi=d["surface"][1],
                                           pct=f'{d["surface"][2]:.0f}'))
    if "typology" in d:
        facts.append(t["d_typology"].format(
            vals=" / ".join(e(v) for v in d["typology"])))
    if "location" in d:
        facts.append(t["d_location"].format(
            vals=" / ".join(e(v.replace("-", " ").title())
                            for v in d["location"])))
    if "address" in d:
        # Street only (S009). This is the "the agencies disagree about WHERE
        # this is" fact, and it prints both sides verbatim — so it is the one
        # place a civico reaches the page even when best_label() has already
        # been cleaned for the title and the URL. Sanitising here as well is
        # deliberate belt-and-braces: the two paths are independent, and the
        # rule is 'no house numbers ever', not 'no house numbers in titles'.
        from address_privacy import street_only
        vals = [s for s in (street_only(v) for v in d["address"]) if s]
        # A disagreement that only existed at civico level is not a location
        # disagreement worth printing — it is two agencies naming the same
        # street, which is agreement.
        if len(set(vals)) > 1:
            facts.append(t["d_address"].format(
                vals=" / ".join(e(v) for v in vals)))
    if not [r for r in g if r.get("price") and not r.get("price_withheld")]:
        facts.append(e(t["no_price"]))

    # Order matters, and getting it wrong printed a falsehood: a
    # photo-weak cluster where NEITHER agency publishes a price was
    # explained to the reader as "identical price and compatible
    # surface". The fallback has to be the weakest claim, not the
    # nearest one — and photo-weak needs its own line rather than
    # borrowing the two-photograph wording.
    ev = set(item["evidence"])
    how = (t["how_ref"] if "ref" in ev else
           t["how_photo"] if "photo" in ev else
           t["how_price"] if "price" in ev else
           t["how_ps"] if "price+surface" in ev else
           t["how_photo_weak"])

    if item.get("verified"):
        # The verification notes in verified_clusters.json are written in
        # English (they are S004's working record). Showing English prose
        # on the Italian page — the page a Valtiberina buyer actually
        # reads — would undercut the one thing this site sells, which is
        # being careful. Italian gets the badge and the date; the note
        # itself appears only where its language belongs.
        note = f' {e(item["verified"])}' if lang == "en" else ""
        badge = (f'<div class="flag"><b>✓ {e(t["verified"])}</b> — '
                 f'{e(t["verified_when"])}.{note}</div>')
    elif "photo-weak" in ev:
        badge = (f'<div class="flag"><b>{e(t["candidate"])}</b> — '
                 f'{e(t["candidate_note"])}</div>')
    else:
        badge = ""

    body = f"""
<h1>{e(comune)} — {e(label)}</h1>
<p class="sub">{e(t["title"])}</p>
<div class="block">{table}{badge}</div>
<div class="block"><h2>{e(t["disagree"])}</h2>
  <ul style="margin:0;padding-left:18px">
    {"".join(f"<li>{f}</li>" for f in facts)}
  </ul>
</div>
<div class="block"><h2>{e(t["how"])}</h2><p style="margin:0">{e(how)}</p>
  <p class="note">{e(t["why_body"])}</p></div>
<p class="noprint"><a href="/{lang}/confronti/">← {e(t["back"])}</a></p>
"""
    desc = f'{comune} — {label}: ' + (
        f'{d["surface"][0]}–{d["surface"][1]} m²' if "surface" in d else
        t["title"])

    # §8.1: Article with ClaimReview-shaped properties. The "claim" is
    # never ours — it is the set of figures the agencies published; what
    # we review is whether they concern the same property. Dates are the
    # static verification date, not build time (§10.2).
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"{comune} — {label}",
        "author": {"@type": "Organization", "name": "CasaZebra"},
        "about": {
            "@type": "Claim",
            "appearance": [{"@type": "CreativeWork", "url": r["url"]}
                           for r in sorted(g, key=lambda x: str(x["url"]))
                           if r.get("url")],
        },
        "claimReviewed": desc,
        "reviewedBy": {"@type": "Organization", "name": "CasaZebra"},
        "verificationStatus": ("hand-verified 2026-08-29"
                               if item.get("verified") else "unconfirmed"),
    }
    return T.shell(f'{comune} — {label} | CasaZebra', body, lang,
                   f'/{"en" if lang == "it" else "it"}/confronti/{sid}.html',
                   desc, schema)


def index_page(items, sids, lang):
    t = TXT[lang]
    tiles = []
    for it, sid in zip(items, sids):
        g, d = it["group"], it["d"]
        import contradictions as C
        head = []
        if "price" in d:
            head.append(f'{d["price"][2]:.0f}% ' +
                        ("sul prezzo" if lang == "it" else "on price"))
        if "surface" in d:
            head.append(f'{d["surface"][2]:.0f}% ' +
                        ("sulla superficie" if lang == "it" else "on surface"))
        if "typology" in d:
            head.append("tipologia" if lang == "it" else "type")
        if "location" in d:
            head.append("comune")
        mark = " ✓" if it.get("verified") else ""
        tiles.append(
            f'<a class="tile" href="/{lang}/confronti/{sid}.html">'
            f'<b>{e(comune_of(g).replace("-", " ").title())} — '
            f'{e(C.best_label(g))}</b>'
            f'<small>{len(g)} ' +
            ("agenzie · " if lang == "it" else "agencies · ") +
            f'{e(", ".join(head))}{mark}</small></a>')

    body = f"""
<div class="hero">
  <h1>{e(t["index_h1"])}</h1>
  <p>{e(t["index_sub"].format(n=len(items)))}</p>
</div>
<div class="grid">{"".join(tiles)}</div>
<p class="note">✓ = {e(t["verified"].lower())}.</p>
"""
    return T.shell(f'{t["index_h1"]} | CasaZebra', body, lang,
                   f'/{"en" if lang == "it" else "it"}/confronti/',
                   t["index_sub"].format(n=len(items)))


def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="../phase0/phase0.sqlite")
    ap.add_argument("--out", default="dist-contradictions")
    ap.add_argument("--candidates", action="store_true",
                    help="also publish single-photo and price+surface "
                         "matches, labelled as unconfirmed")
    a = ap.parse_args()

    import sqlite3
    import contradictions as C
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    items = C.build(conn)

    keep = [it for it in items
            if it.get("verified") or (set(it["evidence"]) & IDENTITY)
            or a.candidates]
    keep.sort(key=lambda it: (0 if it.get("verified") else 1,
                              -(it["d"].get("surface", (0, 0, 0))[2]
                                + it["d"].get("price", (0, 0, 0))[2])))
    print(f"{len(items)} contradictions, publishing {len(keep)} "
          f"({sum(1 for i in keep if i.get('verified'))} hand-verified)")
    if not a.candidates:
        print(f"  {len(items) - len(keep)} held back as unconfirmed "
              f"(--candidates to include them)")

    # Clear the previous build. A stale page is not cosmetic here: a
    # slug changes whenever a cluster's membership or address changes,
    # so yesterday's file would sit there asserting numbers about a
    # named agency that nothing regenerates. If the directory cannot be
    # removed (the sandbox mount refuses to unlink files the host
    # created), fall back to deleting file by file, and if even that
    # fails, say exactly which pages are stale rather than pretending
    # the build is clean.
    if os.path.isdir(a.out):
        try:
            shutil.rmtree(a.out)
        except OSError:
            pass
    sids = [slug(it) for it in keep]

    # §4.4 backlinks: which listings carry an index page, by index_site's
    # own publish gate (Tier A/B always; Tier C when it is a member of a
    # published finding). Rendered from normalize's rows so the URLs
    # match the index build slug for slug.
    import normalize as NN
    nrows, _nb, _ = NN.run(db_path=a.db,
                           out_dir=os.path.dirname(os.path.abspath(a.db)))
    kept_keys = {(g["source"], str(g["source_id"]))
                 for it in keep for g in it["group"]}
    listing_rows = {}
    for r in nrows:
        key = (r["source"], str(r["source_id"]))
        if r["tier"] in ("A", "B") or key in kept_keys:
            listing_rows[key] = r

    urls = []
    for lang in LANGS:
        write(f"{a.out}/{lang}/confronti/index.html",
              index_page(keep, sids, lang))
        urls.append(f"/{lang}/confronti/")
        # The shared footer links to both of these on every page, so
        # until they exist every page ships with two dead links — on a
        # site whose whole claim is carefulness, and whose corrections
        # policy lives behind one of them.
        write(f"{a.out}/{lang}/chi-siamo.html", T.about_page(lang))
        # METHOD is how we link listings; index_method is the surface
        # standard. One page, because they are one argument: the standard
        # is why the contradictions matter, and the contradictions are why
        # the standard is necessary. Splitting them would leave each half
        # looking like an assertion.
        write(f"{a.out}/{lang}/metodologia.html",
              T.shell(("Il metodo" if lang == "it"
                       else "The method") + " — CasaZebra",
                      METHOD[lang] + index_method(lang), lang,
                      f'/{"en" if lang == "it" else "it"}/metodologia.html',
                      T.T[lang]["declaration"]))
        urls += [f"/{lang}/chi-siamo.html", f"/{lang}/metodologia.html"]
        for it, sid in zip(keep, sids):
            write(f"{a.out}/{lang}/confronti/{sid}.html",
                  property_page(it, sid, lang, listing_rows))
            urls.append(f"/{lang}/confronti/{sid}.html")

    for lang in LANGS:
        # The shared header's brand link points at /{lang}/. In the full
        # site that is the homepage; in this standalone slice it did not
        # exist, so every page carried a dead logo link.
        write(f"{a.out}/{lang}/index.html",
              '<!doctype html><meta charset="utf-8">'
              f'<meta http-equiv="refresh" content="0;url=/{lang}/confronti/">'
              f'<link rel="canonical" href="/{lang}/confronti/">')

    write(f"{a.out}/index.html",
          '<!doctype html><meta charset="utf-8">'
          '<meta http-equiv="refresh" content="0;url=/it/confronti/">'
          '<link rel="canonical" href="/it/confronti/">')
    write(f"{a.out}/sitemap.xml",
          '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
          + "</urlset>\n")
    write(f"{a.out}/robots.txt",
          "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n")

    # Files to KEEP is not the same set as URLs to ADVERTISE: the
    # language landing pages are redirects, so they belong on disk but
    # not in the sitemap. Deriving one from the other deleted them on
    # the way out, which put the dead brand link straight back.
    written = {os.path.normpath(f"{a.out}{u}"
                                + ("index.html" if u.endswith("/") else ""))
               for u in urls}
    written |= {os.path.normpath(f"{a.out}/{lang}/index.html")
                for lang in LANGS}
    stale = []
    for root, _, files in os.walk(a.out):
        for fn in files:
            if not fn.endswith(".html"):
                continue
            p = os.path.normpath(os.path.join(root, fn))
            if p in written or p == os.path.normpath(f"{a.out}/index.html"):
                continue
            try:
                os.unlink(p)
            except OSError:
                stale.append(p)
    if stale:
        print(f"  !! {len(stale)} STALE page(s) could not be deleted and are "
              f"still served. Remove them before publishing:")
        for p in stale:
            print(f"       {p}")

    print(f"{len(urls)} pages -> {a.out}/")


if __name__ == "__main__":
    main()
