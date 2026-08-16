/**
 * Client for Suomen metsäkeskus open forest data (WFS / GeoServer).
 *
 * Two things about this service are hard to know ahead of time from a phone:
 * the axis order it applies to an EPSG:4326 bbox, and the exact attribute
 * spelling of a given layer version. So the client probes rather than assumes:
 * it retries an empty result with the axes swapped, remembers what worked, and
 * normalises attributes through an alias table that is matched case-insensitively.
 */

import { isCoarseSoil } from './codes.js';

export const DEFAULT_WFS = 'https://avoin.metsakeskus.fi/rajapinnat/v1/stands/ows';
export const DEFAULT_LAYER = 'stands:stand';

/** Remembered probe results, so the second request in a session is direct. */
const probe = { axis: null /* 'xy' | 'yx' */ };

export function resetProbe() { probe.axis = null; }

function withProxy(url, proxy) {
  if (!proxy) return url;
  return proxy.includes('{url}')
    ? proxy.replace('{url}', encodeURIComponent(url))
    : proxy + encodeURIComponent(url);
}

function buildUrl(base, params) {
  const u = new URL(base);
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
  return u.toString();
}

/* ── Attribute normalisation ────────────────────────────────────────── */

const ALIASES = {
  id:        ['standid', 'standnumber', 'id', 'kuvioid', 'gid'],
  fertility: ['fertilityclass', 'fertilityclasscode', 'kasvupaikka', 'kasvupaikkakoodi', 'sitetype'],
  species:   ['maintreespecies', 'maintreespeciescode', 'paapuulaji', 'mainspecies'],
  age:       ['meanage', 'age', 'keskiika', 'ika', 'agecalculated'],
  basalArea: ['basalarea', 'pohjapintaala', 'ppa'],
  height:    ['meanheight', 'keskipituus'],
  diameter:  ['meandiameter', 'keskilapimitta'],
  volume:    ['volume', 'tilavuus', 'stemvolume'],
  stems:     ['stemcount', 'runkoluku'],
  soil:      ['soiltype', 'soiltypecode', 'maalaji'],
  devClass:  ['developmentclass', 'developmentclasscode', 'kehitysluokka'],
  area:      ['area', 'pintaala'],
  drainage:  ['drainagestate', 'ojitustilanne'],
  updated:   ['updatetime', 'creationtime', 'inventorydate', 'datasource', 'datadate'],
};

function lowerKeyMap(props) {
  const m = new Map();
  for (const k of Object.keys(props || {})) m.set(k.toLowerCase().replace(/[_\s-]/g, ''), k);
  return m;
}

function pick(props, keyMap, names) {
  for (const n of names) {
    const real = keyMap.get(n);
    if (real !== undefined) {
      const v = props[real];
      if (v !== null && v !== undefined && v !== '') return v;
    }
  }
  return null;
}

const num = (v) => {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : parseFloat(String(v).replace(',', '.'));
  return isFinite(n) ? n : null;
};

/* ── Geometry helpers ───────────────────────────────────────────────── */

/**
 * GeoJSON must be [lon, lat], but a WFS asked for EPSG:4326 sometimes answers
 * in lat/lon. Finland sits at lon 19–32 / lat 59.5–70.2, and those ranges do
 * not overlap, so a single coordinate settles it unambiguously.
 */
function looksSwapped(coord) {
  const [a, b] = coord;
  return a > 45 && a < 75 && b > 15 && b < 40;
}

function walkCoords(geom, fn) {
  const rec = (c) => {
    if (typeof c[0] === 'number') return fn(c);
    for (const x of c) rec(x);
  };
  if (geom && geom.coordinates) rec(geom.coordinates);
}

function firstCoord(geom) {
  let found = null;
  walkCoords(geom, (c) => { if (!found) found = c; });
  return found;
}

function fixAxes(geom) {
  const f = firstCoord(geom);
  if (!f || !looksSwapped(f)) return geom;
  walkCoords(geom, (c) => { const t = c[0]; c[0] = c[1]; c[1] = t; });
  return geom;
}

/** Area-weighted centroid of a (Multi)Polygon, in [lon, lat]. */
export function centroidOf(geom) {
  if (!geom) return null;
  const rings = geom.type === 'Polygon' ? [geom.coordinates[0]]
    : geom.type === 'MultiPolygon' ? geom.coordinates.map((p) => p[0])
    : null;
  if (!rings) {
    const f = firstCoord(geom);
    return f ? [f[0], f[1]] : null;
  }
  let cx = 0, cy = 0, area2 = 0;
  for (const ring of rings) {
    for (let i = 0, n = ring.length - 1; i < n; i++) {
      const [x0, y0] = ring[i], [x1, y1] = ring[i + 1];
      const cross = x0 * y1 - x1 * y0;
      area2 += cross; cx += (x0 + x1) * cross; cy += (y0 + y1) * cross;
    }
  }
  if (Math.abs(area2) < 1e-12) {
    const f = firstCoord(geom);
    return f ? [f[0], f[1]] : null;
  }
  return [cx / (3 * area2), cy / (3 * area2)];
}

