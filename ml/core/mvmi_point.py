"""Reading single MVMI cells without losing what "no value" meant.

`features.py` runs every MVMI cell through `MVMI_MAX` and turns anything above the ceiling into
NaN. That is right for the model — a feature vector has no use for the difference between two
kinds of missing — but it is exactly the difference this module exists to preserve. Luke's own
LUETAMA file reserves two values, and they say opposite things:

    32766  a result should have been computed here but cloud cover prevented it   -> unknown
    32767  no result was computed: not forest, scrub or waste land in Finland     -> a fact

The second is not missing data. It is the map telling you the cell is a cemetery, a yard, a
field, a road or a lake, and for deciding whether a 1970 find still stands it is one of the more
informative values in the raster. The 2009 product also carries an undocumented 24580 alongside
the declared pair (see the note in features.py); it behaves like 32766 and is treated as such.

Nothing here decides anything. It returns raw integers plus three sentinels, and
ml/dataset/observation_status.py does the reasoning.

No common grid is built. Every cycle is EPSG:3067 and only the transform differs (2009-2011 on
a 20 m grid, 2013-2021 on 16 m with another origin), so a point is sampled by inverting each
raster's own transform — nearest neighbour by construction, the same choice `Sources` makes with
WarpedVRT, minus the warp and minus opening ten themes, a DEM, two climate rasters and the GTK
pair to read one cell.
"""
import json, os

import numpy as np
import rasterio
from rasterio.windows import Window

from grid import env, luke_url

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
ROOT = os.path.dirname(ML)

# Luke's reserved values, kept apart rather than collapsed (see the module docstring).
OFF_FORESTRY = 32767        # not forest / scrub / waste land: built, field, water, cemetery
CLOUDED = 32766             # a result was expected here and could not be computed
CLOUDED_2009 = 24580        # undocumented, 2009 product only, behaves like CLOUDED

# Our own, for cells that are not in the raster at all — off the edge, or outside a published
# part of the cut layer. Distinct from CLOUDED: the raster is not claiming anything either way.
OUTSIDE = -1
UNKNOWN = -2                # CLOUDED / CLOUDED_2009, normalised
OFF = -3                    # OFF_FORESTRY, normalised

_RESERVED = {OFF_FORESTRY: OFF, CLOUDED: UNKNOWN, CLOUDED_2009: UNKNOWN}


def normalise(v):
    """Raw raster integer -> a measurement, or one of UNKNOWN / OFF."""
    return _RESERVED.get(int(v), int(v))


def is_value(v):
    """True when v is an actual measurement rather than a sentinel."""
    return v >= 0


def _window_read(ds, rows, cols):
    """The cells at (rows, cols), read as one window rather than n point samples.

    A rosette spans at most ~1.4 km, which is ~90 cells at 16 m — one window covers all nine
    points and costs the COG tiles they share exactly once. Points off the raster come back as
    OUTSIDE; the read itself is clipped so an edge case never raises.
    """
    out = [OUTSIDE] * len(rows)
    inside = [i for i, (r, c) in enumerate(zip(rows, cols))
              if 0 <= r < ds.height and 0 <= c < ds.width]
    if not inside:
        return out
    r0, r1 = min(rows[i] for i in inside), max(rows[i] for i in inside) + 1
    c0, c1 = min(cols[i] for i in inside), max(cols[i] for i in inside) + 1
    a = ds.read(1, window=Window(c0, r0, c1 - c0, r1 - r0))       # raw: nodata NOT masked away
    for i in inside:
        out[i] = normalise(a[rows[i] - r0, cols[i] - c0])
    return out


class PointSampler:
    """Opens one raster and reads rosettes from it. Use as a context manager."""

    def __init__(self, path):
        self.path = path
        self.ds = rasterio.open(path)
        self._inv = ~self.ds.transform

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.ds.close()

    def rosette(self, pts):
        """pts: [(x, y), ...] in EPSG:3067 metres -> [int, ...] of the same length."""
        rows, cols = [], []
        for x, y in pts:
            col, row = self._inv * (x, y)
            rows.append(int(np.floor(row)))
            cols.append(int(np.floor(col)))
        return _window_read(self.ds, rows, cols)


def sample_theme(theme, cycle, rosettes):
    """One MVMI theme of one cycle at many rosettes.

    rosettes: {record_id: [(x, y) x 9]} -> {record_id: [int x 9]}. Records are visited north to
    south so consecutive reads land in the same COG tiles.
    """
    order = sorted(rosettes, key=lambda k: -rosettes[k][0][1])
    with env():
        with PointSampler(luke_url(theme, cycle)) as s:
            return {k: s.rosette(rosettes[k]) for k in order}


def cut_parts(species="matsutake"):
    """The published cut raster's parts and bounds, from the app's own metadata.

    Read from prob_meta.json rather than the filenames so the pipeline and js/rasterread.js are
    looking at one list. Returns [] when the layer has not been built for this species.
    """
    meta_path = os.path.join(ROOT, "data", species, "prob_meta.json")
    if not os.path.exists(meta_path):
        return []
    cut = json.load(open(meta_path)).get("cut") or {}
    return [(os.path.join(ROOT, f["url"]), f["bounds"]) for f in cut.get("files", [])]


def sample_cut(rosettes, species="matsutake"):
    """Metsakeskus harvest state at many rosettes: {record_id: [0|1|2|OUTSIDE x 9]}.

    0 no signal, 1 a regeneration felling was declared, 2 the stand register says the ground is
    open or seedling. The parts tile the country, so a rosette near a seam is read from every
    part it touches and the highest value wins — the same precedence fetch_harvests.py burns
    them with, where a fact outranks an intention and both outrank silence.
    """
    out = {k: [OUTSIDE] * len(v) for k, v in rosettes.items()}
    for path, (x0, y0, x1, y1) in cut_parts(species):
        if not os.path.exists(path):
            continue
        touching = {k: pts for k, pts in rosettes.items()
                    if any(x0 <= x < x1 and y0 <= y < y1 for x, y in pts)}
        if not touching:
            continue
        with PointSampler(path) as s:
            for k, pts in touching.items():
                for i, v in enumerate(s.rosette(pts)):
                    if v > out[k][i]:                 # OUTSIDE (-1) < 0 < 1 < 2
                        out[k][i] = v
    return out
