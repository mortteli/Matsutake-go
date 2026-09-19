"""Does the weather of the year explain when matsutake was found?

Fits a conditional logistic regression on the matched sets built by
ml/dataset/build_weather_dataset.py: within one cell and one calendar day, which year was
the year of the find. Matching does the work that covariates would otherwise have to do --
place and season drop out exactly -- so the coefficients are about weather alone, and about
how many people were out looking (the effort term).

Everything is validated leave-one-year-out, because the unit that repeats here is the year,
not the find: two finds in the same autumn saw the same weather and are not two tests of it.

  python ml/train/train_weather.py                  # fit, validate, write the report
  python ml/train/train_weather.py --no-report      # numbers to stdout only
"""
import argparse, csv, datetime as dt, json, math, os, sys
import numpy as np
from scipy.optimize import minimize
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
REPO = os.path.dirname(ML)
DATA = os.path.join(ML, "data", "weather", "weather_dataset.csv")
REPORT = os.path.join(REPO, "docs", "MODEL_REPORT_weather.md")

# Candidate predictors, all as z-scores against 1991-2020 in the same cell and calendar day.
# Names are the feature column stems in the dataset.
SETS = {
    "effort":  ["log_effort"],
    "rain":    ["p60_z", "dry60_z"],
    "temp":    ["t30_z", "cool15_d_z"],
    "weather": ["p60_z", "dry60_z", "t30_z", "cool15_d_z"],
    "full":    ["p60_z", "dry60_z", "t30_z", "cool15_d_z", "log_effort"],
    "rain_hump": ["p60_z", "p60_z2", "dry60_z", "t30_z", "cool15_d_z", "log_effort"],
    # Both effort and temperature trend upwards over 45 years, so a model without a trend
    # term can read the rise in recording as a rise in warmth. year_z absorbs the trend.
    "full_trend": ["p60_z", "dry60_z", "t30_z", "cool15_d_z", "log_effort", "year_z"],
    # The strict test: rain against recording that happened in the same month as the find.
    "vs_month_effort": ["p60_z", "dry60_z", "t30_z", "log_effort_m", "year_z"],
    # What a running season can be scored with: no effort term, because how many people will
    # be out this autumn is not knowable yet, and the rain term curved, because a straight
    # line keeps rewarding rain past the point where the finds stop increasing.
    "season": ["p60_z", "p60_z2", "dry60_z", "t30_z", "cool15_d_z"],
}


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            d = {k: (float(v) if v not in ("", None) else np.nan) for k, v in r.items() if k != "date"}
            d["date"] = r["date"]
            rows.append(d)
    eff = np.array([r["effort"] for r in rows])
    # Effort spans an order of magnitude between years, so it enters as a log and is
    # standardised like everything else.
    le = np.log1p(eff)
    le = (le - le.mean()) / le.std()
    if "effort_m" in rows[0]:
        lem = np.log1p(np.array([r["effort_m"] for r in rows]))
        lem = (lem - lem.mean()) / lem.std()
        for r, v in zip(rows, lem):
            r["log_effort_m"] = v
    yr = np.array([r["year"] for r in rows])
    yr = (yr - yr.mean()) / yr.std()
    for r, v, y in zip(rows, le, yr):
        r["log_effort"] = v
        r["year_z"] = y
        r["p60_z2"] = r["p60_z"] ** 2          # the hump the Finnish fruiting study implies
    return rows


def matrices(rows, cols):
    X = np.array([[r[c] for c in cols] for r in rows], dtype="float64")
    y = np.array([r["is_case"] for r in rows], dtype="int")
    s = np.array([r["set_id"] for r in rows], dtype="int")
    ok = np.isfinite(X).all(axis=1)
    return X[ok], y[ok], s[ok]


def clogit(X, y, s, l2=1e-2):
    """Conditional likelihood: in each set, the case should score highest."""
    groups = [np.where(s == g)[0] for g in np.unique(s)]
    groups = [g for g in groups if y[g].sum() == 1]

    def nll(b):
        tot, grad = l2 * b @ b, 2 * l2 * b
        for g in groups:
            z = X[g] @ b
            m = z.max()
            p = np.exp(z - m)
            p /= p.sum()
            case = np.where(y[g] == 1)[0][0]
            tot -= z[case] - (m + math.log(np.exp(z - m).sum()))
            grad -= X[g][case] - p @ X[g]
        return tot, grad

    b0 = np.zeros(X.shape[1])
    res = minimize(nll, b0, jac=True, method="L-BFGS-B")
    # Standard errors from a finite-difference Hessian of the gradient.
    h, n = 1e-4, len(res.x)
    H = np.zeros((n, n))
    for i in range(n):
        e = np.zeros(n); e[i] = h
        H[:, i] = (nll(res.x + e)[1] - nll(res.x - e)[1]) / (2 * h)
    try:
        se = np.sqrt(np.diag(np.linalg.inv((H + H.T) / 2)))
    except np.linalg.LinAlgError:
        se = np.full(n, np.nan)
    return res.x, se, len(groups)


