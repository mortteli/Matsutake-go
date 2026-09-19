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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    a = ap.parse_args()
    src = os.path.join(ML, "data", a.species, "observations.csv")
    out = os.path.join(ROOT, "data", a.species, "observations.json")
    status = load_status(a.species)

    rows = []
    with open(src, newline="") as f:
        for r in csv.DictReader(f):
            rows.append(dict(
                id=r["id"], source=r["source"],
                lat=round(float(r["lat"]), 5), lon=round(float(r["lon"]), 5),
                date=r["date"] or None,
                unc_m=round(float(r["unc_m"])) if r["unc_m"] else None,
                basis=r["basis"] or None,
                dataset=r["dataset"] or None,
                license=r["license"] or None,
                locality=r["locality"] or None,
                remarks=r.get("remarks") or None,
                event_remarks=r.get("event_remarks") or None,
                habitat=r.get("habitat") or None,
                link=link(r["source"], r["id"]),
                **status.get(r["id"], {}),
            ))

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))
    print("wrote", out, len(rows), "records",
          f"({sum(1 for r in rows if 'hab' in r)} luokiteltu)" if status else "(ei luokittelua)")


if __name__ == "__main__":
    main()
