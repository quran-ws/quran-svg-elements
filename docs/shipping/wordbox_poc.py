#!/usr/bin/env python3
"""Proof of concept: per-word bounding boxes derived from a shipped page.

Answers one question in the shipping proposal — "can a consumer highlight a
word without rendering the page, using only what ships today?"  It can, but
only by parsing path data and composing three transforms, which is exactly the
work a shipped box index would remove.

Boxes are the CONTROL-POINT hull of each word's path data (a superset of the
true outline; Bezier control points lie outside the curve).  A production
builder would take exact extents from the pipeline instead.

Usage:  python3 docs/shipping/wordbox_poc.py 3          # show boxes for a page
        python3 docs/shipping/wordbox_poc.py --all      # build + size the index
"""
import json
import gzip
import os
import re
import sys

try:
    import brotli
except ImportError:
    brotli = None

ROOT = os.environ.get("QSVG_ROOT", os.getcwd())
SRC = os.path.join(ROOT, ".cache/words-svg/hafs-kfqc")

_NUM = re.compile(r'-?\d*\.?\d+(?:[eE][-+]?\d+)?')
_CMD = re.compile(r'[MmLlHhVvCcSsQqTtAaZz]')


def parse_transform(t):
    """Return (a,b,c,d,e,f) for the matrix/translate/scale chain in t."""
    M = (1, 0, 0, 1, 0, 0)
    for name, args in re.findall(r'(matrix|translate|scale)\s*\(([^)]*)\)', t):
        v = [float(x) for x in _NUM.findall(args)]
        if name == "matrix":
            N = tuple(v)
        elif name == "translate":
            N = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        else:
            N = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        a, b, c, d, e, f = M
        na, nb, nc, nd, ne, nf = N
        M = (a*na + c*nb, b*na + d*nb,
             a*nc + c*nd, b*nc + d*nd,
             a*ne + c*nf + e, b*ne + d*nf + f)
    return M


def apply(M, x, y):
    a, b, c, d, e, f = M
    return a*x + c*y + e, b*x + d*y + f


def path_points(d):
    """Yield absolute (x,y) for every coordinate pair, control points included."""
    x = y = 0.0
    i = 0
    tokens = []
    for m in _CMD.finditer(d):
        tokens.append((m.group(0), m.start(), m.end()))
    for k, (cmd, s, e) in enumerate(tokens):
        end = tokens[k+1][1] if k+1 < len(tokens) else len(d)
        nums = [float(v) for v in _NUM.findall(d[e:end])]
        rel = cmd.islower()
        c = cmd.upper()
        if c == "Z":
            continue
        step = {"M": 2, "L": 2, "T": 2, "H": 1, "V": 1,
                "C": 6, "S": 4, "Q": 4, "A": 7}[c]
        for j in range(0, len(nums) - step + 1, step):
            g = nums[j:j+step]
            if c == "H":
                x = x + g[0] if rel else g[0]
                yield x, y
            elif c == "V":
                y = y + g[0] if rel else g[0]
                yield x, y
            elif c == "A":
                nx, ny = g[5], g[6]
                x, y = (x + nx, y + ny) if rel else (nx, ny)
                yield x, y
            else:
                bx, by = (x, y) if rel else (0.0, 0.0)
                for p in range(0, step, 2):
                    yield bx + g[p], by + g[p+1]
                x, y = bx + g[step-2], by + g[step-1]


_WORD = re.compile(r'<g class="word" ([^>]*)>')


def page_boxes(n):
    s = open(os.path.join(SRC, f"{n:03d}.svg")).read()
    root = parse_transform(re.search(r'<g transform="(matrix[^"]+)"', s).group(1))
    out = []
    # walk line groups so each word inherits its own line transform
    chunks = s.split('<g class="line" data-line="')
    for ch in chunks[1:]:
        line = int(ch.split('"', 1)[0])
        lm = re.match(r'[^"]*"><g transform="([^"]+)">', ch)
        if not lm:
            continue
        M = parse_transform(lm.group(1))
        a, b, c, d, e, f = root
        na, nb, nc, nd, ne, nf = M
        F = (a*na + c*nb, b*na + d*nb, a*nc + c*nd, b*nc + d*nd,
             a*ne + c*nf + e, b*ne + d*nf + f)
        chunk = ch
        pieces = chunk.split('<g class="word" ')
        for p in pieces[1:]:
            head, body = p.split('>', 1)
            body = body.split('<g class="word"')[0]
            wid = re.search(r'data-wid="([^"]+)"', head).group(1)
            x0 = y0 = 1e18
            x1 = y1 = -1e18
            for dm in re.finditer(r' d="([^"]*)"', body):
                for px, py in path_points(dm.group(1)):
                    tx, ty = apply(F, px, py)
                    x0 = min(x0, tx); y0 = min(y0, ty)
                    x1 = max(x1, tx); y1 = max(y1, ty)
            if x1 > x0:
                out.append([wid, line, round(x0, 2), round(y0, 2),
                            round(x1, 2), round(y1, 2)])
    return out


def main():
    if "--all" in sys.argv:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(32) as ex:
            rs = list(ex.map(page_boxes, range(1, 605)))
        idx = {"schema": "quran-svg-boxes", "version": "1",
               "space": "SVG user units of the page viewBox",
               "fields": ["wid", "line", "x0", "y0", "x1", "y1"],
               "pages": {str(i+1): r for i, r in enumerate(rs)}}
        out = os.path.join(ROOT, "docs/shipping/out")
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, "wordboxes.json")
        json.dump(idx, open(p, "w"), separators=(",", ":"))
        b = open(p, "rb").read()
        print(f"words boxed: {sum(len(r) for r in rs)}")
        print(f"wordboxes.json raw {len(b)/1024:.0f} KiB  "
              f"gzip {len(gzip.compress(b,9))/1024:.0f} KiB  "
              f"brotli {len(brotli.compress(b,quality=11))/1024:.0f} KiB"
              if brotli else "")
        return
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    for r in page_boxes(n)[:12]:
        print(r)


if __name__ == "__main__":
    main()
