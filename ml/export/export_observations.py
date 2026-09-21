"""Package occurrence records for the static app's "havainnot" (findings) map layer.

Reads ml/data/<species>/observations.csv (committed source data — GBIF + public FinBIF/laji.fi
records, already filtered to redistributable licences by fetch_observations.py) and writes
data/<species>/observations.json: one small record per occurrence, with a link back to its
source page, for the map to plot as markers.

Where ml/data/<species>/observation_status.csv exists, each record also carries how precisely it
was located and whether the ground is still what it was when the find was made — see
ml/dataset/observation_status.py, which computes it. The join is by id and it is optional in
both directions: a record the status table does not mention gets none of those keys at all
rather than a row of nulls, and js/findings.js draws such a record the way it drew every record
before any of this existed. That keeps this script a pure file-to-file transform with no network
and no rasterio, which is what lets observations.json be rebuilt while Luke is down.

python ml/export/export_observations.py [--species matsutake]
"""
import argparse, csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
ROOT = os.path.dirname(ML)


def link(source, id_):
    if source == "gbif":
        return "https://www.gbif.org/occurrence/" + id_
    if source == "laji":
        return "http://" + id_  # a laji.fi/FinBIF persistent identifier, e.g. id.luomus.fi/MY.xxx
    return None


def num(s, cast=int):
    return cast(s) if s not in ("", None) else None


def load_status(species):
    """{id: {json key: value}} from observation_status.csv, or {} when it has not been built.

    Only the fields the map actually reads are carried over; the sampled values the verdict was
    derived from stay in the CSV, where a reviewer can see them, rather than riding along in
    every one of 445 records.
    """
    path = os.path.join(ML, "data", species, "observation_status.csv")
    if not os.path.exists(path):
        return {}
    out = {}
    for r in csv.DictReader(open(path, newline="")):
        rec = dict(prec=r["prec"], hab=r["hab"], hab_why=r["hab_why"])
        for key, src, cast in (("hab_cycle", "era", int), ("est_year", "est_year", int),
                               ("forest_frac", "forest_frac", float),
                               ("hab_frac", "hab_frac", float)):
            v = num(r[src], cast)
            if v is not None:
                rec[key] = v
        out[r["id"]] = rec
    return out


MAX_TEXT = 140          # locality/remarks/habitat are popup-only; the full text is in the CSV


def clip(s):
    """Trim a free-text field for the payload.

    Merging Sweden in takes the file from 455 records to ~5950, and the Swedish localities
    and habitat notes are long ("aldre renbetad fattigris- och lavtallskog pa torr
    moranmark, torrbacke mot myr"). The popup is the only thing that reads them, so the
    untruncated text stays in observations.csv where analysis happens.
    """
    s = (s or "").strip()
    if not s:
        return None
    return s if len(s) <= MAX_TEXT else s[:MAX_TEXT - 1].rstrip() + "…"


def read_species(species, country):
    src = os.path.join(ML, "data", species, "observations.csv")
    status = load_status(species)
    rows = []
    with open(src, newline="") as f:
        for r in csv.DictReader(f):
            if not r["lat"]:
                continue
            rows.append(dict(
                id=r["id"], source=r["source"], country=country,
                lat=round(float(r["lat"]), 5), lon=round(float(r["lon"]), 5),
                date=r["date"] or None,
                unc_m=round(float(r["unc_m"])) if r["unc_m"] else None,
                basis=r["basis"] or None,
                dataset=r["dataset"] or None,
                license=r["license"] or None,
                locality=clip(r.get("locality")),
                remarks=clip(r.get("remarks")),
                event_remarks=clip(r.get("event_remarks")),
                habitat=clip(r.get("habitat")),
                link=link(r["source"], r["id"]),
                **status.get(r["id"], {}),
            ))
    return rows, bool(status)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    ap.add_argument("--merge", action="append", metavar="SPECIES:CC", default=None,
                    help="also include ml/data/<SPECIES>/observations.csv, tagged with country "
                         "code CC (e.g. --merge matsutake_se:SE). Each source is joined to its "
                         "own observation_status.csv.")
    ap.add_argument("--country", default="FI", help="country code for --species")
    a = ap.parse_args()
    out = os.path.join(ROOT, "data", a.species, "observations.json")

    # Every record carries a country. The map draws both under one toggle -- js/findings.js
    # plots plain lat/lon markers, so it needs no projection work to reach Sweden -- but the
    # two sets are not interchangeable and anything that reasons about them has to be able to
    # tell them apart. js/seasonality.js is the immediate case: its area() function encodes
    # Finnish province borders as straight lines fitted between lon 24 and 28.6, so Swedish
    # points at lon 11-24 would be filed under "Lappi" and "Ita- ja Etela-Suomi" and the
    # season chart would quietly become wrong.
    rows, classified = read_species(a.species, a.country)
    per_country = {a.country: len(rows)}
    for spec in (a.merge or []):
        name, _, cc = spec.partition(":")
        extra, extra_classified = read_species(name, cc or "??")
        seen = {r["id"] for r in rows}
        extra = [r for r in extra if r["id"] not in seen]   # GBIF ids are globally unique
        rows += extra
        per_country[cc or "??"] = len(extra)
        classified = classified or extra_classified

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(out)
    print("wrote", out, len(rows), "records", per_country,
          f"({sum(1 for r in rows if 'hab' in r)} luokiteltu)" if classified else "(ei luokittelua)",
          f"{size / 1048576:.1f} MB")


if __name__ == "__main__":
    main()
