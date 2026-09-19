"""Is a recorded find still a lead, or only a record?

Two questions, kept apart because they have different answers and different remedies.

**How precisely was it located.** Straight from `unc_m`, at the thresholds build_dataset.py
already uses to decide what may train the model, so the map and the model say the same thing
about the same record: 250 m is the line below which a find is a place you can walk to, 1 km the
line below which it is at least a neighbourhood. Above that a record is a municipality centroid
with a mushroom attached — 139 of the 445 are, up to 100 km, and 16 of them sit on one pixel in
Utsjoki.

**Whether the ground is still what it was.** A find is a lead because of the forest it was made
in. Where that forest has since been cut, the coordinate is still good and the stand is not, and
the map must say so without either throwing the record away or pretending it is fresh.

The precision question gates the habitat question. Reading a 16 m cell underneath a record
located to ±100 km does not describe the find, it describes whatever happens to sit at the
centroid, so those records are never assessed at all.

Evidence, and what each is worth
--------------------------------
*Metsakeskus harvest state* (`cut`, 2021 onwards) is the only source here that measures rather
than estimates: value 2 comes from the harvesting machine's own telemetry. Trusted outright.

*Stand age against the find's own year* is what catches the case the whole file exists for — a
1935 find standing in a forest planted in 1993. Age is an estimate, so it needs a margin, and
the margin is a bias correction rather than a tolerance: MVMI's k-NN age regresses toward the
plot mean, which makes old stands read young, which is the direction that manufactures false
verdicts.

*Age collapsing between two inventories* (60+ years down to 20 within at most 14 elapsed) is a
felling and nothing else. It covers 2009-2021, where the harvest layer does not reach.

*Site type and main type changing between inventories* is mostly the estimator changing its
mind. Both describe soil, which does not turn over in fourteen years except by ditching, so a
disagreement is worth a flag and never a verdict.

*The forestry-land mask moving between inventories* is worth nothing at all. Measured over
1200x1200 cell windows, 3.7 % of cells around Tampere leave the mask between 2009 and 2023 and
5.6 % enter it; in Etela-Savo 2.8 % each way. Symmetry at that scale is noise — Finland is not
turning over a twentieth of its forestry land — so a cell that is inside the mask in one cycle
and outside it in the other is recorded as unknown, not as a change.

Off forestry land in *both* inventories is the cemetery case, and it stays honest: MVMI never
described this ground, so nothing here can say the trees went and nothing can say they stayed.
`fra_luokka` was the obvious way to split a treed churchyard from a car park — its class 4 is
literally "other land with tree cover" — but the raster carries the same forestry-land mask as
every other theme, so off forestry land it is empty too. What the rosette can still say is how
much forestry land lies within the record's own uncertainty, and that is reported instead.

    python ml/dataset/observation_status.py                     # sample and write the CSV
    python ml/dataset/observation_status.py --ids 3713368706 --explain
    python ml/dataset/observation_status.py --report
    python ml/dataset/observation_status.py --from-cache --margin 30 --report   # no network
"""
import argparse, csv, json, math, os, sys, time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))

from pyproj import Transformer

from grid import CYCLES, cycle_for_year
from mvmi_point import OFF, OUTSIDE, UNKNOWN, is_value, sample_cut, sample_theme

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
NEWEST = max(CYCLES)                    # 2023: the cycle everything is compared against

# Precision bands. build_dataset.py trains on <= 250 m at full weight and 250-1000 m at 0.3,
# and drops the rest; the same two numbers name the bands here.
FINE_M, COARSE_M = 250, 1000

# The oldest date from which the newest inventory's imagery could already show a change. Kept in
# step with MVMI_EFFECTIVE in js/constants.js and ml/ingest/fetch_harvests.py.
MVMI_EFFECTIVE_YEAR = 2021

# Stand age is a k-NN estimate biased toward the plot mean, so old stands read young and the
# errors run toward false "the forest was replaced" verdicts. 20 years is both a plausible
# correction for that bias and the app's own coarsest age step (AGE_STEPS[0], js/constants.js).
# --report prints the verdict counts at 10 / 20 / 30 so the choice can be made against numbers.
AGE_MARGIN = 20

# A felling, read from two inventories at most 14 years apart. Nothing else takes a mature stand
# down to a seedling one.
OLD_ENOUGH, RESET_TO = 60, 20

THEMES = ["maaluokka", "ika", "kasvupaikka", "paatyyppi", "tilavuus"]
OPEN_MIRE = 4                           # paatyyppi: avosuo, naturally ageless and treeless

# Worst first: how a tie between rosette points is broken.
SEVERITY = ["muuttunut", "epavarma", "ulkopuolella", "ennallaan"]

