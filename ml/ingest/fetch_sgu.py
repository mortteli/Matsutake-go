"""Download SGU's open jordarter (soil type) GeoPackage and rasterize its layers onto the SLU
forest-map 12.5 m grid (SWEREF99 TM) — the Swedish equivalent of fetch_gtk.py's soil layer.

Two products, same producer (SGU), different scale:

  --coarse   Jordarter 1:1 000 000, national overview, 15 MB zip. Single layer: `grundlager`
             (parent material), code field `jg2` (int), text field `jg2_tx`.
  (default)  Jordarter 1:25 000-1:100 000, the best resolution mapped for a given area, 3.4 GB
             zip / 8.7 GB gpkg. Three layers sampled directly against a full local copy while
             building this script:

  grundlager       2 956 837 polygons, `jg2`/`jg2_tx` -- same fields as the coarse product,
                   confirmed identical. Parent material, full national coverage. Too many
                   polygons for this script's per-block STRtree+rasterize approach to finish in
                   practical time (the coarse run alone, 45k polygons, took >10 minutes) -- needs
                   per-region tiling or a native rasterizer before it's usable, so it is not
                   rasterized by `all` unless explicitly requested.
  ytlager          411 549 polygons, `jy1`/`jy1_tx`. The surface layer where it differs from
                   grundlager -- e.g. a thin sand sheet over till -- so coverage is partial by
                   design (0 = no override, read grundlager instead), not a data gap. 26 distinct
                   classes; dominated by Morän (220k), Torv (84k), Oklassad jordart (58k),
                   Svallsediment grus-block (14k), Lera-silt (13k), Isälvssediment (10k),
                   Postglacial sand-grus (8k). This is the more ecologically relevant layer for
                   matsutake's dry sandy/lichen-ground preference and is small enough to
                   rasterize in full (rasterized and validated while building this script: ~120k
                   matching-scale features, same order as fetch_skogsstyrelsen_harvests.py's
                   declared-felling layer, which took 20s).
  oversta_ytlager  Only 2 242 polygons nationally, and only 2 distinct classes: 89 "Svallsediment,
                   grus--block" (wave-washed gravel/boulder -- coarse, well-drained) and 75 "Torv"
                   (peat -- the opposite). Too sparse to be a general-purpose feature layer; kept
                   here mainly as a documented dead end, in case a future pass over exactly the
                   coastal/wetland transition it marks turns out to matter.

Outputs (not committed, rebuilt on demand):
  ml/data/raw/sgu_jordarter.gpkg
  ml/data/rasters_se/sgu_<layer>_12m5.tif   uint8 class index (0 = none)
Committed: ml/data/sgu_classes.json  ({layer: {index: {code, name}}})

Usage: python ml/ingest/fetch_sgu.py [download|rasterize|all] [--coarse] [layer ...]
       (layer defaults to ytlager for the fine product, grundlager for --coarse; grundlager is
       available fine-scale too but must be named explicitly -- see the size warning above)
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
# layer -> (code field, name field), all confirmed against full local copies of both products.
LAYERS = {
    "grundlager": ("jg2", "jg2_tx"),
    "ytlager": ("jy1", "jy1_tx"),
    "oversta_ytlager": ("jy0", "jy0_tx"),
}
COARSE_LAYERS = {"grundlager"}    # the only layer the 1:1M product ships


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def gpkg_path(coarse):
    """One file per product. The two used to share a name, which meant that after a coarse
    run the fine download was skipped as "already downloaded" and the fine layers were then
    rasterized out of the 1:1M geopackage -- silently, since grundlager carries the same
    jg2/jg2_tx fields at both scales. The pipeline needs both products (coarse grundlager for
    parent material, fine ytlager for surface texture), so they cannot share a path."""
    return os.path.join(RAW, f"sgu_jordarter_{'coarse' if coarse else 'fine'}.gpkg")


def download(coarse):
    os.makedirs(RAW, exist_ok=True)
    url = URLS["coarse"] if coarse else URLS["fine"]
    zpath = os.path.join(RAW, os.path.basename(url))
    gpkg = gpkg_path(coarse)
    if os.path.exists(gpkg):
        log("already downloaded", os.path.basename(gpkg)); return gpkg
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


def rasterize(layer, coarse):
    import fiona, rasterio, shapely
    from rasterio.features import rasterize as rio_rasterize
    from rasterio.windows import transform as win_transform
    from shapely.strtree import STRtree
    sys.path.insert(0, os.path.join(ML, "core"))
    from grid_se import GridSE, env

    code_f, name_f = LAYERS[layer]
    gpkg = gpkg_path(coarse)
    with fiona.open(gpkg, layer=layer) as src:
        props = src.schema["properties"]
        if code_f not in props:
            raise RuntimeError(f"expected field {code_f!r} not in {layer}; has: {sorted(props)}. "
                               "Update LAYERS in fetch_sgu.py to match.")
        log("using fields", code_f, name_f, "on", layer, "crs", src.crs)
        geoms, codes, names = [], [], {}
        for feat in src:
            g = feat.geometry
            if g is None:
                continue
            c = feat["properties"].get(code_f)
            geoms.append(shapely.geometry.shape(g))
            codes.append(c)
            names[c] = feat["properties"].get(name_f)
    log(layer, "loaded", len(geoms), "polygons")

    uniq = sorted(set(c for c in codes if c is not None), key=lambda c: str(c))
    index = {c: i + 1 for i, c in enumerate(uniq)}          # 0 = no polygon
    classes_path = os.path.join(ML, "data", "sgu_classes.json")
    allc = json.load(open(classes_path)) if os.path.exists(classes_path) else {}
    allc[f"{layer}_{'1m' if coarse else '25k'}"] = {str(i): {"code": c, "name": names.get(c)} for c, i in index.items()}
    json.dump(allc, open(classes_path, "w"), ensure_ascii=False, indent=1)
    log("wrote", classes_path, len(index), "classes for", layer, "1m" if coarse else "25k")

    tree = STRtree(geoms)
    grid = GridSE()
    os.makedirs(RASTERS, exist_ok=True)
    out = os.path.join(RASTERS, f"sgu_{layer}_{'1m' if coarse else '25k'}_12m5.tif")
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
                if k % 20 == 0: log(layer, "block", k)
    log(layer, "raster written", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="all", choices=["download", "rasterize", "all"])
    # `choices=` on a nargs="*" positional errors out on its own [] default before parsing even
    # sees the command line (argparse tries to validate the default list itself against choices),
    # so the layer names are validated by hand below instead.
    ap.add_argument("layers", nargs="*", help="defaults to grundlager (--coarse) or ytlager (fine)")
    ap.add_argument("--coarse", action="store_true", help="1:1 000 000 overview instead of 1:25k-100k")
    ap.add_argument("--keep-gpkg", action="store_true",
                    help="keep the extracted geopackage; by default the fine one (8.7 GB) is "
                         "deleted once rasterized, because the Swedish pipeline runs on a 29 GB disk")
    a = ap.parse_args()
    layers = a.layers or (["grundlager"] if a.coarse else ["ytlager"])
    if bad := set(layers) - set(LAYERS):
        raise SystemExit(f"unknown layer(s) {bad}; choose from {sorted(LAYERS)}")
    if a.coarse and (bad := set(layers) - COARSE_LAYERS):
        raise SystemExit(f"--coarse only ships {COARSE_LAYERS}, not {bad}")
    if a.mode in ("download", "all"):
        download(a.coarse)
    if a.mode in ("rasterize", "all"):
        for layer in layers:
            rasterize(layer, a.coarse)
        if a.mode == "all" and not a.keep_gpkg and not a.coarse:
            g = gpkg_path(a.coarse)
            if os.path.exists(g):
                log("removing", os.path.basename(g), f"({os.path.getsize(g) / 2**30:.1f} GB)")
                os.remove(g)
    log("DONE")
