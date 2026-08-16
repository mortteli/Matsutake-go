/**
 * Logic tests for the parts that are easy to get subtly wrong:
 * attribute normalisation, WFS axis order, the habitat score and — above all —
 * the slope/aspect maths, where a sign error silently points every hunter at
 * the wrong side of the hill.
 *
 * Run with:  node --test test/
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { normaliseStand, centroidOf, bboxOf } from '../js/wfs.js';
import { scoreStand, scoreColor, DEFAULT_FILTERS } from '../js/score.js';
import { fertilityName, speciesName, aspectAbbr, isCoarseSoil } from '../js/codes.js';

/* ── Geometry ───────────────────────────────────────────────────────── */

const square = (x0, y0, x1, y1) => ({
  type: 'Polygon',
  coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
});

test('centroid of a square is its middle', () => {
  const c = centroidOf(square(25, 65, 27, 67));
  assert.ok(Math.abs(c[0] - 26) < 1e-9, `lon ${c[0]}`);
  assert.ok(Math.abs(c[1] - 66) < 1e-9, `lat ${c[1]}`);
});

test('bbox covers the ring', () => {
  assert.deepEqual(bboxOf(square(25, 65, 27, 67)), [25, 65, 27, 67]);
});

test('lat/lon coordinates from the WFS get swapped back to lon/lat', () => {
  // A server that answers EPSG:4326 in lat,lon order.
  const s = normaliseStand({
    geometry: square(65, 25, 67, 27),   // (lat, lon) — the wrong way round
    properties: { standid: 1, fertilityclass: 5 },
  });
  assert.ok(s.lon > 19 && s.lon < 32, `lon should be a Finnish longitude, got ${s.lon}`);
  assert.ok(s.lat > 59 && s.lat < 71, `lat should be a Finnish latitude, got ${s.lat}`);
});

test('already-correct lon/lat coordinates are left alone', () => {
  const s = normaliseStand({
    geometry: square(25, 65, 27, 67),
    properties: { standid: 2 },
  });
  assert.ok(Math.abs(s.lon - 26) < 1e-6);
  assert.ok(Math.abs(s.lat - 66) < 1e-6);
});

/* ── Attribute normalisation ────────────────────────────────────────── */

test('attributes resolve regardless of case, underscores or Finnish naming', () => {
  const a = normaliseStand({
    geometry: square(25, 65, 25.01, 65.01),
    properties: { StandId: 'x', FertilityClass: 5, MainTreeSpecies: 1, MeanAge: 92, BasalArea: 11.5 },
  });
  const b = normaliseStand({
    geometry: square(25, 65, 25.01, 65.01),
    properties: { stand_id: 'y', kasvupaikka: 5, paapuulaji: 1, keskiika: 92, pohjapintaala: '11,5' },
  });
  for (const s of [a, b]) {
    assert.equal(s.fertility, 5);
    assert.equal(s.species, 1);
    assert.equal(s.age, 92);
    assert.equal(s.basalArea, 11.5);
  }
});

test('missing attributes become null, not zero', () => {
  const s = normaliseStand({ geometry: square(25, 65, 25.01, 65.01), properties: { standid: 3 } });
  assert.equal(s.age, null);
  assert.equal(s.fertility, null);
  assert.equal(s.basalArea, null);
});

test('coarse soils are recognised', () => {
  assert.equal(isCoarseSoil(15), true);   // hiekkamaa
  assert.equal(isCoarseSoil(16), true);   // sora / moreeni
  assert.equal(isCoarseSoil(60), false);  // turvemaa
});

/* ── Scoring ────────────────────────────────────────────────────────── */

const stand = (o) => ({
  id: 'x', fertility: 5, species: 1, age: 90, basalArea: 12,
  lat: 66, lon: 26, slope: 6, aspect: 180, coarseSoil: true, ...o,
});

test('the textbook stand scores very high', () => {
  const sc = scoreStand(stand({ fertility: 5, age: 130, basalArea: 8, slope: 7, aspect: 175, lat: 68 }));
  assert.equal(sc.pass, true);
  assert.ok(sc.score >= 88, `expected a prime score, got ${sc.score}`);
});

