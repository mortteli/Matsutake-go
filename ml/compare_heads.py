"""Which model family should the map be made of, judged over several fold splits.

One 5-fold split is not enough to choose a head. The evaluation set is ~109 finds, so a single
split moves the Boyce index by ±0.07 and recall@1 % by ±0.02 on its own — large enough for a
model to look like the winner by luck. This repeats the whole comparison over several fold
seeds and prints the paired differences, which is what the choice should rest on.

Metrics are the ones a "few sure shots" map is read at: how many finds sit in the best 1–2 % of
forest land, and what share of the fungus-reporting sites in that area are matsutake.

  python ml/compare_heads.py --species matsutake --seeds 5
"""
import argparse, os, sys, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from train import load, assign_folds, run_cv, eval_mask, boyce, precision_vs_fungi, recall_at_area
from features import FEATURES

MLP_CFG = {"hidden": 32, "depth": 1, "dropout": 0.4, "wd": 0.01, "lr": 0.003}
LGB_CFG = dict(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=20, subsample=0.8,
               subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0)
KS = (0.01, 0.02, 0.05, 0.10)


def metrics(score, d):
    out = {}
    for k in KS:
        out[f"recall@{k*100:g}"] = round(recall_at_area(score, d, k), 3)
        out[f"prec@{k*100:g}"] = round(precision_vs_fungi(score, d, k), 3)
    out["boyce"] = round(boyce(score, d), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--out", default=None, help="CSV of the per-seed rows")
    a = ap.parse_args()
    d = load(os.path.join(HERE, "data", a.species, "dataset.csv"))
    cols = [c for c in FEATURES if c in d.columns]

    rows = []
    for seed in range(a.seeds):
        t0 = time.time()
        folds = assign_folds(d, seed=seed)
        lg = run_cv(d, cols, folds, LGB_CFG, model="lgbm", lgb_params=LGB_CFG, seed=seed)
        ml = np.mean([run_cv(d, cols, folds, MLP_CFG, seed=seed * 10 + s) for s in range(3)], axis=0)
        rank = lambda s: pd.Series(s).rank(pct=True).values
        # Only the probability combinations can actually be shipped: a rank average has no scale
        # to store in a uint8 raster. The rank average is here as a reference point.
        for name, s in (("lgbm", lg), ("mlp", ml),
                        ("prob_mean", (lg + ml) / 2),
                        ("prob_geo", np.sqrt(np.clip(lg, 1e-9, 1) * np.clip(ml, 1e-9, 1))),
                        ("prob_min", np.minimum(lg, ml)),
                        ("rank_mean", (rank(lg) + rank(ml)) / 2)):
            rows.append(dict(model=name, seed=seed, **metrics(s, d)))
        print(f"seed {seed} done in {time.time()-t0:.0f}s", flush=True)

    df = pd.DataFrame(rows)
    if a.out:
        df.to_csv(a.out, index=False)
    print(f"\n=== mean over {a.seeds} fold splits ===")
    print(df.drop(columns=["seed"]).groupby("model").mean().round(3).to_string())
    piv = df.pivot(index="seed", columns="model")
    print("\n=== paired difference against lgbm (same splits) ===")
    for met in [c for c in df.columns if c not in ("model", "seed")]:
        line = f"{met:12s}"
        for m in sorted(set(df.model) - {"lgbm"}):
            x = piv[met][m] - piv[met]["lgbm"]
            line += f"  {m} {x.mean():+.3f}±{x.std():.3f}"
        print(line)


if __name__ == "__main__":
    main()
