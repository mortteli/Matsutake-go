"""Fetch matsutake occurrence records for Finland.

Sources
  GBIF   (public, no key)  – all records with coordinates for taxonKey 5241820
  laji.fi (FinBIF)         – only if LAJI_TOKEN is set in the environment; the token is
                             never written to disk. Records are de-duplicated against GBIF.
Output: ml/data/matsutake/observations.csv (committed; contains only public data)
"""
import csv, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
OUT = os.path.join(ML, "data", "matsutake", "observations.csv")
GBIF_TAXON = 5241820          # Tricholoma matsutake (S.Ito & S.Imai) Singer
LAJI_TAXON = "MX.72541"
FIELDS = ["source", "id", "date", "year", "month", "day", "lat", "lon", "unc_m", "basis", "dataset", "dataset_key", "license", "locality", "remarks"]
# Courtesy pause between pages. Matsutake is a few hundred records — one or two pages from each
# API — so this costs nothing today; it is here so that pointing the script at a taxon with tens
# of thousands of records cannot turn into a burst against a free public API. Every call below is
# one page of a paging loop, so one sleep in one place covers both sources.
PAGE_PAUSE_S = 0.5


def clean_remarks(s):
    """Free-text notes from the observer. GBIF records sourced from iNaturalist prefix these with
    an automated "Quality assessment: ..." tag joined by " | "; that tag is metadata about the
    record, not something the observer wrote, so it is stripped here rather than shown as if it
    were a remark."""
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
        q = dict(taxonKey=GBIF_TAXON, country="FI", hasCoordinate="true", hasGeospatialIssue="false",
                 limit=300, offset=off)
        j = get_json("https://api.gbif.org/v1/occurrence/search?" + urllib.parse.urlencode(q))
        for r in j["results"]:
            rows.append(dict(source="gbif", id=r["gbifID"], date=(r.get("eventDate") or "")[:10],
                             year=r.get("year"), month=r.get("month"), day=r.get("day"),
                             lat=r["decimalLatitude"], lon=r["decimalLongitude"],
                             unc_m=r.get("coordinateUncertaintyInMeters"), basis=r.get("basisOfRecord"),
                             dataset=r.get("datasetName", ""), dataset_key=r.get("datasetKey", ""),
                             license=r.get("license", ""), locality=(r.get("locality") or "")[:80],
                             remarks=clean_remarks(r.get("occurrenceRemarks"))))
        off += 300
        if j.get("endOfRecords") or not j["results"]:
            break
    return rows


def laji(token):
    """FinBIF warehouse (public records only). Coordinates are the WGS84 centre point of the
    reported area, accuracy in metres; the date comes from the display string."""
    rows, page = [], 1
    while True:
        q = dict(taxonId=LAJI_TAXON, countryId="ML.206", pageSize=1000, page=page, access_token=token)
        j = get_json("https://api.laji.fi/v0/warehouse/query/unit/list?" + urllib.parse.urlencode(q))
        for r in j.get("results", []):
            g, u = r.get("gathering", {}), r.get("unit", {})
            pt = g.get("conversions", {}).get("wgs84CenterPoint", {})
            if "lat" not in pt:
                continue
            d = (g.get("displayDateTime") or "")[:10]
            ok = len(d) == 10 and d[4] == "-" and d[7] == "-"
            y, m, dd = (int(x) for x in d.split("-")) if ok else (None, None, None)
            rows.append(dict(source="laji", id=(u.get("unitId") or "").replace("http://", ""), date=d if ok else "",
                             year=y, month=m, day=dd, lat=pt["lat"], lon=pt["lon"],
                             unc_m=g.get("interpretations", {}).get("coordinateAccuracy"),
                             basis=u.get("recordBasis"), dataset=(r.get("document", {}).get("collectionId") or "").replace("http://tun.fi/", ""),
                             dataset_key=(r.get("document", {}).get("collectionId") or "").replace("http://tun.fi/", ""),
                             license=(r.get("document", {}).get("licenseId") or "").replace("http://tun.fi/MY.intellectualRights", ""),
                             locality=(g.get("locality") or "")[:80],
                             remarks=clean_remarks(u.get("notes") or g.get("notes"))))
        if page >= j.get("lastPage", 1):
            break
        page += 1
    return rows


def redistributable(lic):
    """Records we may keep in a public repository: CC0 / CC BY / CC BY-NC. All-rights-reserved and
    share-alike records are dropped entirely (not used for training either)."""
    l = (lic or "").upper()
    return not ("ARR" in l or "-SA" in l or "SA-4" in l)


def main():
    rows = gbif()
    print("gbif records:", len(rows))
    token = os.environ.get("LAJI_TOKEN")
    if token:
        lrows = laji(token)
        seen = {(round(r["lat"], 3), round(r["lon"], 3), r["date"]) for r in rows}
        new = [r for r in lrows if (round(r["lat"], 3), round(r["lon"], 3), r["date"]) not in seen]
        print("laji records:", len(lrows), "new after de-dup:", len(new))
        rows += new
    n0 = len(rows)
    rows = [r for r in rows if redistributable(r.get("license"))]
    print("dropped for licence (ARR / share-alike):", n0 - len(rows))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    fine = sum(1 for r in rows if r["unc_m"] is not None and float(r["unc_m"]) <= 250)
    print("written", OUT, "total", len(rows), "with uncertainty <= 250 m:", fine)


if __name__ == "__main__":
    main()
