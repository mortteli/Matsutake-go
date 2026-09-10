"""Build the training table for one species.

Rows
  presence   observations with coordinate uncertainty <= 250 m (weight 1); with --coarse also
             250 m < unc <= 1000 m (weight 0.3, features averaged over 5 points in the circle)
  bg_random  uniform random cells on forestry land (MVMI has data)
  bg_fungi   "target-group" background: other fungi observed Aug–Sep 2010+ with <= 250 m accuracy
             (where mushroom pickers actually look), fetched from GBIF and cached

Each presence is sampled from the MVMI cycle matching its year; background from 2023.
Output: ml/data/matsutake/dataset.csv
"""
import argparse, csv, json, math, os, random, sys, time, urllib.parse, urllib.request
import multiprocessing as mp
import numpy as np
import rasterio
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from grid import Grid, cycle_for_year, env
from features import Sources, FEATURES, RASTERS

DATA = os.path.join(HERE, "data", "matsutake")
GBIF_FUNGI_KINGDOM = 5


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def get_json(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            log("retry", i, e); time.sleep(4 * (i + 1))
    raise RuntimeError(url[:120])


def fetch_fungi_background(n, exclude_taxon, seed):
    """Random pages of other-fungi records; GBIF search offsets are limited to 100 000."""
    path = os.path.join(DATA, "background_fungi.csv")
    if os.path.exists(path):
        rows = list(csv.DictReader(open(path)))
        if len(rows) >= n:
            return rows[:n]
    rnd = random.Random(seed)
    base = dict(kingdomKey=GBIF_FUNGI_KINGDOM, country="FI", hasCoordinate="true", hasGeospatialIssue="false",
                coordinateUncertaintyInMeters="0,250", month="8,9", year="2010,2026", limit=300)
    rows, seen = [], set()
    while len(rows) < n:
        q = dict(base, offset=rnd.randrange(0, 99000, 300))
        j = get_json("https://api.gbif.org/v1/occurrence/search?" + urllib.parse.urlencode(q))
        for r in j["results"]:
            if r.get("speciesKey") == exclude_taxon or r["gbifID"] in seen:
                continue
            seen.add(r["gbifID"])
            rows.append(dict(id=r["gbifID"], lat=r["decimalLatitude"], lon=r["decimalLongitude"],
                             year=r.get("year"), species=r.get("species", "")))
        log("fungi background", len(rows))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "lat", "lon", "year", "species"]); w.writeheader(); w.writerows(rows)
    return rows[:n]


def random_forest_cells(grid, n, seed):
    """Uniform random cells where the 2023 site-class raster has forestry-land data."""
    rnd = np.random.default_rng(seed)
    path = os.path.join(RASTERS, "mvmi2023", "kasvupaikka_vmi1x_1923.tif")
    out = []
    with rasterio.open(path) as ds:
        nd = ds.nodata
        while len(out) < n:
            rows = rnd.integers(0, grid.height, 2000); cols = rnd.integers(0, grid.width, 2000)
            xs, ys = rasterio.transform.xy(grid.transform, rows, cols)
            vals = np.array([v[0] for v in ds.sample(zip(xs, ys))])
            ok = (vals != nd) & (vals >= 1) & (vals <= 8)
            out += [(int(r), int(c)) for r, c in zip(rows[ok], cols[ok])]
            log("random background", len(out))
    return out[:n]


_SRC = None
def _init(cycle):
    global _SRC
    _SRC = Sources(Grid(), cycle)


def _work(item):
    row, col, samples = item
    vecs = []
    for r, c in samples or [(row, col)]:
        try:
            v, ok = _SRC.point_features(r, c)
        except Exception as e:
            return None
        if ok:
            vecs.append(v)
    if not vecs:
        return None
    return np.nanmean(np.stack(vecs), axis=0)


def _key(p):
    return f"{p['cycle']}:{p['row']}:{p['col']}:{p['samples'] or ''}"


