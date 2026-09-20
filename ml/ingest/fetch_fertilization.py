"""Does forest fertilisation land where the matsutake map looks?

The hypothesis this script was written to test: fertilised forest should score lower for
matsutake, because the fungus lives on poor, dry podzol and an ectomycorrhizal partner is
worth least to a pine that is handed its nitrogen for free. The ecology is sound enough to
be worth a layer -- *if* fertilisation can be located at all.

Only one kind of fertilisation can. Terveyslannoitus (ash on drained peatland, boron on
deficient stands) is state-aided under Kemera and its successor Metka, and every aided site
leaves two geometries in Metsakeskus's open WFS: the application and, once the work is done,
the completion declaration. Kasvatuslannoitus -- the nitrogen dose on mineral soil, some
50 000 ha a year, the one that would actually touch a pine heath -- needs no permit, no
notification and gets no subsidy, so it appears in no public register at all. See
docs/LANNOITUS_matsutake.md.

So this measures the half that can be measured: take every completed health fertilisation,
read the published matsutake score under it, and ask how much of the map it could ever
repaint. Completion declarations, not applications: an application is an intention, the same
distinction fetch_harvests.py draws between metsankayttoilmoitus and the stand register.

    python ml/ingest/fetch_fertilization.py                 # fetch + measure
    python ml/ingest/fetch_fertilization.py --points out.json --skip-fetch

Output is a report on stdout. Nothing is written into data/: the answer this produced was
"no layer", and the numbers behind that belong in the doc, not in the app.
"""
import argparse, bisect, json, os, sys, time, urllib.request

import numpy as np
import rasterio

