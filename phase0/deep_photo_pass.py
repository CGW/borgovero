"""Candidate-pair deep photo pass (SOT §15, S008).

WHAT AND WHY

photomatch.py hashes the first PHOTOS_PER_LISTING (8) images of every
listing — enough to find candidates corpus-wide, and raising it for
everyone is the §10.1 superlinear trap. But a pair that already matches
on price+surface+street and lacks only identity evidence deserves a
deeper look before a human spends eyes on it: shared images may sit
deeper in the galleries. This pass hashes the FULL galleries of exactly
the listings sitting in candidate clusters, then reports which pairs now
clear the identity bar (2+ distinct shared images at hamming ≤ 5,
photomatch's STRONG_THRESHOLD/MIN_SHARED, with the same within-listing
dedupe and furniture guard).

Nothing is decided here. New hashes land in photo_hashes; the next
contradictions.py run consumes them exactly as it consumes the shallow
ones, and the verified overlay still gates what publishes (§16d). The
ceiling stands: two agencies who shot the same flat separately can never
be joined by hashes — those pairs end at the human look.

    python3 deep_photo_pass.py            # hash + report
    python3 deep_photo_pass.py --dry-run  # show what would be fetched
    python3 deep_photo_pass.py --db phase0.sqlite
"""

import argparse
import io
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, ".")
import config                                            # noqa: E402
import contradictions                                    # noqa: E402
from photomatch import (THUMB, DELAY_S, STRONG_THRESHOLD, MIN_SHARED,
                        MAX_LISTINGS_PER_IMAGE, dhash, hamming,
                        _dedupe_within)                  # noqa: E402


def candidate_members(conn):
    """Listings in clusters that would PRINT as candidates: no identity
    evidence (ref/photo) and no confirming human verdict. These are the
    §15 pairs — price+surface(+street) matches and photo-weak leads."""
    members = set()
    for it in contradictions.build(conn):
        has_identity = bool(set(it["evidence"]) & {"ref", "photo"})
        if has_identity and not any("photo-weak" in e
                                    for e in it["evidence"]):
            continue
        if it.get("verified"):
            continue
        for g in it["group"]:
            members.add((g["source"], g["source_id"]))
    return members


def deep_hash(conn, members, dry_run=False):
    from PIL import Image
    ua = {"User-Agent": config.USER_AGENT}
    todo = []
    for source, sid in sorted(members):
        row = conn.execute(
            "SELECT photo_ids FROM listings WHERE source=? AND source_id=?",
            (source, sid)).fetchone()
        if not row or not row[0]:
            continue
        ids = [str(p) for p in json.loads(row[0])]
        have = {r[0] for r in conn.execute(
            "SELECT photo_id FROM photo_hashes WHERE source=? AND "
            "source_id=?", (source, sid))}
        missing = [p for p in ids if p not in have]
        if missing:
            todo.append((source, sid, missing))

    n = sum(len(m) for _, _, m in todo)
    print(f"{len(members)} candidate-cluster listings, "
          f"{len(todo)} with unhashed gallery depth, {n} images to fetch "
          f"(~{n * DELAY_S / 60:.0f} min)")
    if dry_run:
        for source, sid, missing in todo:
            print(f"  {source}/{sid}: +{len(missing)}")
        return 0

    n_ok = n_err = 0
    for i, (source, sid, missing) in enumerate(todo, 1):
        for pid in missing:
            try:
                url = pid if pid.startswith("http") else THUMB.format(pid=pid)
                parts = urllib.parse.urlsplit(url)
                url = urllib.parse.urlunsplit((
                    parts.scheme, parts.netloc,
                    urllib.parse.quote(parts.path, safe="/%"),
                    parts.query, parts.fragment))
                req = urllib.request.Request(url, headers=ua)
                data = urllib.request.urlopen(req, timeout=20).read()
                h = dhash(Image.open(io.BytesIO(data)))
                conn.execute(
                    "INSERT OR REPLACE INTO photo_hashes "
                    "(source, source_id, photo_id, dhash) VALUES (?,?,?,?)",
                    (source, sid, pid, format(h, "016x")))
                n_ok += 1
            except Exception:
                n_err += 1
            time.sleep(DELAY_S)
        if i % 5 == 0:
            conn.commit()
    conn.commit()
    print(f"deep-hashed {n_ok} images ({n_err} failed)")
    return n_ok


def report(conn, members):
    """Which candidate pairs now clear the identity bar?"""
    furniture = {r[0] for r in conn.execute(
        "SELECT dhash FROM photo_hashes GROUP BY dhash "
        "HAVING count(DISTINCT source || source_id) > ?",
        (MAX_LISTINGS_PER_IMAGE,))}
    packs = {}
    for source, sid in sorted(members):
        rows = conn.execute(
            "SELECT dhash FROM photo_hashes WHERE source=? AND source_id=?",
            (source, sid)).fetchall()
        hs = _dedupe_within([int(r[0], 16) for r in rows
                             if r[0] not in furniture])
        packs[(source, sid)] = hs

    keys = sorted(packs)
    promoted = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            shared = 0
            used_b = set()
            for ha in packs[a]:
                best = None
                for j, hb in enumerate(packs[b]):
                    if j in used_b:
                        continue
                    if hamming(ha, hb) <= STRONG_THRESHOLD:
                        best = j
                        break
                if best is not None:
                    used_b.add(best)
                    shared += 1
            if shared >= MIN_SHARED:
                promoted.append((a, b, shared))

    if promoted:
        print("\nPAIRS NOW AT IDENTITY STRENGTH (2+ distinct shared "
              "images ≤ 5) — contradictions.py will pick these up:")
        for a, b, s in promoted:
            print(f"  {a[0]}/{a[1]}  <->  {b[0]}/{b[1]}   "
                  f"{s} shared images")
    else:
        print("\nNo candidate pair reached identity strength. The "
              "remaining route is the §16d human look — a non-match "
              "proves nothing.")
    return promoted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="phase0.sqlite")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    members = candidate_members(conn)
    deep_hash(conn, members, dry_run=args.dry_run)
    if not args.dry_run:
        report(conn, members)


if __name__ == "__main__":
    main()
