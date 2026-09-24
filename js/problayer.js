import { CUT_GREY } from "./constants.js";
import { projectionFor } from "./geo.js";
import { map, spots } from "./maplayer.js";
import { save, sp, state } from "./state.js";
import { toast } from "./ui.js";

/* ================= probability layer =================
   A GeoTIFF (value 0–100 = P × 100, 255 = no data) produced by ml/export/predict.py and read
   straight from the static site with HTTP range requests (georaster). The slider picks "the best
   X % of forest land": the threshold comes from the score quantiles of random forest cells that
   ml/export/export_app.py stores in prob_meta.json.

   A species' model is not one raster but a list of *regions*, because a model is trained per
   country on that country's forest inventory: Finland at 16 m in EPSG:3067 from Luke's MVMI,
   Sweden at 12.5 m in EPSG:3006 from SLU's forest map. A region is one prob_meta.json and
   everything it describes — its own projection, its own nodata, its own floor and its own
   quantile table — so the two never have to agree on anything except the meaning of the slider,
   which is "the best X % of forestry land" in each. Nothing above this layer branches per
   country: `species.model` is a URL or a list of them, and each file says what it is.

   The one number that is genuinely shared is the slider position. Each region turns it into its
   own threshold through its own quantiles, so "best 2 %" is the best 2 % of Finnish forest land
   in Finland and of Swedish forest land in Sweden — which is what a picker means by it on either
   side of the border. */
export const prob = { meta: null, metaFor: null, builtFor: null, regions: [],
                      rasters: [], cut: [], layers: [], loading: null };

// The flat views the rest of the app reads: every region's rasters, cut bands and layers in one
// list each. Kept in step with the regions by hand rather than computed on access, because
// ui.js's opacity loop and hideProb() run on every frame of a drag.
function reindex() {
  prob.rasters = prob.regions.flatMap(r => r.rasters);
  prob.cut = prob.regions.flatMap(r => r.cut);
  prob.layers = prob.regions.flatMap(r => r.layers);
}

export function loadScript(src) {
  return new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = src; s.onload = res; s.onerror = () => rej(new Error(src));
    document.head.appendChild(s);
  });
}
export function ensureGeoraster() {
  if (window.GeoRasterLayer) return Promise.resolve();
  if (!prob.loading)
    prob.loading = loadScript("vendor/georaster/georaster.browser.bundle.min.js")
      .then(() => loadScript("vendor/georaster/georaster-layer-for-leaflet.min.js"));
  return prob.loading;
}
// A species' model is one metadata URL or several; the first is the primary, the one the panel
// text and the slider's stop list are read from.
export const modelUrls = s => !s.model ? [] : Array.isArray(s.model) ? s.model : [s.model];

async function fetchMeta(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error("meta");
  return r.json();
}
/* Load every region's metadata and pair each with the projection its CRS names.
   Two failures are handled differently on purpose. The primary region failing is the model
   failing, and propagates. An additional region failing — missing file, or a CRS this build has
   no projection for — drops that region and leaves the rest of the map working: a Swedish pilot
   that will not load must not take the Finnish map down with it. A region is never drawn on a
   guess: an unknown CRS means "not drawn", because drawing it in the wrong place is worse than
   not drawing it. */
export async function loadProbMeta(species) {
  if (!species.model) return null;
  if (prob.metaFor === species.key) return prob.meta;
  const urls = modelUrls(species);
  const metas = [await fetchMeta(urls[0])].concat(
    await Promise.all(urls.slice(1).map(u => fetchMeta(u).catch(e => {
      console.warn("model region", u, e); return null;
    }))));
  // the regions being replaced belong to the species being left; take their layers off the map
  // before the list that holds them is thrown away
  prob.layers.forEach(l => map.removeLayer(l));
  prob.regions = [];
  metas.forEach((m, i) => {
    if (!m) return;
    const proj = projectionFor(m.crs);
    if (!proj) { console.warn("model region", urls[i], "has no projection for", m.crs); return; }
    prob.regions.push({ meta: m, proj, rasters: [], cut: [], layers: [] });
  });
  prob.meta = prob.regions[0].meta; prob.metaFor = species.key; prob.builtFor = null;
  reindex();
  return prob.meta;
}
// Is this the region the app's Finnish readouts — Luke's themes, Metsäkeskus, the baked DEM —
// are about? Identity, not a country code: the regions hold their own metadata objects.
export const isPrimaryRegion = meta => !!prob.regions.length && meta === prob.regions[0].meta;

