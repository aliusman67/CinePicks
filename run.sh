#!/usr/bin/env bash
# =============================================================================
# run.sh — Menjalankan layanan CinePicks secara otomatis
#
# Penggunaan:
#   ./run.sh               # jalankan server (foreground)
#   ./run.sh --port 9000   # jalankan di port tertentu
#   ./run.sh --check       # periksa dependensi saja (tanpa menjalankan)
#   ./run.sh --test        # jalankan unit test saja
#   ./run.sh --test --run  # jalankan unit test, lalu server jika lolos
#
# Variabel lingkungan:
#   PORT                   # port server (default 8000)
# =============================================================================
set -euo pipefail

# Pindah ke direktori tempat skrip ini berada
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
DO_CHECK=0
DO_TEST=0
DO_RUN=0
MODE_ARG=0

# ---------------------------------------------------------------- argumen
for arg in "$@"; do
  case "$arg" in
    --check) DO_CHECK=1; MODE_ARG=1 ;;
    --test) DO_TEST=1; MODE_ARG=1 ;;
    --run) DO_RUN=1; MODE_ARG=1 ;;
    --port) ;;                     # nilai dibaca pada iterasi berikutnya
    --port=*) PORT="${arg#*=}" ;;
    --help|-h)
      sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      if [[ "$arg" =~ ^[0-9]+$ ]]; then
        PORT="$arg"
      else
        echo "Argumen tidak dikenal: $arg" >&2
        exit 2
      fi ;;
  esac
done
# dukung bentuk "--port 9000"
prev=""
for arg in "$@"; do
  if [[ "$prev" == "--port" ]]; then
    PORT="$arg"
  fi
  prev="$arg"
done

# Tanpa argumen mode apa pun -> default: jalankan server
if [[ "$MODE_ARG" == "0" ]]; then
  DO_RUN=1
fi

# ---------------------------------------------------------------- dependensi
echo "==> Memeriksa dependensi..."
ok=1

if ! command -v python3 >/dev/null 2>&1; then
  echo "  [X] python3 tidak ditemukan" >&2
  ok=0
else
  echo "  [OK] python3 $(python3 --version 2>&1)"
fi

if ! command -v tesseract >/dev/null 2>&1; then
  echo "  [X] tesseract tidak ditemukan (dibutuhkan untuk OCR foto)" >&2
  ok=0
elif ! tesseract --list-langs 2>/dev/null | grep -q '^eng$'; then
  echo "  [X] tesseract tidak memiliki bahasa 'eng'" >&2
  ok=0
else
  echo "  [OK] tesseract (bahasa eng tersedia)"
fi

if command -v magick >/dev/null 2>&1; then
  echo "  [OK] ImageMagick (magick)"
elif command -v convert >/dev/null 2>&1; then
  echo "  [OK] ImageMagick (convert)"
else
  echo "  [X] ImageMagick tidak ditemukan (dibutuhkan untuk analisis warna foto)" >&2
  ok=0
fi

# ---------------------------------------------------------------- dataset
CSV="Top Movies dataset.csv"
if [[ ! -f "$CSV" ]]; then
  if [[ -f archive.zip ]]; then
    echo "==> Mengekstrak dataset dari archive.zip..."
    unzip -o archive.zip
  else
    echo "  [X] Dataset '$CSV' dan archive.zip tidak ditemukan" >&2
    ok=0
  fi
else
  echo "  [OK] Dataset ditemukan: $CSV"
fi

if [[ "$ok" == "0" ]]; then
  echo "==> Pemeriksaan gagal. Instal dependensi yang hilang lalu coba lagi." >&2
  exit 1
fi
echo "==> Semua dependensi terpenuhi."

# ---------------------------------------------------------------- mode
if [[ "$DO_TEST" == "1" ]]; then
  echo "==> Menjalankan unit test..."
  python3 -m unittest discover -s app/tests -v
  echo "==> Unit test selesai."
fi

if [[ "$DO_RUN" == "0" ]]; then
  if [[ "$DO_CHECK" == "1" ]]; then
    echo "==> Mode --check: hanya memeriksa, tidak menjalankan server."
  fi
  exit 0
fi

# ---------------------------------------------------------------- jalankan
echo "==> Menjalankan server di http://localhost:${PORT} (Ctrl+C untuk berhenti)"
export PORT
exec python3 app/server.py
