#!/usr/bin/env python3
"""Does each ligature group hold the ink its `data-text` names?

`segment_word()` cuts a word into the pieces the Arabic joining rules allow, and each
piece becomes one `<g class="ligature" data-text="...">` in the output. Every audit here
so far has checked the WORD — its marks, its width, how many runs of ink it draws — and
none has checked that cut. Abdullah asked for this after reading p591's output, where
`<g class="ligature" data-text="ء">` contains a single fathah and no letter ink at all,
while the hamzah it names sits in the group before it.

Four things a ligature group can get wrong, in falling order of how provable they are:

  * `empty`      — names letters and holds no body ink. The letters are somewhere else.
  * `count`      — a word emits a different number of groups than its spelling allows.
  * `order`      — groups not in reading order, right to left. An earlier piece's ink
                   must stay right of a later one's on the same line.
  * `marks-only` — holds marks but no letters AND names no letters: harmless, counted
                   separately so it never inflates the real ones.

    python3 tools/audit_ligatures.py 1 604 --jobs 8 --out docs/defects/ligatures.json
"""

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
from collections import Counter

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPE = os.environ.get("QSVG_PIPE", os.path.join(ROOT, "tools", "assign_words.py"))

AW = None
CAP = {}


def _load():
    global AW
    if AW is not None:
        return
    spec = importlib.util.spec_from_file_location("assign_words", PIPE)
    AW = importlib.util.module_from_spec(spec)
    sys.modules["assign_words"] = AW
    spec.loader.exec_module(AW)
    _orig = AW.rewrite
    AW.rewrite = lambda p, a: (CAP.__setitem__("a", a), _orig(p, a))[1]


