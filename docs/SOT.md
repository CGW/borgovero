# Borgo Vero — Source of Truth

**Last updated:** 2026-08-27 (S002, wrap)

This file is the authority. Where it disagrees with a README, a results
document, a code comment or a memory, this file wins — and the disagreement
should be fixed here in the same sitting.

Reconstructed in S002 from `phase0/README.md`, `bv-site/PHASE0-REAL-RESULTS.md`,
`bv-site/CROSS-PORTAL-TEST.md`, `phase0/config.py` and
`phase0/data/id_anchors.json`. S001 ended mid-run and never wrote it, which
cost the first half of S002.

---

## 1. What this is

Borgo Vero tests, and then publishes, one claim about the Valtiberina
property market: **asking prices sit above the state's own registered
valuation bands, and the gap is largest on listings that have sat unsold
the longest.**

The state bands are OMI (*Osservatorio del Mercato Immobiliare*, Agenzia
delle Entrate) — free, bulk-downloadable, semestral, per comune, per zone,
per typology. They are the neutral reference the whole project stands on.

Phase 0 publishes nothing. It exists to answer whether the claim survives
contact with real data, and therefore which site gets built.

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
  analyze.py             the hypothesis test
  selftest.py            synthetic end-to-end check
  db.py                  SQLite schema
bv-site/                 static generator + preview pages (Phase 1 groundwork)
```

Python 3.9+, stdlib plus `requests` and `beautifulsoup4`. SQLite. No pandas,
no build step.

**Storage is disposable and gitignored.** `data/`, `cache/`, `*.sqlite` and
`phase0_results.csv` are not in the repo. The database is regenerated from
cache in seconds and from the network in under a minute. Do not treat a
missing `phase0.sqlite` as lost work. The one file in `data/` that *is*
precious is `id_anchors.json` — see §6.

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

## 4. Current state (end of S002)

| | |
|---|---|
| Ingest | **Done.** 844 listings, eight comuni, 44 requests, fully cached |
| Database | Present. Re-parsing costs zero requests |
| Detail pages | **403 Forbidden.** Search served, detail refused — see §12 |
| OMI bands | Arezzo 2025-2 and 2021-1, valori + zone + KML, in `data/QIP…/`. Loads: 108 rows across seven comuni, sanity anchors pass. **Citerna is province of PERUGIA and needs its own request** — 60 listings currently drop |
| Zone KML | Downloaded, **unused.** `AR20252.zip`. The fix for §12's zone problem |
| ID curve | 23 measured anchors, 2021-03 to 2026-08 |
| Site generator | Preview pages only, demo + real sample |
| Idealista adapter | Written S002, **selectors unverified** — see §9 |

**§5 now rests on real bands.** What it does not rest on is a settled
surface basis, a real zone assignment, or a decided comparison point —
see §5's four caveats before quoting any number from it.

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

### Do NOT record this as a refutation

Taken at face value the ceiling column says the market is not overpriced
and the decision gate prints `THESIS NOT SUPPORTED`. That reading is not
safe, for four reasons, three of which push the same way:

1. **Ceiling vs midpoint flips the sign.** −13,0% and +7,0% are the same
   data. "Above the top of the official range" and "above the middle of
   it" are different claims and both are honest. §12 records that this
   has not been decided.
2. **The advertised surface is contaminated** — see §7. Always in the
   direction of looking cheaper. Unknown rate.
3. **Zone assignment is a text guess** (§12), and it hands rural stock
   urban ceilings.
4. **OMI is built from registered sale contracts** — what property
   actually sold for, not what it was asked. 844 listings asking below
   the range real transactions fall into, while almost nothing sells, is
   close to self-contradictory. When a measurement contradicts an obvious
   fact about the world, suspect the measurement.

**The honest state is: not yet measurable to the precision the claim
requires.** Recording a refutation now would harden it into next
session's starting assumption — exactly how S001's invented rural bands
became a "finding".

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
data entry**, at an unknown rate, and always in the direction of looking
cheaper. It cannot be detected from the search page: the breakdown that
reveals it is on detail pages, which return **403** to a script (§12).

Immobiliare's own stated `Prezzo al m²` divides by commerciale — confirmed
on all three (1.492, 746, 1.160 €/m²).

**Measuring the contamination rate needs ~20 listings read in a browser.**
Until then every €/m² in §5 has an unquantified downward bias.

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

1. **Surface basis is contaminated, not merely unknown.** §7. Unquantified
   downward bias on every €/m². Needs ~20 browser reads to size.
2. **Ceiling vs midpoint is undecided.** −13,0% vs +7,0% on identical
   data. This is a framing choice nobody has made deliberately yet.
3. **Zone assignment is a text guess.** `map_zona` uses Immobiliare's
   `macrozone` (64,7% populated), keyword fallback otherwise. It puts 393
   of 696 listings in the centro storico and only 9 in campagna, while 146
   are farmhouses — so rural stock is priced against C/D/E ceilings up to
   1900 instead of R ceilings at 1400. **The zone KML fixes this properly**
   by point-in-polygon on the lat/lon already stored, and it is already
   downloaded.
4. **Detail pages return 403.** Search served, detail refused. Closes off
   commerciale, stated publication dates, agency references and EPC. Not
   an expense question — the route is shut. Do not circumvent it; the
   Wayback archive is the legitimate alternative for a sample.
5. **Per-listing bands are coarse.** `band_for()` takes min-of-mins and
   max-of-maxes across several OMI typologies and every zone in a fascia
   class. Fine for a distribution, wrong for any single property.
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
| S002 | 2026-08-27 | Anchor harvest completed (23 anchors, 2021-03→2026-08). Confirmed 69% issuance spread — piecewise only, no seasonal dip. `id_curve.py`: extrapolation past outer anchors replaced with floor/ceiling bounds. `analyze.py`: now reads the confidence flag it was always given — confidence mix in data quality, containment-based bucketing for bounds, ambiguous bounds excluded from DOM splits. `config.DOM_MIN_CONFIDENCE` added. `selftest.py` extended to cover both bound paths. This file created. |

---

## 15. Next

Ordered by how much each moves the unresolved answer in §5.

1. **Zone by point-in-polygon.** Parse `data/QIP…/AR20252.zip` (KML, already
   downloaded), assign each listing by its stored lat/lon. Pure stdlib —
   `xml.etree` plus ~30 lines of ray casting, no new dependencies.
   Replaces the text guess that currently puts 393 of 696 listings in the
   centro storico and 9 in campagna.
2. **Size the surface contamination.** Read ~20 listings in a browser and
   count how many fold accessories into the headline `Superficie` (§7).
   No script can do this — detail pages are 403.
3. **Decide ceiling vs midpoint**, deliberately, and write the reasoning
   into §5. Both are honest; publishing without choosing is not.
4. **Request Citerna's bands** — Forniture OMI, provincia di PERUGIA,
   2025-2. Recovers 60 listings. One-shot download, 7-day expiry.
5. **Probe Idealista** (`python3 -m adapters.idealista --probe`) and fix
   `SEL` against what it reports. Its search page is not 403'd and its
   price-drop history is the one dataset with an expiry date (§9).
6. Harvest pre-2021 ID anchors (§6) — now the *only* route to DOM, since
   stated publication dates are behind the 403.
7. Compare the 2021-1 bands against 2025-2 to settle whether date-matched
   bands are needed (§8).
