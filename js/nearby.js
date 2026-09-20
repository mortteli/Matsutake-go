import { DIR8, MIN_CORE_M, MIN_SPOT_HA, NEARBY_CELL_M, NEARBY_CLOSE, NEARBY_CUT_CHECKS, NEARBY_HALF_KM, NEARBY_N, NEARBY_RADIUS_M, NEARBY_REANCHOR_M, NEARBY_SEP_M, NEARBY_VIEW_MAX_M } from "./constants.js";
import { inFeature, toTM35, y3857ToLat } from "./geo.js";
import { ensureFix, gpsError, gpsUpdate, startGps } from "./gps.js";
import { map } from "./maplayer.js";
import { mkAt } from "./metsakeskus.js";
import { gotoSearchHit, search, showSearchResults } from "./search.js";
import { cfg, sp, state } from "./state.js";
import { compositeMask } from "./wms.js";

/* ================= lähellä sinua =================
   The app has rasters, not features: nothing in it knows where one forest ends and the next
   begins. So the scan makes those entities on the spot — one big composite mask around the user,
   labelled into connected patches, each measured and ranked. See the MIN_SPOT_HA / MIN_CORE_M
   comment above for what counts as a spot and why.

   Scale: EPSG:3857 metres are not ground metres — at 63° N one is about 0.45 of a real metre, so
   getting this wrong would overstate every area by ~4×. The correction therefore happens exactly
   once, in the bbox below, and nowhere else: the image is a fixed 2·R/CELL pixels regardless of
   latitude, so a cell is CELL² ground metres *by construction*. (cos varies by ~0.8 % across a
   50 km box; that is well inside the MVMI's own accuracy and is left alone.) Distances shown to
   the user are a separate, exact calculation in EPSG:3067 via toTM35 — the same convention
   ml/pick_sites.py and parseCoords already use. */
// `seq` stands in for an AbortController: an Image load cannot be cancelled, so a scan that is
// no longer the current one is dropped when it lands rather than stopped in flight.
export const nearby = { key: null, spots: null, seq: 0, geocoding: false, anchor: null, paint: null, scanning: null };

// a scan in flight is abandoned rather than awaited: whatever it was computing is now stale
export function clearNearby() { nearby.key = null; nearby.spots = null; nearby.anchor = null; nearby.scanning = null; }
export function nearbyWaiting() {
  return !!search.panel && search.panel.classList.contains("open") && !search.input.value.trim();
}
// deliberately not keyed on where the point came from: a scan is a scan, so a list already
// computed for the map centre is reused as-is once the GPS fix lands on the same square
export function nearbyKey(at) {
  return [state.species, JSON.stringify(cfg()), at.lat.toFixed(2), at.lon.toFixed(2), NEARBY_RADIUS_M].join("|");
}

/* Where the list looks from. A fix wins when there is one, but not having one is not a dead end:
   the map view is itself an answer to "near here" — it is the place the user has already
   chosen to look at — and reading it raises no permission prompt at all. `reason` is carried
   along so the caller knows whether offering the location button would be any use. */
export async function nearbyAnchor() {
  const fix = await ensureFix();
  if (!fix.reason) return { lat: fix.lat, lon: fix.lon, src: "gps" };
  const c = map.getCenter(), b = map.getBounds();
  return { lat: c.lat, lon: c.lng, src: "map", reason: fix.reason,
           wide: map.distance(b.getNorthWest(), b.getNorthEast()) > NEARBY_VIEW_MAX_M };
}

// the scan window, in the projection the WMS speaks
export function scanGeometry(lat, lon) {
  const c = map.options.crs.project(L.latLng(lat, lon));
  const k = Math.cos(lat * Math.PI / 180);          // 3857 unit -> ground metre
  const half = NEARBY_RADIUS_M / k;
  const N = Math.round(2 * NEARBY_RADIUS_M / NEARBY_CELL_M);
  const cell = 2 * half / N;                        // exact, so no rounding drift across the box
  return { N: N, cell: cell, x0: c.x - half, y1: c.y + half, bbox: [c.x - half, c.y - half, c.x + half, c.y + half] };
}
export function scanCellLatLng(geom, ix, iy) {
  return map.options.crs.unproject(L.point(geom.x0 + (ix + 0.5) * geom.cell, geom.y1 - (iy + 0.5) * geom.cell));
}

