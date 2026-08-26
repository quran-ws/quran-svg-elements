#!/usr/bin/env python3
"""Word-level agreement with MushafDatabase: not just *which line*, but *which ink*.

`audit_reference.py` compares the line number each word sits on, which needs no
geometry and is therefore the cheap half of the outside opinion. The expensive half is
the one the queue is actually made of: a word that has stolen a letter from its
neighbour, or lost one to it, sits on the right line and carries the right mark counts.
Nothing inside our own pipeline can see it.

The reference can. It decomposes the same artwork independently, so once the two
coordinate systems are registered (`refdb.register`, exact to under half a unit off the
ayah medallions) each word has two measured ink extents that must agree.

Three independent comparisons per word, weakest to strongest:

  LINE      the line number, as `audit_reference.py` does it
  EDGE      the right and left edge of the word's LETTER ink, in reference units.
            An edge that has moved by more than `--tol` units is ink one side holds
            and the other does not — the signature of a steal.
  PIECES    how many separate letter groups the word is drawn from. This is
            vectorisation-dependent (they ligature differently) so it is reported as a
            distribution, never as a pass/fail.

Only words both sources agree are the same word are compared: the same key AND the
same letter skeleton. Where the two split an ayah differently the key lines up while
the words do not, and comparing those manufactures errors that do not exist.

    python3 tools/audit_ref_words.py "<ref>/SVG V1.01"
    python3 tools/audit_ref_words.py "<ref>/SVG V1.01" 1 50 --jobs 8 --tol 2.0
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
from collections import Counter

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import refdb                                                            # noqa: E402

PIPE = os.environ.get("QSVG_PIPE", os.path.join(ROOT, "tools", "assign_words.py"))
_spec = importlib.util.spec_from_file_location("assign_words", PIPE)
aw = importlib.util.module_from_spec(_spec)
sys.modules["assign_words"] = aw
_spec.loader.exec_module(aw)

_cap = {}
_orig = aw.rewrite


def _spy(page, a):
    _cap["a"] = a
    return _orig(page, a)


aw.rewrite = _spy

REFDIR = None
TOL = 2.0

# Dot units, on both sides. A dot that has drifted to a neighbour moves no letter, so it
# changes neither word's body extent and the EDGE test cannot see it — but it is still
# ink in the wrong word. Seven such words on the first sixty pages were the whole of our
# remaining dot gap against the reference.
_DOTU = {"dot": 1, "two-dots": 2, "three-dots": 3, "two dots": 2, "three dots": 3}


def our_medallions(pg):
    """Our ayah medallion centres, keyed by (surah, ayah) — the registration landmarks."""
    f = os.path.join(ROOT, "mushafs", "hafs", "kfqc", "json", "%03d.json" % pg)
    if not os.path.exists(f):
        return {}
    out = {}
    for e in json.load(open(f, encoding="utf-8")):
        try:
            out[(int(e["surahNumber"]), int(e["ayahNumber"]))] = (float(e["x"]), float(e["y"]))
        except (KeyError, ValueError):
            continue
    return out


def ours(pg):
    """{(surah, ayah, pos): record} for one page, from the pipeline under test."""
    with contextlib.redirect_stdout(io.StringIO()):
        aw.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    out = {}
    for w, at in _cap["a"]:
        if not w:
            continue
        els = [e for a in at for e in a["els"]]
        body = [e for e in els if e["kind"] == "body"]
        if not body:
            continue
        lns = [e.get("line") for e in body if e.get("line")]
        out[(w["surah"], w["ayah"], w["pos"])] = {
            "line": max(set(lns), key=lns.count) if lns else 0,
            "x1": min(e["x1"] for e in body), "x2": max(e["x2"] for e in body),
            "y1": min(e["y1"] for e in body), "y2": max(e["y2"] for e in body),
            "dots": sum(_DOTU.get(e.get("mark") or "", 0)
                        for e in els if not e.get("mkpart")),
            "nbody": len(body),
            "nmark": len([e for e in els if e["kind"] != "body"]),
            "text": w["uthmani"],
        }
    return out


def registration(pg, rp, ref, mine):
    """Fit this page's frame, and say how far the two landmark sets disagree.

    Words first, medallions second. Every page has a hundred-odd words both sources
    agree on and only six to twenty medallions, and the medallions come from ayah
    polygon data that is known broken on some pages. `cross` is how far apart the two
    fits land: a page where they disagree by more than a unit is one to look at before
    believing anything it reports.
    """
    xs, ys = [], []
    for k in set(ref) & set(mine):
        r, m = ref[k], mine[k]
        if "body_x1" not in r or r["skel"] != refdb.skeleton(m["text"]):
            continue
        # Both edges, so a word that is right in one half and wrong in the other still
        # contributes its good end. Baselines carry y: the bottom of the letter ink sits
        # on the line in both sources, while the top of it depends on which tall letter
        # the word happens to contain.
        xs.append((m["x1"], r["body_x1"]))
        xs.append((m["x2"], r["body_x2"]))
        if "body_y2" in r:
            ys.append((m["y2"], r["body_y2"]))
    mx, my = refdb.medallion_pairs(our_medallions(pg), rp)
    reg_w = refdb.register(xs, ys or my, "words") if xs and (ys or my) else None
    reg_m = refdb.register(mx, my, "medallions") if len(mx) >= 3 else None
    if reg_w is None:
        return reg_m, None
    if reg_m is None:
        return reg_w, None
    return reg_w, round(abs(reg_w.bx - reg_m.bx), 3)


def scan(pg):
    """Compare one page. Returns (page, result-dict) — never raises."""
    p = os.path.join(REFDIR, "%03d.svg" % pg)
    if not os.path.exists(p):
        return pg, {"skip": "no reference page"}
    try:
        rp = refdb.read_page(p)
        ref = refdb.fold(rp)
        mine = ours(pg)
        reg, cross = registration(pg, rp, ref, mine)
    except Exception as exc:
        return pg, {"err": "%s: %s" % (type(exc).__name__, exc)}
    if reg is None:
        return pg, {"skip": "no registration", "ref_words": len(ref), "our_words": len(mine)}

    res = {"reg": [reg.ax, reg.bx, reg.ay, reg.by, reg.mad, reg.basis, reg.n],
           "cross": cross,
           "ref_words": len(ref), "our_words": len(mine),
           "only_ref": len(set(ref) - set(mine)), "only_ours": len(set(mine) - set(ref)),
           "text_mismatch": 0, "compared": 0, "line_off": 0, "dot_off": 0,
           "edges": [], "flags": [], "pieces": Counter()}

    for k in sorted(set(ref) & set(mine)):
        r, m = ref[k], mine[k]
        if r["skel"] != refdb.skeleton(m["text"]):
            res["text_mismatch"] += 1
            continue
        if "body_x1" not in r:                    # a word the reference drew no letters for
            continue
        res["compared"] += 1
        if r["line"] and m["line"] and r["line"] != m["line"]:
            res["line_off"] += 1
        # Right edge and left edge, both in reference units. Arabic runs right to left,
        # so x2 is where the word starts and x1 is where it ends.
        d_right = reg.x(m["x2"]) - r["body_x2"]
        d_left = reg.x(m["x1"]) - r["body_x1"]
        res["edges"].append((round(d_right, 2), round(d_left, 2)))
        res["pieces"][(m["nbody"] - r["nbody"])] += 1
        rdots = sum(_DOTU.get(lab, 0) for kind, lab, _b in r["pieces"] if kind == "dots")
        if rdots != m["dots"]:
            res["dot_off"] += 1
        if abs(d_right) > TOL or abs(d_left) > TOL or rdots != m["dots"]:
            res["flags"].append({
                "page": pg, "key": "%d:%d:%d" % k, "word": r["hafs"],
                "d_right": round(d_right, 2), "d_left": round(d_left, 2),
                "ref_x": [round(r["body_x1"], 2), round(r["body_x2"], 2)],
                "our_x": [round(reg.x(m["x1"]), 2), round(reg.x(m["x2"]), 2)],
                "ref_line": r["line"], "our_line": m["line"],
                "ref_bodies": r["nbody"], "our_bodies": m["nbody"],
                "our_dots": m["dots"], "ref_dots": rdots,
                "mad": round(reg.mad, 3), "cross": cross,
            })
    res["pieces"] = dict(res["pieces"])
    return pg, res


def main(argv=None):
    global REFDIR, TOL
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("refdir", help='the reference "SVG V1.01" directory')
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--tol", type=float, default=2.0,
                    help="edge disagreement, in reference units, that counts as a defect")
    ap.add_argument("--json", help="write the flagged words here")
    args = ap.parse_args(argv)
    REFDIR, TOL = args.refdir, args.tol

    from multiprocessing import Pool
    tot = Counter()
    flags, edges, pieces, bad_pages, shaky = [], [], Counter(), [], []
    resid = 0.0
    with Pool(args.jobs, maxtasksperchild=6) as pool:
        for pg, r in pool.imap_unordered(scan, range(args.first, args.last + 1)):
            if "err" in r:
                bad_pages.append((pg, r["err"]))
                continue
            if "skip" in r:
                tot["skipped"] += 1
                bad_pages.append((pg, r["skip"]))
                continue
            tot["pages"] += 1
            for f in ("ref_words", "our_words", "only_ref", "only_ours",
                      "text_mismatch", "compared", "line_off", "dot_off"):
                tot[f] += r[f]
            flags += r["flags"]
            edges += r["edges"]
            pieces.update({int(k): v for k, v in r["pieces"].items()})
            resid = max(resid, r["reg"][4])
            if r.get("cross") is not None and r["cross"] > 1.0:
                shaky.append((pg, r["cross"]))

    n = max(1, len(edges))
    allde = sorted(abs(d) for e in edges for d in e)
    def pct(p):
        return allde[min(len(allde) - 1, int(p * len(allde)))] if allde else 0.0

    print("pages compared %d   (skipped/failed %d)   worst per-page registration MAD %.2f"
          % (tot["pages"], len(bad_pages), resid))
    if shaky:
        print("pages where the word fit and the medallion fit disagree by >1 unit: %s"
              % ", ".join("p%d(%.1f)" % t for t in sorted(shaky, key=lambda t: -t[1])[:10]))
    print("words: reference %d, ours %d   only-ref %d   only-ours %d"
          % (tot["ref_words"], tot["our_words"], tot["only_ref"], tot["only_ours"]))
    print("same key but a different word (ayah split differently): %d" % tot["text_mismatch"])
    print("COMPARABLE WORDS: %d" % tot["compared"])
    print()
    print("LINE  disagreements: %d   (%.4f%% of comparable)"
          % (tot["line_off"], 100.0 * tot["line_off"] / max(1, tot["compared"])))
    print("DOTS  disagreements: %d   (%.4f%% of comparable)"
          % (tot["dot_off"], 100.0 * tot["dot_off"] / max(1, tot["compared"])))
    print("EDGE  disagreements over %.1f units: %d words   (%.3f%%)"
          % (TOL, len(flags), 100.0 * len(flags) / max(1, tot["compared"])))
    print("      |edge error| percentiles (ref units): "
          "p50 %.2f  p90 %.2f  p99 %.2f  p99.9 %.2f  max %.2f"
          % (pct(.50), pct(.90), pct(.99), pct(.999), allde[-1] if allde else 0))
    for t in (1.0, 2.0, 3.0, 5.0, 10.0):
        k = sum(1 for e in edges if abs(e[0]) > t or abs(e[1]) > t)
        print("      words with an edge off by more than %5.1f: %6d  (%.3f%%)"
              % (t, k, 100.0 * k / n))
    print()
    print("PIECES  our letter-group count minus theirs:")
    for d in sorted(pieces):
        print("      %+3d  %6d  (%.2f%%)" % (d, pieces[d], 100.0 * pieces[d] / max(1, sum(pieces.values()))))
    if bad_pages:
        print("\npages not compared:")
        for pg, why in bad_pages[:15]:
            print("   p%-4d %s" % (pg, why))
    if flags:
        print("\nworst disagreements:")
        for f in sorted(flags, key=lambda f: -max(abs(f["d_right"]), abs(f["d_left"])))[:15]:
            print("   p%-4d %-11s %-16s right %+7.2f  left %+7.2f  bodies %d vs %d"
                  % (f["page"], f["key"], f["word"], f["d_right"], f["d_left"],
                     f["our_bodies"], f["ref_bodies"]))
    out = args.json or os.path.join(ROOT, "docs", "defects", "reference_words.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"tol": TOL, "totals": dict(tot), "flags": flags,
                   "pieces": {str(k): v for k, v in pieces.items()},
                   "not_compared": bad_pages}, fh, ensure_ascii=False, indent=1)
    print("\nwrote %s (%d flagged words)" % (out, len(flags)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
