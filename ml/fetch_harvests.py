"""Where the forest in the MVMI raster is no longer standing.

Luke's MVMI is a snapshot: the published map describes the forest as the 2019-2023 inventory
found it. A stand harvested since then still reads as whatever it was before the machines came,
and because regeneration cutting targets *old* stands the error lands hardest exactly where the
model is most confident. This writes the correction as its own 16 m raster, aligned cell for cell
with data/<species>/prob_*.tif, so the app can grey out ground that is gone without the score
underneath being touched:

    0  no signal
    1  a regeneration felling was DECLARED after the inventory  -- an intention
    2  the stand register says the ground is open or seedling   -- a fact

The two codes are not interchangeable and 1 never becomes 2. A metsankayttoilmoitus is filed at
least 10 days before cutting, is valid for three years, and per Metsakeskus's own product
description is "luonteeltaan hakkuuaikomus. Ilmoitettua toimenpidetta ei ole velvoite tehda."
Cross-tabulated against the stand register around Tampere, 57 % of regeneration declarations
filed since 2021 sit on ground that is now open or seedling -- but 36 % are still standing mature
forest, so deleting on a declaration alone would wrongly erase over a third of it. Declarations
of kasvatushakkuu land on a young stand only 6 % of the time and are ignored outright: a thinned
forest is still a forest.

The stand register is the other way round. Metsakeskus updates it primarily from the harvesting
machine's own telemetry -- date, cutting method, and a boundary traced from the machine's GPS --
so it is fact, but it covers privately owned forest only. Declarations reach the rest, which is
why both are here even though only one of them removes anything.

Grid: taken from data/<species>/prob_meta.json rather than from Luke, so the correction is by
construction aligned to the layer it corrects.

    python ml/fetch_harvests.py --species matsutake            # all regions
    python ml/fetch_harvests.py --species matsutake --regions Pirkanmaa
"""
import argparse, json, os, shutil, subprocess, sys, time, zipfile

import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))

BASE = "https://avoin.metsakeskus.fi/aineistot"
PIXEL_M = 16

# The oldest date at which the 1923 cycle's imagery could already show a change; anything
# declared after it may be missing from the raster the map is built on. Kept in step with
# MVMI_EFFECTIVE in index.html.
MVMI_EFFECTIVE = "2021-01-01"

# metsatietostandardi kehitysluokka: aukea, siemenpuumetsikko, taimikot under and over 1.3 m.
# Y1 (ylispuustoinen taimikko) is deliberately absent -- it keeps an overstory that may still be
# old pine, and unlike these four it is not by itself proof that the stand was reset.
CUT_DEVCLASS = ("A0", "S0", "T1", "T2")
REGEN = 3          # cuttingpurpose: uudistushakkuu

CUT_DECLARED = 1
CUT_FACT = 2

# Metsakeskus splits Lapland in two and ships the rest by maakunta.
REGIONS = [
    "Etelä-Karjala", "Etelä-Pohjanmaa", "Etelä-Savo", "Kainuu", "Kanta-Häme",
    "Keski-Pohjanmaa", "Keski-Suomi", "Kymenlaakso", "Lappi_E", "Lappi_P",
    "Pirkanmaa", "Pohjanmaa", "Pohjois-Karjala", "Pohjois-Pohjanmaa", "Pohjois-Savo",
    "Päijät-Häme", "Satakunta", "Uusimaa", "Varsinais-Suomi",
]

# The bulk GeoPackages spell their columns in lower case, unlike the WFS.
#
# The predicates are plain Python on purpose. This fiona build accepts `where=` and `bbox=` and
# then silently ignores both — it yields the whole layer and reports the whole layer's length,
# so a filter that is quietly doing nothing looks exactly like one that works. Filtering here
# cannot fail that way, and it is why each layer is read in one pass below rather than once per
# part: without a working bbox, a second pass would be a second full scan.
SETS = {
    # key: (url folder, file prefix, geopackage layer, predicate on the property dict)
    "stand": ("Metsavarakuviot", "MV", "stand",
              lambda p: p.get("developmentclass") in CUT_DEVCLASS),
    "mki":   ("Metsankayttoilmoitukset", "MKI", "forestusedeclaration",
              lambda p: p.get("cuttingpurpose") == REGEN
                        and (p.get("declarationarrivaldate") or "") >= MVMI_EFFECTIVE),
}