test('wrong site type is rejected outright', () => {
  const sc = scoreStand(stand({ fertility: 3 }));   // tuore kangas
  assert.equal(sc.pass, false);
  assert.ok(sc.reasons.includes('site'));
});

test('young stands are rejected by the age gate', () => {
  const sc = scoreStand(stand({ age: 35 }));
  assert.equal(sc.pass, false);
  assert.ok(sc.reasons.includes('age'));
});

test('spruce-dominated stands are rejected when pineOnly is on', () => {
  const sc = scoreStand(stand({ species: 2 }));
  assert.equal(sc.pass, false);
  assert.ok(sc.reasons.includes('species'));
});

test('north beats south, all else equal', () => {
  const north = scoreStand(stand({ lat: 69 })).score;
  const south = scoreStand(stand({ lat: 60.5 })).score;
  assert.ok(north > south, `${north} should beat ${south}`);
});

test('a slope beats dead-flat ground, all else equal', () => {
  const sloping = scoreStand(stand({ slope: 7 })).score;
  const flat = scoreStand(stand({ slope: 0.2 })).score;
  assert.ok(sloping > flat, `${sloping} should beat ${flat}`);
});

test('a south-facing slope beats a north-facing one', () => {
  const south = scoreStand(stand({ aspect: 180 })).score;
  const north = scoreStand(stand({ aspect: 0 })).score;
  assert.ok(south > north, `${south} should beat ${north}`);
});

test('an open lichen heath beats a dense one', () => {
  const open = scoreStand(stand({ basalArea: 7 })).score;
  const dense = scoreStand(stand({ basalArea: 25 })).score;
  assert.ok(open > dense, `${open} should beat ${dense}`);
});

test('unknown slope is treated as neutral, not as a failure', () => {
  const sc = scoreStand(stand({ slope: null, aspect: null }));
  assert.equal(sc.pass, true);
  const slopePart = sc.parts.find((p) => p.key === 'slope');
  assert.equal(slopePart.unknown, true);
  assert.ok(slopePart.pts > 0 && slopePart.pts < 15);
});

test('requireSlope only rejects when the slope is actually known and gentle', () => {
  const filters = { ...DEFAULT_FILTERS, requireSlope: true };
  assert.equal(scoreStand(stand({ slope: 0.5 }), filters).pass, false);
  assert.equal(scoreStand(stand({ slope: null }), filters).pass, true);
  assert.equal(scoreStand(stand({ slope: 8 }), filters).pass, true);
});

test('scores stay inside 0…100 across the whole input space', () => {
  for (const f of [4, 5, 6]) {
    for (const age of [60, 100, 300]) {
      for (const lat of [60, 70]) {
        for (const slope of [0, 5, 45]) {
          const sc = scoreStand(stand({ fertility: f, age, lat, slope }),
                                { ...DEFAULT_FILTERS, fertility: [4, 5, 6] });
          assert.ok(sc.score >= 0 && sc.score <= 100, `score ${sc.score} out of range`);
        }
      }
    }
  }
});

test('the colour ramp is monotone across the class boundaries', () => {
  assert.equal(scoreColor(95), '#ff2d6f');
  assert.equal(scoreColor(80), '#ff7a18');
  assert.equal(scoreColor(65), '#ffc531');
  assert.equal(scoreColor(50), '#9ad24a');
  assert.notEqual(scoreColor(20), scoreColor(50));
});

/* ── Code lists ─────────────────────────────────────────────────────── */

test('code lists translate both ways', () => {
  assert.equal(fertilityName(5, 'fi'), 'Kuiva kangas');
  assert.equal(fertilityName(5, 'en'), 'Dry heath (CT)');
  assert.equal(speciesName(1, 'fi'), 'Mänty');
  assert.equal(fertilityName(null), '—');
});

test('aspect degrees map to the right compass point', () => {
  assert.equal(aspectAbbr(0), 'P');      // pohjoinen
  assert.equal(aspectAbbr(90), 'I');     // itä
  assert.equal(aspectAbbr(180), 'E');    // etelä
  assert.equal(aspectAbbr(270), 'L');    // länsi
  assert.equal(aspectAbbr(359), 'P');
});