// the composite, as one byte per cell. Luke's masks are 1-bit, so >= 128 is exact, not a guess.
export async function scanMask(geom, species, c) {
  // `first`: the panel is open and somebody is waiting on it, so the scan goes ahead of tile work
  const off = await compositeMask(species.conditions(c), geom.bbox, geom.N, geom.N, null, { first: true });
  const px = off.getContext("2d").getImageData(0, 0, geom.N, geom.N).data;
  const mask = new Uint8Array(geom.N * geom.N);
  // the WMS box is square but the radius is a radius: clip to the circle, the way
  // ml/pick_sites.py does, so a corner of the box cannot offer a spot 35 km away
  const mid = (geom.N - 1) / 2, rCells = geom.N / 2;
  for (let y = 0, i = 0; y < geom.N; y++) {
    const dy = y - mid;
    for (let x = 0; x < geom.N; x++, i++)
      mask[i] = (px[i * 4 + 3] >= 128 && (x - mid) * (x - mid) + dy * dy <= rCells * rCells) ? 1 : 0;
  }
  // out of the species' range: the tile layer bails per tile, the scan cuts per row — stricter,
  // and the right thing when a scan box is 50 km tall
  if (species.maxLat != null) {
    for (let y = 0; y < geom.N; y++) {
      if (y3857ToLat(geom.y1 - (y + 1) * geom.cell) <= species.maxLat) break;
      mask.fill(0, y * geom.N, (y + 1) * geom.N);
    }
  }
  return mask;
}

// 8-connected components, matching ndimage.label(..., structure=np.ones((3,3))) in pick_sites.py.
// Flood fill with an explicit queue: 2.4 million cells would bury a recursive fill.
export function labelPatches(mask, w, h) {
  const lab = new Int32Array(w * h), queue = new Int32Array(w * h);
  let n = 0;
  for (let s = 0; s < mask.length; s++) {
    if (!mask[s] || lab[s]) continue;
    const id = ++n;
    let head = 0, tail = 0;
    lab[s] = id; queue[tail++] = s;
    while (head < tail) {
      const p = queue[head++], px = p % w, py = (p - px) / w;
      for (let dy = -1; dy <= 1; dy++) {
        const ny = py + dy;
        if (ny < 0 || ny >= h) continue;
        for (let dx = -1; dx <= 1; dx++) {
          const nx = px + dx;
          if (nx < 0 || nx >= w) continue;
          const q = ny * w + nx;
          if (mask[q] && !lab[q]) { lab[q] = id; queue[tail++] = q; }
        }
      }
    }
  }
  return { lab: lab, n: n };
}

/* Chamfer distance to the nearest non-matching cell, weights 3 (orthogonal) / 4 (diagonal), so
   every distance is three times its value in cells. It does double duty below: the closing is
   built out of two of these, and the value it leaves behind *is* the core measurement, so a
   patch's width costs no pass of its own. Cells outside the image count as background, which
   makes a patch clipped by the scan edge report a conservative core and area — truncation can
   only lose it a place in the list, never win one, so the edge needs no special case. */
export function chamfer(mask, w, h) {
  const INF = 30000;                                 // not 65535: 65535 + 3 would wrap
  const d = new Uint16Array(w * h);
  for (let i = 0; i < d.length; i++) d[i] = mask[i] ? INF : 0;
  const at = (x, y) => (x < 0 || y < 0 || x >= w || y >= h) ? 0 : d[y * w + x];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = y * w + x;
    if (!d[i]) continue;
    const v = Math.min(d[i], at(x - 1, y - 1) + 4, at(x, y - 1) + 3, at(x + 1, y - 1) + 4, at(x - 1, y) + 3);
    if (v < d[i]) d[i] = v;
  }
  for (let y = h - 1; y >= 0; y--) for (let x = w - 1; x >= 0; x--) {
    const i = y * w + x;
    if (!d[i]) continue;
    const v = Math.min(d[i], at(x + 1, y + 1) + 4, at(x, y + 1) + 3, at(x - 1, y + 1) + 4, at(x + 1, y) + 3);
    if (v < d[i]) d[i] = v;
  }
  return d;
}

