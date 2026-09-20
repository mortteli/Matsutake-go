"""Swedish feature computation, shared by training (small windows around points) and
inference (large blocks). Mirrors features.py: everything is computed on the 12.5 m
SWEREF99 TM grid from float32 arrays with NaN for missing data, so a training pixel and an
inference pixel see exactly the same numbers.

Sources
  SLU forest map 2010 (25 m, EPSG:3021)   local GeoTIFFs from download_slu_forestmap.sh
  Copernicus DEM GLO-30                   ml/data/rasters_se/dem_25m.tif (build_dem_se.py)
  SGU jordarter, two scales               ml/data/rasters_se/sgu_*.tif (fetch_sgu.py)
  Naturvardsverket NMD 2023 (10 m)        ml/data/rasters_se/nmd/*.tif (fetch_nmd.py)
  SMHI PTHBV normals                      ml/data/climate_se/*.tif (fetch_smhi_climate.py)

HOW THIS DIFFERS FROM FINLAND, AND WHY
--------------------------------------
Of Finland's 63 features, most have a Swedish counterpart, a few become engineered proxies,
and a handful do not exist. The three that mattered when the Swedish sources were audited:

  latvuspeitto (canopy cover)  SOLVED. NMD's objekttackning for the 5-45 m height band is
      coverage in percent, binned 5/10/20/.../100, at 10 m, 2023 -- a fresher vintage than
      the Finnish layer. The 0.5-5 m band gives an understory cover that Finland has no
      equivalent for at all, so it is added rather than mirrored.

  paatyyppi (mineral / spruce mire / pine mire / open mire)  SOLVED, and more cleanly than
      expected. NMD's basskikt codes main type and dominant species in one value: 111-118
      forest on fastmark, 121-128 forest on vatmark, 200-224 open mire. 121 "tallskog pa
      vatmark" is rame and 122 "granskog pa vatmark" is korpi, almost exactly. 118
      "temporart ej skog pa fastmark" is a bonus: a 2023 clear-cut signal that owes nothing
      to Skogsstyrelsen's felling layers.

  kasvupaikka (8-step site fertility)  STILL MISSING, and it will stay missing. Sweden does
      classify site fertility -- standortsbonitering derives standortsindex from soil
      moisture, texture, depth and vegetationstyp, and vegetationstyp is a genuine nutrient
      ladder (lavtyp -> ristyp -> grastyp -> orttyp) that would map onto kasvupaikka almost
      one for one. But it is recorded per plot by Riksskogstaxeringen, which withholds exact
      plot coordinates, so neither the layer nor the training data to reproduce it is open.
      NMD's "skoglig produktivitet" is often mistaken for a substitute; it has three classes
      (ej skogsmark / produktiv / improduktiv), so it is a land-class hint, not a ladder. It
      is still worth carrying, because improduktiv skogsmark in northern Sweden is largely
      hallmark, lavhed and thin-soil pine, which is matsutake ground. The fertility axis
      here is therefore engineered from soil texture, cover and the mire grading, and the
      model report should not imply parity with Finland on this point.

Also absent: keskilapimitta (mean diameter) nationally, so stems_ha cannot be computed the
way features.py computes it, and relief7 -- see the DSM note on the terrain block below.

NEIGHBOURHOOD SIZES ARE IN METRES, NOT CELLS
    Finland's 3/9/31-cell filters on a 16 m grid are 48/144/496 m. Reusing those cell counts
    on a 12.5 m grid would silently shrink every neighbourhood by 22 %, and worse, the
    source here is 25 m, so a 3-cell filter would span 1.5 source cells and do nothing at
    all. The sizes below are chosen to match Finland's footprints in metres, and the feature
    names say metres so the trap is not re-laid.
"""
import json, os
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window
from scipy.ndimage import uniform_filter, maximum_filter, minimum_filter

from grid_se import GridSE, RT90_2010, RT90_2005, assert_rt90_transform, env, rt90_path

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
RASTERS = os.path.join(ML, "data", "rasters_se")
SLU_DIR = os.path.join(RASTERS, "slu_forest_map")
NMD_DIR = os.path.join(RASTERS, "nmd")
CLIMATE = os.path.join(ML, "data", "climate_se")

