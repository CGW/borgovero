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
    """Return (delimiter, fieldnames, skip) without assuming any of them.

    `skip` is how many preamble lines sit above the real header. The AdE
    export opens with a caption line —

        Quotazioni Immobiliari : Valori di Mercato - Semestre 2025/2 - ...

    — which carries no delimiters. Feeding that to DictReader makes the
    caption the fieldnames, every lookup returns None, and the loader
    reports zero matching rows as though the file were for the wrong
    province. Callers must skip it; see rows().
    """
    with open(path, encoding="latin-1", errors="replace") as f:
        sample = f.read(8192)
        f.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        reader = csv.reader(f, delimiter=delim)
        skip = 0
        header = next(reader)
        if len(header) < 5:
            header = next(reader)
            skip = 1
        return delim, [h.strip() for h in header], skip


def rows(path):
    """DictReader positioned past the preamble. The only correct way in."""
    delim, cols, skip = sniff(path)
    f = open(path, encoding="latin-1", errors="replace")
    for _ in range(skip):
        next(f)
    return csv.DictReader(f, delimiter=delim), cols


def inspect(path):
    delim, cols, skip = sniff(path)
    print(f"File:      {path}")
    print(f"Delimiter: {delim!r}")
    print(f"Preamble:  {skip} line(s) above the header")
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

    reader, _ = rows(path)
    print("\n--- First rows ---")
    for row, _i in zip(reader, range(3)):
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
    m = config.OMI_COLUMNS
    # OMI writes 'SAN SEPOLCRO'; we write 'sansepolcro'. Compare on the
    # normalised key or every Sansepolcro band is skipped without a word.
    wanted = {config.norm_comune(c) for c in comuni}
    zona_labels = zone_labels(zone_path_for(path))
    out = []
    seen = set()

    reader, _cols = rows(path)
    for rec in reader:
        comune = (rec.get(m["comune"]) or "").strip()
        if comune:
            seen.add(comune)
        if config.norm_comune(comune) not in wanted:
            continue
        lo = _num(rec.get(m["min_eur_m2"]))
        hi = _num(rec.get(m["max_eur_m2"]))
        if lo is None or hi is None:
            continue
        link = (rec.get("LinkZona") or "").strip()
        # Zona_Descr lives in the ZONE file, joined on LinkZona. Without
        # it, centro-storico detection falls back to the B-prefix
        # heuristic — good enough to split a distribution, not to publish.
        descr = zona_labels.get(link) or (
            (rec.get(m["zona"]) or "").strip() if m.get("zona") else "")
        out.append((
            config.norm_comune(comune),
            (rec.get(m["zona_code"]) or "").strip(),
            descr,
            (rec.get(m["tipologia"]) or "").strip(),
            (rec.get(m["stato"]) or "").strip(),
            lo, hi,
            (rec.get(m.get("surface_basis", "")) or "").strip().upper(),
            semester,
        ))
    rows_ = out

    if not rows_:
        near = sorted(c for c in seen
                      if any(config.norm_comune(c)[:4] == w[:4] for w in wanted))
        print(f"\n  !! No bands matched {sorted(wanted)}.")
        if near:
            print(f"     Closest names in the file: {near[:8]}")
            print("     Add the right spelling to config.COMUNI, or extend")
            print("     norm_comune() if this is a punctuation difference.")
        else:
            print(f"     The file holds {len(seen)} distinct comuni and none")
            print("     resemble the ones requested. Wrong file, or the")
            print("     'comune' column mapping is wrong.")
    return rows_


def zone_path_for(valori_path):
    """The ZONE file that pairs with a VALORI file, if it is beside it.

    AdE ships them together as QIP_<id>_1_<semester>_VALORI.csv and
    ..._ZONE.csv. The zone file carries Zona_Descr, which valori does not.
    """
    from pathlib import Path
    p = Path(valori_path)
    for cand in (p.with_name(p.name.replace("VALORI", "ZONE")),
                 p.with_name("omi_zone.csv"),
                 p.with_name("zone.csv")):
        if cand.exists() and cand != p:
            return str(cand)
    return None


def zone_labels(zone_path):
    """LinkZona -> Zona_Descr. Empty dict if no zone file is present.

    Descriptions arrive wrapped in single quotes ('CENTRO STORICO - ...'),
    which are stripped here rather than left to surprise a downstream
    string match.
    """
    if not zone_path:
        return {}
    reader, cols = rows(zone_path)
    if "Zona_Descr" not in cols or "LinkZona" not in cols:
        return {}
    out = {}
    for rec in reader:
        link = (rec.get("LinkZona") or "").strip()
        descr = (rec.get("Zona_Descr") or "").strip().strip("'").strip()
        if link and descr:
            out[link] = descr
    return out


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
