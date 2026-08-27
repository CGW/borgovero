"""Seed a throwaway database with synthetic listings and run the analysis.

Purpose: prove the analysis pipeline works before you point anything at the
network. It fabricates a market with a deliberate stale tail — fresh
listings near the band, old ones far above it — so you can confirm the
decision gate detects the shape it is supposed to detect.

    python selftest.py

Writes to selftest.sqlite, never touches phase0.sqlite. The numbers it
prints are invented. Delete the file afterwards.
"""

import random
import subprocess
import sys
from datetime import date

import config

config.DB_PATH = "selftest.sqlite"

import db  # noqa: E402  (must follow the DB_PATH override)


def seed():
    conn = db.connect()
    conn.execute("DELETE FROM listings")
    conn.execute("DELETE FROM omi_bands")

    db.replace_omi(conn, [
        ("sansepolcro", "B1", "Centro Storico", "Abitazioni civili",
         "NORMALE", 1100.0, 1400.0, "L", config.OMI_SEMESTER),
        ("sansepolcro", "C1", "Periferia", "Abitazioni civili",
         "NORMALE", 750.0, 1050.0, "L", config.OMI_SEMESTER),
        ("anghiari", "B1", "Centro Storico", "Abitazioni civili",
         "NORMALE", 880.0, 1410.0, "L", config.OMI_SEMESTER),
    ], config.OMI_SEMESTER)

    rnd = random.Random(42)
    today = date.today().toordinal()

    # Deliberate shape: overpricing rises with age.
    profiles = [
        (90,   1.02, 60),
        (270,  1.10, 50),
        (550,  1.28, 45),
        (1100, 1.55, 40),
        (2200, 1.95, 35),
    ]

    n = 0
    for dom, mult, count in profiles:
        for _ in range(count):
            comune = rnd.choice(["sansepolcro", "anghiari"])
            zona = rnd.choice(["centro_storico", "periferia"])
            ceiling = 1400.0 if comune == "sansepolcro" else 1410.0
            mq = rnd.randint(60, 220)
            eur_m2 = ceiling * mult * rnd.uniform(0.85, 1.15)
            d = dom + rnd.randint(-40, 40)

            # Commerciale runs ~35-60% above net, matching what was
            # observed live (115 vs 183 m2 on a real listing).
            mq_comm = int(mq * rnd.uniform(1.35, 1.60))

            db.upsert_listing(conn, {
                "source": "immobiliare",
                "source_id": f"SYN{n:05d}",
                "url": f"https://example.invalid/annunci/SYN{n:05d}/",
                "comune": comune,
                "zona_guess": zona,
                "macrozone": "Centro" if zona == "centro_storico" else None,
                "typology": rnd.choice(
                    ["terratetto", "appartamento", "cielo_terra"]),
                "typology_raw": "Appartamento",
                "address_raw": f"Via Sintetica {n}",
                "mq": mq,
                "mq_commercial": mq_comm,
                "surface_raw": f"{mq} m² | commerciale {mq_comm} m²",
                "vani": rnd.randint(2, 8),
                "bathrooms": rnd.randint(1, 3),
                "condition": "Buono / Abitabile",
                "price": int(eur_m2 * mq),
                "agency_id": str(100000 + rnd.randint(0, 5)),
                "agency_name": rnd.choice(
                    ["Agenzia Alfa", "Agenzia Beta", "Agenzia Gamma"]),
                "photo_ids": [],
                "photo_count": rnd.randint(5, 40),
                "listed_date_est": date.fromordinal(today - d).isoformat(),
                "dom_est": d,
                "dom_method": "synthetic",
                "fetched_at": "1970-01-01T00:00:00+00:00",
            })
            n += 1

    conn.commit()
    print(f"Seeded {n} synthetic listings and 3 OMI bands "
          f"into {config.DB_PATH}\n")
    return n


if __name__ == "__main__":
    seed()
    print("=" * 72)
    print("Running analyze.py against the synthetic data")
    print("Expect: rising overpricing by age, and a STALE TAIL verdict.")
    print("=" * 72 + "\n")

    r = subprocess.run(
        [sys.executable, "-c",
         "import config; config.DB_PATH='selftest.sqlite';"
         "import analyze; analyze.main()"],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.stderr:
        print("STDERR:", r.stderr, file=sys.stderr)
        sys.exit(1)
