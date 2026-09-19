import { R3857 } from "./constants.js";
import { bboxToTM35 } from "./geo.js";
import { map } from "./maplayer.js";
import { rasterLevels, readAtLevel } from "./problayer.js";
import { terrain, terrainPart, terrainReady } from "./terrain.js";
import { toast } from "./ui.js";

/* ================= rinnevarjostus (hillshade) =================
   A quick 3D read of the elevation layer: the same baked MML DEM terrain.js already reads for a
   tap's slope, shaded from a fixed sun so hills and eskers (harjut) stand out at a glance without
   having to read the raw ruudukko. An Aputasot toggle like Hakkuut — off by default, never
   persisted — and, like the model layer's remote fallback, quietly unavailable (with a toast)
   where no terrain layer has been published for the site.

   Shaded on a small per-tile canvas rather than through GeoRasterLayer: hillshade needs each
   pixel's *neighbours* to get a slope, and GeoRasterLayer's pixelValuesToColorFn only ever sees
   the one pixel it is colouring. rasterLevels/readAtLevel (problayer.js) are reused as-is — they
   read one overview window of a georaster and hand it back by band, independent of what the
   raster holds — so this is the same COG read path the model layer uses, pointed at the DEM. */

const RES = 96;                 // shading samples per tile edge
const SUN_AZIMUTH_DEG = 315;    // classic cartographic light: from the north-west
const SUN_ALTITUDE_DEG = 45;
const MAX_ALPHA = 0.55;
const CONTRAST = 3.2;           // unit-hillshade deviation from flat -> opacity

const ALT = SUN_ALTITUDE_DEG * Math.PI / 180;
const AZ = SUN_AZIMUTH_DEG * Math.PI / 180;
const FLAT = Math.sin(ALT);     // hillshade of a level cell — the overlay's transparent point

/* Lambertian hillshade: N . L for the surface normal N = (-gxEast, -gyNorth, 1) (normalised) and
   the unit vector L pointing toward the sun, azimuth measured clockwise from north. Written this
   way — rather than through an intermediate slope/aspect pair and atan2, as GDAL's DEMProcessing
   does — there is no aspect-quadrant sign convention to get wrong: an atan2(dy, -dx)-style
   aspect put a NW-facing flank under a NW sun 90 degrees out of phase with this and left the
   whole ridge reading as flat. */
function hillshadeUnit(gxEast, gyNorth) {
  const num = Math.sin(ALT) - gxEast * Math.cos(ALT) * Math.sin(AZ) - gyNorth * Math.cos(ALT) * Math.cos(AZ);
  return Math.max(0, num / Math.sqrt(1 + gxEast * gxEast + gyNorth * gyNorth));
}

/* One tile's shading, sampled on a RES x RES grid read straight off the DEM's own axis-aligned
   box. The overlay only has to look right, not survive a measurement — unlike the model layer's
   widenToProjection/sampleExactly, a rotated TM35 tile is not worth correcting for a decoration. */
