"""Daily weather for a set of points, from FMI's open 10 km grids.

FMI publishes one GeoTIFF per year per variable, each band one day (band 1 = 1 Jan),
10 km cells in ETRS-TM35FIN, 1961 onwards, CC BY 4.0:
  https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_precipitation/geotiff/rrday_YYYY.tif
  https://www.nic.funet.fi/index/geodata/ilmatiede/10km_daily_mean_temperature/geotiff/tday_YYYY.tif

A whole year of Finland is 68x116 cells and a few megabytes, so the files are downloaded
whole into a cache (not committed) rather than range-read band by band. What the rest of
the pipeline wants is not the grid but a handful of cells over many years, so the cache is
distilled once into ml/data/weather/cells_<var>.npz: [year, day-of-year, cell].

The grids stop at the previous calendar year. The running season comes from FMI's station
WFS instead (`--season`), which is coarser -- nearest station, not an interpolated grid --
and is meant for showing "where is this season at", not for fitting anything.

  python ml/ingest/weather_daily.py --cells ml/data/weather/cells.csv --years 1981-2025
  python ml/ingest/weather_daily.py --season 2026 --lat 64.5 --lon 27.0
"""
import argparse, csv, os, sys, time, urllib.request, xml.etree.ElementTree as ET
import numpy as np
import rasterio
from rasterio.env import Env
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
CACHE = os.path.join(ML, "data", "weather", "cache")
OUT = os.path.join(ML, "data", "weather")
BASE = "https://www.nic.funet.fi/index/geodata/ilmatiede"
VARS = {"rr": ("10km_daily_precipitation", "rrday"),      # mm/d
        "t":  ("10km_daily_mean_temperature", "tday"),    # degC
        "snow": ("10km_daily_snow", "snow")}              # cm, not used by the model yet
# The grids carry EPSG:9391 (ETRS89 / TM35FIN(N,E)); the affine is a plain east/north one,
# so points are projected to 3067 and read with the file's own transform.
TO_TM35 = Transformer.from_crs("EPSG:4326", "EPSG:3067", always_xy=True)
FMI_WFS = "https://opendata.fmi.fi/wfs"


def url_for(var, year):
    folder, stem = VARS[var]
    return f"{BASE}/{folder}/geotiff/{stem}_{year}.tif"


def cached(var, year, quiet=False):
    """Local path of one yearly grid, downloading it once if missing."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{VARS[var][1]}_{year}.tif")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    tmp = path + ".part"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url_for(var, year), timeout=180) as r, open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(tmp, path)
            if not quiet:
                print("downloaded", os.path.basename(path), os.path.getsize(path) // 1024, "kB", flush=True)
            return path
        except Exception as e:                      # nic.funet.fi throttles bursts now and then
            print("retry", attempt, e, file=sys.stderr)
            time.sleep(2 ** attempt)
    raise RuntimeError(url_for(var, year))


def grid_geometry(var="rr", year=2020):
    with Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(cached(var, year)) as ds:
            return ds.transform, ds.width, ds.height


def rowcol(lat, lon, transform, width, height):
    """Grid cell holding a WGS84 point, or None outside the grid."""
    x, y = TO_TM35.transform(lon, lat)
    col = int((x - transform.c) // transform.a)
    row = int((y - transform.f) // transform.e)
    if 0 <= row < height and 0 <= col < width:
        return row, col
    return None


def read_year(var, year, cells):
    """(366, len(cells)) float32 for one year; day 366 is NaN in non-leap years.

    Missing data in the source (sea, outside Finland) is nodata; it is turned into NaN here
    so a bad cell is loud rather than a plausible-looking zero millimetres."""
    with Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(cached(var, year)) as ds:
            arr = ds.read().astype("float32")
            nd = ds.nodata
    if nd is not None:
        arr[arr == nd] = np.nan
    arr[arr < -1e30] = np.nan
    out = np.full((366, len(cells)), np.nan, dtype="float32")
    for i, (r, c) in enumerate(cells):
        out[:arr.shape[0], i] = arr[:, r, c]
    return out


def build(cells, years, variables=("rr", "t")):
    """Distil the yearly grids into one array per variable: [year, doy, cell]."""
    os.makedirs(OUT, exist_ok=True)
    for var in variables:
        stack = np.full((len(years), 366, len(cells)), np.nan, dtype="float32")
        for i, y in enumerate(years):
            stack[i] = read_year(var, y, cells)
            print(time.strftime("%H:%M:%S"), var, y, flush=True)
        path = os.path.join(OUT, f"cells_{var}.npz")
        np.savez_compressed(path, data=stack, years=np.array(years),
                            cells=np.array(cells, dtype="int32"))
        print("wrote", path, stack.shape, flush=True)


def load(var):
    d = np.load(os.path.join(OUT, f"cells_{var}.npz"))
    return d["data"], list(d["years"]), [tuple(c) for c in d["cells"]]


def season_from_stations(year, lat, lon, radius_deg=0.75, start="07-01", end=None):
    """Current-season daily rr/t near a point from FMI's station WFS (no key needed).

    The gridded files stop at the previous year, so this is the only open route to the
    running season. It averages whatever stations report inside a small box -- nearest
    station, not interpolation -- so it is for display, not for fitting."""
    end = end or time.strftime("%m-%d")
    box = f"{lon - radius_deg},{lat - radius_deg},{lon + radius_deg},{lat + radius_deg}"
    q = (f"{FMI_WFS}?service=WFS&version=2.0.0&request=getFeature"
         f"&storedquery_id=fmi::observations::weather::daily::simple&bbox={box}"
         f"&starttime={year}-{start}T00:00:00Z&endtime={year}-{end}T00:00:00Z&parameters=rrday,tday")
    with urllib.request.urlopen(q, timeout=120) as r:
        root = ET.fromstring(r.read())
    ns = {"BsWfs": "http://xml.fmi.fi/schema/wfs/2.0"}
    days = {}
    for el in root.iter(f"{{{ns['BsWfs']}}}BsWfsElement"):
        day = el.find("BsWfs:Time", ns).text[:10]
        name = el.find("BsWfs:ParameterName", ns).text
        try:
            val = float(el.find("BsWfs:ParameterValue", ns).text)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(val) or val < -9000:      # WFS marks missing as NaN
            continue
        days.setdefault(day, {}).setdefault(name, []).append(val)
    return {d: {k: float(np.mean(v)) for k, v in p.items()} for d, p in sorted(days.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", help="CSV with row,col columns (as written by build_weather_dataset.py)")
    ap.add_argument("--years", default="1981-2025", help="e.g. 1981-2025")
    ap.add_argument("--vars", default="rr,t")
    ap.add_argument("--season", type=int, help="print a station-based season summary for this year")
    ap.add_argument("--lat", type=float, default=64.5)
    ap.add_argument("--lon", type=float, default=27.0)
    a = ap.parse_args()

    if a.season:
        days = season_from_stations(a.season, a.lat, a.lon)
        rain = sum(d.get("rrday", 0.0) for d in days.values())
        temps = [d["tday"] for d in days.values() if "tday" in d]
        print(f"{a.season} 1 Jul -> {len(days)} days, rain {rain:.0f} mm, mean T {np.mean(temps):.1f} C")
        return

    lo, hi = (int(x) for x in a.years.split("-"))
    years = list(range(lo, hi + 1))
    with open(a.cells) as f:
        cells = [(int(r["row"]), int(r["col"])) for r in csv.DictReader(f)]
    build(cells, years, tuple(a.vars.split(",")))


if __name__ == "__main__":
    main()