// value (0–100) -> share of that region's forest cells scoring below it, from its stored quantiles
export function probRank(v, meta) {
  const q = (meta || prob.meta).quantiles;
  let lo = 0, hi = q.length - 1;
  while (lo < hi) { const m = (lo + hi) >> 1; if (q[m] < v) lo = m + 1; else hi = m; }
  return lo / (q.length - 1);
}
/* The widest share of forest land the slider may offer: the *narrowest* of the regions, so the
   legend's "parhaat X %" is true wherever the layer draws. A region whose raster stops at the
   best 15 % cannot honour a 25 % setting — it would keep painting its own best 15 % under a
   label promising more — and the smallest common ceiling is the only number that avoids that. */
export function probMaxPct() {
  const v = prob.regions.map(r => r.meta.max_pct).filter(x => typeof x === "number");
  return v.length ? Math.min(...v) : (prob.meta && prob.meta.max_pct) || 25;
}
/* The slider stops, not a plain 1–25 range: the whole point of the model layer is the very top of
   it, and the difference between "best 2 %" and "best 0,5 %" is the difference between a day of
   walking and one hillside. The stored raster is quantised finely enough to resolve these. */
export const PROB_STOPS = [0.25, 0.5, 1, 1.5, 2, 3, 5, 7, 10, 15, 20, 25];
export function probStops() { return PROB_STOPS.filter(v => v <= probMaxPct()); }
export function fmtPct(v) { return (v < 1 ? v.toFixed(2).replace(".", ",") : String(v)) + " %"; }
export function probStopIndex(pct) {
  const st = probStops();
  let best = 0;
  st.forEach((v, i) => { if (Math.abs(v - pct) < Math.abs(st[best] - pct)) best = i; });
  return best;
}
export function probThreshold(meta) {
  const m = meta || prob.meta;
  // interpolated, because the stops go below the spacing of the stored quantile grid
  const q = m.quantiles;
  const pos = Math.min(q.length - 1, Math.max(0, (1 - state.prob.pct / 100) * (q.length - 1)));
  const i = Math.floor(pos), f = pos - i;
  const thr = i >= q.length - 1 ? q[q.length - 1] : q[i] + (q[i + 1] - q[i]) * f;
  // cells below the stored floor are kept as 0 ("not in the mapped range"), never as a score
  return Math.max(thr, (m.floor || 0));
}
/* The model score, corrected for forest that has been cut since the inventory. When the baked
   cut layer is loaded it rides along as a second band (values[1]), so one pixel carries both
   "how good was this" and "is it still there":

     2  the stand register says open ground or seedling — drawn grey, whatever it scored. The
        score is deliberately kept rather than blanked: "was excellent forest, now cut" is worth
        seeing, and it is not the same thing as "never was anything".
     1  a regeneration felling was declared but never confirmed — drawn in the score's own
        colour, desaturated and paler, because it may still be standing.

   With `hideCut` off, or where no cut layer is published, values[1] is undefined and this
   behaves exactly as it did before. */
export function probColorFn(meta) {
  const m = meta || prob.meta;
  const thr = probThreshold(m), pct = state.prob.pct / 100, nod = m.nodata;
  const useCut = state.hideCut;
  return values => {
    const v = values[0], cut = values.length > 1 ? values[1] : 0;
    if (v == null || v === nod || v < thr) return null;
    if (useCut && cut === 2) return CUT_GREY;
    const t = Math.min(1, Math.max(0, (probRank(v, m) - (1 - pct)) / pct));   // 0 at threshold … 1 at the very best
    const r = Math.round(255), g = Math.round(209 - 164 * t), b = Math.round(102 + 18 * t);
    if (useCut && cut === 1)
      return "rgba(" + r + "," + Math.round(g + (235 - g) * 0.45) + "," +
             Math.round(b + (235 - b) * 0.45) + ",0.55)";
    return "rgba(" + r + "," + g + "," + b + ",0.85)";
  };
}
/* Every part of the baked model raster is a rectangle in its own national grid, and such a
   rectangle is a trapezoid in lat/lon: at the western edge of the Finnish grid north tilts nearly
   4° off true north, so the part's corners do not line up along meridians. georaster-layer-for-leaflet builds
   the layer's lat/lon box from the SW and NE corners alone, which is the box *inscribed* in that
   trapezoid — it throws away the eastern wedge of every western part and the northern wedge of
   every eastern one, both from the tile grid (options.bounds) and from the drawing itself
   (xMinOfLayer … yMaxOfLayer, which drawTile uses to skip samples). On the map that is a
   dead-straight line with nothing drawn beyond it: around Jämijärvi the whole 24 km wide corridor
   between 22,71° and 23,16° east stayed blank, about 4 % of the country's forest land.
   Measure the box along the part's edges instead of across its corners and hand it back. The
   sample-to-pixel mapping does not go through these numbers — it inverse-projects each sample and
   divides by the raster's own origin and pixel size — so widening them only lifts the clip, and
   a neighbouring part still draws nothing where it has no data.

   Measured with the layer's own projection rather than georaster-layer-for-leaflet's proj4
   projector, which is what the samples are taken with a few lines below: one description of where
   a part is, not two that could disagree, and no dependence on whether the bundled proj4 happens
   to carry a definition for the country's EPSG code. */
