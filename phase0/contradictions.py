"""The contradictions. This is what the site publishes.

One property. Several agencies. Different numbers. No OMI, no
negotiation ladder, no condition positions, no surface basis — this
compares the agencies to themselves, so there is nothing here for anyone
to dispute except their own published figures.

    python3 contradictions.py              # summary + detail
    python3 contradictions.py --summary    # just the aggregate
    python3 contradictions.py --md         # markdown, one block per property

MATCHING — THREE INDEPENDENT ROUTES, EACH LABELLED

Every match carries the evidence that produced it, because the strength
of the claim differs and the site should say which one it is rather than
asserting a flat "same property".

  ref        the agencies' own reference numbers agree, in the same
             comune. DECISIVE where available — it is their identifier,
             not our inference.
  price      identical price to the euro, same comune — BUT ONLY when
             the price is unusual, or the surfaces corroborate it.

             The naive version of this was wrong and produced garbage.
             Round numbers are shared by dozens of unrelated properties:
             matching on EUR 250.000 alone pulled NINE Sansepolcro
             listings into one "property" spanning 85 to 6.000 m². The
             Via della Ginestra case worked because EUR 110.625 is an
             odd, computed figure (an auction base price) that nobody
             lands on twice by chance.

             So the price route now fires only when:
                the price is NOT a round multiple of ROUND_TO, or
                the surfaces agree within SURFACE_TOL
             and any cluster whose surfaces disagree by more than
             MAX_SURFACE_SPREAD is thrown out entirely unless the
             agencies' own reference numbers agree.
  photo      2+ shared photographs after excluding images that recur
             across listings. CANDIDATE ONLY — see photomatch.py, which
             matched a EUR 520.000 villa to a EUR 195.000 terratetto on a
             reused agency photo before the defences went in.

WHAT COUNTS AS A CONTRADICTION

  price      any difference in asking price
  surface    any difference in advertised m²
  typology   one calls it a villa, another a flat — and this one changes
             which OMI band applies, so it is a valuation disagreement
             dressed as a description (SOT S9)

A cluster with no disagreement is not published. Agreement is not news.

HONESTY CONSTRAINTS BAKED IN

  - Marcellini withholds price on most listings ("trattativa riservata").
    A withheld price is NOT a contradiction and must never be rendered
    as EUR 0 or as a disagreement. It is counted separately, because how
    often a price is hidden is its own finding.
  - Photo-matched clusters are marked as candidates. Do not publish one
    without a human looking at it.
  - A non-match proves nothing: some agencies shoot their own photos and
    use their own references. Absence of a cluster is not evidence that a
    property is exclusive to one agency.
"""

import argparse
import statistics as st
import sys
from collections import defaultdict

import config
import db


# A price that is an exact multiple of this is a ROUND ASKING PRICE —
# a human choosing a headline figure — and is shared by many unrelated
# properties. Matching on one alone is meaningless.
ROUND_TO = 1000

# Two listings of the same property rarely differ in surface by more
# than this. Used to corroborate a round-price match.
SURFACE_TOL = 0.15

# Above this spread the "cluster" is not one property, whatever matched.
# 410 m² against 70.350 m² is a house and a land parcel.
MAX_SURFACE_SPREAD = 2.0

# Same guard on price. Two agencies can disagree wildly, but a 74.074.085%
# gap is a PARSE ERROR, not a finding — that exact number reached the
# report when a Marcellini price range ("200.000 - 300.000") was
# concatenated into 200000300000. The parser is fixed; this stays as
# defence in depth, because the cost of publishing a fabricated number
# is the whole project's credibility.
MAX_PRICE_SPREAD = 5.0

# Every member of a 3+ cluster must sit within this of the cluster's
# MEDIAN surface. Checking against the median rather than a neighbour is
# what stops a chain of pairwise-similar listings drifting into one
# incoherent blob.
CLUSTER_TOL = 0.35


