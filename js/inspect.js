import { LAYER, MAIN_CANDIDATES, MAIN_NAMES, SITE_CANDIDATES, SITE_NAMES } from "./constants.js";
import { map } from "./maplayer.js";
import { fmtPct, prob, probRank, probThreshold } from "./problayer.js";
import { harvestHTML, readHarvest, readProb } from "./rasterread.js";
import { cfg, sp, state } from "./state.js";
import { readSlope } from "./terrain.js";
import { checkRow, openSheet } from "./ui.js";
import { loadMask, maskMin, maskRange, maskValues, newCanvas, wmsURL } from "./wms.js";

/* ================= tap to inspect =================
   The WMS reprojection blends a gray-ramp value readout, so instead we
   probe with the same crisp values/intervals masks the map layer uses:
   a probe is "true" when the styled pixel under the point is opaque.

   A tap asks a dozen or more of these at once, so two rules keep it civil. Every probe goes out
   through the same Luke queue as the map tiles — but ahead of them, because a tap is somebody
   waiting. And every probe is remembered for the duration of the tap that asked: the same
   question about the same point is put to the server exactly once, however many readouts want
   the answer. The memo is dropped when the next tap starts, so it never answers for a stale
   point, and a failed probe stays failed for that one tap rather than being retried per caller. */
export let probeMemo = new Map();
export function probe(layerName, sld, latlng) {
  const p = L.CRS.EPSG3857.project(latlng);
  const half = 24;
  const bbox = [p.x - half, p.y - half, p.x + half, p.y + half];
  const url = wmsURL(layerName, sld, bbox, 3, 3);
  let hit = probeMemo.get(url);
  if (!hit) probeMemo.set(url, hit = loadMask(url, { first: true }).then(img => {
    const ctx = newCanvas(3, 3).getContext("2d");
    ctx.drawImage(img, 0, 0);
    return ctx.getImageData(1, 1, 1, 1).data[3] >= 200;
  }));
  return hit;
}
export const probeValues = (layer, values, ll) =>
  probe(layer, maskValues(layer, values), ll).catch(() => null);
export const probeMin = (layer, min, ll) =>
  probe(layer, maskMin(layer, min), ll).catch(() => null);
export const probeRange = (layer, lo, hi, ll) =>
  probe(layer, maskRange(layer, lo, hi), ll).catch(() => null);

// exact class via parallel single-value probes; null if none match
export async function readClass(layerName, candidates, latlng) {
  const hits = await Promise.all(candidates.map(v => probeValues(layerName, [v], latlng)));
  const i = hits.indexOf(true);
  return i === -1 ? null : candidates[i];
}
// value bracket via parallel threshold probes: [lo, hi) between steps
export async function readBracket(layerName, steps, latlng) {
  const hits = await Promise.all(steps.map(t => probeMin(layerName, t, latlng)));
  let lo = null, hi = null;
  for (let i = 0; i < steps.length; i++) {
    if (hits[i]) { lo = steps[i]; hi = i + 1 < steps.length ? steps[i + 1] : null; }
  }
  if (lo == null) return hits[0] === false ? { below: steps[0] } : null;
  return { lo, hi };
}
/* The value interval a bracket pins down, and the interval a metric accepts, in one shape:
   `value ∈ (gt, le]`. Both masks are built on the same half-open intervals (maskMin is
   (limit, 255], maskRange is (lo, limit]), so the comparison below is exact, not an
   approximation — and the raster is unsigned bytes, which is what makes -1 a true lower bound. */
export const bracketInterval = b => b == null ? null :
  b.below != null ? { gt: -1, le: b.below } : { gt: b.lo, le: b.hi == null ? Infinity : b.hi };
export const metricBand = m => m.dir === "range" ? { gt: m.lo, le: m.limit }
                                          : { gt: m.limit, le: Infinity };
/* Does the bracket already settle "does this point clear the metric"?
   true / false when the bracket's interval falls wholly inside or wholly outside the band, null
   when there is no data to judge (another request would only ask the same unanswerable question),
   and undefined when it is genuinely open — which happens only where the user's limit sits
   strictly between two of the fixed steps. Every other case is an answer the bracket already
   paid for, and the pass/fail probe that used to be fired alongside it is pure duplication. */
