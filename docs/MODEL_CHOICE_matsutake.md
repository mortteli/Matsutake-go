# Which model the matsutake map is made of

The map used to be the neural network (`mlp`), then the gradient-boosted trees (`lgbm`). Since
2026-09-20 it is the average of the two (`mlp+lgbm`). This note records why, because the single
cross-validation run in [MODEL_REPORT_matsutake.md](MODEL_REPORT_matsutake.md) is not enough
evidence to choose on.

## The question the map is actually asked

Not "how much of the country's matsutake habitat can you colour in" but "if I drive there, will
there be matsutake". Those pull in opposite directions, and the earlier model was tuned for the
first one: hyper-parameters were selected on PR-AUC, the headline number was recall at 5–10 % of
forest land, and the app's slider could not go below 1 %.

So the comparison here is scored on the tight end instead:

* **recall@k %** — of the held-out finds, how many are inside the best k % of forest land.
  This is the old measure, kept for continuity.
* **prec@k %** — of the fungus-reporting sites inside that same area, how many are matsutake.
  Both presences and the other-fungi background are places somebody actually walked to and
  reported from, so this ratio is the closest thing the data has to "was the trip worth it",
  with the observer-effort bias divided out.
* **Boyce index** — whether the predicted/expected ratio rises monotonically with the score,
  i.e. whether a higher number on the map really does mean a better cell. A map read only at its
  top needs this; a map read as a yes/no mask does not.

## One split is not evidence

The evaluation set is 109 precisely-located finds. Across five different 5-fold spatial block
splits of the same data, one model's Boyce index moves by ±0.07 and its recall@1 % by ±0.02 —
enough for any family to win by luck. The 0.982 Boyce that LightGBM scored in the first report
was one such lucky split; its honest value is 0.92.

`ml/train/compare_heads.py` repeats the whole comparison over five splits. Mean over those splits:

| Model | recall@1 % | prec@1 % | recall@2 % | prec@2 % | recall@5 % | prec@5 % | Boyce |
|---|---|---|---|---|---|---|---|
| lgbm | 0.336 | 0.520 | 0.429 | 0.416 | 0.587 | 0.266 | **0.919** |
| mlp | 0.325 | 0.483 | 0.424 | 0.378 | **0.640** | 0.227 | 0.870 |
| min(mlp, lgbm) | 0.354 | 0.554 | 0.437 | **0.423** | 0.593 | 0.262 | 0.860 |
| √(mlp · lgbm) | **0.356** | **0.556** | 0.444 | 0.422 | 0.615 | 0.251 | 0.831 |
| (mlp + lgbm)/2 | 0.356 | 0.553 | 0.439 | 0.414 | 0.628 | 0.249 | 0.795 |
| rank average | 0.354 | 0.525 | **0.448** | 0.415 | 0.635 | 0.236 | 0.813 |

Paired against LightGBM on the identical splits (mean ± sd of the per-split difference):

| Against lgbm | recall@1 % | prec@1 % | prec@2 % | prec@5 % | Boyce |
|---|---|---|---|---|---|
| mlp | −0.011 ± 0.013 | −0.038 ± 0.020 | −0.038 ± 0.055 | −0.040 ± 0.019 | −0.049 ± 0.053 |
| min(mlp, lgbm) | +0.018 ± 0.011 | +0.033 ± 0.020 | +0.007 ± 0.011 | −0.004 ± 0.006 | −0.059 ± 0.060 |
| √(mlp · lgbm) | +0.020 ± 0.010 | +0.036 ± 0.029 | +0.006 ± 0.013 | −0.016 ± 0.012 | −0.088 ± 0.108 |
| rank average | +0.018 ± 0.013 | +0.005 ± 0.018 | −0.001 ± 0.028 | −0.030 ± 0.010 | −0.106 ± 0.086 |

## The choice

**LightGBM alone** — until 2026-09-20. It was the clear winner on Boyce (+0.05 over the neural
network, consistent in sign across every split) and on precision at 5 %, and level at 2 %. The
mixed heads bought about three percentage points of precision at exactly 1 % and gave back a
similar amount of Boyce, which was a trade, not an improvement.

Two things decided it beyond the table:

* **Extrapolation.** The map is applied to about three billion cells, most of them in feature
  combinations no training row is near. Trees predict a constant outside the training range;
  a network keeps extrapolating linearly and can come back very confident about nothing. On a
  country-wide raster that asymmetry matters more than a third of a standard deviation of
  precision.
* **A map you can read.** The Boyce index is the one metric that says the colours are ordered
  correctly rather than merely separating the top from the bottom. Sorting sites — which is the
  whole task once the map is set to its tightest — is exactly what it measures.

Hyper-parameters are selected with `--select sure`, on precision in the best 2 % rather than on
overall PR-AUC.

## Revisited 2026-09-20: the average of the two

The note above ends by saying the choice can be revisited when the observation set grows. It has:
the laji.fi refetch took the evaluation set from 109 precisely-located finds to 112 and refreshed
the records behind the rest, and §12 of the plan added `keskilapimitta` and `stems_ha` to the
features. Retrained on that table with the same folds and seeds, so that nothing but the head
differs:

| Head | AUC vs fungi | PR-AUC vs fungi | recall@2 % | prec@2 % | recall@5 % | prec@5 % | Boyce |
|---|---|---|---|---|---|---|---|
| lgbm | 0.855 | 0.275 | 0.330 | **0.374** | 0.455 | 0.222 | **0.935** |
| mlp | 0.870 | 0.306 | 0.339 | 0.409 | **0.616** | 0.234 | 0.894 |
| **mlp+lgbm** | **0.872** | **0.317** | **0.375** | 0.372 | 0.562 | **0.250** | 0.917 |

and paired over five fold splits, `(mlp + lgbm)/2` against `lgbm` on the identical splits:
recall@2 % +0.014 ± 0.021, prec@2 % +0.030 ± 0.028, recall@5 % +0.032 ± 0.039,
recall@10 % +0.063 ± 0.034, Boyce −0.041 ± 0.053.

**The average now wins.** It is ahead on both AUCs, both PR-AUCs, recall at every level and
precision at 1 % and 5 %; it is level at prec@2 % and it gives up Boyce. That is the same trade
the 2026-09-11 note refused — the difference is the size of it. Then the mixtures bought
precision only at 1 % and paid Boyce for it; now they buy 0.11 of recall@5 % and 0.04 of PR-AUC
for 0.018 of Boyce on this split. A map that finds a tenth more of the real sites at the same
precision is worth a slightly less perfectly ordered ramp.

The extrapolation argument above still holds and is the reason the head is the *average* rather
than the network alone: half of every published score is still a tree model that cannot run away
outside the training range.

One caveat, recorded because it decides nothing here but would decide a closer call: `lgbm`'s own
row is worse than it should be. `--select sure` scores the two LightGBM configs on prec@2 % on a
single split, and on this split it picked the 300-tree one (prec@2 % 0.374 against 0.355) which
is the weaker of the two on recall. Over five splits with the 400-tree config fixed, `lgbm`
averages recall@5 % 0.564, not the 0.455 in the table. The averaged head beats it either way.

## What the map is worth at each setting

From the head's out-of-fold threshold curve (the full table is in the model report):

| Map covers | Finds inside it | Matsutake share of fungus-reporting sites | Lift vs random forest |
|---|---|---|---|
| best 0.25 % | 10 % | 52 % | 39× |
| best 0.5 % | 18 % | 53 % | 36× |
| best 1 % | 30 % | 52 % | 30× |
| best 2 % | 38 % | 37 % | 19× |
| best 5 % | 56 % | 25 % | 11× |
| best 15 % | 82 % | 12 % | 5× |

Read the first column as "how much walking" and the second as "how often it was somebody's lucky
day". The shipped raster stores the best 15 % of forest land and the app's slider stops at
0.25 %, which is the tightest the stored quantisation can resolve.

These numbers are cross-validated but optimistic in one respect that no split can fix: the
records are where people looked, and people look near roads, near cabins and in known spots. The
model's target-group background corrects for a good part of that, not all of it.

They are also lower at the very top than the 2026-09-11 table above, which read 72 % at the best
0.25 %. That is not the head getting worse: the evaluation set changed with the observation
refetch, and a 0.25 % slice of it holds about eleven finds, so a couple of records moving swings
the number by ten points. The 5 % and 15 % rows, which rest on far more finds, are the stable
ones to compare.
