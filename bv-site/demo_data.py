"""Build a demo database so the site can be seen before the real ingest.

Everything here is INVENTED. Addresses, agencies and prices are fictional.
It exists to exercise the templates — in particular the multi-source
comparison, which needs properties that appear on several portals with
inconsistent claims about them.

    python demo_data.py && python generate.py --db demo.sqlite --out dist
"""

import random
import sqlite3
from datetime import date

DB = "demo.sqlite"

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

STREETS = ["Via del Pentolo", "Via XX Settembre", "Via dei Gherardi",
           "Viale Osimo", "Via Aggiunti", "Via Niccolò Aggiunti",
           "Via della Fraternita", "Piazza Torre di Berta", "Via Luca Pacioli",
           "Via Tiberina", "Via del Prucino", "Via Santa Croce"]
AGENCIES = ["Agenzia Valtiberina", "Immobiliare Tevere", "Casa Toscana",
            "Borgo Immobili", "Studio Aretino"]
PORTALS = ["immobiliare", "idealista", "casa.it"]
TYPES = [("terratetto", "Terratetto unifamiliare"),
         ("appartamento", "Appartamento"),
         ("cielo_terra", "Casa indipendente"),
         ("villa", "Villa unifamiliare")]
CONDITIONS = ["Ottimo / Ristrutturato", "Buono / Abitabile",
              "Da ristrutturare", "Nuovo / In costruzione"]


def main():
    rnd = random.Random(7)
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)
    today = date.today().toordinal()

    for comune, lo, hi in [("sansepolcro", 1100, 1400), ("anghiari", 880, 1410),
                           ("monterchi", 700, 1050), ("citerna", 720, 1100)]:
        for zc, zd in [("B1", "Centro Storico"), ("C1", "Periferia")]:
            adj = 1.0 if zc == "B1" else 0.72
            conn.execute(
                "INSERT INTO omi_bands VALUES (?,?,?,?,?,?,?,?,?)",
                (comune, zc, zd, "Abitazioni civili", "NORMALE",
                 lo * adj, hi * adj, "L", "2026-1"))

    n = 0
    for comune in ["sansepolcro", "anghiari", "monterchi", "citerna"]:
        for _ in range(rnd.randint(14, 22)):
            typ, typ_raw = rnd.choice(TYPES)
            mq = rnd.randint(65, 240)
            mq_c = int(mq * rnd.uniform(1.30, 1.62))
            zona = rnd.choice(["centro_storico", "periferia"])
            dom = int(rnd.choice([90, 200, 400, 800, 1500, 2400])
                      * rnd.uniform(0.7, 1.3))
            # Older listings drift further above the band.
            mult = 1.0 + (dom / 2400) * rnd.uniform(0.5, 1.3)
            base = int((1400 if comune == "sansepolcro" else 1200)
                       * mult * mq / 1000) * 1000
            addr = f"{rnd.choice(STREETS)}"
            vani = rnd.randint(2, 9)
            baths = rnd.randint(1, 3)
            floor = rnd.choice(["piano terra", "1°", "2°", "3°"])
            cond = rnd.choice(CONDITIONS)
            agency = rnd.choice(AGENCIES)

            # Three real-world shapes, all of which the comparison must
            # handle. Note that portal and agency vary independently: the
            # same firm appears on two portals, and two firms appear on
            # the same portal.
            #
            #   solo          one agency, one portal
            #   multi_agency  two firms carrying the same property
            #   self_conflict one firm, two portals, inconsistent data
            shape = rnd.choices(["solo", "multi_agency", "self_conflict"],
                                weights=[62, 26, 12])[0]
            if shape == "solo":
                placements = [(rnd.choice(PORTALS), agency)]
            elif shape == "multi_agency":
                others = [a for a in AGENCIES if a != agency]
                n2 = rnd.choice([2, 2, 3])
                firms = [agency] + rnd.sample(others, n2 - 1)
                placements = [(rnd.choice(PORTALS), f) for f in firms]
            else:
                two = rnd.sample(PORTALS, 2)
                placements = [(two[0], agency), (two[1], agency)]

            for k, (portal, listing_agency) in enumerate(placements):
                drift = 0 if k == 0 else rnd.choice([0, 0.04, 0.08, -0.03, 0.11])
                mq_d = mq if k == 0 else rnd.choice([mq, mq, mq + 13, mq - 5])
                conn.execute(
                    "INSERT INTO listings VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (portal, f"{130000000 - dom * 9000 + n * 37 + k}",
                     f"https://www.{portal}.it/annunci/{130000000 + n*37 + k}/",
                     comune, zona, "Centro" if zona == "centro_storico" else None,
                     typ, typ_raw if k == 0 else rnd.choice([typ_raw, TYPES[0][1]]),
                     addr, mq_d,
                     mq_c if rnd.random() > 0.25 else None,
                     f"{mq_d} m² | commerciale {mq_c} m²",
                     vani if k == 0 else rnd.choice([vani, vani, vani + 1]),
                     baths, floor if k == 0 else rnd.choice([floor, "1°"]),
                     cond if k == 0 else rnd.choice(CONDITIONS),
                     None, int(base * (1 + drift)), None, None,
                     43.57 + rnd.uniform(-.05, .05), 12.13 + rnd.uniform(-.05, .05),
                     str(1000 + AGENCIES.index(listing_agency)),
                     listing_agency,
                     "[]", rnd.randint(6, 40), None,
                     date.fromordinal(today - dom).isoformat(), dom,
                     "immobiliare_id:medium", "1970-01-01T00:00:00+00:00"))
            n += 1

    conn.commit()
    tot = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    conn.close()
    print(f"{n} demo properties, {tot} source listings -> {DB}")
    print("All data is fictional. Do not publish this build.")


if __name__ == "__main__":
    main()
