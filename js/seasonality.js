import { loadFindingsData } from "./findings.js";
import { sp } from "./state.js";

/* ================= seasonality chart =================
   When does the season actually run? The info sheet says "Pohjois-Suomi: elokuun loppu –
   syyskuu" in prose; this is the same claim drawn from the observation records the findings
   layer already plots, so the reader can see the spread rather than take the sentence's word
   for it.

   One stacked column per ISO week, split by area. The areas are latitude bands, so they are
   ordinal rather than nominal and take one hue in three lightness steps (north = lightest):
   the colour itself carries the north-south order, which is the whole point of the picture —
   the north peaks first. */

const AREAS = [
  { key: "lappi", name: "Lappi",                       color: "#ffd166" },
  { key: "keski", name: "Kainuu ja Pohjois-Pohjanmaa", color: "#f59a3c" },
  { key: "etela", name: "Itä- ja Etelä-Suomi",         color: "#d96a21" },
];
/* Stacked bottom-to-top: the darkest step sits on the baseline so the column is not
   top-heavy, which puts the legend's top-to-bottom order and the stack's top-to-bottom
   order on the same north-south axis. */
const STACK = AREAS.slice().reverse();

/* Maakunta borders as two straight lines, which is all a weekly histogram can use. The
   northern line follows the Lappi / Pohjois-Pohjanmaa border from the coast at Simo up past
   Ranua and Posio, then jumps to 66.5° east of Kuusamo — Koillismaa is Pohjois-Pohjanmaa, and
   a plain latitude cut would file its finds, one of the country's richest matsutake grounds,
   under Lappi. The southern line runs along the Pohjois-Pohjanmaa / Kainuu southern edge,
   Kalajoki to Kuhmo. Municipalities straddling a line land on the wrong side; the bands are
   the point, not the borders. */
export function area(lat, lon) {
  const lappiFrom = lon >= 28.6 ? 66.5 : 65.6 + 0.13 * (lon - 25);
  if (lat >= lappiFrom) return "lappi";
  return lat >= 63.6 + 0.08 * (lon - 24) ? "keski" : "etela";
}

/* ISO-8601 week: Monday-based, and the week owning January 4th is week 1. Records carry
   plain "YYYY-MM-DD" strings, some of them truncated to a month or a bare year by whoever
   logged them — those cannot be placed on a week axis and are counted out loud instead. */
function isoWeek(y, m, d) {
  const t = new Date(Date.UTC(y, m - 1, d));
  t.setUTCDate(t.getUTCDate() - ((t.getUTCDay() + 6) % 7) + 3);   // Thursday of this week
  const firstThu = new Date(Date.UTC(t.getUTCFullYear(), 0, 4));
  firstThu.setUTCDate(firstThu.getUTCDate() - ((firstThu.getUTCDay() + 6) % 7) + 3);
  return 1 + Math.round((t - firstThu) / (7 * 864e5));
}

/* Local date, not UTC: which week it is is a question about the phone's calendar. */
function todayParts() {
  const d = new Date();
  return [d.getFullYear(), d.getMonth() + 1, d.getDate()];
}

function weekOf(rec) {
  const s = rec.date;
  if (!s || s.length !== 10) return null;
  const [y, m, d] = s.split("-").map(Number);
  if (!y || !m || !d) return null;
  const w = isoWeek(y, m, d);
  return w >= 1 && w <= 53 ? w : null;
}

/* Weeks to draw. A single June record would otherwise buy six empty columns, so the axis is
   trimmed from both ends for as long as what is dropped stays under half a percent of the
   dated records — and whatever falls outside is reported under the chart. */
function window_(weeks, counts, total) {
  const budget = total * 0.005;
  let lo = 0, hi = weeks.length - 1, dropped = 0;
  while (lo < hi && dropped + counts[weeks[lo]] < budget) dropped += counts[weeks[lo++]];
  dropped = 0;
  while (hi > lo && dropped + counts[weeks[hi]] < budget) dropped += counts[weeks[hi--]];
  return [weeks[lo], weeks[hi]];
}

