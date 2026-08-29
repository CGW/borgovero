# CasaZebra — Source of Truth

**Renamed 2026-08-30 (S007): the product is CasaZebra**, at
**casazebra.it** (bought; casazebra.com is a dormant Wix shell held until
2027 — revisit acquiring it then). Borgo Vero was dropped because
borgovero.it is foreign-held. The repo, its folder, and internal
identifiers (`bv-site/`, `bvc_m2`, `borgo_vero_price`) keep the old name
— they are plumbing, not brand. Historical entries below keep the old
name because they record what was true when they were written.

**Last updated:** 2026-08-30 (S005 — the §17.1 band deadlock resolved as
**(b)**, measured not argued: interval arithmetic over Tier A+B, the
Tier-A-only gate retired, **all eight comuni publishing** at n = 27–290.
`phase0/normalize.py` shipped; `metodologia.html` grown into the standard;
`bv-site/lint.py` added, which caught the site describing itself as *una
valutazione* on all 36 live pages. **Read §17 first — its S005 block
overrides §4.3 of `docs/seo-spec.md` and item 2 of §17.1 itself.**)

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
| S004 | 2026-08-29 | **The strategy inverted: the index is the product, the contradictions are the evidence it is needed.** `docs/seo-spec.md` (contract) and `docs/seo-strategy.html` (argument) adopted, with §17 recording four corrections measured against the database the same day. Load-bearing one: the spec's scope names twelve comuni "already covered by the existing ingest" including Città di Castello and Umbertide — **`config.COMUNI` is eight and those four have zero listings**, are Umbrian, and each needs its own OMI order. Corpus is **~931 publishable pages, not 1.000–3.000**, once the spec's own price+surface gate is applied (Marcellini contributes 31 of 278, because it publishes brackets). **Structural problem: Tier A needs an itemised decomposition, whose only machine-readable source is `surfaceConstitution` on detail pages that 403 — while comune bands are gated on Tier A only, n ≥ 8. As written, no band is publishable at all**, and Phase 2's acceptance criterion is unreachable; three ways out recorded in §17.1, and the choice is the first order of business. Also corrected: "same agency, different portal needs no new scraping" is false — that overlap is empty by construction and needs three or four new adapters, while 107 same-agency same-price groups are free today. The tier system, the land rule, Tier C publishing nothing, the build lint, determinism-as-CI and archive-over-404 are all endorsed unchanged. §3.2's weighting table is flagged as a chosen standard rather than a measurement, because assumed numbers hardening into findings is this project's recurring failure. |
| S004 | 2026-08-29 | **`phase0/data/` was deleted, and the correction made six hours earlier is the only reason the anchors survived.** The whole directory went during a `cp`/`rm` sequence around the Citerna delivery; cause never established, and the sandbox mount — which already refuses to unlink host files and cannot journal sqlite — is the main suspect, so treat it as an operation to avoid rather than a mystery to solve. `id_anchors.json` came back with one `git checkout`, all 23 anchors byte-identical (86.260.004 → 131.271.614). **That file was described in CLAUDE.md and §3 as gitignored and not backed up by a push until this same session tested the claim and found it false.** Had the folklore stood, the anchors would be gone. Everything else in `data/` was genuinely lost: both Arezzo OMI orders and the Citerna one, all re-orderable, no measurement destroyed (§7's readings live in the tracked `surface_reads.py`). Fixes: `phase0/.gitignore` now un-ignores `surface_reads.md`, `surface_sample.md` and `data/*.json` — small human-measured files had no business sharing a fate with 30 MB downloads; and **note that `phase0/.gitignore`, not the root one, governs `data/`** — editing the root looks like it works until `git check-ignore -v` says otherwise. `omi.py` now prints what to re-order and exits 1 instead of raising FileNotFoundError three frames deep. |
| S004 | 2026-08-29 | **Citerna's bands arrived and load — with one shortfall.** `omi.py` takes a repeatable `--path` and defaults to `config.OMI_CSV_PATHS`, because the scope spans two provinces and a single path had silently dropped Citerna for two sessions. Verified before the deletion: 108 Arezzo + 25 Citerna = **133 rows, all eight comuni**, sanity anchors pass, basis LORDA throughout. Citerna's 25 rows cover zones B1, E1, E2, R1. **The order came as `QI_`, not `QIP_` — quotations WITHOUT zone perimeters**, so Citerna gets bands but cannot be polygon-zoned and falls back to the fascia guess that S003 replaced everywhere else. Re-order as QIP when re-ordering the lost files anyway. |
| S004 | 2026-08-29 | **`self_contradictions.py` — a new axis needing no matching at all.** Compares one listing's structured fields to its own free text, so the entire false-positive class that has cost this project the most cannot occur. **150 candidates: 112 typology, 44 surface. NOT published — every one needs reading first.** Five parser bugs found by spot-checking the first twenty, all now regression-tested: `mq. 450` (Italian puts the unit on either side) read a house's own total as a conflict with its land; "85 mq l'uno" ×2 = the 170 field, agreement misread as a 100% gap; "villa su 3.600 mq" is the plot; **"Località Ville di Roti" matched as a toponym** and would have accused an agency over a hamlet's name; and "villetta a schiera" mapped to *villa* — this module committing the exact category error it exists to catch. "Casa indipendente" is deliberately unscored: the captions using it continue "…su tre lati", which is semi-detached, so the field was right and the flag was mine. **Coverage is asymmetric and the module says so out loud:** Marcellini has 229 descriptions, Centogambe 0, Immobiliare 2 of 844 (detail pages 403), so *surface* is 40 Marcellini vs 4 Immobiliare. An axis whose whole sample is one small agency is a complaint about a business, not a market finding. **Captions (779 of 844, every agency) are what make typology publishable.** |
| S004 | 2026-08-29 | **The remaining ten clusters, the missing pages, and the weekly task.** Read both listings for each of the ten `price+surface` clusters that had no photographs — the method the Anghiari villa established. **Seven confirmed**, several of which explain their own disagreement: the Anghiari casale differs by exactly the 43 m² fienile one agency counts and the other does not; Villa Colcello is 250 vs 285 m² between agencies while one of them says 250 in its field and "circa 300 mq" in its own text; Cortesi calls a Sansepolcro house *singola* where Leonardi calls it *bifamiliare*. **One rejected**: three flats at €145.000 in the same converted colonica at La Scheggia — a building split into equally priced units, invisible to price+surface matching and visible only in the listing text. **Two inconclusive**, which added an `inconclusive` verdict to the overlay: "these are different properties" and "this could not be settled" are different claims, and recording the second as the first would stop a later session ever looking again. 36 contradictions, 30 verified, and nothing held back for want of a look. Then the site: `chi-siamo` and `metodologia` are emitted (the footer had linked to both from every page since the generator existed), language landing pages added (the header brand link was dead too), and a **right of reply** published — 7 days, page comes down if the agency is right. The methodology page is this site's own rather than `templates.py`'s, which documents the OMI arithmetic these pages never run. Two bugs found by checking rather than assuming: a page told readers it was matched by "identical price and compatible surface" when NEITHER agency published a price (the evidence fallback chose the nearest label, not the weakest), and the stale-page sweep deleted the new landing pages because it derived "files to keep" from "URLs to advertise". Whole-site link check now passes with zero broken links. Finally, the weekly task runs all three sources plus photo hashing, and reports the remaining Marcellini bracket placeholders. |
| S004 | 2026-08-29 | **Second verification pass — the 19 held-back clusters.** Nine had photographs to compare; all nine settled. Confirmed: the Anghiari Liberty villa (Lionard 550 m² vs Romolini 490 m², both € 1.600.000) — established from the listings' own TEXT, since they share no photographs at all (best hamming 17), a working demonstration that a non-match proves nothing; Fragaiolo, Via della Bozzia (three Cortesi-brand listings of one property), and four single-photo Marcellini pairs. Rejected: Via Casa al Vento, where three Leonardi listings were joined by one identical photograph of the LAKE VIEW — the furniture guard missed it because it appears in exactly three listings and the rule drops images appearing in more than three; lowering that threshold would destroy real three-agency clusters, so the verified overlay is the right instrument, not a tuning change. The reported 81% price gap did NOT survive: Leonardi lists the same villa at € 2.900.000, but that listing was last updated in December 2020 and offers a combined sale with a second building, so its price is not comparable — which motivated `drop` support in the overlay, removing one member from an otherwise good cluster instead of discarding the finding with it. **39 contradictions, 23 verified; worst price gap is now the real 26% at Citerna, not a phantom 81%.** Also fixed three nondeterminisms that made rebuilds churn every URL on the site: page slugs carried a run ordinal, the comune label came from an arbitrary cluster member (it flipped between Badia Tedalda and Sestino — the very disagreement being published), and equal prices left row order to chance. Slugs are now hashed from member ids; two consecutive builds are byte-identical. The generator also reports stale pages it could not delete rather than leaving them silently served. |
| S004 | 2026-08-29 | **A standing warning was folklore.** CLAUDE.md and §3 both said `id_anchors.json` is gitignored and not backed up by a push, and it was repeated to Christopher twice this session. It is tracked, in HEAD since `dda2cab`, and hash-identical to the working copy. Corrected in both places, with the lesson: a caution nobody re-tests stops being a fact. |
| S004 | 2026-08-29 | **Shipped the first pages.** `bv-site/contradictions_site.py` writes one page per property — every agency's figures side by side, each linked to its own listing — IT + EN, sitemap and robots, reusing `templates.py`'s shell. 21 of 40 published; the other 19 need `--candidates` because publication requires identity evidence and these are named local businesses. Output in `bv-site/dist-contradictions/` (gitignored, regenerable). |
| S004 | 2026-08-29 | **Hand-verification pass, then the fixes it demanded.** Every matched photo pair in all 17 multi-agency clusters eyeballed via contact sheets; the three §15.1 named cases read on live pages. Results: 12/12 clusters at hamming ≤5 real, 5/5 at 7–10 false (Matteotti and Cherubino both die); the Badia triple is one Fresciano flat but its +245% was a parser artifact — **all 152 Marcellini "prices" are search brackets** ("meno di € 100.000"), stored as asking prices. Fixed: `agencies.py` stores `price_bracket` and extracts real prices from descriptions (31 recovered, incl. Citerna €214.000 → a real +26% against Leonardi's €270.000 on a photo-verified ruin); `photomatch.py` dedupes hashes within a listing (resize loophole) and merges only on ≤5 evidence, labeling `photo` vs `photo-weak`; `contradictions.py` gains a verified overlay (`verified_clusters.json`, human-measured, committed), a location axis (agencies disagree on the comune: Badia Tedalda vs Sestino), a round-price rarity guard, and `--db`. Report regenerated: **158 → 40 honest contradictions, 15 verified.** The mount now refuses live sqlite writes (ALTER hit disk I/O error), so the corrections were worked out on a sandbox copy and ship as **`phase0/apply_S004_fix.py`** — run it once against the real database (`python3 apply_S004_fix.py`, `--dry-run` to preview). It is idempotent, touches only Marcellini rows, and bypasses `db.observe()` so no fabricated cuts land in `price_history`. A full replacement dump also exists (`phase0_S004_restore.sql`) but the in-place script is the intended route; **the repo's `phase0.sqlite` carries the old bracket prices until one of them is applied.** Verification evidence: `docs/verification-S004.md`. |
| S005 | 2026-08-30 | **The band deadlock resolved on a measurement, and the index pipeline shipped.** §17.1's choice taken as **(b)**: bands are computed over Tier A+B with interval arithmetic, a Tier A listing entering as a zero-width interval, and the unfireable Tier-A-only n ≥ 8 gate is retired. The decision was measured rather than argued — **deflator uncertainty widens the p50 by 14–18%, while the market's own p25–p75 spread is 55–104%**, so hand-seeding Tier A would have spent 64+ browser reads removing a fifth of the uncertainty and left the rest standing. (c) is correspondingly weaker than it looked and should not be revisited on index-quality grounds. **All eight comuni now clear the gate at n = 27–290 and 9–29 agencies**, so Phase 2's "three comune reports" is exceeded on day one. New `phase0/normalize.py` (deterministic, byte-identical across runs); spec §2 corrected to the eight real comuni, §4.3 rewritten, §10.3 lint extended, counts fixed to 36/30/36. **Fifth correction to §17: ~676 listing pages, not ~931** — §17 applied only the price+surface gate and omitted §4.2's tier condition; say ~700. Typology recovered for 244 listings from `typology_raw` and titles already held (no detail pages, no 403), and 123 shops and land parcels removed from a residential index entirely. Three self-inflicted defects caught before shipping and commented in place: a **band-width gate invented at 25%** that would have silently suppressed every farmhouse-dominated comune (rustico's own deflator is 26,7% wide — it killed Monterchi), now derived from the deflator table; **`sia` and `eur_sia` rounded independently**, so a reader dividing our published surface into our published price got a different answer from our published €/m² — fatal on a site whose product is checkable arithmetic; and a **lint that fired on all 35 contradiction pages** because "Fasce OMI" contains the word band. |
| S005 | 2026-08-30 | **The site was calling itself a *valutazione* on all 36 published pages.** Found by the new `bv-site/lint.py`: the footer declaration read *"Borgo Vero è una valutazione indipendente"* — §3.5's regulated word, affirmative, about ourselves — while the method page two blocks below said *"non è una perizia"*. The site contradicted itself about its own nature on every page it published, which is the exact class of thing it publishes other people for. Three separate hardcoded copies existed (footer, IT about, EN about); the EN one said *"third-party assessment"* and survived the first fix because §3.5 never names that word. All now read *indice* / *index*, and **`assessment` is added to the forbidden list — §3.5 should gain it.** The lint deliberately is **not** a substring ban: it excuses negated and attributed uses, because a checker that forces *"It is not an appraisal"* off the page deletes the disclaimer and leaves the claim. It also matches on word boundaries, after the first version reported the English *"days on market are e-stima-ted"* as an Italian regulated-term violation. `metodologia.html` grown into the standard per §3 — surface definition, the land rule, the weighting table, tiers, deflators and the band method — rendered **from `normalize.py`'s own tables** so the published method cannot drift from the applied one. Build verified: 78 pages, two builds byte-identical, lint clean, zero broken internal links. |
| S005 | 2026-08-30 | **The OMI data was never missing — three path strings were stale.** This document, `omi.py`'s error text and the S006 prompt all recorded `phase0/data/` as lost since the 2026-08-29 deletion. All three AdE orders were on disk and intact the whole time: **Arezzo 2025-2 (`QIP1422173`), Arezzo 2021-1 (`QIP1422174`), both with 36 KML perimeter files, and Perugia 2025-2 (`QI1422048`)**. What broke is that **the AdE order number changes on every download** — the re-order came back as 1422173 where `config.OMI_CSV_PATHS` and `zones.KML_ZIP` still named 1421390 — so `omi.py` exited 1 on a missing file and the absence was read as absent data. Paths corrected in both files. **`omi.py` now loads 133 band rows across all eight comuni, including 25 for Citerna, which had none for three sessions** (S002 recorded Citerna as bandless and it stayed that way); `zones.py` re-runs cleanly off the recovered KML zip, 775/1.295 listings zoned. This is the `id_anchors.json` lesson a second time, in the other direction: the first was a caution nobody re-tested, this was an absence nobody looked for. **`ls phase0/data/` before concluding a file is gone.** Remaining gap, known and bounded: the Perugia order is `QI_`, not `QIP_` — no zone perimeters — so Citerna's 69 listings have bands but no point-in-polygon zone and fall back to the fascia guess. Re-ordering Perugia with perimeters closes it. |

---

## 15. Next

**Rewritten at the S003 wrap.** The old list was ordered by "how much
each moves the unresolved answer in §5" — a question the project no
longer asks. §1 is now the Target Offer and §16b–e the contradictions,
so the ordering below is: *what stands between here and a page anyone
can read.*

### RESOLVED at the S004 wrap: the index is the product — see §17

The proposal below was accepted and is now specified in
`docs/seo-spec.md`, with four measured corrections in **§17.1** that
override the spec where they conflict. **Read §17 before the spec.** The
live decision is no longer *whether* to build the index but **how comune
bands get published at all**, since Tier A depends on data behind the
403 — §17.1 correction 3 lays out the three options.

The original framing, kept because the reasoning is what makes the
decision reviewable:

### The strategic turn proposed at the end of S004

Christopher's proposal, and it reframes the product: **stop trying to
estimate value, and standardise the denominator instead.** The reasoning
is that a Zestimate is not buildable here and calling one a valuation is
where the trouble starts — Zillow runs on ~100M homes and millions of
recorded sales, a Valtiberina comune sees perhaps twenty transactions a
year, none public in bulk, and a model trained on asking prices predicts
asking prices. Whereas the 6× villa (§ below) proves the real problem is
that **550 m² from one agency is not 550 m² from another**, so no two
listings in the valley are comparable. Publish one consistent surface
definition and the normalised €/m² that falls out:

    At the surface this agency states:  €3.265/m²
    On a consistent definition:         €2.900–3.300/m²
    Comune band (OMI):                  €1.100–2.400/m²

Legally it is the same footing as what the site publishes today — a
fact, not an opinion of value. **Band, never a point estimate**, and
never called a *perizia*, a valuation or an appraisal: in Italy that is
a regulated act by a qualified technician. It is an index.

The compounding argument is the strongest part: tracking every listing
to its delisting — "withdrawn after 1.240 days at €X" — is also how the
dataset for a real valuation gets accumulated. **The index we can build
today is the mechanism that collects the data for the Zestimate we
cannot.** Nobody publishes asking-price-to-outcome history in Italy.

**What the data says about buildability, measured S004:**

- `listings.mq_commercial` is **0 of 844**. The search payload carries
  ONE surface, of the contaminated basis §7 measured.
- There is **no €/m² in the search payload** either, so commerciale
  cannot be recovered by division from Immobiliare's own stated figure.
- `surfaceConstitution` — the row-by-row breakdown that would let us
  recompute a consistent surface — is **detail-page only, and those
  403** (§12.4).

So the normalised figure **cannot be a point estimate for 844
listings**. It CAN be a band, honestly, today: §7 already read 20 detail
pages by hand, found 78% of headline surfaces clean with errors running
both directions, and bootstrapped correction factors across 696
listings. That interval is the band, and its width is not a hedge — the
width IS the incomparability, which makes it the finding.

**The decision that gates the alternative: does the 403 line move?**
True surfaces for all 844 are readable in Christopher's own browser —
that is how §7 got its 20. Doing it at scale is the same act this
project has declined by script three times and re-affirmed in S003. A
20-listing sample for measurement and an 844-listing harvest for
publication are different things. **Decide it deliberately; do not
arrive at it because the index wants it.**

Two things the rebuilt plan must state: what the index does when a
listing has no usable surface (6 of 844 have none, and every Marcellini
listing whose price is a bracket), and whether that 403 line moves —
because that decides whether the index ships as a band or as a number.

### Two further axes proposed, and what they are actually worth

**Same agency, different portal** — appealing, because there is no
"different mandate" defence. **Currently EMPTY by construction**: the
overlap between agencies on Immobiliare and agencies whose own site we
hold is zero, since Marcellini and Centogambe were chosen precisely
because they are absent from the portal. Idealista cannot fill the gap
(403 + bot detection, §9). It needs three or four new adapters —
Leonardi, Cortesi, Romolini and House all run their own sites. **What
IS free today: 107 groups where one agency lists two or more properties
at an identical price on the portal.** Marcellini's 11291/11316 — one
brick house at 160 m² and 1.450 m² — is already verified.

**Temporal contradictions** — the text route is dead for the same
reason as §7: "new to market" claims live in descriptions, and
Immobiliare descriptions are 2 of 844. Zero freshness claims are
visible. But two things are free:

1. **The payload carries the portal's own `isNew` flag.** 16 listings
   flagged new; **3 of them over a year old by listing ID**, one at 951
   days. The portal's badge against the portal's own ID sequence.
2. **Within the 36 verified properties, 6 of the 27 with two or more
   portal listings show the same house looking more than a year older
   depending which agency's listing you find.** Fragaiolo is 4 days old
   at Rexer, 83 at R.E.Volution and 1.733 days at a third. That is
   §8's relisting/clock-reset question, answerable on the corpus in
   hand.

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
6. **Re-order the OMI files** — all of them, lost with `data/`
   (see the S004 changelog). Arezzo 2025-2 and 2021-1, plus Perugia
   2025-2 for Citerna. **Choose the option WITH zone perimeters so the
   prefix is `QIP_`** — the Citerna order that arrived was `QI_`,
   without the KML, so it could not have been polygon-zoned anyway.
   Ordering fresh fixes that at no extra cost. `omi.py` now tells you
   this when the files are missing. Nothing else is blocked: the
   contradiction pages do not touch OMI.
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

## 17. The index — the strategy adopted at the end of S004

`docs/seo-spec.md` is the contract; `docs/seo-strategy.html` is the
argument. **Where they disagree, the spec wins. Where the spec disagrees
with THIS section, this section wins**, because what follows was checked
against the database on 2026-08-29 and the spec was written before that
check.

The strategy, in one line: **the index is the product and the
contradictions are the evidence it is necessary.** The site stops
competing on prices and competes on comparability — one surface standard
applied to every listing, publishing `eur_stated` (the agency's own
arithmetic) beside `eur_sia` (price ÷ internal habitable area) on every
page. The gap between those two is then the story on every page rather
than on thirty. Adopted; §15's opening decision is resolved in favour of
the index.

The Anghiari villa is the exhibit and it is ours, verified in S004: two
agencies, the same €1.600.000, published €/m² of €508 and €3.265 — 6,4×
apart — because one divides by a *commerciale* of 3.150 m² that swallows
a 2.600 m² park. Under the land rule the 6,4× collapses to the real
disagreement underneath: 550 m² against 490 m², about 12%. That is a
question a buyer can put to an agent. The 6,4× never was.

### §17.1 FOUR CORRECTIONS TO THE SPEC, ALL MEASURED

**1. The scope list is wrong, and it is the load-bearing error.**
`seo-spec.md` §2 names twelve comuni "already covered by the existing
ingest", including San Giustino, Città di Castello, Monte Santa Maria
Tiberina and Umbertide; the HTML headlines "12 comuni". Measured:
`config.COMUNI` is **eight**, and those four have **zero listings
ingested**. They are Umbrian, in Perugia province — so each needs its own
OMI order, and Città di Castello is far larger than anything in scope and
would dominate any corpus-wide figure. Fix the spec to eight, or treat
the other four as an explicit expansion with its own cost.

**2. The corpus is ~931 pages, not 1.000–3.000.** Applying the spec's own
publish gate (price present AND a usable surface) to the current
database: immobiliare 785 of 844, centogambe 115 of 173, marcellini
**31 of 278** — because Marcellini publishes brackets, not prices, so the
gate excludes almost all of it (§16c). Still a 25× multiplier on the
36 pages that exist, still transformative, but plan on ~900 and say ~900.

**3. THE STRUCTURAL PROBLEM: Tier A is unreachable by script, and comune
bands are gated on it.** Tier A needs an itemised decomposition. The only
machine-readable source for one is `surfaceConstitution` in the detail
page's `__NEXT_DATA__` — and **detail pages return 403** (§12.4). Our
whole corpus has 2 descriptions of 844 and `mq_commercial` is 0 of 844.
So essentially every listing is Tier B or C.

But §4.3 computes the comune band from **Tier A listings only, n ≥ 8,
two or more agencies**. With Tier A near-empty, **no comune band can be
published at all** — and the comune report is one of the five page types
and the target of the reframed keyword list. Phase 2's acceptance
criterion ("three comune reports live with bands") is unreachable as
written. This would surface in about week four of Phase 2, after the
pipeline was built.

Three ways out, and the choice belongs in the next session, not later:

  a. **Hand-decompose to seed Tier A.** 8 per comune × 8 comuni = 64
     browser reads minimum, more for villas. This is the §3.4 manual
     loop, and it is the honest successor to S004's verification. It
     also caps how fast bands can appear.
  b. **Recompute the band on Tier A + B with interval arithmetic** —
     a band of bands. Wider, weaker, but publishable now and arguably
     more honest than a point from eight hand-picked listings.
  c. **Move the 403 line** and harvest detail pages for the whole
     corpus. This project has declined that three times and re-affirmed
     it in S003. It is a real option; it is not a free one, and it must
     not be arrived at because the index wants it.

#### RESOLVED in S005, 2026-08-30: **(b), decided on a measurement**

The question "is the band too wide to publish?" was never measured, so
S005 measured it before choosing. Tier B intervals were computed for all
676 eligible listings using §3.4's deflators, villas excluded to Tier C
as §3.4 requires, and the comune p50 interval compared against the
market's own p25–p75 spread of the same listings at their deflator
midpoints:

```
comune                nB   ag   p50 interval (b)   width    market p25-p75   width
sansepolcro          290   29   1.430 - 1.656      14,6%    1.127 - 1.971    55,3%
anghiari             136   24   1.680 - 1.963      15,5%    1.217 - 2.423    65,6%
caprese-michelangelo  64   17     986 - 1.154      15,7%      682 - 1.648    90,1%
pieve-santo-stefano   59   23     606 -   696      13,8%      499 - 1.106    92,7%
citerna               43   11   1.046 - 1.235      16,6%      813 - 1.492    60,0%
badia-tedalda         29   12     479 -   572      17,8%      391 -   952   104,4%
sestino               28    9     981 - 1.145      15,4%      675 - 1.263    55,2%
monterchi             27   13   1.699 - 2.011      16,8%    1.100 - 2.445    72,4%
```

**Deflator uncertainty is 14–18%. The market's own spread is 55–104%.**
The uncertainty option (a) would have spent 64+ browser reads to remove
is roughly a fifth of the variation that is genuinely in the stock and
would remain after the work. That is the whole argument: (a) sharpens the
term that is not dominating.

Consequences, all now written into `seo-spec.md`:

- **The Tier-A-only n ≥ 8 gate is retired.** The band is computed over
  Tier A + B with interval arithmetic, a Tier A listing entering as a
  zero-width interval. The gate becomes n ≥ 8, ≥ 2 agencies, and a p50
  interval no wider than the worst single deflator's own range —
  **derived, not chosen**: `normalize.GATE_MAX_WIDTH_PCT`, currently
  28,0% (rustico's 26,7% × 1,05). This entry originally said a flat 25%,
  which was itself one of S005's invented numbers — narrower than
  rustico's own deflator, so it suppressed Monterchi while looking like
  rigour. Corrected S006; the code was already right. The width gate is
  what the tier condition was trying to express, and it fails loudly on
  a comune too mixed to summarise rather than silently on one merely
  lacking decompositions.
- **All eight comuni clear it immediately**, at n = 27–290 and 9–29
  agencies. Phase 2's "three comune reports with bands" is not just
  reachable, it is exceeded on day one — and §13 should be re-read with
  that in mind rather than left as written.
- **The band is an interval end to end, and is never rendered as its
  midpoint.** Added to the §10.3 lint as the load-bearing check: the
  failure mode is a template collapsing the interval for tidiness, which
  would publish this site's own criticism in this site's own voice.
- **(c) is now clearly the wrong trade** and should not be revisited on
  index-quality grounds. It buys the 14–18% at the cost of a boundary
  held four times and legal exposure on the only asset the product has.
  If it is ever taken it must be for a different reason than this one.

**A fifth correction, found while measuring.** Item 2 above says ~931
publishable pages, but it applied only the price-and-surface gate. §4.2's
actual gate is price **AND tier ∈ {A,B}**, and 255 listings are Tier C:
676 pages, not 931. The C's are 107 villas (§3.4 forces them to A or C,
correctly) and 146 with no typology — but that 146 is largely recoverable
without touching a detail page, because Marcellini carries `typology_raw`
for all 31 of its rows and Centogambe has titles for 83 of its 115. Worth
noting several of those titles read *Locale commerciale* and *Negozio*,
which should probably not be in a residential index at all. **Say ~700
until that recovery is done**, and expect ~800 after.

**4. "Same agency, different portal … needs no new scraping" is false.**
Measured: the overlap between agencies on the portal and agencies whose
own site we hold is **empty**, because Marcellini and Centogambe were
chosen precisely for being absent from Immobiliare, and Idealista is out
of bounds (§9). It needs three or four new adapters. What IS free is
**107 groups where one agency lists two or more properties at an
identical price on the portal** — no mandate defence, no sync defence,
and Marcellini's 11291/11316 (one house at 160 m² and 1.450 m²) is
already verified.

Minor: the documents say 29 and 39 findings in different places. The
current, verified number is **36 contradictions, 30 hand-verified, 36
pages published**.

### §17.2 What the spec gets right, and should not be renegotiated

- **The tier system, and Tier C publishing no index at all.** A site
  objecting to confident numbers from unconfident inputs cannot publish
  confident numbers from unconfident inputs. Tier on every page.
- **The villa row is the honest admission**: a 0,30–0,80 deflator makes
  inference worthless for exactly the category where the abuse is worst,
  so villas with land are decomposed by hand or carry no index.
- **Land never enters a surface figure.** One line, kills the whole abuse
  class, indefensible to argue with because nobody walks on a park.
- **Language discipline enforced by build lint, not by care** — no
  *valutazione*, *stima*, *perizia*, *valuation*, *appraisal*, ever.
- **Byte-identical rebuilds as a CI contract.** Earned in S004; the index
  generator is exactly the thing that would reintroduce run ordinals.
- **The furniture guard is scale-dependent** (`>3 listings`) and misbehaves
  at 10×. Genuine four- and five-agency clusters become common while
  shared views multiply. Becomes a ratio or a co-occurrence test — and
  note S004 already hit its failure mode from the other side: a lake view
  in exactly three listings that the guard could not drop.
- **Archive over 404.** Delisted listings keep their URL and become the
  asking-price-to-outcome record — which is also §8's relisting question
  and the only route to a real valuation later.
- **OMI as external cross-check, not as basis.** Correct, and it
  reconciles §1's reframe with the bands now in the repo: where a
  normalised p50 diverges sharply from the OMI band for the same zone,
  that is either a bug or a finding, and we want to know which.

### §17.3 The weighting table is a CHOSEN standard, not a measurement

§3.2's coefficients are a normative choice — which is legitimate and is
what a standard is — but nothing in this repo measured them, and this
project's failure mode is assumed numbers hardening into findings (S001's
placeholder bands, §16's DOM ladder). The one measured anchor we have is
§7: Immobiliare's own rule is `SUM(surface × coefficient)` over rows
tagged *Principale*, with garage at 50% and garden at 10%, applied
inconsistently by agents. Say on `/it/metodo/` that the table is a
published choice, cite §7 for the parts that match observed practice, and
never present it as derived.

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
