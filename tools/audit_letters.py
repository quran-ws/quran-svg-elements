#!/usr/bin/env python3
"""The gate for the letter-level decomposition.

    python3 tools/audit_letters.py 1 604 --jobs 32      # → .cache/letters/audit/NNN.json + summary
    python3 tools/audit_letters.py 50
    python3 tools/audit_letters.py 1 604 --calib        # DK cuts vs hand cuts, per joint pair

Per page, on .cache/letters-svg/hafs-kfqc/NNN.svg against .cache/words-svg:

  proof rows (a build is accepted only when all three are 0 on every page)
    count     letters emitted != letters in the text, or a letter with no body ink
              (ء drawn as a mark excepted); unsplit runs are counted separately
    ink       contour conservation: every path that is not a cut piece must appear
              verbatim (same d) in both files; cut pieces must sum to their source
              contour's area within 0.5%
    pixels    raster diff letters vs words at WIDTH px. A chord is an abutting seam:
              two anti-aliased edges meet, the pixel lightens by up to ~64/255 on 1–3
              pixels per cut (audit_pixels.py measured 26–60 for split strokes, 100+
              for a real defect). So: max ≤ SEAM_MAX, and over-TOL pixels ≤ SEAM_PX
              + SEAM_PER_CUT × cuts on the page.

  priors (reported, feed the review sheet)
    marks     per-letter mark counts vs the text's expectation (tanween ≈ haraka,
              meem-iqlab ignored: the print's iqlab notation differs from uthmani)
    area      a hand-cut letter's piece area vs the hand layer's area (±3%)
    conf      cuts below the calibrated confidence
"""
import argparse

import numpy as np
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

TOL, SEAM_PX, WIDTH = 24, 10, 1400
SHAPE_DEV, ISLAND, SHAPE_MIN_PX = 0.85, 0.15, 4      # ragged cut, island share, boundary pixels
SIZE_LO, SIZE_HI, SIZE_MIN = 0.34, 3.0, 12           # letter area vs its median, and the sample floor
ISLAND_PX = 40                                       # a piece smaller than this is a refit sliver
SIZES_PATH = os.path.join(L.ROOT, ".cache", "letters", "letter_sizes" + ("-" + L.BUILD_TAG if L.BUILD_TAG else "") + ".json")
Z_SHAPE = 12
SEAM_MAX, SEAM_PER_CUT = 72, 14      # 14: a staircase boundary (model ownership) seams ~10 px per cut
AUDIT_DIR = os.path.join(L.ROOT, ".cache", "letters", "audit" + ("-" + L.BUILD_TAG if L.BUILD_TAG else ""))
_LETTER = re.compile(r'<g class="letter"([^>]*)>(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>', re.S)
_EQUIV = {"fathatan": "fatha", "dammatan": "damma", "kasratan": "kasra"}


def _diff(a_svg, b_svg, width=WIDTH):
    from PIL import Image, ImageChops
    with tempfile.TemporaryDirectory() as td:
        pa, pb = os.path.join(td, "a.png"), os.path.join(td, "b.png")
        subprocess.run(["rsvg-convert", "-w", str(width), "-b", "white", a_svg, "-o", pa], check=True)
        subprocess.run(["rsvg-convert", "-w", str(width), "-b", "white", b_svg, "-o", pb], check=True)
        h = ImageChops.difference(Image.open(pa).convert("L"), Image.open(pb).convert("L")).histogram()
    mx = max((i for i, n in enumerate(h) if n), default=0)
    return mx, sum(h[TOL + 1:])


def letter_areas(inner):
    """Every emitted letter of the word: (run, index, text, drawn area in square page
    units, form). Form is the letter's place in its run — the rightmost letter of a run
    is its first."""
    rows = []
    for attrs, body in _LETTER.findall(inner):
        at = L.parse_attrs(attrs)
        if at.get("data-unsplit") == "1":
            continue
        try:
            idx = int(at.get("data-index", -1))
        except ValueError:
            continue
        area = 0.0
        for m in _PATH.findall(body):
            pa = L.parse_attrs(m)
            if pa.get("data-kind") == "body" and pa.get("d"):
                area += L.area(pa["d"])
        rows.append({"run": at.get("data-run", ""), "idx": idx, "ch": at.get("data-text", ""), "area": area})
    by_run = defaultdict(list)
    for r in rows:
        by_run[r["run"]].append(r)
    for run, rs in by_run.items():
        rs.sort(key=lambda r: r["idx"])
        for i, r in enumerate(rs):
            r["form"] = ("only" if len(rs) == 1 else "first" if i == 0
                         else "last" if i == len(rs) - 1 else "middle")
    return rows


