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
| Stand structure | Old forest gives the yields (first fruiting from 10–15 yr stands); **old and sparse** stand, thin litter | MVMI `ika`, `ppa` (basal area), `latvuspeitto`, `keskipituus`, `keskilapimitta` | age ≥ 60 in the map; `latvuspeitto` ≤ 60 % added 2026-09-20 (both map and model), `stems_ha` (from `ppa`+`keskilapimitta`) added to the model only — see §12 |
| Light | "valoisissa, hiekkapohjaisissa mäntymetsissä"; Vaario et al. 2015: best yields in 41–60 yr pure pine stands with "moderately open A–B canopy density" | `latvuspeitto` (+ 3×3/9×9 neighbourhood mean), `stems_ha` | **yes**, since 2026-09-20 — see §12 |
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

Run on 2026-09-09: the 104 fine GBIF presences, 300 random forestry-land points and
300 target-group points (other fungi, Aug–Sep, 2010+, ≤ 250 m), all sampled from
MVMI 2023 (Paituli GeoTIFFs), the MML 10 m DEM (210 m window) and GTK soil WMS.
Points without MVMI data (water, field, built-up) are excluded: n = 101 / 300 / 232.
GTK's 1:200k soil map does not separate sand from gravel; both are "karkearakeinen".

### 4.1 Single conditions

| Condition (MVMI 2023 unless noted) | Presence % | Random forest % | Other fungi % |
|---|---|---|---|
| kasvupaikka 5–6 (kuiva / karukkokangas) | **13** | 8 | 6 |
| kasvupaikka 4 (kuivahko kangas) | **49** | 26 | 13 |
| kasvupaikka 3 (tuore kangas) | 30 | 51 | 55 |
| kasvupaikka 7 (kalliomaa / hietikko) | 4 | 1 | 3 |
| paatyyppi 1 (kivennäismaa) | 97 | 72 | 94 |
| ika ≥ 60 | 82 | 52 | 54 |
| ika ≥ 80 | 64 | 28 | 27 |
| manty ≥ 20 m³/ha | 90 | 65 | 73 |
| manty ≥ 50 m³/ha | 76 | 44 | 46 |
| kuusi ≥ 20 m³/ha | **17** | 40 | 63 |
| latvuspeitto ≤ 50 % | **70** | 42 | 19 |
| ppa ≤ 20 m²/ha | 87 | 75 | 48 |
| slope ≥ 2° (DEM) | 74 | 44 | 70 |
| north-facing (northness > 0.3) | 41 | 44 | 41 |
| south-facing (northness < −0.3) | 50 | 31 | 39 |
| TPI > +1 m (ridge / upper slope) | **42** | 17 | 21 |
| GTK 1:200k surface soil: coarse-grained (sand / gravel, "karkearakeinen") | **44** | 6 | 16 |
| GTK surface soil: mixed-grained (till, "sekalajitteinen") | 24 | 46 | 24 |
| GTK surface soil: rock (kalliomaa / kalliopaljastuma) | 21 | 14 | 40 |
| GTK surface soil: peat (turve) | 4 | 23 | 2 |
| GTK glacigenic formation mapped at the point (esker, ice-marginal or extramarginal glaciofluvial, littoral) | **53** | 13 | 27 |

| Median | Presence | Random forest | Other fungi |
|---|---|---|---|
| stand age (yr) | 88 | 62 | 62 |
| pine (m³/ha) | 81 | 42 | 47 |
| spruce (m³/ha) | 2 | 9 | 38 |
| canopy cover (%) | 45 | 55 | 66 |
| basal area (m²/ha) | 15 | 16 | 21 |
| mean height (dm) | 132 | 128 | 168 |
| elevation (m) | 154 | 150 | 58 |
| slope (°) | 3.9 | 1.7 | 3.5 |
| TPI (m) | +0.7 | 0.0 | −0.1 |

### 4.2 Rule filters as classifiers

| Rule | Recall (presence %) | Random forest % | Other fungi % |
|---|---|---|---|
| A — **current app default** (site 5–6, mineral, age ≥ 60, pine ≥ 20) | **9** | 0 (0/300) | 1 |
| B — A + kuivahko (site 4–6) | 49 | 9 | 9 |
| C — B + spruce < 20 m³/ha | 48 | 7 | 7 |
| D — C + canopy ≤ 60 % | 45 | 6 | 7 |
| E — site 3–7, mineral, age ≥ 60, pine ≥ 40, spruce < 20, canopy ≤ 60 | **58** | 9 | 9 |
| F — E + TPI > 0 (upper slope / ridge) | 47 | 7 | 6 |

### 4.3 Backtracking effect

