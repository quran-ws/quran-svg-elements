#!/usr/bin/env python3
"""Where the exact cut moved a boundary: two builds side by side, biggest change first.

    QSVG_LETTERS_TAG=model python3 tools/build_split_review_page.py --against raster

The exact splitter cuts on the run's own curves instead of a pixel staircase, so letter
boundaries move. The gates say the ink is conserved and the pieces are cleaner, but a
boundary that moves is a decision, and only an eye can say whether it moved the right way.

This renders the words where the two builds disagree most, each letter in its own colour,
old beside new. Nothing is asked of the reviewer but a look: what is wanted is the answer
to one question -- did the letter boundaries get better or worse.
"""
import argparse
import base64
import html
import io
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import letters_lib as L          # noqa: E402

_LETTER = re.compile(r'<g class="letter"([^>]*)>(.*?)</g>', re.S)
_PATH = re.compile(r'<path ([^>]*?)/>')
OUT = os.path.join(L.ROOT, "docs", "defects", "split_review.html")
COLS = [(200, 30, 30), (30, 110, 220), (20, 150, 60), (225, 150, 10),
        (150, 60, 200), (0, 150, 160), (150, 90, 40), (90, 90, 90)]
Z = 13


def word_letters(svg_dir, page, wid):
    words, _ = L.read_words(page, svg_dir)
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
                out.append((int(at.get("data-index", -1)), at.get("data-text", ""), polys))
        return out
    return []


def png(rgb):
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def draw(letters, frame):
    x0, y0, w, h = frame
    allp = [p for _, _, ps in letters for p in ps]
    if not allp:
        return None
    ink = L.raster(allp, x0, y0, w, h, Z)
    rgb = np.full(ink.shape + (3,), 255, np.uint8)
    for i, (_, _, ps) in enumerate(letters):
        m = L.raster(ps, x0, y0, w, h, Z)
        hh, ww = min(m.shape[0], ink.shape[0]), min(m.shape[1], ink.shape[1])
        rgb[:hh, :ww][m[:hh, :ww]] = COLS[i % len(COLS)]
    return png(rgb[::-1])


def page_diffs(args):
    page, dir_a, dir_b = args
    try:
        a_words, _ = L.read_words(page, dir_a)
        b_words, _ = L.read_words(page, dir_b)
    except Exception:
        return []
    b_by = {w["wid"]: w for w in b_words}
    out = []
    for w in a_words:
        if w["wid"] not in b_by:
            continue
        la = word_letters(dir_a, page, w["wid"])
        lb = word_letters(dir_b, page, w["wid"])
        if not la or not lb or len(la) != len(lb):
            continue
        allp = [p for _, _, ps in la for p in ps] + [p for _, _, ps in lb for p in ps]
        x0, y0, x1, y1 = L.bbox(allp)
        pad = 0.6
        frame = (x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad)
        diff = 0
        for (_, _, pa), (_, _, pb) in zip(la, lb):
            ma = L.raster(pa, *frame, Z)
            mb = L.raster(pb, *frame, Z)
            hh, ww = min(ma.shape[0], mb.shape[0]), min(ma.shape[1], mb.shape[1])
            diff += int((ma[:hh, :ww] ^ mb[:hh, :ww]).sum())
        if diff:
            out.append((diff, page, w["wid"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--against", default="raster",
                    help="tag of the other build (…/.cache/letters-svg-<tag>)")
    ap.add_argument("--pages", type=int, nargs=2, default=(1, 120))
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    dir_b = L.LETTERS_SVG
    dir_a = os.path.join(L.ROOT, ".cache", "letters-svg-" + a.against, "hafs-kfqc")
    if not os.path.isdir(dir_a):
        raise SystemExit("no build at " + dir_a)
    pages = list(range(a.pages[0], a.pages[1] + 1))
    rows = []
    with ProcessPoolExecutor(min(a.jobs, len(pages))) as ex:
        for r in ex.map(page_diffs, [(p, dir_a, dir_b) for p in pages]):
            rows += r
    rows.sort(reverse=True)
    cards = []
    for diff, page, wid in rows[:a.top]:
        la = word_letters(dir_a, page, wid)
        lb = word_letters(dir_b, page, wid)
        allp = [p for _, _, ps in la for p in ps] + [p for _, _, ps in lb for p in ps]
        x0, y0, x1, y1 = L.bbox(allp)
        pad = 0.6
        frame = (x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad)
        ia, ib = draw(la, frame), draw(lb, frame)
        if not ia or not ib:
            continue
        text = "".join(t for _, t, _ in lb)
        cards.append(
            '<div class=card><div class=hd>p%d &middot; %s &middot; <b class=ar>%s</b>'
            ' &middot; %s px moved</div><div class=row>'
            '<figure><img src="%s"><figcaption>before &mdash; raster cut</figcaption></figure>'
            '<figure><img src="%s"><figcaption>after &mdash; exact cut</figcaption></figure>'
            '</div></div>' % (page, html.escape(wid), html.escape(text),
                              "{:,}".format(diff), ia, ib))
    doc = ("<!doctype html><meta charset=utf-8><title>Exact cut: what moved</title>"
           "<style>body{font-family:system-ui;margin:20px;background:#fafafa}"
           ".card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px;"
           "margin-bottom:14px}.hd{font-size:13px;color:#555;margin-bottom:6px}"
           ".ar{font-size:20px}.row{display:flex;gap:22px;align-items:flex-end;flex-wrap:wrap}"
           "figure{margin:0}figcaption{font-size:12px;color:#777;margin-top:4px}"
           "img{display:block;max-height:150px;width:auto}</style>"
           "<h1>Where the exact cut moved a letter boundary</h1>"
           "<p>The cut now runs along the letter's own curves instead of a pixel staircase, "
           "so boundaries move. The gates say the ink is conserved and the pieces are "
           "cleaner. What they cannot say is whether a boundary moved the RIGHT way. Each "
           "row is one word, every letter in its own colour, the old cut beside the new, "
           "worst disagreement first. <b>Only one question is being asked: did these get "
           "better or worse?</b></p>" + "".join(cards))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(doc)
    print("%s: %d words shown of %d that changed" % (a.out, len(cards), len(rows)))


if __name__ == "__main__":
    main()