TO_TM35 = Transformer.from_crs("EPSG:4326", "EPSG:3067", always_xy=True)


def cache_path(species):
    """Every sampled cell, one line per (record, cycle, theme).

    Committed rather than left in data/raw/ with build_dataset.py's scratch, because it is what
    makes `--from-cache --margin N --report` work for somebody who has just cloned the repo: the
    thresholds can be moved and the whole table re-decided in a second, with no network and no
    trust in the verdicts already written. 190 KB against a 2 MB dataset.csv next to it.
    """
    return os.path.join(ML, "data", species, "observation_samples.jsonl")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------ axis A: precision
def precision(unc_m):
    if unc_m is None:
        return "tuntematon"
    if unc_m <= FINE_M:
        return "tarkka"
    if unc_m <= COARSE_M:
        return "summittainen"
    return "alueellinen"


def rosette(lat, lon, unc_m):
    """Nine points: the record's own coordinate and eight at the uncertainty disc's median
    radius. Deterministic, unlike build_dataset.py's five random draws — this output is
    committed and diffed, so it has to come out the same twice. The 30 m floor gives even a
    1 m GPS fix a 3x3 neighbourhood, which is what keeps one stray road cell inside a forest
    from deciding the verdict on its own."""
    x, y = TO_TM35.transform(lon, lat)
    r = max(unc_m or 0, 30) / math.sqrt(2)
    return [(x, y)] + [(x + r * math.cos(math.radians(a)), y + r * math.sin(math.radians(a)))
                       for a in range(0, 360, 45)]


# ------------------------------------------------------------------ axis B: one rosette point
def point_state(p, obs_year, era, margin):
    """One rosette point -> (state, reason). `p` holds raw sampled values, already normalised to
    the OFF / UNKNOWN / OUTSIDE sentinels by mvmi_point."""
    if p["cut"] == 2:
        return "muuttunut", "hakattu"
    if p["cut"] == 1:
        return "epavarma", "hakkuuaikomus"

    off_era, off_new = p["maaluokka_era"] == OFF, p["maaluokka_new"] == OFF
    if off_era and off_new:
        return "ulkopuolella", "ei_metsatalousmaata"
    if off_era != off_new:
        return "ei_tietoa", "metsamaan_rajaus_muuttui"      # mask noise, see the module docstring

    # cycle_for_year(None) returns the newest cycle, which would quietly turn "no date" into a
    # comparison of 2023 against itself. Caught here, before any rule can read obs_year.
    if obs_year is None:
        return "ei_tietoa", "ei_paivamaaraa"

    if obs_year >= MVMI_EFFECTIVE_YEAR:
        return "ennallaan", "tuore_havainto"

    ika_new, ika_era = p["ika_new"], p["ika_era"]

    if is_value(ika_new) and NEWEST - ika_new > obs_year + margin:
        return "muuttunut", "kasvusto_havaintoa_nuorempi"

    if (era < NEWEST and is_value(ika_era) and is_value(ika_new)
            and ika_era >= OLD_ENOUGH and ika_new <= RESET_TO
            and p["paatyyppi_new"] != OPEN_MIRE):
        return "muuttunut", "puusto_nollautunut"

    vol_era, vol_new = p["tilavuus_era"], p["tilavuus_new"]
    site_era, site_new = p["kasvupaikka_era"], p["kasvupaikka_new"]
    main_era, main_new = p["paatyyppi_era"], p["paatyyppi_new"]
    if (is_value(vol_era) and is_value(vol_new) and vol_era >= 70 and vol_new <= 0.4 * vol_era):
        return "epavarma", "puusto_harventunut"
    if is_value(main_era) and is_value(main_new) and main_era != main_new:
        return "epavarma", "kasvupaikkatieto_muuttunut"
    if is_value(site_era) and is_value(site_new) and abs(site_era - site_new) >= 2:
        return "epavarma", "kasvupaikkatieto_muuttunut"

    if not any(is_value(p[f"{t}_new"]) for t in THEMES):
        return "ei_tietoa", "ei_metsavaratietoa"
    return "ennallaan", "ei_muutosta"


