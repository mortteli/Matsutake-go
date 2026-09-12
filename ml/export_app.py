"""Package the probability raster for the static app.

Writes data/<species>/prob_meta.json plus one or more GeoTIFFs (tiled, deflate, overviews)
under data/<species>/. GitHub refuses files over 100 MB, so the raster is split into a grid
of regional files when needed; the app loads only the files intersecting the view.

python ml/export_app.py --species matsutake [--src ml/data/rasters/prob_matsutake_16m.tif] [--max-mb 90]
"""
import argparse, json, math, os, sys, time
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as rio_copy
from rasterio.windows import Window, transform as win_transform

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def write_part(src, window, path, floor, step):
    """One regional part as a real Cloud-Optimised GeoTIFF.

    Scores below `floor` are stored as 0 ("not in the mapped range") and the rest quantised to
    `step`. The two together set how finely the app can slice the top: the 0–100 range is spread
    over the best `max_pct` of forest land, so at max_pct 15 and step 1 one stored level is about
    0.15 % of forest land, which is what a "best 0.25 %" setting needs to mean anything.

    The COG driver is used rather than plain GTiff plus build_overviews: overviews appended to a large
    ordinary GeoTIFF make geotiff.js compute negative byte ranges, so the browser can render
    such a file but cannot read single values out of it.
    """
    tmp = path + ".tmp.tif"
    prof = src.profile.copy()
    prof.update(driver="GTiff", width=int(window.width), height=int(window.height),
                transform=win_transform(window, src.transform), tiled=True,
                blockxsize=512, blockysize=512, compress="deflate", predictor=2, BIGTIFF="IF_SAFER")
    with rasterio.open(tmp, "w", **prof) as dst:
        for r in range(0, int(window.height), 4096):
            for c in range(0, int(window.width), 4096):
                w = Window(c, r, min(4096, int(window.width) - c), min(4096, int(window.height) - r))
                ws = Window(window.col_off + c, window.row_off + r, w.width, w.height)
                a = src.read(1, window=ws)
                q = np.where(a < floor, 0, np.round(a / step) * step).astype(np.uint8)
                dst.write(np.where(a != 255, q, 255).astype(np.uint8), 1, window=w)
    rio_copy(tmp, path, driver="COG", COMPRESS="DEFLATE", PREDICTOR="YES", LEVEL=9,
             BLOCKSIZE=512, OVERVIEW_RESAMPLING="AVERAGE", BIGTIFF="IF_SAFER")
    os.remove(tmp)
    return os.path.getsize(path)


NQ = 1001          # quantile points stored for the app: 0.1 % resolution, enough for its top stop


def forest_quantiles(src, decimate=8):
    """Score distribution over forestry land, read from the map itself rather than from the
    training background sample, so the slider's "best X %" means exactly that on this map.

    Stored on a 0.1 % grid rather than a 1 % one: a slider stop of "the best 0.25 %" cannot be
    resolved from whole percentiles."""
    a = src.read(1, out_shape=(src.height // decimate, src.width // decimate))
    v = a[a != 255]
    return v, np.percentile(v, np.linspace(0, 100, NQ)).astype(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--src", default=None)
    ap.add_argument("--max-mb", type=float, default=90)
    ap.add_argument("--split", type=int, default=3)
    ap.add_argument("--max-pct", type=float, default=15,
                    help="largest share of forest land the app can show; the rest is stored as 0")
    ap.add_argument("--step", type=int, default=1, help="quantisation of stored scores")
    a = ap.parse_args()
    src_path = a.src or os.path.join(HERE, "data", "rasters", f"prob_{a.species}_16m.tif")
    outdir = os.path.join(ROOT, "data", a.species); os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        if f.startswith("prob_") and f.endswith(".tif"):
            os.remove(os.path.join(outdir, f))
    model = json.load(open(os.path.join(HERE, "models", a.species, "model.json")))
    report = json.load(open(os.path.join(HERE, "models", a.species, "report.json")))

    with rasterio.open(src_path) as src:
        v, _ = forest_quantiles(src)
        floor = float(np.percentile(v, 100 - a.max_pct))
        log(f"forest cells sampled {v.size}, floor for the best {a.max_pct} % = score {floor:.0f}")
        files, n = [], a.split
        rows = [int(round(i * src.height / n)) for i in range(n + 1)]
        cols = [int(round(i * src.width / n)) for i in range(n + 1)]
        for i in range(n):
            for j in range(n):
                w = Window(cols[j], rows[i], cols[j + 1] - cols[j], rows[i + 1] - rows[i])
                data = src.read(1, window=w, out_shape=(max(1, w.height // 64), max(1, w.width // 64)))
                if not ((data != 255) & (data >= floor)).any():
                    continue                                   # nothing in the mapped range here
                name = f"prob_{a.species}_16m_{i}{j}.tif"
                path = os.path.join(outdir, name)
                size = write_part(src, w, path, floor, a.step)
                b = rasterio.windows.bounds(w, src.transform)
                files.append(dict(url=f"data/{a.species}/{name}", bounds=[round(x) for x in b]))
                log(f"{name} {size/1e6:.1f} MB" + ("  OVER LIMIT" if size > a.max_mb * 1e6 else ""))
        # quantiles of the values as stored, so the app's threshold and colour ramp match the files
        qv = np.where(v < floor, 0, np.round(v / a.step) * a.step)
        quant = np.percentile(qv, np.linspace(0, 100, NQ)).astype(float).round(1).tolist()

    total = sum(os.path.getsize(os.path.join(ROOT, f["url"])) for f in files)
    head = model.get("head", "mlp")
    meta = dict(species=a.species, trained=model["trained"], n_presence=report["n_presence"],
                crs="EPSG:3067", pixel_m=16, nodata=255, value="model score x 100", head=head,
                floor=round(floor), max_pct=a.max_pct, step=a.step, quantiles=quant, files=files,
                metrics=report["results"].get("head:" + head, report["results"].get(head, {})),
                curve=report.get("curve", []),
                sources="Luke MVMI 2009-2023, MML DEM 10 m, GTK Maapera 1:200k + glacigenic formations, "
                        "FMI 10 km climate, GBIF/FinBIF occurrence records")
    json.dump(meta, open(os.path.join(outdir, "prob_meta.json"), "w"), indent=1)
    log(f"wrote prob_meta.json: {len(files)} files, {total/1e6:.0f} MB total")


if __name__ == "__main__":
    main()
