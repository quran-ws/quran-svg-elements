"""Unit tests for the letter-level decomposition.

    python3 -m unittest tools.tests.test_letters -v

Tests that need the page-50 word SVG or the page-50 tajweed font skip when the
cache is absent.
"""
import os
import unittest

from tools import letters_lib as L

SQUARE = "M0 0L10 0L10 10L0 10Z"
RING = "M0 0L10 0L10 10L0 10ZM3 3L7 3L7 7L3 7Z"          # evenodd hole
P50 = os.path.join(L.WORDS_SVG, "050.svg")


class Geometry(unittest.TestCase):
    def test_flatten_square(self):
        polys = L.flatten(SQUARE)
        self.assertEqual(len(polys), 1)
        self.assertEqual(len(polys[0]), 4)

    def test_parse_relative_and_exponent(self):
        subs = L.parse_d("M1 1c1 0 1 1 1 1l6e-3 0z")
        self.assertEqual(subs[0][1][0], "C")
        self.assertAlmostEqual(subs[0][2][1][0], 2.006, 6)

    def test_area_evenodd(self):
        self.assertAlmostEqual(L.area(L.flatten(SQUARE)), 100, 3)
        self.assertAlmostEqual(L.area(L.flatten(RING)), 84, 3)
        self.assertAlmostEqual(L.area(RING), 84, 3)

    def test_raster_hole(self):
        m = L.raster(L.flatten(RING), 0, 0, 10, 10, 4)
        self.assertTrue(m[4, 4])
        self.assertFalse(m[20, 20])
        self.assertTrue(m[36, 36])

    def test_cut_square_vertical(self):
        pieces = L.cut_run(SQUARE, [[(5, -1), (5, 11)]])
        self.assertEqual(len(pieces), 2)
        a = [L.area(p) for p in pieces]
        self.assertAlmostEqual(sum(a), 100, 1)
        self.assertAlmostEqual(a[0], 50, 1)
        # right piece first
        self.assertGreater(L.bbox(L.flatten(pieces[0]))[0], 4.9)

    def test_cut_two_cuts_ordered_right_to_left(self):
        pieces = L.cut_run(SQUARE, [[(3, -1), (3, 11)], [(7, -1), (7, 11)]])
        self.assertEqual(len(pieces), 3)
        xs = [L.bbox(L.flatten(p))[0] for p in pieces]
        self.assertEqual(xs, sorted(xs, reverse=True))

    def test_cut_polyline_inside_stroke_is_extended(self):
        # the cut is given only INSIDE the ink; the extension reaches the border
        pieces = L.cut_run(SQUARE, [[(5, 2), (5, 8)]])
        self.assertEqual(len(pieces), 2)
        self.assertAlmostEqual(sum(L.area(p) for p in pieces), 100, 1)

    def test_cut_conserves_area_with_hole(self):
        pieces = L.cut_run(RING, [[(5, -1), (5, 11)]])
        self.assertEqual(len(pieces), 2)
        self.assertAlmostEqual(sum(L.area(p) for p in pieces), 84, 1)

    def test_cut_wrong_count_raises(self):
        with self.assertRaises(L.CutError):
            L.cut_run(SQUARE, [[(50, -1), (50, 11)]])

    def test_path_d_roundtrip(self):
        p = L.to_path(RING)
        d = L.path_d(p)
        self.assertAlmostEqual(L.area(d), 84, 3)

    def test_path_d_keeps_curves(self):
        d = "M0 0C1 2 2 2 3 0Q1.5 -2 0 0Z"
        out = L.path_d(L.to_path(d))
        self.assertIn("C", out)
        self.assertIn("Q", out)
        self.assertAlmostEqual(L.area(out), L.area(d), 3)


class Text(unittest.TestCase):
    def test_tables_come_from_the_pipeline(self):
        self.assertEqual(L.HARAKA["َ"], ("fatha", "a"))
        self.assertIn("ا", L.NONJOIN)

    def test_letters_of(self):
        ls = L.letters_of("مُصَدِّقࣰا")
        self.assertEqual([x["ch"] for x in ls], list("مصدقا"))
        self.assertEqual(ls[0]["marks"], ["damma"])
        self.assertIn("shadda", ls[2]["marks"])
        self.assertIn("kasra", ls[2]["marks"])
        self.assertEqual(ls[3]["dots"], "two-dots")
        self.assertEqual(L.runs_of(ls), [[0, 1, 2], [3, 4]])      # د does not join left

    def test_runs_break_after_nonjoiner(self):
        ls = L.letters_of("وَمَن")
        self.assertEqual(L.runs_of(ls), [[0], [1, 2]])
        self.assertEqual(ls[2]["dots"], "dot")

    def test_hamza_carrier_and_final_ya(self):
        ls = L.letters_of("يَـٰٓأَيُّهَا")           # the dagger alef is a mark, not a letter
        self.assertEqual([x["ch"] for x in ls], list("يايها"))
        self.assertIn("hamza", ls[1]["marks"])
        self.assertIn("small-alef", ls[0]["marks"])
        self.assertEqual(ls[2]["dots"], "two-dots")         # medial ya keeps its dots
        ls2 = L.letters_of("فِي")
        self.assertIsNone(ls2[1]["dots"])

    def test_pause_is_word_level(self):
        ls = L.letters_of("ٱلْفُرْقَانَۗ")
        self.assertEqual([x["ch"] for x in ls], list("الفرقان"))
        self.assertEqual(ls[0]["marks"], ["wasla"])

    def test_bare_hamza_is_mark_only(self):
        ls = L.letters_of("يَشَآءُ")
        self.assertFalse(ls[-1]["body"])
        self.assertEqual(L.runs_of(ls)[-1], [len(ls) - 1])


@unittest.skipUnless(os.path.exists(P50), "page-50 word SVG not built")
class Page50(unittest.TestCase):
    def test_read_words(self):
        words, _ = L.read_words(50)
        self.assertGreater(len(words), 120)
        w = [x for x in words if x["wid"] == "3:3:5"][0]
        self.assertEqual([x["ch"] for x in L.letters_of(w["uthmani"])], list("مصدقا"))
        self.assertEqual([l["text"] for l in w["ligatures"]], ["مصد", "قا"])
        self.assertTrue(any(p["kind"] == "body" for p in w["paths"]))

    def test_cut_real_run_vertical(self):
        words, _ = L.read_words(50)
        w = [x for x in words if x["wid"] == "3:3:5"][0]
        d = max((p["d"] for p in w["paths"] if p["kind"] == "body"), key=len)
        x0, y0, x1, y1 = L.bbox(L.flatten(d))
        xm = (x0 + x1) / 2
        pieces = L.cut_run(d, [[(xm, y0 - 1), (xm, y1 + 1)]])
        self.assertEqual(len(pieces), 2)
        self.assertAlmostEqual(sum(L.area(p) for p in pieces), L.area(d), 2)


if __name__ == "__main__":
    unittest.main()