/* Ticks the eye can round: at most five gaps, so a 102-record peak gets 0/25/50/75/100/125
   rather than an axis nobody reads. */
function niceTop(max) {
  for (const step of [1, 2, 5, 10, 20, 25, 50, 100, 200, 500]) {
    if (Math.ceil(max / step) <= 5) return [Math.ceil(max / step) * step, step];
  }
  return [max, max];
}

function stats(data) {
  const byWeek = new Map();          // week -> { lappi, keski, etela }
  const perArea = {};
  AREAS.forEach(a => { perArea[a.key] = { n: 0, weeks: [] }; });
  let dated = 0, nodate = 0, year0 = Infinity, year1 = -Infinity;

  // area() splits Finland along two straight lines fitted between lon 24 and 28.6, so a
  // Swedish find at lon 11-24 would be filed as "Lappi" or "Ita- ja Etela-Suomi" and this
  // chart would silently become wrong. The finds layer draws both countries -- it plots
  // plain lat/lon markers, so it needed no projection work -- but the season chart is
  // Finnish until it has Swedish areas of its own. Records with no country predate the
  // field and are Finnish.
  data = data.filter(f => !f.country || f.country === "FI");

  data.forEach(f => {
    const y = +String(f.date || "").slice(0, 4);
    if (y) { year0 = Math.min(year0, y); year1 = Math.max(year1, y); }
    const w = weekOf(f);
    if (w == null) { nodate++; return; }
    dated++;
    const key = area(f.lat, f.lon);
    if (!byWeek.has(w)) byWeek.set(w, { lappi: 0, keski: 0, etela: 0 });
    byWeek.get(w)[key]++;
    perArea[key].n++;
    perArea[key].weeks.push(w);
  });
  if (!dated) return null;

  const weeks = [...byWeek.keys()].sort((a, b) => a - b);
  const totals = {};
  weeks.forEach(w => { const c = byWeek.get(w); totals[w] = c.lappi + c.keski + c.etela; });
  const [lo, hi] = window_(weeks, totals, dated);
  let outside = 0;
  weeks.forEach(w => { if (w < lo || w > hi) outside += totals[w]; });

  AREAS.forEach(a => {
    const s = perArea[a.key];
    s.weeks.sort((x, y) => x - y);
    s.peak = null;
    let best = 0;
    weeks.forEach(w => { const c = byWeek.get(w)[a.key]; if (c > best) { best = c; s.peak = w; } });
    /* Half of the finds fall between these two weeks — the one number that says how long the
       season lasts, and a stacked column cannot show it per area. */
    s.q1 = s.weeks[Math.floor(s.weeks.length * 0.25)];
    s.q3 = s.weeks[Math.ceil(s.weeks.length * 0.75) - 1];
  });

  return { byWeek, totals, perArea, lo, hi, dated, undated: nodate, outside,
           year0, year1, peak: weeks.reduce((a, w) => totals[w] > totals[a] ? w : a, weeks[0]) };
}

/* A rect with a 4px rounded top and a square baseline — only the segment that caps a stack
   gets the rounding, the ones under it stay square. */
function barPath(x, y, w, h, round) {
  const r = round ? Math.min(4, w / 2, h) : 0;
  return "M" + x + " " + (y + h) + "V" + (y + r) +
    (r ? "a" + r + " " + r + " 0 0 1 " + r + " " + -r + "h" + (w - 2 * r) +
         "a" + r + " " + r + " 0 0 1 " + r + " " + r : "h" + w) +
    "V" + (y + h) + "Z";
}

const PLOT = { x0: 28, x1: 316, top: 20, base: 124, h: 152 };