def set_rank(X, y, s, beta):
    """Per set: the fraction of control years the case year outscores. 0.5 = no skill."""
    out = []
    for g in np.unique(s):
        ix = np.where(s == g)[0]
        if y[ix].sum() != 1:
            continue
        z = X[ix] @ beta
        case = z[y[ix] == 1][0]
        ctrl = z[y[ix] == 0]
        out.append((np.sum(ctrl < case) + 0.5 * np.sum(ctrl == case)) / len(ctrl))
    return np.array(out)


def loyo(rows, cols):
    """Leave-one-year-out over the years of the finds."""
    case_year = {int(r["set_id"]): int(r["year"]) for r in rows if r["is_case"]}
    years = sorted(set(case_year.values()))
    ranks, held = [], []
    for y in years:
        tr = [r for r in rows if case_year[int(r["set_id"])] != y]
        te = [r for r in rows if case_year[int(r["set_id"])] == y]
        Xtr, ytr, str_ = matrices(tr, cols)
        Xte, yte, ste = matrices(te, cols)
        if len(np.unique(ste)) == 0 or ytr.sum() < 5:
            continue
        beta, _, _ = clogit(Xtr, ytr, str_)
        r = set_rank(Xte, yte, ste, beta)
        ranks.append(r); held += [y] * len(r)
    return np.concatenate(ranks), np.array(held)


