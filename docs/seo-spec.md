# CasaZebra — Search & Index Specification

*(Renamed from Borgovero, S007; domain casazebra.it.)*

**Status:** adopted, with four measured corrections — **read `docs/SOT.md` §17 first**
**Companion:** `docs/seo-strategy.html` (the argument; this file is the contract)
**Convention:** § numbering matches `docs/SOT.md` so later sessions can cite `§4.2` etc.

> **This document was written before it was checked against the database.**
> S004 checked it on 2026-08-29 and found four errors; S005 found a fifth
> and resolved the deadlock. **Where SOT §17 disagrees with anything below,
> §17 wins.** Corrections, with the originals left legible:
>
> - **§2 named twelve comuni. `config.COMUNI` is eight.** **Fixed in §2
>   below.** San Giustino, Città di Castello, Monte Santa Maria Tiberina and
>   Umbertide have zero listings ingested, are in Perugia province, and each
>   needs its own OMI order. Every §4.3 gate calculation depends on this list.
> - **Corpus is ~676 listing pages, not 1,000–3,000 and not ~931.** §17's
>   931 applied only the price-and-surface gate; §4.2's actual gate is price
>   **AND tier ∈ {A,B}**, which excludes 255 Tier C listings. Measured
>   2026-08-30: 676 Tier B, 255 Tier C. Of that C, 107 are villas (§3.4
>   forces them to A or C) and 146 are missing typology recoverable from
>   fields already held — so the realistic figure after recovery is ~800.
>   **Say ~700 until the recovery is done.**
> - **§4.3's deadlock against §3.3 is RESOLVED — see §4.3 and SOT §17.1.**
>   Tier A is unreachable by script (`surfaceConstitution` lives on detail
>   pages that 403), so §4.3's Tier-A-only n ≥ 8 gate published nothing.
>   **Route (b) adopted 2026-08-30:** the band is computed over Tier A and B
>   together with interval arithmetic, a Tier A listing entering as a
>   zero-width interval. The Tier-A-only gate is retired and replaced by a
>   band-width gate. The decision was made on a measurement, not a
>   preference: deflator uncertainty widens the p50 by **14–18%**, while the
>   market's own p25–p75 spread is **55–104%**. Hand-seeding Tier A would
>   have removed the smaller term and left the larger one untouched.
>   All eight comuni clear the new gate immediately at n = 27–290.
> - **§4.4's "same agency, different portal needs no new scraping" is false.**
>   That overlap is empty by construction — Marcellini and Centogambe were
>   selected for being absent from the portal. Needs 3–4 new adapters. The
>   107 same-agency same-price groups on the portal are free today.
>
> One flag rather than an error: **§3.2's weighting table is a chosen
> standard, not a measurement.** That is legitimate — it is what a standard
> is — but `/it/metodo/` must say so plainly and cite §7 for the parts that
> match observed practice. Assumed numbers hardening into findings is this
> project's recurring failure mode.

---

## §1. Thesis

The site does not compete on prices. It competes on **comparability**.

Every portal in Italy publishes €/m². None of them are comparable, because the denominator is defined differently by every agency — proven by the Anghiari Liberty villa, where two agencies asking the same €1,600,000 publish €508/m² and €3,265/m² because one divides by a *commerciale* of 3,150 m² that includes a 2,600 m² park.

CasaZebra publishes **one surface standard applied uniformly to every listing in the Valtiberina**, and the contradictions corpus is the evidence that such a standard is necessary.

Two consequences that drive everything below:

1. The **index is the product**; the contradictions are the proof. Reverse of the current site.
2. The index is a **normalization of the agency's own stated figures**, never a valuation. This is both the legal position and the technical truth — see §3 and §11.

## §2. Scope

**In scope — the eight comuni actually ingested**, per `config.ALL_VALTIBERINA`, verified against the database 2026-08-29: Sansepolcro, Anghiari, Caprese Michelangelo, Citerna, Pieve Santo Stefano, Monterchi, Badia Tedalda, Sestino. Seven are in Arezzo province and covered by the Arezzo OMI order; Citerna is in Perugia province and needs the Perugia order.

