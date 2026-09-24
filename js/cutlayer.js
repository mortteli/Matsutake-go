import { toTM35 } from "./geo.js";
import { map } from "./maplayer.js";
import { MK_MINZOOM, mkCellsOf, mkFeatures } from "./metsakeskus.js";
import { repaintProb } from "./problayer.js";
import { DEVCLASS_NAMES, fiDate } from "./rasterread.js";
import { save, state } from "./state.js";
import { refreshSpots } from "./ui.js";

/* ---- "Hakkuut" overlay: the correction, drawn, so it can be argued with ---- */
export let cutLayer = null, cutBusy = false;

export function cutStyle(f) {
  return f.properties.DEVELOPMENTCLASS
    ? { color: "#c8d3cc", weight: 1, fillColor: "#c8d3cc", fillOpacity: .34 }          // fact
    : { color: "#ff9d2e", weight: 1, dashArray: "4 3", fillColor: "#ff9d2e", fillOpacity: .16 }; // intent
}
export function cutPopupHTML(f) {
  const p = f.properties;
  return p.DEVELOPMENTCLASS
    ? "<b>Hakattu</b><br>" + (DEVCLASS_NAMES[p.DEVELOPMENTCLASS] || p.DEVELOPMENTCLASS) +
      (p.MEANAGE > 0 ? ", ikä " + p.MEANAGE + " v" : "") +
      (fiDate(p.TREESTANDDATE) ? "<br><small>tieto " + fiDate(p.TREESTANDDATE) + "</small>" : "")
    : "<b>Hakkuuaikomus</b><br>uudistushakkuu" + (p.AREA ? ", " + String(p.AREA).replace(".", ",") + " ha" : "") +
      (fiDate(p.DECLARATIONARRIVALDATE) ? "<br><small>ilmoitettu " + fiDate(p.DECLARATIONARRIVALDATE) + "</small>" : "");
}
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

export let cutCells = null;           // which cells the drawn overlay is built from
export async function cutRefresh() {
  if (!cutLayer || !map.hasLayer(cutLayer) || cutBusy) return;
  if (map.getZoom() < MK_MINZOOM) { cutLayer.clearLayers(); cutCells = null; return; }
  const bb = boundsToTM35(map.getBounds());
  // Panning inside the same 10 km cells changes nothing about which polygons apply, and
  // rebuilding them was the single most expensive thing this layer did: clearLayers() plus
  // addData() on every moveend meant tearing down and recreating ~1 200 polygons per pan.
  const cells = mkCellsOf(bb).map(c => c.join(",")).join(";");
  if (cells === cutCells) return;
  cutBusy = true;
  try {
    // declarations first so the stand polygons draw over them where both apply
    const lists = await Promise.all([mkFeatures("mki", bb), mkFeatures("stand", bb)]);
    if (map.hasLayer(cutLayer)) {
      cutLayer.clearLayers();
      cutLayer.addData({ type: "FeatureCollection", features: lists[0].concat(lists[1]) });
      cutCells = cells;        // only on success, so a failed fetch is retried on the next move
    }
  } catch (e) { /* Metsäkeskus unreachable: the overlay just stays as it was */ }
  finally { cutBusy = false; }
}
document.getElementById("chkCutLayer").addEventListener("change", e => {
  if (e.target.checked) {
    // A canvas renderer rather than the default SVG one: this layer routinely holds over a
    // thousand polygons with tens of thousands of vertices between them, and one <path> element
    // each is what made the map unusable on a phone. One shared popup rather than one bound per
    // feature, for the same reason — bindPopup builds a Popup instance immediately.
    cutLayer = cutLayer || L.geoJSON(null, { style: cutStyle, renderer: L.canvas({ padding: 0.3 }) })
      .on("click", ev => {
        if (!ev.layer || !ev.layer.feature) return;
        L.popup().setLatLng(ev.latlng).setContent(cutPopupHTML(ev.layer.feature)).openOn(map);
      });
    cutLayer.addTo(map);
    cutCells = null;
    cutRefresh();
  } else if (cutLayer) map.removeLayer(cutLayer);
});
map.on("moveend", cutRefresh);
export const chkHideCut = document.getElementById("chkHideCut");
chkHideCut.checked = state.hideCut;
chkHideCut.addEventListener("change", () => {
  state.hideCut = chkHideCut.checked;
  save();
  refreshSpots();
  repaintProb();     // the model layer carries the correction in its own band
});
