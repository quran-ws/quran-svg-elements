#!/usr/bin/env python3
"""Read the MushafDatabase ligature SVGs as data, and register them onto our pages.

MushafDatabase publishes the same KFGQPC Madani artwork decomposed independently:
one `<g id="md-word-NNN">` per word carrying surah / ayah / word-index-in-ayah /
line-number / hafs text, and inside it one `<path>` per drawn piece, each labelled
`data-type="text"` (a letter or ligature, with `data-text` naming it),
`"diacritic"` (with `data-diacritic`), or `"dots"` (with `data-dots`).

That makes it the only source we have for the two questions our own audits cannot
answer from the ink alone: *where does this word end and the next begin*, and *which
pieces belong to it*. `audit_reference.py` uses only the line number, which needs no
geometry. Anything stronger needs the two coordinate systems registered, which is
what this module adds.

The registration is exact and cheap. Both files draw the same page, so the map from
our rendered page coordinates to theirs is a pure scale-and-offset per axis. The ayah
medallions fix it: both sources mark them, both label them with the surah and ayah, so
they are matched by name rather than by position and the fit has no correspondence
problem. Pages with too few medallions fall back to the line grid, which both sources
also label.

    python3 tools/refdb.py <ref-dir> 3        # dump one page and its registration
"""

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from svg_lines import subpaths                                          # noqa: E402

GROUP = re.compile(r'<g\b([^>]*)>')
PATH = re.compile(r'<path\b([^>]*?)/>', re.S)
ATTR = re.compile(r'([a-zA-Z:-]+)="([^"]*)"')

# The letters, and only the letters. The two sources spell the marks differently — one
# writes a tanwin_al_fath as two strokes and the other as one glyph — so a word is identified
# by its skeleton, never by its full text.
# U+0640 TATWEEL has to be SUBTRACTED, not merely left out: it sits inside the
# 0621..064A run. It is a justification stretch, not a letter — quran.com writes it
# inside مَلَـٰٓئِكَتِهِۦ and the reference does not — so leaving it in made every such
# word look like a different word and silently drop out of the comparison.
_LETTERS = (set(range(0x0621, 0x064B)) | {0x0671, 0x0672, 0x0673, 0x0675}) - {0x0640}

WAQF = "ۖۗۘۙۚۛۜ۝۞۩"

# Our pages carry matrix(1.3333 0 0 -1.3333 ...); the reference is drawn in the space
# that scales up from, so on a body page the ratio is exactly 3/4 — measured over nine
# pages it came out 0.750000 with a spread of 0.0005, which is the noise in locating a
# landmark. Pages 1 and 2 are the exception: they are set on their own spacing rather
# than the body grid, and the reference draws them at 0.8667 and 0.8625. Assuming 3/4
# everywhere put every word on those two pages five units out of place.
SCALE = 0.75
# A slope is only estimated from landmark pairs at least this far apart, in our units.
# Two landmarks a hair apart give a slope that is almost all noise.
_SPREAD = 20.0


# The two sources spell the same rasm with different code points. quran.com writes
# يَأْتِىَ with U+0649 alef maksura where the reference writes يَأۡتِيَ with U+064A yeh;
# one writes ٱ and the other ا. Comparing raw code points made those look like different
# words and dropped them out of the audit entirely — which is how the visibly broken
# يَأْتِىَ on p555 went unreported while the words on either side of it were flagged.
# Only same-rasm forms are folded: two genuinely different words at the same index in
# the same ayah still differ in most of their letters.
_SAME_RASM = {
    "\u0649": "\u064a",                                    # ى -> ي
    "\u0622": "\u0627", "\u0623": "\u0627",              # آ أ -> ا
    "\u0625": "\u0627", "\u0671": "\u0627",              # إ ٱ -> ا
    "\u0672": "\u0627", "\u0673": "\u0627", "\u0675": "\u0627",
    "\u0624": "\u0648",                                    # ؤ -> و
    "\u0626": "\u064a",                                    # ئ -> ي
    "\u0629": "\u0647",                                    # ة -> ه
}


