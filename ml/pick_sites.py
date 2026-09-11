"""Turn the probability raster into a short list of places worth the drive.

The map alone answers "does this forest look like matsutake forest". A trip needs three more
answers, and all three are exclusions rather than scores, so they are applied as a mask and never
mixed into the model's number:

  may I pick here         nature reserves, national parks, other protected areas and military
                          areas are dropped, with a buffer, because their rules vary and a
                          mushroom is not worth reading a reserve's decision text in the dark
  is anyone living there  cells too close to a building, or with many buildings within a
                          kilometre, are dropped: yards, holiday plots and village edges
  can I get there,        cells further than a walk from a drivable road are dropped, and so are
  is the air clean        cells inside the exhaust and noise corridor of a big road

What survives is clustered into stands, and stands are ranked by how good their *worst* quarter
is rather than by their best cell — a single freak pixel is not worth a 90 km drive, a whole
hillside that scores well is.

  python ml/pick_sites.py --species matsutake --center 61.4978 23.7610 --radius-km 100 \
      --osm ml/data/osm/pirkanmaa.npz --top-pct 0.5 --n 3 --out trip.geojson

A 100 km radius is 156 million cells, so every layer is reduced to a boolean as soon as it is
computed and the float distances are never all held at once.
"""
import argparse, json, math, os, sys, time
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, transform as win_transform
from scipy import ndimage
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
PIX = 16.0
TO3067 = Transformer.from_crs(4326, 3067, always_xy=True)
TO4326 = Transformer.from_crs(3067, 4326, always_xy=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _seed_grid(points, shape, transform, margin):
    """0 where a point falls, 1 elsewhere — the input a distance transform wants. Points further
    than `margin` outside the window are dropped; they cannot affect any cell inside it."""
    x0, y1 = transform * (0, 0)
    seed = np.ones(shape, dtype=np.uint8)
    if not len(points):
        return seed
    x1, y0 = transform * (shape[1], shape[0])
    m = ((points[:, 0] > x0 - margin) & (points[:, 0] < x1 + margin) &
         (points[:, 1] > y0 - margin) & (points[:, 1] < y1 + margin))
    p = points[m]
    if len(p):
        cols = ((p[:, 0] - x0) / PIX).astype(np.int64)
        rows = ((y1 - p[:, 1]) / PIX).astype(np.int64)
        ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
        seed[rows[ok], cols[ok]] = 0
    return seed


def within(points, shape, transform, radius_m):
    """Boolean: is there a point within radius_m of this cell. The float distances are freed
    before returning, which matters at 156 million cells."""
    d = ndimage.distance_transform_edt(_seed_grid(points, shape, transform, radius_m * 2 + 100),
                                       sampling=PIX)
    out = d <= radius_m
    del d
    return out


def count_within(points, shape, transform, radius_m):
    """How many points lie within radius_m of each cell (a box filter over the point count —
    close enough to a disc at this radius and far cheaper)."""
    x0, y1 = transform * (0, 0)
    cnt = np.zeros(shape, dtype=np.float32)
    if len(points):
        cols = ((points[:, 0] - x0) / PIX).astype(np.int64)
        rows = ((y1 - points[:, 1]) / PIX).astype(np.int64)
        ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
        np.add.at(cnt, (rows[ok], cols[ok]), 1.0)
    k = max(1, int(round(2 * radius_m / PIX)))
    ndimage.uniform_filter(cnt, k, mode="constant", output=cnt)
    return cnt * (k * k)


def area_mask(z, shape, transform, kinds=None):
    sh = [(dict(type="Polygon", coordinates=[ring.tolist()]), 1)
          for kind, ring in zip(z["poly_kind"], z["poly_xy"])
          if len(ring) >= 4 and (kinds is None or kind in kinds)]
    if not sh:
        return np.zeros(shape, bool)
    return rasterize(sh, out_shape=shape, transform=transform, dtype="uint8") > 0


SITE_NAMES = {1: "lehto", 2: "lehtomainen kangas", 3: "tuore kangas", 4: "kuivahko kangas",
              5: "kuiva kangas", 6: "karukkokangas", 7: "kalliomaa / hietikko", 8: "lakimetsä"}
MAIN_NAMES = {1: "kivennäismaa", 2: "korpi", 3: "räme", 4: "avosuo"}
THEMES = ["kasvupaikka", "paatyyppi", "ika", "manty", "kuusi", "koivu", "latvuspeitto"]


def describe(stands, lab, objs, ids, xs, ys):
    """What each stand is made of, straight from the source rasters — so the list can be read
    as forest ("old pine on dry heath, sandy, gentle north slope") and not only as a score."""
    sys.path.insert(0, HERE)
    from features import RASTERS, SOIL_GROUPS, class_lookup
    mvmi = os.path.join(RASTERS, "mvmi2023")
    soil_lut = class_lookup("soil")
    handles = {t: rasterio.open(os.path.join(mvmi, f"{t}_vmi1x_1923.tif")) for t in THEMES
               if os.path.exists(os.path.join(mvmi, f"{t}_vmi1x_1923.tif"))}
    soil = rasterio.open(os.path.join(RASTERS, "gtk_soil_16m.tif")) if \
        os.path.exists(os.path.join(RASTERS, "gtk_soil_16m.tif")) else None
    dem = rasterio.open(os.path.join(RASTERS, "dem_16m.tif")) if \
        os.path.exists(os.path.join(RASTERS, "dem_16m.tif")) else None
    # the window read from every source is the stand's own bounding box on the shared 16 m grid
    for st, i in zip(stands, ids):
        sl = objs[i - 1]
        sub = lab[sl] == i
        r0, c0 = sl[0].start, sl[1].start
        # the picked window sits inside the national grid; map back through the coordinate axes.
        # xs/ys are cell centres, so flooring the inverse transform lands on exactly that cell.
        gx0, gy0 = xs[c0], ys[r0]
        for t, ds in handles.items():
            cc, rr = ~ds.transform * (gx0, gy0)
            a_ = ds.read(1, window=Window(int(np.floor(cc)), int(np.floor(rr)), sub.shape[1], sub.shape[0]))
            v = a_[sub].astype(float)
            v = v[(v >= 0) & (v < 3000)]
            if not len(v):
                continue
            st[t] = float(np.median(v))
        if soil is not None:
            cc, rr = ~soil.transform * (gx0, gy0)
            g = soil_lut[soil.read(1, window=Window(int(np.floor(cc)), int(np.floor(rr)), sub.shape[1], sub.shape[0]))][sub]
            g = g[g >= 0]
            if len(g):
                names, counts = np.unique(g, return_counts=True)
                st["soil"] = SOIL_GROUPS[int(names[np.argmax(counts)])]
                st["soil_share"] = round(float(counts.max() / counts.sum()), 2)
        if dem is not None:
            cc, rr = ~dem.transform * (gx0, gy0)
            pad = 2
            z = dem.read(1, window=Window(int(np.floor(cc)) - pad, int(np.floor(rr)) - pad,
                                          sub.shape[1] + 2 * pad, sub.shape[0] + 2 * pad),
                         boundless=True, fill_value=dem.nodata).astype("float32") * 0.1
            z[z < -100] = np.nan
            zf = np.where(np.isfinite(z), z, np.nanmean(z) if np.isfinite(z).any() else 0.0)
            gy, gx = np.gradient(zf, PIX)
            core = (slice(pad, -pad), slice(pad, -pad))
            slope = np.degrees(np.arctan(np.hypot(gx, gy)))[core][sub]
            asp = np.degrees(np.arctan2(-gx, gy))[core][sub] % 360
            st["elev_m"] = round(float(np.nanmedian(zf[core][sub])), 0)
            st["slope_deg"] = round(float(np.median(slope)), 1)
            st["aspect_deg"] = round(float(np.median(asp)), 0)
    for ds in list(handles.values()) + [soil, dem]:
        if ds is not None:
            ds.close()


def describe_line(s):
    bits = []
    if "kasvupaikka" in s:
        bits.append(SITE_NAMES.get(int(s["kasvupaikka"]), "?"))
    if "paatyyppi" in s:
        bits.append(MAIN_NAMES.get(int(s["paatyyppi"]), "?"))
    if "ika" in s:
        bits.append(f"{s['ika']:.0f} v")
    if "manty" in s:
        bits.append(f"mänty {s['manty']:.0f} m³/ha")
    if "kuusi" in s:
        bits.append(f"kuusi {s['kuusi']:.0f}")
    if "latvuspeitto" in s:
        bits.append(f"latvuspeitto {s['latvuspeitto']:.0f} %")
    if "soil" in s:
        bits.append(f"maaperä {s['soil']} ({s['soil_share']*100:.0f} %)")
    if "slope_deg" in s:
        card = ["pohjoiseen", "koilliseen", "itään", "kaakkoon", "etelään", "lounaaseen",
                "länteen", "luoteeseen"][int(((s["aspect_deg"] + 22.5) % 360) // 45)]
        bits.append(f"rinne {s['slope_deg']:.1f}° {card}" if s["slope_deg"] >= 1 else "tasainen")
    return " · ".join(bits)


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
    ap.add_argument("--out", default=None, help="write the picked stands as GeoJSON")
    ap.add_argument("--describe", action="store_true",
                    help="also read what the forest is: site class, pine, age, soil, slope")
    a = ap.parse_args()

    src_path = a.src or os.path.join(HERE, "data", "rasters", f"prob_{a.species}_16m.tif")
    cx, cy = TO3067.transform(a.center[1], a.center[0])
    R = a.radius_km * 1000.0

    with rasterio.open(src_path) as src:
        c0, r0 = ~src.transform * (cx - R, cy + R)
        c1, r1 = ~src.transform * (cx + R, cy - R)
        col0, row0 = max(0, int(c0)), max(0, int(r0))
        w = Window(col0, row0, min(src.width, int(c1)) - col0, min(src.height, int(r1)) - row0)
        tr = win_transform(w, src.transform)
        score = src.read(1, window=w)
        nodata = 255 if src.nodata is None else src.nodata
    shape = score.shape
    log(f"window {shape[1]}x{shape[0]} cells around {a.center[0]:.4f}, {a.center[1]:.4f}")

    # 1-D coordinate axes rather than two full meshes: the same numbers, 12 500 floats instead of
    # 156 million, and every mask below broadcasts against them
    xs = (tr.c + (np.arange(shape[1]) + 0.5) * PIX).astype(np.float64)
    ys = (tr.f - (np.arange(shape[0]) + 0.5) * PIX).astype(np.float64)
    keep = (((ys - cy) ** 2)[:, None] + ((xs - cx) ** 2)[None, :]) <= R * R
    keep &= score != nodata
    n_forest = int(keep.sum())
    log(f"mapped forest inside the radius: {n_forest} cells ({n_forest * 256 / 1e6:.0f} km²)")
    if not n_forest:
        sys.exit("no mapped forest inside the radius")

    # The threshold comes from the forest inside the search radius, not from the whole country:
    # "the best half percent" has to mean the best half percent of what is drivable today.
    forest_scores = np.sort(score[keep])
    thr = float(np.percentile(forest_scores, 100 - a.top_pct))
    log(f"best {a.top_pct} % inside the radius starts at score {thr:.0f}")
    keep &= score >= thr
    log(f"  {int(keep.sum())} cells above it")

    z = np.load(a.osm, allow_pickle=True)
    prot = area_mask(z, shape, tr)
    if a.protected_buffer_m > 0 and prot.any():
        prot = ndimage.distance_transform_edt(~prot, sampling=PIX) <= a.protected_buffer_m
    log(f"protected or military, with a {a.protected_buffer_m:.0f} m buffer: {int(prot.sum())} cells")
    keep &= ~prot
    del prot

    for msg, pts, rad, keep_near in (
            (f"closer than {a.min_building_m:.0f} m to a building", z["buildings"], a.min_building_m, False),
            (f"closer than {a.min_bigroad_m:.0f} m to a big road", z["bigroads"], a.min_bigroad_m, False),
            (f"further than {a.max_walk_m:.0f} m from a drivable road", z["driveroads"], a.max_walk_m, True)):
        near = within(pts, shape, tr, rad)
        keep &= near if keep_near else ~near
        del near
        log(f"after dropping cells {msg}: {int(keep.sum())} cells")

    dense = count_within(z["buildings"], shape, tr, 1000.0) > a.max_buildings_1km
    keep &= ~dense
    del dense
    log(f"after dropping cells with more than {a.max_buildings_1km:.0f} buildings within 1 km: "
        f"{int(keep.sum())} cells ({int(keep.sum()) * 256 / 1e4:.0f} ha)")
    if not keep.any():
        sys.exit("nothing survives the filters; loosen --top-pct or the distances")

    lab, n = ndimage.label(keep, structure=np.ones((3, 3)))
    min_cells = max(1, int(round(a.min_area_ha * 1e4 / (PIX * PIX))))
    sizes = np.bincount(lab.ravel())
    big = [i for i in range(1, n + 1) if sizes[i] >= min_cells]
    log(f"stands: {n}, of them {len(big)} at least {a.min_area_ha} ha")
    if not big:
        sys.exit("no stand is large enough; lower --min-area-ha")

    d_prot = ndimage.distance_transform_edt(~area_mask(z, shape, tr), sampling=PIX)
    stands = []
    objs = ndimage.find_objects(lab)
    for i in big:
        sl = objs[i - 1]
        sub = lab[sl] == i
        s = score[sl][sub].astype(float)
        rr, cc = np.nonzero(sub)
        rr = rr + sl[0].start; cc = cc + sl[1].start
        px, py = float(xs[cc].mean()), float(ys[rr].mean())
        j = int(np.argmax(s))                    # a cell that really is in the stand, not a centroid
        stands.append(dict(cells=int(sub.sum()), area_ha=round(sub.sum() * PIX * PIX / 1e4, 2),
                           q25=float(np.percentile(s, 25)), mean=float(s.mean()), max=float(s.max()),
                           cx=px, cy=py, bx=float(xs[cc[j]]), by=float(ys[rr[j]]),
                           prot_m=float(d_prot[rr, cc].min()),
                           km_from_centre=round(math.hypot(px - cx, py - cy) / 1000, 1)))
    del d_prot

    if a.describe:
        describe(stands, lab, objs, big, xs, ys)

    stands.sort(key=lambda s: (s["q25"], s["cells"]), reverse=True)
    picked = []
    for s in stands:
        if all(math.hypot(s["cx"] - p["cx"], s["cy"] - p["cy"]) > a.separation_km * 1000 for p in picked):
            picked.append(s)
        if len(picked) == a.n:
            break

    out = []
    for i, s in enumerate(picked, 1):
        lon, lat = TO4326.transform(s["cx"], s["cy"])
        blon, blat = TO4326.transform(s["bx"], s["by"])
        pct = 100.0 * (1 - np.searchsorted(forest_scores, s["q25"]) / len(forest_scores))
        s.update(rank=i, lat=lat, lon=lon, best_lat=blat, best_lon=blon, top_pct_of_region=round(float(pct), 3))
        out.append(s)
        print(f"\n#{i}  {lat:.5f}, {lon:.5f}   {s['area_ha']} ha, {s['km_from_centre']} km out")
        print(f"    best cell {blat:.5f}, {blon:.5f}")
        print(f"    score: worst quarter {s['q25']:.0f}, mean {s['mean']:.0f}, best {s['max']:.0f}"
              f"  (the stand sits in the best {pct:.2f} % of the region's forest)")
        print(f"    nearest protected area {s['prot_m']/1000:.1f} km")
        line = describe_line(s)
        if line:
            print(f"    {line}")
        print(f"    https://www.google.com/maps/dir/?api=1&destination={lat:.5f},{lon:.5f}&travelmode=driving")

    if a.out:
        fc = dict(type="FeatureCollection", features=[
            dict(type="Feature", geometry=dict(type="Point", coordinates=[round(s["lon"], 6), round(s["lat"], 6)]),
                 properties={k: v for k, v in s.items() if k not in ("cx", "cy", "bx", "by")})
            for s in out])
        d = os.path.dirname(os.path.abspath(a.out))
        os.makedirs(d, exist_ok=True)
        json.dump(fc, open(a.out, "w"), indent=1)
        log("wrote", a.out)


if __name__ == "__main__":
    main()