export function bracketVerdict(band, b) {
  const iv = bracketInterval(b);
  if (!iv) return null;
  if (iv.gt >= band.gt && iv.le <= band.le) return true;
  if (iv.le <= band.gt || iv.gt >= band.le) return false;
  return undefined;
}
// one metric: does any of its alternative layers clear the threshold?
export async function readMetric(m, latlng) {
  const band = metricBand(m);
  const alts = await Promise.all(m.any.map(async a => {
    const val = await readBracket(a.layer, m.steps, latlng);
    const known = bracketVerdict(band, val);
    const pass = known !== undefined ? known
      : await (m.dir === "range" ? probeRange(a.layer, m.lo, m.limit, latlng)
                                 : probeMin(a.layer, m.limit, latlng));
    return { label: a.label || m.label, pass, val };
  }));
  return { m, alts, ok: alts.some(a => a.pass === true) };
}
export async function inspect(latlng) {
  const species = sp(), c = cfg();
  probeMemo = new Map();          // a new point: nothing the last tap learned applies here
  const body = document.getElementById("resultBody");
  body.innerHTML = '<div class="result-head"><span class="big">🔎</span>' +
    '<div><div class="verdict">Tutkitaan paikkaa…</div>' +
    '<div class="sub">' + latlng.lat.toFixed(5) + "° N, " + latlng.lng.toFixed(5) + "° E</div></div></div>";
  openSheet("sheetResult");

  const metrics = species.metrics(c);
  const [site, main, slope, results, pv, harvest] = await Promise.all([
    readClass(LAYER.site, SITE_CANDIDATES, latlng),
    readClass(LAYER.main, MAIN_CANDIDATES, latlng),
    readSlope(latlng),
    Promise.all(metrics.map(m => readMetric(m, latlng))),
    state.prob.on ? readProb(latlng).catch(() => null) : Promise.resolve(null),
    readHarvest(latlng).catch(() => null),
  ]);

  if (site == null && results.every(r => r.alts.every(a => a.val == null))) {
    // Metsäkeskus may still have something to say — a fresh clear-cut is exactly the kind of
    // place Luke's layers can come back empty for, and "ei metsätietoa" alone would leave the
    // most useful fact on the floor.
    body.innerHTML = '<div class="result-head"><span class="big">' +
      (harvest && harvest.state === "cut" ? "🪵" : "🌊") + '</span>' +
      '<div><div class="verdict">' +
      (harvest && harvest.state === "cut" ? "Hakattu — metsä ei ole enää tässä"
                                          : "Ei metsätietoa tässä kohdassa") + '</div>' +
      '<div class="sub">' + (harvest && harvest.state === "cut"
        ? "Luken aineistossa ei ole tälle ruudulle metsätietoa"
        : "vesistö, pelto, rakennettu alue — tai yhteysvirhe") + '</div></div></div>' +
      harvestHTML(harvest);
    return;
  }

  const fmtBracket = (b, unit) => b == null ? "ei tietoa" :
    b.below != null ? "alle " + b.below + " " + unit :
    b.hi == null ? "yli " + b.lo + " " + unit :
    b.lo + "–" + b.hi + " " + unit;

  const wanted = species.siteClasses(c);
  const groundOk = main != null && species.mainTypes(c).includes(main);
  const siteOk = site != null && wanted.includes(site) && groundOk;
  const primeSite = site === species.primeSite && groundOk;
  const hard = results.filter(r => !r.m.soft);
  const standOk = hard.every(r => r.ok);
  const slopeOk = slope && species.slopeGood ? species.slopeGood(slope) : false;
  const outOfRange = species.maxLat != null && latlng.lat > species.maxLat;

  let icon, verdict;
  if (harvest && harvest.state === "cut") {
    // Whatever the MVMI layers say about this cell, the trees they describe are gone.
    icon = "🪵"; verdict = "Hakattu — metsä ei ole enää tässä";
  } else if (siteOk && standOk && !outOfRange) {
    icon = species.emoji;
    verdict = primeSite ? species.verdicts.hit : species.verdicts.hitAlt;
  } else if (siteOk) { icon = "🌲"; verdict = species.verdicts.stand; }
  else { icon = "❌"; verdict = species.verdicts.miss; }

  let html = '<div class="result-head"><span class="big">' + icon + '</span>' +
    '<div><div class="verdict">' + verdict + '</div>' +
    '<div class="sub">' + latlng.lat.toFixed(5) + "° N, " + latlng.lng.toFixed(5) + "° E · " +
    species.region(latlng.lat) + '</div></div></div>' +
    harvestHTML(harvest) +
    '<div class="checks">';

  html += checkRow(siteOk ? "ok" : "no", "Kasvupaikka",
    site != null ? (SITE_NAMES[site] || "tuntematon") + (main > 1 ? " (suo)" : "") : "ei tietoa");
  html += checkRow(groundOk ? "ok" : main == null ? "meh" : "no", "Maapohja",
    main != null ? MAIN_NAMES[main] : "ei tietoa");

  results.forEach(r => {
    const want = r.m.dir === "range"
      ? Math.max(r.m.lo, 0) + "–" + r.m.limit + " " + r.m.unit
      : "≥ " + r.m.limit + " " + r.m.unit;
    r.alts.forEach(a => {
      const st = a.pass === true ? "ok" : (r.m.soft || r.ok) ? "meh" : "no";
      html += checkRow(st, a.label + " (" + want + ")", fmtBracket(a.val, r.m.unit));
    });
  });

  html += checkRow(slope ? (slopeOk ? "ok" : "meh") : "meh", "Rinne",
    slope ? (slope.deg < 1 ? "tasainen" : slope.deg.toFixed(1) + "° " + slope.dir) : "ei tietoa");
  if (pv != null) {
    const floor = (prob.meta && prob.meta.floor) || 0;
    if (pv < floor) {
      html += checkRow("no", "Malli", "alle kartan rajan");
    } else {
      const top = (1 - probRank(pv)) * 100;
      html += checkRow(pv >= probThreshold() ? "ok" : "meh", "Malli",
        pv + " · parhaat " + fmtPct(top < 1 ? Math.max(0.05, Math.round(top * 100) / 100) : Math.round(top)) + " metsästä");
    }
  }
  html += "</div>";

  html += '<a class="navlink" target="_blank" rel="noopener" href="https://www.google.com/maps/dir/?api=1&destination=' +
    latlng.lat.toFixed(6) + "," + latlng.lng.toFixed(6) + '&travelmode=driving">🧭 Navigoi tänne</a>';

  body.innerHTML = html;
}
map.on("click", e => inspect(e.latlng));
