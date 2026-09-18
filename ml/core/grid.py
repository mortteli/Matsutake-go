"""The common 16 m analysis grid: Luke MVMI 2023 raster geometry (ETRS-TM35FIN, EPSG:3067)."""
import os
import rasterio
from rasterio.env import Env
from rasterio.windows import Window

PAITULI = "https://www.nic.funet.fi/index/geodata"
LUKE = PAITULI + "/luke/vmi"
DEM_VRT = "/vsicurl/" + PAITULI + "/mml/dem10m/dem10m_direct.vrt"

# MVMI cycle -> (folder, filename infix). The app's "_1923" is the 2023 product.
CYCLES = {
    2009: ("2009", ""),
    2011: ("2011", "_0711"),
    2013: ("2013", "_vmi11_0913"),
    2015: ("2015", "_vmi1x_1216"),
    2017: ("2017", "_vmi1x_1317"),
    2019: ("2019", "_vmi1x_1519"),
    2021: ("2021", "_vmi1x_1721"),
    2023: ("2023", "_vmi1x_1923"),
}

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


def cycle_for_year(year):
    """Latest MVMI cycle whose year <= observation year (2009 for older finds)."""
    if year is None:
        return 2023
    cands = [c for c in CYCLES if c <= year]
    return max(cands) if cands else 2009


def luke_url(theme, cycle=2023):
    folder, infix = CYCLES[cycle]
    return f"/vsicurl/{LUKE}/{folder}/{theme}{infix}.tif"


def env():
    return Env(**GDAL_ENV)


class Grid:
    """Geometry of the MVMI 16 m grid, read once from the 2023 site-class raster."""

    def __init__(self):
        with env():
            with rasterio.open(luke_url("kasvupaikka")) as ds:
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
