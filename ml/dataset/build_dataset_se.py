"""Build the Swedish training table: presences, random background, target-group background.

Reuses build_dataset.py's worker pool -- the JSONL cache, the chunk and item timeouts and
the pool restart on a hung worker are the parts worth not having two copies of -- and binds
it to SourcesSE with its own cache file. Everything below that is Swedish.

FOUR THINGS THAT ARE NOT LIKE FINLAND
-------------------------------------
1. SPATIAL THINNING, NOT SUBSAMPLING. Finland has 250 usable presences spread thin. Sweden
   has 5391, and they are stacked: 5172 distinct 12.5 m cells but only 1741 distinct 1 km
   cells, and the ten busiest 25 km blocks hold well over a quarter of everything. Left
   alone, the model would be fitted to a handful of thoroughly worked hillsides. So records
   sharing a cell are collapsed (a repeat report measures a picker's return visits, not the
   habitat) and the rest are weighted down by how many share their 1 km cell. Nothing is
   discarded: every row still contributes its feature vector, it just cannot contribute its
   neighbourhood more than once. --thin-km 0 turns it off for comparison.

2. THE UNCERTAINTY RULE IS FINLAND'S, UNCHANGED. unc <= 250 m weighs 1.0, 250-1000 m weighs
   0.3 and is averaged over five random draws in the disc, above 1000 m is dropped. No new
   thresholds anywhere, so observation_status_se.py and this file keep saying the same thing
   about the same record.

3. THE 2010 VINTAGE TRAP. Every presence is from 2015 or later; every structural raster is
   from 2010. A stand felled in between is described by the raster as the forest it used to
   be, and the model would learn that forest as matsutake habitat. Points whose cell was
   felled after 2010 and before their own year are dropped -- and dropped from the
   background too. Filtering only the presences would be worse than not filtering at all: it
   would make "not recently felled" a presence signature manufactured by the filter rather
   than found in the data. This is the Swedish analogue of the cycle-matching in
   build_dataset.py.

4. THE TARGET-GROUP BACKGROUND IS RESTRICTED TO ARTPORTALEN. 5428 of the 5501 presences come
   from Artportalen. If the background is drawn from all of GBIF-Sweden -- museum
   collections, iNaturalist, monitoring programmes -- then prec_fungi_at_k stops measuring
   "where do mushroom pickers look" and starts measuring "which institution digitised what",
   and the metric the model is selected on becomes an artefact of data provenance. The
   dataset key is read out of observations.csv rather than hard-coded.

    python ml/dataset/build_dataset_se.py [--coarse] [--thin-km 1.0] [--n-random 10000]
"""
import argparse, csv, json, math, os, random, sys, urllib.parse
from collections import Counter, defaultdict

import numpy as np
import rasterio
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ML, "core"))

from build_dataset import get_json, log, run_all                    # noqa: E402
from features_se import FEATURES_SE, SourcesSE                      # noqa: E402
from grid_se import GridSE, rt90_path                               # noqa: E402

SPECIES = "matsutake_se"
DATA = os.path.join(ML, "data", SPECIES)
RASTERS = os.path.join(ML, "data", "rasters_se")
SLU_DIR = os.path.join(RASTERS, "slu_forest_map")
GBIF_FUNGI_KINGDOM = 5
MATSUTAKE_TAXON = 5241820
VINTAGE = 2010

def _init_se(_vintage):
    """Bind each pool worker to a Swedish Sources handle.

    The handle has to be installed in build_dataset's namespace, not this one: run_all()
    dispatches build_dataset._work, which reads build_dataset._SRC. Setting a module global
    here instead leaves that one None, every _work call raises, and _work's except clause
    turns each into a None result -- so the run completes, reports no errors, and writes an
    empty dataset. It did exactly that once before this comment existed.
    """
    import build_dataset
    build_dataset._SRC = SourcesSE(GridSE(), VINTAGE)


GBIF_SEARCH = "https://api.gbif.org/v1/occurrence/search?"
SHALLOW_MAX = 3000                      # deepest offset worth asking for; see below
LAT_BANDS = [(lo, lo + 1) for lo in range(55, 70)]


