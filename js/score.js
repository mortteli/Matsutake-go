/**
 * Matsutake habitat scoring.
 *
 * Tricholoma matsutake (tuoksuvalmuska) in Finland fruits in dry, lichen-rich
 * pine heaths — kuiva kangas (CT) and karukkokangas (ClT) — under old Scots
 * pine, very often on the sloping shoulder of an esker, a road cut or a bank
 * where the mineral soil is coarse and the canopy is open. It gets commoner
 * towards the north.
 *
 * Every component returns points out of its weight; the weights sum to 100.
 * The model is deliberately transparent: the UI shows each component so the
 * picker can judge the reasoning instead of trusting a black box.
 */

export const WEIGHTS = {
  site: 25,     // kasvupaikkatyyppi — the hard requirement, dry heath
  age: 25,      // vanha mänty
  lichen: 15,   // jäkälä / avoimuus (proxied by stand density + site type)
  slope: 15,    // rinne
  aspect: 5,    // ilmansuunta (lämmin rinne)
  north: 15,    // pohjoisuus
};

export const DEFAULT_FILTERS = {
  fertility: [5, 6],   // kuiva kangas + karukkokangas
  minAge: 60,
  minScore: 45,
  pineOnly: true,
  requireSlope: false,
  useTerrain: true,
};

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Piecewise-linear interpolation over [[x,y], …] with x ascending. */
function ramp(x, points) {
  if (x == null || !isFinite(x)) return null;
  if (x <= points[0][0]) return points[0][1];
  const last = points[points.length - 1];
  if (x >= last[0]) return last[1];
  for (let i = 1; i < points.length; i++) {
    const [x0, y0] = points[i - 1], [x1, y1] = points[i];
    if (x <= x1) return y0 + (y1 - y0) * ((x - x0) / (x1 - x0));
  }
  return last[1];
}

/* ── Components ─────────────────────────────────────────────────────── */

function siteScore(fertility) {
  switch (fertility) {
    case 5: return WEIGHTS.site;            // kuiva kangas — the classic
    case 6: return WEIGHTS.site * 0.88;     // karukkokangas — jäkälää, joskus liian karu
    case 4: return WEIGHTS.site * 0.55;     // kuivahko kangas — reunatapaus
    case 7: return WEIGHTS.site * 0.35;     // kalliomaa / hietikko
    default: return 0;
  }
}

function ageScore(age) {
  // Nothing before ~50 a; the curve keeps climbing well past 100 a because the
  // best matsutake stands are genuinely old, slow-grown pine.
  if (age == null) return { pts: WEIGHTS.age * 0.3, unknown: true };
  const t = clamp((age - 50) / 100, 0, 1);
  return { pts: Math.pow(t, 0.7) * WEIGHTS.age, unknown: false };
}

/**
 * Lichen / openness. There is no direct "jäkälä" attribute in the open forest
 * data, so we proxy it: barren heath is lichen-dominated by definition, and on
 * dry heath a low basal area means an open, light-flooded floor where reindeer
 * lichen and matsutake both thrive.
 */
function lichenScore(fertility, basalArea, coarseSoil) {
  const W = WEIGHTS.lichen;
  let pts;
  let unknown = false;
  if (fertility === 6) {
    pts = W;                                        // ClT = jäkälätyyppi
  } else if (basalArea == null) {
    pts = W * 0.45; unknown = true;
  } else {
    pts = ramp(basalArea, [[6, W], [12, W * 0.85], [18, W * 0.5], [26, W * 0.15]]);
  }
  if (coarseSoil) pts = Math.min(W, pts + W * 0.1);
  return { pts, unknown };
}

function slopeScore(slopeDeg) {
  if (slopeDeg == null) return { pts: WEIGHTS.slope * 0.42, unknown: true };
  // Gentle-to-moderate slopes drain well and warm up; cliffs do neither.
  const pts = ramp(slopeDeg, [
    [0, WEIGHTS.slope * 0.20],
    [1.5, WEIGHTS.slope * 0.45],
    [3, WEIGHTS.slope * 0.85],
    [6, WEIGHTS.slope],
    [14, WEIGHTS.slope],
    [22, WEIGHTS.slope * 0.6],
    [32, WEIGHTS.slope * 0.3],
  ]);
  return { pts, unknown: false };
}

