"""Write DATA_LICENSES.md: every data source with its licence, and per-dataset attribution for
the occurrence records stored in this repository. Also enriches background_fungi.csv with the
licence and dataset of each record (GBIF occurrence lookups).

Every species with an ml/data/<key>/observations.csv gets its own attribution section. That is
not bookkeeping: most of these records are CC BY, which *requires* naming the dataset they came
from, so a species whose records ship without a section here is a licence violation rather than
an untidy file.

python ml/licenses.py            (LAJI_TOKEN in the environment adds FinBIF collection names)
"""
import csv, json, os, sys, time, urllib.parse, urllib.request, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(HERE, "data", "matsutake")      # background_fungi.csv lives here

sys.path.insert(0, os.path.join(HERE, "ingest"))
from fetch_observations import TAXA                  # noqa: E402  (species -> taxon ids, latin name)


def species_with_records():
    """[(key, taxa, rows)] for every species whose observations.csv exists, TAXA order."""
    out = []
    for key, taxa in TAXA.items():
        path = os.path.join(HERE, "data", key, "observations.csv")
        if os.path.exists(path):
            out.append((key, taxa, list(csv.DictReader(open(path)))))
    return out


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
    species = species_with_records()
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

    bg_counts = collections.Counter(short_license(r.get("license")) for r in bg)
    L = ["# Data sources and licences", "",
         "This repository is public. Everything under `data/` and `ml/data/` is either open data "
         "redistributed under its own licence, or derived from such data. Records whose licence does "
         "not allow redistribution (all rights reserved) or requires share-alike were dropped before "
         "anything was stored or trained on (`ml/ingest/fetch_observations.py`, `redistributable()`).", "",
         "## Environmental data (all CC BY 4.0)", "",
         "| Dataset | Producer | Licence | Used for |", "|---|---|---|---|",
         "| Monilähteinen VMI (MS-NFI) forest maps 2009–2023, 16 m | Luonnonvarakeskus (Luke) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | site class, main type, age, volumes by species, basal area, canopy cover, height — app filters and model features |",
         "| Elevation model 10 m | Maanmittauslaitos (MML) | CC BY 4.0 | elevation, slope, aspect, TPI, relief — model features, and the app's own slope readout via `ml/export/export_terrain.py` |",
         "| Maaperä 1:200 000 (superficial deposits) and Glacigenic landforms | Geologian tutkimuskeskus (GTK) | CC BY 4.0 | soil class, esker / glaciofluvial formation — rasterized copies in `ml/data/rasters/gtk_*_16m.tif` |",
         "| Gridded daily/monthly climate 10 km (1961–) | Ilmatieteen laitos (FMI) | CC BY 4.0 | thermal sum and precipitation normals in `ml/data/climate/` |",
         "| Copernicus DEM GLO-90 via Open-Meteo | ESA / Open-Meteo | CC BY 4.0 | fallback slope readout, used only where `data/terrain/` has not been published |",
         "| Metsävarakuviot (forest stands) | Suomen metsäkeskus | CC BY 4.0 | development class and stand age — clear-cuts and seedling stands are removed from the app's masks, read live from the WFS |",
         "| Metsänkäyttöilmoitukset (forest use declarations) | Suomen metsäkeskus | CC BY 4.0 | declared regeneration fellings — reported on tap only, never used to remove anything |", "",
         "Attribution text used in the app and in derived files: "
         "*© Luonnonvarakeskus (Luke) MVMI, © Maanmittauslaitos, © Geologian tutkimuskeskus, "
         "© Ilmatieteen laitos, © Suomen metsäkeskus — CC BY 4.0.*", "",
         "## Occurrence records", ""]
    today = time.strftime("%Y-%m-%d")
    for key, taxa, obs in species:
        counts = collections.Counter(short_license(r.get("license")) for r in obs)
        used_for = ("training presences and the app's findings layer" if key == "matsutake"
                    else "the app's findings layer, and the measurements behind this species' filter")
        L += [f"### *{taxa['latin']}* — `ml/data/{key}/observations.csv`", "",
              f"{len(obs)} records in Finland, fetched from GBIF"
              + (" and the Finnish Biodiversity Information Facility (FinBIF, laji.fi)" if taxa["laji"] else "")
              + f" on {today}, used for {used_for}. Each row carries its own `license`. "
              "Licence mix: " + ", ".join(f"{k}: {v}" for k, v in counts.most_common()) + ".", ""]
        L += table(obs, "obs")
        cite = ("GBIF.org (" + today + ") GBIF Occurrence Search, *" + taxa["latin"] + "*, Finland, "
                f"https://www.gbif.org/occurrence/search?taxon_key={taxa['gbif']}&country=FI")
        if taxa["laji"]:
            cite += ("; and FinBIF: Suomen Lajitietokeskus / FinBIF (" + today + "), "
                     f"https://laji.fi/taxon/{taxa['laji']}")
        L += ["", "GBIF asks that data use is cited; these records came through the GBIF occurrence "
              "API (no download DOI). Cite as: " + cite + ".", ""]
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
          "| `ml/data/climate/*.tif`, `ml/data/rasters/gtk_*_16m.tif`, `ml/data/gtk_classes.json` | rasterized / aggregated copies of FMI and GTK data | CC BY 4.0 (© FMI, © GTK) |",
          "| `data/*/observations.json` | the occurrence records above, packaged for the app's findings layer | each record keeps the licence it carries in the table above |", "",
          "To publish the derived layers under plain CC BY 4.0, re-run the pipeline with the CC BY-NC "
          "records removed (`ml/ingest/fetch_observations.py` — filter on the `license` column).", "",
          "Software licences: see `LICENSE` (MIT) and `THIRD_PARTY_LICENSES.md`."]
    open(os.path.join(ROOT, "DATA_LICENSES.md"), "w").write("\n".join(L) + "\n")
    print("wrote DATA_LICENSES.md for", ", ".join(
        f"{k} ({len(rows)} records)" for k, _, rows in species))


if __name__ == "__main__":
    main()
