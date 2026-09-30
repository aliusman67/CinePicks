# -*- coding: utf-8 -*-
"""
CineChat AI - Mesin pencarian, penalaran (reasoning), dan pengambilan keputusan film.

Semua diimplementasikan dengan Python standard library (tanpa numpy/sklearn):
  - SEARCHING  : inverted index + BM25 (Okapi BM25) untuk pencarian semantik judul/sinopsis/genre.
  - REASONING  : intent parser berbasis aturan (rule-based NLP) + knowledge base genre/mood.
  - DECISION   : multi-criteria scoring = relevansi + rating + log(votes) + log(popularitas) + kebaruan.
"""
import csv
import math
import os
import random
import re
import difflib
from collections import Counter

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Top Movies dataset.csv")

# ----------------------------------------------------------------------------
# Kosakata & knowledge base
# ----------------------------------------------------------------------------
STOPWORDS = set("""
a an and are as at be but by for from has have i if in into is it its of on or that the to was were will with
yang dan di ke dari untuk dengan pada tidak ini itu juga atau agar supaya karena jadi bila jika sambil hingga
serta tapi tetapi saat sebut para bagi tanpa demi kita kamu mereka dia kalian anda saya kami ialah merupakan
film filmnya mau cari tolong dong kak bang rekomendasi rekomendasiin recommend recommendation please give me
show some want wanna looking for search watch
""".split())

# keyword -> genre dataset
GENRE_KEYWORDS = {
    "science fiction": ["Science Fiction"], "sci-fi": ["Science Fiction"], "scifi": ["Science Fiction"],
    "sci fi": ["Science Fiction"], "fiksi ilmiah": ["Science Fiction"], "luar angkasa": ["Science Fiction"],
    "space": ["Science Fiction"], "alam semesta": ["Science Fiction"],
    "action": ["Action"], "aksi": ["Action"], "laga": ["Action"],
    "adventure": ["Adventure"], "petualangan": ["Adventure"],
    "animation": ["Animation"], "animasi": ["Animation"], "kartun": ["Animation"], "cartoon": ["Animation"],
    "anime": ["Animation"],
    "comedy": ["Comedy"], "komedi": ["Comedy"], "lucu": ["Comedy"], "funny": ["Comedy"], "humor": ["Comedy"],
    "ngakak": ["Comedy"], "kocak": ["Comedy"], "lawak": ["Comedy"],
    "crime": ["Crime"], "kriminal": ["Crime"],
    "documentary": ["Documentary"], "dokumenter": ["Documentary"],
    "drama": ["Drama"],
    "family": ["Family"], "keluarga": ["Family"],
    "anak": ["Family", "Animation"], "anak-anak": ["Family", "Animation"], "anak anak": ["Family", "Animation"],
    "kids": ["Family", "Animation"], "child": ["Family"], "children": ["Family"],
    "bocah": ["Family", "Animation"], "balita": ["Family", "Animation"],
    "superhero": ["Action", "Adventure"], "super hero": ["Action", "Adventure"],
    "pahlawan super": ["Action", "Adventure"], "marvel": ["Action", "Adventure", "Science Fiction"],
    "fantasy": ["Fantasy"], "fantasi": ["Fantasy"],
    "history": ["History"], "sejarah": ["History"], "biopik": ["History"], "biopic": ["History"],
    "horror": ["Horror"], "horor": ["Horror"], "seram": ["Horror"], "scary": ["Horror"],
    "menakutkan": ["Horror"], "hantu": ["Horror"],
    "music": ["Music"], "musik": ["Music"], "musical": ["Music"], "musikal": ["Music"],
    "mystery": ["Mystery"], "misteri": ["Mystery"], "teka-teki": ["Mystery"], "teka teki": ["Mystery"],
    "romance": ["Romance"], "romantis": ["Romance"], "cinta": ["Romance"], "percintaan": ["Romance"],
    "romantic": ["Romance"],
    "thriller": ["Thriller"], "menegangkan": ["Thriller"], "tegang": ["Thriller"], "suspense": ["Thriller"],
    "war": ["War"], "perang": ["War"],
    "western": ["Western"], "koboi": ["Western"],
    "pendidikan": ["Documentary", "History", "Drama", "Family"],
    "edukasi": ["Documentary", "History", "Drama", "Family"],
    "edukatif": ["Documentary", "History", "Drama", "Family"],
    "education": ["Documentary", "History", "Drama", "Family"],
    "educational": ["Documentary", "History", "Drama", "Family"],
    "belajar": ["Documentary", "History", "Drama", "Family"],
    "sekolah": ["Documentary", "History", "Drama", "Family"],
    "kuliah": ["Documentary", "History", "Drama"],
    "biografi": ["History", "Documentary", "Drama"], "biography": ["History", "Documentary", "Drama"],
    "fakta": ["Documentary", "History"], "dokumenter": ["Documentary"], "dokumentasi": ["Documentary"],
    "zombie": ["Horror"], "zombi": ["Horror"], "vampir": ["Horror"], "vampire": ["Horror"], "ghost": ["Horror"],
    "dinosaurus": ["Adventure", "Family", "Animation"], "dinosaur": ["Adventure", "Family", "Animation"],
    "detektif": ["Mystery", "Crime"], "detective": ["Mystery", "Crime"],
    "robot": ["Science Fiction"], "alien": ["Science Fiction"], "waktu": ["Science Fiction"],
    "time travel": ["Science Fiction"], "kisah nyata": ["History", "Drama"], "true story": ["History", "Drama"],
}