def fetch_fungi_background(n, dataset_key, seed):
    """Other fungi reported by the same population that reports the matsutake.

    Two things differ from build_dataset.py's version, and both are forced.

    RESTRICTED TO ARTPORTALEN. 5428 of the 5501 presences come from Artportalen. Drawing the
    background from all of GBIF-Sweden -- museum collections, iNaturalist, monitoring
    programmes -- would make prec_fungi_at_k measure which institution digitised what rather
    than where mushroom pickers actually go, and prec_fungi_at_2 is what `--select sure`
    picks hyper-parameters on. The dataset key is read out of observations.csv, not
    hard-coded.

    STRATIFIED BY LATITUDE, WITH SHALLOW OFFSETS. build_dataset.py draws random offsets up to
    99000. That is fine against Finland's smaller result sets and pathological here: this
    query matches 1.16 million records, and GBIF walks the offset to answer. Measured against
    the live API -- offset 300 returns in 1.7 s, offset 45000 does not return within 120 s.
    The first full run sat in this function for twenty minutes without completing a page.

    So the sample is stratified instead: one shallow window per degree of latitude. That is
    both fast and better than deep random offsets would have been anyway, since a single
    global offset ordering is roughly insertion order, which is a proxy for dataset and date
    rather than for place -- and place is the whole point of a target-group background.
    """
    path = os.path.join(DATA, "background_fungi.csv")
    if os.path.exists(path):
        rows = list(csv.DictReader(open(path)))
        if len(rows) >= n:
            return rows[:n]
    rnd = random.Random(seed)
    base = dict(kingdomKey=GBIF_FUNGI_KINGDOM, country="SE", hasCoordinate="true",
                hasGeospatialIssue="false", coordinateUncertaintyInMeters="0,250",
                month="8,9", year="2010,2026", limit=300)
    if dataset_key:
        base["datasetKey"] = dataset_key

    # Band quotas are PROPORTIONAL to how many records each band actually holds. An equal
    # quota per band would be a different and wrong thing: the background would then describe
    # a Sweden where fungus reporting is uniform with latitude, when in reality it is heavily
    # southern (222k records at 59-60 N against 1.7k at 68-69 N) while the matsutake
    # presences are heavily northern. Latitude alone would separate presence from background
    # almost perfectly, and auc_vs_fungi would be measuring that artefact rather than
    # habitat. Measured on the first build, which did use equal quotas: prec_fungi@2 came out
    # at 0.973, which is not a believable number for this problem.
    counts = {}
    for lo, hi in LAT_BANDS:
        try:
            counts[(lo, hi)] = get_json(GBIF_SEARCH + urllib.parse.urlencode(
                dict(base, decimalLatitude=f"{lo},{hi}", limit=0))).get("count", 0)
        except Exception as e:                                   # noqa: BLE001
            log("band", lo, "count failed:", e)
            counts[(lo, hi)] = 0
    total = sum(counts.values()) or 1
    log(f"{total} background records available across {len(LAT_BANDS)} latitude bands")

    rows, seen = [], set()
    for lo, hi in LAT_BANDS:
        count = counts[(lo, hi)]
        if not count:
            continue
        want = min(count, round(n * count / total))
        if want < 150:                      # below half a page, this band's share is noise
            continue
        cap = min(count, SHALLOW_MAX)
        # Exactly as many pages as the quota asks for. An earlier version floored the quota at
        # 300 and asked for two extra pages on top, which quietly undid the proportionality it
        # was supposed to enforce: the 68-69 N band holds 1740 records and would contribute
        # 900 of them, 52 % of the band, while 59-60 N holds 222000 and would contribute 1799,
        # under 1 %. The background would again have been far more northern than Swedish
        # fungus reporting actually is, in the same direction as the presences.
        pages = max(1, round(want / 300))
        offsets = sorted({rnd.randrange(0, max(cap - 300, 1) + 1, 300) for _ in range(pages)})
        got = 0
        for off in offsets:
            try:
                j = get_json(GBIF_SEARCH + urllib.parse.urlencode(
                    dict(base, decimalLatitude=f"{lo},{hi}", offset=off)))
            except Exception as e:                               # noqa: BLE001
                log("band", lo, "offset", off, "failed:", e)
                continue
            for r in j.get("results", []):
                if r.get("speciesKey") == MATSUTAKE_TAXON or r["gbifID"] in seen:
                    continue
                if r.get("decimalLatitude") is None or r.get("decimalLongitude") is None:
                    continue
                seen.add(r["gbifID"])
                got += 1
                rows.append(dict(id=r["gbifID"], lat=r["decimalLatitude"],
                                 lon=r["decimalLongitude"], year=r.get("year"),
                                 species=r.get("species", "")))
        log(f"fungi background  lat {lo}-{hi}: {count} available, wanted {want}, "
            f"took {got}, total {len(rows)}")

    os.makedirs(DATA, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "lat", "lon", "year", "species"])
        w.writeheader(); w.writerows(rows)
    return rows[:n]


