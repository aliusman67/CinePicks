# -*- coding: utf-8 -*-
"""Unit test untuk MovieEngine: pencarian, intent, reasoning, dan pengambilan keputusan."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import MovieEngine, tokenize, normalize  # noqa: E402


class TestEngineBasics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = MovieEngine()

    def test_dataset_loaded(self):
        self.assertGreater(len(self.engine.movies), 9000)
        self.assertGreater(len(self.engine.postings), 10000)

    def test_tokenize_removes_stopwords(self):
        toks = tokenize("film action terbaik")
        self.assertNotIn("film", toks)
        self.assertIn("action", toks)

    def test_normalize(self):
        self.assertEqual(normalize("Spider-Man: No Way Home"), "spidermannowayhome")

    def test_find_title_exact(self):
        m, score = self.engine.find_title("Interstellar")
        self.assertIsNotNone(m)
        self.assertEqual(m.title, "Interstellar")
        self.assertGreater(score, 0.5)

    def test_find_title_guard_short_query(self):
        # "film zombie" boleh cocok dengan judul "Zombie", tetapi TIDAK boleh
        # salah mencocokkan "G-Zombie" (guard fuzzy untuk query lebih panjang dari judul).
        m, _ = self.engine.find_title("film zombie")
        if m is not None:
            self.assertNotEqual(m.title, "G-Zombie")

    def test_find_title_partial(self):
        # "endgame" harus cocok dengan "Avengers: Endgame"
        m, _ = self.engine.find_title("endgame")
        self.assertIsNotNone(m)
        self.assertEqual(m.title, "Avengers: Endgame")

    def test_find_title_ocr_noisy(self):
        # Teks OCR berisik yang hanya memuat kata ENDGAME
        noise = "i~ N ,',@\\\\ > AN W 2\\\\ S50 NS = 4 T W X N Gl %\\\\/ P el 7ag % 2 &3 2 A B W N \" [~ ENDGAME"
        m, score = self.engine.find_title_ocr(noise)
        self.assertIsNotNone(m)
        self.assertEqual(m.title, "Avengers: Endgame")
        self.assertGreater(score, 0.5)

    def test_find_title_embedded_in_long_text(self):
        # Judul lengkap di dalam teks panjang (mis. poster dengan teks tambahan)
        m, _ = self.engine.find_title("MARVEL STUDIOS AVENGERS ENDGAME APRIL 26")
        self.assertIsNotNone(m)
        self.assertEqual(m.title, "Avengers: Endgame")


class TestIntents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = MovieEngine()

    def test_chat_pendidikan_not_action(self):
        r = self.engine.chat("rekomendasi film pendidikan")
        self.assertEqual(r["lang"], "id")
        self.assertTrue(r["movies"])
        top = [m["title"] for m in r["movies"][:3]]
        self.assertNotIn("The Dark Knight", top)
        self.assertNotIn("Spider-Man: No Way Home", top)

    def test_chat_country_indonesia(self):
        r = self.engine.chat("rekomendasi film indonesia")
        self.assertEqual(r["lang"], "id")
        self.assertTrue(r["movies"])
        self.assertIn("Indonesia", r["reply"])
        self.assertIn("Indonesia", r["movies"][0].get("reason", ""))

    def test_chat_zombie_genre_horror(self):
        r = self.engine.chat("film zombie")
        self.assertTrue(r["movies"])
        genres = r["movies"][0].get("genres", [])
        self.assertIn("Horror", genres)

    def test_chat_anak_family(self):
        r = self.engine.chat("rekomendasi film anak")
        self.assertTrue(r["movies"])
        self.assertTrue(any("Family" in m.get("genres", []) or "Animation" in m.get("genres", [])
                            for m in r["movies"][:3]))

    def test_chat_superhero_action(self):
        r = self.engine.chat("film super hero")
        self.assertTrue(r["movies"])
        genres = r["movies"][0].get("genres", [])
        self.assertTrue("Action" in genres or "Adventure" in genres)
        titles = [m["title"] for m in r["movies"][:3]]
        self.assertFalse(any("LEGO" in t for t in titles))

    def test_chat_similar(self):
        r = self.engine.chat("mirip Interstellar")
        self.assertIn("Interstellar", r["reply"])
        self.assertTrue(r["movies"])

    def test_chat_semantic_no_result(self):
        r = self.engine.chat("zzzqqqxxx")
        self.assertEqual(r["movies"], [])

    def test_chat_surprise(self):
        r = self.engine.chat("surprise me")
        self.assertEqual(len(r["movies"]), 5)

    def test_chat_trending(self):
        r = self.engine.chat("film populer")
        self.assertTrue(r["movies"])

    def test_chat_page_pagination(self):
        r0 = self.engine.chat("film action", page=0)
        r1 = self.engine.chat("film action", page=1)
        self.assertTrue(r0["movies"] and r1["movies"])
        self.assertNotEqual(r0["movies"][0]["title"], r1["movies"][0]["title"])

    def test_chat_year_filter(self):
        r = self.engine.chat("film horor tahun 2022")
        self.assertTrue(r["movies"])
        self.assertTrue(all(m["year"] == 2022 for m in r["movies"]))


if __name__ == "__main__":
    unittest.main()
