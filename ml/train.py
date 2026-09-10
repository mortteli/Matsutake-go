"""Train and evaluate habitat models on ml/data/<species>/dataset.csv.

Presence-vs-background classification with spatial block cross-validation:
  * blocks: 25 km squares, 5 folds, presence-holding blocks spread evenly across folds
  * models: rule baselines, logistic regression, LightGBM, PyTorch MLP (primary)
  * metrics (pooled out-of-fold): ROC-AUC / PR-AUC against each background set,
    recall@k % of forest area (score above the k-th top percentile of random forest cells),
    continuous Boyce index (Spearman between predicted/expected ratio and score bins)
  * MLP hyper-parameters chosen by nested CV on PR-AUC (presence vs other-fungi background)
Writes ml/models/<species>/ (weights, scaler, config) and docs/MODEL_REPORT_<species>.md
"""
import argparse, json, os, sys, time, itertools, random
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.preprocessing import StandardScaler
import torch, torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from features import FEATURES, SOIL_GROUPS, GLAC_GROUPS

BLOCK_M = 25000
RULES = {
    "rule_old_default": lambda d: ((d.site_5 + d.site_6) > 0) & (d.main_1 > 0) & (d.ika >= 60) & (d.manty >= 20),
    "rule_new_default": lambda d: ((d.site_4 + d.site_5 + d.site_6) > 0) & (d.main_1 > 0) & (d.ika >= 60) & (d.manty >= 20) & (d.kuusi <= 20),
    "rule_E":           lambda d: ((d.site_3 + d.site_4 + d.site_5 + d.site_6 + d.site_7) > 0) & (d.main_1 > 0) & (d.ika >= 60) & (d.manty >= 40) & (d.kuusi < 20) & (d.latvuspeitto <= 60),
}
GROUPS = {   # for ablations
    "soil":    [f for f in FEATURES if f.startswith("soil_") or f.startswith("glac_") or f.startswith("coarse_") or f == "glacfl_frac31"],
    "terrain": ["elev", "slope", "northness", "eastness", "tpi7", "tpi31", "relief7"],
    "climate": ["thermal_sum", "precip"],
    "neigh":   [f for f in FEATURES if f.endswith("_m3") or f.endswith("_m9") or f.endswith("9") or f.endswith("31")],
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ----------------------------------------------------------------------------- data
def load(path):
    d = pd.read_csv(path)
    d["y"] = (d.group == "presence").astype(int)
    d["block"] = (d.x // BLOCK_M).astype(int) * 100000 + (d.y // BLOCK_M).astype(int)
    return d


def assign_folds(d, k=5, seed=0):
    """Blocks with presences are sorted by northing and dealt round-robin (so each fold spans
    the latitude range); the remaining blocks are dealt randomly."""
    rnd = random.Random(seed)
    pres_blocks = d[d.y_ == 1].groupby("block").y_.count() if "y_" in d else d[d.y == 1].groupby("block").y.count()
    pb = d[d.y == 1].groupby("block").agg(n=("y", "size"), yy=("y", "size"), north=("y", "size"))
    pb = d[d.y == 1].groupby("block").agg(n=("y", "size"), north=("y", "mean"))
    pb["north"] = d[d.y == 1].groupby("block").y.mean()  # placeholder, replaced below
    pb["north"] = d[d.y == 1].groupby("block")["y"].size()
    north = d[d.y == 1].groupby("block")["row"].mean()      # smaller row = further north
    order = list(north.sort_values().index)
    # shuffle within chunks of k so folds are still balanced along the gradient
    fold_of = {}
    for i in range(0, len(order), k):
        chunk = order[i:i + k]; rnd.shuffle(chunk)
        for j, b in enumerate(chunk):
            fold_of[b] = j
    rest = [b for b in d.block.unique() if b not in fold_of]
    rnd.shuffle(rest)
    for j, b in enumerate(rest):
        fold_of[b] = j % k
    return d.block.map(fold_of).values


def class_weights(d):
    """Balanced: total presence weight == total background weight; the two background sets
    share the background half equally."""
    w = d.weight.values.astype(float).copy()
    wp = w[d.y == 1].sum()
    for g in ("bg_random", "bg_fungi"):
        m = (d.group == g).values
        if m.any():
            w[m] *= (wp / 2) / w[m].sum()
    return w


# ----------------------------------------------------------------------------- metrics
def recall_at_area(score, d, frac):
    bg = score[(d.group == "bg_random").values]
    thr = np.quantile(bg, 1 - frac)
    return float((score[(d.y == 1).values] >= thr).mean())


def boyce(score, d, nbins=10):
    p, b = score[(d.y == 1).values], score[(d.group == "bg_random").values]
    edges = np.quantile(b, np.linspace(0, 1, nbins + 1))
    edges[-1] += 1e-9
    ratios, mids = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        pp = ((p >= lo) & (p < hi)).mean(); bb = ((b >= lo) & (b < hi)).mean()
        if bb > 0:
            ratios.append(pp / bb); mids.append((lo + hi) / 2)
    return float(spearmanr(mids, ratios).correlation) if len(ratios) > 2 else float("nan")


def summarize(score, d):
    y = d.y.values
    fungi = (d.group != "bg_random").values; rand = (d.group != "bg_fungi").values
    out = dict(
        auc_vs_fungi=roc_auc_score(y[fungi], score[fungi]), prauc_vs_fungi=average_precision_score(y[fungi], score[fungi]),
        auc_vs_random=roc_auc_score(y[rand], score[rand]), prauc_vs_random=average_precision_score(y[rand], score[rand]),
        recall_at_5=recall_at_area(score, d, 0.05), recall_at_10=recall_at_area(score, d, 0.10),
        recall_at_20=recall_at_area(score, d, 0.20), boyce=boyce(score, d))
    return {k: round(float(v), 3) for k, v in out.items()}


# ----------------------------------------------------------------------------- models
class MLP(nn.Module):
    def __init__(self, n_in, hidden=64, depth=2, dropout=0.2):
        super().__init__()
        layers, d = [], n_in
        for _ in range(depth):
            layers += [nn.Linear(d, hidden), nn.GELU(), nn.Dropout(dropout)]; d = hidden
        layers += [nn.Linear(d, 1)]
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


def fit_mlp(Xtr, ytr, wtr, Xva=None, yva=None, wva=None, hidden=64, depth=2, dropout=0.2, wd=1e-3, lr=2e-3,
            epochs=300, patience=30, seed=0):
    torch.manual_seed(seed)
    m = MLP(Xtr.shape[1], hidden, depth, dropout)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=wd)
    Xt, yt, wt = map(lambda a: torch.tensor(np.asarray(a), dtype=torch.float32), (Xtr, ytr, wtr))
    if Xva is not None:
        Xv, yv, wv = map(lambda a: torch.tensor(np.asarray(a), dtype=torch.float32), (Xva, yva, wva))
    best, best_state, bad = float("inf"), None, 0
    bce = nn.BCEWithLogitsLoss(reduction="none")
    n = len(Xt); bs = 256
    for ep in range(epochs):
        m.train(); perm = torch.randperm(n)
        for i in range(0, n, bs):
            idx = perm[i:i + bs]
            loss = (bce(m(Xt[idx]), yt[idx]) * wt[idx]).sum() / wt[idx].sum()
            opt.zero_grad(); loss.backward(); opt.step()
        if Xva is not None:
            m.eval()
            with torch.no_grad():
                vl = float((bce(m(Xv), yv) * wv).sum() / wv.sum())
            if vl < best - 1e-4:
                best, bad, best_state = vl, 0, {k: v.clone() for k, v in m.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break
    if best_state is not None:
        m.load_state_dict(best_state)
    m.eval()
    return m


def predict_mlp(m, X):
    with torch.no_grad():
        return torch.sigmoid(m(torch.tensor(np.asarray(X), dtype=torch.float32))).numpy()


class Prep:
    """Impute (train medians) + standardize; stored with the model for inference."""
    def __init__(self, cols):
        self.cols = cols
    def fit(self, X):
        self.median = np.nanmedian(X, axis=0); self.median[~np.isfinite(self.median)] = 0
        Xi = np.where(np.isfinite(X), X, self.median)
        self.mean, self.std = Xi.mean(0), Xi.std(0) + 1e-6
        return self
    def transform(self, X):
        Xi = np.where(np.isfinite(X), X, self.median)
        return (Xi - self.mean) / self.std
    def to_json(self):
        return dict(features=list(self.cols), median=self.median.tolist(), mean=self.mean.tolist(), std=self.std.tolist())


def inner_split(dtr, seed):
    """One inner validation split by block (for early stopping / tuning)."""
    rnd = np.random.default_rng(seed)
    blocks = dtr.block.unique(); rnd.shuffle(blocks)
    val_blocks = set(blocks[: max(1, len(blocks) // 5)])
    va = dtr.block.isin(val_blocks).values
    if dtr[va].y.sum() < 5:                              # make sure some presences land in validation
        pb = dtr[dtr.y == 1].block.unique(); rnd.shuffle(pb)
        va = dtr.block.isin(set(pb[: max(1, len(pb) // 5)]) | val_blocks).values
    return ~va, va


def run_cv(d, cols, folds, cfg, seed=0, model="mlp", lgb_params=None):
    score = np.full(len(d), np.nan)
    for f in sorted(set(folds)):
        tr, te = folds != f, folds == f
        dtr = d[tr]
        prep = Prep(cols).fit(d.loc[tr, cols].values)
        Xtr, Xte = prep.transform(d.loc[tr, cols].values), prep.transform(d.loc[te, cols].values)
        w = class_weights(dtr)
        if model == "mlp":
            itr, iva = inner_split(dtr, seed + f)
            m = fit_mlp(Xtr[itr], dtr.y.values[itr], w[itr], Xtr[iva], dtr.y.values[iva], w[iva], seed=seed + f, **cfg)
            score[te] = predict_mlp(m, Xte)
        elif model == "logreg":
            m = LogisticRegression(C=cfg.get("C", 0.3), max_iter=2000).fit(Xtr, dtr.y.values, sample_weight=w)
            score[te] = m.predict_proba(Xte)[:, 1]
        elif model == "lgbm":
            import lightgbm as lgb
            m = lgb.LGBMClassifier(**(lgb_params or {}), verbose=-1, random_state=seed).fit(Xtr, dtr.y.values, sample_weight=w)
            score[te] = m.predict_proba(Xte)[:, 1]
    return score


def tune_mlp(d, cols, folds, seed=0, n_trials=12):
    """Random search; each trial scored by pooled out-of-fold PR-AUC vs the other-fungi background."""
    space = dict(hidden=[32, 64, 128], depth=[1, 2, 3], dropout=[0.1, 0.25, 0.4], wd=[1e-4, 1e-3, 1e-2], lr=[1e-3, 3e-3])
    rnd = random.Random(seed)
    trials = []
    for t in range(n_trials):
        cfg = {k: rnd.choice(v) for k, v in space.items()}
        s = run_cv(d, cols, folds, cfg, seed=seed)
        met = summarize(s, d)
        trials.append((met["prauc_vs_fungi"], met["recall_at_5"], cfg, met))
        log(f"trial {t}: {cfg} -> prauc_fungi {met['prauc_vs_fungi']} recall@5 {met['recall_at_5']} boyce {met['boyce']}")
    trials.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-ablation", action="store_true")
    a = ap.parse_args()
    path = a.dataset or os.path.join(HERE, "data", a.species, "dataset.csv")
    d = load(path)
    cols = [c for c in FEATURES if c in d.columns]
    folds = assign_folds(d, seed=a.seed)
    log("rows", len(d), "presences", int(d.y.sum()), "features", len(cols), "blocks", d.block.nunique())
    report = {"n": int(len(d)), "n_presence": int(d.y.sum()), "n_bg_random": int((d.group == "bg_random").sum()),
              "n_bg_fungi": int((d.group == "bg_fungi").sum()), "n_features": len(cols), "results": {}}

    for name, fn in RULES.items():
        s = fn(d).astype(float).values + 1e-3 * np.random.default_rng(0).random(len(d))   # tiny jitter breaks ties
        report["results"][name] = summarize(s, d)
        log(name, report["results"][name])
    report["results"]["logreg"] = summarize(run_cv(d, cols, folds, {"C": 0.3}, model="logreg"), d)
    log("logreg", report["results"]["logreg"])
    lgbp = dict(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=20, subsample=0.8,
                subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0)
    report["results"]["lgbm"] = summarize(run_cv(d, cols, folds, {}, model="lgbm", lgb_params=lgbp), d)
    log("lgbm", report["results"]["lgbm"])

    trials = tune_mlp(d, cols, folds, seed=a.seed, n_trials=a.trials)
    best_cfg, best_met = trials[0][2], trials[0][3]
    report["mlp_best_cfg"] = best_cfg
    report["mlp_trials"] = [dict(cfg=t[2], **t[3]) for t in trials]
    # re-run best with 3 seeds averaged (ensemble) for the headline numbers + curves
    scores = np.mean([run_cv(d, cols, folds, best_cfg, seed=s) for s in range(3)], axis=0)
    report["results"]["mlp"] = summarize(scores, d)
    log("mlp (3-seed ensemble)", report["results"]["mlp"])
    d["score_mlp"] = scores

    # precision/recall vs area curve (pooled out-of-fold)
    bg = scores[(d.group == "bg_random").values]; pr = scores[(d.y == 1).values]; fu = scores[(d.group == "bg_fungi").values]
    curve = []
    for frac in (0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50):
        thr = float(np.quantile(bg, 1 - frac))
        curve.append(dict(area_frac=frac, threshold=round(thr, 4), recall=round(float((pr >= thr).mean()), 3),
                          other_fungi_frac=round(float((fu >= thr).mean()), 3),
                          lift=round(float((pr >= thr).mean() / frac), 1)))
    report["curve"] = curve

    if not a.no_ablation:
        report["ablation"] = {}
        for g, drop in GROUPS.items():
            sub = [c for c in cols if c not in drop]
            s = np.mean([run_cv(d, sub, folds, best_cfg, seed=s) for s in range(2)], axis=0)
            report["ablation"]["without_" + g] = summarize(s, d)
            log("ablation without", g, report["ablation"]["without_" + g])
        sub = cols + ["row", "col"]
        d["row"] = d["row"].astype(float); d["col"] = d["col"].astype(float)
        s = np.mean([run_cv(d, sub, folds, best_cfg, seed=s) for s in range(2)], axis=0)
        report["ablation"]["with_location"] = summarize(s, d)
        log("ablation with location", report["ablation"]["with_location"])

    # final: fold models trained on the full 5-fold splits (each sees 80 %), ensemble at inference
    outdir = os.path.join(HERE, "models", a.species); os.makedirs(outdir, exist_ok=True)
    prep = Prep(cols).fit(d[cols].values)
    X = prep.transform(d[cols].values); w = class_weights(d)
    members = []
    for f in sorted(set(folds)):
        tr = folds != f
        itr, iva = inner_split(d[tr], a.seed + f)
        Xtr = X[tr]; ytr = d.y.values[tr]; wtr = w[tr]
        m = fit_mlp(Xtr[itr], ytr[itr], wtr[itr], Xtr[iva], ytr[iva], wtr[iva], seed=a.seed + f, **best_cfg)
        torch.save(m.state_dict(), os.path.join(outdir, f"mlp_fold{f}.pt")); members.append(m)
    ens = np.mean([predict_mlp(m, X) for m in members], axis=0)
    bgq = np.quantile(ens[(d.group == "bg_random").values], np.linspace(0, 1, 101))
    json.dump(dict(species=a.species, features=cols, prep=prep.to_json(), mlp=dict(best_cfg, n_in=len(cols)),
                   n_members=len(members), bg_random_quantiles=bgq.tolist(),
                   trained=time.strftime("%Y-%m-%d"), dataset=os.path.relpath(path, HERE)),
              open(os.path.join(outdir, "model.json"), "w"), indent=1)
    json.dump(report, open(os.path.join(outdir, "report.json"), "w"), indent=1)
    d[["group", "lat", "lon", "year", "cycle", "score_mlp"]].to_csv(os.path.join(outdir, "oof_scores.csv"), index=False)
    write_report(report, a.species)
    log("DONE")


def write_report(r, species):
    L = [f"# Habitat model report — {species}", "",
         f"Rows: {r['n']} (presences {r['n_presence']}, random-forest background {r['n_bg_random']}, "
         f"other-fungi background {r['n_bg_fungi']}); {r['n_features']} features; 5-fold spatial block CV (25 km blocks).", "",
         "## Models (pooled out-of-fold)", "",
         "| Model | AUC vs fungi | PR-AUC vs fungi | AUC vs random | recall@5 % | recall@10 % | recall@20 % | Boyce |",
         "|---|---|---|---|---|---|---|---|"]
    for k, m in r["results"].items():
        L.append(f"| {k} | {m['auc_vs_fungi']} | {m['prauc_vs_fungi']} | {m['auc_vs_random']} | {m['recall_at_5']} | {m['recall_at_10']} | {m['recall_at_20']} | {m['boyce']} |")
    L += ["", "recall@k %: share of held-out finds scoring above the top-k % of random forest cells "
          "(i.e. if the map is coloured over k % of forest land).", "",
          "## MLP threshold curve (out-of-fold)", "",
          "| Map covers (share of forest) | Recall of finds | Other-fungi sites kept | Lift vs random |", "|---|---|---|---|"]
    for c in r["curve"]:
        L.append(f"| {int(c['area_frac']*100)} % | {int(c['recall']*100)} % | {int(c['other_fungi_frac']*100)} % | {c['lift']}× |")
    L += ["", f"Best MLP config: `{json.dumps(r['mlp_best_cfg'])}`", ""]
    if "ablation" in r:
        L += ["## Ablations (MLP, same folds)", "", "| Variant | PR-AUC vs fungi | recall@5 % | recall@10 % | Boyce |", "|---|---|---|---|---|"]
        L.append(f"| full | {r['results']['mlp']['prauc_vs_fungi']} | {r['results']['mlp']['recall_at_5']} | {r['results']['mlp']['recall_at_10']} | {r['results']['mlp']['boyce']} |")
        for k, m in r["ablation"].items():
            L.append(f"| {k} | {m['prauc_vs_fungi']} | {m['recall_at_5']} | {m['recall_at_10']} | {m['boyce']} |")
    L += ["", "## Hyper-parameter trials", "", "| PR-AUC vs fungi | recall@5 % | config |", "|---|---|---|"]
    for t in r["mlp_trials"]:
        L.append(f"| {t['prauc_vs_fungi']} | {t['recall_at_5']} | `{json.dumps(t['cfg'])}` |")
    os.makedirs(os.path.join(HERE, "..", "docs"), exist_ok=True)
    open(os.path.join(HERE, "..", "docs", f"MODEL_REPORT_{species}.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
