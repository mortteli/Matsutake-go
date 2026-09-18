import { DIR8 } from "./constants.js";
import { toTM35 } from "./geo.js";
import { ensureGeoraster } from "./problayer.js";
import { readBlockAt } from "./rasterread.js";

/* ================= slope and aspect =================
   Baked when the site publishes it, live only when it does not.

   The baked layer is the MML 10 m elevation model that ml/build_dem16.py already warps onto the
   16 m analysis grid for training, exported by ml/export_terrain.py and read with range requests
   exactly like the probability raster. It answers a tap with no external call at all, it makes
   the slope in the sheet the same slope the model scored, and it is the last piece the result
   sheet needed to work with every live API blocked.

   Open-Meteo remains the fallback for a deployment that has not run the export. It is one
   request per tap, well inside its free tier — but it serves Copernicus GLO-90, so it describes
   ~90 m of ground where the model used 10 m, and the two can honestly disagree. */
export const terrain = { meta: null, load: null, parts: [] };
export const TERRAIN_META = "data/terrain/terrain_meta.json";
export const SLOPE_TIMEOUT_MS = 6000;

// null (once, cached) when no terrain layer is published — the fallback is then permanent and
// costs no repeated 404
export function terrainReady() {
  if (!terrain.load) terrain.load = fetch(TERRAIN_META)
    .then(r => r.ok ? r.json() : Promise.reject(new Error("no terrain layer")))
    .then(m => ensureGeoraster().then(() => {
      terrain.meta = m;
      terrain.parts = m.files.map(() => null);
      return m;
    }))
    .catch(() => null);
  return terrain.load;
}
// parts are parsed on demand: a tap needs the one part it lands in, not all nine headers
export function terrainPart(meta, i) {
  if (!terrain.parts[i])
    terrain.parts[i] = parseGeoraster(new URL(meta.files[i].url, location.href).href).catch(() => null);
  return terrain.parts[i];
}
/* Downslope gradient -> what the sheet shows. `gx` is the eastward and `gy` the *southward*
   derivative in metres per metre, which is the orientation ml/features.py's np.gradient uses when
   it builds the model's own slope and aspect features — one convention, two call sites. */
export function slopeOf(gx, gy) {
  const bearing = (Math.atan2(-gx, gy) * 180 / Math.PI + 360) % 360;   // downslope, 0 = north
  return { deg: Math.atan(Math.hypot(gx, gy)) * 180 / Math.PI, dir: DIR8[Math.round(bearing / 45) % 8] };
}
export async function readSlopeBaked(meta, latlng) {
  const { x, y } = toTM35(latlng.lat, latlng.lng);
  const i = meta.files.findIndex(f => x >= f.bounds[0] && x <= f.bounds[2] &&
                                      y >= f.bounds[1] && y <= f.bounds[3]);
  if (i < 0) return null;                                   // sea, or outside the published area
  const gr = await terrainPart(meta, i);
  if (!gr) return null;
  const z = await readBlockAt([gr], x, y, 1);
  if (!z) return null;
  const scale = meta.scale || 0.1, cell = gr.pixelWidth;    // stored decimetres -> metres
  const at = (r, c) => (z[r][c] == null || z[r][c] === meta.nodata) ? NaN : z[r][c] * scale;
  const gx = (at(1, 2) - at(1, 0)) / (2 * cell), gy = (at(2, 1) - at(0, 1)) / (2 * cell);
  return isFinite(gx) && isFinite(gy) ? slopeOf(gx, gy) : null;
}
export async function readSlopeRemote(latlng) {
  // sample 4 points ±100 m N/S/E/W via Open-Meteo (Copernicus DEM ~90 m)
  const dLat = 100 / 111320;
  const dLon = 100 / (111320 * Math.cos(latlng.lat * Math.PI / 180));
  const lats = [latlng.lat + dLat, latlng.lat - dLat, latlng.lat, latlng.lat].map(v => v.toFixed(6)).join(",");
  const lons = [latlng.lng, latlng.lng, latlng.lng + dLon, latlng.lng - dLon].map(v => v.toFixed(6)).join(",");
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), SLOPE_TIMEOUT_MS);
  try {
    const r = await fetch("https://api.open-meteo.com/v1/elevation?latitude=" + lats + "&longitude=" + lons,
      { signal: ctrl.signal });
    const j = await r.json();
    const [zN, zS, zE, zW] = j.elevation;
    return slopeOf((zE - zW) / 200, (zS - zN) / 200);
  } catch { return null; }
  finally { clearTimeout(t); }
}
export async function readSlope(latlng) {
  const meta = await terrainReady();
  return meta ? readSlopeBaked(meta, latlng) : readSlopeRemote(latlng);
}
