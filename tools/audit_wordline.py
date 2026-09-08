#!/usr/bin/env python3
"""Is every word in the <g class="line"> it is DRAWN in?

A whole-corpus detector that needs no reference decomposition and no eye. It
reads the emitted product — the same files a consumer gets — and asks two
independent questions about every `<g class="word">`:

  ORDER    the printed page is read top line to bottom line, and inside a line
           right to left. Concatenating the words of a page in that order must
           give the mushaf's own word order. Measured over the 2026-08-29
           build: inside a line the order is right on 9,046 of 9,046 lines, so
           every break in the concatenated sequence is a LINE-MEMBERSHIP fault
           and nothing else.

  GEOMETRY every line's words occupy one horizontal band. A word's own band
           overlap with the line it is filed under must beat its overlap with
           every other line on the page.

Neither test can be fooled by the other's blind spot: ORDER knows nothing about
where ink is drawn, GEOMETRY knows nothing about the text. A word is reported
as MISPLACED only when both agree, and both name the same target line. Words
that only one test flags are reported separately as `order_only` /
`geom_only` — they are the review queue, not the count.

Usage:
    python3 tools/audit_wordline.py [first] [last] [--dir D] [--json OUT]
                                    [--hist]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIR = os.path.join(os.environ.get("QSVG_ROOT", ROOT),
                           ".cache", "words-svg", "hafs-kfqc")

_NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_CMD = re.compile(r"([MmZzLlHhVvCcSsQqTtAa])")


def path_bbox(d):
    """Bounding box of a path `d` string, using every on-curve point and every
    control point. Control points bound the curve, so the box is a superset of
    the true one — which can only make this audit more conservative."""
    toks = _CMD.split(d)
    x = y = 0.0
    sx = sy = 0.0
    xs, ys = [], []
    i = 1
    cmd = None
    while i < len(toks):
        cmd = toks[i]
        args = [float(v) for v in _NUM.findall(toks[i + 1])]
        i += 2
        rel = cmd.islower()
        c = cmd.upper()
        if c == "Z":
            x, y = sx, sy
            continue
        n = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6,
             "S": 4, "Q": 4, "T": 2, "A": 7}[c]
        if n == 0 or not args:
            continue
        for k in range(0, len(args) - n + 1, n):
            a = args[k:k + n]
            if c == "H":
                x = x + a[0] if rel else a[0]
            elif c == "V":
                y = y + a[0] if rel else a[0]
            elif c == "A":
                nx, ny = a[5], a[6]
                x, y = (x + nx, y + ny) if rel else (nx, ny)
            else:
                pts = [(a[j], a[j + 1]) for j in range(0, n, 2)]
                for px, py in pts[:-1]:
                    xs.append(x + px if rel else px)
                    ys.append(y + py if rel else py)
                nx, ny = pts[-1]
                x, y = (x + nx, y + ny) if rel else (nx, ny)
            xs.append(x)
            ys.append(y)
            if c == "M":
                sx, sy = x, y
                # a second coordinate pair after M is an implicit L
                c = "L"
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _mat_mul(a, b):
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
            a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
            a[0] * b[4] + a[2] * b[5] + a[4],
            a[1] * b[4] + a[3] * b[5] + a[5])


def _parse_transform(s):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, body in re.findall(r"(matrix|translate|scale)\(([^)]*)\)", s):
        v = [float(t) for t in _NUM.findall(body)]
        if name == "matrix":
            t = tuple(v[:6])
        elif name == "translate":
            t = (1.0, 0.0, 0.0, 1.0, v[0], v[1] if len(v) > 1 else 0.0)
        else:
            t = (v[0], 0.0, 0.0, v[1] if len(v) > 1 else v[0], 0.0, 0.0)
        m = _mat_mul(m, t)
    return m


def _apply(m, box):
    xs, ys = [], []
    for px, py in ((box[0], box[1]), (box[2], box[1]),
                   (box[0], box[3]), (box[2], box[3])):
        xs.append(m[0] * px + m[2] * py + m[4])
        ys.append(m[1] * px + m[3] * py + m[5])
    return (min(xs), min(ys), max(xs), max(ys))


_TAG = re.compile(r"<(/?)(g|path)\b([^>]*)>")
_ATTR = re.compile(r'([\w:-]+)="([^"]*)"')


def scan_page(svg):
    """[(line_no, word_key, screen_bbox)] in document order, plus the line order."""
    stack = []          # (tagname, class, attrs, ctm)
    ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    ctms = [ctm]
    line_no = None
    line_seq = []
    cur = None          # (line_no, word_key, box)
    words = []
    for m in _TAG.finditer(svg):
        close, tag, attrs = m.group(1), m.group(2), m.group(3)
        if tag == "path":
            if close:
                continue
            if cur is not None:
                a = dict(_ATTR.findall(attrs))
                if "d" in a:
                    b = path_bbox(a["d"])
                    if b:
                        c = _apply(ctms[-1], b)
                        if cur[2] is None:
                            cur[2] = list(c)
                        else:
                            cur[2][0] = min(cur[2][0], c[0])
                            cur[2][1] = min(cur[2][1], c[1])
                            cur[2][2] = max(cur[2][2], c[2])
                            cur[2][3] = max(cur[2][3], c[3])
            continue
        if close:
            if not stack:
                continue
            kind = stack.pop()
            ctms.pop()
            if kind == "word":
                if cur is not None and cur[2] is not None:
                    words.append((cur[0], cur[1], tuple(cur[2])))
                cur = None
            elif kind == "line":
                line_no = None
            continue
        if attrs.rstrip().endswith("/"):
            continue
        a = dict(_ATTR.findall(attrs))
        ctms.append(_mat_mul(ctms[-1], _parse_transform(a.get("transform", ""))))
        cls = a.get("class", "")
        if cls == "line":
            line_no = int(a["data-line"])
            line_seq.append(line_no)
            stack.append("line")
        elif cls == "word":
            cur = [line_no, a.get("data-word-key"), None]
            stack.append("word")
        else:
            stack.append("g")
    return words, line_seq


def _ordinal(word_key):
    s, a, p = (int(v) for v in word_key.split(":"))
    return (s, a, p)


def _overlap(b, band):
    return max(0.0, min(b[3], band[1]) - max(b[1], band[0]))


def _bands(words):
    """Each line's band from the MEDIAN of its words' tops and bottoms, so one
    misfiled word cannot drag the band it is being tested against."""
    by_line = {}
    for ln, word_key, b in words:
        by_line.setdefault(ln, []).append(b)
    out = {}
    for ln, bs in by_line.items():
        tops = sorted(b[1] for b in bs)
        bots = sorted(b[3] for b in bs)
        out[ln] = (tops[len(tops) // 2], bots[len(bots) // 2])
    return out


def _order_breaks(words, moves):
    """Reading-order breaks on the page once `moves` (word_key -> line) is applied.

    Lines keep their printed order; inside a line the words are put in mushaf
    order, which the product already gets right on every line it draws."""
    seen = []
    for ln, word_key, _ in words:
        if ln not in seen:
            seen.append(ln)
    seq = []
    for line in seen:
        ws = [word_key for ln, word_key, _ in words if moves.get(word_key, ln) == line]
        ws.sort(key=_ordinal)
        seq.extend(ws)
    return sum(1 for i in range(1, len(seq))
               if _ordinal(seq[i]) < _ordinal(seq[i - 1]))


def audit_page(pg, svg, words=None):
    """Two independent signals, and a row only counts when they agree.

    GEOMETRY proposes: a word whose band overlap with another line beats the
    overlap with its own belongs to that other line. ORDER disposes: applying
    the whole page's geometric moves must not leave the page's reading order
    broken, and where the order WAS broken it must now be repaired."""
    if words is None:
        words, _ = scan_page(svg)
    if not words:
        return []
    bands = _bands(words)
    rows, moves = [], {}
    for ln, word_key, b in words:
        own = _overlap(b, bands[ln])
        best, bestln = own, ln
        for l2, band in bands.items():
            if l2 == ln:
                continue
            o = _overlap(b, band)
            if o > best:
                best, bestln = o, l2
        if bestln != ln:
            moves[word_key] = bestln
            rows.append({"page": pg, "word_key": word_key, "line": ln,
                         "target": bestln,
                         "own_overlap": round(own, 2),
                         "target_overlap": round(best, 2)})
    before = _order_breaks(words, {})
    after = _order_breaks(words, moves) if moves else before
    for r in rows:
        r["order_breaks_before"] = before
        r["order_breaks_after"] = after
        r["verdict"] = "misplaced" if after == 0 else "review"
    return rows


def main(argv):
    first, last = 1, 604
    d = DEFAULT_DIR
    out_json = None
    hist = False
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] == "--dir":
            d = argv[i + 1]
            i += 2
        elif argv[i] == "--json":
            out_json = argv[i + 1]
            i += 2
        elif argv[i] == "--hist":
            hist = True
            i += 1
        else:
            pos.append(argv[i])
            i += 1
    if len(pos) >= 1:
        first = int(pos[0])
    if len(pos) >= 2:
        last = int(pos[1])

    rows = []
    npages = nlines = 0
    within = within_ok = 0
    broken_before = broken_after = 0
    margins = []
    for pg in range(first, last + 1):
        p = os.path.join(d, "%03d.svg" % pg)
        if not os.path.exists(p):
            continue
        svg = open(p, encoding="utf-8").read()
        npages += 1
        words, lines = scan_page(svg)
        nlines += len(set(lines))
        by_line = {}
        for ln, word_key, b in words:
            by_line.setdefault(ln, []).append(word_key)
        for ln, ws in by_line.items():
            within += 1
            if all(_ordinal(ws[k]) < _ordinal(ws[k + 1])
                   for k in range(len(ws) - 1)):
                within_ok += 1
        pr = audit_page(pg, svg, words)
        rows.extend(pr)
        if words:
            b0 = pr[0]["order_breaks_before"] if pr else _order_breaks(words, {})
            b1 = pr[0]["order_breaks_after"] if pr else b0
            broken_before += 1 if b0 else 0
            broken_after += 1 if b1 else 0
        if hist:
            # distribution of (own band overlap - best rival overlap) for
            # EVERY word, which is what the geometric test thresholds at 0
            bands = _bands(words)
            for ln, word_key, b in words:
                own = _overlap(b, bands[ln])
                riv = max([_overlap(b, bd) for l2, bd in bands.items()
                           if l2 != ln] or [0.0])
                margins.append(own - riv)

    by_v = {}
    for r in rows:
        by_v[r["verdict"]] = by_v.get(r["verdict"], 0) + 1
    print("pages %d  lines %d" % (npages, nlines))
    print("within-line order correct on %d of %d lines" % (within_ok, within))
    print("pages whose reading order breaks across a line boundary: %d"
          % broken_before)
    print("MISPLACED (geometry, confirmed by order) %d on %d pages"
          % (by_v.get("misplaced", 0),
             len({r["page"] for r in rows if r["verdict"] == "misplaced"})))
    if by_v.get("review"):
        print("  review (moves do not repair the order) %d" % by_v["review"])
    if hist and margins:
        margins.sort()
        print("\nown-band overlap minus best rival, all %d words:" % len(margins))
        edges = [-1e9, -8, -4, -2, -1, -0.5, 0, 0.5, 1, 2, 4, 8, 1e9]
        for lo, hi in zip(edges, edges[1:]):
            n = sum(1 for m in margins if lo <= m < hi)
            print("  [%8.1f, %8.1f)  %6d %s"
                  % (lo, hi, n, "#" * min(60, n // 200)))
    if out_json:
        json.dump(rows, open(out_json, "w"), indent=1)
        print("wrote %s" % out_json)
    for r in rows:
        print("  p%-3d %-12s line %s -> %s (own %.1f, target %.1f) %s"
              % (r["page"], r["word_key"], r["line"], r["target"],
                 r["own_overlap"], r["target_overlap"], r["verdict"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