SLU_THEMES = list(RT90_2010)                 # age, height, vol_total, vol_pine, ...
# Physically possible maximum per theme. The 2010 rasters declare 65535 as nodata except
# HEIGHT, which is uint8 with nodata 128; anything above these ceilings is treated as
# missing rather than trusted, the same discipline MVMI_MAX applies in features.py.
SLU_MAX = {"age": 400, "height": 60, "vol_total": 2000, "vol_pine": 2000, "vol_spruce": 2000,
           "vol_birch": 1000, "vol_decid": 1000, "vol_contorta": 800}

# 62.5 m / 162.5 m / 512.5 m, against Finland's 48 / 144 / 496 m.
N_SMALL, N_MID, N_BIG = 5, 13, 41
MARGIN_SE = 24                               # cells; largest neighbourhood is 41 (radius 20)

SOIL_GROUPS = ["coarse", "till", "fine", "rock", "peat", "other"]
PARENT_GROUPS = ["glaciofluvial", "littoral", "moraine", "other"]


# ------------------------------------------------------------------ SGU class grouping
def soil_group(name):
    """SGU jordart name -> one of SOIL_GROUPS, mirroring features.py's soil_group().

    Order matters. Swedish till names compound freely with their texture ("Sandig moran",
    "Moranlera"), so moran has to be tested before sand and before lera, or half the till in
    the country would be filed as coarse or fine. Finland has the same hazard and solves it
    the same way.
    """
    n = (name or "").lower()
    if "torv" in n:
        return "peat"
    if "berg" in n or "vittringsjord" in n:
        return "rock"
    if "morän" in n or "moran" in n:                        # incl. Moränlera, Sandig morän
        return "till"
    if "glaciär" in n or "vatten" in n or "oklassad" in n:
        return "other"
    if "lera" in n or "silt" in n and "finsand" not in n:
        return "fine"
    # "Postglacial grovsilt-finsand" spans 0.02-0.2 mm, which is what Finland calls hieta
    # and files as coarse; kept consistent with that rather than with the name's leading word.
    if any(k in n for k in ("sand", "grus", "block", "isälvs", "isalvs", "svall", "flygsand")):
        return "coarse"
    if "svämsediment" in n or "älvsediment" in n:
        return "fine"
    return "other"


def parent_group(name):
    """SGU grundlager name -> one of PARENT_GROUPS, mirroring features.py's glac_group().

    Finland reads genesis from a separate GTK glacigenic theme; Sweden gets it from the
    coarse (1:1M) grundlager layer, which is a different product from the fine ytlager used
    for texture. Keeping the two blocks on different source products is deliberate: it is
    what makes train.py's soil ablation measure something rather than re-measuring one layer
    twice.
    """
    n = (name or "").lower()
    if "isälvs" in n or "isalvs" in n:
        return "glaciofluvial"
    if "svall" in n or "flygsand" in n:
        return "littoral"
    if "morän" in n or "moran" in n:
        return "moraine"
    return "other"


def class_lookup(layer, groups, fn):
    """uint8 raster value -> group index, from ml/data/sgu_classes.json (-1 = no polygon)."""
    lut = np.full(256, groups.index("other"), dtype=np.int16)
    lut[0] = -1
    path = os.path.join(ML, "data", "sgu_classes.json")
    if os.path.exists(path):
        for idx, rec in json.load(open(path)).get(layer, {}).items():
            lut[int(idx)] = groups.index(fn(rec["name"]))
    return lut


