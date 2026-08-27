#!/usr/bin/env python3
"""Pixel-identity audit: the decomposed build vs the original artwork, every page.

THE invariant of this project — the decomposition may regroup ink but never
move, add, or remove it. Found violated 2026-08-27 by Abdullah's eye on p17:
the split-word emitter sent elements to another path's home without
compensating for the frame difference (a displaced قلى copy) and re-emitted a
fully-drained source path verbatim (the duplicate). The bench gate renders two
pages; this audit renders all 604, because the defect lived only on pages the
gate never drew.

    python3 tools/audit_pixels.py 1 604 [jobs]     # ~jobs-parallel, prints per-page
    python3 tools/audit_pixels.py 17               # one page

A page passes when at most SEAM_PX pixels differ by more than TOL (of 255) at
WIDTH px wide, re-verified at 2200px. Thresholds sit inside measured empty
bands: strength — AA jitter tops out ~24, hairline seams where a split
stroke's halves abut render ~26-60, true defects 100+; count — seams produce
1-3 px per page, the smallest real defect produced 100+ (p17's displaced
قلى pair), nothing in between over all 604 pages on 2026-08-27.
"""
import json, os, subprocess, sys, tempfile

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 24
SEAM_PX = 10
WIDTH = 1400


def _diff_at(pg, svg_path, width):
    from PIL import Image, ImageChops
    with tempfile.TemporaryDirectory() as td:
        pa, pb = os.path.join(td, "a.png"), os.path.join(td, "b.png")
        subprocess.run(["rsvg-convert", "-w", str(width), "-b", "white",
                        ROOT + "/mushafs/hafs/kfqc/svg/%03d.svg" % pg, "-o", pa],
                       check=True)
        subprocess.run(["rsvg-convert", "-w", str(width), "-b", "white",
                        svg_path, "-o", pb], check=True)
        h = ImageChops.difference(Image.open(pa).convert("L"),
                                  Image.open(pb).convert("L")).histogram()
    mx = max((i for i, n in enumerate(h) if n), default=0)
    return mx, sum(h[TOL + 1:])


def contour_conservation(pg, svg):
    """Structural proof that no ink was added or removed: the multiset of
    contour bodies (path text after each moveto — position-independent) must
    match the artwork exactly. A duplicate (p604's stacked basmalah) or a
    dropped contour shows here even when the raster can't see it; a MOVED
    contour conserves its body and is the raster check's job."""
    import re as _re
    from collections import Counter as _C
    orig = open(ROOT + "/mushafs/hafs/kfqc/svg/%03d.svg" % pg, encoding="utf-8").read()
    def tails(s):
        # normalise what the emitter may legitimately rewrite on a SEPARATED
        # contour: its relative moveto becomes absolute and the implicit
        # lineto after it gains an explicit l/L (add_line_structure.build_d).
        c = _C()
        for d in _re.findall(r'\bd="([^"]+)"', s):
            _NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
            for t in _re.split(r"[Mm]\s*%s[,\s]*%s" % (_NUM, _NUM), d)[1:]:
                t = t.lstrip(" ,")
                if t[:1] in "lL":
                    t = t[1:].lstrip(" ,")
                c[t] += 1
        return c
    to, tu = tails(orig), tails(svg)
    extra = sum((tu - to).values())
    missing = sum((to - tu).values())
    return extra, missing


def check_page(pg):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import assign_words as aw
    _, svg, _, _ = aw.assign_page("hafs/kfqc", pg, ROOT + "/.cache/words")
    extra, missing = contour_conservation(pg, svg)
    import re as _re
    # a mark named "x+y" must never ship: one outline carrying two marks is
    # split into two named marks before emission (Abdullah 2026-08-27);
    # measured zero over all 604 pages after the p1/p2 relabel
    compound = len(_re.findall(r'data-mark="[^"]*\+[^"]*"', svg))
    with tempfile.TemporaryDirectory() as td:
        ours = os.path.join(td, "ours.svg")
        open(ours, "w").write(svg)
        mx, bad = _diff_at(pg, ours, WIDTH)
        if bad:
            # a defect exists at every scale; a hairline straddling one sample
            # grid does not (p142: one 124-strong pixel at 1400px, zero at
            # 2600px). Count only what reproduces.
            mx2, bad2 = _diff_at(pg, ours, 2200)
            if not bad2:
                mx, bad = mx2, 0
    return {"page": pg, "max": mx, "bad_px": bad, "compound_marks": compound,
            "contours_extra": extra, "contours_missing": missing}


def main():
    args = [a for a in sys.argv[1:] if a.isdigit()]
    a = int(args[0]) if args else 1
    b = int(args[1]) if len(args) > 1 else a if args else 604
    jobs = int(args[2]) if len(args) > 2 else 16
    if os.environ.get("QSVG_PXCHILD"):
        r = check_page(a)
        print(json.dumps(r))
        return
    import concurrent.futures as cf
    fails = []
    def run(pg):
        env = dict(os.environ, QSVG_PXCHILD="1", QSVG_ROOT=ROOT)
        out = subprocess.run([sys.executable, os.path.abspath(__file__), str(pg)],
                             capture_output=True, text=True, env=env)
        try:
            return json.loads(out.stdout.strip().splitlines()[-1])
        except Exception:
            return {"page": pg, "max": -1, "bad_px": -1,
                    "error": (out.stderr or out.stdout)[-300:]}
    with cf.ThreadPoolExecutor(jobs) as ex:
        for r in ex.map(run, range(a, b + 1)):
            if (r["bad_px"] > SEAM_PX or r["bad_px"] < 0
                    or r.get("contours_extra") or r.get("contours_missing")
                    or r.get("compound_marks")):
                fails.append(r)
                print("FAIL p%03d max %d bad_px %d extra %s missing %s %s"
                      % (r["page"], r["max"], r["bad_px"],
                         r.get("contours_extra"), r.get("contours_missing"),
                         r.get("error", "")))
    print("\npages %d-%d | FAILURES: %d" % (a, b, len(fails)))
    if fails:
        json.dump(fails, open(os.path.join(ROOT, ".cache", "pixel_fails.json"), "w"),
                  indent=1)
        print("wrote .cache/pixel_fails.json")
        sys.exit(1)
    print("every page pixel-identical (tol %d/255, seam allowance %d px, at %dpx)"
          % (TOL, SEAM_PX, WIDTH))


if __name__ == "__main__":
    main()
