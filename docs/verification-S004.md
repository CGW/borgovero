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

---

# Second pass — the 19 held-back clusters (same day)

After the fixes, 19 clusters remained unpublished for want of identity
evidence. Nine had photographs to compare; all nine are settled. The other
ten are `price+surface`-only and have no shared images, so they need the
listings read, not the photos looked at — still outstanding.

## Confirmed (8)

| property | agencies | the contradiction |
|---|---|---|
| Anghiari, Liberty villa above the centro | Lionard vs Romolini | **550 vs 490 m²** at the same €1.600.000 — and the published €/m² differs **6×** (€508 vs €3.265), because Lionard divides by a *commerciale* of 3.150 m² that swallows the park |
| Caprese, Fragaiolo (4 listings) | R.E.Volution, Rexer, Marcellini, portal | €75.000–85.000, 115–150 m², terratetto vs colonica |
| Anghiari, Via della Bozzia (3 listings) | Cortesi + Cortesi Luxury | one property, three listings, 87 vs 105 m², rustico vs villa |
| Sansepolcro, Via Tiberina Nord | Leonardi vs Marcellini | **200 vs 400 m²**; neither publishes a price |
| Anghiari, via Infrantoio | T.V.I. vs Marcellini | 1500 vs 1600 m²; T.V.I. asks €2.300.000, Marcellini withholds |
| Sansepolcro, casa singola | Centogambe vs Marcellini | 180 vs 160 m²; €310.000 vs withheld |
| Sansepolcro, casa in pietra | Centogambe vs Marcellini | 220 vs 200 m²; €160.000 vs withheld |
| Badia Tedalda / Sestino, Via Sestinese | Rimmo vs Marcellini | filed under **different comuni** |

**The Anghiari villa is the most instructive case in the project so far.**
Lionard and Romolini describe the same building in unmistakable detail — an
early-1900s Liberty villa built for a wealthy Briton, a 2.600 m² park with
statues, years of use as an art gallery, Impruneta terracotta floors, pietra
serena door surrounds — and they share **no photographs whatsoever** (best
hamming 17, against a control of ~22). §16b's "a non-match proves nothing"
is no longer a caution; it is a documented case with a name.

It also produces the cleanest illustration of why surface basis matters
(§7): same villa, same asking price, and the €/m² a buyer would compare
differs by a factor of six.

## Rejected (1)

**Via Casa al Vento.** Three Leonardi listings joined by one identical
photograph of the **lake view** (hamming 0) — the same panorama from three
different houses on the same hillside; their surfaces run 200 to 420 m². The
Marcellini join is a bedroom against a kitchen.

Worth recording *why the guards missed it*: `MAX_LISTINGS_PER_IMAGE` drops
images appearing in **more than** three listings, and this view appears in
exactly three. Lowering the threshold would destroy real three-agency
clusters (the €2,3M estate is three agencies sharing the same aerials), so
the fix is the verified overlay, not a tuning change. Some false positives
are only visible to a human, and the design should stop pretending
otherwise.

## The 81% price gap did not survive

Leonardi lists the same Anghiari villa at €2.900.000 against the other two
at €1.600.000. But that listing was **last updated in December 2020** and
its own text offers the sale combined with a second building in the same
park (13.000 m² in total). An innocent reading exists, so publishing "81%
apart" would be an accusation the evidence does not support.

This produced `drop` support in `verified_clusters.json`: remove one member
from an otherwise sound cluster rather than discarding the cluster and the
real finding with it. **The worst price disagreement the project can stand
behind is 26% (Citerna), not 81%.**

## Three nondeterminisms, found by rebuilding twice

Comparing two consecutive builds byte for byte — worth doing routinely —
showed the site churning URLs with no data change:

1. **Page slugs carried a run ordinal**, so every URL shifted whenever any
   cluster was added, verified or suppressed. Now hashed from the cluster's
   member ids: a URL changes only when the listings being compared change.
2. **The comune label came from an arbitrary cluster member.** It flipped
   between `badia-tedalda-` and `sestino-` on alternate builds — on the one
   property whose *finding* is that the agencies disagree about the comune.
   Now most-common, ties alphabetical.
3. **Equal prices left table row order to chance**, so page content differed
   between identical builds.

Two consecutive builds are now identical. The generator also reports stale
pages it could not delete instead of leaving them silently served — a stale
page here asserts numbers about a named agency that nothing regenerates.

## Correction to a standing warning

`phase0/data/id_anchors.json` **is tracked and pushed** — `.gitignore`
un-ignores it, it has been in HEAD since `dda2cab`, and its blob hash
matches the working copy. CLAUDE.md, the SOT and two of this session's own
handovers said the opposite. The warning had been repeated for months
without anyone running `git ls-files | grep anchor`.
