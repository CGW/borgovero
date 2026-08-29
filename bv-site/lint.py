"""Build lint — seo-spec.md §10.3. Fails the build, not a report.

    python3 lint.py dist-contradictions/

WHY THIS IS NOT A SUBSTRING BAN
-------------------------------
§3.5 forbids *valutazione*, *perizia*, *stima*, *appraisal*, *valuation*
in published copy. The obvious implementation — grep for the word, fail
if present — fails on the single most important sentence on the site:

    "Non è una perizia."
    "It is not an appraisal."

A lint that forces those sentences off the page would delete the
disclaimer and leave the claim, which is worse than no lint. So this
checks how the word is *used*: a forbidden term is legal when it is
negated or attributed elsewhere ("for a formal valuation you need a
qualified surveyor"), and illegal when the site applies it to itself.

That distinction is exactly the one that mattered in practice. S005 found
the footer declaration on all 36 published pages reading "Borgo Vero è una
valutazione indipendente" — the regulated word, affirmative, about
ourselves, on every page, while the method page two blocks below said
"non è una perizia". A substring ban would have flagged both sentences
equally and told us nothing about which one was the problem.
"""

import glob
import html
import os
import re
import sys

FORBIDDEN = ["valutazione", "valutazioni", "perizia", "perizie", "stima",
             "appraisal", "valuation", "market value", "fair price",
             # Not in §3.5's list, added S005. The EN about page called the
             # site an "independent, non-profit third-party assessment"
             # while the IT one had been fixed to "indice" — so the two
             # languages made different claims about what Borgo Vero is,
             # and the lint passed because §3.5 never named this word.
             # "Assessment" carries in English exactly the implication
             # "valutazione" carries in Italian. §3.5 should gain it.
             "assessment", "assessments"]

# Negations and attributions that make a forbidden term legitimate. Matched
# in the ~60 characters preceding the term, lowercased and de-accented.
EXCUSED = [
    "non è una", "non e una", "non è un", "non e un", "non siamo",
    "non facciamo", "non una", "nessuna", "nessun", "niente", "senza",
    "not a", "not an", "is not", "are not", "no ", "never", "rather than",
    "instead of", "does not claim",
    # Attribution: the term describes what someone ELSE does, or what the
    # reader would need to go elsewhere for. Both are honest uses.
    "per una", "per la", "serve un", "you need", "carried out by",
    "regulated act", "atto che compie", "in italia un", "in italia una",
]

# A comune band must reach the page as an interval. The failure mode is a
# template collapsing it to a midpoint for tidiness, which would publish
# this site's own criticism in this site's own voice (SOT §17.1).
#
# SCOPED TO COMUNE REPORTS BY PATH, deliberately. The first version of this
# check looked for the words "fascia" or "band" anywhere on a page, and
# fired on all 35 contradiction pages — because the shared sources line
# reads "Fasce OMI: Agenzia delle Entrate". A check that fires on every
# page is not a check, it is noise that trains you to ignore the output.
# Comune reports do not exist yet, so this is dormant until they do; that
# is the honest state, and better than a heuristic that looks like
# coverage.
BAND_PATH = re.compile(r"/(comuni|comune)/")
INTERVAL_RE = re.compile(r"\d[\d.,]*\s*(?:&ndash;|–|-|to|a)\s*(?:€|&euro;)?\s*\d")

# Listing index pages (§4.2, enforced per §10.3). Scoped by path like the
# band check, and for the same reason: these requirements are template
# contracts for one page type, not site-wide heuristics.
LISTING_PATH = re.compile(r"/immobili/")

# The extraction paragraph is marked in the template (class="estratto")
# precisely so this check does not have to guess which paragraph is the
# extractable unit. §8.4: 40 words, self-contained.
EXTRACT_RE = re.compile(r'<p class="lede estratto">(.*?)</p>', re.S)
DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

# A Tier C page publishes the agency's own figures and the reason there is
# no index — never a normalized interval. An interval attached to a
# surface or a EUR/m2 on a C page means a normalized figure leaked.
M2_INTERVAL_RE = re.compile(r"\d[\d.,]*\s*–\s*[\d.,]*\d\s*(?:m²|/m²)")


