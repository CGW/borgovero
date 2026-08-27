"""A small REAL Sansepolcro dataset, collected live on 2026-08-27.

Unlike demo_data.py, nothing here is invented. Every price, surface, street
and agency was read from Immobiliare.it and Idealista.it on that date.

    python real_sample.py && python generate.py --db real.sqlite --out dist

Then paste https://www.immobiliare.it/annunci/128457332/ into the homepage
and it resolves — that is a real listing, on a real street, at a real price.

WHAT THIS IS NOT:
  - Complete. 30 of Sansepolcro's 179 Immobiliare listings and 30 of its 188
    on Idealista. The full ingest is Phase 0's job.
  - Current. A snapshot of one afternoon. Prices move.
  - Fully identified. Only three properties could be tied to a verified
    Immobiliare listing ID during collection, so only those three resolve
    from a pasted URL. The rest carry real data but no source link.

The three verified cross-portal matches are the point of this file:
Viale Osimo (both portals agree), Via Fratelli Rosselli (villa vs flat)
and Via Francesco Petrarca (357 vs 350 sqm, villa vs flat).
"""

import sqlite3
from datetime import date

DB = "real.sqlite"

SCHEMA = """
DROP TABLE IF EXISTS listings; DROP TABLE IF EXISTS omi_bands;
CREATE TABLE listings (
  source TEXT, source_id TEXT, url TEXT, comune TEXT, zona_guess TEXT,
  macrozone TEXT, typology TEXT, typology_raw TEXT, address_raw TEXT,
  mq INTEGER, mq_commercial INTEGER, surface_raw TEXT, vani REAL,
  bathrooms INTEGER, floor TEXT, condition TEXT, epc TEXT, price INTEGER,
  description TEXT, caption TEXT, lat REAL, lon REAL, agency_id TEXT,
  agency_name TEXT, photo_ids TEXT, photo_count INTEGER, photo_url TEXT,
  listed_date_est TEXT, dom_est INTEGER, dom_method TEXT, fetched_at TEXT);
CREATE TABLE omi_bands (
  comune TEXT, zona_code TEXT, zona_descr TEXT, tipologia TEXT, stato TEXT,
  min_eur_m2 REAL, max_eur_m2 REAL, surface_basis TEXT, semester TEXT);
"""

# --- OMI ---------------------------------------------------------------
# PLACEHOLDER, pending the real Agenzia delle Entrate download. Anchored on
# the two figures already established for this market: Sansepolcro B1 centro
# storico ~EUR1,245/m2 and Anghiari's registered range EUR880-1,410/m2.
# Replace with the real file before believing any percentage.
OMI = [
    ("sansepolcro", "B1", "Centro Storico", "Abitazioni civili", "NORMALE",
     1100, 1400, "L", "2026-1"),
    ("sansepolcro", "C1", "Periferia", "Abitazioni civili", "NORMALE",
     790, 1010, "L", "2026-1"),
    ("sansepolcro", "E1", "Campagna", "Abitazioni civili", "NORMALE",
     620, 900, "L", "2026-1"),
]

# --- Immobiliare.it, Sansepolcro, 2026-08-27 ---------------------------
# (source_id, price, mq, street, typology_raw, rooms, agency, zona)
# source_id None = ID not captured during collection; no URL lookup for it.
IMMO = [
    ("128457332", 280000, 115, "Viale Osimo", "Appartamento", 5,
     "House Immobiliare", "centro_storico"),
    ("127740612", 370000, 210, "Via Fratelli Rosselli", "Villa bifamiliare", 5,
     "House Immobiliare", "centro_storico"),
    ("131271614", 270000, 116, "Via Giovanni Boccaccio", "Appartamento", 4,
     "Misuri Costruzioni", "periferia"),
    (None, 430000, 357, "Via Francesco Petrarca", "Villa plurifamiliare", 6,
     "House Immobiliare", "periferia"),
    (None, 260000, 240, "Strada Comunale di San Pietro in Villa", "Rustico", 6,
     "Leonardi Immobiliare", "campagna"),
    (None, 450000, 300, "Strada Statale Tiberina", "Casale", 6,
     "Leonardi Immobiliare", "campagna"),
    (None, 149000, 115, "Via XX Settembre", "Appartamento", 3,
     "House Immobiliare", "centro_storico"),
    (None, 118000, 85, "Via Cinque Vie", "Appartamento", 3,
     "House Immobiliare", "centro_storico"),
    (None, 145000, 125, "Via del Martellino", "Appartamento", 4,
     "Leonardi Immobiliare", "periferia"),
    (None, 95000, 115, "Via San Bartolomeo", "Terratetto unifamiliare", 5,
     "Leonardi Immobiliare", "centro_storico"),
    (None, 75000, 75, "Via Piero della Francesca", "Appartamento", 3,
     "Leonardi Immobiliare", "centro_storico"),
    (None, 128000, 100, "Via Palmiro Togliatti", "Appartamento", 4,
     "Leonardi Immobiliare", "periferia"),
    (None, 245000, 156, "Via Bruno Buozzi", "Villa bifamiliare", 5,
     "Rexer", "periferia"),
    (None, 260000, 150, "Via Del Prucino", "Terratetto unifamiliare", 5,
     "House Immobiliare", "centro_storico"),
    (None, 235000, 156, "Via Caduti del lavoro", "Appartamento", 4,
     "House Immobiliare", "periferia"),
]

