# Habitat model report — matsutake

Rows: 5837 (presences 109, random-forest background 3000, other-fungi background 2587); 62 features; 5-fold spatial block CV (25 km blocks).

## Models (pooled out-of-fold)

| Model | AUC vs fungi | PR-AUC vs fungi | AUC vs random | recall@5 % | recall@10 % | recall@20 % | Boyce |
|---|---|---|---|---|---|---|---|
| rule_old_default | 0.591 | 0.076 | 0.601 | 0.156 | 0.239 | 0.358 | 0.683 |
| rule_new_default | 0.741 | 0.129 | 0.773 | 0.394 | 0.587 | 0.661 | 0.506 |
| rule_E | 0.708 | 0.117 | 0.732 | 0.257 | 0.459 | 0.587 | 0.644 |
| logreg | 0.879 | 0.373 | 0.912 | 0.651 | 0.771 | 0.881 | 0.819 |
| gam | 0.877 | 0.399 | 0.905 | 0.606 | 0.771 | 0.862 | 0.863 |
| maxent | 0.888 | 0.418 | 0.913 | 0.661 | 0.807 | 0.853 | 0.908 |
| lgbm | 0.883 | 0.432 | 0.913 | 0.587 | 0.743 | 0.881 | 0.982 |
| xgb | 0.866 | 0.385 | 0.896 | 0.578 | 0.734 | 0.862 | 0.816 |
| mlp | 0.881 | 0.367 | 0.911 | 0.661 | 0.798 | 0.881 | 0.888 |

recall@k %: share of held-out finds scoring above the top-k % of random forest cells (i.e. if the map is coloured over k % of forest land).

All models are fitted in the presence-background setting: presences vs. a background made of random forestry-land cells (what habitat is available) and other-fungi observation sites (where people actually look, i.e. the target-group correction for observer bias). `maxent` is the MaxEnt-equivalent infinitely-weighted L1 logistic regression on MaxEnt feature classes (linear, quadratic, forward/reverse hinges); `gam` is a spline-basis logistic GAM; `logreg` is a ridge logistic regression; `lgbm`/`xgb` are gradient-boosted trees; `mlp` is the neural network used for the map. Baseline configs are the best of a small grid on the same folds (slightly optimistic for them, not for the MLP whose config is chosen by nested CV).

## MLP threshold curve (out-of-fold)

| Map covers (share of forest) | Recall of finds | Other-fungi sites kept | Lift vs random |
|---|---|---|---|
| 1 % | 32 % | 1 % | 32.1× |
| 2 % | 44 % | 2 % | 22.0× |
| 5 % | 66 % | 8 % | 13.2× |
| 10 % | 79 % | 17 % | 8.0× |
| 15 % | 85 % | 23 % | 5.7× |
| 20 % | 88 % | 29 % | 4.4× |
| 30 % | 91 % | 41 % | 3.1× |
| 50 % | 95 % | 59 % | 1.9× |

## Rank-averaged ensembles (same folds)

| Ensemble | AUC vs fungi | PR-AUC vs fungi | recall@5 % | recall@10 % | recall@20 % | Boyce |
|---|---|---|---|---|---|---|
| mlp+lgbm | 0.891 | 0.413 | 0.661 | 0.798 | 0.908 | 0.794 |
| mlp+maxent | 0.888 | 0.41 | 0.67 | 0.807 | 0.853 | 0.775 |
| mlp+lgbm+maxent | 0.894 | 0.424 | 0.633 | 0.798 | 0.899 | 0.855 |
| all | 0.891 | 0.429 | 0.642 | 0.798 | 0.899 | 0.901 |

Best MLP config: `{"hidden": 32, "depth": 1, "dropout": 0.4, "wd": 0.01, "lr": 0.003}`

## Ablations (MLP, same folds)

| Variant | PR-AUC vs fungi | recall@5 % | recall@10 % | Boyce |
|---|---|---|---|---|
| full | 0.367 | 0.661 | 0.798 | 0.888 |
| without_soil | 0.253 | 0.578 | 0.688 | 0.844 |
| without_terrain | 0.343 | 0.606 | 0.725 | 0.703 |
| without_climate | 0.37 | 0.661 | 0.752 | 0.871 |
| without_neigh | 0.304 | 0.615 | 0.706 | 0.86 |
| with_location | 0.429 | 0.661 | 0.734 | 0.615 |

## Hyper-parameter trials

| PR-AUC vs fungi | recall@5 % | config |
|---|---|---|
| 0.378 | 0.67 | `{"hidden": 32, "depth": 1, "dropout": 0.4, "wd": 0.01, "lr": 0.003}` |
| 0.373 | 0.679 | `{"hidden": 128, "depth": 1, "dropout": 0.1, "wd": 0.01, "lr": 0.001}` |
| 0.348 | 0.642 | `{"hidden": 128, "depth": 1, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.348 | 0.642 | `{"hidden": 128, "depth": 1, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.346 | 0.67 | `{"hidden": 128, "depth": 2, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.345 | 0.651 | `{"hidden": 32, "depth": 1, "dropout": 0.4, "wd": 0.001, "lr": 0.001}` |
| 0.341 | 0.633 | `{"hidden": 32, "depth": 1, "dropout": 0.1, "wd": 0.01, "lr": 0.003}` |
| 0.338 | 0.706 | `{"hidden": 64, "depth": 2, "dropout": 0.25, "wd": 0.001, "lr": 0.001}` |
| 0.338 | 0.661 | `{"hidden": 64, "depth": 1, "dropout": 0.1, "wd": 0.01, "lr": 0.001}` |
| 0.333 | 0.642 | `{"hidden": 64, "depth": 2, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.327 | 0.697 | `{"hidden": 64, "depth": 1, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.327 | 0.697 | `{"hidden": 64, "depth": 1, "dropout": 0.4, "wd": 0.001, "lr": 0.003}` |
| 0.323 | 0.697 | `{"hidden": 128, "depth": 2, "dropout": 0.4, "wd": 0.01, "lr": 0.001}` |
| 0.323 | 0.67 | `{"hidden": 128, "depth": 2, "dropout": 0.25, "wd": 0.0001, "lr": 0.003}` |
| 0.313 | 0.679 | `{"hidden": 32, "depth": 2, "dropout": 0.4, "wd": 0.001, "lr": 0.001}` |
| 0.299 | 0.679 | `{"hidden": 64, "depth": 3, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.298 | 0.679 | `{"hidden": 64, "depth": 3, "dropout": 0.25, "wd": 0.01, "lr": 0.001}` |
| 0.297 | 0.679 | `{"hidden": 64, "depth": 3, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.288 | 0.679 | `{"hidden": 32, "depth": 3, "dropout": 0.25, "wd": 0.01, "lr": 0.001}` |
| 0.28 | 0.688 | `{"hidden": 64, "depth": 3, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
