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

    def test_cut_two_cuts_in_reading_order(self):
        # cuts come in reading order: cut k closes letter k, the rightmost first
        pieces = L.cut_run(SQUARE, [[(7, -1), (7, 11)], [(3, -1), (3, 11)]])
        self.assertEqual(len(pieces), 3)
        xs = [L.bbox(L.flatten(p))[0] for p in pieces]
        self.assertEqual(xs, sorted(xs, reverse=True))
        self.assertAlmostEqual(L.area(pieces[1]), 40, 1)

    def test_cut_side_chosen_by_reference_point(self):
        # a horizontal cut: the piece for letter 0 is whichever side holds its reference
        pieces = L.cut_run(SQUARE, [[(-1, 4), (11, 4)]], refs=[(5, 8)])
        self.assertAlmostEqual(L.area(pieces[0]), 60, 1)
        pieces = L.cut_run(SQUARE, [[(-1, 4), (11, 4)]], refs=[(5, 1)])
        self.assertAlmostEqual(L.area(pieces[0]), 40, 1)

    def test_cut_keeps_only_ink_touching_the_cut(self):
        # a U shape: the cut through the left arm must not take the right arm along
        U = "M0 0L10 0L10 10L8 10L8 2L2 2L2 10L0 10Z"
        pieces = L.cut_run(U, [[(-0.2, 6), (2.2, 6)]], refs=[(1, 9)])
        self.assertEqual(len(pieces), 2)
        self.assertAlmostEqual(L.area(pieces[0]), 8, 0)      # the top of the left arm only

    def test_cut_that_stops_inside_the_ink_is_refused(self):
        with self.assertRaises(L.CutError):
            L.cut_run(SQUARE, [[(5, 2), (5, 8)]])

    def test_cut_leaves_ink_crossed_by_the_extension_alone(self):
        # two bars; the cut through the lower bar's neck must not take the upper bar
        BARS = "M0 0L10 0L10 2L0 2ZM0 5L5 5L5 7L0 7Z"       # the upper bar sits over the LEFT letter
        pieces = L.cut_run(BARS, [[(5, 0), (5, 2)]], refs=[(8, 1), (2, 1)])
        self.assertEqual(len(pieces), 2)
        self.assertAlmostEqual(L.area(pieces[0]), 10, 1)
        self.assertAlmostEqual(L.area(pieces[1]), 20, 1)

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
        self.assertLess(abs(sum(L.area(p) for p in pieces) - L.area(d)), 0.001 * L.area(d))


if __name__ == "__main__":
    unittest.main()


TAJ50 = os.path.join(L.ROOT, ".cache", "tajweed", "fonts", "p50.ttf")
DKFONT = os.path.join(L.ROOT, ".cache", "digitalkhatt", "DigitalKhattV2.otf")


@unittest.skipUnless(os.path.exists(P50) and os.path.exists(TAJ50), "page-50 word SVG or tajweed font missing")
class Tajweed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools import tajweed_lib as T
        cls.T = T
        cls.words, _ = L.read_words(50)
        cls.font = T.PageFont(50)
        cls.scale = T.page_scale(cls.words, cls.font)
        cls.pairs = T.pair_glyphs(cls.words, cls.font, cls.scale)

    def test_scale_is_the_measured_one(self):
        self.assertAlmostEqual(self.scale, 0.00616, 4)

    def test_every_word_registers_exactly(self):
        self.assertEqual(len(self.pairs), len(self.words))
        self.assertTrue(all(p["cov"] >= 0.97 for p in self.pairs.values()))

    def test_lift_cuts_on_qayyum(self):
        T = self.T
        w = [x for x in self.words if x["wid"] == "3:2:7"][0]        # ٱلْقَيُّومُ
        p = self.pairs[w["wid"]]
        tree, _ = L.outline_tree([poly for q in w["paths"] if q["d"] for poly in L.flatten(q["d"])], 0.05)
        lig = [l for l in w["ligatures"] if l["text"] == "لقيو"][0]
        rp = [poly for q in lig["paths"] if q["kind"] == "body" for poly in L.flatten(q["d"])]
        cuts = []
        for name, cid in self.font.layers(p["code"]):
            if self.font.is_letter_layer(cid):
                cuts += T.lift_cuts(self.font.outline_page(name, self.scale, p["tx"], p["ty"]), tree, rp)
        # ي and و are both hand-cut: ق|ي once, ي|و from both layers
        self.assertEqual(len(cuts), 3)
        for c in cuts:
            self.assertTrue(all(L.point_poly_dist(pt, rp) < 0.5 for pt in (c[0], c[-1])))