**Expansion, not scope.** San Giustino, Città di Castello, Monte Santa Maria Tiberina and Umbertide were previously listed here in error. They have **zero listings ingested**, sit in Perugia province, and each needs its own OMI order. Città di Castello is also far larger than anything in scope and would dominate any corpus-wide figure. Adding them is a costed expansion with its own ingest and OMI work, not a line in this list. §12.1 is closed by this paragraph.

**Explicit non-goals.**

- No geographic expansion beyond the Valtiberina in v1. Depth beats breadth; revisit only after §13 acceptance criteria for Phase 3 are met.
- No price prediction, valuation, appraisal, or *perizia*. See §3.4.
- No republication of agency photographs, ever. Perceptual hashes only.
- No agency lead sales. See §11.4.
- No 1:1 language mirror. See §9.

---

## §3. The standard

This is the core artifact. `/it/metodo/` is the most important page on the site — for buyers, for the right-of-reply defence, and for AI citation.

### §3.1 Metrics published per listing

| Field | Definition |
|---|---|
| `sia_m2` | **Superficie interna abitabile.** Internal habitable floor area, measured to the internal face of external walls. Excludes all accessories and all land. **This is the headline denominator.** |
| `bvc_m2` | **BV-commerciale.** `sia_m2` plus weighted accessories per §3.2. Land always excluded. Exists so buyers can compare against what agencies claim. |
| `land_m2` | Garden, park, terreno, agricultural land. Reported as its own figure, **never inside a surface metric.** |
| `stated_m2` | The surface the agency published, verbatim, with the label they used. |
| `eur_sia` | `price / sia_m2` — headline. |
| `eur_bvc` | `price / bvc_m2`. |
| `eur_stated` | `price / stated_m2` — what the agency's own arithmetic yields. |

Every listing page shows `eur_stated` and `eur_sia` side by side. The gap between them is the story on every single page, not just the 30 findings.

### §3.2 Weighting table

Published in HTML table form at `/it/metodo/` — not an image, not a PDF. Machine-readable is the point.

| Component | Weight into `bvc_m2` | Cap |
|---|---|---|
| Internal habitable area, h ≥ 2.40 m | 100% | — |
| Sub-height space, 1.50–2.40 m | 50% | — |
| Below 1.50 m | 0% | — |
| Habitable annex / dependance | 100% | — |
| Veranda, enclosed and unheated | 60% | — |
| Covered loggia / portico | 35% | — |
| Open balcony / terrace | 25% | ≤ 25% of `sia_m2` |
| Cantina / magazzino, non-habitable | 25% | ≤ 15% of `sia_m2` |
| Garage / box | 50% | ≤ 40 m² |
| Covered parking space | 30% | ≤ 25 m² |
| Ruin / unrestorable annex | 0% | reported separately |
| Private garden ≤ 1,000 m² | 10% | ≤ 15% of `sia_m2` |
| Land / park > 1,000 m² | **0%** | reported as `land_m2` |
| Pool, tennis court, well, vineyard | 0% | reported as amenities |

The land rule is the one that matters. A single line — *land never enters a surface figure* — eliminates the entire class of abuse the Anghiari villa demonstrates, and is trivially defensible because no buyer walks on a park.

### §3.3 Confidence tiers

Most listings will not give a decomposition. Publishing a confident number from an unconfident input is exactly the failure the site exists to criticise, so tiers are mandatory.

| Tier | Input available | What publishes |
|---|---|---|
| **A — measured** | Itemized decomposition parsed, ≥ 80% of stated surface attributable to named components | Point value for `sia_m2`, `bvc_m2`, `eur_sia` |
| **B — inferred** | Single surface figure + property typology only | **Band, never a point.** Typology deflator per §3.4 applied to produce a range |
| **C — insufficient** | No usable surface, or typology whose deflator range exceeds ±20% | **No index published.** Page shows the agency's stated figures and a note explaining why no normalized figure is given |

Tier is displayed on every listing page. A site arguing that others hide their method cannot hide its own confidence.

### §3.4 Typology deflators (Tier B only)

Stated *commerciale* → `sia_m2`, published as a range:

| Typology | Deflator range | Tier B allowed? |
|---|---|---|
| Apartment, urban | 0.78 – 0.88 | Yes |
| Terratetto / townhouse | 0.72 – 0.85 | Yes |
| Restored casale / farmhouse | 0.65 – 0.85 | Yes |
| Villa with park | 0.30 – 0.80 | **No — force Tier A or C** |

The villa row is the honest admission: for the exact category where the abuse is worst, inference is worthless. Villas with land must be decomposed by hand or carry no index. Expect this to be the bulk of the manual work, and treat it as the successor to the S004 hand-verification loop.

### §3.5 Language discipline

Never, in copy or in markup: *valutazione*, *perizia*, *stima*, *appraisal*, *valuation*, *market value*, *what it's worth*, *fair price*.

Always: *indice*, *superficie normalizzata*, *prezzo al m² su base uniforme*, *normalized €/m²*.

A *perizia* in Italy is a regulated act performed by a qualified technician. The distinction is not cosmetic. Add these terms to a lint check in the build (§10.3).

---

## §4. Page types

### §4.1 URL structure

```
/it/metodo/                          the standard (§3)
/it/immobili/{comune}/{slug}-{id}/   listing index page
/it/comuni/{comune}/                 comune report + band
/it/agenzie/{agency}/                agency page — gated, §11
/it/contraddizioni/{slug}/           findings — existing 36
/it/archivio/{comune}/               delisted history
/it/guide/{slug}/                    explainers (IT)
/en/guides/{slug}/                   explainers (EN)
/dati/                               dataset downloads
/it/correzioni/                      public corrections log
/it/diritto-di-replica/              right-of-reply route
```

Slugs stay deterministic and free of run ordinals — the S004 nondeterminism fix is a permanent contract, see §10.2.

### §4.2 Listing index page — template contract

The unit that turns 36 pages into ~700. It is only non-thin if every page carries all of:

1. **Extraction paragraph, first 40 words.** Price, `stated_m2` with the agency's label, `sia_m2` or band, `eur_stated` vs `eur_sia`, tier, retrieval date. This paragraph is what an LLM lifts; everything after it is elaboration.
2. Full surface decomposition table (Tier A) or the deflator range applied (Tier B).
3. Position within the comune band (§4.3) — "this listing sits above the 75th percentile on a normalized basis".
4. Cross-listing status: does this property appear elsewhere, at what price, at what surface. Links to the finding page if one exists.
5. Days on market, and price history if observed.
6. Source link with retrieval date, right-of-reply link, corrections link, and the standing line: *"A normalization of the figures the agency itself published. Not a valuation."*

**Publish gate:** price present AND tier ∈ {A, B} AND listing active. Tier C listings get a page only if they carry a finding or a price history worth recording.

### §4.3 Comune report

Replaces the old "home prices in {city}" idea entirely. Contains: normalized band, n, date, agencies active, surface conventions observed per agency, contradictions found, worst spread, listing table sortable by `eur_sia`.

**The band is computed over Tier A and Tier B together, with interval arithmetic.** Each listing contributes an interval, not a point: Tier B's interval is `[price / (stated_m2 × d_hi), price / (stated_m2 × d_lo)]` for its §3.4 deflator range, and a Tier A listing enters as an interval of zero width. Each of p25 / p50 / p75 is therefore itself an interval, and **the published band is the interval, never its midpoint.** Tier C contributes nothing.

This replaces the original "Tier A listings only, n ≥ 8" rule, which could never fire — Tier A is unreachable by script (§17.1) and the corpus is effectively all B and C. Rationale, measured 2026-08-30: the deflator range widens p50 by 14–18%, while the genuine p25–p75 spread of the stock is 55–104%. The uncertainty the old gate was protecting against is a fifth of the variation it was going to publish anyway. **A wide honest band is the product; a point estimate from eight hand-picked listings is the thing this site objects to.**

