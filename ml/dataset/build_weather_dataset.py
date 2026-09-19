"""Dated matsutake finds x the weather that preceded them.

The question is not "where" (that is the habitat model) but "which years, in a place that
has matsutake, did someone find it". So each find becomes a matched set:

  case     the cell and calendar day of the find, in the year of the find
  controls the same cell and the same calendar day in every other year of the record

Matching on cell and calendar day removes the two things that would otherwise explain
everything -- where the species lives, and when in the autumn it fruits -- and leaves the
weather of the year. What it cannot remove is that a control year may well have had
mushrooms that nobody reported; a control is "no record", not "no fruiting", and the size
of that hole is what the effort column is for (Finnish fungal records per year from GBIF).

Out: ml/data/weather/weather_dataset.csv, ml/data/weather/cells.csv, effort_gbif.csv
"""
import argparse, csv, datetime as dt, json, os, sys, urllib.request
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ML, "ingest"))
import weather_daily as W                                     # noqa: E402

OBS = os.path.join(ML, "data", "matsutake", "observations.csv")
OUT = os.path.join(ML, "data", "weather")
REF = (1991, 2020)              # the normal period the anomalies are measured against
WINDOWS = (7, 30, 60, 90)


def load_observations(max_unc, first_year, last_year, months=(7, 8, 9, 10)):
    """Dated finds inside the analysis window, one per cell and day.

    Location precision only has to be good enough for a 10 km weather cell, so this keeps
    records the 16 m habitat model throws away -- an order of magnitude more of them."""
    transform, width, height = W.grid_geometry()
    seen, rows = set(), []
    with open(OBS) as f:
        for r in csv.DictReader(f):
            if not r["date"] or len(r["date"]) != 10:
                continue
            try:
                d = dt.date.fromisoformat(r["date"])
                lat, lon = float(r["lat"]), float(r["lon"])
            except (ValueError, TypeError):
                continue
            unc = float(r["unc_m"]) if r["unc_m"] else None
            if unc is None or unc > max_unc:
                continue
            if not (first_year <= d.year <= last_year) or d.month not in months:
                continue
            rc = W.rowcol(lat, lon, transform, width, height)
            if rc is None:
                continue
            key = (rc, d)                      # two people reporting the same find is one case
            if key in seen:
                continue
            seen.add(key)
            rows.append({"date": d, "row": rc[0], "col": rc[1], "lat": lat, "lon": lon,
                         "unc_m": unc, "id": r["id"]})
    return sorted(rows, key=lambda r: r["date"])


def features(rr, tt, years, yi, ci, date):
    """Weather before one (cell, date). Windows end the day before the find: the rain that
    fell on the morning of the picking trip did not grow the mushroom."""
    d0 = date.timetuple().tm_yday - 1          # 0-based index of the day itself
    out = {}
    rain, temp = rr[yi, :, ci], tt[yi, :, ci]
    for n in WINDOWS:
        out[f"p{n}"] = float(np.nansum(rain[max(0, d0 - n):d0]))
        out[f"t{n}"] = float(np.nanmean(temp[max(0, d0 - n):d0]))
    mar1 = dt.date(years[yi], 3, 1).timetuple().tm_yday - 1
    out["dd5"] = float(np.nansum(np.clip(temp[mar1:d0] - 5.0, 0, None)))
    dry = rain[max(0, d0 - 60):d0] < 1.0       # <1 mm is a dry day in FMI's own rounding
    run = best = 0
    for v in dry:
        run = run + 1 if v else 0
        best = max(best, run)
    out["dry60"] = float(best)
    # Has the autumn cooling started: days in the last 30 whose 7-day mean is below 15 C.
    # Japanese work puts primordium initiation at a soil temperature near 19 C; air is a
    # proxy for soil and runs warmer in daytime, so the threshold here is empirical.
    rm = np.convolve(np.nan_to_num(temp, nan=np.nanmean(temp)), np.ones(7) / 7, mode="same")
    out["cool15_d"] = float(np.sum(rm[max(0, d0 - 30):d0] < 15.0))
    out["cool12_d"] = float(np.sum(rm[max(0, d0 - 30):d0] < 12.0))
    # Placebo: rain AFTER the find. A mushroom cannot have grown on it. If it explains the
    # find year as well as the rain before does, then what the model found is "wet autumns"
    # (or wet autumns send people to the woods), not the water that grew the fruiting body.
    out["pnext30"] = float(np.nansum(rain[d0 + 1:min(366, d0 + 31)]))
    return out


def gbif_effort(years, cache):
    """Finnish fungal records per year, Aug-Sep, as a stand-in for how many people were out.

    Matsutake records are not a yield series: they are a record of picking. Two years with
    the same weather and a tenfold difference in records differ in observers, not mushrooms."""
    if os.path.exists(cache):
        with open(cache) as f:
            return {int(r["year"]): int(r["n"]) for r in csv.DictReader(f)}
    eff = {}
    for y in years:
        url = ("https://api.gbif.org/v1/occurrence/search?country=FI&kingdomKey=5"
               f"&hasCoordinate=true&basisOfRecord=HUMAN_OBSERVATION&year={y}&month=8,9&limit=0")
        with urllib.request.urlopen(url, timeout=120) as r:
            eff[y] = int(json.load(r)["count"])
        print("effort", y, eff[y], flush=True)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["year", "n"])
        w.writerows(sorted(eff.items()))
    return eff


