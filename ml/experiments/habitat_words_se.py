"""Do the Swedish field notes describe habitat the model cannot see?

754 of the 5501 Artportalen records carry a free-text `habitat` description, written by the
person who found the mushroom. Counted over those strings:

    tall       567 (75 %)   sand      261 (35 %)   lav       153 (20 %)   moran  142 (19 %)
    hed         95 (13 %)   renbet     79 (10 %)   hallmark   57 ( 8 %)   brand   38 ( 5 %)

Three of those have no counterpart in either country's feature stack -- fire history,
reindeer grazing, and lichen ground cover -- and one, bedrock outcrop, is only covered at
the 1:1 M scale of the coarse SGU layer. Before anyone spends a week building a burned-area
raster or chasing the Sametinget grazing boundary, the cheap question is whether those words
are already predictable from the features we have, and whether the model is visibly worse on
the records that carry them.

TWO TESTS, NEITHER NEEDING A NEW RASTER

1. probe()  Can FEATURES_SE already tell a labelled record from an unlabelled one? Logistic
   regression, scored out-of-fold on the SAME spatial blocks train.py uses. The blocks are
   not optional: these labels are heavily clustered (one observer describing forty stops on
   one hillside the same way), and a random split would report a beautiful AUC for a model
   that had memorised the hillside. AUC near 0.5 means the word describes something no
   current layer encodes, and the distance above 0.5 is how much of it is already implicit.

2. score_delta()  Do records carrying the word score LOWER under the trained model than
   records that do not? This is the decision-relevant one. If burn-scar finds sit
   systematically below the rest, the model is blind to a habitat it is being asked to
   predict, and the effect size says how much recall that costs. Significance is a two-sided
   permutation test rather than a t-test: with n = 38 for `brand` against ~600, a
   permutation test is exact and a t-test is an assumption.

3. A latitude control for `renbet`. Reindeer husbandry occupies the northern half of Sweden,
   so a grazing signal and a latitude signal are easy to confuse. probe() is run twice for
   that word -- once on the full feature set, once on northing and elevation alone. If
   latitude alone gets most of the AUC, a grazing-boundary layer would mostly be adding
   latitude, which train.py's with_latitude_only ablation already warns about.

    python ml/experiments/habitat_words_se.py [--species matsutake_se] [--perm 10000]
"""
import argparse, csv, os, sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
ROOT = os.path.dirname(ML)
sys.path.insert(0, os.path.join(ML, "core"))
sys.path.insert(0, os.path.join(ML, "train"))

from registry import features as features_for                    # noqa: E402
from train import assign_folds, load                             # noqa: E402

# Substring sets, matched case-folded against habitat + remarks + locality. Deliberately
# blunt: these are labels for a screening test, not a classification anyone will ship.
KEYWORDS = {
    "sand": ("sand",),                          # sandtallskog, sandig, flygsand
    "lav": ("lav",),                            # lavtallskog, lavflack, renlav, lavhed
    "moran": ("morän", "moran"),
    "hed": ("hed",),                            # tallhed, hedartad, sandhed
    "renbet": ("renbet", "rengärd"),            # reindeer-grazed
    "hallmark": ("hällmark", "hallmark", "berghäll"),
    "brand": ("brän", "brand", "brunn"),        # naturvårdsbränd, brandfält, brandpräglat
    "as": ("rullsten", "grusås", "tallås", "sandås", "åsrygg"),
}


def label_table(species):
    """{gbif id: {word: 0/1}} over the records that carry any free text at all.

    The comparison set is the records that DID get a description but did not use the word,
    not every presence: someone who wrote nothing tells us nothing about whether their site
    had burned, and counting their silence as "no fire" would bury the signal.
    """
    path = os.path.join(ML, "data", species, "observations.csv")
    out = {}
    for r in csv.DictReader(open(path, newline="")):
        text = " ".join(filter(None, (r.get("habitat"), r.get("remarks"),
                                      r.get("locality")))).lower()
        if not (r.get("habitat") or "").strip():
            continue                            # habitat field only: remarks are about the find
        out[r["id"]] = {w: int(any(k in text for k in keys)) for w, keys in KEYWORDS.items()}
    return out


