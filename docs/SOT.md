# Borgo Vero — Source of Truth

**Last updated:** 2026-08-29 (S004 — top contradictions hand-verified;
Marcellini "prices" found to be brackets; photo threshold break measured;
the honest count is 40, of which 15 verified by eye. See
`docs/verification-S004.md`)

This file is the authority. Where it disagrees with a README, a results
document, a code comment or a memory, this file wins — and the disagreement
should be fixed here in the same sitting.

Reconstructed in S002 from `phase0/README.md`, `bv-site/PHASE0-REAL-RESULTS.md`,
`bv-site/CROSS-PORTAL-TEST.md`, `phase0/config.py` and
`phase0/data/id_anchors.json`. S001 ended mid-run and never wrote it, which
cost the first half of S002.

---

## 1. What this is

**REFRAMED S003.** The project's claim has changed. What follows is the
current one; the previous framing and why it was retired are below.

Borgo Vero answers one question for a buyer looking at one property:
**what should I actually pay for this?**

It publishes a single euro figure per listing — the **Target Offer** —
derived from the state's own registered transaction data, next to the
asking price, with the gap stated in euros. The engine is §16.

The state bands are OMI (*Osservatorio del Mercato Immobiliare*, Agenzia
delle Entrate) — free, bulk-downloadable, semestral, per comune, per zone,
per typology, and built from **registered sale contracts**: what property
actually sold for. They are the neutral reference the whole project
stands on.

### What was retired, and why it matters that it was

The original claim was: *asking prices sit above the state's own
registered valuation bands, and the gap is largest on listings that have
sat unsold the longest.*

Both halves failed on real data. There is **no age gradient** (§5), and
the market-wide overpricing claim does not survive a comparison it was
never set up to make: **OMI is built from transactions, our 844 figures
are asking prices, and those are not the same quantity.** Sellers ask
high and settle lower. Banca d'Italia's quarterly survey of estate
agents puts the national average discount from initial asking price at
**7–8% through 2025** (Q1 7,0 / Q3 7,5 / Q4 ~8,0), with an average
selling time of 5,5 months, and states the discount runs **larger for
older homes in slower inland towns**.

Apply that to our own median: asking sits at midpoint × 1,102; less a
national 8% gives midpoint × 1,014. **Expected closing prices land on
the OMI midpoint — exactly where registered transactions sit.** For three
sessions the difference between an ask and a sale was being read as
seller over-optimism.

**This does not exonerate the market, and the reframe is not a retreat.**
Two things follow instead:

1. **The national figure is a floor for this market, not a description
   of it.** Banca d'Italia's 8% comes paired with a 5,5-month selling
   time. Our stock sits for *years* — 83 listings over four. A property
   that cannot clear in four years does not close 8% under asking. The
   achievable-price gap here is **wider** than the national number, not
   narrower, and it is unmeasured.
2. **Whoever pays near asking absorbs all of it.** The discount is the
   reward for knowing the local norm. A foreign buyer who does not know
   it pays the full spread. That asymmetry — not seller greed — is the
   concrete harm, and it is addressable by publishing a number.

So the finding survives; the framing was wrong. "This market is
overpriced" is weak on the median listing and an agent can dismiss it in
one conversation — taking the 90 listings where it is unambiguously true
down with it. **"Here is what you should pay, from the state's own
data"** cannot be dismissed, because the number is the government's.

Phase 0 still publishes nothing. It exists to establish that the Target
Offer can be computed defensibly before a single page is built.

---

## 2. Scope

Eight comuni in the Valtiberina. Live counts measured 2026-08-27,
Immobiliare only, 25 per search page:

| Comune | n | Comune | n |
|---|---|---|---|
| Sansepolcro | 365 | Pieve Santo Stefano | 67 |
| Anghiari | 167 | Monterchi | 38 |
| Caprese Michelangelo | 82 | Badia Tedalda | 34 |
| Citerna | 60 | Sestino | 31 |
| | | **All eight** | **844** |

**Measured by full ingest**, 44 requests. The earlier 179/111 for the two
largest comuni were wrong; the other six were right to the listing. Every
listing was checked against its comune centre by lat/lon — furthest is
10,1 km, none exceeds 15 km — so these are real counts, not neighbouring-
comune bleed.

`config.COMUNI` is now all eight. The two-comune Phase 0 scope was a
request-budget decision and the budget turned out to be 44 requests.

**Citerna is in the province of Perugia (Umbria)**, not Arezzo. It needs
its own OMI request.

---

## 3. Architecture

```
phase0/
  config.py              scope, politeness, OMI mapping, gates, DOM buckets
  fetcher.py             polite HTTP, disk cache, robots reporting
  adapters/immobiliare.py  discovery + __NEXT_DATA__ parsing + --probe
  omi.py                 band loader, --inspect, sanity check
  id_curve.py            ID -> date interpolation (Job B)
  run.py                 ingest orchestrator + field-yield health
  zones.py               OMI zone by point-in-polygon from the KML (S003)
  analyze.py             the hypothesis test
  fairprice.py           THE PRODUCT — one Target Offer per listing (S003)
  surface_reads.py       the 20 browser-read surface samples (S003, §7)
  dupes.py               duplicate clusters
  selftest.py            synthetic end-to-end check
  db.py                  SQLite schema
bv-site/                 static generator + preview pages (Phase 1 groundwork)
```

Python 3.9+, stdlib plus `requests` and `beautifulsoup4`. SQLite. No pandas,
no build step.

**`photomatch.py` adds a third dependency: `pillow`** (S003), for
decoding JPEG thumbnails before hashing. It is the only module that
needs it, and it is imported inside the functions rather than at module
level so the rest of the pipeline still runs without it.

```bash
pip3 install pillow
pip3 install pillow --break-system-packages   # macOS/Homebrew Python
```

**Storage is disposable and gitignored.** `data/`, `cache/`, `*.sqlite` and
`phase0_results.csv` are not in the repo. The database is regenerated from
cache in seconds and from the network in under a minute. Do not treat a
missing `phase0.sqlite` as lost work. The one file in `data/` that *is*
precious is `id_anchors.json` — see §6. **It is tracked and pushed**
(`.gitignore` un-ignores it explicitly; checked S004 — in HEAD, hash matches
the working copy). The old warning that a clean push does not back it up was
wrong, and had been repeated at the end of several sessions without anyone
running `git ls-files | grep anchor`.

### Three findings that shaped the design

1. **The search page carries everything.** Immobiliare embeds complete data
   for all 25 results in `__NEXT_DATA__`: price, surface, rooms, floor,
   typology, coordinates, macrozone, condition, photo IDs, agency. Per-listing
   fetching would be 602 requests; search-page harvest is 27. Detail pages are
   needed only for EPC and full description, neither of which Phase 0 uses.

2. **`find_results()` locates the results array structurally**, by looking for
   a list whose items carry a `realEstate` key, rather than indexing a fixed
   path. Next.js payloads get reorganised; `--probe` reports field yield so a
   restructure surfaces immediately instead of silently storing nulls.

3. **Surface basis decides the answer.** See §7.

---

## 4. Current state (end of S003)

| | |
|---|---|
| Ingest | **Done, three sources: 1.295 listings.** Immobiliare 844, Marcellini 278, Centogambe 173 |
| Agency sites | **Built S003** (§16c). Both permit crawling; Centogambe publishes a sitemap. 79 of its listings are password-gated and 126 Marcellini listings withhold price — recorded as findings (§16e) |
| Contradictions | **36 properties where agencies disagree** — 7 on price (worst 26%), 29 on surface (worst 103%), 9 on typology, plus location disagreements (§16d). S003's 158 was inflated by two bugs found in S004: Marcellini bracket labels stored as prices, and photo joins at hamming 7–10 that were all false. **30 of the 36 hand-verified** — every one of the 19 held-back clusters was checked (`docs/verification-S004.md`, `phase0/verified_clusters.json`). **The publishable output** — 36 property pages plus chi-siamo and metodologia, IT + EN |
| Photo matching | 7.966 thumbnails hashed across all three sources; the only working join key (§16b) |
| Target Offer | Built (§16), **not publishable yet** — 4 of 5 negotiation rungs assumed |
| Price history | `price_history` + first/last seen live; weekly ingest scheduled. Effectively empty — the clock starts now |
| Database | Present. Re-parsing costs zero requests. **Never copy the .sqlite across the mount** — it corrupts; dump to SQL text instead |
| Detail pages | **403 Forbidden.** Search served, detail refused — see §12 |
| OMI bands | Arezzo 2025-2 and 2021-1, valori + zone + KML, in `data/QIP…/`. Loads: 108 rows across seven comuni, sanity anchors pass. **Citerna is province of PERUGIA and needs its own request** — 60 listings currently drop. NOTE: `omi.py` needs `--path data/QIP…/QIP_1421390_1_20252_VALORI.csv`; the `config.OMI_CSV_PATH` default does not exist |
| Zone KML | **Loaded and applied (S003).** `zones.py` assigns `listings.zona_poly` by point-in-polygon; 775 of 844 assigned, 0 fall outside every zone. §12's former #3 is closed |
| ID curve | 23 measured anchors, 2021-03 to 2026-08 |
| Site generator | Preview pages only, demo + real sample |
| Idealista adapter | Selectors **verified** S003, but `harvest()` must never run — 403 + bot detection (§9) |

**§5 is no longer the headline.** It remains the honest record of the
OMI comparison, but §1 was reframed in S003 and the project's output is
now the per-property Target Offer (§16) and the cross-agency
contradictions (§16d). Read §1 before quoting anything from §5.

---

## 5. Findings — and why none of them is the answer yet

**S001's numbers are withdrawn.** They were computed on placeholder bands
and a two-comune sample whose counts were wrong. Superseded entirely.

