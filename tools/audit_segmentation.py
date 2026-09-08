#!/usr/bin/env python3
"""Prove the word boundaries ARE the word-by-word-translation-translation release's, everywhere.

The release (`.cache/word_by_word_translation/hafs.json`) is the only source of where words split
(docs/HAFS-JSON-SOURCE.md). `build_word_by_word_translation_seg.py` derives the plan that makes the
word source agree with it; this asks the question the other way round, of the
finished article: for all 6,236 ayahs, does the pipeline emit the release's
words — the same number, in the same order, with the same letters?

Two things are checked, and both must be 0:

    count      an ayah where we emit a different number of words
    skeleton   a word whose letters are not the release's word's letters
               (marks, alef/ya variants, hamzah seats and tatweel folded —
               spelling conventions differ at thousands of words and none of
               them is a boundary)

Together they say that `data-word-key="s:a:n"` names the release's nth word of
that ayah — which is what makes the triple a complete word key, with no second
id to keep in step.

    python3 tools/audit_segmentation.py [--svg]

`--svg` reads the emitted pages in `.cache/words-svg/hafs-kfqc` instead of the
word source, which proves the same thing about the artefact a consumer gets
rather than about the pipeline's intent.
"""
import collections
import os
import re
import sys

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)

import build_word_by_word_translation_seg as seg                            # release_words, skeleton

_W = re.compile(r'<g class="word" data-word-key="(\d+):(\d+):(\d+)"'
                r'[^>]*data-rasm-uthmani="([^"]*)"')


def ours_from_svg():
    d = os.path.join(ROOT, ".cache", "words-svg", "hafs-kfqc")
    by = collections.defaultdict(dict)
    for pg in range(1, 605):
        f = os.path.join(d, "%03d.svg" % pg)
        if not os.path.exists(f):
            raise SystemExit("%s is missing — emit the pages first" % f)
        for s0, a0, p, ut in _W.findall(open(f, encoding="utf-8").read()):
            by[(int(s0), int(a0))][int(p)] = ut
    return by


def ours_from_pipeline():
    import assign_words
    by = collections.defaultdict(dict)
    for pg in range(1, 605):
        for words in assign_words.page_words(
                pg, os.path.join(ROOT, ".cache", "words")).values():
            for w in words:
                by[(w["surah"], w["ayah"])][w["pos"]] = w["rasm_uthmani"]
    return by


def main():
    use_svg = "--svg" in sys.argv
    theirs = seg.release_words()
    ours = ours_from_svg() if use_svg else ours_from_pipeline()
    bad_count, bad_skel = [], []
    for k in sorted(theirs):
        mine = [ours.get(k, {})[p] for p in sorted(ours.get(k, {}))]
        want = theirs[k]
        if len(mine) != len(want):
            bad_count.append("%d:%d we emit %d, the release has %d"
                             % (k[0], k[1], len(mine), len(want)))
            continue
        for n, (ut, t) in enumerate(zip(mine, want), 1):
            if seg.skeleton(ut) != seg.skeleton(t):
                bad_skel.append("%d:%d:%d %s vs the release's %s"
                                % (k[0], k[1], n, ut, t))
    for name, rows in (("count", bad_count), ("skeleton", bad_skel)):
        print("%-9s %d" % (name, len(rows)))
        for r in rows[:20]:
            print("    " + r)
    ok = not (bad_count or bad_skel)
    print("%d ayahs, %d words | %s"
          % (len(theirs), sum(len(v) for v in theirs.values()),
             "the segmentation IS the release's" if ok else "MISMATCHES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