@unittest.skipUnless(os.path.exists(P50) and os.path.exists(DKFONT), "page-50 word SVG or DK font missing")
class DigitalKhatt(unittest.TestCase):
    def test_shape_bism(self):
        from tools import dk_lib as D
        names = [g[0] for g in D.shape("بِسْمِ")]
        self.assertEqual(len(names), 3)
        self.assertTrue(names[0].startswith("meem") and names[-1].startswith("behshape"))

    def test_letter_glyphs_one_per_letter(self):
        from tools import dk_lib as D
        text = "يَحْزُنكَ"
        letters = L.letters_of(text)
        lg = D.letter_glyphs(text, letters)
        self.assertEqual(len(lg), len(letters))
        self.assertTrue(all(e is not None for e in lg))
        self.assertTrue(lg[1][0].startswith("hah"))

    def test_label_and_neck_on_musaddiqan(self):
        from tools import dk_lib as D
        words, _ = L.read_words(50)
        w = [x for x in words if x["wid"] == "3:3:5"][0]
        letters = L.letters_of(w["uthmani"])
        lg = D.letter_glyphs(w["uthmani"], letters)
        lig = [l for l in w["ligatures"] if l["text"] == "مصد"][0]
        rp = [poly for q in lig["paths"] if q["kind"] == "body" for poly in L.flatten(q["d"])]
        labels, meta = D.label_run(rp, lg[0:3])
        self.assertIsNotNone(labels)
        self.assertTrue(all(s > 0.05 for s in meta["share"]))
        refs = D.centroids(labels, meta)
        for i in range(2):
            nc = D.joint_cut(rp, labels, meta, i)
            self.assertIsNotNone(nc)
            self.assertLess(nc["neck"], 2.5)
            pieces = L.cut_run(max((q["d"] for q in lig["paths"] if q["kind"] == "body"), key=len), [nc["poly"]], refs=[refs[i]])
            self.assertEqual(len(pieces), 2)
        # the meem's cut sits right after its loop: the whole baseline under the sad is the sad's
        nc = D.joint_cut(rp, labels, meta, 0)
        mx = sum(p[0] for p in nc["poly"]) / 2
        loop_x1 = L.bbox([p for p in rp if L._shoelace(p) and L.bbox([p])[2] > mx][0:1] or rp)[0]
        self.assertGreater(mx, L.bbox(rp)[0] + 0.55 * (L.bbox(rp)[2] - L.bbox(rp)[0]))


class ShapeTrims(unittest.TestCase):
    """The loops drawn on the shapes page, as training labels."""

    def test_only_confirmed_loops_become_labels(self):
        from tools.build_letter_labels import load_shape_trims
        got = load_shape_trims()
        self.assertTrue(got, "no trims loaded")
        flat = [t for v in got.values() for t in v]
        self.assertGreaterEqual(len(flat), 80)
        for t in flat:
            self.assertGreaterEqual(len(t["path"]), 4)

    def test_a_loop_names_its_letter_and_denies_the_rest(self):
        import numpy as np
        from tools.build_letter_labels import apply_trims, H, W, Z
        ink = np.zeros((H, W), dtype=bool)
        ink[10:20, 10:60] = True                      # a run of ink, two letters wide
        mask = np.zeros((H, W), dtype=np.uint16)
        mask[ink] = 0b11                              # both positions still possible
        frame = (0.0, 0.0, float(Z))                  # canvas units = page units
        loop = [(10 / Z, 10 / Z), (35 / Z, 10 / Z), (35 / Z, 20 / Z), (10 / Z, 20 / Z)]
        used = apply_trims(mask, ink, frame, [{"index": 3, "path": loop}], [3, 4], 2)
        self.assertEqual(used, 1)
        inside = mask[12:18, 12:30]
        self.assertTrue((inside == 0b01).all(), "inside the loop must be letter 0 alone")
        outside = mask[12:18, 40:58]
        self.assertTrue((outside == 0b10).all(), "outside must lose letter 0")
        self.assertTrue((mask[~ink] == 0).all(), "non-ink must stay ignored")


class ContourOwnership(unittest.TestCase):
    """clean_labels rule (1b): a contour decides its own owner."""

    def _run(self, lab, ink, n):
        from tools.letter_model import clean_labels
        return clean_labels(lab.copy(), ink, n)

    def test_a_speck_on_another_contour_goes_to_that_contours_owner(self):
        import numpy as np
        ink = np.zeros((40, 60), dtype=bool)
        ink[10:30, 5:20] = True                      # contour A, letter 0
        ink[10:30, 35:55] = True                     # contour B, letter 1, and a speck of 0
        lab = np.full(ink.shape, -1, dtype=np.int64)
        lab[10:30, 5:20] = 0
        lab[10:30, 35:55] = 1
        lab[11:14, 36:39] = 0                        # letter 0 holding a corner of contour B
        out = self._run(lab, ink, 2)
        self.assertEqual(int((out[10:30, 35:55] == 0).sum()), 0,
                         "the speck must go to the letter that owns that contour")
        self.assertEqual(int((out[10:30, 5:20] == 0).sum()), 20 * 15,
                         "the letter's own contour must be untouched")

    def test_a_letter_that_owns_its_second_contour_keeps_it(self):
        """A final kaf is a bowl plus a separate stroke 1,857 times of 1,893."""
        import numpy as np
        ink = np.zeros((40, 60), dtype=bool)
        ink[10:30, 5:25] = True                      # the bowl, letter 0's body
        ink[5:8, 30:50] = True                       # the separate stroke, also letter 0
        ink[10:30, 35:55] = True                     # the neighbour, letter 1
        lab = np.full(ink.shape, -1, dtype=np.int64)
        lab[10:30, 5:25] = 0
        lab[5:8, 30:50] = 0
        lab[10:30, 35:55] = 1
        out = self._run(lab, ink, 2)
        self.assertEqual(int((out[5:8, 30:50] == 0).sum()), 3 * 20,
                         "a whole second contour the letter owns must survive")
