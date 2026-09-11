#!/bin/sh
# Local copies of the MVMI 2023 themes used by features.py (resumable). ~10 GB.
set -e
dir="$(dirname "$0")/data/rasters/mvmi2023"; mkdir -p "$dir"; cd "$dir"
for t in kasvupaikka paatyyppi ika manty kuusi koivu tilavuus ppa latvuspeitto keskipituus; do
  f="${t}_vmi1x_1923.tif"
  [ -f "$f.ok" ] && continue
  curl -sS -C - -o "$f" "https://www.nic.funet.fi/index/geodata/luke/vmi/2023/$f" && touch "$f.ok"
  echo "done $f"
done
