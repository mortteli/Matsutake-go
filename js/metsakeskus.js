import { MVMI_EFFECTIVE } from "./constants.js";
import { map, spots } from "./maplayer.js";
import { gate } from "./wms.js";

/* ================= Metsäkeskus: the forest that is no longer there =================
   Luke's MVMI is a snapshot. A stand clear-cut after MVMI_EFFECTIVE still reads as whatever it
   was before the machines came, and because regeneration cutting targets *old* stands, the error
   lands hardest exactly where this map is most confident. Two Metsäkeskus datasets fix it, and
   they are not interchangeable:

     stand (metsävarakuviot) — what the forest IS. Metsäkeskus updates it primarily from the
       harvesting machine's own telemetry (date, cutting method, a boundary traced from the
       machine's GPS), otherwise from aerial or satellite imagery. A development class of
       A0/S0/T1/T2 means open ground or a seedling stand: no mushroom this map knows about
       grows there. This is fact, so it is *subtracted* from the mask.
       Its limit is ownership: Metsäkeskus holds stand data for privately owned forest only.

     forestusedeclaration (metsänkäyttöilmoitukset) — what someone INTENDS. Filed at least 10
       days before cutting and valid for three years, and per Metsäkeskus's own product
       description "luonteeltaan hakkuuaikomus. Ilmoitettua toimenpidettä ei ole velvoite
       tehdä." Measured against the stand data around Tampere, 57 % of regeneration
       declarations filed since 2021 sit on ground that is now open or seedling — but 36 % are
       still standing mature forest. So a declaration is *never* subtracted, only reported on
       tap. Its strength is coverage: declaring is a legal duty, so it reaches forest the stand
       data does not.

   Both come from one CORS-open WFS, so this costs no pipeline run and never goes stale.
   Metsäkeskus serves EPSG:3067 and Finnish GK zones but *not* 3857, so the WMS path the Luke
   masks use is unavailable here: fetch GeoJSON and fill the polygons ourselves. That is the
   better half of the trade anyway — vertices are projected exactly, with nothing resampled. */
export const MK_WFS = "https://avoin.metsakeskus.fi/rajapinnat/v1/ows";
export const MK_SINCE = MVMI_EFFECTIVE + "T00:00:00Z";
// metsätietostandardi kehitysluokka: aukea, siemenpuumetsikkö, taimikot under and over 1.3 m.
// Y1 (ylispuustoinen taimikko) is deliberately absent — it keeps an overstory that may still be
// old pine, and unlike these four it is not by itself proof that the stand was reset.
export const MK_CUT_DEVCLASS = ["A0", "S0", "T1", "T2"];
export const MK_REGEN = 3;            // CUTTINGPURPOSE: uudistushakkuu. 1 (kasvatushakkuu) lands on a
                               // young stand only 6 % of the time — thinning leaves a forest.
export const MK_CELL_M = 10000;       // fetch by 10 km cell, not by tile: a z13 tile is ~4.9 km, so one
                               // request serves many tiles and panning stays free
export const MK_MAX = 4000;           // per cell; ~300 declarations / ~600 young stands is typical
/* Below this zoom the app does not ask Metsäkeskus anything at all. One screen is then a whole
   region: a 10 km cell is a few pixels across, a clear-cut stand is well under one, and the
   correction cannot change a pixel it is smaller than. It is also the difference between a
   handful of requests and a flood — a zoom-5 tile spans some 600 km, so enumerating its 10 km
   cells asks for thousands of cells for one tile, and the map builds dozens of tiles at a time.
   The same constant gates the drawn "Hakkuut" overlay, which has always had this floor. */
export const MK_MINZOOM = 11;
export const MK_PAR = 4;
export const mkGate = gate(MK_PAR);   // shared by cell fetches and point queries, which rank ahead
export const MK_TIMEOUT_MS = 9000;
// A 10 km cell of stands is 811 features and 2.0 MB if the server is allowed to send all 40 of
// its columns, of which this app reads four. `propertyName` cuts that to 1.47 MB, and the same
// trick takes declarations from 0.90 to about 0.55 MB. Anything added to a popup or to
// harvestHTML() has to be added here too, or it will arrive undefined.
export const MK_KIND = {
  stand: { type: "v1:stand",
           props: "GEOMETRY,DEVELOPMENTCLASS,MEANAGE,MEANHEIGHT,TREESTANDDATE",
           filter: " AND DEVELOPMENTCLASS IN ('" + MK_CUT_DEVCLASS.join("','") + "')" },
  mki:   { type: "v1:forestusedeclaration",
           props: "GEOMETRY,DECLARATIONARRIVALDATE,AREA,CUTTINGPURPOSE",
           filter: " AND DECLARATIONARRIVALDATE AFTER " + MK_SINCE + " AND CUTTINGPURPOSE=" + MK_REGEN },
};

/* Cells are cached, but not forever. Each holds a couple of megabytes of parsed GeoJSON, and
   featureBox() pins a bounding box onto every feature, so nothing in a cached cell can be
   collected. Panning across the country used to retain every cell ever visited. The cap is a
   working set of roughly 30 x 30 km per kind; `mkDone` mirrors the resolved value so tiles can
   read what has already arrived without awaiting a promise (see SpotLayer.createTile). */
export const MK_CACHE_CELLS = 12;
export const MK_RETRY_MS = 30000;     // cool-off after a failed cell, so an outage cannot become a loop
export const mkCache = new Map();     // "kind:gx:gy" -> Promise<Feature[]>
export const mkDone = new Map();      // same key -> Feature[], resolved only
export const mkFailed = new Map();    // same key -> when it last failed