S002 ran the full chain: 844 listings, eight comuni, real OMI bands,
auctions and non-comparable stock removed, 696 usable.

```
vs OMI BAND CEILING
  median                    −13,0%
  IQR                       −41,5% to +19,0%
  above the ceiling         36% of listings
  more than +50% over       11% of listings   (n=74, median +78%)

vs OMI BAND MIDPOINT
  median                     +7,0%
  above the midpoint        57% of listings
  more than +50% over       24% of listings
```

### S003 re-run with polygon zones

Same 696 listings, zone assignment replaced by point-in-polygon (§15.1
done). The S002 numbers above were reproduced exactly first, so the delta
is the zoning correction and nothing else:

```
                         S002 (text guess)    S003 (polygon zones)
vs ceiling   median            −13,0%               −8,5%
             IQR          −41,5 / +19,0        −36,8 / +26,2
             above ceiling       36%                  42%
             >+50% over     74 (med +78%)        90 (med +82%)
vs midpoint  median             +7,0%               +10,2%
             above midpoint      57%                  58%
```

274 listings changed band; 252 moved *up* (median +10,3 pp) — the text
guess had been handing rural stock urban ceilings, which understated
overpricing, exactly as §12 predicted. 664 of 696 now match on their own
exact OMI zone (`band_how = …+zone-exact`), which also retires most of
§12's old #5 (fascia-wide min/max) for zoned listings.

Both caveats that remain are §7 (surface contamination, downward bias)
and the ceiling-vs-midpoint choice. Reasons 2 and 4 below still stand;
reason 3 is resolved.

### Do NOT record this as a refutation

Taken at face value the ceiling column says the market is not overpriced
and the decision gate prints `THESIS NOT SUPPORTED`. That reading is not
safe, for four reasons, three of which push the same way:

1. **Ceiling vs midpoint flips the sign.** −13,0% and +7,0% are the same
   data. "Above the top of the official range" and "above the middle of
   it" are different claims and both are honest. §12 records that this
   has not been decided.
2. ~~The advertised surface is contaminated~~ **SIZED S003 (§7).** 78% of
   sampled listings are clean and the error runs both ways; correcting
   it moves the ceiling median by −0,7 pp. This reason is spent — it
   cannot account for the gap, and it never pointed the way S002 assumed.
3. ~~Zone assignment is a text guess~~ **FIXED S003.** Point-in-polygon;
   it moved the answer +4,5 pp toward the thesis but not across zero.
4. **OMI is built from registered sale contracts** — what property
   actually sold for, not what it was asked. 844 listings asking below
   the range real transactions fall into, while almost nothing sells, is
   close to self-contradictory. When a measurement contradicts an obvious
   fact about the world, suspect the measurement.

**The honest state is: not yet measurable to the precision the claim
requires.** Recording a refutation now would harden it into next
session's starting assumption — exactly how S001's invented rural bands
became a "finding".

**Update, end of S003.** Two of those four reasons have now been worked
and neither rescued the ceiling reading: zoning moved it +4,5 pp and
surface contamination is worth −0,7 pp. Reason 4 (OMI is built from
registered sales, and almost nothing sells) is untouched and is now
carrying most of the weight, alongside the undecided framing in reason 1.
**The remaining honest position is narrower than it was:** on the
ceiling the market is not overpriced, on the midpoint it is, and the
measurement is no longer the thing standing in the way of choosing.

### What does survive, independent of all of the above

- **74 listings ask more than 50% over their band, median +78%.** Real,
  specific, and unaffected by the framing questions.
- The spread is genuinely wide. "This market has no consensus price"
  holds where "this market is overpriced" does not.
- The cross-portal findings (§9) do not touch OMI at all.

### Days on market

No age gradient, and it is not a mix effect — rustico share by bucket runs
13/28/22/24/22% with no trend, and with rustici removed the gradient is
still flat. On present measurement DOM does not predict overpricing.

Given §7 and §12 this is not yet a refutation of the stale-tail thesis
either. It is the same unresolved measurement applied to a subgroup.

---

## 6. The ID curve (Job B)

Immobiliare listing IDs are broadly sequential over time, so a curve through
known (id, date) pairs estimates when any listing was published. This is the
only route to days-on-market for anything listed before ingest starts. If
access ends — block, C&D, a layout change — every pre-existing property
becomes permanently unmeasurable and the archive can only grow forward.

### Anchors

23 measured pairs, harvested from Internet Archive captures of the
Sansepolcro search page (`wayback_anchors.py`). The largest listing ID
visible in a snapshot is a hard lower bound on issuance at that date.

```
range      86,260,004 (2021-03-07)  ..  131,271,614 (2026-08-23)
mean rate  681,197 ids/month
spread     69% between segments  -> non-linear, piecewise only
```

These **superseded** the earlier working assumption of 47M ≈ end-2018, which
implied ~958k ids/month against a measured ~681k and made every listing look
roughly a third newer than it was.

The 69% spread fails the <40% threshold that would have justified a single
line across the range. Only one anchor gap exceeds 8M ids
(86.26M–95.31M, 2021-03 to 2022-04); every other bracketed estimate is
tightly constrained.

**The seasonal dip hypothesis is not supported.** Dec–Jan segments run at
the mean (2023-12→2024-02 = 671k). The low segments (507k, 410k) sit
adjacent to failed captures and track gap length, not season.

### The weak end has moved

S001's problem was that 77% of the dataset sat *above* the last anchor.
That is fixed: dataset max 131,983,778 against a 131,271,614 anchor.

What is now unanchored is the **bottom**. Nothing below 86,260,004, while
the dataset reaches down to 56,648,574 and Anghiari's lowest live ID is
69,315,424. **The stale tail — the entire point of the project — lives
exactly there.**

### Bounds, not fabricated dates (S002)

Outside the anchored range, `estimate_date()` no longer extrapolates the
nearest slope outwards. It clamps and returns a bound:

| confidence | meaning | DOM is |
|---|---|---|
| `high` | bracketed, anchors <8M ids apart | an estimate |
| `medium` | bracketed, wide gap | an estimate |
| `bound_old` | below earliest anchor | a **floor** |
| `bound_new` | above latest anchor | a **ceiling** |

Extrapolating backwards was actively harmful: issuance grew over time, so
projecting the 2021-22 rate into 2017 makes old listings look far newer than
they are — the same direction as the 47M error already corrected once.

A bound gives up per-listing precision and gains something better: it cannot
be wrong. `analyze.py` places a bounded listing by **containment** — a floor
of 1,999 days lies entirely inside "over 4 years", so the listing belongs
there with certainty and no estimate is required. A bound that straddles two
buckets places nothing and is dropped from the DOM splits.

With the current anchors, every listing below 86.26M gets a floor of 1,999
days (≥5.5 years) and lands in "over 4 years" with certainty; everything
above 131.27M gets a ceiling of 4 days and lands in "under 6 months".
**Nothing is discarded.**

Two consequences worth holding:

- This works *because* the earliest anchor is more than 4 years old. An
  anchor added at, say, 2024 would not change that; but if the oldest bucket
  boundary ever moves past the earliest anchor's age, those listings become
  unplaceable.
- Sub-86M listings all collapse to the same DOM figure. Correct for
  bucketing, meaningless for **ranking**. Never sort a published list by DOM
  within that group.

### Priority for new anchors

**Pre-2021 (ids below 86M) first.** Everything else second. Anghiari anchors
are useful but no longer urgent — they would land in an already
well-constrained region.

---

## 7. Two surfaces, and why it decides everything

Italian listings carry two surface figures:

```
superficie              floor area you can walk on
superficie commerciale  floor area PLUS a weighted share of balconies,
                        terraces, gardens and garages
```

A verified live listing showed `115 m² | commerciale 183,2 m²` — a **59%
difference**. Agencies quote *commerciale* because a bigger denominator makes
the same price look cheaper per metre.

### What the advertised figure actually is (measured S002)

Three Sansepolcro detail pages, read in a browser 2026-08-27. Immobiliare's
rule: portions tagged *Principale* count at 100%; accessories carry a
coefficient (garage 50%, garden 10%) and appear only in the commerciale
total. The headline `Superficie` is the sum of the *Principale* rows.

| listing | headline | commerciale | dwelling | headline is |
|---|---|---|---|---|
| Villa bifam. Rosselli | 210 | 248 | 210 | dwelling only |
| Villa plurifam. Petrarca | 357 | 576,5 | 357 | dwelling only |
| Quadrilocale Martellino | 125 | 125 | **100** | **commerciale** |

**The rule is not reliably applied.** On the third, the agent tagged a
50 m² garage as *Principale* at 50%, folding 25 m² of garage into the
headline. 125 m² advertised against 100 m² of dwelling — a 20% inflated
denominator, which moves that listing from −17,1% to **+3,6%** against its
band.

So the basis is neither net nor commerciale. It is **contaminated by agent
data entry**. It cannot be detected from the search page: the breakdown that
reveals it is on detail pages, which return **403** to a script (§12).

Immobiliare's own stated `Prezzo al m²` divides by commerciale — confirmed
on all three (1.492, 746, 1.160 €/m²).

### MEASURED S003 — 20 listings read in a browser

Stratified across the price-vs-band distribution (4 deep below, 6 below,
6 above, 4 far above) so the rate is not estimated from outliers only.
Data and arithmetic in `phase0/surface_reads.py`.

**The rule, now confirmed exactly**, not inferred:

```
headline Superficie = SUM(surface x coefficient) over rows tagged 'Principale'
```

Verified to the square metre on three listings: 116350107
(1000×100% + 2200×10% = 1220), 110972593 (249 + 80×25% + 60×25% = 284),
115047499 (80×100% = 80). The coefficient applies to *Principale* rows
too — S002's "Principale counts at 100%" was wrong.

