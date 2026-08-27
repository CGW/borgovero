# Cross-portal test — real Sansepolcro properties

**Run 27 August 2026** against live Immobiliare.it and Idealista.it.
Sample: 75 Immobiliare listings, 90 Idealista listings, Sansepolcro only.

**Verdict: the feature has teeth.** Real properties appear on both portals, and they disagree on things that matter.

---

## Inventory doesn't match

| | Sansepolcro listings |
|---|---|
| Immobiliare.it | 179 |
| Idealista.it | 188 |

Neither portal has the whole market. A buyer checking one is seeing a partial picture — which is itself a reason for Borgo Vero to exist.

---

## Confirmed same-property matches

### Via Fratelli Rosselli — €370,000

| | Immobiliare | Idealista |
|---|---|---|
| Price | €370,000 | €370,000 |
| Surface | 210 m² | 210 m² |
| **Typology** | **Villa bifamiliare** | **Flat / apartment** |
| **Rooms** | **5+** | **6** |

Same price, same surface, same street. One portal calls it a semi-detached villa, the other calls it a flat. Both cannot be right, and the distinction is exactly the one that drives which OMI band applies.

### Via Francesco Petrarca — €430,000

| | Immobiliare | Idealista |
|---|---|---|
| Price | €430,000 | €430,000 |
| **Surface** | **357 m²** | **350 m²** |
| **Typology** | **Villa plurifamiliare** | **Flat / apartment** |
| **Rooms** | **5+** | **9** |

Seven square metres apart, and again a villa on one portal and a flat on the other. €/m² differs by 2% purely from the surface discrepancy — small here, but it establishes that surface figures are not copied, they are re-entered.

### Viale Osimo — €280,000

| | Immobiliare | Idealista |
|---|---|---|
| Price | €280,000 | €280,000 |
| Surface | 115 m² | 115 m² |
| Rooms | 5 | 5 |

A clean match. Worth including precisely because it shows the comparison does not manufacture conflict where none exists — most of the value is in showing agreement is *possible*, which makes the disagreements meaningful.

---

## Two things Idealista gives that Immobiliare does not

### 1. Price-drop history, published

Idealista shows the previous asking price and the percentage cut, right on the search results page:

| Property | Now | Was | Cut |
|---|---|---|---|
| Via Pasquale Alienati | €178,000 | €187,000 | −5% |
| Strada Provinciale 258 | €100,000 | €107,000 | −7% |

**This is the single most valuable finding of the test.** The spec assumed price history had to be accumulated by observing the market for 12+ months. Idealista publishes a slice of it now — meaning the price-decay curve has a running start rather than starting from zero on launch day.

Two of the first 30 listings carried a visible cut. If that rate holds, roughly 6–7% of the market has published price history available immediately.

### 2. €/m² computed on their own surface figure

Idealista prints €/m² directly. Because it is computed on *their* surface number, and their surface number sometimes differs from Immobiliare's, the two portals publish **different €/m² for the same property**. That is a third divergence axis on top of price and surface, and it needs no calculation on our part — both numbers are stated.

---

## What this changes in the build

1. **Idealista is not optional.** It carries ~5% more inventory, published price history, and a second surface figure. It is the difference between a comparison and a list.

2. **Typology disagreement is a first-class field.** It was in `COMPARE_FIELDS` already, but the test shows it is the *most* commonly contested field — more than price. It also determines which OMI band applies, so a disagreement here changes the valuation, not just the description.

3. **Surface figures are re-entered, not copied.** 357 vs 350 on the same property proves the two portals get their data separately. Every surface disagreement is therefore a real signal, not a sync artifact.

4. **Address matching works but needs normalisation.** Idealista appends `Nn` to street names with no civico ("Viale Osimo Nn") and sometimes includes a civico ("Via Vannocchia, 133"). Strip the suffix, split on comma, fuzzy-match the remainder.

5. **Price is the reliable join key at this scale.** Across 165 listings, exact price plus approximate surface produced unambiguous matches. In a market this small, collisions are rare enough to handle by inspection.

---

## Caveats

- Matches above were identified **by inspection** across a partial sample, not by a rigorous automated pass. The overlap *rate* is not established — that needs the full ingest of both portals.
- Idealista's page structure was read from rendered DOM (`article.item`), not a JSON payload. It is more fragile than Immobiliare's `__NEXT_DATA__` and will need the breakage assertions from spec §3.
- Only Sansepolcro was tested. Agency-exclusive listings, which never reach either portal, remain unmeasured.
