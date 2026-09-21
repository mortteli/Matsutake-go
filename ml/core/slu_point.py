"""Single-cell reads of the Swedish rasters, preserving what the nodata values do and do not
mean. The Swedish counterpart of mvmi_point.py.

THE ONE THING THIS CANNOT DO THAT THE FINNISH VERSION CAN
mvmi_point.py exists to keep two Luke nodata values apart: 32767 means "not forestry land",
which is a measurement, and 32766 means "cloud", which is an absence of one. That
distinction is what lets observation_status.py answer "this find is outside forestry land"
(a fine answer -- the record may be a garden or a roadside, and the map says so) separately
from "we do not know" (no answer at all).

SLU publishes a single nodata per raster -- 65535 for the uint16 themes, 128 for the uint8
height -- covering both cases at once. So OFF has no Swedish equivalent, `ulkopuolella` never
occurs in the Swedish classification, and a record on a churchyard lawn is reported as
`ei_tietoa` rather than as a deliberate outside-forest-land verdict. That is a real loss of
resolution, not a modelling choice, and observation_status_se.py's docstring says so where a
reader will meet it.

  UNKNOWN (-2)  the raster has no value here: not forest land, or not modelled. Indistinguishable.
  OUTSIDE (-1)  the point falls outside the raster's own extent entirely.
  >= 0          a real reading, in the theme's own units (years, m, m3/ha).
"""
import os

import numpy as np
import rasterio

OUTSIDE, UNKNOWN = -1, -2


def is_value(v):
    return v is not None and v >= 0


def normalise(v, nodata):
    return UNKNOWN if (nodata is not None and v == nodata) else int(v)


def _sample(path, points, scale=1):
    """Read one cell per point, in file order. Returns a list aligned with `points`."""
    if not os.path.exists(path):
        return [OUTSIDE] * len(points)
    with rasterio.open(path) as ds:
        nodata = ds.nodata
        # rasterio's sample() yields OUTSIDE-safe zeros for points off the edge, so the
        # bounds test is done here rather than trusted to the reader.
        L, B, R, T = ds.bounds
        inside = [(L <= x <= R and B <= y <= T) for x, y in points]
        vals = list(ds.sample([p for p, ok in zip(points, inside) if ok]))
        out, it = [], iter(vals)
        for ok in inside:
            out.append(normalise(next(it)[0], nodata) if ok else OUTSIDE)
    return out


def sample_theme(theme, vintage, points, slu_dir, to_rt90=None):
    """One SLU theme at `vintage`, sampled at WGS84-derived SWEREF99 TM points.

    The rasters are in RT90 (EPSG:3021), so the points are transformed rather than the
    rasters -- nine points per record is far cheaper to move than a 555 MB raster, and it
    avoids introducing a resampling step that features_se.py does not also apply.
    """
    from pyproj import Transformer
    from grid_se import rt90_path, assert_rt90_transform
    assert_rt90_transform()
    tr = to_rt90 or Transformer.from_crs("EPSG:3006", "EPSG:3021", always_xy=True)
    rt = [tr.transform(x, y) for x, y in points]
    return _sample(rt90_path(theme, vintage, slu_dir), rt)


def sample_cut(points, rasters_dir):
    """{'cut': [...], 'cut_year': [...]} from the Skogsstyrelsen felling rasters.

    cut is 0 none / 1 declared / 2 completed, taking the stronger of the two layers.
    cut_year is the completed felling's year (full, not year-2000) or 0 when undated --
    which is what lets the Swedish rule be "cut AFTER the find" rather than Finland's
    undated "cut at some point".
    """
    declared = os.path.join(rasters_dir, "cut_declared_12m5.tif")
    fact = os.path.join(rasters_dir, "cut_fact_12m5.tif")
    d = _sample(declared, points)
    f = _sample(fact, points)
    years = _sample_band(fact, points, band=2)
    cut, cut_year = [], []
    for dv, fv, yv in zip(d, f, years):
        if fv == 2:
            cut.append(2)
        elif dv == 1:
            cut.append(1)
        elif dv == OUTSIDE and fv == OUTSIDE:
            cut.append(OUTSIDE)
        else:
            cut.append(0)
        cut_year.append(yv + 2000 if yv and yv > 0 else 0)
    return {"cut": cut, "cut_year": cut_year}


def _sample_band(path, points, band):
    if not os.path.exists(path):
        return [0] * len(points)
    with rasterio.open(path) as ds:
        if ds.count < band:
            return [0] * len(points)
        L, B, R, T = ds.bounds
        inside = [(L <= x <= R and B <= y <= T) for x, y in points]
        vals = list(ds.sample([p for p, ok in zip(points, inside) if ok], indexes=[band]))
        out, it = [], iter(vals)
        for ok in inside:
            out.append(int(next(it)[0]) if ok else 0)
    return out