| | n | share |
|---|---|---|
| Published a breakdown | 18 of 20 | 90% |
| **Headline == dwelling (clean)** | **14 of 18** | **78%** |
| Headline inflated — looks cheaper | 3 of 18 | 17% |
| Headline understated — looks dearer | 1 of 18 | 6% |

```
116350107  head 1220 vs dwelling 1000   x1,22   garden 2.200 m2 tagged Principale @10%
110972593  head  284 vs dwelling  249   x1,14   two cellars 80+60 tagged Principale @25%
43607800   head   68 vs dwelling   65   x1,05   cantina 12 m2 tagged Principale @25%
115047499  head   80 vs dwelling  170   x0,47   a 90 m2 RESIDENCE floor tagged Accessoria
```

**Two things here overturn what S002 assumed.**

1. **It is not one-directional.** S002 recorded the bias as "always in the
   direction of looking cheaper". It is not — 115047499 excludes a
   90 m² living floor from its headline, so that listing's €/m² is
   overstated by 2,1×. A one-directional bias can be corrected with a
   factor; a two-directional error can only be bounded, which is worse
   in kind but, as it turns out, smaller in size.
2. **The size is small.** Bootstrapping the 18 observed correction
   factors across all 696 usable listings (2.000 draws):

```
                        observed     surface-corrected (95% CI)
ceiling median            −8,5%       −9,2%   [−10,7 , −7,7]
midpoint median          +10,2%       +9,2%   [ +7,6 , +11,4]
above ceiling             42%          41%    [ 39,8 , 42,8]
```

**§7 does not rescue the ceiling comparison and never could have.** The
correction is under 1,5 pp and its central estimate points *away* from
overpricing, not toward it, because the clean 78% dominate and the one
large error runs the other way.

Remaining caution, and it is real: n=18 is small, so the 22% rate itself
is only bounded to roughly 6–48%. The bootstrap also assumes
contamination is independent of listing type; the one large downward
case was cheap unrestored stock, and if that correlates the effect is
not random. Two listings (11%) publish no breakdown at all.

**Note for any future adapter:** the breakdown is machine-readable in the
detail page's `__NEXT_DATA__` at
`props.pageProps.detailData.realEstate.properties[0].surfaceConstitution`
— `constitutionKey`, `surface`, `percentage`, `surfaceType`. If detail
access ever opens, this is a parse, not a manual read. It stays
browser-only while detail pages 403 (§12.4).

Run both ways on test data:

```
Median over OMI ceiling, net surface:          +22.0%
Median over OMI ceiling, commerciale surface:  -16.9%
```

Same listings, opposite conclusions. `SURFACE_BASIS = "both"` runs both and
prints the divergence before any other number.

**OMI states its own basis per row** (`N` netta / `L` lorda) and the loader
captures it. Whichever basis is published has to match it, or the percentage
is decoration.

Publish both columns. Picking one hands an agent the argument that the wrong
one was picked; showing both makes the gap itself the finding.

---

## 8. Open questions

### Does overpricing concentrate outside the centro storico?

S001 found +52% (elsewhere) vs +13% (centro storico). **That comparison is
weaker than it looks:** it is a single cell of the DOM × zone table — the
1–2 year row — so it rests on *both* the invented rural bands (approximated
at 0,72× centro) *and* the ID curve S001 declared unpublishable.

**S002 loaded the real bands, and the premise was wrong twice over.**

First, the centro storico is not the premium zone. Sansepolcro 2025-2,
*Abitazioni civili*:

| Zone | | Band |
|---|---|---|
| B1 | centro storico | 1000–1400 |
| **C1** | **hillside north of the centro** | **1200–1700** |
| D1 | expansion south/west | 1000–1400 |
| E1 | industrial Santa Fiora | 850–1100 |
| R2 | frazioni, south | 850–1100 |
| R3 | frazioni, north | 750–1000 |

C1 is the most expensive residential zone by 20–30%, and *Ville e Villini*
in C1 runs 1500–1900 — the highest band in either comune. Anghiari has only
B1 and R1, so the comparison there is coarser.

Second, the invented rural bands were far too low. 0,72× centro gave
720–1008; real rural ceilings are 1000, 1100, and for *Ville e Villini*
1200, 1400 and 1450. Rural listings were measured against a ceiling **9–44%
too low**, which mechanically manufactured the rural overpricing.

**Still unresolved**, because it needs a re-run against real listings, and
the database does not exist yet. What can be said now is that the S001
finding should be treated as an artifact until reproduced.

### How much of the rural answer is our own classification?

OMI has **no category for a stone farmhouse** — the region's characteristic
property. The 92 rustici must be filed under one of OMI's four residential
tiers, and the choice decides the answer:

```
rural median EUR1.381/m2, R zones only
  as Ville e Villini (published)    950-1400  ->   -1,4%
  as Abitazioni di tipo economico   650- 950  ->  +45,4%
```

Same properties, same prices, same file, 47 percentage points apart.

**Decision (S002): file rustici under Ville e Villini — the most generous
band — and report the span alongside.** If overpricing survives the most
favourable classification available, no agent can dismiss it as a chosen
denominator. If it only appears under the harshest, we would be doing
exactly what this project accuses agencies of. Same principle as
`SURFACE_BASIS="both"`.

`analyze._rustico_span()` prints both readings and states whether the
verdict depends on the choice. **Revisit per-listing** once the ingest
reports yield on `condition`: restored → Ville e Villini, to-renovate →
economico. Unpopulated ones need the default regardless.

That OMI has no farmhouse category is itself worth publishing.

### Are date-matched bands needed? — ANSWERED S003: no. But see what it revealed.

Compared 2021-1 against 2025-2 across the 89 keys present in both
(comune × zone × typology × stato). Restricted to the residential
typologies we actually band against, n=31:

```
ceiling drift 2021-1 -> 2025-2   median  +0,0%   mean +1,6%
unchanged                        22 of 31 rows
moved up 6, moved down 3         range −4,0% to +16,0%
```

**Date-matching the bands is not worth building.** A listing from 2021
measured against 2025-2 bands is, for 71% of rows, measured against a
literally identical band. The movement that exists is concentrated in a
handful of urban centro rows — Anghiari B1 +16,0%, Sansepolcro C1
+13,3%, Sansepolcro B1 +12,0%, all *Abitazioni civili* — and rural R
zones did not move at all.

**But the reason it does not matter is itself a limitation.** OMI bands
for this area barely moved in four and a half years, in a period when
Italian residential prices did move and post-COVID foreign interest in
Tuscan borghi was widely reported. Two readings:

1. The Valtiberina genuinely stagnated. Plausible — it is not Chianti,
   and stagnation is consistent with §5's "almost nothing sells".
2. **OMI updates are sticky**, and the band is a lagging administrative
   figure rather than a live market reading.

If (2) carried weight, part of any measured gap would be OMI's inertia
rather than seller over-optimism — the same direction §7 already pushes.

**Checked the same day, against the whole province** (238 residential
rows, 35 comuni, both semesters, offline):

| | n | median | mean | unchanged |
|---|---|---|---|---|
| Whole province | 238 | +0,0% | +3,3% | 55% |
| **Valtiberina (our 8)** | 31 | +0,0% | **+1,6%** | **71%** |
| Rest of province | 207 | +0,0% | +3,5% | 53% |

Per comune: **Cortona +7,7%**, **Arezzo +4,5%**, San Giovanni Valdarno
+1,1%, Montevarchi +0,0%, Sansepolcro +2,7%.

**Reading (1) wins.** OMI does move when the market moves — Cortona, the
province's foreign-buyer hotspot, is up 7,7% and Arezzo city 4,5% over
the same four and a half years. The bands are sticky in general but not
frozen, so the Valtiberina's flatness is a signal about the Valtiberina
rather than an artefact of the instrument.

That is a finding, not just a cleared caveat: **the Valtiberina is the
flat part of a province whose tourist areas appreciated.** It
independently supports §5's fourth reason — a market where the state's
own registered transaction values have not moved in four and a half
years is one where very little is transacting.

Residual caution: OMI is still a lagging administrative figure and the
comparison rests on two semesters, not a series. Do not claim "OMI
tracks the market accurately", only "OMI moved elsewhere and not here."

### Is the market relisting to reset the clock?

S001's implied median DOM was 0,9 years against a market known to run 2–4.
Two readings, and both point the same way:

1. The curve was compressing time — largely addressed by the S002 anchors
   and bounds.
2. Listings are being deleted and reposted, resetting their IDs. The gap
   between apparent and real age would then be a direct measure of how much
   relisting happens, making relist detection the highest-value feature in
   the build rather than a defensive one.

Resolvable only by observing `first_seen` directly over time. Start
accumulating now.

---

## 9. Cross-portal (Idealista)

Tested 2026-08-27: 75 Immobiliare vs 90 Idealista listings, Sansepolcro only.
**The feature has teeth.**

Inventory differs — Immobiliare 179, Idealista 188. Neither portal has the
whole market.

Confirmed same-property disagreements: two properties matched on identical
price and street were called *villa* by one portal and *flat* by the other,
with room counts differing (5+ vs 6, 5+ vs 9) and surfaces re-entered rather
than copied (357 vs 350 m²). **Typology is the most commonly contested
field — more than price — and it determines which OMI band applies, so a
disagreement changes the valuation, not just the description.**

### CORRECTIONS MEASURED S003 — two claims below were wrong

**1. Idealista's search page IS blocked to scripts.** §9 previously said
it "is not 403'd". That was a browser observation written down as a fact
about scripts. Measured 2026-08-28: a plain `urllib` GET with the project
UA returns **403**, and in a real browser the page first serves a
*"Verifica del dispositivo"* interstitial — active bot detection, which
clears on its own for a genuine browser and device.

