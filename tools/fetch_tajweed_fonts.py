#!/usr/bin/env python3
"""Fetch the 604 QUL "QPC V4 Tajweed" page fonts into .cache/tajweed/fonts/.

These are the KFGQPC V4 (1441H) page glyphs — the SAME artwork as our pages — with
every tajweed-coloured letter cut by hand into its own COLR layer. The letter-level
decomposition lifts those cuts as proof-class evidence
(docs/superpowers/specs/2026-09-05-letter-level-decomposition-design.md).

Source page: https://qul.tarteel.ai/resources/font/240   (~160 MB in all)

    python3 tools/fetch_tajweed_fonts.py            # idempotent; skips files present
"""
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, ".cache", "tajweed", "fonts")
URL = "https://static-cdn.tarteel.ai/qul/fonts/quran_fonts/v4-tajweed/ttf/p%d.ttf"


def fetch(page):
    dst = os.path.join(OUT, "p%d.ttf" % page)
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        return page, "present"
    try:
        with urllib.request.urlopen(URL % page, timeout=60) as r:
            data = r.read()
    except Exception as e:                       # report, never raise: the count below is the verdict
        return page, "ERROR %s" % e
    if len(data) < 1000:
        return page, "ERROR short (%d bytes)" % len(data)
    with open(dst + ".part", "wb") as f:
        f.write(data)
    os.replace(dst + ".part", dst)
    return page, "fetched"


def main():
    os.makedirs(OUT, exist_ok=True)
    first, last = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (1, 604)
    with ThreadPoolExecutor(32) as ex:
        res = list(ex.map(fetch, range(first, last + 1)))
    bad = [(p, s) for p, s in res if s.startswith("ERROR")]
    for p, s in bad:
        print("p%d %s" % (p, s))
    n = sum(1 for p in range(1, 605)
            if os.path.exists(os.path.join(OUT, "p%d.ttf" % p)))
    print("%d fonts present in %s (%d fetched now, %d errors)"
          % (n, OUT, sum(1 for _, s in res if s == "fetched"), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
