"""Package occurrence records for the static app's "havainnot" (findings) map layer.

Reads ml/data/<species>/observations.csv (committed source data — GBIF + public FinBIF/laji.fi
records, already filtered to redistributable licences by fetch_observations.py) and writes
data/<species>/observations.json: one small record per occurrence, with a link back to its
source page, for the map to plot as markers.

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", default="matsutake")
    a = ap.parse_args()
    src = os.path.join(ML, "data", a.species, "observations.csv")
    out = os.path.join(ROOT, "data", a.species, "observations.json")

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
                link=link(r["source"], r["id"]),
            ))

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))
    print("wrote", out, len(rows), "records")


if __name__ == "__main__":
    main()