# Each site uses its own vocabulary for the same building. Marcellini
# labels categories in the PLURAL ('Appartamenti', 'Ville', 'Coloniche')
# because they are menu headings; Immobiliare uses the singular. Treating
# those as disagreements produced lines like
#
#     TYPOLOGY appartamenti vs appartamento -> different OMI band
#
# which is not a finding, it is a plural. Publishing it would hand an
# agent an easy way to dismiss the real disagreements alongside it.
#
# 'colonica' and 'rustico' are likewise the same building — a stone
# farmhouse — and OMI has no category for either (SOT S8).
#
# A REAL typology disagreement is one that changes the OMI band:
# appartamento vs villa, appartamento vs terratetto.
TYPOLOGY_SYNONYMS = {
    "appartamenti": "appartamento",
    "appartamento": "appartamento",
    "attico": "appartamento",
    "mansarda": "appartamento",
    "ville": "villa",
    "villa": "villa",
    "villini": "villa",
    "villetta": "villa",
    "coloniche": "rustico",
    "colonica": "rustico",
    "casale": "rustico",
    "rustico": "rustico",
    "poderi": "rustico",
    "podere": "rustico",
    "casolare": "rustico",
    "negozi": "negozio",
    "negozio": "negozio",
    "capannoni": "capannone",
    "terratetto": "terratetto",
    "cielo_terra": "terratetto",
    "cielo terra": "terratetto",
}


def norm_typology(t):
    if not t:
        return None
    k = str(t).strip().lower()
    return TYPOLOGY_SYNONYMS.get(k, k)


def _norm_street(a):
    """'Via della Ginestra 4' -> 'viadellaginestra'. Civici differ."""
    if not a:
        return None
    s = "".join(c.lower() for c in a if c.isalnum() or c.isspace())
    s = " ".join(w for w in s.split() if not w.isdigit())
    return s.replace(" ", "") or None


def load(conn):
    rows = [dict(r) for r in conn.execute(
        "SELECT source, source_id, agency_name, agency_ref, price, "
        "price_withheld, price_bracket, mq, typology, typology_raw, "
        "address_raw, comune, title, url FROM listings")]
    for r in rows:
        r["key"] = (r["source"], r["source_id"])
    return rows


