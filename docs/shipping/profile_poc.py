#!/usr/bin/env python3
"""Proof of concept for the SHIPPING PROFILES — measurement only.

Reads emitted dev pages from .cache/words-svg/hafs-kfqc/NNN.svg and rewrites
them into candidate production profiles, reporting real byte sizes raw /
gzip -9 / brotli q11.

NOTHING here is part of the pipeline. It exists to settle "how much does the
lean profile actually save" with numbers instead of opinion. The real profile
switch, if adopted, belongs in rewrite() in tools/assign_words.py.

Usage:  python3 docs/shipping/profile_poc.py [page ...]        # default sample
        python3 docs/shipping/profile_poc.py --all             # all 604
"""
import gzip
import re
import sys
import os
import json

try:
    import brotli
except ImportError:
    brotli = None

ROOT = os.environ.get("QSVG_ROOT", os.getcwd())
SRC = os.path.join(ROOT, ".cache/words-svg/hafs-kfqc")

# ---------------------------------------------------------------- transforms

_DROP_DEV = re.compile(r' data-(?:eid|sig)="[^"]*"')
_DROP_FAMILY = re.compile(r' data-mark-family="[^"]*"')
_DROP_TEXTS = re.compile(r' data-(?:rasm|imlaei|qpc)="[^"]*"')
_LIG_OPEN = re.compile(r'<g class="ligature" data-text="[^"]*">')
_FILL = re.compile(r' fill="#231f20"')
_NUM = re.compile(r'-?\d+\.\d{4,}')


def drop_dev(s):
    """P1: remove attributes that only the dev/review loop reads."""
    return _DROP_DEV.sub("", s)


def flatten_ligatures(s):
    """P2: dissolve <g class="ligature"> wrappers; paths land in the word.

    Order is preserved exactly, so the paint order and therefore the pixels are
    unchanged (every path in the mushaf is the same colour: coverage composites
    order-independently -- CLAUDE.md, 'data-line serves two layers').
    """
    out = []
    i = 0
    depth = 0
    for m in _LIG_OPEN.finditer(s):
        out.append(s[i:m.start()])
        i = m.end()
        depth += 1
    out.append(s[i:])
    s = "".join(out)
    # remove exactly `depth` closing </g> that belonged to ligature groups.
    # Ligature groups always close immediately before the next ligature/word
    # boundary; the safe mechanical rule is to re-parse.  We instead rebuild by
    # counting: see rebuild_words() which does it structurally.
    return s, depth


def round_coords(s, nd=3):
    """P-round: collapse float noise in path data.

    Emitted coordinates carry binary-float tails ("357.86800000000005").  This
    is NOT pixel-neutral in principle; measured separately so the size win can
    be weighed against the pixel gate.
    """
    def r(m):
        v = float(m.group(0))
        t = f"{v:.{nd}f}".rstrip("0").rstrip(".")
        return t if t not in ("", "-") else "0"
    return _NUM.sub(r, s)


def strip_presentation(s):
    """Move the constant fill to a CSS rule on the root instead of 1000 paths."""
    s = _FILL.sub("", s)
    s = s.replace("<svg ", '<svg style="fill:#231f20" ', 1)
    return s


# ------------------------------------------------------- structural rebuilder

import xml.etree.ElementTree as ET

SVGNS = "http://www.w3.org/2000/svg"


def rebuild(path, *, ligatures=True, marks=True, dev=True, texts=True,
            polygons=True, family=True):
    """Structural rewrite via ElementTree so nesting can be changed safely."""
    ET.register_namespace("", SVGNS)
    tree = ET.parse(path)
    root = tree.getroot()

    def tag(e):
        return e.tag.split("}")[-1]

    def walk(parent):
        for child in list(parent):
            walk(child)
            cls = child.get("class")
            if cls == "ligature" and not ligatures:
                idx = list(parent).index(child)
                parent.remove(child)
                for k, gc in enumerate(list(child)):
                    parent.insert(idx + k, gc)
            if cls == "ayahPolygon" and not polygons:
                parent.remove(child)
        for e in parent.iter():
            if not dev:
                e.attrib.pop("data-eid", None)
                e.attrib.pop("data-sig", None)
            if not family:
                e.attrib.pop("data-mark-family", None)
            if not texts:
                for a in ("data-rasm", "data-imlaei", "data-qpc"):
                    e.attrib.pop(a, None)
            if not marks:
                for a in ("data-mark", "data-mark-family", "data-form",
                          "data-iqlab"):
                    e.attrib.pop(a, None)

    walk(root)

    if not marks:
        # collapse every word to ONE path: concatenate the d of its children.
        for w in root.iter():
            if w.get("class") != "word":
                continue
            ds = [p.get("d") for p in list(w) if p.get("d")]
            for c in list(w):
                w.remove(c)
            p = ET.SubElement(w, f"{{{SVGNS}}}path")
            p.set("d", " ".join(ds))
            p.set("fill", "#231f20")
            p.set("fill-rule", "evenodd")

    return ET.tostring(root, encoding="unicode")


# --------------------------------------------------------------- measurement

def sizes(s):
    b = s.encode()
    g = len(gzip.compress(b, 9))
    br = len(brotli.compress(b, quality=11)) if brotli else 0
    return len(b), g, br


PROFILES = {
    "P0 dev (as emitted)":
        lambda p: open(p).read(),
    "P1 -dev attrs (eid,sig)":
        lambda p: rebuild(p, dev=False),
    "P2 P1 -ligature groups":
        lambda p: rebuild(p, dev=False, ligatures=False),
    "P3 P2 -family -alt texts":
        lambda p: rebuild(p, dev=False, ligatures=False, family=False,
                          texts=False),
    "P4 P2 + fill in CSS":
        lambda p: strip_presentation(rebuild(p, dev=False, ligatures=False)),
    "P5 P4 + coords 3dp *":
        lambda p: round_coords(
            strip_presentation(rebuild(p, dev=False, ligatures=False))),
    "P6 one path per word (no marks)":
        lambda p: rebuild(p, dev=False, ligatures=False, marks=False),
    "P7 P6 + coords 3dp *":
        lambda p: round_coords(
            rebuild(p, dev=False, ligatures=False, marks=False)),
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv:
        pages = [f"{i:03d}" for i in range(1, 605)]
    elif args:
        pages = [f"{int(a):03d}" for a in args]
    else:
        pages = ["001", "003", "049", "255", "350", "604"]

    tot = {k: [0, 0, 0] for k in PROFILES}
    for pg in pages:
        p = os.path.join(SRC, f"{pg}.svg")
        for name, fn in PROFILES.items():
            r = sizes(fn(p))
            for i in range(3):
                tot[name][i] += r[i]

    n = len(pages)
    base = tot["P0 dev (as emitted)"]
    print(f"pages measured: {n}\n")
    print(f"{'profile':32} {'raw KiB':>10} {'gzip KiB':>10} "
          f"{'brotli KiB':>11} {'raw %':>7} {'br %':>7}")
    for name, (r, g, b) in tot.items():
        print(f"{name:32} {r/1024:10.0f} {g/1024:10.0f} {b/1024:11.0f} "
              f"{100*r/base[0]:6.1f}% {100*b/base[2]:6.1f}%")
    print("\n* coordinate rounding is NOT proven pixel-neutral; measured so the")
    print("  size win can be weighed against the pixel gate.")
    print(f"\nextrapolated to 604 pages (brotli, MiB):")
    for name, (r, g, b) in tot.items():
        print(f"  {name:32} raw {r/n*604/1048576:7.1f}  br {b/n*604/1048576:6.1f}")


if __name__ == "__main__":
    main()
