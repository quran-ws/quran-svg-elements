#!/usr/bin/env python3
"""Proof of concept for the flagship embed endpoint: GET /v1/ayah/<s>:<a>.svg

Extracts one ayah (or an arbitrary word run) out of a shipped page SVG as a
standalone, self-contained SVG cropped to the ink.

Why this is not a one-liner:

  * an ayah is emitted as SEVERAL <g class="ayah-fragment"> nodes -- one per printed
    line it occupies -- so the crop is the UNION of their boxes, never a
    single node's box;
  * the root frame is `matrix(1.3333 0 0 -1.3333 E 640)`, a NEGATIVE y scale,
    so a naive min/max in path coordinates gives an upside-down box;
  * every line carries its own inner translate, so boxes must be composed
    through the whole ancestor chain, not read off the path data.

The pruning strategy avoids all three by KEEPING the ancestor chain: we copy
the root <g> and each line wrapper verbatim and delete only the sibling
content.  Transforms then compose themselves, exactly as they do in the page.

Boxes are the control-point hull of the path data (a superset of the true
outline -- Bezier control points lie outside the curve), same caveat as
wordbox_poc.py.  A production builder takes exact extents from the pipeline.

Usage:
    python3 ayah_crop_poc.py 2:255                    # -> out/ayah-2-255.svg
    python3 ayah_crop_poc.py 2:255 --pad 6 --width 900
    python3 ayah_crop_poc.py 2:255:4                  # a single word
    python3 ayah_crop_poc.py --survey                 # corpus stats
    python3 ayah_crop_poc.py --estimate 400           # size the full 6,236
"""
import json
import os
import re
import sys
import glob
import gzip
import xml.etree.ElementTree as ET

try:
    import brotli
except ImportError:
    brotli = None

ROOT = os.environ.get("QSVG_ROOT", os.getcwd())
SRC = os.path.join(ROOT, ".cache/words-svg/hafs-kfqc")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
NS = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")