def cluster(rows, conn=None):
    """{frozenset(keys): set(evidence)} — every route that fired."""
    found = defaultdict(set)

    by_ref = defaultdict(list)
    by_price = defaultdict(list)
    for r in rows:
        c = config.norm_comune(r["comune"])
        if r["agency_ref"]:
            by_ref[(c, str(r["agency_ref"]).lstrip("0").lower())].append(r)
        if r["price"]:
            by_price[(c, r["price"])].append(r)

    for grp in by_ref.values():
        if len({g["agency_name"] or g["source"] for g in grp}) > 1:
            found[frozenset(g["key"] for g in grp)].add("ref")
    for (c, price), grp in by_price.items():
        if len({g["agency_name"] or g["source"] for g in grp}) < 2:
            continue
        if price % ROUND_TO != 0:
            # Odd, computed figure. Nobody lands on it twice by accident.
            found[frozenset(g["key"] for g in grp)].add("price")
            continue
        # Round price: only believe it where the surfaces corroborate.
        # Pair them up rather than lumping the whole price point together.
        withmq = [g for g in grp if g["mq"]]
        for i in range(len(withmq)):
            for j in range(i + 1, len(withmq)):
                a, b = withmq[i], withmq[j]
                if (a["agency_name"] or a["source"]) == \
                   (b["agency_name"] or b["source"]):
                    continue
                lo, hi = sorted((a["mq"], b["mq"]))
                if (hi - lo) / lo > SURFACE_TOL:
                    continue
                # If both name a street and the streets differ, these are
                # two different properties that merely share a common
                # price point and a common size. EUR 170.000 at 105/120 m²
                # turned up on three separate streets before this check.
                sa, sb = _norm_street(a["address_raw"]), _norm_street(b["address_raw"])
                if sa and sb and sa != sb and not (sa in sb or sb in sa):
                    continue
                # BLANK streets can't contradict, which is how five
                # €280.000 listings — a stream-side villetta, a centro
                # B&B palazzo and three riders on three different
                # frazioni — became one "property" (S004, the Cherubino
                # cluster; both Romolini rows had no address at all).
                # A round price with a blank street is believable only
                # when the price point is RARE: exactly these two
                # listings corpus-wide. €29.000 appears twice and is
                # one flat in Fresciano; €280.000 appears five times
                # and is five different houses.
                if not (sa and sb) and len(grp) > 2:
                    continue
                found[frozenset((a["key"], b["key"]))].add("price+surface")

    try:
        import photomatch
        pconn = conn if conn is not None else db.connect()
        idx = {r["source_id"]: r for r in rows}
        pclusters, strength = photomatch.clusters(pconn, detail=True)
        for members in pclusters.values():
            keys = [idx[m]["key"] for m in members if m in idx]
            if len(keys) > 1 and len(
                    {idx[m]["agency_name"] or idx[m]["source"]
                     for m in members if m in idx}) > 1:
                # 'photo' only when every merged edge inside the cluster
                # is photo-strong (2+ distinct shared images at <=5).
                # Anything resting on a single shared image is
                # 'photo-weak' — a candidate for eyes, never identity.
                # S004 eyeballed both kinds: strong was right 12/12;
                # single-image joins were right sometimes (a lived-in
                # kitchen) and catastrophically wrong other times (the
                # €520k villa) — which is exactly why they stay labeled.
                edges = [strength[fs] for fs in strength
                         if fs <= set(members)]
                tag = ("photo" if edges and all(e == "photo-strong"
                                               for e in edges)
                       else "photo-weak")
                found[frozenset(keys)].add(tag)
    except Exception:
        pass

    # MERGE ONLY IDENTITY-BASED EVIDENCE.
    #
    # An earlier version union-found across every route and produced a
    # disaster: 14 listings at EUR 200.000 merged into one "property",
    # including EIGHT different Marcellini refs, spanning 100 to 160 m².
    # Another merged Coloniche, Negozi, TerreniEdificabili and
    # Appartamenti together.
    #
    # The cause is that "surfaces within 15%" IS NOT TRANSITIVE. 100
    # links to 115, 115 to 130, 130 to 150 — and 100 and 160 end up in
    # the same cluster although they are 60% apart. Union-find requires
    # an equivalence relation; a tolerance is not one.
    #
    # So: `ref` and `photo` are identity claims and merge transitively.
    # `price`/`price+surface` are similarity claims and stay as the pairs
    # they were emitted as.
    IDENTITY = {"ref", "photo"}
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for keys in found:
        ks = list(keys)
        for k in ks[1:]:
            union(ks[0], k)

    groups = defaultdict(set)
    evid = defaultdict(set)
    members = defaultdict(list)      # the pairs each merge was built from
    for keys, evidence in found.items():
        root = find(next(iter(keys)))
        groups[root] |= set(keys)
        evid[root] |= evidence
        members[root].append((keys, evidence))

    by_key = {r["key"]: r for r in rows}

    def coherent_merge(keys):
        """Is this merged cluster believable as ONE property?

        Two ways a merge goes wrong, both seen in real output:
          - chaining on a tolerance, giving 100 m² and 160 m² in one
            cluster via intermediate steps
          - one agency appearing many times, which means the price point
            (not the property) did the grouping: EIGHT Marcellini refs
            landed in a single EUR 200.000 'property'
        """
        rs = [by_key[k] for k in keys if k in by_key]
        mqs = sorted(r["mq"] for r in rs if r["mq"])
        if len(mqs) > 2:
            med = mqs[len(mqs) // 2]
            if max(mqs) / med > 1 + CLUSTER_TOL \
                    or med / min(mqs) > 1 + CLUSTER_TOL:
                return False
        agencies = {r["agency_name"] or r["source"] for r in rs}
        return len(rs) <= len(agencies) + 1

    out = {}
    for root, keys in groups.items():
        if len(keys) == 2 or coherent_merge(keys):
            out[frozenset(keys)] = evid[root]
        else:
            # Merge rejected — keep the pairs it was assembled from
            # rather than throwing the evidence away entirely.
            for pair, evidence in members[root]:
                out[frozenset(pair)] = evidence

    # Final coherence check. Even an identity-merged cluster can go wrong
    # (a shared facade merges a whole building), so every member must sit
    # within tolerance of the cluster's MEDIAN surface — not merely
    # within tolerance of some neighbour it chained through.
    # ONLY similarity-built clusters get this check. Applying it to
    # everything threw away the findings themselves: Via della Ginestra
    # is five agencies on one auction at an odd price to the euro, with
    # surfaces 90 to 133 m² — a 48% disagreement, which is the whole
    # point, and the coherence rule rejected it for being incoherent.
    #
    # Identity evidence (a shared reference, shared photographs, a
    # non-round price nobody lands on twice) is precisely what earns the
    # right to believe a large surface gap. Only `price+surface`, which
    # can chain, needs policing.
    return out


def disagreements(group, identity=False):
    """What actually differs. Withheld prices excluded from price.

    identity=True when the cluster is held together by ref or
    photo-strong evidence — the only case where an ADDRESS difference is
    a finding rather than a mismatch signal (S004: the same
    photo-verified Monterchi rustico is 'Località Omarino' at one agency
    and 'località Padonchia' at the other; the same Fresciano flat is
    'Badia Tedalda' at two agencies and 'Sestino' at the third).
    """
    out = {}
    priced = [g for g in group if g["price"] and not g.get("price_withheld")]
    prices = {g["price"] for g in priced}
    if len(prices) > 1:
        lo, hi = min(prices), max(prices)
        out["price"] = (lo, hi, (hi - lo) / lo * 100)

    comuni = {config.norm_comune(g["comune"]) for g in group
              if g["comune"]}
    if len(comuni) > 1:
        out["location"] = sorted(comuni)
    elif identity:
        streets = {_norm_street(g["address_raw"]): g["address_raw"]
                   for g in group if _norm_street(g["address_raw"])}
        if len(streets) > 1 and not any(
                a in b or b in a for a in streets for b in streets if a != b):
            out["address"] = sorted(streets.values())

    mqs = {g["mq"] for g in group if g["mq"]}
    if len(mqs) > 1:
        lo, hi = min(mqs), max(mqs)
        out["surface"] = (lo, hi, (hi - lo) / lo * 100)

    # Compare NORMALISED typologies — 'Appartamenti' vs 'appartamento'
    # is a plural, not a disagreement. Report the raw labels though, so
    # the reader sees what each agency actually wrote.
    norm = {}
    for g in group:
        raw = g["typology"] or g["typology_raw"]
        if raw:
            norm.setdefault(norm_typology(raw), set()).add(str(raw).lower())
    if len(norm) > 1:
        out["typology"] = sorted(
            "/".join(sorted(v)) for v in norm.values())

    out["_withheld"] = sum(1 for g in group if g.get("price_withheld"))
    return out


def best_label(group):
    """The most informative address in the cluster, not just row[0]'s.

    Five clusters printed 'address not given' purely because the first
    row happened to lack one while a sibling had it.
    """
    # sorted() first so a length tie resolves alphabetically instead of
    # by whatever order the cluster's set happened to iterate in. The
    # label ends up in the published page's URL, and a URL that changes
    # between identical rebuilds is a dead link for anyone who saved it.
    addrs = sorted(g["address_raw"] for g in group if g["address_raw"])
    if addrs:
        return max(addrs, key=len)
    titles = sorted(g["title"] for g in group if g["title"])
    return max(titles, key=len) if titles else "address not given"


def same_agency_pair(group):
    """Two listings from the SAME agency inside one cluster. Either the
    agency has listed one property twice, or the match is wrong. Flag it
    rather than presenting it as an inter-agency contradiction."""
    names = [g["agency_name"] or g["source"] for g in group]
    return len(names) != len(set(names))


def load_verified(path="verified_clusters.json"):
    """S004's hand-verification, kept as data the pipeline consumes.

    Each entry: {"ids": [source_ids...], "verdict": "confirmed"|
    "rejected", "note": "...", "drop": [source_ids...]}. Confirmed
    clusters carry the note into the output; a cluster containing a
    rejected pair is suppressed even if a matcher still emits it. The
    file is committed to the repo (NOT in gitignored data/) because,
    like id_anchors.json, it is measured once by a human and cannot be
    regenerated by code.

    `drop` removes named listings from an otherwise good cluster. It
    exists because "the match is wrong" and "this member does not
    belong in the comparison" are different findings, and killing the
    whole cluster to deal with the second throws away the first. The
    Anghiari Liberty villa is the case: three agencies do list it, but
    one listing was last updated in December 2020 and offers the sale
    combined with a second building in the same park, so its price is
    not comparable and publishing an "81% price contradiction" against
    it would be an accusation the evidence does not support. Dropping
    that one member leaves the real finding standing.
    """
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent / path
    if not p.exists():
        return []
    return json.loads(p.read_text())


def build(conn):
    rows = load(conn)
    idx = {r["key"]: r for r in rows}
    verified = load_verified()
    items = []
    n_rejected = 0
    for keys, evidence in cluster(rows, conn).items():
        group = [idx[k] for k in keys if k in idx]
        if len(group) < 2:
            continue
        sids = {g["source_id"] for g in group}
        ver = None
        for v in verified:
            vids = set(v["ids"])
            if v["verdict"] == "rejected":
                # A cluster that contains a known-false set, or sits
                # inside one, inherits the rejection.
                if vids <= sids or sids <= vids:
                    ver = v
                    break
            else:
                # 'Confirmed' covers ONLY members that were actually
                # eyeballed: the cluster must sit inside the verified
                # set. A merge that pulls in extra listings makes a
                # bigger claim than the one that was checked.
                if sids <= vids:
                    ver = v
                    break
        if ver and ver["verdict"] == "rejected":
            n_rejected += 1
            continue
        if ver and ver.get("drop"):
            group = [g for g in group if g["source_id"] not in ver["drop"]]
            if len(group) < 2:
                continue
        identity = bool(set(evidence) & {"ref", "photo"}) \
            or (ver and ver["verdict"] == "confirmed")
        d = disagreements(group, identity=identity)
        if not any(k in d for k in
                   ("price", "surface", "typology", "location", "address")):
            continue
        # Reject impossible clusters. A surface spread of 400 m² against
        # 70.350 m² is a house and a field, not a disagreement about one
        # property — only the agencies' own reference numbers can
        # override this.
        if "surface" in d and d["surface"][2] / 100 > MAX_SURFACE_SPREAD \
                and "ref" not in evidence:
            continue
        if "price" in d and d["price"][2] / 100 > MAX_PRICE_SPREAD:
            print(f"  !! dropped a cluster with a {d['price'][2]:.0f}% price "
                  f"gap — suspect a parse error, not a contradiction:")
            for g in group:
                print(f"       {g['source']}/{g['source_id']} "
                      f"{g['agency_name']} EUR {g['price']} {g['url']}")
            continue
        items.append({"group": group, "evidence": sorted(evidence), "d": d,
                      "verified": ver["note"] if ver else None})
    if n_rejected:
        print(f"  {n_rejected} cluster(s) suppressed by verified_clusters.json"
              " (hand-checked in S004 and found to be different properties)")
    items.sort(key=lambda it: -(it["d"].get("surface", (0, 0, 0))[2]
                                + it["d"].get("price", (0, 0, 0))[2]
                                + (50 if it["verified"] else 0)))
    return items


def summary(items, conn):
    n_src = dict(conn.execute(
        "SELECT source, COUNT(*) FROM listings GROUP BY source").fetchall())
    print("=" * 74)
    print("WHAT THE AGENCIES SAY ABOUT THE SAME PROPERTY")
    print("=" * 74)
    print("\n  sources: " + ", ".join(f"{k} {v}" for k, v in n_src.items()))

    if not items:
        print("\n  No contradictions found yet.")
        print("  Run the harvests first — this needs all sources present:")
        print("    python3 run.py            (immobiliare)")
        print("    python3 run_agencies.py   (centogambe + marcellini)")
        print("    python3 photomatch.py --harvest")
        return

    price = [it for it in items if "price" in it["d"]]
    surf = [it for it in items if "surface" in it["d"]]
    typ = [it for it in items if "typology" in it["d"]]

    print(f"\n  properties listed by 2+ agencies WITH a disagreement: {len(items)}")
    print(f"    disagree on PRICE     {len(price):>4}", end="")
    if price:
        v = [it["d"]["price"][2] for it in price]
        print(f"   median {st.median(v):.0f}%   worst {max(v):.0f}%")
    else:
        print()
    print(f"    disagree on SURFACE   {len(surf):>4}", end="")
    if surf:
        v = [it["d"]["surface"][2] for it in surf]
        print(f"   median {st.median(v):.0f}%   worst {max(v):.0f}%")
    else:
        print()
    print(f"    disagree on TYPOLOGY  {len(typ):>4}"
          "   (changes which OMI band applies)")

    ev = defaultdict(int)
    for it in items:
        ev["+".join(it["evidence"])] += 1
    print("\n  matched by:")
    for k, v in sorted(ev.items(), key=lambda kv: -kv[1]):
        note = ("  CANDIDATES — eyeball before publishing"
                if "photo-weak" in k else "")
        print(f"    {k:16} {v:>4}{note}")

    n_ver = sum(1 for it in items if it.get("verified"))
    if n_ver:
        print(f"\n  verified by hand (S004 eyeball pass): {n_ver} of {len(items)}")

    wh = conn.execute("SELECT COUNT(*) FROM listings "
                      "WHERE price_withheld=1").fetchone()[0]
    if wh:
        print(f"\n  separately: {wh} listing(s) withhold the price entirely")
        print("  ('trattativa riservata') — not a contradiction, but the")
        print("  same opacity by another route.")


def detail(items, limit=25):
    print("\n" + "=" * 74)
    print("THE CONTRADICTIONS")
    print("=" * 74)
    for it in items[:limit]:
        g, d = it["group"], it["d"]
        head = g[0]
        print(f"\n  {head['comune']} — {best_label(g)}")
        print(f"  matched by: {'+'.join(it['evidence'])}"
              + ("   VERIFIED BY HAND (S004)" if it.get("verified") else "")
              + ("   CANDIDATE — single shared image"
                 if "photo-weak" in it["evidence"] and not it.get("verified")
                 else "")
              + ("   [SAME AGENCY TWICE — check]" if same_agency_pair(g) else ""))
        for r in sorted(g, key=lambda x: (-(x["price"] or 0),
                              str(x["agency_name"] or x["source"]),
                              str(x["source_id"]))):
            ref = f"rif.{r['agency_ref']}" if r["agency_ref"] else ""
            price = "withheld" if r.get("price_withheld") else \
                (f"{r['price']:,}" if r["price"] else
                 (f"[{r['price_bracket']}]" if r.get("price_bracket")
                  else "?"))
            print(f"    {str(r['agency_name'] or r['source'])[:24]:26}"
                  f"{ref:12} EUR {price:>10}  {str(r['mq'] or '?'):>5} m²  "
                  f"{str(r['typology'] or r['typology_raw'] or '')[:12]:14}")
        if "price" in d:
            print(f"      PRICE    EUR {d['price'][0]:,} vs {d['price'][1]:,}"
                  f"   ({d['price'][2]:.0f}% apart)")
        if "surface" in d:
            print(f"      SURFACE  {d['surface'][0]} vs {d['surface'][1]} m²"
                  f"   ({d['surface'][2]:.0f}% apart)")
        if "typology" in d:
            print(f"      TYPOLOGY {' vs '.join(d['typology'])}"
                  f"   -> different OMI band")
        if "location" in d:
            print(f"      LOCATION {' vs '.join(d['location'])}"
                  f"   -> the agencies disagree on the COMUNE")
        if "address" in d:
            print(f"      ADDRESS  {' vs '.join(d['address'])}")


def markdown(items, path="contradictions.md"):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# What the agencies say about the same property\n\n")
        for it in items:
            g, d = it["group"], it["d"]
            head = g[0]
            f.write(f"## {head['comune'].title()} — {best_label(g)}\n\n")
            f.write("| Agency | Ref | Asking | Surface | Type |\n|---|---|---|---|---|\n")
            for r in sorted(g, key=lambda x: (-(x["price"] or 0),
                                  str(x["agency_name"] or x["source"]),
                                  str(x["source_id"]))):
                price = "*withheld*" if r.get("price_withheld") else \
                    (f"€ {r['price']:,}" if r["price"] else
                     (f"*{r['price_bracket']}*" if r.get("price_bracket")
                      else "—"))
                f.write(f"| {r['agency_name'] or r['source']} "
                        f"| {r['agency_ref'] or '—'} | {price} "
                        f"| {r['mq'] or '—'} m² "
                        f"| {r['typology'] or r['typology_raw'] or '—'} |\n")
            f.write("\n")
            if "surface" in d:
                f.write(f"**Surface differs by {d['surface'][2]:.0f}%** "
                        f"({d['surface'][0]} vs {d['surface'][1]} m²).\n\n")
            if "price" in d:
                f.write(f"**Price differs by {d['price'][2]:.0f}%** "
                        f"(€ {d['price'][0]:,} vs € {d['price'][1]:,}).\n\n")
            if "typology" in d:
                f.write(f"**Disagree on property type**: "
                        f"{' vs '.join(d['typology'])}.\n\n")
            if "location" in d:
                f.write(f"**The agencies disagree on the comune**: "
                        f"{' vs '.join(c.title() for c in d['location'])}.\n\n")
            if "address" in d:
                f.write(f"**Different addresses for the same property**: "
                        f"{' vs '.join(d['address'])}.\n\n")
            if it.get("verified"):
                f.write(f"**Verified by hand, 2026-08-29** — "
                        f"{it['verified']}\n\n")
            f.write(f"<sub>Matched by {'+'.join(it['evidence'])}."
                    + (" Candidate — unverified."
                       if "photo-weak" in it["evidence"]
                       and not it.get("verified") else "")
                    + "</sub>\n\n---\n\n")
    print(f"\n  -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    # Read-only analysis can run against a copy of the database (the
    # sandbox mount corrupts LIVE sqlite writes, S003/S004) — pass the
    # copy's path here. Default: the configured DB via db.connect().
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    if a.db:
        import sqlite3
        conn = sqlite3.connect(a.db)
        conn.row_factory = sqlite3.Row
    else:
        conn = db.connect()
    items = build(conn)
    summary(items, conn)
    if items and not a.summary:
        detail(items, a.limit)
    if a.md and items:
        markdown(items)


if __name__ == "__main__":
    main()
