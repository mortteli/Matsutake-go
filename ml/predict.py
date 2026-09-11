"""Full-Finland inference: stream every feature source block by block over the MVMI 16 m grid,
run the fold-ensemble MLP, and write a tiled GeoTIFF with overviews (COG-style):
  value 0..100 = probability × 100, 255 = no forestry-land data.

python ml/predict.py --species matsutake [--block 2048] [--out ml/data/rasters/prob_matsutake_16m.tif]
Restartable: finished blocks are recorded in <out>.progress.
"""
import argparse, json, os, sys, time
import multiprocessing as mp
import numpy as np, rasterio, torch
from rasterio.enums import Resampling
from rasterio.windows import Window

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from grid import Grid, env
from features import Sources, FEATURES, RASTERS
from train import MLP, Prep


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load_model(species):
    mdir = os.path.join(HERE, "models", species)
    cfg = json.load(open(os.path.join(mdir, "model.json")))
    prep = Prep(cfg["features"])
    p = cfg["prep"]
    prep.median, prep.mean, prep.std = (np.array(p[k], dtype=np.float32) for k in ("median", "mean", "std"))
    members = []
    for f in range(cfg["n_members"]):
        m = MLP(cfg["mlp"]["n_in"], cfg["mlp"]["hidden"], cfg["mlp"]["depth"], cfg["mlp"]["dropout"])
        m.load_state_dict(torch.load(os.path.join(mdir, f"mlp_fold{f}.pt"), map_location="cpu")); m.eval()
        members.append(m)
    idx = [FEATURES.index(c) for c in cfg["features"]]
    return cfg, prep, members, idx


_W = {}


def _init(species, cycle):
    """One Sources handle and one model copy per worker process."""
    import torch as _t
    _t.set_num_threads(1)
    cfg, prep, members, idx = load_model(species)
    _W.update(grid=Grid(), cfg=cfg, prep=prep, members=members, idx=idx)
    _W["src"] = Sources(_W["grid"], cycle)


def _block(args):
    row_off, col_off, height, width = args
    w = Window(col_off, row_off, width, height)
    feats, valid = _W["src"].features(w)
    arr = np.full((height, width), 255, dtype=np.uint8)
    if valid.any():
        X = _W["prep"].transform(feats[_W["idx"]][:, valid].T)
        with torch.no_grad():
            xt = torch.tensor(X, dtype=torch.float32)
            p = np.mean([torch.sigmoid(m(xt)).numpy() for m in _W["members"]], axis=0)
        arr[valid] = np.clip(np.round(p * 100), 0, 100).astype(np.uint8)
    return row_off, col_off, int(valid.sum()), arr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--block", type=int, default=1024)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0, help="stop after N blocks (testing)")
    a = ap.parse_args()
    out = a.out or os.path.join(RASTERS, f"prob_{a.species}_16m.tif")
    grid = Grid()
    prog = out + ".progress"
    done = set(open(prog).read().split()) if os.path.exists(prog) else set()
    prof = grid.profile("uint8", nodata=255)
    mode = "r+" if (os.path.exists(out) and done) else "w"

    # Skip blocks with no forestry land at all (sea, open water, built-up) before dispatching.
    with env():
        todo = []
        with rasterio.open(os.path.join(RASTERS, "mvmi2023", "kasvupaikka_vmi1x_1923.tif")) as site:
            nod = site.nodata
            for w in grid.blocks(a.block):
                key = f"{w.row_off},{w.col_off}"
                if key in done:
                    continue
                s = site.read(1, window=w)
                if not ((s != nod) & (s >= 1)).any():
                    done.add(key); todo.append((w, False))
                else:
                    todo.append((w, True))
        empty = [w for w, live in todo if not live]
        work = [(int(w.row_off), int(w.col_off), int(w.height), int(w.width)) for w, live in todo if live]
        log(f"blocks: {len(work)} with data, {len(empty)} empty, {len(done) - len(empty)} already done")

        ctx = mp.get_context("fork")
        t0 = time.time()
        with rasterio.open(out, mode, **(prof if mode == "w" else {})) as dst, open(prog, "a") as pf:
            for w in empty:
                pf.write(f"{w.row_off},{w.col_off}\n")
            pf.flush()
            if a.limit:
                work = work[:a.limit]
            with ctx.Pool(a.workers, initializer=_init, initargs=(a.species, 2023)) as pool:
                for i, (row_off, col_off, nvalid, arr) in enumerate(
                        pool.imap_unordered(_block, work, chunksize=1), 1):
                    dst.write(arr, 1, window=Window(col_off, row_off, arr.shape[1], arr.shape[0]))
                    pf.write(f"{row_off},{col_off}\n"); pf.flush()
                    if i % 20 == 0 or i == len(work):
                        el = time.time() - t0
                        log(f"{i}/{len(work)} blocks  {el/i:.1f}s/block  eta {(len(work)-i)*el/i/60:.0f} min")
    if not a.limit:
        with rasterio.open(out, "r+") as dst:
            dst.build_overviews([2, 4, 8, 16, 32, 64, 128], Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")
        log("overviews built")
    log("DONE", out)


if __name__ == "__main__":
    main()
