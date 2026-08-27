# Phase 0 — hypothesis test

Answers one question: **is the Valtiberina market actually overpriced against OMI, and by how much?**

Publishes nothing. Ingests Sansepolcro and Anghiari from Immobiliare, loads OMI bands, estimates days-on-market from listing IDs, and prints a distribution with an explicit decision gate.

**Verified against the live site 2026-08-27.** Three findings changed the design:

### 1. The search page carries everything — no detail fetches needed

Immobiliare embeds complete listing data for all 25 results in the search page's `__NEXT_DATA__` blob: price, surface, rooms, floor, typology, coordinates, macrozone, condition, photo IDs, and the selling agency.

|  | requests |
|---|---|
| Per-listing fetching | 602 |
| Search-page harvest | **27** |

A ~22× reduction. Full Valtiberina ingest is minutes, not hours, with proportionally less ToS exposure. Detail pages are needed only for EPC class and full description — neither of which Phase 0 uses.

### 2. The universe is 602, not ~1,500

Measured live, Immobiliare only:

| Comune | | Comune | |
|---|---|---|---|
| Sansepolcro | 179 | Pieve Santo Stefano | 67 |
| Anghiari | 111 | Monterchi | 38 |
| Caprese Michelangelo | 82 | Badia Tedalda | 34 |
| Citerna | 60 | Sestino | 31 |
| | | **All eight** | **602** |

Phase 0 scope (Sansepolcro + Anghiari) is 290 listings in ~12 requests.

### 3. There are two surface figures, and they decide the answer

A live listing showed `Superficie: 115 m² | commerciale 183,2 m²` — a **59% difference**. Agencies quote *commerciale*, which weights balconies, terraces and garages into the total, because it makes €/m² look lower.

Running the analysis both ways on test data:

```
Median over OMI ceiling, net surface:          +22.0%
Median over OMI ceiling, commerciale surface:  -16.9%
```

**Same listings. Opposite conclusions.** This is not a detail — it is the single biggest threat to the validity of the whole exercise, and it is also precisely the manipulation the project exists to expose. `SURFACE_BASIS = "both"` in config runs it both ways and prints the divergence before anything else.

**Before publishing either number, confirm which surface basis the OMI file uses.** If they don't match, the comparison is meaningless.

---

## Install

```bash
cd phase0
pip install requests beautifulsoup4
```

Python 3.9+. Everything else is stdlib — SQLite, no pandas, no build step.

## Verify the pipeline before touching the network

```bash
python3 selftest.py
```

Seeds a throwaway database with **invented** listings shaped like a market with a stale tail, runs the analysis, and should print a `STALE TAIL IS THE STORY` verdict. If that works, the stats and gate logic are sound and anything that goes wrong afterwards is ingest, not analysis.

Delete `selftest.sqlite` when done.

---

## Run order

### 1. Set your contact URL

`config.py` → `CONTACT_URL`. The script refuses to run until you do.

An identifiable user agent is the cheapest protection available: it turns "unknown bot hammering our site" into "someone we could just email." Ten seconds, and it materially changes how a portal responds if they notice you.

### 2. Probe the adapter

```bash
python3 -m adapters.immobiliare --probe
```

Fetches one search page and reports per-field yield across all 25 listings on it, plus any typologies it couldn't map.

The JSON paths were verified live on 2026-08-27, so this should pass first time. It exists because Next.js payloads get reorganised: `find_results()` locates the results array by looking for a list whose items carry a `realEstate` key, rather than indexing a fixed path, so a restructure doesn't break it. If Immobiliare renames that key, the probe tells you immediately instead of the ingest silently storing nulls.

Also note what the probe says about `robots.txt`. The script **reports and does not enforce** — deliberately. What you do with that is a decision you should make once, knowingly, rather than inherit as a default.

### 3. Ingest

```bash
python3 run.py
```

~4s per request, single-threaded, every response cached to disk. **~12 requests, under a minute** for Sansepolcro + Anghiari. Add `--comuni` with the full list from `config.ALL_VALTIBERINA` for all eight (~27 requests).

Re-running costs zero requests — everything is served from the HTML cache, so reparsing after a parser change is free.

Ends with a field-yield report. Below-threshold yields mean stop and fix the parser: a partial crawl produces confident wrong numbers, which is the worst possible failure for this project.