FLUSH_SHAPES = 40000       # burn and drop, so a region's geometries never all sit in memory


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


class Part:
    """One published tile of the map, held as a disk-backed array while regions stream past."""

    def __init__(self, name, bounds, work):
        self.name = name
        x0, y0, x1, y1 = bounds
        self.bounds = bounds
        self.width = int(round((x1 - x0) / PIXEL_M))
        self.height = int(round((y1 - y0) / PIXEL_M))
        self.transform = from_origin(x0, y1, PIXEL_M, PIXEL_M)
        self.path = os.path.join(work, name + ".dat")
        self.arr = np.memmap(self.path, dtype=np.uint8, mode="w+",
                             shape=(self.height, self.width))
        self.arr[:] = 0

    def intersects(self, b):
        return not (b[2] <= self.bounds[0] or b[0] >= self.bounds[2] or
                    b[3] <= self.bounds[1] or b[1] >= self.bounds[3])

    def burn(self, shapes, value, scratch):
        """Rasterize into a scratch buffer, then merge under this layer's precedence rules.

        Going through a scratch array rather than straight into `arr` is what keeps the merge
        order-independent: a fact always wins, and an intention only ever fills ground no fact
        has claimed, no matter which region happened to be downloaded first.
        """
        buf = scratch[:self.height, :self.width]      # parts differ by a row; share one buffer
        buf[:] = 0
        rasterize(((g, 1) for g in shapes), out=buf, transform=self.transform,
                  all_touched=False, default_value=1)
        hit = buf == 1
        np.putmask(self.arr, hit if value == CUT_FACT else hit & (self.arr == 0), value)


def download(folder, prefix, region, work):
    """Fetch one region's GeoPackage. The listing 301s to S3, so redirects must be followed."""
    url = f"{BASE}/{folder}/Maakunta/{prefix}_{region}.zip"
    zpath = os.path.join(work, f"{prefix}_{region}.zip")
    subprocess.run(["curl", "-sSL", "--fail", "--retry", "4", "--retry-delay", "3",
                    "--max-time", "1800", "-o", zpath, url], check=True)
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if n.endswith(".gpkg")]
        if not names:
            raise RuntimeError(f"no geopackage in {zpath}")
        z.extract(names[0], work)
    os.remove(zpath)
    return os.path.join(work, names[0])


def geom_bbox(g):
    """Bounding box of a GeoJSON-ish geometry, from its rings alone.

    The exterior ring contains every interior one, so walking all rings is wasteful but always
    right, and this runs once per feature — cheaper than building a shapely object per polygon.
    """
    xs0 = ys0 = float("inf")
    xs1 = ys1 = float("-inf")
    rings = g["coordinates"] if g["type"] == "Polygon" else [r for poly in g["coordinates"] for r in poly]
    for ring in rings:
        for x, y in ring:
            if x < xs0: xs0 = x
            if x > xs1: xs1 = x
            if y < ys0: ys0 = y
            if y > ys1: ys1 = y
    return (xs0, ys0, xs1, ys1)


