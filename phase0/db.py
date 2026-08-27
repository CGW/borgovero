"""SQLite store for Phase 0. Deliberately small — this is a hypothesis test."""

import sqlite3
import json
from pathlib import Path

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    url             TEXT,
    comune          TEXT,
    zona_guess      TEXT,
    macrozone       TEXT,      -- Immobiliare's own zone label
    typology        TEXT,
    typology_raw    TEXT,
    address_raw     TEXT,
    mq              INTEGER,   -- the smaller, non-commercial figure
    mq_commercial   INTEGER,   -- weighted; what agencies quote. See analyze.py
    surface_raw     TEXT,      -- verbatim, e.g. '115 m2 | commerciale 183,2 m2'
    vani            REAL,
    bathrooms       INTEGER,
    floor           TEXT,
    condition       TEXT,      -- ga4Condition, maps to OMI stato_conservativo
    epc             TEXT,      -- detail page only; null in Phase 0
    price           INTEGER,
    description     TEXT,
    caption         TEXT,
    lat             REAL,
    lon             REAL,
    agency_id       TEXT,
    agency_name     TEXT,
    photo_ids       TEXT,      -- json array; stable IDs, feed identity later
    photo_count     INTEGER,
    listed_date_est TEXT,      -- from ID interpolation, ISO date
    dom_est         INTEGER,   -- days on market, derived
    dom_method      TEXT,
    fetched_at      TEXT,
    PRIMARY KEY (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_listings_comune ON listings(comune);
CREATE INDEX IF NOT EXISTS idx_listings_agency ON listings(agency_id);

CREATE TABLE IF NOT EXISTS omi_bands (
    comune        TEXT,
    zona_code     TEXT,
    zona_descr    TEXT,
    tipologia     TEXT,
    stato         TEXT,
    min_eur_m2    REAL,
    max_eur_m2    REAL,
    surface_basis TEXT,   -- 'N' netta / 'L' lorda, as OMI states it
    semester      TEXT
);

CREATE INDEX IF NOT EXISTS idx_omi_comune ON omi_bands(comune);

CREATE TABLE IF NOT EXISTS id_date_pairs (
    source     TEXT,
    source_id  TEXT,
    known_date TEXT,
    method     TEXT,
    PRIMARY KEY (source, source_id)
);
"""


def connect():
    Path(config.HTML_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_listing(conn, rec):
    cols = [
        "source", "source_id", "url", "comune", "zona_guess", "macrozone",
        "typology", "typology_raw", "address_raw", "mq", "mq_commercial",
        "surface_raw", "vani", "bathrooms", "floor", "condition", "epc",
        "price", "description", "caption", "lat", "lon", "agency_id",
        "agency_name", "photo_ids", "photo_count", "listed_date_est",
        "dom_est", "dom_method", "fetched_at",
    ]
    vals = []
    for c in cols:
        v = rec.get(c)
        if isinstance(v, (list, dict)):
            v = json.dumps(v, ensure_ascii=False)
        vals.append(v)

    placeholders = ",".join("?" * len(cols))
    conn.execute(
        f"INSERT OR REPLACE INTO listings ({','.join(cols)}) VALUES ({placeholders})",
        vals,
    )


def listing_exists(conn, source, source_id):
    cur = conn.execute(
        "SELECT 1 FROM listings WHERE source=? AND source_id=?",
        (source, source_id),
    )
    return cur.fetchone() is not None


def all_listings(conn):
    return conn.execute("SELECT * FROM listings").fetchall()


def replace_omi(conn, rows, semester):
    conn.execute("DELETE FROM omi_bands WHERE semester=?", (semester,))
    conn.executemany(
        """INSERT INTO omi_bands
           (comune, zona_code, zona_descr, tipologia, stato,
            min_eur_m2, max_eur_m2, surface_basis, semester)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        rows,
    )


def omi_for(conn, comune, semester):
    # comune is stored already normalised by omi.load() — see
    # config.norm_comune. Normalise the lookup too or 'SAN SEPOLCRO'
    # and 'sansepolcro' never meet.
    return conn.execute(
        "SELECT * FROM omi_bands WHERE comune=? AND semester=?",
        (config.norm_comune(comune), semester),
    ).fetchall()
