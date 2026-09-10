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
python ml/train.py --species matsutake    # spatial CV, tuning, report -> ml/models/, docs/MODEL_REPORT_*.md
python ml/predict.py --species matsutake  # full-Finland inference -> probability raster
```

Data sources (all open): Luke MVMI 2009–2023 (CC BY 4.0), MML elevation model 10 m
(CC BY 4.0), GTK Maaperä 1:200 000 and glacigenic formations (CC BY 4.0), FMI gridded
climate 10 km (CC BY 4.0), GBIF / FinBIF occurrence records (various CC licences).

`LAJI_TOKEN` is read from the environment only; never commit it.
