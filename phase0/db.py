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
    -- Idealista publishes a previous asking price and the percentage cut
    -- right on the search page. Immobiliare does not. This is the only
    -- price history available without observing the market for months,
    -- and it is overwritten on the portal's next update — capture it on
    -- every run or it is gone.
    price_previous  INTEGER,
    price_cut_pct   REAL,
    -- Idealista also prints EUR/m2 computed on ITS OWN surface figure,
    -- which sometimes differs from Immobiliare's for the same property.
    -- Stored as stated rather than recomputed; the divergence is a finding.
    eur_m2_stated   REAL,
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

-- Observation history. THE POINT OF RUNNING ON A SCHEDULE.
--
-- `listings` holds the CURRENT state and upserts overwrite it, so on its
-- own a second ingest destroys the previous price instead of recording a
-- change. This table is what makes repeated runs accumulate rather than
-- flatten, and it is the only route to the two numbers the Target Offer
-- engine currently assumes (SOT S16):
--
--   the real negotiation ladder   price cuts observed over time
--   whether listings relist       an id vanishing and similar stock
--                                 reappearing under a new id (SOT S8)
--
-- One row per OBSERVED CHANGE, not one per run — re-ingesting an
-- unchanged listing writes nothing here. Cheap to keep forever.
CREATE TABLE IF NOT EXISTS price_history (
    source     TEXT NOT NULL,
    source_id  TEXT NOT NULL,
    seen_at    TEXT NOT NULL,   -- ISO, when we observed this price
    price      INTEGER,
    prev_price INTEGER,         -- null on first sighting
    PRIMARY KEY (source, source_id, seen_at)
);

CREATE INDEX IF NOT EXISTS idx_price_hist ON price_history(source, source_id);

