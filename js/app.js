/**
 * Matsutake Go — main application.
 *
 * Flow: the map moves → we ask the Forest Centre WFS for the stands inside the
 * view → each stand is scored against the matsutake habitat model → the ones
 * that pass are drawn as coloured polygons and, in the background, refined with
 * slope and aspect read from an elevation model.
 */

import { t, setLang, getLang, applyStatic } from './i18n.js';
import { fetchStands, fetchLayers, bboxOf, resetProbe, DEFAULT_WFS, DEFAULT_LAYER } from './wfs.js';
import { enrichStands, terrainState, disableTerrain } from './terrain.js';
import { scoreStand, scoreColor, DEFAULT_FILTERS } from './score.js';
import { renderStand, renderList, distanceBearing } from './sheet.js';
import { fertilityName } from './codes.js';
import * as wp from './waypoints.js';

const VERSION = '1.0.0';
const MIN_ZOOM = 12;
const FINLAND = { lat: 65.2, lng: 26.5, zoom: 5 };
const FINLAND_BOUNDS = [[59.3, 18.8], [70.4, 32.2]];

/* ── Config ─────────────────────────────────────────────────────────── */

const cfg = Object.assign({
  ...DEFAULT_FILTERS,
  wfsUrl: DEFAULT_WFS,
  layer: DEFAULT_LAYER,
  proxy: '',
  mmlKey: '',
  basemap: 'osm',
  showHabitat: true,
  autoscan: true,
}, JSON.parse(localStorage.getItem('mg.cfg') || '{}'));

const saveCfg = () => localStorage.setItem('mg.cfg', JSON.stringify(cfg));

/* ── State ──────────────────────────────────────────────────────────── */

const state = {
  stands: [],
  byId: new Map(),      // stand id → stand
  layerById: new Map(),
  shown: new Set(),
  visible: [],          // [{s, sc}] sorted by score, for the list view
  selected: null,
  fetchedBounds: null,
  abort: null,
  terrainAbort: null,
  gps: null,            // L.LatLng
  accuracy: null,
  heading: null,
  following: false,
  autoMoveUntil: 0,     // programmatic pans must not break the follow lock
  sheetMode: null,      // 'stand' | 'list'
};

/** setView that the movestart handler knows to ignore. */
function autoPan(latlng, zoom) {
  state.autoMoveUntil = Date.now() + 900;
  map.setView(latlng, zoom, { animate: true });
}

/* ── DOM shorthands ─────────────────────────────────────────────────── */

const $ = (id) => document.getElementById(id);
const statusText = $('status-text');
const statusDot = $('status-dot');

let toastTimer;
function toast(msg, ms = 3200) {
  const el = $('toast');
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, ms);
}

function status(text, kind = '') {
  statusText.textContent = text;
  statusDot.className = 'dot' + (kind ? ' ' + kind : '');
}

/* ── Map ────────────────────────────────────────────────────────────── */

const saved = JSON.parse(localStorage.getItem('mg.view') || 'null');
const start = saved || FINLAND;

const map = L.map('map', {
  center: [start.lat, start.lng],
  zoom: start.zoom,
  zoomControl: true,
  preferCanvas: true,
  maxZoom: 19,
  minZoom: 4,
  attributionControl: true,
  tap: false,
});

const BASEMAPS = {
  osm: {
    label: 'Peruskartta',
    layer: () => L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, maxNativeZoom: 19,
      attribution: '&copy; OpenStreetMap',
    }),
  },
  topo: {
    label: 'Maastokartta',
    layer: () => L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, maxNativeZoom: 17, subdomains: 'abc',
      attribution: '&copy; OpenTopoMap (CC-BY-SA)',
    }),
  },
  aerial: {
    label: 'Ilmakuva',
    layer: () => L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19, maxNativeZoom: 18,
        attribution: 'Imagery &copy; Esri',
      }),
  },
  mml: {
    label: 'MML maastokartta',
    needsKey: true,
    layer: () => L.tileLayer(
      'https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts/1.0.0/maastokartta/default/WGS84_Pseudo-Mercator/{z}/{y}/{x}.png?api-key=' +
      encodeURIComponent(cfg.mmlKey), {
        maxZoom: 19, maxNativeZoom: 18,
        attribution: '&copy; Maanmittauslaitos',
      }),
  },
  mmlOrtho: {
    label: 'MML ortoilmakuva',
    needsKey: true,
    layer: () => L.tileLayer(
      'https://avoin-karttakuva.maanmittauslaitos.fi/avoin/wmts/1.0.0/ortokuva/default/WGS84_Pseudo-Mercator/{z}/{y}/{x}.jpg?api-key=' +
      encodeURIComponent(cfg.mmlKey), {
        maxZoom: 19, maxNativeZoom: 18,
        attribution: '&copy; Maanmittauslaitos',
      }),
  },
};

