# Sweden — open forest data for training (comparison to Finland)

Sweden's matsutake range extends into the far north (Norrbotten), and finds are turning up there
in growing numbers. This started as a source audit against Finland's `ml/` pipeline and turned
into a working first cut: `ml/core/grid_se.py` and four `ml/ingest/fetch_*_se.py`-style scripts
now exist and have each been run against real data (see "What's actually been run" below). This
document is both the audit and the record of what was verified while building it.

## Source-by-source match

| Role in the FI pipeline | Finnish source | Swedish equivalent | Producer | Resolution / CRS | Licence | Access |
|---|---|---|---|---|---|---|
| Forest structure (volumes, height, diameter, basal area, biomass) | Monilähteinen VMI (MVMI), 16 m | **SLU forest map** (Skogliga grunddata), 2015 "leaf" set | SLU + Skogsstyrelsen, from Lantmäteriet laser scanning + Riksskogstaxeringen field plots | 12.5 m, SWEREF99 TM (EPSG:3006) | Open data | **Plain static GeoTIFFs on `gis.slu.se`, no login** — `/vsicurl/` works exactly like Paituli does for MVMI. Confirmed live: `ml/core/grid_se.py` reads the real header (52400×97400 px, 12.5 m, EPSG:3006) over the network. The *Skogsstyrelsen*-branded WMS/REST wrapper around the same data does need an account — irrelevant here since the ingest scripts never touch it |
| Species share of volume | manty/kuusi/koivu volumes | SLU forest map, 2018 "andel" set: pine/spruce/birch/oak/beech/contorta/other-deciduous | SLU + Skogsstyrelsen | 12.5 m | Open data | Same server, same access, confirmed via directory listing |
| Stand age | age (all MVMI cycles) | SLU forest map, 2010 vintage only | SLU + Skogsstyrelsen | 25 m, **RT90 2.5 gon V (EPSG:3021)**, not SWEREF99 | Open data | Confirmed present at `2010/Data/Raster/Rt90/AGE_XX_P_10.tif`; needs reprojecting before use, and is ~15 years stale — no newer age raster is published alongside the 2015/2018 sets |
| Elevation / slope / aspect | MML 10 m DEM | Lantmäteriet höjddata, grid 1 m | Lantmäteriet | 1 m | CC0 | `opendata.lantmateriet.se` — free account required (not yet obtained; nothing built against it yet) |
| Soil | GTK Maaperä 1:200 000 | **SGU Jordarter** | SGU | 1:25 000–1:100 000 (3.4 GB zip) or 1:1 000 000 (15 MB zip) | Open data (SGU's WMS states `Fees: NONE`, `AccessConstraints: NONE`) | Direct GeoPackage-in-zip download, no login: `resource.sgu.se/data/oppnadata/...` |
| Stand reality-check (remove clear-cuts) | Metsäkeskus metsävarakuviot | **Utförda avverkningar** (`sksUtfordAvverk`) | Skogsstyrelsen | vector, GeoPackage, 2.7 GB zip | Open data | Direct download, no login: `geodpags.skogsstyrelsen.se/geodataport/data/` |
| Declared-but-not-cut (tap-only info) | Metsäkeskus metsänkäyttöilmoitukset | **Avverkningsanmälan** (`sksAvverkAnm`) | Skogsstyrelsen | vector, GeoPackage, 67 MB zip | Open data | Same portal |
| Climate normals | FMI gridded 10 km | **SMHI PTHBV** | SMHI | ~4 km, point/multipoint query only (no bulk grid file) | CC BY 4.0 SE | `opendata-download-metanalys.smhi.se` — public JSON API |
| Training presences | GBIF + FinBIF (laji.fi) | GBIF, fed by Artportalen | GBIF.org | point | Mixed CC0 / CC BY-NC | GBIF occurrence API |

## What's actually been run

- **`ml/core/grid_se.py`** — read live against `gis.slu.se`. Confirmed: SWEREF99 TM (EPSG:3006),
  12.5 m cells, 52400 × 97400 px, bounds (267500, 6132500)–(922500, 7350000).
- **`ml/ingest/fetch_observations_se.py`** — run to completion against the live GBIF API.
  **5501** georeferenced Swedish *Tricholoma matsutake* records (vs Finland's 445), 5215 of them
  at ≤250 m coordinate uncertainty, none dropped on licence. That count needs a large caveat,
  though: **only 33 of the 5501 (0.6 %) carry a validated identification** — the rest are
  `identificationVerificationStatus=Unvalidated` citizen sightings straight from Artportalen, not
  expert-reviewed museum/collection records the way most of the Finnish set is. The sample is also
  almost entirely recent: of the first 300 records fetched, 299 were logged in 2024–2026 — this
  really does look like the recent wave the map is being built to catch, not a hundred years of
  steady reporting the way Finland's set reads. The new `verification_status` column exists so
  training can weight or filter on it rather than pooling both kinds of record at face value.
  Output: `ml/data/matsutake_se/observations.csv` (committed).
- **`ml/ingest/fetch_sgu.py`** — both resolutions have now been downloaded and verified in full
  (not just the coarse one). Coarse (1:1 000 000, 15 MB): layer `grundlager`, code field `jg2`
  (int), name field `jg2_tx`, 45121 polygons, EPSG:3006 already (no reprojection needed, unlike
  GTK's WFS for Finland) — ran end-to-end, rasterized cleanly. Fine (1:25 000–1:100 000, 3.4 GB
  zip / 8.7 GB gpkg): the `grundlager` layer and `jg2`/`jg2_tx` fields carry over exactly as
  guessed — but the fine product is **2 956 837 polygons**, 65× the coarse one, and also ships
  two more detailed candidate layers not in the coarse product: `ytlager` (`jy1`/`jy1_tx`) and
  `oversta_ytlager` (`jy0`/`jy0_tx`, the topmost surface layer — arguably the more ecologically
  relevant one for matsutake's dry sandy/lichen-ground preference than the geological `grundlager`
  it currently reads). The fine layer's rasterize was **not** run to completion: the coarse run
  alone took over 10 minutes for 45121 polygons in the current block-by-block Python
  STRtree+rasterize approach, so 2.96 M polygons at the same rate would be impractically slow —
  this needs a different strategy (per-region tiling, or shelling out to `gdal_rasterize` if it's
  available in the target environment; it isn't in this one) before it's usable at full
  resolution, not just a bigger run of the same code.
- **`ml/ingest/fetch_skogsstyrelsen_harvests.py`** — both halves have now been run end-to-end
  against full local copies. Declared-felling (`sksAvverkAnm_gpkg.zip`, 67 MB): layer
  `AvverkningsAnmalanYta`, 129176 features, EPSG:3006. **`Avverktyp` is the felling-type field to
  filter on, not `Andamal`** — that was the first guess and it's wrong: `Andamal` is 92 %
  `"Uppgift saknas"` (no data), a purpose/land-use field, not a felling-type one.
  `Avverktyp='Föryngringsavverkning'` (regeneration felling) matched 120102 of 129176 records and
  rasterized in 20 seconds. Completed-felling (`sksUtfordAvverk_gpkg.zip`, 2.7 GB zip / 7.5 GB
  gpkg): layer is `UtfordAvverkningYta` (not the guessed `UtfordAvverkYta`), 1381787 features. The
  field guess carried over correctly this time — same `Avverktyp='Föryngringsavverkning'`, matching
  94 % of records — but the layer is built from Sentinel-2 change detection
  (`KallaDatum`='Bildanalys', `Forebild`/`Efterbild` before/after image IDs) rather than machine
  telemetry the way Finland's stand register is, and its date field is `Avvdatum`, not
  `Inkomdatum`. Full run: ~7.5 minutes to load 1343406 matching polygons, ~5 minutes to rasterize
  across 312 blocks — 12.5 minutes end to end, 279.8 million of 5.1 billion cells (5.5 %) flagged
  as completed fellings.
- **`ml/ingest/fetch_smhi_climate.py`** — run against the live API for a 40-point sample. Found
  and fixed two real API quirks while doing it: multipoint queries take **repeated `ll=` params**,
  not a semicolon-joined list (the API's own error message said so), and the server 400s without
  `Accept-Encoding: gzip`. 22 of the 40 sample points returned land data, the rest sea/border
  nulls, which the script now filters instead of crashing on. A full-country run is ~50 000
  lattice points in ~1000 batched requests — not run in full here, but every piece of the pipeline
  (lattice generation, batching, null handling, GeoTIFF writing) has been exercised against the
  real API.
- **`ml/ingest/download_slu_forestmap.sh`** — every URL in it was checked with a real HTTP
  request (directory listing or HEAD) before being written in; the files themselves (1–3.5 GB
  each, ~10 GB total) were not downloaded in full given the size.

## Where it doesn't line up

- **No direct site-fertility-class layer.** The SLU forest map gives volumes, height, diameter,
  basal area and biomass, not a soil-fertility class the way MVMI's `kasvupaikka` does. A stand-in
  would have to be engineered from SGU soil texture (sandy/esker ground for the dry, lichen-rich
  sites matsutake wants) plus low canopy cover plus pine dominance.
- **No canopy-cover layer either**, but there's a workable substitute not yet wired up:
  Naturvårdsverket's Nationella marktäckedata (NMD), CC0, 10 m, giving percent coverage in two
  height bands.
- **Age is stale and in the wrong projection** — see the table above.
- **Presence data is much larger but far less curated than Finland's.** 5501 vs 445 sounds like an
  advantage, but only 33 records have been through any identification review, and the recency
  skew (2024–2026) suggests a lot of it is the same recent public-attention wave that prompted
  this whole audit, not decades of steady collection the way the Finnish museum records are.

## What's better in Sweden

- Elevation at 1 m vs Finland's 10 m (once a Lantmäteriet account exists).
- Species-level volumes split further (contorta, oak, beech) via the 2018 "andel" set.
- The completed-felling layer is very likely all forest ownership, not just private land the way
  Metsäkeskus's kuviot are limited to: it's built from Sentinel-2 before/after image comparison
  (`KallaDatum`='Bildanalys'), which doesn't care who owns the ground the way Finland's
  machine-telemetry stand register does. No ownership field to check directly, but the detection
  method itself implies uniform coverage.
- The forest-attribute rasters need no account at all for the ingest pipeline (only the
  Skogsstyrelsen-branded live-tile WMS does), unlike what Skogsstyrelsen's own documentation pages
  suggest at first read.

## Next steps

1. Speed up `fetch_sgu.py`'s rasterizer (or tile it by county) before attempting the fine-scale
   1:25k-100k soil pass — the schema is confirmed but a 2.96 M-polygon full run isn't practical
   with the current per-block STRtree approach. Consider `oversta_ytlager` (topmost surface soil)
   instead of `grundlager` (parent material) while doing so.
2. Register a Lantmäteriet open-data account for the elevation grid.
3. Run `download_slu_forestmap.sh` and the full `fetch_smhi_climate.py` country pass.
4. Build `ml/core/features_se.py` alongside `features.py`, and a `dataset_se.csv` builder — treat
   Sweden as a second, parallel model rather than pooling training rows with Finland's, since the
   feature sets aren't the same shape yet (proxy canopy cover, no native site class, a stale
   reprojected age layer).
5. Decide how to handle `verification_status` in training — at minimum, check whether restricting
   to validated-only records changes anything before trusting the full 5501.
