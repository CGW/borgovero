# S008 — continuation prompt

Paste this to open the next session.

---

S008 — CasaZebra. Read `docs/SOT.md` §15 first — its S008 brief is the
authority for this session — then §16d (the publication gate) and the
S006/S007 changelog rows for what is already live.

**The site is LIVE at https://casazebra.it** — 1.658 URLs submitted with
lastmod, all eight comune bands published, Dataset schema valid,
paste-a-URL lookup on the landing page, repo and production in sync at
`a5c4687`+. Do not rebuild what works; every change goes through
`bv-site/build.py`, which builds twice, diffs, lints, and only then
installs.

**The goal Christopher set for this session:** comprehensive property
pages — one page that shows ALL the listings of a property and all
their variations: every agency, every channel (portal and the agency's
own site), every disagreement in price, surface, typology, floor. Today
a listing page shows its own figures plus cross-listings only for
verified findings; S008 widens that to the full dossier. The three
pieces below are ordered so each feeds the next.

## In order

1. **Agency-site link harvester** — the §15 brief, follow it as
   written. Leonardi (159), House (127), Romolini (93), Cortesi (78+9);
   index pages only; match on the agency's own ref where both channels
   carry it, else price+surface+comune under the no-coin-flip rule (two
   candidates at the same price and surface is NO match). Store
   `url_alt` with provenance and match route. Consumers: `cerca.json`
   (own-site pastes then resolve), listing pages cite both channels.
   Proven case to open with: Leonardi's
   `/immobile/appartamento-ingresso-indipendente-3-camere/` =
   immobiliare 105891071 — and the two channels disagree on typology
   (appartamento vs cielo terra), which is S008's exhibit the way the
   Anghiari villa was S004's.

2. **Candidate-pair deep photo pass** — §15 brief, second block. For
   pairs matching price+surface+street but lacking identity evidence,
   hash FULL galleries and re-test at hamming ≤ 5. Do NOT raise
   `PHOTOS_PER_LISTING` corpus-wide (§10.1). Before building anything:
   Christopher's 2026-08-30 run already deep-hashed 94 previously
   unhashed listings (445 thumbnails) — re-run `contradictions.py`
   against the richer evidence first and see what clusters formed on
   their own.

3. **The comprehensive property page.** Extend the §4.2 listing page
   into the dossier: (a) verified cluster members with the full
   comparison table — already built, keep; (b) harvester-matched
   own-site listings of the same property, labelled by match route; (c)
   candidate matches shown ONLY with the existing unconfirmed
   labelling discipline — "these listings may be the same property; we
   publish it as a lead, not as an established fact." Never present a
   candidate join as fact: a named-agency same-property claim above
   candidate level needs identity evidence or a human look (§16d), and
   that gate is the reason the site can name names at all. The
   confronti page stays the finding; the listing page becomes where a
   buyer sees everything known about one property.

4. **Close the €149.000 pair** — SICASA 80620571 / House 126557887,
   Via XX Settembre, identical price. The machine is done with it:
   full galleries compared (25 × 21), closest pair hamming 12, zero
   shared images; floor 2°/3° and vani 3/5 disagree; the NOW own-site
   slug says Piazza Torre di Berta. Same flat shot twice, or two flats
   — only Christopher's eyes settle it. Whichever way it goes, record
   it in `phase0/verified_clusters.json`: as verified-same (with his
   note and the NOW/Romolini URLs), or as checked-and-different — the
   file already holds both kinds, and an unrecorded human look is a
   look that gets repeated.

## Cautions that cost real time when ignored

* Agency sites are four small businesses, not portals: check
  `robots.txt` per site before the first request, fetch politely, and
  index pages only unless a match is impossible without the detail.
* Every adapter joins the weekly maintenance surface forever. Say so at
  the wrap; the count is now the argument for the ingest heartbeat.
* The no-coin-flip rule is not decoration. S004's five false clusters
  all came from weak joins that looked obvious.
* The sandbox mount cannot journal sqlite. Work on a copy; anything
  that must reach the real DB runs on Christopher's machine.
* **No inline comments in paste blocks.** S007 lost a run to
  `# 2025-2, both provinces` being passed to argparse as arguments.
* A `git commit` reporting "nothing to commit" right after a successful
  one is a duplicate run — check `git log` before re-staging.
* This project's failure mode is an assumed number hardening into a
  finding. The harvester's match table is data, not a verdict, until
  §16d says otherwise.

## Already done in S006–S007 — do not redo

* 777 listing pages + 8 comune reports, built, linted, deployed.
* The derived width gate (28,0%) fixed in spec §4.3, §10.3 and SOT
  §17.1; spec §13 Phase 2 rewritten for eight comuni.
* OMI loaded (2025-2 all eight comuni incl. Citerna; 2021-1 under its
  own label; `omi.py --semester`); §17.2 cross-check run — Badia
  Tedalda below the OMI floor is a recorded finding-in-waiting.
* Rename to CasaZebra end to end; casazebra.it live, apex canonical,
  www 308s in; GSC verified, sitemap Success (1.658 URLs, lastmod),
  Dataset schema valid.
* Phase 1 pages: llms.txt, /dati/ (CC BY 4.0), correzioni (first entry
  logged), diritto-di-replica, ClaimReview schema + backlinks on
  findings, per-agency price-publication table (Marcellini 26/202) and
  the prezzi-non-pubblicati guide.
* Paste-a-URL lookup (`/cerca.json`, 1.158 entries, honest no-page
  answers).
* Typology recovery via `source_id`; garages/negozi out of scope.

## Also open, smaller (queue after the dossier work)

* **Archive layer (§6)** — delisted pages currently 404; every ingest
  without it deletes history. This becomes URGENT the moment the
  heartbeat starts.
* Weekly ingest→build→deploy heartbeat with §10.4 alerts.
* Per-listing interval graphic (own-made, zebra-striped; agency photos
  stay banned per §2) — doubles as og:image for the press push.
* Zone-matched OMI cross-check (Badia Tedalda R1 stock vs R1 band) now
  that `zones.py` runs with perimeters.
* Perugia QIP re-order for Citerna polygon zoning; casazebra.com
  revisit in 2027.

## Standing, unchanged

Publish the discrepancy, never the accusation. Band, never a point
estimate — and never the midpoint of a band. Never valutazione, stima,
perizia or assessment; it is an indice. Named agencies are named, so
publication requires identity evidence and a human look. Every session
ends with the SOT updated in place and a copy-pasteable git block.
