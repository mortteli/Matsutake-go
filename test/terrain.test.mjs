/**
 * Slope/aspect tests against a synthetic elevation model.
 *
 * A sign error in the Horn kernel would send the user to the shady north side
 * of every esker, so the aspect is checked against known artificial terrain:
 * a plane rising east, a plane rising north, and dead-flat ground.
 *
 * The Terrarium tiles are faked by stubbing Image and canvas, encoding the
 * synthetic elevations exactly as the real tiles do:
 *   elevation = R * 256 + G + B / 256 − 32768
 */

import test from 'node:test';
import assert from 'node:assert/strict';

/** Current synthetic terrain: (globalPixelX, globalPixelY) → metres. */
let elevFn = () => 0;

class FakeImage {
  set src(v) { this._src = v; queueMicrotask(() => this.onload?.()); }
  get src() { return this._src; }
}

globalThis.Image = FakeImage;
globalThis.document = {
  createElement(tag) {
    assert.equal(tag, 'canvas');
    let drawn = null;
    return {
      width: 0, height: 0,
      getContext: () => ({
        drawImage: (img) => { drawn = img; },
        getImageData: (_x, _y, w, h) => {
          const m = /\/(\d+)\/(\d+)\/(\d+)\.png/.exec(drawn.src);
          const tx = Number(m[2]), ty = Number(m[3]);
          const data = new Uint8ClampedArray(w * h * 4);
          for (let iy = 0; iy < h; iy++) {
            for (let ix = 0; ix < w; ix++) {
              const v = Math.round((elevFn(tx * 256 + ix, ty * 256 + iy) + 32768) * 256);
              const p = (iy * w + ix) * 4;
              data[p] = (v >> 16) & 255;
              data[p + 1] = (v >> 8) & 255;
              data[p + 2] = v & 255;
              data[p + 3] = 255;
            }
          }
          return { data };
        },
      }),
    };
  },
};

const { terrainAt } = await import('../js/terrain.js');

/** Metres per DEM pixel — mirrors the constant used inside terrain.js. */
const pxMetres = (lat, z = 12) => (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** z;

/** Web-mercator global pixel coordinates, same projection terrain.js uses. */
function project(lon, lat, z = 12) {
  const n = 256 * 2 ** z;
  const s = Math.sin((lat * Math.PI) / 180);
  return [((lon + 180) / 360) * n, (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * n];
}

/**
 * A tilted plane anchored at (lon, lat), so elevations stay in a realistic
 * range instead of running to hundreds of kilometres at the antimeridian.
 * `east`/`south` are metres of rise per pixel in those directions.
 */
function plane(lon, lat, { east = 0, south = 0, base = 200 } = {}) {
  const [rx, ry] = project(lon, lat);
  return (gx, gy) => base + east * (gx - rx) + south * (gy - ry);
}

/* Each test uses a location far from the others so the tile cache cannot
   serve one test's terrain to another. */

test('a plane rising to the east reads as a west-facing slope', async () => {
  const K = 1.0;                      // metres of rise per DEM pixel eastward
  const lat = 66, lon = 26;
  elevFn = plane(lon, lat, { east: K });
  const t = await terrainAt(lon, lat);
  assert.ok(t, 'expected a terrain reading');

  const expected = (Math.atan(K / pxMetres(lat)) * 180) / Math.PI;
  assert.ok(Math.abs(t.slope - expected) < 0.05,
    `slope ${t.slope.toFixed(3)}° should be ≈${expected.toFixed(3)}°`);
  assert.ok(Math.abs(t.aspect - 270) < 0.5,
    `aspect ${t.aspect?.toFixed(1)}° should be ≈270° (downhill to the west)`);
});

test('a plane rising to the north reads as a south-facing slope', async () => {
  const K = 1.0;
  const lat = 62, lon = 20;
  // Pixel y grows southward, so a negative south-gradient rises to the north.
  elevFn = plane(lon, lat, { south: -K });
  const t = await terrainAt(lon, lat);
  assert.ok(t, 'expected a terrain reading');

  const expected = (Math.atan(K / pxMetres(lat)) * 180) / Math.PI;
  assert.ok(Math.abs(t.slope - expected) < 0.05,
    `slope ${t.slope.toFixed(3)}° should be ≈${expected.toFixed(3)}°`);
  assert.ok(Math.abs(t.aspect - 180) < 0.5,
    `aspect ${t.aspect?.toFixed(1)}° should be ≈180° (downhill to the south)`);
});

test('flat ground has zero slope and no aspect', async () => {
  elevFn = () => 214;

  const t = await terrainAt(30, 68);
  assert.ok(t, 'expected a terrain reading');
  assert.ok(t.slope < 0.01, `slope ${t.slope} should be ~0`);
  assert.equal(t.aspect, null, 'flat ground must not claim a direction');
  assert.ok(Math.abs(t.elevation - 214) < 0.01, `elevation ${t.elevation} should be 214`);
});

test('a south-east facing slope reports an aspect between south and east', async () => {
  // Rises to the west and to the north → downhill towards the south-east (135°).
  const K = 1.0;
  elevFn = plane(24, 60.5, { east: -K, south: -K });

  const t = await terrainAt(24, 60.5);
  assert.ok(t, 'expected a terrain reading');
  assert.ok(Math.abs(t.aspect - 135) < 1,
    `aspect ${t.aspect?.toFixed(1)}° should be ≈135° (south-east)`);
});

test('a north-east facing slope reports the opposite aspect', async () => {
  // Mirror image of the case above: rises to the south-west, drains north-east.
  const K = 1.0;
  elevFn = plane(29.5, 63.7, { east: -K, south: K });

  const t = await terrainAt(29.5, 63.7);
  assert.ok(t, 'expected a terrain reading');
  assert.ok(Math.abs(t.aspect - 45) < 1,
    `aspect ${t.aspect?.toFixed(1)}° should be ≈45° (north-east)`);
});

test('a steeper plane reports a steeper slope', async () => {
  elevFn = plane(28.5, 69.4, { east: 0.2 });
  const gentle = await terrainAt(28.5, 69.4);

  elevFn = plane(22.5, 61.2, { east: 3.0 });
  const steep = await terrainAt(22.5, 61.2);

  assert.ok(steep.slope > gentle.slope * 5,
    `${steep.slope.toFixed(2)}° should be far steeper than ${gentle.slope.toFixed(2)}°`);
});
