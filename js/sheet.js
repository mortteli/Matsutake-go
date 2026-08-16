/** Bottom-sheet content: stand detail and the "best in view" list. */

import { t, getLang } from './i18n.js';
import { fertilityName, speciesName, devClassName, soilName, aspectName, aspectAbbr } from './codes.js';
import { scoreColor, scoreLabel } from './score.js';

const esc = (s) => String(s ?? '').replace(/[<>&"]/g, (c) =>
  ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));

const n1 = (v, unit = '') => (v == null ? '—' : `${v.toFixed(1)}${unit}`);
const n0 = (v, unit = '') => (v == null ? '—' : `${Math.round(v)}${unit}`);

/** Slope as a phrase: dead-flat ground has no meaningful direction to report. */
export function slopeText(s) {
  if (s.slope == null) return null;
  if (s.slope < 1.5) return t('f.flat');
  return `${s.slope.toFixed(s.slope < 10 ? 1 : 0)}° ${aspectAbbr(s.aspect)}`;
}

export function formatDistance(m) {
  if (m == null) return '';
  return m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(m < 10000 ? 1 : 0)} km`;
}

/** Great-circle distance and initial bearing between two WGS84 points. */
export function distanceBearing(from, to) {
  const R = 6371000, rad = Math.PI / 180;
  const φ1 = from.lat * rad, φ2 = to.lat * rad;
  const dφ = (to.lat - from.lat) * rad, dλ = (to.lng - from.lng) * rad;
  const a = Math.sin(dφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(dλ / 2) ** 2;
  const dist = 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
  const y = Math.sin(dλ) * Math.cos(φ2);
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(dλ);
  return { dist, bearing: ((Math.atan2(y, x) / rad) + 360) % 360 };
}

function dial(score) {
  const c = scoreColor(score);
  const deg = Math.round((score / 100) * 360);
  return `<div class="score-dial" style="background:conic-gradient(${c} ${deg}deg, #263229 ${deg}deg)">
    <div style="position:absolute;inset:6px;border-radius:50%;background:var(--bg-2);display:grid;place-items:center">
      <b style="color:${c}">${score}</b><small>/100</small>
    </div>
  </div>`;
}

function bars(parts) {
  return `<div class="bars">${parts.map((p) => {
    const pct = Math.round((p.pts / p.max) * 100);
    const c = pct >= 75 ? '#4ade80' : pct >= 45 ? '#ffc531' : '#ff7a18';
    return `<div class="bar-row">
      <span class="lbl">${esc(t('part.' + p.key))}${p.unknown ? ` <em style="font-style:normal;opacity:.55">(${esc(t('sheet.estimated'))})</em>` : ''}</span>
      <span class="val">${p.pts.toFixed(0)}/${p.max}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${pct}%;background:${c}"></span></span>
    </div>`;
  }).join('')}</div>`;
}

/** One plain-language sentence about why this stand looks the way it does. */
function verdict(s, sc) {
  const lang = getLang();
  const bits = [];
  const fi = lang === 'fi';

  if (s.fertility === 5) bits.push(fi ? 'kuivaa kangasta' : 'dry heath');
  else if (s.fertility === 6) bits.push(fi ? 'karukkokangasta, jäkälää yleensä runsaasti' : 'barren lichen heath');
  else if (s.fertility === 4) bits.push(fi ? 'kuivahkoa kangasta — reunatapaus' : 'sub-dry heath — borderline');

  if (s.age != null) {
    bits.push(fi ? `männikkö ${Math.round(s.age)} v` : `pine stand ${Math.round(s.age)} yr`);
  }
  if (s.basalArea != null && s.basalArea <= 14) {
    bits.push(fi ? 'puusto harvaa ja valoisaa' : 'open, light-flooded canopy');
  }
  if (s.slope != null) {
    if (s.slope >= 3) {
      bits.push(fi
        ? `rinne ${s.slope.toFixed(0)}° ${aspectName(s.aspect, 'fi')}`
        : `slope ${s.slope.toFixed(0)}° facing ${aspectName(s.aspect, 'en')}`);
    } else {
      bits.push(fi ? 'maasto lähes tasaista' : 'nearly flat ground');
    }
  }
  if (s.lat != null && s.lat >= 66) bits.push(fi ? 'napapiirin pohjoispuolella' : 'north of the Arctic Circle');

  const head = fi
    ? `${scoreLabel(sc.score, 'fi')[0].toUpperCase()}${scoreLabel(sc.score, 'fi').slice(1)}`
    : `${scoreLabel(sc.score, 'en')[0].toUpperCase()}${scoreLabel(sc.score, 'en').slice(1)}`;

  return `<div class="verdict"><strong>${esc(head)}.</strong> ${esc(bits.join(', '))}.</div>`;
}

export function renderStand(s, sc, opts = {}) {
  const lang = getLang();
  const facts = [
    [t('f.type'), fertilityName(s.fertility, lang)],
    [t('f.species'), speciesName(s.species, lang)],
    [t('f.age'), s.age == null ? '—' : `${Math.round(s.age)} ${t('f.years')}`],
    [t('f.slope'), slopeText(s) ?? '—'],
    [t('f.basal'), s.basalArea == null ? '—' : `${n0(s.basalArea)} m²/ha`],
    [t('f.elev'), s.elevation == null ? '—' : `${n0(s.elevation)} m`],
    [t('f.height'), s.height == null ? '—' : n1(s.height, ' m')],
    [t('f.area'), s.area == null ? '—' : `${n1(s.area)} ha`],
  ];

  const rawRows = Object.entries(s.raw || {})
    .filter(([k]) => !/geom/i.test(k))
    .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('');

  const saved = opts.saved;
  const geoUrl = `https://www.google.com/maps/dir/?api=1&destination=${s.lat.toFixed(6)},${s.lon.toFixed(6)}`;

  return `
  <div class="sd-head">
    ${dial(sc.score)}
    <div class="sd-title">
      <h2>${esc(fertilityName(s.fertility, lang))} · ${esc(speciesName(s.species, lang))}</h2>
      <p>${s.lat.toFixed(5)}, ${s.lon.toFixed(5)}${opts.distance != null ? ` · ${formatDistance(opts.distance)}` : ''}</p>
    </div>
  </div>
  ${verdict(s, sc)}
  <div class="facts">
    ${facts.map(([k, v]) => `<div class="fact"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}
  </div>
  ${bars(sc.parts)}
  <div class="btn-row">
    <button class="btn${saved ? ' ghost' : ''}" data-act="save">
      <svg viewBox="0 0 24 24">${saved
        ? '<path d="m5 13 4 4L19 7"/>'
        : '<path d="M12 21s-7-4.6-7-10a7 7 0 0 1 14 0c0 5.4-7 10-7 10Z"/><circle cx="12" cy="11" r="2.4"/>'}</svg>
      ${esc(saved ? t('sheet.saved') : t('sheet.save'))}
    </button>
    <a class="btn ghost" href="${geoUrl}" target="_blank" rel="noopener">
      <svg viewBox="0 0 24 24"><path d="m3 11 18-8-8 18-2-8-8-2Z"/></svg>
      ${esc(t('sheet.navigate'))}
    </a>
  </div>
  ${rawRows ? `<details class="raw"><summary>${esc(t('sheet.raw'))}</summary><table>${rawRows}</table></details>` : ''}
  `;
}

export function renderList(items, opts = {}) {
  const lang = getLang();
  if (!items.length) {
    return `<div class="rl-head"><h2>${esc(t('list.title'))}</h2></div>
            <div class="empty">${esc(t('list.empty')).replace(/\n/g, '<br>')}</div>`;
  }
  const rows = items.map((it, i) => {
    const { s, sc } = it;
    const c = scoreColor(sc.score);
    const d = opts.from ? distanceBearing(opts.from, { lat: s.lat, lng: s.lon }) : null;
    const sub = [
      fertilityName(s.fertility, lang),
      s.age != null ? `${Math.round(s.age)} ${t('f.years')}` : null,
      slopeText(s),
    ].filter(Boolean).join(' · ');
    return `<button class="rl-item" data-idx="${i}">
      <span class="rl-badge" style="background:${c}">${sc.score}</span>
      <span class="rl-body"><b>${esc(scoreLabel(sc.score, lang))}</b><small>${esc(sub)}</small></span>
      ${d ? `<span class="rl-dist"><b>${esc(formatDistance(d.dist))}</b>${esc(aspectAbbr(d.bearing))}</span>` : ''}
    </button>`;
  }).join('');

  return `<div class="rl-head"><h2>${esc(t('list.title'))}</h2><span>${esc(t('list.count', items.length))}</span></div>${rows}`;
}