let baseLayer = null;
function setBasemap(key) {
  const def = BASEMAPS[key] || BASEMAPS.osm;
  if (def.needsKey && !cfg.mmlKey) return setBasemap('osm');
  if (baseLayer) map.removeLayer(baseLayer);
  baseLayer = def.layer().addTo(map);
  baseLayer.bringToBack();
  cfg.basemap = BASEMAPS[key] ? key : 'osm';
  saveCfg();
  renderBasemapButtons();
}

const habitatGroup = L.layerGroup().addTo(map);

/* ── GPS ────────────────────────────────────────────────────────────── */

const gpsIcon = L.divIcon({
  className: 'gps-dot',
  html: '<span class="pulse"></span><span class="cone" hidden></span><span class="core"></span>',
  iconSize: [0, 0],
});
let gpsMarker = null, accCircle = null, watchId = null;

function updateGpsVisual() {
  if (!state.gps) return;
  if (!gpsMarker) {
    gpsMarker = L.marker(state.gps, { icon: gpsIcon, interactive: false, zIndexOffset: 1000 }).addTo(map);
    accCircle = L.circle(state.gps, {
      radius: state.accuracy || 0, color: '#2f8dff', weight: 1,
      fillColor: '#2f8dff', fillOpacity: 0.1, interactive: false,
    }).addTo(map);
  } else {
    gpsMarker.setLatLng(state.gps);
    accCircle.setLatLng(state.gps).setRadius(state.accuracy || 0);
  }
  const cone = gpsMarker.getElement()?.querySelector('.cone');
  if (cone) {
    if (state.heading == null) cone.hidden = true;
    else { cone.hidden = false; cone.style.transform = `rotate(${state.heading + 180}deg)`; }
  }
}

function startGps() {
  if (!navigator.geolocation) return toast(t('toast.gpsUnavailable'));
  if (watchId != null) return;
  status(t('toast.gpsSearching'), 'busy');
  watchId = navigator.geolocation.watchPosition(
    (pos) => {
      const { latitude, longitude, accuracy, heading, speed } = pos.coords;
      state.gps = L.latLng(latitude, longitude);
      state.accuracy = accuracy;
      if (heading != null && !isNaN(heading) && speed > 0.6) state.heading = heading;
      updateGpsVisual();
      if (state.following) autoPan(state.gps, Math.max(map.getZoom(), 14));
      if (statusDot.classList.contains('busy') && statusText.textContent === t('toast.gpsSearching')) {
        status(t('st.ready'), 'ok');
      }
    },
    (err) => {
      if (err.code === err.PERMISSION_DENIED) toast(t('toast.gpsDenied'), 5000);
      else toast(t('toast.gpsUnavailable'), 4000);
      state.following = false;
      $('btn-locate').classList.remove('following');
    },
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 }
  );
}

function enableCompass() {
  const handler = (e) => {
    const h = e.webkitCompassHeading ?? (e.absolute && e.alpha != null ? 360 - e.alpha : null);
    if (h != null && isFinite(h)) { state.heading = h; updateGpsVisual(); }
  };
  if (typeof DeviceOrientationEvent !== 'undefined' &&
      typeof DeviceOrientationEvent.requestPermission === 'function') {
    DeviceOrientationEvent.requestPermission()
      .then((r) => { if (r === 'granted') window.addEventListener('deviceorientation', handler); })
      .catch(() => {});
  } else {
    window.addEventListener('deviceorientationabsolute', handler);
    window.addEventListener('deviceorientation', handler);
  }
}

/* ── Habitat scanning ───────────────────────────────────────────────── */

