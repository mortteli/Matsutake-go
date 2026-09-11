# Data sources and licences

This repository is public. Everything under `data/` and `ml/data/` is either open data redistributed under its own licence, or derived from such data. Records whose licence does not allow redistribution (all rights reserved) or requires share-alike were dropped before anything was stored or trained on (`ml/fetch_observations.py`, `redistributable()`).

## Environmental data (all CC BY 4.0)

| Dataset | Producer | Licence | Used for |
|---|---|---|---|
| Monilähteinen VMI (MS-NFI) forest maps 2009–2023, 16 m | Luonnonvarakeskus (Luke) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | site class, main type, age, volumes by species, basal area, canopy cover, height — app filters and model features |
| Elevation model 10 m | Maanmittauslaitos (MML) | CC BY 4.0 | elevation, slope, aspect, TPI, relief |
| Maaperä 1:200 000 (superficial deposits) and Glacigenic landforms | Geologian tutkimuskeskus (GTK) | CC BY 4.0 | soil class, esker / glaciofluvial formation — rasterized copies in `ml/data/rasters/gtk_*_16m.tif` |
| Gridded daily/monthly climate 10 km (1961–) | Ilmatieteen laitos (FMI) | CC BY 4.0 | thermal sum and precipitation normals in `ml/data/climate/` |
| Copernicus DEM GLO-90 via Open-Meteo | ESA / Open-Meteo | CC BY 4.0 | slope readout in the app |

Attribution text used in the app and in derived files: *© Luonnonvarakeskus (Luke) MVMI, © Maanmittauslaitos, © Geologian tutkimuskeskus, © Ilmatieteen laitos — CC BY 4.0.*

## Occurrence records (training presences), `ml/data/matsutake/observations.csv`

445 records of *Tricholoma matsutake* in Finland, fetched from GBIF and the Finnish Biodiversity Information Facility (FinBIF, laji.fi) on 2026-09-10. Each row carries its own `license`. Licence mix: CC BY 4.0: 396, CC BY-NC 4.0: 49.

