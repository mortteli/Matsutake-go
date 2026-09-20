"""Is a recorded Swedish find still a lead? The Swedish half of observation_status.py.

This does NOT define a second classification. It imports Finland's, because the map already
speaks that vocabulary: js/findings.js keys its colours, its filters and its Finnish
explanatory sentences off the exact strings `tarkka` / `summittainen` / `alueellinen` /
`tuntematon` and `ennallaan` / `epavarma` / `muuttunut` / `ulkopuolella` / `ei_tietoa` plus
their reason codes. A Swedish record that carried a new code would render as a blank.
REASONS_SE is asserted against the Finnish vocabulary at import time so that cannot happen
by accident.

    axis A, precision   imported verbatim. It is a pure function of unc_m, so it ports with
                        nothing to decide: 5215 tarkka, 176 summittainen, 98 alueellinen,
                        12 tuntematon.
    axis B, habitat     same states, same reason codes, different evidence underneath.

WHAT SWEDEN CAN AND CANNOT SEE
------------------------------
Finland compares two MVMI cycles and asks what changed. Sweden has one usable structural
vintage (SLU 2010) plus an older one (2005), and nearly every find postdates both, so the
change rules that carry Finland's verdicts mostly cannot fire here. What Sweden has instead
is a better felling record: Skogsstyrelsen dates every completed felling, so where Finland's
cut layer can only say "cut, at some point", Sweden can say "cut AFTER this find was made".

Fires:
    hakattu                 a completed felling (Sentinel-2 change detection) dated after the
                            find -- a stronger statement than Finland's undated equivalent
    hakkuuaikomus           a current Avverkningsanmalan. Skogsstyrelsen publishes only
                            notifications <=5 years old and <=75 % harvested, so unlike
                            Finland's metsankayttoilmoitukset there is no lapsed-notification
                            filter to add
    osa_alueesta_hakattu    from aggregate(), unchanged
    liian_epatarkka         unc > 1000 m or missing: 110 of 5501 records
    ei_paivamaaraa          no date
    ei_metsavaratietoa      no SLU theme has a value anywhere in the rosette
    tuore_havainto          see the note below -- the identifier and its sentence are kept,
                            the evidence under them is re-grounded
    kasvusto_havaintoa_nuorempi   alive but nearly dead: it needs a find older than the
                            stand's establishment year minus the margin, and with a 2010 age
                            raster that means a pre-1990 find. At most a handful of the 73
                            preserved specimens.

Cannot fire, and why:
    kasvupaikkatieto_muuttunut   no kasvupaikka or paatyyppi equivalent at any SLU vintage.
    ei_metsatalousmaata          SLU publishes ONE nodata value for both "not forest land"
    metsamaan_rajaus_muuttui     and "no estimate here". ml/core/mvmi_point.py exists purely
                            to keep Luke's 32767 ("a fact") apart from 32766 ("cloud"); SLU
                            gives us no such distinction, so the OFF sentinel never resolves
                            and the `ulkopuolella` state simply never occurs. That is visible
                            in the app: findings.js's `parhaat` filter counts `ulkopuolella`
                            as good, so a Swedish record on a churchyard lawn reads
                            `ei_tietoa` where a Finnish one would read "outside forestry
                            land". Sweden genuinely cannot tell a treed churchyard from a gap
                            in the model, and the honest answer is to say so rather than to
                            guess.
    puusto_nollautunut      all three are guarded by "the compared vintage is older than the
    puusto_harventunut      newest one". 2010 IS the newest usable vintage, so for any find
    ei_muutosta             from 2010 onward -- which is essentially all of them -- there is
                            no second reading to compare against.

WHY tuore_havainto HAD TO BE RE-GROUNDED
Finland's rule is "the find is newer than the imagery, so nothing could have changed
unseen". Sweden's newest structural raster is 2010, older than nearly every find, so
applying that rule mechanically would mark 99 % of records "the forest is still standing" on
the strength of no evidence at all. Here the time-aware evidence is the felling layer, not
the structural raster: UtfordAvverkningYta is Sentinel-2 change detection with national
coverage, so "a layer that would have seen a felling saw none" is a real observation. The
Finnish sentence -- "Tuore havainto: metsavaratieto ei ehdi nayttaa muutosta, eika hakkuita
ole ilmoitettu" -- is literally true under that grounding, so it is kept verbatim and only
the evidence reaching it changed.

    python ml/dataset/observation_status_se.py            # sample and classify
    python ml/dataset/observation_status_se.py --report   # cross-tab, no re-sampling
"""
import argparse, csv, json, os, sys, time
from collections import Counter

