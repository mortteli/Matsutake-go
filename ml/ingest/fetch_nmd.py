"""Nationella Marktäckedata (NMD) 2023 from Naturvårdsverket -- the layers that close two
of the three gaps the Swedish audit thought were unfillable.

docs/SWEDEN_DATA.md concluded that Sweden has no canopy-cover layer and no site-class
layer. The first half of that is wrong. NMD publishes, CC0, at 10 m, in SWEREF99 TM, from
a plain HTTPS directory with no account:

  objekttackning 5-45 m   canopy coverage in percent, binned 5/10/20/.../100 (11 values).
                          A direct equivalent of MVMI's latvuspeitto, and a 2023 vintage
                          against Finland's 2019-2023.
  objekttackning 0.5-5 m  understory coverage, same units. Finland has no equivalent layer
                          at all.
  basskikt                53 classes that code main type and dominant species together:
                          111-118 forest on fastmark (mineral soil), 121-128 forest on
                          vatmark (peat), 200-224 open mire graded mager/frodig. That maps
                          onto paatyyppi's kangas / korpi / rame / neva more cleanly than
                          anything in the SLU products. 118 "temporart ej skog pa fastmark"
                          is also a free 2023 clear-cut signal, independent of
                          Skogsstyrelsen's felling layers.
  produktivitet           THREE classes only -- ej skogsmark / produktiv / improduktiv.
                          Worth having (improduktiv skogsmark in the north is largely
                          hallmark, lavhed and thin-soil pine, which is matsutake ground)
                          but it is not a fertility ladder and must not be described as
                          one. The kasvupaikka gap stays open; see docs/SWEDEN_DATA.md.

WHY THIS DOES NOT JUST CALL urlretrieve
---------------------------------------
The four zips total 7.5 GB and are mostly ballast we would never open: a 633 MB metadata
geopackage, 504 MB of overviews, a tree-species raster made redundant by the SLU volumes,
and in the objekthojd zip three rasters we do not want next to the two we do. Disk is the
binding constraint for the whole Swedish pipeline (29 GB, and the SGU and Skogsstyrelsen
geopackages peak at 17 GB on their own), so this reads each zip's central directory over a
range request and inflates only the members it needs: ~3.1 GB instead of 7.5 GB, and no
intermediate zip on disk at any point.

The zips are ZIP64 -- the objekthojd one is over 4 GB, so its members' offsets live in the
0x0001 extra field rather than the 32-bit header field, and a reader that ignores that
reads garbage. zipfile cannot do this over HTTP without downloading the whole archive
first, which is the thing being avoided.

    python ml/ingest/fetch_nmd.py                 # all four products
    python ml/ingest/fetch_nmd.py --only cover    # one of: cover, understory, base, prod
    python ml/ingest/fetch_nmd.py --list          # print each archive's members, fetch nothing
"""
import argparse, os, struct, sys, time, urllib.request, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ML = os.path.dirname(HERE)
OUT = os.path.join(ML, "data", "rasters_se", "nmd")

BASE = "https://geodata.naturvardsverket.se/nedladdning/marktacke/NMD2023"

# product key -> (zip url, member suffix to extract, local name)
PRODUCTS = {
    "cover": (f"{BASE}/Tillaggsskikt/NMD2023_Tillaggsskikt_Objekthojd_objekttackning_v1_1.zip",
              "NMD2023_Objekt_tackning_hojdintervall_5_till_45_v1_1.tif", "cover_5_45m.tif"),
    "understory": (f"{BASE}/Tillaggsskikt/NMD2023_Tillaggsskikt_Objekthojd_objekttackning_v1_1.zip",
                   "NMD2023_Objekt_tackning_hojdintervall_0_5_till_5_v1_1.tif", "cover_05_5m.tif"),
    "base": (f"{BASE}/Basskikt_v2_x/NMD2023_basskikt_v2_1.zip",
             "NMD2023bas_v2_1.tif", "basskikt.tif"),
    "prod": (f"{BASE}/Tillaggsskikt/NMD2023_Produktivitet_v1_0.zip",
             "NMD2023ochNMD2018_produktivitet_v1_0.tif", "produktivitet.tif"),
}

CHUNK = 8 << 20


def log(*a):
    print(*a, flush=True)


def _get(url, start=None, end=None, retries=5):
    headers = {}
    if start is not None:
        headers["Range"] = f"bytes={start}-" + ("" if end is None else str(end))
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)
        except Exception as e:                                  # noqa: BLE001 -- retry anything
            if attempt == retries - 1:
                raise
            log(f"  retry {attempt + 1}/{retries - 1} after {type(e).__name__}: {e}")
            time.sleep(3 * (attempt + 1))


def content_length(url):
    return int(urllib.request.urlopen(
        urllib.request.Request(url, method="HEAD"), timeout=60).headers["Content-Length"])


