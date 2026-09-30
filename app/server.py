# -*- coding: utf-8 -*-
"""
CineChat AI - Backend server (Python standard library, tanpa framework).

Stack ringan & efisien:
  - http.server ThreadingHTTPServer (multi-thread, stdlib)
  - engine.py : BM25 search + rule-based reasoning + multi-criteria decision
  - vision.py : OCR (tesseract) + analisis warna (ImageMagick) untuk upload foto

Jalankan:  python3 app/server.py  ->  http://localhost:8000
"""
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")
sys.path.insert(0, APP_DIR)

from engine import MovieEngine          # noqa: E402
from vision import analyze_photo        # noqa: E402

PORT = int(os.environ.get("PORT", "8000"))
MAX_UPLOAD = 10 * 1024 * 1024           # 10 MB
MAX_MESSAGE = 1000                      # karakter
RATE_LIMIT_WINDOW = 60                  # detik
RATE_LIMIT_MAX = 120                    # request per window per IP
SESSION_TTL = 30 * 60                   # 30 menit

# Rate limit sederhana per IP (sliding window)
_RATE = {}          # ip -> [timestamps]
_SESSIONS = {}      # session_id -> {"query": str, "page": int, "ts": float}

SECURITY_HEADERS = [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Content-Security-Policy",
     "default-src 'self'; img-src 'self' https://image.tmdb.org data: blob:; "
     "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
]

FOLLOWUP_RE = re.compile(r"^(lagi|lainnya|yang lain|lanjut|next|more|another|tambah|masih ada)\b", re.IGNORECASE)

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".json": "application/json; charset=utf-8",
}

print("Memuat dataset film (sekali di awal)...")
t0 = time.time()
ENGINE = MovieEngine()
print(f"Siap: {len(ENGINE.movies)} film, {len(ENGINE.postings)} kosakata, "
      f"indeks BM25 dibangun dalam {time.time() - t0:.2f}s")


# ----------------------------------------------------------------------------
# Utilitas multipart (parser multipart/form-data sederhana)
# ----------------------------------------------------------------------------
def parse_multipart(body, content_type):
    m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type or "")
    if not m:
        return []
    boundary = (m.group(1) or m.group(2)).strip().encode()
    parts = []
    for raw in body.split(b"--" + boundary):
        raw = raw.strip(b"\r\n")
        if not raw or raw == b"--":
            continue
        header_block, sep, data = raw.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = {}
        for line in header_block.split(b"\r\n"):
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().lower().decode("latin-1")] = v.strip().decode("latin-1")
        cd = headers.get("content-disposition", "")
        name_m = re.search(r'name="([^"]*)"', cd)
        fn_m = re.search(r'filename="([^"]*)"', cd)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        parts.append({
            "name": name_m.group(1) if name_m else None,
            "filename": fn_m.group(1) if fn_m else None,
            "content_type": headers.get("content-type", ""),
            "data": data,
        })
    return parts


def resolve_static(rel_path):
    """Resolve path statis dengan aman dari path traversal. Return None jika di luar STATIC_DIR."""
    safe = os.path.normpath(rel_path).lstrip("/")
    full = os.path.join(STATIC_DIR, safe)
    if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
        return None
    return full


# ----------------------------------------------------------------------------
# HTTP handler
# ----------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "CinePicks/2.0"

    def version_string(self):
        return self.server_version

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def _sec_headers(self):
        for k, v in SECURITY_HEADERS:
            self.send_header(k, v)

    def _check_rate(self):
        """Rate limit per IP (sliding window). Return True jika boleh lanjut."""
        ip = self.client_address[0]
        now = time.time()
        hits = [t for t in _RATE.get(ip, []) if now - t < RATE_LIMIT_WINDOW]
        if len(hits) >= RATE_LIMIT_MAX:
            _RATE[ip] = hits
            return False
        hits.append(now)
        _RATE[ip] = hits
        return True

    # ---------------------------------------------------------- respons JSON
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self._sec_headers()
        self.end_headers()
        self.wfile.write(body)

    # ---------------------------------------------------------- file statis
    def _static(self, rel_path):
        full = resolve_static(rel_path)
        if not full:
            self.send_error(404, "Not Found")
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self._sec_headers()
        self.end_headers()
        self.wfile.write(body)

    # ---------------------------------------------------------- GET
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._static("index.html")
        elif path.startswith("/static/"):
            self._static(path[len("/static/"):])
        elif path == "/api/health":
            self._json({
                "status": "ok",
                "movies": len(ENGINE.movies),
                "vocab": len(ENGINE.postings),
                "uptime_s": round(time.time() - t0, 1),
            })
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404, "Not Found")

    # ---------------------------------------------------------- POST
    def do_POST(self):
        path = urlparse(self.path).path
        if not self._check_rate():
            self._json({"error": "Terlalu banyak request. Coba lagi nanti."}, 429)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > MAX_UPLOAD + 1024 * 1024:
            self._json({"error": "Payload terlalu besar."}, 413)
            return
        body = self.rfile.read(length) if length else b""

        if path == "/api/chat":
            self._handle_chat(body)
        elif path == "/api/upload":
            self._handle_upload(body)
        else:
            self._json({"error": "Endpoint tidak ditemukan."}, 404)

    # ---------------------------------------------------------- API chat
    def _handle_chat(self, body):
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json({"error": "JSON tidak valid."}, 400)
            return
        message = str(payload.get("message", "") or "").strip()
        if len(message) > MAX_MESSAGE:
            self._json({"error": "Pesan terlalu panjang (maks %d karakter)." % MAX_MESSAGE}, 400)
            return
        if not message:
            self._json({"error": "Pesan kosong."}, 400)
            return

        sid = str(payload.get("session_id", "") or "")[:64]
        sess = _SESSIONS.get(sid) if sid else None

        # Follow-up multi-turn: "lagi", "lainnya", "lanjut", dll -> halaman berikutnya
        if FOLLOWUP_RE.match(message) and sess and sess.get("query"):
            sess["page"] = sess.get("page", 0) + 1
            sess["ts"] = time.time()
            result = ENGINE.chat(sess["query"], page=sess["page"])
        else:
            page = 0
            result = ENGINE.chat(message, page=page)
            if sid:
                _SESSIONS[sid] = {"query": message, "page": 0, "ts": time.time()}
        self._json(result)

    # ---------------------------------------------------------- API upload
    def _handle_upload(self, body):
        ctype = self.headers.get("Content-Type", "")
        parts = parse_multipart(body, ctype)
        file_part = None
        for p in parts:
            if p.get("filename"):
                file_part = p
                break
        if not file_part:
            self._json({"error": "Tidak ada file foto pada request. Gunakan field 'file'."}, 400)
            return
        if not (file_part.get("content_type", "").startswith("image/") or file_part["data"]):
            self._json({"error": "File harus berupa gambar."}, 400)
            return
        if len(file_part["data"]) > MAX_UPLOAD:
            self._json({"error": "Ukuran gambar maksimal 10 MB."}, 413)
            return
        try:
            result = analyze_photo(file_part["data"], ENGINE)
        except Exception as exc:  # jangan buat server mati
            self._json({"error": "Gagal menganalisis foto: %s" % exc}, 500)
            return
        if "error" in result:
            self._json(result, 400)
            return
        self._json(result)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 56)
    print("  CineChat AI berjalan di: http://localhost:%d" % PORT)
    print("  Tekan Ctrl+C untuk berhenti.")
    print("=" * 56)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
        server.shutdown()


if __name__ == "__main__":
    main()