def probe(X, y, folds, seed=0):
    """Out-of-fold AUC of logistic regression from features to a binary word label."""
    if y.sum() < 8 or (1 - y).sum() < 8:
        return float("nan")
    oof = np.zeros(len(y))
    for f in sorted(set(folds)):
        tr, te = folds != f, folds == f
        if y[tr].sum() < 3 or (1 - y[tr]).sum() < 3 or te.sum() == 0:
            oof[te] = y[tr].mean() if tr.sum() else 0.5
            continue
        mu, sd = np.nanmean(X[tr], 0), np.nanstd(X[tr], 0)
        sd[sd == 0] = 1.0
        Z = np.nan_to_num((X - mu) / sd)
        m = LogisticRegression(max_iter=2000, C=0.3).fit(Z[tr], y[tr])
        oof[te] = m.predict_proba(Z[te])[:, 1]
    try:
        return float(roc_auc_score(y, oof))
    except ValueError:
        return float("nan")


def score_delta(score, y, n_perm=10000, seed=0):
    """(mean score with the word) - (without), and a two-sided permutation p-value."""
    if y.sum() < 3 or (1 - y).sum() < 3:
        return float("nan"), float("nan")
    obs = float(score[y == 1].mean() - score[y == 0].mean())
    rng = np.random.default_rng(seed)
    k = int(y.sum())
    idx = np.arange(len(y))
    hits = 0
    for _ in range(n_perm):
        pick = rng.choice(idx, k, replace=False)
        mask = np.zeros(len(y), bool)
        mask[pick] = True
        if abs(float(score[mask].mean() - score[~mask].mean())) >= abs(obs):
            hits += 1
    return obs, (hits + 1) / (n_perm + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake_se")
    ap.add_argument("--perm", type=int, default=10000)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "HABITAT_WORDS_SE.md"))
    a = ap.parse_args()

    d = load(os.path.join(ML, "data", a.species, "dataset.csv"))
    folds = np.asarray(assign_folds(d, seed=0))
    cols = [c for c in features_for("se") if c in d.columns]

    labels = label_table(a.species)
    pres = d[(d.y == 1) & d["id"].astype(str).isin(labels)].copy()
    pres_folds = folds[pres.index.values]
    X = pres[cols].to_numpy(dtype=float)
    print(f"{len(pres)} presences carry a habitat description, of {int(d.y.sum())} presences")

    oof_path = os.path.join(ML, "models", a.species, "oof_scores.csv")
    oof = None
    if os.path.exists(oof_path):
        o = pd.read_csv(oof_path, dtype={"id": str})
        # Name the score column rather than taking "the first one that is not id or group" --
        # that picked `lat`, and the experiment then reported latitude differences between
        # word groups as if they were model-score differences, with deltas of -3.6 on a score
        # that lives in [0, 1].
        col = next((c for c in o.columns if c.startswith("score")), None)
        if col is None:
            raise SystemExit(f"no score column in {oof_path}; has {list(o.columns)}")
        oof = dict(zip(o["id"], o[col]))
        print(f"model scores from {os.path.basename(oof_path)} column {col!r}")
    else:
        print("no oof_scores.csv yet -- run train.py --country se first; "
              "the score-delta column will be blank")

    rows = []
    for word in KEYWORDS:
        y = np.array([labels[str(i)][word] for i in pres["id"].astype(str)])
        auc = probe(X, y, pres_folds)
        lat_auc = float("nan")
        if word == "renbet":
            ctrl = pres[["northing", "elev"]].to_numpy(dtype=float)
            lat_auc = probe(ctrl, y, pres_folds)
        delta = p = float("nan")
        if oof:
            s = np.array([oof.get(str(i), np.nan) for i in pres["id"].astype(str)])
            ok = np.isfinite(s)
            if ok.sum() > 20:
                delta, p = score_delta(s[ok], y[ok], a.perm)
        rows.append(dict(word=word, n=int(y.sum()), auc=auc, lat_auc=lat_auc,
                         delta=delta, p=p))
        print(f"  {word:10s} n={int(y.sum()):4d}  AUC {auc:.3f}"
              + (f"  (northing+elev alone {lat_auc:.3f})" if np.isfinite(lat_auc) else "")
              + (f"  score delta {delta:+.3f} p={p:.4f}" if np.isfinite(delta) else ""))

    write_report(rows, a, len(pres))


MIN_N = 20              # below this the probe is noise, whatever it returns