def central_directory(url, total):
    """{member name: (local header offset, compressed size, uncompressed size, method)}.

    Reads the tail of the archive and walks the central directory in place, resolving the
    ZIP64 extra field for any member whose 32-bit fields are saturated.
    """
    tail_len = min(total, 1 << 21)
    tail = _get(url, total - tail_len, total - 1).read()
    ents, i = {}, 0
    while True:
        i = tail.find(b"PK\x01\x02", i)
        if i < 0:
            return ents
        method = struct.unpack("<H", tail[i + 10:i + 12])[0]
        csz, usz = struct.unpack("<II", tail[i + 20:i + 28])
        nlen, elen = struct.unpack("<HH", tail[i + 28:i + 32])
        off = struct.unpack("<I", tail[i + 42:i + 46])[0]
        name = tail[i + 46:i + 46 + nlen].decode("utf-8", "replace")
        extra = tail[i + 46 + nlen:i + 46 + nlen + elen]
        j = 0
        while j + 4 <= len(extra):                              # ZIP64 extended information
            hid, hsz = struct.unpack("<HH", extra[j:j + 4])
            body, k = extra[j + 4:j + 4 + hsz], 0
            if hid == 1:                                        # fields appear only if saturated
                if usz == 0xFFFFFFFF:
                    usz = struct.unpack("<Q", body[k:k + 8])[0]; k += 8
                if csz == 0xFFFFFFFF:
                    csz = struct.unpack("<Q", body[k:k + 8])[0]; k += 8
                if off == 0xFFFFFFFF:
                    off = struct.unpack("<Q", body[k:k + 8])[0]; k += 8
            j += 4 + hsz
        ents[name] = (off, csz, usz, method)
        i += 4


def extract(url, entry, dest):
    """Stream one member out of the remote archive, inflating as it arrives."""
    off, csz, usz, method = entry
    head = _get(url, off, off + 29).read()
    if head[:4] != b"PK\x03\x04":
        raise RuntimeError(f"no local file header at offset {off}")
    nlen, elen = struct.unpack("<HH", head[26:30])
    start = off + 30 + nlen + elen
    dec = zlib.decompressobj(-15) if method == 8 else None
    tmp = dest + ".part"
    got, next_report, t0 = 0, 0.1, time.time()
    with _get(url, start, start + csz - 1) as r, open(tmp, "wb") as fh:
        while True:
            buf = r.read(CHUNK)
            if not buf:
                break
            got += len(buf)
            fh.write(dec.decompress(buf) if dec else buf)
            if got / csz >= next_report:
                rate = got / 1048576 / max(time.time() - t0, 1e-6)
                log(f"    {got / csz * 100:3.0f} %  {got / 1048576:.0f}/{csz / 1048576:.0f} MB"
                    f"  {rate:.1f} MB/s")
                next_report += 0.1
        if dec:
            fh.write(dec.flush())
    size = os.path.getsize(tmp)
    if size != usz:
        os.remove(tmp)
        raise RuntimeError(f"{os.path.basename(dest)}: inflated to {size} bytes, expected {usz}")
    os.replace(tmp, dest)
    open(dest + ".ok", "w").close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=sorted(PRODUCTS), action="append",
                    help="fetch only these products (repeatable); default is all four")
    ap.add_argument("--list", action="store_true", help="print archive members and exit")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    wanted = a.only or sorted(PRODUCTS)
    sizes = {}                                                  # one central-directory read per zip

    for key in wanted:
        url, member, local = PRODUCTS[key]
        dest = os.path.join(a.out, local)
        if os.path.exists(dest + ".ok") and not a.list:
            log(f"{key}: have {local}")
            continue
        if url not in sizes:
            total = content_length(url)
            log(f"\n{os.path.basename(url)}  ({total / 1048576:.0f} MB archive)")
            sizes[url] = (total, central_directory(url, total))
        total, ents = sizes[url]
        if a.list:
            for nm, (o, c, u, m) in sorted(ents.items()):
                if u:
                    log(f"  {nm.split('/')[-1]:68s} {c / 1048576:8.1f} -> {u / 1048576:8.1f} MB")
            continue
        match = [nm for nm in ents if nm.endswith(member)]
        if len(match) != 1:
            raise SystemExit(f"{key}: expected exactly one member ending {member!r}, got {match}")
        off, csz, usz, method = ents[match[0]]
        log(f"{key}: {member}  {csz / 1048576:.0f} MB -> {usz / 1048576:.0f} MB")
        extract(url, ents[match[0]], dest)
        log(f"  wrote {dest}")

    if not a.list:
        log("\nfetched:")
        for f in sorted(os.listdir(a.out)):
            if f.endswith(".tif"):
                log(f"  {f:22s} {os.path.getsize(os.path.join(a.out, f)) / 1048576:8.0f} MB")


if __name__ == "__main__":
    sys.exit(main())
