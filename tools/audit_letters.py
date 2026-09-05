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


def audit_page(page, do_pixels=True):
    lsvg = os.path.join(L.LETTERS_SVG, "%03d.svg" % page)
    wsvg = os.path.join(L.WORDS_SVG, "%03d.svg" % page)
    res = {"page": page, "count": 0, "ink": 0, "pixels": 0, "marks": 0, "area": 0, "unsplit": 0,
           "letters": 0, "words": 0, "detail": []}
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
            a0 = L.area(src_d[base])
            a1 = sum(L.area(d) for d in ds)
            # no two pieces of one contour may overlap
            import pathops as _po
            paths = [L.to_path(d) for d in ds]
            for i in range(len(paths)):
                for j in range(i + 1, len(paths)):
                    ov = _po.op(paths[i], paths[j], _po.PathOp.INTERSECTION)
                    ov.simplify()
                    if abs(ov.area) > 0.01:
                        res["ink"] += 1
                        res["detail"].append((w["wid"], "ink", "pieces %d and %d of %s overlap (%.3f)" % (i, j, base, abs(ov.area))))
            if abs(a1 - a0) > max(0.005 * a0, 0.02):
                res["ink"] += 1
                res["detail"].append((w["wid"], "ink", "pieces of %s sum %.3f vs %.3f" % (base, a1, a0)))
            seen[src_d[base]] += 1
        if seen != src_paths:
            res["ink"] += 1
            res["detail"].append((w["wid"], "ink", "path multiset differs (%d vs %d)" % (sum(seen.values()), sum(src_paths.values()))))
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
    a = ap.parse_args()
    pages = list(range(a.first, (a.last or a.first) + 1))
    if a.calib and a.step > 1:
        pages = pages[::a.step]
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
            print("p%03d words %3d letters %4d | count %d ink %d pixels %d (max %s, bad %s) | marks %3d unsplit %2d"
                  % (r["page"], r["words"], r["letters"], r["count"], r["ink"], r["pixels"],
                     r.get("pixel_max"), r.get("pixel_bad"), r["marks"], r["unsplit"]), flush=True)
            for k in ("count", "ink", "pixels", "marks", "unsplit", "letters", "words"):
                tot[k] += r[k]
    print("TOTAL", dict(tot))
    print("PROOF FAILURES:", tot["count"] + tot["ink"] + tot["pixels"])


if __name__ == "__main__":
    main()
