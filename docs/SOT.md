# Borgo Vero — Source of Truth

**Last updated:** 2026-08-27 (S002)

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
| Sansepolcro | 179 | Pieve Santo Stefano | 67 |
| Anghiari | 111 | Monterchi | 38 |
| Caprese Michelangelo | 82 | Badia Tedalda | 34 |
| Citerna | 60 | Sestino | 31 |
| | | **All eight** | **602** |

Phase 0 runs Sansepolcro + Anghiari only — 290 listings, ~12 requests.
All eight is ~27 requests. The universe is 602, not the ~1,500 originally
assumed.

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
| Ingest | Working, verified live 2026-08-27 |
| Database | **Not present.** Needs a fresh run — ~12 requests |
| OMI bands | **Downloaded and verified.** Arezzo 2025-2 and 2021-1, valori + zone + KML, in `data/QIP…/`. Loader tested: 53 rows across both comuni, sanity anchors pass. Not yet loaded into a database, because there is no database |
| ID curve | 23 measured anchors, 2021-03 to 2026-08 |
| Site generator | Preview pages only, demo + real sample |
| Idealista adapter | Written S002, **selectors unverified** — see §9 |

**Every percentage in §5 still rests on placeholder bands** — they were
computed in S001 and have not been recomputed. §8 records what the real
bands say about them, and it is not flattering.

---

## 5. Findings so far

From 289 listings collected 2026-08-27, 261 usable (90%): Sansepolcro 178,
Anghiari 111.

```
ASKING €/m²
  median                    €1.318/m²
  p10 / p90                 €500 / €2.316

vs OMI BAND CEILING          (placeholder bands)
  median                    +14,2%
  IQR                       −18,9% to +53,7%
  p90                       +107,7%
  above the ceiling         58% of listings
  more than +50% over       28% of listings
```

**The median is not the story. The spread is.** An IQR from −19% to +54%
means this market has no consensus price — same kind of property, same
comuni, same moment. That inconsistency is a stronger and more defensible
claim than "the market is overpriced".

Lead with: *28% of listings ask more than 50% above the state's own
registered band*, and *the interquartile range spans 73 percentage points*.
Do not lead with "the market is 40% overpriced" — the data does not support
it.

### Where the overpricing sits

| | n | median €/m² | median size | over ceiling |
|---|---|---|---|---|
| rural types | 92 | €1.381 | 240 m² | +23% |
| urban types | 169 | €1.318 | 118 m² | +13% |

This inverts the assumption the build was carrying: the historic centre is
the *better*-priced part of this market, not the worse. **Open question —
see §8.**

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

1. **OMI bands are placeholders.** Sansepolcro centro €1.100–1.400 and
   Anghiari €880–1.410 are anchored on prior figures, not the Agenzia file.
   Rural bands were approximated at 0,72× centro and are the least
   trustworthy of all. Every percentage moves when the real file loads.
2. **Surface basis unresolved.** See §7. Confirm the OMI file's basis before
   believing either column.
3. **Zone assignment is coarse.** Immobiliare's own `macrozone` where present
   ("Centro" → centro storico, everything else → periferia), keyword fallback
   otherwise. Good enough to split a distribution, not to publish per-listing.
4. **Single source.** Immobiliare only. Idealista carries ~5% more inventory
   in Sansepolcro; agency-exclusive listings are invisible to both.
5. **EPC is null in Phase 0.** Detail pages only, not needed yet.
6. **Sub-86M listings share one DOM figure.** Bucketable, not rankable.

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
| S002 | 2026-08-27 | Real bands loaded and inspected. Fixed a second load-breaking bug: `sniff()` skipped the AdE preamble line but `load()` did not, so `DictReader` took the caption as its header and matched zero rows. Added `rows()` as the single correct entry point, plus `zone_labels()` joining `Zona_Descr` from the ZONE file on `LinkZona`. `band_for()` filtered by zone only for centro storico — everything else collapsed across all zones, handing a rural farmhouse a 1900 ceiling set by C1 villas; now filtered via `config.ZONA_TO_FASCIA` on OMI's own B/C/D/E/R letter. Its no-match fallback also spanned Capannoni to Ville (280–1900); now residential only. Rustici filed under Ville e Villini with the span reported (§8). README/SOT commands corrected to `python3`. |
| S002 | 2026-08-27 | OMI: found `Comune_descrizione` is `SAN SEPOLCRO` with a space — the loader's exact-match filter would have dropped every Sansepolcro band and then all 178 Sansepolcro listings, silently. Added `config.norm_comune` on both write and lookup. Corrected `stato`→`Stato`, `zona`→None (Zona_Descr is in the zone file), semester→2025-2, sanity anchor→1000–1400, all verified against the OMI web consultation. Confirmed basis is **L (lorda)** — neither surface column matches it (§7). Seismic-suspension list checked: Arezzo never appears. Bulk files requested (Arezzo, 2025-2 and 2021-1, with zone perimeters). Built `adapters/idealista.py` with offline `--selftest`; added `price_previous`, `price_cut_pct`, `eur_m2_stated` and a migration. |
| S002 | 2026-08-27 | Anchor harvest completed (23 anchors, 2021-03→2026-08). Confirmed 69% issuance spread — piecewise only, no seasonal dip. `id_curve.py`: extrapolation past outer anchors replaced with floor/ceiling bounds. `analyze.py`: now reads the confidence flag it was always given — confidence mix in data quality, containment-based bucketing for bounds, ambiguous bounds excluded from DOM splits. `config.DOM_MIN_CONFIDENCE` added. `selftest.py` extended to cover both bound paths. This file created. |

---

## 15. Next

1. Download the OMI *valori* file → `omi.py --inspect` → fix `OMI_COLUMNS`
   → `omi.py` → **check the sanity anchors before anything else.**
2. Fresh ingest (`run.py`), then `id_curve.py --backfill`, then `analyze.py`.
3. Re-run the rural-vs-urban comparison against real bands (§8).
4. Write the Idealista adapter — the price-drop history expires (§9).
5. Harvest pre-2021 ID anchors (§6).
