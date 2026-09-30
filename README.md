# CinePicks — Chat Rekomendasi Film

![Logo CinePicks](static/logo.png)

Aplikasi web sederhana untuk mencari dan merekomendasikan film dari dataset
**Top Movies dataset.csv** (9.837 judul). Mendukung chat teks (Indonesia/Inggris),
filter genre/mood/tahun/negara, rekomendasi film serupa, serta **upload foto**
yang "dibaca" dengan OCR dan analisis warna untuk menghasilkan rekomendasi.

Dibangun dengan **Python standard library** (tanpa framework) di backend dan
**HTML/CSS/JavaScript vanilla** di frontend — ringan, cepat, tanpa `pip install`.

---

## Alur Aplikasi

```
PENGGUNA
   │
   │  mengetik query / mengunggah foto poster
   ▼
┌─────────────────────┐      POST /api/chat      ┌──────────────────────────┐
│   FRONTEND          │ ───────────────────────► │  BACKEND (server.py)     │
│   index.html        │      POST /api/upload    │  ThreadingHTTPServer     │
│   app.js + style.css│                          │  - rate limit per IP     │
└─────────────────────┘                          │  - validasi input        │
   ▲                                             └───────────┬──────────────┘
   │                                                         │
   │  reply + movies[] (kartu film: poster, rating,          ▼
   │  alasan rekomendasi, deskripsi)              ┌──────────────────────────┐
   └────────────────────────────────────────────── │  ENGINE (engine.py)      │
                                                   │  1. Intent parsing (ID/EN)│
                                                   │     genre/mood/negara/   │
                                                   │     tahun/judul          │
                                                   │  2. SEARCHING: BM25      │
                                                   │  3. DECISION: scoring    │
                                                   └───────────┬──────────────┘
                                                               │  (jika upload foto)
                                                               ▼
                                                   ┌──────────────────────────┐
                                                   │  VISION (vision.py)      │
                                                   │  - tesseract OCR -> judul │
                                                   │  - ImageMagick -> warna  │
                                                   │  - inferensi mood/genre  │
                                                   └──────────────────────────┘
```

---

## Fitur

- **Chat rekomendasi film**
  - Genre: `film action terbaik`, `horor tahun 2022`, `film anak`, `film pendidikan`
  - Mood: `film sedih romantis`, `seram`, `lucu`, `menegangkan`
  - Negara: `rekomendasi film indonesia`, `film korea`, `film jepang sedih`
  - Judul: `Interstellar`, `mirip The Batman`
  - Lainnya: `film populer` (trending), `surprise me` (acak), `lagi` (halaman berikutnya)
- **Upload foto poster** — OCR (tesseract) membaca judul pada foto; jika tidak ada
  teks, warna dominan (ImageMagick) dipakai untuk inferensi mood/genre film.
- **Kartu rekomendasi lengkap** — poster, rating, tahun, genre, alasan rekomendasi,
  dan deskripsi/sinopsis.
- **Multi-turn sederhana** — ketik `lagi`, `lainnya`, atau `next` untuk melihat
  rekomendasi halaman berikutnya dari query sebelumnya.

## Tech Stack

| Lapisan  | Teknologi |
|----------|-----------|
| Backend  | Python 3 stdlib (`http.server.ThreadingHTTPServer`) |
| Pencarian| Inverted index + Okapi BM25 (implementasi murni Python) |
| Vision   | `tesseract` (OCR) + ImageMagick `convert` (warna dominan) |
| Frontend | HTML + CSS + JavaScript vanilla (tanpa build step) |
| Testing  | `unittest` (stdlib) |

## Struktur Proyek

```
LLM-Web/
├── Top Movies dataset.csv   # dataset (9.837 film)
├── app/
│   ├── server.py            # HTTP server, API, keamanan, sesi, rate limit
│   ├── engine.py            # BM25 search, intent parsing, scoring, deskripsi
│   ├── vision.py            # OCR + analisis warna + rekomendasi dari foto
│   ├── static/
│   │   ├── index.html       # UI utama
│   │   ├── style.css        # tema gelap ala aplikasi streaming
│   │   └── app.js           # logika frontend
│   └── tests/
│       ├── test_engine.py   # unit test mesin rekomendasi
│       └── test_security.py # unit test keamanan & vision
├── run.sh                    # skrip otomatis: cek dependensi, test, jalankan server
└── README.md
```

## Algoritma

1. **SEARCHING** — inverted index atas judul (bobot 3x), genre (2x), sinopsis (1x),
   diberi peringkat dengan **Okapi BM25** (`k1=1.5`, `b=0.75`).
2. **REASONING** — rule-based intent parser (ID/EN): genre, mood, negara, tahun,
   "terbaik/terbaru/populer", "mirip X", "kejutan", plus knowledge base kata kunci.
3. **DECISION** — multi-criteria scoring:
   `0.40·rating + 0.25·log(votes) + 0.20·log(popularity) + 0.15·recency`,
   dengan prioritas jumlah genre yang cocok; mode "terbaik" memakai
   `rating × log(votes)`, mode "populer" memakai `log(popularity)`.
4. **VISION** — OCR (`tesseract`, psm 3 + fallback psm 11) untuk mencocokkan judul
   film secara substring/fuzzy; jika gagal, pohon keputusan warna
   (gelap → thriller/horor, cerah → animasi/keluarga, hangat → romansa,
   dingin → sci-fi) memetakan foto ke genre.

## Menjalankan

```bash
cd LLM-Web
./run.sh                 # jalankan server (otomatis cek dependensi + dataset)
./run.sh --port 9000     # jalankan di port 9000
./run.sh --check         # periksa dependensi saja
./run.sh --test          # jalankan unit test saja
./run.sh --test --run    # unit test dulu, server dijalankan jika lolos
```

Atau langsung tanpa skrip:

```bash
python3 app/server.py    # buka http://localhost:8000
```

Kebutuhan sistem: Python 3.8+, `tesseract` dengan bahasa `eng`, dan ImageMagick
(`convert`/`magick`). Tidak ada dependensi Python eksternal.

## API

| Method | Endpoint      | Keterangan |
|--------|---------------|------------|
| GET    | `/api/health` | Status server, jumlah film, uptime |
| POST   | `/api/chat`   | `{ "message": "...", "session_id": "..." }` → `{ reply, movies[], lang }` |
| POST   | `/api/upload` | `multipart/form-data` field `file` (gambar) → hasil OCR + rekomendasi |

Setiap objek film berisi: `title`, `year`, `rating`, `votes`, `genres`,
`overview`, `poster`, `reason` (alasan rekomendasi), dan `description`.

## Testing

```bash
cd LLM-Web
python3 -m unittest discover -s app/tests -v
```

Cakupan: loading dataset, tokenisasi, pencarian judul (substring + fuzzy guard),
intent genre/mood/negara/tahun/surprise/trending, pagination, no-result,
multipart parser, path traversal, sniffing gambar, dan pohon keputusan warna.

## Keamanan

- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Content-Security-Policy`, `Permissions-Policy`.
- Rate limiting per IP (sliding window, 120 request/menit).
- Validasi input: maks 1.000 karakter pesan, upload maks 10 MB, deteksi magic bytes.
- Path traversal dicegah via `resolve_static()`.
- Subprocess (`tesseract`, `convert`) dipanggil tanpa shell.
- Semua output frontend di-escape (anti-XSS).

## Catatan

- Poster dimuat dari `image.tmdb.org` (membutuhkan akses internet di browser).
- Deskripsi bahasa Indonesia disediakan untuk film Indonesia di dataset;
  film lain memakai template deskripsi + sinopsis asli (Inggris).