# ------------------------------------------------------------------ NMD basskikt grouping
# 111-118 forest on fastmark (mineral), 121-128 forest on vatmark (peat), 200-224 open mire,
# 23/43 low mountain forest, 3/51-54/61/62 farmland, built and water.
NMD_MINERAL = set(range(111, 119)) | {43}
NMD_PEAT_FOREST = set(range(121, 129)) | {23}
NMD_OPEN_MIRE = {200} | set(range(211, 219)) | set(range(221, 225))
NMD_CLEARCUT = {118, 128}                    # "temporart ej skog" -- a 2023 felling signal
NMD_MIRE_RICH = {214, 224}                   # fastmattemyr / grasdominerad, frodig
NMD_MIRE_POOR = {212, 213, 223}              # ristuvemyr, fastmattemyr mager, mager gras
NMD_NONFOREST = {0, 3, 51, 52, 53, 54, 61, 62}


def _nmd_lut(values):
    lut = np.zeros(256, dtype=np.float32)
    for v in values:
        if v < 256:
            lut[v] = 1.0
    return lut


NMD_LUTS = {
    "main_mineral": _nmd_lut(NMD_MINERAL),
    "main_peat_forest": _nmd_lut(NMD_PEAT_FOREST),
    "main_open_mire": _nmd_lut(NMD_OPEN_MIRE),
    "main_clearcut": _nmd_lut(NMD_CLEARCUT),
    "mire_rich": _nmd_lut(NMD_MIRE_RICH),
    "mire_poor": _nmd_lut(NMD_MIRE_POOR),
    "nonforest": _nmd_lut(NMD_NONFOREST),
}


# ------------------------------------------------------------------------- feature list
CONT = SLU_THEMES + ["cover", "understory", "ba_est", "vol_per_height"]
NEIGH = ["age", "vol_pine", "vol_spruce", "vol_total", "cover", "ba_est"]

FEATURES_SE = (
    CONT                                                                        # 12
    + ["pine_share", "spruce_share", "birch_share", "decid_share",
       "contorta_share", "conifer_share"]                                       # 6
    + [f"{v}_m60" for v in NEIGH] + [f"{v}_m160" for v in NEIGH]                # 12
    + ["pine_max160", "spruce_min160", "age_max160", "open_frac160"]            # 4
    + ["main_mineral", "main_peat_forest", "main_open_mire", "main_clearcut",
       "mire_rich", "mire_poor", "main_missing"]                                # 7
    + ["productive", "improductive", "prod_missing"]                            # 3
    + ["elev", "slope", "northness", "eastness", "tpi160", "tpi500"]            # 6
    + [f"soil_{g}" for g in SOIL_GROUPS] + ["soil_none", "coarse_frac160",
       "coarse_frac500", "rock_frac160", "peat_frac160"]                        # 11
    + [f"parent_{g}" for g in PARENT_GROUPS] + ["parent_none", "glacfl_frac500"]  # 6
    + ["thermal_sum", "precip"]                                                 # 2
)                                                                               # = 69


def _nanmean_filter(a, size):
    v = np.isfinite(a).astype(np.float32)
    s = uniform_filter(np.where(v > 0, a, 0).astype(np.float32), size, mode="nearest")
    c = uniform_filter(v, size, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / c, np.nan)


