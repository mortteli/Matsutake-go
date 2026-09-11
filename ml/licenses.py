"""Write DATA_LICENSES.md: every data source with its licence, and per-dataset attribution for
the occurrence records stored in this repository. Also enriches background_fungi.csv with the
licence and dataset of each record (GBIF occurrence lookups).

python ml/licenses.py            (LAJI_TOKEN in the environment adds FinBIF collection names)
"""
import csv, json, os, sys, time, urllib.parse, urllib.request, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(HERE, "data", "matsutake")


def get_json(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(3 * (i + 1))
    return None


def short_license(l):
    l = (l or "").strip()
    m = {"http://creativecommons.org/publicdomain/zero/1.0/legalcode": "CC0 1.0",
         "http://creativecommons.org/licenses/by/4.0/legalcode": "CC BY 4.0",
         "http://creativecommons.org/licenses/by-nc/4.0/legalcode": "CC BY-NC 4.0",
         "CC_BY_4_0": "CC BY 4.0", "CC_BY_NC_4_0": "CC BY-NC 4.0", "CC0_1_0": "CC0 1.0", "CC-BY": "CC BY 4.0"}
    if l in m: return m[l]
    if "intellectualRights" in l:
        s = l.split("intellectualRights")[-1]                     # e.g. CC-BY-NC-4.0, CC-BY-4.0, ARR
        s = s.replace("CC-BY-NC-SA", "CC BY-NC-SA").replace("CC-BY-NC", "CC BY-NC").replace("CC-BY", "CC BY").replace("CC0-", "CC0 ")
        return s.replace("-4.0", " 4.0").replace("-1.0", " 1.0")
    return l or "unknown"


def enrich_background():
    path = os.path.join(DATA, "background_fungi.csv")
    if not os.path.exists(path):
        return []
    rows = list(csv.DictReader(open(path)))
    if rows and "license" in rows[0] and all(r.get("license") for r in rows):
        return rows
    todo = [r for r in rows if not r.get("license")]
    print("looking up licences for", len(todo), "background records", flush=True)
    info = {}
    for i in range(0, len(todo), 100):
        ids = [r["id"] for r in todo[i:i + 100]]
        q = "&".join("gbifId=" + x for x in ids)
        j = get_json("https://api.gbif.org/v1/occurrence/search?limit=100&" + q)
        for o in (j or {}).get("results", []):
            info[str(o["gbifID"])] = (o.get("license", ""), o.get("datasetKey", ""), o.get("datasetName", ""))
    for r in rows:
        lic, dk, dn = info.get(r["id"], ("", "", ""))
        r["license"] = r.get("license") or lic; r["dataset_key"] = r.get("dataset_key") or dk; r["dataset"] = r.get("dataset") or dn
    fields = ["id", "lat", "lon", "year", "species", "dataset", "dataset_key", "license"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    return rows


def main():
    obs = list(csv.DictReader(open(os.path.join(DATA, "observations.csv"))))
    bg = enrich_background()
    token = os.environ.get("LAJI_TOKEN")
    titles = {}
    def gbif_title(key):
        if key not in titles:
            j = get_json(f"https://api.gbif.org/v1/dataset/{key}")
            titles[key] = (j or {}).get("title", key)
        return titles[key]
    def laji_title(cid):
        if cid not in titles:
            j = get_json(f"https://api.laji.fi/v0/collections/{cid}?access_token={token}") if token else None
            titles[cid] = ((j or {}).get("longName") or (j or {}).get("collectionName") or cid) if isinstance(j, dict) else cid
        return titles[cid]

    def table(rows, src_label):
        c = collections.Counter((r.get("source", "gbif"), r.get("dataset_key", ""), short_license(r.get("license"))) for r in rows)
        L = ["| Source | Dataset / collection | Licence | Records |", "|---|---|---|---|"]
        for (src, key, lic), n in sorted(c.items(), key=lambda x: -x[1]):
            name = laji_title(key) if src == "laji" else gbif_title(key) if key else "(unknown)"
            link = f"https://www.gbif.org/dataset/{key}" if src == "gbif" and key else f"https://laji.fi/collection/{key}" if key else ""
            L.append(f"| {'GBIF' if src == 'gbif' else 'FinBIF (laji.fi)'} | [{name}]({link}) | {lic} | {n} |")
        return L

    lic_counts = collections.Counter(short_license(r.get("license")) for r in obs)
    bg_counts = collections.Counter(short_license(r.get("license")) for r in bg)
    L = ["# Data sources and licences", "",
         "This repository is public. Everything under `data/` and `ml/data/` is either open data "
         "redistributed under its own licence, or derived from such data. Records whose licence does "
         "not allow redistribution (all rights reserved) or requires share-alike were dropped before "
         "anything was stored or trained on (`ml/fetch_observations.py`, `redistributable()`).", "",
         "## Environmental data (all CC BY 4.0)", "",
         "| Dataset | Producer | Licence | Used for |", "|---|---|---|---|",
         "| Monilähteinen VMI (MS-NFI) forest maps 2009–2023, 16 m | Luonnonvarakeskus (Luke) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | site class, main type, age, volumes by species, basal area, canopy cover, height — app filters and model features |",
         "| Elevation model 10 m | Maanmittauslaitos (MML) | CC BY 4.0 | elevation, slope, aspect, TPI, relief |",
         "| Maaperä 1:200 000 (superficial deposits) and Glacigenic landforms | Geologian tutkimuskeskus (GTK) | CC BY 4.0 | soil class, esker / glaciofluvial formation — rasterized copies in `ml/data/rasters/gtk_*_16m.tif` |",
         "| Gridded daily/monthly climate 10 km (1961–) | Ilmatieteen laitos (FMI) | CC BY 4.0 | thermal sum and precipitation normals in `ml/data/climate/` |",
         "| Copernicus DEM GLO-90 via Open-Meteo | ESA / Open-Meteo | CC BY 4.0 | slope readout in the app |", "",
         "Attribution text used in the app and in derived files: "
         "*© Luonnonvarakeskus (Luke) MVMI, © Maanmittauslaitos, © Geologian tutkimuskeskus, © Ilmatieteen laitos — CC BY 4.0.*", "",
         "## Occurrence records (training presences), `ml/data/matsutake/observations.csv`", "",
         f"{len(obs)} records of *Tricholoma matsutake* in Finland, fetched from GBIF and the Finnish "
         "Biodiversity Information Facility (FinBIF, laji.fi) on " + time.strftime("%Y-%m-%d") + ". "
         "Each row carries its own `license`. Licence mix: " + ", ".join(f"{k}: {v}" for k, v in lic_counts.most_common()) + ".", ""]
    L += table(obs, "obs")
    L += ["", "GBIF asks that data use is cited; the records here came through the GBIF occurrence API "
          "(no download DOI). Cite as: GBIF.org (" + time.strftime("%Y-%m-%d") + ") GBIF Occurrence "
          "Search, *Tricholoma matsutake*, Finland, https://www.gbif.org/occurrence/search?taxon_key=5241820&country=FI ; "
          "and FinBIF: Suomen Lajitietokeskus / FinBIF (" + time.strftime("%Y-%m-%d") + "), https://laji.fi/taxon/MX.72541.", ""]
    if bg:
        L += ["## Target-group background records, `ml/data/matsutake/background_fungi.csv`", "",
              f"{len(bg)} records of other fungi (August–September, 2010–, coordinate accuracy ≤ 250 m) used only as "
              "presence-background contrast. Licence mix: " + ", ".join(f"{k}: {v}" for k, v in bg_counts.most_common()) + ".", ""]
        L += table(bg, "bg")
    L += ["", "## Derived data in this repository", "",
          "| File | What | Licence |", "|---|---|---|",
          "| `ml/data/matsutake/dataset.csv` | training table: the records above joined with environmental features | CC BY-NC 4.0 (contains CC BY-NC records) |",
          "| `ml/models/matsutake/` | model weights, scaler, CV report | CC BY-NC 4.0 |",
          "| `data/matsutake/prob_*.tif`, `prob_meta.json` | 16 m probability map for the app | CC BY-NC 4.0 — attribution as above; non-commercial because CC BY-NC observation records contributed to training |",
          "| `ml/data/climate/*.tif`, `ml/data/rasters/gtk_*_16m.tif`, `ml/data/gtk_classes.json` | rasterized / aggregated copies of FMI and GTK data | CC BY 4.0 (© FMI, © GTK) |", "",
          "To publish the derived layers under plain CC BY 4.0, re-run the pipeline with the CC BY-NC "
          "records removed (`ml/fetch_observations.py` — filter on the `license` column).", "",
          "Software licences: see `LICENSE` (MIT) and `THIRD_PARTY_LICENSES.md`."]
    open(os.path.join(ROOT, "DATA_LICENSES.md"), "w").write("\n".join(L) + "\n")
    print("wrote DATA_LICENSES.md; observation licences:", dict(lic_counts))


if __name__ == "__main__":
    main()