function aspectScore(aspectDeg, slopeDeg) {
  const W = WEIGHTS.aspect;
  if (aspectDeg == null || slopeDeg == null || slopeDeg < 1.5) {
    return { pts: W * 0.5, unknown: true };
  }
  // 180° = south. Warm southern shoulders fruit first and hardest.
  const off = Math.abs(((aspectDeg - 180 + 540) % 360) - 180); // 0 = due south
  const pts = ramp(off, [[0, W], [60, W * 0.85], [110, W * 0.5], [180, W * 0.2]]);
  return { pts, unknown: false };
}

function northScore(lat) {
  if (lat == null) return { pts: WEIGHTS.north * 0.4, unknown: true };
  // Finland spans ~59.8–70.1 °N. The north is where the good years happen.
  const pts = ramp(lat, [[60, WEIGHTS.north * 0.2], [64, WEIGHTS.north * 0.5],
                         [66.5, WEIGHTS.north * 0.8], [69, WEIGHTS.north]]);
  return { pts, unknown: false };
}

/* ── Main entry ─────────────────────────────────────────────────────── */

/**
 * @param {object} s   normalised stand (see wfs.js normaliseStand)
 * @param {object} f   active filters
 * @returns {{score:number, pass:boolean, reasons:string[], parts:object[]}}
 */
export function scoreStand(s, f = DEFAULT_FILTERS) {
  const reject = [];

  // Hard gates — these are the picker's non-negotiables.
  if (!f.fertility.includes(s.fertility)) reject.push('site');
  if (f.pineOnly && s.species != null && s.species !== 1 && s.species !== 10) reject.push('species');
  if (s.age != null && s.age < f.minAge) reject.push('age');
  if (f.requireSlope && s.slope != null && s.slope < 3) reject.push('slope');

  const site = siteScore(s.fertility);
  const age = ageScore(s.age);
  const lichen = lichenScore(s.fertility, s.basalArea, s.coarseSoil);
  const slope = slopeScore(s.slope);
  const aspect = aspectScore(s.aspect, s.slope);
  const north = northScore(s.lat);

  let total = site + age.pts + lichen.pts + slope.pts + aspect.pts + north.pts;

  // A spruce-led or young stand that slipped past a null check should not
  // masquerade as a good spot.
  if (s.species != null && s.species !== 1 && s.species !== 10) total *= 0.45;

  const parts = [
    { key: 'site',   pts: site,       max: WEIGHTS.site,   unknown: false },
    { key: 'age',    pts: age.pts,    max: WEIGHTS.age,    unknown: age.unknown },
    { key: 'lichen', pts: lichen.pts, max: WEIGHTS.lichen, unknown: lichen.unknown },
    { key: 'slope',  pts: slope.pts,  max: WEIGHTS.slope,  unknown: slope.unknown },
    { key: 'aspect', pts: aspect.pts, max: WEIGHTS.aspect, unknown: aspect.unknown },
    { key: 'north',  pts: north.pts,  max: WEIGHTS.north,  unknown: north.unknown },
  ];

  return {
    score: Math.round(clamp(total, 0, 100)),
    pass: reject.length === 0,
    reasons: reject,
    parts,
  };
}

/** Colour ramp shared by polygons, list badges and the score dial. */
export function scoreColor(score) {
  if (score >= 90) return '#ff2d6f';
  if (score >= 75) return '#ff7a18';
  if (score >= 60) return '#ffc531';
  if (score >= 45) return '#9ad24a';
  return '#6f8a7c';
}

export function scoreLabel(score, lang = 'fi') {
  const fi = ['ei suositella', 'mahdollinen', 'hyvä', 'erinomainen', 'huippupaikka'];
  const en = ['unlikely', 'possible', 'good', 'excellent', 'prime spot'];
  const i = score >= 90 ? 4 : score >= 75 ? 3 : score >= 60 ? 2 : score >= 45 ? 1 : 0;
  return (lang === 'en' ? en : fi)[i];
}
