# Data pipeline review: performance and external-API fair use

Scope: everything that moves data into the app, both **baked** (run once offline, shipped as
files) and **live** (fetched from the browser on every visit). Findings are from reading the
code, not from live measurement against the third-party services — figures like Luke's
concurrency cap are the app's own code comments, taken at face value.

> **Status (implemented).** Everything recommended below is in the code, except the one part that
> needs a pipeline run on a machine with the DEM. Measured in Chromium against a stubbed Luke, on
> a load / four pans / one tap at zoom 12:
>
> | | before | after |
> |---|---|---|
> | peak simultaneous requests to Luke | **153** | **5** |
> | Luke requests for the whole session | 435 | 269 |
> | Luke requests per tap (matsutake defaults) | 30 | 29 |
> | Metsäkeskus requests on opening the app (zoom 5) | **101 964** | **0** |
>
> The last row is a storm this review did not catch: `SpotLayer.createTile` asked Metsäkeskus for
> every 10 km cell its tile covered, and at zoom 5 a tile covers some 600 km, so simply opening the
> app fired ~100 000 WFS requests — enough that Chromium ran out of sockets. The drawn "Hakkuut"
> overlay already had a zoom floor for exactly this reason; the mask path now shares it
> (`MK_MINZOOM`). §4 (baked slope) is implemented in the app and in `ml/export/export_terrain.py`; until a
> deployment runs that export and publishes `data/terrain/`, the app still falls back to Open-Meteo
> per tap, which is the documented behaviour rather than an outstanding to-do.

The Metsäkeskus half of this was already reviewed and fixed in
[docs/PERF_HANDOVER_hakkuut.md](PERF_HANDOVER_hakkuut.md) (PRs #7/#8): propertyName trimming, an
LRU cell cache, a non-blocking tile path, a canvas renderer, and direct point queries for taps are
all in place and verified in the current code. That work does not need revisiting. What follows is
the rest of the pipeline — most importantly, the **same class of problem Metsäkeskus already had
is still present, unfixed, on the Luke WMS side**, and it is the biggest live-API risk in the app.

---

## What is baked

Baked = computed once by `ml/*.py`, committed as static files, read by the browser via HTTP range
requests on the GeoTIFFs — no API call at request time.

| Files | Built by | From | Used for |
|---|---|---|---|
| `data/matsutake/prob_matsutake_16m_*.tif` (9 parts) | `ml/export/predict.py` + `ml/export/export_app.py` | Luke MVMI, MML 10 m DEM, GTK soil/glacigenic, FMI climate normals, GBIF/FinBIF training points | **Matsutake only** — the 🧠 probability map |
| `data/matsutake/cut_matsutake_16m_*.tif` (9 parts) | `ml/ingest/fetch_harvests.py` | Metsäkeskus bulk GeoPackages (stand + declarations) | Grey-out layer under the probability map, and the offline fallback for tap/overlay when the live WFS is unreachable |
| `data/matsutake/prob_meta.json` | same | — | Manifest: bounds, file list, cut metadata (`built` date) |
| `ml/data/rasters/dem_16m.tif` (84 MB) | `ml/ingest/build_dem16.py` | MML 10 m DEM, warped once to the 16 m analysis grid | Model training/inference only — **not shipped as a client-readable product today** (see §4 below) |
| `ml/data/climate/*.tif`, `ml/data/gtk_classes.json`, `ml/data/matsutake/observations.csv` | `climate.py`, `fetch_gtk.py`, `fetch_observations.py` | FMI, GTK, GBIF/FinBIF | Model training inputs only |

The other four species — herkkutatti, kanttarelli, suppilovahvero, ukonsieni — have **no baked
layer at all**. Every pixel of their map is a live Luke WMS request, every time, for every viewer.

---

## Live external APIs and fair use, one by one

**Luke GeoServer WMS** (`kartta.luke.fi/geoserver/MVMI/wms`) — the rule-based species layer and
the tap probes. The code itself documents the constraint (`index.html:458,515-516`):

> `x-concurrent-limit-user: 6`

and one call site respects it (`scanMask` → `compositeMask(..., NEARBY_PAR)`, pooled at 3). **Two
call sites do not:**

- `SpotLayer.createTile` (`index.html:1220`) calls `compositeMask(species.conditions(c), bbox,
  size.x, size.y, 0, cut.features)` — **`limit = 0`**, and `mapPool` treats `limit <= 0` as "no
  pooling, plain `Promise.all`" (`index.html:518`). Every visible tile fires all of its
  condition-layer jobs at once, uncapped.
- `inspect()` (`index.html:1734-1742`) does the same for a tap: `readClass` (8 candidates for
  `LAYER.site`, 4 for `LAYER.main`) and `readMetric` per metric (see below) are all plain
  `Promise.all`, no pool.

This is not a small overshoot. One tile for kanttarelli used to be 7 jobs (site + main + age +
cover + a 3-way host union with `pineToo` on); replacing that union with a single total-volume
condition makes it 5, or 6 with the spruce toggle, but suppilovahvero and herkkutatti are still
5 each and the pooling is still missing, so the shape of the problem is unchanged. Leaflet's
default `keepBuffer` (2) means many tiles are being created at once on any pan or zoom. Dozens of tiles × several jobs each routinely means 50-100+
simultaneous requests to a server whose own header says 6 — from the *one* call site the code
already knows needs pooling, right next to the comment saying so.

This is worse than slow. `loadImg` inside `compositeMask` has no `.catch` — a rejected/throttled
image fails the whole tile (`done(err, tile)`), which is at least visible. But the tap-probe
helpers (`probeValues`, `probeMin`, `probeRange`, `index.html:1662-1667`) **do** swallow errors
into `null`, and `readClass`/`readMetric` treat `null` as "condition not met". A 503 from Luke
under self-inflicted load during a tap does not error loudly — it silently reads as "this is not a
matsutake spot." **The uncapped fan-out is a correctness bug wearing a performance costume.**

**Metsäkeskus WFS** (`avoin.metsakeskus.fi`) — already reviewed and fixed. `MK_PAR = 4`, LRU cell
cache, point-query fast path, failure cool-off. No further action needed.

**Nominatim** (`nominatim.openstreetmap.org`) — search is debounced 600 ms, aborts the previous
request on a new keystroke, and scopes by `viewbox`; "lähellä sinua" reverse-geocodes one name at a
time in sequence, capped at 3. This is inside Nominatim's usage policy (max 1 req/s, an identifying
`Referer`, which the browser sends automatically since `fetch()` cannot set a custom `User-Agent`).
No changes needed.