def skeleton(t):
    return "".join(_SAME_RASM.get(c, c) for c in (t or "") if ord(c) in _LETTERS)


def _box(d):
    """Bounding box of one path's `d`, or None if it draws nothing."""
    xs, ys = [], []
    for p in subpaths(d):
        xs += [p["xmin"], p["xmax"]]
        ys += [p["ymin"], p["ymax"]]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _close(s, start):
    """Index just past the `</g>` closing the `<g>` that opens at `start`."""
    depth, i = 0, start
    while i < len(s):
        if s.startswith("<g", i) and (i + 2 >= len(s) or s[i + 2] in " >\t\r\n"):
            depth += 1
            i += 2
        elif s.startswith("</g>", i):
            depth -= 1
            i += 4
            if depth == 0:
                return i
        else:
            i += 1
    return len(s)


def _pieces(s, lo, hi):
    """Every drawn piece in [lo, hi), as (kind, label, box)."""
    out = []
    for m in PATH.finditer(s, lo, hi):
        a = dict(ATTR.findall(m.group(1)))
        b = _box(a.get("d", ""))
        if b is None:
            continue
        kind = a.get("data-type", "")
        label = (a.get("data-text") or a.get("data-diacritic") or a.get("data-dots")
                 or a.get("data-waqf") or "")
        out.append((kind, label, b))
    return out


def read_page(path):
    """One reference page as plain data.

    `words` keeps the reference's own word numbering; `fold()` converts it to ours.
    """
    s = io.open(path, encoding="utf-8-sig").read()
    vb = re.search(r'viewBox="([^"]*)"', s)
    page = {"viewbox": [float(x) for x in vb.group(1).split()] if vb else None,
            "words": [], "marks": []}
    for m in GROUP.finditer(s):
        a = dict(ATTR.findall(m.group(1)))
        gid = a.get("id", "")
        end = _close(s, m.start())
        if gid.startswith("md-word-") and a.get("data-type") == "text":
            try:
                # The release writes `data-aya`; an earlier one wrote
                # `data-ayah`. Both are the publisher's name for the same
                # thing, quoted as it writes them — reading only one silently
                # matched ZERO words out of 77,432 and reported "0 pages".
                _ay = a.get("data-aya", a.get("data-ayah"))
                rec = {"surah": int(a["data-surah"]), "ayah": int(_ay),
                       "idx": int(a["data-word-index-in-ayah"])}
            except (KeyError, ValueError):
                continue
            rec["line"] = int(a.get("data-line-number", 0) or 0)
            rec["hafs"] = a.get("data-hafs", "")
            rec["imlaey"] = a.get("data-imlaey", "")
            rec["waw"] = a.get("data-waw-alatf") == "true"
            rec["pieces"] = _pieces(s, m.end(), end)
            page["words"].append(rec)
        elif gid.startswith("md-ayah-mark-"):
            pcs = _pieces(s, m.end(), end)
            if not pcs:
                continue
            x1 = min(p[2][0] for p in pcs)
            y1 = min(p[2][1] for p in pcs)
            x2 = max(p[2][2] for p in pcs)
            y2 = max(p[2][3] for p in pcs)
            try:
                sa = (int(a["data-surah"]), int(a["data-ayah"]))
            except (KeyError, ValueError):
                sa = None
            page["marks"].append({"key": sa, "line": int(a.get("data-line-number", 0) or 0),
                                  "cx": (x1 + x2) / 2.0, "cy": (y1 + y2) / 2.0,
                                  "box": (x1, y1, x2, y2)})
    return page