def random_forest_cells(grid, n, seed):
    """Uniform random cells where the SLU 2010 model produced a standing volume.

    Sampled against the RT90 raster through its own transform rather than through a warp:
    the mask is identical at 25 m granularity and this avoids paying for a reprojection to
    answer a yes/no question. It is the same test block_features uses for `valid`.
    """
    rnd = np.random.default_rng(seed)
    to_rt90 = Transformer.from_crs(grid.crs, "EPSG:3021", always_xy=True)
    out = []
    with rasterio.open(rt90_path("vol_total", VINTAGE, SLU_DIR)) as ds:
        nd = ds.nodata
        while len(out) < n:
            rows = rnd.integers(0, grid.height, 4000)
            cols = rnd.integers(0, grid.width, 4000)
            xs, ys = rasterio.transform.xy(grid.transform, rows, cols)
            rx, ry = to_rt90.transform(np.asarray(xs), np.asarray(ys))
            vals = np.array([v[0] for v in ds.sample(zip(rx, ry))], dtype="float64")
            ok = (vals != nd) & (vals >= 0) & (vals < 2000)
            out += [(int(r), int(c)) for r, c in zip(rows[ok], cols[ok])]
            log("random background", len(out))
    return out[:n]


def cut_lookup(points):
    """[(cut_flag, cut_year)] for grid (row, col) pairs, from the felling rasters."""
    flags = [0] * len(points)
    years = [0] * len(points)
    grid = GridSE()
    for name, value in (("cut_declared_12m5.tif", 1), ("cut_fact_12m5.tif", 2)):
        path = os.path.join(RASTERS, name)
        if not os.path.exists(path):
            log("no", name, "-- felling filter will not see it")
            continue
        with rasterio.open(path) as ds:
            xs, ys = zip(*[grid.transform * (c + 0.5, r + 0.5) for r, c in points])
            band1 = [v[0] for v in ds.sample(zip(xs, ys), indexes=[1])]
            band2 = ([v[0] for v in ds.sample(zip(xs, ys), indexes=[2])]
                     if ds.count > 1 else [0] * len(points))
        for i, (b1, b2) in enumerate(zip(band1, band2)):
            if b1:
                flags[i] = max(flags[i], value)
                if value == 2 and b2:
                    years[i] = int(b2) + 2000
    return list(zip(flags, years))


