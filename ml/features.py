"""Feature computation shared by training (small windows around points) and inference
(large blocks). Everything is computed on the MVMI 16 m grid from float32 arrays with
NaN for missing data, so a training pixel and an inference pixel see exactly the same
numbers.

Sources
  MVMI themes (Luke)         local GeoTIFF if downloaded, else remote range reads
  DEM 10 m (MML)             remote VRT, warped/bilinear to the 16 m grid
  GTK soil + glacigenic      local rasters made by fetch_gtk.py
  FMI climate normals        ml/data/climate/*.tif warped to the grid (bilinear)
"""
import json, os
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from scipy.ndimage import uniform_filter, maximum_filter, minimum_filter

from grid import Grid, env, luke_url, DEM_VRT

HERE = os.path.dirname(os.path.abspath(__file__))
RASTERS = os.path.join(HERE, "data", "rasters")
CLIMATE = os.path.join(HERE, "data", "climate")

MVMI_THEMES = ["kasvupaikka", "paatyyppi", "ika", "manty", "kuusi", "koivu", "tilavuus",
               "ppa", "latvuspeitto", "keskipituus"]
MARGIN = 16                     # cells; largest neighbourhood is 31 (radius 15)

SOIL_GROUPS = ["coarse", "till", "fine", "rock", "peat", "other"]
GLAC_GROUPS = ["glaciofluvial", "littoral", "moraine", "other"]


def soil_group(name):
    n = (name or "").lower()
    if any(k in n for k in ("karkearakeinen", "hiekka", "sora", "kivikko", "lohkare")):
        return "coarse"
    if "hieno hieta" in n or any(k in n for k in ("savi", "hiesu", "lieju", "hienojakoinen", "hienorakeinen")):
        return "fine"
    if "hieta" in n:
        return "coarse"
    if any(k in n for k in ("sekalajitteinen", "moreeni")):
        return "till"
    if any(k in n for k in ("kallio", "rakka", "kivi")):
        return "rock"
    if any(k in n for k in ("turve", "soistuma", "rahka", "sara")):
        return "peat"
    return "other"


def glac_group(name):
    n = (name or "").lower()
    if "moraine" in n or "morainic" in n or "diamicton" in n:
        return "moraine"
    if "littoral" in n or "beach" in n or "aeolian" in n or "dune" in n:
        return "littoral"
    if any(k in n for k in ("esker", "glaciofluvial", "extramarginal", "ice-contact", "ice contact", "delta", "sandur")):
        return "glaciofluvial"
    return "other"


def class_lookup(kind):
    """index (uint8 raster value) -> group index, from ml/data/gtk_classes.json"""
    groups = SOIL_GROUPS if kind == "soil" else GLAC_GROUPS
    fn = soil_group if kind == "soil" else glac_group
    lut = np.full(256, groups.index("other"), dtype=np.int16)
    lut[0] = -1                                              # no polygon
    path = os.path.join(HERE, "data", "gtk_classes.json")
    if os.path.exists(path):
        for idx, rec in json.load(open(path)).get(kind, {}).items():
            lut[int(idx)] = groups.index(fn(rec["name"]))
    return lut


# ----------------------------------------------------------------------------- feature list
CONT = ["ika", "manty", "kuusi", "koivu", "tilavuus", "ppa", "latvuspeitto", "keskipituus"]
NEIGH = ["ika", "manty", "kuusi", "latvuspeitto", "ppa"]

FEATURES = (
    CONT
    + ["pine_share", "spruce_share", "decid_share", "stem_density"]
    + [f"site_{k}" for k in range(1, 9)] + ["site_missing"]
    + [f"main_{k}" for k in range(1, 5)]
    + [f"{v}_m3" for v in NEIGH] + [f"{v}_m9" for v in NEIGH]
    + ["dry_site_frac9", "pine_max9", "spruce_min9"]
    + ["elev", "slope", "northness", "eastness", "tpi7", "tpi31", "relief7"]
    + [f"soil_{g}" for g in SOIL_GROUPS] + ["soil_none", "coarse_frac9", "coarse_frac31"]
    + [f"glac_{g}" for g in GLAC_GROUPS] + ["glac_none", "glacfl_frac31"]
    + ["thermal_sum", "precip"]
)


def _nanmean_filter(a, size):
    v = np.isfinite(a).astype(np.float32)
    s = uniform_filter(np.where(v > 0, a, 0).astype(np.float32), size, mode="nearest")
    c = uniform_filter(v, size, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / c, np.nan)


