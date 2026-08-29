"""Listings that contradict THEMSELVES — field against the agency's own text.

WHY THIS IS A DIFFERENT, AND IN ONE WAY STRONGER, FINDING

`contradictions.py` compares agencies to each other, and everything hard
about it is the matching: three sessions were spent proving two listings
describe one property, and most of the errors along the way were matching
errors (a shared lake view, a reused kitchen photograph, a round price).

This module needs NO matching at all. It compares ONE listing's
structured fields to the free text in that SAME listing. There is
nothing to link, so there is nothing to link wrongly — the whole class
of false positives that has cost this project the most simply cannot
occur here.

It is also a sharper claim. "Two agencies disagree" invites the reply
that somebody made a typo. "This listing's own field contradicts its own
description" does not — and the field is the number that portals sort,
filter and price by, so it is the number that decides which buyers ever
see the property at all.

    python3 self_contradictions.py            # summary + detail
    python3 self_contradictions.py --md       # markdown

COVERAGE, STATED HONESTLY — AND WHY IT SHAPED THE DESIGN

    marcellini    229 of 278 carry a full description
    centogambe      0 (the adapter does not store description text yet)
    immobiliare     2 of 844 descriptions — the search payload omits them
                    and detail pages return 403 (SOT S12.4)
                779 of 844 CAPTIONS, which is what makes this fair

Surface claims mostly live in descriptions, so on surface this is
largely a Marcellini measurement, and it must be reported as one. An
axis whose entire sample is a single small agency is not a market
finding, it is a complaint about one business — and publishing it that
way would be unfair even if every instance were true.

Captions are what rescue it: 779 of 844 across every agency on the
portal, and captions name the property type constantly ("Casa
semi-indipendente...", "CASA LIBERA SU TRE LATI..."). So TYPOLOGY is
measurable across the whole market and SURFACE is not, and the two are
reported separately rather than added together into one flattering
number.

GUARDS, BECAUSE THE OBVIOUS VERSION OF THIS IS WRONG

An Italian listing mentions many surfaces that are not the dwelling:
"giardino di 2.600 mq", "terreno 9.000 mq", "garage 31 mq". Naively
comparing every number in the text to the surface field would flag
almost every listing in the corpus, and every flag would be junk.

  1. A number preceded by a land/garden/garage word is skipped.
  2. A listing is only flagged when NO stated surface, and no SUM of
     stated surfaces, lands within TOL of the field. The sum rule
     matters: "150 mq + 100 mq" against a field of 250 is a listing
     agreeing with itself in pieces, not contradicting itself.
  3. Absurd values (under 15 m², over 5.000 m²) are ignored as parse
     noise rather than published as findings.

Output is CANDIDATES. Every one is read by a human before publication,
exactly as the photo clusters were.
"""

import argparse
import re
import sys
from collections import defaultdict

import config
import db
from contradictions import TYPOLOGY_SYNONYMS, norm_typology

# A stated surface within this of the field is agreement, not conflict.
TOL = 0.10

# Below/above these, a number in prose is not a dwelling surface.
MIN_MQ, MAX_MQ = 15, 5000

# Words that mean the number after them is NOT the dwelling. Getting
# this list wrong is the difference between a report and a pile of
# noise: nearly every rural listing quotes its land in the same
# sentence as its house.
NOT_DWELLING = (
    "giardino", "terreno", "terreni", "orto", "parco", "garage", "box",
    "cantina", "soffitta", "resede", "corte", "cortile", "piscina",
    "annesso", "annessi", "fienile", "seccatoio", "loggiato", "portico",
    "balcone", "terrazzo", "terrazza", "lotto", "vigneto", "uliveto",
    "oliveto", "bosco", "seminativ", "pertinenza", "pertinenze",
    "capannone", "magazzino", "deposito", "tettoia", "posto auto",
)

# Italian writes the unit on either side — "200 mq" and "mq. 450" are
# both normal, and only matching the first missed a listing that agreed
# with itself ("per un totale di mq. 450") and published it as a
# contradiction against its own land area. `post` catches the trailing
# form, `pre_unit` the leading one.
MQ_RE = re.compile(
    r"(?P<pre>[A-Za-zàèéìòù'\s\.]{0,40}?)"
    r"(?:(?P<pre_unit>mq\.?|m²|m2|metri\s+quadri?)\s*"
    r"(?P<num2>\d{1,3}(?:\.\d{3})*(?:,\d+)?)"
    r"|(?P<num>\d{1,3}(?:\.\d{3})*(?:,\d+)?)\s*"
    r"(?:mq\.?|m²|m2|metri\s+quadri))"
    r"(?P<post>[^.;\n]{0,18})",
    re.I)

# "due appartamenti di ca 85 mq l'uno" states 85 PER UNIT, so a field
# of 170 is the listing agreeing with itself. Without this the pattern
# reads 85 against 170 and calls it a 100% contradiction.
EACH_RE = re.compile(r"\b(l'uno|ciascun\w*|cadaun\w*|per\s+piano)\b", re.I)

