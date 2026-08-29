"""Apply S004's Marcellini price corrections to the live database.

WHY THIS EXISTS AS A SCRIPT

The corrections were worked out in a sandbox whose mount cannot write
sqlite (S004: even ALTER TABLE returned "disk I/O error"), so they could
not be applied where they were found. Rather than shipping a whole
replacement database, this applies the two changes in place, on the real
file, and reports what it did.

WHAT IT CHANGES, AND NOTHING ELSE

  1. Adds listings.price_bracket if missing.
  2. For every Marcellini row with a price: moves it OUT of `price`,
     because the Marcellini price field is a SEARCH BRACKET, not an
     asking price -- live pages read "Prezzo: meno di EUR 100.000" or
     "tra EUR 200.000 ed EUR 300.000". to_int() took the first number,
     so all 152 "priced" rows were exact 100k multiples, and a EUR
     29.000 flat was published as a +245% contradiction against a
     "EUR 100.000" that actually meant *under* 100.000.
  3. Recovers the real asking price where the listing's own description
     prints one ("Prezzo 214.000,00") -- 31 rows, including the Citerna
     casale at EUR 214.000 that is now the project's best price
     contradiction.

WHAT IT DOES NOT TOUCH

  price_history. A parser change looks exactly like a market event
  (SOT S16), and price_history is the one table that cannot be
  regenerated. These UPDATEs bypass db.observe() deliberately.

  Any source other than marcellini.

Safe to run twice: step 2 is a no-op once the prices are already out.

    cd ~/borgovero/phase0 && python3 apply_S004_fix.py
    python3 apply_S004_fix.py --dry-run     # show, change nothing
"""

import argparse
import re
import sqlite3

import config

PRICE_IN_TEXT = re.compile(
    r"[Pp]rezzo\s*:?\s*(?:€|EUR)?\s*(\d{1,3}(?:\.\d{3})+(?:,\d+)?)")

# The three bracket texts read from live pages in S004. The rest need
# the next agency harvest to recover theirs; they are marked so it is
# obvious they are unrecovered rather than absent.
KNOWN_BRACKETS = {
    "11063": "meno di € 100.000",
    "11077": "meno di € 100.000",
    "11118": "tra € 200.000 ed € 300.000",
}
UNRESOLVED = "bracket (unresolved)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=config.DB_PATH)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row

    have = {r["name"] for r in conn.execute("PRAGMA table_info(listings)")}
    if "price_bracket" not in have:
        print("  adding listings.price_bracket")
        if not a.dry_run:
            conn.execute("ALTER TABLE listings ADD COLUMN price_bracket TEXT")

    rows = conn.execute(
        "SELECT source_id, price, description FROM listings "
        "WHERE source='marcellini'").fetchall()

    moved = recovered = 0
    for r in rows:
        sid, price, desc = r["source_id"], r["price"], r["description"]
        real = None
        if desc:
            m = PRICE_IN_TEXT.search(desc)
            if m:
                p = int(m.group(1).replace(".", "").split(",")[0])
                if p >= 5000:
                    real = p
        if price is None and real is None:
            continue
        bracket = KNOWN_BRACKETS.get(sid, UNRESOLVED if price else None)
        # A row already holding its recovered description price is not a
        # bracket being removed — counting it as one made the second run
        # report work it had not done.
        if price is not None and price != real:
            moved += 1
        if real is not None:
            recovered += 1
        if not a.dry_run:
            conn.execute(
                "UPDATE listings SET price=?, price_bracket=COALESCE(?, price_bracket) "
                "WHERE source='marcellini' AND source_id=?",
                (real, bracket, sid))

    if not a.dry_run:
        conn.commit()

    print(f"  bracket labels removed from price: {moved}")
    print(f"  real prices recovered from descriptions: {recovered}")

    left = conn.execute(
        "SELECT COUNT(*) FROM listings WHERE source='marcellini' "
        "AND price IS NOT NULL").fetchone()[0]
    ph = conn.execute(
        "SELECT COUNT(*) FROM price_history WHERE source='marcellini'"
    ).fetchone()[0]
    print(f"  marcellini rows now carrying a real price: {left}")
    print(f"  price_history marcellini rows (must be 0): {ph}")
    if a.dry_run:
        print("\n  --dry-run: nothing was written")
    conn.close()


if __name__ == "__main__":
    main()
