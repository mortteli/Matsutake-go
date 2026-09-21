"""The Swedish analysis grid: SWEREF99 TM (EPSG:3006) at 12.5 m, covering the whole country.

Mirrors grid.py's Grid class for Finland.

WHICH GEOMETRY, AND WHY NOT THE 2015 ONE
----------------------------------------
This module used to read its geometry from the SLU 2015 "leaf" total-volume raster over
/vsicurl. That raster is 52400 x 97400 at 12.5 m from (267500, 7350000), so it stops at
northing 7350000 -- about 66.3 N on the central meridian, and lower further east. SLU
clipped it to the laser coverage of the day and cut Gotland out by name. Reprojecting our
5501 Swedish matsutake records onto it, 1508 of them (27 %) land outside: 939 fine
presences in Lule lappmark, 271 in Torne lappmark, 216 in Norrbotten -- the densest
matsutake ground in Sweden. A grid derived from that raster discards them silently.

The grid below is the SLU 2018 geometry, which does cover the whole country. Nothing reads
the 2018 rasters themselves (they are strip-compressed at 52600 px per strip and 3.5 GB a
file -- see download_slu_forestmap.sh), but their footprint is the national extent, and the
2015 raster tiles into it exactly:

    (267500 - 265000) / 12.5  = 200      exact
    (7672500 - 7350000) / 12.5 = 25800   exact

so the 2015 raster is Window(200, 25800, 52400, 97400) of this grid, with no resampling.
That keeps a south-only 12.5 m refinement experiment cheap if it is ever wanted.

The geometry is hard-coded rather than read from a remote header: GridSE() is constructed
by every ingest, dataset, training and inference script, and the old version made a network
call to gis.slu.se on each one. The numbers are asserted against the real raster by
ml/ingest/check_grid_se.py.
"""
import rasterio
from rasterio.env import Env
from rasterio.transform import from_origin
from rasterio.windows import Window

SLU_FOREST_MAP = "/vsicurl/https://gis.slu.se/data/slu_forest_map"

# 2010 vintage, 25 m, RT90 2.5 gon V (EPSG:3021), tiled 128x128, nodata 65535. The feature
# spine: national coverage including Gotland (top northing 7636500), separate birch volume,
# and the only vintage with an age raster. Downloaded by download_slu_forestmap.sh.
RT90_2010 = {
    "age": "AGE",
    "height": "HEIGHT",
    "vol_total": "TOTALVOL",
    "vol_pine": "PINEVOL",
    "vol_spruce": "SPRUCEVOL",
    "vol_birch": "BIRCHVOL",
    "vol_decid": "DECIDUOUSVOL",
    "vol_contorta": "CONTORTAVOL",
}
# observation_status_se.py needs a second vintage to compare a stand against; only these two
# are fetched, because only these two feed a change rule.
RT90_2005 = {"age": "AGE", "vol_total": "TOTALVOL"}

SLU_NODATA = 65535          # one value for both "not forest land" and "no estimate" --
                            # see slu_point.py for why that costs us a classification state

# 2015 vintage, 12.5 m, SWEREF99 TM. South of 66.3 N only; not part of FEATURES_SE. Kept so
# features_se.py can validate its estimated basal area against the real BA_leaf raster.
LEAF_2015 = {
    "basal_area": "BA_leaf.tif",
    "biomass": "Biomass_leaf.tif",
    "mean_diameter": "DGV_leaf.tif",
    "mean_height": "HGV_leaf.tif",
    "vol_spruce": "GranVol_leaf.tif",
    "vol_pine": "TallVol_leaf.tif",
    "vol_deciduous": "LovVol_leaf.tif",
    "vol_total": "VolTot_leaf.tif",
}
LEAF_2015_WINDOW = Window(200, 25800, 52400, 97400)     # where LEAF_2015 sits in this grid

CRS = "EPSG:3006"
RT90 = "EPSG:3021"
PIXEL_M = 12.5
WIDTH, HEIGHT = 52600, 123200
ORIGIN_X, ORIGIN_Y = 265000.0, 7672500.0                # top-left

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.vrt",
    GDAL_HTTP_MAX_RETRY="5",
    GDAL_HTTP_RETRY_DELAY="3",
    GDAL_HTTP_TIMEOUT="90",
    GDAL_HTTP_CONNECTTIMEOUT="20",
    GDAL_HTTP_MULTIPLEX="YES",
    VSI_CACHE="TRUE",
    VSI_CACHE_SIZE=str(512 * 1024 * 1024),
)


