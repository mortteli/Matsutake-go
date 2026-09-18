import { fromTM35 } from "./geo.js";
import { inspect } from "./inspect.js";
import { map } from "./maplayer.js";
import { nearbyFollowMap, renderNearby } from "./nearby.js";
import { closeOverlays } from "./ui.js";

/* ================= place search =================
   Nominatim (OpenStreetMap) geocoding, biased to Finland and to the current view. Its usage
   policy allows one request a second and no keystroke-by-keystroke autocomplete, so the input is
   debounced and every earlier request is aborted before a new one goes out. A pair of numbers is
   read as coordinates without asking anyone: WGS84 degrees, or ETRS-TM35FIN metres (EPSG:3067),
   which is what Finnish map sheets and this app's own readouts are in. */
export const search = { marker: null, timer: null, abort: null, panel: null, input: null, list: null };

export function parseCoords(q) {
  const m = q.replace(/,\s*(?=[-\d])/g, " ").match(/(-?\d+(?:[.,]\d+)?)\s+(-?\d+(?:[.,]\d+)?)/);
  if (!m) return null;
  const a = parseFloat(m[1].replace(",", ".")), b = parseFloat(m[2].replace(",", "."));
  if (Math.abs(a) <= 90 && Math.abs(b) <= 180) return { lat: a, lon: b, label: "Koordinaatit (WGS84)" };
  // EPSG:3067: northing is the ~7-million number, easting the ~300-thousand one, either order
  const [n, e] = a > b ? [a, b] : [b, a];
  if (n > 6.5e6 && n < 7.9e6 && e > 4e4 && e < 8e5) {
    const ll = fromTM35(e, n);
    return { lat: ll[0], lon: ll[1], label: "Koordinaatit (ETRS-TM35FIN)" };
  }
  return null;
}

// `lead` is an optional array of ready-made <li> nodes to put above the results — the nearby
// section. It shares the one scroll container, so nothing about the markup changes.
export function showSearchResults(items, hint, lead) {
  search.list.innerHTML = "";
  (lead || []).forEach(li => search.list.appendChild(li));
  if (hint) {
    const li = document.createElement("li");
    li.className = "hint";
    li.textContent = hint;
    search.list.appendChild(li);
    return;
  }
  items.forEach(it => {
    const li = document.createElement("li");
    li.textContent = it.title;
    if (it.sub) { const sm = document.createElement("small"); sm.textContent = it.sub; li.appendChild(sm); }
    li.addEventListener("click", () => gotoSearchHit(it));
    search.list.appendChild(li);
  });
}

export function gotoSearchHit(it) {
  const ll = L.latLng(it.lat, it.lon);
  if (search.marker) map.removeLayer(search.marker);
  search.marker = L.marker(ll, { title: it.title }).addTo(map).bindPopup(it.title);
  // a spot knows its own extent, so show the whole forest — but capped, or a 5 ha patch would
  // fly to z19 and fill the screen with pink
  if (it.bounds) map.flyToBounds(it.bounds, { padding: [40, 40], maxZoom: 16, duration: 0.8 });
  else map.flyTo(ll, it.zoom || Math.max(map.getZoom(), 13), { duration: 0.8 });
  closeSearch();
  // no automatic inspection: the point of searching is to look at the map there, and the result
  // sheet would cover it. The marker is tappable like any other place on the map.
  search.marker.on("click", () => inspect(ll));
}

export async function runSearch(q) {
  const coords = parseCoords(q);
  if (coords) {
    showSearchResults([{ title: coords.label, sub: coords.lat.toFixed(5) + ", " + coords.lon.toFixed(5),
                         lat: coords.lat, lon: coords.lon, zoom: 15 }]);
    return;
  }
  if (q.length < 3) { showSearchResults([], "Kirjoita vähintään kolme merkkiä."); return; }
  if (search.abort) search.abort.abort();
  search.abort = new AbortController();
  showSearchResults([], "Haetaan…");
  const b = map.getBounds();
  const url = "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=8&countrycodes=fi" +
    "&accept-language=fi&viewbox=" + [b.getWest(), b.getNorth(), b.getEast(), b.getSouth()].join(",") +
    "&q=" + encodeURIComponent(q);
  try {
    const r = await fetch(url, { signal: search.abort.signal, headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error(r.status);
    const j = await r.json();
    if (!j.length) { showSearchResults([], "Ei osumia."); return; }
    showSearchResults(j.map(h => {
      const parts = h.display_name.split(", ");
      // a house number has no name of its own: "1, Hämeenkatu" reads better than "1"
      const title = h.name || parts.slice(0, 2).reverse().join(" ");
      return { title: title, sub: parts.slice(h.name ? 1 : 2).join(", "),
               lat: +h.lat, lon: +h.lon, zoom: h.type === "house" || h.addresstype === "road" ? 16 : 13 };
    }));
  } catch (e) {
    if (e.name !== "AbortError") showSearchResults([], "Haku ei juuri nyt onnistu — kokeile hetken päästä.");
  }
}

export function openSearch() {
  search.panel.classList.add("open");
  search.input.focus(); search.input.select();
}
export function closeSearch() {
  search.panel.classList.remove("open");
  search.input.blur();
}

export function initSearch() {
  search.panel = document.getElementById("searchPanel");
  search.input = document.getElementById("searchInput");
  search.list = document.getElementById("searchResults");
  document.getElementById("btnSearch").addEventListener("click", () => {
    if (search.panel.classList.contains("open")) closeSearch();
    else { closeOverlays(); openSearch(); renderNearby(); }   // opening fires no `input` event
  });
  search.input.addEventListener("input", () => {
    clearTimeout(search.timer);
    const q = search.input.value.trim();
    if (!q) { renderNearby(); return; }
    // repaint on the keystroke, not when the debounce fires, so the nearby list goes away the
    // moment you start typing rather than lingering under the query for another half second
    showSearchResults([], q.length < 3 ? "Kirjoita vähintään kolme merkkiä." : "Haetaan…");
    search.timer = setTimeout(() => runSearch(q), 600);      // Nominatim: no per-keystroke queries
  });
  search.input.addEventListener("keydown", e => {
    if (e.key === "Enter") { clearTimeout(search.timer); runSearch(search.input.value.trim()); }
    if (e.key === "Escape") closeSearch();
  });
  map.on("movestart", () => { if (document.activeElement !== search.input) closeSearch(); });
  map.on("moveend", nearbyFollowMap);
}