// A failure is not cached as a result, but it is remembered for a while. Without this, every
// tile that wants a dead cell re-requests it, and the redraw those requests trigger asks again.
export function mkFresh(key) {
  const t = mkFailed.get(key);
  if (t == null) return true;
  if (Date.now() - t < MK_RETRY_MS) return false;
  mkFailed.delete(key);
  return true;
}

/* Tiles are drawn before their harvest cells arrive, so the layer has to be repainted when one
   lands. Four cells arriving together must cost one repaint, not four. */
export let cutRedrawTimer = null;
export function scheduleCutRedraw() {
  if (cutRedrawTimer) return;
  cutRedrawTimer = setTimeout(() => {
    cutRedrawTimer = null;
    if (typeof spots !== "undefined" && map.hasLayer(spots)) spots.redraw();
  }, 400);
}

export function mkTouch(key) {        // Map preserves insertion order: re-insert to mark as recently used
  if (mkCache.has(key)) { const v = mkCache.get(key); mkCache.delete(key); mkCache.set(key, v); }
  while (mkCache.size > MK_CACHE_CELLS) {
    const oldest = mkCache.keys().next().value;
    mkCache.delete(oldest);
    mkDone.delete(oldest);
  }
}

export function mkGet(kind, cql, count, opt) {
  const k = MK_KIND[kind];
  const url = MK_WFS + "?service=WFS&version=2.0.0&request=GetFeature" +
    "&typeNames=" + encodeURIComponent(k.type) +
    "&propertyName=" + encodeURIComponent(k.props) +
    "&srsName=EPSG:4326&outputFormat=application/json&count=" + (count || MK_MAX) +
    "&CQL_FILTER=" + encodeURIComponent(cql);
  // the timeout starts when the request does, not when it is queued
  return mkGate(() => {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), MK_TIMEOUT_MS);
    return fetch(url, { signal: ctl.signal })
      .then(r => r.ok ? r.json() : Promise.reject(new Error("metsakeskus " + r.status)))
      .then(j => j.features || [])
      .finally(() => clearTimeout(timer));
  }, opt);
}
export const mkBBox = (x0, y0, x1, y1) =>
  "BBOX(GEOMETRY," + x0 + "," + y0 + "," + x1 + "," + y1 + ",'EPSG:3067')";

// One 10 km cell of one kind, fetched once. A failure is never cached as a *result* — Metsäkeskus
// being down must leave the map exactly as it was before this feature existed, and the cell must
// be fetchable again — but it is remembered for MK_RETRY_MS before the next attempt, so an outage
// costs one request per cell per half minute rather than one per tile per redraw.
export function mkCell(kind, gx, gy) {
  const key = kind + ":" + gx + ":" + gy;
  const hit = mkCache.get(key);
  if (hit) { mkTouch(key); return hit; }
  if (!mkFresh(key)) return Promise.resolve([]);
  const x0 = gx * MK_CELL_M, y0 = gy * MK_CELL_M;
  const p = mkGet(kind, mkBBox(x0, y0, x0 + MK_CELL_M, y0 + MK_CELL_M) + MK_KIND[kind].filter)
    .then(feats => {
      if (mkCache.has(key)) mkDone.set(key, feats);
      if (kind === "stand") scheduleCutRedraw();   // tiles drawn without it are now out of date
      return feats;
    })
    .catch(() => {
      mkCache.delete(key); mkDone.delete(key); mkFailed.set(key, Date.now());
      return [];
    });
  mkCache.set(key, p);
  mkTouch(key);
  return p;
}
// `bb` is {xmin,ymin,xmax,ymax} in EPSG:3067.
export function mkCellsOf(bb) {
  const out = [];
  for (let gx = Math.floor(bb.xmin / MK_CELL_M); gx <= Math.floor(bb.xmax / MK_CELL_M); gx++)
    for (let gy = Math.floor(bb.ymin / MK_CELL_M); gy <= Math.floor(bb.ymax / MK_CELL_M); gy++)
      out.push([gx, gy]);
  return out;
}
// Polygons outside the caller's exact extent come back too; they simply draw off-canvas.
export function mkFeatures(kind, bb) {
  return Promise.all(mkCellsOf(bb).map(j => mkCell(kind, j[0], j[1])))
    .then(lists => [].concat.apply([], lists));
}
// What is already in hand for `bb`, without awaiting anything. Missing cells are requested in
// the background and reported as `pending`, so the caller can draw now and come back later.
export function mkFeaturesNow(kind, bb) {
  const features = [];
  let pending = false;
  for (const [gx, gy] of mkCellsOf(bb)) {
    const key = kind + ":" + gx + ":" + gy;
    if (mkDone.has(key)) { mkTouch(key); features.push.apply(features, mkDone.get(key)); }
    else if (mkFresh(key)) { pending = true; mkCell(kind, gx, gy); }
  }
  return { features: features, pending: pending };
}
// A question about one point, answered with one point's worth of data. Going through mkFeatures
// would round a 2 m box up to the enclosing 10 km cell and download megabytes to answer it — but
// if that cell happens to be loaded already, use it and skip the request entirely.
export function mkAt(kind, x, y) {
  const gx = Math.floor(x / MK_CELL_M), gy = Math.floor(y / MK_CELL_M);
  const key = kind + ":" + gx + ":" + gy;
  if (mkDone.has(key)) { mkTouch(key); return Promise.resolve(mkDone.get(key)); }
  // `first`, the same way Luke's queue ranks a tap or a scan: a point query is a question somebody
  // is waiting on, and one 10 km cell of speculative tile work ahead of it is seconds of nothing.
  return mkGet(kind, mkBBox(x - 1, y - 1, x + 1, y + 1) + MK_KIND[kind].filter, 10, { first: true })
    .catch(() => []);
}
