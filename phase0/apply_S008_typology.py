"""One-off: re-map listings.typology after the S008 map_typology fix.

THE BUG THIS CORRECTS

map_typology() used to scan the structured portal field and the agency
caption as ONE lowercase blob, in TYPOLOGY_MAP dict order. "appartamento"
is the first key, so an agency headline containing the word overrode
Immobiliare's own field on 45 of 844 rows — e.g. 105891071, whose field
says "Terratetto unifamiliare" and whose caption shouts "APPARTAMENTO
INGRESSO INDIPENDENTE". One of those 45 was queued as S008's exhibit
("portal says appartamento, own site says cielo terra") — a contradiction
that existed only in our normalization. The fixed function reads the
field first and falls back to the caption only when the field yields
nothing.

WHAT THIS SCRIPT DOES

Recomputes typology from (typology_raw, caption) with the FIXED function
for immobiliare rows only, and reports every change. Idempotent: a second
run finds nothing to change. Does not touch price, price_history, or any
other source's rows. Run it on the real database on Christopher's
machine — the sandbox mount cannot journal sqlite.

    python3 apply_S008_typology.py --dry-run
    python3 apply_S008_typology.py
"""

import argparse
import sqlite3
import sys

sys.path.insert(0, ".")
from adapters.immobiliare import map_typology  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="phase0.sqlite")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    changes = []
    rows = db.execute(
        "SELECT source_id, typology_raw, caption, typology FROM listings "
        "WHERE source='immobiliare'").fetchall()
    for sid, raw, cap, old in rows:
        new = map_typology(raw, cap)
        if new != (old or "unknown"):
            changes.append((sid, old, new, raw))

    print(f"{len(rows)} immobiliare rows, {len(changes)} typology changes")
    for sid, old, new, raw in changes:
        print(f"  {sid}: {old} -> {new}   (field: {raw!r})")

    if args.dry_run:
        print("dry run — nothing written")
        return
    for sid, old, new, raw in changes:
        db.execute(
            "UPDATE listings SET typology=? WHERE source='immobiliare' "
            "AND source_id=?", (new, sid))
    db.commit()
    print("written" if changes else "nothing to write — already applied")


if __name__ == "__main__":
    main()