/* Close the mask by `r` cells — dilate, then erode — and hand back the closed mask together with
   its distance transform. Two chamfer passes do the whole job: the erosion is `d > r` on the
   dilated mask, and the closed mask's own distance is that same d less r, because a distance
   transform changes by exactly the amount you erode. Closing keeps thin structures (unlike
   opening), so the core test below still has ribbons to reject. */
export function closeMask(mask, w, h, r) {
  const inv = new Uint8Array(mask.length);
  for (let i = 0; i < mask.length; i++) inv[i] = mask[i] ? 0 : 1;
  const dInv = chamfer(inv, w, h);                 // background cells: how far to a matching one
  const dil = new Uint8Array(mask.length);
  for (let i = 0; i < mask.length; i++) dil[i] = dInv[i] <= r ? 1 : 0;
  const dDil = chamfer(dil, w, h);
  const closed = new Uint8Array(mask.length), dist = new Uint16Array(mask.length);
  for (let i = 0; i < mask.length; i++) if (dDil[i] > r) { closed[i] = 1; dist[i] = dDil[i] - r; }
  return { closed: closed, dist: dist };
}

/* One linear pass into parallel arrays per component: how big, how far across, where it is. The
   point we hand back is the cell *deepest inside* the patch, not its centroid — a centroid can
   land in the clearcut a horseshoe curls around, and the deepest cell is also simply where you
   want to be standing. pick_sites.py picks its bx/by the same way and for the same reason. */
export function patchStats(lab, n, dist, mask, geom, fix) {
  const cells = new Int32Array(n + 1), best = new Int32Array(n + 1).fill(-1), bestD = new Uint16Array(n + 1);
  const minX = new Int32Array(n + 1).fill(geom.N), maxX = new Int32Array(n + 1).fill(-1);
  const minY = new Int32Array(n + 1).fill(geom.N), maxY = new Int32Array(n + 1).fill(-1);
  for (let i = 0; i < lab.length; i++) {
    const id = lab[i];
    if (!id) continue;
    const x = i % geom.N, y = (i - x) / geom.N;
    if (mask[i]) cells[id]++;      // hectares count cells that really qualify, not bridged gaps
    if (x < minX[id]) minX[id] = x;
    if (x > maxX[id]) maxX[id] = x;
    if (y < minY[id]) minY[id] = y;
    if (y > maxY[id]) maxY[id] = y;
    if (dist[i] > bestD[id]) { bestD[id] = dist[i]; best[id] = i; }
  }
  const cellHa = NEARBY_CELL_M * NEARBY_CELL_M / 1e4;
  const me = toTM35(fix.lat, fix.lon);
  const out = [];
  for (let id = 1; id <= n; id++) {
    const areaHa = cells[id] * cellHa;
    // the chamfer counts the step out to the first *background* cell, so the deepest cell of an
    // n-wide patch reads (n+1)/2 — subtract the one cell back off. Values are built from 3s and
    // 4s, so 80 m lands on the next reachable step up, a 3-cell (96 m) core.
    const coreM = (2 * (bestD[id] / 3) - 1) * NEARBY_CELL_M;
    if (areaHa < MIN_SPOT_HA || coreM < MIN_CORE_M) continue;
    const bx = best[id] % geom.N, by = (best[id] - bx) / geom.N;
    const ll = scanCellLatLng(geom, bx, by);
    const there = toTM35(ll.lat, ll.lng);
    // row indices grow southward, so the patch's south-west corner is (minX, maxY)
    const sw = scanCellLatLng(geom, minX[id], maxY[id]), ne = scanCellLatLng(geom, maxX[id], minY[id]);
    out.push({
      areaHa: areaHa, coreM: coreM, lat: ll.lat, lon: ll.lng, tm: there,
      distM: Math.hypot(there.x - me.x, there.y - me.y),
      bounds: [[sw.lat, sw.lng], [ne.lat, ne.lng]],
      name: null,
    });
  }
  return out;
}