def fold(page):
    """Reference words renumbered into our word numbering.

    The reference splits two things we do not: a conjunction waw is its own word
    (`waw-alatf`), and a stop sign is its own word. Both belong to a neighbour in the
    layout we follow, so unless they are folded back every index after the first waw
    on the page is off by one and every word downstream looks misplaced.

    Returns {(surah, ayah, our-index): record}, each record carrying the merged text
    and the union of the merged words' pieces.
    """
    seq = {}
    for w in page["words"]:
        seq.setdefault((w["surah"], w["ayah"]), []).append(w)
    out = {}
    for sa, items in seq.items():
        items.sort(key=lambda w: w["idx"])
        merged, pend_txt, pend_pcs = [], "", []
        for w in items:
            if w["waw"]:                       # joins the word that follows it
                pend_txt += w["hafs"]
                pend_pcs += w["pieces"]
                continue
            txt = w["hafs"]
            if txt and all(c in WAQF or c.isspace() for c in txt) and merged:
                merged[-1]["pieces"] += w["pieces"]      # a stop belongs to the word before
                continue
            merged.append({"line": w["line"], "hafs": pend_txt + txt,
                           "imlaey": w["imlaey"],
                           "pieces": pend_pcs + list(w["pieces"])})
            pend_txt, pend_pcs = "", []
        if pend_txt and merged:                # a trailing waw with nothing after it
            merged.append({"line": merged[-1]["line"], "hafs": pend_txt,
                           "imlaey": "", "pieces": pend_pcs})
        for i, rec in enumerate(merged, 1):
            rec["key"] = (sa[0], sa[1], i)
            rec["skel"] = skeleton(rec["hafs"])
            body = [p for p in rec["pieces"] if p[0] == "text"]
            rec["nbody"] = len(body)
            rec["ndia"] = len([p for p in rec["pieces"] if p[0] == "diacritic"])
            rec["ndots"] = len([p for p in rec["pieces"] if p[0] == "dots"])
            for tag, src in (("", rec["pieces"]), ("body_", body)):
                if src:
                    rec[tag + "x1"] = min(p[2][0] for p in src)
                    rec[tag + "y1"] = min(p[2][1] for p in src)
                    rec[tag + "x2"] = max(p[2][2] for p in src)
                    rec[tag + "y2"] = max(p[2][3] for p in src)
            out[rec["key"]] = rec
    return out


# ---------------------------------------------------------------------------
# Registering their coordinates onto ours
# ---------------------------------------------------------------------------

class Registration:
    """Maps a point in our rendered page coordinates into the reference's.

    The scale is not fitted. Our pages carry `matrix(1.3333 0 0 -1.3333 -55 640)` and
    the reference is drawn in the space that matrix scales up from, so the ratio is
    exactly 3/4 — measured over nine pages it came out 0.750000 with a spread of
    0.0005, which is the noise in locating a medallion's centre. Fitting it anyway
    spends the landmarks on a number that is already known and leaves the offsets,
    which are what actually vary, resting on six or seven points.
    """

    def __init__(self, bx, by, mad, basis, n, scale=None):
        self.ax = self.ay = SCALE if scale is None else scale
        self.fitted = scale is not None
        self.bx, self.by = bx, by
        self.mad, self.basis, self.n = mad, basis, n
        self.residual = mad          # kept: callers written against the old fit

    def x(self, v):
        return self.ax * v + self.bx

    def y(self, v):
        return self.ay * v + self.by

    def inv_x(self, v):
        return (v - self.bx) / self.ax

    def inv_y(self, v):
        return (v - self.by) / self.ay

    def scale(self):
        return self.ax

    def __repr__(self):
        return ("<Registration %s n=%d  x*%.4f%+.3f  y*%.4f%+.3f  mad %.3f>"
                % (self.basis, self.n, self.ax, self.bx, self.ay, self.by, self.mad))


