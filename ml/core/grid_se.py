"""The Swedish analysis grid: SLU forest map 2015 raster geometry (SWEREF99 TM, EPSG:3006).

Mirrors grid.py's Grid class for Finland. Rasters are served as plain static files from SLU's
own GIS server (no login, no WMS wrapper) so /vsicurl/ reads work exactly like Paituli's mirror
of Luke's MVMI does for Finland — this module only ever reads header metadata over HTTP range
requests, never the whole file.
"""
import rasterio
from rasterio.env import Env
from rasterio.windows import Window

SLU_FOREST_MAP = "/vsicurl/https://gis.slu.se/data/slu_forest_map"

# 2015 vintage, 12.5 m: basal area, mean diameter, mean height, biomass, volume by species group
# (pine / spruce / other deciduous — no birch/oak/beech split) and total volume.
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

# 2018 vintage, species share of volume (0-100%): splits deciduous further than 2015 does.
ANDEL_2018 = {
    "share_pine": "Tall_andel.tif",
    "share_spruce": "Gran_andel.tif",
    "share_birch": "Bjork_andel.tif",
    "share_oak": "Ek_andel.tif",
    "share_beech": "Bok_andel.tif",
    "share_contorta": "Contorta_andel.tif",
    "share_other_deciduous": "OvrLov_andel.tif",
}

# 2010 vintage, 25 m, RT90 2.5 gon V (EPSG:3021) — reproject before use. The only vintage with
# an age raster; ~15 years stale by the time anyone trains on it, same caveat as Finland's older
# MVMI cycles but with no newer replacement documented yet.
AGE_2010_RT90 = "AGE_XX_P_10.tif"

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


def andel_url(name, year=2018):
    return f"{SLU_FOREST_MAP}/{year}/data/{ANDEL_2018[name]}"


def age_url():
    return f"{SLU_FOREST_MAP}/2010/Data/Raster/Rt90/{AGE_2010_RT90}"


class GridSE:
    """Geometry of the SLU forest map 12.5 m grid, read once from the 2015 total-volume raster."""

    def __init__(self):
        with env():
            with rasterio.open(leaf_url("vol_total")) as ds:
                self.crs = ds.crs
                self.transform = ds.transform
                self.width = ds.width
                self.height = ds.height
                self.nodata = ds.nodata
                self.bounds = ds.bounds

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
    print("size:", g.width, "x", g.height)
    print("bounds:", g.bounds)
    print("nodata:", g.nodata)
