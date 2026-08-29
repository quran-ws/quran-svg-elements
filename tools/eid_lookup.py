#!/usr/bin/env python3
"""Resolve a data-eid to its pipeline element, DRIFT-PROOF.

eids are assigned at emit time, so they renumber whenever the build changes
— an eid a human read five minutes ago can point at different ink now (p413,
2026-08-29). The d-string cannot drift: it IS the ink. This looks the eid up
in the CURRENTLY CACHED svg (what the review platform serves, i.e. what the
human is looking at), then finds the element whose geometry draws that same
d, and prints the override key for it.

    python3 tools/eid_lookup.py <page> <eid> [<eid> ...]
"""
import os
import re
import sys

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assign_words as aw  # noqa: E402
from add_line_structure import build_d  # noqa: E402


def main():
    pg = int(sys.argv[1])
    eids = sys.argv[2:]
    svg = open(os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc",
                            "%03d.svg" % pg), encoding="utf-8").read()
    want = {}
    for eid in eids:
        m = re.search(r'data-eid="%s"[^>]*?\sd="([^"]*)"' % re.escape(eid),
                      svg)
        if not m:
            print("%s: not in the cached svg" % eid)
            continue
        want[m.group(1)] = eid
        i = svg.rfind('<g class="word"', 0, m.start())
        j = svg.rfind('<g class=', 0, m.start())
        h = re.search(r'data-wid="([^"]*)" '
                      r'data-uthmani="([^"]*)"',
                      svg[i:i + 300])
        print("%s: shown inside %s" % (
            eid, ":".join(h.groups()) if h and j <= i
            else re.sub(r"\s+", " ", svg[j:j + 60])))

    cap = {}
    _o = aw.rewrite
    aw.rewrite = lambda p, a: (cap.__setitem__("a", a), _o(p, a))[1]
    try:
        aw.assign_page("hafs/kfqc", pg,
                       os.path.join(ROOT, ".cache", "words"))
    finally:
        aw.rewrite = _o
    for w, at in cap["a"]:
        for a in at:
            for e in a["els"]:
                d = build_d(e["contours"])
                if d in want:
                    print("  %s -> key %.1f,%.1f,%.1f,%.1f  kind=%s mark=%s"
                          "  held by %s" % (
                              want[d], e["x1"], e["y1"], e["x2"], e["y2"],
                              e.get("kind"), e.get("mark"),
                              ("%d:%d:%d %s" % (w["surah"], w["ayah"],
                                                w["pos"], w["uthmani"]))
                              if w else "(wordless)"))


if __name__ == "__main__":
    main()
