#!/usr/bin/env python3
"""Does each word hold EXACTLY the same ink as MushafDatabase's same word?

`audit_ligcuts.py` compares the ligature CUT and the word's outer EDGES. This
asks Abdullah's stricter question: forget marks, forget groups — is the SET OF
INK assigned to a word identical on the two sides?

It is answered EXACTLY, not by rasterising. The two decompositions trace the
same outlines: on p3 both sides emit 1,354 word-assigned contours, the median
contour has 28 points on each side, and one uniform affine at scale 4/3 in BOTH
axes carries theirs onto ours with a centroid residual of 0.010u median and
0.083u worst. So every contour on one side has a partner on the other, and the
test is which word each side gives the pair to.

Rasterising was tried as a cross-check and is too blunt to adjudicate: 150
control words this test proves ink-identical still differ by up to 467 pixels
(4.4% of their ink) at 10 px/unit, because the two sides' curve decompositions
put edges on different sides of a sample. That measure has no empty band; this
one does. `raster_page()` is kept for spot checks.

  registration  their ink -> ours, per page, refined by least squares on the
                contour pairs themselves. Residual is printed by --proof.
  pairing       a contour matches the other side's when their widths and
                heights agree within SIZE = 0.15u and their centroids within
                TOL = 0.6u. NOT by point count: the two sides write the same
                outline with different command decompositions, so their point
                counts differ by 2-4 on 27% of contours while width and height
                agree to 0.01u. Measured margin over 4,108 contours on
                p3/p58/p455: 4,106 find their partner within 0.1u (median
                0.010u, p99 0.036u) and 2 have no partner at all, while the
                NEXT nearest size-compatible contour is never closer than
                2.025u. EMPTY BAND 0.1u..2.0u, so 0.6 sits in a gap and the
                pairing is proof-class, not a guess.
  verdict       for each word, the multiset of contours ours holds vs theirs.
                Symmetric difference 0 = the word's ink is identical.

    python3 tools/audit_inkidentity.py 1 604 --jobs 32
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PIPE = os.environ.get("QSVG_PIPE", os.path.join(ROOT, "tools", "assign_words.py"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
DEFAULT_REF = os.path.expanduser(
    "~/Dev/github.com/AbdullahObaid/MushafDatabase-Ligature-Based-SVG/SVG V1.01")
TOL = 0.6
SIZE = 0.15    # contour width/height agreement; see --proof for the margin

_TOK = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|(-?(?:\d+\.?\d*|\.\d+)(?:[eE]-?\d+)?)")
_NARG = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7, Z=0)


def subpaths(d):
    """One point list per subpath (contour). Control points are kept: they are
    part of the shape's identity and make the point count a real signature."""
    toks = [(m.group(1), m.group(2)) for m in _TOK.finditer(d)]
    i, cmd, x, y, sx, sy = 0, None, 0.0, 0.0, 0.0, 0.0
    out, cur = [], None
    while i < len(toks):
        if toks[i][0]:
            cmd = toks[i][0]
            i += 1
            if cmd in "Zz":
                x, y = sx, sy
                continue
        if cmd is None:
            break
        n = _NARG[cmd.upper()]
        a = []
        while len(a) < n and i < len(toks) and toks[i][1] is not None:
            a.append(float(toks[i][1]))
            i += 1
        if len(a) < n:
            break
        rel, c = cmd.islower(), cmd.upper()
        if c == "M":
            x, y = (x + a[0], y + a[1]) if rel else (a[0], a[1])
            sx, sy = x, y
            cur = [(x, y)]
            out.append(cur)
            cmd = "l" if rel else "L"
            continue
        if cur is None:
            cur = [(x, y)]
            out.append(cur)
        if c == "L":
            x, y = (x + a[0], y + a[1]) if rel else (a[0], a[1])
        elif c == "H":
            x = x + a[0] if rel else a[0]
        elif c == "V":
            y = y + a[0] if rel else a[0]
        elif c in "CSQT":
            pts = [(a[j], a[j + 1]) for j in range(0, len(a), 2)]
            for px, py in pts:
                cur.append((x + px, y + py) if rel else (px, py))
            x, y = (x + pts[-1][0], y + pts[-1][1]) if rel else pts[-1]
            continue
        elif c == "A":
            x, y = (x + a[5], y + a[6]) if rel else (a[5], a[6])
        cur.append((x, y))
    return [s for s in out if len(s) > 1]


