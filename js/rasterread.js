import { CYCLE } from "./constants.js";
import { inFeature, toTM35 } from "./geo.js";
import { mkAt } from "./metsakeskus.js";
import { prob } from "./problayer.js";

/* ---- reading a baked EPSG:3067 COG at a point ----
   The score, the cut layer and the terrain layer are three products on the same grid in the same
   format, split into parts the same way, so they are read by the same two functions rather than
   by three copies of this loop. `pad` widens the read to the (2·pad+1)² block around the point —
   one range request either way, since a COG tile holds far more than nine pixels — and is clamped
   to the part, so a point on a seam still returns a full block rather than throwing. */
export async function readBlockAt(rasters, x, y, pad) {
  const p = pad || 0, n = 2 * p + 1;
  for (const gr of rasters) {
    if (!gr || x < gr.xmin || x > gr.xmax || y < gr.ymin || y > gr.ymax) continue;
    const col = Math.floor((x - gr.xmin) / gr.pixelWidth), row = Math.floor((gr.ymax - y) / gr.pixelHeight);
    const left = Math.min(Math.max(col - p, 0), Math.max(0, gr.width - n));
    const top  = Math.min(Math.max(row - p, 0), Math.max(0, gr.height - n));
    try {
      const v = await gr.getValues({ left, top, right: left + n, bottom: top + n, width: n, height: n });
      return v[0];                                  // band 0, as [row][col]
    } catch (e) { return null; }
  }
  return null;
}
export async function readValueAt(rasters, x, y) {
  const b = await readBlockAt(rasters, x, y, 0);
  return b ? b[0][0] : null;
}

// model score at a point (null if the layer is not loaded or the point is outside the rasters)
export async function readProb(latlng) {
  if (!prob.rasters.length || !prob.meta) return null;
  const { x, y } = toTM35(latlng.lat, latlng.lng);
  const val = await readValueAt(prob.rasters, x, y);
  return (val == null || val === prob.meta.nodata) ? null : val;
}

/* What Metsäkeskus knows about the stand under a point, in the two flavours the map has to keep
   apart: `cut` is the stand register saying the trees are gone, `declared` is somebody's filed
   intention to take them. Null when neither applies — or when Metsäkeskus cannot be reached,
   which reads the same as "nothing to report" and never blocks the rest of the panel. */
export const DEVCLASS_NAMES = { A0: "aukea", S0: "siemenpuumetsikkö", T1: "taimikko (alle 1,3 m)", T2: "taimikko (yli 1,3 m)" };
// Metsäkeskus stamps these as Finnish local time with an explicit offset ("2026-07-31T00:00:00
// +03:00"), and the day is the whole meaning — a stand was measured *that day*. Going through
// Date would re-express it in the viewer's zone and hand anyone west of Finland the day before,
// so the date part is read straight off the string.
export const fiDate = s => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s || "");
  return m ? +m[3] + "." + +m[2] + "." + m[1] : null;
};

// The same answer read off the baked layer: no stand details and no dates, but it works with no
// network at all. Only ever a fallback — the live register is newer than any published raster.
export async function readCutBaked(latlng) {
  if (!prob.cut.length) return null;
  const { x, y } = toTM35(latlng.lat, latlng.lng);
  const val = await readValueAt(prob.cut, x, y);
  return val === 2 ? "cut" : val === 1 ? "declared" : null;
}

export async function readHarvest(latlng) {
  const p = toTM35(latlng.lat, latlng.lng);
  const [stands, decls] = await Promise.all([
    mkAt("stand", p.x, p.y),
    mkAt("mki", p.x, p.y),
  ]);
  if (!stands.length && !decls.length) {
    const baked = await readCutBaked(latlng).catch(() => null);
    if (baked) return { state: baked, stale: true };
  }
  const hitStand = stands.find(f => inFeature(f, latlng.lng, latlng.lat));
  // several declarations can stack on one stand over the years; the newest is the story
  const hitDecls = decls.filter(f => inFeature(f, latlng.lng, latlng.lat))
    .sort((a, b) => (b.properties.DECLARATIONARRIVALDATE || "").localeCompare(a.properties.DECLARATIONARRIVALDATE || ""));
  if (hitStand) {
    const s = hitStand.properties;
    return { state: "cut", devclass: s.DEVELOPMENTCLASS, age: s.MEANAGE, height: s.MEANHEIGHT,
             asOf: s.TREESTANDDATE, declared: hitDecls[0] && hitDecls[0].properties };
  }
  if (hitDecls.length) return { state: "declared", declared: hitDecls[0].properties };
  return null;
}

export function harvestHTML(h) {
  if (!h) return "";
  // read off the published raster because Metsäkeskus could not be reached: say so, and do not
  // pretend to details the raster does not carry
  if (h.stale) {
    const when = prob.meta && prob.meta.cut ? prob.meta.cut.built : null;
    return '<div class="warn"><b>⚠️ ' + (h.state === "cut" ? "Kuvio on hakattu." : "Hakkuuaikomus.") +
      '</b> Tieto on kartan mukana julkaistusta hakkuutasosta' + (when ? " (" + when + ")" : "") +
      ', ei Metsäkeskuksen rajapinnasta — yhteyttä ei juuri nyt saatu, joten tuoreimmat hakkuut ' +
      'voivat puuttua.</div>';
  }
  if (h.state === "cut") {
    const bits = [DEVCLASS_NAMES[h.devclass] || ("kehitysluokka " + h.devclass)];
    if (h.height > 0) bits.push("keskipituus " + h.height.toFixed(1).replace(".", ",") + " m");
    if (h.age > 0) bits.push("ikä " + h.age + " v");
    const asOf = fiDate(h.asOf);
    return '<div class="warn"><b>⚠️ Kuvio on hakattu.</b> Metsäkeskuksen kuviotieto: ' +
      bits.join(", ") + (asOf ? " (tieto " + asOf + ")" : "") + ". Kartan pohja-aineisto on Luken " +
      "VMI 20" + CYCLE.slice(2) + ", joka näyttää täällä yhä hakkuuta edeltävän metsän.</div>";
  }
  const d = h.declared || {}, when = fiDate(d.DECLARATIONARRIVALDATE);
  return '<div class="warn"><b>⚠️ Hakkuuaikomus' + (when ? " " + when : "") + '</b>' +
    (d.AREA ? " (uudistushakkuu, " + String(d.AREA).replace(".", ",") + " ha)" : " (uudistushakkuu)") +
    '. Metsänkäyttöilmoitus on aikomus — ilmoitettua hakkuuta ei ole pakko tehdä, eikä ' +
    'toteutusta ole vahvistettu kuviotiedossa. Metsä voi olla pystyssä tai poissa.</div>';
}
