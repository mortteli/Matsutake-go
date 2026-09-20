#!/bin/sh
# Local copies of the SLU forest attribute rasters used by features_se.py (resumable).
# No account needed -- these are plain static files on SLU's own GIS server, unlike
# Skogsstyrelsen's WMS/REST wrapper around the same data, which does require one.
# 2015 "leaf" set + 2018 species-share set: ~10 GB. 2010 age (RT90): ~0.6 GB.
set -e
dir="$(dirname "$0")/../data/rasters_se/slu_forest_map"; mkdir -p "$dir"; cd "$dir"
BASE="https://gis.slu.se/data/slu_forest_map"

# 2015, 12.5 m, SWEREF99 TM: basal area, mean diameter, mean height, biomass, volume by
# species group (pine / spruce / other deciduous, no birch/oak/beech split) and total volume.
for f in BA_leaf Biomass_leaf DGV_leaf HGV_leaf GranVol_leaf TallVol_leaf LovVol_leaf VolTot_leaf; do
  out="2015_${f}.tif"
  [ -f "$out.ok" ] && continue
  curl -sS -C - -o "$out" "$BASE/2015/data/${f}.tif" && touch "$out.ok"
  echo "done $out"
done

# 2018, 12.5 m: species share of volume (%) -- splits deciduous further than the 2015 set does.
for f in Tall_andel Gran_andel Bjork_andel Ek_andel Bok_andel Contorta_andel OvrLov_andel; do
  out="2018_${f}.tif"
  [ -f "$out.ok" ] && continue
  curl -sS -C - -o "$out" "$BASE/2018/data/${f}.tif" && touch "$out.ok"
  echo "done $out"
done

# 2010, 25 m, RT90 2.5 gon V (EPSG:3021) -- the only vintage with an age raster. Reproject to
# SWEREF99 TM before use (grid_se.py's GridSE is in EPSG:3006); ~15 years stale by now, the
# same kind of caveat as Finland's older MVMI cycles but with no newer replacement documented.
out="2010_AGE_rt90.tif"
if [ ! -f "$out.ok" ]; then
  curl -sS -C - -o "$out" "$BASE/2010/Data/Raster/Rt90/AGE_XX_P_10.tif" && touch "$out.ok"
  echo "done $out"
fi