**A bulk Idealista harvest is therefore not available**, on exactly the
reasoning already applied to Immobiliare's detail pages (§12.4): the
block is deliberate, and defeating bot detection is out of bounds. The
adapter's `harvest()` should not be run. **Do not build a pipeline on
this.** What remains legitimate is Christopher reading pages in his own
browser, which is how the sample below was taken.

This is the second time a "not blocked" assumption written from a browser
session has failed against a script. Assume blocked until a script has
actually fetched it.

**2. Idealista does NOT carry more inventory.** §9 said 188 vs 179. The
179 was the wrong Immobiliare count, corrected in S002 to **365**.
Measured live: Idealista shows **189** Sansepolcro listings against
Immobiliare's 365. Immobiliare has roughly **twice** the inventory, not
less. The cross-portal argument for Idealista is the price history and
the typology disagreements — not coverage.

### The price cuts, measured (S003)

One search page read in a browser, Sansepolcro, 30 listings:

```
selector   .pricedown   (also .pricedown_price, .pricedown_icon)

3 of 30 carry a visible cut = 10%
  EUR 187.000 -> 178.000   -5%
  EUR 107.000 -> 100.000   -7%
  EUR 280.000 -> 265.000   -5%
```

**This is the only measured negotiation data the project has**, and it
bears directly on §16's assumed `DOM_DISCOUNT` ladder. Note carefully
what it is and is not: these are **asking-price reductions the seller has
already made**, not the ask-to-close discount. A buyer negotiates *on top
of* the cut. So a listing showing −5% has conceded 5% before anyone
made an offer, and Banca d'Italia's 7–8% would then apply to the
reduced price.

Two readings, and the difference matters for the ladder:

- If cuts and closing discounts stack, total concession on a cut listing
  is ~12–13%, which sits near the S003 ladder's 1–2 year rung.
- If the published cut is *part* of the eventual total, the ladder's
  upper rungs are too aggressive.

Unresolved on n=30 from one comune. It is, however, the first real number
under any of this.

### The piece that expires

**Idealista publishes price-drop history on the search results page** —
previous asking price and percentage cut, e.g. €178.000 was €187.000 (−5%).

The spec assumed price history had to be accumulated by observing the market
for 12+ months. Idealista hands over a slice of it now. Two of the first 30
listings carried a visible cut; if that rate holds, ~6–7% of the market has
published history available immediately.

**Those figures vanish on the next update.** This is the one piece of the
dataset with an expiry date, which is why the Idealista adapter is the next
build item.

Idealista also prints €/m² computed on *its own* surface figure, giving a
third divergence axis at zero calculation cost.

### The adapter (built S002, UNVERIFIED)

`adapters/idealista.py` exists and mirrors the Immobiliare adapter's
interface: `search_url`, `parse_result`, `harvest`, `--probe`. It captures
`price_previous`, `price_cut_pct` and `eur_m2_stated`, which are new columns
on `listings` (added with an `ALTER`-based migration in `db._migrate`, since
`CREATE TABLE IF NOT EXISTS` will not add columns to an existing table).

**It has never touched the live site.** It was written offline from the
cross-portal notes, so the URL patterns, CSS class names and pagination
scheme are informed guesses. Two mitigations:

- Every extractor takes a *list* of candidate selectors and reports which
  one fired. `--probe` prints the page's most common containers when
  nothing matches, so a miss is diagnosable rather than silent.
- `--selftest` parses a fixture shaped like the two real listings recorded
  above, offline. It proves the parsing logic is right even while the
  selectors are unconfirmed — and after a selector repair it confirms
  nothing else broke.

**Run `--probe` before `--selftest` is taken as any kind of green light.**

Remaining notes:

- Rendered DOM, not a JSON payload. Structurally more fragile than
  Immobiliare's `__NEXT_DATA__` and will break on redesigns the other
  would survive.
- Address normalisation handles three quirks: the link title is a full
  sentence ("Appartamento in vendita in via Roma, 12"), `Nn` is appended
  where a street has no civico, and a civico may follow a comma.
  Immobiliare does none of these; each one left in place is a property
  that fails to match its twin.
- Idealista publishes **one** surface figure and does not state its basis.
  Stored as `mq` with `mq_commercial` left null rather than guessed — §7
  is already the largest open risk and this would compound it.
- No coordinates on the search page, so `lat`/`lon` are null. Once the OMI
  zone KML is loaded, Immobiliare listings can be zoned by point-in-polygon
  but Idealista ones cannot without detail fetches.
- **Price is the reliable join key** at this scale. Exact price plus
  approximate surface produced unambiguous matches across 165 listings.
  The matcher itself is not written — that is a separate module.
- Overlap *rate* is not established — matches were found by inspection on a
  partial sample.

---

## 10. Run order

```bash
cd phase0
pip install requests beautifulsoup4

python3 selftest.py                  # verify the pipeline offline first
python3 -m adapters.immobiliare --probe
python3 run.py                       # ~12 requests, under a minute
python3 omi.py --inspect             # then fix OMI_COLUMNS in config.py
python3 omi.py                       # loads + sanity-checks
python3 id_curve.py --backfill
python3 id_curve.py --report
python3 analyze.py
```

`config.CONTACT_URL` must be set before anything runs — the script refuses
otherwise. An identifiable user agent turns "unknown bot hammering our site"
into "someone we could just email".

Re-running the ingest costs zero requests; everything is served from the HTML
cache, so reparsing after a parser change is free.

### The OMI sanity gate

`omi.py` compares loaded bands against known anchors:

```
sansepolcro B1   1100–1400   (centro storico ~€1.245/m²)
anghiari    all   880–1410   (registered range)
```

**If those do not line up, the column mapping is wrong and every number
downstream is garbage.** Column names shift between releases, which is why
`--inspect` prints a ready-to-paste `OMI_COLUMNS` block rather than assuming.

---

## 11. Reading the verdict

The DOM split matters more than the headline median. Two very different
markets produce the same overall number:

- **Uniform** — everything sits ~30% over the band. The claim is *"this
  market is overpriced."*
- **Stale tail** — fresh listings sit near the band, old ones far above and
  drag the median up. The claim is *"stale listings are wildly overpriced and
  distort what everyone believes the market is worth."*

The second is narrower, much harder to argue with, and points the whole build
at long-DOM properties — ranked lists become the front page rather than a
side feature.

Gate thresholds: `GATE_STRONG` 35%, `GATE_MODERATE` 20%.

Before accepting a `UNIFORM OVERPRICING` verdict, check the DOM confidence
mix printed in the data-quality block. If the oldest bucket is thin or
carried entirely by bounds, the gradient may be real but unresolved rather
than absent.

---

## 12. Known limitations

In descending order of how much each could move the answer:

1. **Ceiling vs midpoint is undecided.** −8,5% vs +10,2% on identical
   data. This is a framing choice nobody has made deliberately yet, and
   with §7 and §12.3 now resolved it is the **largest remaining
   limitation** — the only one left that flips the sign of the answer.
2. **Surface contamination — SIZED S003, and it is small.** §7. 78% of
   sampled listings are clean, the error runs both ways, and correcting
   it moves the ceiling median by −0,7 pp. It no longer ranks first.
   Residual: n=18, so the rate is bounded only to ~6–48%.
3. **RESOLVED S003 — zone assignment is now point-in-polygon.**
   `zones.py` assigns `zona_poly` from the official KML perimeters: 775
   of 844 assigned, 0 points fall outside every zone, and 664 of 696
   usable listings match their exact OMI zone band. The 69 unassigned
   are Citerna (60, no KML — Perugia) and 9 without coordinates; those
   fall back to the old text guess, visibly, in the data-quality block.
   The correction moved 252 listings up a median +10,3 pp — see §5.
4. **Detail pages return 403.** Search served, detail refused. Closes off
   commerciale, stated publication dates, agency references and EPC. Not
   an expense question — the route is shut. Do not circumvent it; the
   Wayback archive is the legitimate alternative for a sample.
5. **Per-listing bands are coarse — largely retired S003.** With an
   exact polygon zone, `band_for()` uses that zone's own rows (95% of
   usable listings). Residual coarseness: min/max across the mapped OMI
   typologies within the zone, and the fascia-letter fallback for the
   32 listings whose zone does not quote their typology.
6. **Citerna has no bands.** Province of Perugia. 60 listings drop.
7. **Single source.** Immobiliare only. Idealista carries more inventory
   and publishes price cuts; agency-exclusive listings are invisible.
8. **Sub-86M listings share one DOM figure.** Bucketable, not rankable.
9. **robots.txt disallows the crawl.** Proceeding was a deliberate
   decision (S002) with an identifiable UA. It constrains what can be
   published commercially — see §9's licence note for the parallel OMI
   problem.

---

## 13. Out of scope for Phase 0

No publishing, no page generation, no dedup, no photo embeddings, no
disposition classification. Phase 0 exists to tell you which site you are
building before writing a page of it.

---

## 14. Changelog