# keyword mood -> genre prioritas
MOOD_KEYWORDS = {
    "sedih": ["Drama", "Romance"], "sad": ["Drama", "Romance"], "galau": ["Drama", "Romance"],
    "menangis": ["Drama", "Romance"], "cry": ["Drama", "Romance"], "haru": ["Drama"],
    "mengharukan": ["Drama"],
    "lucu": ["Comedy", "Animation", "Family"], "funny": ["Comedy", "Animation"],
    "ceria": ["Comedy", "Animation", "Family"], "happy": ["Comedy", "Animation", "Family"],
    "seram": ["Horror", "Thriller", "Mystery"], "horor": ["Horror", "Thriller"], "takut": ["Horror", "Thriller"],
    "scary": ["Horror", "Thriller"], "mencekam": ["Thriller", "Horror"],
    "menegangkan": ["Thriller", "Action"], "thrilling": ["Thriller", "Action"],
    "romantis": ["Romance", "Drama"], "romantic": ["Romance", "Drama"],
    "epik": ["Action", "Adventure", "Fantasy"], "epic": ["Action", "Adventure", "Fantasy"],
    "misterius": ["Mystery", "Thriller"], "mysterious": ["Mystery", "Thriller"],
    "inspiratif": ["Drama", "History"], "motivasi": ["Drama", "History"], "inspiring": ["Drama", "History"],
    "petualang": ["Adventure", "Fantasy"], "adventure": ["Adventure"],
}

# Penanda bahasa Indonesia
ID_MARKERS = {
    "film", "yang", "dengan", "untuk", "rekomendasi", "terbaik", "terbaru", "saya", "mau", "cari",
    "sedih", "seram", "lucu", "tahun", "dan", "atau", "filmnya", "dong", "kak", "bang", "tolong",
    "rekomendasiin", "tonton", "nonton", "pilih", "kapan", "apa", "kenapa", "bagaimana",
    "mirip", "seperti", "kayak", "sejenis", "serupa", "tentang", "sinopsis",
    "halo", "hai", "hallo", "hei", "pagi", "siang", "sore", "malam", "makasih", "terima", "kasih", "bantuan",
    "pendidikan", "edukasi", "edukatif", "belajar", "sekolah", "kuliah", "biografi", "fakta", "dokumenter",
    "indonesia", "indo", "korea", "korsel", "jepang", "japan", "drakor", "bollywood", "tiongkok",
    "anak", "anakanak", "superhero", "pahlawan", "marvel", "keluarga",
}

# keyword negara -> kode bahasa dataset
COUNTRY_KEYWORDS = {
    "indonesia": "id", "indo": "id",
    "korea": "ko", "korean": "ko", "korsel": "ko", "drakor": "ko",
    "jepang": "ja", "japan": "ja", "japanese": "ja",
    "india": "hi", "bollywood": "hi",
    "china": "zh", "chinese": "zh", "tiongkok": "zh", "mandarin": "zh", "cina": "zh",
    "prancis": "fr", "france": "fr", "french": "fr",
    "spanyol": "es", "spanish": "es",
    "inggris": "en", "british": "en", "amerika": "en", "hollywood": "en", "american": "en",
}
COUNTRY_NAMES = {
    "id": "Indonesia", "ko": "Korea Selatan", "ja": "Jepang", "hi": "India",
    "zh": "China", "fr": "Prancis", "es": "Spanyol", "en": "Amerika/Inggris",
}

# Deskripsi naratif bahasa Indonesia untuk film Indonesia di dataset
MOVIE_DESCRIPTIONS_ID = {
    "photocopier": "Drama misteri yang mengangkat isu sosial: seorang mahasiswi kehilangan beasiswanya "
                   "setelah foto-fotonya di sebuah pesta tersebar, lalu ia berusaha mengungkap kebenaran "
                   "di balik insiden tersebut. Dipuji kritikus karena relevan dengan isu kekerasan seksual.",
    "mariposa": "Drama romantis remaja: murid baru Acha jatuh cinta pada Iqbal, siswa berprestasi yang "
                "dingin dan sulit didekati, lalu berusaha sekuat tenaga merebut hatinya.",
    "theraid2": "Sekuel film aksi legendaris The Raid: Rama menyamar masuk ke sindikat kriminal Jakarta "
                "untuk membongkar korupsi di kepolisian, dengan koreografi pertarungan yang brutal dan memukau.",
    "aperfectfit": "Komedi romantis: seorang blogger mode di Bali bertemu perajin sepatu berbakat, "
                   "dan percikan asmara pun muncul di antara mereka.",
    "headshot": "Film aksi-thriller: seorang pria yang kehilangan ingatan terbangun di tepi pantai "
                "dan harus menghadapi masa lalunya yang kelam serta orang-orang yang memburunya.",
    "theraid": "Film aksi legendaris Indonesia: satu tim polisi terjebak di gedung markas gembong narkoba "
               "di jantung Jakarta dan harus bertahan hidup lantai demi lantai.",
    "toohandsometohandle": "Komedi romantis: pemuda yang terlalu tampan memilih mengurung diri, "
                           "namun akhirnya setuju bersekolah dan menghadapi kekacauan asmara.",
    "thenightcomesforus": "Aksi kriminal berdarah: seorang algojo triad berbalik melindungi nyawa "
                          "seorang gadis dan harus bertahan dari kejaran seluruh organisasinya.",
    "madumurni": "Drama komedi tentang pernikahan muda, mimpi, dan konflik keluarga.",
    "sabrina": "Horor thriller tentang boneka terkutuk dan teror gaib yang mengancam sebuah keluarga.",
    "jakartacityofdreamers": "Drama tentang perjuangan seorang pemuda mengejar mimpinya menjadi aktor "
                             "di tengah kerasnya kota Jakarta.",
    "narutobersyukur": "Film pendek drama adaptasi cerpen Pidi Baiq tentang rasa syukur dan makna hidup.",
    "satansslaves": "Horor yang dikenal juga sebagai Pengabdi Setan: setelah ibunya meninggal, "
                    "keluarga Rini diteror oleh sesuatu yang jahat dari masa lalu.",
    "beforeimetyou": "Drama romantis: Gadis, seorang perempuan muda di tengah hiruk pikuk Jakarta, "
                     "mencari cinta dan jati diri.",
    "impetigore": "Horor misteri: seorang perempuan mewarisi rumah di desa leluhurnya tanpa menyadari "
                  "ancaman mengerikan yang menantinya di sana.",
}