def _mat(s):
    for name, n in (("matrix", 6), ("translate", 2), ("scale", 2)):
        m = re.match(r"\s*%s\(([^)]*)\)" % name, s or "")
        if not m:
            continue
        v = [float(t) for t in re.split(r"[\s,]+", m.group(1).strip()) if t]
        if name == "matrix":
            return tuple(v[:6])
        if name == "translate":
            return (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        return (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
    return (1, 0, 0, 1, 0, 0)


def _mul(A, B):
    a, b, c, d, e, f = A
    g, h, i, j, k, l = B
    return (a * g + c * h, b * g + d * h, a * i + c * j, b * i + d * j,
            a * k + c * l + e, b * k + d * l + f)


def _walk(node, M, word, out, keyof):
    for ch in node:
        tag = ch.tag.split("}")[-1]
        M2 = _mul(M, _mat(ch.get("transform"))) if ch.get("transform") else M
        if tag == "g":
            k = keyof(ch)
            _walk(ch, M2, k if k is not None else word, out, keyof)
        elif tag == "path" and ch.get("d"):
            a, b, c, d, e, f = M2
            for sp in subpaths(ch.get("d")):
                out.append((word, [(a * x + c * y + e, b * x + d * y + f)
                                   for x, y in sp]))


def _walk_paths(node, M, word, out, keyof):
    """Same walk, but one row per PATH with its accumulated matrix, so a word's
    ink can be re-rendered exactly as the source drew it."""
    for ch in node:
        tag = ch.tag.split("}")[-1]
        M2 = _mul(M, _mat(ch.get("transform"))) if ch.get("transform") else M
        if tag == "g":
            k = keyof(ch)
            _walk_paths(ch, M2, k if k is not None else word, out, keyof)
        elif tag == "path" and ch.get("d"):
            out.append((word, ch.get("d"), M2))


def _sig(pts):
    """(bbox centre x, bbox centre y, width, height, point count).

    The centre is the BOX centre, not the average of the points. The point
    average is decomposition-dependent — the two sides write the same outline
    with different numbers of control points, which moves the average and left
    2,218 obviously-identical contours (79.46x18.23 against 79.41x18.20)
    unpaired. The box is stable to 0.05u on the largest contours."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0,
            max(xs) - min(xs), max(ys) - min(ys), len(pts))


# ---------------------------------------------------------------- our side

AW = None


def _load():
    global AW
    if AW is not None:
        return
    spec = importlib.util.spec_from_file_location("assign_words", PIPE)
    AW = importlib.util.module_from_spec(spec)
    sys.modules["assign_words"] = AW
    spec.loader.exec_module(AW)


def ours(pg, paths=False):
    """FRESH build, in process — assign_page returns the emitted SVG text, so
    nothing is read from (or written to) the page cache."""
    _load()
    with contextlib.redirect_stdout(io.StringIO()):
        svg = AW.assign_page("hafs/kfqc", pg,
                             os.path.join(ROOT, ".cache", "words"))[1]

    def keyof(g):
        if g.get("class") != "word":
            return None
        return g.get("data-wid") or ""

    out = []
    root = ET.fromstring(svg)
    if paths:
        _walk_paths(root, (1, 0, 0, 1, 0, 0), None, out, keyof)
        return out
    _walk(root, (1, 0, 0, 1, 0, 0), None, out, keyof)
    return [(w, _sig(p)) for w, p in out]


# ---------------------------------------------------------------- their side

WAQF = "ۖۗۘۙۚۛۜ۝۞۩"
NS = "{http://www.w3.org/2000/svg}"


def their_positions(root):
    """{their group id: our (surah, ayah, pos)} — the same folding
    audit_reference.py and audit_ligcuts.py use: a conjunction waw and a
    standalone stop sign are words of their own for them and belong to a
    neighbour for us."""
    seq = defaultdict(list)
    for w in root.iter(NS + "g"):
        if not (w.get("id") or "").startswith("md-word-"):
            continue
        if w.get("data-type") != "text":
            continue
        try:
            sa = (int(w.get("data-surah")), int(w.get("data-aya")))
            idx = int(w.get("data-word-index-in-ayah"))
        except (TypeError, ValueError):
            continue
        seq[sa].append((idx, w.get("id"), w.get("data-hafs") or "",
                        w.get("data-waw-alatf") == "true"))
    out = {}
    for sa, items in seq.items():
        items.sort()
        merged, pend = [], []
        for _, gid, txt, waw in items:
            if waw:
                pend.append(gid)
                continue
            if txt and all(c in WAQF or c.isspace() for c in txt) and merged:
                merged[-1].append(gid)     # a stop belongs to the word before
                continue
            merged.append(pend + [gid])
            pend = []
        if pend and merged:
            merged[-1].extend(pend)
        for i, gids in enumerate(merged, 1):
            for gid in gids:
                out[gid] = "%d:%d:%d" % (sa[0], sa[1], i)
    return out


def theirs(pg, refdir, paths=False):
    p = os.path.join(refdir, "%03d.svg" % pg)
    if not os.path.exists(p):
        return None
    root = ET.parse(p).getroot()
    pos = their_positions(root)

    def keyof(g):
        gid = g.get("id") or ""
        return pos.get(gid) if gid.startswith("md-word-") else None

    out = []
    if paths:
        _walk_paths(root, (1, 0, 0, 1, 0, 0), None, out, keyof)
        return out
    _walk(root, (1, 0, 0, 1, 0, 0), None, out, keyof)
    return [(w, _sig(p)) for w, p in out]


# ---------------------------------------------------------------- registration


def estimate(ow, tw):
    """(sx, tx, sy, ty) from the two word-ink bounding boxes, then refined on
    the contour pairs the first estimate finds."""
    # The scale is 4/3 on every page — it is our own emitted root matrix. Do
    # NOT derive it from the two ink bounding boxes: on the ornate spreads p1
    # and p2 the frame ink differs between the two sources and the bbox
    # estimate came out at 1.15, which pairs 38 of 302 contours. The offset is
    # a MODAL VOTE over size-compatible contour pairs, which cannot be dragged
    # by ink one side has and the other does not.
    S = 4.0 / 3.0
    bysize = defaultdict(list)
    for s in ow:
        bysize[(round(s[2], 1), round(s[3], 1))].append(s)
    votes = Counter()
    for s in tw:
        key = (round(S * s[2], 1), round(S * s[3], 1))
        cand = bysize.get(key) or []
        if not 1 <= len(cand) <= 3:
            continue
        for o in cand:
            votes[(round((o[0] - S * s[0]) * 4) / 4.0,
                   round((o[1] - S * s[1]) * 4) / 4.0)] += 1
    if not votes:
        return None
    (tx, ty), _ = votes.most_common(1)[0]
    T = (S, tx, S, ty)
    for _ in range(2):
        pairs = match(ow, tw, T, tol=1.5)[0]
        if len(pairs) < 50:
            break
        xs_t = [tw[j][0] for _, j in pairs]
        xs_o = [ow[i][0] for i, _ in pairs]
        ys_t = [tw[j][1] for _, j in pairs]
        ys_o = [ow[i][1] for i, _ in pairs]
        T = _lin(xs_t, xs_o) + _lin(ys_t, ys_o)
    return T


def _lin(X, Y):
    n = len(X)
    mx, my = sum(X) / n, sum(Y) / n
    den = sum((x - mx) ** 2 for x in X) or 1e-9
    s = sum((x - mx) * (y - my) for x, y in zip(X, Y)) / den
    return (s, my - s * mx)


def match(ow, tw, T, tol=TOL):
    """1:1 pairing of contours by geometry. Returns (pairs, ours_only,
    theirs_only) as index lists."""
    sx, tx, sy, ty = T
    grid = defaultdict(list)
    for i, s in enumerate(ow):
        grid[(int(s[0]), int(s[1]))].append(i)
    used = set()
    pairs = []
    unmatched_t = []
    for j, s in enumerate(tw):
        cx, cy = sx * s[0] + tx, sy * s[1] + ty
        w, h, n = sx * s[2], sy * s[3], s[4]
        best, bd = None, tol
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for i in grid.get((int(cx) + dx, int(cy) + dy), ()):
                    if i in used:
                        continue
                    o = ow[i]
                    # NOT the point count: the two sides express the same
                    # outline with different command decompositions and their
                    # counts differ by 2-4 on 27% of contours while width and
                    # height agree to 0.01u. Size is the signature.
                    if abs(o[2] - w) > SIZE or abs(o[3] - h) > SIZE:
                        continue
                    d = max(abs(o[0] - cx), abs(o[1] - cy))
                    if d < bd:
                        best, bd = i, d
        if best is None:
            unmatched_t.append(j)
        else:
            used.add(best)
            pairs.append((best, j))
    return pairs, [i for i in range(len(ow)) if i not in used], unmatched_t


# ---------------------------------------------------------------- comparison


def page(args):
    pg, refdir = args
    try:
        tw_all = theirs(pg, refdir)
        if tw_all is None:
            return pg, None
        ow_all = ours(pg)
    except Exception as exc:
        return pg, {"err": "%s: %s" % (type(exc).__name__, str(exc)[:80])}
    ow = [(w, s) for w, s in ow_all if w]
    tw = [(w, s) for w, s in tw_all if w]
    if len(ow) < 50 or len(tw) < 50:
        return pg, {"err": "too few word contours"}
    T = estimate([s for _, s in ow], [s for _, s in tw])
    if T is None:
        return pg, {"err": "registration failed"}
    pairs, o_only, t_only = match([s for _, s in ow], [s for _, s in tw], T)
    if len(pairs) < 0.5 * len(ow):
        # p1 and p2 only. The ornate opening spread is set at a DIFFERENT SIZE
        # in the reference: our contour widths are 1.03-1.15x theirs across the
        # quantiles and no single scale aligns them, against a flat 1.3333 on
        # every other page. The two sources are not drawing the same artwork
        # there, so the words are excluded rather than reported as differing.
        return pg, {"err": "artwork differs (paired %d of %d contours)"
                    % (len(pairs), len(ow)), "excluded_words": len(set(
                        w for w, _ in ow))}
    sx, tx, sy, ty = T
    res = sorted(max(abs(ow[i][1][0] - (sx * tw[j][1][0] + tx)),
                     abs(ow[i][1][1] - (sy * tw[j][1][1] + ty)))
                 for i, j in pairs)

    per = defaultdict(lambda: {"same": 0, "ours_extra": [], "theirs_extra": []})
    for i, j in pairs:
        ok, tk = ow[i][0], tw[j][0]
        if ok == tk:
            per[ok]["same"] += 1
        else:
            s = ow[i][1]
            item = {"w": round(s[2], 2), "h": round(s[3], 2),
                    "x": round(s[0], 1), "y": round(s[1], 1), "other": tk}
            per[ok]["ours_extra"].append(item)
            per[tk]["theirs_extra"].append(dict(item, other=ok))
    for i in o_only:
        s = ow[i][1]
        per[ow[i][0]]["ours_extra"].append(
            {"w": round(s[2], 2), "h": round(s[3], 2), "x": round(s[0], 1),
             "y": round(s[1], 1), "other": "UNPAIRED"})
    for j in t_only:
        s = tw[j][1]
        per[tw[j][0]]["theirs_extra"].append(
            {"w": round(sx * s[2], 2), "h": round(sy * s[3], 2),
             "x": round(sx * s[0] + tx, 1), "y": round(sy * s[1] + ty, 1),
             "other": "UNPAIRED"})
    rows = []
    for k, v in per.items():
        if v["ours_extra"] or v["theirs_extra"]:
            rows.append({"page": pg, "key": k, "same": v["same"],
                         "ours_extra": v["ours_extra"],
                         "theirs_extra": v["theirs_extra"]})
    return pg, {"words": len(per), "contours": len(ow), "pairs": len(pairs),
                "ours_unpaired": len(o_only), "theirs_unpaired": len(t_only),
                "resid": res, "rows": rows,
                "T": [round(x, 5) for x in T]}


def _same_box(a, b, tol):
    def ub(es):
        return (min(e["x"] - e["w"] / 2 for e in es),
                min(e["y"] - e["h"] / 2 for e in es),
                max(e["x"] + e["w"] / 2 for e in es),
                max(e["y"] + e["h"] / 2 for e in es))
    p, q = ub(a), ub(b)
    return max(abs(p[i] - q[i]) for i in range(4)) <= tol


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--ref", default=DEFAULT_REF)
    ap.add_argument("--jobs", type=int, default=int(os.environ.get("QSVG_JOBS", 32)))
    ap.add_argument("--proof", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "defects",
                                                  "ink_identity.json"))
    args = ap.parse_args(argv)

    if args.proof:
        for pg in (3, 58, 143, 324, 384, 455, 500, 579):
            _, r = page((pg, args.ref))
            if not r or "err" in r:
                print("p%-4d %s" % (pg, (r or {}).get("err", "no ref")))
                continue
            res = r["resid"]
            n = len(res)
            print("p%-4d contours %4d  paired %4d  unpaired ours %2d theirs %2d"
                  "  |  ours = %.5f*x %+.3f , %.5f*y %+.3f  |  centroid "
                  "residual med %.4f p99 %.4f max %.4f"
                  % (pg, r["contours"], r["pairs"], r["ours_unpaired"],
                     r["theirs_unpaired"], r["T"][0], r["T"][1], r["T"][2],
                     r["T"][3], res[n // 2], res[int(n * .99)], res[-1]))
        return 0

    from multiprocessing import Pool
    tot = Counter()
    rows, resid, bad = [], [], []
    with Pool(args.jobs, maxtasksperchild=4) as pool:
        for pg, r in pool.imap_unordered(page, [(p, args.ref)
                                                for p in range(args.first,
                                                               args.last + 1)]):
            if not r:
                tot["no-ref"] += 1
                continue
            if "err" in r:
                tot["page-error"] += 1
                tot["excluded_words"] += r.get("excluded_words", 0)
                bad.append((pg, r["err"]))
                continue
            tot["pages"] += 1
            tot["words"] += r["words"]
            tot["contours"] += r["contours"]
            tot["pairs"] += r["pairs"]
            tot["ours_unpaired"] += r["ours_unpaired"]
            tot["theirs_unpaired"] += r["theirs_unpaired"]
            rows += r["rows"]
            resid += r["resid"][-3:]
    print("pages %d (excluded %d, %d words)"
          % (tot["pages"], tot["page-error"], tot["excluded_words"]))
    for p, e in bad[:8]:
        print("   p%-4d %s" % (p, e))
    print("word-assigned contours %d | paired %d | unpaired ours %d theirs %d"
          % (tot["contours"], tot["pairs"], tot["ours_unpaired"],
             tot["theirs_unpaired"]))
    print("words compared %d | words whose ink is NOT identical %d"
          % (tot["words"], len(rows)))
    sz = sorted(max(e["w"], e["h"])
                for r in rows for e in r["ours_extra"] + r["theirs_extra"])
    if sz:
        print("\nmis-assigned contour size (larger of w,h), %d pieces:" % len(sz))
        h = Counter(min(30, int(s)) for s in sz)
        for i in range(31):
            if h[i]:
                print("   %2d-%2du %5d %s" % (i, i + 1, h[i],
                                              "#" * min(60, h[i])))
    # ------------------------------------------------------------------
    # classify. A word can differ for three quite different reasons and only
    # one of them is a defect.
    for r in rows:
        o = r["ours_extra"]
        t = r["theirs_extra"]
        moved = [e for e in o + t if e["other"] != "UNPAIRED"]
        if moved:
            r["class"] = "ownership"
        elif not o and t and all(e["h"] < 1.2 and e["w"] > 8 for e in t):
            # a long hairline rule: the sajdah underline, which they put
            # INSIDE the word group and we do not
            r["class"] = "their-sajdah-rule"
        elif (len(o) == len(t)
              and all(abs(a["w"] - b["w"]) < 0.15 and abs(a["h"] - b["h"]) < 0.15
                      for a, b in zip(sorted(o, key=lambda e: (e["w"], e["h"])),
                                      sorted(t, key=lambda e: (e["w"], e["h"]))))
              and not _same_box(o, t, 0.6)):
            # the SAME shape drawn in a different PLACE. Our pages are proven
            # pixel-identical to the artwork (audit_pixels), so the artwork has
            # it where we have it.
            r["class"] = "position-differs"
        elif o and t and _same_box(o, t, 1.5):
            # both sides draw the same region, cut into a different number of
            # subpaths (their three-dot glyph is 2 subpaths, ours is 3)
            r["class"] = "subpath-split"
        elif not o and t:
            r["class"] = "theirs-only-ink"
        elif o and not t and max(max(e["w"], e["h"]) for e in o) < 0.5:
            # a degenerate contour that draws nothing: the QSVG_NULLMARK
            # family. We carry it, they dropped it. Not ink.
            r["class"] = "ours-null-contour"
        elif o and not t:
            r["class"] = "ours-only-ink"
        else:
            r["class"] = "region-differs"
    print("")
    for k, n in Counter(r["class"] for r in rows).most_common():
        print("   %-20s %5d word(s)" % (k, n))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows.sort(key=lambda r: -max([max(e["w"], e["h"])
                                  for e in r["ours_extra"] + r["theirs_extra"]]
                                 or [0]))
    json.dump(rows, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nwrote %s (%d rows)" % (args.out, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------- stage 2: pixels
#
# 667 of the 699 words the contour test separates differ ONLY because the two
# sides cut the same ink into different subpaths — their three-dot glyph is two
# subpaths where ours is three contours, so two of ours find no 1:1 partner even
# though the ink is the same and both sides give it to the same word. That is a
# tracing difference, not an ownership one, and only pixels can say so. Stage 2
# renders each such word's ink from BOTH sides into the same box and diffs.

RASTER_SCALE = 10.0        # px per unit; a 30u word renders ~300 px wide
RASTER_TOL = 100           # 0-255; above the 24 audit_pixels uses for AA


def _wordsvg(items, box, scale):
    x0, y0, x1, y1 = box
    body = "".join(
        '<path d="%s" transform="matrix(%s)" fill="#000" fill-rule="evenodd"/>'
        % (d, " ".join("%.6f" % v for v in M)) for d, M in items)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="%.3f %.3f %.3f %.3f"><rect x="%.3f" y="%.3f" width="%.3f" '
            'height="%.3f" fill="#fff"/>%s</svg>'
            % (max(4, int((x1 - x0) * scale)), max(4, int((y1 - y0) * scale)),
               x0, y0, x1 - x0, y1 - y0, x0, y0, x1 - x0, y1 - y0, body))


def raster_page(args):
    """[(key, differing-pixels, total-ink-pixels, box)] for the listed words."""
    import subprocess
    import tempfile
    from PIL import Image, ImageChops
    pg, refdir, keys, scale = args
    keys = set(keys)
    op = ours(pg, paths=True)
    tp = theirs(pg, refdir, paths=True)
    ow = [(w, s) for w, s in ours(pg) if w]
    tw = [(w, s) for w, s in theirs(pg, refdir) if w]
    T = estimate([s for _, s in ow], [s for _, s in tw])
    sx, tx, sy, ty = T
    R = (sx, 0.0, 0.0, sy, tx, ty)
    mine, ref = defaultdict(list), defaultdict(list)
    for w, d, M in op:
        if w in keys:
            mine[w].append((d, M))
    for w, d, M in tp:
        if w in keys:
            ref[w].append((d, _mul(R, M)))
    out = []
    with tempfile.TemporaryDirectory() as td:
        for k in sorted(keys):
            items = mine.get(k, []) + ref.get(k, [])
            if not items:
                continue
            xs, ys = [], []
            for w, s in ow:
                if w == k:
                    xs += [s[0] - s[2] / 2, s[0] + s[2] / 2]
                    ys += [s[1] - s[3] / 2, s[1] + s[3] / 2]
            for w, s in tw:
                if w == k:
                    xs += [sx * s[0] + tx - sx * s[2] / 2,
                           sx * s[0] + tx + sx * s[2] / 2]
                    ys += [sy * s[1] + ty - sy * s[3] / 2,
                           sy * s[1] + ty + sy * s[3] / 2]
            if not xs:
                continue
            box = (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)
            png = []
            for side, items in (("a", mine.get(k, [])), ("b", ref.get(k, []))):
                f = os.path.join(td, "%s.svg" % side)
                open(f, "w", encoding="utf-8").write(_wordsvg(items, box, scale))
                g = os.path.join(td, "%s.png" % side)
                subprocess.run(["rsvg-convert", f, "-o", g], check=True)
                png.append(Image.open(g).convert("L"))
            if png[0].size != png[1].size:
                out.append((k, -1, 0, box))
                continue
            diff = ImageChops.difference(png[0], png[1]).histogram()
            bad = sum(diff[RASTER_TOL + 1:])
            ink = sum(1 for v in png[0].getdata() if v < 128)
            out.append((k, bad, ink, box))
    return pg, out
