import { clearFocus, hideFindings, renderFindingsPanel, showFindings } from "./findings.js";
import { map, spots } from "./maplayer.js";
import { clearNearby } from "./nearby.js";
import { hideProb, prob, renderProb, showProb, syncRuleLayer, updateProbLegend } from "./problayer.js";
import { search } from "./search.js";
import { renderSeasonality } from "./seasonality.js";
import { SPECIES } from "./species.js";
import { cfg, save, sp, state } from "./state.js";

/* ================= UI plumbing ================= */
export const sheets = ["sheetSettings", "sheetInfo", "sheetResult"];
export const modals = ["modalSpecies", "modalFinding"];
export const backdrop = document.getElementById("backdrop");
export const modalSpecies = document.getElementById("modalSpecies");
export function openSheet(id) {
  sheets.forEach(s => document.getElementById(s).classList.toggle("open", s === id));
  modals.forEach(m => document.getElementById(m).classList.remove("open"));
  backdrop.classList.add("on");
}
export function openModal(id) {
  sheets.forEach(s => document.getElementById(s).classList.remove("open"));
  modals.forEach(m => document.getElementById(m).classList.toggle("open", m === id));
  backdrop.classList.add("on");
}
export function closeOverlays() {
  sheets.forEach(s => document.getElementById(s).classList.remove("open"));
  modals.forEach(m => document.getElementById(m).classList.remove("open"));
  backdrop.classList.remove("on");
  if (search.panel) search.panel.classList.remove("open");
  clearFocus();          // the uncertainty circle a finding modal drew belongs to that modal
}
backdrop.addEventListener("click", closeOverlays);
document.getElementById("btnLayers").addEventListener("click", () => openSheet("sheetSettings"));
document.getElementById("btnInfo").addEventListener("click", () => openSheet("sheetInfo"));
document.getElementById("btnSpecies").addEventListener("click", () => openModal("modalSpecies"));
// the findings chip is a three-dot key with no room to explain itself; the sheet has the rest
document.getElementById("legendFinding").addEventListener("click", () => openSheet("sheetSettings"));

/* One line of a verdict readout: a tick, a cross or a neutral dot, a label and a value. Shared
   by the tapped-point sheet and the finding modal so the two never drift apart in wording or
   in what a mark means — "ok" it passes, "no" it fails, "meh" the data cannot say.

   `wide` is for a value that is a sentence rather than a measurement: it drops to its own line
   under the label instead of being crushed into whatever width is left on the right. */
export function checkRow(state_, label, value, wide) {
  const mark = state_ === "ok" ? "✔" : state_ === "no" ? "✘" : "•";
  return '<div class="c' + (wide ? " wide" : "") + '"><span class="mark ' + state_ + '">' + mark +
         '</span><span class="k">' + label + '</span><span class="v">' + value + '</span></div>';
}

export let toastTimer = null;
export function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("on");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("on"), 3500);
}

export let redrawTimer = null;
export function refreshSpots() {
  clearNearby();          // every filter control funnels through here, so this covers them all
  clearTimeout(redrawTimer);
  redrawTimer = setTimeout(() => spots.redraw(), 350);
}

/* ---- species picker ---- */
export function renderSpeciesList() {
  const host = document.getElementById("speciesList");
  host.innerHTML = "";
  SPECIES.forEach(s => {
    const b = document.createElement("button");
    b.className = "sp" + (s.key === state.species ? " active" : "");
    b.innerHTML = '<span class="e">' + s.emoji + '</span>' +
      '<span><span class="n">' + s.name + '</span><br>' +
      '<span class="d">' + s.latin + ' · ' + s.tagline + '</span></span>';
    b.addEventListener("click", () => { selectSpecies(s.key); closeOverlays(); });
    host.appendChild(b);
  });
}
export function selectSpecies(key) {
  if (key === state.species) return;
  state.species = key;
  save();
  clearHelpers();
  clearNearby();
  hideProb(true);
  hideFindings(true);
  applySpecies();
  spots.redraw();
  toast(sp().emoji + " " + sp().name + " — " + sp().tagline);
}

/* ---- per-species filter controls ---- */
export function renderControls() {
  const s = sp(), c = cfg();
  const host = document.getElementById("speciesFilters");
  host.innerHTML = "";
  s.controls.forEach(ct => {
    const row = document.createElement("div");
    row.className = "row";
    const lbl = '<label>' + ct.label + (ct.hint ? '<br><small>' + ct.hint + '</small>' : '') + '</label>';
    if (ct.type === "range") {
      row.innerHTML = lbl +
        '<input type="range" min="' + ct.min + '" max="' + ct.max + '" step="' + ct.step + '">' +
        '<span class="val"></span>';
      const inp = row.querySelector("input"), val = row.querySelector(".val");
      inp.value = c[ct.key];
      const paint = () => { val.textContent = c[ct.key] + ct.unit; };
      paint();
      inp.addEventListener("input", () => {
        c[ct.key] = +inp.value; paint(); save(); refreshSpots();
      });
    } else {
      row.innerHTML = lbl + '<label class="switch"><input type="checkbox"><i></i></label>';
      const inp = row.querySelector("input");
      inp.checked = !!c[ct.key];
      inp.addEventListener("change", () => {
        c[ct.key] = inp.checked; save(); refreshSpots();
      });
    }
    host.appendChild(row);
  });
}

/* ---- per-species helper overlays ---- */
export let activeHelpers = [];
export function clearHelpers() {
  activeHelpers.forEach(l => map.removeLayer(l));
  activeHelpers = [];
}
export function renderHelpers() {
  const s = sp();
  const host = document.getElementById("helperLayers");
  host.innerHTML = "";
  s.helpers.forEach(h => {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = '<label>' + h.label + '</label>' +
      '<label class="switch"><input type="checkbox"><i></i></label>';
    const inp = row.querySelector("input");
    let layer = null;
    inp.addEventListener("change", () => {
      if (inp.checked) {
        layer = layer || h.make();
        layer.addTo(map);
        activeHelpers.push(layer);
      } else if (layer) {
        map.removeLayer(layer);
        activeHelpers = activeHelpers.filter(l => l !== layer);
      }
    });
    host.appendChild(row);
  });
}

export function applySpecies() {
  const s = sp();
  document.getElementById("appTitle").textContent = s.emoji + " " + s.name + " GO";
  document.getElementById("btnSpecies").textContent = s.emoji;
  document.getElementById("legendText").textContent = s.legend;
  document.getElementById("filterTitle").textContent = s.name + "-suodatin";
  document.getElementById("infoBody").innerHTML = s.info;
  renderSeasonality();
  document.title = s.name + " GO " + s.emoji;
  renderControls();
  renderHelpers();
  renderSpeciesList();
  renderProb();
  if (state.prob.on && s.model) showProb(); else { updateProbLegend(); syncRuleLayer(); }
  renderFindingsPanel();
  if (state.findings.on && s.findings) showFindings(); else hideFindings(false);
}

export const rngOpacity = document.getElementById("rngOpacity");
rngOpacity.value = Math.round(state.opacity * 100);
document.getElementById("valOpacity").textContent = rngOpacity.value + " %";
rngOpacity.addEventListener("input", () => {
  state.opacity = +rngOpacity.value / 100;
  document.getElementById("valOpacity").textContent = rngOpacity.value + " %";
  spots.setOpacity(state.opacity);
  prob.layers.forEach(l => l.setOpacity(state.opacity));
  save();
});

