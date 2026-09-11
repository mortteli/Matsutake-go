"""Local development server for Matsutake GO.

    python3 serve.py [port]        # default 8000, then open http://localhost:8000

Plain `python3 -m http.server` is not enough: the probability layer reads the GeoTIFFs with
HTTP range requests, and Python's SimpleHTTPRequestHandler ignores the Range header. The
reader then miscomputes byte offsets and the model layer stays blank. GitHub Pages serves
ranges correctly, so this only matters locally.
"""
import http.server, os, re, functools, threading


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if not m:
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404); return None
        size = os.fstat(f.fileno()).st_size
        start, end = m.group(1), m.group(2)
        if start == "":
            length = int(end); start = max(0, size - length); end = size - 1
        else:
            start = int(start); end = int(end) if end else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_error(416); f.close(); return None
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        f.seek(start)
        self._range_remaining = end - start + 1
        return _Limited(f, end - start + 1)

    def log_message(self, fmt, *a):
        pass


class _Limited:
    def __init__(self, f, n): self.f, self.n = f, n
    def read(self, amt=None):
        if self.n <= 0: return b""
        amt = self.n if amt is None else min(amt, self.n)
        d = self.f.read(amt); self.n -= len(d); return d
    def close(self): self.f.close()


def serve(root, port):
    h = functools.partial(RangeHandler, directory=root)
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    s = http.server.ThreadingHTTPServer(("127.0.0.1", port), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


if __name__ == "__main__":
    import sys, os
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    root = os.path.dirname(os.path.abspath(__file__))
    serve(root, port)
    print(f"Matsutake GO on http://localhost:{port}  (Ctrl-C to stop)")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
