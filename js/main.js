import { map } from "./maplayer.js";
import { initSearch } from "./search.js";
import { sp } from "./state.js";
import { applySpecies, toast } from "./ui.js";

applySpecies();
initSearch();

// zoom hint
export let hinted = false;
map.on("zoomend", () => {
  if (!hinted && map.getZoom() >= 6 && map.getZoom() < 10) {
    hinted = true;
    toast("Lähennä karttaa — pinkit alueet tarkentuvat 16 m ruutuihin 🔍");
  }
});

// an empty map north of a species' range would otherwise look broken
export let rangeToastAt = 0;
map.on("moveend", () => {
  const s = sp();
  if (s.maxLat == null || map.getBounds().getSouth() <= s.maxLat) return;
  if (Date.now() - rangeToastAt < 30000) return;
  rangeToastAt = Date.now();
  toast(s.name + " ei kasva näin pohjoisessa — kartta on siksi tyhjä");
});
setTimeout(() => toast("Napauta karttaa tutkiaksesi paikkaa " + sp().emoji), 1500);