# Pola intent
RE_SIMILAR = re.compile(
    r"(?:film\s+)?(?:yang\s+)?(?:mirip|seperti|kayak|sejenis|serupa|similar(?:\s+to)?|like)\s+(.+)",
    re.IGNORECASE,
)
RE_YEAR = re.compile(r"\b(19[3-9]\d|20[0-9]\d)\b")


# ----------------------------------------------------------------------------
# Struktur data film
# ----------------------------------------------------------------------------
class Movie:
    __slots__ = ("id", "title", "norm_title", "overview", "genres", "popularity",
                 "votes", "rating", "year", "language", "poster")

    def __init__(self, idx, row):
        self.id = idx
        self.title = (row.get("Title") or "").strip()
        self.norm_title = normalize(self.title)
        self.overview = (row.get("Overview") or "").strip()
        self.genres = [g.strip() for g in (row.get("Genre") or "").split(",") if g.strip()]
        self.popularity = to_float(row.get("Popularity"))
        self.votes = to_int(row.get("Vote_Count"))
        self.rating = to_float(row.get("Vote_Average"))
        self.year = parse_year(row.get("Release_Date"))
        self.language = (row.get("Original_Language") or "").strip()
        self.poster = (row.get("Poster_Url") or "").strip()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year or 0,
            "rating": round(self.rating, 1),
            "votes": self.votes,
            "genres": self.genres[:3],
            "overview": (self.overview[:240] + "…") if len(self.overview) > 240 else self.overview,
            "poster": self.poster,
            "popularity": round(self.popularity, 1),
        }


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def parse_year(date_str):
    if not date_str:
        return 0
    m = re.search(r"(19|20)\d{2}", str(date_str))
    return int(m.group(0)) if m else 0


