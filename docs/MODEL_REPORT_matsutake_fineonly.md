# Habitat model report — matsutake_fineonly

Rows: 5696 (presences 109, random-forest background 3000, other-fungi background 2587); 62 features; 5-fold spatial block CV (25 km blocks).

## Models (pooled out-of-fold)

| Model | AUC vs fungi | PR-AUC vs fungi | AUC vs random | recall@5 % | recall@10 % | recall@20 % | Boyce |
|---|---|---|---|---|---|---|---|
| rule_old_default | 0.562 | 0.094 | 0.572 | 0.156 | 0.239 | 0.312 | 0.203 |
| rule_new_default | 0.72 | 0.155 | 0.748 | 0.45 | 0.587 | 0.651 | 0.203 |
| rule_E | 0.703 | 0.128 | 0.726 | 0.275 | 0.468 | 0.587 | 0.652 |
| logreg | 0.87 | 0.373 | 0.911 | 0.642 | 0.78 | 0.826 | 0.886 |
| gam | 0.869 | 0.396 | 0.889 | 0.624 | 0.752 | 0.844 | 0.702 |
| maxent | 0.878 | 0.396 | 0.909 | 0.651 | 0.78 | 0.853 | 0.855 |
| lgbm | 0.861 | 0.372 | 0.898 | 0.606 | 0.688 | 0.817 | 0.869 |
| xgb | 0.86 | 0.337 | 0.893 | 0.578 | 0.661 | 0.844 | 0.868 |
| mlp | 0.871 | 0.398 | 0.891 | 0.569 | 0.761 | 0.853 | 0.665 |

recall@k %: share of held-out finds scoring above the top-k % of random forest cells (i.e. if the map is coloured over k % of forest land).

All models are fitted in the presence-background setting: presences vs. a background made of random forestry-land cells (what habitat is available) and other-fungi observation sites (where people actually look, i.e. the target-group correction for observer bias). `maxent` is the MaxEnt-equivalent infinitely-weighted L1 logistic regression on MaxEnt feature classes (linear, quadratic, forward/reverse hinges); `gam` is a spline-basis logistic GAM; `logreg` is a ridge logistic regression; `lgbm`/`xgb` are gradient-boosted trees; `mlp` is the neural network used for the map. Baseline configs are the best of a small grid on the same folds (slightly optimistic for them, not for the MLP whose config is chosen by nested CV).

## MLP threshold curve (out-of-fold)

| Map covers (share of forest) | Recall of finds | Other-fungi sites kept | Lift vs random |
|---|---|---|---|
| 1 % | 33 % | 1 % | 33.0× |
| 2 % | 41 % | 3 % | 20.6× |
| 5 % | 56 % | 7 % | 11.4× |
| 10 % | 76 % | 16 % | 7.6× |
| 15 % | 82 % | 23 % | 5.5× |
| 20 % | 85 % | 27 % | 4.3× |
| 30 % | 86 % | 34 % | 2.9× |
| 50 % | 93 % | 49 % | 1.9× |

## Rank-averaged ensembles (same folds)

| Ensemble | AUC vs fungi | PR-AUC vs fungi | recall@5 % | recall@10 % | recall@20 % | Boyce |
|---|---|---|---|---|---|---|
| mlp+lgbm | 0.874 | 0.4 | 0.624 | 0.752 | 0.862 | 0.849 |
| mlp+maxent | 0.878 | 0.401 | 0.624 | 0.78 | 0.853 | 0.726 |
| mlp+lgbm+maxent | 0.88 | 0.406 | 0.633 | 0.78 | 0.853 | 0.899 |
| all | 0.88 | 0.401 | 0.651 | 0.78 | 0.853 | 0.938 |

Best MLP config: `{"hidden": 128, "depth": 1, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}`


## Hyper-parameter trials

| PR-AUC vs fungi | recall@5 % | config |
|---|---|---|
| 0.339 | 0.56 | `{"hidden": 128, "depth": 1, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.326 | 0.523 | `{"hidden": 64, "depth": 3, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.324 | 0.679 | `{"hidden": 64, "depth": 2, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.318 | 0.642 | `{"hidden": 64, "depth": 3, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.315 | 0.606 | `{"hidden": 64, "depth": 1, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.311 | 0.633 | `{"hidden": 64, "depth": 2, "dropout": 0.25, "wd": 0.001, "lr": 0.001}` |
| 0.308 | 0.606 | `{"hidden": 64, "depth": 3, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.302 | 0.505 | `{"hidden": 128, "depth": 2, "dropout": 0.4, "wd": 0.01, "lr": 0.001}` |