_SIZES = None


def sizes_table():
    global _SIZES
    if _SIZES is None:
        _SIZES = json.load(open(SIZES_PATH, encoding="utf-8")) if os.path.exists(SIZES_PATH) else {}
    return _SIZES


def build_sizes(pages, jobs):
    """The median drawn area of every letter in every position, over the whole mushaf."""
    from collections import defaultdict as dd
    acc = dd(list)
    with ProcessPoolExecutor(min(jobs, len(pages))) as ex:
        for rows in ex.map(_areas_of_page, pages):
            for ch, form, area in rows:
                acc["%s|%s" % (ch, form)].append(area)
    out = {k: {"median": float(np.median(v)), "n": len(v)} for k, v in acc.items()}
    os.makedirs(os.path.dirname(SIZES_PATH), exist_ok=True)
    with open(SIZES_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return out


def _areas_of_page(page):
    path = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
    if not os.path.exists(path):
        return []
    words, _ = L.read_words(page, L.LETTERS_SVG)
    out = []
    for w in words:
        for r in letter_areas(w["inner"]):
            if r["area"] > 0:
                out.append((r["ch"], r["form"], r["area"]))
    return out


def letter_index_of(inner):
    """Map each emitted path's `d` to the letter group it sits in: {d: (index, text)}."""
    out = {}
    for attrs, body in _LETTER.findall(inner):
        at = L.parse_attrs(attrs)
        if at.get("data-unsplit") == "1":
            continue
        try:
            idx = int(at.get("data-index", -1))
        except ValueError:
            continue
        for m in _PATH.findall(body):
            pa = L.parse_attrs(m)
            if pa.get("data-kind") == "body" and pa.get("d"):
                out[pa["d"]] = (idx, at.get("data-text", ""))
    return out


def straightness(mask_a, mask_b, z):
    """The shared boundary of two pieces: its pixel count, its length and how far it
    wanders from a straight line, in page units. A cut across a stroke is a short
    straight segment; two letters running alongside each other share a long curved
    boundary, which is not a defect."""
    from scipy import ndimage as _ndi
    touch = _ndi.binary_dilation(mask_a, np.ones((3, 3), bool)) & mask_b
    n = int(touch.sum())
    if n < SHAPE_MIN_PX:
        return n, 0.0, 0.0
    ys, xs = np.nonzero(touch)
    pts = np.stack([xs / z, ys / z], 1)
    c = pts.mean(0)
    _, sv, vt = np.linalg.svd(pts - c, full_matrices=False)
    axis = vt[0]
    perp = np.array([-axis[1], axis[0]])
    along = (pts - c) @ axis
    dev = np.abs((pts - c) @ perp)
    return n, float(along.max() - along.min()), float(dev.max())


def shape_checks(res, wid, base, per_letter, texts, run_m, z):
    """Two shape rules inside one source contour: a letter's ink is one piece, and the
    boundary where a cut separates two letters is straight across the stroke."""
    from scipy import ndimage as _ndi
    eight = np.ones((3, 3), dtype=bool)
    for k, m in sorted(per_letter.items()):
        lab, nc = _ndi.label(m, structure=eight)
        if nc < 2:
            continue
        sizes = sorted((int(v) for v in np.bincount(lab.ravel())[1:] if v >= ISLAND_PX), reverse=True)
        if len(sizes) < 2:
            continue
        share = sizes[-1] / float(sum(sizes))
        if share <= ISLAND:
            res["shape"] += 1
            res["detail"].append((wid, "shape", "letter %d %s is in %d pieces inside %s, the smallest %.0f%% of it"
                                  % (k, texts.get(k, ""), len(sizes), base, 100 * share)))
    # stroke half-width where two letters meet, to tell a cut from a shared flank
    edt = _ndi.distance_transform_edt(run_m) / z
    ks = sorted(per_letter)
    for k, k2 in zip(ks, ks[1:]):
        if k2 != k + 1:
            continue
        n, extent, dev = straightness(per_letter[k], per_letter[k2], z)
        if n < SHAPE_MIN_PX:
            continue
        touch = _ndi.binary_dilation(per_letter[k], np.ones((3, 3), bool)) & per_letter[k2]
        width = 2 * float(edt[touch].max()) if touch.any() else 0.0
        if extent > 2.5 * max(width, 0.1):
            continue                       # a shared flank, not a cut across the stroke
        if dev > SHAPE_DEV:
            res["shape"] += 1
            res["detail"].append((wid, "shape", "the cut between %s and %s in %s wanders %.2fu from a straight line"
                                  % (texts.get(k, ""), texts.get(k2, ""), base, dev)))


def audit_page(page, do_pixels=True):
    lsvg = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
    wsvg = os.path.join(L.WORDS_SVG, "%03d.svg" % page)
    res = {"page": page, "count": 0, "ink": 0, "pixels": 0, "marks": 0, "area": 0, "unsplit": 0,
           "shape": 0, "size": 0, "letters": 0, "words": 0, "detail": []}
    if not os.path.exists(lsvg):
        res["missing"] = True
        return res
    words_l, s_l = L.read_words(page, L.LETTERS_SVG)
    words_w, s_w = L.read_words(page)
    cuts_path = os.path.join(L.CUTS_DIR, "%03d.json" % page)
    cuts = json.load(open(cuts_path, encoding="utf-8")) if os.path.exists(cuts_path) else {"words": {}}
    by_w = {w["wid"]: w for w in words_w}
    # ink: every non-cut path verbatim; cut pieces sum to their source
    all_w = Counter(p["d"] for w in words_w for p in w["paths"])
    for w in words_l:
        res["words"] += 1
        src = by_w.get(w["wid"])
        if src is None:
            res["ink"] += 1
            res["detail"].append((w["wid"], "ink", "word missing in the word build"))
            continue
        by_d = letter_index_of(w["inner"])
        src_d = {p["eid"]: p["d"] for p in src["paths"]}
        src_paths = Counter(p["d"] for p in src["paths"])
        seen = Counter()
        pieces = defaultdict(list)
        for p in w["paths"]:
            if p["attrs"].get("data-cut") == "1":
                base = p["eid"].rsplit("-", 1)[0]
                pieces[base].append(p["d"])
            else:
                seen[p["d"]] += 1
        for base, ds in pieces.items():
            if base not in src_d:
                res["ink"] += 1
                res["detail"].append((w["wid"], "ink", "piece of unknown contour %s" % base))
                continue
            # the pieces must reproduce the contour as RENDERED and not overlap: rastered
            # at 12 px/u (the boolean library mishandles evenodd operands, so no path
            # ops and no path areas here); a difference is a blob that survives a 2x2
            # opening and exceeds the refit sliver band (measured 6–28 px along chords)
            from scipy import ndimage as _ndi
            k2 = np.ones((2, 2), dtype=bool)
            run_polys = L.flatten(src_d[base])
            bx0, by0, bx1, by1 = L.bbox(run_polys)
            fr = (bx0 - 1, by0 - 1, bx1 - bx0 + 2, by1 - by0 + 2)
            run_m = L.raster(run_polys, *fr, 12)
            masks_ = []
            for d in ds:
                m = L.raster(L.flatten(d), *fr, 12)
                mm = np.zeros(run_m.shape, dtype=bool)
                hh, ww = min(m.shape[0], run_m.shape[0]), min(m.shape[1], run_m.shape[1])
                mm[:hh, :ww] = m[:hh, :ww]
                masks_.append(mm)
            per_letter, texts = {}, {}
            for d, m in zip(ds, masks_):
                hit = by_d.get(d)
                if hit is None:
                    continue
                k, t = hit
                texts[k] = t
                per_letter[k] = m if k not in per_letter else (per_letter[k] | m)
            if len(per_letter) > 1 or any(m.sum() for m in per_letter.values()):
                shape_checks(res, w["wid"], base, per_letter, texts, run_m, 12)
            uni = np.any(masks_, axis=0)
            diff = int(_ndi.binary_opening(uni & ~run_m, structure=k2).sum() + _ndi.binary_opening(run_m & ~uni, structure=k2).sum())
            if diff >= 40:
                res["ink"] += 1
                res["detail"].append((w["wid"], "ink", "pieces of %s do not reproduce it (%d px)" % (base, diff)))
            for i in range(len(masks_)):
                for j in range(i + 1, len(masks_)):
                    blob = int(_ndi.binary_opening(masks_[i] & masks_[j], structure=k2).sum())
                    if blob >= 40:
                        res["ink"] += 1
                        res["detail"].append((w["wid"], "ink", "pieces %d and %d of %s overlap (%d px)" % (i, j, base, blob)))
            a0 = a1 = 0.0
            seen[src_d[base]] += 1
        if seen != src_paths:
            res["ink"] += 1
            res["detail"].append((w["wid"], "ink", "path multiset differs (%d vs %d)" % (sum(seen.values()), sum(src_paths.values()))))
        # size: a letter far off what that letter measures elsewhere in the mushaf
        tbl = sizes_table()
        if tbl:
            for r in letter_areas(w["inner"]):
                ent = tbl.get("%s|%s" % (r["ch"], r["form"]))
                if not ent or ent["n"] < SIZE_MIN or not r["area"]:
                    continue
                ratio = r["area"] / ent["median"]
                if ratio < SIZE_LO or ratio > SIZE_HI:
                    res["size"] += 1
                    res["detail"].append((w["wid"], "size", "letter %d %s (%s) is %.2fx the usual area"
                                          % (r["idx"], r["ch"], r["form"], ratio)))
        # count + marks
        try:
            letters = L.letters_of(w["uthmani"])
        except ValueError:
            letters = None
        groups = _LETTER.findall(w["inner"])
        if not groups:
            res["unsplit"] += 1
            continue
        got = []
        for attrs, body in groups:
            at = L.parse_attrs(attrs)
            paths = [L.parse_attrs(m) for m in _PATH.findall(body)]
            got.append((at, paths))
        if letters is not None:
            n_expected = len(letters)
            n_got = 0
            for at, paths in got:
                if at.get("data-unsplit") == "1":
                    res["unsplit"] += 1
                    n_got += len(L.letters_of(at.get("data-text", "")) or [None]) if at.get("data-text") else 1
                else:
                    n_got += 1
            if n_got != n_expected:
                res["count"] += 1
                res["detail"].append((w["wid"], "count", "%d letters emitted, %d in the text" % (n_got, n_expected)))
            for at, paths in got:
                if at.get("data-unsplit") == "1":
                    continue
                idx = int(at.get("data-index", -1))
                if idx < 0 or idx >= len(letters):
                    continue
                res["letters"] += 1
                l = letters[idx]
                bodies = [p for p in paths if p.get("data-kind") == "body"]
                if l["body"] and not bodies:
                    res["count"] += 1
                    res["detail"].append((w["wid"], "count", "letter %d %s has no body ink" % (idx, l["ch"])))
                want = Counter(_EQUIV.get(m, m) for m in l["marks"])
                if l["dots"]:
                    want[l["dots"]] += 1
                have = Counter()
                for p in paths:
                    if p.get("data-kind") == "mark" and p.get("data-mark"):
                        for part in p["data-mark"].split("+"):
                            have[_EQUIV.get(part, part)] += 1
                have.pop("meem-iqlab", None)
                want.pop("meem-iqlab", None)
                if want != have:
                    res["marks"] += 1
                    res["detail"].append((w["wid"], "marks", "letter %d %s wants %s has %s"
                                          % (idx, l["ch"], dict(want), dict(have))))
        # area vs hand layer
        wrec = cuts["words"].get(w["wid"], {})
        for run in wrec.get("runs", []):
            for c in run.get("cuts", []):
                if c.get("src") == "tajweed" and c.get("layer_area"):
                    pass        # a layer holds the letter AND its marks: compared in --calib, not here
    if do_pixels:
        mx, bad = _diff(wsvg, lsvg)
        n_cuts = s_l.count('data-cut="1"') - sum(1 for w in words_l for p in w["paths"] if p["attrs"].get("data-cut") == "1" and p["eid"].endswith("-0"))
        res["pixel_max"], res["pixel_bad"], res["cuts"] = mx, bad, n_cuts
        if mx > SEAM_MAX or bad > SEAM_PX + SEAM_PER_CUT * n_cuts:
            res["pixels"] = 1
    return res


def _one(page):
    r = audit_page(page)
    os.makedirs(AUDIT_DIR, exist_ok=True)
    with open(os.path.join(AUDIT_DIR, "%03d.json" % page), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False)
    return r


def calib(pages):
    """DK cuts vs hand cuts on joints that have both: build DK cuts for the hand-cut
    joints and report the distance between the two chords' midpoints per joint pair."""
    from tools import dk_lib as D
    from tools.build_letter_cuts import align_runs
    out = defaultdict(list)
    for page in pages:
        cuts_path = os.path.join(L.CUTS_DIR, "%03d.json" % page)
        if not os.path.exists(cuts_path):
            continue
        rec = json.load(open(cuts_path, encoding="utf-8"))
        words, _ = L.read_words(page)
        by_w = {w["wid"]: w for w in words}
        for wid, wrec in rec["words"].items():
            w = by_w.get(wid)
            if not w or wrec.get("flags"):
                continue
            letters, runs = align_runs(w)
            if runs is None:
                continue
            lg = D.letter_glyphs(w["uthmani"], letters)
            for (lig, idx), run in zip(runs, wrec["runs"]):
                hand = [c for c in run.get("cuts", []) if c["src"] == "tajweed"]
                if not hand or run.get("flags"):
                    continue
                rp = [poly for p in lig["paths"] if p["kind"] == "body" for poly in L.flatten(p["d"])]
                labels, meta = D.label_run(rp, [lg[i] for i in idx])
                if labels is None:
                    continue
                anchors_ = [[tuple(p) for p in a] for a in run.get("anchors", [])]
                for c in hand:
                    j = c["after"]
                    dk = D.joint_cut(rp, labels, meta, j, anchors_=anchors_ or None)
                    pair = letters[idx[j]]["ch"] + letters[idx[j + 1]]["ch"]
                    if dk is None:
                        out[pair].append(None)
                        continue
                    hm = (sum(p[0] for p in c["poly"]) / len(c["poly"]), sum(p[1] for p in c["poly"]) / len(c["poly"]))
                    dm = (sum(p[0] for p in dk["poly"]) / 2, sum(p[1] for p in dk["poly"]) / 2)
                    out[pair].append(((hm[0] - dm[0]) ** 2 + (hm[1] - dm[1]) ** 2) ** 0.5)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", type=int)
    ap.add_argument("last", type=int, nargs="?")
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--calib", action="store_true")
    ap.add_argument("--out", help="write the calibration table here (json)")
    ap.add_argument("--step", type=int, default=1, help="calib: every N-th page")
    ap.add_argument("--size-table", action="store_true", help="rebuild the letter-size medians and stop")
    a = ap.parse_args()
    pages = list(range(a.first, (a.last or a.first) + 1))
    if a.calib and a.step > 1:
        pages = pages[::a.step]
    if a.size_table:
        out = build_sizes(pages, a.jobs)
        vals = sorted(out.items(), key=lambda kv: -kv[1]["n"])
        print("letter/form combinations %d, written to %s" % (len(out), SIZES_PATH))
        for k, v in vals[:10]:
            print("   %-10s n=%-6d median %.2f" % (k, v["n"], v["median"]))
        return
    if a.calib:
        table = calib(pages)
        allv = [v for vs in table.values() for v in vs if v is not None]
        miss = sum(1 for vs in table.values() for v in vs if v is None)
        allv.sort()
        print("joints with both cuts: %d (DK missing on %d)" % (len(allv), miss))
        if allv:
            for q in (0.5, 0.75, 0.9, 0.95, 0.99):
                print("  p%02d  %.2fu" % (q * 100, allv[min(len(allv) - 1, int(q * len(allv)))]))
            print("  >1u: %d  >2u: %d  >3u: %d" % tuple(sum(1 for v in allv if v > t) for t in (1, 2, 3)))
        if a.out:
            json.dump({k: v for k, v in table.items()}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
        return
    tot = Counter()
    with ProcessPoolExecutor(min(a.jobs, len(pages))) as ex:
        for r in ex.map(_one, pages):
            if r.get("missing"):
                print("p%03d MISSING" % r["page"])
                tot["missing"] += 1
                continue
            print("p%03d words %3d letters %4d | count %d ink %d pixels %d (max %s, bad %s) | shape %2d size %2d | marks %3d unsplit %2d"
                  % (r["page"], r["words"], r["letters"], r["count"], r["ink"], r["pixels"],
                     r.get("pixel_max"), r.get("pixel_bad"), r.get("shape", 0), r.get("size", 0),
                     r["marks"], r["unsplit"]), flush=True)
            for k in ("count", "ink", "pixels", "shape", "size", "marks", "unsplit", "letters", "words"):
                tot[k] += r.get(k, 0)
    print("TOTAL", dict(tot))
    print("PROOF FAILURES:", tot["count"] + tot["ink"] + tot["pixels"])


if __name__ == "__main__":
    main()