def block_features(src, margin=MARGIN_SE):
    """src: dict of float32 arrays (NaN = nodata) on the same (H+2m, W+2m) window.
    Returns (features [n, H, W] float32, valid [H, W] bool)."""
    m = margin
    crop = (slice(m, -m if m else None), slice(m, -m if m else None))
    out = {}
    for k in CONT:
        if k in src:
            out[k] = src[k]

    vol = np.where(np.isfinite(src["vol_total"]), src["vol_total"], 0) + 1.0
    out["pine_share"] = src["vol_pine"] / vol
    out["spruce_share"] = src["vol_spruce"] / vol
    out["birch_share"] = src["vol_birch"] / vol
    out["decid_share"] = (src["vol_birch"] + src["vol_decid"]) / vol
    # Lodgepole reads as "pine" in any aggregate pine layer and is ecologically wrong for
    # matsutake. Nationally it is only ~1 m3/ha, but it is concentrated in northern Sweden,
    # which is exactly where the observations are.
    out["contorta_share"] = src["vol_contorta"] / vol
    out["conifer_share"] = (src["vol_pine"] + src["vol_spruce"]) / vol

    # Finland's ppa comes straight from MVMI. Sweden's 2010 set has no basal area, so it is
    # reconstructed from the form-factor identity V = G * H * F with F ~ 0.47 for Scots pine.
    # check_ba_est.py regresses this against the real 2015 BA_leaf raster where that exists;
    # if the fit is poor the feature should be dropped rather than shipped as a fiction.
    h = np.maximum(src["height"], 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["ba_est"] = src["vol_total"] / (0.47 * h)
        # Not stem density: that needs a mean diameter Sweden does not publish nationally.
        # This is dimensionally basal-area-like and needs no invented constant.
        out["vol_per_height"] = src["vol_total"] / h

    # Two of the NEIGH themes are derived rather than read -- ba_est is reconstructed above,
    # and cover comes from NMD under its own name -- so the neighbourhoods are taken over
    # src plus what has been computed so far, not over src alone.
    pool = dict(src, **out)
    for v in NEIGH:
        out[f"{v}_m60"] = _nanmean_filter(pool[v], N_SMALL)
        out[f"{v}_m160"] = _nanmean_filter(pool[v], N_MID)
    out["pine_max160"] = maximum_filter(
        np.where(np.isfinite(src["vol_pine"]), src["vol_pine"], 0), N_MID, mode="nearest")
    out["spruce_min160"] = minimum_filter(
        np.where(np.isfinite(src["vol_spruce"]), src["vol_spruce"], 999), N_MID, mode="nearest")
    out["age_max160"] = maximum_filter(
        np.where(np.isfinite(src["age"]), src["age"], 0), N_MID, mode="nearest")
    # Finland's dry_site_frac9 counts dry kasvupaikka classes in a neighbourhood. With no
    # fertility ladder the nearest honest equivalent is how much of the surroundings carries
    # almost no standing volume -- open, poor ground.
    out["open_frac160"] = uniform_filter(
        (np.where(np.isfinite(src["vol_total"]), src["vol_total"], 0) < 50).astype(np.float32),
        N_MID, mode="nearest")

    base = src["nmd_base"]
    for k in ("main_mineral", "main_peat_forest", "main_open_mire", "main_clearcut",
              "mire_rich", "mire_poor"):
        out[k] = src[k]
    out["main_missing"] = (~np.isfinite(base) | (base == 0)).astype(np.float32)

    prod = src["nmd_prod"]
    out["productive"] = (prod == 1).astype(np.float32)
    out["improductive"] = (prod == 2).astype(np.float32)
    out["prod_missing"] = (~np.isfinite(prod)).astype(np.float32)

    # Terrain. Copernicus GLO-30 is a SURFACE model: over 25 m forest it sits between canopy
    # and ground, and the offset tracks the very stand structure the model is predicting. So
    # the surface is smoothed to ~110 m before differencing, and Finland's short-range
    # relief7 is dropped entirely -- max-minus-min over a few cells would light up on
    # clear-cut edges and canopy breaks, which correlate with the felling layer and with
    # vol_total. That is a leak dressed as terrain.
    z = src["elev"]
    zf = np.where(np.isfinite(z), z, np.nanmean(z) if np.isfinite(z).any() else 0.0)
    zs = uniform_filter(zf, 9, mode="nearest")
    gy, gx = np.gradient(zs, 12.5)
    out["elev"] = z
    out["slope"] = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    asp = np.arctan2(-gx, gy)                                # downslope direction, 0 = north
    out["northness"] = np.cos(asp).astype(np.float32)
    out["eastness"] = np.sin(asp).astype(np.float32)
    out["tpi160"] = zf - uniform_filter(zf, N_MID, mode="nearest")
    out["tpi500"] = zf - uniform_filter(zf, N_BIG, mode="nearest")

    sg = src["soil_group"]
    for i, g in enumerate(SOIL_GROUPS):
        out[f"soil_{g}"] = (sg == i).astype(np.float32)
    out["soil_none"] = (sg < 0).astype(np.float32)
    coarse = (sg == SOIL_GROUPS.index("coarse")).astype(np.float32)
    out["coarse_frac160"] = uniform_filter(coarse, N_MID, mode="nearest")
    out["coarse_frac500"] = uniform_filter(coarse, N_BIG, mode="nearest")
    out["rock_frac160"] = uniform_filter(
        (sg == SOIL_GROUPS.index("rock")).astype(np.float32), N_MID, mode="nearest")
    out["peat_frac160"] = uniform_filter(
        (sg == SOIL_GROUPS.index("peat")).astype(np.float32), N_MID, mode="nearest")

    pg = src["parent_group"]
    for i, g in enumerate(PARENT_GROUPS):
        out[f"parent_{g}"] = (pg == i).astype(np.float32)
    out["parent_none"] = (pg < 0).astype(np.float32)
    out["glacfl_frac500"] = uniform_filter((pg == 0).astype(np.float32), N_BIG, mode="nearest")

    out["thermal_sum"] = src["thermal_sum"]
    out["precip"] = src["precip"]

    # One preallocated array: stacking 69 cropped copies doubles peak memory, which matters
    # more here than in Finland because the grid is 27 % taller.
    h_, w_ = out[FEATURES_SE[0]][crop].shape
    feats = np.empty((len(FEATURES_SE), h_, w_), dtype=np.float32)
    for i, k in enumerate(FEATURES_SE):
        feats[i] = out[k][crop]
    # Finland tests kasvupaikka & ika. Sweden has no kasvupaikka, so forestry land is where
    # the SLU 2010 model produced a volume and an age at all.
    valid = np.isfinite(src["vol_total"][crop]) & np.isfinite(src["age"][crop])
    return feats, valid


class SourcesSE:
    """Opens every Swedish input once; reads any window as float32/NaN on the 12.5 m grid."""

    def __init__(self, grid: GridSE = None, vintage=2010, slu_dir=SLU_DIR, require_soil=True):
        assert_rt90_transform()              # a null datum shift would displace every read
        self.grid = grid or GridSE()
        self.vintage = vintage
        self._env = env(); self._env.__enter__()
        g = self.grid
        warp = dict(crs=g.crs, transform=g.transform, width=g.width, height=g.height)

        # SLU 2010/2005 are 25 m in EPSG:3021 and need both a reprojection and a datum shift.
        # Nearest, matching features.py's choice for cross-grid MVMI cycles: these are k-NN
        # estimates, and bilinear across a stand boundary manufactures values no plot holds.
        self.slu, self._slu_raw = {}, []
        table = RT90_2010 if vintage == 2010 else RT90_2005
        for t in table:
            ds = rasterio.open(rt90_path(t, vintage, slu_dir))
            self._slu_raw.append(ds)
            self.slu[t] = WarpedVRT(ds, **warp, resampling=Resampling.nearest,
                                    src_nodata=ds.nodata, nodata=ds.nodata)

        dem = os.path.join(RASTERS, "dem_25m.tif")
        self._dem = rasterio.open(dem) if os.path.exists(dem + ".ok") else None
        self.dem = WarpedVRT(self._dem, **warp, resampling=Resampling.bilinear) if self._dem else None
        self.dem_scale = 0.1                                  # stored as decimetres

        self._nmd, self.nmd = {}, {}
        for key, fn in (("base", "basskikt.tif"), ("prod", "produktivitet.tif"),
                        ("cover", "cover_5_45m.tif"), ("understory", "cover_05_5m.tif")):
            p = os.path.join(NMD_DIR, fn)
            if os.path.exists(p + ".ok"):
                ds = rasterio.open(p)
                self._nmd[key] = ds
                self.nmd[key] = WarpedVRT(ds, **warp, resampling=Resampling.nearest,
                                          src_nodata=ds.nodata, nodata=ds.nodata)

        self._clim, self.clim = {}, {}
        for k, fn in (("thermal_sum", "thermal_sum_dd.tif"), ("precip", "precip_annual_mm.tif")):
            p = os.path.join(CLIMATE, fn)
            if os.path.exists(p):
                ds = rasterio.open(p)
                self._clim[k] = ds
                self.clim[k] = WarpedVRT(ds, **warp, resampling=Resampling.bilinear)

        soil_p = os.path.join(RASTERS, "sgu_ytlager_25k_12m5.tif")
        parent_p = os.path.join(RASTERS, "sgu_grundlager_1m_12m5.tif")
        have = os.path.exists(soil_p) and os.path.exists(parent_p)
        if require_soil and not have:
            raise FileNotFoundError(
                f"missing SGU rasters; run fetch_sgu.py all --coarse and fetch_sgu.py all\n"
                f"  {soil_p}\n  {parent_p}")
        self.soil = rasterio.open(soil_p) if os.path.exists(soil_p) else None
        self.parent = rasterio.open(parent_p) if os.path.exists(parent_p) else None
        self.soil_lut = class_lookup("ytlager_25k", SOIL_GROUPS, soil_group)
        self.parent_lut = class_lookup("grundlager_1m", PARENT_GROUPS, parent_group)

    # _read and _read_int are features.py's verbatim: the boundless-read padding they
    # implement (WarpedVRT forbids reads past the edge) is exactly as necessary here, and
    # diverging on them would be a silent source of edge bugs.
    @staticmethod
    def _read(ds, window, nodata=None):
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
            out[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0] = ds.read(
                1, window=Window(cc0, rr0, cc1 - cc0, rr1 - rr0))
        return out

    def read(self, window: Window):
        shape = (int(window.height), int(window.width))
        src = {}
        for t, ds in self.slu.items():
            a = self._read(ds, window)
            a[(a > SLU_MAX[t]) | (a < 0)] = np.nan
            src[t] = a
        for t in SLU_THEMES:                                  # 2005 carries only two themes
            src.setdefault(t, np.full(shape, np.nan, np.float32))

        if self.dem is not None:
            z = self._read(self.dem, window) * self.dem_scale
            z[z < -100] = np.nan
        else:
            z = np.full(shape, np.nan, np.float32)
        src["elev"] = z

        for key in ("cover", "understory"):
            if key in self.nmd:
                a = self._read(self.nmd[key], window)
                a[(a < 0) | (a > 100)] = np.nan
            else:
                a = np.full(shape, np.nan, np.float32)
            src[key] = a

        base = self._read(self.nmd["base"], window) if "base" in self.nmd else np.full(shape, np.nan, np.float32)
        src["nmd_base"] = base
        idx = np.where(np.isfinite(base), base, 0).astype(np.int32).clip(0, 255)
        for k, lut in NMD_LUTS.items():
            if k != "nonforest":
                src[k] = lut[idx]
        src["nmd_prod"] = (self._read(self.nmd["prod"], window) if "prod" in self.nmd
                           else np.full(shape, np.nan, np.float32))

        for k in ("thermal_sum", "precip"):
            src[k] = (self._read(self.clim[k], window) if k in self.clim
                      else np.full(shape, np.nan, np.float32))

        src["soil_group"] = self.soil_lut[self._read_int(self.soil, window, shape)].astype(np.float32)
        src["parent_group"] = self.parent_lut[self._read_int(self.parent, window, shape)].astype(np.float32)
        return src

    def features(self, window: Window, margin=MARGIN_SE):
        w = Window(window.col_off - margin, window.row_off - margin,
                   window.width + 2 * margin, window.height + 2 * margin)
        return block_features(self.read(w), margin)

    def point_features(self, row, col, half=8):
        """Feature vector of one cell, computed from a (2*half+1)^2 window so that every
        neighbourhood feature is exactly as in block inference."""
        w = Window(col - half, row - half, 2 * half + 1, 2 * half + 1)
        feats, valid = self.features(w)
        return feats[:, half, half], bool(valid[half, half])

    def close(self):
        for ds in (list(self.slu.values()) + self._slu_raw + [self.dem, self._dem,
                   self.soil, self.parent] + list(self.nmd.values()) + list(self._nmd.values())
                   + list(self.clim.values()) + list(self._clim.values())):
            try:
                ds.close()
            except Exception:                                 # noqa: BLE001
                pass
        self._env.__exit__(None, None, None)