function boundsToWgs(b) {
  return { south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() };
}

let scanTimer = null;
function scheduleScan(delay = 500) {
  clearTimeout(scanTimer);
  scanTimer = setTimeout(() => scan(false), delay);
}

async function scan(force) {
  if (!cfg.showHabitat) return;

  if (map.getZoom() < MIN_ZOOM) {
    clearHabitat();
    status(t('st.zoomIn'));
    $('scan-cta').hidden = true;
    return;
  }

  const view = map.getBounds();
  if (!force && state.fetchedBounds && state.fetchedBounds.contains(view)) {
    renderHabitat();
    return;
  }
  if (!L.latLngBounds(FINLAND_BOUNDS).intersects(view)) {
    clearHabitat();
    status(t('toast.outsideFinland'));
    return;
  }
  if (!navigator.onLine) {
    status(t('st.offline'), 'err');
    return;
  }

  state.abort?.abort();
  state.terrainAbort?.abort();
  const ac = new AbortController();
  state.abort = ac;

  const padded = view.pad(0.25);
  status(t('st.loading'), 'busy');
  $('scan-cta').hidden = true;

  try {
    const { stands, truncated } = await fetchStands(boundsToWgs(padded), cfg, ac.signal);
    if (ac.signal.aborted) return;

    state.stands = stands;
    state.fetchedBounds = padded;
    renderHabitat();

    if (truncated) toast(t('toast.truncated'));

    if (cfg.useTerrain && !terrainState.disabled) {
      refineTerrain();
    }
  } catch (err) {
    if (err.name === 'AbortError') return;
    console.warn('[matsutake] WFS failed', err);
    status(t('st.error'), 'err');
    toast(`${t('st.error')}: ${err.message}`, 6000);
    $('scan-cta').hidden = false;
  }
}

async function refineTerrain() {
  const ac = new AbortController();
  state.terrainAbort = ac;

  // Only the stands that already cleared the hard gates are worth the tiles.
  const candidates = state.stands
    .map((s) => ({ s, sc: scoreStand(s, cfg) }))
    .filter((x) => x.sc.pass)
    .sort((a, b) => b.sc.score - a.sc.score)
    .slice(0, 260)
    .map((x) => x.s);

  if (!candidates.length) return;
  status(t('st.terrain'), 'busy');

  let repaint;
  await enrichStands(candidates, () => {
    clearTimeout(repaint);
    repaint = setTimeout(() => { if (!ac.signal.aborted) restyleHabitat(); }, 250);
  }, ac.signal);

  if (ac.signal.aborted) return;
  clearTimeout(repaint);

  if (terrainState.disabled && terrainState.ok === 0) {
    toast(t('toast.terrainOff'), 5000);
  }
  renderHabitat();

  // A sheet opened mid-scan would otherwise keep showing "—" for the slope.
  if (state.selected && state.sheetMode === 'stand') selectStand(state.selected);
}

function clearHabitat() {
  habitatGroup.clearLayers();
  state.layerById.clear();
  state.shown.clear();
  state.byId.clear();
  state.stands = [];
  state.visible = [];
  state.fetchedBounds = null;
  updateListBadge();
}

function styleFor(sc, selected) {
  const c = scoreColor(sc.score);
  return {
    color: selected ? '#ffffff' : c,
    weight: selected ? 3 : 1.5,
    opacity: 0.95,
    fillColor: c,
    fillOpacity: sc.score >= 75 ? 0.55 : 0.42,
  };
}

/** Rebuild the habitat layer from scratch (filters changed, or new data). */
function renderHabitat() {
  habitatGroup.clearLayers();
  state.layerById.clear();
  state.shown.clear();
  state.byId = new Map(state.stands.map((s) => [s.id, s]));

  const scored = [];
  for (const s of state.stands) {
    const sc = scoreStand(s, cfg);
    if (!sc.pass) continue;
    scored.push({ s, sc });

    const layer = L.geoJSON(
      { type: 'Feature', geometry: s.geometry, properties: {} },
      { style: styleFor(sc, false), smoothFactor: 1, bubblingMouseEvents: false }
    );
    layer.on('click', (ev) => {
      L.DomEvent.stopPropagation(ev);   // otherwise the map click closes the sheet again
      selectStand(s.id);
    });
    state.layerById.set(s.id, layer);
    if (sc.score >= cfg.minScore) { habitatGroup.addLayer(layer); state.shown.add(s.id); }
  }

  scored.sort((a, b) => b.sc.score - a.sc.score);
  state.visible = scored.filter((x) => x.sc.score >= cfg.minScore);

  const n = state.visible.length;
  status(n ? t('st.found', n, false) : t('st.none'), n ? 'ok' : '');
  updateListBadge();

  if (state.selected) highlight(state.selected);
}

