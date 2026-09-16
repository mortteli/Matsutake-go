# Network requests, per use case

What actually leaves the browser for nine common interactions. Everything here is read from
`index.html` — request counts, queue limits, debounces and zoom floors are the constants in that
file, named so they can be checked against it.

## Services

| Participant | Host | What is asked for |
|---|---|---|
| **Luke** | `kartta.luke.fi/geoserver/MVMI/wms` | `GetMap` PNG, one per condition, styled server-side with `SLD_BODY` so the answer is a 1-bit mask. Shared queue `lukeGate`, **5** in flight (`LUKE_PAR`, one under GeoServer's `x-concurrent-limit-user: 6`). |
| **MK** | `avoin.metsakeskus.fi/rajapinnat/v1/ows` | WFS `GetFeature` GeoJSON, `v1:stand` and `v1:forestusedeclaration`. Shared queue `mkGate`, **4** in flight (`MK_PAR`), 9 s timeout, only at zoom ≥ **11** (`MK_MINZOOM`). |
| **Static** | same origin (GitHub Pages) | `prob_meta.json`, `terrain_meta.json`, the vendored georaster scripts, and HTTP **range** requests into the 9+9 GeoTIFF parts under `data/matsutake/`. |
| **Nominatim** | `nominatim.openstreetmap.org` | `/search` for the box, `/reverse` for the names in "lähellä sinua". One request a second, never per keystroke. |
| **Open-Meteo** | `api.open-meteo.com/v1/elevation` | Slope, **fallback only** — used when no baked terrain layer is published. |
| **Basemap** | OSM / OpenTopoMap / ArcGIS | Ordinary raster tiles. |

Two properties hold across every diagram below:

- **One queue per service, shared by every call site.** Tiles, taps and the nearby scan all go
  through the same `gate`, so the number of open connections is a property of the app and not of
  whichever feature happens to be running.
- **A tap or a scan jumps the line** (`{first: true}`), and **a tile panned off screen is never
  requested at all** — `run` drops it with `DROPPED` at the head of the queue instead of spending
  a slot on an image nobody will see.

```mermaid
flowchart LR
  U([User]) --> App[index.html<br/>Leaflet + SpotLayer + GeoRasterLayer]
  App --> LQ[lukeGate · 5 in flight]
  App --> MQ[mkGate · 4 in flight]
  LQ --> LUKE[(Luke MVMI WMS<br/>kartta.luke.fi)]
  MQ --> MK[(Metsäkeskus WFS<br/>avoin.metsakeskus.fi)]
  App --> ST[(Static origin<br/>prob_meta.json · *.tif range reads)]
  App --> NOM[(Nominatim<br/>search + reverse)]
  App --> OM[(Open-Meteo elevation<br/>fallback only)]
  App --> BM[(Basemap tiles)]
```

---

## 1. Zoom and pan the matsutake map, model layer on

Per **new** tile: 5 Luke masks (`kasvupaikka`, `paatyyppi`, `ika`, `manty`, `kuusi` at matsutake's
defaults) plus range reads into the model raster. Metsäkeskus is fetched by **10 km cell**, not by
tile, so one WFS response serves many tiles and panning inside the same cells is free. The tile is
drawn with whatever harvest data is already in hand and handed back immediately — it never waits on
the ~1.5 MB cell download.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant App as SpotLayer / GeoRasterLayer
  participant LQ as lukeGate 5
  participant L as Luke WMS
  participant MQ as mkGate 4
  participant MK as Metsäkeskus WFS
  participant S as Static origin
  participant BM as Basemap

  U->>App: zoom / pan
  App->>BM: basemap tiles z/x/y, OSM / OpenTopoMap / ArcGIS

  loop each new tile, keepBuffer 1
    App->>LQ: 5 GetMap jobs, one SLD_BODY mask per condition
    LQ->>L: GetMap kasvupaikka, paatyyppi, ika, manty, kuusi
    L-->>App: 5 transparent PNGs, AND-composited on canvas
    alt zoom 11 or deeper, and hideCut on
      App->>App: mkFeaturesNow stand — cached cells only, never awaited
      App->>MQ: request missing 10 km cells in background
      MQ->>MK: GetFeature v1 stand, BBOX 10 km, propertyName trimmed
      MK-->>App: about 1.47 MB GeoJSON per cell
      App->>App: scheduleCutRedraw, debounced 400 ms
      App->>LQ: redraw re-issues the 5 masks per visible tile
    else shallower than zoom 11
      Note over App,MK: no Metsäkeskus request at all
    end
  end

  par model layer, same pan
    App->>S: HTTP Range reads into the 9 prob tif parts
    App->>S: HTTP Range reads into the 9 cut tif parts
    S-->>App: byte ranges, band 0 = score, band 1 = cut class
  end

  Note over App,LQ: tiles panned off are marked _dead and dropped<br/>at the head of the queue — DROPPED, no request sent
  Note over App,MK: 12 cells cached per kind, LRU · a failed cell<br/>is retried at most once per 30 s
```

**Costs:** 5 Luke requests per new tile. 1 WFS request per newly entered 10 km cell (≈ 1.47 MB),
capped at 12 cells per kind. Zero Metsäkeskus traffic below zoom 11. A landing cell costs one extra
debounced redraw of the visible tiles.

---

## 2. Change a forest setting (ikä, mäntyä, kuivahko, karukko, vähäkuusiset)

Every filter control funnels through `refreshSpots()`: clear the nearby list, then one debounced
`spots.redraw()`. Dragging a slider therefore costs **one** redraw, not one per input event. The
masks change, so all of them are re-fetched; the Metsäkeskus cells do not depend on the filter and
come straight from cache.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant App as Settings sheet
  participant LQ as lukeGate 5
  participant L as Luke WMS
  participant MK as Metsäkeskus WFS
  participant S as Static origin

  U->>App: drag Mäntyä vähintään, or toggle Myös karukkokangas
  App->>App: cfg updated, saved to localStorage, clearNearby
  App->>App: refreshSpots — debounce 350 ms, coalescing the whole drag
  App->>LQ: redraw, 5 new SLD masks per visible tile
  LQ->>L: GetMap with the new thresholds
  L-->>App: new masks
  Note over App,MK: no WFS request — stand cells are filter-independent<br/>and already in mkDone
  Note over App,S: no range reads — the model layer is not a rule layer<br/>and is untouched by these controls
```

**Costs:** 5 Luke requests × visible tiles, once per 350 ms of settling. Everything else: zero.
(The opacity slider is pure canvas — **no** requests at all.)

---

## 3. Change a hakkuu setting

Two different controls, two different shapes.

**3a — "Piilota hakatut" (`chkHideCut`)** subtracts cut stands from the rule mask and recolours the
model layer's second band. The recolour is in-memory; the mask redraw is the same debounced path as
use case 2.

**3b — "Hakkuut" overlay (`chkCutLayer`)** draws the polygons themselves, so it needs **both**
datasets — stands *and* declarations — for the whole view.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant App as Settings sheet
  participant LQ as lukeGate 5
  participant L as Luke WMS
  participant MQ as mkGate 4
  participant MK as Metsäkeskus WFS

  rect rgb(240,245,240)
  Note over U,MK: 3a — toggle Piilota hakatut
  U->>App: chkHideCut change
  App->>App: refreshSpots, debounce 350 ms
  App->>LQ: redraw, 5 masks per tile
  LQ->>L: GetMap
  alt zoom 11 or deeper, cells not cached
    App->>MQ: mkFeaturesNow stand, missing cells
    MQ->>MK: GetFeature v1 stand
  else cells cached, or shallower than zoom 11
    Note over App,MK: no request
  end
  App->>App: repaintProb — updateColors only, zero network
  end

  rect rgb(245,242,235)
  Note over U,MK: 3b — toggle the Hakkuut overlay
  U->>App: chkCutLayer change
  alt shallower than MK_MINZOOM 11
    App->>App: clearLayers, cutCells = null — no request
  else zoom 11 or deeper
    App->>MQ: mkFeatures mki and mkFeatures stand for the view bbox
    MQ->>MK: GetFeature v1 forestusedeclaration, per 10 km cell
    MQ->>MK: GetFeature v1 stand, per 10 km cell
    MK-->>App: about 0.55 MB and 1.47 MB per cell
    App->>App: draw on a canvas renderer, one shared popup
  end
  end

  U->>App: pan the map with the overlay on
  App->>App: cutRefresh on moveend
  alt same 10 km cell set as last time
    Note over App,MK: cutCells matches — nothing rebuilt, nothing fetched
  else new cells
    App->>MQ: only the cells not already cached
  end
```

**Costs:** 3a is a mask redraw and an in-memory recolour. 3b is up to 2 WFS requests per 10 km cell
in view, then nothing at all while panning inside the same cells.

---

## 4. Change the mushroom

The species picker drops the model layer entirely (`hideProb(true)` releases the rasters), rebuilds
the controls, and redraws with a different set of layers and SLDs. `renderProb()` always asks for
the species' `prob_meta.json` — matsutake is the only species with a model, so for the other four
this is a UI note and **no** request.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant App as Species modal
  participant LQ as lukeGate 5
  participant L as Luke WMS
  participant S as Static origin
  participant MK as Metsäkeskus WFS

  U->>App: pick 🌰 Herkkutatti
  App->>App: save, clearHelpers, clearNearby, hideProb with drop
  App->>App: applySpecies — title, controls, legend, info

  alt species has a model, e.g. back to 🍄 Matsutake
    App->>S: GET data/matsutake/prob_meta.json, no-cache
    S-->>App: quantiles, floor, max_pct, 9 file bounds, cut metadata
    opt model layer switched on
      App->>S: GET the vendor georaster bundles, once per session
      App->>S: Range reads, 9 prob tif headers plus 9 cut tif headers
      App->>S: Range reads per visible tile
    end
  else species has no model
    Note over App,S: no request — panel shows ei vielä tälle lajille
  end

  App->>LQ: spots.redraw with the new species' conditions
  LQ->>L: GetMap for the new layer set, e.g. kuusi and latvuspeitto
  L-->>App: new masks
  Note over App,MK: no WFS request — stand cells are species-independent<br/>and survive the switch in mkCache
```

**Costs:** 4–5 Luke requests per visible tile. One `prob_meta.json` when switching *to* matsutake.
The 9+9 raster headers only if the model layer is on. Metsäkeskus: nothing.

---

## 5. Open the app — Finland overview at zoom 5

Cold start at `setView([65.4, 26.5], 5)`. Zoom 5 is below `MK_MINZOOM`, so Metsäkeskus is never
touched: at that scale a 10 km cell is a few pixels and enumerating the cells of one z5 tile would
mean thousands of requests.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant B as Browser
  participant S as Static origin
  participant BM as Basemap
  participant LQ as lukeGate 5
  participant L as Luke WMS
  participant MK as Metsäkeskus WFS

  U->>B: open the app
  B->>S: index.html, one file — markup, CSS and all logic
  B->>S: manifest.webmanifest and icon.svg
  B->>S: leaflet.css and leaflet.js from vendor
  Note over B: localStorage restores species, filters, opacity,<br/>hideCut and the model toggle — no network

  par basemap
    B->>BM: OSM tiles for the country view
  and rule layer
    B->>LQ: 5 GetMap jobs per visible z5 tile
    LQ->>L: GetMap kasvupaikka, paatyyppi, ika, manty, kuusi
    L-->>B: masks, AND-composited, dilated 1 px
  and model panel
    B->>S: GET data/matsutake/prob_meta.json
    S-->>B: quantiles — needed for the slider stops even with the layer off
  end

  opt model layer was left on
    B->>S: vendor/georaster bundles
    B->>S: Range reads, 9 prob_*.tif + 9 cut_*.tif headers
    B->>S: Range reads per visible tile
  end

  Note over B,MK: zoom 5 is below MK_MINZOOM 11 — zero Metsäkeskus requests
  Note over B,S: data/terrain/terrain_meta.json is NOT fetched yet —<br/>it is lazy, first asked for by the first tap
```

**Costs:** the static bundle, basemap tiles, 5 Luke requests per visible tile, one
`prob_meta.json`. No Metsäkeskus, no terrain, no geocoder.

---

## 6. Change the matsutake "best %" slider

The rasters already hold every score; the slider only moves the threshold the colour function
compares against. So this is a **pure client-side repaint** — the one interaction in the app that
touches the network not at all.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant App as Model panel
  participant G as GeoRasterLayer
  participant S as Static origin
  participant L as Luke WMS

  U->>App: drag Näytä parhaat — stops 0,25 to 15 percent
  App->>App: state.prob.pct, localStorage save, label repaint on every input
  App->>App: debounce 150 ms
  App->>G: updateColors probColorFn
  G->>G: probThreshold from the quantiles already in prob.meta<br/>recolour cached pixel values in place
  G-->>U: new colours
  Note over App,S: no new range reads — the scores were fetched once<br/>and the threshold is applied to values in memory
  Note over App,L: no GetMap — the rule layer is a separate layer<br/>and is not affected by the model threshold
```

**Costs:** zero requests.

---

## 7. Search for a place

Opening the 🔍 panel does two unrelated things. The **nearby scan** runs immediately and is by far
the most expensive single action in the app: five *full-size* Luke reads, 1563 × 1563 px each
(≈ 190 KB), covering a 50 km box. Typing is what talks to Nominatim, and only after a 600 ms
debounce — its usage policy forbids per-keystroke autocomplete.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant App as Search panel
  participant LQ as lukeGate 5
  participant L as Luke WMS
  participant MQ as mkGate 4
  participant MK as Metsäkeskus WFS
  participant N as Nominatim

  U->>App: tap 🔍
  App->>App: nearbyAnchor — GPS fix if already granted, otherwise map centre
  alt view wider than 150 km, or outside the species' range
    Note over App,L: no scan — the panel asks the user to zoom in
  else
    App->>LQ: compositeMask, first = true, jumps ahead of tile work
    LQ->>L: 5 GetMap, 1563 x 1563 px each, about 190 KB
    L-->>App: masks → close by 1 cell → label patches → rank
    loop candidates, max 40 checks, until 3 picks
      App->>MQ: mkAt stand, 2 m box, first = true
      MQ->>MK: GetFeature v1 stand, count 10 — a few kB
      Note over App,MK: skipped entirely where the tile layer<br/>already loaded that 10 km cell
    end
    App-->>U: three rows, drawn before any name exists
    loop up to 3 spots, serialised
      App->>N: GET /reverse, zoom 14
      N-->>App: village / town — row repainted
      App->>App: wait 1100 ms · Nominatim allows one request a second
    end
  end

  U->>App: type "Ylöjärvi Teivo"
  App->>App: nearby list cleared on the keystroke, then debounce 600 ms
  alt the query parses as coordinates, WGS84 or EPSG 3067
    Note over App,N: no request — parsed locally
  else
    App->>N: abort the previous request, then GET /search limit 8, countrycodes fi, viewbox
    N-->>App: up to 8 hits
  end

  U->>App: pick a hit
  App->>App: flyTo or flyToBounds, maxZoom 16
  Note over App,L: the fly is an ordinary pan — see use case 1<br/>5 masks per new tile, WFS cells above zoom 11, basemap tiles
  Note over App,L: no automatic inspect — searching means looking at the map
```

**Costs:** 5 large Luke reads per scan, up to 40 tiny WFS point queries, up to 3 Nominatim reverse
lookups spaced 1.1 s. One `/search` per 600 ms of settled typing. A scan re-runs on pan only after
the view has moved 5 km (`NEARBY_REANCHOR_M`).

---

## 8. Tap a forest for info

The heaviest *burst*, and deliberately so: every probe is a 3 × 3 px `GetMap` that costs the server
almost nothing, they all jump the queue ahead of tile work, and the same question about the same
point is asked exactly once per tap (`probeMemo`, dropped when the next tap starts).

For matsutake: 8 site-class probes + 4 ground-type probes + 7 age steps + 5 pine steps + 5 spruce
steps ≈ **29 probes**, plus at most one extra per metric when the user's own limit falls strictly
between two fixed steps — every other case is already settled by the bracket that was paid for.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant App as inspect
  participant LQ as lukeGate 5, tap first
  participant L as Luke WMS
  participant MQ as mkGate 4, tap first
  participant MK as Metsäkeskus WFS
  participant S as Static origin
  participant OM as Open-Meteo

  U->>App: tap the map
  App->>App: probeMemo cleared, sheet opens on Tutkitaan paikkaa

  par site and ground class
    App->>LQ: readClass kasvupaikka, 8 single-value probes
    App->>LQ: readClass paatyyppi, 4 single-value probes
    LQ->>L: GetMap 3x3 px, SLD values mask
  and metrics, matsutake
    App->>LQ: readBracket ika, 7 threshold probes
    App->>LQ: readBracket manty, 5 threshold probes
    App->>LQ: readBracket kuusi, 5 threshold probes
    LQ->>L: GetMap 3x3 px, SLD intervals mask
    opt the user's limit sits between two steps
      App->>LQ: one extra pass/fail probe for that metric
    end
  and slope
    App->>S: GET data/terrain/terrain_meta.json, once per session
    alt a terrain layer is published
      S-->>App: bounds of 9 parts
      App->>S: Range read, 3x3 block from the one part the tap lands in
    else no terrain layer, null cached permanently
      App->>OM: GET /v1/elevation, 4 points 100 m apart, 6 s timeout
      OM-->>App: Copernicus GLO-90 elevations
    end
  and model score, if the layer is on
    App->>S: Range read at the point in the prob tif
  and harvest
    App->>MQ: mkAt stand and mkAt mki, 2 m box each
    MQ->>MK: two GetFeature calls, count 10 — a few kB
    Note over App,MK: zero requests where the enclosing 10 km cell<br/>is already in mkDone from the tile layer
    opt both empty
      App->>S: readCutBaked — Range read in the cut tif, shown as stale
    end
  end

  App-->>U: verdict, check rows, harvest warning, navigation link
  Note over App,L: same point asked twice in one tap = one request<br/>a failed probe stays failed for that tap, never retried per caller
```

**Costs:** ≈ 29–32 tiny Luke probes, 0–2 tiny WFS queries, 1 static metadata fetch (once per
session) plus a range read — or exactly one Open-Meteo request where no terrain layer is published.

---

## 9. Press 📍 and walk with the map following

The GPS itself costs the app nothing: `watchPosition` is a browser API, and whatever network
geolocation the OS does behind it is not a request this app makes or can see. Everything below is
what the *fixes* set off.

Two things carry the cost. The **first** fix is a `setView` to at least zoom 13 — from the country
view that is a whole screen of new tiles, and because 13 is past `MK_MINZOOM`, it is usually the
moment the session makes its first Metsäkeskus request at all. **Every** fix after that repaints an
open, empty search panel, and the watch fires about once a second.

That repaint is the trap the scan keying exists to close. A scan is identified by the place it is
scanning — `state.species | cfg | lat.toFixed(2) | lon.toFixed(2) | radius` — never by the repaint
counter, so ticks that land on the same cell of that grid — 0,01° is about 1,1 km north-south
and 0,5 km east-west at 63° N — ride the scan already in flight. Keyed on the
counter instead, a phone with a live fix started a fresh 5-read scan every second and the list sat
on "Etsitään…" for as long as the panel stayed open.

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant G as Browser geolocation
  participant App as Map and search panel
  participant BM as Basemap
  participant LQ as lukeGate 5
  participant L as Luke WMS
  participant MQ as mkGate 4
  participant MK as Metsäkeskus WFS
  participant N as Nominatim

  U->>App: tap 📍, or the "Näytä omalta sijainnilta" row
  App->>G: watchPosition, highAccuracy, maximumAge 3 s, timeout 20 s
  Note over App,G: no app request — the OS may use its own network,<br/>which this app neither makes nor sees

  G-->>App: first fix
  App->>App: gpsUpdate — dot and accuracy circle, both client-side
  App->>App: firstFix, setView to zoom 13 or deeper
  par the jump loads a screen
    App->>BM: basemap tiles at the new zoom
  and
    App->>LQ: 5 GetMap per new tile
    LQ->>L: GetMap kasvupaikka, paatyyppi, ika, manty, kuusi
  and first time past MK_MINZOOM 11
    App->>MQ: mkFeaturesNow stand, the cells under the view
    MQ->>MK: GetFeature v1 stand, per 10 km cell
    Note over App,MK: usually the session's first Metsäkeskus request
  end

  loop every fix, about once a second while walking
    G-->>App: position
    App->>App: marker and circle moved, no network
    alt following
      App->>App: panTo — new tiles only where you actually cross one
      App->>BM: tiles for newly exposed rows or columns
      App->>LQ: 5 GetMap for each genuinely new tile
      opt the Hakkuut overlay is on
        App->>App: cutRefresh on moveend
        Note over App,MK: same 10 km cell set as last time — nothing fetched
      end
    else not following, after a drag or a second 📍 tap
      Note over App,BM: the watch keeps running on purpose — marker stays live,<br/>lastFix stays fresh, no re-acquire when the panel reopens
    end

    opt the search panel is open and empty
      App->>App: renderNearby, anchored on the fix
      alt same nearbyKey — still inside the same 0,01 degree square
        Note over App,L: rides the scan already in flight, or repaints the<br/>cached list with distances recomputed from the new fix
      else walked into a new square
        App->>LQ: compositeMask, first = true
        LQ->>L: 5 GetMap, 1563 x 1563 px each
        App->>MQ: up to 40 mkAt stand point checks, until 3 picks
        MQ->>MK: GetFeature v1 stand, count 10
        App->>N: up to 3 GET /reverse, spaced 1100 ms
      end
    end
  end

  U->>App: drag the map
  App->>App: dragstart stops following, watch untouched
  Note over U,N: a denied or failed fix calls stopGps and re-renders the<br/>open list against the map centre — it never hangs waiting
```

**Costs:** the first fix is the expensive one — a full screen of tiles at zoom 13 plus the first
WFS cells. After that, walking costs 5 Luke requests per tile you actually cross into, and the
once-a-second repaint costs **nothing** unless you leave the 0,01° square the current scan was
keyed to.