def run_all(pts, workers, chunk=100, chunk_timeout=900, item_timeout=180):
    """Feature vectors for all points, cycle by cycle, with a JSONL cache so a restart resumes,
    and chunk/item timeouts so a hung or crashed worker cannot stall the pool forever."""
    cache_path = os.path.join(HERE, "data", "raw", "feature_cache.jsonl")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                d = json.loads(line); cache[d["k"]] = d["v"]
            except ValueError:
                pass
    log("cache entries", len(cache))
    ctx = mp.get_context("fork")
    out = [None] * len(pts)
    with open(cache_path, "a") as cf:
        for cycle in sorted(set(p["cycle"] for p in pts)):
            idx = [i for i, p in enumerate(pts) if p["cycle"] == cycle]
            todo = [i for i in idx if _key(pts[i]) not in cache]
            for i in idx:
                if _key(pts[i]) in cache:
                    out[i] = cache[_key(pts[i])]
            log("cycle", cycle, "points", len(idx), "to compute", len(todo))
            if not todo:
                continue
            nw = workers if cycle == 2023 else min(workers, 4)
            pool = ctx.Pool(nw, initializer=_init, initargs=(cycle,))
            done_n = 0
            try:
                for c0 in range(0, len(todo), chunk):
                    ids = todo[c0:c0 + chunk]
                    args = [(pts[i]["row"], pts[i]["col"], pts[i]["samples"]) for i in ids]
                    try:
                        res = pool.map_async(_work, args, chunksize=4).get(timeout=chunk_timeout)
                    except mp.TimeoutError:
                        log("chunk timed out — restarting pool and retrying items one by one")
                        pool.terminate(); pool.join()
                        pool = ctx.Pool(nw, initializer=_init, initargs=(cycle,))
                        res = []
                        for arg in args:
                            try:
                                res.append(pool.apply_async(_work, (arg,)).get(timeout=item_timeout))
                            except mp.TimeoutError:
                                log("item timed out", arg[:2]); res.append(None)
                                pool.terminate(); pool.join()
                                pool = ctx.Pool(nw, initializer=_init, initargs=(cycle,))
                    for i, v in zip(ids, res):
                        vv = None if v is None else [float(x) for x in v]
                        out[i] = vv; cache[_key(pts[i])] = vv
                        cf.write(json.dumps({"k": _key(pts[i]), "v": vv}) + "\n")
                    cf.flush()
                    done_n += len(ids)
                    log("  done", done_n, "of", len(todo))
            finally:
                pool.terminate(); pool.join()
    return [None if v is None else np.array(v, dtype=np.float32) for v in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coarse", action="store_true", help="also use 250 m < unc <= 1000 m presences")
    ap.add_argument("--n-random", type=int, default=3000)
    ap.add_argument("--n-fungi", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(DATA, "dataset.csv"))
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    grid = Grid()
    to_grid = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)

    pts = []
    for r in csv.DictReader(open(os.path.join(DATA, "observations.csv"))):
        unc = float(r["unc_m"]) if r["unc_m"] not in ("", None) else None
        if unc is None or unc > 1000 or (unc > 250 and not a.coarse):
            continue
        year = int(r["year"]) if r["year"] else None
        x, y = to_grid.transform(float(r["lon"]), float(r["lat"]))
        row, col = grid.xy_to_rowcol(x, y)
        samples = None
        if unc > 250:                                   # average over the uncertainty disc
            samples = []
            for _ in range(5):
                t, u = rnd.random() * 2 * math.pi, unc * math.sqrt(rnd.random())
                samples.append(grid.xy_to_rowcol(x + u * math.cos(t), y + u * math.sin(t)))
        pts.append(dict(group="presence", weight=1.0 if unc <= 250 else 0.3, lat=float(r["lat"]), lon=float(r["lon"]),
                        x=x, y=y, row=row, col=col, year=year, cycle=cycle_for_year(year), unc_m=unc,
                        samples=samples, id=r["id"]))
    log("presences", len(pts))
    for row, col in random_forest_cells(grid, a.n_random, a.seed):
        x, y = grid.transform * (col + 0.5, row + 0.5)
        lon, lat = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True).transform(x, y)
        pts.append(dict(group="bg_random", weight=1.0, lat=lat, lon=lon, x=x, y=y, row=row, col=col,
                        year=None, cycle=2023, unc_m=None, samples=None, id=""))
    for r in fetch_fungi_background(a.n_fungi, 5241820, a.seed):
        x, y = to_grid.transform(float(r["lon"]), float(r["lat"]))
        row, col = grid.xy_to_rowcol(x, y)
        pts.append(dict(group="bg_fungi", weight=1.0, lat=float(r["lat"]), lon=float(r["lon"]), x=x, y=y, row=row, col=col,
                        year=int(r["year"]) if r["year"] else None, cycle=2023, unc_m=None, samples=None, id=r["id"]))
    log("total points", len(pts))

    feats = run_all(pts, a.workers)
    meta = ["group", "weight", "id", "lat", "lon", "x", "y", "row", "col", "year", "cycle", "unc_m"]
    n_ok = 0
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(meta + FEATURES)
        for p, v in zip(pts, feats):
            if v is None:
                continue
            n_ok += 1
            w.writerow([p[k] if p[k] is not None else "" for k in meta] + [f"{x:.5g}" if np.isfinite(x) else "" for x in v])
    log("written", a.out, "rows", n_ok, "of", len(pts))


if __name__ == "__main__":
    main()
