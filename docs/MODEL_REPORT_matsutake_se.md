# Habitat model report — matsutake_se

Rows: 17069 (presences 4046, random-forest background 7249, other-fungi background 5774); 69 features; 5-fold spatial block CV (25 km blocks).

Map head: **lgbm** (hyper-parameters chosen for precision in the best 2 %).

## Models (pooled out-of-fold)

| Model | AUC vs fungi | PR-AUC vs fungi | recall@2 % | prec@2 % | recall@5 % | prec@5 % | recall@10 % | Boyce |
|---|---|---|---|---|---|---|---|---|
| rule_se_simple | 0.642 | 0.556 | 0.072 | 0.65 | 0.161 | 0.627 | 0.348 | 0.485 |
| rule_se_dry | 0.497 | 0.427 | 0.031 | 0.508 | 0.058 | 0.467 | 0.107 | 0.176 |
| logreg | 0.889 | 0.843 | 0.399 | 0.898 | 0.545 | 0.866 | 0.706 | 1.0 |
| gam | 0.902 | 0.861 | 0.456 | 0.92 | 0.627 | 0.864 | 0.773 | 0.985 |
| maxent | 0.763 | 0.701 | 0.175 | 0.855 | 0.297 | 0.791 | 0.434 | 0.988 |
| lgbm | 0.906 | 0.863 | 0.469 | 0.902 | 0.637 | 0.847 | 0.771 | 1.0 |
| mlp | 0.907 | 0.87 | 0.479 | 0.922 | 0.644 | 0.852 | 0.79 | 0.964 |
| head:lgbm | 0.906 | 0.863 | 0.469 | 0.902 | 0.637 | 0.847 | 0.771 | 1.0 |

recall@k %: share of held-out finds scoring above the top-k % of random forest cells (i.e. if the map is coloured over k % of forest land). prec@k %: of the fungus-reporting sites inside that coloured area, the share that are matsutake finds — what a visit to a coloured cell is worth, and the number to watch for a deliberately tight map.

All models are fitted in the presence-background setting: presences vs. a background made of random forestry-land cells (what habitat is available) and other-fungi observation sites (where people actually look, i.e. the target-group correction for observer bias). `maxent` is the MaxEnt-equivalent infinitely-weighted L1 logistic regression on MaxEnt feature classes (linear, quadratic, forward/reverse hinges); `gam` is a spline-basis logistic GAM; `logreg` is a ridge logistic regression; `lgbm`/`xgb` are gradient-boosted trees; `mlp` is a neural network. The row named `head:` is the one the exported map is made of. Configs are the best of a small grid on the same folds (slightly optimistic, the MLP's nested-CV config aside), so read the head's own numbers as the optimistic end of its range.

## Threshold curve of the map head (lgbm, out-of-fold)

| Map covers (share of forest) | Recall of finds | Other-fungi sites kept | Matsutake share of fungi sites | Lift vs random |
|---|---|---|---|---|
| 0.25 % | 15 % | 0 % | 96 % | 61.2× |
| 0.5 % | 26 % | 0 % | 95 % | 52.3× |
| 1 % | 35 % | 2 % | 91 % | 35.7× |
| 2 % | 46 % | 3 % | 90 % | 23.4× |
| 5 % | 63 % | 8 % | 84 % | 12.7× |
| 10 % | 77 % | 14 % | 79 % | 7.7× |
| 15 % | 86 % | 19 % | 75 % | 5.7× |
| 20 % | 90 % | 24 % | 72 % | 4.5× |
| 30 % | 94 % | 34 % | 65 % | 3.1× |
| 50 % | 98 % | 55 % | 55 % | 2.0× |

## Rank-averaged ensembles (same folds)

| Ensemble | AUC vs fungi | PR-AUC vs fungi | recall@5 % | recall@10 % | recall@20 % | Boyce |
|---|---|---|---|---|---|---|
| mlp+lgbm | 0.912 | 0.874 | 0.659 | 0.798 | 0.915 | 0.997 |
| mlp+maxent | 0.87 | 0.821 | 0.534 | 0.667 | 0.814 | 0.988 |
| mlp+lgbm+maxent | 0.896 | 0.85 | 0.6 | 0.75 | 0.875 | 0.952 |

Rank averages cannot be stored in the map (they have no probability scale), so a rank ensemble can only ever be a comparison; `--head mlp+lgbm` averages the two probabilities instead.

Best MLP config: `{"hidden": 64, "depth": 3, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}`


## Hyper-parameter trials

| PR-AUC vs fungi | recall@5 % | config |
|---|---|---|
| 0.867 | 0.635 | `{"hidden": 64, "depth": 3, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.863 | 0.624 | `{"hidden": 32, "depth": 1, "dropout": 0.4, "wd": 0.001, "lr": 0.001}` |
| 0.862 | 0.622 | `{"hidden": 32, "depth": 3, "dropout": 0.25, "wd": 0.01, "lr": 0.001}` |
| 0.865 | 0.63 | `{"hidden": 64, "depth": 3, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.856 | 0.622 | `{"hidden": 64, "depth": 2, "dropout": 0.25, "wd": 0.001, "lr": 0.001}` |
| 0.858 | 0.612 | `{"hidden": 128, "depth": 1, "dropout": 0.1, "wd": 0.01, "lr": 0.001}` |
| 0.867 | 0.645 | `{"hidden": 64, "depth": 3, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
| 0.86 | 0.624 | `{"hidden": 128, "depth": 2, "dropout": 0.4, "wd": 0.01, "lr": 0.001}` |
| 0.859 | 0.614 | `{"hidden": 128, "depth": 1, "dropout": 0.25, "wd": 0.0001, "lr": 0.001}` |
| 0.861 | 0.612 | `{"hidden": 64, "depth": 2, "dropout": 0.1, "wd": 0.001, "lr": 0.003}` |
| 0.857 | 0.611 | `{"hidden": 128, "depth": 2, "dropout": 0.25, "wd": 0.0001, "lr": 0.003}` |
| 0.853 | 0.617 | `{"hidden": 64, "depth": 1, "dropout": 0.4, "wd": 0.0001, "lr": 0.003}` |
