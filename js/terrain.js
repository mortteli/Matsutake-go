/**
 * Slope and aspect from Terrarium terrain-RGB tiles.
 *
 * "Preferably some sloping" is the one criterion the forest database cannot
 * answer, so we read it off a digital elevation model instead. The AWS Open
 * Data Terrarium tiles are global, CORS-enabled and free, and over Finland
 * they carry the national 2 m elevation model resampled — plenty for judging
 * whether a stand sits on an esker shoulder or on a flat plain.
 *
 * Encoding: elevation (m) = R * 256 + G + B / 256 − 32768.
 */

const TILE_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
const TILE_SIZE = 256;
const DEM_ZOOM = 12;          // ≈17 m/px at 64 °N
const SAMPLE_STEP_PX = 2;     // ≈33 m baseline — stand scale, not boulder scale
const MAX_TILES = 48;
const MAX_PARALLEL = 4;

const cache = new Map();      // "z/x/y" → Promise<Float32Array|null>
let inFlight = 0;
const queue = [];
let disabled = false;

export const terrainState = { failures: 0, ok: 0, get disabled() { return disabled; } };

export function disableTerrain() { disabled = true; }

function pump() {
  while (inFlight < MAX_PARALLEL && queue.length) queue.shift()();
}

function loadTile(z, x, y) {
  const key = `${z}/${x}/${y}`;
  const hit = cache.get(key);
  if (hit) { cache.delete(key); cache.set(key, hit); return hit; }   // LRU touch

  const promise = new Promise((resolve) => {
    const start = () => {
      inFlight++;
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.decoding = 'async';
      const done = (val) => { inFlight--; pump(); resolve(val); };
      img.onload = () => {
        try {
          const cv = document.createElement('canvas');
          cv.width = TILE_SIZE; cv.height = TILE_SIZE;
          const ctx = cv.getContext('2d', { willReadFrequently: true });
          ctx.drawImage(img, 0, 0, TILE_SIZE, TILE_SIZE);
          const d = ctx.getImageData(0, 0, TILE_SIZE, TILE_SIZE).data;
          const out = new Float32Array(TILE_SIZE * TILE_SIZE);
          for (let i = 0, p = 0; i < out.length; i++, p += 4) {
            out[i] = d[p] * 256 + d[p + 1] + d[p + 2] / 256 - 32768;
          }
          terrainState.ok++;
          done(out);
        } catch {
          terrainState.failures++;
          done(null);   // tainted canvas — CORS not granted
        }
      };
      img.onerror = () => { terrainState.failures++; done(null); };
      img.src = TILE_URL.replace('{z}', z).replace('{x}', x).replace('{y}', y);
    };
    queue.push(start);
    pump();
  });

  cache.set(key, promise);
  while (cache.size > MAX_TILES) cache.delete(cache.keys().next().value);
  return promise;
}

/* ── Web-mercator pixel maths ───────────────────────────────────────── */

function project(lon, lat, z) {
  const n = TILE_SIZE * Math.pow(2, z);
  const x = ((lon + 180) / 360) * n;
  const s = Math.sin((lat * Math.PI) / 180);
  const y = (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * n;
  return [x, y];
}

/** Metres per DEM pixel at a given latitude. */
function pixelMetres(lat, z) {
  return (156543.03392 * Math.cos((lat * Math.PI) / 180)) / Math.pow(2, z);
}

async function elevationAt(lon, lat, z) {
  const [px, py] = project(lon, lat, z);
  const tx = Math.floor(px / TILE_SIZE);
  const ty = Math.floor(py / TILE_SIZE);
  const max = Math.pow(2, z);
  if (ty < 0 || ty >= max) return null;
  const data = await loadTile(z, ((tx % max) + max) % max, ty);
  if (!data) return null;
  const ix = Math.min(TILE_SIZE - 1, Math.max(0, Math.floor(px - tx * TILE_SIZE)));
  const iy = Math.min(TILE_SIZE - 1, Math.max(0, Math.floor(py - ty * TILE_SIZE)));
  const v = data[iy * TILE_SIZE + ix];
  return v < -1000 ? null : v;
}

/**
 * Slope (degrees), aspect (degrees clockwise from north) and elevation at a
 * point, using Horn's 3×3 kernel over a ~33 m baseline.
 * @returns {Promise<{slope:number, aspect:number|null, elevation:number}|null>}
 */
export async function terrainAt(lon, lat, z = DEM_ZOOM) {
  if (disabled) return null;
  const d = pixelMetres(lat, z) * SAMPLE_STEP_PX;
  const dLat = d / 111320;
  const dLon = d / (111320 * Math.cos((lat * Math.PI) / 180) || 1);

  const grid = await Promise.all(
    [1, 0, -1].flatMap((j) => [-1, 0, 1].map((i) => elevationAt(lon + i * dLon, lat + j * dLat, z)))
  );
  if (grid.some((v) => v == null)) return null;

  // Grid is row-major with the north row first:
  //   nw n ne        Horn's kernel, as used by ESRI:
  //   w  c  e          dz/dx = ((ne + 2e + se) − (nw + 2w + sw)) / 8d
  //   sw s se          dz/dy = ((sw + 2s + se) − (nw + 2n + ne)) / 8d
  const [nw, n, ne, w, c, e, sw, s, se] = grid;
  const dzdx = ((ne + 2 * e + se) - (nw + 2 * w + sw)) / (8 * d);
  const dzdy = ((sw + 2 * s + se) - (nw + 2 * n + ne)) / (8 * d);

  const grad = Math.hypot(dzdx, dzdy);
  const slope = (Math.atan(grad) * 180) / Math.PI;

  // Aspect points downhill: 0° = north, increasing clockwise.
  let aspect = null;
  if (grad > 1e-4) {
    const a = (Math.atan2(dzdy, -dzdx) * 180) / Math.PI;
    aspect = a < 0 ? 90 - a : a > 90 ? 450 - a : 90 - a;
    aspect = ((aspect % 360) + 360) % 360;
  }

  return { slope, aspect, elevation: c };
}

/**
 * Fill in slope/aspect/elevation for a list of stands, most promising first.
 * @param {Array} stands           normalised stands (mutated in place)
 * @param {(n:number)=>void} onTick called every few stands so the map can repaint
 */
export async function enrichStands(stands, onTick, signal) {
  if (disabled || !stands.length) return;
  let done = 0;
  const batch = 6;

  for (let i = 0; i < stands.length; i += batch) {
    if (signal?.aborted) return;
    const slice = stands.slice(i, i + batch);
    await Promise.all(slice.map(async (s) => {
      if (s.slope != null || s.lat == null) return;
      const t = await terrainAt(s.lon, s.lat);
      if (t) { s.slope = t.slope; s.aspect = t.aspect; s.elevation = t.elevation; }
    }));
    done += slice.length;

    // Give up quickly and quietly if the DEM host is unreachable.
    if (terrainState.ok === 0 && terrainState.failures >= 3) { disabled = true; return; }
    onTick?.(done);
  }
}