def block_features(src, margin=MARGIN):
    """src: dict of float32 arrays (NaN = nodata) on the same (H+2m, W+2m) window.
    Returns (features [n, H, W] float32, valid [H, W] bool)."""
    m = margin
    crop = (slice(m, -m if m else None), slice(m, -m if m else None))
    out = {}
    site, main = src["kasvupaikka"], src["paatyyppi"]
    for k in CONT:
        out[k] = src[k]
    vol = np.where(np.isfinite(src["tilavuus"]), src["tilavuus"], 0) + 1.0
    out["pine_share"] = src["manty"] / vol
    out["spruce_share"] = src["kuusi"] / vol
    out["decid_share"] = src["koivu"] / vol
    out["stem_density"] = src["ppa"] / (np.maximum(src["keskipituus"], 10.0) / 10.0)  # basal area per metre of height
    for k in range(1, 9):
        out[f"site_{k}"] = (site == k).astype(np.float32)
    out["site_missing"] = (~np.isfinite(site)).astype(np.float32)
    for k in range(1, 5):
        out[f"main_{k}"] = (main == k).astype(np.float32)
    for v in NEIGH:
        out[f"{v}_m3"] = _nanmean_filter(src[v], 3)
        out[f"{v}_m9"] = _nanmean_filter(src[v], 9)
    out["dry_site_frac9"] = uniform_filter(np.isin(site, [4, 5, 6, 7]).astype(np.float32), 9, mode="nearest")
    out["pine_max9"] = maximum_filter(np.where(np.isfinite(src["manty"]), src["manty"], 0), 9, mode="nearest")
    out["spruce_min9"] = minimum_filter(np.where(np.isfinite(src["kuusi"]), src["kuusi"], 999), 9, mode="nearest")
    z = src["elev"]
    zf = np.where(np.isfinite(z), z, np.nanmean(z) if np.isfinite(z).any() else 0.0)
    gy, gx = np.gradient(zf, 16.0)
    out["elev"] = z
    out["slope"] = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    asp = np.arctan2(-gx, gy)                                    # downslope direction, 0 = north
    out["northness"] = np.cos(asp).astype(np.float32)
    out["eastness"] = np.sin(asp).astype(np.float32)
    out["tpi7"] = zf - uniform_filter(zf, 7, mode="nearest")
    out["tpi31"] = zf - uniform_filter(zf, 31, mode="nearest")
    out["relief7"] = maximum_filter(zf, 7, mode="nearest") - minimum_filter(zf, 7, mode="nearest")
    sg = src["soil_group"]                                        # int group index, -1 none
    for i, g in enumerate(SOIL_GROUPS):
        out[f"soil_{g}"] = (sg == i).astype(np.float32)
    out["soil_none"] = (sg < 0).astype(np.float32)
    coarse = (sg == SOIL_GROUPS.index("coarse")).astype(np.float32)
    out["coarse_frac9"] = uniform_filter(coarse, 9, mode="nearest")
    out["coarse_frac31"] = uniform_filter(coarse, 31, mode="nearest")
    gg = src["glac_group"]
    for i, g in enumerate(GLAC_GROUPS):
        out[f"glac_{g}"] = (gg == i).astype(np.float32)
    out["glac_none"] = (gg < 0).astype(np.float32)
    out["glacfl_frac31"] = uniform_filter((gg == 0).astype(np.float32), 31, mode="nearest")
    out["thermal_sum"] = src["thermal_sum"]
    out["precip"] = src["precip"]
    feats = np.stack([out[k][crop].astype(np.float32) for k in FEATURES])
    valid = np.isfinite(site[crop]) & np.isfinite(src["ika"][crop])
    return feats, valid


