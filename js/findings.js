import { CUT_GREY, FINDING_COLOR, FINDING_SUSPECT, FINDING_UNKNOWN } from "./constants.js";
import { map } from "./maplayer.js";
import { save, sp, state } from "./state.js";
import { checkRow, closeOverlays, openModal } from "./ui.js";

/* ================= findings layer =================
   The GBIF / FinBIF occurrence records that ml/ trains the probability model on (see
   ml/export/export_observations.py), plotted as their own point layer so a single find can be
   inspected the same way a tapped point can. One JSON per species, fetched once and cached —
   there is currently data for matsutake only, so the toggle only appears when `sp().findings`
   names a file.

   A record carries two independent qualities, and the marker keeps them on separate channels
   because one cannot substitute for the other. Fill colour says whether the ground is still
   what it was when the find was made (`hab`, computed offline by
   ml/dataset/observation_status.py). Geometry says how precisely the find was located (`prec`).
   A tight dot on cut ground and a vague ring on standing forest are different problems, and a
   single "quality" grade would hide which one you are looking at.

   Records with no classification — an older observations.json, or a species whose status table
   has not been built — simply lack `prec`/`hab` and fall back to the plain yellow dot this
   layer drew before any of this existed. */
export const findings = { data: null, dataFor: null, layer: null, rings: null, focus: null };

/* Below this zoom a 1 km circle is a few pixels of noise rather than a statement about where
   the find might be, so the uncertainty rings are not drawn at all. */
const RING_ZOOM = 11;

/* Markers draw at a 4-5px radius, but tap accuracy shouldn't be held to that: a dedicated
   canvas renderer lets the hit area extend `tolerance` px past the visible dot without
   drawing it any bigger. Scoped to this layer only, so every other vector layer on the map
   keeps the default SVG renderer. */
const findingsRenderer = L.canvas({ padding: 0.5, tolerance: 10 });

const BASIS_NAMES = {
  HUMAN_OBSERVATION: "havainto",
  HUMAN_OBSERVATION_PHOTO: "valokuvahavainto",
  HUMAN_OBSERVATION_UNSPECIFIED: "havainto",
  MACHINE_OBSERVATION: "konetunnistus (esim. kuvantunnistus)",
  MATERIAL_SAMPLE: "näyte",
  PRESERVED_SPECIMEN: "säilötty näyte (herbaario)",
};
const LICENSE_NAMES = {
  "http://creativecommons.org/licenses/by/4.0/legalcode": "CC BY 4.0",
  "http://creativecommons.org/licenses/by-nc/4.0/legalcode": "CC BY-NC 4.0",
  "http://tun.fi/MZ.intellectualRightsCC-BY-NC-4.0": "CC BY-NC 4.0",
  "CC-BY": "CC BY",
};
const SOURCE_NAMES = { gbif: "GBIF", laji: "Suomen Lajitietokeskus (FinBIF)" };

const PREC_NAMES = {
  tarkka: "tarkka",
  summittainen: "summittainen",
  alueellinen: "vain seutu",
  tuntematon: "ei kerrottu",
};
/* The mark each precision band gets in the readout: what the model is allowed to learn from is
   also what you can walk to. */
const PREC_MARK = { tarkka: "ok", summittainen: "meh", alueellinen: "no", tuntematon: "no" };

const HAB_MARK = { ennallaan: "ok", epavarma: "meh", muuttunut: "no", ulkopuolella: "meh",
                   ei_tietoa: "meh" };
/* The headline over the modal. "Hakattu — metsä ei ole enää tässä" is the same sentence
   inspect.js puts on a tapped clear-cut, so the two readouts agree word for word. */
const HAB_HEAD = {
  ennallaan: ["🍄", "Metsä on yhä pystyssä"],
  epavarma: ["🌲", "Metsä on ehkä muuttunut"],
  muuttunut: ["🪵", "Hakattu — metsä ei ole enää tässä"],
  ulkopuolella: ["🍄", "Löytö metsätalousmaan ulkopuolelta"],
  ei_tietoa: ["📍", "Havainto — metsää ei voi arvioida"],
};

