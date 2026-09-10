"""Package the probability raster for the static app.

Writes data/<species>/prob_meta.json plus one or more GeoTIFFs (tiled, deflate, overviews)
under data/<species>/. GitHub refuses files over 100 MB, so the raster is split into a grid
of regional files when needed; the app loads only the files intersecting the view.

python ml/export_app.py --species matsutake [--src ml/data/rasters/prob_matsutake_16m.tif] [--max-mb 90]
"""
import argparse, json, math, os, sys, time
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window, transform as win_transform

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def write_part(src, window, path):
    prof = src.profile.copy()
    prof.update(width=int(window.width), height=int(window.height), transform=win_transform(window, src.transform),
                tiled=True, blockxsize=512, blockysize=512, compress="deflate", predictor=2, BIGTIFF="IF_SAFER")
    with rasterio.open(path, "w", **prof) as dst:
        for r in range(0, int(window.height), 4096):
            for c in range(0, int(window.width), 4096):
                w = Window(c, r, min(4096, int(window.width) - c), min(4096, int(window.height) - r))
                ws = Window(window.col_off + c, window.row_off + r, w.width, w.height)
                dst.write(src.read(1, window=ws), 1, window=w)
        dst.build_overviews([2, 4, 8, 16, 32, 64, 128], Resampling.average)
    return os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--src", default=None)
    ap.add_argument("--max-mb", type=float, default=90)
    ap.add_argument("--split", type=int, default=0, help="force an NxN split")
    a = ap.parse_args()
    src_path = a.src or os.path.join(HERE, "data", "rasters", f"prob_{a.species}_16m.tif")
    outdir = os.path.join(ROOT, "data", a.species); os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        if f.startswith("prob_") and f.endswith(".tif"):
            os.remove(os.path.join(outdir, f))
    model = json.load(open(os.path.join(HERE, "models", a.species, "model.json")))
    report = json.load(open(os.path.join(HERE, "models", a.species, "report.json")))
    files = []
    with rasterio.open(src_path) as src:
        n = a.split or 1
        while True:
            files = []
            rows, cols = [int(round(i * src.height / n)) for i in range(n + 1)], [int(round(i * src.width / n)) for i in range(n + 1)]
            too_big = False
            for i in range(n):
                for j in range(n):
                    w = Window(cols[j], rows[i], cols[j + 1] - cols[j], rows[i + 1] - rows[i])
                    name = f"prob_{a.species}_16m" + (f"_{i}{j}" if n > 1 else "") + ".tif"
                    path = os.path.join(outdir, name)
                    # skip parts that are entirely nodata
                    data = src.read(1, window=w, out_shape=(max(1, w.height // 64), max(1, w.width // 64)))
                    if not (data != 255).any():
                        continue
                    size = write_part(src, w, path)
                    b = rasterio.windows.bounds(w, src.transform)
                    files.append(dict(url=f"data/{a.species}/{name}", bounds=[round(x) for x in b], mb=round(size / 1e6, 1)))
                    log(name, f"{size/1e6:.1f} MB")
                    if size > a.max_mb * 1e6:
                        too_big = True
            if not too_big or a.split:
                break
            for f in files:
                os.remove(os.path.join(ROOT, f["url"]))
            n += 1
            log("parts too large, splitting", f"{n}x{n}")
    q = [round(float(x) * 100, 2) for x in model["bg_random_quantiles"]]
    meta = dict(species=a.species, trained=model["trained"], n_presence=report["n_presence"], crs="EPSG:3067",
                pixel_m=16, nodata=255, value="probability x 100", quantiles=q,
                files=[dict(url=f["url"], bounds=f["bounds"]) for f in files],
                metrics=report["results"].get("mlp", {}), curve=report.get("curve", []),
                sources="Luke MVMI 2009–2023, MML DEM 10 m, GTK Maaperä 1:200k + glacigenic formations, FMI 10 km climate, GBIF/FinBIF")
    json.dump(meta, open(os.path.join(outdir, "prob_meta.json"), "w"), indent=1)
    log("wrote", os.path.join(outdir, "prob_meta.json"), "files", len(files))


if __name__ == "__main__":
    main()
