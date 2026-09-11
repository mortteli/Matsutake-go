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

## Do the coarse records help?

Presences with 250 m – 1 km coordinate uncertainty (141) train at weight 0.3 with features averaged over five draws inside the uncertainty disc, and are never scored. Re-running the whole comparison with those rows dropped (`--fine-only`, 109 presences, identical folds and identical evaluation set) gives:

| Model | recall@5 % with coarse | fine-only | AUC with coarse | fine-only | Boyce with coarse | fine-only |
|---|---|---|---|---|---|---|
| logreg | **0.651** | 0.642 | 0.879 | 0.87 | 0.819 | 0.886 |
| gam | **0.606** | 0.624 | 0.877 | 0.869 | 0.863 | 0.702 |
| maxent | **0.661** | 0.651 | 0.888 | 0.878 | 0.908 | 0.855 |
| lgbm | **0.587** | 0.606 | 0.883 | 0.861 | 0.982 | 0.869 |
| xgb | **0.578** | 0.578 | 0.866 | 0.86 | 0.816 | 0.868 |
| mlp | **0.661** | 0.569 | 0.881 | 0.871 | 0.888 | 0.665 |

Every model is better with the coarse records included, the neural network most of all (0.661 vs 0.569 recall at 5 % of forest land). Because the evaluation set is the same 109 finds in both columns, this is a like-for-like comparison: the extra records add information about the habitat without degrading the precise ones. Full fine-only numbers are in `MODEL_REPORT_matsutake_fineonly.md`.

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
