#!/usr/bin/env python3
"""Export-shape invariants of the emitted page SVG, the ones a consumer's
converter measured on 2026-09-04 (docs/defects/upstream_svg_issues.md).

Each check is one line of the consumer's list, stated as a property that
must hold on EVERY page of the production profile:

    markers   one <g class="ayah-mark"> per ayah, each with id + data-ayah-key,
              one ornament and one numeral inside, and no two markers drawing
              the same ornament at the same spot. The artwork on p1/p2 draws
              every ornament twice; the copy rides inside the same marker as
              data-duplicate="1" (collapsing it darkens the rim — pixel
              identity forbids it) and is not counted as a second ornament.
    viewbox   data-content-view-box="0 0 345 550" on every page; the visual
              viewBox contains it and may grow to reveal the native outer frame
    kinds     every <path> carries data-kind
    xforms    no <path> carries a transform (a cross-path translation is baked
              into the absolute moveto instead)
    noise     every absolute moveto the emitter writes has at most three
              decimals (the source relative segments have three; the emitter's
              accumulated float sum is written back as the designer's number)
    textattrs a word group carries data-word-key and data-rasm-uthmani only; the
              other text forms live in the bundle's index/by-page/NNN.json
    word_key  every word group carries data-word-key, surah:ayah:word — the
              only word key there is (docs/HAFS-JSON-SOURCE.md)
    headers   every surah-name group has exactly one header_ink path and at most one
              ornament path, which precedes the title ink in paint order
    frame     exactly one first-painted page-frame group with one even-odd ornament path

    python3 tools/audit_export.py [first [last]] [--jobs N]

Prints one line per failing page and a totals line; exit 1 if any check
fails anywhere. Runs the emitter in the production profile.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from multiprocessing import Pool

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
CONTENT_VIEWBOX = "0 0 345 550"
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
TEXT_FORMS = ("data-rasm-imlai", "data-qpc", "data-rasm", "data-search")


def check_svg(svg):
    """{check: count of violations} for one emitted page."""
    bad = Counter()
    # -- markers
    groups = re.findall(r'<g class="ayah-mark"[^>]*>(.*?)</g>\s*</g>', svg, re.S)
    seen = Counter()
    for gi, body in zip(re.findall(r'<g class="ayah-mark"[^>]*>', svg), groups):
        if 'data-ayah-key="' not in gi or ' id="mk-' not in gi:
            bad["markers"] += 1
        orn = [p for p in re.findall(r"<path\b[^>]*>", body)
               if 'data-kind="ayah_mark_ornament"' in p and "data-duplicate=" not in p]
        num = re.findall(r'data-kind="ayah_number"', body)
        if len(orn) != 1 or len(num) != 1:
            bad["markers"] += 1
        m = re.search(r'<g transform="([^"]*)"><path [^>]*\bd="([^"]*)"', body)
        if m:
            seen[m.groups()] += 1
    bad["markers"] += sum(v - 1 for v in seen.values() if v > 1)
    # -- visual/content boxes and native page frame
    try:
        root = ET.fromstring(svg)
        visual = [float(value) for value in root.get("viewBox", "").split()]
        content = [float(value) for value in root.get("data-content-view-box", "").split()]
        content_text = " ".join(root.get("data-content-view-box", "").split())
        if len(visual) != 4 or len(content) != 4 or content_text != CONTENT_VIEWBOX:
            bad["viewbox"] += 1
        elif (visual[0] > content[0] or visual[1] > content[1]
              or visual[0] + visual[2] < content[0] + content[2]
              or visual[1] + visual[3] < content[1] + content[3]):
            bad["viewbox"] += 1

        frames = [node for node in root.iter()
                  if node.tag.rsplit("}", 1)[-1] == "g" and node.get("class") == "page-frame"]
        if len(frames) != 1:
            bad["frame"] += 1
        else:
            frame = frames[0]
            paths = [node for node in frame if node.tag.rsplit("}", 1)[-1] == "path"]
            if (len(paths) != 1 or paths[0].get("data-kind") != "ornament"
                    or paths[0].get("fill-rule") != "evenodd"
                    or paths[0].get("data-page-frame") is not None
                    or paths[0].get("data-page-frame-box") is not None):
                bad["frame"] += 1
            parents = {child: parent for parent in root.iter() for child in parent}
            parent = parents.get(frame)
            if parent is None or list(parent).index(frame) != 0:
                bad["frame"] += 1
    except (ET.ParseError, TypeError, ValueError):
        bad["viewbox"] += 1
        bad["frame"] += 1
    # -- kinds / xforms
    for p in re.findall(r"<path\b[^>]*>", svg):
        if "data-kind=" not in p:
            bad["kinds"] += 1
        if "transform=" in p:
            bad["xforms"] += 1
    # -- noise: absolute movetos with more than three decimals
    for d in re.findall(r'\bd="([^"]*)"', svg):
        for x, y in re.findall(r"M(%s)[ ,]?(%s)" % (NUM, NUM), d):
            for v in (x, y):
                if "e" in v.lower():
                    continue
                if "." in v and len(v.split(".")[1]) > 3:
                    bad["noise"] += 1
    # -- surah header parts
    for body in re.findall(r'<g class="surah-name"[^>]*>(.*?)</g>', svg, re.S):
        kinds = re.findall(r'<path\b[^>]*data-kind="([^"]+)"', body)
        if kinds.count("header_ink") != 1 or kinds.count("ornament") > 1:
            bad["headers"] += 1
        if "ornament" in kinds and kinds.index("ornament") > kinds.index("header_ink"):
            bad["headers"] += 1
    # -- textattrs
    for g in re.findall(r'<g class="word"[^>]*>', svg):
        bad["textattrs"] += sum(1 for a in TEXT_FORMS if a + '="' in g)
        if not re.search(r' data-word-key="\d+:\d+:\d+"', g):
            bad["word_key"] += 1
    return dict(bad)


def _one(pg):
    os.environ["QSVG_PROFILE"] = "production"
    sys.path.insert(0, TOOLS)
    import assign_words
    _, svg, _, _ = assign_words.assign_page(
        "hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    return pg, check_svg(svg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--jobs", type=int, default=32)
    ap.add_argument("--json", help="write per-page results here")
    a = ap.parse_args()
    pages = range(a.first, a.last + 1)
    with Pool(a.jobs) as pool:
        res = dict(pool.map(_one, pages))
    tot = Counter()
    for pg in pages:
        if any(res[pg].values()):
            print("p%03d %s" % (pg, " ".join("%s=%d" % kv for kv in sorted(res[pg].items()) if kv[1])))
        tot.update(res[pg])
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    print("TOTAL pages=%d %s" % (len(pages), " ".join(
        "%s=%d" % (k, tot.get(k, 0)) for k in
        ("markers", "viewbox", "frame", "kinds", "xforms", "noise", "textattrs", "word_key", "headers"))))
    return 1 if sum(tot.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
