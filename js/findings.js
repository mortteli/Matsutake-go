import { FINDING_COLOR } from "./constants.js";
import { map } from "./maplayer.js";
import { save, sp, state } from "./state.js";
import { closeOverlays, openModal } from "./ui.js";

/* ================= findings layer =================
   The GBIF / FinBIF occurrence records that ml/ trains the probability model on (see
   ml/export/export_observations.py), plotted as their own point layer so a single find can be
   inspected the same way a tapped point can. One JSON per species, fetched once and cached —
   there is currently data for matsutake only, so the toggle only appears when `sp().findings`
   names a file. */
export const findings = { data: null, dataFor: null, layer: null };

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

const fmtLicense = l => l ? (LICENSE_NAMES[l] || l) : "ei tiedossa";
const fmtBasis = b => b ? (BASIS_NAMES[b] || b.toLowerCase().replace(/_/g, " ")) : "ei tiedossa";
const fmtDate = d => {
  if (!d) return "ei tiedossa";
  const [y, m, day] = d.split("-");
  return day && m && y ? day + "." + m + "." + y : d;
};
const row = (k, v) => '<div class="c"><span class="k">' + k + '</span><span class="v">' + v + '</span></div>';

export async function loadFindingsData(species) {
  if (!species.findings) return null;
  if (findings.dataFor === species.key) return findings.data;
  const r = await fetch(species.findings, { cache: "no-cache" });
  if (!r.ok) throw new Error("findings fetch failed");
  findings.data = await r.json(); findings.dataFor = species.key;
  return findings.data;
}

export function openFinding(f) {
  document.getElementById("findingBody").innerHTML =
    '<div class="result-head"><span class="big">🍄</span>' +
    '<div><div class="verdict">Matsutake-havainto</div>' +
    '<div class="sub">' + f.lat.toFixed(5) + "° N, " + f.lon.toFixed(5) + "° E</div></div></div>" +
    '<div class="checks">' +
    row("Päivämäärä", fmtDate(f.date)) +
    row("Paikannuksen tarkkuus", f.unc_m != null ? "± " + f.unc_m + " m" : "ei tiedossa") +
    row("Havaintotapa", fmtBasis(f.basis)) +
    (f.locality ? row("Paikka", f.locality) : "") +
    row("Aineisto", f.dataset || "ei tiedossa") +
    row("Lähde", SOURCE_NAMES[f.source] || f.source) +
    row("Lisenssi", fmtLicense(f.license)) +
    "</div>" +
    (f.link ? '<a class="navlink" target="_blank" rel="noopener" href="' + f.link +
      '">🔗 Näytä alkuperäinen tietue</a>' : "");
  openModal("modalFinding");
}
document.getElementById("btnFindingClose").addEventListener("click", closeOverlays);

export function buildFindingsLayer(data) {
  const layer = L.layerGroup();
  data.forEach(f => {
    L.circleMarker([f.lat, f.lon], {
      radius: 5, weight: 1.5, color: "#221500", fillColor: FINDING_COLOR, fillOpacity: 0.92,
    }).addTo(layer).on("click", e => { L.DomEvent.stopPropagation(e); openFinding(f); });
  });
  return layer;
}

export async function showFindings() {
  const species = sp();
  try {
    const data = await loadFindingsData(species);
    if (!data) return;
    if (!findings.layer || findings.layer._species !== species.key) {
      if (findings.layer) map.removeLayer(findings.layer);
      findings.layer = buildFindingsLayer(data);
      findings.layer._species = species.key;
    }
    if (!map.hasLayer(findings.layer)) findings.layer.addTo(map);
    document.getElementById("legendFinding").hidden = false;
  } catch (e) {
    state.findings.on = false; save();
    document.getElementById("legendFinding").hidden = true;
  }
}
export function hideFindings(drop) {
  if (findings.layer) map.removeLayer(findings.layer);
  if (drop) findings.layer = null;
  document.getElementById("legendFinding").hidden = true;
}

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
    '<p class="note" id="findingsNote"></p>';
  const on = host.querySelector("#findingsOn");
  on.checked = state.findings.on;
  on.addEventListener("change", () => {
    state.findings.on = on.checked; save();
    if (on.checked) showFindings(); else hideFindings(false);
  });
  loadFindingsData(s).then(data => {
    const note = document.getElementById("findingsNote");
    if (note && data) note.textContent = data.length + " havaintoa. Näiden perusteella malli on opetettu.";
  }).catch(() => {});
}
