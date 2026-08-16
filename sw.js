/**
 * Service worker: keep the app shell installable and usable in the forest,
 * where the map matters most and the network is worst.
 *
 * - App shell: cache-first, refreshed in the background.
 * - Map tiles: cache-first with a capped store, so the ground you already
 *   walked over stays on screen when the signal drops.
 * - WFS queries: never cached — stale stand data would be misleading.
 */

const VERSION = 'v1';
const SHELL = `matsutake-shell-${VERSION}`;
const TILES = `matsutake-tiles-${VERSION}`;
const TILE_LIMIT = 900;

const SHELL_FILES = [
  './',
  './index.html',
  './styles.css',
  './manifest.webmanifest',
  './js/app.js',
  './js/wfs.js',
  './js/score.js',
  './js/terrain.js',
  './js/sheet.js',
  './js/codes.js',
  './js/i18n.js',
  './js/waypoints.js',
  './icons/icon.svg',
  './icons/icon-192.png',
  './vendor/leaflet/leaflet.js',
  './vendor/leaflet/leaflet.css',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(SHELL)
      .then((c) => Promise.allSettled(SHELL_FILES.map((f) => c.add(f))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith('matsutake-') && k !== SHELL && k !== TILES)
            .map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

const isTile = (url) =>
  /tile\.openstreetmap\.org|tile\.opentopomap\.org|server\.arcgisonline\.com|avoin-karttakuva\.maanmittauslaitos\.fi|elevation-tiles-prod/.test(url);

async function trimCache(name, max) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  if (keys.length <= max) return;
  for (const k of keys.slice(0, keys.length - max)) await cache.delete(k);
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = request.url;

  // Live data only — a cached stand list is worse than none.
  if (/service=WFS|GetFeature|GetCapabilities/i.test(url)) return;

  if (isTile(url)) {
    event.respondWith((async () => {
      const cache = await caches.open(TILES);
      const hit = await cache.match(request);
      if (hit) return hit;
      try {
        const res = await fetch(request);
        if (res.ok || res.type === 'opaque') {
          cache.put(request, res.clone());
          trimCache(TILES, TILE_LIMIT);
        }
        return res;
      } catch (err) {
        return hit || Response.error();
      }
    })());
    return;
  }

  event.respondWith((async () => {
    const cache = await caches.open(SHELL);
    const hit = await cache.match(request, { ignoreSearch: false });
    const network = fetch(request).then((res) => {
      if (res.ok) cache.put(request, res.clone());
      return res;
    }).catch(() => null);
    return hit || (await network) || new Response('Offline', { status: 503 });
  })());
});
