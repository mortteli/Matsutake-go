"""Fetch matsutake occurrence records for Sweden.

Source: GBIF (public, no key) — all records with coordinates for taxonKey 5241820, country=SE.
Sweden has no laji.fi-style national warehouse API separate from GBIF: Artportalen (the Swedish
species-observation system) already feeds GBIF directly, so there is no second source to merge
here the way fetch_observations.py merges in FinBIF/laji.fi for Finland.

Output: ml/data/matsutake_se/observations.csv (committed; contains only public, redistributable data)

Unlike the Finnish dataset, most Swedish records carry identificationVerificationStatus=Unvalidated
(citizen sightings logged directly in Artportalen, not expert-reviewed museum/collection records)
and the great majority date from 2024-2026 — a recent wave of interest, not a century of records.
That status is kept as its own column so training/weighting can treat it differently from a
verified record, rather than silently pooling both at face value.
"""
import csv, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
OUT = os.path.join(ML, "data", "matsutake_se", "observations.csv")
GBIF_TAXON = 5241820          # Tricholoma matsutake (S.Ito & S.Imai) Singer
FIELDS = ["source", "id", "date", "year", "month", "day", "lat", "lon", "unc_m", "basis",
          "verification_status", "dataset", "dataset_key", "license", "province", "locality",
          "remarks", "event_remarks", "habitat"]
# Same courtesy pause as fetch_observations.py — see there for why.
PAGE_PAUSE_S = 0.5


def clean_text(s):
    s = (s or "").strip()
    if s.lower().startswith("quality assessment:"):
        s = s.split(" | ", 1)[1].strip() if " | " in s else ""
    return s[:300] or None


def get_json(url, tries=5):
    for i in range(tries):
        try:
            time.sleep(PAGE_PAUSE_S)
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print("retry", i, e, file=sys.stderr); time.sleep(4 * (i + 1))
    raise RuntimeError(url[:120])


def gbif():
    rows, off = [], 0
    while True:
        q = dict(taxonKey=GBIF_TAXON, country="SE", hasCoordinate="true", hasGeospatialIssue="false",
                 limit=300, offset=off)
        j = get_json("https://api.gbif.org/v1/occurrence/search?" + urllib.parse.urlencode(q))
        for r in j["results"]:
            rows.append(dict(source="gbif", id=r["gbifID"], date=(r.get("eventDate") or "")[:10],
                             year=r.get("year"), month=r.get("month"), day=r.get("day"),
                             lat=r["decimalLatitude"], lon=r["decimalLongitude"],
                             unc_m=r.get("coordinateUncertaintyInMeters"), basis=r.get("basisOfRecord"),
                             verification_status=r.get("identificationVerificationStatus", ""),
                             dataset=r.get("datasetName", ""), dataset_key=r.get("datasetKey", ""),
                             license=r.get("license", ""), province=r.get("stateProvince", ""),
                             locality=(r.get("locality") or "")[:80],
                             remarks=clean_text(r.get("occurrenceRemarks")),
                             event_remarks=clean_text(r.get("eventRemarks")),
                             habitat=clean_text(r.get("habitat"))))
        off += 300
        if j.get("endOfRecords") or not j["results"]:
            break
    return rows


def redistributable(lic):
    """Same rule as fetch_observations.py: keep CC0 / CC BY / CC BY-NC, drop all-rights-reserved
    and share-alike records."""
    l = (lic or "").upper()
    return not ("ARR" in l or "-SA" in l or "SA-4" in l)


def main():
    rows = gbif()
    print("gbif records:", len(rows))
    n0 = len(rows)
    rows = [r for r in rows if redistributable(r.get("license"))]
    print("dropped for licence (ARR / share-alike):", n0 - len(rows))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    fine = sum(1 for r in rows if r["unc_m"] is not None and float(r["unc_m"]) <= 250)
    validated = sum(1 for r in rows if r["verification_status"] not in ("Unvalidated", ""))
    print("written", OUT, "total", len(rows), "with uncertainty <= 250 m:", fine,
          "validated identification:", validated)


if __name__ == "__main__":
    main()
