# S009 — continuation prompt

Paste this to open the next session.

---

S009 — CasaZebra. Read `docs/SOT.md` §15's **S008 OUTCOME** block first,
then the S008 changelog row. The dossier work is BUILT AND VERIFIED in
the sandbox but **not yet applied to the real database or deployed** —
that is where S009 starts.

## Step zero — Christopher's machine, before anything else

Three things ran only against a sandbox copy and are waiting:

```bash
cd ~/borgovero/phase0
python3 apply_S008_typology.py --dry-run
python3 apply_S008_typology.py
sqlite3 phase0.sqlite < apply_S008_data.sql
```

Then the build + deploy — **the deploy commands are in CLAUDE.md now**
(S008 recorded them; note that `build.py` rmtree's `dist-site/.vercel`
on every build, so the `vercel link` line is mandatory or you deploy to
a fresh project no domain points at). Expect and accept: **45 listing
slugs churn** (the typology fix renames their URLs; the old ones 404
until the archive layer exists — resubmit the sitemap in GSC), all
eight comune bands shift a little, and 22 listings change tier. These
are corrections, not drift: the portal's structured field now beats the
agency's caption.

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
   that reported success).

## Cautions carried forward

* The sandbox mount cannot journal sqlite; background processes do not
  survive between sandbox calls — long harvests must chunk, and the
  fetch cache is what makes chunking cheap.
* A stale `.git/index.lock` blocks commits: `rm -f ~/borgovero/.git/index.lock`
  if a commit fails on it. The sandbox cannot remove it.
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