def page(pg):
    _load()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            AW.assign_page("hafs/kfqc", pg, os.path.join(ROOT, ".cache", "words"))
    except Exception as exc:
        return pg, [], Counter({"page-error": 1})

    rows, stats = [], Counter()
    for w, atoms in CAP["a"]:
        if not w:
            continue
        segs = AW.segment_word(w["rasm_uthmani"]) or []
        key = "%d:%d:%d" % (w["surah"], w["ayah"], w["pos"])
        stats["words"] += 1

        # ONE GROUP IS NOT ONE ATOM (fixed 2026-08-29). The emitter opens a
        # new <g class="ligature"> only when atom["lig"] changes
        # (assign_words rewrite(): lig = (id(word), atom.get("lig", ai)), and
        # the group opens on lig_key change), so consecutive atoms sharing a
        # lig emit as ONE group — 3.7% of words, 308 of 8,236 in a 64-page
        # sample. And the group's data-text comes from atom["seg"], never
        # from segment_word()[i]. Pairing groups to segments BY INDEX
        # therefore named the wrong piece for every one of those words:
        # measured against the emitter's real model, `count` was 38%
        # false-positive AND missed 67% of true mismatches. Build the
        # emitter's groups, and take each name where the emitter takes it.
        groups = []
        for ai, a in enumerate(atoms):
            lk = a.get("lig", ai)
            els = a.get("els") or []
            if groups and groups[-1]["lig"] == lk:
                groups[-1]["els"].extend(els)
                groups[-1]["atoms"].append(a)
            else:
                groups.append({"lig": lk, "els": list(els), "atoms": [a],
                               "named": (a.get("seg") or {}).get("text", "")})
        for g in groups:
            body = [e for e in g["els"] if e["kind"] == "body"]
            g["n"] = len(g["els"])
            g["body"] = body
            g["x1"] = min((e["x1"] for e in body), default=None)
            g["x2"] = max((e["x2"] for e in body), default=None)
            g["marks"] = [e.get("mark") for e in g["els"]
                          if e["kind"] != "body"]
        stats["ligature groups"] += len(groups)

        # Groups and segments are paired BY INDEX, which only means anything when the
        # word emits as many groups as its spelling allows. Where it does not — 2,455
        # words — every later index is shifted and `data-text` names the wrong piece, so
        # nothing downstream of that is reported for the word: it is one defect (`count`),
        # not a group's worth of them. Reporting them anyway put 343 words in the list
        # whose real fault is the count.
        # No index pairing any more, so no gate: every check below reads the
        # name the emitted group actually carries.

        # a group with no letter ink at all
        for i, g in enumerate(groups):
            if g["body"]:
                continue
            named = g["named"]
            kind = "empty" if named else "marks-only"
            stats[kind] += 1
            if kind == "empty":
                rows.append({"page": pg, "key": key, "word": w["rasm_uthmani"],
                             "kind": "empty", "group": i, "names": named,
                             "holds": [m for m in g["marks"] if m]})

        # SURPLUS ONLY. Measured over 604 pages: every true count mismatch
        # is ngroups < nsegs and NOT ONE is a surplus — a deficit is the
        # joining rule disagreeing with the art, which align_segs_atoms
        # exists to absorb and which the pipeline already prices as
        # `ligatures:%d(cost=...)`. Reporting deficits put ~2,000 rows in
        # the list that no one could act on. A SURPLUS is different: the
        # word draws more runs than its spelling allows, which is a real
        # rule violation.
        if len(groups) > max(1, len(segs)):
            stats["count"] += 1
            rows.append({"page": pg, "key": key, "word": w["rasm_uthmani"], "kind": "count",
                         "group": len(groups), "names": "|".join(s["text"] for s in segs),
                         "holds": []})
        elif len(groups) < max(1, len(segs)):
            stats["count-deficit(not reported)"] += 1

        # A mark drawn over another group's ink than the one holding it.
        #
        # Tested by OVERLAP, not by distance between centres. Comparing centres called
        # 26,525 marks misplaced — a third of them — because ligature groups sit side by
        # side and a mark near a boundary is legitimately nearer the next group's middle.
        # A mark belongs to the letters it touches, so the test is: no horizontal overlap
        # with its own group's ink, and real overlap with another's.
        for i, g0 in enumerate(groups):
            own = g0["body"]
            if not own:
                continue
            for e in g0["els"]:
                if e["kind"] == "body" or e.get("mkpart") or e.get("standalone"):
                    continue
                if max(min(b["x2"], e["x2"]) - max(b["x1"], e["x1"])
                       for b in own) > -0.6:
                    continue                      # sits on its own group's letters
                best, bo = None, -0.6
                for j, g in enumerate(groups):
                    if j == i or not g["body"]:
                        continue
                    o = max(min(b["x2"], e["x2"]) - max(b["x1"], e["x1"])
                            for b in g["body"])
                    if o > bo:
                        bo, best = o, j
                if best is None:
                    continue
                stats["misplaced"] += 1
                rows.append({"page": pg, "key": key, "word": w["rasm_uthmani"],
                             "kind": "misplaced", "group": i,
                             "names": "%s sits on group %d's letters"
                                      % (e.get("mark") or "?", best),
                             "holds": [e.get("mark")]})

        # reading order: right to left, so each group's ink starts left of
        # the one before. The 0.6u tolerance made this near-total noise —
        # a kaf headstroke legitimately overhangs the waw before it
        # (وَكَانَ, وَكَفَىٰ, فَٱدْعُ were most of the 62 rows). The
        # overhang is a HIGH stroke: require the offending group's ink to
        # break the order at the BASELINE too, where letters actually sit,
        # and demand a real margin rather than 0.6.
        withink = [g for g in groups if g["x1"] is not None]
        for a, b in zip(withink, withink[1:]):
            _alow = max(e["y2"] for e in a["body"])
            _blow = max(e["y2"] for e in b["body"])
            if b["x2"] > a["x2"] + 4.0 and abs(_alow - _blow) < 6.0:
                stats["order"] += 1
                rows.append({"page": pg, "key": key, "word": w["rasm_uthmani"], "kind": "order",
                             "group": withink.index(b),
                             "names": "%.1f..%.1f then %.1f..%.1f"
                                      % (a["x1"], a["x2"], b["x1"], b["x2"]),
                             "holds": []})
                break
    return pg, rows, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("first", nargs="?", type=int, default=1)
    ap.add_argument("last", nargs="?", type=int, default=604)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "defects", "ligatures.json"))
    args = ap.parse_args(argv)

    from multiprocessing import Pool
    rows, stats = [], Counter()
    with Pool(args.jobs, maxtasksperchild=8) as pool:
        for pg, r, s in pool.imap_unordered(page, range(args.first, args.last + 1)):
            rows += r
            stats.update(s)

    print("words %d | ligature groups %d | page errors %d\n"
          % (stats["words"], stats["ligature groups"], stats["page-error"]))
    for k in ("empty", "count", "order", "misplaced", "marks-only"):
        print("   %-12s %6d" % (k, stats[k]))
    print("\n%d group(s) to look at\n" % len([r for r in rows]))
    for kind in ("empty", "count", "order", "misplaced"):
        sel = [r for r in rows if r["kind"] == kind]
        if not sel:
            continue
        print("== %s (%d) ==" % (kind, len(sel)))
        for r in sel[:20]:
            print("   p%-4d %-11s %-18s group %-2d names %-14s holds %s"
                  % (r["page"], r["key"], r["word"], r["group"], r["names"] or "-",
                     r["holds"] or "-"))
        if len(sel) > 20:
            print("   ... and %d more" % (len(sel) - 20))
        print()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(rows, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
