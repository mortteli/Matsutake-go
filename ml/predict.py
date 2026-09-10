"""Full-Finland inference: stream every feature source block by block over the MVMI 16 m grid,
run the fold-ensemble MLP, and write a tiled GeoTIFF with overviews (COG-style):
  value 0..100 = probability × 100, 255 = no forestry-land data.

python ml/predict.py --species matsutake [--block 2048] [--out ml/data/rasters/prob_matsutake_16m.tif]
Restartable: finished blocks are recorded in <out>.progress.
"""
import argparse, json, os, sys, time
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--block", type=int, default=2048)
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0, help="stop after N blocks (testing)")
    a = ap.parse_args()
    out = a.out or os.path.join(RASTERS, f"prob_{a.species}_16m.tif")
    cfg, prep, members, idx = load_model(a.species)
    torch.set_num_threads(max(1, os.cpu_count() - 1))
    grid = Grid()
    src = Sources(grid, 2023)
    prog = out + ".progress"
    done = set(open(prog).read().split()) if os.path.exists(prog) else set()
    prof = grid.profile("uint8", nodata=255)
    mode = "r+" if (os.path.exists(out) and done) else "w"
    site = src.mvmi["kasvupaikka"]
    with env(), rasterio.open(out, mode, **(prof if mode == "w" else {})) as dst, open(prog, "a") as pf:
        n_blocks = 0
        for w in grid.blocks(a.block):
            key = f"{w.row_off},{w.col_off}"
            if key in done:
                continue
            s = site.read(1, window=w)
            if not ((s != site.nodata) & (s >= 1)).any():
                pf.write(key + "\n"); pf.flush(); continue           # sea / no forestry land
            t0 = time.time()
            feats, valid = src.features(w)
            arr = np.full((w.height, w.width), 255, dtype=np.uint8)
            if valid.any():
                X = feats[idx][:, valid].T                              # (n_valid, n_features)
                X = prep.transform(X)
                with torch.no_grad():
                    xt = torch.tensor(X, dtype=torch.float32)
                    p = np.mean([torch.sigmoid(m(xt)).numpy() for m in members], axis=0)
                arr[valid] = np.clip(np.round(p * 100), 0, 100).astype(np.uint8)
            dst.write(arr, 1, window=w)
            pf.write(key + "\n"); pf.flush()
            n_blocks += 1
            log(f"block {key} valid {int(valid.sum())} in {time.time()-t0:.1f}s")
            if a.limit and n_blocks >= a.limit:
                break
    src.close()
    if not a.limit:
        with rasterio.open(out, "r+") as dst:
            dst.build_overviews([2, 4, 8, 16, 32, 64, 128], Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")
        log("overviews built")
    log("DONE", out)


if __name__ == "__main__":
    main()
