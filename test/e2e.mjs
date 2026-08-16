/**
 * Browser smoke test.
 *
 * Serves the app, stubs the Forest Centre WFS and the tile hosts, then walks
 * the real UI: scan → polygons → tap a stand → open the list. Fails on any
 * console error. Writes screenshots to test/screenshots/.
 *
 * Run with:  node test/e2e.mjs
 */

import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SHOTS = path.join(ROOT, 'test', 'screenshots');
const PORT = 8199;

/* ── A tiny static file server ──────────────────────────────────────── */

const TYPES = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.webmanifest': 'application/manifest+json',
  '.svg': 'image/svg+xml', '.png': 'image/png',
};

const server = createServer(async (req, res) => {
  try {
    const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '') || 'index.html';
    const file = path.join(ROOT, rel);
    if (!file.startsWith(ROOT)) { res.writeHead(403).end(); return; }
    const body = await readFile(file);
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404).end('not found');
  }
});

/* ── Fake map and DEM tiles ─────────────────────────────────────────── */

function png(width, height, pixel) {
  const raw = Buffer.alloc(height * (1 + width * 4));
  for (let y = 0; y < height; y++) {
    const row = y * (1 + width * 4);
    raw[row] = 0;
    for (let x = 0; x < width; x++) {
      const p = row + 1 + x * 4;
      raw[p] = pixel[0]; raw[p + 1] = pixel[1]; raw[p + 2] = pixel[2]; raw[p + 3] = pixel[3];
    }
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(body) >>> 0);
    return Buffer.concat([len, body, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0); ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

let CRC_TABLE = null;
function crc32(buf) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Int32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[n] = c;
    }
  }
  let c = -1;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return c ^ -1;
}

const MAP_TILE = png(4, 4, [30, 44, 38, 255]);
// Terrarium encoding of a flat 200 m plateau: 128*256 + 200 − 32768 = 200.
const DEM_TILE = png(8, 8, [128, 200, 0, 255]);

/* ── Fake forest stands ─────────────────────────────────────────────── */

const CENTRE = { lat: 66.5, lon: 26.0 };

function box(i, props) {
  const d = 0.004;
  const lon = CENTRE.lon + (i % 4) * d * 2.2 - 0.012;
  const lat = CENTRE.lat + Math.floor(i / 4) * d - 0.006;
  return {
    type: 'Feature',
    id: `stand.${i}`,
    geometry: {
      type: 'Polygon',
      coordinates: [[[lon, lat], [lon + d * 1.8, lat], [lon + d * 1.8, lat + d * 0.8],
                     [lon, lat + d * 0.8], [lon, lat]]],
    },
    properties: { standid: 1000 + i, area: 3.2, ...props },
  };
}

const STANDS = {
  type: 'FeatureCollection',
  features: [
    box(0, { fertilityclass: 5, maintreespecies: 1, meanage: 145, basalarea: 8,  meanheight: 14, soiltype: 15, developmentclass: '04' }),
    box(1, { fertilityclass: 6, maintreespecies: 1, meanage: 110, basalarea: 6,  meanheight: 11, soiltype: 16, developmentclass: '04' }),
    box(2, { fertilityclass: 5, maintreespecies: 1, meanage: 72,  basalarea: 19, meanheight: 13, soiltype: 12, developmentclass: '03' }),
    box(3, { fertilityclass: 3, maintreespecies: 2, meanage: 80,  basalarea: 26, meanheight: 21, soiltype: 11, developmentclass: '04' }), // spruce, mesic — must be dropped
    box(4, { fertilityclass: 5, maintreespecies: 1, meanage: 30,  basalarea: 12, meanheight: 6,  soiltype: 15, developmentclass: 'T2' }), // too young — dropped
    box(5, { fertilityclass: 5, maintreespecies: 1, meanage: 95,  basalarea: 11, meanheight: 15, soiltype: 15, developmentclass: '04' }),
    box(6, { fertilityclass: 4, maintreespecies: 1, meanage: 100, basalarea: 15, meanheight: 16, soiltype: 12, developmentclass: '04' }), // VT — off by default
    box(7, { fertilityclass: 5, maintreespecies: 1, meanage: 125, basalarea: 9,  meanheight: 14, soiltype: 16, developmentclass: '04' }),
  ],
};