import numpy as np
import rasterio
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ML, "core"))

from observation_status import FINE_M, COARSE_M, SEVERITY, aggregate, precision, rosette  # noqa: E402
from grid_se import GridSE, RT90_2010, rt90_path                                          # noqa: E402
from slu_point import OUTSIDE, UNKNOWN, is_value, sample_cut, sample_theme                # noqa: E402

SPECIES = "matsutake_se"
RASTERS = os.path.join(ML, "data", "rasters_se")
SLU_DIR = os.path.join(RASTERS, "slu_forest_map")

NEWEST = 2010                           # the newest SLU vintage with a full theme set
OLDER = 2005
CUT_LAYER_FROM = 2010                   # UtfordAvverkningYta's usable national coverage
AGE_MARGIN = 20                         # as in Finland: k-NN age regresses to the plot mean
THEMES = ["age", "vol_total"]           # the two themes both vintages carry

TO_SWEREF = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)

# Every reason code this module can emit. Asserted below against Finland's, so a new Swedish
# code cannot reach the map without being added to the shared vocabulary on purpose.
REASONS_SE = {
    "liian_epatarkka", "ei_paivamaaraa", "ei_metsavaratietoa", "hakattu", "hakkuuaikomus",
    "osa_alueesta_hakattu", "osa_alueesta_muuttunut", "tuore_havainto",
    "kasvusto_havaintoa_nuorempi",
}
UNREACHABLE_IN_SE = {
    "ei_metsatalousmaata": "SLU has one nodata for 'not forest' and 'no estimate'",
    "metsamaan_rajaus_muuttui": "same: no OFF sentinel to compare between vintages",
    "kasvupaikkatieto_muuttunut": "no kasvupaikka/paatyyppi equivalent at any SLU vintage",
    "puusto_nollautunut": "2010 is the newest vintage; no later reading to compare",
    "puusto_harventunut": "same",
    "ei_muutosta": "same -- the no-change verdict needs two comparable vintages",
}


def _assert_vocabulary():
    """Refuse to run if this module could emit a code js/findings.js cannot render."""
    js = os.path.join(os.path.dirname(ML), "js", "findings.js")
    if not os.path.exists(js):
        return
    text = open(js, encoding="utf-8").read()
    missing = sorted(r for r in REASONS_SE if f'"{r}"' not in text and f"'{r}'" not in text
                     and f"{r}:" not in text)
    if missing:
        raise RuntimeError(
            f"reason codes {missing} are not in js/findings.js's HAB_WHY table, so they would "
            f"render as blanks on the map. Add them there deliberately, or stop emitting them.")


_assert_vocabulary()


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def point_state(p, obs_year, margin=AGE_MARGIN):
    """One rosette point -> (state, reason). Mirrors observation_status.point_state's shape
    and ordering; only the evidence differs. See the module docstring for which of Finland's
    branches have no Swedish counterpart."""
    cut, cut_year = p["cut"], p["cut_year"]
    # Finland can only say "cut". Sweden dates it, so a felling that predates the find is not
    # evidence against the find -- the mushroom was reported after the machines left.
    if cut == 2 and (not cut_year or not obs_year or cut_year >= obs_year):
        return "muuttunut", "hakattu"
    if cut == 1:
        return "epavarma", "hakkuuaikomus"

    age_new, vol_new = p["age_new"], p["vol_total_new"]
    if not is_value(age_new) and not is_value(vol_new):
        return "ei_tietoa", "ei_metsavaratietoa"
    if obs_year is None:
        return "ei_tietoa", "ei_paivamaaraa"

    # The stand was established after the find was made: the raster is describing a forest
    # that did not exist yet. Alive in principle, near-dead in practice with a 2010 raster.
    if is_value(age_new) and NEWEST - age_new > obs_year + margin:
        return "muuttunut", "kasvusto_havaintoa_nuorempi"

    # The felling layer is the time-aware evidence here, not the structural raster.
    if obs_year >= CUT_LAYER_FROM:
        return "ennallaan", "tuore_havainto"
    return "ei_tietoa", "ei_metsavaratietoa"