def thin_weights(pts, cell_m):
    """Scale each presence's weight by how many presences share its `cell_m` cell.

    Deterministic, and lossless in the sense that matters: no row is removed, so every
    feature vector still reaches the model. What is removed is a neighbourhood's ability to
    speak more loudly than any other simply because more people walked it.
    """
    if not cell_m:
        return
    groups = defaultdict(list)
    for p in pts:
        if p["group"] == "presence":
            groups[(int(p["x"] // cell_m), int(p["y"] // cell_m))].append(p)
    for members in groups.values():
        for p in members:
            p["weight"] /= len(members)
    log(f"thinned at {cell_m:.0f} m: {len(groups)} distinct cells, "
        f"total presence weight {sum(p['weight'] for p in pts if p['group'] == 'presence'):.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coarse", action="store_true", help="also use 250 m < unc <= 1000 m presences")
    ap.add_argument("--thin-km", type=float, default=1.0, help="inverse-density cell; 0 disables")
    ap.add_argument("--n-random", type=int, default=10000)
    ap.add_argument("--n-fungi", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=os.path.join(DATA, "dataset.csv"))
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    grid = GridSE()
    to_grid = Transformer.from_crs("EPSG:4326", grid.crs, always_xy=True)
    to_wgs = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)

    recs = list(csv.DictReader(open(os.path.join(DATA, "observations.csv"))))
    dataset_key = Counter(r["dataset_key"] for r in recs if r["dataset_key"]).most_common(1)
    dataset_key = dataset_key[0][0] if dataset_key else None
    log("target-group background restricted to dataset", dataset_key)

    pts, by_cell = [], {}
    for r in recs:
        unc = float(r["unc_m"]) if r["unc_m"] not in ("", None) else None
        if unc is None or unc > 1000 or (unc > 250 and not a.coarse):
            continue
        year = int(r["year"]) if r["year"] else None
        x, y = to_grid.transform(float(r["lon"]), float(r["lat"]))
        row, col = grid.xy_to_rowcol(x, y)
        if (row, col) in by_cell:           # same 12.5 m cell: one habitat, not two
            continue
        samples = None
        if unc > 250:
            samples = []
            for _ in range(5):
                t, u = rnd.random() * 2 * math.pi, unc * math.sqrt(rnd.random())
                samples.append(grid.xy_to_rowcol(x + u * math.cos(t), y + u * math.sin(t)))
        p = dict(group="presence", weight=1.0 if unc <= 250 else 0.3, id=r["id"],
                 lat=float(r["lat"]), lon=float(r["lon"]), x=x, y=y, row=row, col=col,
                 year=year, cycle=VINTAGE, unc_m=unc, samples=samples,
                 verification_status=r.get("verification_status", ""))
        by_cell[(row, col)] = p
        pts.append(p)
    log("presences", len(pts), f"(from {len(recs)} records; duplicates on one cell collapsed)")

    for row, col in random_forest_cells(grid, a.n_random, a.seed):
        x, y = grid.transform * (col + 0.5, row + 0.5)
        lon, lat = to_wgs.transform(x, y)
        pts.append(dict(group="bg_random", weight=1.0, id="", lat=lat, lon=lon, x=x, y=y,
                        row=row, col=col, year=None, cycle=VINTAGE, unc_m=None, samples=None,
                        verification_status=""))
    for r in fetch_fungi_background(a.n_fungi, dataset_key, a.seed):
        x, y = to_grid.transform(float(r["lon"]), float(r["lat"]))
        row, col = grid.xy_to_rowcol(x, y)
        if not (0 <= row < grid.height and 0 <= col < grid.width):
            continue
        pts.append(dict(group="bg_fungi", weight=1.0, id=r["id"], lat=float(r["lat"]),
                        lon=float(r["lon"]), x=x, y=y, row=row, col=col,
                        year=int(r["year"]) if r["year"] else None, cycle=VINTAGE,
                        unc_m=None, samples=None, verification_status=""))
    log("total points", len(pts))

    # The felling filter, applied identically to all three groups -- see the module docstring.
    cuts = cut_lookup([(p["row"], p["col"]) for p in pts])
    kept, dropped = [], Counter()
    for p, (flag, cut_year) in zip(pts, cuts):
        p["cut"], p["cut_year"] = flag, cut_year
        if flag == 2 and cut_year and cut_year > VINTAGE and (p["year"] is None or cut_year <= p["year"]):
            dropped[p["group"]] += 1
            continue
        kept.append(p)
    log("felled between the 2010 raster and the record:", dict(dropped), "->", len(kept), "points")
    pts = kept

    thin_weights(pts, a.thin_km * 1000)

    # n_1km lets train.py score recall over distinct neighbourhoods without re-deriving it.
    cell = 1000
    for p in pts:
        p["n_1km"] = f"{int(p['x'] // cell)}_{int(p['y'] // cell)}"

    feats = run_all(pts, a.workers, initializer=_init_se, cache_name="feature_cache_se.jsonl")
    meta = ["group", "weight", "id", "lat", "lon", "x", "y", "row", "col", "year", "cycle",
            "unc_m", "verification_status", "cut", "cut_year", "n_1km"]
    n_ok = Counter()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(meta + FEATURES_SE)
        for p, v in zip(pts, feats):
            if v is None:
                continue
            n_ok[p["group"]] += 1
            w.writerow([p.get(k) if p.get(k) is not None else "" for k in meta]
                       + [f"{x:.5g}" if np.isfinite(x) else "" for x in v])
    log("written", a.out, dict(n_ok), "of", len(pts))


if __name__ == "__main__":
    main()
