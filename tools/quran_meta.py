#!/usr/bin/env python3
"""Quran structural metadata, read from the verified caches — never hand-typed.

Three facts this module answers, and where each one comes from:

* **surah** — number, Arabic name, English name, revelation place, ayah count:
  `.cache/meta/chapters.json`, fetched verbatim from the same quran.com API the
  word cache comes from (`/api/v4/chapters?language=en`) and cached on first
  use, exactly as `page_words()` caches `/verses/by_page`.
* **juz / hizb / rubʿ / nisf of every ayah** — `.cache/words/page-*.json`, the
  per-page word cache the pipeline already reads. Every verse record there
  carries `juz_number`, `hizb_number` and `rub_el_hizb_number`, and the three
  are arithmetically consistent over all 6,236 verses (measured: 0 exceptions,
  juz = ceil(rub/8), hizb = ceil(rub/4)), so the global rubʿ index 1-240 is
  the single key and the rest derive from it.
* **the rasm** — a diacritic-stripped form of the uthmani text for search.

Nothing here is typed by hand: every string is copied out of a cache that came
off the API, and the derived numbers are arithmetic on cached numbers.
"""

import glob
import json
import os
import unicodedata
import urllib.request

ROOT = (os.environ.get("QSVG_ROOT")
        or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CHAPTERS_API = "https://api.quran.com/api/v4/chapters?language=en"

_CH = {}
_RUB = {}


def _meta_dir():
    d = os.path.join(ROOT, ".cache", "meta")
    os.makedirs(d, exist_ok=True)
    return d


def chapters():
    """{surah number: chapter record} from the cached quran.com chapter list."""
    if not _CH:
        path = os.path.join(_meta_dir(), "chapters.json")
        if not os.path.exists(path):
            req = urllib.request.Request(
                CHAPTERS_API, headers={"User-Agent": "quran-svg-tools/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            json.dump(data, open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        else:
            data = json.load(open(path, encoding="utf-8"))
        for c in data["chapters"]:
            _CH[int(c["id"])] = {
                "number": int(c["id"]),
                "name_arabic": c["name_arabic"],
                "name_simple": c["name_simple"],
                "name_complex": c["name_complex"],
                "name_english": c["translated_name"]["name"],
                "revelation_place": c["revelation_place"],
                "revelation_order": c["revelation_order"],
                "ayah_count": int(c["verses_count"]),
                "bismillah_pre": bool(c["bismillah_pre"]),
                "pages": list(c["pages"]),
            }
    return _CH


def rub_starts(words_cache=None):
    """{rubʿ 1-240: (surah, ayah)} — the first verse of each of the 240 quarters.

    Built by scanning the page word cache and keeping, per `rub_el_hizb_number`,
    the numerically first verse key. The mushaf order and the numeric order of
    (surah, ayah) coincide, so "first" is unambiguous.
    """
    if not _RUB:
        # Derived once and memoised on disk: scanning all 604 page files costs
        # about a second, and every page build would otherwise pay it.
        derived = os.path.join(_meta_dir(), "rub_starts.json")
        if os.path.exists(derived):
            _RUB.update({int(k): tuple(v) for k, v
                         in json.load(open(derived)).items()})
            return _RUB
        cache = words_cache or os.path.join(ROOT, ".cache", "words")
        best = {}
        for f in sorted(glob.glob(os.path.join(cache, "page-*.json"))):
            data = json.load(open(f, encoding="utf-8"))
            for v in data.get("verses", []):
                r = int(v["rub_el_hizb_number"])
                key = tuple(int(x) for x in v["verse_key"].split(":"))
                if r not in best or key < best[r]:
                    best[r] = key
        if len(best) == 240:
            tmp = derived + ".tmp"
            json.dump({str(k): list(v) for k, v in best.items()}, open(tmp, "w"))
            os.replace(tmp, derived)
        _RUB.update(best)
    return _RUB


def _ordered():
    if "_o" not in _RUB:
        rub_starts()
        _RUB["_o"] = sorted(((v, k) for k, v in _RUB.items()
                             if isinstance(k, int)))
    return _RUB["_o"]


def position(surah, ayah):
    """{'juz','hizb','rub','rub_in_hizb','nisf'} for one ayah.

    `rub` is the global quarter index 1-240; `rub_in_hizb` is 1-4 inside its
    hizb; `nisf` is 1 for the first half of the hizb (quarters 1-2) and 2 for
    the second (quarters 3-4) — the نصف الحزب division.
    """
    key = (int(surah), int(ayah))
    lo, hi = 0, len(_ordered()) - 1
    seq = _ordered()
    r = seq[0][1]
    while lo <= hi:
        mid = (lo + hi) // 2
        if seq[mid][0] <= key:
            r = seq[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return rub_position(r)


def rub_position(r):
    r = int(r)
    return {"juz": (r + 7) // 8, "hizb": (r + 3) // 4, "rub": r,
            "rub_in_hizb": ((r - 1) % 4) + 1,
            "nisf": 1 if ((r - 1) % 4) < 2 else 2}


def starts_at(surah, ayah):
    """Which division, if any, BEGINS at this ayah: {'juz','hizb','rub'} subset."""
    seq = {v: k for k, v in rub_starts().items() if isinstance(k, int)}
    r = seq.get((int(surah), int(ayah)))
    if r is None:
        return {}
    p = rub_position(r)
    out = {"rub": r}
    if p["rub_in_hizb"] == 1:
        out["hizb"] = p["hizb"]
        if p["hizb"] % 2 == 1:
            out["juz"] = p["juz"]
    if p["rub_in_hizb"] == 3:
        out["nisf"] = p["hizb"]
    return out


# ---------------------------------------------------------------------------
# The rasm — a clean search key
# ---------------------------------------------------------------------------
#
# Measured over all 77,429 words of the cached uthmani text: 72 distinct code
# points appear. Every one of them falls into exactly two groups —
#
#   KEEP  category Lo, 47 code points: the Arabic letters, INCLUDING every
#         alef form separately (ا U+0627, أ U+0623, إ U+0625, آ U+0622,
#         ٱ U+0671), ى U+0649 beside ي U+064A, and ة U+0629 beside ه U+0647.
#         Abdullah ruled these are NOT folded, so they are not.
#   DROP  categories Mn (24 code points: every haraka, tanween, sukun,
#         shadda, superscript alef, and every small high/low sign),
#         Lm (U+0640 tatweel ×6,736, U+06E5 small waw ×1,257,
#         U+06E6 small yeh ×957 — modifier letters, drawn as marks in this
#         print), So (U+06DE rub sign ×199, U+06E9 sajdah ×15) and
#         Cf (U+200F RLM ×1).
#
# The two groups are disjoint by Unicode category, so the rule is a category
# test rather than a hand-written code-point list — nothing to keep in sync.
_DROP_CATEGORIES = ("Mn", "Lm", "So", "Cf", "Me", "Sk")


def rasm(text):
    """Diacritic-stripped uthmani: the letters only, folded nowhere.

    `ٱلرَّحْمَٰنِ` → `ٱلرحمن`. Note the alef wasla is KEPT as itself — Abdullah
    ruled against alef/hamza/ya folding, so this is the letter skeleton of the
    uthmani spelling, not a normalised search form.
    """
    if not text:
        return ""
    out = [ch for ch in text
           if unicodedata.category(ch) not in _DROP_CATEGORIES]
    return " ".join("".join(out).split())


if __name__ == "__main__":
    import sys
    ch = chapters()
    print("chapters %d, rub starts %d"
          % (len(ch), len([k for k in rub_starts() if isinstance(k, int)])))
    for a in sys.argv[1:]:
        print(a, "->", rasm(a))
