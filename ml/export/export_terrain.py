"""Package elevation for the static app, so a tap needs no elevation API.

The app's result sheet reads slope and aspect for the tapped point. Asking Open-Meteo for them
costs one live request per tap and answers from Copernicus GLO-90 (~90 m), while the model under
the same pin was trained and scored on the MML 10 m model warped to the 16 m analysis grid
(ml/ingest/build_dem16.py). This exports that same warped elevation as COGs the browser reads with range
requests, exactly like prob_*.tif: no external call, and the slope in the sheet is the slope the
model saw.

Elevation is exported rather than ready-made slope/aspect on purpose. It is the smaller and by far
the more compressible of the two — a surface, not noise — and the app derives slope from a 3x3
block with the same central differences ml/core/features.py uses, so there is one definition of slope
in the project instead of two.

Output: data/terrain/terrain_meta.json + data/terrain/dem_<pixel>m_<ij>.tif
        (int16 decimetres, nodata -32768 — the units of ml/data/rasters/dem_16m.tif, unchanged)

    python ml/export/export_terrain.py [--downsample 4] [--split 3] [--max-mb 90]

Size is the only real decision here. The 16 m grid is 42 240 x 73 472 cells, which even as
well-predicted int16 is far more than a git repository should carry; --downsample averages it
down first. The default 4 (64 m cells, ~85 MB in nine parts) still resolves terrain finer than
the ±100 m sampling the Open-Meteo readout used, and it is the same elevation source as the
model. Pass --downsample 1 for the full 16 m grid if the hosting can take the gigabytes.
"""
import argparse, json, os, time, warnings
import numpy as np, rasterio
from rasterio.shutil import copy as rio_copy
from rasterio.transform import Affine
from rasterio.windows import Window, bounds as win_bounds

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
ROOT = os.path.dirname(ML)
SRC = os.path.join(ML, "data", "rasters", "dem_16m.tif")
NODATA = -32768
BLOCK = 4096          # source rows per read; a multiple of every sane --downsample


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def downsample(a, k):
    """Block mean of a (h, w) int16 array, nodata-aware, back to int16.

    A plain average resampling would blend -32768 into every coastal cell; here a block is nodata
    only when all of it is, so the coastline keeps its shape instead of growing a cliff.
    """
    if k == 1:
        return a
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k).astype("float32")
    b[b == NODATA] = np.nan
    with warnings.catch_warnings():                       # an all-sea block is expected, not news
        warnings.simplefilter("ignore", RuntimeWarning)
        m = np.nanmean(b, axis=(1, 3))
    return np.where(np.isfinite(m), np.round(m), NODATA).astype("int16")


def write_part(src, window, k, path):
    """One regional part as a real Cloud-Optimised GeoTIFF.

    The COG driver rather than GTiff + build_overviews, for the same reason as export_app.py:
    overviews appended to a large ordinary GeoTIFF make geotiff.js compute negative byte ranges,
    so the browser can draw such a file but cannot read single values out of it — and reading
    single values is the whole point of this one.
    """
    h, w = int(window.height) // k, int(window.width) // k
    t = src.transform * Affine.translation(window.col_off, window.row_off) * Affine.scale(k, k)
    prof = dict(driver="GTiff", dtype="int16", count=1, nodata=NODATA, crs=src.crs, transform=t,
                width=w, height=h, tiled=True, blockxsize=512, blockysize=512,
                compress="deflate", predictor=2, BIGTIFF="IF_SAFER")
    tmp = path + ".tmp.tif"
    with rasterio.open(tmp, "w", **prof) as dst:
        for r in range(0, int(window.height), BLOCK):
            rows = min(BLOCK, int(window.height) - r)
            rows -= rows % k
            if rows <= 0:
                break
            ws = Window(window.col_off, window.row_off + r, int(window.width), rows)
            dst.write(downsample(src.read(1, window=ws), k), 1, window=Window(0, r // k, w, rows // k))
    rio_copy(tmp, path, driver="COG", COMPRESS="DEFLATE", PREDICTOR="YES", LEVEL=9,
             BLOCKSIZE=512, OVERVIEW_RESAMPLING="AVERAGE", BIGTIFF="IF_SAFER")
    os.remove(tmp)
    return os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--downsample", type=int, default=4, help="source cells per exported cell")
    ap.add_argument("--split", type=int, default=3, help="parts per axis")
    ap.add_argument("--max-mb", type=float, default=90, help="GitHub refuses files over 100 MB")
    a = ap.parse_args()
    if not os.path.exists(a.src):
        raise SystemExit(f"{a.src} not found — run ml/ingest/build_dem16.py first")
    if not os.path.exists(a.src + ".ok") and a.src == SRC:
        raise SystemExit(f"{a.src} is an unfinished warp (no .ok) — let ml/ingest/build_dem16.py finish")

    outdir = os.path.join(ROOT, "data", "terrain")
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        if f.startswith("dem_") and f.endswith(".tif"):
            os.remove(os.path.join(outdir, f))

    k, n = a.downsample, a.split
    with rasterio.open(a.src) as src:
        pixel = int(round(src.transform.a * k))
        # part edges on multiples of k, so every part starts on a whole exported cell
        rows = [int(round(i * src.height / n)) // k * k for i in range(n)] + [src.height // k * k]
        cols = [int(round(i * src.width / n)) // k * k for i in range(n)] + [src.width // k * k]
        files = []
        for i in range(n):
            for j in range(n):
                w = Window(cols[j], rows[i], cols[j + 1] - cols[j], rows[i + 1] - rows[i])
                name = f"dem_{pixel}m_{i}{j}.tif"
                path = os.path.join(outdir, name)
                size = write_part(src, w, k, path)
                b = win_bounds(w, src.transform)
                files.append(dict(url=f"data/terrain/{name}", bounds=[round(x) for x in b]))
                log(f"{name} {size/1e6:.1f} MB" + ("  OVER LIMIT" if size > a.max_mb * 1e6 else ""))

    meta = dict(crs="EPSG:3067", pixel_m=pixel, value="elevation", units="dm", scale=0.1,
                nodata=NODATA, built=time.strftime("%Y-%m-%d"), files=files,
                source="MML 10 m elevation model, warped to the 16 m analysis grid by "
                       "ml/ingest/build_dem16.py" + (f" and averaged to {pixel} m" if k > 1 else ""),
                attribution="© Maanmittauslaitos — CC BY 4.0")
    json.dump(meta, open(os.path.join(outdir, "terrain_meta.json"), "w"), indent=1)
    total = sum(os.path.getsize(os.path.join(ROOT, f["url"])) for f in files)
    log(f"wrote terrain_meta.json: {len(files)} files, {total/1e6:.0f} MB total, {pixel} m cells")


if __name__ == "__main__":
    main()
