# -*- coding: utf-8 -*-
"""
CineChat AI - Modul "membaca foto" (vision) tanpa dependensi Python eksternal.

Memanfaatkan tool sistem yang sudah tersedia:
  - tesseract (OCR)  : membaca teks pada foto (judul poster, dll).
  - ImageMagick      : mengekstrak warna dominan foto.

Alur penalaran foto:
  OCR teks -> cocokkan judul film (fuzzy) -> rekomendasi film serupa.
  Jika tidak ada teks -> warna dominan -> inferensi mood/genre -> rekomendasi.
"""
import os
import re
import subprocess
import tempfile

from engine import normalize, tokenize

MAGICK = "convert"  # ImageMagick (tersedia di sistem)


# ----------------------------------------------------------------------------
# Tool wrapper
# ----------------------------------------------------------------------------
def _run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout or "", r.returncode
    except Exception:
        return "", -1


# ----------------------------------------------------------------------------
# OCR
# ----------------------------------------------------------------------------
def read_text(path):
    """Baca teks dari foto dengan tesseract (psm 3, fallback psm 11)."""
    for psm in ("3", "11"):
        out, code = _run(["tesseract", path, "stdout", "-l", "eng", "--psm", psm])
        text = " ".join(out.split())
        if text:
            return text
    return ""


# ----------------------------------------------------------------------------
# Warna dominan
# ----------------------------------------------------------------------------
def dominant_colors(path, n=6):
    """Ambil n warna dominan via ImageMagick -> [(count, (r,g,b))] terurut."""
    out, code = _run([
        MAGICK, path, "-resize", "48x48!", "-alpha", "off", "-depth", "8", "-colors", str(n),
        "-format", "%c", "histogram:info:-",
    ])
    colors = []
    for line in out.splitlines():
        m = re.search(r"(\d+):\s*\(\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)", line)
        if m:
            count = int(m.group(1))
            rgb = (int(float(m.group(2))), int(float(m.group(3))), int(float(m.group(4))))
            colors.append((count, rgb))
    colors.sort(key=lambda x: -x[0])
    return colors


def analyze_colors(colors):
    """REASONING: statistik warna -> inferensi mood/genre film."""
    if not colors:
        return {"label": "tidak terbaca", "genres": ["Drama"], "stats": {},
                "explanation": "Warna tidak terbaca; pakai genre umum."}

    total = sum(c for c, _ in colors) or 1
    r = g = b = sat = 0.0
    for count, (rr, gg, bb) in colors:
        w = count / total
        r += rr * w
        g += gg * w
        b += bb * w
        sat += (max(rr, gg, bb) - min(rr, gg, bb)) * w

    brightness = 0.299 * r + 0.587 * g + 0.114 * b   # luminance
    saturation = sat
    warmth = r - b                                    # + = hangat, - = dingin

    stats = {
        "brightness": round(brightness, 0),
        "saturation": round(saturation, 0),
        "warmth": round(warmth, 0),
        "top_colors": ["#%02X%02X%02X" % rgb for _, rgb in colors[:4]],
        "color_pct": [round(100 * c / total) for c, _ in colors[:4]],
    }

    # Pohon keputusan sederhana
    if brightness < 85 and saturation < 90:
        genres = ["Mystery", "Thriller", "Horror"]
        label = "Gelap & misterius"
    elif brightness < 85:
        genres = ["Thriller", "Crime", "Action"]
        label = "Gelap tapi penuh warna (neo-noir)"
    elif brightness > 170 and saturation > 110:
        genres = ["Animation", "Comedy", "Family"]
        label = "Cerah & ceria"
    elif warmth > 25 and saturation >= 60:
        genres = ["Romance", "Drama", "Action"]
        label = "Hangat & emosional"
    elif warmth < -20 and saturation >= 50:
        genres = ["Science Fiction", "Adventure", "Fantasy"]
        label = "Dingin & futuristik"
    elif saturation < 45:
        genres = ["Drama", "History", "Romance"]
        label = "Lembut & tenang"
    else:
        genres = ["Adventure", "Comedy", "Drama"]
        label = "Seimbang & natural"

    explanation = (
        f"Foto memiliki kecerahan {stats['brightness']:.0f}/255, saturasi {stats['saturation']:.0f}, "
        f"dan suhu warna {stats['warmth']:.0f} (hangat jika positif). "
        f"Pohon keputusan mengklasifikasikannya sebagai \"{label}\" -> genre [{', '.join(genres)}]."
    )
    return {"label": label, "genres": genres, "stats": stats, "explanation": explanation}


