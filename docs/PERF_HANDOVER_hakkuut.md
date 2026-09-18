# Handover: the harvest layers are too slow

Reported from the field: with the 🪵 **Hakkuut** overlay on, the map takes **~2 minutes** to become
usable and stays unresponsive while it loads. Reproduced around Sasi (61.5914, 23.3742) at roughly
z15.

**Answer to "memory leak or sheer volume?" — both, and a third thing that is worse than either.**
There is a real unbounded cache (§3), the payload is genuinely large (§1), but the dominant cost is
that the overlay builds thousands of SVG elements in the DOM and rebuilds them on every pan (§2),
while the mushroom layer sits blocked on the network waiting for the same data (§4).

Everything below was measured against the live Metsäkeskus WFS on 2026-09-14, not estimated.

---

## The measurements

One 10 km cell — the unit `mkFeatures()` fetches — around Sasi:

| dataset | features | payload | properties | geometry | vertices |
|---|---|---|---|---|---|
| `v1:stand` (A0/S0/T1/T2) | 811 | **2.00 MB** | 0.81 MB, 40 fields each | 1.36 MB | 47,944 |
| `v1:forestusedeclaration` (regen, ≥2021) | 433 | **0.90 MB** | 0.51 MB, 42 fields each | 0.50 MB | 17,822 |
| **per cell** | **1,244** | **2.90 MB** | 1.32 MB | 1.86 MB | **65,766** |

A z15 viewport straddles 1–4 of these cells, so a single screen can pull **3–12 MB** and put
**1,200–5,000 polygons** on the map. Coordinates come back with **8 decimal places** — about 1 mm,
on a 16 m grid.

The app uses **4 of the 40** stand fields (`DEVELOPMENTCLASS`, `MEANAGE`, `MEANHEIGHT`,
`TREESTANDDATE`) and **3 of the 42** declaration fields (`DECLARATIONARRIVALDATE`, `AREA`,
`CUTTINGPURPOSE`). The tile mask needs no properties at all.

---

## 1. The server will send less if asked — `propertyName` works

Verified against the live endpoint:

| request | size | change |
|---|---|---|
| `v1:stand`, everything (current) | 2.00 MB | — |
| `propertyName=GEOMETRY,DEVELOPMENTCLASS,MEANAGE,MEANHEIGHT,TREESTANDDATE` | 1.47 MB | −27 % |
| `propertyName=GEOMETRY` | 1.39 MB | −31 % |

**Do:** add a `propertyName` to `MK_KIND` in `index.html:566` and pass it in `mkGet()`
(`index.html:572`). The tile-mask path wants geometry only; the tap readout wants the handful of
fields `harvestHTML()` prints.

> Careful: this WFS silently ignores some parameters. `where` and `bbox` are ignored by the *fiona*
> client in `ml/ingest/fetch_harvests.py` (see its `SETS` comment) — that is a different layer, but the
> habit of verifying rather than trusting applies here too. `propertyName` was confirmed working by
> inspecting the returned keys, and any change to it must be re-verified the same way.

Worth ~28 % of the bytes. Necessary, not sufficient — do §2 as well.

---

## 2. The overlay puts 1,244 SVG paths in the DOM, and rebuilds them on every pan

`cutRefresh()` (`index.html:2365`) is bound to `moveend` (`index.html:2394`) and does:

```js
cutLayer.clearLayers();
...
cutLayer.addData({ type: "FeatureCollection", features: lists[0].concat(lists[1]) });
```

`L.geoJSON` creates **one `L.Polygon` per feature, each an SVG `<path>`, each with a bound popup**
(`cutPopup`, `index.html:2356`). That is ~1,244 elements and ~65,766 path vertices per cell,
destroyed and recreated on every map move. On a phone this is the two minutes.

### The fix: draw the overlay from the raster that already exists

PR #7 publishes `data/matsutake/cut_*.tif` — a national 16 m raster of exactly this information
(`0` none, `1` declared, `2` cut), already aligned to the model parts and already read by the app
for the model layer. **The overlay does not need vectors at all.**

Replace the `L.geoJSON` overlay with a `GeoRasterLayer` over those COGs, coloured by value:

- zero WFS requests for the overlay,
- zero DOM paths,
- reads only the byte ranges in view, like the model layer already does,
- works offline once cached.

`showProb()` (`index.html:~1240`) already loads `prob.cut` via `parseGeoraster`; the overlay can
reuse those same rasters rather than loading them twice — check `prob.cut` first and only
`parseGeoraster` if empty.

**Ordering note:** this depends on PR #7 being merged, since `main` currently has only the live
correction and no `cut` section in `prob_meta.json`. Until then, the fallback is
`L.geoJSON(..., { renderer: L.canvas() })`, which draws to one canvas instead of thousands of
elements — much cheaper, though still paying the download.

Keep the popups working by hit-testing on click against the cached features (or, with the raster,
just reuse the existing `readHarvest()` tap path — it already returns everything the popup shows).

---

## 3. `mkCache` never evicts — this is the leak

```js
const mkCache = new Map();     // index.html:565  "kind:gx:gy" -> Promise<Feature[]>
```