/* One sentence per reason code, composed here rather than baked into the JSON so every Finnish
   string in this layer lives in one place and a wording fix does not mean re-running a
   twenty-minute sampling job. {} placeholders are filled from the record. */
const HAB_WHY = {
  hakattu: "Kuviorekisteri sanoo maan aukeaksi tai taimikoksi. Koordinaatti on yhä hyvä ja " +
    "lähimetsässä voi olla.",
  hakkuuaikomus: "Uudistushakkuu on ilmoitettu, mutta ilmoitus ei ole velvoite — metsä voi olla " +
    "yhä pystyssä.",
  osa_alueesta_hakattu: "Osa epätarkkuusympyrästä ({hab_pct}) on kuviorekisterin mukaan aukeaa " +
    "tai taimikkoa. Tuliko löytö hakatulta vai säilyneeltä osalta, sitä tietue ei kerro.",
  osa_alueesta_muuttunut: "Osa epätarkkuusympyrästä ({hab_pct}) on vaihtunut havainnon jälkeen. " +
    "Tuliko löytö muuttuneelta vai säilyneeltä osalta, sitä tietue ei kerro.",
  kasvusto_havaintoa_nuorempi: "Kasvusto on syntynyt vasta noin {est_year}, havainto on vuodelta " +
    "{year}. Puusto on siis vaihtunut löydön jälkeen, mutta koordinaatti kelpaa yhä.",
  puusto_nollautunut: "Puusto on nollautunut inventointien {era} ja 2023 välillä — merkki " +
    "uudistushakkuusta.",
  puusto_harventunut: "Puuston tilavuus on romahtanut inventointien {era} ja 2023 välillä.",
  kasvupaikkatieto_muuttunut: "Kasvupaikkatieto on muuttunut inventointien {era} ja 2023 " +
    "välillä. Voi olla oikea muutos, voi olla inventointien arviointiero.",
  tuore_havainto: "Tuore havainto: metsävaratieto ei ehdi näyttää muutosta, eikä hakkuita ole " +
    "ilmoitettu.",
  ei_muutosta: "Metsä on Luken inventoinneissa samanlaista kuin havaintohetkellä.",
  ei_metsatalousmaata: "Ei metsätalousmaata — hautausmaa, piha, pelto tai vastaava. Luke ei ole " +
    "koskaan kuvannut tätä maata, joten mikään ei kerro metsän kadonneen eikä säilyneen. " +
    "Epätarkkuusympyrästä {forest_pct} on metsätalousmaata.",
  metsamaan_rajaus_muuttui: "Metsätalousmaan rajaus on siirtynyt inventointien välillä, mikä on " +
    "enimmäkseen rajauksen kohinaa eikä todiste muutoksesta.",
  ei_metsavaratietoa: "Tästä ruudusta ei ole metsävaratietoa.",
  ei_paivamaaraa: "Havainnolla ei ole päivämäärää, joten muutosta ei voi ajoittaa.",
  liian_epatarkka: "Paikannus on liian karkea (± {unc_m}) yhdenkään metsikön tunnistamiseen, " +
    "joten metsän tilaa ei arvioida lainkaan.",
};

const FILTERS = {
  kaikki: () => true,
  paikannetut: f => !f.prec || f.prec === "tarkka" || f.prec === "summittainen",
  parhaat: f => !f.prec || ((f.prec === "tarkka" || f.prec === "summittainen") &&
                            (f.hab === "ennallaan" || f.hab === "ulkopuolella")),
};

const fmtLicense = l => l ? (LICENSE_NAMES[l] || l) : "ei tiedossa";
const fmtBasis = b => b ? (BASIS_NAMES[b] || b.toLowerCase().replace(/_/g, " ")) : "ei tiedossa";
const fmtDate = d => {
  if (!d) return "ei tiedossa";
  const [y, m, day] = d.split("-");
  return day && m && y ? day + "." + m + "." + y : d;
};
const fmtM = m => m >= 1000 ? String(Math.round(m / 100) / 10).replace(".", ",") + " km" : m + " m";
const row = (k, v) => '<div class="c"><span class="k">' + k + '</span><span class="v">' + v + '</span></div>';
/* Remarks are free text typed by whoever logged the observation (iNaturalist etc.), unlike the
   other fields here which come from a controlled vocabulary or a curated place name — so this is
   the one value in the modal that must be escaped before it goes into innerHTML. */