79 of 104 presences date from before the 2023 cycle (cycle counts: 2009 ×16,
2011 ×1, 2013 ×18, 2015 ×4, 2017 ×4, 2019 ×14, 2021 ×25, 2023 ×22). Comparing the
matched cycle with 2023 at the same pixel: the site class differs for 36 of 79, and
the age estimate is more than 15 years lower than expected for 36 of 79 (harvest,
thinning or re-estimation). Age ≥ 60 holds for 82 % of finds in both versions, so the
headline numbers are robust, but pixel-level labels are noisy enough that the model
must see neighbourhood aggregates and the matched cycle.

### 4.4 What this says

1. **The current default map misses 91 % of the known finds.** Not because the
   ecology is wrong, but because MVMI's `kasvupaikka` theme rarely says "kuiva kangas":
   Luke's own accuracy note puts pixel-level site-class agreement at ~55 %, and the
   finds land on class 4 (49 %) and even class 3 (30 %) far more than on 5–6 (13 %).
   The literal "kuiva kangas" rule is therefore the wrong proxy for the literal
   "kuiva kangas" ecology.
2. **The strongest signals are not in the filter at all:** coarse-grained soil
   (44 % of finds vs 6 % of random forest — the single strongest variable, exactly the
   "hiekkapohjainen" of the sources), a mapped glaciofluvial / esker formation (53 % vs
   13 %), little or no spruce (17 % vs 63 % of other-fungi sites), open canopy (70 %
   ≤ 50 % vs 19 %), old age, high pine volume, and positive TPI (ridge / upper slope,
   42 % vs 17–21 %). Peat is almost absent under finds (4 % vs 23 %).
3. **Aspect shows no north-slope preference** in this sample (if anything south-facing),
   so the Suomen Luonto anecdote should be a feature, not a rule.
4. **Observer bias is real:** the other-fungi background sits at 58 m elevation
   median vs 150 m for random forest, i.e. people report from the coast and the south.
   Contrasting against that background is what keeps the model from just learning
   "Lapland".
5. A hand-tuned rule (E) already reaches 58 % recall at ~9 % of forest area, but every
   rule is a hard box; the probability model is expected to do clearly better because
   it can trade these signals off continuously and use the soil/terrain layers.

_Immediate, low-risk app change worth doing regardless of the model: make "kuivahko
kangas" default on and add a "little spruce" condition. Not done yet — pending your go._

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

| Phase | Deliverable | State |
|---|---|---|
| 0 | Sources, data audit, empirical comparison, plan | done |
| 1 | `ml/` data pipeline: fetch GBIF (+ laji.fi), match MVMI cycle, sample all features, build dataset + background sets | done |
| 2 | Baselines + NN, spatial CV, tuning, ablations, report with precision/recall curves | done — `docs/MODEL_REPORT_matsutake.md` |
| 3 | Full-Finland inference → COG; app layer with threshold slider; README | done — `data/matsutake/`, 🧠 panel in the app |
| 4 | Phenology sub-model; second species through the same config | open |

## 8. Decisions (answered 2026-09-10)

| Question | Decision |
|---|---|
| laji.fi records | Token supplied and used; the token lives only in the environment, never in the repo. FinBIF added 56 records, 12 of them at ≤ 250 m. |
| Private finds | None. |
| Accuracy cutoff | ≤ 250 m are the evaluation set; 250 m – 1 km records also train, at weight 0.3 and with features averaged over 5 draws inside the uncertainty disc, and are never scored. |
| Hosting | Cloud-Optimised GeoTIFF read client-side with range requests (`georaster-layer-for-leaflet`, vendored), split into parts under 90 MB so GitHub accepts them. |
| Resolution | 16 m, the native MVMI grid. |
| Location features | No raw latitude/longitude. Climate stands in for position: FMI thermal sum (degree days > 5 °C) and precipitation normals, 1991–2020. |
| Models | Neural network for the published map, compared against a rule baseline, ridge logistic regression, a spline-basis GAM, a MaxEnt-equivalent, LightGBM and XGBoost. |
| Phenology | Later, as its own layer. It must accumulate rain over the season and account for summer warmth, not just the last few weeks. |
| Python in the repo | Yes: `ml/` holds the pipeline, the training data, and the model weights. |
| Quick filter fix | Done: "kuivahko kangas" on by default plus a "little spruce" condition (9 % → 48 % of known finds inside the map). |

## 9. Modelling approach as built

All models are fitted in the **presence-background** setting, which is what presence-only
observation data supports: the response is not "mushroom vs no mushroom" but "this cell looks
like the places where the species has been recorded, compared with the places available".
Two background sets are used together and weighted equally:

- **Random forestry land** — what habitat exists in Finland (the availability distribution).
- **Other-fungi observation sites** — the *target-group background*: August–September records of
  other fungi with ≤ 250 m accuracy. Matsutake is only recorded where mushroom pickers walk, so
  contrasting against other fungal records cancels most of that sampling bias. Without it a model
  mostly learns "where people go", and the honest metric is the one measured against this set.

`maxent` in the report is MaxEnt's estimator rather than the Java program: infinitely weighted
logistic regression (Fithian & Hastie 2013), which is equivalent to fitting an inhomogeneous
Poisson process, over MaxEnt's feature classes (linear, quadratic, forward and reverse hinges at
five quantile knots) with an L1 penalty. The GAM is a natural-cubic-spline basis (six knots per
continuous feature) with a ridge penalty. Because the data are presence-background, the output of
every model is a **relative** occurrence score; absolute probability of finding a mushroom is not
identifiable from this data, so the map is calibrated to rank cells and the slider is expressed as
"the best X % of forest land" rather than as a percentage chance.

## 9b. Is a recorded find still a lead? (`ml/dataset/observation_status.py`)

The map plots all 445 records. Roughly a third of them are a municipality centroid with a
mushroom attached — 139 are located no better than 1 km, up to 100 km, and 16 of those share a
single pixel in Utsjoki — and the file reaches back to 1866, so a good many describe a forest
that was cut decades ago. Until this step every one of them was the same yellow dot.

Two questions, deliberately not merged into one score, because a tight dot on cut ground and a
vague ring on standing forest are different problems.

**How precisely was it located** (`prec`), from `unc_m` alone, at the thresholds
`build_dataset.py` already uses so the map and the model say the same thing about the same
record: `tarkka` ≤ 250 m (114) · `summittainen` ≤ 1 km (144) · `alueellinen` above that (139) ·
`tuntematon` where no accuracy was reported (48, nearly all herbarium specimens).

**Whether the ground is still what it was** (`hab`). Precision gates this: reading a 16 m cell
under a record located to ± 100 km describes the centroid, not the find, so `alueellinen` and
`tuntematon` records are never assessed. The remaining 258 are sampled at nine points — the
coordinate plus eight at the uncertainty disc's median radius, deterministic so the committed
output reproduces — and each point is judged, then the points are aggregated by majority with
ties going to the worse state and a minority "cut" pulling the record down rather than being
outvoted into silence.

| Evidence | Worth | Why |
|---|---|---|
| Metsäkeskus stand register says open or seedling | verdict: **muuttunut** | Harvesting-machine telemetry. The only thing here that is measured rather than estimated. |
| Regeneration felling declared | flag: **epavarma** | An intention, not an obligation; 57 % are realised. |
| MVMI 2023 stand age puts establishment after the find year, by more than the margin | verdict: **muuttunut** | The case this whole step exists for: a 1935 find standing in a forest planted in 1993. |
| Stand age ≥ 60 in the find's own cycle, ≤ 20 in 2023 | verdict: **muuttunut** | Forty years down in at most fourteen elapsed is a felling and nothing else. Covers 2009–2021, where the harvest layer does not reach. |
| Volume collapsed, or site/main type changed between cycles | flag: **epavarma** | Site type and main type describe soil, which does not turn over in fourteen years except by ditching — a disagreement is mostly the k-NN estimator changing its mind. |
| Off forestry land in **both** cycles | **ulkopuolella** | The cemetery case. MVMI never described this ground, so nothing can say the trees went and nothing can say they stayed. |
| Forestry-land mask moved between cycles | **nothing** | Measured over 1200×1200 cell windows: around Tampere 3.7 % of cells leave the mask between 2009 and 2023 and 5.6 % enter it; in Etelä-Savo 2.8 % each way. Symmetry at that scale is noise, not land-use change. |

