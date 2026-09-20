"""Assert that grid_se.py's hard-coded national grid is the real thing, and that it holds
every Swedish matsutake observation.

grid_se.py used to read its geometry from a remote raster header on every import, which
cost a network call per script run. The numbers are hard-coded now, so something has to
check them against the source -- that is this file. It also reprojects the committed
observations and counts how many land outside, which is the measurement that motivated
moving off the 2015 grid in the first place.

    python ml/ingest/check_grid_se.py            # header checks + observation coverage
    python ml/ingest/check_grid_se.py --offline  # skip the two remote header reads
"""
import argparse, csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ML, "core"))

import rasterio
from pyproj import Transformer

from grid_se import (GridSE, LEAF_2015_WINDOW, ORIGIN_X, ORIGIN_Y, PIXEL_M, RT90,
                     SLU_FOREST_MAP, WIDTH, HEIGHT, assert_rt90_transform, env, leaf_url)

# The 2018 andel rasters are never read for their values -- see download_slu_forestmap.sh --
# but their footprint is where this grid's extent comes from, so that is what we check.
ANDEL_2018_URL = f"{SLU_FOREST_MAP}/2018/data/Tall_andel.tif"

fails = []


def check(label, got, want, tol=0.0):
    """Compare, allowing a tolerance on floats: the rasters carry float64 affine transforms,
    so an offset that is exactly 200 cells reads back as 199.99999999998."""
    pair = got if isinstance(got, tuple) else (got,)
    ref = want if isinstance(want, tuple) else (want,)
    ok = len(pair) == len(ref) and all(
        abs(g - w) <= tol if isinstance(g, float) or isinstance(w, float) else g == w
        for g, w in zip(pair, ref))
    shown = tuple(round(v, 4) if isinstance(v, float) else v for v in pair)
    shown = shown if isinstance(got, tuple) else shown[0]
    print(f"  {'ok ' if ok else 'FAIL'} {label}: {shown}" + ("" if ok else f"  (expected {want})"))
    if not ok:
        fails.append(label)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip the remote header reads")
    ap.add_argument("--observations", default=os.path.join(ML, "data", "matsutake_se", "observations.csv"))
    a = ap.parse_args()

    g = GridSE()
    print(f"grid: {g.width} x {g.height} @ {PIXEL_M} m, {g.crs}")
    print(f"      bounds {g.bounds}  ({g.width * g.height / 1e9:.2f}e9 cells)")

    print("\nRT90 datum shift:")
    err = assert_rt90_transform()
    print(f"  ok  worst control residual {err:.2f} m")

    if not a.offline:
        print("\n2018 andel header (the national footprint this grid copies):")
        with env(), rasterio.open(ANDEL_2018_URL) as ds:
            check("width", ds.width, WIDTH)
            check("height", ds.height, HEIGHT)
            check("pixel", (ds.transform.a, -ds.transform.e), (PIXEL_M, PIXEL_M), tol=1e-6)
            check("origin", (ds.transform.c, ds.transform.f), (ORIGIN_X, ORIGIN_Y), tol=0.01)

        print("\n2015 leaf header (must tile into this grid with no resampling):")
        with env(), rasterio.open(leaf_url("vol_total")) as ds:
            check("width", ds.width, int(LEAF_2015_WINDOW.width))
            check("height", ds.height, int(LEAF_2015_WINDOW.height))
            col = (ds.transform.c - ORIGIN_X) / PIXEL_M
            row = (ORIGIN_Y - ds.transform.f) / PIXEL_M
            check("col offset", col, float(LEAF_2015_WINDOW.col_off), tol=1e-3)
            check("row offset", row, float(LEAF_2015_WINDOW.row_off), tol=1e-3)

    print(f"\nobservation coverage ({os.path.basename(a.observations)}):")
    rows = list(csv.DictReader(open(a.observations, newline="")))
    to_se = Transformer.from_crs("EPSG:4326", g.crs, always_xy=True)
    L, B, R, T = g.bounds
    # The 2015 grid, for the comparison that justifies not using it.
    l15 = ORIGIN_X + LEAF_2015_WINDOW.col_off * PIXEL_M
    t15 = ORIGIN_Y - LEAF_2015_WINDOW.row_off * PIXEL_M
    r15 = l15 + LEAF_2015_WINDOW.width * PIXEL_M
    b15 = t15 - LEAF_2015_WINDOW.height * PIXEL_M

    out_new = out_old = 0
    by_province = {}
    for r in rows:
        if not r["lat"]:
            continue
        x, y = to_se.transform(float(r["lon"]), float(r["lat"]))
        if not (L <= x <= R and B <= y <= T):
            out_new += 1
            by_province[r["province"]] = by_province.get(r["province"], 0) + 1
        if not (l15 <= x <= r15 and b15 <= y <= t15):
            out_old += 1
    n = len(rows)
    print(f"  {n} records")
    print(f"  outside the 2015 leaf grid : {out_old:5d}  ({100 * out_old / n:.1f} %)")
    print(f"  outside this national grid : {out_new:5d}  ({100 * out_new / n:.1f} %)")
    if out_new:
        fails.append("observations outside the grid")
        for p, c in sorted(by_province.items(), key=lambda kv: -kv[1])[:8]:
            print(f"      {p or '(no province)'}: {c}")

    print()
    if fails:
        print("FAILED:", ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