const escapeHtml = s => s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* Is this record located tightly enough to stand on a stand at all? Also the line above which
   build_dataset.py lets a record train the model. */
const located = f => f.prec === "tarkka" || f.prec === "summittainen";

/* Reasons that describe a change, and so are only as true as the share of the disc they were
   read from. A verdict can win on four of nine points, and the sentence must not then state
   as fact what a bare majority suspects. */
const PARTIAL_MATTERS = new Set(["hakattu", "hakkuuaikomus", "kasvusto_havaintoa_nuorempi",
                                 "puusto_nollautunut", "puusto_harventunut",
                                 "kasvupaikkatieto_muuttunut"]);

function habSentence(f) {
  const t = HAB_WHY[f.hab_why];
  if (!t) return null;
  const partial = PARTIAL_MATTERS.has(f.hab_why) && f.hab_frac != null && f.hab_frac < 0.999
    ? " Tämä pätee " + Math.round(f.hab_frac * 100) + " %:iin tarkistuspisteistä " +
      "epätarkkuusympyrän sisällä." : "";
  return (t + partial)
          .replace("{est_year}", f.est_year)
          .replace("{year}", (f.date || "").slice(0, 4))
          .replace("{era}", f.hab_cycle)
          .replace("{unc_m}", f.unc_m == null ? "?" : fmtM(f.unc_m))
          .replace("{forest_pct}", Math.round((f.forest_frac || 0) * 100) + " %")
          .replace("{hab_pct}", Math.round((f.hab_frac || 0) * 100) + " %");
}

export async function loadFindingsData(species) {
  if (!species.findings) return null;
  if (findings.dataFor === species.key) return findings.data;
  const r = await fetch(species.findings, { cache: "no-cache" });
  if (!r.ok) throw new Error("findings fetch failed");
  findings.data = await r.json(); findings.dataFor = species.key;
  return findings.data;
}

/* ---- the modal ---- */
export function openFinding(f, alsoHere) {
  const sentence = habSentence(f);
  clearFocus();
  /* A record located to ± 50 km is drawn as a small ring, because a circle that size would
     swallow half of Lapland. Drawn for as long as the modal is open, it says the same thing far
     better than any number in the readout can. */
  if (f.unc_m > 1000) {
    findings.focus = L.circle([f.lat, f.lon], {
      radius: f.unc_m, fill: false, color: FINDING_UNKNOWN, weight: 1.5, dashArray: "5 5",
    }).addTo(map);
  }
  const [icon, verdict] = HAB_HEAD[f.hab] || ["🍄", "Matsutake-havainto"];
  document.getElementById("findingBody").innerHTML =
    '<div class="result-head"><span class="big">' + icon + '</span>' +
    '<div><div class="verdict">' + verdict + '</div>' +
    '<div class="sub">' + f.lat.toFixed(5) + "° N, " + f.lon.toFixed(5) + "° E</div></div></div>" +
    '<div class="checks">' +
    (f.prec ? checkRow(PREC_MARK[f.prec], "Paikannus",
      (f.unc_m != null ? "± " + fmtM(f.unc_m) + " · " : "") + PREC_NAMES[f.prec]) : "") +
    (sentence ? checkRow(HAB_MARK[f.hab], "Metsä havainnon jälkeen", sentence, true) : "") +
    (alsoHere > 1 ? checkRow("meh", "Sama keskipiste",
      alsoHere + " havaintoa on kirjattu tähän samaan pisteeseen", true) : "") +
    row("Päivämäärä", fmtDate(f.date)) +
    row("Havaintotapa", fmtBasis(f.basis)) +
    (f.locality ? row("Paikka", f.locality) : "") +
    row("Aineisto", f.dataset || "ei tiedossa") +
    row("Lähde", SOURCE_NAMES[f.source] || f.source) +
    row("Lisenssi", fmtLicense(f.license)) +
    (f.habitat ? row("Elinympäristö", escapeHtml(f.habitat)) : "") +
    (f.event_remarks ? row("Paikan kuvaus", escapeHtml(f.event_remarks)) : "") +
    (f.remarks ? row("Huomiot", escapeHtml(f.remarks)) : "") +
    "</div>" +
    (f.link ? '<a class="navlink" target="_blank" rel="noopener" href="' + f.link +
      '">🔗 Näytä alkuperäinen tietue</a>' : "");
  openModal("modalFinding");
}
document.getElementById("btnFindingClose").addEventListener("click", closeOverlays);