| Session | Date | What changed |
|---|---|---|
| S001 | 2026-08-27 | Spec, Phase 0 ingest, site generator, cross-portal test, first real-data run on placeholder bands. Wayback anchor harvest started, interrupted mid-run on Sansepolcro. No wrap written. |
| S002 | 2026-08-27 | **Full chain run end to end for the first time.** 844 listings ingested across all eight comuni (44 requests), real bands loaded, DOM backfilled, analysis produced. Headline −13,0% vs ceiling / +7,0% vs midpoint. Recorded as **unresolved, not refuted** — §5 gives the four reasons. Detail pages found to return 403, closing off commerciale, stated dates and EPC; decided not to circumvent. Measured what Immobiliare's `Superficie` actually is from three browser reads: usually dwelling-only, but contaminated by agent data entry at an unknown rate, always toward looking cheaper (§7). Found 37 judicial auctions at median €414/m² against the market's €1.143 and excluded them; found Citerna is in Perugia province and has no bands; added a loud guard for both. Fixed `band_for()` zone collapse, its non-residential fallback, the missing typologies (Trilocale/Quadrilocale/Casa colonica, 99,9% yield), the gate's "uniform overpricing" wording on a negative median, and the price-yield threshold that always tripped. Added `dupes.py` — 42 clusters, 7,2% surplus, median moves +1,3%. |
| S002 | 2026-08-27 | Real bands loaded and inspected. Fixed a second load-breaking bug: `sniff()` skipped the AdE preamble line but `load()` did not, so `DictReader` took the caption as its header and matched zero rows. Added `rows()` as the single correct entry point, plus `zone_labels()` joining `Zona_Descr` from the ZONE file on `LinkZona`. `band_for()` filtered by zone only for centro storico — everything else collapsed across all zones, handing a rural farmhouse a 1900 ceiling set by C1 villas; now filtered via `config.ZONA_TO_FASCIA` on OMI's own B/C/D/E/R letter. Its no-match fallback also spanned Capannoni to Ville (280–1900); now residential only. Rustici filed under Ville e Villini with the span reported (§8). README/SOT commands corrected to `python3`. |
| S002 | 2026-08-27 | OMI: found `Comune_descrizione` is `SAN SEPOLCRO` with a space — the loader's exact-match filter would have dropped every Sansepolcro band and then all 178 Sansepolcro listings, silently. Added `config.norm_comune` on both write and lookup. Corrected `stato`→`Stato`, `zona`→None (Zona_Descr is in the zone file), semester→2025-2, sanity anchor→1000–1400, all verified against the OMI web consultation. Confirmed basis is **L (lorda)** — neither surface column matches it (§7). Seismic-suspension list checked: Arezzo never appears. Bulk files requested (Arezzo, 2025-2 and 2021-1, with zone perimeters). Built `adapters/idealista.py` with offline `--selftest`; added `price_previous`, `price_cut_pct`, `eur_m2_stated` and a migration. |
| S003 | 2026-08-27 | **Zone assignment moved from text guess to point-in-polygon.** New `zones.py` (stdlib: zipfile + xml.etree + ray casting with holes) parses the official KML perimeters, identifies comuni by Document name rather than a hand-kept code table, and writes `listings.zona_poly` (new column, migrated): 775/844 assigned, 0 outside every zone, landmark spot-checks pass. `band_for()` now matches the exact OMI zone first (664/696 usable), then the zone's fascia letter, then comune; data-quality block prints the `band_how` mix. S002 numbers reproduced exactly before switching, so the delta is pure zoning: ceiling median −13,0→−8,5%, midpoint +7,0→+10,2%, above-ceiling 36→42%, the >+50% club 74→90 listings; 252 listings moved up median +10,3 pp. §12.3 closed, §12.5 largely retired. Discovered `omi.py` must be run with `--path` to the QIP valori CSV — bands are not persisted in a fresh working copy. |
| S003 | 2026-08-28 | **The product became the contradictions.** Built `adapters/agencies.py` + `run_agencies.py` for Marcellini and Centogambe (the two named agencies absent from Immobiliare): 1.295 listings across three sources. Built `photomatch.py` — dHash over CDN and agency thumbnails, the only join key that works after coordinates (agency fallback points), photo IDs (no overlap), addresses (5% have a civico) and price (only joins when prices agree) all failed. 7.966 thumbnails hashed. Built `contradictions.py`: **158 properties where agencies disagree — 10 on price (median 34%, worst 245%), 146 on surface, 40 on typology.** Matching was got wrong twice in opposite directions, both recorded in §16d: merging every route transitively chained a tolerance into blobs (one cluster hit 14 listings and 8 Marcellini refs), and over-correcting with a coherence rule then deleted the findings themselves. Final design merges, tests whether the result is believable as one property, and falls back to pairs when it is not. Typology normalised — `appartamenti vs appartamento` is a plural, not a valuation disagreement. Found **opacity is itself the finding** (§16e): Centogambe password-gates 79 of 255 listings while publishing them in its sitemap; Marcellini withholds price on 126 of 278. Fixed `to_int` concatenating Marcellini price ranges into a 74.074.085% "gap", then cleared the 374 `price_history` rows that fix produced — **a parser change looks exactly like a market event** and must never be left in the one table that cannot be regenerated. Also: `.sqlite` copied across the sandbox mount arrives corrupt (recovered via SQL dump); `pillow` is now a dependency of `photomatch.py` only. |
| S003 | 2026-08-28 | **§1 REFRAMED — the project's claim changed.** Established that OMI is built from registered *transactions* while our 844 figures are *asking* prices, and that the difference had been read as seller over-optimism for three sessions. Banca d'Italia puts the national ask-to-close discount at 7–8% (2025) with a 5,5-month selling time; applying it puts our median expected close on the OMI midpoint. The market-wide overpricing claim is retired. It is replaced by a per-listing **Target Offer** — `min(fair_value, asking × (1 − negotiation_discount))` — built in new `fairprice.py`: 705 priced, 620 publishable, median gap +20,0% / €32.742, €38,6M total. Added `publishable()` after the first run's headline offender turned out to be a €6,75M estate measured against ordinary rural bands; 12% now suppressed rather than guessed. Condition expressed as a position *inside* the OMI band because OMI publishes only NORMALE here (107/108 rows). Recorded loudly that the DOM discount ladder above the first rung is unmeasured and that the engine's own DOM table therefore echoes its input rather than evidencing anything. Note: the national 8% is a **floor** for a market whose stock sits for years, so the achievable-price gap here is wider than measured, not narrower. |
| S003 | 2026-08-28 | **§7 measured, and it does not say what S002 thought.** 20 detail pages read in Christopher's own browser (Claude in Chrome; detail pages still 403 to scripts, and the decision not to proxy around that was re-affirmed rather than reversed). Confirmed the headline rule exactly — `SUM(surface × coefficient)` over *Principale* rows, coefficient applying to Principale too, which corrects S002's "Principale counts at 100%". 14 of 18 listings clean (78%); contamination runs **both** directions, refuting "always toward looking cheaper"; bootstrapped across 696 listings it moves the ceiling median −8,5 → −9,2% and the midpoint +10,2 → +9,2%. §7 demoted from the top limitation. Also answered §15.7 offline: OMI bands barely moved 2021-1 → 2025-2 in the Valtiberina (71% identical, mean +1,6%) while Cortona ran +7,7% and Arezzo +4,5% over the same period — date-matched bands are unnecessary, and the flatness is a finding about this market rather than about OMI. Recorded `surfaceConstitution`'s location in `__NEXT_DATA__` for any future adapter. |
| S002 | 2026-08-27 | Anchor harvest completed (23 anchors, 2021-03→2026-08). Confirmed 69% issuance spread — piecewise only, no seasonal dip. `id_curve.py`: extrapolation past outer anchors replaced with floor/ceiling bounds. `analyze.py`: now reads the confidence flag it was always given — confidence mix in data quality, containment-based bucketing for bounds, ambiguous bounds excluded from DOM splits. `config.DOM_MIN_CONFIDENCE` added. `selftest.py` extended to cover both bound paths. This file created. |
| S004 | 2026-08-29 | **The remaining ten clusters, the missing pages, and the weekly task.** Read both listings for each of the ten `price+surface` clusters that had no photographs — the method the Anghiari villa established. **Seven confirmed**, several of which explain their own disagreement: the Anghiari casale differs by exactly the 43 m² fienile one agency counts and the other does not; Villa Colcello is 250 vs 285 m² between agencies while one of them says 250 in its field and "circa 300 mq" in its own text; Cortesi calls a Sansepolcro house *singola* where Leonardi calls it *bifamiliare*. **One rejected**: three flats at €145.000 in the same converted colonica at La Scheggia — a building split into equally priced units, invisible to price+surface matching and visible only in the listing text. **Two inconclusive**, which added an `inconclusive` verdict to the overlay: "these are different properties" and "this could not be settled" are different claims, and recording the second as the first would stop a later session ever looking again. 36 contradictions, 30 verified, and nothing held back for want of a look. Then the site: `chi-siamo` and `metodologia` are emitted (the footer had linked to both from every page since the generator existed), language landing pages added (the header brand link was dead too), and a **right of reply** published — 7 days, page comes down if the agency is right. The methodology page is this site's own rather than `templates.py`'s, which documents the OMI arithmetic these pages never run. Two bugs found by checking rather than assuming: a page told readers it was matched by "identical price and compatible surface" when NEITHER agency published a price (the evidence fallback chose the nearest label, not the weakest), and the stale-page sweep deleted the new landing pages because it derived "files to keep" from "URLs to advertise". Whole-site link check now passes with zero broken links. Finally, the weekly task runs all three sources plus photo hashing, and reports the remaining Marcellini bracket placeholders. |
| S004 | 2026-08-29 | **Second verification pass — the 19 held-back clusters.** Nine had photographs to compare; all nine settled. Confirmed: the Anghiari Liberty villa (Lionard 550 m² vs Romolini 490 m², both € 1.600.000) — established from the listings' own TEXT, since they share no photographs at all (best hamming 17), a working demonstration that a non-match proves nothing; Fragaiolo, Via della Bozzia (three Cortesi-brand listings of one property), and four single-photo Marcellini pairs. Rejected: Via Casa al Vento, where three Leonardi listings were joined by one identical photograph of the LAKE VIEW — the furniture guard missed it because it appears in exactly three listings and the rule drops images appearing in more than three; lowering that threshold would destroy real three-agency clusters, so the verified overlay is the right instrument, not a tuning change. The reported 81% price gap did NOT survive: Leonardi lists the same villa at € 2.900.000, but that listing was last updated in December 2020 and offers a combined sale with a second building, so its price is not comparable — which motivated `drop` support in the overlay, removing one member from an otherwise good cluster instead of discarding the finding with it. **39 contradictions, 23 verified; worst price gap is now the real 26% at Citerna, not a phantom 81%.** Also fixed three nondeterminisms that made rebuilds churn every URL on the site: page slugs carried a run ordinal, the comune label came from an arbitrary cluster member (it flipped between Badia Tedalda and Sestino — the very disagreement being published), and equal prices left row order to chance. Slugs are now hashed from member ids; two consecutive builds are byte-identical. The generator also reports stale pages it could not delete rather than leaving them silently served. |
| S004 | 2026-08-29 | **A standing warning was folklore.** CLAUDE.md and §3 both said `id_anchors.json` is gitignored and not backed up by a push, and it was repeated to Christopher twice this session. It is tracked, in HEAD since `dda2cab`, and hash-identical to the working copy. Corrected in both places, with the lesson: a caution nobody re-tests stops being a fact. |
| S004 | 2026-08-29 | **Shipped the first pages.** `bv-site/contradictions_site.py` writes one page per property — every agency's figures side by side, each linked to its own listing — IT + EN, sitemap and robots, reusing `templates.py`'s shell. 21 of 40 published; the other 19 need `--candidates` because publication requires identity evidence and these are named local businesses. Output in `bv-site/dist-contradictions/` (gitignored, regenerable). |
| S004 | 2026-08-29 | **Hand-verification pass, then the fixes it demanded.** Every matched photo pair in all 17 multi-agency clusters eyeballed via contact sheets; the three §15.1 named cases read on live pages. Results: 12/12 clusters at hamming ≤5 real, 5/5 at 7–10 false (Matteotti and Cherubino both die); the Badia triple is one Fresciano flat but its +245% was a parser artifact — **all 152 Marcellini "prices" are search brackets** ("meno di € 100.000"), stored as asking prices. Fixed: `agencies.py` stores `price_bracket` and extracts real prices from descriptions (31 recovered, incl. Citerna €214.000 → a real +26% against Leonardi's €270.000 on a photo-verified ruin); `photomatch.py` dedupes hashes within a listing (resize loophole) and merges only on ≤5 evidence, labeling `photo` vs `photo-weak`; `contradictions.py` gains a verified overlay (`verified_clusters.json`, human-measured, committed), a location axis (agencies disagree on the comune: Badia Tedalda vs Sestino), a round-price rarity guard, and `--db`. Report regenerated: **158 → 40 honest contradictions, 15 verified.** The mount now refuses live sqlite writes (ALTER hit disk I/O error), so the corrections were worked out on a sandbox copy and ship as **`phase0/apply_S004_fix.py`** — run it once against the real database (`python3 apply_S004_fix.py`, `--dry-run` to preview). It is idempotent, touches only Marcellini rows, and bypasses `db.observe()` so no fabricated cuts land in `price_history`. A full replacement dump also exists (`phase0_S004_restore.sql`) but the in-place script is the intended route; **the repo's `phase0.sqlite` carries the old bracket prices until one of them is applied.** Verification evidence: `docs/verification-S004.md`. |

---

## 15. Next

**Rewritten at the S003 wrap.** The old list was ordered by "how much
each moves the unresolved answer in §5" — a question the project no
longer asks. §1 is now the Target Offer and §16b–e the contradictions,
so the ordering below is: *what stands between here and a page anyone
can read.*

### The decision — MADE, S004

Christopher chose **verify first, then ship**. The verification ran
(every matched photo pair in all 17 multi-agency clusters eyeballed;
the three named cases checked against live pages) and its evidence is
`docs/verification-S004.md`. Then the fixes: Marcellini brackets
(§16c), photo threshold + resize dedupe (§16d), verified overlay,
location axis, round-price rarity guard. `contradictions.md` is
regenerated under all of them: **40 contradictions, 15 verified by
hand.** The Target Offer still waits for its ladder, as decided.

### Then, in order

1. **Ship — BUILT S004.** `bv-site/contradictions_site.py`: one page per
   property, every agency's version side by side, each figure linked to
   the listing it was published on. IT + EN, sitemap, robots, no
   framework, zero hosting cost — it reuses `templates.py`'s shell so
   the house style is shared with the main generator. **21 pages
   published of 40 contradictions; 19 held back**, because publication
   requires identity evidence (verified / `ref` / `photo` / non-round
   `price`) — `photo-weak` and bare `price+surface` need `--candidates`
   and print as unconfirmed. Named agencies are named, so the gate is
   deliberately tighter than the report. Verification notes render on
   the EN pages only; the IT pages carry the badge and date, because
   English prose on the page a Valtiberina buyer reads would undercut
   the care the site is selling.

   **Completed later in S004:** all 36 contradictions now publish (the
   seven newly confirmed clusters cleared the gate and nothing is held
   back); `chi-siamo` and `metodologia` are emitted, so the shared
   footer's links resolve; the language landing pages exist, so the
   header's brand link resolves; and a **right of reply** is published
   on the methodology page — an agency that believes two listings here
   are not the same property is answered within 7 days, and the page
   comes down if they are right. The methodology page is this site's
   own, not the OMI one in `templates.py`, which describes arithmetic
   these pages never run.

   A whole-site link check passes with zero broken internal links, and
   two consecutive builds are byte-identical.

   **Remaining before it goes live:** a domain and hosting (static, so
   effectively free), `correzioni@borgovero.it` actually receiving
   mail — the right of reply is a promise the site makes in writing, so
   the mailbox has to exist before publication, not after — and a human
   read of all 36 pages.
2. **DONE — all 19 held-back clusters are checked.** Nine by
   photograph, ten by reading both listings. 7 confirmed, 1 rejected
   (La Scheggia), 2 inconclusive. Nothing is now held back for want of
   a look.
3. **DONE — the weekly task now runs all three sources plus photo
   hashing** (`borgovero-weekly-ingest`, Mondays 07:00). It also
   reports how many `'bracket (unresolved)'` Marcellini rows remain,
   and says when that hits zero, because bracket-vs-rival-price
   contradictions become checkable then (a rival asking €150.000 for a
   property Marcellini brackets as "under €100.000" is a contradiction
   neither can wave off). **First run to watch: Monday 31 August** —
   check it does not report a parser break, and that the Centogambe
   password-gated 79 are reported as a finding rather than failures.
4. **Measure the negotiation ladder.** ~20–30 observed price cuts makes
   §16's `DOM_DISCOUNT` real instead of assumed. Accumulation started
   S003; the agency sites are likely to show a cut *before* the portal
   does.
5. **Resolve lorda vs netta** (§7). A published euro figure has to be
   right in a way a distribution median never did. `NET_TO_LORDA` is
   deliberately 1,0 until measured.
6. **Citerna's OMI bands** — Forniture OMI, provincia di PERUGIA,
   2025-2, with the KML. Recovers 53 listings and lets them be zoned.
7. **Run `dupes.py` before any ranked list.** 42 clusters found in S002
   and never applied.
8. **Decide ceiling vs midpoint** (§5). Demoted: it decides the framing
   of a market-wide claim the project no longer leads with, but it still
   has to be settled before any OMI comparison is published.
9. Harvest pre-2021 ID anchors (§6) — still the only route to DOM below
   86M, and DOM matters more now than it did.

### Known-unfinished, small

- One property (`Marcellini rif.10991`) still appears in two clusters.
  Merging them should pass both guards; something in pair construction
  prevents it. Cosmetic — 1 of 158 — but unexplained.
- `adapters/idealista.py` selectors are verified but `harvest()` must
  never run (§9).

---

## 16. The Target Offer engine — the product

`phase0/fairprice.py`. One euro figure per listing: **what a buyer should
pay.** This is the deliverable §1 now describes; `analyze.py` remains the
hypothesis test and is not user-facing.

### Two quantities, deliberately not merged

```
FAIR VALUE     what the property is worth. OMI band for its exact zone
               and typology, positioned by condition and specs.
               Days on market does NOT enter. A house is not worth less
               because it has been advertised for four years.

TARGET OFFER   what you should pay. Fair value, capped by what the
               seller has demonstrably been unable to refuse.

    target = min(fair_value, asking x (1 - negotiation_discount))
```

The minimum is the whole logic. Where asking exceeds worth, fair value
binds and the buyer is told not to overpay. Where the listing is priced
within value, the negotiation term binds and the buyer is still told to
negotiate. **Neither branch ever recommends paying above the state's own
valuation.**

### Current output (705 priced, 620 publishable)

```
median gap, asking vs target      +20,0%      EUR 32.742
IQR                          +12,0% to +31,0%
total gap, publishable only        EUR 38,6M across 620 listings
which term binds       fair value 43%  |  negotiation 57%
```

### The publishability gate — the most important part

The first run's headline "worst offender" was a €6,75M luxury estate
measured against **ordinary rural R1 bands of 670–980 €/m²**, producing a
€5,5M "gap". That is not a finding, it is OMI having no band for that
stock — the same hole as the missing farmhouse category (§8). It would
have been the first number any agent or journalist looked at.

**A wrong number on the flagship listing discredits the 700 correct ones
behind it.** So `publishable()` suppresses rather than guesses:

| | n | |
|---|---|---|
| Publishable | 620 (88%) | 507 high, 113 medium |
| Suppressed | 85 (12%) | |
| — surface over 500 m² | 59 | outside the stock OMI bands describe |
| — no exact polygon zone | 21 | text-guess zoning is not good enough to publish |
| — asking >3× band ceiling | 5 | OMI almost certainly publishes no band for it |

Rustici are capped at **medium** regardless: OMI has no farmhouse
category, so their band is our choice and the alternative reading moves
them 14 pp (§8). Honest to show, dishonest to show as precise.

### What is measured and what is assumed

**Measured:** the OMI band (registered contracts, 2025-2), the zone
(point-in-polygon, §12.3), the surface rule (§7), and the national
negotiation norm (Banca d'Italia).

**Assumed — and these are the direct descendants of S001's placeholder
bands:**

```
CONDITION_POSITION   where in the band each condition sits.
                     OMI publishes only NORMALE for this province
                     (107 of 108 rows), so condition CANNOT come from
                     the state's data. Expressed as a position INSIDE
                     the band, never a multiplier outside it, so every
                     published number stays within a range the Agenzia
                     delle Entrate itself printed.

DOM_DISCOUNT         8% for under-6-months is the measured national
                     norm. Every longer bucket — 12/16/20/25% — is
                     EXTRAPOLATED AND UNMEASURED.
```

**The "by days on market" table `fairprice.py` prints is not evidence.**
Where the negotiation term binds (57% of listings) the gap *is* the
assumed discount, so that table largely echoes `DOM_DISCOUNT` back. It
becomes a finding only once the ladder is measured — which needs
`first_seen` observed over time and actual closing prices, the same
accumulate-forward problem as relist detection (§8). **Start now.**

### Accumulation started S003 — the ladder's only real route

`INSERT OR REPLACE` was overwriting the previous price with no record of
it, so **re-running the ingest destroyed exactly the history the ladder
needs.** Scheduling it before fixing that would have been worse than not
scheduling it at all.

Added:

```
price_history      one row per OBSERVED CHANGE (not per run)
                   source, source_id, seen_at, price, prev_price
listings.first_seen  set once, never updated
listings.last_seen   moves every run
```

`db.observe()` must be called **before** `upsert_listing` or the old
price is already gone; `run.py` now does this and prints an "OBSERVED
THIS RUN" block with every cut in full. `db.disappeared()` returns
listings missing from the latest run — sold, withdrawn or relisted, and
**the closest observable sale signal this project has** (§8).

Verified offline end to end: previous price survives the upsert,
first/last seen populate, disappearance detects correctly.

**Scheduled weekly, Mondays 07:00** (`borgovero-weekly-ingest`). Weekly
not daily on purpose: the signals wanted are *price-change events* and
*disappearance*, both of which weekly resolves fine, at a seventh of the
footprint against a robots.txt that disallows the crawl (§12.9). Runs
only while the app is open; a missed run fires at next launch.

**Roughly 20–30 observed cuts makes the ladder measurable.** At 10%
of listings carrying a cut (§9's Idealista sample) that is plausibly a
few weeks, not months.

### §16b. Cross-agency variance — the actual product (S003)

Christopher's framing, and it is a better product than the Target Offer:
**Leonardi, Marcellini, Centogambe, Cortesi, SICASA, House Immobiliare,
Romolini, Tiber Immobiliare and It Casa list the same properties at
different prices and different square footage.** Publishing that variance
needs **no assumptions at all** — not OMI, not the negotiation ladder,
not condition positions, not the surface basis. It compares agencies to
themselves. Every hard problem in §16 evaporates.

Coverage on Immobiliare: **582 of 844 listings (69%)** across seven of
the nine. **Marcellini and Centogambe are not on Immobiliare** and need
their own sites.

**The phenomenon is confirmed in data we already hold.** Three agencies,
Via della Ginestra, identical price to the euro (€110.625), surfaces
**133 / 90 / 97 m²** — a 48% disagreement on one property.

### Matching is the blocking problem, and photos are the only key

Every obvious join key fails, measured:

| key | verdict |
|---|---|
| coordinates | **unusable** — SICASA pins 28 *different* properties (Gricignano, Via del Tevere, Via Petrarca, Piazza della Repubblica) to one point at Sansepolcro's centre. Exact-coordinate matching finds agency habits |
| photo IDs | **unusable** — zero overlap; each upload gets its own id |
| address | **weak** — 100% populated but street-level; 5% have a house number, 105 blank |
| price | **useless here** — works only when prices agree, and disagreement is the thing we want |

`photomatch.py` (S003) uses **dHash on the CDN thumbnails**
(`pic.im-cdn.it/image/{id}/thumb.jpg`, 100×75, ~2,7 KB; `small.jpg` is
403). Validated on a five-agency auction cluster: hamming **0** and
**5** between listings from different agencies.

**Three hard-won cautions, all from real failures:**

1. **Store the hash as hex TEXT, not INTEGER.** A 64-bit dHash with the
   top bit set exceeds SQLite's *signed* 64-bit INTEGER and raises
   `OverflowError` — which silently discarded **half** of every harvest
   until it was caught.
2. **A single shared image is NOT proof.** The first real run matched a
   €520.000 villa at Montedoglio to a €195.000 terratetto on Via Santa
   Croce (reused agency photo), and merged three *different flats* in one
   Trebbio building (shared facade). Now requires `MIN_SHARED = 2`
   images and excludes any image recurring across more than 3 listings
   as agency furniture. Output is **candidates to eyeball**, never
   automatic publication.
3. **A non-match proves nothing.** A different auction triple with
   identical prices shared no photos at all — best hamming 22 against a
   control of 22. Some agencies shoot their own. Photo matching finds a
   *subset*, and a subset is enough: one proven cluster with a 48%
   surface disagreement is a story. Exhaustiveness is not required.

**State:** pipeline works end to end; 52 of 841 listings hashed here
(sandbox calls cap at 120s). Full harvest is ~6.600 thumbnails, ~45
minutes, and should be run on Christopher's machine. No multi-agency
cluster found yet at 6% coverage — expected, not evidence of absence.

### §16c. Marcellini and Centogambe — built S003

`adapters/agencies.py`. The two named agencies absent from Immobiliare,
now covered: **255 Centogambe + 322 Marcellini = 577 more listings**,
against 844 on Immobiliare.

**Access is cleaner than either portal, and was checked before a line
was written:**

```
centogambe   robots.txt = "User-agent: * / Disallow:"  (empty Disallow
             = everything permitted) AND publishes sitemap_index.xml.
             255 listings enumerated directly — no search crawling.
marcellini   no robots.txt at all (404). Enumerated via
             Elenco.asp?Pagina=Elenco&Cat=<category>, 9 categories.
```

Neither refuses a script. Nothing here needs working around, unlike
Immobiliare's detail pages and Idealista's search. Both run at
`config.REQUEST_DELAY_S` with the identifiable UA — these are small
businesses on WordPress and classic ASP, where a hammering is far more
noticeable than on a portal.

**The agency reference number is the real prize.** Centogambe prints
`rif. 0383`, Marcellini `Rif: 11175`, and portals print the same
reference inside the listing description ("Riferimento: 5258", seen on
an Immobiliare detail page). **That is a second join key and a better
one than photographs** — exact, agency-issued, and needing no
eyeballing, where `photomatch.py` only ever produces candidates a human
must confirm. Caveat: Immobiliare descriptions are 2/844 populated in
our data because the search payload omits them and detail pages 403, so
matching on `rif` currently works agency-site → agency-site, and
agency-site → portal only where a reference surfaces some other way.

**A finding, not a parser bug: Marcellini withholds prices.** Every
sampled listing reads `Prezzo: trattativa riservata`. The adapter stores
`price=None` with `price_withheld=True` rather than coercing or
dropping — how much of an agency's inventory hides its price is a
measure of market opacity and belongs in the output. Quantify the rate
on the full run.

**CORRECTED S004 — the rest of Marcellini's "prices" were brackets.**
The listings that don't say *riservata* carry a price **bracket**, not a
price: live pages read `Prezzo: meno di € 100.000` or
`tra € 200.000 ed € 300.000`. `to_int()` took the first number, so all
152 "priced" rows landed on exact €100k multiples and the report printed
a fabricated +245% flagship contradiction (a €29.000 flat against the
"€100.000" that actually meant *under* €100.000). The adapter now stores
the bracket text in `listings.price_bracket` and puts a figure in
`price` only when the listing's own description prints one
("Prezzo 214.000,00" — 31 of 229 stored descriptions do). Those 31 are
real asking prices and produced the best price contradiction found so
far (Citerna, §16d). The 149 bracket-only rows need the next harvest to
recover their exact bracket text (`'bracket (unresolved)'` marks them);
a stored bracket still bounds the price, so once recovered it can catch
a rival's price falling *outside* the bracket.

Probe verified 2026-08-28: 8/8 Centogambe refs, prices and surfaces
parsed. One bug found and fixed — a `rif` regex without a word boundary
matched inside *pe·rif·eria* and produced `ref=eria`.

    python3 -m adapters.agencies --probe

Not yet wired into the database; `parse_*` returns dicts shaped for
`listings`, but a `source`-aware upsert and a comune normalisation pass
are still needed (Marcellini's `Zona` carries comuni outside scope —
Verghereto, Citerna — which must be filtered to `config.COMUNI`).

### §16d. `contradictions.py` — the publishable output (S003, verified S004)

**The agencies contradict each other, and this is the report that shows
it.** No OMI, no negotiation ladder, no assumed parameters. It compares
the agencies to their own published figures.

**Current, verified state (S004):**

```
properties listed by 2+ agencies WITH a disagreement    40
  disagree on PRICE       9    median 10%   worst 81% (unverified)
  disagree on SURFACE    33    median 13%   worst 110%
  disagree on TYPOLOGY   11    (changes which OMI band applies)
  plus LOCATION disagreements (new axis, see below)
  verified by hand, eyeball pass on every matched photo pair:  15 of 40
```

S003's headline was 158 (10 price / 146 surface / 40 typology). The
drop to 40 is not lost findings, it is two removed fabrications
(§16c's Marcellini brackets, which both faked price gaps *and* joined
unrelated listings through shared bracket values; and photo joins in
the hamming 7–10 band, every one of which was false — a kitchen matched
a bathroom) plus the guards below. What survived verification is
stronger than what the 158 claimed: see `docs/verification-S004.md`
for the 16-case verified set, led by Via Tiberina (525 vs 1065 m² on
the same photo-confirmed house) and Citerna (€214.000 vs €270.000,
both real asking prices, same photo-confirmed ruin).

First run, on Immobiliare's 844 plus 19 agency rows (superseded,
kept for the record):

```
properties listed by 2+ agencies WITH a disagreement    66
  disagree on SURFACE    58    median 7%   worst 48%
  disagree on TYPOLOGY   23    (changes which OMI band applies)
  disagree on PRICE       0    <- STRUCTURAL, see below
```

The flagship case, five agencies on one auction:

```
Via della Ginestra, Sansepolcro — all at EUR 110.625
  Centro Aste Arezzo          132 m²
  Aste Preaste Investimenti   133 m²
  Professione Aste             97 m²
  Simplex Domus                90 m²
  Valerio Pisano              (no surface)
  -> 48% apart on the same property
```

**Zero price disagreements is a limitation, not a finding.** The `price`
and `price+surface` routes use price *as the join key*, so they can only
ever surface listings that already agree on price. **Price
contradictions can only be found by the `ref` and `photo` routes**,
which do not depend on price — and both need the full harvests
(`run_agencies.py`, `photomatch.py --harvest`). That is the single
strongest reason to finish them.

### Matching routes, each labelled in the output (revised S004)

| route | strength | note |
|---|---|---|
| `ref` | **decisive** | the agencies' own reference numbers agree. Their identifier, not our inference |
| `photo` | **identity** (S004) | 2+ **distinct** shared images at hamming ≤5. Eyeballed 12/12 correct |
| `price` | strong | identical price **only when it is not a round number** |
| `price+surface` | good | round price, surfaces within 15%, streets present and not contradicting — and if either street is blank, the price point must be **rare** (exactly the two listings corpus-wide) |
| `photo-weak` | **candidate only** | a single distinct shared image at ≤5; must be eyeballed (a lived-in kitchen proved one real; a reused villa shot once merged €520k with €195k) |

**S004 measured where photo evidence breaks**, by eyeballing every
matched pair in all 17 multi-agency clusters: every cluster whose best
pair sat at hamming ≤5 was the same property (12/12); every cluster
resting only on 7–10 was two different properties (5/5). So
`MATCH_THRESHOLD=10` remains only as the candidate net;
`STRONG_THRESHOLD=5` is what merges. Two further S004 fixes in
`photomatch.py`: hashes are deduped **within** a listing before
counting shared images (a WordPress site serving `-scaled.jpg` and
`-740x554.jpg` of one photograph used to satisfy `MIN_SHARED=2` by
itself), and `contradictions.py` consumes per-edge strength labels.

**The verified overlay.** `phase0/verified_clusters.json` records the
S004 eyeball verdicts as data: confirmed clusters carry their note into
the output ("Verified by hand, 2026-08-29 — …"); any cluster containing
a rejected set is suppressed. Confirmed applies only when the emitted
cluster sits *inside* the verified member set — a merge that pulls in
extra listings makes a bigger claim than the one that was checked, and
prints as candidate again. Like `id_anchors.json`, this file is
human-measured and cannot be regenerated: it is committed to the repo,
not gitignored.

**A fourth axis: location (S004).** Verified same-property pairs
disagree on *where the property is* — the same Fresciano flat filed
under Badia Tedalda by two agencies and Sestino by a third; the same
Monterchi rustico at "Località Omarino" vs "località Padonchia".
`disagreements()` now reports comune conflicts always, and
address conflicts on identity-evidence clusters (where a differing
street is a finding, not a mismatch signal).

**Clustering: pairs merge only on IDENTITY evidence.** `ref` and `photo`
are identity claims and merge transitively; `price` / `price+surface`
are similarity claims and stay as emitted pairs.

This was got wrong twice, in opposite directions, and both are worth
remembering:

1. **Merging everything transitively.** "Surfaces within 15%" is not an
   equivalence relation — 100 links to 115, 115 to 130, 130 to 150 —
   so union-find chained unrelated listings into blobs. One cluster
   reached **14 listings at €200.000 including eight different
   Marcellini refs**, spanning 100 to 160 m²; another merged
   *Coloniche, Negozi, TerreniEdificabili and Appartamenti* into a
   single "property". Union-find needs an equivalence relation; a
   tolerance is not one.
2. **Over-correcting with a coherence rule.** Requiring every member to
   sit near the cluster's median surface then deleted the findings:
   Via della Ginestra — five agencies, one auction, an odd price to the
   euro, surfaces 90 to 133 m² — was rejected for a 48% spread, *which
   is the discovery*. The rule now applies **only to similarity-built
   clusters**, since identity evidence is exactly what earns the right
   to believe a large surface gap.

**Typology is compared on NORMALISED labels.** Marcellini writes
category headings in the plural, so the report was printing
`appartamenti vs appartamento -> different OMI band`, which is a plural,
not a finding — and publishing it would let an agent dismiss the real
disagreements beside it. `colonica`/`casale`/`podere` all normalise to
`rustico` for the same reason. What survives — `appartamento vs
terratetto`, `rustico vs villa` — genuinely changes the band.

**Two further false-positive classes, found and fixed on the first runs,
both of which would have been publicly embarrassing:**

1. **Round prices group the whole market.** Matching on €250.000 alone
   pulled *nine* Sansepolcro listings into one "property" spanning 85 to
   6.000 m². Via della Ginestra worked only because €110.625 is an odd,
   computed auction figure. The price route now requires a non-round
   price, or surface corroboration.
2. **Common price + common size collide.** €170.000 at 105/120 m²
   appeared on three different streets as three separate "matches".
   Fixed by rejecting pairs whose normalised street names contradict.

3. **Blank streets can't contradict (S004 — the Cherubino cluster).**
   Five €280.000 listings became one "property" because the guard above
   had nothing to fire on: both Romolini rows carried no address at all.
   Read in full, the two Romolini listings are a stream-side villetta
   (ref 2963) and a centro-storico B&B palazzo (ref 940) — different
   properties at the same round price, with three riders on three
   different frazioni. Fix: a round-price pair with a blank street is
   believed only when the price point is rare — exactly those two
   listings corpus-wide (€29.000 appears twice and is one flat;
   €280.000 appeared five times and was five houses).

Also rejects any cluster whose surfaces differ by more than 200% unless
reference numbers agree — 410 m² against 70.350 m² is a house and a
field, not a disagreement.

Withheld prices are counted separately and never rendered as €0 or as a
contradiction.

    python3 contradictions.py            # summary + detail
    python3 contradictions.py --md       # contradictions.md, per property

### §16e. Opacity is itself the finding (S003)

Two of the nine agencies hide a large share of their own inventory, by
two different mechanisms. Neither is a bug in our pipeline; both belong
in the published output.

```
Centogambe   79 of 255 listings (31%) are PASSWORD-PROTECTED
             "Accesso negato. Inserisci la password per continuare."
             Published in their public sitemap, then gated.

Marcellini   126 of 278 (45%) say "Prezzo: trattativa riservata"
             and the REST publish only a bracket ("meno di € 100.000",
             "tra € 200.000 ed € 300.000") — S004. Effective price
             opacity of the price field: 100%. The only real prices
             Marcellini publishes anywhere are the 31 listings whose
             free-text description happens to print one.
```

**The Centogambe diagnosis took three attempts and the first two were
wrong**, which is worth recording so nobody re-runs the same dead end:

1. *"31% fetch failure, probably transient"* — wrong; the same URLs fail
   every time.
2. *"Their host is throttling us, slow down"* — wrong; raising the delay
   from 4s to 8s recovered exactly zero of them. `stored 0`.
3. **Correct:** opened one in a real browser and got a password form.
   The wall is deliberate and applies to browsers too.

**Do not retry these and do not attempt the password.** A gate is a
closed door. They are recorded as gated and counted.

That an agency password-gates a third of its listings while listing them
publicly, and another withholds prices on well over half, is exactly the
opacity the site exists to expose — and it needs no matching, no OMI and
no assumptions to state. It is arguably the single most publishable
fact found so far.

### A lead worth checking, not yet a finding

Immobiliare listing **128457332** stands at **€280.000**; the Idealista
sample showed a Sansepolcro listing cut **€280.000 → €265.000 (−5%)**.
If those are the same property, **Immobiliare is showing a stale
pre-cut price** — which would mean asking prices in the dataset run
high, and the whole overpricing measure with them. Not confirmed:
identity needs an address and surface match. **Check it**; if it
generalises it is a large correction and a cross-portal finding in its
own right.

### Also unresolved before publication

- **Surface basis.** OMI states **L (lorda**, walls included**)**; the
  advertised figure's basis is unestablished (§7). If it is wall-
  exclusive, every fair value here is understated by 5–10%.
  `NET_TO_LORDA` is left at 1,0 rather than invented.
- **Duplicates.** The worst-10 list already shows three Monterchi rustici
  at the same €980.000. `dupes.py` found 42 clusters (S002) and must run
  before any ranked list is published.
- **Citerna** still has no bands — 53 listings unpriced.
