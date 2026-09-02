"""One sepia photograph per comune, for the /it/comuni/ table. (S010)

WHY THESE ARE A DIFFERENT KIND OF IMAGE FROM THE LISTING PHOTOS

`harvest_listing_images.py` publishes third-party photographs under a
deliberate, argued position: credited, linked, EXIF-stripped, removed on
request. Everything in that file's header is about the exposure that
carries.

These eight are not that. They are Christopher's own photographs of the
eight comuni, so there is no copyright question, no agency to credit, no
opt-out to honour and no takedown to promise. They are decoration for a
table, and the only thing they must not do is imply they show a listing.

SEPIA HERE, AND WHY THAT IS NOT THE THING S009 REJECTED

S009 considered a sepia filter for the LISTING photographs and rejected
it: a tint is not a transformation, it changes nothing about copyright or
personal data, and it reads as disguise rather than good faith. That
argument is about someone else's photograph. On our own photographs of a
hill town, sepia is a visual choice and nothing else — it also does the
useful work of making these read as illustration rather than as the
property being discussed, which is exactly the confusion to avoid on a
page full of prices.

EXIF STILL GOES

Ours or not, a phone writes GPS into a JPEG. Nobody is harmed by knowing
where Anghiari is, but the habit is worth keeping unconditional: the day
someone drops a photo taken from their own terrace into this folder, the
pipeline should already be stripping it rather than needing to be told.
Pillow drops EXIF on re-encode unless explicitly asked to keep it; we
never ask.

FILENAMES ARE RESOLVED THROUGH norm_comune, NOT MATCHED AS STRINGS

The folder holds badia_tedalda.jpg, caprese-michelangelo.jpg and
pieve_santo_stefano.jpg — underscores and hyphens mixed. config.COMUNI
uses hyphens; omi_bands.comune uses neither. That exact mismatch cost
S008 three of eight comuni, where a slug-vs-normalized join returned
nothing and looked precisely like "OMI has no band here". So every
filename goes through the same normalizer the database uses, and a file
that does not resolve is reported loudly rather than skipped.

    python3 make_comune_images.py            # writes bv-site/assets/comuni/
    python3 make_comune_images.py --dry-run
"""

import argparse
import os
import sys

import config

SRC_DIR = os.path.join("..", "photos_borgi")
OUT_DIR = os.path.join("..", "bv-site", "assets", "comuni")

# Wide and short: the table cell is a strip, not a portrait. 960 is two
# times the largest rendered width so it stays sharp on a retina screen,
# and q72 on a tinted photograph is indistinguishable from q90 because
# sepia collapses the chroma channels anyway.
WIDTH = 960
RATIO = 3 / 1
QUALITY = 72

# S010: shared with harvest_listing_images.py. The two pipelines have to
# land on the same palette or our photographs and the agencies' sit side
# by side looking like a mistake.
from sepia import sepia


def crop_to_ratio(im):
    w, h = im.size
    want = w / RATIO
    if h > want:                       # too tall: take the middle band
        top = int((h - want) / 2)
        return im.crop((0, top, w, int(top + want)))
    keep = int(h * RATIO)              # too wide: take the middle column
    left = int((w - keep) / 2)
    return im.crop((left, 0, left + keep, h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    from PIL import Image

    if not os.path.isdir(SRC_DIR):
        sys.exit(f"no {SRC_DIR} — nothing to do")

    # {normalized comune: source path}
    found = {}
    for fn in sorted(os.listdir(SRC_DIR)):
        stem, ext = os.path.splitext(fn)
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        found[config.norm_comune(stem.replace("_", " ").replace("-", " "))] = \
            os.path.join(SRC_DIR, fn)

    want = {config.norm_comune(c): c for c in config.COMUNI}
    missing = [c for n, c in want.items() if n not in found]
    extra = [p for n, p in found.items() if n not in want]

    print(f"{len(found)} image(s) in {SRC_DIR}, "
          f"{len(want) - len(missing)} of {len(want)} comuni matched")
    if missing:
        print(f"  NO PHOTO: {', '.join(sorted(missing))}")
    if extra:
        # Loud, not silent. A file that resolves to nothing is either a
        # comune we do not cover or a filename the normalizer could not
        # read, and those need different fixes.
        print(f"  UNMATCHED FILE(S): {', '.join(sorted(extra))}")

    if a.dry_run:
        print("\n--dry-run: nothing written")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    total = 0
    for norm, slug in sorted(want.items()):
        src = found.get(norm)
        if not src:
            continue
        im = Image.open(src)
        im = crop_to_ratio(im.convert("RGB"))
        w, h = im.size
        if w > WIDTH:
            im = im.resize((WIDTH, max(1, round(h * WIDTH / w))),
                           Image.LANCZOS)
        # No exif= argument. That omission IS the stripping.
        dest = os.path.join(OUT_DIR, f"{slug}.webp")
        sepia(im).save(dest, "WEBP", quality=QUALITY, method=6)
        total += os.path.getsize(dest)
        print(f"  {slug}.webp  {im.size[0]}x{im.size[1]}  "
              f"{os.path.getsize(dest) / 1024:.0f} KB")
    print(f"\ndone: {total / 1024:.0f} KB in {OUT_DIR}")


if __name__ == "__main__":
    main()
