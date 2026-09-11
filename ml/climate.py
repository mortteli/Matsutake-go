"""Static climate normals from FMI's open 10 km monthly grids (Paituli):
  thermal sum (effective temperature sum, degree days > 5 °C, 1991–2020 mean)
  annual precipitation (mm, 1991–2020 mean)
Written as small GeoTIFFs to ml/data/climate/ (committed).
"""
import calendar, os, re, sys, time, urllib.request
import numpy as np, rasterio
from rasterio.env import Env

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "climate")
BASE = "https://www.nic.funet.fi/index/geodata/ilmatiede"
YEARS = range(1991, 2021)


def listing(url):
    html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "ignore")
    return re.findall(r'href="([^"?/]+\.tif)"', html)


def read_year(url):
    with Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(url) as ds:
            return ds.read().astype("float64"), ds.profile, ds.nodata


def main():
    os.makedirs(OUT, exist_ok=True)
    tdir = BASE + "/10km_monthly_mean_temp/geotiff/"
    pdir = BASE + "/10km_monthly_precipitation/geotiff/"
    tfiles = {int(re.search(r"(\d{4})", f).group(1)): f for f in listing(tdir) if re.search(r"(\d{4})", f)}
    pfiles = {int(re.search(r"(\d{4})", f).group(1)): f for f in listing(pdir) if re.search(r"(\d{4})", f)}
    ts, ps, prof = None, None, None
    for y in YEARS:
        a, prof, nd = read_year("/vsicurl/" + tdir + tfiles[y])
        a[a == nd] = np.nan
        days = np.array([calendar.monthrange(y, m)[1] for m in range(1, 13)])[:, None, None]
        dd = np.nansum(np.clip(a - 5.0, 0, None) * days, axis=0)   # monthly-mean approximation of ETS
        ts = dd if ts is None else ts + dd
        if y in pfiles:
            p, _, ndp = read_year("/vsicurl/" + pdir + pfiles[y])
            p[p == ndp] = np.nan
            pa = np.nansum(p, axis=0)
            ps = pa if ps is None else ps + pa
        print(time.strftime("%H:%M:%S"), y, flush=True)
    n = len(list(YEARS))
    prof.update(count=1, dtype="float32", nodata=-9999, compress="deflate")
    for name, arr in (("thermal_sum_dd", ts / n), ("precip_annual_mm", ps / n if ps is not None else None)):
        if arr is None: continue
        arr = np.where(np.isfinite(arr), arr, -9999).astype("float32")
        with rasterio.open(os.path.join(OUT, name + ".tif"), "w", **prof) as dst:
            dst.write(arr, 1)
        print("wrote", name, float(np.nanmin(arr[arr > -9999])), float(np.nanmax(arr)))
    print("DONE")


if __name__ == "__main__":
    main()