def classify(rec, samples, margin=AGE_MARGIN):
    unc = float(rec["unc_m"]) if rec["unc_m"] not in ("", None) else None
    year = int(rec["year"]) if rec["year"] else None
    prec = precision(unc)
    row = dict(id=rec["id"], prec=prec, year=year or "", unc_m="" if unc is None else round(unc),
               hab="", hab_why="", hab_frac="", era=NEWEST, age_new="", est_year="",
               cut="", forest_frac="")
    if prec in ("alueellinen", "tuntematon"):
        row.update(hab="ei_tietoa", hab_why="liian_epatarkka", era="")
        return row

    s = samples[rec["id"]]
    states = [point_state({k: v[i] for k, v in s.items()}, year, margin) for i in range(9)]
    hab, why, frac = aggregate(states)

    on_forest = [i for i in range(9) if is_value(s["vol_total_new"][i])]
    ages = [s["age_new"][i] for i in on_forest if is_value(s["age_new"][i])]
    age_new = sorted(ages)[len(ages) // 2] if ages else None
    cut = max((v for v in s["cut"] if v != OUTSIDE), default=None)

    row.update(hab=hab, hab_why=why, hab_frac="" if frac is None else frac,
               age_new="" if age_new is None else age_new,
               est_year="" if age_new is None else NEWEST - age_new,
               cut="" if cut is None else cut,
               forest_frac=round(len(on_forest) / 9, 2))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default=SPECIES)
    ap.add_argument("--report", action="store_true", help="cross-tab from the cache, no sampling")
    ap.add_argument("--margin", type=int, default=AGE_MARGIN)
    a = ap.parse_args()

    src = os.path.join(ML, "data", a.species, "observations.csv")
    recs = [r for r in csv.DictReader(open(src, newline="")) if r["lat"]]
    log(len(recs), "records")

    # Only the assessable ones are sampled, as observation_status.py does: the rest are
    # decided by unc_m alone and reading rasters for them would be work with no output.
    want = [r for r in recs if precision(float(r["unc_m"]) if r["unc_m"] else None)
            in ("tarkka", "summittainen")]
    log(len(want), "assessable (tarkka/summittainen)")

    cache = os.path.join(ML, "data", a.species, "observation_samples.jsonl")
    samples = sample_all(want, cache, offline=a.report)

    rows = [classify(r, samples, a.margin) for r in recs if r["id"] in samples
            or precision(float(r["unc_m"]) if r["unc_m"] else None) in ("alueellinen", "tuntematon")]
    out = os.path.join(ML, "data", a.species, "observation_status.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    log("wrote", out, len(rows), "rows")
    report(rows)


def sample_all(recs, cache_path, offline=False):
    """{id: {theme: [9 values]}} for every record, cached to disk as JSONL."""
    cached = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            cached[d["id"]] = d["s"]
    todo = [r for r in recs if r["id"] not in cached]
    log(len(cached), "cached,", len(todo), "to sample")
    if offline or not todo:
        return cached

    grid = GridSE()
    pts = {r["id"]: rosette(float(r["lat"]), float(r["lon"]),
                            float(r["unc_m"]) if r["unc_m"] else None, transformer=TO_SWEREF)
           for r in todo}
    flat = [xy for r in todo for xy in pts[r["id"]]]

    got = {}
    for theme in THEMES:
        got[f"{theme}_new"] = sample_theme(theme, NEWEST, flat, SLU_DIR)
        got[f"{theme}_era"] = sample_theme(theme, OLDER, flat, SLU_DIR)
    got.update(sample_cut(flat, RASTERS))

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "a") as fh:
        for k, r in enumerate(todo):
            s = {t: v[k * 9:(k + 1) * 9] for t, v in got.items()}
            cached[r["id"]] = s
            fh.write(json.dumps({"id": r["id"], "s": s}) + "\n")
    return cached


def report(rows):
    print("\nprecision:")
    for k, n in Counter(r["prec"] for r in rows).most_common():
        print(f"  {k:16s} {n:5d}")
    print("\nhabitat status:")
    for k, n in Counter(r["hab"] for r in rows).most_common():
        print(f"  {k:16s} {n:5d}")
    print("\nreason:")
    for k, n in Counter(r["hab_why"] for r in rows).most_common():
        print(f"  {k:30s} {n:5d}")
    unused = sorted(REASONS_SE - {r["hab_why"] for r in rows})
    if unused:
        print("\nreason codes this run never emitted:", ", ".join(unused))
    print("\nunreachable in Sweden by construction:")
    for k, why in sorted(UNREACHABLE_IN_SE.items()):
        print(f"  {k:30s} {why}")


if __name__ == "__main__":
    main()
