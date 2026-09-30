# -*- coding: utf-8 -*-
"""Unit test keamanan: multipart parser, path traversal, sniffing gambar, dan validasi input."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import parse_multipart, resolve_static, STATIC_DIR  # noqa: E402
from vision import sniff_image, analyze_colors  # noqa: E402


class TestMultipartParser(unittest.TestCase):
    def _body(self, boundary=b"XBOUND"):
        return (
            b"--XBOUND\r\n"
            b'Content-Disposition: form-data; name="file"; filename="foto.jpg"\r\n'
            b"Content-Type: image/jpeg\r\n\r\n"
            b"\xff\xd8\xff\xd9fakejpeg"
            b"\r\n--XBOUND--\r\n"
        )

    def test_parse_multipart_file(self):
        parts = parse_multipart(self._body(), 'multipart/form-data; boundary="XBOUND"')
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["filename"], "foto.jpg")
        self.assertEqual(parts[0]["content_type"], "image/jpeg")
        self.assertEqual(parts[0]["data"], b"\xff\xd8\xff\xd9fakejpeg")

    def test_parse_multipart_no_boundary(self):
        self.assertEqual(parse_multipart(b"abc", "multipart/form-data"), [])

    def test_parse_multipart_empty(self):
        self.assertEqual(parse_multipart(b"", 'multipart/form-data; boundary="X"'), [])


class TestPathTraversal(unittest.TestCase):
    def test_static_ok(self):
        self.assertIsNotNone(resolve_static("index.html"))

    def test_static_traversal_blocked(self):
        self.assertIsNone(resolve_static("../../../../etc/passwd"))
        self.assertIsNone(resolve_static("/etc/passwd"))

    def test_static_missing_file(self):
        self.assertIsNone(resolve_static("tidak-ada.html"))


class TestImageSniffing(unittest.TestCase):
    def test_sniff_jpeg(self):
        self.assertEqual(sniff_image(b"\xff\xd8\xff\xe0\x00\x10JFIF"), "image/jpeg")

    def test_sniff_png(self):
        self.assertEqual(sniff_image(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8), "image/png")

    def test_sniff_garbage(self):
        self.assertIsNone(sniff_image(b"ini bukan gambar"))

    def test_sniff_webp(self):
        data = b"RIFF\x00\x00\x00\x00WEBPVP8 "
        self.assertEqual(sniff_image(data), "image/webp")


class TestColorMood(unittest.TestCase):
    def test_dark_mood(self):
        colors = [(90, (10, 12, 18)), (10, (30, 32, 40))]
        analysis = analyze_colors(colors)
        self.assertIn("Gelap", analysis["label"])
        self.assertIn("Horror", analysis["genres"])

    def test_bright_mood(self):
        colors = [(60, (250, 220, 120)), (40, (240, 130, 160))]
        analysis = analyze_colors(colors)
        self.assertIn("Cerah", analysis["label"])
        self.assertIn("Animation", analysis["genres"])

    def test_empty_colors_fallback(self):
        analysis = analyze_colors([])
        self.assertEqual(analysis["genres"], ["Drama"])


if __name__ == "__main__":
    unittest.main()
