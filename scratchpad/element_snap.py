#!/usr/bin/env python3
"""Full-mushaf element snapshot and diff, keyed by CONTENT, never by data-eid.

The handoff's rule 5: "Full-mushaf element diff by (word key, kind, mark,
d-string) — never by data-eid, which is NOT stable across builds."

snapshot: writes one JSON per page holding, for every <path> in the emitted
SVG, the tuple (owner group key, class of the enclosing group, data-kind,
data-mark, d-string) plus the ORDER that path appears in inside its own group.

diff: compares two snapshots and reports, separately,
  * elements present on one side only (multiset difference) — a REAL change,
  * elements whose group changed,
  * groups whose element ORDER changed (expected: the RTL re-order),
  * group-attribute changes (expected: the wid/aid/sid collapse).
"""
import json
import os
import re
import sys
from multiprocessing import Pool

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")

TAG = re.compile(r'<(/?)(g|path)\b([^>]*?)(/?)>')
ATTR = re.compile(r'([a-zA-Z-]+)="([^"]*)"')


def page_records(pg):
    """[(group-path, kind, mark, d)] in document order + group attribute rows."""
    svg = open(os.path.join(CACHE, "%03d.svg" % pg), encoding="utf-8").read()
    stack = []
    els, groups = [], []
    for m in TAG.finditer(svg):
        close, name, body, selfclose = m.groups()
        if name == "g":
            if close:
                if stack:
                    stack.pop()
                continue
            a = dict(ATTR.findall(body))
            cls = a.get("class", "")
            # identity of the group, independent of the attribute renaming
            if cls == "word":
                key = "word:" + (a.get("data-wid") or "%s:%s:%s" % (
                    a.get("data-surah"), a.get("data-ayah"), a.get("data-word")))
            elif cls == "ayah":
                key = "ayah:" + (a.get("data-aid") or "%s:%s" % (
                    a.get("data-surah"), a.get("data-ayah")))
            elif cls == "ligature":
                key = "lig:" + a.get("data-text", "")
            elif cls == "line":
                key = "line:" + a.get("data-line", "")
            elif cls in ("surah-name", "basmalah"):
                key = cls + ":" + (a.get("data-sid") or a.get("data-surah") or "")
            elif cls.endswith("-mark"):
                key = cls + ":" + (a.get("data-aid") or "%s:%s" % (
                    a.get("data-surah"), a.get("data-ayah")))
            elif cls == "ayah-marker":
                key = "marker:" + (a.get("data-aid") or "%s:%s" % (
                    a.get("data-surah"), a.get("data-ayah")))
            else:
                key = cls
            groups.append(["/".join(x[0] for x in stack) + "|" + key,
                           {k: v for k, v in a.items() if k != "class"}])
            if not selfclose:
                stack.append((key, len(els)))
            continue
        a = dict(ATTR.findall(body))
        gpath = "/".join(x[0] for x in stack)
        els.append((gpath, a.get("data-kind", ""), a.get("data-mark", ""),
                    a.get("d", "")))
    return els, groups


def snap(job):
    pg, out = job
    els, groups = page_records(pg)
    json.dump({"els": els, "groups": groups},
              open(os.path.join(out, "%03d.json" % pg), "w"))
    return pg


def load(d, pg):
    return json.load(open(os.path.join(d, "%03d.json" % pg)))


def diff(a, b, lo, hi):
    import collections
    added = collections.Counter()
    removed = collections.Counter()
    moved = 0
    order_changed = 0
    groups_total = 0
    attr_changed = collections.Counter()
    pages_order = collections.Counter()
    for pg in range(lo, hi + 1):
        A, B = load(a, pg), load(b, pg)
        # 1. ink identity: multiset of d-strings must be equal
        da = collections.Counter(e[3] for e in A["els"])
        db = collections.Counter(e[3] for e in B["els"])
        for k, v in (db - da).items():
            added[("d", pg)] += v
        for k, v in (da - db).items():
            removed[("d", pg)] += v
        # 2. ownership: multiset of (group, kind, mark, d)
        ca = collections.Counter(tuple(e) for e in A["els"])
        cb = collections.Counter(tuple(e) for e in B["els"])
        moved += sum((cb - ca).values())
        # 3. order inside each group
        ga = collections.defaultdict(list)
        gb = collections.defaultdict(list)
        for i, e in enumerate(A["els"]):
            ga[e[0]].append(e[3])
        for i, e in enumerate(B["els"]):
            gb[e[0]].append(e[3])
        for k in set(ga) | set(gb):
            groups_total += 1
            if ga.get(k) != gb.get(k):
                order_changed += 1
                pages_order[pg] += 1
        # 4. group attributes
        for (ka, aa), (kb, ab) in zip(A["groups"], B["groups"]):
            if aa != ab:
                attr_changed[(tuple(sorted(aa)), tuple(sorted(ab)))] += 1
    print("pages %d-%d" % (lo, hi))
    print("  d-strings ADDED   : %d (on %d pages)"
          % (sum(added.values()), len({k[1] for k in added})))
    print("  d-strings REMOVED : %d (on %d pages)"
          % (sum(removed.values()), len({k[1] for k in removed})))
    print("  elements whose (group,kind,mark,d) changed: %d" % moved)
    print("  groups whose element ORDER changed: %d of %d (%d pages)"
          % (order_changed, groups_total, len(pages_order)))
    print("  group attribute-set changes:")
    for (aa, ab), n in attr_changed.most_common(20):
        print("    %-70s -> %-70s %d" % (",".join(aa), ",".join(ab), n))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "snapshot":
        out = sys.argv[2]
        lo = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        hi = int(sys.argv[4]) if len(sys.argv) > 4 else 604
        os.makedirs(out, exist_ok=True)
        with Pool(24) as p:
            for _ in p.imap_unordered(snap, [(pg, out) for pg in
                                             range(lo, hi + 1)]):
                pass
        print("snapshot -> %s" % out)
    else:
        diff(sys.argv[2], sys.argv[3],
             int(sys.argv[4]) if len(sys.argv) > 4 else 1,
             int(sys.argv[5]) if len(sys.argv) > 5 else 604)
