# Matsutake habitat probability model — plan (v0, for review)

Goal: replace the hand-tuned AND-of-thresholds filter with a **probability-of-occurrence
surface** for *Tricholoma matsutake* (tuoksuvalmuska) at 16 m resolution over Finland,
fitted to real observations and tuned on precision/recall. The pipeline is written so
that the next species is "one more config entry", the same way `SPECIES` works in
`index.html` today.

This document is the plan only. Nothing in the app changes until the plan is approved.

---

## 1. What the sources say about matsutake habitat

Sources read: fi.wikipedia (Tuoksuvalmuska), en.wikipedia (Matsutake), laji.fi taxon
MX.72541 (same species text as LuontoPortti), Suomen Luonto ("Lajia etsimässä:
Matsutake, harvojen herkku" and the older "Kulttisieni kasvaa Suomenkin luonnossa"),
Arktiset Aromit (tuoksuvalmuska page), Suomen Sieniseura (Vuoden sieni 2007),
Vaario et al. 2015 *Fruiting pattern of T. matsutake in Southern Finland*
(Scand. J. For. Res. 30:259–265), Vaario et al. 2010 (mycorrhiza with pine *and* spruce
in vitro), and the Fennoscandian habitat summary in Fungi Magazine 2016.
LuontoPortti, Arktiset Aromit and funga.fi block automated fetching, so their text was
taken from search excerpts; laji.fi carries the identical LuontoPortti species text.

| Factor | What the sources say | Data proxy available (open) | In current filter? |
|---|---|---|---|
| Host tree | Pine companion everywhere; Suomen Luonto: "männyn **ja kuusen** seuralaisena"; forms mycorrhiza with both pine and spruce in vitro | MVMI `manty`, `kuusi`, `koivu` m³/ha; pine share of `tilavuus` | pine ≥ 20 m³/ha only |
| Site type | Dry / barren heath, lichen heath: "kuivilla mäntyvaltaisilla kankailla … poronjäkäliä, kanervaa ja puolukkaa"; "hiekkapohjaisilla jäkäläkankailla paikoin runsas" | MVMI `kasvupaikka` 5–6 (4 secondary; 7 = kalliomaa/hietikko) | yes (5, 6, optional 4) |
| Soil | Sandy; glaciofluvial deposits and **eskers (harjut)**, often along larger rivers; in the south also rocky shallow soil; never clay; **thin humus** | GTK Maaperä 1:200k surface soil class (Hk/Sr/Mr/Ka…), GTK glaciofluvial formations layer (tested, works) | **no** |
| Stand structure | Old forest gives the yields (first fruiting from 10–15 yr stands); **old and sparse** stand, thin litter | MVMI `ika`, `ppa` (basal area), `latvuspeitto`, `keskipituus`, `keskilapimitta` | age ≥ 60 only; sparseness not used |
| Light | "valoisissa, hiekkapohjaisissa mäntymetsissä" | low–moderate `latvuspeitto`, low `ppa` | **no** |
| Topography | Sandy eskers and hillsides; "suosivan jäkälää kasvavia harjuja ja vieläpä niiden **pohjoisrinteitä**" | MML DEM 10 m (Paituli, open): slope, aspect/northness, TPI, ruggedness | slope only in tap readout, not in the map |
| Moisture | Well-drained soil, but yields only in rainy summers; ~average precipitation before onset ⇒ high yield (Vaario 2015); snow cover / melt mentioned | static: TWI, distance to water; dynamic: FMI daily obs (`rrday`, `tday`, snow) — tested, works | **no** |
| Disturbance | Reindeer grazing and fire favour it; best yields with little ground vegetation | Reindeer husbandry area (poronhoitoalue) flag; fire history not open | **no** (latitude text only) |
| Region | Rare in the south, common in the north: Kainuu, Koillismaa, Lappi; along big rivers | lat/lon, elevation, FMI climate normals | text only |
| Season | Late July – early October, peak Aug–Sep; GBIF confirms (Aug 214 / Sep 192 records) | observation date → phenology model | text only |
| Companion vegetation | Reindeer lichen, heather, lingonberry | no direct raster (lichen cover is not in MVMI); `kasvupaikka` 5–6 is the proxy; Sentinel-2 lichen index later | via site class only |
| "Certain species around" | The shiro is an ectomycorrhizal community around pine roots — not observable from any map | none | n/a |

**Bottom line:** the current filter covers host tree, site type and age. It is silent on
soil/eskers, stand openness, aspect, moisture, disturbance, and it has no ranking inside
the pink area. Those are exactly the things the sources emphasise most (sandy esker,
lichen, old *and sparse*, north slope).

## 2. Observation data (what exists today)

GBIF, *Tricholoma matsutake* (taxonKey 5241820), country = FI, queried 2026-09-09:

| Subset | Records |
|---|---|
| All Finnish records | 461 |
| With coordinates, uncertainty ≤ 250 m (usable at 16 m) | **104** (69 at 1 m, 21 at 100 m) |
| With coordinates, uncertainty ≤ 1 km | 246 |
| Since 2000 with coordinates | 208 |
| Fine subset: month Aug / Sep / Oct | 54 / 49 / 1 |
| Fine subset with day precision | 103 of 104 |
| Fine subset, distinct ~1 km cells | 89 (clusters at Rokua, Haukipudas, UKK park, Toramomaa) |
| Fine subset by latitude 59–63° / 64–66° / 67–69° | 27 / 47 / 30 |

Main publishers of the fine records: Atlas of Finnish Fungi (Sieniatlas, 41), LajiGIS
(28), iNaturalist (8), Löydös (5), university herbaria (rest).

Things to get more of:
- **laji.fi API** (needs a free token): FinBIF often holds records whose public GBIF copy
  is coarsened to 1–10 km. Could raise the fine set substantially.
- Your own / friends' finds, if any (kept private, used for training only).

Background ("pseudo-absence") data, both already downloadable:
- Random points on forestry land (MVMI has data) — describes *available* habitat.
- **Target-group background**: other fungi observed Aug–Sep 2010+ with ≤ 250 m accuracy
  in Finland: **192 747** records (Tricholomataceae alone 5 823). This corrects observer
  bias: matsutake gets reported where mushroom pickers walk, so we contrast it against
  where mushroom pickers walk *and found something else*.

## 3. Backtracking the observation time to the forest state at that time

Yes, this works, and the pipeline does it by default. Luke publishes every MVMI cycle
as whole-Finland GeoTIFFs on Paituli (open, no key), all 16 m, ETRS-TM35FIN:

| Cycle (satellite/field years) | Folder | File name pattern |
|---|---|---|
| 2009 | `luke/vmi/2009/` | `ika.tif`, `kasvupaikka.tif`, … |
| 2011 | `luke/vmi/2011/` | `*_0711.tif` |
| 2013 | `luke/vmi/2013/` | `*_vmi11_0913.tif` |
| 2015 | `luke/vmi/2015/` | `*_vmi1x_1216.tif` |
| 2017 | `luke/vmi/2017/` | `*_vmi1x_1317.tif` |
| 2019 | `luke/vmi/2019/` | `*_vmi1x_1519.tif` |
| 2021 | `luke/vmi/2021/` | `*_vmi1x_1721.tif` |
| 2023 (the app's `_1923`) | `luke/vmi/2023/` | `*_vmi1x_1923.tif` |

Rule: observation year → latest cycle whose year ≤ observation year (≤ 2 years off).
Verified: the files are tiled (512×512, LZW, uint16, nodata 32767) and can be sampled
with HTTP range requests in ~2 s per layer without downloading the 0.5–1.7 GB files.
The same works for the MML 10 m DEM (`mml/dem10m/dem10m_direct.vrt`).

What backtracking buys: a 2014 find in a stand that was clear-cut in 2019 would look
like "young forest" in the 2023 raster and poison the training set; with the 2013 cycle
it is correctly an old pine stand. Age itself only drifts by the year difference, so the
main gain is catching harvests, thinnings and site-class re-estimation.

Weather at the time: FMI's gridded daily climate data (10 km grid, 1961→, open files on
Paituli under `ilmatiede/10km_daily_precipitation`, `…_mean_temperature`, `…_snow`) can
be sampled the same way as the forest rasters, so each dated find can carry
"precipitation in the 30/60 days before", degree days, snow-melt date and day-of-year.
FMI's station WFS (`fmi::observations::weather::daily::simple`, by bbox) works too and is
the fallback; Open-Meteo's ERA5 archive is rate-limited from this environment. The same
folder has 10 km monthly normals for static climate features (temperature sum,
precipitation), which are the "honest" alternative to raw latitude/longitude.

## 4. Empirical check of the current filter against the observations

_Running now: for the 104 fine presences, 300 random forestry-land points and 300
target-group fungi points, sample MVMI 2023 (site, main type, age, pine, spruce, canopy,
basal area, height), the DEM (elevation, slope, northness, TPI) and GTK soil (surface soil
class, glaciofluvial formation), plus the back-tracked MVMI cycle for each presence.
The table below is filled in from that run._

(see section 4 results appended below once the run completes)

## 5. Experiment design

### 5.1 Units and labels
- Presence-only data ⇒ **presence vs background** classification (the MaxEnt setting).
  Output is a *relative* occurrence probability; absolute prevalence is unknowable
  from presence-only data, so the map is calibrated to rank and to "share of forest
  area", not to "70 % chance of a mushroom".
- Each presence contributes its 16 m pixel plus neighbourhood aggregates (mean/max/min
  within 50 m and 150 m) to absorb GPS error and raster misregistration.
- Background: 50 % random forestry land + 50 % target-group fungi points, weighted so
  the two halves count equally; several thousand points.

### 5.2 Feature set v1 (all open data)
- MVMI (cycle matched to observation year): `kasvupaikka` one-hot, `paatyyppi`, `ika`,
  `manty`, `kuusi`, `koivu`, `tilavuus`, `ppa`, `latvuspeitto`, `lehtip_latvuspeitto`,
  `keskipituus`, `keskilapimitta`, `maaluokka`; derived: pine share, openness
  (`ppa` per height), stem-density proxy.
- DEM 10 m: elevation, slope, northness, eastness, TPI at 100 m and 500 m, TWI.
- GTK: surface soil class (sand/gravel/till/rock/peat), glaciofluvial formation flag,
  distance to nearest esker polygon.
- Location/climate: latitude, longitude (or FMI 10 km climate normals: temperature sum,
  precipitation), reindeer-husbandry-area flag (statutory area; district polygons are
  restricted data, so a municipality-based approximation), distance to large rivers and
  lakes (MML topographic database on Paituli).

### 5.3 Models
1. Baselines: regularised logistic regression (≈ MaxEnt) and gradient boosting.
2. **Neural network (primary):** small MLP, 2–3 hidden layers of 32–64 units, dropout,
   weight decay, class-balanced loss, trained on the tabular features; fold-ensembled.
   Optional v2: tiny CNN on 9×9 raster patches to learn context (esker ridge shape,
   forest edge) instead of hand-made neighbourhood features.
3. The current rule filter is scored as a fixed classifier so every model is compared
   against it on the same folds.

### 5.4 Validation
- **Spatial block cross-validation**: 25 km blocks, 5 folds, blocks assigned so that
  each fold spans the latitude range. Random splits would leak (Rokua alone has many
  points) and overstate accuracy.
- Metrics: ROC-AUC and PR-AUC against target-group background; presence recall at a
  fixed share of forest area ("recall@5 % of Finland's forest"); continuous Boyce index;
  calibration curve.
- Report precision (background rejected) vs recall (presences kept) as a curve, so a
  threshold can be chosen for a target recall (e.g. 80 %) and the resulting map area
  is known.

### 5.5 Hyperparameter tuning
- Nested CV; search over hidden width, depth, dropout, weight decay, learning rate,
  background mix, neighbourhood radius, and feature subsets (with/without location).
- Selection criterion: PR-AUC on the outer folds; ties broken by Boyce index.
- Ablations answer "are we missing something?": drop soil, drop DEM, drop location,
  drop backtracking (use 2023 for everything) and watch the metric move.

### 5.6 Phenology sub-model (phase 4, optional)
P(fruiting now | site, date, weather) from the 103 dated finds and FMI weather:
precipitation in the previous 30 and 60 days, temperature sum, day-of-year, latitude.
Shown in the app as a "today" multiplier on the habitat map.

### 5.7 Outputs
- Probability raster as a Cloud-Optimised GeoTIFF (uint8, 0–100), first at 32 m
  (~100–200 MB), 16 m when the model earns it (3.1 G cells, ~0.5–1 GB).
- Training report: CV metrics, precision/recall curve, ablations, feature importance.
- `ml/` folder with reproducible scripts (Python: rasterio, scikit-learn, PyTorch CPU,
  lightgbm). The app itself stays a static page.

## 6. Getting the layer into the app (choose one)

- **A. Precomputed COG + client-side reader (recommended).** Host the GeoTIFF on GitHub
  Releases (or Pages if < 100 MB) and read it with `georaster-layer-for-leaflet`, which
  uses HTTP range requests. One file, threshold slider in the UI, works offline-ish.
- B. XYZ PNG tile pyramid (zoom 5–13, ~80 000 tiles) on GitHub Pages. Simple, but a big
  repo and no dynamic threshold.
- C. In-browser inference: fetch raw-value MVMI layers per tile from Luke's WMS and run
  the MLP in JavaScript (ONNX). No hosting, but DEM and soil features would be missing,
  so the model would be weaker.

The existing rule filter stays as a "sääntökartta" toggle for comparison.

## 7. Phases

| Phase | Deliverable |
|---|---|
| 0 (this) | Sources, data audit, empirical comparison, plan |
| 1 | `ml/` data pipeline: fetch GBIF (+ laji.fi), match MVMI cycle, sample all features, build dataset + background sets |
| 2 | Baselines + NN, spatial CV, tuning, ablations, report with precision/recall curves |
| 3 | Full-Finland inference → COG; app layer with threshold slider; README |
| 4 | Phenology sub-model; second species through the same config |

## 8. Open questions for you

1. **laji.fi token**: can you register at laji.fi and paste an API access token (or
   pull the matsutake records yourself)? It may double the fine-resolution set.
2. **Private finds**: do you have your own coordinates to add (kept out of the repo)?
3. **Accuracy cutoff**: strict ≤ 250 m (104 records) or also ≤ 1 km with
   uncertainty-aware sampling (246 records, noisier)?
4. **Hosting**: option A, B or C above? Is a ~100–200 MB file on GitHub Releases fine?
5. **Resolution**: start at 32 m (fast, small) or go straight to 16 m?
6. **Location as a feature**: lat/lon makes the map more accurate but bakes in where
   people look; climate normals only is the "honest" alternative. Preference?
7. **NN as primary** with logistic/GBM baselines — agreed, or baselines only first?
8. **Phenology** now or as phase 4?
9. **Python in the repo**: OK to add an `ml/` folder with `requirements.txt`? The app
   remains a single static page.
