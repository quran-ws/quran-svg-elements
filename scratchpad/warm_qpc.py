#!/usr/bin/env python3
"""Fill .cache/words-qpc/ — the King Fahd Complex's own text, word by word.

`assign_words.qpc_words()` reads `.cache/words-qpc/page-NNN.json` and has named
this script as what writes it since the cache was introduced; the script did not
exist until 2026-09-08, so no checkout could emit `data-qpc` and the fifth text
form was simply absent everywhere.

It does NOT fetch. quran.com does not serve `qpc_uthmani_hafs` as a word field —
asking for it returns the default fields silently — and its
`/quran/verses/qpc_uthmani_hafs` endpoint answers with `text_uthmani`. The text
is already in the repo: `.cache/official/hafsData_v2-0.json` is the UthmanicHafs
v2.0 release, ayah-keyed, and it is the print's own spelling (sukun U+06E1,
open tanwin U+08F0-08F2) where quran.com writes the rasm_uthmani spelling.

So the work here is alignment, not download: split each ayah's text on spaces
and pair the tokens with our word list for that ayah. Where the two disagree on
how many words the ayah has — the handful of sites where the segmentation plan
splits or fuses (CLAUDE.md, `QSVG_WBWSEG`) — the ayah is left out rather than
guessed at, because a mis-paired qpc is worse than an absent one.

    python3 scratchpad/warm_qpc.py            # all 604 pages
    python3 scratchpad/warm_qpc.py 42 48      # a range
"""
import json
import os
import sys
import unicodedata

ROOT = os.environ.get("QSVG_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
OFFICIAL = os.path.join(ROOT, ".cache", "official", "hafsData_v2-0.json")
WORDS = os.path.join(ROOT, ".cache", "words")
OUT = os.path.join(ROOT, ".cache", "words-qpc")

# The ornaments ride in the text but are not words, and every ayah ends with its
# number drawn as a QCF presentation-form glyph (1:1 ends "\ufc00") — also not a
# word. Both are dropped before pairing.
_DROP = {"\u06de", "\u06e9"}          # ۞ rubʿ rosette, ۩ sajdah


def _is_marker(tok):
    return all(0xFB50 <= ord(c) <= 0xFDFF or 0xFE70 <= ord(c) <= 0xFEFF
               or 0xE000 <= ord(c) <= 0xF8FF for c in tok)


def official():
    """{(surah, ayah): [token, ...]} from the release, ornaments dropped."""
    rows = json.load(open(OFFICIAL, encoding="utf-8"))
    rows = rows if isinstance(rows, list) else rows.get("data", [])
    out = {}
    for r in rows:
        toks = [t for t in r["aya_text"].split()
                if t and not all(ch in _DROP for ch in t)
                and not _is_marker(t)]
        out[(int(r["sura_no"]), int(r["aya_no"]))] = toks
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    first = int(args[0]) if args else 1
    last = int(args[1]) if len(args) > 1 else (first if args else 604)
    if not os.path.exists(OFFICIAL):
        print("missing %s — the UthmanicHafs release is the source" % OFFICIAL,
              file=sys.stderr)
        return 1
    text = official()
    os.makedirs(OUT, exist_ok=True)

    pages = paired = skipped_ayahs = 0
    mismatch = []
    for pg in range(first, last + 1):
        src = os.path.join(WORDS, "page-%03d.json" % pg)
        if not os.path.exists(src):
            continue
        data = json.load(open(src, encoding="utf-8"))
        ayahs = []
        for v in data.get("verses", []):
            s, a = (int(x) for x in v["verse_key"].split(":"))
            ours = [w for w in v.get("words", [])
                    if w.get("char_type_name") == "word"]
            toks = text.get((s, a))
            if toks is None or len(toks) != len(ours):
                skipped_ayahs += 1
                if toks is not None:
                    mismatch.append(("%d:%d" % (s, a), len(ours), len(toks)))
                continue
            ayahs.append({"verse_key": v["verse_key"], "words": [
                {"position": w["position"], "qpc_uthmani_hafs": t}
                for w, t in zip(ours, toks)]})
            paired += len(ours)
        json.dump({"verses": ayahs},
                  open(os.path.join(OUT, "page-%03d.json" % pg), "w",
                       encoding="utf-8"), ensure_ascii=False)
        pages += 1

    print("words-qpc: %d pages written, %d words paired, %d ayahs left out"
          % (pages, paired, skipped_ayahs))
    if mismatch:
        print("  word-count disagreements (ours vs the release), first 10:",
              file=sys.stderr)
        for k, o, t in mismatch[:10]:
            print("    %-9s ours %2d  release %2d" % (k, o, t), file=sys.stderr)
        print("  %d in total" % len(mismatch), file=sys.stderr)
    return 0


sys.exit(main())
