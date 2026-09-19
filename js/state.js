import { SPECIES } from "./species.js";

/* ================= state ================= */
export const STORE_KEY = "matsutakego.v2";
// `hideCut` is global rather than per-species on purpose: all five need standing forest, and
// ukonsieni's own text already says a bare clear-cut is out.
export const state = { species: SPECIES[0].key, cfg: {}, opacity: 0.75, hideCut: true, prob: { on: true, pct: 2 }, findings: { on: true, filter: "kaikki" } };
SPECIES.forEach(s => { state.cfg[s.key] = Object.assign({}, s.defaults); });

export function sp()  { return SPECIES.find(s => s.key === state.species) || SPECIES[0]; }
export function cfg() { return state.cfg[state.species]; }

export function load() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return;
    const j = JSON.parse(raw);
    if (j.species && SPECIES.some(s => s.key === j.species)) state.species = j.species;
    if (typeof j.opacity === "number") state.opacity = j.opacity;
    if (typeof j.hideCut === "boolean") state.hideCut = j.hideCut;
    if (j.prob) { state.prob.on = !!j.prob.on; if (typeof j.prob.pct === "number") state.prob.pct = j.prob.pct; }
    if (j.findings) {
      state.findings.on = !!j.findings.on;
      if (["kaikki", "paikannetut", "parhaat"].includes(j.findings.filter))
        state.findings.filter = j.findings.filter;
    }
    SPECIES.forEach(s => {
      if (j.cfg && j.cfg[s.key]) Object.keys(s.defaults).forEach(k => {
        if (j.cfg[s.key][k] !== undefined) state.cfg[s.key][k] = j.cfg[s.key][k];
      });
    });
  } catch (e) { /* private mode / corrupt value — defaults are fine */ }
}
export function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
}
load();
