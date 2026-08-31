# S009 — continuation prompt

Paste this to open the next session.

---

S009 — CasaZebra. Read `docs/SOT.md` §15's **S008 OUTCOME** block first,
then the S008 changelog row.

## S008 is fully landed — do not redo any of it

Applied, deployed and indexed on 2026-08-31: the typology fix and the
harvest data are in the real database, casazebra.it serves the S008
build (dossier blocks live, 1.630 URLs), and Search Console reports the
sitemap **Success, 1.630 pages discovered**. The 45 typology-renamed
slugs are 404ing by design until the archive layer exists (§6).
`/it/comuni/` — the front door — is now a table, one row per comune,
`Chiesto al m²` against `Venduto al m²` (OMI 2025-2), both on the
agencies' stated-surface basis, with the three-state colour.

**One judgement is still open and belongs to Christopher, not to code:**
whether Citerna's red row (€884 asked, €350–780 sold — the only comune
where the whole registered-sale band sits below asking) reads as
informative or as an accusation next to five ambers. It was more
prominent as a table row than it had been as a card. If it reads wrong,
the fix is wording or a legend, not deleting the state.

Deploy commands live in CLAUDE.md. Two traps recorded there, both paid
for once already: `build.py` rmtree's `dist-site/.vercel` every build
(so the `vercel link` line is mandatory), and **the CDN serves stale
content on clean URLs after a deploy** — verify with a cache-buster
(`curl -s "https://casazebra.it/robots.txt?cb=$RANDOM"`), because the
clean URL will happily show you the old file and look like proof.

S009 therefore starts at the eyeball queue below, not at a deploy.

## The eyeball queue (§16d — only Christopher's eyes close these)

1. **The €149.000 pair** — SICASA 80620571 / House 126557887, Via XX
   Settembre. Machine is done: 25×21 full galleries, zero shared
   images, floor 3°/2° and vani 5/3 disagree. Record the verdict in
   `phase0/verified_clusters.json` either way (the file holds both
   kinds; an unrecorded look gets repeated).
2. **Via Tiberina 4-way** — the verified Romolini/Leonardi stone tower
   (525/1065 m²) plus Centogambe 0674 + Marcellini 10721 (500/450 m²).
   The new pair is photo-strong INTERNALLY (3 shared images ≤5); the
   bridge between the two pairs is photo-weak. If the four are one
   house, it is a 137% surface spread across four agencies — the
   strongest finding the site would hold. Add to the overlay as
   confirmed (all four ids) or drop the new members.
3. **Centogambe 0032 ↔ Marcellini 10444** — photo-weak, one shared
   image, 90 vs 170 m², Marcellini price withheld.

## Then, in order

1. **Publish the surviving exhibit properly** — 105891071's real story
   is the agency's own headline ("APPARTAMENTO INGRESSO INDIPENDENTE")
   against the portal field (Terratetto) and its own site (cielo
   terra). That is `self_contradictions.py`'s axis; its 150 candidates
   were never published because each needs reading. Decide whether the
   Leonardi case (and how many of the 45 caption-override rows) become
   a finding page, through the §16d gate as always.
2. **itcasa (40 portal rows) and the harvest's known gaps.** All nine
   of Christopher's named agencies are done (S008 second wave); itcasa
   is the largest agency still unharvested. The gaps worth revisiting,
   each measured rather than assumed: **NOW** yields only its homepage
   (50 cards) because `/properties/` and `/citt/` render client-side —
   revisit only if NOW ever ships server-rendered archives, not by
   adding a headless browser; **Romolini** is capped by its robots.txt
   forbidding query-param pagination; **Cortesi/NOW** index cards carry
   no surface, so each unique candidate spends one detail fetch.
   **Tiber has no website at all** and **Lancisi has 68 own-site
   listings and zero portal rows** — both are recorded findings now,
   not to-dos.
3. **Archive layer (§6)** — now URGENT-adjacent: S008 just deliberately
   churned 45 URLs and had nowhere to point their history. Every
   ingest without it deletes history, and the heartbeat multiplies
   ingests.
4. **Weekly heartbeat** — the parser count is now **11** (immobiliare,
   marcellini, centogambe, + eight agency-site indices). Each is
   weekly maintenance forever, and small-business WordPress themes get
   re-skinned without notice, so the heartbeat needs a per-site
   "harvested N, matched M" alert: a theme change shows up as a site
   silently dropping to zero cards, which is exactly what NOW looked
   like before `_merge_windows` (50 cards, 0 prices — a parse failure
   that reported success). **The heartbeat is also what makes the
   ask-to-close ladder possible**: `price_history` currently holds 173
   rows from two timestamps and ZERO observed changes, so every
   negotiation figure the site could publish today would be
   `DOM_DISCOUNT`'s unmeasured extrapolation. Agency sites usually show
   a cut before the portal does, and there are now 1.165 own-site cards
   with prices — roughly 20–30 observed cuts makes the first rung real.
5. **Derived build inputs, so deploys can be git-connected** (raised by
   Christopher, S008). Every build currently reads the 3,4 MB scraped
   corpus, so even a CSS change needs the database and a local run —
   which is why this project deploys by CLI while Skoolgrades deploys
   on push. The site does not actually need the corpus: it needs
   `normalized.csv` (262 KB), `comune_bands.json` (3 KB), the findings
   export `build.py` already constructs, and the OMI subset. Track
   those (~300 KB), build from them, and presentation changes become
   push-to-deploy with CI running the real gates. **The cost is a new
   invariant**: a derived export that silently drifts from the corpus
   publishes stale numbers with nothing complaining, so it needs a
   freshness gate (export data-date vs corpus) before it is trusted —
   size the work as "make staleness impossible", not "write an export".
   Pairs naturally with the heartbeat and the archive layer.

## Cautions carried forward

* The sandbox mount cannot journal sqlite; background processes do not
  survive between sandbox calls — long harvests must chunk, and the
  fetch cache is what makes chunking cheap.
* A stale `.git/index.lock` blocks commits: `rm -f ~/borgovero/.git/index.lock`
  if a commit fails on it. The sandbox cannot remove it.
* **casazebra.com is not ours** — a dormant shell held by someone else
  to 2027, serving nothing (no homepage, no robots, no sitemap). It is
  not a deploy target and not a Search Console property; revisit
  acquiring it in 2027. Small standing cost: anyone guessing the .com
  lands on a blank page.
* No inline comments in paste blocks (S007 lost a run to one).
* The match table is data, not a verdict, until §16d says otherwise —
  S008 held that line even when its own exhibit failed the test; keep
  holding it.
* Deep-hashing candidate galleries makes photomatch's fuzzy furniture
  guard (>3 listings per image at hamming ≤10) drop MORE images — a
  four-listing property cluster's shared photos look like furniture to
  it. The overlay is the instrument for those, not a threshold change
  (S004's lake-view lesson, same shape).

## Standing, unchanged

Publish the discrepancy, never the accusation. Band, never a point
estimate — never the midpoint. Never *valutazione*, *stima*, *perizia*
or *assessment*; it is an *indice*. Named agencies are named, so
publication requires identity evidence and a human look. Every session
ends with the SOT updated in place and a copy-pasteable git block.
