# S004 — Hand-verification of the top contradictions

**Date:** 2026-08-28. **Method:** every matched photo pair for 17 multi-agency
photo clusters downloaded and eyeballed side by side (contact sheets); live
pages read for the three §15.1 named cases (Marcellini and Centogambe by
script — both permit it; Immobiliare detail pages in Chrome). No new
harvests, no matching redesign, DB opened read-only immutable.

**Decision context:** Christopher chose *verify only, decide after*. This is
the evidence for the ship/wait call.

---

## The three named cases

### 1. Badia-Tedalda triple (was: "€100.000 vs €29.000, +245%") — IDENTITY REAL, HEADLINE DEAD

The three listings are the same flat — a quadrifamiliare in Fresciano:
Centogambe's slug is *appartamento-su-palazzina-quadrifamiliare*, Leonardi's
description says *appartamento in quadrifamiliare*, and the Marcellini↔
Centogambe kitchen photograph matches (same room, same personal items,
Marcellini watermark).

**But the +245% price contradiction is a parser artifact.** Marcellini's live
page says `Prezzo: meno di € 100.000` — a **bracket**, which the adapter
stored as an asking price of €100.000. €29.000 sits *inside* "meno di
100.000". No price contradiction exists.

What actually contradicts, all verified live:

| axis | Leonardi (105564667) | Marcellini (11063) | Centogambe (0585) |
|---|---|---|---|
| price | €29.000 | *bracket only* | €29.000 |
| surface | 65 m² | 70 m² | 70 m² |
| typology | **Rustico** (portal field) / "appartamento" (own description) | Appartamenti | Appartamento |
| comune | Badia Tedalda (Fresciano) | Badia Tedalda | **Sestino** |

Leonardi contradicts *itself* (files a flat as Rustico), and the agencies
disagree on **which comune the property is in** — a contradiction axis the
report does not yet measure. Also found: `Riferimento: 4388` in the portal
description — the §16c agency ref, visible on detail pages (browser-only).

### 2. Anghiari Corso Matteotti (€83k/€150k/€190k) — DEAD

False positive. The three photo joins are hamming 7–10: a white kitchen
matched to a beige-tiled bathroom, the bathroom to a hallway. Three different
flats on three different streets (Cortesi's is in **Sansepolcro**, via del
Prucino, per its own record). Threshold noise, nothing more.

### 3. Via Cherubino Alberti (Romolini ×2 at €280.000) — DEAD

The two Romolini listings are different properties outright, read in full:
ref 2963 is a villetta on a mountain stream 4 km outside town (205 m², garden
2.600 m²); ref 940 is a B&B palazzo in the centro storico (228 m², giardino
pensile, fusion of two buildings). Round price + blank addresses — the
street-contradiction guard had nothing to fire on. The three rider listings
(Leonardi, Now, House) share zero photos with either (hamming 18–24) and
carry three different frazioni. The whole 5-listing cluster is the
round-price false-positive class.

---

## Systemic finding 1 — Marcellini prices are brackets, not prices

Of 152 priced Marcellini rows, **all 152 are exact €100k multiples**
(114×€100.000, 23×€200.000, 12×€300.000…). Live pages show why: the field is
`meno di € 100.000` / `tra € 200.000 ed € 300.000` — search brackets the
adapter read as asking prices.

Consequences:

- Every Marcellini price in the DB is wrong. 3 of the report's 10 price
  contradictions rest on them (Badia +245%, Citerna +35%, Fragaiolo +33%) —
  all three die *as price contradictions*.
- Marcellini's effective price opacity is **100%**, not 57% — no listing
  publishes an asking price in its price field. §16e gets stronger.
- **The real prices are partly recoverable, from data already held:** 31 of
  229 stored Marcellini descriptions contain `Prezzo: <real figure>` in the
  text. E.g. 11118 (Citerna) says **€214.000** — against Leonardi's €270.000
  on the same photo-verified property, a genuine **+26%** contradiction with
  two real asking prices. Adapter fix: store the bracket as `price_bracket`,
  extract description prices, leave `price` null otherwise.

## Systemic finding 2 — the photo threshold has a clean break

17 multi-agency photo clusters eyeballed, every matched pair viewed:

- **All 12 clusters whose best pair is hamming ≤5: same property.** Confirmed
  by distinct photographs, watermarks, matching estate features.
- **All 5 clusters whose best pair is hamming ≥7: false.** (Matteotti 7,
  Garbo 7, Via di Caprese 10, Centogambe-vs-Marcellini 10, Ipn-vs-Marcellini
  9.) Kitchens matched to bathrooms, a villa facade to a wardrobe.

Perfect separation in this sample: **cluster min-hamming ≤5 ⇒ real; ≥7 ⇒
false.** `MATCH_THRESHOLD = 10` let all five fakes in. Fix: keep 10 for
*candidate generation* if useful, but publication requires a ≤5 pair —
or simply lower the threshold to 5–6.

Also: **the MIN_SHARED=2 resize loophole.** C31's Marcellini↔Centogambe join
was one photograph counted twice (Centogambe serves `-scaled.jpg` and
`-740x554.jpg` of the same image; iterating from that side, both matched one
Marcellini photo → `shared=2`). It happened to be right this time, but the
guard the SOT records ("a single shared image is NOT proof") is bypassable by
any WordPress site that publishes multiple crops. Fix: dedupe near-identical
hashes *within* a listing before counting shared images.

