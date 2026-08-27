"""OMI band loader.

The Agenzia delle Entrate publishes semestral property quotations as a
zipped, semicolon-delimited CSV. Column names have shifted across releases,
so nothing here assumes them — run `--inspect` first, then fix
config.OMI_COLUMNS if needed.

Download:
    https://www1.agenziaentrate.gov.it/servizi/Consultazione/ricerca.htm

You want the *valori* file (quotations), not the *zone* file (geometry).
"""

import argparse
import csv
import sys

import config
import db


def sniff(path):
    """Return (delimiter, fieldnames) without assuming either."""
    with open(path, encoding="latin-1", errors="replace") as f:
        sample = f.read(8192)
        f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.reader(f, delimiter=delim)
        header = next(reader)
        # AdE files sometimes carry a preamble line before the real header.
        if len(header) < 5:
            header = next(reader)
        return delim, [h.strip() for h in header]


def inspect(path):
    delim, cols = sniff(path)
    print(f"File:      {path}")
    print(f"Delimiter: {delim!r}")
    print(f"Columns:   {len(cols)}\n")
    for c in cols:
        print(f"  {c}")

    print("\n--- Suggested config.OMI_COLUMNS ---")
    guesses = {
        "comune":     ["comune_descrizione", "comune", "comune_amm"],
        "zona":       ["zona_descr", "descr_zona", "microzona"],
        "zona_code":  ["zona", "cod_zona", "linkzona"],
        "fascia":     ["fascia"],
        "tipologia":  ["descr_tipologia", "tipologia"],
        "stato":      ["stato_conservativo", "stato"],
        "min_eur_m2": ["compr_min", "valore_min", "min"],
        "max_eur_m2": ["compr_max", "valore_max", "max"],
    }
    lower = {c.lower(): c for c in cols}
    out = {}
    for key, cands in guesses.items():
        hit = next((lower[c] for c in cands if c in lower), None)
        if not hit:
            hit = next((orig for lc, orig in lower.items()
                        if any(c in lc for c in cands)), None)
        out[key] = hit
    print("OMI_COLUMNS = {")
    for k, v in out.items():
        mark = "" if v else "   # <-- NOT FOUND, set manually"
        print(f'    "{k}":{" " * (12 - len(k))}{v!r},{mark}')
    print("}")

    with open(path, encoding="latin-1", errors="replace") as f:
        r = csv.DictReader(f, delimiter=delim)
        rows = [next(r) for _ in range(3)]
    print("\n--- First rows ---")
    for row in rows:
        print({k: v for k, v in list(row.items())[:10]})


def _num(v):
    if v is None:
        return None
    s = str(v).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def load(path, comuni, semester):
    delim, cols = sniff(path)
    m = config.OMI_COLUMNS
    wanted = {c.lower() for c in comuni}
    rows = []

    with open(path, encoding="latin-1", errors="replace") as f:
        for rec in csv.DictReader(f, delimiter=delim):
            comune = (rec.get(m["comune"]) or "").strip()
            if comune.lower() not in wanted:
                continue
            lo = _num(rec.get(m["min_eur_m2"]))
            hi = _num(rec.get(m["max_eur_m2"]))
            if lo is None or hi is None:
                continue
            rows.append((
                comune.lower(),
                (rec.get(m["zona_code"]) or "").strip(),
                (rec.get(m["zona"]) or "").strip(),
                (rec.get(m["tipologia"]) or "").strip(),
                (rec.get(m["stato"]) or "").strip(),
                lo, hi,
                (rec.get(m.get("surface_basis", "")) or "").strip().upper(),
                semester,
            ))
    return rows


def report_surface_basis(rows):
    """Which surface OMI's EUR/m2 refers to.

    Everything downstream hinges on this. An advertised 'superficie' is
    floor area; 'commerciale' adds weighted balconies, terraces and
    garages. OMI quotes netta or lorda. Comparing the wrong pair produces
    a number that looks authoritative and means nothing.
    """
    seen = {}
    for r in rows:
        b = r[7] or "?"
        seen[b] = seen.get(b, 0) + 1

    print("\n--- OMI surface basis ---")
    labels = {"N": "NETTA (internal floor area)",
              "L": "LORDA (includes walls)",
              "?": "NOT STATED in this file"}
    for b, n in sorted(seen.items(), key=lambda x: -x[1]):
        print(f"  {labels.get(b, b):32} {n} rows")

    if "?" in seen and len(seen) == 1:
        print("\n  !! The surface-basis column was not found or is empty.")
        print("     Check OMI_COLUMNS['surface_basis'] against --inspect.")
        print("     Until this is known, neither EUR/m2 comparison is anchored.")
    return seen


def sanity_check(rows):
    """Compare against known anchors. Wrong columns show up here loudly."""
    print("\n--- Sanity check against known anchors ---")
    ok = True
    for (comune, zona), (exp_lo, exp_hi) in config.OMI_SANITY_ANCHORS.items():
        rel = [r for r in rows if r[0] == comune
               and (zona is None or r[1].upper() == zona.upper())]
        if not rel:
            print(f"  {comune} {zona or ''}: NO ROWS — check comune spelling")
            ok = False
            continue
        lo = min(r[5] for r in rel)
        hi = max(r[6] for r in rel)
        label = f"{comune} {zona or ''}".strip()
        fits = lo >= exp_lo * 0.5 and hi <= exp_hi * 2.0
        print(f"  {label:24} loaded EUR{lo:,.0f}-{hi:,.0f}  "
              f"expected ~EUR{exp_lo:,}-{exp_hi:,}  "
              f"{'OK' if fits else '<-- CHECK COLUMN MAPPING'}")
        ok = ok and fits
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true",
                    help="print columns and suggested mapping, load nothing")
    ap.add_argument("--path", default=config.OMI_CSV_PATH)
    args = ap.parse_args()

    if args.inspect:
        inspect(args.path)
        return

    rows = load(args.path, config.COMUNI, config.OMI_SEMESTER)
    print(f"Loaded {len(rows)} band rows for {', '.join(config.COMUNI)}")
    if not rows:
        print("\n!! Nothing loaded. Run --inspect and check OMI_COLUMNS,")
        print("   and confirm comune spelling matches the file exactly.")
        sys.exit(1)

    sanity_check(rows)
    report_surface_basis(rows)

    conn = db.connect()
    db.replace_omi(conn, rows, config.OMI_SEMESTER)
    conn.commit()
    print(f"\nStored under semester {config.OMI_SEMESTER}.")


if __name__ == "__main__":
    main()