def burn_region(gpkg, layer, keep, parts, value, scratch):
    """One pass over the layer, fanning each kept polygon into every part it touches.

    One pass rather than one per part because this fiona ignores `bbox` (see SETS): a per-part
    read would rescan the whole region for every tile of the map it happens to straddle.
    """
    import fiona
    buckets = [[] for _ in parts]
    kept = 0

    def flush():
        for part, shapes in zip(parts, buckets):
            if shapes:
                part.burn(shapes, value, scratch)
                shapes.clear()

    with fiona.open(gpkg, layer=layer) as src:
        for feat in src:
            if not keep(feat["properties"]):
                continue
            g = feat.geometry
            if g is None:
                continue
            bb = geom_bbox(g)
            for i, part in enumerate(parts):
                if part.intersects(bb):
                    buckets[i].append(g)
            kept += 1
            if kept % FLUSH_SHAPES == 0:
                flush()
    flush()
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--regions", nargs="*", default=REGIONS)
    ap.add_argument("--sets", nargs="*", default=["stand", "mki"], choices=list(SETS))
    ap.add_argument("--work", default=os.path.join(HERE, "data", "harvests"))
    ap.add_argument("--keep-work", action="store_true")
    a = ap.parse_args()

    meta_path = os.path.join(ROOT, "data", a.species, "prob_meta.json")
    with open(meta_path) as fh:
        meta = json.load(fh)
    os.makedirs(a.work, exist_ok=True)

    parts = []
    for f in meta["files"]:
        name = os.path.basename(f["url"]).replace("prob_", "cut_").replace(".tif", "")
        parts.append(Part(name, f["bounds"], a.work))
    log(f"{len(parts)} parts, up to {max(p.width for p in parts)} x "
        f"{max(p.height for p in parts)} cells each")
    scratch = np.zeros((max(p.height for p in parts), max(p.width for p in parts)), dtype=np.uint8)

    # Facts first, so that within a region an intention can already see them; the merge rule in
    # Part.burn keeps the result the same whatever order the regions arrive in.
    for key in ("stand", "mki"):
        if key not in a.sets:
            continue
        folder, prefix, layer, keep = SETS[key]
        value = CUT_FACT if key == "stand" else CUT_DECLARED
        for region in a.regions:
            t0 = time.time()
            gpkg = download(folder, prefix, region, a.work)
            try:
                rb = bounds_of(gpkg, layer)
                touched = [p for p in parts if p.intersects(rb)]
                n = burn_region(gpkg, layer, keep, touched, value, scratch)
            finally:
                os.remove(gpkg)
            log(f"  {prefix:4s} {region:18s} {n:8d} kept  {time.time()-t0:5.0f}s")

    out_dir = os.path.join(ROOT, "data", a.species)
    files = []
    for part in parts:
        part.arr.flush()
        path = os.path.join(out_dir, part.name + ".tif")
        write_cog(part, path)
        files.append({"url": f"data/{a.species}/{part.name}.tif", "bounds": part.bounds})
        log(f"  wrote {part.name}.tif  {os.path.getsize(path)/1e6:.1f} MB")

    meta["cut"] = {
        "files": files,
        "values": {"1": "declared regeneration felling, unconfirmed", "2": "open or seedling stand"},
        "since": MVMI_EFFECTIVE,
        "source": "Suomen metsakeskus: metsavarakuviot + metsankayttoilmoitukset (CC BY 4.0)",
        "built": time.strftime("%Y-%m-%d"),
    }
    with open(meta_path, "w") as fh:
        json.dump(meta, fh, separators=(",", ":"))
    log("updated", os.path.relpath(meta_path, ROOT))

    if not a.keep_work:
        shutil.rmtree(a.work, ignore_errors=True)


def bounds_of(gpkg, layer):
    import fiona
    with fiona.open(gpkg, layer=layer) as src:
        return src.bounds


def write_cog(part, path):
    """Same COG recipe as ml/export_app.py, so the app reads both layers the same way."""
    from rasterio.shutil import copy as rio_copy
    tmp = path + ".tmp.tif"
    # nodata 255 matches the probability parts even though this layer never stores it:
    # georaster-layer-for-leaflet refuses to draw two rasters together unless every one of
    # height, width, noDataValue, pixelWidth, projection and the corners agrees.
    with rasterio.open(tmp, "w", driver="GTiff", width=part.width, height=part.height,
                       count=1, dtype="uint8", crs="EPSG:3067", transform=part.transform,
                       nodata=255, tiled=True, blockxsize=512, blockysize=512,
                       compress="deflate", predictor=2, BIGTIFF="IF_SAFER") as dst:
        for r in range(0, part.height, 4096):
            h = min(4096, part.height - r)
            dst.write(np.asarray(part.arr[r:r + h]), 1,
                      window=rasterio.windows.Window(0, r, part.width, h))
    # NEAREST, not AVERAGE: these are class codes, and an averaged overview would invent a 1
    # ("declared") along every boundary between cut ground and standing forest.
    rio_copy(tmp, path, driver="COG", COMPRESS="DEFLATE", PREDICTOR="YES", LEVEL=9,
             BLOCKSIZE=512, OVERVIEW_RESAMPLING="NEAREST", BIGTIFF="IF_SAFER")
    os.remove(tmp)


if __name__ == "__main__":
    sys.exit(main())