/* ── The run ────────────────────────────────────────────────────────── */

const fail = (msg) => { console.error(`✗ ${msg}`); process.exitCode = 1; };
const pass = (msg) => console.log(`✓ ${msg}`);

fs.mkdirSync(SHOTS, { recursive: true });
await new Promise((r) => server.listen(PORT, r));

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 },      // iPhone-ish
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true,
  serviceWorkers: 'block',
  permissions: ['geolocation'],
  geolocation: { latitude: CENTRE.lat - 0.002, longitude: CENTRE.lon - 0.004 },
  locale: 'fi-FI',
});

const errors = [];
let wfsCalls = 0;

await ctx.route('**/*', async (route) => {
  const url = route.request().url();
  if (url.startsWith(`http://localhost:${PORT}`)) return route.continue();

  if (/service=WFS/i.test(url)) {
    if (/GetCapabilities/i.test(url)) {
      return route.fulfill({
        contentType: 'text/xml',
        body: `<?xml version="1.0"?><WFS_Capabilities xmlns="http://www.opengis.net/wfs/2.0">
          <FeatureTypeList><FeatureType><Name>stands:stand</Name></FeatureType>
          <FeatureType><Name>stands:treestandsummary</Name></FeatureType></FeatureTypeList>
        </WFS_Capabilities>`,
      });
    }
    wfsCalls++;
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(STANDS) });
  }

  if (/elevation-tiles-prod/.test(url)) {
    return route.fulfill({ contentType: 'image/png', body: DEM_TILE,
                           headers: { 'Access-Control-Allow-Origin': '*' } });
  }
  if (/\.(png|jpg|jpeg)/.test(url)) {
    return route.fulfill({ contentType: 'image/png', body: MAP_TILE });
  }
  return route.abort();
});

const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));

await page.goto(`http://localhost:${PORT}/index.html`, { waitUntil: 'load' });
await page.waitForFunction(() => window.matsutake?.map, null, { timeout: 15000 });
pass('app booted');

// Land on the test area and let the scan run.
await page.evaluate(([lat, lon]) => {
  localStorage.setItem('mg.cfg', '{}');
  window.matsutake.map.setView([lat, lon], 14);
}, [CENTRE.lat, CENTRE.lon]);

await page.waitForFunction(() => window.matsutake.state.stands.length > 0, null, { timeout: 15000 });
await page.waitForTimeout(1500);

if (wfsCalls === 0) fail('the WFS was never queried');
else pass(`WFS queried (${wfsCalls}×)`);

const shown = await page.evaluate(() => ({
  total: window.matsutake.state.stands.length,
  visible: window.matsutake.state.visible.length,
  ids: window.matsutake.state.visible.map((v) => v.s.raw.standid),
  scores: window.matsutake.state.visible.map((v) => v.sc.score),
  slope: window.matsutake.state.visible[0]?.s.slope,
  elevation: window.matsutake.state.visible[0]?.s.elevation,
}));

if (shown.total !== 8) fail(`expected 8 stands from the WFS, got ${shown.total}`);
else pass('all 8 stands parsed');

// 1003 spruce/mesic, 1004 too young, 1006 sub-dry heath (off by default) must be filtered out.
const dropped = [1003, 1004, 1006].filter((id) => shown.ids.includes(id));
if (dropped.length) fail(`these should have been filtered out: ${dropped.join(', ')}`);
else pass(`filters kept ${shown.visible} of 8 stands (${shown.ids.join(', ')})`);

if (!shown.scores.every((s, i, a) => i === 0 || a[i - 1] >= s)) fail('list is not sorted by score');
else pass(`scores sorted high→low: ${shown.scores.join(', ')}`);

if (shown.elevation !== 200) fail(`DEM should read 200 m, got ${shown.elevation}`);
else pass('elevation decoded from the DEM tiles (200 m, flat)');

// `hidden` must actually hide: these elements set display:flex/grid in CSS.
const ctaVisible = await page.evaluate(() => {
  const el = document.getElementById('scan-cta');
  return el.offsetParent !== null || getComputedStyle(el).display !== 'none';
});
if (ctaVisible) fail('the "search this area" button should be hidden after an automatic scan');
else pass('scan button stays hidden while auto-scan is working');