/** Cheap update after terrain data arrives — no geometry rebuild. */
function restyleHabitat() {
  const scored = [];
  for (const s of state.stands) {
    const layer = state.layerById.get(s.id);
    if (!layer) continue;
    const sc = scoreStand(s, cfg);
    if (!sc.pass) {
      if (state.shown.has(s.id)) { habitatGroup.removeLayer(layer); state.shown.delete(s.id); }
      continue;
    }
    scored.push({ s, sc });
    const want = sc.score >= cfg.minScore;
    if (want && !state.shown.has(s.id)) { habitatGroup.addLayer(layer); state.shown.add(s.id); }
    if (!want && state.shown.has(s.id)) { habitatGroup.removeLayer(layer); state.shown.delete(s.id); }
    if (want) layer.setStyle(styleFor(sc, s.id === state.selected));
  }
  scored.sort((a, b) => b.sc.score - a.sc.score);
  state.visible = scored.filter((x) => x.sc.score >= cfg.minScore);
  updateListBadge();
}

function updateListBadge() {
  const badge = $('list-badge');
  const n = state.visible.length;
  badge.textContent = n > 99 ? '99+' : String(n);
  badge.hidden = n === 0;
}

function highlight(id) {
  for (const sid of state.shown) {
    const s = state.byId.get(sid);
    const layer = state.layerById.get(sid);
    if (s && layer) layer.setStyle(styleFor(scoreStand(s, cfg), sid === id));
  }
}

/* ── Sheet ──────────────────────────────────────────────────────────── */

/**
 * The sheet deliberately has no scrim: in the forest you want to keep panning
 * the map while a stand's details are open. Instead the map stays live and a
 * tap on it dismisses the sheet.
 */
function openSheet(html, mode) {
  const sheet = $('sheet');
  $('sheet-content').innerHTML = html;
  $('sheet-content').scrollTop = 0;
  sheet.classList.add('open');
  sheet.setAttribute('aria-hidden', 'false');
  state.sheetMode = mode;

  // Lift the locate button clear of the sheet so it stays thumb-reachable.
  requestAnimationFrame(() => {
    document.documentElement.style.setProperty('--sheet-h', `${sheet.offsetHeight}px`);
    document.body.classList.add('sheet-open');
  });
}

function closeSheet() {
  $('sheet').classList.remove('open');
  $('sheet').setAttribute('aria-hidden', 'true');
  document.body.classList.remove('sheet-open');
  state.sheetMode = null;
  if (state.selected) { state.selected = null; highlight(null); }
}

function selectStand(id, opts = {}) {
  const s = state.byId.get(id);
  if (!s) return;
  state.selected = id;
  highlight(id);
  const sc = scoreStand(s, cfg);
  const distance = state.gps ? distanceBearing(state.gps, { lat: s.lat, lng: s.lon }).dist : null;
  openSheet(renderStand(s, sc, { saved: wp.has(s.id), distance }), 'stand');
  if (opts.pan) {
    const bb = bboxOf(s.geometry);
    if (bb) map.fitBounds([[bb[1], bb[0]], [bb[3], bb[2]]], { maxZoom: 16, padding: [40, 240] });
  }
}

function openList() {
  const items = state.visible.slice(0, 60);
  openSheet(renderList(items, { from: state.gps }), 'list');
}

/* ── Sheet interactions ─────────────────────────────────────────────── */