### 4. OMI bands

Download the semestral *Quotazioni immobiliari* export from the [Agenzia delle Entrate](https://www1.agenziaentrate.gov.it/servizi/Consultazione/ricerca.htm). You want the **valori** file, not the **zone** file. Free, bulk, no scraping.

```bash
python3 omi.py --inspect     # prints real columns + suggested mapping
python3 omi.py               # loads, then sanity-checks
```

Column names shift between releases, so nothing is assumed. `--inspect` prints a ready-to-paste `OMI_COLUMNS` block.

The sanity check compares loaded bands against your known anchors — Sansepolcro B1 ~€1,245/m², Anghiari €880–1,410/m². **If those don't line up, the column mapping is wrong and every number downstream is garbage.** That check exists so you find out now rather than after building a site on it.

### 5. Listing dates (Job B)

```bash
python3 id_curve.py --backfill
python3 id_curve.py --report
```

Seeded with your two known anchors (~47M ≈ 2018–19, ~116M ≈ 2024–25). Two points is a straight line, and ID issuance isn't linear — volume grew, so the curve bends. **Mid-range estimates are the weakest, and the Valtiberina stale tail sits exactly there.**

Add pairs as you find them:

```bash
python3 id_curve.py --add 78500000 2021-06-15 --method wayback
```

Cheapest sources: Wayback CDX first-capture for any listing URL, listings that state their own publication date, agency pages that date their listings.

**This is the urgent one.** It's the only route to days-on-market for anything listed before your ingest starts. If access ends — block, C&D, a layout change you can't follow — every pre-existing property becomes permanently unmeasurable and the archive can only grow forward from that day.

### 6. The answer

```bash
python3 analyze.py
```

Prints data quality, the distribution against band ceiling and midpoint, splits by DOM / comune / typology, and the decision gate. Writes `phase0_results.csv` sorted worst-offender first.

**Eyeball the top 20 rows.** If they look like parse errors rather than real listings, fix the parser before believing any median.

---

## Reading the verdict

The DOM split matters more than the headline median. Two very different markets produce the same overall number:

- **Uniform** — everything sits ~30% over the band. The claim is *"this market is overpriced."*
- **Stale tail** — fresh listings sit near the band, old ones sit far above and drag the median up. The claim is *"stale listings are wildly overpriced and distort what everyone believes the market is worth."*

The second is narrower, much harder to argue with, and points the whole build at long-DOM properties — Tier 7 ranked lists become the front page rather than a side feature.

The gate prints which shape it found.

**One caution on a `UNIFORM OVERPRICING` verdict:** with only two ID anchors the DOM buckets may be too coarse to resolve a spread that's actually there. Add anchors and re-run before accepting it.

---

## Files

| File | |
|---|---|
| `config.py` | scope, rate limits, OMI mapping, gate thresholds |
| `fetcher.py` | polite HTTP, disk cache, robots reporting, 404/410 capture |
| `adapters/immobiliare.py` | discovery + JSON-first parsing + `--probe` |
| `omi.py` | band loader with `--inspect` and sanity check |
| `id_curve.py` | ID→date interpolation (Job B) |
| `run.py` | ingest orchestrator + field-yield health |
| `analyze.py` | the hypothesis test |
| `selftest.py` | synthetic end-to-end check |
| `db.py` | SQLite schema |

## What this does not do

No publishing, no page generation, no dedup, no photo embeddings, no disposition classification. Those are Phase 1 and later — see the build spec. This exists to tell you which site you're building before you write a page of it.

## Known limitations

- **Surface basis is unresolved and it matters more than anything else here.** See finding 3 above. Confirm the OMI file's basis before believing either number.
- **`zona` now uses Immobiliare's own `macrozone`** (e.g. "Centro") where present, falling back to keyword matching. Better than pure text guessing, still not an OMI microzone boundary — good enough to split a distribution, not to publish per-listing.
- **DOM is an estimate from two ID anchors.** Treat buckets as ordinal, not precise. Anghiari's lowest live ID is 69,315,424, which sits between the two known anchors and is worth dating properly — it would sharpen the middle of the curve where the stale tail lives.
- **EPC is null in Phase 0.** It's on detail pages only, and Phase 0 doesn't need it.
- **Single source.** Agency-exclusive listings that never reach Immobiliare are invisible here. That's Phase 2.