def verdict(r):
    if not np.isfinite(r["auc"]) or r["n"] < MIN_N:
        return f"too few labelled records to test (n={r['n']})"
    # An out-of-fold AUC well BELOW 0.5 is not inverse predictive power. With labels this
    # clustered -- one observer describing a whole hillside the same way -- it means the
    # probe learned a within-block association that does not survive being asked about a
    # block it has not seen. Read as "no generalizable signal", same as 0.5.
    if r["auc"] >= 0.70:
        if np.isfinite(r["p"]) and r["p"] < 0.05 and r["delta"] < 0:
            # The interesting case, and the one the original design did not anticipate: the
            # features CAN identify this habitat, and the model still scores it down. That is
            # not a missing layer, it is the model disagreeing with the people who found the
            # mushrooms -- and the people were there.
            return ("**seen but penalised** — the features predict this word well, yet the "
                    "model scores these finds significantly lower")
        base = "already covered — the current features predict this word well"
    elif 0.42 <= r["auc"] <= 0.58:
        base = "**not encoded** — no current layer sees this"
    elif r["auc"] < 0.42:
        base = "**not encoded** — the probe does not generalize across blocks at all"
    else:
        base = "partly covered"
    if r["word"] == "renbet" and np.isfinite(r["lat_auc"]) and r["lat_auc"] >= r["auc"] - 0.03:
        return base + "; **latitude confound** — northing and elevation alone do as well"
    if base.startswith("**not encoded**"):
        if np.isfinite(r["p"]) and r["p"] < 0.05 and r["delta"] < 0:
            return base + ", and the model scores these finds lower: **a new layer is justified**"
        return base + ", but the model does not visibly suffer on these finds"
    return base


def write_report(rows, a, n_pres):
    L = ["# Swedish habitat words vs the model's features", "",
         f"Generated by `ml/experiments/habitat_words_se.py` over {n_pres} presences that "
         f"carry an Artportalen `habitat` description.", "",
         "`AUC` is out-of-fold logistic regression from `FEATURES_SE` to the word, on the same",
         "spatial blocks `train.py` uses — a random split would flatter it badly, because one",
         "observer often describes forty stops on one hillside the same way. `score delta` is the",
         "trained model's mean out-of-fold score on records carrying the word minus those without,",
         "with a two-sided permutation p-value.", "",
         "| word | n | AUC from features | model score delta | p | verdict |",
         "|---|---:|---:|---:|---:|---|"]
    for r in sorted(rows, key=lambda r: -r["n"]):
        auc = f"{r['auc']:.3f}" if np.isfinite(r["auc"]) else "—"
        if r["word"] == "renbet" and np.isfinite(r["lat_auc"]):
            auc += f" (lat {r['lat_auc']:.3f})"
        dl = f"{r['delta']:+.3f}" if np.isfinite(r["delta"]) else "—"
        pv = f"{r['p']:.4f}" if np.isfinite(r["p"]) else "—"
        L.append(f"| `{r['word']}` | {r['n']} | {auc} | {dl} | {pv} | {verdict(r)} |")
    L += ["", "## How to read this", "",
          "A word with a **low AUC** describes something none of the current rasters encode. That",
          "alone is not a reason to build a layer — the model may be finding those sites anyway",
          "through other features. The reason to build one is a low AUC **together with** a",
          "negative score delta: the model cannot see the habitat, and it is visibly failing on",
          "the finds that have it.", "",
          "An AUC well **below** 0.5 is not inverse predictive power. With labels this clustered —",
          "one observer describing a whole hillside the same way — it means the probe learned a",
          "within-block association that does not survive being asked about an unseen block. Read",
          "it as no generalizable signal, the same as 0.5.", "",
          "**seen but penalised** is the row worth acting on first. The features identify the",
          "habitat perfectly well and the model still scores it down, so the fix is not a new",
          "raster — it is that the model is disagreeing with people who were standing on the",
          "ground.", "",
          "`n` counts distinct 12.5 m cells, not records: `build_dataset_se.py` collapses repeat",
          "reports of the same cell, because a second report measures a picker's return visit",
          "rather than a second habitat. That is why `renbet` falls from 79 records to 9 cells —",
          "reindeer-grazed sites are exactly the ones people revisit — and why it cannot be",
          "tested here at all.", "",
          "`renbet` carries a second AUC from northing and elevation alone. Reindeer husbandry",
          "occupies the northern half of Sweden, so a grazing signal and a latitude signal are",
          "easy to confuse; if the control is close to the full-feature AUC, a Sametinget",
          "boundary layer would mostly be re-adding latitude, which `train.py`'s",
          "`with_latitude_only` ablation already watches for.", ""]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write("\n".join(L) + "\n")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
