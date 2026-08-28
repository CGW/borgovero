"""Zone assignment by point-in-polygon against the OMI zone perimeters.

Replaces the text guess in `map_zona` (§12.3 of the SOT): Immobiliare's
`macrozone` label is only 64,7% populated and the keyword fallback put 393
of 696 usable listings in the centro storico and 9 in campagna, in a
market where 146 listings are farmhouses. Every listing already carries
lat/lon from `__NEXT_DATA__`; the Agenzia delle Entrate publishes the
official zone perimeters as KML. Crossing the two is exact, free, and
uses no third-party dependency: `zipfile` + `xml.etree` + ~30 lines of
ray casting.

Writes `listings.zona_poly` — the OMI zone code (B1, C1, R2...) the
listing's coordinates fall inside, or NULL when:

  - the listing has no coordinates (12 of 844), or
  - its comune has no KML in the archive (Citerna: province of Perugia,
    not in the Arezzo file — same reason it has no bands, §12.6), or
  - the point falls inside no zone polygon. OMI zones are supposed to
    tile the comune, but perimeters are digitised and a point can sit in
    a sliver gap or genuinely outside the comune boundary.

NULL means "unknown", and analyze.py falls back to the old text guess for
those rows only — never silently for everything.

Usage:
    python3 zones.py            # assign, write zona_poly, report
    python3 zones.py --check    # report only, write nothing
"""

import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import config
import db

KML_ZIP = "data/QIP1421390_WRDCRS77S02Z404C/AR20252.zip"


# --- KML parsing -------------------------------------------------------

def _localname(tag):
    return tag.rsplit("}", 1)[-1]


def _parse_ring(text):
    """KML <coordinates>: 'lon,lat[,alt] lon,lat[,alt] ...' -> [(lon, lat)]."""
    ring = []
    for tok in (text or "").split():
        parts = tok.split(",")
        if len(parts) >= 2:
            ring.append((float(parts[0]), float(parts[1])))
    return ring


def _polygons_of(placemark):
    """Every <Polygon> under a placemark as (outer, [holes])."""
    polys = []
    for el in placemark.iter():
        if _localname(el.tag) != "Polygon":
            continue
        outer, holes = None, []
        for b in el.iter():
            name = _localname(b.tag)
            if name not in ("outerBoundaryIs", "innerBoundaryIs"):
                continue
            for coords in b.iter():
                if _localname(coords.tag) == "coordinates":
                    ring = _parse_ring(coords.text)
                    if len(ring) >= 3:
                        if name == "outerBoundaryIs":
                            outer = ring
                        else:
                            holes.append(ring)
        if outer:
            polys.append((outer, holes))
    return polys


def _zona_code(placemark):
    """CODZONA from ExtendedData. The name element carries it too, but the
    structured field is the one the file format commits to."""
    for data in placemark.iter():
        if _localname(data.tag) == "Data" and data.get("name") == "CODZONA":
            for v in data:
                if _localname(v.tag) == "value":
                    return (v.text or "").strip() or None
    return None


def load_zones(zip_path=KML_ZIP):
    """{norm_comune: [(zona_code, [(outer, holes)])]} for in-scope comuni.

    The archive holds every comune in the province; the Document <name>
    ('SANSEPOLCRO (AR) Anno/Semestre 2025/2 ...') identifies each one, so
    membership is decided by name rather than a hand-kept table of
    codici catastali that would fail silently on a typo.
    """
    scope = {config.norm_comune(c) for c in config.COMUNI}
    zones = {}
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            if not member.lower().endswith(".kml"):
                continue
            root = ET.fromstring(zf.read(member))
            doc_name = ""
            for el in root.iter():
                if _localname(el.tag) == "name":
                    doc_name = el.text or ""
                    break
            comune = config.norm_comune(doc_name.split("(")[0])
            if comune not in scope:
                continue
            per_comune = zones.setdefault(comune, [])
            for pm in root.iter():
                if _localname(pm.tag) != "Placemark":
                    continue
                code = _zona_code(pm)
                polys = _polygons_of(pm)
                if code and polys:
                    per_comune.append((code, polys))
    return zones


