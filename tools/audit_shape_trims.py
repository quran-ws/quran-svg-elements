#!/usr/bin/env python3
"""What the hand-drawn shape corrections say about the build.

    python3 tools/audit_shape_trims.py            # ranked table
    python3 tools/audit_shape_trims.py --json out.json

A trim in `docs/defects/letter_shape_verdicts.jsonl` is a loop Abdullah drew around the
ink that IS the letter, on one example word. All 87 of them mean the ink INSIDE the loop
(87 of 87, measured 2026-09-08), so the loop is an exact statement of that letter's mask.

That makes each trim two things at once:

  a LABEL   -- the pixels inside the loop belong to this letter and the rest of the run
               does not, which is a stronger statement than a cut line, and
  an AUDIT  -- the distance between the loop and what the build actually emitted is a
               measured defect, and because the trim is attached to a SHAPE CLUSTER it
               indicts every letter drawn that way, not just the one example.

The leverage is the cluster: a shape drawn 3,298 times is one drawing and 3,298 letters.
This tool reports IoU per trim and ranks by how many letters the shape carries, so the
worst-first order is by ink at stake rather than by how wrong one example looks.
"""
import argparse
import json
from collections import Counter
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402
from tools.build_letter_cuts import align_runs   # noqa: E402

VERDICTS = os.path.join(L.ROOT, "docs", "defects", "letter_shape_verdicts.jsonl")
_LETTER = re.compile(r'<g class="letter"([^>]*)>(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>')
Z = 10
PAD = 1.0


def _word_letters(page, wid):
    words, _ = L.read_words(page, L.LETTERS_SVG)
    for w in words:
        if w["wid"] != wid:
            continue
        out = []
        for m in _LETTER.finditer(w["inner"]):
            at = L.parse_attrs(m.group(1))
            polys = []
            for pm in _PATH.finditer(m.group(2)):
                pa = L.parse_attrs(pm.group(1))
                if pa.get("data-kind") == "body" and pa.get("d"):
                    polys += L.flatten(pa["d"])
            if polys:
                out.append((int(at.get("data-index", -1)), at.get("data-text", ""),
                            at.get("data-run", ""), polys))
        return out
    return []


def loop_mask(trim, x0, y0, shape):
    """The drawn loop as a mask on the word's raster grid.

    The grid is taken from the ink raster rather than recomputed: L.raster rounds its
    own way, and a mask one pixel off does not broadcast against it.
    """
    from PIL import Image, ImageDraw
    H, W = shape
    im = Image.new("1", (W, H), 0)
    pts = [(int((qx - x0) * Z), int((qy - y0) * Z)) for qx, qy in trim["page_path"]]
    if trim.get("kind") == "loop":
        ImageDraw.Draw(im).polygon(pts, fill=1)
    else:
        ImageDraw.Draw(im).line(pts, fill=1, width=3)
    return np.array(im, dtype=bool)


def _run_ink(letters, idx, x0, y0, w, h):
    ps = [p for i, _, _, pp in letters if i in idx for p in pp]
    return L.raster(ps, x0, y0, w, h, Z) if ps else None