function svg(s) {
  const slots = s.hi - s.lo + 1;
  const now = isoWeek(...todayParts());
  const slotW = (PLOT.x1 - PLOT.x0) / slots;
  const barW = Math.min(24, slotW - 7);
  const plotH = PLOT.base - PLOT.top;
  const [top, step] = niceTop(Math.max(...Object.values(s.totals)));
  const y = n => PLOT.base - (n / top) * plotH;

  let g = "", bars = "", ticks = "", hits = "";
  /* Where in the season today sits. A hairline behind the bars and a small "nyt" over it: it
     answers "is it time yet?" without competing with the data for ink. Outside the drawn weeks
     — which is most of the year — nothing is drawn, because nothing is in season. */
  const nowX = now >= s.lo && now <= s.hi
    ? PLOT.x0 + (now - s.lo) * slotW + slotW / 2 : null;
  const nowMark = nowX == null ? "" :
    '<line class="snow" x1="' + nowX + '" y1="' + PLOT.top + '" x2="' + nowX + '" y2="' + PLOT.base + '"/>' +
    '<text class="sax now" x="' + nowX + '" y="13" text-anchor="middle">nyt</text>';
  for (let n = 0; n <= top; n += step) {
    g += '<line class="sgrid' + (n ? "" : " base") + '" x1="' + PLOT.x0 + '" y1="' + y(n) +
         '" x2="' + PLOT.x1 + '" y2="' + y(n) + '"/>' +
         '<text class="sax" x="24" y="' + y(n) + '" text-anchor="end" dominant-baseline="middle">' + n + '</text>';
  }
  for (let w = s.lo; w <= s.hi; w++) {
    const c = s.byWeek.get(w) || { lappi: 0, keski: 0, etela: 0 };
    const x = PLOT.x0 + (w - s.lo) * slotW;
    const bx = x + (slotW - barW) / 2;
    let bottom = PLOT.base;
    STACK.forEach((a, i) => {
      if (!c[a.key]) return;
      /* A single record is 0.9 px tall next to a 102-record peak; a floor of 2 px is the
         difference between "one find" and "no finds" at a glance. The 2 px surface gap that
         separates touching fills is only taken where the segment can spare it. */
      const h = Math.max((c[a.key] / top) * plotH, 2);
      const above = STACK.slice(i + 1).some(o => c[o.key] > 0);
      const gap = above && h >= 4 ? 2 : 0;
      bars += '<path fill="' + a.color + '" d="' +
        barPath(bx, bottom - h, barW, h - gap, !above) + '"/>';
      bottom -= h;
    });
    if (w % 2 === 0 || w === now)
      ticks += '<text class="sax' + (w === now ? " now" : "") + '" x="' + (x + slotW / 2) +
        '" y="136" text-anchor="middle">' + w + '</text>';
    hits += '<rect class="shit" data-w="' + w + '" tabindex="0" role="img" x="' + x +
      '" y="' + PLOT.top + '" width="' + slotW + '" height="' + (PLOT.base - PLOT.top) +
      '" aria-label="' + weekLabel(s, w) + '"/>';
  }
  return '<svg class="schart" viewBox="0 0 320 ' + PLOT.h + '" role="group" aria-label="Havainnot viikoittain">' +
    g + nowMark + bars + ticks +
    '<text class="sax" x="' + PLOT.x1 + '" y="148" text-anchor="end">viikko</text>' +
    hits + '</svg>';
}

const plural = n => n + (n === 1 ? " havainto" : " havaintoa");

/* What the picture leaves out, said before the reader has to wonder: a record dated to a month
   or a bare year cannot sit on a week, and the axis is trimmed at both ends. */
function missing(s) {
  const parts = [];
  if (s.undated) parts.push(plural(s.undated) + " on ilman tarkkaa päivää");
  if (s.outside) parts.push(plural(s.outside) + " osuu kuvan viikkojen ulkopuolelle");
  return parts.length
    ? parts.join(", ") + " — " + (parts.length > 1 ? "ne eivät ole" : "se ei ole") + " kuvassa. "
    : "";
}

/* The hovered week, written into the readout under the chart rather than into a floating
   tooltip: a tooltip that follows a finger on a phone covers the very columns it describes.
   Counts ride a colour chip instead of an area name so the line keeps the same two rows at
   every phone width, and the legend right below names the colours. */