async function hillshadeGrid(gr, tb) {
  const cell = gr.pixelWidth;
  const toCol = x => (x - gr.xmin) / cell, toRow = y => (gr.ymax - y) / gr.pixelHeight;
  let left = Math.floor(toCol(tb.xmin)) - 1, right = Math.ceil(toCol(tb.xmax)) + 1;
  let top = Math.floor(toRow(tb.ymax)) - 1, bottom = Math.ceil(toRow(tb.ymin)) + 1;
  left = Math.max(0, left); top = Math.max(0, top);
  right = Math.min(gr.width, right); bottom = Math.min(gr.height, bottom);
  if (right - left < 3 || bottom - top < 3) return null;   // sea, or off this part entirely

  const levels = await rasterLevels(gr);
  let k = Math.max(0, Math.floor(Math.log2(Math.max((right - left) / RES, (bottom - top) / RES, 1))));
  while (k > 0 && !levels[k]) k--;
  const step = 1 << k;
  const win = {
    left: left >> k, top: top >> k,
    right: Math.min((right >> k) + 1, levels[k] ? levels[k].getWidth() : right),
    bottom: Math.min((bottom >> k) + 1, levels[k] ? levels[k].getHeight() : bottom),
  };
  const [band] = await readAtLevel(gr, k, win);
  // meta.nodata/scale, the same fields readSlopeBaked trusts — not gr.noDataValue, which the
  // georaster parse does not reliably carry for these COGs
  const nodata = terrain.meta.nodata, scale = terrain.meta.scale || 0.1;
  const at = (r, c) => {
    if (r < top || r >= bottom || c < left || c >= right) return NaN;
    const v = band.at(r, c);
    return (v == null || v === nodata) ? NaN : v * scale;
  };

  const out = new Float32Array(RES * RES);
  for (let r = 0; r < RES; r++) {
    const y = tb.ymax - (r + 0.5) / RES * (tb.ymax - tb.ymin);
    const row = Math.round(toRow(y));
    for (let c = 0; c < RES; c++) {
      const x = tb.xmin + (c + 0.5) / RES * (tb.xmax - tb.xmin);
      const col = Math.round(toCol(x));
      const zW = at(row, col - step), zE = at(row, col + step);
      const zN = at(row - step, col), zS = at(row + step, col);
      const i = r * RES + c;
      if (!isFinite(zW) || !isFinite(zE) || !isFinite(zN) || !isFinite(zS)) { out[i] = NaN; continue; }
      out[i] = hillshadeUnit((zE - zW) / (2 * cell * step), (zN - zS) / (2 * cell * step));
    }
  }
  return out;
}

// unit hillshade -> white (sunlit) or black (shadow) at an alpha that grows with how far the
// slope departs from flat, so level ground — a bog, a lake — stays untinted
function paint(vals, ctx) {
  const img = ctx.createImageData(RES, RES);
  for (let i = 0; i < vals.length; i++) {
    const o = i * 4, v = vals[i];
    if (!isFinite(v)) { img.data[o + 3] = 0; continue; }
    const diff = v - FLAT, a = Math.min(1, Math.abs(diff) * CONTRAST) * MAX_ALPHA;
    const c = diff > 0 ? 255 : 0;
    img.data[o] = c; img.data[o + 1] = c; img.data[o + 2] = c; img.data[o + 3] = Math.round(a * 255);
  }
  ctx.putImageData(img, 0, 0);
}

export const HillshadeLayer = L.GridLayer.extend({
  initialize(options) {
    L.GridLayer.prototype.initialize.call(this, options);
    this.on("tileunload", e => { e.tile._dead = true; });
  },
  createTile(coords, done) {
    const tile = document.createElement("canvas");
    const size = this.getTileSize();
    tile.width = size.x; tile.height = size.y;
    const meta = terrain.meta;
    if (!meta) { setTimeout(() => done(null, tile), 0); return tile; }

    const n = Math.pow(2, coords.z), w = 2 * R3857 / n;
    const x0 = -R3857 + coords.x * w, y1 = R3857 - coords.y * w;
    const tb = bboxToTM35([x0, y1 - w, x0 + w, y1]);

    const i = meta.files.findIndex(f => tb.xmax >= f.bounds[0] && tb.xmin <= f.bounds[2] &&
                                        tb.ymax >= f.bounds[1] && tb.ymin <= f.bounds[3]);
    if (i < 0) { setTimeout(() => done(null, tile), 0); return tile; }   // sea, or outside the published area

    terrainPart(meta, i)
      .then(gr => (gr && !tile._dead ? hillshadeGrid(gr, tb) : null))
      .then(vals => {
        if (vals && !tile._dead) {
          const small = document.createElement("canvas");
          small.width = RES; small.height = RES;
          paint(vals, small.getContext("2d"));
          const ctx = tile.getContext("2d");
          ctx.imageSmoothingEnabled = true;
          ctx.drawImage(small, 0, 0, size.x, size.y);
        }
        done(null, tile);
      })
      .catch(() => done(null, tile));
    return tile;
  },
});

let layer = null;
const chkHillshade = document.getElementById("chkHillshade");
chkHillshade.addEventListener("change", async () => {
  if (!chkHillshade.checked) { if (layer) map.removeLayer(layer); return; }
  const meta = await terrainReady();
  if (!meta) {
    chkHillshade.checked = false;
    toast("Rinnevarjostusta ei ole julkaistu tälle sivustolle");
    return;
  }
  layer = layer || new HillshadeLayer();
  layer.addTo(map);
});
