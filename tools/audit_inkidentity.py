#!/usr/bin/env python3
"""Does each word hold EXACTLY the same ink as MushafDatabase's same word?

`audit_ligcuts.py` compares the ligature CUT and the word's outer EDGES. This
asks Abdullah's stricter question: forget marks, forget groups — is the SET OF
INK assigned to a word identical on the two sides?

It is answered EXACTLY, not by rasterising. The two decompositions trace the
same outlines: on p3 both sides emit 1,354 word-assigned contours, the median
contour has 28 points on both sides, and one uniform affine (scale 1.33330 in x
and 1.33328 in y) carries their ink bbox onto ours. So every contour on one
side has a partner on the other, and the test is whether the two sides give the
partners to the same word.

  registration  their ink -> ours, per page, refined by least squares on the
                contour pairs themselves. Residual is printed by --proof.
  pairing       a contour matches the other side's when their widths and
                heights agree within SIZE = 0.15u and their centroids within
                TOL = 0.6u. NOT by point count: the two sides write the same
                outline with different command decompositions, so their point
                counts differ by 2-4 on 27% of contours while width and height
                agree to 0.01u. Measured margin, p3/p58/p455: the correct
                partner is 0.025u away (median), 0.35u at p99, 0.94u at worst;
                the NEXT nearest size-compatible contour is never closer than
                2.0u. Empty band 0.94u..2.0u, so 0.6 is inside a gap and the
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


def ours(pg):
    """FRESH build, in process — assign_page returns the emitted SVG text, so
    nothing is read from (or written to) the page cache."""
    _load()
    with contextlib.redirect_stdout(io.StringIO()):
        svg = AW.assign_page("hafs/kfqc", pg,
                             os.path.join(ROOT, ".cache", "words"))[1]

    def keyof(g):
        if g.get("class") != "word":
            return None
        return "%s:%s:%s" % (g.get("data-surah"), g.get("data-ayah"),
                             g.get("data-word"))

    out = []
    _walk(ET.fromstring(svg), (1, 0, 0, 1, 0, 0), None, out, keyof)
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


def theirs(pg, refdir):
    p = os.path.join(refdir, "%03d.svg" % pg)
    if not os.path.exists(p):
        return None
    root = ET.parse(p).getroot()
    pos = their_positions(root)

    def keyof(g):
        gid = g.get("id") or ""
        return pos.get(gid) if gid.startswith("md-word-") else None

    out = []
    _walk(root, (1, 0, 0, 1, 0, 0), None, out, keyof)
    return [(w, _sig(p)) for w, p in out]


# ---------------------------------------------------------------- registration


def estimate(ow, tw):
    """(sx, tx, sy, ty) from the two word-ink bounding boxes, then refined on
    the contour pairs the first estimate finds."""
    def bb(sigs):
        xs = [s[0] for s in sigs]
        ys = [s[1] for s in sigs]
        return min(xs), max(xs), min(ys), max(ys)
    a, b = bb(ow), bb(tw)
    sx = (a[1] - a[0]) / (b[1] - b[0])
    sy = (a[3] - a[2]) / (b[3] - b[2])
    T = (sx, a[0] - sx * b[0], sy, a[2] - sy * b[2])
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
    pairs, o_only, t_only = match([s for _, s in ow], [s for _, s in tw], T)
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
    print("pages %d (errors %d)" % (tot["pages"], tot["page-error"]))
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