function weekHtml(s, w) {
  const c = s.byWeek.get(w) || { lappi: 0, keski: 0, etela: 0 };
  const n = s.totals[w] || 0;
  return "<b>Viikko " + w + "</b> · " + plural(n) + (n ? " " + AREAS.map(a =>
    '<span class="sc"><i style="background:' + a.color + '"></i>' + c[a.key] + "</span>").join("") : "");
}

function weekLabel(s, w) {
  const c = s.byWeek.get(w) || { lappi: 0, keski: 0, etela: 0 };
  const n = s.totals[w] || 0;
  if (!n) return "Viikko " + w + ": ei havaintoja";
  return "Viikko " + w + ": " + plural(n) + " — " +
    AREAS.filter(a => c[a.key]).map(a => a.name + " " + c[a.key]).join(" · ");
}

export function renderSeasonality() {
  const host = document.getElementById("seasonChart");
  if (!host) return;
  const species = sp();
  host.innerHTML = "";
  if (!species.findings) return;
  loadFindingsData(species).then(data => {
    if (!data || sp().key !== species.key) return;
    const s = stats(data);
    if (!s) return;
    const summary = plural(s.dated) + " vuosilta " + s.year0 + "–" + s.year1 +
      " · huippu viikolla " + s.peak;
    host.innerHTML =
      '<h3>Havaintojen ajoittuminen</h3>' +
      // "milloin löytöjä on tehty" rather than the species name in the partitive: the ending
      // is not regular across these five (ukonsientä, not *ukonsienia), and the heading and
      // the layer emoji already say which mushroom this is
      '<p class="note">Milloin löytöjä on tehty: yksi pylväs viikossa, väri kertoo ' +
      'alueen. Sama havaintoaineisto kuin kartan ' + sp().emoji + '-tasolla, eli eri ' +
      'vuosikymmenet samassa kuvassa — pylvään korkeus on havaintojen määrä, ei sadon ' +
      'runsaus.</p>' +
      svg(s) +
      '<p class="sread" id="seasRead">' + summary + '</p>' +
      '<div class="seas">' + AREAS.map(a => {
        const p = s.perArea[a.key];
        if (!p.n) return "";
        return '<div class="srow"><span class="sdot" style="background:' + a.color + '"></span>' +
          '<span class="sname">' + a.name + '</span>' +
          '<span class="sval">' + p.n + '</span>' +
          '<span class="smeta">huippu vk ' + p.peak + ' · puolet vk ' + p.q1 + '–' + p.q3 + '</span></div>';
      }).join("") + '</div>' +
      '<p class="note">' + missing(s) +
      "Alueet ovat leveyspiirivyöhykkeitä: Lappi, sen alla Kainuu ja Pohjois-Pohjanmaa " +
      "(Koillismaa mukaan lukien) ja näiden eteläpuolella loput maasta, jossa havainnot ovat " +
      "Pohjois-Karjalasta ja Savosta Uudellemaalle ja Varsinais-Suomeen.</p>";

    const read = host.querySelector("#seasRead");
    const show = w => { read.innerHTML = w == null ? summary : weekHtml(s, w); };
    host.querySelectorAll(".shit").forEach(r => {
      const w = +r.dataset.w;
      const on = () => { host.querySelectorAll(".shit").forEach(o => o.classList.remove("on"));
                         r.classList.add("on"); show(w); };
      r.addEventListener("pointerdown", on);
      r.addEventListener("pointerover", on);
      r.addEventListener("focus", on);
      /* A tap ends with a pointerout the moment the finger lifts, so on touch the readout
         stays put until another column is tapped — a week's numbers that vanish with the
         finger that asked for them are no answer at all. */
      r.addEventListener("pointerout", e => {
        if (e.pointerType === "touch") return;
        r.classList.remove("on"); show(null);
      });
      r.addEventListener("blur", () => { r.classList.remove("on"); show(null); });
    });
  }).catch(() => { host.innerHTML = ""; });
}
