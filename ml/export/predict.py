"""Full-Finland inference: stream every feature source block by block over the MVMI 16 m grid,
run whichever fold ensemble the trained model's head names (MLP, LightGBM or the average of the
two), and write a tiled GeoTIFF with overviews (COG-style):
  value 0..100 = probability × 100, 255 = no forestry-land data.

python ml/export/predict.py --species matsutake [--block 2048] [--out ml/data/rasters/prob_matsutake_16m.tif]
                     [--bbox 227000 6722000 427000 6922000]   # one region only, EPSG:3067
Restartable: finished blocks are recorded in <out>.progress.
"""
import argparse, json, os, sys, time
import multiprocessing as mp
import numpy as np, rasterio, torch
from rasterio.enums import Resampling
from rasterio.windows import Window

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ML, "core"))
sys.path.insert(0, os.path.join(ML, "train"))
from grid import Grid, env
from features import Sources, FEATURES, RASTERS

# One predict.py for both countries; see ml/core/registry.py. The Finnish names above stay
# as the module-level default so nothing that imports them changes, and the Swedish ones are
# bound per worker from the model's own config.
from registry import features as _features_for, grid_class, sources_class
import grid_se as _grid_se
from train import MLP, Prep


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_model(species):
    """Returns the config, the preprocessor, the fold models of whichever families the trained
    head uses, and the indices that pick the model's features out of the full feature stack."""
    mdir = os.path.join(ML, "models", species)
    cfg = json.load(open(os.path.join(mdir, "model.json")))
    prep = Prep(cfg["features"])
    p = cfg["prep"]
    prep.median, prep.mean, prep.std = (np.array(p[k], dtype=np.float32) for k in ("median", "mean", "std"))
    head = cfg.get("head", "mlp")
    mlps, gbms = [], []
    if "mlp" in head:
        for f in range(cfg["n_members"]):
            m = MLP(cfg["mlp"]["n_in"], cfg["mlp"]["hidden"], cfg["mlp"]["depth"], cfg["mlp"]["dropout"])
            m.load_state_dict(torch.load(os.path.join(mdir, f"mlp_fold{f}.pt"), map_location="cpu")); m.eval()
            mlps.append(m)
    if "lgbm" in head:
        import lightgbm as lgb
        gbms = [lgb.Booster(model_file=os.path.join(mdir, f"lgbm_fold{f}.txt")) for f in range(cfg["n_members"])]
    # The model records the feature list it was trained on, so the country follows from the
    # model rather than from a flag that could disagree with it.
    country = cfg.get("country", "fi")
    idx = [_features_for(country).index(c) for c in cfg["features"]]
    return cfg, prep, (head, mlps, gbms), idx


_W = {}


def _init(species, cycle):
    """One Sources handle and one model copy per worker process."""
    import torch as _t
    _t.set_num_threads(1)
    cfg, prep, members, idx = load_model(species)
    country = cfg.get("country", "fi")
    g = grid_class(country)()
    _W.update(grid=g, cfg=cfg, prep=prep, members=members, idx=idx)
    _W["src"] = sources_class(country)(g, cycle)


