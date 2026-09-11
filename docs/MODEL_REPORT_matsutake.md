# Habitat model report — matsutake

Rows: 5837 (presences 109, random-forest background 3000, other-fungi background 2587); 62 features; 5-fold spatial block CV (25 km blocks).

Map head: **lgbm** (hyper-parameters chosen for precision in the best 2 %).

## Models (pooled out-of-fold)

| Model | AUC vs fungi | PR-AUC vs fungi | recall@2 % | prec@2 % | recall@5 % | prec@5 % | recall@10 % | Boyce |
|---|---|---|---|---|---|---|---|---|
| rule_old_default | 0.591 | 0.076 | 0.101 | 0.138 | 0.156 | 0.101 | 0.239 | 0.683 |
| rule_new_default | 0.741 | 0.129 | 0.156 | 0.17 | 0.394 | 0.161 | 0.587 | 0.506 |
| rule_E | 0.708 | 0.117 | 0.147 | 0.18 | 0.257 | 0.137 | 0.459 | 0.644 |
| logreg | 0.879 | 0.373 | 0.45 | 0.43 | 0.651 | 0.212 | 0.771 | 0.819 |
| gam | 0.88 | 0.381 | 0.394 | 0.434 | 0.587 | 0.245 | 0.798 | 0.827 |
| maxent | 0.889 | 0.419 | 0.468 | 0.398 | 0.661 | 0.216 | 0.807 | 0.908 |
| lgbm | 0.88 | 0.401 | 0.413 | 0.413 | 0.615 | 0.3 | 0.725 | 0.911 |
| xgb | 0.866 | 0.385 | 0.413 | 0.405 | 0.578 | 0.269 | 0.734 | 0.816 |
| mlp | 0.883 | 0.345 | 0.422 | 0.414 | 0.67 | 0.259 | 0.798 | 0.812 |
| head:lgbm | 0.88 | 0.401 | 0.413 | 0.413 | 0.615 | 0.3 | 0.725 | 0.911 |

recall@k %: share of held-out finds scoring above the top-k % of random forest cells (i.e. if the map is coloured over k % of forest land). prec@k %: of the fungus-reporting sites inside that coloured area, the share that are matsutake finds — what a visit to a coloured cell is worth, and the number to watch for a deliberately tight map.

All models are fitted in the presence-background setting: presences vs. a background made of random forestry-land cells (what habitat is available) and other-fungi observation sites (where people actually look, i.e. the target-group correction for observer bias). `maxent` is the MaxEnt-equivalent infinitely-weighted L1 logistic regression on MaxEnt feature classes (linear, quadratic, forward/reverse hinges); `gam` is a spline-basis logistic GAM; `logreg` is a ridge logistic regression; `lgbm`/`xgb` are gradient-boosted trees; `mlp` is a neural network. The row named `head:` is the one the exported map is made of. Configs are the best of a small grid on the same folds (slightly optimistic, the MLP's nested-CV config aside), so read the head's own numbers as the optimistic end of its range.

## Threshold curve of the map head (lgbm, out-of-fold)

| Map covers (share of forest) | Recall of finds | Other-fungi sites kept | Matsutake share of fungi sites | Lift vs random |
|---|---|---|---|---|
| 0.25 % | 14 % | 0 % | 72 % | 58.7× |
| 0.5 % | 23 % | 0 % | 66 % | 47.7× |
| 1 % | 31 % | 1 % | 52 % | 31.2× |
| 2 % | 41 % | 2 % | 41 % | 20.6× |
| 5 % | 61 % | 6 % | 30 % | 12.3× |
| 10 % | 72 % | 14 % | 17 % | 7.2× |
| 15 % | 79 % | 22 % | 13 % | 5.3× |
| 20 % | 82 % | 28 % | 10 % | 4.1× |
| 30 % | 91 % | 40 % | 8 % | 3.1× |
| 50 % | 97 % | 60 % | 6 % | 1.9× |

## Rank-averaged ensembles (same folds)

| Ensemble | AUC vs fungi | PR-AUC vs fungi | recall@5 % | recall@10 % | recall@20 % | Boyce |
|---|---|---|---|---|---|---|
| mlp+lgbm | 0.889 | 0.398 | 0.679 | 0.798 | 0.908 | 0.886 |
| mlp+maxent | 0.889 | 0.401 | 0.67 | 0.807 | 0.853 | 0.86 |
| mlp+lgbm+maxent | 0.893 | 0.417 | 0.679 | 0.798 | 0.872 | 0.862 |
| all | 0.89 | 0.426 | 0.661 | 0.807 | 0.872 | 0.923 |

Rank averages cannot be stored in the map (they have no probability scale), so a rank ensemble can only ever be a comparison; `--head mlp+lgbm` averages the two probabilities instead.

Best MLP config: `{"hidden": 32, "depth": 1, "dropout": 0.4, "wd": 0.001, "lr": 0.001}`

## Ablations (MLP, same folds)

| Variant | PR-AUC vs fungi | recall@5 % | recall@10 % | Boyce |
|---|---|---|---|---|
| full | 0.345 | 0.67 | 0.798 | 0.812 |
| without_soil | 0.257 | 0.596 | 0.688 | 0.878 |
| without_terrain | 0.351 | 0.624 | 0.734 | 0.796 |
| without_climate | 0.37 | 0.661 | 0.734 | 0.858 |
| without_neigh | 0.285 | 0.624 | 0.688 | 0.858 |
| with_location | 0.427 | 0.67 | 0.761 | 0.652 |

## Hyper-parameter trials

| PR-AUC vs fungi | recall@5 % | config |
|---|---|---|
| 0.345 | 0.651 | `{"hidden": 32, "depth": 1, "dropout": 0.4, "wd": 0.001, "lr": 0.001}` |
| 0.373 | 0.679 | `{"hidden": 128, "depth": 1, "dropout": 0.1, "wd": 0.01, "lr": 0.001}` |
| 0.348 | 0.642 | `{"hidden": 128, "depth": 1, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.323 | 0.697 | `{"hidden": 128, "depth": 2, "dropout": 0.4, "wd": 0.01, "lr": 0.001}` |
| 0.327 | 0.697 | `{"hidden": 64, "depth": 1, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.323 | 0.67 | `{"hidden": 128, "depth": 2, "dropout": 0.25, "wd": 0.0001, "lr": 0.003}` |
| 0.338 | 0.706 | `{"hidden": 64, "depth": 2, "dropout": 0.25, "wd": 0.001, "lr": 0.001}` |
| 0.333 | 0.642 | `{"hidden": 64, "depth": 2, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.297 | 0.679 | `{"hidden": 64, "depth": 3, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.28 | 0.688 | `{"hidden": 64, "depth": 3, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.299 | 0.679 | `{"hidden": 64, "depth": 3, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.288 | 0.679 | `{"hidden": 32, "depth": 3, "dropout": 0.25, "wd": 0.01, "lr": 0.001}` |