class Sources:
    """Opens every input once for a given MVMI cycle; reads any window as float32/NaN."""

    def __init__(self, grid: Grid, cycle=2023, local_dir=os.path.join(RASTERS, "mvmi2023"), require_soil=True):
        self.grid = grid
        self.cycle = cycle
        self._env = env(); self._env.__enter__()
        warp = dict(crs=grid.crs, transform=grid.transform, width=grid.width, height=grid.height,
                    resampling=Resampling.bilinear)
        # Older cycles sit on other grids (2009–2011: 20 m, origin 61600/7776700; 2013–2021: 16 m,
        # origin 61600/7778304), so they are warped (nearest) onto the 2023 grid before reading.
        self.mvmi, self._mvmi_raw = {}, []
        for t in MVMI_THEMES:
            local = os.path.join(local_dir, f"{t}_vmi1x_1923.tif")
            path = local if (cycle == 2023 and os.path.exists(local + ".ok")) else luke_url(t, cycle)
            ds = rasterio.open(path)
            if cycle == 2023:
                self.mvmi[t] = ds
            else:
                self._mvmi_raw.append(ds)
                self.mvmi[t] = WarpedVRT(ds, **dict(warp, resampling=Resampling.nearest, nodata=ds.nodata))
        self._dem = rasterio.open(DEM_VRT)
        self.dem = WarpedVRT(self._dem, **warp)
        self._clim = {k: rasterio.open(os.path.join(CLIMATE, f)) for k, f in
                      (("thermal_sum", "thermal_sum_dd.tif"), ("precip", "precip_annual_mm.tif"))}
        self.clim = {k: WarpedVRT(d, **warp) for k, d in self._clim.items()}
        soil_path, glac_path = os.path.join(RASTERS, "gtk_soil_16m.tif"), os.path.join(RASTERS, "gtk_glac_16m.tif")
        if require_soil or (os.path.exists(soil_path) and os.path.exists(glac_path)):
            self.soil, self.glac = rasterio.open(soil_path), rasterio.open(glac_path)
        else:                                   # testing without GTK: every cell "no polygon"
            self.soil = self.glac = None
        self.soil_lut, self.glac_lut = class_lookup("soil"), class_lookup("glac")

    @staticmethod
    def _read(ds, window, nodata=None):
        """Window read that also works past the raster edge (WarpedVRT forbids boundless
        reads): read the overlapping part and pad with NaN."""
        r0, c0 = int(window.row_off), int(window.col_off)
        h, w = int(window.height), int(window.width)
        rr0, cc0 = max(r0, 0), max(c0, 0)
        rr1, cc1 = min(r0 + h, ds.height), min(c0 + w, ds.width)
        out = np.full((h, w), np.nan, dtype=np.float32)
        if rr1 > rr0 and cc1 > cc0:
            a = ds.read(1, window=Window(cc0, rr0, cc1 - cc0, rr1 - rr0)).astype(np.float32)
            nd = ds.nodata if nodata is None else nodata
            if nd is not None:
                a[a == nd] = np.nan
            out[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = a
        return out

    @staticmethod
    def _read_int(ds, window, shape):
        if ds is None:
            return np.zeros(shape, np.uint8)
        r0, c0 = int(window.row_off), int(window.col_off)
        h, w = shape
        rr0, cc0 = max(r0, 0), max(c0, 0)
        rr1, cc1 = min(r0 + h, ds.height), min(c0 + w, ds.width)
        out = np.zeros((h, w), np.uint8)
        if rr1 > rr0 and cc1 > cc0:
            out[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = ds.read(1, window=Window(cc0, rr0, cc1 - cc0, rr1 - rr0))
        return out

    def read(self, window: Window):
        src = {}
        for t, ds in self.mvmi.items():
            a = self._read(ds, window)
            a[a > 60000] = np.nan                       # 32767/65535 style nodata in older cycles
            src[t] = a
        z = self._read(self.dem, window)
        z[z < -1000] = np.nan
        src["elev"] = z
        for k, ds in self.clim.items():
            src[k] = self._read(ds, window)
        shape = (int(window.height), int(window.width))
        src["soil_group"] = self.soil_lut[self._read_int(self.soil, window, shape)].astype(np.float32)
        src["glac_group"] = self.glac_lut[self._read_int(self.glac, window, shape)].astype(np.float32)
        return src

    def features(self, window: Window, margin=MARGIN):
        w = Window(window.col_off - margin, window.row_off - margin,
                   window.width + 2 * margin, window.height + 2 * margin)
        return block_features(self.read(w), margin)

    def point_features(self, row, col, half=8):
        """Feature vector of one cell, computed from a (2*half+1)² window so that all
        neighbourhood features are exactly as in block inference."""
        w = Window(col - half, row - half, 2 * half + 1, 2 * half + 1)
        feats, valid = self.features(w)
        return feats[:, half, half], bool(valid[half, half])

    def close(self):
        for ds in list(self.mvmi.values()) + self._mvmi_raw + [self.dem, self._dem, self.soil, self.glac] + \
                  list(self.clim.values()) + list(self._clim.values()):
            try: ds.close()
            except Exception: pass
        self._env.__exit__(None, None, None)