def text_of(path):
    raw = open(path, encoding="utf-8").read()
    # Drop head/style/script before flattening, or CSS tokens land in copy.
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", txt)


def check_terms(path, txt):
    out = []
    low = txt.lower()
    for term in FORBIDDEN:
        # Word boundaries, not substrings. Without \b, "stima" matches
        # inside the English "e-stima-ted" and the lint reports the
        # sentence "days on market are estimated" as an Italian
        # regulated-term violation. Cross-language substring collisions
        # are the reason this list is matched as words.
        for m in re.finditer(r"\b" + re.escape(term) + r"\b", low):
            before = low[max(0, m.start() - 60):m.start()]
            if any(x in before for x in EXCUSED):
                continue
            snippet = txt[max(0, m.start() - 70):m.end() + 40].strip()
            out.append(f"{path}: affirmative use of '{term}' — ...{snippet}...")
    return out


def check_bands(path, txt):
    if not BAND_PATH.search(path.replace(os.sep, "/")):
        return []
    if "€" not in txt and "EUR" not in txt:
        return []
    return ([] if INTERVAL_RE.search(txt) else
            [f"{path}: comune report carries a price but no interval — "
             f"a band must never be rendered as a single figure"])


def check_listing(path, raw, txt):
    if not LISTING_PATH.search(path.replace(os.sep, "/")):
        return []
    out = []

    # §4.2 item 6: source link, retrieval date, standing line. The
    # standing line is checked by its negation clause rather than its full
    # text so an editorial rewording does not silently disable the check —
    # what must never leave the page is the "not a" claim itself.
    if 'rel="nofollow' not in raw:
        out.append(f"{path}: no source link (§4.2.6)")
    if not ("Letto il" in txt or "Retrieved" in txt):
        out.append(f"{path}: no retrieval date (§4.2.6)")
    if not ("Non è una perizia" in txt or "Not a valuation" in txt):
        out.append(f"{path}: standing not-a-valuation line missing (§4.2.6)")

    m = EXTRACT_RE.search(raw)
    if not m:
        out.append(f"{path}: no extraction paragraph (§8.4)")
        return out
    words = html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).split()
    ex = " ".join(words)
    if len(words) > 40:
        out.append(f"{path}: extraction paragraph {len(words)} words, "
                   f"limit 40 (§8.4)")
    if not ("Livello" in ex or "Tier" in ex):
        out.append(f"{path}: extraction paragraph missing tier (§4.2.1)")
    if not DATE_RE.search(ex):
        out.append(f"{path}: extraction paragraph missing retrieval "
                   f"date (§4.2.1)")
    if "Livello B" in ex or "Tier B" in ex:
        for tok, name in (("€", "price"), ("m²", "surface"),
                          ("–", "interval")):
            if tok not in ex:
                out.append(f"{path}: Tier B extraction paragraph missing "
                           f"{name} (§4.2.1)")
    if ("Livello C" in ex or "Tier C" in ex) and M2_INTERVAL_RE.search(txt):
        out.append(f"{path}: Tier C page carries a normalized interval — "
                   f"a C listing publishes no figure of ours (§3.3)")
    return out


def main(root):
    files = sorted(glob.glob(os.path.join(root, "**", "*.html"), recursive=True))
    if not files:
        print(f"lint: no HTML found under {root}", file=sys.stderr)
        return 2

    failures = []
    for f in files:
        raw = open(f, encoding="utf-8").read()
        txt = text_of(f)
        failures += check_terms(f, txt)
        failures += check_bands(f, txt)
        failures += check_listing(f, raw, txt)

    if failures:
        print(f"LINT FAILED — {len(failures)} problem(s) in {len(files)} pages\n")
        for x in failures:
            print("  " + x)
        return 1

    print(f"lint OK — {len(files)} pages, no affirmative use of a forbidden "
          f"term, every published band an interval")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dist-contradictions"))
