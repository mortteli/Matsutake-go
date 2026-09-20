"""Warp Copernicus DEM GLO-30 onto a 25 m Swedish cache, so training and inference read
identical elevation values from local disk.

Mirrors build_dem16.py for Sweden, with three differences that are all forced by the data.

WHY COPERNICUS AND NOT LANTMATERIET
    Sweden's 1 m national elevation model is CC0 and is the right answer, but it is served
    from opendata.lantmateriet.se behind a free account that cannot be registered from this
    container. Copernicus GLO-30 is open, needs no account, is served as COGs from a public
    S3 bucket, and covers Sweden in 1-degree tiles of about 21 MB. It costs resolution: 30 m
    against Finland's 10 m.

WHY 25 m AND NOT 12.5 m
    The source is 30 m. A cache on the full 12.5 m analysis grid would be 6.48e9 cells of
    pure upsampling -- 13 GB raw -- to hold no more information than 26300 x 61600 at 25 m
    does. features_se.py wraps this in a WarpedVRT to 12.5 m at read time, identically for a
    training pixel and an inference pixel, which is the invariant that actually matters.

WHY IT WARPS FROM /vsicurl RATHER THAN DOWNLOADING THE TILES
    Downloading all ~200 tiles first costs 4.2 GB of peak disk. The Swedish pipeline shares
    a 29 GB disk with two geopackages that peak at 17 GB on their own, so the tiles are read
    over range requests straight into the warp and never land on disk. The block loop is
    restartable through <out>.progress, which is what makes that safe over a long run.

CAVEAT: GLO-30 IS A SURFACE MODEL
    It is a DSM, not a DTM: over 25 m forest it sits somewhere between canopy and ground,
    and the offset varies with the stand structure the model is trying to predict. That is
    why features_se.py drops the short-range relief feature Finland has and smooths the
    surface to about 100 m before differencing -- see the note there.

Output: ml/data/rasters_se/dem_25m.tif  (int16 decimetres, nodata -32768)
Usage:  python ml/ingest/build_dem_se.py [--vrt-only]
"""
import argparse, os, sys, time, urllib.request
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.transform import from_origin

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ML, "core"))
from grid_se import GridSE, PIXEL_M, ORIGIN_X, ORIGIN_Y, WIDTH, HEIGHT, env

RASTERS = os.path.join(ML, "data", "rasters_se")
OUT = os.path.join(RASTERS, "dem_25m.tif")
VRT = os.path.join(RASTERS, "copernicus_glo30.vrt")
NODATA = -32768
BLOCK = 2048                                  # on the 25 m cache grid

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
# Sweden plus a margin, so bilinear resampling at the border has neighbours to work with.
LAT_RANGE = range(54, 71)
LON_RANGE = range(9, 26)

# The 25 m cache is an exact 2x decimation of the 12.5 m analysis grid, so the WarpedVRT
# back up to 12.5 m in features_se.py is a clean 1:2 and introduces no new registration.
DEM_PIXEL_M = PIXEL_M * 2
DEM_WIDTH, DEM_HEIGHT = WIDTH // 2, HEIGHT // 2


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def tile_url(lat, lon):
    n = f"Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM"
    return f"{BUCKET}/{n}/{n}.tif"


def exists(url):
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30)
        return True
    except Exception:                                          # noqa: BLE001 -- 404 means no tile
        return False


def build_vrt():
    """A GDAL VRT over the /vsicurl tiles that cover Sweden."""
    urls = []
    for lat in LAT_RANGE:
        for lon in LON_RANGE:
            u = tile_url(lat, lon)
            if exists(u):
                urls.append("/vsicurl/" + u)
        log(f"  N{lat}: {len(urls)} tiles so far")
    if not urls:
        raise SystemExit("no Copernicus tiles resolved -- is the bucket reachable?")
    log("tiles", len(urls))
    os.makedirs(RASTERS, exist_ok=True)
    from osgeo import gdal                                     # optional; fall back below
    gdal.BuildVRT(VRT, urls)
    return VRT