## Systemic finding 3 — a fourth contradiction axis: location

Verified same-property pairs disagree on *where the property is*:
Badia Tedalda vs Sestino (C31), Località Omarino vs località Padonchia (C39),
Frazione Basilica vs Pieve S. Stefano labels inside the auction set. The
report measures price/surface/typology; location disagreement is publishable
and currently uncounted.

---

## The verified-publishable set (all photo-confirmed by eye, this session)

| # | property | agencies | the contradiction |
|---|---|---|---|
| 1 | Pieve S.S., Via Tiberina (C42) | Leonardi vs Romolini | **525 vs 1065 m²** (+103%), €250k vs €275k (+10%) |
| 2 | Monterchi, strada prov. (C38) | Cortesi vs Leonardi | €370k vs €390k, 220 vs 245 m², **appartamento vs terratetto** (photos show a detached new-build villa — both arguably wrong) |
| 3 | Citerna, Via Marconi (C36) | Leonardi vs Marcellini | **€270.000 vs €214.000** (+26%, Marcellini's real price from its own description), 400 vs 550 m² |
| 4 | Anghiari, Via F. Nomi (C24) | Best Realty vs Great Estate | **376 vs 535 m²** (+42%) at €1.150.000 |
| 5 | Anghiari, Mameli/SP47 (C27) | T.V.I. vs Dama RE | **600 vs 800 m²** (+33%) at €1.950.000 |
| 6 | Anghiari (C23) | Best Realty + Luxus vs Great Estate | 1267 vs 1061 m² (+19%) at €2.300.000 |
| 7 | Sansepolcro, Montedoglio (C10) | Leonardi vs private | **420 vs 800 m²** (+90%); Leonardi withholds price |
| 8 | Sansepolcro, Misciano (C12) | Tai Tiferno vs Marcellini | **250 vs 435 m²** (+74%); Marcellini price withheld |
| 9 | Caprese, Pian d'Arno (C32) | House vs Coldwell Banker | 126 vs 154 m² (+22%) at €179.000 |
| 10 | Caprese, Fragaiolo (C35) | private vs Marcellini | 120 vs 150 m² (+25%) |
| 11 | Badia T./Sestino, Fresciano (C31) | Leonardi + Centogambe + Marcellini | typology Rustico vs Appartamento; 65 vs 70 m²; **comune disagreement**; €29.000 asked |
| 12 | Badia T., Rofelle (C29) | Rexer vs private | villa vs terratetto at €40.000 |
| 13 | Badia T., Via del Castello (C30) | Rexer vs private | rustico vs terratetto at €57.000 |
| 14 | Sansepolcro, Via Buozzi (C0) | Rexer vs private | €245k vs €235k, same flat |
| 15 | Sansepolcro, Via della Ginestra (S003) | 5 auction agencies | **90 vs 133 m²** (48%) at identical €110.625 — surfaces confirmed in current data |
| 16 | Sansepolcro, via Capitini (C3) | Cortesi vs Cortesi Luxury | 230 vs 262 m² at €590.000 — same brand |

Same-agency self-contradictions, photo-confirmed: Leonardi lists one interior
as €250k/190 m²/terratetto (Via Martiri della Libia) *and* €250k/140 m²/
appartamento (Via di Montebello) (C22); Marcellini lists one house as 160 m²
*and* 1450 m² (11291/11316, C48). Romolini's 122343296/122343298 and
122342984/122342982 pairs (C11, C34) not yet eyeballed-in-full: candidates.

Plus §16e opacity, now sharper: Centogambe gates 31% of its sitemap;
**Marcellini publishes a real price on ~0% of its price fields** (31 hide one
in the description text).

## Killed this session

The Matteotti +129%, Garbo +127%, Via di Caprese +36% price contradictions
(false photo matches); the Cherubino €280k five-listing cluster (round-price
riders, and the Romolini "double listing" is two different properties); the
Badia +245% *as a price number*; the Citerna +35% and Fragaiolo +33% *as
recorded* (bracket artifacts — Citerna returns as a **real +26%** via the
description price).

Of the report's headline "10 price / 146 surface / 40 typology": the price
column as printed does not survive (3 false matches, 3 brackets; survivors:
+26% real, +10%, +5%, +4%, +1%). **The surface and typology columns are where
the product is** — every big verified case above is surface or typology, and
the un-eyeballed remainder of the 146 needs the same min-hamming/route
discipline before publication, not re-verification one by one: apply the ≤5
rule and the bracket fix, regenerate, and the report's numbers become
publishable wholesale.

## Data hygiene noted in passing

- `listings.last_seen`/`first_seen` are NULL on the current DB — the
  observe() path landed after the last full ingest. First weekly run fills.
- Centogambe 0585 is filed under `badia-tedalda` in our DB; its live page
  says Sestino. Check the adapter's comune assignment for sitemap listings.
- One Marcellini listing (rif 10991) still sits in two clusters (§15,
  known-unfinished) — untouched this session.

## What this means for ship vs wait

The contradictions product survives verification, but not in the shape
`contradictions.md` currently prints. Three code fixes stand between here and
a publishable report: (1) Marcellini `price_bracket` + description-price
extraction, (2) photo threshold ≤5 with within-listing hash dedupe, (3) a
location-disagreement axis. All three are small. After them, the 16 cases
above are publishable immediately — several are stronger than anything in the
original headline — and the regenerated full report inherits the same
discipline.