_NUM = re.compile(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?")
_CMD = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")


# ---------------------------------------------------------------- transforms
def parse_transform(t):
    M = (1, 0, 0, 1, 0, 0)
    if not t:
        return M
    for name, args in re.findall(r"(matrix|translate|scale)\s*\(([^)]*)\)", t):
        v = [float(x) for x in _NUM.findall(args)]
        if name == "matrix":
            N = tuple(v)
        elif name == "translate":
            N = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        else:
            N = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        a, b, c, d, e, f = M
        na, nb, nc, nd, ne, nf = N
        M = (a * na + c * nb, b * na + d * nb,
             a * nc + c * nd, b * nc + d * nd,
             a * ne + c * nf + e, b * ne + d * nf + f)
    return M


def apply(M, x, y):
    a, b, c, d, e, f = M
    return a * x + c * y + e, b * x + d * y + f


def path_points(d):
    """Yield absolute (x, y) for every coordinate pair, control points included."""
    x = y = 0.0
    sx = sy = 0.0
    i = 0
    cmd = None
    toks = []
    pos = 0
    while pos < len(d):
        m = _CMD.search(d, pos)
        if not m:
            break
        c = m.group()
        nxt = _CMD.search(d, m.end())
        seg = d[m.end():nxt.start() if nxt else len(d)]
        toks.append((c, [float(v) for v in _NUM.findall(seg)]))
        pos = nxt.start() if nxt else len(d)
    for c, v in toks:
        rel = c.islower()
        C = c.upper()
        if C == "Z":
            x, y = sx, sy
            continue
        if C == "H":
            for n in v:
                x = x + n if rel else n
                yield x, y
            continue
        if C == "V":
            for n in v:
                y = y + n if rel else n
                yield x, y
            continue
        if C == "A":
            step = 7
            for k in range(0, len(v) - 6, step):
                px, py = v[k + 5], v[k + 6]
                x = x + px if rel else px
                y = y + py if rel else py
                yield x, y
            continue
        step = {"M": 2, "L": 2, "T": 2, "S": 4, "Q": 4, "C": 6}[C]
        for k in range(0, len(v) - step + 1, step):
            chunk = v[k:k + step]
            bx, by = x, y
            for j in range(0, step, 2):
                px, py = chunk[j], chunk[j + 1]
                ax = bx + px if rel else px
                ay = by + py if rel else py
                yield ax, ay
                if j == step - 2:
                    x, y = ax, ay
            if C == "M" and k == 0:
                sx, sy = x, y


def bbox_of(el, M):
    """Union control-point box of el's subtree, in the frame M maps into."""
    lo = [float("inf"), float("inf")]
    hi = [float("-inf"), float("-inf")]

    def rec(e, M):
        M = mul(M, parse_transform(e.get("transform")))
        if e.tag == NS + "path" and e.get("d"):
            for px, py in path_points(e.get("d")):
                X, Y = apply(M, px, py)
                lo[0] = min(lo[0], X); lo[1] = min(lo[1], Y)
                hi[0] = max(hi[0], X); hi[1] = max(hi[1], Y)
        for c in e:
            rec(c, M)

    rec(el, M)
    if lo[0] == float("inf"):
        return None
    return (lo[0], lo[1], hi[0], hi[1])


def mul(M, N):
    a, b, c, d, e, f = M
    na, nb, nc, nd, ne, nf = N
    return (a * na + c * nb, b * na + d * nb,
            a * nc + c * nd, b * nc + d * nd,
            a * ne + c * nf + e, b * ne + d * nf + f)


IDENT = (1, 0, 0, 1, 0, 0)


# ------------------------------------------------------------------- cropping
def load(page):
    return ET.parse(os.path.join(SRC, "%03d.svg" % page)).getroot()


def page_of(key):
    """Which page holds this ayah / word key.  Scans; a service uses an index."""
    sa = ":".join(key.split(":")[:2])
    for f in sorted(glob.glob(SRC + "/*.svg")):
        s = open(f).read()
        if ('data-ayah-key="%s"' % sa) in s:
            yield int(os.path.basename(f)[:3])


def crop(page, key, pad=4.0, marker=True, width=None, ink=None, bg=None):
    """Return (svg_bytes, meta) for `key` = "s:a" (ayah) or "s:a:w" (word)."""
    root = load(page)
    parts = key.split(":")
    want_word = len(parts) == 3

    body = None
    for ch in root:
        if ch.tag == NS + "g" and ch.get("transform"):
            body = ch
            break
    rootM = parse_transform(body.get("transform"))

    # Which nodes are we keeping?
    if want_word:
        sel = [e for e in body.iter(NS + "g")
               if e.get("class") == "word" and e.get("data-word-key") == key]
    else:
        sel = [e for e in body.iter(NS + "g")
               if e.get("class") == "ayah" and e.get("data-ayah-key") == key]
    if not sel:
        return None, None
    keep = set(id(e) for e in sel)
    # every ancestor of a kept node stays
    parent = {}
    for p in body.iter():
        for c in p:
            parent[id(c)] = p
    node_by_id = {id(e): e for e in body.iter()}
    for e in sel:
        cur = e
        while id(cur) in parent:
            cur = parent[id(cur)]
            keep.add(id(cur))
    keep.add(id(body))

    # the ayah end-mark for this ayah, if asked and present
    if marker and not want_word:
        for e in body.iter(NS + "g"):
            if e.get("class") == "ayah-mark" and e.get("data-ayah-key") == key:
                keep.add(id(e))
                cur = e
                while id(cur) in parent:
                    cur = parent[id(cur)]
                    keep.add(id(cur))

    # everything BELOW a selected node is ink we want, wholesale
    subtree = set()
    roots = list(sel)
    if marker and not want_word:
        roots += [e for e in body.iter(NS + "g")
                  if e.get("class") == "ayah-mark" and e.get("data-ayah-key") == key]
    for e in roots:
        for d in e.iter():
            subtree.add(id(d))
    keep |= subtree

    def prune(e):
        for c in list(e):
            if id(c) in keep:
                prune(c)
            else:
                e.remove(c)

    prune(body)

    box = bbox_of(body, IDENT)
    if box is None:
        return None, None
    x0, y0, x1, y1 = box
    x0 -= pad; y0 -= pad; x1 += pad; y1 += pad

    svg = ET.Element(NS + "svg", {
        "version": "1.1",
        "viewBox": "%.3f %.3f %.3f %.3f" % (x0, y0, x1 - x0, y1 - y0),
    })
    if width:
        svg.set("width", str(width))
        svg.set("height", "%.2f" % (width * (y1 - y0) / (x1 - x0)))
    svg.set("data-src-page", str(page))
    svg.set("data-ayah-key" if not want_word else "data-word-key", key)
    if bg:
        ET.SubElement(svg, NS + "rect", {
            "x": "%.3f" % x0, "y": "%.3f" % y0,
            "width": "%.3f" % (x1 - x0), "height": "%.3f" % (y1 - y0),
            "fill": bg})
    svg.append(body)
    if ink:
        st = ET.SubElement(svg, NS + "style")
        st.text = "path{fill:%s}" % ink
        svg.remove(st)
        svg.insert(0, st)
    out = ET.tostring(svg, encoding="utf-8", xml_declaration=False)
    meta = {"page": page, "key": key, "nodes": len(sel),
            "box": [round(v, 2) for v in (x0, y0, x1, y1)],
            "bytes": len(out)}
    return out, meta


# -------------------------------------------------------------------- surveys
def survey():
    """How fragmented are ayahs, and across how many pages?"""
    import collections
    per_page = collections.Counter()      # (ayahKey) -> node count
    pages_of = collections.defaultdict(set)
    for f in sorted(glob.glob(SRC + "/*.svg")):
        p = int(os.path.basename(f)[:3])
        s = open(f).read()
        for ayahKey in re.findall(r'<g class="ayah-fragment" data-ayah-key="([^"]+)"', s):
            per_page[ayahKey] += 1
            pages_of[ayahKey].add(p)
    n = len(per_page)
    frag = collections.Counter(per_page.values())
    multi = sum(v for k, v in frag.items() if k > 1)
    spans = collections.Counter(len(v) for v in pages_of.values())
    print("ayahs seen:", n)
    print("node-count histogram (nodes per ayah, whole corpus):",
          dict(sorted(frag.items())[:12]), "...")
    print("ayahs emitted as >1 node:", multi)
    print("worst:", per_page.most_common(6))
    print("pages spanned histogram:", dict(sorted(spans.items())))


def estimate(k=400):
    """Crop k ayahs, measure, extrapolate to 6,236."""
    import random, time
    random.seed(7)
    files = sorted(glob.glob(SRC + "/*.svg"))
    sample = random.sample(files, min(60, len(files)))
    tot = 0; cnt = 0; br = 0; gz = 0
    t0 = time.time()
    for f in sample:
        p = int(os.path.basename(f)[:3])
        s = open(f).read()
        ayahKeys = sorted(set(re.findall(r'<g class="ayah-fragment" data-ayah-key="([^"]+)"', s)))
        for ayahKey in ayahKeys:
            if cnt >= k:
                break
            out, meta = crop(p, ayahKey)
            if out is None:
                continue
            tot += len(out); cnt += 1
            gz += len(gzip.compress(out, 9))
            if brotli:
                br += len(brotli.compress(out, quality=11))
        if cnt >= k:
            break
    dt = time.time() - t0
    print("crops: %d  mean raw %.1f KiB  mean gzip %.1f KiB  mean brotli %.1f KiB"
          % (cnt, tot / cnt / 1024, gz / cnt / 1024, (br / cnt / 1024) if brotli else -1))
    print("time %.1fs  -> %.0f ms per crop (single core, includes page parse)"
          % (dt, dt / cnt * 1000))
    print("extrapolated to 6,236 ayahs: raw %.1f MiB | gzip %.1f MiB | brotli %.1f MiB"
          % (tot / cnt * 6236 / 2**20, gz / cnt * 6236 / 2**20,
             (br / cnt * 6236 / 2**20) if brotli else -1))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "--survey":
        survey()
    elif args[0] == "--estimate":
        estimate(int(args[1]) if len(args) > 1 else 400)
    else:
        key = args[0]
        pad = float(args[args.index("--pad") + 1]) if "--pad" in args else 4.0
        width = args[args.index("--width") + 1] if "--width" in args else None
        ink = args[args.index("--ink") + 1] if "--ink" in args else None
        bg = args[args.index("--bg") + 1] if "--bg" in args else None
        pg = int(args[args.index("--page") + 1]) if "--page" in args else None
        pages = [pg] if pg else list(page_of(key))
        for p in pages:
            out, meta = crop(p, key, pad=pad, width=width, ink=ink, bg=bg)
            if out is None:
                continue
            name = "%s-p%03d.svg" % (key.replace(":", "-"), p)
            open(os.path.join(OUT, name), "wb").write(out)
            print(json.dumps(meta), "->", os.path.join(OUT, name))
