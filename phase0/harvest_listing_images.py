"""One listing image per property, downscaled and stripped. (S009)

THE DECISION THIS IMPLEMENTS

Christopher's call, 2026-08-31: publish the agency's photograph, credited,
linked, and removed on request. The alternatives considered and rejected
were abstract generative art (safe, but it does not show the property) and
a sepia filter (which changes nothing about copyright or personal data — a
tint is not a transformation, and it reads as disguise rather than good
faith).

So this is a copy of someone else's photograph, published. That is a real
position with real exposure, taken deliberately rather than laundered. The
mitigations below are what make it defensible; none of them is optional.

SELF-HOSTED, NOT HOTLINKED

Hotlinking would cost nothing and was tempting. It also spends the
agency's bandwidth on our traffic, breaks silently whenever they reorganise
their media library, and leaves us unable to strip anything. A local copy
is friendlier to them AND more controllable.

WHAT EACH IMAGE LOSES ON THE WAY IN

  EXIF, all of it     Camera bodies and phones write GPS into JPEG headers.
                      An agency's marketing photo can carry the exact
                      coordinates of a home. Pillow drops EXIF on re-encode
                      unless explicitly asked to keep it; we never ask.
  resolution          600px wide. Enough to see the property, not enough to
                      read a house number or a licence plate off a facade.
  weight              WebP q70. ~40 KB against ~259 KB originals.

600px is a deliberate compromise and worth naming: it does NOT reliably
prevent a face in a foreground being recognisable. It reduces the odds; it
does not eliminate them. The real safeguard is the opt-out below, and the
honest description of it is 'we take it down when asked', not 'we made it
safe'.

OPT-OUT IS PART OF THE PIPELINE, NOT A PROMISE

data/image_optout.json lists sites and individual listings whose images we
must not publish. It is consulted here AND at render. A takedown that
depends on someone remembering to edit a template is not a takedown.

    python3 harvest_listing_images.py --dry-run
    python3 harvest_listing_images.py
    python3 harvest_listing_images.py --optout romolini

Run on Christopher's machine. Writes into bv-site/assets/listing/.
"""

import argparse
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, ".")

import config   # noqa: E402
import db       # noqa: E402

OUT_DIR = os.path.join("..", "bv-site", "assets", "listing")
OPTOUT = os.path.join("data", "image_optout.json")

WIDTH = 600
QUALITY = 70
DELAY_S = 2.0     # agency hosts, not a CDN — see photomatch.AGENCY_DELAY_S


def load_optout():
    if not os.path.exists(OPTOUT):
        return {"sites": [], "listings": []}
    with open(OPTOUT) as fh:
        return json.load(fh)


def save_optout(d):
    os.makedirs(os.path.dirname(OPTOUT), exist_ok=True)
    with open(OPTOUT, "w") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)


def suppressed(opt, source, source_id):
    return (source in opt.get("sites", [])
            or f"{source}/{source_id}" in opt.get("listings", []))


def asset_name(source, source_id):
    safe = "".join(c if c.isalnum() else "-" for c in str(source_id))
    return f"{source}-{safe}.webp"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--optout", metavar="SITE_OR_SOURCE/ID",
                    help="add to the opt-out list, delete any asset, exit")
    args = ap.parse_args()

    opt = load_optout()

    if args.optout:
        key = "listings" if "/" in args.optout else "sites"
        if args.optout not in opt.setdefault(key, []):
            opt[key].append(args.optout)
            save_optout(opt)
        # Deleting the file is the point. An opt-out that leaves the asset
        # on disk is an opt-out that survives until the next deploy and
        # then quietly reappears.
        gone = 0
        if os.path.isdir(OUT_DIR):
            for fn in list(os.listdir(OUT_DIR)):
                src = fn.rsplit("-", 1)[0] if "-" in fn else ""
                if args.optout == src or fn.startswith(
                        args.optout.replace("/", "-")):
                    os.remove(os.path.join(OUT_DIR, fn))
                    gone += 1
        print(f"opted out: {args.optout}  ({gone} asset(s) deleted)")
        return

    from PIL import Image

    conn = db.connect()
    conn.row_factory = __import__("sqlite3").Row
    rows = conn.execute(
        "SELECT source, source_id, photo_ids FROM listings "
        "WHERE photo_ids IS NOT NULL AND photo_ids NOT IN ('', '[]') "
        "AND price IS NOT NULL AND mq IS NOT NULL "
        "ORDER BY source, source_id").fetchall()

    os.makedirs(OUT_DIR, exist_ok=True)
    todo, skip_opt, skip_have = [], 0, 0
    for r in rows:
        if suppressed(opt, r["source"], r["source_id"]):
            skip_opt += 1
            continue
        dest = os.path.join(OUT_DIR, asset_name(r["source"], r["source_id"]))
        if os.path.exists(dest) and not args.refetch:
            skip_have += 1
            continue
        todo.append((r, dest))

    if args.limit:
        todo = todo[:args.limit]

    print(f"{len(rows)} publishable listing(s) with a photo")
    print(f"  {skip_opt} suppressed by opt-out, {skip_have} already local")
    print(f"  {len(todo)} to fetch  ~{len(todo) * DELAY_S / 60:.0f} min")
    if args.dry_run:
        print("\n--dry-run: nothing fetched")
        return

    ua = {"User-Agent": config.USER_AGENT}
    ok = fail = 0
    total = 0
    for i, (r, dest) in enumerate(todo, 1):
        try:
            pid = json.loads(r["photo_ids"])[0]
            url = (str(pid) if str(pid).startswith("http")
                   else f"https://pic.im-cdn.it/image/{pid}/large.jpg")
            p = urllib.parse.urlsplit(url)
            url = urllib.parse.urlunsplit((
                p.scheme, p.netloc, urllib.parse.quote(p.path, safe="/%"),
                p.query, p.fragment))
            data = urllib.request.urlopen(
                urllib.request.Request(url, headers=ua), timeout=25).read()
            im = Image.open(io.BytesIO(data)).convert("RGB")
            w, h = im.size
            if w > WIDTH:
                im = im.resize((WIDTH, max(1, round(h * WIDTH / w))),
                               Image.LANCZOS)
            # No exif= argument: re-encoding without it is what drops GPS,
            # camera serial, and the original timestamp.
            im.save(dest, "WEBP", quality=QUALITY, method=6)
            total += os.path.getsize(dest)
            ok += 1
        except Exception as e:
            fail += 1
            if fail <= 5:
                print(f"  [{type(e).__name__}] {r['source']}/{r['source_id']}")
        time.sleep(DELAY_S)
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}  {ok} saved  {fail} failed  "
                  f"{total/1024/1024:.1f} MB")

    print(f"\ndone: {ok} image(s), {fail} failed, "
          f"{total/1024/1024:.1f} MB in {OUT_DIR}")
    print("Every one is a third party's photograph. The credit line and the "
          "link are\nnot decoration — they are the reason this is "
          "defensible. Do not let a\ntemplate change drop them.")


if __name__ == "__main__":
    main()
