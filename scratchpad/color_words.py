#!/usr/bin/env python3
"""Colorize a decomposed page SVG: every word gets its own fill color, so
ownership is visible in a render (before/after pixels are otherwise identical).

Usage: python3 color_words.py <in.svg> <out.svg>
Marks (data-kind="mark") are tinted darker than the word's letter bodies so a
stolen mark reads at a glance.
"""
import re, sys

PALETTE = ["#c0392b", "#2471a3", "#1e8449", "#b7950b", "#7d3c98",
           "#d35400", "#148f77", "#884ea0", "#a04000", "#1a5276",
           "#7b241c", "#196f3d", "#6c3483", "#9a7d0a", "#0e6251"]

src = open(sys.argv[1], encoding="utf-8").read()
out = []
pos = 0
depth = 0            # nesting depth inside the current word group
word_i = -1
color = None
tag = re.compile(r"<g\b[^>]*>|</g>|<path\b[^>]*?/>", re.S)
wkey = re.compile(r'class="word"')
kind = re.compile(r'data-kind="([^"]+)"')
n = 0
for m in tag.finditer(src):
    t = m.group(0)
    out.append(src[pos:m.start()])
    pos = m.end()
    if t.startswith("<g"):
        if color is not None:
            depth += 1
        elif wkey.search(t):
            word_i += 1
            color = PALETTE[word_i % len(PALETTE)]
            depth = 1
    elif t == "</g>":
        if color is not None:
            depth -= 1
            if depth == 0:
                color = None
    else:  # path
        if color is not None:
            k = kind.search(t)
            c = color
            t2 = re.sub(r'fill="[^"]*"', 'fill="%s"' % c, t)
            if 'fill="' not in t2:
                t2 = t2[:-2] + ' fill="%s"/>' % c
            if k and k.group(1) == "mark":
                t2 = t2[:-2] + ' opacity="0.62"/>'
            t = t2
            n += 1
    out.append(t)
out.append(src[pos:])
open(sys.argv[2], "w", encoding="utf-8").write("".join(out))
print("colored %d paths, %d words" % (n, word_i + 1))