| Source | Dataset / collection | Licence | Records |
|---|---|---|---|
| GBIF | [The Atlas of Finnish Fungi](https://www.gbif.org/dataset/2bc4c2db-1dfa-419c-93ce-6602c5ae8c99) | CC BY 4.0 | 99 |
| GBIF | [Agaricales Fennoscandiae orientalis](https://www.gbif.org/dataset/3e256ae0-cfcb-4614-84e8-f511545dd34f) | CC BY 4.0 | 95 |
| GBIF | [Fungal collection of the Botanical Museum, University of Oulu (OULU)](https://www.gbif.org/dataset/23acc755-a8a6-4cf8-bed0-83d30863acea) | CC BY 4.0 | 45 |
| GBIF | [TUR Fungus collections of the University of Turku](https://www.gbif.org/dataset/166fab75-907b-4768-8d58-05c5badab9f6) | CC BY 4.0 | 33 |
| FinBIF (laji.fi) | [iNaturalist Suomi Finland](https://laji.fi/collection/HR.3211) | CC BY-NC 4.0 | 33 |
| GBIF | [Fungi collection of the University of Eastern Finland](https://www.gbif.org/dataset/cdbcc960-d9d9-43b8-bdaa-148fb034a635) | CC BY 4.0 | 32 |
| GBIF | [iNaturalist Research-grade Observations](https://www.gbif.org/dataset/50c9509d-22c7-4a22-a47d-8c48425ef4a7) | CC BY-NC 4.0 | 16 |
| GBIF | [Notebook, general observations](https://www.gbif.org/dataset/df12ca07-f133-4550-ab3b-fde13f0e76ba) | CC BY 4.0 | 16 |
| GBIF | [LajiGIS: Species mapping and surveys](https://www.gbif.org/dataset/687c05e9-96d6-40e3-b1c9-2e026d0b3fc0) | CC BY 4.0 | 15 |
| GBIF | [Löydös Open Finnish Observation Database](https://www.gbif.org/dataset/956bc674-6022-4c52-833e-c5fb39dc837a) | CC BY 4.0 | 12 |
| GBIF | [KUO Fungal collections](https://www.gbif.org/dataset/e175d14f-c9e8-4a35-8e4a-372b72bbf797) | CC BY 4.0 | 10 |
| GBIF | [LajiGIS: Miscellaneous occurrences](https://www.gbif.org/dataset/128e38cb-9d38-4ecf-989a-1d66175c20e6) | CC BY 4.0 | 9 |
| GBIF | [marine metagenome Metagenome](https://www.gbif.org/dataset/f71cff20-c223-445a-9fb1-ff3a7466d993) | CC BY 4.0 | 7 |
| GBIF | [NABU|naturgucker](https://www.gbif.org/dataset/6ac3f774-d9fb-4796-b3e9-92bf6c81c084) | CC BY 4.0 | 5 |
| GBIF | [LajiGIS: Species monitoring sites](https://www.gbif.org/dataset/887bd779-6454-436f-b1f8-86b70488b59f) | CC BY 4.0 | 4 |
| FinBIF (laji.fi) | [Notebook, general observations](https://laji.fi/collection/HR.1747) | CC BY 4.0 | 3 |
| GBIF | [Fungi collection of Jyväskylä University Museum](https://www.gbif.org/dataset/8431711e-f762-11e1-a439-00145eb45e9a) | CC BY 4.0 | 2 |
| GBIF | [International Barcode of Life project (iBOL)](https://www.gbif.org/dataset/040c5662-da76-4782-a48e-cdea1892d14c) | CC BY 4.0 | 2 |
| FinBIF (laji.fi) | [Agaricales Fennoscandiae orientalis](https://laji.fi/collection/HR.137) | CC BY 4.0 | 2 |
| FinBIF (laji.fi) | [The Atlas of Finnish Fungi](https://laji.fi/collection/HR.2129) | CC BY 4.0 | 2 |
| GBIF | [Botanical Collections of the Åbo Akademi](https://www.gbif.org/dataset/9f6be6a5-fa23-4471-97c6-67cd21bcf53a) | CC BY 4.0 | 1 |
| GBIF | [HAMBI Fungal Biotechnology Culture Collection (FBCC)](https://www.gbif.org/dataset/8baeafb0-20a4-4114-a3ac-2c26c881c65d) | CC BY 4.0 | 1 |
| FinBIF (laji.fi) | [Nature surveys Manninen](https://laji.fi/collection/HR.5136) | CC BY 4.0 | 1 |

GBIF asks that data use is cited; the records here came through the GBIF occurrence API (no download DOI). Cite as: GBIF.org (2026-09-10) GBIF Occurrence Search, *Tricholoma matsutake*, Finland, https://www.gbif.org/occurrence/search?taxon_key=5241820&country=FI ; and FinBIF: Suomen Lajitietokeskus / FinBIF (2026-09-10), https://laji.fi/taxon/MX.72541.

## Target-group background records, `ml/data/matsutake/background_fungi.csv`

3295 records of other fungi (August–September, 2010–, coordinate accuracy ≤ 250 m) used only as presence-background contrast. Licence mix: CC BY 4.0: 2462, CC BY-NC 4.0: 784, CC0 1.0: 49.

| Source | Dataset / collection | Licence | Records |
|---|---|---|---|
| GBIF | [The Atlas of Finnish Fungi](https://www.gbif.org/dataset/2bc4c2db-1dfa-419c-93ce-6602c5ae8c99) | CC BY 4.0 | 949 |
| GBIF | [iNaturalist Research-grade Observations](https://www.gbif.org/dataset/50c9509d-22c7-4a22-a47d-8c48425ef4a7) | CC BY-NC 4.0 | 672 |
| GBIF | [LajiGIS: Species mapping and surveys](https://www.gbif.org/dataset/687c05e9-96d6-40e3-b1c9-2e026d0b3fc0) | CC BY 4.0 | 651 |
| GBIF | [LajiGIS: Miscellaneous occurrences](https://www.gbif.org/dataset/128e38cb-9d38-4ecf-989a-1d66175c20e6) | CC BY 4.0 | 297 |
| GBIF | [LajiGIS: Species monitoring sites](https://www.gbif.org/dataset/887bd779-6454-436f-b1f8-86b70488b59f) | CC BY 4.0 | 274 |
| GBIF | [Notebook, general observations](https://www.gbif.org/dataset/df12ca07-f133-4550-ab3b-fde13f0e76ba) | CC BY 4.0 | 214 |
| GBIF | [Observation.org, Nature data from around the World](https://www.gbif.org/dataset/8a863029-f435-446a-821e-275f4f641165) | CC BY-NC 4.0 | 112 |
| GBIF | [iNaturalist Research-grade Observations](https://www.gbif.org/dataset/50c9509d-22c7-4a22-a47d-8c48425ef4a7) | CC0 1.0 | 49 |
| GBIF | [iNaturalist Research-grade Observations](https://www.gbif.org/dataset/50c9509d-22c7-4a22-a47d-8c48425ef4a7) | CC BY 4.0 | 30 |
| GBIF | [The Vaasa Society for the Environment Species Observations](https://www.gbif.org/dataset/22507486-e8de-4173-bf82-561b911b8747) | CC BY 4.0 | 28 |
| GBIF | [Löydös Open Finnish Observation Database](https://www.gbif.org/dataset/956bc674-6022-4c52-833e-c5fb39dc837a) | CC BY 4.0 | 18 |
| GBIF | [Finnish invasive species observations](https://www.gbif.org/dataset/083fd36d-c3d1-4631-b6fb-cb6fa2ea8f47) | CC BY 4.0 | 1 |

## Derived data in this repository

| File | What | Licence |
|---|---|---|
| `ml/data/matsutake/dataset.csv` | training table: the records above joined with environmental features | CC BY-NC 4.0 (contains CC BY-NC records) |
| `ml/models/matsutake/` | model weights, scaler, CV report | CC BY-NC 4.0 |
| `data/matsutake/prob_*.tif`, `prob_meta.json` | the published 16 m habitat map: 9 Cloud-Optimised GeoTIFF parts, EPSG:3067, value = model score × 100, 255 = no forestry data. Scores below 21 (the best 25 % of forest land) are stored as 0 and the rest quantised to steps of 2, which halves the files with no visible difference | CC BY-NC 4.0 — attribution as above; non-commercial because CC BY-NC observation records contributed to training |
| `ml/data/climate/*.tif`, `ml/data/rasters/gtk_*_16m.tif`, `ml/data/gtk_classes.json` | rasterized / aggregated copies of FMI and GTK data | CC BY 4.0 (© FMI, © GTK) |

To publish the derived layers under plain CC BY 4.0, re-run the pipeline with the CC BY-NC records removed (`ml/fetch_observations.py` — filter on the `license` column).

Software licences: see `LICENSE` (MIT) and `THIRD_PARTY_LICENSES.md`.
