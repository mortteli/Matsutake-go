"""Where the forest in the SLU forest-map raster is no longer standing -- the Swedish equivalent
of fetch_harvests.py. Same two-tier idea as Finland:

    0  no signal
    1  a felling was DECLARED (Avverkningsanmalan)         -- an intention
    2  Skogsstyrelsen's own record says the stand was cut  -- a fact (once its schema is confirmed)

Declared layer (AvverkningsAnmalanYta, EPSG:3006, 129k features, 67 MB zip) was downloaded and
inspected directly while building this script:
  Avverktyp='Foryngringsavverkning'  is the felling-type field to filter on (NOT `Andamal`, which
  is 92% "Uppgift saknas" -- no info -- and is a purpose/land-use field, not a felling-type one).
  Inkomdatum is the notification date.
Skogsstyrelsen's own page says only currently-valid notifications (<=5 years old, <=75% harvested)
are published, so there is no expiry filter to add on top -- unlike Finland's 3-year-validity
metsankayttoilmoitukset, which stay in the feed after they lapse.

Completed-fact layer (sksUtfordAvverk, 2.7 GB zip, 7.5 GB gpkg) was later downloaded in full and
inspected directly: layer `UtfordAvverkningYta`, 1 381 787 features, EPSG:3006, same `Avverktyp`
field and `Föryngringsavverkning` value as the declared layer (94 % of records). It is built from
Sentinel-2 change detection (`KallaDatum`='Bildanalys', with `Forebild`/`Efterbild` before/after
image IDs) rather than machine telemetry the way Finland's stand register is, and its felling date
field is `Avvdatum`, not `Inkomdatum`. rasterize_layer() still logs the real column list and raises
before writing anything if a future schema change breaks the field guess, rather than silently
producing an empty raster (the exact silent-failure mode fetch_harvests.py's own comments warn
about).

Output (not committed, rebuilt on demand): ml/data/rasters_se/cut_declared_12m5.tif,
ml/data/rasters_se/cut_fact_12m5.tif -- uint8, aligned to grid_se.GridSE.

Usage: python ml/ingest/fetch_skogsstyrelsen_harvests.py [declared|fact|all]
"""
import argparse, os, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
RAW = os.path.join(ML, "data", "raw")
RASTERS = os.path.join(ML, "data", "rasters_se")
BASE = "https://geodpags.skogsstyrelsen.se/geodataport/data"

DECLARED_FELLING_TYPE = "Föryngringsavverkning"     # regeneration felling, confirmed value
FACT_LAYER = "UtfordAvverkningYta"                  # confirmed against the real 7.5 GB gpkg
FACT_FIELD_CANDIDATES = ["Avverktyp", "AVVERKTYP", "Skogstyp"]   # Avverktyp confirmed correct
FACT_FELLING_TYPE = "Föryngringsavverkning"         # confirmed: 94% of records


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def download(name):
    """name: 'AvverkAnm' (declared, 67 MB) or 'UtfordAvverk' (fact, 2.7 GB)."""
    os.makedirs(RAW, exist_ok=True)
    url = f"{BASE}/sks{name}_gpkg.zip"
    zpath = os.path.join(RAW, f"sks{name}.zip")
    gpkg = os.path.join(RAW, f"sks{name}.gpkg")
    if os.path.exists(gpkg):
        log(name, "already downloaded"); return gpkg
    import subprocess
    subprocess.run(["curl", "-sS", "-C", "-", "--retry", "5", "--retry-delay", "3",
                    "--max-time", "10800", "-o", zpath, url], check=True)
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if n.endswith(".gpkg")]
        if not names:
            raise RuntimeError(f"no geopackage in {zpath}")
        z.extract(names[0], RAW)
        os.replace(os.path.join(RAW, names[0]), gpkg)
    os.remove(zpath)
    log(name, "downloaded and extracted", gpkg)
    return gpkg


def rasterize_layer(gpkg, layer, field_candidates, match_value, date_field, value, out_name):
    import fiona, rasterio, shapely
    from rasterio.features import rasterize as rio_rasterize
    from rasterio.windows import transform as win_transform
    from shapely.strtree import STRtree
    sys.path.insert(0, os.path.join(ML, "core"))
    from grid_se import GridSE, env

    available = fiona.listlayers(gpkg)
    if layer not in available:
        log("layer name guess", repr(layer), "not found; available:", available,
            "-- using", available[0], "instead")
        layer = available[0]
    with fiona.open(gpkg, layer=layer) as src:
        props = src.schema["properties"]
        field = next((f for f in field_candidates if f in props), None)
        if field is None:
            raise RuntimeError(f"none of {field_candidates} found in {layer}; has: {sorted(props)}. "
                               "Update the field candidates in fetch_skogsstyrelsen_harvests.py.")
        log("using field", field, "on", layer, "(", len(props), "columns total )")
        geoms = []
        for feat in src:
            p = feat["properties"]
            if p.get(field) != match_value:
                continue
            g = feat.geometry
            if g is None:
                continue
            geoms.append(shapely.geometry.shape(g))
    log(layer, "kept", len(geoms), "of", "?", "features")
    if not geoms:
        raise RuntimeError(f"no features matched {field}={match_value!r} in {layer} -- check the value")

    tree = STRtree(geoms)
    grid = GridSE()
    os.makedirs(RASTERS, exist_ok=True)
    out = os.path.join(RASTERS, out_name)
    with env():
        with rasterio.open(out, "w", **grid.profile("uint8", nodata=0)) as dst:
            for k, w in enumerate(grid.blocks(4096)):
                x0, y0 = grid.transform * (w.col_off, w.row_off + w.height)
                x1, y1 = grid.transform * (w.col_off + w.width, w.row_off)
                hits = tree.query(shapely.box(x0, y0, x1, y1))
                if len(hits) == 0:
                    continue
                shapes = [(geoms[i], value) for i in hits]
                arr = rio_rasterize(shapes, out_shape=(w.height, w.width),
                                    transform=win_transform(w, grid.transform), fill=0, dtype="uint8")
                dst.write(arr, 1, window=w)
                if k % 20 == 0: log(out_name, "block", k)
    log("raster written", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("which", nargs="?", default="all", choices=["declared", "fact", "all"])
    a = ap.parse_args()
    if a.which in ("declared", "all"):
        gpkg = download("AvverkAnm")
        rasterize_layer(gpkg, "AvverkningsAnmalanYta", ["Avverktyp"], DECLARED_FELLING_TYPE,
                        "Inkomdatum", 1, "cut_declared_12m5.tif")
    if a.which in ("fact", "all"):
        gpkg = download("UtfordAvverk")
        rasterize_layer(gpkg, FACT_LAYER, FACT_FIELD_CANDIDATES, FACT_FELLING_TYPE,
                        "Avvdatum", 2, "cut_fact_12m5.tif")
    log("DONE")


if __name__ == "__main__":
    sys.exit(main())
