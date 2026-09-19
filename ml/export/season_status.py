"""How does the running season compare with a normal one, at one point?

Applies the weather-only conditional-logit fit from ml/train/train_weather.py to today:
the anomalies are measured from station observations of the running season, against the
1991-2020 distribution of the same anomalies in the same 10 km cell on the same calendar
day. The output is a relative odds -- "this year looks N times more like a find year than
a normal year here" -- not a probability of finding anything.

The gridded files stop at the previous calendar year, so the running season has to come
from FMI's station WFS: the average of the stations inside a box around the point, which
is coarser than the interpolated grid and blind to a shower that missed the stations.

  python ml/export/season_status.py --lat 64.5 --lon 27.0
  python ml/export/season_status.py --lat 62.7 --lon 29.0 --date 2026-09-05
"""
import argparse, datetime as dt, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ML, "ingest"))
sys.path.insert(0, os.path.join(ML, "dataset"))
import weather_daily as W                                     # noqa: E402
from build_weather_dataset import features                    # noqa: E402

MODEL = os.path.join(ML, "models", "weather", "clogit_weather.json")
REF = list(range(1991, 2021))


def station_series(year, lat, lon, until):
    """Daily rain and temperature for this year up to `until`, as two 366-long arrays."""
    days = W.season_from_stations(year, lat, lon, start="04-01", end=until.strftime("%m-%d"))
    rain = np.full(366, np.nan, dtype="float32")
    temp = np.full(366, np.nan, dtype="float32")
    for iso, vals in days.items():
        d = dt.date.fromisoformat(iso).timetuple().tm_yday - 1
        if "rrday" in vals:
            rain[d] = max(vals["rrday"], 0.0)                 # WFS reports -1 for "trace"
        if "tday" in vals:
            temp[d] = vals["tday"]
    return rain, temp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    a = ap.parse_args()
    date = dt.date.fromisoformat(a.date)

    with open(MODEL) as f:
        model = json.load(f)

    transform, width, height = W.grid_geometry()
    rc = W.rowcol(a.lat, a.lon, transform, width, height)
    if rc is None:
        sys.exit("point is outside the FMI grid")

    # Climatology of the same calendar day in the same cell, from the gridded files.
    ref_rr = np.stack([W.read_year("rr", y, [rc])[:, 0] for y in REF])
    ref_t = np.stack([W.read_year("t", y, [rc])[:, 0] for y in REF])
    ref = [features(ref_rr[i][None, :, None], ref_t[i][None, :, None], [y], 0, 0,
                    dt.date(y, date.month, date.day)) for i, y in enumerate(REF)]

    rain, temp = station_series(date.year, a.lat, a.lon, date)
    now = features(rain[None, :, None], temp[None, :, None], [date.year], 0, 0, date)

    z, lines = {}, []
    for k in sorted(now):
        if k == "pnext30":                 # the placebo the model was tested against; it lies
            continue                        # in the future of a running season by construction
        vals = np.array([r[k] for r in ref], dtype="float64")
        m, s = vals.mean(), vals.std()
        z[k] = (now[k] - m) / s if s > 1e-9 else 0.0
        pct = 100 * now[k] / m if m > 1e-9 else float("nan")
        lines.append(f"  {k:10s} {now[k]:8.1f}   normal {m:7.1f}   {pct:5.0f} %   z {z[k]:+.2f}")

    # The fit is in z-scores; a season far outside the range it was fitted on is clipped
    # rather than extrapolated, and said so below.
    zz = {k + "_z": float(np.clip(v, -2.5, 2.5)) for k, v in z.items()}
    zz["p60_z2"] = zz.get("p60_z", 0.0) ** 2
    clipped = [k for k, v in z.items() if abs(v) > 2.5]
    score = sum(c * zz.get(f, 0.0) for f, c in zip(model["features"], model["coef"]))
    print(f"{a.lat:.3f}, {a.lon:.3f}  cell {rc}  {date}  (stations, {date.year})")
    print("\n".join(lines))
    print(f"\nrelative odds vs a normal year here: {np.exp(score):.2f}x "
          f"(weather-only fit, {model['n_sets']} sets, {model['fitted']})")
    print("This is how find-like the season looks, not a probability of finding anything.")
    if clipped:
        print("outside the fitted range, clipped to +/-2.5 sd:", ", ".join(clipped))


if __name__ == "__main__":
    main()