export function clearFocus() {
  if (findings.focus) { map.removeLayer(findings.focus); findings.focus = null; }
}

/* ---- markers ---- */
function markerStyle(f) {
  /* Nothing classified: the dot this layer has always drawn. */
  if (!f.hab) return { radius: 5, weight: 1.5, color: "#221500", fillColor: FINDING_COLOR, fillOpacity: 0.92 };
  if (!located(f)) {
    /* Not a pin. A marker that visibly declines to claim a place — every one of these is a
       municipality centroid, and sixteen of them share a single pixel in Utsjoki. */
    return { radius: 4, weight: 1, color: FINDING_UNKNOWN, fillOpacity: 0, dashArray: "2 3" };
  }
  const fill = { ennallaan: FINDING_COLOR, epavarma: FINDING_SUSPECT, muuttunut: CUT_GREY,
                 ulkopuolella: FINDING_COLOR, ei_tietoa: FINDING_UNKNOWN }[f.hab];
  return f.hab === "ulkopuolella"
    ? { radius: 5, weight: 2, color: FINDING_COLOR, fillOpacity: 0 }
    : { radius: 5, weight: 1.5, color: "#221500", fillColor: fill,
        fillOpacity: f.hab === "ei_tietoa" ? 0.45 : 0.92 };
}

export function buildFindingsLayer(data) {
  const layer = L.layerGroup(), rings = L.layerGroup();
  const keep = FILTERS[state.findings.filter] || FILTERS.kaikki;
  /* 105 of the 445 records share 29 coordinates, nearly all of them coarse ones stacked on a
     municipality centroid. Drawing one marker per position instead of one per record is what
     stops those piles from reading as the country's richest matsutake ground. */
  const seen = new Map();
  data.filter(keep).forEach(f => {
    const key = f.lat + "," + f.lon;
    if (seen.has(key)) { seen.get(key).push(f); return; }
    seen.set(key, [f]);
  });
  seen.forEach(group => {
    const f = group[0];
    L.circleMarker([f.lat, f.lon], { ...markerStyle(f), renderer: findingsRenderer })
      .addTo(layer)
      .on("click", e => { L.DomEvent.stopPropagation(e); openFinding(f, group.length); });
    if (f.prec === "summittainen" && f.unc_m)
      L.circle([f.lat, f.lon], { radius: f.unc_m, fill: false, color: FINDING_COLOR,
                                 weight: 1, opacity: 0.5, dashArray: "4 5" }).addTo(rings);
  });
  layer._rings = rings;
  return layer;
}

/* The uncertainty rings live in their own group so zooming out drops them without rebuilding
   445 markers. */
function syncRings() {
  const rings = findings.layer && findings.layer._rings;
  if (!rings) return;
  const want = map.hasLayer(findings.layer) && map.getZoom() >= RING_ZOOM;
  if (want && !map.hasLayer(rings)) rings.addTo(map);
  else if (!want && map.hasLayer(rings)) map.removeLayer(rings);
}
map.on("zoomend", syncRings);