**Open-Meteo elevation** (`api.open-meteo.com/v1/elevation`) — one request per tap, bundling 4
points (`readSlope`, `index.html:1698-1717`). No API key; free tier is meant for non-commercial,
moderate volume. Two problems, not just one:

1. **It's an avoidable dependency.** The model already warps the MML 10 m DEM onto the 16 m grid
   for training/inference (`ml/ingest/build_dem16.py` → `ml/data/rasters/dem_16m.tif`, 84 MB, already on
   disk). A slope/aspect (or even a raw elevation) COG exported next to `prob_*.tif`/`cut_*.tif`,
   read the same way, would answer every tap with zero network calls and work with Metsäkeskus and
   Luke both blocked — which is the one thing not yet true for the result sheet today.
2. **It's inconsistent with the model it's supposedly describing.** Open-Meteo's elevation API
   serves Copernicus GLO-90 (~90 m). The baked model was trained and scored against the MML 10 m
   DEM. The slope/aspect shown in the tap sheet can genuinely disagree with what actually produced
   the color under the pin.

**GBIF / FinBIF (laji.fi)** — offline only, `ml/ingest/fetch_observations.py`, run by a developer, not a
visitor. Small result set (a few hundred records for one taxon). No throttling between pages
today; harmless at this volume, worth a courtesy `time.sleep()` between pages only if this script
is ever pointed at a much larger taxon.

**GTK WFS, FMI/Paituli, OSM PBF extract** — all offline-only, all already well-behaved: GTK pages
in parallel with retries and resumable per-page caching; FMI reads year-by-year with `/vsicurl/`;
the OSM extract is cached to disk once and skipped on every later run. Nothing to change.

**Basemap tiles** (OSM standard, OpenTopoMap, Esri) — ordinary Leaflet tile-layer usage, subject to
each provider's own tile policy. Normal for a low-traffic hobby app; flagging only so it's a known
quantity if traffic ever grows.