# "villa ... su 3.600 mq" is the plot the house stands on, not the
# house. No land word precedes the number, so NOT_DWELLING never fired.
ON_LAND_RE = re.compile(r"\bsu\s*$", re.I)

# Typology words as they appear in prose. Mapped through the same
# synonym table the cross-agency report uses, so 'colonica' and
# 'rustico' do not read as a disagreement here either.
# ORDER MATTERS: regex alternation takes the FIRST branch that matches,
# so 'villetta a schiera' has to precede the bare 'villetta' or the
# longer phrase is never seen and a terraced house scores as a villa.
TYPO_RE = re.compile(
    r"\b(villett\w*\s+a\s+schiera|"
    r"appartament\w*|attico|mansard\w*|vill[ae]tt\w*|vill[ae]|"
    r"casal\w*|colonic\w*|rustic\w*|poder\w*|casolar\w*|"
    r"terratett\w*|cielo\s*terra|cieloterra|"
    r"casa\s+semi[- ]?indipendente|casa\s+indipendente|"
    r"casa\s+libera\s+su\s+tre\s+lati|casa\s+singola|bifamiliar\w*|"
    r"negozi\w*|capannon\w*|palazz\w*)\b", re.I)

# A place name is not a description. "Casa di paese in Localita Ville
# di Roti" matched 'Ville' and reported the agency for calling a rustico
# a villa — the word was the hamlet's name. Any typology word sitting
# inside a toponym is skipped.
TOPONYM_RE = re.compile(
    r"\b(localit\w*|loc\.?|frazione|fraz\.?|via|viale|piazza|strada|"
    r"vocabolo|voc\.?|podere)\b[^,.;]{0,24}$", re.I)

PROSE_TYPOLOGY = {
    # 'Villetta a schiera' is a TERRACED house. Mapping it to villa
    # would have this module making the same category error it exists
    # to catch.
    "villetta a schiera": "terratetto",
    "casali": "rustico",
    "casale": "rustico",
    "coloniche": "rustico",
    "casa semi-indipendente": "terratetto",
    "casa semi indipendente": "terratetto",
    "casa libera su tre lati": "terratetto",
    "casa singola": "villa",
    "bifamiliare": "villa",
    "cieloterra": "terratetto",
    "cielo terra": "terratetto",
    # DELIBERATELY UNSCORED. 'Casa indipendente' reads as detached, but
    # the captions using it here continue '...su tre lati' — free on
    # three sides, which is semi-detached, so a terratetto field is
    # right and the flag was mine, not the agency's. Three of the first
    # fourteen candidates were this one mapping. An ambiguous word that
    # produces confident accusations is worth less than no word.
    "casa indipendente": None,
    "palazzo": None,
    "palazzina": None,
}


def _to_int(s):
    try:
        return int(str(s).replace(".", "").split(",")[0])
    except ValueError:
        return None


def stated_surfaces(text):
    """Every plausible DWELLING surface stated in the prose.

    Returns (value, multiplier) pairs — the multiplier is 2 for a
    figure the text says applies to each of two units.
    """
    out = []
    for m in MQ_RE.finditer(text or ""):
        pre = (m.group("pre") or "").lower()
        if any(w in pre for w in NOT_DWELLING) or ON_LAND_RE.search(pre):
            continue
        n = _to_int(m.group("num") or m.group("num2"))
        if not n or not (MIN_MQ <= n <= MAX_MQ):
            continue
        each = bool(EACH_RE.search(m.group("post") or ""))
        out.append((n, 2 if each else 1))
    return out


def stated_typologies(text):
    out = set()
    for m in TYPO_RE.finditer(text or ""):
        if TOPONYM_RE.search((text or "")[max(0, m.start() - 30):m.start()]):
            continue
        w = re.sub(r"\s+", " ", m.group(1).lower())
        if w in PROSE_TYPOLOGY:
            mapped = PROSE_TYPOLOGY[w]
        else:
            mapped = norm_typology(w) or TYPOLOGY_SYNONYMS.get(w[:-1])
            if mapped == w and w not in TYPOLOGY_SYNONYMS:
                # e.g. 'appartamenti' -> strip inflection and retry
                for stem, canon in TYPOLOGY_SYNONYMS.items():
                    if w.startswith(stem[:6]):
                        mapped = canon
                        break
        if mapped:
            out.add(mapped)
    return out


def surface_conflict(field_mq, text):
    """(stated, why) when the text contradicts the surface field."""
    if not field_mq or field_mq <= 0:
        return None
    pairs = stated_surfaces(text)
    if not pairs:
        return None
    nums = [n for n, _ in pairs]
    # Agreement in one piece, or per-unit ("85 mq l'uno" x2 = 170)...
    for n, mult in pairs:
        if abs(n - field_mq) / field_mq <= TOL:
            return None
        if mult > 1 and abs(n * mult - field_mq) / field_mq <= TOL:
            return None
    # ...or in several. "150 mq + 100 mq" against a field of 250 is a
    # listing agreeing with itself, which an earlier version of this
    # would have published as a contradiction.
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if abs(nums[i] + nums[j] - field_mq) / field_mq <= TOL:
                return None
    if len(nums) > 2 and abs(sum(nums) - field_mq) / field_mq <= TOL:
        return None
    best = max(nums, key=lambda n: abs(n - field_mq))
    return (best, f"text says {best} m², field says {field_mq} m²")


