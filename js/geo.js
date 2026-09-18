import { R3857, R_EARTH } from "./constants.js";

/* ---- geometry helpers: WGS84 <-> spherical Mercator, and point-in-polygon ---- */
export const lonTo3857 = lon => lon * R3857 / 180;
export const latTo3857 = lat => Math.log(Math.tan((90 + lat) * Math.PI / 360)) * R_EARTH;
export const y3857ToLat = y => (2 * Math.atan(Math.exp(y / R_EARTH)) - Math.PI / 2) * 180 / Math.PI;
export const ringsOf = g => !g ? [] :
  g.type === "Polygon" ? g.coordinates :
  g.type === "MultiPolygon" ? [].concat.apply([], g.coordinates) : [];
// EPSG:3857 [minx,miny,maxx,maxy] -> the EPSG:3067 box that covers it. TM35FIN is rotated
// against Mercator, so all four corners are projected and the extremes taken.
export function bboxToTM35(bbox) {
  const lons = [bbox[0], bbox[2]].map(x => x * 180 / R3857);
  const lats = [bbox[1], bbox[3]].map(y3857ToLat);
  let xmin = Infinity, ymin = Infinity, xmax = -Infinity, ymax = -Infinity;
  lats.forEach(lat => lons.forEach(lon => {
    const p = toTM35(lat, lon);
    xmin = Math.min(xmin, p.x); xmax = Math.max(xmax, p.x);
    ymin = Math.min(ymin, p.y); ymax = Math.max(ymax, p.y);
  }));
  return { xmin, ymin, xmax, ymax };
}
// A feature's EPSG:3857 bounding box, computed once and kept on the feature itself. The same
// polygons are re-tested against every tile of their 10 km cell, so this is worth caching.
export function featureBox(f) {
  if (f._bb) return f._bb;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  ringsOf(f.geometry).forEach(ring => ring.forEach(pt => {
    const x = lonTo3857(pt[0]), y = latTo3857(pt[1]);
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }));
  return (f._bb = [x0, y0, x1, y1]);
}
// Ray casting over every ring. GeoJSON holes are wound the other way but the parity rule does
// not care: a point inside a hole crosses one extra boundary and falls out again.
export function inFeature(f, lon, lat) {
  let inside = false;
  ringsOf(f.geometry).forEach(ring => {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside;
    }
  });
  return inside;
}
/* WGS84 -> ETRS-TM35FIN (EPSG:3067), Snyder's transverse Mercator series, GRS80. Split at the
   point where the series stops depending on the latitude: a tile is sampled row by row and a row
   is one latitude, so its trigonometry is worth doing once for the whole row rather than once per
   sample. toTM35 is the same thing for a single point. */
export function tm35Row(lat) {
  const a = 6378137, f = 1 / 298.257222101, k0 = 0.9996, lon0 = 27 * Math.PI / 180;
  const e2 = f * (2 - f), ep2 = e2 / (1 - e2);
  const phi = lat * Math.PI / 180;
  const sin = Math.sin(phi), cos = Math.cos(phi), tan = Math.tan(phi);
  const N = a / Math.sqrt(1 - e2 * sin * sin), T = tan * tan, C = ep2 * cos * cos;
  const e4 = e2 * e2, e6 = e4 * e2;
  const M = a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * Math.sin(2 * phi)
    + (15 * e4 / 256 + 45 * e6 / 1024) * Math.sin(4 * phi) - (35 * e6 / 3072) * Math.sin(6 * phi));
  return lon => {
    const A = (lon * Math.PI / 180 - lon0) * cos;
    const x = 500000 + k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120);
    const y = k0 * (M + N * tan * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720));
    return { x, y };
  };
}
export function toTM35(lat, lon) { return tm35Row(lat)(lon); }
// ETRS-TM35FIN (EPSG:3067) -> WGS84, the inverse of the series above (Snyder 8-21..8-25)
export function fromTM35(x, y) {
  const a = 6378137, f = 1 / 298.257222101, k0 = 0.9996, lon0 = 27 * Math.PI / 180;
  const e2 = f * (2 - f), ep2 = e2 / (1 - e2);
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
  const M = y / k0, mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256));
  const phi1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu)
    + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * Math.sin(4 * mu)
    + (151 * e1 ** 3 / 96) * Math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * Math.sin(8 * mu);
  const sin = Math.sin(phi1), cos = Math.cos(phi1), tan = Math.tan(phi1);
  const C1 = ep2 * cos * cos, T1 = tan * tan;
  const N1 = a / Math.sqrt(1 - e2 * sin * sin), R1 = a * (1 - e2) / (1 - e2 * sin * sin) ** 1.5;
  const D = (x - 500000) / (N1 * k0);
  const phi = phi1 - (N1 * tan / R1) * (D * D / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D ** 4 / 24
    + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * ep2 - 3 * C1 * C1) * D ** 6 / 720);
  const lam = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6
    + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * ep2 + 24 * T1 * T1) * D ** 5 / 120) / cos;
  return [phi * 180 / Math.PI, lam * 180 / Math.PI];
}
