"""Describe the Swedish pilot raster for the static app.

The raster itself is already written — ml/export/predict.py produced it and it was cropped,
floored and converted to a COG under data/matsutake_se/ — so this only writes the metadata the
app reads: which file, in which grid, and the score quantiles that turn the slider's "best X %"
into a threshold.

    python ml/export/export_app_se.py [--src data/matsutake_se/prob_matsutake_se_pilot_12m5.tif]

`forest_quantiles` and `NQ` are imported from export_app.py rather than reimplemented, because
"the best X % of forestry land" has to mean the same thing on both sides of the border or the one
slider governing both regions is lying about one of them. It is measured the same way here: over
the values as they are *stored* in the published file, decimated, so the number the app thresholds
at is a percentile of the map the user is looking at and not of some other population.

The file keeps only the best 15 % — everything below that floor is stored as 0 — so the quantile
table is flat 0 up to its 85th percentile and only resolves scores above it. That is exactly the
shape export_app.py produces for Finland, and probThreshold() clamps to `floor` for the same
reason in both.
"""
import argparse, json, os, sys, time
import numpy as np, rasterio

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
ROOT = os.path.dirname(ML)
sys.path.insert(0, HERE)
from export_app import NQ, forest_quantiles                      # noqa: E402  (after sys.path)

REL = "data/matsutake_se/prob_matsutake_se_pilot_12m5.tif"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=REL, help="published COG, relative to the repo root")
    ap.add_argument("--max-pct", type=float, default=15,
                    help="share of forestry land the file covers; must match the floor it was written with")
    a = ap.parse_args()

    path = os.path.join(ROOT, a.src)
    outdir = os.path.dirname(path)
    meta = json.load(open(os.path.join(outdir, "prob_meta.json")))
    report = json.load(open(os.path.join(ML, "models", "matsutake_se", "report.json")))

    with rasterio.open(path) as src:
        v, quant = forest_quantiles(src)
        b = src.bounds
        assert src.crs.to_epsg() == 3006, f"expected SWEREF99 TM, got {src.crs}"
        floor = int(meta["floor"])
        kept = float((v >= floor).mean())
        log(f"{src.width}x{src.height} @ {src.res[0]} m, {v.size} forestry-land cells sampled, "
            f"{kept * 100:.1f} % of them at or above the stored floor {floor}")

    # Everything the app needs, beside what the pilot's own metadata already says. The notes are
    # kept: a reader of this file should still be told it is a pilot and that the metrics in it
    # are national and out-of-fold.
    meta.update(
        pixel_m=float(src.res[0]),
        value="model score x 100",
        max_pct=a.max_pct,
        step=1,
        quantiles=[round(float(q), 1) for q in quant],
        quantiles_note=f"score at each of {NQ} evenly spaced percentiles of the forestry-land cells "
                       "in this published file, measured the same way as the Finnish parts "
                       "(ml/export/export_app.py) so the app's 'best X %' means the same on both "
                       "sides of the border",
        files=[dict(url=a.src.replace(os.sep, "/"),
                    bounds=[round(b.left), round(b.bottom), round(b.right), round(b.top)])],
        attribution="Malli: Matsutake GO ml (GBIF/Artportalen · SLU · Naturvårdsverket · SGU · "
                    "Skogsstyrelsen · SMHI · Copernicus)",
        app_name="Ruotsin pilottialue (Västerbotten)",
        app_note="Ruotsista kartalla on vain 150 x 150 km:n pilottialue Västerbottenissa, "
                 "omalla mallillaan opetettuna — sen ulkopuolella Ruotsi on kartoittamatta, ei huono.",
        n_presence=report.get("n_presence"),
    )
    json.dump(meta, open(os.path.join(outdir, "prob_meta.json"), "w"), indent=1)
    log(f"wrote {outdir}/prob_meta.json: 1 file, {os.path.getsize(path) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
