# S006 — continuation prompt

Paste this to open the next session.

---

S006 — Borgo Vero. Read `docs/SOT.md` §17 first — its **S005 block** is the
authority and it overrides both `docs/seo-spec.md` §4.3 and item 2 of §17.1
itself. Then `docs/seo-spec.md` §4.2 and §4.3.

The band deadlock is closed. Route **(b)** was taken in S005 and it was
measured, not argued: deflator uncertainty widens a comune p50 by 14–18%
while the market's own p25–p75 spread is 55–104%, so hand-seeding Tier A
would have removed a fifth of the uncertainty and left the rest. Bands
compute over Tier A+B with interval arithmetic; **all eight comuni publish**
at n = 27–290. Do not reopen this, and do not reopen (c) on index-quality
grounds — the measurement is what makes it a bad trade, and it is recorded.

**S006 is a build session, not a decision session.** The pipeline exists and
the standard is published; what is missing is the pages.

## In order

1. **Listing index pages, `/it/immobili/{comune}/{slug}-{id}/`.** ~676 of
   them, per the §4.2 template contract. The extraction paragraph is the
   first 40 words and is the unit an LLM lifts — price, `stated_m2` with the
   agency's own label, the `sia` interval, `eur_stated` beside `eur_sia`,
   tier, retrieval date. Render from `phase0/normalize.py`; do not
   recompute anything in the template.
   **Tier C listings get a page too** where they carry a finding or a price
   history, and that page states plainly why there is no number of ours.
2. **Comune report template, `/it/comuni/{comune}/`.** Eight of them. The
   band is an interval end to end and is **never** rendered as its midpoint
   — `bv-site/lint.py` has a dormant check scoped to `/comuni/` paths that
   wakes up the moment these pages exist. Publish the two widths side by
   side: our conversion uncertainty and the market's own spread.
3. **Free typology recovery.** 51 priced-and-surfaced listings still sit in
   Tier C for want of a typology, 86 unresolved overall. `_TEXT_RULES` in
   `normalize.py` is where this goes. No detail pages, no new requests.
4. **Re-read `seo-spec.md` §13.** Phase 2's acceptance criteria were written
   expecting three comuni to clear a gate. Eight do. The criteria are not
   wrong so much as no longer the binding constraint, and leaving them
   unread is how a plan quietly stops describing the work.

## Two known-stale things — fix or explicitly defer, do not ignore

- **`docs/seo-strategy.html` is now the stale document.** It still headlines
  "~1.000–3.000 pages", "39 contradictions", "12 comuni" and "29 live". The
  spec and the SOT were corrected in S004/S005 and this was not, so it
  currently disagrees with both. Real numbers: **36 contradictions, 30
  hand-verified, 36 pages live, ~676 index pages, eight comuni.**
- **The OMI data is still missing.** `phase0/data/` holds only
  `id_anchors.json`; the orders deleted on 2026-08-29 were never re-placed
  and `omi.py` exits 1. Re-order **Arezzo 2025-2 (and 2021-1) plus Perugia
  for Citerna**, choosing the option WITH perimeters so the prefix is
  `QIP_`. Until then §17.2's "OMI as external cross-check" cannot run and
  **no band has been checked against any outside source** — worth saying out
  loud before the bands go on a public page.

## Already done in S005 — do not redo

- Route (b) decided and implemented; the Tier-A-only gate retired and
  replaced by n ≥ 8, ≥ 2 agencies, and a p50 interval no wider than the
  worst single deflator (derived, currently 28,0%).
- `phase0/normalize.py` — tiering, deflators, interval bands, publish gate.
  Deterministic; two runs byte-identical. Outputs `normalized.csv` and
  `comune_bands.json`, both gitignored and regenerable in seconds.
- `bv-site/lint.py` — §10.3 lint. Negation-aware by design.
- `metodologia.html` grown into the standard (§3), IT and EN, rendered from
  `normalize.py`'s own tables so the published method cannot drift from the
  applied one. The weighting table is stated on the page as a **published
  choice**, citing §7 only for the garage and garden rows.
- Spec §2 fixed to the eight real comuni; §4.3 rewritten; counts corrected.
- 244 typologies recovered from fields already held; 123 shops and land
  parcels removed from a residential index entirely.

## Cautions that cost real time when ignored

- **`phase0/.gitignore` governs `data/`, not the root one.** Editing the
  root looks like it works. `git check-ignore -v <path>` is the only proof.
- **The sandbox mount cannot journal sqlite and refuses to unlink
  host-created files.** Work on a copy; deliver as SQL text. Never copy a
  `.sqlite` across it.
- **Detail pages 403 to scripts**, Idealista's search 403s and shows bot
  detection, and 79 Centogambe listings are password-gated deliberately.
  None of these are bugs and none should be retried.
- **Never run `git add --dry-run` against this repo from the sandbox** — the
  mount cannot clean up `.git/index.lock` afterwards.
- **A caution nobody re-tests becomes folklore.** CLAUDE.md said for months
  that `id_anchors.json` was not backed up by a push; it was wrong, and the
  correction is the only reason the 23 anchors survived a deletion the same
  afternoon.
- **This project's failure mode is an assumed number hardening into a
  finding**, and S005 produced three of them before catching them: an
  invented 25% width gate that would have suppressed every
  farmhouse-dominated comune, `sia` and `eur_sia` rounded independently so
  the published arithmetic did not check out, and a lint that fired on
  every page because "Fasce OMI" contains the word *band*. Expect to
  generate more; check your own numbers against the database before they
  reach a page.

## Standing, unchanged

Publish the discrepancy, never the accusation. Band, never a point estimate
— and never the midpoint of a band. Never *valutazione*, *stima*, *perizia*
or *assessment*; it is an **indice**. Named agencies are named, so
publication requires identity evidence and a human look.