export function widenToProjection(layer, gr) {
  const proj = layer._proj;
  if (!proj) return;                       // no projection: leave the library's own bounds alone
  let w = 180, e = -180, s = 90, n = -90;
  const STEPS = 64;
  for (let i = 0; i <= STEPS; i++) {
    const x = gr.xmin + (gr.xmax - gr.xmin) * i / STEPS;
    const y = gr.ymin + (gr.ymax - gr.ymin) * i / STEPS;
    [[x, gr.ymin], [x, gr.ymax], [gr.xmin, y], [gr.xmax, y]].forEach(pt => {
      const ll = proj.inverse(pt[0], pt[1]);
      w = Math.min(w, ll[1]); e = Math.max(e, ll[1]);
      s = Math.min(s, ll[0]); n = Math.max(n, ll[0]);
    });
  }
  const b = L.latLngBounds([s, w], [n, e]);
  layer._bounds = b;
  layer.options.bounds = b;                                    // which tiles Leaflet creates
  layer.xMinOfLayer = w; layer.xMaxOfLayer = e;                 // which samples drawTile paints
  layer.yMinOfLayer = s; layer.yMaxOfLayer = n;
}
/* ---- sampling a tile on the raster's own grid ----
   georaster-layer-for-leaflet reads one rectangle of raster per tile — the rectangle between the
   tile's north-west and south-east corners — and then stretches it linearly across the tile. That
   is only right when the raster's grid runs the same way as the map's. Ours does not: a Web
   Mercator tile is a rotated quadrilateral in ETRS-TM35FIN, turned by the grid convergence, which
   reaches nearly 4° at the western edge of the country. No rectangle is its footprint. The
   library draws one anyway, unturned, so the error grows from the middle of the tile outwards,
   and because every tile re-centres its own error the picture jumps by twice that much across a
   tile seam. Measured at Jämijärvi before this: 61 of 64 blocks of the model layer sat 12 screen
   pixels or more from the ground they describe — 55 m at z14, 220 m at z12 — in a sawtooth that
   reset at every seam. Shapes broke along the seams and broke differently at the next zoom
   level. docs/MODEL_LAYER_SEAMS.md has the measurements.

   So the samples are taken here instead. Every sample centre is carried into the raster's own
   grid with the same projection the tap probe uses, which names the raster pixel actually under
   it; nothing depends on the tile it happens to fall in, so neighbouring tiles agree by
   construction. The projection comes off the layer, put there when the region was built, so a
   Swedish part is sampled through SWEREF99 TM and a Finnish one through TM35FIN with no branch
   here at all — the two are the same series with a different central meridian (js/geo.js). Drawn twice with
   the seams moved (256 px tiles against 512 px ones), the model layer now comes out the same
   picture — 0 % of pixels differ at z12 against 32 % before. The library's own drawTile then
   paints the grid we hand back, which is what it believes it is painting anyway. */

// Overview images of one part, indexed by how many full-resolution pixels one of their pixels
// covers: 1, 2, 4, … The parts are written by ml/export_app.py through GDAL's COG driver, so the
// overviews halve each time; an image that is not a clean power of two is left out.
export function rasterLevels(gr) {
  if (!gr._levels) gr._levels = (async () => {
    const tif = gr._geotiff, levels = [];
    const n = tif && tif.getImageCount ? await tif.getImageCount() : 0;
    for (let i = 0; i < n; i++) {
      const img = await tif.getImage(i);
      const f = gr.width / img.getWidth(), k = Math.round(Math.log2(f));
      if (k >= 0 && Math.abs(f / 2 ** k - 1) < 0.02 && !levels[k]) levels[k] = img;
    }
    return levels;
  })().catch(() => []);
  return gr._levels;
}

