import { boundsToTM35 } from "./geo.js";
import { map } from "./maplayer.js";
import { MK_MINZOOM, MK_RETRY_MS, mkCellsOf, mkComplete, mkFeatures, mkViewFits, mkWatchView } from "./metsakeskus.js";
import { repaintProb } from "./problayer.js";
import { DEVCLASS_NAMES, fiDate } from "./rasterread.js";
import { save, state } from "./state.js";
import { refreshSpots, toast } from "./ui.js";

/* ---- "Hakkuut" overlay: the correction, drawn, so it can be argued with ---- */
export let cutLayer = null;

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
export let cutCells = null;           // which cells the drawn overlay is built from
let cutLoading = null, cutGen = 0, cutRetry = null, cutHinted = false;
export async function cutRefresh() {
  if (!cutLayer || !map.hasLayer(cutLayer)) return;
  const bb = boundsToTM35(map.getBounds());
  if (map.getZoom() < MK_MINZOOM || !mkViewFits(bb)) {
    cutGen++; cutLoading = null;
    cutLayer.clearLayers(); cutCells = null;
    if (!cutHinted && map.getZoom() >= MK_MINZOOM) {
      cutHinted = true;
      toast("Lähennä vielä vähän — hakkuut haetaan Metsäkeskukselta pienemmältä alueelta 🪵");
    }
    return;
  }
  // Panning inside the same 10 km cells changes nothing about which polygons apply, and
  // rebuilding them was the single most expensive thing this layer did: clearLayers() plus
  // addData() on every moveend meant tearing down and recreating ~1 200 polygons per pan.
  const cells = mkCellsOf(bb).map(c => c.join(",")).join(";");
  if (cells === cutCells || cells === cutLoading) return;
  // A newer view supersedes a load still under way. This used to be a busy flag that dropped
  // the move instead, so zooming in during a slow load left the overlay built for the view the
  // user had already left, or empty, until the next pan.
  const gen = ++cutGen;
  cutLoading = cells;
  try {
    // declarations first so the stand polygons draw over them where both apply
    const lists = await Promise.all([mkFeatures("mki", bb), mkFeatures("stand", bb)]);
    if (gen !== cutGen || !map.hasLayer(cutLayer)) return;
    cutLayer.clearLayers();
    cutLayer.addData({ type: "FeatureCollection", features: lists[0].concat(lists[1]) });
    // A failed cell comes back as [] like an empty one. Remember the view as done only when
    // every cell really arrived, and otherwise try again once the failure cool-off has passed.
    if (mkComplete("mki", bb) && mkComplete("stand", bb)) cutCells = cells;
    else {
      clearTimeout(cutRetry);
      cutRetry = setTimeout(cutRefresh, MK_RETRY_MS + 1000);
    }
  } catch (e) { /* Metsäkeskus unreachable: the overlay just stays as it was */ }
  finally { if (gen === cutGen) cutLoading = null; }
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
mkWatchView(() => boundsToTM35(map.getBounds()));
export const chkHideCut = document.getElementById("chkHideCut");
chkHideCut.checked = state.hideCut;
chkHideCut.addEventListener("change", () => {
  state.hideCut = chkHideCut.checked;
  save();
  refreshSpots();
  repaintProb();     // the model layer carries the correction in its own band
});