def _block(args):
    row_off, col_off, height, width = args
    w = Window(col_off, row_off, width, height)
    feats, valid = _W["src"].features(w)
    arr = np.full((height, width), 255, dtype=np.uint8)
    n = int(valid.sum())
    if n:
        X = _W["prep"].transform(feats[_W["idx"]][:, valid].T)
        del feats
        head, mlps, gbms = _W["members"]
        with torch.no_grad():
            scores = np.zeros(len(X), dtype=np.float32)
            for i in range(0, len(X), 1_000_000):                 # bounded peak memory
                chunk = np.ascontiguousarray(X[i:i + 1_000_000], dtype=np.float32)
                parts = []
                if mlps:
                    xt = torch.from_numpy(chunk)
                    parts.append(np.mean([torch.sigmoid(m(xt)).numpy() for m in mlps], axis=0))
                if gbms:
                    parts.append(np.mean([g.predict(chunk, num_threads=1) for g in gbms], axis=0))
                scores[i:i + 1_000_000] = np.mean(parts, axis=0)
        arr[valid] = np.clip(np.round(scores * 100), 0, 100).astype(np.uint8)
    return row_off, col_off, n, arr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--block", type=int, default=1024)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0, help="stop after N blocks (testing)")
    ap.add_argument("--bbox", type=float, nargs=4, default=None, metavar=("X0", "Y0", "X1", "Y1"),
                    help="only cover this EPSG:3067 box (the raster still spans Finland, the rest stays nodata)")
    ap.add_argument("--overviews", action="store_true",
                    help="build overviews on the full raster (slow; the app parts get their own)")
    a = ap.parse_args()
    country = json.load(open(os.path.join(ML, "models", a.species, "model.json"))).get("country", "fi")
    px = "16m" if country == "fi" else "12m5"
    rasters = RASTERS if country == "fi" else os.path.join(ML, "data", "rasters_se")
    out = a.out or os.path.join(rasters, f"prob_{a.species}_{px}.tif")
    grid = grid_class(country)()
    prog = out + ".progress"
    done = set(open(prog).read().split()) if os.path.exists(prog) else set()
    prof = grid.profile("uint8", nodata=255)
    mode = "r+" if (os.path.exists(out) and done) else "w"

    # Skip blocks with no forestry land at all (sea, open water, built-up) before dispatching.
    with env():
        todo = []
        # Blocks with no forestry land are skipped before dispatch. Finland tests the site
        # class; Sweden has none, so it tests the SLU 2010 standing volume -- the same thing
        # block_features uses for `valid`. It is a 25 m RT90 raster, so the window has to be
        # taken in its own grid rather than the analysis one.
        site_path = (os.path.join(RASTERS, "mvmi2023", "kasvupaikka_vmi1x_1923.tif") if country == "fi"
                     else _grid_se.rt90_path("vol_total", 2010,
                                             os.path.join(ML, "data", "rasters_se", "slu_forest_map")))
        with rasterio.open(site_path) as site:
            nod = site.nodata
            site_vrt = None
            if country != "fi":
                from rasterio.vrt import WarpedVRT
                from rasterio.enums import Resampling as _R
                site_vrt = WarpedVRT(site, crs=grid.crs, transform=grid.transform,
                                     width=grid.width, height=grid.height,
                                     resampling=_R.nearest, src_nodata=nod, nodata=nod)
            if a.bbox:
                x0, y0, x1, y1 = a.bbox
                r0, c0 = grid.xy_to_rowcol(x0, y1); r1, c1 = grid.xy_to_rowcol(x1, y0)
            for w in grid.blocks(a.block):
                key = f"{w.row_off},{w.col_off}"
                if key in done:
                    continue
                if a.bbox and (w.row_off > r1 or w.row_off + w.height < r0 or
                               w.col_off > c1 or w.col_off + w.width < c0):
                    continue                      # outside the requested region: leave it nodata
                s = (site_vrt or site).read(1, window=w)
                if not ((s != nod) & (s >= 1)).any():
                    done.add(key); todo.append((w, False))
                else:
                    todo.append((w, True))
        empty = [w for w, live in todo if not live]
        work = [(int(w.row_off), int(w.col_off), int(w.height), int(w.width)) for w, live in todo if live]
        log(f"blocks: {len(work)} with data, {len(empty)} empty, {len(done) - len(empty)} already done")

        ctx = mp.get_context("fork")
        t0 = time.time()
        if a.limit:
            work = work[:a.limit]
        with open(prog, "a") as pf:
            for w in empty:
                pf.write(f"{w.row_off},{w.col_off}\n")
            pf.flush()
        # The dataset is reopened and closed every FLUSH_EVERY blocks. A tiled, compressed
        # GeoTIFF only gets its tile index written when the dataset is closed, so a run that
        # is interrupted without closing leaves the tiles on disk but unreadable.
        FLUSH_EVERY = 100
        with ctx.Pool(a.workers, initializer=_init, initargs=(a.species, 2023),
                      maxtasksperchild=8) as pool:
            results = pool.imap_unordered(_block, work, chunksize=1)
            i, exhausted = 0, False
            while not exhausted:
                first = not os.path.exists(out)
                with rasterio.open(out, "w" if first else "r+", **(prof if first else {})) as dst, \
                     open(prog, "a") as pf:
                    for _ in range(FLUSH_EVERY):
                        try:
                            row_off, col_off, nvalid, arr = next(results)
                        except StopIteration:
                            exhausted = True; break
                        dst.write(arr, 1, window=Window(col_off, row_off, arr.shape[1], arr.shape[0]))
                        pf.write(f"{row_off},{col_off}\n")
                        i += 1
                        if i % 20 == 0 or i == len(work):
                            el = time.time() - t0
                            log(f"{i}/{len(work)} blocks  {el/i:.1f}s/block  eta {(len(work)-i)*el/i/60:.0f} min")
                    pf.flush()
    if a.overviews and not a.limit:
        with rasterio.open(out, "r+") as dst:
            dst.build_overviews([2, 4, 8, 16, 32, 64, 128], Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")
        log("overviews built")
    log("DONE", out)


if __name__ == "__main__":
    main()