def boot_ci(v, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    m = [rng.choice(v, len(v), replace=True).mean() for _ in range(n)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def year_level(rows):
    """Finds per year against that year's weather, with effort divided out."""
    cases = [r for r in rows if r["is_case"]]
    years = sorted({int(r["year"]) for r in rows})
    n_by_year = {y: 0 for y in years}
    for c in cases:
        n_by_year[int(c["year"])] += 1
    effort = {int(r["year"]): r["effort"] for r in rows}
    # Weather of a year, averaged over the cells that ever produced a find: one number per
    # year, so the sample here is 45 years and not 200 finds.
    out = []
    for y in years:
        w = [r for r in rows if int(r["year"]) == y]
        out.append({"year": y, "n": n_by_year[y], "effort": effort[y],
                    "rate": 1e4 * n_by_year[y] / max(effort[y], 1),
                    "p60_z": float(np.nanmean([r["p60_z"] for r in w])),
                    "p60_pct": float(np.nanmean([r["p60_pct"] for r in w])),
                    "t30_z": float(np.nanmean([r["t30_z"] for r in w])),
                    "dry60_z": float(np.nanmean([r["dry60_z"] for r in w]))})
    return out


def hump_table(rows, col="p60_pct", bins=(0, 70, 90, 110, 130, 1e9)):
    """Case share by band of 'precipitation as a percentage of normal'.

    The Finnish fruiting study reports the best yields at 90-110 % of normal, i.e. a hump
    rather than 'wetter is better'. With matched sets each band's expected share under no
    effect is just the share of control years in it, so the ratio is readable directly."""
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        sel = [r for r in rows if np.isfinite(r.get(col, np.nan)) and lo <= r[col] < hi]
        if not sel:
            continue
        cases = sum(r["is_case"] for r in sel)
        out.append({"band": f"{lo:.0f}-{hi:.0f}%" if hi < 1e8 else f">{lo:.0f}%",
                    "n": len(sel), "cases": cases, "share": cases / len(sel)})
    base = sum(r["is_case"] for r in rows) / len(rows)
    for o in out:
        o["ratio"] = o["share"] / base
    return out, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--no-report", action="store_true")
    a = ap.parse_args()

    rows = load(a.data)
    n_sets = len({r["set_id"] for r in rows})
    n_case_years = len({int(r["year"]) for r in rows if r["is_case"]})
    print(f"{n_sets} matched sets, {len(rows)} rows, finds from {n_case_years} years")

    lines = ["# Weather and the matsutake fruiting year — model report", "",
             f"Generated by `ml/train/train_weather.py` on {dt.date.today().isoformat()} from "
             f"`{os.path.relpath(a.data, REPO)}`.", "",
             f"{n_sets} matched sets (one dated find each, {len(rows)} cell-years in total), "
             f"finds from {n_case_years} different years. Each set is one 10 km cell on one "
             "calendar day, the find's year against every other year 1981–2025.", ""]

    lines += ["## 1. Coefficients (conditional logistic regression)", "",
              "Positive = that year looked more like a find year. All predictors are z-scores "
              "against 1991–2020 in the same cell and on the same calendar day, so a coefficient "
              "is the log-odds per standard deviation of anomaly.", "",
              "| Model | Predictor | Coef | SE | z |", "|---|---|---|---|---|"]
    fits = {}
    for name, cols in SETS.items():
        X, y, s = matrices(rows, cols)
        beta, se, ng = clogit(X, y, s)
        fits[name] = (beta, se, cols)
        for c, b, e in zip(cols, beta, se):
            lines.append(f"| {name} | `{c}` | {b:+.3f} | {e:.3f} | {b / e:+.1f} |")
        print(f"{name:10s} " + "  ".join(f"{c}={b:+.3f}({b / e:+.1f}z)" for c, b, e in zip(cols, beta, se)))
    lines.append("")

    lines += ["## 2. Leave-one-year-out", "",
              "Per set, the share of control years the model ranks below the actual find year. "
              "0.50 is no skill — the model cannot tell the find year from any other year in "
              "that place on that date.", "",
              "| Model | Sets | Mean rank | 95 % CI |", "|---|---|---|---|"]
    for name, cols in SETS.items():
        r, held = loyo(rows, cols)
        lo, hi = boot_ci(r)
        lines.append(f"| {name} | {len(r)} | {r.mean():.3f} | {lo:.3f}–{hi:.3f} |")
        print(f"LOYO {name:10s} mean rank {r.mean():.3f}  CI {lo:.3f}-{hi:.3f}  n={len(r)}")
    lines.append("")

    # Which lookback window is the one that matters, and does rain after the find explain
    # the find as well as rain before it (it should not).
    lines += ["## 2b. One predictor at a time", "",
              "Each fitted alone, so the numbers are comparable. `pnext30` is the placebo: "
              "rain in the 30 days *after* the find.", "",
              "| Predictor | Coef | z | LOYO mean rank |", "|---|---|---|---|"]
    for col in ["p7_z", "p30_z", "p60_z", "p90_z", "dry60_z", "t30_z", "t7_z", "cool15_d_z",
                "dd5_z", "pnext30_z", "log_effort", "log_effort_m"]:
        if col not in rows[0]:
            continue
        X, y, s_ = matrices(rows, [col])
        b, se, _ = clogit(X, y, s_)
        r, _ = loyo(rows, [col])
        lines.append(f"| `{col}` | {b[0]:+.3f} | {b[0] / se[0]:+.1f} | {r.mean():.3f} |")
        print(f"  single {col:12s} {b[0]:+.3f} ({b[0] / se[0]:+.1f}z)  LOYO {r.mean():.3f}")
    lines.append("")

    # Where the hump peaks, if there is one.
    bq, seq, _ = clogit(*matrices(rows, ["p60_z", "p60_z2"]))
    if bq[1] < 0:
        peak = -bq[0] / (2 * bq[1])
        lines += [f"Fitted as a quadratic in the rain anomaly alone, the odds peak at "
                  f"**{peak:+.2f} standard deviations** of 60-day precipitation and fall away "
                  f"on both sides (curvature {bq[1]:+.3f}, {bq[1] / seq[1]:+.1f} z).", ""]
        print(f"  hump peak at {peak:+.2f} sd")

    # Does the rain effect hold in both halves of the country?
    lines += ["## 2c. North and south", "", "| Region | Sets | `p60_z` | z |", "|---|---|---|---|"]
    for name, sel in (("north (lat >= 64)", lambda r: r["lat"] >= 64),
                      ("south (lat < 64)", lambda r: r["lat"] < 64)):
        sub = [r for r in rows if sel(r)]
        X, y, s_ = matrices(sub, ["p60_z", "dry60_z", "t30_z"])
        b, se, ng = clogit(X, y, s_)
        lines.append(f"| {name} | {ng} | {b[0]:+.3f} | {b[0] / se[0]:+.1f} |")
        print(f"  {name}: sets={ng} p60_z={b[0]:+.3f} ({b[0] / se[0]:+.1f}z)")
    lines.append("")

    tab, base = hump_table(rows)
    lines += ["## 3. Is it 'wetter is better' or a hump?", "",
              "60-day precipitation before the day, as a percentage of the 1991–2020 normal for "
              f"that cell and date. Baseline share of case years is {base:.3f}; ratio above 1 "
              "means finds are over-represented in that band.", "",
              "| Rain vs normal | Cell-years | Finds | Share | vs baseline |", "|---|---|---|---|---|"]
    for t in tab:
        lines.append(f"| {t['band']} | {t['n']:.0f} | {t['cases']:.0f} | {t['share']:.3f} | {t['ratio']:.2f}× |")
        print(f"  {t['band']:>8s} n={t['n']:5.0f} cases={t['cases']:3.0f} ratio={t['ratio']:.2f}")
    lines.append("")

    yl = year_level(rows)
    with_finds = [r for r in yl if r["n"] > 0]
    rho_n, p_n = spearmanr([r["p60_z"] for r in with_finds], [r["n"] for r in with_finds])
    rho_r, p_r = spearmanr([r["p60_z"] for r in with_finds], [r["rate"] for r in with_finds])
    rho_t, p_t = spearmanr([r["t30_z"] for r in with_finds], [r["rate"] for r in with_finds])
    rho_e, p_e = spearmanr([r["effort"] for r in with_finds], [r["n"] for r in with_finds])
    recent = [r for r in with_finds if r["year"] >= 2010]
    rho_r2, p_r2 = spearmanr([r["p60_z"] for r in recent], [r["rate"] for r in recent])
    lines += ["## 4. Year level", "",
              f"{len(with_finds)} years with at least one find. Rate = finds per 10 000 Finnish "
              "fungal records that August–September (GBIF), i.e. finds with the number of people "
              "out looking divided out.", "",
              "| Pair | Spearman ρ | p |", "|---|---|---|",
              f"| rain anomaly vs raw find count | {rho_n:+.2f} | {p_n:.3f} |",
              f"| rain anomaly vs effort-adjusted rate | {rho_r:+.2f} | {p_r:.3f} |",
              f"| temperature anomaly vs rate | {rho_t:+.2f} | {p_t:.3f} |",
              f"| **observer effort vs raw find count** | {rho_e:+.2f} | {p_e:.3f} |",
              f"| rain anomaly vs rate, 2010–2025 only ({len(recent)} years) | {rho_r2:+.2f} | {p_r2:.3f} |", "",
              "Read this section as description, not as a result. Finnish fungal recording grew "
              "from a few hundred records an autumn in the 1980s to over ten thousand, so an early "
              "year's rate is one or two finds divided by a denominator too small to divide by, and "
              "any variable that trends with time — temperature included — will correlate with the "
              "rate for that reason alone. The negative temperature correlation below is that "
              "artefact, not a finding. The matched sets in sections 1–3 are where the question is "
              "actually answered, because there the comparison is inside one place and one date.", "",
              "| Year | Finds | Fungal records | Rate | Rain % of normal | T anomaly |",
              "|---|---|---|---|---|---|"]
    for r in yl:
        if r["n"] or r["year"] >= 2010:
            lines.append(f"| {r['year']} | {r['n']:.0f} | {r['effort']:,.0f} | {r['rate']:.1f} | "
                         f"{r['p60_pct']:.0f} % | {r['t30_z']:+.2f} |")
    lines.append("")
    print(f"year level: rain~count rho={rho_n:+.2f} (p={p_n:.3f}), rain~rate rho={rho_r:+.2f} "
          f"(p={p_r:.3f}), effort~count rho={rho_e:+.2f} (p={p_e:.3f})")

    # Save the season fit: weather only, since how many people will be out this autumn is
    # not knowable while the autumn is running.
    beta, se, cols = fits["season"]
    mdir = os.path.join(ML, "models", "weather")
    os.makedirs(mdir, exist_ok=True)
    with open(os.path.join(mdir, "clogit_weather.json"), "w") as f:
        json.dump({"features": cols, "coef": list(map(float, beta)), "se": list(map(float, se)),
                   "fitted": dt.date.today().isoformat(), "n_sets": n_sets,
                   "note": "conditional logit, z-scores vs 1991-2020 in the same cell and day"},
                  f, indent=1)

    if not a.no_report:
        with open(REPORT, "w") as f:
            f.write("\n".join(lines) + "\n")
        print("wrote", os.path.relpath(REPORT, REPO))


if __name__ == "__main__":
    main()
