"""Download GTK surface-soil (1:200k) and glacigenic-formation polygons through GTK's open WFS
and rasterize both onto the MVMI 16 m grid.

Outputs (not committed, rebuilt on demand):
  ml/data/raw/gtk_soil.ndjson.gz, ml/data/raw/gtk_glac.ndjson.gz
  ml/data/rasters/gtk_soil_16m.tif      uint8 class index (0 = none)
  ml/data/rasters/gtk_glac_16m.tif      uint8 class index (0 = none)
Committed: ml/data/gtk_classes.json  (index -> code/name for both layers)

Usage: python ml/fetch_gtk.py [download|rasterize|all]
"""
import gzip, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
RASTERS = os.path.join(HERE, "data", "rasters")
BASE = "https://gtkdata.gtk.fi/arcgis/services/Rajapinnat/GTK_Maapera_WFS/MapServer/WFSServer?"
LAYERS = {
    "soil": ("Rajapinnat_GTK_Maapera_WFS:maapera_200k_maalajit", "PINTAMAALAJI_KOODI", "PINTAMAALAJI"),
    "glac": ("Rajapinnat_GTK_Maapera_WFS:jaatikkosyntyiset_maaperamuodostumat_jaatikkojokisyntyiset_ja_moreenimuodostumat",
             "DEPOSIT_TYPE_CLASS", "DEPOSIT_TYPE_NAME"),
}
PAGE = 2000


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def get(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return r.read()
        except Exception as e:
            log("retry", i, e)
            time.sleep(5 * (i + 1))
    raise RuntimeError("WFS request failed: " + url[:120])


def download(key, threads=6):
    """Page through the layer in parallel (pages are independent) and write NDJSON."""
    import re
    from concurrent.futures import ThreadPoolExecutor
    layer, code_f, name_f = LAYERS[key]
    os.makedirs(RAW, exist_ok=True)
    out = os.path.join(RAW, f"gtk_{key}.ndjson.gz")
    done = os.path.join(RAW, f"gtk_{key}.done")
    if os.path.exists(done):
        log(key, "already downloaded"); return
    hits = get(BASE + urllib.parse.urlencode(dict(service="WFS", version="2.0.0", request="GetFeature",
                                                  typeNames=layer, resultType="hits")))
    total = int(re.search(rb'numberMatched="(\d+)"', hits).group(1))
    log(key, "features to fetch", total)

    def page(start):
        q = dict(service="WFS", version="2.0.0", request="GetFeature", typeNames=layer,
                 count=PAGE, startIndex=start, outputFormat="GEOJSON", srsName="urn:ogc:def:crs:EPSG::3067")
        return json.loads(get(BASE + urllib.parse.urlencode(q))).get("features", [])

    n = 0
    with gzip.open(out, "wt") as f, ThreadPoolExecutor(threads) as ex:
        for feats in ex.map(page, range(0, total, PAGE)):
            for ft in feats:
                p = ft["properties"]
                f.write(json.dumps({"c": p.get(code_f), "n": p.get(name_f), "g": ft["geometry"]}) + "\n")
            n += len(feats)
            if n % (PAGE * 10) < PAGE:
                log(key, "features", n)
    open(done, "w").write(str(n))
    log(key, "download complete", n)


def rasterize(key):
    import numpy as np, rasterio, shapely
    from shapely.strtree import STRtree
    from rasterio.features import rasterize as rio_rasterize
    from rasterio.windows import transform as win_transform
    from pyproj import Transformer
    sys.path.insert(0, HERE)
    from grid import Grid, env

    src = os.path.join(RAW, f"gtk_{key}.ndjson.gz")
    geoms, codes, names = [], [], {}
    with gzip.open(src, "rt") as f:
        for line in f:
            d = json.loads(line)
            g = d["g"]
            if not g: continue
            geoms.append(shapely.from_geojson(json.dumps(g)))
            codes.append(d["c"]); names[d["c"]] = d["n"]
    log(key, "loaded", len(geoms), "polygons")
    # WFS may ignore srsName and answer in lon/lat; detect and reproject
    b = shapely.total_bounds(np.array(geoms, dtype=object))
    if abs(b[0]) < 180 and abs(b[3]) < 90:
        log(key, "reprojecting from EPSG:4326")
        tr = Transformer.from_crs("EPSG:4326", "EPSG:3067", always_xy=True)
        geoms = [shapely.transform(g, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1]))) for g in geoms]
    uniq = sorted(set(c for c in codes if c is not None), key=lambda c: str(c))
    index = {c: i + 1 for i, c in enumerate(uniq)}            # 0 = no polygon
    classes_path = os.path.join(HERE, "data", "gtk_classes.json")
    allc = json.load(open(classes_path)) if os.path.exists(classes_path) else {}
    allc[key] = {str(i): {"code": c, "name": names.get(c)} for c, i in index.items()}
    json.dump(allc, open(classes_path, "w"), ensure_ascii=False, indent=1)
    tree = STRtree(geoms)
    grid = Grid()
    os.makedirs(RASTERS, exist_ok=True)
    out = os.path.join(RASTERS, f"gtk_{key}_16m.tif")
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
                if k % 20 == 0: log(key, "block", k)
    log(key, "raster written", out)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("download", "all"):
        download("glac"); download("soil")
    if mode in ("rasterize", "all"):
        rasterize("glac"); rasterize("soil")
    log("DONE")