export async function findNearbySpots(fix) {
  const species = sp(), geom = scanGeometry(fix.lat, fix.lon);
  const mask = await scanMask(geom, species, cfg());
  const closed = closeMask(mask, geom.N, geom.N, NEARBY_CLOSE * 3);   // chamfer counts 3 per cell
  const { lab, n } = labelPatches(closed.closed, geom.N, geom.N);
  const spots = patchStats(lab, n, closed.dist, mask, geom, fix);
  // Size is the only quality the boolean mask offers, but the biggest forest in a 25 km circle
  // is not always the one to drive to — so hectares count half at NEARBY_HALF_KM.
  spots.sort((a, b) => (b.areaHa / (1 + b.distM / 1000 / NEARBY_HALF_KM)) -
                       (a.areaHa / (1 + a.distM / 1000 / NEARBY_HALF_KM)));
  // Then drop the ones Metsäkeskus says have been cut. The scan mask itself is left alone: a
  // 50 km box holds on the order of 15 000 young stands, far too many to fetch on a phone. So
  // the check lands where it actually decides a trip — on the deepest cell of each surviving
  // candidate, the point the list hands out and `pick_sites.py` calls bx/by. That is a weaker
  // correction than the tile layer gets: a patch's hectares can still be padded by ground that
  // has since been cut, and two forests can still be bridged through a clearcut between them.
  // What it does guarantee is that the place you are sent to still has trees on it.
  const picked = [];
  let looked = 0, cutOut = 0;
  for (const s of spots) {
    if (picked.length === NEARBY_N || looked >= NEARBY_CUT_CHECKS) break;
    if (!picked.every(p => Math.hypot(s.tm.x - p.tm.x, s.tm.y - p.tm.y) > NEARBY_SEP_M)) continue;
    if (state.hideCut) { looked++; if (await spotIsCut(s)) { cutOut++; continue; } }
    picked.push(s);
  }
  // Fragmented regions (Tampere is the extreme case, see NEARBY_CLOSE above) can turn up only a
  // handful of candidates to begin with, so losing even one or two to recent logging is enough to
  // empty the list — a fate a "loosen your filters" message describes wrongly. Carried on the
  // array itself so the empty-list branch in renderNearby can tell the two apart without a second
  // return value threading through the cache (`nearby.spots` has to stay a plain spot array).
  picked.cutOut = cutOut;
  return picked;
}

// A few kilobytes per candidate, or nothing at all where the tile layer has already loaded that
// cell. Candidates are spread over a 50 km box, so the enclosing cells are usually *not* loaded —
// asking for them whole would have meant megabytes per spot.
export async function spotIsCut(s) {
  const feats = await mkAt("stand", s.tm.x, s.tm.y);
  return feats.some(f => inFeature(f, s.lon, s.lat));
}

/* ---------- rendering ---------- */
export const fmtKm = m => m < 1000 ? Math.round(m / 10) * 10 + " m" : (m / 1000).toFixed(1).replace(".", ",") + " km";
export const fmtHa = ha => (ha < 10 ? ha.toFixed(1) : Math.round(ha).toString()).replace(".", ",") + " ha";

export function nearbyRow(s, at) {
  const me = toTM35(at.lat, at.lon), dE = s.tm.x - me.x, dN = s.tm.y - me.y;
  const where = fmtKm(Math.hypot(dE, dN)) + " " +
    DIR8[(Math.round(Math.atan2(dE, dN) * 4 / Math.PI) + 8) % 8];
  const li = document.createElement("li");
  li.className = "spot";
  li.appendChild(document.createTextNode(sp().emoji + " " + (s.name || where)));
  const area = document.createElement("span");
  area.className = "area";
  area.textContent = fmtHa(s.areaHa);
  li.appendChild(area);
  const sm = document.createElement("small");
  sm.textContent = (s.name ? where + " · " : "") + "ydin ~" + Math.round(s.coreM / 10) * 10 + " m";
  li.appendChild(sm);
  li.addEventListener("click", () => gotoSearchHit({
    title: s.name || (sp().name + ", " + where), lat: s.lat, lon: s.lon, bounds: s.bounds }));
  return li;
}

