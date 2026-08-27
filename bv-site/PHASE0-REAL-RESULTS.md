# Phase 0 on real data — Sansepolcro + Anghiari

**Collected 27 August 2026 from Immobiliare.it.** 289 listings, 261 usable (90%).
Anghiari 111, Sansepolcro 178.

---

## Headline

```
ASKING €/m²
  median                    €1.318/m²
  p10 / p90                 €500 / €2.316

vs OMI BAND CEILING          (placeholder bands — see caveat)
  median                    +14,2%
  IQR                       −18,9%  to  +53,7%
  p90                       +107,7%
  above the ceiling         58% of listings
  more than +50% over       28% of listings
```

**The median is not the story. The spread is.**

An IQR running from −19% to +54% means this market has no consensus price. A quarter of listings sit meaningfully below the band and a quarter sit more than half again above it — for the same kind of property, in the same comuni, at the same time. That inconsistency is a stronger and more defensible claim than "the market is overpriced," and it is exactly what Borgo Vero was set up to make visible.

**28% of listings asking more than 50% above the band ceiling** is the number worth leading with.

---

## Where the overpricing actually sits

| | centro storico | elsewhere |
|---|---|---|
| listed <1yr | +7% | +15% |
| listed 1–2yr | +13% | **+52%** |
| listed 2yr+ | −23% | −8% |

Peripheral and rural listings are further above the band than centro storico ones. That inverts the assumption the build has been carrying — the historic centre is the *better*-priced part of this market, not the worse.

| | n | median €/m² | median size | over ceiling |
|---|---|---|---|---|
| rural types | 92 | €1.381 | 240 m² | +23% |
| urban types | 169 | €1.318 | 118 m² | +13% |

---

## The days-on-market finding cannot be reported

The age gradient came out non-monotonic — rising to +47,6% at 1–2 years, then reversing to −32,0% beyond 4 years. I tested three explanations before accepting any of it:

- **Typology mix?** No. Excluding rural types entirely, the reversal survives: −13,4% at 2–4yr, −34,3% at 4yr+.
- **Size effect?** No. Correlation between surface and €/m² is **−0,09** — negligible, and the size buckets are non-monotonic.
- **The ID curve?** **Yes.**

```
ID CURVE SANITY
  id range              56.648.574 .. 131.983.778
  below the 47M anchor           0
  between the two anchors       61
  ABOVE the 116M anchor        200   <-- 77% of the dataset
```

**Two anchors, and 77% of the data lies beyond the later one.** Every DOM figure for those 200 listings is a straight-line extrapolation past the last known point, using a slope fitted between 2018 and 2024. ID issuance is not linear, so the further past 116M you project, the worse it gets.

Corroborating evidence that it is wrong: the implied **median DOM is 0,9 years**, against a market known to run 2–4 years. The curve is compressing time.

**No days-on-market claim can be published until the curve has more anchors.** This is the single most actionable result here, and it makes the Phase 0 Job B backfill urgent rather than merely advisable — it needs pairs *above* 116M most of all.

### A second reading worth testing

If the curve turns out to be roughly right, then a 0,9-year median in a 2–4 year market means something else: **listings are being deleted and reposted, resetting their IDs.** The gap between apparent age and real age would then be a direct measure of how much relisting happens — which is the §4 clock-reset behaviour, and would make relist detection the highest-value feature in the build rather than a defensive one.

Both readings point the same way: get more ID anchors, and start observing `first_seen` directly.

---

## Caveats, in order of severity

1. **The OMI bands are placeholders.** Sansepolcro centro €1.100–1.400 and Anghiari €880–1.410 are anchored on prior figures, not the Agenzia delle Entrate file. Every percentage above moves when the real bands load — and the rural bands, which I approximated at 0,72× the centro figure, are the least trustworthy of all. This is Phase 0's next step.

2. **DOM is unreliable** (above).

3. **Single source.** Immobiliare only. Idealista carries ~5% more inventory in Sansepolcro and agency-exclusive listings are invisible here entirely.

4. **Surface basis unresolved.** These figures divide by the advertised (floor-area) surface. The *commerciale* figure was not captured in the search payload, and on the one listing where both were visible they differed by 59% — enough to flip the sign of the headline.

5. **Zone assignment is coarse.** Immobiliare's `macrozone` field, where present; "Centro" mapped to centro storico, everything else to periferia. Real OMI microzone boundaries are finer.

---

## What this changes

**Ship the spread, not the median.** "28% of listings ask more than 50% above the state's own registered band" and "the interquartile range spans 73 percentage points" are both defensible on this data. "The market is 40% overpriced" is not.

**Reprioritise Phase 0.** The ID backfill moves from urgent-because-it-expires to blocking — no DOM claim is publishable without it, and DOM is the moat.

**Reconsider where to point the site.** The overpricing concentrates outside the centro storico, not inside it. The build has been assuming the opposite.
