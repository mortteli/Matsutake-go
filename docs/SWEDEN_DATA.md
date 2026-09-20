# Sweden — open forest data for training (comparison to Finland)

Sweden's matsutake range extends into the far north (Norrbotten), and finds are
turning up there in GBIF/Artportalen. This is a data audit for whether Sweden
has an open-data stack that could support the same pipeline as
[`ml/`](../ml/README.md) — not an implementation yet. Short answer: **yes, almost
variable for variable**, but three things differ enough to matter before any
code gets written: raster access needs a login (unlike Luke's open CORS WMS),
two feature layers have no direct equivalent, and the national grid is a
different projection.

## Source-by-source match

| Role in the FI pipeline | Finnish source | Swedish equivalent | Producer | Resolution | Licence | Access |
|---|---|---|---|---|---|---|
| Forest structure (site type, main type, age, species volumes, canopy cover) | Monilähteinen VMI (MVMI), 16 m | **Skogliga grunddata** (National Forest Attribute Maps) | SLU + Skogsstyrelsen, from Lantmäteriet laser scanning + Riksskogstaxeringen (NFI) field plots | 12.5 m (2015 vintage); 25 m for the 2000/2005/2010 vintages | Open data, CC0 per Skogsstyrelsen's open-data page | Download (`gis.slu.se/data/slu_forest_map`), WMS/WFS/REST via Skogsstyrelsen's "Geodatatjänster" — **raster download/WMS needs a free user account**, unlike Luke's account-free CORS GeoServer |
| Elevation / slope / aspect | MML 10 m DEM | **Lantmäteriet höjddata**, grid 1 m (newer, finer than Finland's) | Lantmäteriet | 1 m | CC0 | `opendata.lantmateriet.se`, account required but free, no fee |
| Soil / esker | GTK Maaperä 1:200 000 + glacigenic formations | **SGU Jordarter** (soil type map, best available scale per area) + glaciofluvial/esker layer | SGU (Sveriges geologiska undersökning) | 1:25 000–1:100 000 where mapped, 1:1 000 000 fallback elsewhere | Stated as open data on SGU's site; exact licence text not yet confirmed — verify before redistributing derived rasters | WMS (`resource.sgu.se/service/wms/130/...`) + download |
| Climate normals (thermal sum, precipitation) | FMI gridded 10 km | **SMHI** gridded climate data (PTHBV-type products) | SMHI | ~4 km grid | CC BY 4.0 SE | `opendata.smhi.se` |
| Stand reality-check (remove clear-cuts from the current-generation mask) | Metsäkeskus metsävarakuviot (dev. class) | **Utförda avverkningar** (completed fellings — actual measured clear-cut polygons, similar detection method) | Skogsstyrelsen | vector | CC0 | `geodpags.skogsstyrelsen.se`, no login for vector downloads |
| Declared-but-not-yet-cut (tap-only info layer) | Metsäkeskus metsänkäyttöilmoitukset | **Avverkningsanmälda områden** (harvest notifications) | Skogsstyrelsen | vector | CC0 | same portal |
| Training presences | GBIF + FinBIF (laji.fi) | GBIF, fed by **Artportalen** (Swedish Species Observation System) | GBIF.org / SLU Artdatabanken | point | Mixed CC0 / CC BY / CC BY-NC per record, same pattern as FinBIF | GBIF occurrence API, `taxonKey=5241820&country=SE` |

Sweden uses **SWEREF99 TM (EPSG:3006)** as its national grid, the equivalent of
Finland's ETRS-TM35FIN (EPSG:3067) — same idea (a single national TM
projection), different code and origin, so nothing in `core/grid.py` carries
over as-is.

## Where it doesn't line up

- **Login wall on the raster side.** The app's live map layer works by asking
  Luke's GeoServer for a `SLD_BODY`-recoloured tile straight from the browser
  — no server, no key, CORS open. Skogsstyrelsen's WMS/REST for the forest
  attribute rasters wants an account. That rules out the live-tile trick for
  a Swedish rule-based layer; it would need the same treatment already used
  for the harvest correction and the probability map — pre-bake Cloud-Optimised
  GeoTIFFs offline and ship them as static files read via HTTP range requests.
- **No direct `kasvupaikka` (site fertility class) layer.** Skogliga grunddata
  gives volumes, height, diameter, basal area and biomass, not a soil-fertility
  class. A stand-in would have to be built from SGU soil texture (sandy/esker
  ground for the dry, lichen-rich sites matsutake wants) plus low canopy cover
  plus pine dominance — a real feature-engineering step, not a straight port of
  `mvmi_point.py`.
- **No direct canopy-cover layer either**, but there is a workable substitute:
  Naturvårdsverket's **Nationella marktäckedata (NMD)**, a supplementary raster
  giving percent coverage in two height bands (0.5–5 m and 5–45 m), 10 m grid,
  CC0, no account needed. That maps reasonably well onto `latvuspeitto`.
- **Age is stale.** The `age` raster only exists for the 2000/2005/2010
  vintages (25 m); the current 2015, 12.5 m vintage doesn't carry it in what's
  documented publicly. Skogsstyrelsen mentions a second laser-scanning round
  finishing in 2024, so a newer age product may exist behind the account wall
  — needs checking once someone has logged in, not something a web search
  resolves.
- **Presence data may be thinner than it looks.** The literature (Danell &
  Camacho's Swedish matsutake survey) counts only ~81 records nationally
  between 1849–1997, though a dedicated 1998 field survey found 121 localities
  in Norrbotten — those field-survey localities likely predate Artportalen and
  may not be digitized into GBIF at all. Worth pulling actual GBIF counts
  (`ml/ingest/fetch_observations.py`-style query, `country=SE`) before assuming
  parity with Finland's 445 records.

## What's *better* in Sweden

- Elevation at 1 m vs Finland's 10 m.
- Species-level volumes include contorta, oak and beech separately, not just
  pine/spruce/birch.
- The clear-cut correction layer (`Utförda avverkningar`) looks like it may
  cover all forest ownership, not just private land the way Metsäkeskus's
  kuviot are limited — worth confirming, since that was the one hard limit
  called out in the Finnish harvest-correction section of the README.

## If this goes ahead

Roughly the same shape as the existing `ml/ingest/` scripts, one per source
(`fetch_slu_forestmap.py`, `fetch_sgu.py`, `fetch_smhi_climate.py`,
`fetch_skogsstyrelsen_harvests.py`), plus a SWEREF99 TM grid definition
alongside the existing ETRS-TM35FIN one in `core/grid.py`. Given the feature
gaps above, treat it as a second, parallel model rather than pooling
Finnish and Swedish training rows into one — the feature sets aren't quite
the same shape (no native site-class raster, a proxy canopy-cover source,
a stale age layer) until that's built and validated on its own, the same way
`docs/HABITAT_MODEL_PLAN.md` was validated against Finnish GBIF records before
being trusted.

Before writing any ingest code: register a Skogsstyrelsen open-data account to
see the actual WMS `GetCapabilities` and raster band names, and pull the real
GBIF occurrence count for `country=SE` to see how much presence data there
actually is to train on.
