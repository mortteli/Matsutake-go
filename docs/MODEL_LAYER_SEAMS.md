# The model layer broke at every tile seam: a Mercator tile is not a TM35 rectangle

Screenshots from Jämijärvi showed the baked model layer clipping along the map's tile borders:
a hillside drawn in one tile did not meet the same hillside in the next, and the break moved when
the zoom changed. This is the same family of bug as [MODEL_LAYER_CLIP.md](MODEL_LAYER_CLIP.md) —
a TM35 rectangle is not a lat/lon rectangle — one level down, in how a tile is sampled rather
than in how the layer's box is measured.

## What it was

`georaster-layer-for-leaflet` samples a tile like this (`drawTile` → `getRasters`):

```js
const f = c(0, 0), d = c(numberOfSamplesDown, numberOfSamplesAcross);   // two corners, inverse-projected
georaster.getValues({ left: f.x, top: f.y, right: d.x, bottom: d.y, width, height });
…
values = sampledRaster.map(band => band[sampleRow][sampleColumn]);      // stretched linearly over the tile
```

One **rectangle** of raster per tile, taken between the tile's north-west and south-east corners,
then spread evenly across the tile. That is right only when the raster's grid runs the same way as
the map's. Ours does not: a Web Mercator tile is a rotated quadrilateral in ETRS-TM35FIN, turned
by the grid convergence, which reaches nearly 4° at the western edge of the country. No rectangle
is its footprint.

The library draws one anyway, unturned. The error is zero in the middle of a tile and grows
outwards, and since every tile re-centres its own error, the picture **jumps by twice that much
across a seam** — which is exactly what a shape breaking along a tile border looks like. The
amount scales with the tile's size on the ground, so it changes at every zoom level.

## How far off it was

Headless Chromium, model layer on, external tiles blocked, at Jämijärvi (61,82° N 22,72° E). For
every screen pixel the reference value is read straight from the GeoTIFF — pixel → lat/lon →
`toTM35` → raster pixel — and compared with what the layer actually painted there.

**Where the drawing sits.** Best-matching shift per 96 × 96 px block, searched over ±12 px, ties
going to no shift. Every zoom ran into the search limit, so these are floors, not the worst of it:

| zoom | blocks displaced | shift | at this scale |
|---|---|---|---|
| z12 | 62 / 64 | ±12 px or more | ≥ 220 m |
| z14 | 61 / 64 | ±12 px or more | ≥ 55 m |
| z16 | 60 / 64 | ±12 px or more | ≥ 14 m |

**Where the error is.** Share of pixels showing the wrong value, by distance to the nearest tile
seam — flat would mean "grain", a slope means "seam":

| zoom | < 16 px from a seam | < 48 | < 96 | tile centres |
|---|---|---|---|---|
| z12 | 53,2 % | 50,8 % | 42,7 % | 19,4 % |
| z14 | 21,6 % | 17,2 % | 16,2 % | 7,2 % |
| z16 | 11,6 % | 10,6 % | 6,6 % | 2,5 % |

**Does the tile grid show through?** Draw the same view twice, once with 256 px tiles and once
with 512 px ones, sample spacing held at 2 screen px in both, and compare the two pictures pixel
for pixel. A correct layer cannot tell the difference:

| | z12 | z14 | z16 |
|---|---|---|---|
| pixels that differ | 31,7 % | 16,7 % | 12,0 % |

The tap probe was right all along — it goes through `toTM35` — so the map was also disagreeing
with its own readout by up to a tile's worth of error.

## The fix

`sampleExactly()` in `index.html` puts a `getRasters` of our own on each part's layer, and the
library's `drawTile` then paints the grid it is handed — which is what it believes it is painting
anyway.

- **Every sample centre is projected.** Screen point → lat/lon → `toTM35` → the raster pixel
  actually under it. The same function the tap probe uses, so the drawn pixel and the tapped value
  are now the same pixel. Web Mercator is separable, so a tile costs `across + down`
  unprojections rather than `across × down`; `tm35Row()` splits the TM35 series so its
  trigonometry runs once per row of samples. `toTM35` is that function for one point and returns
  bit-identical results (checked over 20 000 random points in Finland).
- **One overview level per part per zoom.** The coarsest level still finer than a sample, measured
  from the map scale and the layer's resolution — never from how many samples this tile happens to
  hold, since a tile clipping the corner of a part is handed one or two samples for the whole of
  it. Two tiles side by side reading different levels would show two generalisations of the same
  forest, and that seam would be as plain as the one this replaces.
- **The window is read in the level's own pixels**, so the pixel a sample lands on is `full >> k`
  whichever tile is asking. Nothing about the read depends on the tile.
- **Anything unexpected falls back** to the library's own sampling — a part with no overviews, a
  projection this does not cover — drawing a slightly displaced map rather than none at all.

## Verification

Same harness, after:

| | z12 | z14 | z16 |
|---|---|---|---|
| blocks displaced | 8 / 64, ±1 px | 16 / 64, ±1 px | see below |
| wrong pixels at a seam / at tile centres | 19,6 % / 9,7 % | 4,8 % / 4,4 % | 6,0 % / 2,5 % |
| 256 px tiles against 512 px tiles | **0,00 %** | 3,97 % | 4,27 % |

The z12 picture is now **exactly** the same drawing wherever the seams fall, at Jämijärvi
(0,00 %) and at Ilomantsi on the other side of the central meridian (0,00 %), where the
convergence tilts the other way. The zoom ladder is clean and every part agrees: z6–z7 → overview
6, z8 → 5, z9 → 4, z10 → 3, z11 → 2, z12 → 1, z13 and in → full resolution.

What is left at z14 and closer is the library's own grain, not a displacement. Zoomed in past the
raster's resolution it snaps each tile's inner extent to the raster grid, so the *cells* — never
their values — still start a fraction of a pixel differently in each tile. A cell is about one
raster pixel there, so the wobble is at most half of one, and the block matcher's ±6 px readings
at z16 are it running out of signal: shifting a block of 14 px cells barely changes the match
(5,8 % wrong at no shift against 3,7 % at its best guess), so it picks an arbitrary winner.

Cost: a wash. Whole-screen pan at Jämijärvi, warm, four pans averaged:

| | z11 | z13 | CPU per pan (z11) |
|---|---|---|---|
| before | 340 ms | 430 ms | 546 ms |
| after | 375 ms | 250 ms | 513 ms |

The z11 pan makes 6 range requests / 960 kB where the old sampling made 9 / 1152 kB: the window
read is the tile's actual footprint, at the level it is drawn at, rather than a rectangle at
whatever level geotiff.js picked plus a resample down to the sample grid.

## Not fixed here, on purpose

Zooming out still thins the map out: the overviews are built with `OVERVIEW_RESAMPLING=AVERAGE`
(`ml/export_app.py`), so a lone excellent 16 m cell is averaged with its neighbours and can fall
under the threshold before it is drawn. That is a property of the baked files, not of the
drawing — changing it means re-baking the parts with a maximum-preserving resampling and deciding
whether "best 5 % of forest land" should mean the best cell or the average cell of a block.