def aggregate(states):
    """Nine point verdicts -> one. Majority of what could be assessed, ties to the worse state.

    One cut cell inside a kilometre-wide disc must not condemn the record, but it must not be
    swallowed either — a minority "muuttunut" pulls the record down to "epavarma" instead of
    being outvoted into silence."""
    usable = [s for s in states if s[0] != "ei_tietoa"]
    if not usable:
        reasons = Counter(r for _, r in states)
        return "ei_tietoa", reasons.most_common(1)[0][0], None
    share = Counter(s for s, _ in usable)
    top = max(share.values())
    state = next(s for s in SEVERITY if share.get(s) == top)
    frac = top / len(usable)
    if state != "muuttunut" and 0 < share.get("muuttunut", 0) < len(usable) / 2:
        changed = Counter(r for s, r in usable if s == "muuttunut").most_common(1)[0][0]
        # Not "this find is on a clear-cut" — part of the disc is, and which part the find came
        # from is exactly what the record does not say. The reason code has to carry that,
        # or the readout states as fact something the aggregation only suspects.
        why = "osa_alueesta_hakattu" if changed == "hakattu" else "osa_alueesta_muuttunut"
        return "epavarma", why, round(share["muuttunut"] / len(usable), 2)
    reason = Counter(r for s, r in usable if s == state).most_common(1)[0][0]
    return state, reason, round(frac, 2)


# ------------------------------------------------------------------ sampling
def load_cache(path):
    cache = {}
    if os.path.exists(path):
        for line in open(path):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            cache[d["k"]] = d["v"]
    return cache


def sample_all(rosettes, eras, cache, offline, path):
    """{id: {"theme_era"/"theme_new"/"cut": [9 ints]}}, filling the cache as it goes.

    One pass per (theme, cycle) rather than per record: a raster is opened once and the records
    that need it are read north to south, so consecutive reads land in the same COG tiles."""
    need = defaultdict(dict)                       # (theme, cycle) -> {id: pts}
    for rid, pts in rosettes.items():
        for theme in THEMES:
            for cycle in {eras[rid], NEWEST}:
                if f"{rid}:{cycle}:{theme}" not in cache:
                    need[(theme, cycle)][rid] = pts
    if any(f"{rid}:cut" not in cache for rid in rosettes):
        need[("cut", 0)] = {r: p for r, p in rosettes.items() if f"{r}:cut" not in cache}

    if need and offline:
        raise SystemExit(f"--from-cache, but {sum(len(v) for v in need.values())} samples are "
                         f"missing from {path}. Run once without it.")

    if need:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as fh:
            for (theme, cycle), want in sorted(need.items()):
                log(f"sampling {theme} {cycle or ''} at {len(want)} records")
                got = sample_cut(want) if theme == "cut" else sample_theme(theme, cycle, want)
                for rid, vals in got.items():
                    key = f"{rid}:cut" if theme == "cut" else f"{rid}:{cycle}:{theme}"
                    cache[key] = vals
                    fh.write(json.dumps({"k": key, "v": vals}) + "\n")
                fh.flush()

    out = {}
    for rid in rosettes:
        era = eras[rid]
        rec = {"cut": cache[f"{rid}:cut"]}
        for theme in THEMES:
            rec[f"{theme}_era"] = cache[f"{rid}:{era}:{theme}"]
            rec[f"{theme}_new"] = cache[f"{rid}:{NEWEST}:{theme}"]
        out[rid] = rec
    return out