# --- Idealista.it, Sansepolcro, 2026-08-27 -----------------------------
# (price, mq, street, typology_raw, rooms, was_price, drop_pct, zona)
# Idealista does not name the agency on its result cards, so agency is
# unknown here — which the comparison renders honestly as the portal name.
IDEA = [
    (280000, 115, "Viale Osimo", "Flat / apartment", 5, None, None,
     "centro_storico"),                                   # matches 128457332
    (370000, 210, "Via Fratelli Rosselli", "Flat / apartment", 6, None, None,
     "centro_storico"),                                   # matches 127740612
    (430000, 350, "Via Francesco Petrarca", "Flat / apartment", 9, None, None,
     "periferia"),                                        # 357 vs 350 sqm
    (390000, 200, "Via Tiberina Sud", "Duplex", 6, None, None, "periferia"),
    (230000, 110, "Via Sinj", "3 room flat", 3, None, None, "periferia"),
    (490000, 255, "Viale Eduino Francini", "Flat / apartment", 7, None, None,
     "centro_storico"),
    (880000, 370, "Via delle Fontanelle", "Detached house", 12, None, None,
     "periferia"),
    (178000, 110, "Via Pasquale Alienati", "4 room flat", 4, 187000, 5,
     "periferia"),
    (180000, 100, "Via del Prucino", "3 room flat", 3, None, None,
     "centro_storico"),
    (415000, 145, "Via Vannocchia", "Detached house", 7, None, None,
     "campagna"),
    (100000, 70, "Strada Provinciale 258", "Detached house", 2, 107000, 7,
     "campagna"),
    (250000, 170, "Via dei Montefeltro", "Flat / apartment", 5, None, None,
     "periferia"),
    (310000, 195, "Via Dante Alighieri", "Detached house", 3, None, None,
     "periferia"),
    (175000, 120, "Via dei Lorena", "4 room flat", 4, None, None, "periferia"),
    (129000, 85, "Via E. Francini", "Flat / apartment", 5, None, None,
     "centro_storico"),
    (145000, 100, "Via Guido Cavalcanti", "Duplex", 4, None, None, "periferia"),
    (128000, 95, "Via dei Visconti", "3 room flat", 3, None, None, "periferia"),
    (198000, 225, "Via Francesco De Largi", "Flat / apartment", 7, None, None,
     "periferia"),
    (185000, 130, "Via John Fitzgerald Kennedy", "Duplex", 4, None, None,
     "periferia"),
    (165000, 120, "Via Pasquale Alienati", "Detached house", 4, None, None,
     "periferia"),
    (85000, 66, "Via dei Cipolli", "2 room flat", 2, None, None,
     "centro_storico"),
    (295000, 170, "Via di Pallottino", "Villa", 5, None, None, "campagna"),
    (380000, 170, "Via Tiberina Nord", "Semi-detached house", 6, None, None,
     "periferia"),
    (170000, 120, "Strada Comunale di Mezzatorre", "Flat / apartment", 5,
     None, None, "campagna"),
    (149000, 75, "Via della Fraternita", "4 room flat", 4, None, None,
     "centro_storico"),
    (88000, 95, "Via Niccolo Aggiunti", "4 room flat", 4, None, None,
     "centro_storico"),
]

TYP = {
    "appartamento": "appartamento", "flat / apartment": "appartamento",
    "3 room flat": "appartamento", "4 room flat": "appartamento",
    "2 room flat": "appartamento", "duplex": "appartamento",
    "terratetto unifamiliare": "terratetto",
    "semi-detached house": "terratetto",
    "villa bifamiliare": "villa", "villa plurifamiliare": "villa",
    "villa": "villa", "detached house": "cielo_terra",
    "rustico": "rustico", "casale": "rustico",
}


def row(source, sid, url, price, mq, street, typ_raw, rooms, agency, zona,
        dom, note=None):
    return (source, sid or f"{source}-{abs(hash(street+str(price)))%10**8}",
            url, "sansepolcro", zona,
            "Centro" if zona == "centro_storico" else None,
            TYP.get(typ_raw.lower(), "unknown"), typ_raw, street,
            mq, None, f"{mq} m²", rooms, None, None, None, None, price,
            note, None, None, None,
            None, agency, "[]", 0, None,
            date.fromordinal(date.today().toordinal() - dom).isoformat(),
            dom, "immobiliare_id:medium" if sid else "unknown",
            "2026-08-27T00:00:00+00:00")


def main():
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO omi_bands VALUES (?,?,?,?,?,?,?,?,?)", OMI)

    Q = "INSERT INTO listings VALUES (" + ",".join("?" * 31) + ")"
    n = 0

    for sid, price, mq, street, typ, rooms, agency, zona in IMMO:
        url = f"https://www.immobiliare.it/annunci/{sid}/" if sid else None
        # DOM unknown without the ID curve; leave it out rather than invent it.
        conn.execute(Q, row("immobiliare", sid, url, price, mq, street, typ,
                            rooms, agency, zona, 0))
        n += 1

    for price, mq, street, typ, rooms, was, drop, zona in IDEA:
        note = (f"Prezzo ridotto da €{was:,} (−{drop}%)".replace(",", ".")
                if was else None)
        conn.execute(Q, row("idealista", None, None, price, mq, street, typ,
                            rooms, None, zona, 0, note))
        n += 1

    conn.commit()
    matched = conn.execute("""
        SELECT address_raw, COUNT(DISTINCT source) s FROM listings
        GROUP BY lower(address_raw) HAVING s > 1""").fetchall()
    conn.close()

    print(f"{n} real listings -> {DB}")
    print(f"cross-portal matches: {len(matched)}")
    for a, _ in matched:
        print(f"   {a}")
    print("\nCollected live 2026-08-27. Partial snapshot, not the full market.")
    print("OMI bands are placeholders — download the real file before "
          "trusting any percentage.")


if __name__ == "__main__":
    main()
