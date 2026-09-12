# ml/ — habitat probability model

Python pipeline that turns public observations into a 16 m probability-of-occurrence
raster for a mushroom species. The web app stays a static page; this folder is only run
offline. See `docs/HABITAT_MODEL_PLAN.md` for the reasoning and the data audit.

```
pip install -r ml/requirements.txt
python ml/fetch_observations.py           # GBIF (+ laji.fi if LAJI_TOKEN is set in the env)
python ml/climate.py                      # FMI 10 km normals -> ml/data/climate/*.tif
python ml/fetch_gtk.py all                # GTK soil + glacigenic polygons -> 16 m rasters (large, not committed)
sh  ml/download_mvmi.sh                   # local copies of the ten MVMI 2023 rasters (~10 GB, not committed)
python ml/build_dataset.py [--coarse]     # presences (cycle-matched) + background -> dataset.csv
python ml/train.py --species matsutake --head lgbm --select sure   # spatial CV, tuning, report
python ml/predict.py --species matsutake   # full-Finland inference -> probability raster
python ml/export_app.py --species matsutake --split 3   # -> data/matsutake/*.tif + prob_meta.json
```

Choosing what the map is made of

```
python ml/compare_heads.py --species matsutake --seeds 5   # model families over several fold splits
```

`--head` decides which family the exported map is: `lgbm` (the shipped one), `mlp`, or
`mlp+lgbm` for the average of the two probabilities. `--select sure` picks hyper-parameters on
precision in the best 2 % of forest land instead of overall PR-AUC — the map is read at its top,
so that is what it is tuned for. The reasoning and the numbers:
[docs/MODEL_CHOICE_matsutake.md](../docs/MODEL_CHOICE_matsutake.md).

Planning a trip

```
python ml/fetch_osm.py --center 61.4978 23.7610 --radius-km 115 --out ml/data/osm/pirkanmaa.npz
python ml/pick_sites.py --species matsutake --center 61.4978 23.7610 --radius-km 100 \
    --osm ml/data/osm/pirkanmaa.npz --top-pct 0.5 --n 3 --out trip.geojson
```

`pick_sites.py` takes the raster down to a handful of places: it drops protected and military
areas, cells near buildings or inside a big road's corridor, and anything further from a drivable
road than you would want to walk; then it clusters what is left and ranks stands by their 25th
percentile score, so one freak pixel cannot win. The exclusion layers come from OpenStreetMap
via `fetch_osm.py` (ODbL).

Notes

* `predict.py` is restartable: finished blocks are recorded next to the output and the raster is
  flushed every 100 blocks, because a tiled compressed GeoTIFF only writes its tile index on close.
  `--bbox` covers one region first (the rest of the country stays nodata) and a later full run
  picks up where it stopped, which is how a single region can be looked at without waiting hours
  for the whole map.
* The exported parts are Cloud-Optimised GeoTIFFs read by the app with HTTP range requests. Serve
  the site with `python3 serve.py`, not `python3 -m http.server`, which ignores Range headers.
* Presences from 250 m to 1 km train at weight 0.3 with features averaged over the uncertainty
  disc and are never scored; `--fine-only` reproduces the comparison without them.

Data sources (all open): Luke MVMI 2009–2023 (CC BY 4.0), MML elevation model 10 m
(CC BY 4.0), GTK Maaperä 1:200 000 and glacigenic formations (CC BY 4.0), FMI gridded
climate 10 km (CC BY 4.0), GBIF / FinBIF occurrence records (various CC licences).

`LAJI_TOKEN` is read from the environment only; never commit it.
