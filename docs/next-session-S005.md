# S005 — continuation prompt

Paste this to open the next session.

---

S005 — Borgo Vero. Read `docs/SOT.md` **§17 first**, then `docs/seo-spec.md`.
§17 records four corrections measured against the database that override the
spec where they conflict; the spec was written before that check.

The strategy inverted at the end of S004: **the index is the product, the
contradictions are the evidence it is necessary.** One surface standard
applied to every listing, publishing `eur_stated` beside `eur_sia` on every
page, so the gap is the story on ~900 pages instead of on 36.

**The decision that comes before any code, and it is not "shall we build the
index" — that is settled. It is: how does a comune band get published at
all?**

Tier A requires an itemised surface decomposition. The only machine-readable
source is `surfaceConstitution` in the detail page `__NEXT_DATA__`, and
detail pages return 403 (§12.4). Our corpus has 2 descriptions of 844 and
`mq_commercial` is 0 of 844. So the corpus is essentially all Tier B and C —
while `seo-spec.md` §4.3 computes comune bands from **Tier A only, n ≥ 8**.
As written, **no band is publishable**, and Phase 2's acceptance criterion
("three comune reports live with bands") cannot be met. Three options in
§17.1:

  a. hand-decompose ~8 listings per comune to seed Tier A (64+ browser
     reads, the §3.4 manual loop, caps how fast bands appear);
  b. recompute the band over Tier A + B with interval arithmetic — a band
     of bands, wider and weaker but publishable now, and arguably more
     honest than a point from eight hand-picked listings;
  c. move the 403 line and harvest detail pages.

(c) reverses a boundary held three times and re-affirmed in S003. It is a
real option. Do not let it be arrived at because the index wants it — if it
is taken, take it deliberately and record why.

## Then, in order

1. **Fix `seo-spec.md` §2 to the eight comuni actually ingested.** It names
   twelve including Città di Castello and Umbertide, which have zero
   listings, are Umbrian, and each need their own OMI order. Every §4.3 gate
   calculation downstream depends on this list.
2. **Correct the counts throughout both documents**: 36 contradictions, 30
   hand-verified, 36 pages — not 29 or 39. And ~931 publishable listing
   pages, not 1.000–3.000.
3. **Build `/it/metodo/` first**, per §3 — it is the citation target, the
   right-of-reply defence and the page every other page is an application
   of. Note the contradictions site already emits a `metodologia.html`
   written in S004; that is the page to grow into the standard, not a new
   one. Say plainly there that §3.2's weighting table is a published
   *choice*, citing §7 for the parts matching observed practice.
4. **Then the normalisation pipeline and tier assignment**, on the three
   comuni that can clear a gate.

## Already done in S004 — do not redo

- 36 contradictions, **30 hand-verified**; `phase0/verified_clusters.json`
  carries every verdict with its reasoning (`confirmed` / `rejected` /
  `inconclusive`, plus `drop` for a member that does not belong).
- The site is built and correct: 36 property pages plus `chi-siamo` and
  `metodologia`, IT + EN, right of reply published, **zero broken internal
  links, two consecutive builds byte-identical**. `bv-site/contradictions_site.py`.
- Marcellini "prices" were **search brackets**; fixed, 31 real prices
  recovered from description text, `price_bracket` column added.
- Photo matching: merges only on hamming ≤ 5 (12/12 real at ≤5, 5/5 false
  at ≥7), hashes deduped within a listing.
- `self_contradictions.py` exists — 150 candidates, **not published**,
  needs the hand-check pass (§17 / task list).
- The weekly task runs all three sources plus photo hashing.

## Cautions that cost real time when ignored

- **`phase0/data/` was deleted on 2026-08-29.** `id_anchors.json` came back
  from git; the OMI files did not. **Re-order them** — Arezzo 2025-2 (and
  2021-1) plus Perugia for Citerna, choosing the option WITH perimeters so
  the prefix is `QIP_`. `omi.py` now tells you this and exits 1.
- **`phase0/.gitignore`, not the root one, governs `data/`.** Editing the
  root looks like it works. `git check-ignore -v <path>` is the only proof.
- The sandbox mount **cannot journal sqlite and refuses to unlink
  host-created files**. Work on a copy; deliver as SQL text. Never copy a
  `.sqlite` across it.
- Detail pages 403 to scripts; Idealista's search 403s and shows bot
  detection; 79 Centogambe listings are password-gated deliberately. None
  of these are bugs, none should be retried.
- **A caution nobody re-tests becomes folklore.** CLAUDE.md said for months
  that `id_anchors.json` was not backed up by a push. It was wrong, we
  tested it on 2026-08-29, and that correction is the only reason the 23
  anchors survived the deletion the same afternoon.

## Standing, unchanged

Publish the discrepancy, never the accusation. Band, never a point estimate.
Never *valutazione*, *stima* or *perizia* — it is an index. Named agencies
are named, so publication requires identity evidence and a human look.