$('sheet-content').addEventListener('click', (ev) => {
  const item = ev.target.closest('.rl-item');
  if (item && state.sheetMode === 'list') {
    const idx = Number(item.dataset.idx);
    const entry = state.visible[idx];
    if (entry) selectStand(entry.s.id, { pan: true });
    return;
  }
  const saveBtn = ev.target.closest('[data-act="save"]');
  if (saveBtn && state.selected) {
    const s = state.byId.get(state.selected);
    if (!s) return;
    const sc = scoreStand(s, cfg);
    const added = wp.toggle({
      id: s.id, lat: s.lat, lon: s.lon, score: sc.score, age: s.age, slope: s.slope,
      fertilityName: fertilityName(s.fertility, getLang()),
      name: `${sc.score} · ${fertilityName(s.fertility, getLang())}`,
    });
    toast(t(added ? 'toast.saved' : 'toast.removed'), 1800);
    selectStand(s.id);
    renderWaypoints();
  }
});

map.on('click', closeSheet);

// Drag the grip down to dismiss.
(() => {
  const sheet = $('sheet');
  let y0 = null, dy = 0;
  const grip = $('sheet-grip');
  grip.addEventListener('pointerdown', (e) => {
    y0 = e.clientY; dy = 0;
    sheet.style.transition = 'none';
    grip.setPointerCapture(e.pointerId);
  });
  grip.addEventListener('pointermove', (e) => {
    if (y0 == null) return;
    dy = Math.max(0, e.clientY - y0);
    sheet.style.transform = `translateY(${dy}px)`;
  });
  const end = () => {
    if (y0 == null) return;
    sheet.style.transition = '';
    sheet.style.transform = '';
    if (dy > 90) closeSheet();
    y0 = null;
  };
  grip.addEventListener('pointerup', end);
  grip.addEventListener('pointercancel', end);
})();

/* ── Drawer & settings ──────────────────────────────────────────────── */

function openDrawer() {
  $('drawer').classList.add('open');
  $('drawer').setAttribute('aria-hidden', 'false');
  $('scrim').hidden = false;
  renderWaypoints();
}
function closeDrawer() {
  $('drawer').classList.remove('open');
  $('drawer').setAttribute('aria-hidden', 'true');
  $('scrim').hidden = true;
}

$('btn-menu').addEventListener('click', openDrawer);
$('btn-close-drawer').addEventListener('click', closeDrawer);
$('scrim').addEventListener('click', closeDrawer);

function syncControls() {
  $('in-age').value = cfg.minAge;
  $('out-age').textContent = `${cfg.minAge} v`;
  $('in-score').value = cfg.minScore;
  $('out-score').textContent = cfg.minScore;
  $('in-pine').checked = cfg.pineOnly;
  $('in-slope').checked = cfg.requireSlope;
  $('in-terrain').checked = cfg.useTerrain;
  $('in-autoscan').checked = cfg.autoscan;
  $('in-wfs').value = cfg.wfsUrl;
  $('in-layer').value = cfg.layer;
  $('in-proxy').value = cfg.proxy;
  $('in-mml').value = cfg.mmlKey;
  $('in-show-habitat').checked = cfg.showHabitat;
  document.querySelectorAll('#chips-fertility .chip').forEach((c) => {
    c.classList.toggle('on', cfg.fertility.includes(Number(c.dataset.ft)));
  });
}

$('in-age').addEventListener('input', (e) => {
  cfg.minAge = Number(e.target.value);
  $('out-age').textContent = `${cfg.minAge} v`;
});
$('in-age').addEventListener('change', () => { saveCfg(); renderHabitat(); });

$('in-score').addEventListener('input', (e) => {
  cfg.minScore = Number(e.target.value);
  $('out-score').textContent = cfg.minScore;
  restyleHabitat();
});
$('in-score').addEventListener('change', saveCfg);

$('in-pine').addEventListener('change', (e) => { cfg.pineOnly = e.target.checked; saveCfg(); renderHabitat(); });
$('in-slope').addEventListener('change', (e) => { cfg.requireSlope = e.target.checked; saveCfg(); renderHabitat(); });
$('in-autoscan').addEventListener('change', (e) => { cfg.autoscan = e.target.checked; saveCfg(); });
$('in-terrain').addEventListener('change', (e) => {
  cfg.useTerrain = e.target.checked;
  saveCfg();
  if (cfg.useTerrain && !terrainState.disabled) refineTerrain();
});

