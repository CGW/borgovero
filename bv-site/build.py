"""The one build. Everything the site publishes comes out of this script,
or it is not published.

    python3 build.py --db ../phase0/phase0.sqlite --out dist-site

What it does, in order:
  1. contradictions_site  -> findings, method, about     (subprocess)
  2. index_site           -> listings, comune reports    (subprocess)
  3. phase1_site          -> llms.txt, /dati/, correzioni, replica, guide
  4. merge into one tree; ONE sitemap.xml, ONE robots.txt
  5. lint the merged tree — a failure kills the build
  6. do all of it TWICE and diff — §10.2 is enforced here, not in CI

WHY THE DETERMINISM CHECK LIVES HERE AND NOT IN GITHUB ACTIONS. The
database is gitignored (it is a scraped corpus; the repo carries the code
and the human-measured files only), so a CI runner has nothing to build
from. A CI job that skipped the actual build would be a green light wired
to nothing — worse than absent, because it would be trusted. So the
contract is enforced where the data is: every local build builds twice.
If the corpus ever moves into an artifact store, lift this into CI then.

The subprocess boundary for steps 1–2 is deliberate: both generators are
also standalone scripts with their own CLIs, and importing them here
would let this script's state leak into theirs. A subprocess gets the
same isolation a fresh terminal run gets, which is exactly what their
own byte-identical guarantees were measured under.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "phase0"))


def run_generator(script, db, out):
    r = subprocess.run([sys.executable, os.path.join(HERE, script),
                        "--db", db, "--out", out],
                       capture_output=True, text=True, cwd=HERE)
    if r.returncode != 0:
        sys.exit(f"{script} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def locs(sitemap_path):
    if not os.path.exists(sitemap_path):
        return []
    txt = open(sitemap_path, encoding="utf-8").read()
    return re.findall(r"<loc>(.*?)</loc>", txt)


def merge_tree(src, dst):
    """Copy src over dst, refusing to overwrite — a path collision means
    two generators think they own the same page, which is a bug to fix,
    not a race to win silently."""
    for root, _, files in os.walk(src):
        for fn in files:
            s = os.path.join(root, fn)
            rel = os.path.relpath(s, src)
            d = os.path.join(dst, rel)
            if os.path.exists(d):
                sys.exit(f"BUILD COLLISION: two generators produced {rel}")
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)


# The one production origin. It is a DEFAULT, not a flag to remember:
# S008 shipped a build whose sitemap carried path-only <loc> entries and
# whose robots.txt said "Sitemap: /sitemap.xml", because the documented
# deploy command omitted --base-url and the empty default looked like a
# successful build. Search Console rejects path-only <loc>, so that tree
# would have turned a green sitemap report red on deploy. A required
# argument that is silently optional is not a safeguard.
PROD_ORIGIN = "https://casazebra.it"


def build_once(db, out, base_url=""):
    """One complete site into `out`. Returns the merged URL list.

    `base_url` (e.g. https://casazebra.it, no trailing slash)
    makes sitemap.xml and robots.txt use absolute URLs — the sitemap
    protocol requires them, and Search Console rejects path-only <loc>
    entries. Empty keeps paths, which is fine for a local preview and
    wrong for a deploy."""
    import json
    import sqlite3

    import contradictions as C
    import contradictions_site as CS
    import normalize as N
    import phase1_site as P1

    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = os.path.join(tmp, "a"), os.path.join(tmp, "b")
        out_contr = run_generator("contradictions_site.py", db, a_dir)
        out_index = run_generator("index_site.py", db, b_dir)

        # Steps 1-2 own their trees; the contradictions build also wrote
        # robots.txt and the root redirect, which are site-wide files that
        # belong to the merge, not to one generator. Take them, then merge.
        os.makedirs(out, exist_ok=True)
        merge_tree(a_dir, out)
        # index_site writes no root files by design — see its build().
        merge_tree(b_dir, out)

        urls = locs(os.path.join(out, "sitemap.xml"))
        urls += locs(os.path.join(out, "sitemap-immobili.xml"))
        os.unlink(os.path.join(out, "sitemap-immobili.xml"))

        # The front door. The contradictions build points the root at
        # /it/confronti/ — right when those 36 pages were the whole site,
        # wrong now: a visitor landing on the findings index concludes
        # the site has 36 properties (it happened on launch day). The
        # index is the product; the root lands on the comuni overview,
        # which links the evidence one click away.
        for lang in ("it", "en"):
            with open(os.path.join(out, lang, "index.html"), "w",
                      encoding="utf-8") as f:
                f.write('<!doctype html><meta charset="utf-8">'
                        f'<meta http-equiv="refresh" content="0;url=/{lang}/comuni/">'
                        f'<link rel="canonical" href="/{lang}/comuni/">')
        with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
            f.write('<!doctype html><meta charset="utf-8">'
                    '<meta http-equiv="refresh" content="0;url=/it/comuni/">'
                    '<link rel="canonical" href="/it/comuni/">')

    # Step 3: Phase 1 pages, computed from the same pipeline the page
    # generators used. Nothing here recomputes an index figure.
    rows, bands, _ = N.run(db_path=db,
                           out_dir=os.path.dirname(os.path.abspath(db)))
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    data_date = max(r[0] or "" for r in
                    conn.execute("SELECT fetched_at FROM listings"))
    fetched = {(r["source"], str(r["source_id"])): r["fetched_at"]
               for r in conn.execute(
                   "SELECT source, source_id, fetched_at FROM listings")}
    items = C.build(conn)
    conn.close()

    # Per-URL lastmod for the sitemap: a listing page's date is its own
    # retrieval date; everything else carries the corpus date. From the
    # database, not the clock — a lastmod that changed on every rebuild
    # would claim 1,600 fresh pages weekly and teach Google to ignore
    # exactly the field this exists for (§10.2 applies to sitemaps too).
    import index_site as IS
    lastmod = {}
    for r in rows:
        d = (fetched.get((r["source"], str(r["source_id"]))) or data_date)
        for lang in ("it", "en"):
            lastmod[IS.listing_url(r, lang)] = str(d)[:10]

    keep = [it for it in items
            if it.get("verified") or (set(it["evidence"]) & CS.IDENTITY)]
    findings_export = []
    for it in keep:
        sid = CS.slug(it)
        findings_export.append({
            "id": sid,
            "url": f"/it/confronti/{sid}.html",
            "comune": CS.comune_of(it["group"]),
            "label": C.best_label(it["group"]),
            "verified": bool(it.get("verified")),
            "evidence": sorted(it["evidence"]),
            "disagreements": {k: list(v) if isinstance(v, tuple) else v
                              for k, v in it["d"].items()},
            "members": sorted(
                [{"source": g["source"], "source_id": str(g["source_id"]),
                  "agency": g["agency_name"] or g["source"],
                  "url": g["url"]} for g in it["group"]],
                key=lambda m: (m["source"], m["source_id"])),
        })
    findings_export.sort(key=lambda f: f["id"])

    urls += P1.build(out, rows, bands, len(keep), findings_export, data_date)

    # Step 4: one sitemap over everything, sorted, no duplicates.
    urls = sorted(set(urls))
    default_mod = str(data_date)[:10]
    with open(os.path.join(out, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "".join(f"  <url><loc>{base_url}{u}</loc>"
                          f"<lastmod>{lastmod.get(u, default_mod)}</lastmod>"
                          f"</url>\n"
                          for u in urls)
                + "</urlset>\n")
    with open(os.path.join(out, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("User-agent: *\nAllow: /\n"
                f"Sitemap: {base_url}/sitemap.xml\n")

    print(out_contr.strip().splitlines()[-1])
    print(out_index.strip().splitlines()[-1])
    return urls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="../phase0/phase0.sqlite")
    ap.add_argument("--out", default="dist-site")
    ap.add_argument("--base-url", default=PROD_ORIGIN,
                    help=f"absolute site origin for sitemap/robots "
                         f"(default {PROD_ORIGIN}). Pass --base-url '' "
                         f"ONLY for a local preview that will never be "
                         f"deployed.")
    a = ap.parse_args()
    db = os.path.abspath(a.db)
    base = a.base_url.rstrip("/")
    if not base:
        print("base-url empty: sitemap and robots will carry PATHS, not "
              "URLs. Preview only — do not deploy this tree.")

    # §10.2: build twice into scratch, diff, and only then install.
    with tempfile.TemporaryDirectory() as tmp:
        one, two = os.path.join(tmp, "one"), os.path.join(tmp, "two")
        build_once(db, one, base)
        build_once(db, two, base)
        r = subprocess.run(["diff", "-rq", one, two],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("NON-DETERMINISTIC BUILD — §10.2 violated:\n" + r.stdout)
        print("determinism: two builds byte-identical")

        lint = subprocess.run([sys.executable,
                               os.path.join(HERE, "lint.py"), one],
                              capture_output=True, text=True)
        print(lint.stdout.strip())
        if lint.returncode != 0:
            sys.exit("lint failed — nothing installed")

        # Third gate: the sitemap must be deployable. <loc> has to be a
        # fully-qualified URL — Search Console rejects path-only entries,
        # and a rejected sitemap is invisible until someone opens GSC
        # days later. Skipped only for an explicitly-empty base, which
        # already announced itself as preview-only above.
        if base:
            bad = [u for u in locs(os.path.join(one, "sitemap.xml"))
                   if not u.startswith("http")]
            if bad:
                sys.exit(f"sitemap has {len(bad)} path-only <loc> entries "
                         f"(e.g. {bad[0]}) — nothing installed")
            print(f"sitemap: {len(locs(os.path.join(one, 'sitemap.xml')))} "
                  f"absolute URLs under {base}")

        # Install: tree into place only after both gates pass. rmtree can
        # fail on the sandbox mount (host-created files refuse unlink);
        # fall back to overwrite-in-place, which the byte-identical
        # guarantee makes safe for changed files, and report anything
        # stale that survives.
        if os.path.isdir(a.out):
            try:
                shutil.rmtree(a.out)
            except OSError:
                pass
        wanted = set()
        for root, _, files in os.walk(one):
            for fn in files:
                rel = os.path.relpath(os.path.join(root, fn), one)
                wanted.add(rel)
                d = os.path.join(a.out, rel)
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(os.path.join(root, fn), d)
        stale = []
        for root, _, files in os.walk(a.out):
            for fn in files:
                rel = os.path.relpath(os.path.join(root, fn), a.out)
                # Deploy machinery living in the output dir is not stale
                # site content: .vercel/ is the CLI's project link, and
                # deleting it silently unlinks the project so the next
                # deploy creates a duplicate.
                if rel.split(os.sep)[0].startswith("."):
                    continue
                if rel not in wanted:
                    try:
                        os.unlink(os.path.join(root, fn))
                    except OSError:
                        stale.append(rel)
        if stale:
            print(f"  !! {len(stale)} stale file(s) could not be removed:")
            for s in stale[:10]:
                print(f"       {s}")

    n = sum(len(fs) for _, _, fs in os.walk(a.out))
    print(f"installed: {n} files -> {a.out}/")


if __name__ == "__main__":
    main()
