"""Download SGU's open jordarter (soil type) GeoPackage and rasterize it onto the SLU forest-map
12.5 m grid (SWEREF99 TM) — the Swedish equivalent of fetch_gtk.py's soil layer.

Two products, same producer (SGU), same `grundlager` layer name (confirmed against the live
service's WMS GetCapabilities layer list: SE.GOV.SGU.JORD.GRUNDLAGER.*), different scale:

  --coarse   Jordarter 1:1 000 000, national overview, 15 MB zip, code field `jg2` (int),
             text field `jg2_tx` — verified directly against a full local copy of the file.
  (default)  Jordarter 1:25 000-1:100 000, the best resolution mapped for a given area, 3.4 GB
             zip. Column names were NOT verified here — the zip is too large to fetch and inspect
             in one sitting — but SGU's own WMS layer list names it `grundlager` too, so the
             `--coarse` schema is used as the first guess and the actual columns are logged before
             anything is rasterized, so a wrong guess fails loudly instead of silently writing an
             empty raster (the exact failure mode fetch_harvests.py's own comments warn about).

Outputs (not committed, rebuilt on demand):
  ml/data/raw/sgu_jordarter.gpkg
  ml/data/rasters_se/sgu_soil_12m5.tif   uint8 class index (0 = none)
Committed: ml/data/sgu_classes.json  (index -> code/name)

Usage: python ml/ingest/fetch_sgu.py [download|rasterize|all] [--coarse]
"""
import argparse, json, os, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
RAW = os.path.join(ML, "data", "raw")
RASTERS = os.path.join(ML, "data", "rasters_se")

URLS = {
    "coarse": "https://resource.sgu.se/data/oppnadata/jordarter1miljon/jordarter1miljon.zip",
    "fine": "https://resource.sgu.se/data/oppnadata/jordarter25k-100k/jordarter25k-100k.zip",
}
LAYER = "grundlager"
# (code field, name field) tried in this order; the coarse product uses the first pair.
CODE_FIELD_CANDIDATES = [("jg2", "jg2_tx"), ("jg3", "jg3_tx"), ("JG2", "JG2_TX")]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def download(coarse):
    os.makedirs(RAW, exist_ok=True)
    url = URLS["coarse"] if coarse else URLS["fine"]
    zpath = os.path.join(RAW, os.path.basename(url))
    gpkg = os.path.join(RAW, "sgu_jordarter.gpkg")
    if os.path.exists(gpkg):
        log("already downloaded"); return gpkg
    import subprocess
    subprocess.run(["curl", "-sS", "-C", "-", "--retry", "5", "--retry-delay", "3",
                    "--max-time", "7200", "-o", zpath, url], check=True)
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if n.endswith(".gpkg")]
        if not names:
            raise RuntimeError(f"no geopackage in {zpath}")
        z.extract(names[0], RAW)
        os.replace(os.path.join(RAW, names[0]), gpkg)
    os.remove(zpath)
    log("downloaded and extracted", gpkg)
    return gpkg


def pick_fields(props):
    for code_f, name_f in CODE_FIELD_CANDIDATES:
        if code_f in props:
            return code_f, name_f if name_f in props else None
    raise RuntimeError(f"none of the expected code fields found; layer has: {sorted(props)}. "
                       "Update CODE_FIELD_CANDIDATES in fetch_sgu.py to match.")


def rasterize():
    import fiona, numpy as np, rasterio
    from rasterio.features import rasterize as rio_rasterize
    from rasterio.windows import transform as win_transform
    from shapely.strtree import STRtree
    import shapely
    sys.path.insert(0, os.path.join(ML, "core"))
    from grid_se import GridSE, env

    gpkg = os.path.join(RAW, "sgu_jordarter.gpkg")
    with fiona.open(gpkg, layer=LAYER) as src:
        code_f, name_f = pick_fields(src.schema["properties"])
        log("using fields", code_f, name_f, "crs", src.crs)
        geoms, codes, names = [], [], {}
        for feat in src:
            g = feat.geometry
            if g is None:
                continue
            c = feat["properties"].get(code_f)
            geoms.append(shapely.geometry.shape(g))
            codes.append(c)
            if name_f:
                names[c] = feat["properties"].get(name_f)
    log("loaded", len(geoms), "polygons")

    uniq = sorted(set(c for c in codes if c is not None), key=lambda c: str(c))
    index = {c: i + 1 for i, c in enumerate(uniq)}          # 0 = no polygon
    classes_path = os.path.join(ML, "data", "sgu_classes.json")
    json.dump({str(i): {"code": c, "name": names.get(c)} for c, i in index.items()},
              open(classes_path, "w"), ensure_ascii=False, indent=1)
    log("wrote", classes_path, len(index), "classes")

    tree = STRtree(geoms)
    grid = GridSE()
    os.makedirs(RASTERS, exist_ok=True)
    out = os.path.join(RASTERS, "sgu_soil_12m5.tif")
    with env():
        with rasterio.open(out, "w", **grid.profile("uint8", nodata=0)) as dst:
            for k, w in enumerate(grid.blocks(4096)):
                x0, y0 = grid.transform * (w.col_off, w.row_off + w.height)
                x1, y1 = grid.transform * (w.col_off + w.width, w.row_off)
                hits = tree.query(shapely.box(x0, y0, x1, y1))
                if len(hits) == 0:
                    continue
                shapes = [(geoms[i], index[codes[i]]) for i in hits if codes[i] is not None]
                arr = rio_rasterize(shapes, out_shape=(w.height, w.width),
                                    transform=win_transform(w, grid.transform), fill=0, dtype="uint8")
                dst.write(arr, 1, window=w)
                if k % 20 == 0: log("block", k)
    log("raster written", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="all", choices=["download", "rasterize", "all"])
    ap.add_argument("--coarse", action="store_true", help="1:1 000 000 overview instead of 1:25k-100k")
    a = ap.parse_args()
    if a.mode in ("download", "all"):
        download(a.coarse)
    if a.mode in ("rasterize", "all"):
        rasterize()
    log("DONE")
