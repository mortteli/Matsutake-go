"""Turn the probability raster into a short list of places worth the drive.

The map alone answers "does this forest look like matsutake forest". A trip needs three more
answers, and all three are exclusions rather than scores, so they are applied as a mask and not
mixed into the model's number:

  may I pick here      nature reserves, national parks, other protected areas and military areas
                       are dropped, with a buffer, because their rules vary and a mushroom is not
                       worth reading a reserve's decision text in the dark
  is anyone living there  cells too close to a building, or with many buildings within a kilometre,
                       are dropped: yards, holiday plots and village edges
  can I get there, is the air clean  cells further than a walk from a drivable road are dropped,
                       and so are cells inside the exhaust and noise corridor of a big road

What survives is clustered into stands, and stands are ranked by how good their *worst* cell is
(the 25th percentile of the stand's scores) rather than by their best one — a single freak pixel
is not worth a 90 km drive, a whole hillside that scores well is.

  python ml/pick_sites.py --species matsutake --center 61.4978 23.7610 --radius-km 100 \
      --osm ml/data/osm/pirkanmaa.npz --top-pct 0.5 --n 3
"""
import argparse, json, math, os, sys, time
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, transform as win_transform
from scipy import ndimage
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

PIX = 16.0
TO3067 = Transformer.from_crs(4326, 3067, always_xy=True)
TO4326 = Transformer.from_crs(3067, 4326, always_xy=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def distance_m(points, shape, transform, maxdist=5000.0):
    """Metres to the nearest of `points` (EPSG:3067), on the window's grid.

    Only points within maxdist of the window are burned in, and the distance transform is
    capped there, so a window far from any road does not cost a full-country pass."""
    x0, y1 = transform * (0, 0)
    x1, y0 = transform * (shape[1], shape[0])
    seed = np.ones(shape, dtype=np.uint8)
    if len(points):
        m = ((points[:, 0] > x0 - maxdist) & (points[:, 0] < x1 + maxdist) &
             (points[:, 1] > y0 - maxdist) & (points[:, 1] < y1 + maxdist))
        p = points[m]
        if len(p):
            cols = ((p[:, 0] - x0) / PIX).astype(np.int64)
            rows = ((y1 - p[:, 1]) / PIX).astype(np.int64)
            ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
            seed[rows[ok], cols[ok]] = 0
    return ndimage.distance_transform_edt(seed, sampling=PIX)


def count_within(points, shape, transform, radius_m):
    """How many of `points` lie within radius_m of each cell (a box filter on the point count —
    close enough to a disc at these radii and far cheaper)."""
    x0, y1 = transform * (0, 0)
    cnt = np.zeros(shape, dtype=np.float32)
    if len(points):
        cols = ((points[:, 0] - x0) / PIX).astype(np.int64)
        rows = ((y1 - points[:, 1]) / PIX).astype(np.int64)
        ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
        np.add.at(cnt, (rows[ok], cols[ok]), 1.0)
    k = max(1, int(round(2 * radius_m / PIX)))
    return ndimage.uniform_filter(cnt, k, mode="constant") * (k * k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--src", default=None, help="probability raster (default ml/data/rasters/prob_<species>_16m.tif)")
    ap.add_argument("--osm", default=os.path.join(HERE, "data", "osm", "pirkanmaa.npz"))
    ap.add_argument("--center", type=float, nargs=2, default=[61.4978, 23.7610], metavar=("LAT", "LON"))
    ap.add_argument("--radius-km", type=float, default=100.0)
    ap.add_argument("--top-pct", type=float, default=0.5,
                    help="keep the best X %% of the forest land inside the search radius")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--min-area-ha", type=float, default=1.0)
    ap.add_argument("--min-building-m", type=float, default=300.0)
    ap.add_argument("--max-buildings-1km", type=float, default=25.0)
    ap.add_argument("--min-bigroad-m", type=float, default=500.0)
    ap.add_argument("--max-walk-m", type=float, default=1500.0)
    ap.add_argument("--protected-buffer-m", type=float, default=150.0)
    ap.add_argument("--separation-km", type=float, default=12.0)
    ap.add_argument("--out", default=None, help="GeoJSON of the picked stands")
    a = ap.parse_args()

    src_path = a.src or os.path.join(HERE, "data", "rasters", f"prob_{a.species}_16m.tif")
    cx, cy = TO3067.transform(a.center[1], a.center[0])
    R = a.radius_km * 1000.0

    with rasterio.open(src_path) as src:
        c0, r0 = ~src.transform * (cx - R, cy + R)
        c1, r1 = ~src.transform * (cx + R, cy - R)
        w = Window(max(0, int(c0)), max(0, int(r0)),
                   min(src.width, int(c1)) - max(0, int(c0)), min(src.height, int(r1)) - max(0, int(r0)))
        tr = win_transform(w, src.transform)
        score = src.read(1, window=w)
        nodata = src.nodata if src.nodata is not None else 255
    shape = score.shape
    log(f"window {shape[1]}x{shape[0]} cells around {a.center}")

    ys, xs = np.mgrid[0:shape[0], 0:shape[1]]
    X = tr.c + (xs + 0.5) * PIX
    Y = tr.f - (ys + 0.5) * PIX
    in_radius = (X - cx) ** 2 + (Y - cy) ** 2 <= R * R
    forest = (score != nodata) & in_radius
    log(f"forest cells in radius: {int(forest.sum())} ({forest.sum()*256/1e6:.0f} km²)")
    if not forest.any():
        sys.exit("no mapped forest inside the radius")

    # The threshold is taken from the forest inside the search radius, not from the whole
    # country: "the best half percent" has to mean the best half percent of what is drivable.
    thr = np.percentile(score[forest], 100 - a.top_pct)
    log(f"score threshold for the best {a.top_pct} % inside the radius: {thr:.0f}")

    z = np.load(a.osm, allow_pickle=True)
    d_build = distance_m(z["buildings"], shape, tr, maxdist=2000)
    n_build = count_within(z["buildings"], shape, tr, 1000.0)
    d_big = distance_m(z["bigroads"], shape, tr, maxdist=3000)
    d_road = distance_m(z["driveroads"], shape, tr, maxdist=4000)
    log("distance layers done")

    shapes = [(dict(type="Polygon", coordinates=[ring.tolist()]), 1)
              for kind, ring in zip(z["poly_kind"], z["poly_xy"]) if len(ring) >= 4]
    prot = (rasterize(shapes, out_shape=shape, transform=tr, dtype="uint8") > 0) if shapes else np.zeros(shape, bool)
    if a.protected_buffer_m > 0 and prot.any():
        prot = ndimage.distance_transform_edt(~prot, sampling=PIX) <= a.protected_buffer_m
    log(f"protected/military cells (with {a.protected_buffer_m:.0f} m buffer): {int(prot.sum())}")

    ok = (forest & (score >= thr) & ~prot
          & (d_build >= a.min_building_m) & (n_build <= a.max_buildings_1km)
          & (d_big >= a.min_bigroad_m) & (d_road <= a.max_walk_m))
    log(f"cells passing every filter: {int(ok.sum())} ({ok.sum()*256/1e4:.0f} ha)")
    if not ok.any():
        sys.exit("nothing survives the filters; loosen --top-pct or the distances")

    lab, n = ndimage.label(ok, structure=np.ones((3, 3)))
    log(f"stands: {n}")
    min_cells = max(1, int(a.min_area_ha * 10000 / (PIX * PIX)))
    stands = []
    for i in range(1, n + 1):
        m = lab == i
        k = int(m.sum())
        if k < min_cells:
            continue
        s = score[m].astype(float)
        px, py = float(X[m].mean()), float(Y[m].mean())
        # report a cell that actually exists in the stand, not the centroid of a banana shape
        j = int(np.argmax(np.where(m, score, -1)))
        bx, by = float(X.flat[j]), float(Y.flat[j])
        stands.append(dict(cells=k, area_ha=round(k * PIX * PIX / 1e4, 2),
                           q25=float(np.percentile(s, 25)), mean=float(s.mean()), max=float(s.max()),
                           cx=px, cy=py, bx=bx, by=by,
                           walk_m=float(d_road[m].min()), build_m=float(d_build[m].min()),
                           big_m=float(d_big[m].min()), prot_m=float("nan"),
                           drive_km=round(math.hypot(px - cx, py - cy) / 1000, 1)))
    log(f"stands of at least {a.min_area_ha} ha: {len(stands)}")
    if not stands:
        sys.exit("no stand is large enough; lower --min-area-ha")

    # distance to the nearest protected area, reported so the pick can be sanity-checked
    d_prot = ndimage.distance_transform_edt(~(rasterize(shapes, out_shape=shape, transform=tr,
                                                        dtype="uint8") > 0), sampling=PIX) if shapes else None
    for s in stands:
        if d_prot is not None:
            r = int((tr.f - s["cy"]) / PIX); c = int((s["cx"] - tr.c) / PIX)
            s["prot_m"] = float(d_prot[min(max(r, 0), shape[0] - 1), min(max(c, 0), shape[1] - 1)])

    stands.sort(key=lambda s: (s["q25"], s["cells"]), reverse=True)
    picked = []
    for s in stands:
        if all(math.hypot(s["cx"] - p["cx"], s["cy"] - p["cy"]) > a.separation_km * 1000 for p in picked):
            picked.append(s)
        if len(picked) == a.n:
            break

    forest_scores = np.sort(score[forest])
    out = []
    for i, s in enumerate(picked, 1):
        lon, lat = TO4326.transform(s["cx"], s["cy"])
        blon, blat = TO4326.transform(s["bx"], s["by"])
        pct_in_region = 100.0 * (1 - np.searchsorted(forest_scores, s["q25"]) / len(forest_scores))
        s.update(rank=i, lat=lat, lon=lon, best_lat=blat, best_lon=blon,
                 top_pct_of_region=round(float(pct_in_region), 3))
        out.append(s)
        print(f"\n#{i}  {lat:.5f}, {lon:.5f}   {s['area_ha']} ha, {s['drive_km']} km from centre")
        print(f"    score q25 {s['q25']:.0f} / mean {s['mean']:.0f} / max {s['max']:.0f}"
              f"  = best {pct_in_region:.2f} % of the region's forest")
        print(f"    nearest road {s['walk_m']:.0f} m, nearest building {s['build_m']:.0f} m, "
              f"big road {s['big_m']:.0f} m, protected area {s['prot_m']:.0f} m")
        print(f"    https://www.google.com/maps/dir/?api=1&destination={lat:.5f},{lon:.5f}&travelmode=driving")

    if a.out:
        fc = dict(type="FeatureCollection", features=[
            dict(type="Feature", geometry=dict(type="Point", coordinates=[s["lon"], s["lat"]]),
                 properties={k: v for k, v in s.items() if k not in ("cx", "cy", "bx", "by")})
            for s in out])
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(fc, open(a.out, "w"), indent=1)
        log("wrote", a.out)


if __name__ == "__main__":
    main()
