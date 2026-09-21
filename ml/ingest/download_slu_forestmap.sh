#!/bin/sh
# Local copies of the SLU forest attribute rasters used by features_se.py (resumable).
# No account needed -- these are plain static files on SLU's own GIS server, unlike
# Skogsstyrelsen's WMS/REST wrapper around the same data, which does require one.
#
# WHY THE 2010 SET AND NOT THE NEWER ONES
#
# The 2015 "leaf" set is 12.5 m and looks like the obvious choice, but its raster stops at
# northing 7350000 (~66.3 N on the central meridian): SLU clipped it to the laser coverage
# of the day, and Gotland is cut out by name (VolTot_leaf.tif.xml names
# SLU_Skogskarta_clipMaskNOGotland.shp). 1508 of our 5501 Swedish matsutake records --
# 27 % -- fall outside it, nearly all of them in Lule lappmark, Torne lappmark and
# Norrbotten, which is the densest matsutake ground in the country. It also has no age
# raster and no separate birch volume.
#
# The 2018 "andel" set does cover the whole country, but it is strip-compressed at 52600 px
# per strip and 3.5 GB per file: 24 GB for the seven files, against 29 GB of disk, and a
# single point read costs about a megabyte. It is unusable at any scale. Its only value is
# its geometry, which is what grid_se.py's national grid is derived from.
#
# The 2010 vintage in RT90 is tiled 128x128, covers the whole country including Gotland
# (top northing 7636500, ~68.8 N), and is the only vintage with an age raster. It costs
# 25 m instead of 12.5 m and is fifteen years stale -- the same kind of caveat as Finland's
# older MVMI cycles, but with data everywhere the finer set has none. features_se.py warps
# it from EPSG:3021 onto the SWEREF99 TM grid; see grid_se.py's assert_rt90_transform for
# why that warp is guarded.
set -e
dir="$(dirname "$0")/../data/rasters_se/slu_forest_map"; mkdir -p "$dir"; cd "$dir"
BASE="https://gis.slu.se/data/slu_forest_map"

# 2010, 25 m, RT90 2.5 gon V (EPSG:3021) -- the feature spine. ~3.4 GB.
for f in AGE HEIGHT TOTALVOL PINEVOL SPRUCEVOL BIRCHVOL DECIDUOUSVOL CONTORTAVOL; do
  out="2010_${f}.tif"
  [ -f "$out.ok" ] && continue
  curl -sS -C - -o "$out" "$BASE/2010/Data/Raster/Rt90/${f}_XX_P_10.tif" && touch "$out.ok"
  echo "done $out"
done

# 2005, same grid -- only AGE and TOTALVOL, and only so observation_status_se.py has a
# second vintage to compare against. Everything else reads 2010 alone. ~1.2 GB.
for f in AGE TOTALVOL; do
  out="2005_${f}.tif"
  [ -f "$out.ok" ] && continue
  curl -sS -C - -o "$out" "$BASE/2005/Data/Raster/Rt90/${f}_XX_P_05.tif" && touch "$out.ok"
  echo "done $out"
done
