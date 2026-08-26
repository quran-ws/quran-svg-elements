#!/usr/bin/env python3
"""Render a crop of a decomposed page SVG for before/after evidence.

Usage: python3 crop_evidence.py <svg> <out.png> <x1> <y1> <x2> <y2> [zoom]
Coords are page viewBox units (0-345 x, 0-550 y, y down) as printed by
find_word.py / dump_line.py. A small margin is added.
"""
import os, subprocess, sys, tempfile

svg, out = sys.argv[1], sys.argv[2]
x1, y1, x2, y2 = map(float, sys.argv[3:7])
z = float(sys.argv[7]) if len(sys.argv) > 7 else 6.0
M = 4.0
x1, y1, x2, y2 = x1 - M, y1 - M, x2 + M, y2 + M
from PIL import Image
with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
    tmp = f.name
subprocess.run(["rsvg-convert", "-z", str(z), "-b", "white", "-o", tmp, svg],
               check=True)
im = Image.open(tmp)
box = (max(0, int(x1 * z)), max(0, int(y1 * z)),
       min(im.width, int(x2 * z)), min(im.height, int(y2 * z)))
im.crop(box).save(out)
os.unlink(tmp)
print("wrote %s  %dx%d" % (out, box[2] - box[0], box[3] - box[1]))
