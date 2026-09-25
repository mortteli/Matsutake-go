import { R3857, SPOT_COLOR } from "./constants.js";
import { bboxToTM35, boundsToTM35, y3857ToLat } from "./geo.js";
import { MK_MINZOOM, mkFeaturesNow, mkViewFits, onCutRedraw } from "./metsakeskus.js";
import { cfg, sp, state } from "./state.js";
import { DROPPED, compositeMask, newCanvas, subtractCut } from "./wms.js";

/* ================= composite spot layer =================
   For every map tile, fetch one server-styled binary mask per condition
   (a condition with several members is unioned first) and keep only the
   pixels present in ALL conditions. */

// Tiles painted before their Metsäkeskus cell arrived, waiting to be corrected once it does.
// Keyed by tile coords so only the tiles that actually used incomplete cut data get touched —
// a bare layer-wide redraw() on every cell arrival tore down and re-fetched every visible tile
// from Luke, which is what turned "one cell landed" into the whole layer blinking out and back
// in while zooming. Each keeps the Luke mask it was drawn from, uncorrected, so the correction
// is applied to that rather than to a fresh set of WMS requests.
const cutPending = new Map();   // "z:x:y" -> { tile, mask, bbox, size }
const tileKey = coords => coords.z + ":" + coords.x + ":" + coords.y;

// Luke's mask, minus the cut stands, coloured and drawn into the tile canvas. Synchronous, and
// the canvas is cleared first, so a correction replaces the picture in one frame: no blink.
function drawTile(tile, size, mask, bbox, cutFeatures) {
  const off = newCanvas(size.x, size.y), octx = off.getContext("2d");
  octx.drawImage(mask, 0, 0);
  subtractCut(octx, cutFeatures, bbox, size.x, size.y);
  octx.globalCompositeOperation = "source-in";      // recolor result
  octx.fillStyle = SPOT_COLOR;
  octx.fillRect(0, 0, size.x, size.y);
  // dilate by 1 px so 16 m cells stay visible at berry-app zooms
  const ctx = tile.getContext("2d");
  ctx.clearRect(0, 0, size.x, size.y);
  for (let dx = -1; dx <= 1; dx++)
    for (let dy = -1; dy <= 1; dy++)
      ctx.drawImage(off, dx, dy);
}

// Debounced, and called only when a "stand" cell resolves — correct just the tiles waiting on
// cut data, in place, rather than the whole layer. Reads what has arrived and never requests
// anything itself: a tile whose cell failed or was evicted is painted with what there is, not
// sent round again.
onCutRedraw(() => {
  for (const [key, t] of cutPending) {
    if (t.tile._dead) { cutPending.delete(key); continue; }
    const cut = mkFeaturesNow("stand", bboxToTM35(t.bbox), false);
    if (cut.pending) continue;          // still waiting on another cell
    cutPending.delete(key);
    drawTile(t.tile, t.size, t.mask, t.bbox, cut.features);
  }
});

export const SpotLayer = L.GridLayer.extend({
  initialize(options) {
    L.GridLayer.prototype.initialize.call(this, options);
    // An Image load cannot be cancelled, but a queued one has not started yet: mark the tile so
    // the Luke queue can drop whatever of it is still waiting when Leaflet throws it away.
    this.on("tileunload", e => {
      e.tile._dead = true;
      const key = tileKey(e.coords), t = cutPending.get(key);
      if (t && t.tile === e.tile) cutPending.delete(key);
    });
  },
  createTile(coords, done) {
    const tile = document.createElement("canvas");
    const size = this.getTileSize();
    tile.width = size.x; tile.height = size.y;

    const n = Math.pow(2, coords.z), w = 2 * R3857 / n;
    const x0 = -R3857 + coords.x * w, y1 = R3857 - coords.y * w;
    const bbox = [x0, y1 - w, x0 + w, y1];

    const species = sp(), c = cfg();
    // species outside its range: draw nothing rather than pretend
    if (species.maxLat != null && y3857ToLat(y1 - w) > species.maxLat) {
      setTimeout(() => done(null, tile), 0);
      return tile;
    }

    // Draw with whatever harvest data is already in hand and hand the tile back now. Waiting for
    // the fetch first meant every tile sat on a ~1.5 MB download before showing anything, which
    // is what made the map feel frozen rather than merely slow — the Luke masks were ready long
    // before. A missing cell is requested in the background and only this tile is corrected,
    // debounced, once it lands. Metsäkeskus being unreachable simply leaves the tile as it was
    // before this feature existed; an outage may not blank the map.
    // Only when the whole view is small enough to be worth correcting (mkViewFits): a tile at the
    // zoom floor on a wide screen would otherwise start a download of dozens of cells.
    const bbTM = bboxToTM35(bbox);
    const useCut = state.hideCut && coords.z >= MK_MINZOOM && this._map &&
      mkViewFits(boundsToTM35(this._map.getBounds()));
    if (useCut) mkFeaturesNow("stand", bbTM);          // start the fetch alongside Luke's
    const key = tileKey(coords);
    cutPending.delete(key);
    compositeMask(species.conditions(c), bbox, size.x, size.y, null,
                  { alive: () => !tile._dead }).then(mask => {
      // what has arrived by now, not by when the tile was asked for
      const cut = useCut ? mkFeaturesNow("stand", bbTM, false) : { features: [], pending: false };
      drawTile(tile, size, mask, bbox, cut.features);
      if (cut.pending) cutPending.set(key, { tile, mask, bbox, size });
      done(null, tile);
    }).catch(err => done(err === DROPPED ? null : err, tile));
    return tile;
  }
});