/** Rough bounding box of a geometry: [minLon, minLat, maxLon, maxLat]. */
export function bboxOf(geom) {
  let a = Infinity, b = Infinity, c = -Infinity, d = -Infinity;
  walkCoords(geom, ([x, y]) => {
    if (x < a) a = x; if (y < b) b = y;
    if (x > c) c = x; if (y > d) d = y;
  });
  return isFinite(a) ? [a, b, c, d] : null;
}

/* ── Normalisation ──────────────────────────────────────────────────── */

export function normaliseStand(feature) {
  const props = feature.properties || {};
  const km = lowerKeyMap(props);
  const geom = fixAxes(feature.geometry);
  const cen = centroidOf(geom);
  const soil = num(pick(props, km, ALIASES.soil));

  return {
    id: String(pick(props, km, ALIASES.id) ?? feature.id ?? Math.random().toString(36).slice(2)),
    geometry: geom,
    lon: cen ? cen[0] : null,
    lat: cen ? cen[1] : null,
    fertility: num(pick(props, km, ALIASES.fertility)),
    species: num(pick(props, km, ALIASES.species)),
    age: num(pick(props, km, ALIASES.age)),
    basalArea: num(pick(props, km, ALIASES.basalArea)),
    height: num(pick(props, km, ALIASES.height)),
    diameter: num(pick(props, km, ALIASES.diameter)),
    volume: num(pick(props, km, ALIASES.volume)),
    stems: num(pick(props, km, ALIASES.stems)),
    soil,
    coarseSoil: isCoarseSoil(soil),
    devClass: pick(props, km, ALIASES.devClass),
    area: num(pick(props, km, ALIASES.area)),
    updated: pick(props, km, ALIASES.updated),
    slope: null,   // filled in by terrain.js
    aspect: null,
    elevation: null,
    raw: props,
  };
}

/* ── Requests ───────────────────────────────────────────────────────── */

async function fetchJson(url, signal) {
  const res = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  const text = await res.text();
  if (!res.ok) {
    const detail = text.slice(0, 300).replace(/\s+/g, ' ').trim();
    throw new Error(`HTTP ${res.status}${detail ? ` — ${detail}` : ''}`);
  }
  if (text.trim().startsWith('<')) {
    // GeoServer answers exceptions as XML even when JSON was requested.
    const msg = /<ows:ExceptionText[^>]*>([\s\S]*?)<\/ows:ExceptionText>/i.exec(text)
             || /<ExceptionText[^>]*>([\s\S]*?)<\/ExceptionText>/i.exec(text);
    throw new Error(msg ? msg[1].trim().slice(0, 220) : 'Palvelin palautti XML-virheen');
  }
  return JSON.parse(text);
}

/**
 * Fetch stand polygons intersecting a bbox.
 * @param {{south:number,west:number,north:number,east:number}} b  WGS84 bounds
 */
export async function fetchStands(b, cfg, signal) {
  const base = cfg.wfsUrl || DEFAULT_WFS;
  const layer = cfg.layer || DEFAULT_LAYER;
  const count = cfg.count || 3000;

  const orders = probe.axis ? [probe.axis] : ['xy', 'yx'];
  let lastErr = null;

  for (const order of orders) {
    const bbox = order === 'xy'
      ? [b.west, b.south, b.east, b.north]
      : [b.south, b.west, b.north, b.east];

    const url = withProxy(buildUrl(base, {
      service: 'WFS',
      version: '2.0.0',
      request: 'GetFeature',
      typeNames: layer,
      srsName: 'EPSG:4326',
      outputFormat: 'application/json',
      count: String(count),
      bbox: `${bbox.map((v) => v.toFixed(6)).join(',')},EPSG:4326`,
    }), cfg.proxy);

    try {
      const json = await fetchJson(url, signal);
      const feats = json.features || [];
      if (feats.length === 0) {
        // Maybe the axes are the other way round — try the other order once.
        if (!probe.axis && order === 'xy') continue;
        // An empty answer proves nothing about axis order, so don't lock one in:
        // this may simply be a stretch of forest with no stands mapped.
        return { stands: [], truncated: false };
      }
      probe.axis = order;
      return {
        stands: feats.map(normaliseStand).filter((s) => s.geometry && s.lat != null),
        truncated: feats.length >= count,
      };
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      lastErr = err;
    }
  }

  if (lastErr) throw lastErr;
  return { stands: [], truncated: false };
}

/** Read GetCapabilities and list the layers the service publishes. */
export async function fetchLayers(cfg, signal) {
  const url = withProxy(buildUrl(cfg.wfsUrl || DEFAULT_WFS, {
    service: 'WFS', version: '2.0.0', request: 'GetCapabilities',
  }), cfg.proxy);

  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const xml = new DOMParser().parseFromString(await res.text(), 'application/xml');
  if (xml.querySelector('parsererror')) throw new Error('Vastausta ei voitu jäsentää');

  const names = [];
  for (const ft of xml.getElementsByTagName('*')) {
    if (ft.localName !== 'FeatureType') continue;
    for (const child of ft.children) {
      if (child.localName === 'Name' && child.textContent.trim()) {
        names.push(child.textContent.trim());
        break;
      }
    }
  }
  if (!names.length) throw new Error('Palvelu ei ilmoittanut yhtään kohdetasoa');
  return names;
}
