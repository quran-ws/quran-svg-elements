#!/usr/bin/env python3
"""Inventory every data-* / id / class attribute in the emitted page SVGs.

Scans .cache/words-svg/hafs-kfqc/001.svg .. 604.svg and writes
docs/demo/data/attrs.json: one row per (element scope, attribute) pair, where
the scope is written the way a developer would select it -- tag name plus the
element's class, e.g. "g.word", "g.ayah-mark", "path", "svg".

Distinct-value sets are carried up to DISTINCT_CAP entries; past that the row
carries "distinct_capped": true and "distinct" is the number of distinct
values actually retained (a lower bound on the true count).
"""

import datetime
import json
import multiprocessing
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SVG_DIR = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
OUT = os.path.join(ROOT, "docs", "demo", "data", "attrs.json")

PAGES = 604
WORKERS = 32
DISTINCT_CAP = 500
SAMPLES = 8

# Start tags only: name, then a run of name="value" pairs.
TAG_RE = re.compile(r'<([A-Za-z_][\w.:-]*)((?:\s+[\w:.-]+\s*=\s*"[^"]*")*)\s*/?>')
ATTR_RE = re.compile(r'([\w:.-]+)\s*=\s*"([^"]*)"')


def _wanted(name):
    return name == "id" or name == "class" or name.startswith("data-")


def scan_page(n):
    """Return {(scope, attr): [count, set-of-values(capped), capped_flag]}."""
    path = os.path.join(SVG_DIR, "%03d.svg" % n)
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return out
    for m in TAG_RE.finditer(text):
        tag = m.group(1)
        if ":" in tag:  # strip any namespace prefix
            tag = tag.rsplit(":", 1)[1]
        attrs = ATTR_RE.findall(m.group(2))
        if not attrs:
            continue
        cls = None
        for name, val in attrs:
            if name == "class":
                cls = val
                break
        scope = tag if not cls else tag + "." + ".".join(cls.split())
        for name, val in attrs:
            if ":" in name:
                name = name.rsplit(":", 1)[1]
            if not _wanted(name):
                continue
            rec = out.get((scope, name))
            if rec is None:
                rec = out[(scope, name)] = [0, set(), False]
            rec[0] += 1
            if len(rec[1]) < DISTINCT_CAP:
                rec[1].add(val)
            elif val not in rec[1]:
                rec[2] = True
    # sets -> sorted lists so they pickle back cheaply and deterministically
    return {k: (v[0], sorted(v[1]), v[2]) for k, v in out.items()}


def main():
    t0 = datetime.datetime.now()
    pages = list(range(1, PAGES + 1))
    merged = {}
    with multiprocessing.Pool(WORKERS) as pool:
        for part in pool.imap_unordered(scan_page, pages, chunksize=4):
            for key, (count, vals, capped) in part.items():
                rec = merged.get(key)
                if rec is None:
                    rec = merged[key] = [0, set(), False]
                rec[0] += count
                if capped:
                    rec[2] = True
                for v in vals:
                    if len(rec[1]) < DISTINCT_CAP:
                        rec[1].add(v)
                    elif v not in rec[1]:
                        rec[2] = True

    rows = []
    for (scope, attr), (count, vals, capped) in merged.items():
        samples = sorted(vals, key=lambda s: (len(s), s))[:SAMPLES]
        rows.append({
            "scope": scope,
            "attr": attr,
            "count": count,
            "distinct": len(vals),
            "distinct_capped": capped,
            "samples": samples,
        })
    rows.sort(key=lambda r: (r["scope"], r["attr"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({
            "generated": datetime.datetime.now().isoformat(timespec="seconds"),
            "pages": PAGES,
            "rows": rows,
        }, fh, ensure_ascii=False, indent=1)

    dt = (datetime.datetime.now() - t0).total_seconds()
    sys.stdout.write("attrs.json: %d rows from %d pages in %.1fs -> %s\n"
                     % (len(rows), PAGES, dt, OUT))


if __name__ == "__main__":
    main()