`fra_luokka` was the obvious way to tell a treed churchyard (its class 4, "other land with tree
cover") from a car park. It carries the same forestry-land mask as every other MVMI theme, so
off forestry land it is empty too, and the branch was dropped. What the rosette can still report
is how much forestry land lies inside the record's own uncertainty — `forest_frac` — which is
the honest version of "the forest next door might still have it".

**The age margin is a bias correction, not a tolerance.** MVMI age is a k-NN estimate that
regresses toward the plot mean, so old stands read young, which is exactly the direction that
manufactures false "the forest was replaced" verdicts. `--report` prints the verdict counts at
10 / 20 / 30 / 40 years; 20 is what shipped.

### What this cannot tell you

- The stand register covers **privately owned forest only**. `ennallaan` on Metsähallitus land
  is weaker evidence than the same word on private land, and the app cannot say which you are
  looking at. `cut = 0` means the register has nothing here, never "the forest is standing".
- **MVMI cannot see a thinning.** A stand taken down to 40 % of its volume still reads
  `ennallaan` here and may well have lost its matsutake. This detects replacement, not decline.
- Nothing here validates the **identification**. A `tarkka` + `ennallaan` dot still rests on
  somebody's 1970 determination.
- 2009 and 2011 are on a 20 m grid with a different origin, so a cross-cycle comparison is
  nearest-neighbour. The residual half-cell is far inside the record's own uncertainty, and the
  nine-point rosette absorbs it.

### Known, not fixed

`cycle_for_year()` floors at 2009, so an 1866 find located to 1 m trains the model against 2009
forest — some presences describe a stand that did not exist when the mushroom was found. This
step now measures how many, but does not act on it; feeding the verdict back into
`build_dataset.py` would touch the model, its metrics and the published rasters.

## 10. What shipped

- `ml/` — reproducible pipeline: observations, GTK and FMI rasters, a 16 m elevation warp,
  cycle-matched feature extraction, training with spatial CV, inference, app export.
- `ml/models/matsutake/` — the five fold networks, the scaler, and the cross-validation report.
- `data/matsutake/` — the published map, nine Cloud-Optimised GeoTIFF parts at 16 m.
- The app's 🧠 panel: model layer, "best X % of forest land" slider, and a model row in the
  tap readout.

Two failures worth remembering, both now fixed in code: a tiled compressed GeoTIFF writes its
tile index only on close, so an interrupted run leaves unreadable tiles; and the browser reads
these files with HTTP range requests, which `python3 -m http.server` ignores, so the layer looks
broken locally unless served with `serve.py`.

## 11. Open items

- Phenology layer (rain accumulation over the season, summer warmth, snowmelt date).
- Second species through the same configuration once matsutake is validated.
- Lichen cover has no open raster; site class and soil are standing in for it.

## 12. Stand openness / light (2026-09-20)

Revisited on a direct report: every matsutake the user has personally found, and every one
recognisable from photos, stood in a visibly open, light stand — not a dense, forestry-grade
pine plantation. That matches what §1's "Light" row already flagged as unimplemented, and it is
the single strongest signal in §4.1 that was not acted on: `latvuspeitto` ≤ 50 % holds for 70 %
of the 104 fine presences, against 42 % of random forestry land and only 19 % of the other-fungi
background — a bigger gap than age, pine volume, or anything except soil grain and the
glaciofluvial-formation flag. Vaario et al. 2015 (the only Finnish field study) independently
reports the best yields in 41–60 yr pure pine stands with "moderately open A–B canopy density",
not the densest ones; the US Forest Service's write-up of the sibling species *T. magnivelare*
gives the same story — management that lets light reach the forest floor outproduces dense
thinning-age pine.

`latvuspeitto` (canopy cover) was already a model feature (`ml/core/features.py`, incl. its 3×3
and 9×9 neighbourhood means) but was never in the app's rule filter — matsutake was the only one
of the five species with no canopy-cover control at all. Checked Luke's open MVMI theme list
(45 themes, `LUETAMA-2019.txt`): there is no published stems/ha (`runkoluku`) raster — it is only
used internally to derive seedling-stand canopy cover — but `keskilapimitta_` (mean diameter, cm)
*is* open and was not being read. Combined with the already-read `ppa` (basal area), it gives the
standard forestry stem-count estimate `N = ppa / (π/4 · d²)`, a real stand-density figure and a
better structural proxy than the ad hoc `ppa / keskipituus` the model used before — an old,
widely-spaced stand and a young dense one can share the same canopy cover but not the same stem
count.

What changed:
- `ml/core/features.py`: added `keskilapimitta` as an MVMI theme/feature; replaced the old
  `stem_density` proxy with `stems_ha`, the basal-area/diameter stem-count estimate.
- `ml/train/train.py`: added a `structure` ablation group (`latvuspeitto`, `ppa`, `stems_ha`,
  `keskilapimitta` and their neighbourhood means) so the report can show how much this group is
  worth.
- `js/species.js` / `js/constants.js`: matsutake gets a "Latvuspeitto enintään" slider, default
  60 % (`MATSU_MAX_COVER`) — the same threshold already validated as rule E in `train.py`'s rule
  baselines, which drops recall only from 48 % to 45 % on top of the existing default conditions
  while cutting the mapped area.
- Pending after this change: rerun `build_dataset.py` → `train.py` → `predict.py` →
  `export_app.py` to retrain on the new features and re-publish the probability raster; the
  §10 "what shipped" model and the report numbers in `docs/MODEL_REPORT_matsutake.md` are stale
  until that runs.