CREATE TABLE IF NOT EXISTS id_date_pairs (
    source     TEXT,
    source_id  TEXT,
    known_date TEXT,
    method     TEXT,
    PRIMARY KEY (source, source_id)
);
"""


# Columns added after the first schema shipped. CREATE TABLE IF NOT EXISTS
# will not add a column to a table that already exists, so a database made
# before these landed would silently lack them and every write would fail.
LATE_COLUMNS = {
    "listings": [
        ("price_previous", "INTEGER"),
        ("price_cut_pct", "REAL"),
        ("eur_m2_stated", "REAL"),
        # OMI zone code from point-in-polygon against the official KML
        # perimeters (zones.py). NULL = unknown (no coords, no KML for the
        # comune, or the point sits in no zone polygon); analyze.py falls
        # back to zona_guess for those rows only.
        ("zona_poly", "TEXT"),
        # Observation window. first_seen is set once and never updated;
        # last_seen moves every run. A listing whose last_seen falls
        # behind the latest run has DISAPPEARED — sold, withdrawn, or
        # relisted under a new id — and that is the closest thing to a
        # sale signal this project can observe (SOT S8).
        ("first_seen", "TEXT"),
        ("last_seen", "TEXT"),
        # The agency's OWN reference ("rif. 0383", "Rif: 11175"). The
        # best join key available (SOT S16c): exact and agency-issued,
        # where photo matching only ever yields candidates to eyeball.
        ("agency_ref", "TEXT"),
        # Marcellini's default is "Prezzo: trattativa riservata". Stored
        # as a flag with price NULL rather than coerced or dropped — how
        # often an agency hides its price measures market opacity, which
        # is the thing this project exists to show.
        ("price_withheld", "INTEGER"),
        ("title", "TEXT"),
        ("zona_raw", "TEXT"),
        # Marcellini's price FIELD is a search bracket, not an asking
        # price: live pages read "meno di (euro) 100.000" or "tra
        # (euro) 200.000 ed (euro) 300.000" (verified in-browser
        # 2026-08-29, S004). to_int() took the first number, so ALL 152
        # "priced" Marcellini rows were 100k multiples — brackets stored
        # as prices, which manufactured the +245% Badia "contradiction".
        # The bracket text is kept here verbatim; `price` holds a real
        # figure only when the listing's own description prints one
        # ("Prezzo 214.000,00" — 31 of 229 stored descriptions do).
        # 'bracket (unresolved)' marks rows corrected in S004 whose
        # exact bracket text needs the next harvest to recover.
        ("price_bracket", "TEXT"),
    ],
}


def _migrate(conn):
    for table, cols in LATE_COLUMNS.items():
        have = {r["name"] for r in
                conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, decl in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    conn.commit()


def connect():
    Path(config.HTML_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def observe(conn, rec, seen_at):
    """Record what changed BEFORE the upsert overwrites it.

    Must be called before upsert_listing or the previous price is already
    gone — `INSERT OR REPLACE` does not preserve it. This is the whole
    reason repeated ingests are worth running.

    Returns 'new' | 'price_change' | 'unchanged'.

    TRAP, hit on 2026-08-28 and it WILL recur: a PARSER CHANGE looks
    exactly like a market event. Fixing `to_int` so Marcellini price
    ranges stopped concatenating ('200.000 - 300.000' had been parsing
    as 200000300000) made 96 of 152 priced listings report a
    'price_change' in a two-hour window. None of them were real.

    price_history is the one table that cannot be regenerated, and it is
    what the negotiation ladder will eventually be measured from, so
    fabricated cuts in it are worse than no data at all.

    RULE: after changing any price parser, delete that source's rows for
    the run that follows —

        DELETE FROM price_history WHERE source=? AND seen_at >= ?

    and note it in the SOT changelog so a later session does not read the
    spike as a market signal.
    """
    row = conn.execute(
        "SELECT price, first_seen FROM listings WHERE source=? AND source_id=?",
        (rec.get("source"), rec.get("source_id")),
    ).fetchone()

    new_price = rec.get("price")

    if row is None:
        rec["first_seen"] = seen_at
        rec["last_seen"] = seen_at
        conn.execute(
            "INSERT OR IGNORE INTO price_history "
            "(source, source_id, seen_at, price, prev_price) VALUES (?,?,?,?,?)",
            (rec.get("source"), rec.get("source_id"), seen_at, new_price, None),
        )
        return "new"

    rec["first_seen"] = row["first_seen"] or seen_at
    rec["last_seen"] = seen_at

    old_price = row["price"]
    if new_price is not None and old_price is not None and new_price != old_price:
        conn.execute(
            "INSERT OR IGNORE INTO price_history "
            "(source, source_id, seen_at, price, prev_price) VALUES (?,?,?,?,?)",
            (rec.get("source"), rec.get("source_id"), seen_at,
             new_price, old_price),
        )
        return "price_change"
    return "unchanged"


def disappeared(conn, source, latest_run):
    """Listings not seen in the latest run. See the first_seen comment."""
    return conn.execute(
        "SELECT source_id, price, first_seen, last_seen, url FROM listings "
        "WHERE source=? AND last_seen IS NOT NULL AND last_seen < ?",
        (source, latest_run),
    ).fetchall()


def price_changes(conn, since=None):
    q = "SELECT * FROM price_history WHERE prev_price IS NOT NULL"
    args = []
    if since:
        q += " AND seen_at >= ?"
        args.append(since)
    return conn.execute(q + " ORDER BY seen_at DESC", args).fetchall()


def upsert_listing(conn, rec):
    cols = [
        "source", "source_id", "url", "comune", "zona_guess", "macrozone",
        "typology", "typology_raw", "address_raw", "mq", "mq_commercial",
        "surface_raw", "vani", "bathrooms", "floor", "condition", "epc",
        "price", "price_previous", "price_cut_pct", "eur_m2_stated",
        "description", "caption", "lat", "lon", "agency_id",
        "agency_name", "photo_ids", "photo_count", "listed_date_est",
        "dom_est", "dom_method", "fetched_at", "first_seen", "last_seen",
        "agency_ref", "price_withheld", "title", "zona_raw",
        "price_bracket",
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