**Publish gate:** n ≥ 8 active Tier A+B listings AND ≥ 2 distinct agencies AND the p50 interval no wider than the widest single §3.4 deflator range, plus 5% interpolation tolerance — **derived in `normalize.py` as `GATE_MAX_WIDTH_PCT`, currently 28,0%** (rustico's 26,7% × 1,05). An earlier draft fixed this at a flat 25%, which was an invented number: rustico's own deflator range is wider than that, so the gate silently suppressed every farmhouse-dominated comune — it suppressed Monterchi on the first run, and it would have read as rigour. The defensible rule is that a band may not be wider than the worst uncertainty among its own inputs; if mixing typologies pushes it past that, the stock genuinely is too mixed to summarise and the suppression message is true. The width condition is what the old tier condition was really trying to express, and it fails loudly on a comune whose stock is too mixed to summarise rather than silently on one that simply lacks decompositions. Below the gate, the comune gets a stub linking to listings, with **no band and no index claims**.

Every comune report states n, the tier split behind it, and the band width, in the extraction paragraph. A reader must be able to see how much of the range is the market and how much is us.

### §4.4 Findings

Unchanged from S004: `confirmed` publishes, `inconclusive` and `rejected` do not. Add a link from each finding to the index pages of its member listings, and vice versa. The findings become the "why this standard exists" evidence layer.

### §4.5 Archive

See §6. Delisted listings retain their URL and become historical records.

---

## §5. Data model additions

```
listing:
  id, source_agency, source_url, first_seen, last_seen, status
  price_eur, price_history[]
  stated_m2, stated_label            # verbatim
  tier                               # A | B | C
  components[]                       # {kind, m2, weight, capped_bool}
  sia_m2, sia_range                  # range populated for tier B
  bvc_m2, land_m2
  typology
  comune, cluster_id                 # FK to contradiction cluster if any
  photo_hashes[]

comune_band:
  comune, computed_at, n, p25, p50, p75, tier_a_only=true

archive_record:
  listing_id, delisted_at, days_on_market, final_price, price_drops[]
```

`price_history` and `archive_record` are the strategically important additions — see §7.

---

## §6. Listing lifecycle

```
active → (absent from 2 consecutive weekly ingests) → delisted → archived
```

Archived pages **keep their URL**. Do not 404, do not redirect. Swap to the historical template: *"No longer listed. On the market 1,240 days. Asking price reduced twice, from €X to €Y."* Remove from band computation; retain in the archive index.

Rationale is both SEO and strategic: 404s waste accumulated link equity, and the archive is the dataset described in §7.

---

## §7. The long game — why the archive matters more than the index

A genuine Zestimate needs **transaction** prices. Italy does not publish them in bulk; OMI gives coarse semi-annual €/m² bands per zone, which S004 already rejected as a basis. Asking prices predict asking prices.

But tracking every listing to its delisting produces, over two to three years, **asking-price-to-outcome history for the entire valley** — days on market, price-drop cadence, withdrawal versus sale. Nobody publishes this in Italy.

So: the index shippable today is also the instrument that collects the data for the valuation that is not yet possible. Design `price_history` and `archive_record` for that future consumer now, because retrofitting historical data is impossible.

National context worth recording in the methodology page: Banca d'Italia puts the Q2 2026 average asking-to-sale discount at ~7% with ~5 months to sell — figures that visibly do not describe this market, where S004 found a listing last updated in December 2020. That divergence is itself publishable content.

---

## §8. Structured data & machine-readability

### §8.1 Schema.org

- **Do not** use `RealEstateListing` on index pages. It implies CasaZebra is offering the property. Use `WebPage` + `mainEntity: Place`, with surfaces as `additionalProperty: QuantitativeValue`, and an explicit `citation` to the source listing URL.
- **Site level:** `Dataset` describing the index, with `license`, `creator`, `temporalCoverage`, `distribution` pointing at §8.3.
- **Findings:** `Article` with `ClaimReview`-shaped properties — claim, both sources, review date, verification status.
- **Method page:** `Dataset` + `HowTo`-style structure for the weighting table.

### §8.2 `llms.txt`

At root. Points to `/it/metodo/`, `/dati/`, and the current corpus counts. Keep it generated, not hand-maintained, so it can't drift.

### §8.3 Dataset export

`/dati/` publishes CSV and JSON of: all Tier A/B normalized listings, all confirmed findings, all comune bands. Stable IDs. Licence **CC BY 4.0** — attribution is a link, which makes the free dataset a link-acquisition mechanism rather than a giveaway.

### §8.4 Extraction discipline

Every page type's first 40 words are the extractable unit and must be self-contained: what, how much, measured how, verified how, as of when. Enforce with a build check on word count and required tokens.

---

## §9. Languages

Split by layer, not mirrored.

| Layer | IT | EN |
|---|---|---|
| Method | Full | Full — this is the citation target |
| Listing index pages | Full | Extraction paragraph only |
| Comune reports | Full | Full (short form) |
| Findings | Full | Extraction paragraph + table |
| Agency pages | Full | No |
| Explainers | Full | Full, different topics — see below |
| Archive | Full | No |

Explainer topics differ by language rather than translating:

- **IT:** superficie commerciale vs calpestabile; come si calcola davvero il prezzo al m²; perché due agenzie pubblicano prezzi diversi per la stessa casa; provvigione e costi d'agenzia.
- **EN:** what €/m² actually means in an Italian listing; why the same Italian house appears on three sites at three prices; surveying, notary, compromesso; buying with land — what you're actually paying for.

`hreflang` only between genuine equivalents. Do not pair an IT full page with an EN stub.

---

## §10. Build & operations

### §10.1 Scale limits

Photo hashing goes superlinear. At ~3,000 listings × ~10 images, naive pairwise comparison is ~450M operations — tolerable in chunked numpy popcount, hours in pure Python. **Above ~10,000 images, move to a BK-tree or LSH index.** Budget this before the corpus grows, not after the weekly build stops finishing.

The S004 furniture guard (`drop images appearing in > 3 listings`) is scale-dependent and **will misbehave at 10×**: genuine 4- and 5-agency clusters become common while shared stock views also multiply. Replace the absolute threshold with a ratio, or with a co-occurrence test across unrelated properties.

### §10.2 Determinism

Byte-identical rebuilds are a contract, not a nicety — add a CI check that builds twice and diffs. This was earned in S004; do not let the index generator reintroduce run ordinals, arbitrary member selection, or unstable sort on ties.

### §10.3 Build lint

Fail the build on: a forbidden §3.5 term in any published copy; a listing page missing source link, retrieval date, or the not-a-valuation line; a comune band published below n=8, below 2 agencies, or with a p50 interval wider than the §4.3 derived gate (`normalize.GATE_MAX_WIDTH_PCT`); a comune band rendered as a single figure rather than an interval; a Tier B villa-with-park; a Tier C listing carrying any normalized figure; an extraction paragraph over 40 words or missing a required token.

The "band rendered as a single figure" check is the load-bearing one. Under §4.3 the band is an interval all the way through the pipeline, and the failure mode is a template collapsing it to a midpoint for tidiness — which would publish exactly the false precision the site exists to object to, in the site's own voice.

### §10.4 Ingest

Weekly, unchanged. Ingest freshness is both a ranking factor and the entire trust proposition — a stale index is worse than no index, because the site's whole claim is accuracy. Alert on: ingest failure, agency parser returning < 50% of prior listing count, any comune dropping below its publish gate.

---

## §11. Editorial & legal constraints

These are template requirements, not policy documents. Cheap to implement, and they double as the E-E-A-T signals that drive §8.

1. **Publish the discrepancy, never the accusation.** "These two listings state different surfaces" is verifiable. "This agency inflates surfaces" is an unprovable claim about intent.
2. **Right-of-reply link on every page** that names an agency — not only in `chi-siamo`. Replies published verbatim alongside.
3. **Dated corrections policy** (7 days, already written) plus a public corrections log at `/it/correzioni/`.
4. **No agency lead sales.** A site that audits agencies cannot take their money; the first paid agency is the first softened finding, and a competitor will say so publicly. Conversion is buyer-side — see §12.2.
5. **Agency pages (§4.1) ship only after a legal review.** Everything else in this spec can ship without one.

---

## §12. Open decisions

### §12.1 Comune list
Final v1 list to be fixed from current ingest coverage. Each comune in or out determines whether §4.3 gates are reachable.

### §12.2 Conversion event
Recommended: **watch-a-comune email alerts** — notify when a listing in the comune has a price contradiction, a price drop, or an `eur_sia` below the p25 band. Near-zero running cost, builds a buyer list, structurally buyer-side. Paid buyer's-side service (pre-purchase listing check) is the later monetization. Needs a decision before Phase 3.

### §12.3 Should `bvc_m2` be published at all?
Argument against: publishing a second surface metric partly re-enters the game the site criticises. Argument for: buyers cannot connect `sia_m2` to anything an agency told them without it. Current recommendation is to publish both with `sia_m2` clearly primary.

### §12.4 Land disclosure depth
Whether to further split `land_m2` into garden / agricultural / woodland. Useful to buyers, more parsing cost.

---

## §13. Phases and acceptance criteria

### Phase 1 — Standard and instrumentation *(weeks 0–3)*
Ship `/it/metodo/`, the weighting table, tier definitions, `llms.txt`, dataset export, corrections log, right-of-reply route. Retrofit the existing 36 findings with extraction paragraphs and schema.

**Accept when:** method page live in IT and EN; > 90% of existing pages indexed; two consecutive builds byte-identical; build lint enforcing §10.3.

### Phase 2 — Index on all eight comuni *(weeks 3–8)*
Normalization pipeline, tier assignment, listing index pages, comune bands. *(Rewritten S006: the original targeted "three comuni clearing n ≥ 8" because it predated the S005 gate decision — under the A+B interval gate all eight comuni clear on day one, so three-of-eight was no longer the binding constraint and left as written it described work already exceeded. The pipeline and both page templates shipped S005–S006.)*

**Accept when:** eight comune reports live with interval bands; ≥ 700 listing pages published with correct tiers; hand-audit of 20 random Tier B interval computations passes — reproduce `sia` and `eur_sia` from the published price, surface and deflator by hand *(replaces "20 Tier A decompositions": Tier A is empty by measurement, §17.1, so that audit could never run)*; GSC impressions rising. The OMI cross-check (§17.2) has run at least once against the published bands, with divergences either explained or recorded as findings.

### Phase 3 — Coverage, press, conversion *(weeks 8–16)*
Extend to the full comune list. Four IT and four EN explainers. Press push on the six-fold villa, framed as consumer protection, offering the dataset. Alert signup live.

**Accept when:** all gate-clearing comuni published; ≥ 1 tier-1 press pickup or ≥ 15 referring domains; site cited by name when ChatGPT or Perplexity is asked whether Italian listing prices are reliable.

### Phase 4 — Archive and agency layer *(months 4–9)*
Archive templates and delisting detection. Legal review, then agency pages if cleared.

**Accept when:** archive records accumulating with `days_on_market`; legal review complete with a documented decision either way.

---

## §14. Expected timeline

Disaggregated by query class, because a single number for "when do we rank" is misleading:

| Query class | Time to compete | Note |
|---|---|---|
| Zero-competition entity queries — property names, agency + street, "perché due agenzie prezzi diversi" | **2–8 weeks** | Nothing to outrank. This is where the index's unique data lives. |
| AI citation | **2–4 months** | Runs ahead of Google; models weight method and freshness over domain age |
| Normalized-price and comparability queries | **4–8 months** | Created by this spec; effectively uncontested once the index exists |
| Contested explainers (*commerciale vs calpestabile*) | **8–14 months** | Hundreds of agency blogs; needs links |
| Portal-adjacent (*prezzi case Anghiari*) | **6–9 months with the index** | Was 18–24 without it. Expect position 4–8, never 1 |

Volume at maturity is modest — low thousands of sessions per month. For a business where a single transaction is six or seven figures, that is the correct trade, but it should be a deliberate one.

**Watch instead of traffic**, in order: pages indexed (months 1–2, target > 90%) → GSC impressions with clicks still near zero (months 2–4) → named in an AI answer (months 3–5) → referring domains, 15–25 genuine (months 4–8) → clicks and alert signups (month 6+).

---

## §15. What this spec changes from S004

| Was | Now |
|---|---|
| Contradictions are the product | The **index** is the product; contradictions are the evidence it's needed |
| 36 pages | ~700 pages, each with data nobody else has |
| Hand-verification is the bottleneck | Tiering makes verification a quality gate, not a throughput limit |
| Findings-only corpus | Findings + index + bands + archive |
| Delisted listings disappear | Delisted listings become the outcome dataset (§7) |
| Method page describes an OMI approach the site doesn't use | Method page **is** the standard, and is the primary citation target |
