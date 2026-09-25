import { R3857, R_EARTH } from "./constants.js";

/* ---- geometry helpers: WGS84 <-> spherical Mercator, and point-in-polygon ---- */
export const lonTo3857 = lon => lon * R3857 / 180;
export const latTo3857 = lat => Math.log(Math.tan((90 + lat) * Math.PI / 360)) * R_EARTH;
export const y3857ToLat = y => (2 * Math.atan(Math.exp(y / R_EARTH)) - Math.PI / 2) * 180 / Math.PI;
export const ringsOf = g => !g ? [] :
  g.type === "Polygon" ? g.coordinates :
  g.type === "MultiPolygon" ? [].concat.apply([], g.coordinates) : [];
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
/* ---- WGS84 <-> a national transverse Mercator grid ----
   Snyder's transverse Mercator series, written once and given its constants, because the grids
   the app reads differ by almost nothing: ETRS-TM35FIN (EPSG:3067) and SWEREF99 TM (EPSG:3006)
   are the same projection on the same GRS80 ellipsoid at the same scale and false easting, and
   disagree only on where the central meridian runs — 27° E against 15° E. Copying the series per
   country would be copying twelve lines of ellipsoidal algebra to change one number in it.

   `row` splits the forward series at the point where it stops depending on the latitude: a tile
   is sampled row by row and a row is one latitude, so its trigonometry is worth doing once for
   the whole row rather than once per sample. `forward` is the same thing for a single point. */
export function tmProjection(p) {
  const a = p.a == null ? 6378137 : p.a;                    // GRS80, shared by ETRS89 and SWEREF99
  const f = p.f == null ? 1 / 298.257222101 : p.f;
  const k0 = p.k0 == null ? 0.9996 : p.k0;
  const x0 = p.x0 == null ? 500000 : p.x0, y0 = p.y0 == null ? 0 : p.y0;
  const lon0 = p.lon0 * Math.PI / 180;
  const e2 = f * (2 - f), ep2 = e2 / (1 - e2), e4 = e2 * e2, e6 = e4 * e2;
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));

  function row(lat) {
    const phi = lat * Math.PI / 180;
    const sin = Math.sin(phi), cos = Math.cos(phi), tan = Math.tan(phi);
    const N = a / Math.sqrt(1 - e2 * sin * sin), T = tan * tan, C = ep2 * cos * cos;
    const M = a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * Math.sin(2 * phi)
      + (15 * e4 / 256 + 45 * e6 / 1024) * Math.sin(4 * phi) - (35 * e6 / 3072) * Math.sin(6 * phi));
    return lon => {
      const A = (lon * Math.PI / 180 - lon0) * cos;
      const x = x0 + k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120);
      const y = y0 + k0 * (M + N * tan * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720));
      return { x, y };
    };
  }
  // the inverse of the series above (Snyder 8-21..8-25)
  function inverse(x, y) {
    const M = (y - y0) / k0, mu = M / (a * (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256));
    const phi1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu)
      + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * Math.sin(4 * mu)
      + (151 * e1 ** 3 / 96) * Math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * Math.sin(8 * mu);
    const sin = Math.sin(phi1), cos = Math.cos(phi1), tan = Math.tan(phi1);
    const C1 = ep2 * cos * cos, T1 = tan * tan;
    const N1 = a / Math.sqrt(1 - e2 * sin * sin), R1 = a * (1 - e2) / (1 - e2 * sin * sin) ** 1.5;
    const D = (x - x0) / (N1 * k0);
    const phi = phi1 - (N1 * tan / R1) * (D * D / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D ** 4 / 24
      + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * ep2 - 3 * C1 * C1) * D ** 6 / 720);
    const lam = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6
      + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * ep2 + 24 * T1 * T1) * D ** 5 / 120) / cos;
    return [phi * 180 / Math.PI, lam * 180 / Math.PI];
  }
  // EPSG:3857 [minx,miny,maxx,maxy] -> the grid box that covers it. A national TM grid is rotated
  // against Mercator, so all four corners are projected and the extremes taken.
  function box3857(bbox) {
    const lons = [bbox[0], bbox[2]].map(x => x * 180 / R3857);
    const lats = [bbox[1], bbox[3]].map(y3857ToLat);
    let xmin = Infinity, ymin = Infinity, xmax = -Infinity, ymax = -Infinity;
    lats.forEach(lat => lons.forEach(lon => {
      const q = row(lat)(lon);
      xmin = Math.min(xmin, q.x); xmax = Math.max(xmax, q.x);
      ymin = Math.min(ymin, q.y); ymax = Math.max(ymax, q.y);
    }));
    return { xmin, ymin, xmax, ymax };
  }
  return { row, forward: (lat, lon) => row(lat)(lon), inverse, box3857 };
}
export const TM35FIN = tmProjection({ lon0: 27 });      // EPSG:3067, Finland
export const SWEREF99TM = tmProjection({ lon0: 15 });   // EPSG:3006, Sweden
/* The grids a baked raster may declare in its metadata. A raster whose CRS is not in here is not
   drawn rather than drawn in the wrong place: `projectionFor` returns null and the caller says so,
   which is the one failure mode a map must never handle by guessing. */
export const PROJECTIONS = { "EPSG:3067": TM35FIN, "EPSG:3006": SWEREF99TM };
export const projectionFor = crs => PROJECTIONS[crs] || null;

/* Finland by name, for the Finnish-only layers — the Metsäkeskus queries, the baked DEM, the
   coordinate search. They are about Finnish services and Finnish data, so they say TM35 rather
   than carrying a projection around. */
export const toTM35 = (lat, lon) => TM35FIN.forward(lat, lon);
export const fromTM35 = (x, y) => TM35FIN.inverse(x, y);
export const bboxToTM35 = bbox => TM35FIN.box3857(bbox);
// EPSG:3067 box covering a LatLngBounds. TM35FIN is rotated against the map's projection, so
// all four corners are projected and the extremes taken.
export function boundsToTM35(b) {
  let xmin = Infinity, ymin = Infinity, xmax = -Infinity, ymax = -Infinity;
  [[b.getSouth(), b.getWest()], [b.getSouth(), b.getEast()],
   [b.getNorth(), b.getWest()], [b.getNorth(), b.getEast()]].forEach(ll => {
    const p = toTM35(ll[0], ll[1]);
    xmin = Math.min(xmin, p.x); xmax = Math.max(xmax, p.x);
    ymin = Math.min(ymin, p.y); ymax = Math.max(ymax, p.y);
  });
  return { xmin: xmin, ymin: ymin, xmax: xmax, ymax: ymax };
}
