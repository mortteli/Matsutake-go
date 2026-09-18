import { FIX_MAX_AGE_MS } from "./constants.js";
import { map } from "./maplayer.js";
import { nearbyWaiting, renderNearby } from "./nearby.js";
import { toast } from "./ui.js";

/* ================= GPS ================= */
export let gpsMarker = null, gpsCircle = null, gpsWatch = null, follow = false, firstFix = true;
// The last known position, kept in memory only: a home address in localStorage would buy
// nothing and would quietly hand the nearby list spots from 300 km away after a train ride.
export let lastFix = null;
export const btnLocate = document.getElementById("btnLocate");

export function gpsUpdate(pos) {
  lastFix = { lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy, t: Date.now() };
  const ll = [pos.coords.latitude, pos.coords.longitude];
  if (!gpsMarker) {
    gpsMarker = L.marker(ll, {
      icon: L.divIcon({ className: "gps-dot", html: '<span class="pulse"></span><span class="core"></span>',
        iconSize: [16, 16] }),
      interactive: false, zIndexOffset: 1000,
    }).addTo(map);
    gpsCircle = L.circle(ll, { radius: pos.coords.accuracy || 0, weight: 1,
      color: "#2e86ff", fillColor: "#2e86ff", fillOpacity: 0.12, interactive: false }).addTo(map);
  } else {
    gpsMarker.setLatLng(ll);
    gpsCircle.setLatLng(ll).setRadius(pos.coords.accuracy || 0);
  }
  if (firstFix) { firstFix = false; map.setView(ll, Math.max(map.getZoom(), 13)); }
  else if (follow) map.panTo(ll, { animate: true });
  // the fix may be the one an open, empty search panel was waiting for
  if (nearbyWaiting()) renderNearby();
}
export function gpsError(err) {
  toast(err.code === 1 ? "Salli sijainti selaimen asetuksista 📍" : "Sijaintia ei saatu — yritä uudelleen");
  stopGps();
  // an open list may be waiting on this fix; it has to fall back to the map view, not hang
  if (nearbyWaiting()) renderNearby();
}
export function startGps() {
  if (!navigator.geolocation) { toast("Selain ei tue paikannusta"); return; }
  follow = true; firstFix = !gpsMarker;
  btnLocate.classList.add("active");
  if (gpsWatch == null)
    gpsWatch = navigator.geolocation.watchPosition(gpsUpdate, gpsError,
      { enableHighAccuracy: true, maximumAge: 3000, timeout: 20000 });
  if (gpsMarker) map.setView(gpsMarker.getLatLng(), Math.max(map.getZoom(), 13));
}
export function stopGps() {
  // note: the watch itself is deliberately left running — the marker stays live and `lastFix`
  // stays fresh, so the nearby list does not have to re-acquire a fix every time it opens.
  follow = false;
  btnLocate.classList.remove("active");
}
/* A position for the nearby list, without ever raising a permission prompt on its own. Tapping
   🔎 must not feel like tapping 📍, so the only silent path is one the user has already granted;
   everything else comes back as a reason the panel can render. */
export async function ensureFix() {
  if (lastFix && Date.now() - lastFix.t < FIX_MAX_AGE_MS) return lastFix;
  if (!navigator.geolocation) return { reason: "unsupported" };
  let granted = false;
  try {
    // no Permissions API (older Safari) -> treat as "ask", i.e. leave it to the 📍 button
    granted = !!navigator.permissions && (await navigator.permissions.query({ name: "geolocation" })).state === "granted";
  } catch (e) { granted = false; }
  if (!granted) return { reason: lastFix ? "stale" : "off" };
  try {
    const pos = await new Promise((res, rej) => navigator.geolocation.getCurrentPosition(res, rej,
      { maximumAge: FIX_MAX_AGE_MS, timeout: 8000 }));
    // deliberately not gpsUpdate(): that would drop a marker and, on the first fix, yank the map
    // out from under someone who only opened a search box
    lastFix = { lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy, t: Date.now() };
    return lastFix;
  } catch (e) {
    return lastFix || { reason: e && e.code === 1 ? "denied" : "off" };
  }
}
btnLocate.addEventListener("click", () => (follow ? stopGps() : startGps()));
map.on("dragstart", () => { if (follow) stopGps(); });
