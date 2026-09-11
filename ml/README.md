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
python ml/predict.py --species matsutake   # full-Finland inference -> probability raster (~1 h)
python ml/export_app.py --species matsutake --split 3   # -> data/matsutake/*.tif + prob_meta.json
```

Notes

* `predict.py` is restartable: finished blocks are recorded next to the output and the raster is
  flushed every 100 blocks, because a tiled compressed GeoTIFF only writes its tile index on close.
* The exported parts are Cloud-Optimised GeoTIFFs read by the app with HTTP range requests. Serve
  the site with `python3 serve.py`, not `python3 -m http.server`, which ignores Range headers.
* Presences from 250 m to 1 km train at weight 0.3 with features averaged over the uncertainty
  disc and are never scored; `--fine-only` reproduces the comparison without them.

Data sources (all open): Luke MVMI 2009–2023 (CC BY 4.0), MML elevation model 10 m
(CC BY 4.0), GTK Maaperä 1:200 000 and glacigenic formations (CC BY 4.0), FMI gridded
climate 10 km (CC BY 4.0), GBIF / FinBIF occurrence records (various CC licences).

`LAJI_TOKEN` is read from the environment only; never commit it.