const badge = await page.textContent('#list-badge');
if (badge !== String(shown.visible)) fail(`badge says ${badge}, expected ${shown.visible}`);
else pass(`badge shows ${badge}`);

await page.screenshot({ path: path.join(SHOTS, '01-map.png') });

// Tap the best stand and check the detail sheet.
await page.evaluate(() => window.matsutake.selectStand(window.matsutake.state.visible[0].s.id));
await page.waitForTimeout(400);
const sheetOpen = await page.evaluate(() => document.getElementById('sheet').classList.contains('open'));
if (!sheetOpen) fail('the detail sheet did not open');
else pass('detail sheet opens');

const sheetText = await page.textContent('#sheet-content');
for (const needle of ['Kuiva kangas', 'Mänty', 'Kasvupaikka', 'Tallenna kohde']) {
  if (!sheetText.includes(needle)) fail(`the sheet is missing "${needle}"`);
}
pass('detail sheet shows the site type, species and score breakdown');
await page.screenshot({ path: path.join(SHOTS, '02-stand.png') });

const distanceShown = /\d+\s?(m|km)/.test(sheetText);
if (!distanceShown) fail('the sheet should show the distance from the GPS fix');
else pass('distance from the GPS fix is shown');

// Save it, and check it survives into the waypoint list.
await page.click('[data-act="save"]');
await page.waitForTimeout(300);
const savedCount = await page.evaluate(() => JSON.parse(localStorage.getItem('mg.waypoints') || '[]').length);
if (savedCount !== 1) fail(`expected 1 saved spot, got ${savedCount}`);
else pass('spot saved to the waypoint list');

// The map must stay live under the sheet, and a tap on it dismisses the sheet.
const mapLive = await page.evaluate(() => document.getElementById('scrim').hidden);
if (!mapLive) fail('the sheet should not put a scrim over the map');
else pass('map stays interactive while the sheet is open');

const locateReachable = await page.evaluate(() => {
  const r = document.getElementById('btn-locate').getBoundingClientRect();
  const sheet = document.getElementById('sheet').getBoundingClientRect();
  return r.bottom <= sheet.top + 1 && r.top > 0;
});
if (!locateReachable) fail('the locate button is hidden behind the sheet');
else pass('locate button lifts clear of the sheet');

await page.evaluate(() => window.matsutake.map.fire('click'));
await page.waitForTimeout(400);
if (await page.evaluate(() => document.getElementById('sheet').classList.contains('open'))) {
  fail('tapping the map did not dismiss the sheet');
} else pass('tapping the map dismisses the sheet');

// The "best in view" list.
await page.click('#btn-list');
await page.waitForTimeout(400);
const items = await page.locator('.rl-item').count();
if (items !== shown.visible) fail(`list shows ${items} rows, expected ${shown.visible}`);
else pass(`list shows all ${items} matches with distances`);
await page.screenshot({ path: path.join(SHOTS, '03-list.png') });

// Settings drawer, and the layer probe against GetCapabilities.
await page.evaluate(() => window.matsutake.map.fire('click'));
await page.waitForTimeout(300);
await page.click('#btn-menu');
await page.waitForTimeout(400);
await page.screenshot({ path: path.join(SHOTS, '04-settings.png') });

await page.click('#btn-test');
await page.waitForTimeout(800);
const testOut = await page.textContent('#test-out');
if (!testOut.includes('stands:stand')) fail(`layer probe failed: ${testOut}`);
else pass('layer probe reads GetCapabilities');

// Widening the filters must bring the sub-dry heath stand back.
await page.click('.chip[data-ft="4"]');
await page.waitForTimeout(500);
const withVt = await page.evaluate(() => window.matsutake.state.visible.map((v) => v.s.raw.standid));
if (!withVt.includes(1006)) fail('enabling kuivahko kangas did not bring stand 1006 back');
else pass('filter chips re-score the map live');

if (errors.length) {
  fail(`console errors:\n  ${errors.join('\n  ')}`);
} else {
  pass('no console errors');
}

await browser.close();
server.close();

console.log(process.exitCode ? '\nFAILED' : '\nAll checks passed.');