def gbif_effort_month(years, months, cache):
    """The same count per year AND month.

    The yearly figure cannot tell a wet September apart from a dry one: if rain sends
    pickers into the forest, a model fitted with only a yearly effort term will read their
    footsteps as mushrooms. The monthly count is contemporaneous with the find, so putting
    it in the model asks the harder question -- was that year's rain still the tell once we
    know how much recording went on that very month."""
    if os.path.exists(cache):
        with open(cache) as f:
            return {(int(r["year"]), int(r["month"])): int(r["n"]) for r in csv.DictReader(f)}
    eff = {}
    for y in years:
        for m in months:
            url = ("https://api.gbif.org/v1/occurrence/search?country=FI&kingdomKey=5"
                   f"&hasCoordinate=true&basisOfRecord=HUMAN_OBSERVATION&year={y}&month={m}&limit=0")
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(url, timeout=120) as r:
                        eff[(y, m)] = int(json.load(r)["count"])
                    break
                except Exception as e:
                    print("retry", y, m, e, file=sys.stderr)
            print("effort", y, m, eff.get((y, m)), flush=True)
    with open(cache, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["year", "month", "n"])
        w.writerows([(y, m, n) for (y, m), n in sorted(eff.items())])
    return eff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-unc", type=float, default=10000, help="metres; a 10 km cell tolerates a lot")
    ap.add_argument("--first-year", type=int, default=1981)
    ap.add_argument("--last-year", type=int, default=2025, help="the grids end with the previous calendar year")
    ap.add_argument("--fetch", action="store_true", help="download any missing yearly grids first")
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    obs = load_observations(a.max_unc, a.first_year, a.last_year)
    cells = sorted({(o["row"], o["col"]) for o in obs})
    print(f"{len(obs)} dated finds in {len(cells)} cells, {a.first_year}-{a.last_year}")
    with open(os.path.join(OUT, "cells.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["row", "col"]); w.writerows(cells)

    years = list(range(a.first_year, a.last_year + 1))
    if a.fetch or not os.path.exists(os.path.join(OUT, "cells_rr.npz")):
        W.build(cells, years, ("rr", "t"))
    rr, yrs_rr, cells_rr = W.load("rr")
    tt, yrs_t, _ = W.load("t")
    assert yrs_rr == yrs_t == years and cells_rr == cells, "cached cells do not match this run"
    print("missing daily values: rr %.4f%%, t %.4f%%" %
          (100 * np.isnan(rr).mean(), 100 * np.isnan(tt).mean()))

    cell_ix = {c: i for i, c in enumerate(cells)}
    year_ix = {y: i for i, y in enumerate(years)}
    ref_years = [y for y in years if REF[0] <= y <= REF[1]]
    effort = gbif_effort(years, os.path.join(OUT, "effort_gbif.csv"))
    effort_m = gbif_effort_month(years, (7, 8, 9, 10), os.path.join(OUT, "effort_gbif_month.csv"))

    rows, keys = [], None
    for si, o in enumerate(obs):
        ci = cell_ix[(o["row"], o["col"])]
        md = (o["date"].month, o["date"].day)
        # Same cell, same calendar day, every year of the record: one case, the rest controls.
        per_year = {}
        for y in years:
            try:
                d = dt.date(y, *md)
            except ValueError:                 # 29 Feb never happens in this window, but be safe
                continue
            per_year[y] = features(rr, tt, years, year_ix[y], ci, d)
        keys = keys or sorted(per_year[o["date"].year])
        ref = {k: np.array([per_year[y][k] for y in ref_years if y in per_year]) for k in keys}
        for y, f in per_year.items():
            row = {"set_id": si, "is_case": int(y == o["date"].year), "year": y,
                   "date": dt.date(y, *md).isoformat(), "row": o["row"], "col": o["col"],
                   "lat": round(o["lat"], 4), "lon": round(o["lon"], 4), "unc_m": o["unc_m"],
                   "effort": effort.get(y, 0),
                   "effort_m": effort_m.get((y, md[0]), 0)}
            for k in keys:
                row[k] = round(f[k], 3)
                m, s = float(np.mean(ref[k])), float(np.std(ref[k]))
                row[k + "_z"] = round((f[k] - m) / s, 4) if s > 1e-9 else 0.0
                if k.startswith("p") or k == "dd5":
                    row[k + "_pct"] = round(100.0 * f[k] / m, 1) if m > 1e-9 else None
                if k.startswith("t"):
                    row[k + "_anom"] = round(f[k] - m, 3)
            rows.append(row)

    path = os.path.join(OUT, "weather_dataset.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print("wrote", path, len(rows), "rows,", sum(r["is_case"] for r in rows), "cases")


if __name__ == "__main__":
    main()