def build_vrt_no_gdal():
    """Same VRT without the osgeo bindings, which rasterio does not install.

    Every GLO-30 tile is a 1-degree WGS84 grid with the same pixel size, so the mosaic
    geometry can be written out directly rather than probed file by file over the network.
    """
    urls = []
    for lat in LAT_RANGE:
        for lon in LON_RANGE:
            u = tile_url(lat, lon)
            if exists(u):
                urls.append((lat, lon, u))
        log(f"  N{lat}: {len(urls)} tiles so far")
    if not urls:
        raise SystemExit("no Copernicus tiles resolved -- is the bucket reachable?")
    log("tiles", len(urls))

    with env(), rasterio.open("/vsicurl/" + urls[0][2]) as s0:
        res_y = -s0.transform.e                                 # constant across the product
        nodata = s0.nodata
        dtype = s0.dtypes[0]
    lat0, lat1 = min(u[0] for u in urls), max(u[0] for u in urls) + 1
    lon0, lon1 = min(u[1] for u in urls), max(u[1] for u in urls) + 1
    W = int(round((lon1 - lon0) / res_y))
    H = int(round((lat1 - lat0) / res_y))

    os.makedirs(RASTERS, exist_ok=True)
    parts = [
        f'<VRTDataset rasterXSize="{W}" rasterYSize="{H}">',
        '  <SRS>EPSG:4326</SRS>',
        f'  <GeoTransform>{lon0}, {res_y}, 0, {lat1}, 0, {-res_y}</GeoTransform>',
        f'  <VRTRasterBand dataType="Float32" band="1">',
        f'    <NoDataValue>{nodata if nodata is not None else -32767}</NoDataValue>',
    ]
    for lat, lon, u in urls:
        with env(), rasterio.open("/vsicurl/" + u) as s:
            sw, sh = s.width, s.height
        xoff = int(round((lon - lon0) / res_y))
        yoff = int(round((lat1 - (lat + 1)) / res_y))
        parts += [
            '    <ComplexSource>',
            f'      <SourceFilename relativeToVRT="0">/vsicurl/{u}</SourceFilename>',
            '      <SourceBand>1</SourceBand>',
            f'      <SrcRect xOff="0" yOff="0" xSize="{sw}" ySize="{sh}"/>',
            f'      <DstRect xOff="{xoff}" yOff="{yoff}" xSize="{sw}" ySize="{sh}"/>',
            *([f'      <NODATA>{nodata}</NODATA>'] if nodata is not None else []),
            '    </ComplexSource>',
        ]
    parts += ['  </VRTRasterBand>', '</VRTDataset>']
    open(VRT, "w").write("\n".join(parts))
    log("wrote", VRT, f"{W} x {H}", dtype)
    return VRT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vrt-only", action="store_true", help="build the tile VRT and stop")
    a = ap.parse_args()

    if not os.path.exists(VRT):
        try:
            build_vrt()
        except ImportError:
            build_vrt_no_gdal()
    else:
        log("reusing", VRT)
    if a.vrt_only:
        return

    grid = GridSE()
    transform = from_origin(ORIGIN_X, ORIGIN_Y, DEM_PIXEL_M, DEM_PIXEL_M)
    prof = dict(driver="GTiff", dtype="int16", count=1, crs=grid.crs, transform=transform,
                width=DEM_WIDTH, height=DEM_HEIGHT, nodata=NODATA, tiled=True,
                blockxsize=512, blockysize=512, compress="deflate", predictor=2,
                BIGTIFF="IF_SAFER")

    prog = OUT + ".progress"
    done = set(open(prog).read().split()) if os.path.exists(prog) else set()
    mode = "r+" if (os.path.exists(OUT) and done) else "w"

    windows = []
    for row in range(0, DEM_HEIGHT, BLOCK):
        for col in range(0, DEM_WIDTH, BLOCK):
            windows.append(rasterio.windows.Window(
                col, row, min(BLOCK, DEM_WIDTH - col), min(BLOCK, DEM_HEIGHT - row)))

    with env():
        src = rasterio.open(VRT)
        vrt = WarpedVRT(src, crs=grid.crs, transform=transform, width=DEM_WIDTH,
                        height=DEM_HEIGHT, resampling=Resampling.bilinear,
                        src_nodata=src.nodata, nodata=src.nodata)
        with rasterio.open(OUT, mode, **(prof if mode == "w" else {})) as dst, open(prog, "a") as pf:
            todo = [w for w in windows if f"{w.row_off},{w.col_off}" not in done]
            log("blocks to do", len(todo), "of", len(windows))
            for i, w in enumerate(todo):
                t0 = time.time()
                arr = vrt.read(1, window=w).astype("float32")
                # -9999 sea fill and the blend at tile edges; Sweden tops out at 2097 m
                bad = ~np.isfinite(arr) | (arr < -50) | (arr > 2500)
                out = np.where(bad, NODATA, np.round(arr * 10)).astype("int16")
                dst.write(out, 1, window=w)
                pf.write(f"{w.row_off},{w.col_off}\n"); pf.flush()
                if i % 5 == 0:
                    log(f"{i}/{len(todo)} valid {float((~bad).mean()):.2f} {time.time() - t0:.0f}s")
        vrt.close(); src.close()

    with rasterio.open(OUT, "r+") as dst:
        dst.build_overviews([2, 4, 8, 16, 32], Resampling.average)
    open(OUT + ".ok", "w").close()          # features_se.py only trusts a completed warp
    log("DONE", OUT, f"{os.path.getsize(OUT) / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
