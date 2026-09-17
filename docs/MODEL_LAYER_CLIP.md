# The model layer stopped at a straight line: a TM35 rectangle is not a lat/lon rectangle

A screenshot from Jämijärvi showed the model layer ending at a dead-straight north–south line
about 1,5 km west of the phone, with nothing drawn east of it — while the rule layer
("matsutake-tyypin metsä") carried on across the whole screen. This is what that was, how far it
reached, and what the fix is.

## It was not tile loading, a missing part, or the data

- **Not loading.** Reproduced in headless Chromium against local files with a 15 s wait: the same
  line, in the same place, every run.
- **Not a missing part.** Two kilometres east of the line, `prob_matsutake_16m_20.tif` has 45 % of
  its forest cells above the "best 7 %" threshold. The data was there all along.
- **Not the forest data.** Metsäkeskus and Luke have no edge here, and the cut (hakkuu) shading
  rides in the same layers, so it was blanked with everything else.

## What it was

Registering the screenshot against OpenStreetMap z13 tiles put the line at **lon 22,7094–22,7095**.
The NE corner of `prob_matsutake_16m_20.tif` (x = 282 912, y = 6 994 608 in EPSG:3067) reprojects
to **lon 22,70948**. Same number.

`georaster-layer-for-leaflet` derives the layer's lat/lon box from two corners:

```js
var f = projector.forward({x: xmin, y: ymin}),   // SW
    _ = projector.forward({x: xmax, y: ymax});   // NE
this._bounds = L.latLngBounds(L.latLng(f.y, f.x), L.latLng(_.y, _.x));
this.xMaxOfLayer = this._bounds.getEast();  …  options.bounds = this._bounds;
```

A rectangle in ETRS-TM35FIN is a **trapezoid** in lat/lon — 217 km west of the 27° central
meridian grid north tilts ~3,8° — so the box through the SW and NE corners is the one *inscribed*
in it. Everything beyond gets clipped twice over: `drawTile` skips samples outside
`xMinOfLayer…yMaxOfLayer`, and `options.bounds` stops Leaflet from creating those tiles at all.
Hence the straight line, cut mid-tile (painting stopped at column 195 of 256 in every tile), with
no tiles whatsoever further east.

## How much of the country it covered

Comparing, on a 500 m grid, where the nine parts hold data against where their boxes allowed
drawing:

| | |
|---|---|
| forest-land cells with a model value | 1 316 979 |
| never drawn | 58 199 — **4,4 %**, about **16 000 km²** |

Where:

| band | never drawn | what it is |
|---|---|---|
| lat 59,3–63,0 | lon 22,71–23,16 | ~24 km corridor from the south coast past Jämijärvi, Parkano and Ikaalinen |
| lat 62,8–66,5 | lon 22,11–22,71 | the same seam one row north: Kokkola–Kalajoki coast inland |
| lat 66,5–70,2 | lon 21,31–22,11 | Tornionjaakso and Muonio |
| lat ≈ 63,0 and ≈ 66,5, east of 27° | ~8–10 km tall stripes | the *row* seams: east of the central meridian the corner box clips in latitude instead |

Nothing is lost near 27° east: convergence goes to zero at the central meridian, so the
508 192 seam has no gap at all.

## The fix

`widenToProjection()` in `index.html` measures the box along each part's edges (64 steps per edge)
instead of across two corners, and writes it back into `_bounds`, `options.bounds` and
`xMinOfLayer…yMaxOfLayer` before the layer is added to the map.

Widening is safe. The sample-to-pixel mapping never goes through these numbers — `drawTile`
inverse-projects each sample and divides by the raster's own origin and pixel size — so they only
gate what is drawn. Where two parts' boxes now overlap, the part without data there still draws
nothing: its samples fall outside its raster and are skipped. There is no double-painting, because
the parts do not overlap in TM35.

## Verification

Headless Chromium, model layer on at "best 7 %", external tiles blocked. For every tile the layer
holds, its painted canvas pixels are counted and compared against what the part's own values say
should paint at each of the layer's 128 × 128 samples in that tile — so "expected" is measured
from the GeoTIFF, not assumed.

37 locations from Salo to Karesuvanto, every seam included. Painted samples, before → after:

| location | before | after | after ÷ expected |
|---|---|---|---|
| Jämijärvi (the screenshot) | 16 962 | 42 201 | 1,00 |
| corridor at 22,95° E | 0 (no tiles) | 6 486 | 0,97 |
| Parkano / Ikaalinen | 0 (no tiles) | 8 021 | 0,98 |
| Salo / Somero | 0 (no tiles) | 12 271 | 1,00 |
| Pori / Kokemäki | 0 (no tiles) | 1 703 | 0,90 |
| Kristiinankaupunki | 0 (no tiles) | 1 269 | 1,03 |
| Kauhava / Lapua | 0 (no tiles) | 3 478 | 0,94 |
| Kokkola inland | 0 (no tiles) | 864 | 0,98 |
| Kemijärvi (lat seam) | 4 975 | 23 228 | 1,26 |
| Salla (lat seam) | 36 | 4 160 | 1,36 |

After the fix no tile anywhere is blank, and no tile stops mid-way: the remaining scatter around
1,0 is the layer's own sampling grain (each sample paints a 2 × 2 px rect, and rect sizes differ
where a tile is only partly covered), not a clip. Tampere, Jyväskylä, Kuopio, Oulu, Kajaani,
Rovaniemi, Ivalo, Joensuu and the Helsinki region were unaffected either way, as expected — they
are nowhere near a seam.

Cost: none. A view at Jämijärvi, Jyväskylä or Oulu makes 3–4 range requests into the GeoTIFFs,
all to the part that actually holds the data — the parts whose widened box now reaches over a
neighbour do not fetch anything there — and the console stays clean.

`bboxToTM35()` — the other place where a box crosses projections, for the Metsäkeskus queries —
was checked and is correct: it transforms all four corners and takes the envelope, which
over-covers, which is the safe direction for a query.
