# ml/ — habitat probability model

Python pipeline that turns public observations into a 16 m probability-of-occurrence
raster for a mushroom species. The web app stays a static page; this folder is only run
offline. See `docs/HABITAT_MODEL_PLAN.md` for the reasoning and the data audit.

Layout — each stage only imports the one before it:

```
core/     grid.py, features.py,    shared grid geometry + feature extraction, imported by every stage
          mvmi_point.py
ingest/   fetch_*.py, climate.py,  external sources -> local files under data/ (raw or cached)
          build_dem16.py, download_mvmi.sh
dataset/  build_dataset.py         ingested data + observations -> data/<species>/dataset.csv
          observation_status.py    observations -> how precisely each was located, and whether
                                   the forest it was found in is still standing
train/    train.py, compare_heads.py   dataset.csv -> models/<species>/ + docs/MODEL_REPORT_*.md
export/   predict.py,              trained model -> full-Finland raster -> the app's static data/
          export_app.py, export_terrain.py
plan/     pick_sites.py, fetch_osm.py   raster + OSM exclusions -> a short list of trip candidates
```

`data/` and `models/` stay flat at `ml/` — every stage reads/writes them by the same relative
path regardless of which subfolder its own script lives in.

```
pip install -r ml/requirements.txt
python ml/ingest/fetch_observations.py           # GBIF (+ laji.fi if LAJI_TOKEN is set in the env)
python ml/ingest/climate.py                      # FMI 10 km normals -> ml/data/climate/*.tif
python ml/ingest/fetch_gtk.py all                # GTK soil + glacigenic polygons -> 16 m rasters (large, not committed)
sh  ml/ingest/download_mvmi.sh                   # local copies of the eleven MVMI 2023 rasters (~10 GB, not committed)
python ml/dataset/build_dataset.py [--coarse]     # presences (cycle-matched) + background -> dataset.csv
python ml/dataset/observation_status.py           # per-record precision + habitat verdict -> observation_status.csv
python ml/dataset/observation_status.py --report  # the cross-tab; --from-cache re-runs it with no network
python ml/train/train.py --species matsutake --head mlp+lgbm --select sure   # spatial CV, tuning, report
python ml/export/predict.py --species matsutake   # full-Finland inference -> probability raster
python ml/export/export_app.py --species matsutake --split 3   # -> data/matsutake/*.tif + prob_meta.json
```

Terrain for the app's tap readout — independent of any species, run once:

```
python ml/ingest/build_dem16.py                  # MML 10 m -> ml/data/rasters/dem_16m.tif (once, slow)
python ml/export/export_terrain.py --downsample 4  # -> data/terrain/*.tif + terrain_meta.json
```

Without `data/terrain/` the app falls back to Open-Meteo's elevation API for the slope in the
result sheet: one live request per tap, answered from a ~90 m DEM where the model used 10 m.
With it, a tap costs no external call at all and the slope shown is the slope the model scored.

Choosing what the map is made of

```
python ml/train/compare_heads.py --species matsutake --seeds 5   # model families over several fold splits
```

`--head` decides which family the exported map is: `mlp+lgbm` (the shipped one, the average of
the two probabilities), or `lgbm` or `mlp` alone. `--select sure` picks hyper-parameters on
precision in the best 2 % of forest land instead of overall PR-AUC — the map is read at its top,
so that is what it is tuned for. The reasoning and the numbers:
[docs/MODEL_CHOICE_matsutake.md](../docs/MODEL_CHOICE_matsutake.md).

Planning a trip

```
python ml/plan/fetch_osm.py --center 61.4978 23.7610 --radius-km 115 --out ml/data/osm/pirkanmaa.npz
python ml/plan/pick_sites.py --species matsutake --center 61.4978 23.7610 --radius-km 100 \
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
* `export_app.py` quarters any part that comes out over `--max-mb` and keeps quartering (three
  levels deep) until each file fits, so `--split` only sets the starting grid. GitHub rejects a
  file over 100 MB outright, and how well a region compresses is not knowable before writing it.
* Presences from 250 m to 1 km train at weight 0.3 with features averaged over the uncertainty
  disc and are never scored; `--fine-only` reproduces the comparison without them.

Data sources (all open): Luke MVMI 2009–2023 (CC BY 4.0), MML elevation model 10 m
(CC BY 4.0), GTK Maaperä 1:200 000 and glacigenic formations (CC BY 4.0), FMI gridded
climate 10 km (CC BY 4.0), GBIF / FinBIF occurrence records (various CC licences).

`LAJI_TOKEN` is read from the environment only; never commit it.
