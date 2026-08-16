/**
 * WFS request tests with a stubbed fetch.
 *
 * The service's EPSG:4326 axis order cannot be known in advance, so the client
 * probes it. These tests pin down that probing — in particular that an empty
 * answer (a stretch of forest with no mapped stands) never locks in an axis
 * order that was never confirmed.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import { fetchStands, resetProbe } from '../js/wfs.js';

const BOUNDS = { south: 66.4, west: 25.9, north: 66.6, east: 26.1 };
const CFG = { wfsUrl: 'https://example.test/ows', layer: 'stands:stand' };

const feature = (coords) => ({
  type: 'Feature',
  geometry: { type: 'Polygon', coordinates: [coords] },
  properties: { standid: 7, fertilityclass: 5, maintreespecies: 1, meanage: 90 },
});

const LONLAT = feature([[25.9, 66.4], [26.0, 66.4], [26.0, 66.5], [25.9, 66.4]]);
const LATLON = feature([[66.4, 25.9], [66.4, 26.0], [66.5, 26.0], [66.4, 25.9]]);

/** Installs a fetch stub and records every URL it is asked for. */
function stubFetch(handler) {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    const body = handler(url, calls.length);
    return {
      ok: body.ok !== false,
      status: body.status ?? 200,
      text: async () => body.text,
    };
  };
  return calls;
}

const bboxOf = (url) => new URL(url).searchParams.get('bbox');

test('a normal answer is parsed and the request carries the bbox and layer', async () => {
  resetProbe();
  const calls = stubFetch(() => ({ text: JSON.stringify({ features: [LONLAT] }) }));

  const { stands } = await fetchStands(BOUNDS, CFG);
  assert.equal(stands.length, 1);
  assert.equal(stands[0].fertility, 5);

  const url = new URL(calls[0]);
  assert.equal(url.searchParams.get('typeNames'), 'stands:stand');
  assert.equal(url.searchParams.get('outputFormat'), 'application/json');
  assert.match(url.searchParams.get('bbox'), /EPSG:4326$/);
  assert.equal(bboxOf(calls[0]).split(',')[0], '25.900000', 'first bbox attempt should be lon-first');
});

test('an empty lon/lat answer triggers one retry with the axes swapped', async () => {
  resetProbe();
  const calls = stubFetch((url) => {
    // This server only understands lat,lon order.
    const lonFirst = bboxOf(url).startsWith('25.9');
    return { text: JSON.stringify({ features: lonFirst ? [] : [LATLON] }) };
  });

  const { stands } = await fetchStands(BOUNDS, CFG);
  assert.equal(calls.length, 2, 'expected exactly one retry');
  assert.equal(stands.length, 1);
  // The lat/lon geometry must still come out as usable Finnish coordinates.
  assert.ok(stands[0].lon > 19 && stands[0].lon < 32);
  assert.ok(stands[0].lat > 59 && stands[0].lat < 71);
});

test('once the axis order is known, later requests use it directly', async () => {
  resetProbe();
  let calls = stubFetch((url) => {
    const lonFirst = bboxOf(url).startsWith('25.9');
    return { text: JSON.stringify({ features: lonFirst ? [] : [LATLON] }) };
  });
  await fetchStands(BOUNDS, CFG);
  assert.equal(calls.length, 2);

  calls = stubFetch(() => ({ text: JSON.stringify({ features: [LATLON] }) }));
  await fetchStands(BOUNDS, CFG);
  assert.equal(calls.length, 1, 'the remembered axis order should be used straight away');
  assert.equal(bboxOf(calls[0]).split(',')[0], '66.400000');
});

test('an area with genuinely no stands does not lock in a wrong axis order', async () => {
  resetProbe();
  let calls = stubFetch(() => ({ text: JSON.stringify({ features: [] }) }));

  const empty = await fetchStands(BOUNDS, CFG);
  assert.equal(empty.stands.length, 0);
  assert.equal(calls.length, 2, 'both orders should have been tried');

  // Now move somewhere that does have stands, in the ordinary lon/lat order.
  calls = stubFetch(() => ({ text: JSON.stringify({ features: [LONLAT] }) }));
  const { stands } = await fetchStands(BOUNDS, CFG);
  assert.equal(stands.length, 1);
  assert.equal(bboxOf(calls[0]).split(',')[0], '25.900000',
    'an earlier empty area must not have pinned the axis order to lat/lon');
});

test('a GeoServer XML exception surfaces as a readable error', async () => {
  resetProbe();
  stubFetch(() => ({
    text: '<?xml version="1.0"?><ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1">' +
          '<ows:Exception><ows:ExceptionText>Unknown type name stands:stand</ows:ExceptionText>' +
          '</ows:Exception></ows:ExceptionReport>',
  }));

  await assert.rejects(() => fetchStands(BOUNDS, CFG), /Unknown type name/);
});

test('an HTTP error surfaces with its status code', async () => {
  resetProbe();
  stubFetch(() => ({ ok: false, status: 503, text: 'Service Unavailable' }));
  await assert.rejects(() => fetchStands(BOUNDS, CFG), /503/);
});

test('the truncation flag is set when the server fills the feature limit', async () => {
  resetProbe();
  stubFetch(() => ({ text: JSON.stringify({ features: Array(50).fill(LONLAT) }) }));
  const { truncated } = await fetchStands(BOUNDS, { ...CFG, count: 50 });
  assert.equal(truncated, true);
});

test('a CORS proxy is applied to the request URL when configured', async () => {
  resetProbe();
  const calls = stubFetch(() => ({ text: JSON.stringify({ features: [LONLAT] }) }));
  await fetchStands(BOUNDS, { ...CFG, proxy: 'https://proxy.test/?url=' });
  assert.ok(calls[0].startsWith('https://proxy.test/?url='), calls[0]);
  assert.ok(decodeURIComponent(calls[0]).includes('https://example.test/ows'));
});

// GetCapabilities parsing needs a DOM, so it is covered by test/e2e.mjs instead.