$('chips-fertility').addEventListener('click', (ev) => {
  const chip = ev.target.closest('.chip');
  if (!chip) return;
  const code = Number(chip.dataset.ft);
  const i = cfg.fertility.indexOf(code);
  if (i >= 0) { if (cfg.fertility.length === 1) return; cfg.fertility.splice(i, 1); }
  else cfg.fertility.push(code);
  chip.classList.toggle('on');
  saveCfg();
  renderHabitat();
});

$('in-wfs').addEventListener('change', (e) => { cfg.wfsUrl = e.target.value.trim() || DEFAULT_WFS; resetProbe(); saveCfg(); });
$('in-layer').addEventListener('change', (e) => { cfg.layer = e.target.value.trim() || DEFAULT_LAYER; saveCfg(); });
$('in-proxy').addEventListener('change', (e) => { cfg.proxy = e.target.value.trim(); resetProbe(); saveCfg(); });
$('in-mml').addEventListener('change', (e) => {
  cfg.mmlKey = e.target.value.trim();
  saveCfg();
  renderBasemapButtons();
  if (!cfg.mmlKey && BASEMAPS[cfg.basemap]?.needsKey) setBasemap('osm');
});

$('btn-reset-src').addEventListener('click', () => {
  cfg.wfsUrl = DEFAULT_WFS; cfg.layer = DEFAULT_LAYER; cfg.proxy = '';
  resetProbe(); saveCfg(); syncControls();
  $('test-out').className = 'test-out'; $('test-out').textContent = '';
});

$('btn-test').addEventListener('click', async () => {
  const out = $('test-out');
  out.className = 'test-out';
  out.textContent = '…';
  try {
    const names = await fetchLayers(cfg);
    const dl = $('layer-list');
    dl.innerHTML = names.map((n) => `<option value="${n}"></option>`).join('');
    out.className = 'test-out ok';
    out.textContent = `OK — ${names.length} tasoa:\n${names.slice(0, 12).join('\n')}`;
    if (!names.includes(cfg.layer)) {
      const guess = names.find((n) => /stand|kuvio/i.test(n));
      if (guess) { cfg.layer = guess; saveCfg(); syncControls(); out.textContent += `\n\nValittiin: ${guess}`; }
    }
  } catch (err) {
    out.className = 'test-out err';
    out.textContent = `Virhe: ${err.message}\n\nJos syynä on CORS, kokeile välityspalvelinta alla.`;
  }
});

$('btn-lang').addEventListener('click', () => {
  const next = getLang() === 'fi' ? 'en' : 'fi';
  setLang(next);
  $('btn-lang').textContent = next === 'fi' ? 'In English' : 'Suomeksi';
  $('out-age').textContent = `${cfg.minAge} ${next === 'fi' ? 'v' : 'yr'}`;
  renderWaypoints();
  if (state.sheetMode === 'list') openList();
  else if (state.selected) selectStand(state.selected);
});

/* ── Waypoints UI ───────────────────────────────────────────────────── */

function renderWaypoints() {
  const list = wp.all();
  $('wp-count').textContent = list.length;
  $('wp-list').innerHTML = list.length
    ? list.map((w) => `<div class="wp-item">
        <button class="wp-go" data-lat="${w.lat}" data-lon="${w.lon}">
          <b>${w.name.replace(/</g, '&lt;')}</b>
          <small>${w.lat.toFixed(5)}, ${w.lon.toFixed(5)}</small>
        </button>
        <button class="wp-del" data-del="${w.id}" aria-label="Poista">
          <svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13"/></svg>
        </button>
      </div>`).join('')
    : `<p class="muted small">${t('toast.noWaypoints')}</p>`;
}

$('wp-list').addEventListener('click', (ev) => {
  const del = ev.target.closest('[data-del]');
  if (del) { wp.remove(del.dataset.del); renderWaypoints(); return; }
  const go = ev.target.closest('.wp-go');
  if (go) {
    closeDrawer();
    map.setView([Number(go.dataset.lat), Number(go.dataset.lon)], 15);
  }
});

$('btn-export-gpx').addEventListener('click', async () => {
  if (!(await wp.exportGpx())) toast(t('toast.noWaypoints'));
});
$('btn-clear-wp').addEventListener('click', () => {
  if (!wp.all().length) return toast(t('toast.noWaypoints'));
  if (confirm(t('wp.confirmClear'))) { wp.clear(); renderWaypoints(); toast(t('toast.cleared')); }
});