export function nearbySection(title, nodes, sub) {
  const head = document.createElement("li");
  head.className = "sect";
  head.appendChild(document.createTextNode(title));
  if (sub) { const sm = document.createElement("small"); sm.textContent = sub; head.appendChild(sm); }
  return [head].concat(nodes);
}

// one row standing in for the whole list: scanning, or a reason there is nothing to show
export function nearbyNotice(text, action) {
  const li = document.createElement("li");
  li.className = action ? "act" : "hint";
  li.textContent = text;
  if (action) li.addEventListener("click", action);
  return li;
}

export const HINT_SHORT = "Tai hae paikkaa, osoitetta tai koordinaatteja.";
export const HINT_LONG = "Esim. ”Ylöjärvi Teivo”, ”Hämeenkatu 1 Tampere” tai ”61.4978 23.7610”.";

export function paintNearby(lead) { showSearchResults([], lead ? HINT_SHORT : HINT_LONG, lead); }

// Shared by the cache hit and the fresh scan: an empty result is a real answer, not the absence
// of one, and needs the same explanatory row every time it is shown — including on a cached
// empty array, which is truthy in JS and was otherwise painting as a silent blank list.
export function spotNodes(spots, at) {
  if (spots.length) return spots.map(s => nearbyRow(s, at));
  return [nearbyNotice(spots.cutOut
    ? "Sopivia kuvioita löytyi " + (NEARBY_RADIUS_M / 1000) + " km säteeltä, mutta ne on hakattu " +
      "äskettäin — kokeile poistaa ”Piilota hakatut kuviot” asetuksista."
    : "Ei yli " + MIN_SPOT_HA + " ha:n yhtenäisiä alueita " +
      (NEARBY_RADIUS_M / 1000) + " km säteellä — löysää suodattimia asetuksista.")];
}

export async function renderNearby() {
  const seq = ++nearby.seq;
  const species = sp();
  const at = await nearbyAnchor();
  if (seq !== nearby.seq || !nearbyWaiting()) return;
  nearby.anchor = at;

  const gps = at.src === "gps";
  const title = gps ? "Lähellä sinua" : "Lähellä karttanäkymää";
  const sub = (gps ? "" : "kartan keskeltä · ") +
    "yli " + MIN_SPOT_HA + " ha yhtenäistä metsää, jossa ehdot täyttyvät";
  // The one row in the panel that may raise a permission prompt, and only ever an offer: the list
  // above it is already there. Refocusing first keeps the panel open when the fix recentres the
  // map, and the repaint is left to gpsUpdate/gpsError, which know when there is something new.
  const locate = gps || at.reason === "unsupported" ? [] :
    [nearbyNotice("📍 Näytä omalta sijainnilta", () => { search.input.focus(); startGps(); })];
  const paint = nodes => paintNearby(nearbySection(title, nodes.concat(locate), sub));
  nearby.paint = paint;   // the name queue repaints through the newest one, never a captured one

  if (at.wide)
    return paint([nearbyNotice("Zoomaa lähemmäs — lista etsii " + (NEARBY_RADIUS_M / 1000) +
      " km säteeltä kartan keskipistettä.")]);
  if (species.maxLat != null && at.lat > species.maxLat)
    return paint([nearbyNotice(species.name + " ei kasva näin pohjoisessa")]);

  const key = nearbyKey(at);
  if (nearby.key === key && nearby.spots) {
    // distance and bearing are recomputed from the current anchor, so a cached list never shows
    // stale kilometres to someone who has walked, or panned, since
    paint(spotNodes(nearby.spots, at));
    return geocodeNearby(nearby.spots);   // rows still without a name are owed one
  }
  paint([nearbyNotice("Etsitään lähimpiä metsiä…")]);

  /* A scan is identified by the place it is scanning, never by the repaint counter. A GPS watch
     repaints the open panel about once a second, and every repaint bumped `seq`: the scan in
     flight was cancelled when it landed and a fresh one started behind it, so the list sat on
     "Etsitään…" for as long as the panel stayed open — five full-size WMS reads a second
     behind it, against a queue main sizes for six. Ticks that land on the same square now ride
     the scan already running, and the paint above is what they are here for anyway. */
  if (nearby.scanning === key) return;
  nearby.scanning = key;

  let spots;
  try {
    spots = await findNearbySpots(at);
  } catch (e) {
    if (nearby.scanning !== key) return;               // a different place is being scanned now
    nearby.scanning = null;
    if (nearbyWaiting())
      nearby.paint([nearbyNotice("Metsätietoa ei juuri nyt saatu — kokeile hetken päästä.")]);
    return;
  }
  if (nearby.scanning !== key) return;
  nearby.scanning = null;
  nearby.key = key; nearby.spots = spots;
  if (!nearbyWaiting()) return;
  // from here on the repaint is `nearby.paint`, not this render's: a scan outlives the repaint
  // that started it, and the heading and distances belong to whichever anchor is current now
  nearby.paint(spotNodes(spots, nearby.anchor));
  geocodeNearby(spots);
}