# --- point in polygon --------------------------------------------------

def _in_ring(lon, lat, ring):
    """Even-odd ray casting. Ring is [(lon, lat)], closed or not."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x_cross = xi + (lat - yi) / (yj - yi) * (xj - xi)
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _in_polygon(lon, lat, outer, holes):
    if not _in_ring(lon, lat, outer):
        return False
    return not any(_in_ring(lon, lat, h) for h in holes)


def _bbox(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


class ZoneIndex:
    """Zone lookup for one comune, with bbox pre-check."""

    def __init__(self, zone_list):
        self.entries = []
        for code, polys in zone_list:
            for outer, holes in polys:
                self.entries.append((code, _bbox(outer), outer, holes))

    def locate(self, lat, lon):
        for code, (x0, y0, x1, y1), outer, holes in self.entries:
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            if _in_polygon(lon, lat, outer, holes):
                return code
        return None


# --- assignment --------------------------------------------------------

def fascia_class(zona_code):
    """B1 -> centro_storico etc., for comparison against the old guess."""
    letter = (zona_code or "")[:1].upper()
    for cls, letters in config.ZONA_TO_FASCIA.items():
        if letter in letters:
            return cls
    return None


def assign(conn, write=True, zip_path=KML_ZIP):
    zones = load_zones(zip_path)
    indexes = {c: ZoneIndex(zl) for c, zl in zones.items()}

    listings = conn.execute(
        "SELECT source, source_id, comune, lat, lon, zona_guess "
        "FROM listings").fetchall()

    counts = {"assigned": 0, "no_coords": 0, "no_kml": 0, "outside": 0}
    per_zone = {}
    moved = {}          # (old_class, new_class) -> n
    missing_kml = set()
    updates = []

    for L in listings:
        comune = config.norm_comune(L["comune"])
        idx = indexes.get(comune)
        if idx is None:
            counts["no_kml"] += 1
            missing_kml.add(L["comune"])
            continue
        if L["lat"] is None or L["lon"] is None:
            counts["no_coords"] += 1
            continue
        code = idx.locate(L["lat"], L["lon"])
        if code is None:
            counts["outside"] += 1
            continue
        counts["assigned"] += 1
        per_zone[(L["comune"], code)] = per_zone.get((L["comune"], code), 0) + 1
        key = (L["zona_guess"] or "?", fascia_class(code) or "?")
        moved[key] = moved.get(key, 0) + 1
        updates.append((code, L["source"], L["source_id"]))

    if write:
        conn.executemany(
            "UPDATE listings SET zona_poly=? WHERE source=? AND source_id=?",
            updates)
        conn.commit()

    # --- report ---------------------------------------------------------
    print(f"\nZONE ASSIGNMENT (point-in-polygon, {Path(zip_path).name})")
    print(f"  zones loaded: "
          + ", ".join(f"{c}:{len(zl)}" for c, zl in sorted(zones.items())))
    print(f"  assigned {counts['assigned']}   no-coords {counts['no_coords']}"
          f"   no-kml {counts['no_kml']}   in-no-zone {counts['outside']}")
    if missing_kml:
        print(f"  no KML for: {', '.join(sorted(missing_kml))} "
              "(Citerna is Perugia — expected)")

    print("\n  per zone:")
    for (comune, code), n in sorted(per_zone.items()):
        print(f"    {comune:22} {code:4} {n:4}")

    print("\n  old text guess -> polygon class:")
    for (old, new), n in sorted(moved.items(), key=lambda kv: -kv[1]):
        flag = "" if old == new else "   MOVED"
        print(f"    {old:15} -> {new:15} {n:4}{flag}")

    if not write:
        print("\n  --check: nothing written")
    return counts


def main():
    write = "--check" not in sys.argv
    conn = db.connect()
    assign(conn, write=write)


if __name__ == "__main__":
    main()