def measure(r):
    """How far the emitted letter is from the letter Abdullah drew."""
    letters = _word_letters(r["page"], r["wid"])
    if not letters:
        return dict(r, ok=False, why="word not in the build")
    allp = [p for _, _, _, ps in letters for p in ps]
    bx0, by0, bx1, by1 = L.bbox(allp)
    x0, y0 = bx0 - PAD, by0 - PAD
    w, h = bx1 - bx0 + 2 * PAD, by1 - by0 + 2 * PAD
    ink = L.raster(allp, x0, y0, w, h, Z)
    mine = [p for i, _, _, ps in letters if i == r["index"] for p in ps]
    cur = (L.raster(mine, x0, y0, w, h, Z) if mine
           else np.zeros_like(ink))
    poly = loop_mask(r["trim"], x0, y0, ink.shape)
    want = ink & (poly if r["trim"].get("select", "in") == "in" else ~poly)
    inter = int((cur & want).sum())
    union = int((cur | want).sum())
    iou = inter / union if union else 0.0
    tot = max(int(ink.sum()), 1)
    run = [t for i, t, _, _ in letters if i == r["index"]]
    # which run of the word holds this letter, and does the drawn ink lie in it?
    kind, run_text = "label", ""
    try:
        words, _ = L.read_words(r["page"])
        src = [x for x in words if x["wid"] == r["wid"]]
        _, runs = align_runs(src[0]) if src else (None, None)
        for lig, idx in (runs or []):
            if r["index"] in idx:
                run_text = lig["text"]
                if len(idx) < 2:
                    kind = "single-letter run"        # the split is not what is wrong
                elif not (want & cur).any() and not (want & _run_ink(letters, idx, x0, y0, w, h)).any():
                    kind = "cross-run"                # the ink he means is in another run
                break
    except Exception:
        pass
    return {"id": r["id"], "letter": r["letter"], "form": r["form"], "n": r["n"],
            "kind": kind, "run": run_text,
            "page": r["page"], "wid": r["wid"], "index": r["index"],
            "text": run[0] if run else "",
            "iou": round(iou, 3),
            "missing": round(1.0 - inter / max(int(want.sum()), 1), 3),
            "extra": round(1.0 - inter / max(int(cur.sum()), 1), 3),
            "want_share": round(100.0 * int(want.sum()) / tot, 1),
            "cur_share": round(100.0 * int(cur.sum()) / tot, 1),
            "ok": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--json")
    ap.add_argument("--iou", type=float, default=0.90,
                    help="a trim the build already satisfies above this IoU is settled")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(VERDICTS, encoding="utf-8") if l.strip()]
    trims = [r for r in rows if r["verdict"] == "trim"]
    with ProcessPoolExecutor(min(a.jobs, max(len(trims), 1))) as ex:
        res = list(ex.map(measure, trims))
    good = [r for r in res if r.get("ok")]
    bad = [r for r in res if not r.get("ok")]
    good.sort(key=lambda r: -(1.0 - r["iou"]) * r["n"])
    settled = [r for r in good if r["iou"] >= a.iou]
    open_ = [r for r in good if r["iou"] < a.iou]
    carried = sum(r["n"] for r in good)
    at_stake = sum(r["n"] for r in open_)
    print("%d trims | %d already met by the build (IoU >= %.2f) | %d disagree"
          % (len(good), len(settled), a.iou, len(open_)))
    print("letters drawn with these shapes: %s, of which %s sit under a shape the build "
          "gets wrong" % ("{:,}".format(carried), "{:,}".format(at_stake)))
    kinds = Counter(r.get("kind", "label") for r in good)
    print("what each correction can say: " + ", ".join(
        "%s %d" % (k, v) for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])))
    for k in ("single-letter run", "cross-run"):
        for r in [x for x in good if x.get("kind") == k]:
            print("   %-17s %s %s p%-4d %-12s idx%d run %s  (%s letters)"
                  % (k, r["letter"], r["form"], r["page"], r["wid"], r["index"],
                     r.get("run", "?"), "{:,}".format(r["n"])))
    if bad:
        print("unreadable: %d" % len(bad))
    print()
    print("%-13s %-3s %-7s %7s  %5s %8s %7s  %s"
          % ("shape", "ch", "form", "letters", "IoU", "missing", "extra", "example"))
    for r in open_[:40]:
        print("%-13s %-3s %-7s %7s  %5.2f %7.0f%% %6.0f%%  p%-4d %-12s idx%d"
              % (r["id"], r["letter"], r["form"], "{:,}".format(r["n"]), r["iou"],
                 100 * r["missing"], 100 * r["extra"], r["page"], r["wid"], r["index"]))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"trims": good, "unreadable": bad}, f, ensure_ascii=False, indent=1)
        print("\nwritten to", a.json)


if __name__ == "__main__":
    main()