---

## Recommended changes, in order

1. **Give Luke WMS one real, shared concurrency budget.** ✅ `gate()` + `lukeGate` (`LUKE_PAR = 5`). Per-call pooling isn't enough — today
   the tile layer (0), the tap probes (0), and the nearby scan (3) each manage their own budget
   independently, so three independent unpooled/under-pooled paths can all be in flight at once
   against the same 6-connection cap. Replace the three call sites with one module-level queue
   (a `mapPool`-style limiter that all `loadImg` calls for `kartta.luke.fi` share, sized to the
   documented 6, leaving a little headroom) so the app can never open more connections to Luke than
   Luke itself says it allows, no matter how many tiles Leaflet decides to build at once.
2. ✅ **Fix `inspect()`'s fan-out**, once it shares the pool from #1 — 8 + 4 + (metrics × alt layers ×
   (1 + steps)) requests per tap, routed through the same limiter, so a tap can no longer touch off
   30 simultaneous requests.
3. ✅ **Stop asking Luke the same question twice per metric.** `readMetric` fires a dedicated
   pass/fail probe (`probeMin`/`probeRange` at `limit`) *and* a full bracket scan
   (`readBracket`, one probe per step) against the same layer and point. Derive the pass/fail
   boolean from the bracket result instead (only issue a separate request when the user's `limit`
   falls strictly between two fixed step values, which the bracket alone can't resolve) — cuts tap
   traffic by up to ~30%.
4. ✅ (code) **Bake slope/aspect and drop the Open-Meteo tap dependency.** Export a COG from
   `ml/data/rasters/dem_16m.tif` next to `prob_*.tif`/`cut_*.tif`, read it the same way. This
   removes a live external call from every tap, fixes the 10 m/90 m mismatch, and extends
   "works offline once cached" to the last part of the result sheet that doesn't have it yet.
5. ✅ **(Cheap, pairs with #1)** Consider a smaller `keepBuffer` on `SpotLayer` specifically — unlike
   a plain image tile, each of its tiles costs several WMS fetches, so pre-loading a ring of
   off-screen tiles is proportionally more expensive here than for an ordinary basemap.
6. ✅ **(Low priority, hygiene only)** Add a small delay between pages in `fetch_observations.py`'s
   GBIF/FinBIF loops if it's ever reused for a taxon with a much larger record count than
   matsutake's.

Items 1-3 are the ones worth doing first: they're the direct counterpart of the Metsäkeskus fixes
that already shipped, applied to the API the app actually hits far more often, and #1 in particular
is a correctness fix as much as a performance one.

## How it was done

One `gate(limit)` primitive replaced `mapPool`, and every service now has exactly one module-level
queue: `lukeGate` for every WMS image (`loadMask`) and `mkGate` inside `mkGet` for every
Metsäkeskus fetch, point queries included. `compositeMask` no longer takes a concurrency argument
at all — a caller can only say how its batch is *ranked*: `first` puts a tap or a "lähellä sinua"
scan ahead of speculative tile work, and `alive` lets the queue drop a tile Leaflet has already
thrown away instead of spending a slot on an image nobody will see. That last part, plus
`keepBuffer: 1`, is where the 435 → 269 drop in total requests comes from.

The tap's duplicate probe is gone by construction rather than by special-casing: `readBracket`'s
result already pins the value to an interval, `bracketVerdict` compares that interval with the
band the metric accepts, and only a limit sitting strictly between two fixed steps still needs its
own request. Exhaustively checked against the probe it replaces for every value 0–255 across
twelve metric shapes: identical answers, ~94 % of cases settled without the extra request. With
the shipped defaults every limit is on a step, so the extra request is never issued; the saving is
small in absolute terms (30 → 29 requests per tap) because the bracket probes, not the pass
probes, are the bulk of a tap.

`readSlope` now prefers a baked layer and keeps Open-Meteo only as the fallback. The baked layer is
elevation, not ready-made slope: it compresses far better, and the app derives slope with the same
central differences `ml/core/features.py` uses, so there is one definition of slope in the project
instead of two. `readBlockAt` / `readValueAt` are now the single way the app reads a baked
EPSG:3067 COG at a point, shared by the score, the cut layer and the terrain layer.
