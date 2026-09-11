"""Access and exclusion layers for site picking, from an OpenStreetMap extract.

The habitat model says where the forest looks right. It says nothing about whether you are
allowed to pick there, whether you can park within walking distance, or whether the stand sits
in somebody's back yard or against a motorway. Those come from OSM:

  buildings    one point per building          -> keep away from houses and yards
  bigroads     motorway/trunk/primary + ramps  -> exhaust, noise, nowhere to stop
  driveroads   anything a car can drive        -> a spot you cannot reach is not a spot
  areas        nature reserves, national parks, protected areas, military areas

Everything is stored in EPSG:3067 metres, ready for a distance transform on the 16 m grid.

  python ml/fetch_osm.py --bbox 60.4 21.4 62.6 26.2 --out ml/data/osm/pirkanmaa.npz
  python ml/fetch_osm.py --center 61.4978 23.7610 --radius-km 115 --out ml/data/osm/pirkanmaa.npz

The extract is downloaded once to ml/data/raw/ unless --pbf points at a local file.
Source: OpenStreetMap contributors, ODbL.
"""
import argparse, math, os, subprocess, sys, time
import numpy as np
import osmium
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
PBF_URL = "https://download.openstreetmap.fr/extracts/europe/finland.osm.pbf"
BIG = {"motorway", "trunk", "primary", "motorway_link", "trunk_link", "primary_link"}
DRIVE = BIG | {"secondary", "tertiary", "unclassified", "residential", "service", "track",
               "secondary_link", "tertiary_link", "living_street"}
TF = Transformer.from_crs(4326, 3067, always_xy=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def densify(pts, step=40.0):
    """A point at least every `step` metres along a polyline, so that a distance transform on a
    16 m grid cannot slip through the gap between two far-apart vertices."""
    out = []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) // step))
        out.extend((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n))
    out.append(tuple(pts[-1]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("LAT0", "LON0", "LAT1", "LON1"),
                    help="WGS84 box to keep")
    ap.add_argument("--center", type=float, nargs=2, metavar=("LAT", "LON"))
    ap.add_argument("--radius-km", type=float, default=115.0)
    ap.add_argument("--pbf", default=None, help="local .osm.pbf (downloaded if missing)")
    ap.add_argument("--out", default=os.path.join(HERE, "data", "osm", "finland.npz"))
    a = ap.parse_args()

    if a.bbox:
        lat0, lon0, lat1, lon1 = a.bbox
    elif a.center:
        lat, lon = a.center
        dlat = a.radius_km / 111.0
        dlon = a.radius_km / (111.0 * math.cos(math.radians(lat)))
        lat0, lat1, lon0, lon1 = lat - dlat, lat + dlat, lon - dlon, lon + dlon
    else:
        ap.error("give --bbox or --center")
    log(f"keeping {lat0:.2f}..{lat1:.2f} N, {lon0:.2f}..{lon1:.2f} E")

    pbf = a.pbf or os.path.join(HERE, "data", "raw", "finland.osm.pbf")
    if not os.path.exists(pbf):
        os.makedirs(os.path.dirname(pbf), exist_ok=True)
        log("downloading", PBF_URL)
        subprocess.run(["curl", "-sS", "-C", "-", "-o", pbf, PBF_URL], check=True)
    log("reading", pbf, f"{os.path.getsize(pbf)/1e6:.0f} MB")

    def inbox(lat, lon):
        return lat0 <= lat <= lat1 and lon0 <= lon <= lon1

    buildings, big, drive = [], [], []
    n = 0
    t0 = time.time()
    ways = osmium.FileProcessor(pbf).with_locations("flex_mem") \
                 .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
    for w in ways:
        n += 1
        if n % 2_000_000 == 0:
            log(f"  ways {n/1e6:.0f}M  buildings {len(buildings)}  big {len(big)}  drive {len(drive)}")
        hw = w.tags.get("highway")
        is_building = "building" in w.tags
        if (hw is None and not is_building) or (hw is not None and hw not in DRIVE):
            continue
        try:
            ll = [(nd.lon, nd.lat) for nd in w.nodes if nd.location.valid()]
        except Exception:                     # way with nodes missing from the extract
            continue
        if not ll or not any(inbox(la, lo) for lo, la in ll[:: max(1, len(ll) // 4)]):
            continue
        if hw is None:
            buildings.append(TF.transform(ll[0][0], ll[0][1]))
            continue
        xs, ys = TF.transform([p[0] for p in ll], [p[1] for p in ll])
        pts = list(zip(xs, ys))
        (big if hw in BIG else drive).extend(densify(pts) if len(pts) > 1 else pts)
    log(f"ways done: {len(buildings)} buildings, {len(big)} big-road points, "
        f"{len(drive)} drivable-road points ({time.time()-t0:.0f}s)")

    kinds, names, rings = [], [], []
    t1 = time.time()
    areas = osmium.FileProcessor(pbf).with_areas() \
                  .with_filter(osmium.filter.EntityFilter(osmium.osm.AREA))
    for ar in areas:
        t = ar.tags
        if t.get("leisure") == "nature_reserve" or t.get("boundary") in ("protected_area", "national_park"):
            kind = "protected"
        elif t.get("landuse") == "military" or "military" in t:
            kind = "military"
        else:
            continue
        for ring in ar.outer_rings():
            ll = [(nd.lon, nd.lat) for nd in ring]
            if len(ll) < 4 or not any(inbox(la, lo) for lo, la in ll[:: max(1, len(ll) // 6)]):
                continue
            xs, ys = TF.transform([p[0] for p in ll], [p[1] for p in ll])
            kinds.append(kind); names.append(t.get("name", ""))
            rings.append(np.array(list(zip(xs, ys)), dtype="float64"))
    log(f"areas done: {len(rings)} rings ({time.time()-t1:.0f}s)")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    np.savez_compressed(a.out,
                        buildings=np.array(buildings, dtype="float64").reshape(-1, 2),
                        bigroads=np.array(big, dtype="float64").reshape(-1, 2),
                        driveroads=np.array(drive, dtype="float64").reshape(-1, 2),
                        poly_kind=np.array(kinds), poly_name=np.array(names),
                        poly_xy=np.array(rings, dtype=object))
    log("wrote", a.out, f"{os.path.getsize(a.out)/1e6:.0f} MB")


if __name__ == "__main__":
    main()