export async function showFindings() {
  const species = sp();
  try {
    const data = await loadFindingsData(species);
    if (!data) return;
    if (!findings.layer || findings.layer._species !== species.key ||
        findings.layer._filter !== state.findings.filter) {
      if (findings.layer) hideFindings(true);
      findings.layer = buildFindingsLayer(data);
      findings.layer._species = species.key;
      findings.layer._filter = state.findings.filter;
    }
    if (!map.hasLayer(findings.layer)) findings.layer.addTo(map);
    syncRings();
    document.getElementById("legendFinding").hidden = false;
  } catch (e) {
    state.findings.on = false; save();
    document.getElementById("legendFinding").hidden = true;
  }
}
export function hideFindings(drop) {
  clearFocus();
  if (findings.layer) {
    if (findings.layer._rings) map.removeLayer(findings.layer._rings);
    map.removeLayer(findings.layer);
  }
  if (drop) findings.layer = null;
  document.getElementById("legendFinding").hidden = true;
}

/* ---- the settings panel ---- */
const KEY_ROWS = [
  ["ennallaan", "metsä on yhä pystyssä"],
  ["epavarma", "metsä on ehkä muuttunut"],
  ["muuttunut", "hakattu tai vaihtunut — koordinaatti yhä hyvä"],
  ["ulkopuolella", "ei metsätalousmaata (esim. hautausmaa)"],
  ["ei_tietoa", "ei arvioitavissa — karkea paikannus tai ei tietoa"],
];

export function renderFindingsPanel() {
  const s = sp(), host = document.getElementById("findingsPanel");
  host.innerHTML = "";
  if (!s.findings) {
    host.innerHTML = '<p class="note">Ei vielä tälle lajille — havaintoja on toistaiseksi vain matsutakelle.</p>';
    return;
  }
  host.innerHTML =
    '<div class="row"><label>Näytä havainnot<br><small>GBIF ja Suomen Lajitietokeskus — napauta pistettä nähdäksesi tiedot</small></label>' +
    '<label class="switch"><input type="checkbox" id="findingsOn"><i></i></label></div>' +
    '<div class="seg" id="findingsSeg">' +
    '<button data-f="kaikki">Kaikki</button>' +
    '<button data-f="paikannetut">Paikannetut</button>' +
    '<button data-f="parhaat">Parhaat vihjeet</button></div>' +
    '<p class="note" id="findingsNote"></p>' +
    '<div class="fkey">' + KEY_ROWS.map(([k, t]) =>
      '<div><span class="fdot ' + k + '"></span>' + t + '</div>').join("") + '</div>';

  const on = host.querySelector("#findingsOn");
  on.checked = state.findings.on;
  on.addEventListener("change", () => {
    state.findings.on = on.checked; save();
    if (on.checked) showFindings(); else hideFindings(false);
  });

  const seg = host.querySelector("#findingsSeg");
  const paintSeg = () => seg.querySelectorAll("button").forEach(
    b => b.classList.toggle("active", b.dataset.f === state.findings.filter));
  paintSeg();
  seg.addEventListener("click", e => {
    const b = e.target.closest("button");
    if (!b || b.dataset.f === state.findings.filter) return;
    state.findings.filter = b.dataset.f; save();
    paintSeg();
    loadFindingsData(s).then(d => { if (d) paintNote(d); }).catch(() => {});
    if (state.findings.on) showFindings();
  });

  loadFindingsData(s).then(data => { if (data) paintNote(data); }).catch(() => {});
}

/* The old note said "445 havaintoa. Näiden perusteella malli on opetettu.", which overstates it
   twice over: the model saw 109 at full weight and 141 downweighted, and a third of the file is
   located no better than a province. These are the numbers that make a future re-run's drift
   visible without any tooling. */
function paintNote(data) {
  const note = document.getElementById("findingsNote");
  if (!note) return;
  const n = data.length;
  const shown = data.filter(FILTERS[state.findings.filter] || FILTERS.kaikki).length;
  const classified = data.filter(f => f.hab).length;
  if (!classified) { note.textContent = n + " havaintoa."; return; }
  const fine = data.filter(located).length;
  const gone = data.filter(f => f.hab === "muuttunut").length;
  note.textContent = shown + " / " + n + " näkyvissä · " + fine + " paikannettu · " +
    gone + " sellaisesta metsästä joka on sittemmin vaihtunut.";
}
