import { WMS } from "./constants.js";
import { SpotLayer } from "./spotlayer.js";
import { state } from "./state.js";

/* ================= map ================= */
export const map = L.map("map", { zoomControl: false, attributionControl: true })
  .setView([65.4, 26.5], 5);
L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);

export const basemaps = {
  osm: L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "© OpenStreetMap | Metsä: © Luke MVMI 2023, © Suomen metsäkeskus — CC BY 4.0" }),
  topo: L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
    maxZoom: 17, attribution: "© OpenTopoMap (CC-BY-SA) | © Luke MVMI 2023, © Suomen metsäkeskus — CC BY 4.0" }),
  sat: L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 18, attribution: "© Esri | © Luke MVMI 2023, © Suomen metsäkeskus — CC BY 4.0" }),
};
export let currentBasemap = basemaps.osm.addTo(map);

// keepBuffer 1 rather than Leaflet's 2: an ordinary tile costs one cached image, one of these
// costs up to seven WMS requests, so a two-tile ring of off-screen work is proportionally far
// more expensive here than it is for a basemap.
export const spots = new SpotLayer({ opacity: state.opacity, maxZoom: 19, keepBuffer: 1 }).addTo(map);
spots.on("loading", () => document.getElementById("spinner").classList.add("on"));
spots.on("load",    () => document.getElementById("spinner").classList.remove("on"));

// optional helper overlays (single-condition, server-styled)
export function helperLayer(layerName, sld) {
  return L.tileLayer.wms(WMS, {
    layers: layerName, format: "image/png", transparent: true,
    version: "1.1.1", opacity: 0.45, SLD_BODY: sld,
  });
}
document.getElementById("basemapSeg").addEventListener("click", e => {
  const btn = e.target.closest("button"); if (!btn) return;
  document.querySelectorAll("#basemapSeg button").forEach(b => b.classList.toggle("active", b === btn));
  map.removeLayer(currentBasemap);
  currentBasemap = basemaps[btn.dataset.bm].addTo(map);
  currentBasemap.bringToBack();
});
