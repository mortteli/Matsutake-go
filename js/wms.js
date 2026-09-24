import { WMS } from "./constants.js";
import { featureBox, latTo3857, lonTo3857, ringsOf } from "./geo.js";

/* ================= SLD mask builders ================= */
export function sldWrap(layerName, colorMap) {
  return '<?xml version="1.0" encoding="UTF-8"?>' +
    '<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld">' +
    '<NamedLayer><Name>' + layerName + '</Name><UserStyle><FeatureTypeStyle><Rule>' +
    '<RasterSymbolizer>' + colorMap + '</RasterSymbolizer>' +
    '</Rule></FeatureTypeStyle></UserStyle></NamedLayer></StyledLayerDescriptor>';
}
// pixels whose raw value is in `values` -> opaque, everything else transparent
export function maskValues(layerName, values, color) {
  const entries = values.map(v => '<ColorMapEntry quantity="' + v + '" color="' + (color || "#ff0000") + '" opacity="1"/>').join("");
  return sldWrap(layerName, '<ColorMap type="values">' + entries + '</ColorMap>');
}
// pixels with raw value in (min, 255] -> opaque; no-data stays transparent
export function maskMin(layerName, min, color) {
  return sldWrap(layerName,
    '<ColorMap type="intervals">' +
    '<ColorMapEntry quantity="' + min + '" color="#000000" opacity="0"/>' +
    '<ColorMapEntry quantity="255" color="' + (color || "#ff0000") + '" opacity="1"/>' +
    '</ColorMap>');
}
// pixels with raw value in (lo, hi] -> opaque; no-data stays transparent.
// lo = -1 gives a plain "at most hi" mask.
export function maskRange(layerName, lo, hi, color) {
  return sldWrap(layerName,
    '<ColorMap type="intervals">' +
    '<ColorMapEntry quantity="' + lo + '" color="#000000" opacity="0"/>' +
    '<ColorMapEntry quantity="' + hi + '" color="' + (color || "#ff0000") + '" opacity="1"/>' +
    '<ColorMapEntry quantity="255" color="#000000" opacity="0"/>' +
    '</ColorMap>');
}
export function wmsURL(layerName, sld, bbox, w, h) {
  return WMS + "?service=WMS&version=1.1.1&request=GetMap" +
    "&layers=" + encodeURIComponent(layerName) +
    "&srs=EPSG:3857&bbox=" + bbox.join(",") +
    "&width=" + w + "&height=" + h +
    "&format=image/png&transparent=true" +
    "&SLD_BODY=" + encodeURIComponent(sld);
}
export function newCanvas(w, h) {
  const cv = document.createElement("canvas");
  cv.width = w; cv.height = h;
  return cv;
}
/* ================= request budgets =================
   One queue per external service, shared by every call site, so how many connections the app
   opens to a server is a property of the app and not of whichever feature happens to be running.
   Per-call pooling is not enough: the tile layer, the tap probes and the "lähellä sinua" scan can
   all be in flight at once, and three independently pooled paths add up to three times the budget
   they each think they are keeping.

   `run(fn, opt)` calls `fn` only once a slot is free — the request is not merely awaited late, it
   is *made* late, which is the whole point. Two options shape the queue:

     first  jump the line. A tap and a scan are somebody waiting with a finger on the screen;
            tiles are speculative work the map decided to do. Without this a tap would queue
            behind a whole pan's worth of tiles.
     alive  a predicate re-checked at the head of the queue. A tile that has been panned off the
            screen before its turn comes costs nothing: `run` drops it with DROPPED instead of
            spending a slot on an image nobody will see. */