Every 10 km cell ever visited is retained for the life of the page, holding its parsed GeoJSON.
At ~2.9 MB of JSON per cell — several times that as live JS objects — panning across a region
accumulates hundreds of megabytes. `featureBox()` additionally pins a `_bb` array onto every
feature object, so nothing is collectable while the cache holds the cell.

**Do:** make it an LRU capped at ~12 cells (roughly a 30 × 30 km working set). On eviction just
drop the entry; the `_bb` caches go with it. Do not cache failures — that behaviour is already
correct in `mkCell()` (`index.html:587`) and should stay.

---

## 4. The mushroom layer blocks on the harvest download

`SpotLayer.createTile` (`index.html:1130`):

```js
const cut = state.hideCut ? mkFeatures("stand", bboxToTM35(bbox)).catch(() => []) : Promise.resolve([]);
cut.then(feats => compositeMask(...)).then(off => { ... });
```

Every tile waits for a 1.4–2 MB fetch before it draws **anything**. The Luke WMS masks could have
been composited and shown in the meantime. This is why the map feels frozen rather than merely
slow.

**Do:** composite and hand back the tile immediately with whatever cut data is already cached
(`[]` if none), and redraw when the fetch resolves. A `GridLayer` tile can be repainted in place —
keep the tile canvas and its context, and when the cell arrives, redraw those tiles whose cell it
was. Simplest correct version: if the cell is not yet cached, draw without the subtraction now and
call `spots.redraw()` once the cell lands (debounced, so 4 cells arriving do not cause 4 redraws).

---

## 5. A tap costs 2.9 MB

`readHarvest()` (`index.html:1438`) builds a **±1 m** box and hands it to `mkFeatures()`, which
rounds up to the enclosing 10 km cell. If that cell is not already cached, one tap on the map
downloads 2.9 MB to answer a question about one point.

`spotIsCut()` (`index.html:2069`) does the same, and "lähellä sinua" can call it up to
`NEARBY_CUT_CHECKS` (40) times across candidates that may sit in many different cells.

**Do:** give both a direct point query that does not go through the cell cache — the same CQL
`BBOX` but with the actual ±1 m box and `count=10`. That is a few kilobytes. Keep the cell cache
for the tile mask, where whole-cell fetching genuinely pays off; use it opportunistically on tap
(if the cell happens to be cached, answer from it and skip the request).

---

## Suggested order

1. **§4** — biggest perceived win, smallest change: stop blocking tiles on the network.
2. **§5** — makes tapping and "lähellä sinua" cheap; small, self-contained.
3. **§2** — the actual fix for the overlay; do the raster version if PR #7 has merged, the
   `L.canvas()` version if not.
4. **§1** — `propertyName` trimming; mechanical, ~28 % of bytes.
5. **§3** — LRU cap; prevents the slow bloat on a long session.

§1 and §3 are worth doing even after §2, because the tile mask (§4) still fetches polygons.

---

## Verification

Do not accept "feels faster". Measure:

1. **Repro first.** Load `mortteli.github.io/Matsutake-go` at 61.5914, 23.3742, z15, 🪵 on, and
   record DevTools → Network total bytes and Performance total blocking time. That is the baseline.
2. **Bytes per screen.** After §1, one screen at z15 should transfer well under half of today's
   3–12 MB.
3. **DOM node count.** `document.querySelectorAll("#map path").length` — today this reaches into
   the thousands with the overlay on. After §2 it should be near zero (raster) or unchanged-but-
   -cheap (canvas renderer draws no per-feature elements).
4. **First paint of the mushroom layer.** After §4, coloured tiles must appear before the harvest
   fetch resolves. Throttle to "Slow 4G" in DevTools and watch the order.
5. **Memory.** Pan across ~10 provinces with the overlay on, then take a heap snapshot. After §3,
   retained size must plateau rather than grow monotonically.
6. **Correctness must not regress.** Re-run the checks that already exist for this feature:
   - the reported spot 61.5914388, 23.3742114 must still read "Kuvio on hakattu" with the T1
     seedling stand and its date;
   - the 45 y pine control ~230 m south (`stand.27724126`) must *not* be called harvested;
   - with Metsäkeskus blocked in DevTools the map must still render normally and never blank.
7. **Mobile.** The report came from a phone. Test at 390 px wide with network throttling, not on a
   desktop.

---

## Context an agent will want

- The correction exists in two forms on purpose. **Live WFS** (always current, used by the rule
  mask, the tap readout and "lähellä sinua") and the **baked raster** (published with the map, used
  by the model layer, and the right source for the overlay). On tap the live answer always wins;
  the raster is the offline fallback and says so.
- `2` means the stand register says open ground or seedling — a **fact**, from harvester telemetry.
  `1` means a regeneration felling was **declared** but is unconfirmed; 36 % of such declarations
  sit on forest that is still standing, which is why `1` is never treated as `2` and never removes
  anything. Do not "simplify" these into one value while optimising.
- `ml/ingest/fetch_harvests.py` regenerates the raster. It takes ~45 min for the whole country and needs
  ~20 GB of transient disk. Nothing in this perf work should require re-running it.
- Background on the whole feature: `README.md` → "Hakatut kuviot".