def normalize(text):
    """Normalisasi teks: huruf kecil + hanya alfanumerik."""
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def tokenize(text):
    """Tokenisasi sederhana + buang stopword."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


# ----------------------------------------------------------------------------
# Mesin utama
# ----------------------------------------------------------------------------
class MovieEngine:
    def __init__(self, csv_path=CSV_PATH):
        self.movies = []
        self.postings = {}       # term -> {doc_id: tf}
        self.doc_len = []        # panjang dokumen (jumlah token berbobot)
        self.avgdl = 1.0
        self.title_tokens = {}   # token -> [doc_id] (untuk pencocokan judul cepat)
        self.max_log_pop = 1.0
        self.max_log_votes = 1.0
        self._load(csv_path)
        self._build_index()

    # ------------------------------------------------------------------ load
    def _load(self, csv_path):
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            for idx, row in enumerate(csv.DictReader(f)):
                self.movies.append(Movie(idx, row))
        for m in self.movies:
            for t in tokenize(m.title):
                self.title_tokens.setdefault(t, []).append(m.id)
            self.max_log_pop = max(self.max_log_pop, math.log1p(m.popularity))
            self.max_log_votes = max(self.max_log_votes, math.log1p(m.votes))
        if not self.movies:
            raise RuntimeError("Dataset kosong: " + csv_path)

    # ------------------------------------------------------------ index BM25
    def _build_index(self):
        """Bangun inverted index dengan bobot: judul x3, genre x2, sinopsis x1."""
        for m in self.movies:
            tf = Counter()
            for t in tokenize(m.title):
                tf[t] += 3
            for g in m.genres:
                for t in tokenize(g):
                    tf[t] += 2
            for t in tokenize(m.overview):
                tf[t] += 1
            length = sum(tf.values())
            self.doc_len.append(length)
            for term, count in tf.items():
                self.postings.setdefault(term, {})[m.id] = count
        self.avgdl = sum(self.doc_len) / max(1, len(self.doc_len))

    def _idf(self, term):
        df = len(self.postings.get(term, ()))
        n = len(self.movies)
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def bm25_search(self, query_text, limit=60, k1=1.5, b=0.75):
        """SEARCHING: Okapi BM25 terhadap judul + genre + sinopsis."""
        q_terms = tokenize(query_text)
        if not q_terms:
            return []
        q_tf = Counter(q_terms)
        scores = {}
        for term in q_tf:
            idf = self._idf(term)
            if idf <= 0:
                continue
            for doc_id, tf in self.postings.get(term, {}).items():
                dl = self.doc_len[doc_id]
                denom = tf + k1 * (1.0 - b + b * dl / self.avgdl)
                scores[doc_id] = scores.get(doc_id, 0.0) + idf * tf * (k1 + 1.0) / denom * q_tf[term]
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:limit]
        return ranked  # [(doc_id, bm25)]

    # ------------------------------------------------------------ kualitas
    def quality_score(self, m, prefer_new=False):
        """DECISION: skor kualitas film (0..1)."""
        rating = m.rating / 10.0 if m.rating else 0.0
        votes = math.log1p(m.votes) / self.max_log_votes if m.votes else 0.0
        pop = math.log1p(m.popularity) / self.max_log_pop if m.popularity else 0.0
        recency = 0.0
        if prefer_new and m.year:
            recency = max(0.0, (m.year - 1980) / 50.0)
        return 0.40 * rating + 0.25 * votes + 0.20 * pop + 0.15 * recency

    def _rank(self, candidates, prefer_new=False, with_relevance=None):
        """Gabungkan relevansi pencarian + skor kualitas (pengambilan keputusan)."""
        if with_relevance:
            max_rel = max((r for _, r in with_relevance), default=1.0)
            rel_map = {doc_id: rel / max(1e-9, max_rel) for doc_id, rel in with_relevance}
            scored = []
            for doc_id in candidates:
                m = self.movies[doc_id]
                final = 0.55 * rel_map.get(doc_id, 0.0) + 0.45 * self.quality_score(m, prefer_new)
                scored.append((final, doc_id))
        else:
            scored = [(self.quality_score(self.movies[i], prefer_new), i) for i in candidates]
        scored.sort(reverse=True)
        return [self.movies[i] for _, i in scored]

    # ------------------------------------------------------------ pencarian judul
    def find_title(self, text, min_len=4):
        """Cari judul film di dalam teks (substring -> fuzzy fallback)."""
        q = normalize(text)
        if len(q) < min_len:
            return None, 0.0
        # 1) Pencocokan substring langsung (C-level, cepat)
        best, best_score = None, 0.0
        for m in self.movies:
            nt = m.norm_title
            if len(nt) < min_len:
                continue
            if nt in q or q in nt:
                score = len(nt) / max(len(q), 1)
                if score > best_score:
                    best, best_score = m, score
        if best and best_score >= 0.5:
            return best, best_score
        # 2) Fallback fuzzy: kandidat dari token bersama + SequenceMatcher
        q_tokens = {t for t in tokenize(text) if len(t) >= 4}
        if q_tokens:
            cand = Counter()
            for t in q_tokens:
                for doc_id in self.title_tokens.get(t, ()):
                    cand[doc_id] += 1
            for doc_id, overlap in cand.most_common(10):
                nt = self.movies[doc_id].norm_title
                if len(nt) < min_len:
                    continue
                # Guard: query lebih panjang dari judul berarti user kemungkinan
                # menyebut kata tematik ("film zombie"), bukan judul "G-Zombie".
                if len(q) > len(nt) + 2:
                    continue
                ratio = difflib.SequenceMatcher(None, q, nt).ratio()
                score = ratio + 0.08 * min(overlap, 4)
                if score > best_score:
                    best, best_score = self.movies[doc_id], score
        if best and best_score >= 0.72:
            return best, best_score
        return None, 0.0

    # ------------------------------------------------------------ rekomendasi
    def similar_to(self, movie, genres=None, year=None, limit=5, offset=0):
        """Film serupa: BM25 dari sinopsis judul + bonus genre bersama.

        Filter tambahan (genre/tahun) dilonggarkan satu per satu jika
        membuat hasil kosong, agar tetap ada rekomendasi yang masuk akal.
        """
        query = movie.title + " " + movie.overview
        ranked = self.bm25_search(query, limit=80)
        cand_ids = [i for i, _ in ranked if i != movie.id]
        if not cand_ids:
            cand_ids = [m.id for m in self.movies if m.id != movie.id]
        if genres:
            filtered = [i for i in cand_ids if any(g in self.movies[i].genres for g in genres)]
            if filtered:
                cand_ids = filtered
        if year:
            filtered = [i for i in cand_ids if self.movies[i].year == year]
            if filtered:
                cand_ids = filtered
        # bonus genre bersama
        shared = {m.id: len(set(m.genres) & set(movie.genres)) for m in self.movies}
        max_shared = max(shared.values()) or 1
        scored = []
        rel_map = {i: r for i, r in ranked if i in cand_ids}
        max_rel = max(rel_map.values()) or 1.0
        for i in cand_ids:
            m = self.movies[i]
            rel = rel_map.get(i, 0.0) / max_rel
            genre_bonus = 0.20 * (shared[i] / max_shared)
            final = 0.45 * rel + genre_bonus + 0.35 * self.quality_score(m)
            scored.append((final, i))
        scored.sort(reverse=True)
        return [self.movies[i] for _, i in scored[offset:offset + limit]]

    def constraint_search(self, genres=None, year=None, prefer_best=False, prefer_new=False,
                          countries=None, prefer_popular=False, limit=5, offset=0):
        """REASONING -> DECISION: filter berdasarkan batasan, lalu urutkan.

        Prioritas pengurutan:
          1) jumlah genre yang cocok (semakin banyak semakin relevan),
          2) skor keputusan (rating x log(votes) jika prefer_best,
             popularitas jika prefer_popular, else skor kualitas).
        """
        cand = list(range(len(self.movies)))
        if countries:
            cand = [i for i in cand if self.movies[i].language in countries]
        if genres:
            cand = [i for i in cand if any(g in self.movies[i].genres for g in genres)]
        if year:
            cand = [i for i in cand if self.movies[i].year == year]
        if not cand and countries:
            # relaksasi: jika filter negara membuat kosong, longgarkan negara
            cand = [i for i in range(len(self.movies))]
            if genres:
                cand = [i for i in cand if any(g in self.movies[i].genres for g in genres)]
            if year:
                cand = [i for i in cand if self.movies[i].year == year]
        if not cand and genres:  # relaksasi: jika terlalu ketat, longgarkan tahun
            cand = [i for i in range(len(self.movies)) if any(g in self.movies[i].genres for g in genres)]
        scored = []
        for i in cand:
            m = self.movies[i]
            matched = sum(1 for g in (genres or []) if g in m.genres)
            if prefer_best:
                q = m.rating * math.log1p(m.votes)
            elif prefer_popular:
                q = math.log1p(m.popularity)
            else:
                q = self.quality_score(m, prefer_new)
            scored.append((matched, q, i))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return [self.movies[i] for _, _, i in scored[offset:offset + limit]]

    def semantic_search(self, message, limit=5, offset=0):
        """Pencarian semantik bebas (tanpa batasan eksplisit).

        Jika BM25 tidak menemukan kecocokan, kembalikan daftar kosong —
        lebih jujur daripada merekomendasikan film populer yang tidak relevan.
        """
        ranked = self.bm25_search(message, limit=80)
        if not ranked:
            return []
        return self._rank([i for i, _ in ranked], with_relevance=ranked)[offset:offset + limit]

    # ------------------------------------------------------------ intent
    def _detect_language(self, msg):
        # Token mentah (termasuk stopword seperti "rekomendasi"/"film") agar
        # kata-kata khas bahasa Indonesia tetap terdeteksi.
        tokens = set(re.findall(r"[a-z0-9]+", msg.lower()))
        if tokens & ID_MARKERS:
            return "id"
        return "en"

    def _extract_year(self, msg):
        m = RE_YEAR.search(msg)
        return int(m.group(1)) if m else None

    def _extract_genres(self, msg):
        low = " " + msg.lower() + " "
        found = []
        for kw, genres in sorted(GENRE_KEYWORDS.items(), key=lambda x: -len(x[0])):
            if (" " + kw + " ") in low or low.startswith(kw + " ") or low.endswith(" " + kw):
                for g in genres:
                    if g not in found:
                        found.append(g)
        return found

    def _extract_moods(self, msg):
        low = " " + msg.lower() + " "
        found = []
        for kw, genres in sorted(MOOD_KEYWORDS.items(), key=lambda x: -len(x[0])):
            if (" " + kw + " ") in low or low.startswith(kw + " ") or low.endswith(" " + kw):
                for g in genres:
                    if g not in found:
                        found.append(g)
        return found

    def _extract_country(self, msg):
        """Deteksi preferensi negara, mis. 'film indonesia' -> ['id']."""
        low = " " + msg.lower() + " "
        found = []
        for kw, code in sorted(COUNTRY_KEYWORDS.items(), key=lambda x: -len(x[0])):
            if (" " + kw + " ") in low or low.startswith(kw + " ") or low.endswith(" " + kw):
                if code not in found:
                    found.append(code)
        return found

    # ------------------------------------------------------------ chat utama
    def chat(self, message, page=0):
        message = (message or "").strip()
        if not message:
            return self._reply("id", "Ketik sesuatu dulu ya, misalnya: 'rekomendasi film action terbaik'.", [], "")
        lang = self._detect_language(message)
        low = message.lower()
        offset = max(0, page) * 5

        # Sapaan & bantuan
        if re.match(r"^(halo|hai|hi|hello|hey|hallo|hei|pagi|siang|sore|malam)\b", low):
            return self._reply(lang, self._t(lang, "greeting"), [], self._t(lang, "greet_reason"))
        if re.search(r"\b(help|bantuan|menu|fitur|bisa apa|cara pakai)\b", low):
            return self._reply(lang, self._t(lang, "help"), [], self._t(lang, "help_reason"))
        if re.search(r"\b(thanks|thank you|makasih|terima kasih|thx|tq)\b", low):
            return self._reply(lang, self._t(lang, "thanks"), [], "")

        year = self._extract_year(message)
        genres = self._extract_genres(message)
        moods = self._extract_moods(message)
        all_genres = genres + [g for g in moods if g not in genres]
        countries = self._extract_country(message)
        prefer_best = bool(re.search(r"\b(terbaik|best|top|rating tertinggi|paling bagus|must watch|wajib)\b", low))
        prefer_new = bool(re.search(r"\b(terbaru|baru rilis|new|recent|latest|rilis|up to date)\b", low))
        prefer_popular = bool(re.search(r"\b(trending|populer|popular|sedang ramai|viral|hits|terpopuler)\b", low))
        want_random = bool(re.search(r"\b(random|acak|kejutan|surprise|kaget|rekomendasiin aja|terserah)\b", low))
        has_constraint = bool(all_genres or year or prefer_best or prefer_new or countries or prefer_popular)
        ask_about = bool(re.search(r"\b(tentang|info|sinopsis|apa itu|about|jelaskan|describe)\b", low))

        # Intent "mirip/seperti X" (dicek lebih dulu)
        m_sim = RE_SIMILAR.search(low)

        # 0) Intent "kejutan/acak" -> pilihan film acak berkualitas
        if want_random and not m_sim:
            pool = self._rank(range(len(self.movies)))[:200]
            picks = random.sample(pool, min(5, len(pool)))
            return self._reply(lang, self._t(lang, "surprise"), picks,
                               reasons=self._make_reasons(lang, picks, "constraint"))

        # 1) Intent "mirip/seperti X" -> cari judul target, lalu rekomendasi serupa
        if m_sim:
            target, score = self.find_title(m_sim.group(1))
            if target:
                recs = self.similar_to(target, genres=genres or None, year=year, offset=offset)
                return self._reply(
                    lang,
                    self._t(lang, "similar").format(title=target.title),
                    recs,
                    self._t(lang, "similar_reason").format(title=target.title, n=len(recs)),
                    reasons=self._make_reasons(lang, recs, "similar", genres=genres or None, target=target),
                )

        # 2) Judul eksplisit — hanya dicek jika TIDAK ada preferensi genre/mood/tahun
        #    (agar "best sci-fi space adventure" tidak salah dibaca sebagai judul film),
        #    kecuali user memang bertanya "tentang/about" judul tertentu.
        target = None
        if (not has_constraint) or ask_about:
            target, tscore = self.find_title(message)
        if target and not has_constraint:
            recs = self.similar_to(target)
            return self._reply(
                lang,
                self._t(lang, "about").format(title=target.title, year=target.year or "?",
                                              rating=round(target.rating, 1), genres=", ".join(target.genres[:3])),
                recs,
                self._t(lang, "about_reason").format(title=target.title),
                reasons=self._make_reasons(lang, recs, "about", target=target),
            )
        if target:
            recs = self.similar_to(target, genres=genres or None, year=year)
            return self._reply(
                lang,
                self._t(lang, "similar").format(title=target.title),
                recs,
                self._t(lang, "similar_reason").format(title=target.title, n=len(recs)),
                reasons=self._make_reasons(lang, recs, "similar", genres=genres or None, target=target),
            )

        # 3) Rekomendasi berbasis batasan (genre/mood/tahun/negara/terbaik/terbaru/populer)
        if has_constraint:
            recs = self.constraint_search(genres=all_genres or None, year=year,
                                          prefer_best=prefer_best, prefer_new=prefer_new,
                                          countries=countries or None,
                                          prefer_popular=prefer_popular,
                                          offset=offset)
            if not recs:
                return self._reply(lang, self._t(lang, "no_result"), [],
                                   self._t(lang, "no_result_reason"))
            parts = []
            if countries:
                parts.append(self._t(lang, "reason_country").format(
                    c=", ".join(COUNTRY_NAMES.get(c, c) for c in countries)))
            if all_genres:
                parts.append(self._t(lang, "reason_genre").format(g=", ".join(all_genres[:4])))
            if year:
                parts.append(self._t(lang, "reason_year").format(y=year))
                if all(m.year != year for m in recs):
                    parts.append(self._t(lang, "relax_year").format(y=year))
            if prefer_best:
                parts.append(self._t(lang, "reason_best"))
            if prefer_new:
                parts.append(self._t(lang, "reason_new"))
            if prefer_popular:
                parts.append(self._t(lang, "reason_popular"))
            reason = " ".join(parts) + " " + self._t(lang, "reason_score")
            reply_text = (self._t(lang, "found_country").format(
                c=", ".join(COUNTRY_NAMES.get(c, c) for c in countries))
                if countries else self._t(lang, "found").format(n=len(recs)))
            return self._reply(lang, reply_text, recs, reason,
                               reasons=self._make_reasons(lang, recs, "constraint",
                                                          genres=all_genres or None,
                                                          prefer_best=prefer_best, prefer_new=prefer_new,
                                                          countries=countries or None))

        # 4) Fallback: pencarian semantik BM25
        recs = self.semantic_search(message, offset=offset)
        if not recs:
            return self._reply(lang, self._t(lang, "no_result"), [],
                               self._t(lang, "no_result_reason"))
        reason = self._t(lang, "reason_semantic")
        return self._reply(lang, self._t(lang, "found").format(n=len(recs)), recs, reason,
                           reasons=self._make_reasons(lang, recs, "semantic", query=message))

    # ------------------------------------------------------------ pembangun jawaban
    def _reply(self, lang, text, movies, reasoning=None, reasons=None):
        # Catatan: parameter `reasoning` (alur debug internal) sengaja TIDAK
        # dikirim ke frontend lagi; penjelasan diberikan per-film lewat `reasons`.
        movie_list = []
        for i, m in enumerate(movies):
            d = m.to_dict()
            if reasons and i < len(reasons) and reasons[i]:
                d["reason"] = reasons[i]
            d["description"] = self.movie_description(m, lang)
            movie_list.append(d)
        return {
            "reply": text,
            "movies": movie_list,
            "lang": lang,
        }

    def movie_description(self, m, lang):
        """Deskripsi naratif per film (dijelaskan), untuk ditampilkan di kartu."""
        if lang == "id":
            curated = MOVIE_DESCRIPTIONS_ID.get(m.norm_title)
            if curated:
                return curated
            genre_str = ", ".join(m.genres[:3]).lower() or "drama"
            desc = f"Film {genre_str} tahun {m.year} dengan rating {round(m.rating, 1)} dari {m.votes:,} suara."
            if m.overview:
                desc += " Sinopsis: " + m.overview
            return desc
        genre_str = ", ".join(m.genres[:3]) or "drama"
        desc = f"A {genre_str} movie from {m.year}, rated {round(m.rating, 1)} ({m.votes:,} votes)."
        if m.overview:
            desc += " Synopsis: " + m.overview
        return desc

    def movie_reason(self, lang, m, mode, genres=None, target=None, query=None,
                     prefer_best=False, prefer_new=False, countries=None):
        """Alasan personal kenapa film ini direkomendasikan (per kartu)."""
        parts = []
        if countries and m.language in countries:
            parts.append(self._t(lang, "why_country").format(c=COUNTRY_NAMES.get(m.language, m.language)))
        if genres:
            matched = [g for g in genres if g in m.genres]
            if matched:
                parts.append(self._t(lang, "why_genre").format(g=", ".join(matched[:3])))
        if mode in ("similar", "about") and target is not None:
            shared = sorted(set(m.genres) & set(target.genres))
            if shared:
                parts.append(self._t(lang, "why_shared").format(g=", ".join(shared[:3]), title=target.title))
        if mode == "semantic" and query:
            parts.append(self._t(lang, "why_keyword").format(q=query[:48]))
        if prefer_best and m.rating:
            parts.append(self._t(lang, "why_best").format(r=round(m.rating, 1), v=f"{m.votes:,}"))
        elif m.rating:
            parts.append(self._t(lang, "why_rating").format(r=round(m.rating, 1), v=f"{m.votes:,}"))
        if prefer_new and m.year:
            parts.append(self._t(lang, "why_new").format(y=m.year))
        if not parts:
            parts.append(self._t(lang, "why_popular"))
        return " • ".join(parts[:3])

    def _make_reasons(self, lang, movies, mode, genres=None, target=None, query=None,
                      prefer_best=False, prefer_new=False, countries=None):
        return [self.movie_reason(lang, m, mode, genres=genres, target=target, query=query,
                                  prefer_best=prefer_best, prefer_new=prefer_new,
                                  countries=countries) for m in movies]

    def _t(self, lang, key):
        T = {
            "greeting": {
                "id": "Halo! Saya CineChat AI, asisten rekomendasi film dari 9.800+ judul. "
                      "Kamu bisa tanya seperti:\n• 'rekomendasi film action terbaik'\n• 'film sedih romantis'\n• 'mirip Interstellar'\n• atau unggah foto poster untuk dianalisis.",
                "en": "Hi! I'm CineChat AI, a movie recommendation assistant built from 9,800+ titles. "
                      "Try:\n- 'best action movies'\n- 'sad romantic movies'\n- 'similar to Interstellar'\n- or upload a poster photo for analysis.",
            },
            "help": {
                "id": "Fitur saya:\n1. Chat rekomendasi berdasarkan genre, mood, tahun, atau judul.\n2. Upload foto (poster/screenshot) -> saya baca teksnya (OCR) dan warna dominannya, lalu beri rekomendasi.\nContoh: 'film horor terbaik tahun 2022' atau 'film mirip The Batman'.",
                "en": "Features:\n1. Chat recommendations by genre, mood, year, or title.\n2. Upload a photo (poster/screenshot) -> I read its text (OCR) and dominant colors, then recommend movies.\nExample: 'best horror movies of 2022' or 'movies similar to The Batman'.",
            },
            "thanks": {
                "id": "Sama-sama! Selamat menonton. Mau rekomendasi genre lain?",
                "en": "You're welcome! Enjoy your movie. Want another genre?",
            },
            "similar": {
                "id": "Kalau kamu suka \"{title}\", 5 film ini punya genre/sinopsis serupa:",
                "en": "If you liked \"{title}\", these 5 movies share similar genre/plot:",
            },
            "similar_reason": {
                "id": "REASONING: mendeteksi judul \"{title}\" -> mencari film dengan genre bersama + kemiripan sinopsis (BM25) -> mengurutkan {n} kandidat dengan skor gabungan.",
                "en": "REASONING: detected title \"{title}\" -> searched shared genres + plot similarity (BM25) -> ranked {n} candidates by blended score.",
            },
            "about": {
                "id": "\"{title}\" ({year}) - rating {rating}, genre: {genres}. Ini film serupa yang mungkin kamu suka:",
                "en": "\"{title}\" ({year}) - rated {rating}, genres: {genres}. Here are similar movies you may like:",
            },
            "about_reason": {
                "id": "REASONING: judul \"{title}\" ditemukan lewat pencocokan judul -> rekomendasi diambil dari kemiripan sinopsis (BM25) + genre bersama.",
                "en": "REASONING: title \"{title}\" matched via title lookup -> recommendations from plot similarity (BM25) + shared genres.",
            },
            "found": {
                "id": "Ini rekomendasi saya (diurutkan berdasarkan skor keputusan):",
                "en": "Here are my recommendations (ranked by decision score):",
            },
            "found_country": {
                "id": "Ini rekomendasi film {c} pilihan saya, lengkap dengan alasan dan deskripsinya:",
                "en": "Here are my {c} movie picks with reasons and descriptions:",
            },
            "reason_genre": {
                "id": "REASONING: terdeteksi preferensi genre [{g}] -> penyaringan 9.837 film.",
                "en": "REASONING: detected genre preference [{g}] -> filtered 9,837 movies.",
            },
            "reason_year": {
                "id": "Filter tahun {y}.",
                "en": "Filtered by year {y}.",
            },
            "reason_best": {
                "id": "Prioritas 'terbaik' -> diurutkan berdasarkan rating x log(jumlah vote).",
                "en": "Priority 'best' -> sorted by rating x log(vote count).",
            },
            "reason_new": {
                "id": "Prioritas film terbaru -> bonus skor kebaruan.",
                "en": "Priority recent -> recency bonus applied.",
            },
            "reason_popular": {
                "id": "Diurutkan berdasarkan popularitas (log popularity).",
                "en": "Ranked by popularity (log popularity).",
            },
            "surprise": {
                "id": "Ini pilihan kejutan untukmu — film-film berkualitas yang mungkin belum kamu tonton:",
                "en": "Here's a surprise pick for you — quality movies you may not have watched:",
            },
            "reason_score": {
                "id": "DECISION: skor akhir = 0.40*rating + 0.25*log(votes) + 0.20*log(popularitas) + 0.15*kebaruan.",
                "en": "DECISION: final score = 0.40*rating + 0.25*log(votes) + 0.20*log(popularity) + 0.15*recency.",
            },
            "why_genre": {
                "id": "Cocok dengan genre [{g}]",
                "en": "Matches genre [{g}]",
            },
            "why_shared": {
                "id": "Berbagi genre [{g}] dengan \"{title}\"",
                "en": "Shares genres [{g}] with \"{title}\"",
            },
            "why_keyword": {
                "id": "Sinopsisnya relevan dengan kata kunci \"{q}\"",
                "en": "Plot relevant to keywords \"{q}\"",
            },
            "why_best": {
                "id": "Rating {r} termasuk tertinggi dengan {v} suara",
                "en": "Rating {r} among the highest with {v} votes",
            },
            "why_rating": {
                "id": "Rating {r} dari {v} suara",
                "en": "Rated {r} from {v} votes",
            },
            "why_new": {
                "id": "Rilis {y} (terbaru)",
                "en": "Released {y} (recent)",
            },
            "why_popular": {
                "id": "Populer di dataset",
                "en": "Popular in the dataset",
            },
            "why_country": {
                "id": "Film {c}",
                "en": "{c} movie",
            },
            "reason_country": {
                "id": "Filter negara: {c}.",
                "en": "Country filter: {c}.",
            },
            "reason_semantic": {
                "id": "REASONING: tidak ada batasan eksplisit -> SEARCHING BM25 pada judul+sinopsis+genre -> DECISION: gabungkan relevansi (55%) dengan skor kualitas (45%).",
                "en": "REASONING: no explicit constraint -> BM25 SEARCH on title+overview+genre -> DECISION: blended relevance (55%) with quality score (45%).",
            },
            "no_result": {
                "id": "Maaf, saya tidak menemukan film yang cocok untuk pencarian itu. "
                      "Coba sebutkan genre (action, horor, komedi, dokumenter/pendidikan), "
                      "mood (sedih, seram, lucu), tahun rilis, atau judul film.",
                "en": "Sorry, I couldn't find movies matching that search. "
                      "Try mentioning a genre (action, horror, comedy, documentary/educational), "
                      "a mood (sad, scary, funny), a release year, or a movie title.",
            },
            "no_result_reason": {
                "id": "REASONING: pencarian BM25 tidak menghasilkan kecocokan yang cukup kuat, "
                      "sehingga sistem menahan diri untuk tidak merekomendasikan film populer yang tidak relevan.",
                "en": "REASONING: BM25 search produced no strong matches, "
                      "so the system avoided recommending irrelevant popular movies.",
            },
            "relax_year": {
                "id": "Catatan: tidak ada film genre tersebut di tahun {y}, jadi filter tahun dilonggarkan.",
                "en": "Note: no such movie exists in {y}, so the year filter was relaxed.",
            },
        }
        return T.get(key, {}).get(lang, T.get(key, {}).get("id", ""))


# ----------------------------------------------------------------------------
# Singleton
# ----------------------------------------------------------------------------
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = MovieEngine()
    return _engine


if __name__ == "__main__":
    e = MovieEngine()
    print("Dataset dimuat:", len(e.movies), "film | kosakata:", len(e.postings))
    for q in ["rekomendasi film action terbaik", "film sedih romantis", "mirip Interstellar",
              "horor terbaik tahun 2022", "best sci-fi space adventure",
              "rekomendasi film pendidikan", "film edukasi anak", "film zombie"]:
        print("\nQ:", q)
        r = e.chat(q)
        print("A:", r["reply"][:120])
        for mv in r["movies"][:3]:
            print("  -", mv["title"], "|", mv["year"], "|", mv["rating"], "|", mv["genres"])
            print("    why:", mv.get("reason", ""))