/* One window of one part, read at overview level `k` and handed back band by band. The window is
   given in the level's own pixels, so the pixel a sample lands on is `full >> k` — the same pixel
   whichever tile is asking. */
export async function readAtLevel(gr, k, win) {
  if (gr.values) return gr.values.map(band => ({ at: (row, col) => band[row][col] }));
  const img = (await rasterLevels(gr))[k];
  if (!img) throw new Error("no overview level " + k);
  const bands = await img.readRasters({ window: [win.left, win.top, win.right, win.bottom],
                                        fillValue: gr.noDataValue });
  const w = win.right - win.left, h = win.bottom - win.top;
  return bands.map(band => ({
    at: (row, col) => {
      const x = (col >> k) - win.left, y = (row >> k) - win.top;
      return (x < 0 || x >= w || y < 0 || y >= h) ? gr.noDataValue : band[y * w + x];
    },
  }));
}

export async function sampleOnRasterGrid(layer, o) {
  const m = layer.getMap(), grs = layer.georasters, gr = grs[0];
  const gridRow = layer._proj.row;                       // WGS84 -> this raster's grid, per row
  const across = o.numberOfSamplesAcross, down = o.numberOfSamplesDown;
  const nw = o.innerTileTopLeftPoint;
  const lngAt = x => m.unproject(L.point(x, nw.y), o.zoom).lng;
  const latAt = y => m.unproject(L.point(nw.x, y), o.zoom).lat;
  // Web Mercator is separable: a sample's longitude follows from its column alone and its
  // latitude from its row alone, so this costs across + down unprojections, not across × down.
  const lon = new Float64Array(across), lat = new Float64Array(down);
  for (let c = 0; c < across; c++) lon[c] = lngAt(nw.x + (c + 0.5) * o.widthOfSampleInScreenPixels);
  for (let r = 0; r < down; r++) lat[r] = latAt(nw.y + (r + 0.5) * o.heightOfSampleInScreenPixels);

  // the raster pixel under every sample, and the window that holds them all
  const col = new Int32Array(across * down), row = new Int32Array(across * down);
  let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
  for (let r = 0; r < down; r++) {
    const tm = gridRow(lat[r]);                         // the series' latitude half, once a row
    for (let c = 0; c < across; c++) {
      const p = tm(lon[c]), i = r * across + c;
      const x = Math.floor((p.x - gr.xmin) / gr.pixelWidth);
      const y = Math.floor((gr.ymax - p.y) / gr.pixelHeight);
      const inside = x >= 0 && x < gr.width && y >= 0 && y < gr.height;
      col[i] = inside ? x : -1; row[i] = inside ? y : -1;
      if (!inside) continue;
      if (x < left) left = x;
      if (x > right) right = x;
      if (y < top) top = y;
      if (y > bottom) bottom = y;
    }
  }

  /* Which overview to read: the coarsest one still finer than a sample. The spacing is measured
     off the map scale and the layer's own resolution, never off this tile's sample count — a tile
     clipping the corner of a part is handed a sample or two for the whole of it, and taking that
     at face value would talk the part into reading at kilometre pixels. The answer is then kept
     for the zoom, because two tiles side by side reading different levels would show two
     different generalisations of the same forest, and that seam would be as plain as the one
     this replaces. */
  const levels = await rasterLevels(gr);
  if (!gr._levelFor) gr._levelFor = {};
  if (gr._levelFor[o.zoom] == null) {
    const px = layer.getTileSize().x / Math.max(1, layer.options.resolution || 32);   // screen px a sample covers
    const at00 = gridRow(latAt(nw.y))(lngAt(nw.x));
    const stepX = px * Math.abs(gridRow(latAt(nw.y))(lngAt(nw.x + 1)).x - at00.x) / gr.pixelWidth;
    const stepY = px * Math.abs(gridRow(latAt(nw.y + 1))(lngAt(nw.x)).y - at00.y) / gr.pixelHeight;
    let k = Math.max(0, Math.floor(Math.log2(Math.max(stepX, stepY, 1))));
    while (k > 0 && !levels[k]) k--;
    gr._levelFor[o.zoom] = k;
  }
  const k = gr._levelFor[o.zoom];
  const img = levels[k];
  const win = right < left ? { left: 0, top: 0, right: 0, bottom: 0 } : {
    left: left >> k, top: top >> k,
    right: Math.min((right >> k) + 1, img ? img.getWidth() : Infinity),
    bottom: Math.min((bottom >> k) + 1, img ? img.getHeight() : Infinity),
  };

  // the parts are read side by side: the score and the cut layer are two files, and waiting for
  // one before asking for the other doubles how long a tile takes to appear
  const bands = (await Promise.all(grs.map(g => readAtLevel(g, k, win)))).flat();
  return bands.map(band => {
    const out = [];
    for (let r = 0; r < down; r++) {
      const line = new Array(across);
      for (let c = 0; c < across; c++) {
        const i = r * across + c;
        line[c] = col[i] < 0 ? gr.noDataValue : band.at(row[i], col[i]);
      }
      out.push(line);
    }
    return out;
  });
}