/* ── Layers popover ─────────────────────────────────────────────────── */

function renderBasemapButtons() {
  const host = $('basemaps');
  host.innerHTML = Object.entries(BASEMAPS)
    .filter(([, d]) => !d.needsKey || cfg.mmlKey)
    .map(([k, d]) => `<button class="bm${k === cfg.basemap ? ' on' : ''}" data-bm="${k}">${d.label}</button>`)
    .join('');
}

$('basemaps').addEventListener('click', (ev) => {
  const b = ev.target.closest('[data-bm]');
  if (b) setBasemap(b.dataset.bm);
});

$('btn-layers').addEventListener('click', () => {
  const pop = $('layers-pop');
  pop.hidden = !pop.hidden;
});
document.addEventListener('click', (ev) => {
  const pop = $('layers-pop');
  if (!pop.hidden && !pop.contains(ev.target) && !ev.target.closest('#btn-layers')) pop.hidden = true;
});

$('in-show-habitat').addEventListener('change', (e) => {
  cfg.showHabitat = e.target.checked;
  saveCfg();
  if (cfg.showHabitat) { map.addLayer(habitatGroup); scan(true); }
  else map.removeLayer(habitatGroup);
});

/* ── Buttons ────────────────────────────────────────────────────────── */

$('btn-locate').addEventListener('click', () => {
  if (!watchId) { startGps(); enableCompass(); }
  state.following = !state.following;
  $('btn-locate').classList.toggle('following', state.following);
  if (state.gps && state.following) autoPan(state.gps, Math.max(map.getZoom(), 14));
  else if (!state.gps) toast(t('toast.gpsSearching'), 2000);
});

$('btn-scan').addEventListener('click', () => scan(true));
$('scan-cta').addEventListener('click', () => scan(true));
$('btn-list').addEventListener('click', () => {
  if (state.sheetMode === 'list') closeSheet(); else openList();
});

$('legend-toggle').addEventListener('click', () => {
  $('legend').classList.toggle('closed');
  localStorage.setItem('mg.legend', $('legend').classList.contains('closed') ? '0' : '1');
});

/* ── Map events ─────────────────────────────────────────────────────── */

map.on('dragstart', () => {
  // A manual drag breaks the follow lock, exactly like a car navigator.
  if (state.following && Date.now() > state.autoMoveUntil) {
    state.following = false;
    $('btn-locate').classList.remove('following');
  }
});

map.on('moveend zoomend', () => {
  const c = map.getCenter();
  localStorage.setItem('mg.view', JSON.stringify({ lat: c.lat, lng: c.lng, zoom: map.getZoom() }));
  if (cfg.autoscan) scheduleScan();
  else if (map.getZoom() >= MIN_ZOOM) $('scan-cta').hidden = false;
});

window.addEventListener('online', () => { if (cfg.autoscan) scan(true); });
window.addEventListener('offline', () => status(t('st.offline'), 'err'));

/* ── Boot ───────────────────────────────────────────────────────────── */

setLang(getLang());
$('btn-lang').textContent = getLang() === 'fi' ? 'In English' : 'Suomeksi';
$('version').textContent = `v${VERSION}`;
if (localStorage.getItem('mg.legend') === '0') $('legend').classList.add('closed');

syncControls();
setBasemap(cfg.basemap);
renderWaypoints();
status(t('st.ready'), 'ok');

if (!saved) map.fitBounds(FINLAND_BOUNDS);
if (map.getZoom() >= MIN_ZOOM && cfg.autoscan) scheduleScan(200);
else if (map.getZoom() < MIN_ZOOM) status(t('st.zoomIn'));

// Ask for a fix straight away — the app is useless without knowing where you are.
if (navigator.permissions?.query) {
  navigator.permissions.query({ name: 'geolocation' })
    .then((p) => { if (p.state === 'granted') { startGps(); } })
    .catch(() => {});
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  });
}

// Expose a little of the internals for debugging in the field console.
window.matsutake = {
  map, state, cfg, scan, scoreStand, disableTerrain,
  renderHabitat, restyleHabitat, selectStand, openList, VERSION,
};