def env():
    return Env(**GDAL_ENV)


def leaf_url(name, year=2015):
    return f"{SLU_FOREST_MAP}/{year}/data/{LEAF_2015[name]}"


def rt90_path(theme, vintage=2010, local_dir=None):
    """Local file written by download_slu_forestmap.sh, or the remote URL if absent."""
    import os
    table = RT90_2010 if vintage == 2010 else RT90_2005
    if local_dir:
        local = os.path.join(local_dir, f"{vintage}_{table[theme]}.tif")
        if os.path.exists(local + ".ok"):
            return local
    return f"{SLU_FOREST_MAP}/{vintage}/Data/Raster/Rt90/{table[theme]}_XX_P_{vintage % 100:02d}.tif"


# --------------------------------------------------------------------------- RT90 guard
# EPSG:3021 -> EPSG:3006 is a real datum change and needs Sweden's 7-parameter Helmert
# ("RT90 to SWEREF99 (1)", EPSG:9.5.1 accuracy 0.1 m). PROJ ships it, but if its EPSG
# database or proj-data cannot be resolved PROJ silently falls back to a ballpark
# transformation that changes the projection parameters and skips the datum shift. That is
# not an error and raises nothing -- it just returns coordinates wrong by about 200 m.
# Measured here against a deliberately datum-less pipeline, the fallback is off by 198 m at
# (1500000, 7000000) and 244 m at (1700000, 7400000): eight to ten cells of the 25 m age
# raster, applied to every single feature read in the country.
#
# The control values below were computed with the correct operation and are checked, not
# quoted -- run this module to reprint them.
_RT90_CONTROL = [
    ((1500000.0, 7000000.0), (540621.7, 6998082.7)),
    ((1700000.0, 7400000.0), (735449.8, 7400479.9)),
]


def assert_rt90_transform(tol=5.0):
    """Raise if PROJ resolved EPSG:3021->EPSG:3006 without the Swedish datum shift.

    Returns the worst control-point residual in metres.
    """
    from pyproj import Transformer
    tr = Transformer.from_crs(RT90, CRS, always_xy=True)
    worst = 0.0
    for (sx, sy), (ex, ey) in _RT90_CONTROL:
        gx, gy = tr.transform(sx, sy)
        worst = max(worst, ((gx - ex) ** 2 + (gy - ey) ** 2) ** 0.5)
    if worst > tol:
        raise RuntimeError(
            f"EPSG:3021->EPSG:3006 is off by {worst:.0f} m at a control point. PROJ has most "
            f"likely fallen back to a ballpark transformation without the RT90->SWEREF99 "
            f"Helmert, which displaces every SLU 2010 reading by roughly 200 m. PROJ chose: "
            f"{tr.description!r} (accuracy {tr.accuracy}). Check pyproj's PROJ data directory."
        )
    return worst


class GridSE:
    """Geometry of the national Swedish 12.5 m analysis grid (SWEREF99 TM)."""

    def __init__(self):
        self.crs = rasterio.crs.CRS.from_string(CRS)
        self.transform = from_origin(ORIGIN_X, ORIGIN_Y, PIXEL_M, PIXEL_M)
        self.width = WIDTH
        self.height = HEIGHT
        self.nodata = SLU_NODATA
        self.bounds = rasterio.coords.BoundingBox(
            ORIGIN_X, ORIGIN_Y - HEIGHT * PIXEL_M, ORIGIN_X + WIDTH * PIXEL_M, ORIGIN_Y)

    def profile(self, dtype="uint8", nodata=0, count=1):
        return dict(driver="GTiff", dtype=dtype, count=count, crs=self.crs, transform=self.transform,
                    width=self.width, height=self.height, nodata=nodata, tiled=True,
                    blockxsize=512, blockysize=512, compress="deflate", predictor=2, BIGTIFF="IF_SAFER")

    def blocks(self, size=4096):
        for row in range(0, self.height, size):
            for col in range(0, self.width, size):
                yield Window(col, row, min(size, self.width - col), min(size, self.height - row))

    def xy_to_rowcol(self, x, y):
        col, row = ~self.transform * (x, y)
        return int(row), int(col)


if __name__ == "__main__":
    g = GridSE()
    print("crs:", g.crs)
    print("transform:", g.transform)
    print("size:", g.width, "x", g.height, f"({g.width * g.height / 1e9:.2f}e9 cells)")
    print("bounds:", g.bounds)
    print("rt90 control residual:", f"{assert_rt90_transform():.1f} m")