WFS = "https://avoin.metsakeskus.fi/rajapinnat/v1/ows"
# Metsakeskus splits the aid registers by act and work type: 11 = Kemera (34/2015),
# 13 = Metka (71/2023), 50 = terveyslannoitus. Kemera stopped taking applications at the end
# of 2023 but its sites stay in the register, so both acts are needed for a full history.
LAYERS = ["completiondeclaration_stand_13_50", "completiondeclaration_stand_11_50"]
PAGE = 2000
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
META = os.path.join(ROOT, "data", "matsutake", "prob_meta.json")
OBS = os.path.join(ROOT, "data", "matsutake", "observations.json")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def centroid(ring):
    """Shoelace centroid of one ring. A stand averages under 2 ha -- some 75 cells of the
    16 m grid -- so its centre is a fair stand-in for the whole polygon, and it keeps this
    from being a rasterising job for 80 000 polygons."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        f = x0 * y1 - x1 * y0
        a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
    if a == 0:                                   # degenerate ring: fall back to the mean vertex
        n = len(ring)
        return sum(p[0] for p in ring) / n, sum(p[1] for p in ring) / n
    a *= 0.5
    return cx / (6 * a), cy / (6 * a)


def fetch(layer):
    rows, start = [], 0
    while True:
        url = (f"{WFS}?service=WFS&version=2.0.0&request=GetFeature&typeNames=v1:{layer}"
               f"&outputFormat=application/json&srsName=EPSG:3067"
               f"&count={PAGE}&startIndex={start}")
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=180) as r:
                    page = json.loads(r.read())
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        feats = page.get("features", [])
        for f in feats:
            g, p = f.get("geometry"), f["properties"]
            if not g:
                continue
            ring = (g["coordinates"] if g["type"] == "Polygon" else g["coordinates"][0])[0]
            x, y = centroid(ring)
            rows.append(dict(x=round(x, 1), y=round(y, 1), area=p.get("AREA"),
                             year=(p.get("ARRIVALDATE") or "")[:4], layer=layer))
        start += PAGE
        log(f"  {layer}: {len(rows)} stands")
        if len(feats) < PAGE:
            return rows


def threshold(q, pct):
    """Score at which the map draws "the best pct % of forest" -- the same interpolation
    js/problayer.js does on the quantiles stored with the model."""
    pos = min(len(q) - 1, max(0.0, (1 - pct / 100) * (len(q) - 1)))
    i = int(pos); f = pos - i
    return q[i] + (q[min(i + 1, len(q) - 1)] - q[i]) * f


def sample(meta, xs, ys):
    """Published score under each point; -1 outside every tile, 255 outside the model mask."""
    vals = np.full(len(xs), -1, np.int16)
    for f in meta["files"]:
        with rasterio.open(os.path.join(ROOT, f["url"])) as src:
            b = src.bounds
            sel = np.where((vals < 0) & (xs >= b.left) & (xs < b.right)
                           & (ys > b.bottom) & (ys <= b.top))[0]
            if not len(sel):
                continue
            vals[sel] = np.array(list(src.sample(zip(xs[sel], ys[sel]), indexes=1)),
                                 np.int16).ravel()
    return vals


def top_area_ha(meta, pcts):
    """How much forest the map actually paints at each slider stop, read off the rasters
    rather than assumed from the percentage: the quantiles are over model forest cells, and
    the published tiles are what the app really draws."""
    tot = {p: 0 for p in pcts}
    thr = {p: threshold(meta["quantiles"], p) for p in pcts}
    for f in meta["files"]:
        with rasterio.open(os.path.join(ROOT, f["url"])) as src:
            for _, w in src.block_windows(1):
                a = src.read(1, window=w)
                ok = a != meta["nodata"]
                for p in pcts:
                    tot[p] += int((ok & (a >= thr[p])).sum())
    px_ha = (meta["pixel_m"] ** 2) / 1e4
    return {p: n * px_ha for p, n in tot.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default=os.path.join(ROOT, "ml", "data", "fertilization.json"),
                    help="where the fetched stand centroids are cached")
    ap.add_argument("--skip-fetch", action="store_true", help="reuse the cached points")
    ap.add_argument("--pcts", type=float, nargs="*", default=[0.25, 0.5, 1, 2, 5, 10, 15])
    a = ap.parse_args()

    if a.skip_fetch and os.path.exists(a.points):
        pts = json.load(open(a.points))
        log(f"cached: {len(pts)} stands")
    else:
        pts = []
        for layer in LAYERS:
            pts += fetch(layer)
        os.makedirs(os.path.dirname(a.points), exist_ok=True)
        json.dump(pts, open(a.points, "w"))
        log(f"wrote {len(pts)} stands -> {a.points}")

    meta = json.load(open(META))
    q = meta["quantiles"]
    xs = np.array([p["x"] for p in pts]); ys = np.array([p["y"] for p in pts])
    ha = np.array([p["area"] or 0.0 for p in pts])
    vals = sample(meta, xs, ys)

    forest = vals != meta["nodata"]
    print(f"completed health fertilisations: {len(pts)} stands, {ha.sum():,.0f} ha, "
          f"{min(p['year'] for p in pts if p['year'])}-{max(p['year'] for p in pts if p['year'])}")
    print(f"  on model forest: {forest.sum()} ({forest.mean() * 100:.1f} %)")
    print(f"  scoring below the published floor (outside the best {meta['max_pct']} %): "
          f"{(vals == 0).sum()} ({(vals == 0).mean() * 100:.1f} %)")
    tops = top_area_ha(meta, [p for p in a.pcts])
    for pct in a.pcts:
        t = threshold(q, pct)
        m = forest & (vals >= t)
        exp = pct / 100 * len(pts)               # what chance alone would put there
        print(f"  best {pct:>5} % (score >= {t:5.1f}): {m.sum():5d} stands, {ha[m].sum():8.0f} ha"
              f"  = {ha[m].sum() / tops[pct] * 100:7.4f} % of that slice"
              f"  ({m.sum() / max(exp, 1e-9):.3f} x chance)")

    if os.path.exists(OBS):
        from pyproj import Transformer
        obs = json.load(open(OBS))
        tr = Transformer.from_crs(4326, 3067, always_xy=True)
        ox, oy = tr.transform([o["lon"] for o in obs], [o["lat"] for o in obs])
        ox = np.asarray(ox); oy = np.asarray(oy)
        d = np.array([np.sqrt(np.min((xs - x) ** 2 + (ys - y) ** 2)) for x, y in zip(ox, oy)])
        print(f"\nknown matsutake finds: {len(d)}")
        for lim in (200, 500, 1000, 2000, 5000):
            print(f"  within {lim:5d} m of a fertilised stand: {int((d < lim).sum()):4d} "
                  f"({(d < lim).mean() * 100:.1f} %)")
        print(f"  median distance: {np.median(d) / 1000:.1f} km")


if __name__ == "__main__":
    main()
