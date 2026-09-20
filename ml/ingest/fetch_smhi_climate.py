"""Climate normals for Sweden from SMHI's open PTHBV grid (daily temperature and precipitation
since 1961) -- the Swedish equivalent of climate.py's FMI 10 km grid.

Unlike FMI, which ships whole-country GeoTIFFs directly, PTHBV is queried point by point (or
"multipoint": several points per request) through a JSON API -- there is no bulk grid file to
download. Endpoint and response shape confirmed live while building this script:

  https://opendata-download-metanalys.smhi.se/api/category/pthbv1g/version/1/geotype/multipoint/
      from/2022/to/2023/period/monthly/data.json?epsg=4326&ll=16.158,58.5812&var=p&var=t
  -> {"dates": [...], "point_values": [{"east":.., "north":.., "p": [...], "t": [...]}]}

  (the server refuses plain HTTP/1.1 without gzip: send Accept-Encoding, or use curl --compressed)

PTHBV's native grid is ~4 km, so this script samples SMHI's own grid rather than the 12.5 m
analysis grid: it lays down a 4 km point lattice over Sweden (in SWEREF99 TM, reprojected to
WGS84 for the query -- the API only accepts EPSG:4326 lon/lat here), batches points into
multipoint requests, computes the same two features climate.py does for Finland (thermal sum,
annual precipitation), and writes them onto that coarse lattice as a GeoTIFF. features_se.py reads
it the same way features.py reads the Finnish climate rasters -- resampled at extraction time, not
here -- so a ~4 km native cell is no different in kind from FMI's 10 km one.

Output (not committed): ml/data/climate_se/thermal_sum_dd.tif, precip_annual_mm.tif
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
OUT = os.path.join(ML, "data", "climate_se")
API = "https://opendata-download-metanalys.smhi.se/api/category/pthbv1g/version/1/geotype/multipoint"
CELL_M = 4000
BATCH = 50            # points per request; unverified upper bound, kept conservative
YEARS = (1991, 2020)  # normal period, matching climate.py's FMI window


def get_json(url, tries=5):
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
    for i in range(tries):
        try:
            time.sleep(0.3)
            with urllib.request.urlopen(req, timeout=120) as r:
                import gzip
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw)
        except Exception as e:
            print("retry", i, e, file=sys.stderr); time.sleep(4 * (i + 1))
    raise RuntimeError(url[:150])


def lattice_points():
    """4 km lattice over Sweden, in SWEREF99 TM, from the same bounds as the 12.5 m analysis
    grid so nothing here silently drifts out of sync with grid_se.py."""
    sys.path.insert(0, os.path.join(ML, "core"))
    from grid_se import GridSE
    from pyproj import Transformer
    g = GridSE()
    tr = Transformer.from_crs(g.crs, "EPSG:4326", always_xy=True)
    xs = range(int(g.bounds.left), int(g.bounds.right), CELL_M)
    ys = range(int(g.bounds.bottom), int(g.bounds.top), CELL_M)
    pts = [(x + CELL_M / 2, y + CELL_M / 2) for y in ys for x in xs]
    lons, lats = tr.transform([p[0] for p in pts], [p[1] for p in pts])
    return pts, list(zip(lons, lats))


def fetch_batch(lonlat_batch):
    # Repeated ll= params, not semicolon-joined -- confirmed against the API's own error message
    # when a semicolon-joined list was tried while building this script.
    q = [("epsg", 4326)] + [("ll", f"{lon:.5f},{lat:.5f}") for lon, lat in lonlat_batch] + \
        [("var", "p"), ("var", "t")]
    url = f"{API}/from/{YEARS[0]}/to/{YEARS[1]}/period/monthly/data.json?" + urllib.parse.urlencode(q)
    return get_json(url)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap the number of lattice points (testing)")
    a = ap.parse_args()

    pts_xy, pts_lonlat = lattice_points()
    if a.limit:
        pts_xy, pts_lonlat = pts_xy[:a.limit], pts_lonlat[:a.limit]
    print(f"{len(pts_xy)} lattice points, {CELL_M} m spacing, {len(pts_xy)//BATCH + 1} requests")

    thermal_sum = {}
    precip_annual = {}
    for i in range(0, len(pts_lonlat), BATCH):
        batch_xy = pts_xy[i:i + BATCH]
        batch_ll = pts_lonlat[i:i + BATCH]
        j = fetch_batch(batch_ll)
        months = len(j["dates"])
        for xy, pv in zip(batch_xy, j["point_values"]):
            t = pv.get("t", [])
            p = pv.get("p", [])
            if len(t) != months or len(p) != months:
                continue
            # A lattice point can land over the sea or just outside Sweden (the analysis grid's
            # bounding box is rectangular; PTHBV only covers land), where SMHI answers null.
            tv = [v for v in t if v is not None]
            pv_ = [v for v in p if v is not None]
            if len(tv) < months / 2 or len(pv_) < months / 2:  # mostly missing -- not on land
                continue
            dd = sum(max(v - 5.0, 0) * 30.4 for v in tv)   # degree-days above 5C, ~monthly weight
            thermal_sum[xy] = dd / (len(tv) / 12)           # annualised over however many months came back
            precip_annual[xy] = sum(pv_) / (len(pv_) / 12)
        if i % (BATCH * 20) == 0:
            print(time.strftime("%H:%M:%S"), "point", i, "of", len(pts_xy), flush=True)

    write_lattice_tif(thermal_sum, "thermal_sum_dd.tif")
    write_lattice_tif(precip_annual, "precip_annual_mm.tif")
    print("DONE")


def write_lattice_tif(values, name):
    import numpy as np, rasterio
    from rasterio.transform import from_origin
    sys.path.insert(0, os.path.join(ML, "core"))
    from grid_se import GridSE
    g = GridSE()
    w = int((g.bounds.right - g.bounds.left) / CELL_M) + 1
    h = int((g.bounds.top - g.bounds.bottom) / CELL_M) + 1
    arr = np.full((h, w), -9999, dtype="float32")
    for (x, y), v in values.items():
        col = int((x - g.bounds.left) / CELL_M)
        row = int((g.bounds.top - y) / CELL_M)
        if 0 <= row < h and 0 <= col < w:
            arr[row, col] = v
    transform = from_origin(g.bounds.left, g.bounds.top, CELL_M, CELL_M)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with rasterio.open(path, "w", driver="GTiff", dtype="float32", count=1, crs=g.crs,
                       transform=transform, width=w, height=h, nodata=-9999,
                       compress="deflate") as dst:
        dst.write(arr, 1)
    print("wrote", path, "valid cells", int((arr > -9999).sum()), "of", arr.size)


if __name__ == "__main__":
    main()