// Hand the layer its samples instead of letting it guess them. Anything unexpected — a part with
// no overviews to read, a projection this does not cover — falls back to the library's own
// sampling, which draws a slightly displaced map rather than none at all.
export function sampleExactly(layer) {
  const fallback = layer.getRasters;
  layer.getRasters = function (o) {
    return sampleOnRasterGrid(this, o).catch(err => {
      if (!this._samplingWarned) { this._samplingWarned = true; console.warn("tile sampling:", err); }
      return fallback.call(this, o);
    });
  };
}

// The rule mask and the model draw the same claim two ways; showing both at once just invites
// them to disagree on screen. So only one is ever on the map: the model, once it has something
// to say for the current species, otherwise the rule mask.
export function syncRuleLayer() {
  const showingProb = state.prob.on && !!sp().model;
  if (showingProb) { if (map.hasLayer(spots)) map.removeLayer(spots); }
  else if (!map.hasLayer(spots)) spots.addTo(map);
  document.getElementById("legendRule").hidden = showingProb;
  document.getElementById("regularFilterSettings").hidden = showingProb;
}

// geotiff.js fetches inside a worker, where relative URLs cannot be resolved
const asGeoraster = f => parseGeoraster(new URL(f.url, location.href).href);

async function loadRegionRasters(r) {
  r.rasters = await Promise.all(r.meta.files.map(asGeoraster));
  // The cut layer is optional: a region may not have one, and a failed load must leave the
  // probability map working rather than take it down with it.
  r.cut = r.meta.cut ? await Promise.all(r.meta.cut.files.map(f => asGeoraster(f).catch(() => null)))
                           .catch(() => []) : [];
  if (r.cut.some(c => !c)) r.cut = [];
}
// Whose data a region is drawn from. Regions written after this key existed carry their own line;
// the Finnish parts predate it and keep the one they have always shown.
const attributionFor = r => r.meta.attribution ||
  ("Malli: Matsutake GO ml (GBIF · Luke · MML · GTK · FMI)" +
   (r.cut.length ? " · hakkuut © Suomen metsäkeskus" : ""));

export async function showProb() {
  const species = sp();
  try {
    const meta = await loadProbMeta(species);
    if (!meta) return;
    await ensureGeoraster();
    if (prob.builtFor !== species.key) {
      hideProb(true);
      const ok = [];
      for (const r of prob.regions) {
        try { await loadRegionRasters(r); ok.push(r); }
        catch (e) {
          if (r === prob.regions[0]) throw e;      // the primary failing is the model failing
          console.warn("model region", r.meta.species, e);
        }
      }
      prob.regions = ok;
      prob.regions.forEach(r => {
        r.layers = r.rasters.map((gr, i) => {
          const layer = new GeoRasterLayer({
            georasters: r.cut[i] ? [gr, r.cut[i]] : [gr],
            opacity: state.opacity, resolution: 128, pixelValuesToColorFn: probColorFn(r.meta),
            attribution: attributionFor(r),
          });
          layer._proj = r.proj;              // read by widenToProjection and sampleOnRasterGrid
          widenToProjection(layer, gr);
          sampleExactly(layer);
          return layer;
        });
      });
      prob.builtFor = species.key;
      reindex();
    }
    prob.layers.forEach(l => { if (!map.hasLayer(l)) l.addTo(map); });
    updateProbLegend();
    syncRuleLayer();
  } catch (e) {
    state.prob.on = false; save(); renderProb();
    toast("Todennäköisyyskarttaa ei voitu ladata");
    syncRuleLayer();
  }
}
export function hideProb(drop) {
  prob.layers.forEach(l => map.removeLayer(l));
  if (drop) {
    prob.regions.forEach(r => { r.rasters = []; r.cut = []; r.layers = []; });
    prob.builtFor = null;
    reindex();
  }
  document.getElementById("legendProb").hidden = true;
  syncRuleLayer();
}
// Recolour in place — the rasters stay loaded, only the colour function changes. Per region,
// because one slider position is a different score in each of them.
export function repaintProb() {
  if (!prob.meta || !prob.layers.length) return;
  prob.regions.forEach(r => r.layers.forEach(l => l.updateColors(probColorFn(r.meta))));
  updateProbLegend();
}