def typology_conflict(field_typ, text):
    if not field_typ:
        return None
    f = norm_typology(field_typ)
    said = stated_typologies(text)
    if not said or f in said:
        return None
    # Only report when the prose names exactly one thing — a
    # description mentioning several building types is describing a
    # property with several buildings, not contradicting itself.
    if len(said) != 1:
        return None
    other = next(iter(said))
    return (other, f"text calls it a {other}, field says {f}")


def build(conn):
    rows = [dict(r) for r in conn.execute(
        "SELECT source, source_id, agency_name, agency_ref, price, "
        "price_bracket, mq, typology, typology_raw, description, caption, "
        "comune, address_raw, url FROM listings")]
    out = []
    for r in rows:
        text = " ".join(x for x in (r["caption"], r["description"]) if x)
        if len(text) < 25:
            continue
        found = {}
        s = surface_conflict(r["mq"], text)
        if s:
            found["surface"] = s
        t = typology_conflict(r["typology"] or r["typology_raw"], text)
        if t:
            found["typology"] = t
        if found:
            out.append({"row": r, "found": found, "text": text})
    return out


def coverage(conn):
    cov = {}
    for (src,) in conn.execute("SELECT DISTINCT source FROM listings"):
        n = conn.execute("SELECT COUNT(*) FROM listings WHERE source=?",
                         (src,)).fetchone()[0]
        d = conn.execute("SELECT COUNT(*) FROM listings WHERE source=? AND "
                         "description IS NOT NULL AND LENGTH(description)>40",
                         (src,)).fetchone()[0]
        c = conn.execute("SELECT COUNT(*) FROM listings WHERE source=? AND "
                         "caption IS NOT NULL AND LENGTH(caption)>10",
                         (src,)).fetchone()[0]
        cov[src] = (n, d, c)
    return cov


def report(items, conn):
    print("=" * 74)
    print("LISTINGS THAT CONTRADICT THEMSELVES")
    print("=" * 74)
    print("\n  The agency's own structured field against its own text.")
    print("  No matching involved, so no property is linked to another.\n")

    cov = coverage(conn)
    print("  coverage — this decides what can honestly be claimed:")
    for src, (n, d, c) in sorted(cov.items()):
        print(f"    {src:12} {n:5} listings | {d:5} with description "
              f"| {c:5} with caption")

    by_axis = defaultdict(list)
    for it in items:
        for axis in it["found"]:
            by_axis[axis].append(it)

    print(f"\n  candidates: {len(items)}")
    for axis in ("surface", "typology"):
        rows = by_axis.get(axis, [])
        per_src = defaultdict(int)
        for it in rows:
            per_src[it["row"]["source"]] += 1
        print(f"    {axis:9} {len(rows):4}   " +
              ", ".join(f"{k} {v}" for k, v in sorted(per_src.items())))

    # The fairness check, printed rather than left to be noticed.
    for axis, rows in by_axis.items():
        srcs = {it["row"]["source"] for it in rows}
        if len(srcs) == 1:
            print(f"\n  !! every {axis} candidate comes from "
                  f"{next(iter(srcs))} alone. That is a fact about which "
                  f"source publishes text, NOT about which agency is "
                  f"careless, and it must not be published as the latter.")

    print("\n  CANDIDATES — every one needs reading before publication.")


def detail(items, limit=30):
    print("\n" + "=" * 74)
    for it in items[:limit]:
        r = it["row"]
        print(f"\n  {r['agency_name'] or r['source']} — {r['comune']} "
              f"{r['address_raw'] or ''}")
        print(f"  {r['url']}")
        for axis, (val, why) in it["found"].items():
            print(f"    {axis.upper():9} {why}")


def markdown(items, path="self_contradictions.md"):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Listings that contradict themselves\n\n")
        f.write("The agency's own field against its own text. "
                "Candidates — each needs reading before publication.\n\n")
        for it in items:
            r = it["row"]
            f.write(f"## {r['agency_name'] or r['source']} — "
                    f"{(r['comune'] or '').title()}"
                    f"{' ' + r['address_raw'] if r['address_raw'] else ''}\n\n")
            for axis, (val, why) in it["found"].items():
                f.write(f"- **{axis}**: {why}\n")
            f.write(f"\n<{r['url']}>\n\n---\n\n")
    print(f"\n  -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    if a.db:
        import sqlite3
        conn = sqlite3.connect(a.db)
        conn.row_factory = sqlite3.Row
    else:
        conn = db.connect()

    items = build(conn)
    report(items, conn)
    if not a.summary:
        detail(items, a.limit)
    if a.md:
        markdown(items)


if __name__ == "__main__":
    main()
