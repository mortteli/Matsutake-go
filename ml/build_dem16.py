"""Warp the MML 10 m elevation model onto the 16 m analysis grid once, so that training and
full-Finland inference read identical elevation values from local disk instead of fetching
~25 GB of remote tiles per pass.

Output: ml/data/rasters/dem_16m.tif  (int16 decimetres, nodata -32768)
Restartable: finished blocks are recorded in <out>.progress.
"""
import os, sys, time
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.windows import Window

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from grid import Grid, env, DEM_VRT

OUT = os.path.join(HERE, "data", "rasters", "dem_16m.tif")
NODATA = -32768
BLOCK = 4096


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main():
    grid = Grid()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    prog = OUT + ".progress"
    done = set(open(prog).read().split()) if os.path.exists(prog) else set()
    prof = grid.profile("int16", nodata=NODATA)
    mode = "r+" if (os.path.exists(OUT) and done) else "w"
    with env():
        src = rasterio.open(DEM_VRT)
        vrt = WarpedVRT(src, crs=grid.crs, transform=grid.transform, width=grid.width,
                        height=grid.height, resampling=Resampling.bilinear,
                        src_nodata=src.nodata, nodata=src.nodata)
        with rasterio.open(OUT, mode, **(prof if mode == "w" else {})) as dst, open(prog, "a") as pf:
            todo = [w for w in grid.blocks(BLOCK) if f"{w.row_off},{w.col_off}" not in done]
            log("blocks to do", len(todo))
            for i, w in enumerate(todo):
                t0 = time.time()
                a = vrt.read(1, window=w).astype("float32")
                bad = ~np.isfinite(a) | (a < -50) | (a > 2000)      # sea/edge blending of -9999
                out = np.where(bad, NODATA, np.round(a * 10)).astype("int16")
                dst.write(out, 1, window=w)
                pf.write(f"{w.row_off},{w.col_off}\n"); pf.flush()
                if i % 5 == 0:
                    log(f"{i}/{len(todo)} valid {float((~bad).mean()):.2f} {time.time()-t0:.0f}s")
        vrt.close(); src.close()
    with rasterio.open(OUT, "r+") as dst:
        dst.build_overviews([2, 4, 8, 16, 32], Resampling.average)
    log("DONE", OUT, f"{os.path.getsize(OUT)/1e9:.1f} GB")


if __name__ == "__main__":
    main()