/* A view-anchored list follows the map, but a scan is five full-size reads off Luke's GeoServer,
   so it only re-runs once the view has genuinely moved somewhere else. Panning with the search
   field focused leaves the panel open (see the `movestart` handler in initSearch), which is
   exactly the case this covers. */
export function nearbyFollowMap() {
  const a = nearby.anchor;
  if (!nearbyWaiting() || !a || a.src !== "map") return;
  const b = map.getBounds();
  // zooming out of the country view is as much a move as panning is, even at the same centre
  if (a.wide !== (map.distance(b.getNorthWest(), b.getNorthEast()) > NEARBY_VIEW_MAX_M)) return renderNearby();
  if (map.distance(map.getCenter(), L.latLng(a.lat, a.lon)) < NEARBY_REANCHOR_M) return;
  renderNearby();
}

/* Names, filled in after the rows are already on screen — the list must never wait on the
   network. It repaints through `nearby.paint`, renderNearby's own repaint closed over the heading
   and the location row, so a row that gains a name cannot silently lose the section around it and
   a name landing late is still drawn from the newest anchor.

   What makes this queue current is the spot array it was handed, not `nearby.seq`: seq counts
   repaints, and with GPS on the watch repaints the open panel every second or so. Aborting on seq
   meant a phone with a live fix fetched one name and then kept bearings for the other two — the
   cached-list path never restarts the queue. The array only changes when a new scan replaces it,
   which is exactly when these names stop being the ones on screen.

   Nominatim allows one request a second, so these go out one at a time; zoom 14 asks
   for the village rather than the municipality, and where that still comes back the same for two
   spots the row keeps its distance-and-bearing title instead of repeating a name. */
export async function geocodeNearby(spots) {
  if (!spots.some(s => s.name === null)) return;      // the common case: a repaint with every name in
  // A queue from a superseded scan notices and stops within one courtesy pause. Waiting it out
  // beats returning: these rows would otherwise keep their bearings until the next scan.
  while (nearby.geocoding) {
    if (spots !== nearby.spots) return;
    await new Promise(res => setTimeout(res, 200));
  }
  const todo = spots.filter(s => s.name === null);    // `null` = not asked yet, "" = asked, no usable name
  if (!todo.length) return;
  nearby.geocoding = true;
  try {
    const seen = new Set(spots.map(s => s.name).filter(Boolean));
    for (const s of todo) {
      if (spots !== nearby.spots) return;
      try {
        const r = await fetch("https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14" +
          "&accept-language=fi&lat=" + s.lat.toFixed(5) + "&lon=" + s.lon.toFixed(5),
          { headers: { Accept: "application/json" } });
        const a = (r.ok ? await r.json() : {}).address || {};
        const place = a.village || a.hamlet || a.suburb || a.town || a.city_district || a.city;
        const admin = a.town || a.city;
        const title = !place ? "" : (admin && admin !== place) ? place + ", " + admin : place;
        // a forest often sits in the same village as the last one; repeating the name would make
        // three different places look like one, so that row keeps its bearing instead
        s.name = seen.has(title) ? "" : title;
        if (title) seen.add(title);
      } catch (e) { s.name = ""; }
      if (spots === nearby.spots && nearbyWaiting())
        nearby.paint(spots.map(x => nearbyRow(x, nearby.anchor)));
      await new Promise(res => setTimeout(res, 1100));   // Nominatim: at most one request a second
    }
  } finally { nearby.geocoding = false; }
}
