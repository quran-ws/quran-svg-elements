#!/usr/bin/env python3
"""Do the human overrides contradict the text?

Every entry in .cache/review/overrides.json seats one piece of ink on one
word, optionally naming it. Two things can be checked without any eye:

  CONTRADICTS  the override names a mark the target word's spelling does
               not contain at all (p589: a small_waw pinned to كَانَ, which
               has no ۥ — it was إِنَّهُۥ's suffix, read by distance instead
               of direction).
  MISSING      the geometry key matches no element on the page any more, so
               the override is dead weight (the pipeline moved past it).

Neither is proof on its own — a composite outline can carry a mark the
spelling writes differently — but both are worth a human's eye, and a
CONTRADICTS entry has never yet been right.
"""
import json
import os
import sys

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assign_words as aw  # noqa: E402

# the letter/sign each mark name is written with in the rasm_uthmani text
CHARS = {
    "fathah": "َ", "kasrah": "ِ", "dammah": "ُ",
    "tanwin_al_fath": "ًࣰ", "tanwin_al_kasr": "ٍࣲ",
    "tanwin_al_damm": "ٌࣱ", "shaddah": "ّ",
    "sukun": "ْۡ", "maddah": "ٓ",
    "omitted_alif": "ٰ", "small_waw": "ۥ", "small_yaa": "ۦ",
    "hamzah": "ءٕٔ", "hamzat_al_wasl": "ٱٖ",
    "small_meem": "ۭۢ",
}


def main():
    ovp = os.path.join(ROOT, ".cache", "review", "overrides.json")
    ov = json.load(open(ovp))
    cache = os.path.join(ROOT, ".cache", "words")
    bad, dead, total = [], [], 0
    for pg in sorted(ov, key=int):
        entries = ov[pg]
        if not entries:
            continue
        cap = {}
        _orig = aw.rewrite
        aw.rewrite = lambda p, a: (cap.__setitem__("a", a), _orig(p, a))[1]
        try:
            aw.assign_page("hafs/kfqc", int(pg), cache)
        finally:
            aw.rewrite = _orig
        words = {}
        boxes = set()
        for w, at in cap.get("a", []):
            if w:
                words["%d:%d:%d" % (w["surah"], w["ayah"], w["pos"])] = w
            for a in at:
                for e in a["els"]:
                    boxes.add("%.1f,%.1f,%.1f,%.1f"
                              % (e["x1"], e["y1"], e["x2"], e["y2"]))
        for key, val in entries.items():
            total += 1
            tgt, _, name = val.partition("|")
            w = words.get(tgt)
            if key not in boxes:
                dead.append((pg, key, val))
            if name and w and name in CHARS:
                if not any(c in w["rasm_uthmani"] for c in CHARS[name]):
                    bad.append((pg, key, val, w["rasm_uthmani"]))
    print("overrides %d | CONTRADICTS %d | key no longer present %d"
          % (total, len(bad), len(dead)))
    for pg, key, val, txt in bad:
        print("  CONTRADICTS p%s  %s -> %s   (%s has no %s)"
              % (pg, key, val, txt, val.partition("|")[2]))
    for pg, key, val in dead:
        print("  key-gone     p%s  %s -> %s" % (pg, key, val))


if __name__ == "__main__":
    main()