def _slope(pairs):
    """Scale, by the median of slopes between widely separated landmark pairs.

    Pairing the i-th smallest with the i-th largest gives n/2 pairs that are all far
    apart, so every slope is well conditioned, and the median of them cannot be moved by
    a minority of bad landmarks. Returns None when the page does not offer enough
    separation to say anything, and the caller keeps the structural 3/4.
    """
    pts = sorted(pairs)
    n = len(pts)
    if n < 8:
        return None
    sl = []
    for i in range(n // 2):
        a, b = pts[i], pts[n - 1 - i]
        if b[0] - a[0] > _SPREAD:
            sl.append((b[1] - a[1]) / (b[0] - a[0]))
    if len(sl) < 4:
        return None
    sl.sort()
    m = len(sl)
    return sl[m // 2] if m % 2 else 0.5 * (sl[m // 2 - 1] + sl[m // 2])


def _offset(pairs, scale):
    """Median b for ref = SCALE * ours + b, and the median absolute residual.

    The median, not the mean, and not least squares. Landmarks taken from matched
    words are mostly right and a few are exactly the defects being looked for; a mean
    would let those pull the frame toward them and hide themselves. A median cannot be
    moved by a minority at all, however far out it sits.
    """
    if not pairs:
        return None
    res = sorted(r - scale * o for o, r in pairs)
    n = len(res)
    b = res[n // 2] if n % 2 else 0.5 * (res[n // 2 - 1] + res[n // 2])
    dev = sorted(abs(r - scale * o - b) for o, r in pairs)
    return b, dev[len(dev) // 2]


def register(x_pairs, y_pairs, basis="landmarks"):
    """Fit scale and offsets from (ours, theirs) landmark pairs.

    The scale is taken from x, where the landmarks span the page, and applied to both
    axes: the artwork is never stretched on one axis only. It is only accepted when it
    is within a few percent of 3/4 — anything further is a broken landmark set, not a
    differently scaled page, and keeping 3/4 lets the page's real error show.
    """
    scale = _slope(x_pairs)
    if scale is None or not (0.6 < scale < 1.0):
        scale = None
    fx = _offset(x_pairs, scale or SCALE)
    fy = _offset(y_pairs, scale or SCALE)
    if fx is None or fy is None:
        return None
    return Registration(fx[0], fy[0], max(fx[1], fy[1]), basis,
                        min(len(x_pairs), len(y_pairs)), scale)


def medallion_pairs(our_marks, ref_page):
    """Landmarks from the ayah medallions, matched by surah and ayah.

    Exact but scarce, and they come from `mushafs/.../json/NNN.json`, whose ayah
    polygons are known broken on a handful of pages (294, 305, 431, 551, 602, 604 at
    least). A page registered on those alone comes out shifted by most of its width
    and then reports every word on it as misplaced — which is how p397, p431 and p551
    produced 258 of 689 "defects" that were nothing of the kind.
    """
    if not our_marks or not ref_page["marks"]:
        return [], []
    theirs = {m["key"]: (m["cx"], m["cy"]) for m in ref_page["marks"] if m["key"]}
    common = sorted(set(k for k in our_marks if k) & set(theirs))
    return ([(our_marks[k][0], theirs[k][0]) for k in common],
            [(our_marks[k][1], theirs[k][1]) for k in common])


if __name__ == "__main__":
    refdir = sys.argv[1]
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    p = read_page(os.path.join(refdir, "%03d.svg" % pg))
    f = fold(p)
    print("page %d  viewBox %s" % (pg, p["viewbox"]))
    print("raw words %d  folded %d  medallions %d"
          % (len(p["words"]), len(f), len(p["marks"])))
    for k in sorted(f)[:8]:
        r = f[k]
        print("  %-11s line %2d  %-14s bodies %2d dia %2d dots %2d  x %.1f..%.1f"
              % ("%d:%d:%d" % k, r["line"], r["hafs"], r["nbody"], r["ndia"],
                 r["ndots"], r.get("body_x1", -1), r.get("body_x2", -1)))
