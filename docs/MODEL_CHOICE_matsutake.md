# Which model the matsutake map is made of

The map used to be the neural network (`mlp`). It is now the gradient-boosted trees (`lgbm`).
This note records why, because the single cross-validation run in
[MODEL_REPORT_matsutake.md](MODEL_REPORT_matsutake.md) is not enough evidence to choose on.

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

`ml/compare_heads.py` repeats the whole comparison over five splits. Mean over those splits:

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

**LightGBM alone.** It is the clear winner on Boyce (+0.05 over the neural network, consistent in
sign across every split) and on precision at 5 %, and it is level at 2 %. The mixed heads buy
about three percentage points of precision at exactly 1 % and give back a similar amount of Boyce,
which is a trade, not an improvement — and the Boyce differences between the mixtures are inside
their own noise, so there is nothing there to select on either.

Two things decided it beyond the table:

* **Extrapolation.** The map is applied to about three billion cells, most of them in feature
  combinations no training row is near. Trees predict a constant outside the training range;
  a network keeps extrapolating linearly and can come back very confident about nothing. On a
  country-wide raster that asymmetry matters more than a third of a standard deviation of
  precision.
* **A map you can read.** The Boyce index is the one metric that says the colours are ordered
  correctly rather than merely separating the top from the bottom. Sorting sites — which is the
  whole task once the map is set to its tightest — is exactly what it measures.

Hyper-parameters are now selected with `--select sure`, on precision in the best 2 % rather than
on overall PR-AUC. `--head mlp` and `--head mlp+lgbm` remain in `ml/train.py`, so the choice can
be revisited when the observation set grows.

## What the map is worth at each setting

From the head's out-of-fold threshold curve (the full table is in the model report):

| Map covers | Finds inside it | Matsutake share of fungus-reporting sites | Lift vs random forest |
|---|---|---|---|
| best 0.25 % | 14 % | 72 % | 59× |
| best 0.5 % | 23 % | 66 % | 48× |
| best 1 % | 31 % | 52 % | 31× |
| best 2 % | 41 % | 41 % | 21× |
| best 5 % | 61 % | 30 % | 12× |
| best 15 % | 79 % | 13 % | 5× |

Read the first column as "how much walking" and the second as "how often it was somebody's lucky
day". The shipped raster stores the best 15 % of forest land and the app's slider stops at
0.25 %, which is the tightest the stored quantisation can resolve.

These numbers are cross-validated but optimistic in one respect that no split can fix: the
records are where people looked, and people look near roads, near cabins and in known spots. The
model's target-group background corrects for a good part of that, not all of it.