export function updateProbLegend() {
  const el = document.getElementById("legendProb");
  el.hidden = !state.prob.on || !prob.meta;
  const showCut = state.hideCut && prob.cut.length;
  document.getElementById("legendProbText").textContent =
    "malli: parhaat " + fmtPct(state.prob.pct) + " metsämaasta" + (showCut ? " · harmaa = hakattu" : "");
}
export function renderProb() {
  const s = sp(), host = document.getElementById("probPanel");
  host.innerHTML = "";
  if (!s.model) {
    host.innerHTML = '<p class="note">Ei vielä tälle lajille — mallia opetetaan ensin matsutakelle.</p>';
    return;
  }
  host.innerHTML =
    '<div class="row"><label>Näytä malli<br><small>havainnoista opetettu malli, 16 m</small></label>' +
    '<label class="switch"><input type="checkbox" id="probOn"><i></i></label></div>' +
    '<div class="row"><label>Näytä parhaat<br><small>osuus metsämaasta</small></label>' +
    '<input type="range" id="probPct" min="0" max="' + (probStops().length - 1) + '" step="1">' +
    '<span class="val" id="probPctVal"></span></div>' +
    '<p class="note" id="probNote">Väri: keltainen = juuri rajan yli, pinkki = mallin parhaat ruudut. ' +
    'Pienempi osuus = vähemmän paikkoja mutta parempia: parhaassa 0,5 %:ssa kaksi kolmesta ' +
    'sieni-ilmoituksesta on matsutakea, parhaassa 5 %:ssa joka kolmas. ' +
    'Sääntökartta piilotetaan mallin ollessa päällä.</p>';
  const on = host.querySelector("#probOn"), rng = host.querySelector("#probPct"), val = host.querySelector("#probPctVal");
  on.checked = state.prob.on; rng.value = probStopIndex(state.prob.pct); val.textContent = fmtPct(state.prob.pct);
  on.addEventListener("change", () => {
    state.prob.on = on.checked; save();
    if (on.checked) showProb(); else hideProb(false);
  });
  let t = null;
  rng.addEventListener("input", () => {
    state.prob.pct = probStops()[+rng.value]; val.textContent = fmtPct(state.prob.pct); save();
    clearTimeout(t);
    t = setTimeout(repaintProb, 150);
  });
  loadProbMeta(s).then(m => {
    if (!m) return;
    const st = probStops();
    rng.max = st.length - 1;
    if (state.prob.pct > st[st.length - 1]) { state.prob.pct = st[st.length - 1]; save(); }
    rng.value = probStopIndex(state.prob.pct);
    state.prob.pct = st[+rng.value];                 // snap a stored value onto the stop list
    val.textContent = fmtPct(state.prob.pct);
    const note = document.getElementById("probNote");
    if (note && m.trained) note.insertAdjacentHTML("beforeend",
      " Opetettu " + m.trained + (m.n_presence ? " · " + m.n_presence + " havaintoa" : "") +
      ". Kartta kattaa metsämaan parhaan " + fmtPct(probMaxPct()) + "; muualla malli ei piirrä mitään.");
    // Each additional region says in its own metadata what it covers, so a pilot that maps one
    // corner of a country cannot be mistaken for the country. The app does not know the sentence;
    // the file that put the raster there does.
    prob.regions.slice(1).forEach(r => {
      if (note && r.meta.app_note) note.insertAdjacentHTML("beforeend", " " + r.meta.app_note);
    });
  }).catch(() => {});
}
