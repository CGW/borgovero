"""Street name only. No house numbers, ever. (S009, Christopher's call)

WHY THIS IS ITS OWN MODULE

CasaZebra publishes a permanent, cross-referenced archive of listings that
outlives the listings themselves, and it pairs each address with price,
surface, days-on-market and price-cut history. One agency listing that
names a civico is public information about a property. The same civico in
an archive that also states how long the seller has been waiting and how
far they have already dropped their price is an inference about a
particular household's negotiating position, at an address, that survives
the sale.

Street granularity keeps every finding the site exists to publish — two
agencies disagreeing 48% on a surface is no less true without the number —
and drops the part that identifies a home.

WHAT WENT WRONG, AND IT WAS THE SELECTION RULE

`contradictions.best_label()` chose the cluster's address with
`max(addrs, key=len)`. The longest address is by construction the one
carrying the most identifying detail, so the rule actively preferred the
civico and the CAP. Two pages were live on casazebra.it with it in the URL
and the title:

    sansepolcro-via-della-ginestra-4-cd4560.html      civico 4
    sansepolcro-via-dei-tarlati-52037-cb6e9e.html     CAP 52037

A URL is the worst place for this to land: it is what gets shared, saved,
indexed and archived, and unlike page text it cannot be quietly corrected
later.

NOT THE SAME AS generate.norm_address()

That one also drops digits, but it is a MATCHING key — lowercased, noise
words stripped, never displayed. This is the DISPLAY form: it keeps the
street's real capitalisation and wording so a reader recognises the place.
Two different jobs; keeping them in one function would mean one of them
silently changing when the other needed tuning.
"""

import re

# A civico can be '4', '4/A', '18-20', 'n. 7', 'snc' (senza numero civico),
# or a bare CAP like 52037 that a portal appended to the street.
_CIVICO = re.compile(
    r"""(?ix)
    (?: ,\s* | \s+ )
    (?:
        n\.?\s*\d+[a-z]?(?:\s*/\s*[a-z0-9]+)?     # n. 7, n.7/A
      | snc\b                                      # senza numero civico
      | \d+\s*[/-]\s*[a-z0-9]+                     # 4/A, 18-20
      | \d+\s*[a-z]?\b                             # 4, 4a, and any CAP
    )
    """)

# Everything after the street: 'Sansepolcro, Arezzo, Toscana, 52037, Italia'.
# Cut at the first comma once the civico patterns have been removed, so a
# street that legitimately contains a comma is not the common case.
_TAIL = re.compile(r"\s*[;,]\s*.*$", re.S)

# Street-type words. A string with none of these is probably a locality
# ('Trebbio', 'Localita Gragnano'), which is coarser than a street and so
# fine to keep whole — but it must still lose any trailing number.
_STREET_WORDS = ("via", "viale", "corso", "piazza", "piazzale", "largo",
                 "vicolo", "strada", "lungarno", "borgo", "salita",
                 "traversa", "circonvallazione")


def street_only(addr):
    """The publishable form of an address: street name, nothing finer.

    Returns '' for an empty input so callers can treat 'no address' and
    'address we refuse to print' identically — the page says the same
    thing either way, and a caller that had to distinguish them would be
    a caller reintroducing the civico.
    """
    if not addr:
        return ""

    s = " ".join(str(addr).split())
    s = _TAIL.sub("", s)
    # Repeat: 'Via della Ginestra, 4, 52037' sheds one token per pass.
    for _ in range(4):
        new = _CIVICO.sub("", s).strip(" ,;-")
        if new == s:
            break
        s = new

    s = re.sub(r"\s{2,}", " ", s).strip(" ,;-")
    # A trailing bare number can survive the loop when it is the whole tail.
    s = re.sub(r"[\s,]+\d+[a-z]?$", "", s, flags=re.I).strip(" ,;-")
    return s


def is_street(addr):
    """Whether a label names a street rather than a locality or a title."""
    low = (addr or "").lower()
    return any(low.startswith(w + " ") for w in _STREET_WORDS)


if __name__ == "__main__":
    CASES = [
        ("Via della Ginestra, 4, 52037 Gragnano AR, Italia, Sansepolcro, AR,",
         "Via della Ginestra"),
        ("Via dei Tarlati, 52037 Sansepolcro AR, Italia", "Via dei Tarlati"),
        ("Via dei Tarlati 1122", "Via dei Tarlati"),
        ("Via della Ginestra 4", "Via della Ginestra"),
        ("via senese aretina 3", "via senese aretina"),
        ("Via Palazzetta 18", "Via Palazzetta"),
        ("Loc Cignano, 48D", "Loc Cignano"),
        ("Localita Gragnano, 40", "Localita Gragnano"),
        ("Via Martiri Della Resistenza 6", "Via Martiri Della Resistenza"),
        ("Via Di Violino, 26", "Via Di Violino"),
        ("Trebbio, Sansepolcro, Arezzo, Toscana, 50237, Italia", "Trebbio"),
        ("Via Giovanni Cimabue 11", "Via Giovanni Cimabue"),
        ("Via XX Settembre", "Via XX Settembre"),
        ("Strada Comunale di San Pietro in Villa",
         "Strada Comunale di San Pietro in Villa"),
        ("Via Cinque Vie", "Via Cinque Vie"),
        ("", ""),
        (None, ""),
    ]
    bad = 0
    for raw, want in CASES:
        got = street_only(raw)
        flag = "ok " if got == want else "FAIL"
        if got != want:
            bad += 1
        print(f"  {flag} {str(raw)[:52]:54} -> {got!r}")
    print(f"\n{len(CASES) - bad}/{len(CASES)} passed")
    raise SystemExit(1 if bad else 0)