# ------------------------------------------------------------------ one record
def classify(rec, samples, margin, explain=False):
    """rec: a row of observations.csv. Returns the CSV row this script writes."""
    unc = float(rec["unc_m"]) if rec["unc_m"] not in ("", None) else None
    year = int(rec["year"]) if rec["year"] else None
    prec = precision(unc)
    row = dict(id=rec["id"], prec=prec, year=year or "", unc_m="" if unc is None else round(unc),
               hab="", hab_why="", hab_frac="", era="", age_new="", est_year="",
               cut="", forest_frac="")

    if prec in ("alueellinen", "tuntematon"):
        row.update(hab="ei_tietoa", hab_why="liian_epatarkka")
        return row

    era = cycle_for_year(year)
    s = samples[rec["id"]]
    row["era"] = era

    states = []
    for i in range(9):
        p = {k: v[i] for k, v in s.items()}
        states.append(point_state(p, year, era, margin))
    hab, why, frac = aggregate(states)

    on_forest = [i for i in range(9) if is_value(s["maaluokka_new"][i])]
    ages = [s["ika_new"][i] for i in on_forest if is_value(s["ika_new"][i])]
    age_new = sorted(ages)[len(ages) // 2] if ages else None
    cut = max(v for v in s["cut"] if v != OUTSIDE) if any(v != OUTSIDE for v in s["cut"]) else None

    row.update(hab=hab, hab_why=why, hab_frac="" if frac is None else frac,
               age_new="" if age_new is None else age_new,
               est_year="" if age_new is None else NEWEST - age_new,
               cut="" if cut is None else cut,
               forest_frac=round(len(on_forest) / 9, 2))

    if explain:
        print(f"\n=== {rec['id']}  {rec['date'] or 'ei pvm'}  ±{row['unc_m'] or '?'} m  "
              f"{rec['locality'] or ''}")
        print(f"    {rec['lat']}, {rec['lon']}  ->  tarkkuus '{prec}', vertailujaksot {era} vs {NEWEST}")
        print(f"    rusetin säde {round(max(unc or 0, 30) / math.sqrt(2))} m")
        print(f"    {'piste':>6} {'cut':>4} " +
              " ".join(f"{t[:5]+'.'+str(c)[-2:]:>9}" for t in THEMES for c in (era, NEWEST)))
        for i in range(9):
            vals = " ".join(f"{fmt_raw(s[f'{t}_{w}'][i]):>9}"
                            for t in THEMES for w in ("era", "new"))
            print(f"    {i:>6} {s['cut'][i]:>4} {vals}   -> {states[i][0]} / {states[i][1]}")
        print(f"    metsätalousmaata {row['forest_frac']:.0%} · ikä(2023) {row['age_new'] or '-'}"
              f" · syntynyt {row['est_year'] or '-'}")
        print(f"    TUOMIO: {hab} / {why}" + (f"  ({frac:.0%} arvioitavista)" if frac else ""))
    return row


def fmt_raw(v):
    return {OFF: "ei-mm", UNKNOWN: "pilvi", OUTSIDE: "ulkona"}.get(v, str(v))


# ------------------------------------------------------------------ driver
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--margin", type=int, default=AGE_MARGIN)
    ap.add_argument("--ids", nargs="*", help="only these record ids")
    ap.add_argument("--explain", action="store_true", help="print every sampled value per record")
    ap.add_argument("--report", action="store_true", help="cross-tab instead of writing the CSV")
    ap.add_argument("--from-cache", action="store_true", help="no network: reuse cached samples")
    a = ap.parse_args()

    data = os.path.join(ML, "data", a.species)
    recs = list(csv.DictReader(open(os.path.join(data, "observations.csv"), newline="")))
    if a.ids:
        recs = [r for r in recs if r["id"] in a.ids]
        if not recs:
            raise SystemExit("no such record id in observations.csv")

    assessable = [r for r in recs
                  if precision(float(r["unc_m"]) if r["unc_m"] else None)
                  in ("tarkka", "summittainen")]
    log(f"{len(recs)} havaintoa, joista {len(assessable)} paikannettu tarkemmin kuin {COARSE_M} m")

    rosettes = {r["id"]: rosette(float(r["lat"]), float(r["lon"]),
                                 float(r["unc_m"]) if r["unc_m"] else None) for r in assessable}
    eras = {r["id"]: cycle_for_year(int(r["year"]) if r["year"] else None) for r in assessable}
    cache = load_cache(cache_path(a.species))
    samples = (sample_all(rosettes, eras, cache, a.from_cache, cache_path(a.species))
               if rosettes else {})

    rows = [classify(r, samples, a.margin, a.explain) for r in recs]

    if a.report:
        report(rows, recs, samples, a)
        return
    if a.ids:
        return                                  # a spot check never rewrites the committed CSV

    out = os.path.join(data, "observation_status.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log(f"wrote {out} ({len(rows)} rows, margin {a.margin} v)")


def report(rows, recs, samples, a):
    by_id = {r["id"]: r for r in recs}
    precs = ["tarkka", "summittainen", "alueellinen", "tuntematon"]
    habs = ["ennallaan", "epavarma", "muuttunut", "ulkopuolella", "ei_tietoa"]
    tab = Counter((r["prec"], r["hab"]) for r in rows)

    print(f"\n{len(rows)} havaintoa · ikämarginaali {a.margin} v\n")
    print(f"{'':<14}" + "".join(f"{h:>14}" for h in habs) + f"{'yht':>7}")
    for p in precs:
        line = [tab[(p, h)] for h in habs]
        print(f"{p:<14}" + "".join(f"{v:>14}" for v in line) + f"{sum(line):>7}")
    tot = [sum(tab[(p, h)] for p in precs) for h in habs]
    print(f"{'yht':<14}" + "".join(f"{v:>14}" for v in tot) + f"{sum(tot):>7}")

    print("\nsyyt:")
    for why, n in Counter(r["hab_why"] for r in rows).most_common():
        print(f"  {n:>4}  {why}")

    print("\nikämarginaalin vaikutus:")
    for m in (10, 20, 30, 40):
        c = Counter(classify(by_id[r["id"]], samples, m)["hab"] for r in rows)
        print(f"  {m:>3} v:  " + "  ".join(f"{h} {c[h]}" for h in habs))

    old = [r for r in rows if r["year"] and int(r["year"]) < 1950 and r["hab"] != "ei_tietoa"]
    if old:
        print(f"\nennen 1950 tehdyt, arvioitavissa olevat ({len(old)}): "
              + "  ".join(f"{h} {sum(1 for r in old if r['hab'] == h)}" for h in habs))


if __name__ == "__main__":
    main()