# ----------------------------------------------------------------------------
# Rekomendasi dari foto
# ----------------------------------------------------------------------------
def recommend_from_photo(path, engine):
    """Membaca foto, lalu menghasilkan rekomendasi film."""
    text = read_text(path)
    colors = dominant_colors(path)
    analysis = analyze_colors(colors)

    result = {
        "ocr_text": text[:300],
        "analysis": analysis,
        "matched_movie": None,
        "movies": [],
    }

    # 1) Coba cocokkan teks OCR dengan judul film
    matched = None
    if text:
        matched, score = engine.find_title(text)

    if matched:
        recs = engine.similar_to(matched, limit=5)
        result["matched_movie"] = matched.to_dict()
        result["movies"] = [
            dict(m.to_dict(),
                 reason=engine.movie_reason("id", m, "similar", target=matched),
                 description=engine.movie_description(m, "id"))
            for m in recs
        ]
        return result

    # 2) Tidak ada judul: gunakan mood warna + kata kunci OCR (jika ada)
    mood_genres = analysis["genres"]
    keywords = []
    if text:
        # kata kunci bermakna dari OCR
        keywords = [t for t in tokenize(text) if len(t) >= 4]
        ocr_movies = engine.semantic_search(" ".join(keywords), limit=8) if keywords else []
    else:
        ocr_movies = []

    mood_movies = engine.constraint_search(genres=mood_genres, limit=8)

    # Gabungkan: mood dulu, lalu sisipkan hasil OCR yang relevan (tanpa duplikat)
    merged = []
    seen = set()
    ocr_ids = {m.id for m in ocr_movies}
    for mv in mood_movies + ocr_movies:
        if mv.id not in seen:
            seen.add(mv.id)
            merged.append(mv)
    movie_list = []
    for mv in merged[:5]:
        d = mv.to_dict()
        if mv.id in ocr_ids and keywords:
            d["reason"] = engine.movie_reason("id", mv, "semantic", query=" ".join(keywords)[:48])
        else:
            d["reason"] = engine.movie_reason("id", mv, "constraint", genres=mood_genres)
        d["description"] = engine.movie_description(mv, "id")
        movie_list.append(d)
    result["movies"] = movie_list
    return result


# ----------------------------------------------------------------------------
# Validasi file gambar
# ----------------------------------------------------------------------------
IMAGE_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # perlu cek WEBP
    b"BM": "image/bmp",
}


def sniff_image(data):
    """Deteksi tipe gambar dari magic bytes."""
    for magic, mime in IMAGE_MAGIC.items():
        if data.startswith(magic):
            if mime == "image/webp":
                if data[8:12] == b"WEBP":
                    return mime
                continue
            return mime
    return None


def save_temp(data):
    fd, path = tempfile.mkstemp(suffix=".img", prefix="cinechat_")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def analyze_photo(data, engine):
    """Endpoint lengkap: validasi -> simpan -> baca -> rekomendasi. Selalu bersihkan."""
    mime = sniff_image(data)
    if not mime:
        return {"error": "Format gambar tidak didukung. Gunakan JPEG, PNG, GIF, WebP, atau BMP."}
    path = save_temp(data)
    try:
        result = recommend_from_photo(path, engine)
        result["image_type"] = mime
        result["size_kb"] = round(len(data) / 1024, 1)
        return result
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    import sys
    from engine import MovieEngine
    eng = MovieEngine()
    if len(sys.argv) < 2:
        print("pemakaian: python vision.py <file_gambar>")
        sys.exit(1)
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    res = analyze_photo(data, eng)
    print("OCR :", res.get("ocr_text"))
    print("Mood:", res.get("analysis", {}).get("label"), res.get("analysis", {}).get("genres"))
    for mv in res.get("movies", [])[:5]:
        print(" -", mv["title"], "|", mv["year"], "|", mv["rating"], "|", mv["genres"])
        print("   why:", mv.get("reason", ""))
