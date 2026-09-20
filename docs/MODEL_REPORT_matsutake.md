# Habitat model report — matsutake

Rows: 5845 (presences 112, random-forest background 3000, other-fungi background 2587); 63 features; 5-fold spatial block CV (25 km blocks).

Map head: **mlp+lgbm** (hyper-parameters chosen for precision in the best 2 %).

## Models (pooled out-of-fold)

| Model | AUC vs fungi | PR-AUC vs fungi | recall@2 % | prec@2 % | recall@5 % | prec@5 % | recall@10 % | Boyce |
|---|---|---|---|---|---|---|---|---|
| rule_old_default | 0.56 | 0.081 | 0.116 | 0.159 | 0.152 | 0.101 | 0.214 | 0.362 |
| rule_new_default | 0.726 | 0.127 | 0.196 | 0.183 | 0.384 | 0.154 | 0.589 | 0.465 |
| rule_E | 0.685 | 0.121 | 0.161 | 0.209 | 0.286 | 0.139 | 0.473 | 0.439 |
| logreg | 0.865 | 0.322 | 0.42 | 0.448 | 0.598 | 0.205 | 0.75 | 0.841 |
| gam | 0.866 | 0.315 | 0.411 | 0.407 | 0.598 | 0.205 | 0.759 | 0.931 |
| maxent | 0.854 | 0.257 | 0.411 | 0.346 | 0.589 | 0.161 | 0.732 | 0.816 |
| lgbm | 0.855 | 0.275 | 0.33 | 0.374 | 0.455 | 0.222 | 0.652 | 0.935 |
| xgb | 0.853 | 0.278 | 0.348 | 0.371 | 0.509 | 0.243 | 0.652 | 0.966 |
| mlp | 0.87 | 0.306 | 0.339 | 0.409 | 0.616 | 0.234 | 0.795 | 0.894 |
| head:mlp+lgbm | 0.872 | 0.317 | 0.375 | 0.372 | 0.562 | 0.25 | 0.759 | 0.917 |

recall@k %: share of held-out finds scoring above the top-k % of random forest cells (i.e. if the map is coloured over k % of forest land). prec@k %: of the fungus-reporting sites inside that coloured area, the share that are matsutake finds — what a visit to a coloured cell is worth, and the number to watch for a deliberately tight map.

All models are fitted in the presence-background setting: presences vs. a background made of random forestry-land cells (what habitat is available) and other-fungi observation sites (where people actually look, i.e. the target-group correction for observer bias). `maxent` is the MaxEnt-equivalent infinitely-weighted L1 logistic regression on MaxEnt feature classes (linear, quadratic, forward/reverse hinges); `gam` is a spline-basis logistic GAM; `logreg` is a ridge logistic regression; `lgbm`/`xgb` are gradient-boosted trees; `mlp` is a neural network. The row named `head:` is the one the exported map is made of. Configs are the best of a small grid on the same folds (slightly optimistic, the MLP's nested-CV config aside), so read the head's own numbers as the optimistic end of its range.

## Threshold curve of the map head (mlp+lgbm, out-of-fold)

| Map covers (share of forest) | Recall of finds | Other-fungi sites kept | Matsutake share of fungi sites | Lift vs random |
|---|---|---|---|---|
| 0.25 % | 9 % | 0 % | 52 % | 39.3× |
| 0.5 % | 17 % | 0 % | 52 % | 35.7× |
| 1 % | 29 % | 1 % | 52 % | 29.5× |
| 2 % | 37 % | 2 % | 37 % | 18.8× |
| 5 % | 56 % | 7 % | 25 % | 11.2× |
| 10 % | 75 % | 17 % | 15 % | 7.6× |
| 15 % | 82 % | 25 % | 12 % | 5.5× |
| 20 % | 84 % | 30 % | 10 % | 4.2× |
| 30 % | 93 % | 41 % | 8 % | 3.1× |
| 50 % | 96 % | 61 % | 6 % | 1.9× |

## Rank-averaged ensembles (same folds)

| Ensemble | AUC vs fungi | PR-AUC vs fungi | recall@5 % | recall@10 % | recall@20 % | Boyce |
|---|---|---|---|---|---|---|
| mlp+lgbm | 0.873 | 0.311 | 0.571 | 0.75 | 0.866 | 0.93 |
| mlp+maxent | 0.868 | 0.29 | 0.598 | 0.795 | 0.848 | 0.652 |
| mlp+lgbm+maxent | 0.874 | 0.308 | 0.598 | 0.804 | 0.848 | 0.889 |
| all | 0.878 | 0.319 | 0.571 | 0.795 | 0.857 | 0.849 |

Rank averages cannot be stored in the map (they have no probability scale), so a rank ensemble can only ever be a comparison; `--head mlp+lgbm` averages the two probabilities instead.

Best MLP config: `{"hidden": 128, "depth": 2, "dropout": 0.4, "wd": 0.01, "lr": 0.001}`

## Ablations (MLP, same folds)

| Variant | PR-AUC vs fungi | recall@5 % | recall@10 % | Boyce |
|---|---|---|---|---|
| full | 0.306 | 0.616 | 0.795 | 0.894 |
| without_soil | 0.153 | 0.446 | 0.571 | 0.905 |
| without_terrain | 0.291 | 0.625 | 0.732 | 0.812 |
| without_climate | 0.308 | 0.616 | 0.768 | 0.819 |
| without_neigh | 0.265 | 0.554 | 0.759 | 0.684 |
| without_structure | 0.305 | 0.625 | 0.741 | 0.797 |
| with_location | 0.349 | 0.634 | 0.768 | 0.603 |

## Hyper-parameter trials

| PR-AUC vs fungi | recall@5 % | config |
|---|---|---|
| 0.313 | 0.571 | `{"hidden": 128, "depth": 2, "dropout": 0.4, "wd": 0.01, "lr": 0.001}` |
| 0.309 | 0.607 | `{"hidden": 64, "depth": 3, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.318 | 0.643 | `{"hidden": 32, "depth": 1, "dropout": 0.4, "wd": 0.001, "lr": 0.001}` |
| 0.273 | 0.571 | `{"hidden": 64, "depth": 1, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.287 | 0.589 | `{"hidden": 64, "depth": 3, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.321 | 0.634 | `{"hidden": 64, "depth": 2, "dropout": 0.25, "wd": 0.001, "lr": 0.001}` |
| 0.293 | 0.562 | `{"hidden": 128, "depth": 1, "dropout": 0.1, "wd": 0.01, "lr": 0.001}` |
| 0.301 | 0.518 | `{"hidden": 128, "depth": 2, "dropout": 0.25, "wd": 0.0001, "lr": 0.003}` |
| 0.293 | 0.571 | `{"hidden": 128, "depth": 1, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.253 | 0.571 | `{"hidden": 64, "depth": 2, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.279 | 0.67 | `{"hidden": 32, "depth": 3, "dropout": 0.25, "wd": 0.01, "lr": 0.001}` |
| 0.307 | 0.598 | `{"hidden": 64, "depth": 3, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