export const DROPPED = new Error("dropped");
export function gate(limit) {
  const waiting = [];
  let active = 0;
  const pump = () => {
    while (active < limit && waiting.length) {
      const job = waiting.shift();
      if (job.alive && !job.alive()) { job.rej(DROPPED); continue; }
      active++;
      Promise.resolve().then(job.fn).then(job.res, job.rej)
        .then(() => { active--; pump(); });
    }
  };
  return (fn, opt) => new Promise((res, rej) => {
    const job = { fn, res, rej, alive: opt && opt.alive };
    if (opt && opt.first) waiting.unshift(job); else waiting.push(job);
    pump();
  });
}
// Luke's GeoServer answers with `x-concurrent-limit-user: 6`; stay one under it so a basemap or
// helper overlay sharing the connection pool cannot push the app over the line.
export const LUKE_PAR = 5;
export const lukeGate = gate(LUKE_PAR);

export function loadImg(url) {
  return new Promise((res, rej) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => res(img);
    img.onerror = () => rej(new Error("tile load failed"));
    img.src = url;
  });
}
// every Luke WMS image the app asks for, from every call site, goes through here
export const loadMask = (url, opt) => lukeGate(() => loadImg(url), opt);
/* One binary mask per condition member, OR'd inside a condition and AND'd across them — the
   whole map in one function, so the tile layer and the nearby scan cannot drift apart. Every
   member goes out through `loadMask`, so a caller cannot choose its own concurrency: `opt` only
   says how this batch is ranked in the shared Luke queue ({ first, alive }, see `gate`). Returns
   an *uncoloured* canvas: the answer is in its alpha channel. Luke serves 1-bit paletted PNGs
   and resamples nearest-neighbour, so as long as nothing is scaled on the way in, every pixel
   of the result is alpha 0 or 255. */
export function compositeMask(groups, bbox, w, h, cut, opt) {
  const jobs = [];
  groups.forEach((g, gi) => g.forEach(m => jobs.push({ gi, url: wmsURL(m.layer, m.sld, bbox, w, h) })));
  return Promise.all(jobs.map(j => loadMask(j.url, opt))).then(imgs => {
    const byGroup = groups.map(() => []);
    jobs.forEach((j, i) => byGroup[j.gi].push(imgs[i]));
    // OR inside a group
    const unions = byGroup.map(list => {
      if (list.length === 1) return list[0];
      const cv = newCanvas(w, h), cx = cv.getContext("2d");
      list.forEach(im => cx.drawImage(im, 0, 0));   // source-over = alpha union
      return cv;
    });
    // AND across groups
    const off = newCanvas(w, h), octx = off.getContext("2d");
    octx.drawImage(unions[0], 0, 0);
    octx.globalCompositeOperation = "destination-in";
    for (let i = 1; i < unions.length; i++) octx.drawImage(unions[i], 0, 0);
    subtractCut(octx, cut, bbox, w, h);
    return off;
  });
}

/* AND NOT the stands Metsäkeskus says have been cut since the inventory, drawn into a mask's
   context. Vertices are projected one by one, so nothing is resampled and the 16 m grid stays
   honest; "evenodd" keeps polygon holes as holes. Separate from compositeMask so a tile that was
   drawn before its harvest data arrived can be corrected from the mask it already has, without
   asking Luke for the same images again. */
export function subtractCut(octx, cut, bbox, w, h) {
  if (!cut || !cut.length) return;
  const sx = w / (bbox[2] - bbox[0]), sy = h / (bbox[3] - bbox[1]);
  octx.globalCompositeOperation = "destination-out";
  octx.fillStyle = "#000";
  octx.beginPath();
  // A fetch covers a 10 km cell but a tile is a fraction of it, so most of what came back
  // cannot touch this tile. Reject those on a cached bounding box first — otherwise every
  // tile walks all ~800 polygons of its cell, vertex by vertex.
  cut.forEach(f => {
    const fb = featureBox(f);
    if (fb[2] < bbox[0] || fb[0] > bbox[2] || fb[3] < bbox[1] || fb[1] > bbox[3]) return;
    ringsOf(f.geometry).forEach(ring => {
      ring.forEach((pt, i) => {
        const px = (lonTo3857(pt[0]) - bbox[0]) * sx, py = (bbox[3] - latTo3857(pt[1])) * sy;
        if (i) octx.lineTo(px, py); else octx.moveTo(px, py);
      });
      octx.closePath();
    });
  });
  octx.fill("evenodd");
}
