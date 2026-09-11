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
from sklearn import __version__ as _SKL_VERSION
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.preprocessing import SplineTransformer
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
    # data governance: a presence whose record is no longer in observations.csv (e.g. dropped
    # for its licence) must not train the model either
    obs = os.path.join(os.path.dirname(path), "observations.csv")
    if os.path.exists(obs) and "id" in d.columns:
        keep = set(pd.read_csv(obs, dtype=str)["id"])
        before = len(d)
        d = d[(d.group != "presence") | d["id"].astype(str).isin(keep)].reset_index(drop=True)
        if len(d) != before:
            log("dropped", before - len(d), "presence rows not in observations.csv")
    d["y"] = (d.group == "presence").astype(int)
    d["block"] = (d.x // BLOCK_M).astype(int) * 100000 + (d.y // BLOCK_M).astype(int)
    return d


def assign_folds(d, k=5, seed=0):
    """Blocks with presences are sorted by northing and dealt round-robin in shuffled chunks
    (so each fold spans the latitude range); the remaining blocks are dealt randomly."""
    rnd = random.Random(seed)
    north = d[d.y == 1].groupby("block")["row"].mean()      # smaller row = further north
    order = list(north.sort_values().index)
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
    m = eval_mask(d); score, d = score[m], d[m]
    bg = score[(d.group == "bg_random").values]
    thr = np.quantile(bg, 1 - frac)
    return float((score[(d.y == 1).values] >= thr).mean())


def boyce(score, d, nbins=10):
    m = eval_mask(d); score, d = score[m], d[m]
    p, b = score[(d.y == 1).values], score[(d.group == "bg_random").values]
    edges = np.quantile(b, np.linspace(0, 1, nbins + 1))
    edges[-1] += 1e-9
    ratios, mids = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        pp = ((p >= lo) & (p < hi)).mean(); bb = ((b >= lo) & (b < hi)).mean()
        if bb > 0:
            ratios.append(pp / bb); mids.append((lo + hi) / 2)
    return float(spearmanr(mids, ratios).correlation) if len(ratios) > 2 else float("nan")


def eval_mask(d):
    """Coarse presences (unc > 250 m) may train the model but are never used for scoring."""
    unc = pd.to_numeric(d.get("unc_m"), errors="coerce") if "unc_m" in d else pd.Series(np.nan, index=d.index)
    return ~((d.y == 1) & (unc > 250)).values


def precision_vs_fungi(score, d, frac):
    """Of the fungus-reporting sites inside the coloured area, what share are matsutake finds.

    The random background says how much land is coloured; this says what a visit to a coloured
    cell is worth, because both presences and the other-fungi background are places somebody
    actually walked to and reported from. It is the metric to watch when the map is wanted tight
    ("few sure shots") rather than wide."""
    m = eval_mask(d); score, d = score[m], d[m]
    thr = np.quantile(score[(d.group == "bg_random").values], 1 - frac)
    n_p = int((score[(d.y == 1).values] >= thr).sum())
    n_f = int((score[(d.group == "bg_fungi").values] >= thr).sum())
    return float(n_p / (n_p + n_f)) if n_p + n_f else float("nan")


def summarize(score, d):
    m = eval_mask(d)
    score, d = score[m], d[m]
    y = d.y.values
    fungi = (d.group != "bg_random").values; rand = (d.group != "bg_fungi").values
    out = dict(
        auc_vs_fungi=roc_auc_score(y[fungi], score[fungi]), prauc_vs_fungi=average_precision_score(y[fungi], score[fungi]),
        auc_vs_random=roc_auc_score(y[rand], score[rand]), prauc_vs_random=average_precision_score(y[rand], score[rand]),
        recall_at_1=recall_at_area(score, d, 0.01), recall_at_2=recall_at_area(score, d, 0.02),
        recall_at_5=recall_at_area(score, d, 0.05), recall_at_10=recall_at_area(score, d, 0.10),
        recall_at_20=recall_at_area(score, d, 0.20),
        prec_fungi_at_1=precision_vs_fungi(score, d, 0.01), prec_fungi_at_2=precision_vs_fungi(score, d, 0.02),
        prec_fungi_at_5=precision_vs_fungi(score, d, 0.05),
        boyce=boyce(score, d))
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


def continuous_mask(X):
    """columns that are not 0/1 indicators (splines / hinges are only built for these)"""
    return np.array([not np.all(np.isin(X[np.isfinite(X[:, j]), j], [0.0, 1.0])) for j in range(X.shape[1])])


class GamBasis:
    """Spline-basis logistic GAM: natural cubic splines (6 knots) for every continuous feature,
    indicators passed through, ridge penalty via the logistic C. Fitted on standardized inputs."""
    def __init__(self, n_knots=6):
        self.n_knots = n_knots
    def fit(self, X):
        self.cont = continuous_mask(X)
        self.spl = SplineTransformer(n_knots=self.n_knots, degree=3, include_bias=False, extrapolation="linear")
        self.spl.fit(X[:, self.cont])
        return self
    def transform(self, X):
        return np.hstack([self.spl.transform(X[:, self.cont]), X[:, ~self.cont]])


class MaxentBasis:
    """MaxEnt feature classes on standardized inputs: linear, quadratic, forward and reverse
    hinges at 5 quantile knots per continuous feature; indicators passed through."""
    def fit(self, X):
        self.cont = continuous_mask(X)
        Xc = X[:, self.cont]
        self.knots = np.nanquantile(Xc, [0.1, 0.3, 0.5, 0.7, 0.9], axis=0)     # (5, n_cont)
        return self
    def transform(self, X):
        Xc = X[:, self.cont]
        parts = [Xc, Xc ** 2]
        for k in self.knots:
            parts.append(np.maximum(0, Xc - k)); parts.append(np.maximum(0, k - Xc))
        return np.hstack(parts + [X[:, ~self.cont]])


def fit_predict_other(model, Xtr, ytr, wtr, Xte, cfg, seed=0):
    if model == "logreg":
        m = LogisticRegression(C=cfg.get("C", 0.3), max_iter=3000).fit(Xtr, ytr, sample_weight=wtr)
        return m.predict_proba(Xte)[:, 1]
    if model == "gam":
        b = GamBasis().fit(Xtr)
        m = LogisticRegression(C=cfg.get("C", 0.2), max_iter=5000).fit(b.transform(Xtr), ytr, sample_weight=wtr)
        return m.predict_proba(b.transform(Xte))[:, 1]
    if model == "maxent":
        # Infinitely-weighted logistic regression (Fithian & Hastie 2013) == MaxEnt / Poisson point
        # process: background weights >> presence weights, L1 penalty as in MaxEnt's lasso.
        b = MaxentBasis().fit(Xtr)
        w = wtr.copy(); w[ytr == 0] *= cfg.get("W", 50.0)
        # scikit-learn 1.8 deprecated `penalty` in favour of `l1_ratio` and silently fits an L2
        # model if the old spelling is passed, which would quietly turn MaxEnt's lasso into ridge.
        lasso = ({"l1_ratio": 1.0} if tuple(int(x) for x in _SKL_VERSION.split(".")[:2]) >= (1, 8)
                 else {"penalty": "l1"})
        m = LogisticRegression(solver="saga", C=cfg.get("C", 0.1), max_iter=4000, tol=1e-3, **lasso)
        m.fit(b.transform(Xtr), ytr, sample_weight=w)
        return m.decision_function(b.transform(Xte))                      # log relative intensity
    if model == "lgbm":
        import lightgbm as lgb
        m = lgb.LGBMClassifier(**cfg, verbose=-1, random_state=seed).fit(Xtr, ytr, sample_weight=wtr)
        return m.predict_proba(Xte)[:, 1]
    if model == "xgb":
        import xgboost as xgb
        m = xgb.XGBClassifier(**cfg, random_state=seed, n_jobs=4, verbosity=0).fit(Xtr, ytr, sample_weight=wtr)
        return m.predict_proba(Xte)[:, 1]
    raise ValueError(model)


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
        else:
            score[te] = fit_predict_other(model, Xtr, dtr.y.values, w, Xte, lgb_params or cfg, seed)
    return score


def tune_mlp(d, cols, folds, seed=0, n_trials=12, select="prauc"):
    """Random search; each trial scored by pooled out-of-fold PR-AUC vs the other-fungi background."""
    space = dict(hidden=[32, 64, 128], depth=[1, 2, 3], dropout=[0.1, 0.25, 0.4], wd=[1e-4, 1e-3, 1e-2], lr=[1e-3, 3e-3])
    rnd = random.Random(seed)
    trials = []
    for t in range(n_trials):
        cfg = {k: rnd.choice(v) for k, v in space.items()}
        s = run_cv(d, cols, folds, cfg, seed=seed)
        met = summarize(s, d)
        k = ((met["prec_fungi_at_2"], met["recall_at_2"]) if select == "sure"
             else (met["prauc_vs_fungi"], met["recall_at_5"]))
        trials.append((k[0], k[1], cfg, met))
        log(f"trial {t}: {cfg} -> prauc_fungi {met['prauc_vs_fungi']} prec_fungi@2 {met['prec_fungi_at_2']} "
            f"recall@5 {met['recall_at_5']} boyce {met['boyce']}")
    trials.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return trials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-ablation", action="store_true")
    ap.add_argument("--fine-only", action="store_true", help="drop presences with unc > 250 m from training too")
    ap.add_argument("--head", default="mlp", choices=["mlp", "lgbm", "mlp+lgbm"],
                    help="model family the exported map is made of; mlp+lgbm averages the two probabilities")
    ap.add_argument("--select", default="prauc", choices=["prauc", "sure"],
                    help="what hyper-parameters are chosen for: overall PR-AUC, or precision in the best 2 %%")
    a = ap.parse_args()
    path = a.dataset or os.path.join(HERE, "data", a.species, "dataset.csv")
    d = load(path)
    if a.fine_only:
        d = d[eval_mask(d)].reset_index(drop=True)
    n_coarse = int((~eval_mask(d)).sum())
    cols = [c for c in FEATURES if c in d.columns]
    folds = assign_folds(d, seed=a.seed)
    log("rows", len(d), "presences", int(d.y.sum()), "features", len(cols), "blocks", d.block.nunique())
    report = {"n": int(len(d)), "n_presence": int(d.y.sum()) - n_coarse, "n_presence_coarse": n_coarse,
              "n_bg_random": int((d.group == "bg_random").sum()),
              "n_bg_fungi": int((d.group == "bg_fungi").sum()), "n_features": len(cols), "results": {}}

    for name, fn in RULES.items():
        s = fn(d).astype(float).values + 1e-3 * np.random.default_rng(0).random(len(d))   # tiny jitter breaks ties
        report["results"][name] = summarize(s, d)
        log(name, report["results"][name])
    oof = {}

    def key(met):
        """--select prauc: overall separation. --select sure: the tight end of the map, where a
        'few sure shots' user actually reads it (precision against the other-fungi background in
        the best 2 % of forest land, then how many finds that 2 % still holds)."""
        return ((met["prec_fungi_at_2"], met["recall_at_2"]) if a.select == "sure"
                else (met["prauc_vs_fungi"], met["recall_at_5"]))

    def best_of(model, grid):
        best = None
        for cfg in grid:
            s = run_cv(d, cols, folds, cfg, model=model, lgb_params=cfg)
            met = summarize(s, d)
            log(f"  {model} {cfg} -> prauc_fungi {met['prauc_vs_fungi']} prec_fungi@2 {met['prec_fungi_at_2']} recall@5 {met['recall_at_5']}")
            if best is None or key(met) > key(best[0]):
                best = (met, cfg, s)
        report["results"][model] = dict(best[0], cfg=best[1])
        oof[model] = best[2]
        log(model, report["results"][model])

    best_of("logreg", [{"C": 0.1}, {"C": 0.3}, {"C": 1.0}])
    best_of("gam", [{"C": 0.05}, {"C": 0.2}, {"C": 1.0}])
    best_of("maxent", [{"C": 0.03, "W": 50.0}, {"C": 0.1, "W": 50.0}, {"C": 0.3, "W": 50.0}])
    best_of("lgbm", [dict(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=20, subsample=0.8,
                          subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0),
                     dict(n_estimators=300, learning_rate=0.05, num_leaves=7, min_child_samples=30, subsample=0.8,
                          subsample_freq=1, colsample_bytree=0.7, reg_lambda=3.0)])
    best_of("xgb", [dict(n_estimators=400, learning_rate=0.03, max_depth=4, min_child_weight=5, subsample=0.8,
                         colsample_bytree=0.8, reg_lambda=1.0),
                    dict(n_estimators=300, learning_rate=0.05, max_depth=3, min_child_weight=10, subsample=0.8,
                         colsample_bytree=0.7, reg_lambda=3.0)])

    trials = tune_mlp(d, cols, folds, seed=a.seed, n_trials=a.trials, select=a.select)
    best_cfg, best_met = trials[0][2], trials[0][3]
    report["mlp_best_cfg"] = best_cfg
    report["mlp_trials"] = [dict(cfg=t[2], **t[3]) for t in trials]
    # re-run best with 3 seeds averaged (ensemble) for the headline numbers + curves
    scores = np.mean([run_cv(d, cols, folds, best_cfg, seed=s) for s in range(3)], axis=0)
    report["results"]["mlp"] = summarize(scores, d)
    log("mlp (3-seed ensemble)", report["results"]["mlp"])
    d["score_mlp"] = scores
    oof["mlp"] = scores

    # Rank-averaged ensembles across model families. Ranks rather than raw scores because the
    # models are on different scales (maxent returns a log intensity, the rest probabilities).
    def ranks(s):
        return pd.Series(s).rank(pct=True).values
    report["ensembles"] = {}
    for name, members in [("mlp+lgbm", ["mlp", "lgbm"]), ("mlp+maxent", ["mlp", "maxent"]),
                          ("mlp+lgbm+maxent", ["mlp", "lgbm", "maxent"]),
                          ("all", ["mlp", "lgbm", "xgb", "maxent", "gam", "logreg"])]:
        if all(m in oof for m in members):
            s = np.mean([ranks(oof[m]) for m in members], axis=0)
            report["ensembles"][name] = summarize(s, d)
            log("ensemble", name, report["ensembles"][name])

    # the head is what ends up in the map; everything below (curve, ablations, saved weights)
    # describes that model, not necessarily the MLP
    head_oof = {"mlp": lambda: oof["mlp"], "lgbm": lambda: oof["lgbm"],
                "mlp+lgbm": lambda: (oof["mlp"] + oof["lgbm"]) / 2}[a.head]()
    report["head"] = a.head
    report["select"] = a.select
    report["results"]["head:" + a.head] = summarize(head_oof, d)
    log("head", a.head, report["results"]["head:" + a.head])

    # precision/recall vs area curve (pooled out-of-fold)
    scores = head_oof
    em = eval_mask(d)
    bg = scores[em & (d.group == "bg_random").values]; pr = scores[em & (d.y == 1).values]; fu = scores[em & (d.group == "bg_fungi").values]
    curve = []
    for frac in (0.0025, 0.005, 0.01, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50):
        thr = float(np.quantile(bg, 1 - frac))
        n_p, n_f = int((pr >= thr).sum()), int((fu >= thr).sum())
        curve.append(dict(area_frac=frac, threshold=round(thr, 4), recall=round(float((pr >= thr).mean()), 3),
                          other_fungi_frac=round(float((fu >= thr).mean()), 3),
                          prec_fungi=round(n_p / (n_p + n_f), 3) if n_p + n_f else None,
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
    lgb_cfg = report["results"]["lgbm"]["cfg"] if "lgbm" in report["results"] else None
    if "lgbm" in a.head:
        import lightgbm as lgb
        for f in sorted(set(folds)):
            tr = folds != f
            g = lgb.LGBMClassifier(**lgb_cfg, verbose=-1, random_state=a.seed + f)
            g.fit(X[tr], d.y.values[tr], sample_weight=class_weights(d[tr]))
            g.booster_.save_model(os.path.join(outdir, f"lgbm_fold{f}.txt"))
        lg_ens = np.mean([lgb.Booster(model_file=os.path.join(outdir, f"lgbm_fold{f}.txt")).predict(X)
                          for f in sorted(set(folds))], axis=0)
        ens = lg_ens if a.head == "lgbm" else (ens + lg_ens) / 2
    bgq = np.quantile(ens[(d.group == "bg_random").values], np.linspace(0, 1, 101))
    json.dump(dict(species=a.species, features=cols, head=a.head, select=a.select,
                   prep=prep.to_json(), mlp=dict(best_cfg, n_in=len(cols)), lgbm=lgb_cfg,
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
         f"Map head: **{r.get('head', 'mlp')}** (hyper-parameters chosen for "
         f"{'precision in the best 2 %' if r.get('select') == 'sure' else 'overall PR-AUC'}).", "",
         "## Models (pooled out-of-fold)", "",
         "| Model | AUC vs fungi | PR-AUC vs fungi | recall@2 % | prec@2 % | recall@5 % | prec@5 % | recall@10 % | Boyce |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, m in r["results"].items():
        L.append(f"| {k} | {m['auc_vs_fungi']} | {m['prauc_vs_fungi']} | {m['recall_at_2']} | {m['prec_fungi_at_2']} "
                 f"| {m['recall_at_5']} | {m['prec_fungi_at_5']} | {m['recall_at_10']} | {m['boyce']} |")
    L += ["", "recall@k %: share of held-out finds scoring above the top-k % of random forest cells "
          "(i.e. if the map is coloured over k % of forest land). prec@k %: of the fungus-reporting "
          "sites inside that coloured area, the share that are matsutake finds — what a visit to a "
          "coloured cell is worth, and the number to watch for a deliberately tight map.", "",
          "All models are fitted in the presence-background setting: presences vs. a background made of "
          "random forestry-land cells (what habitat is available) and other-fungi observation sites "
          "(where people actually look, i.e. the target-group correction for observer bias). "
          "`maxent` is the MaxEnt-equivalent infinitely-weighted L1 logistic regression on MaxEnt feature "
          "classes (linear, quadratic, forward/reverse hinges); `gam` is a spline-basis logistic GAM; "
          "`logreg` is a ridge logistic regression; `lgbm`/`xgb` are gradient-boosted trees; `mlp` is a "
          "neural network. The row named `head:` is the one the exported map is made of. Configs are the "
          "best of a small grid on the same folds (slightly optimistic, the MLP's nested-CV config aside), "
          "so read the head's own numbers as the optimistic end of its range.", "",
          f"## Threshold curve of the map head ({r.get('head', 'mlp')}, out-of-fold)", "",
          "| Map covers (share of forest) | Recall of finds | Other-fungi sites kept | Matsutake share of fungi sites | Lift vs random |",
          "|---|---|---|---|---|"]
    for c in r["curve"]:
        pc = "—" if c.get("prec_fungi") is None else f"{int(c['prec_fungi']*100)} %"
        L.append(f"| {c['area_frac']*100:g} % | {int(c['recall']*100)} % | {int(c['other_fungi_frac']*100)} % | {pc} | {c['lift']}× |")
    if r.get("ensembles"):
        L += ["", "## Rank-averaged ensembles (same folds)", "",
              "| Ensemble | AUC vs fungi | PR-AUC vs fungi | recall@5 % | recall@10 % | recall@20 % | Boyce |", "|---|---|---|---|---|---|---|"]
        for k, m in r["ensembles"].items():
            L.append(f"| {k} | {m['auc_vs_fungi']} | {m['prauc_vs_fungi']} | {m['recall_at_5']} | {m['recall_at_10']} | {m['recall_at_20']} | {m['boyce']} |")
        L += ["", "Rank averages cannot be stored in the map (they have no probability scale), so a "
              "rank ensemble can only ever be a comparison; `--head mlp+lgbm` averages the two "
              "probabilities instead."]
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
