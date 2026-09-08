#!/usr/bin/env python3
"""Quran structural metadata, read from the verified caches — never hand-typed.

Three facts this module answers, and where each one comes from:

* **surah** — number, Arabic name, English name, revelation place, ayah count:
  `.cache/meta/chapters.json`, fetched verbatim from the same quran.com API the
  word cache comes from (`/api/v4/chapters?language=en`) and cached on first
  use, exactly as `page_words()` caches `/verses/by_page`.
* **juz / hizb / rubʿ / nisf of every ayah** — `.cache/words/page-*.json`, the
  per-page word cache the pipeline already reads. Every ayah record there
  carries `juz_number`, `hizb_number` and `rub_el_hizb_number`, and the three
  are arithmetically consistent over all 6,236 ayahs (measured: 0 exceptions,
  juz = ceil(rubu_al_hizb/8), hizb = ceil(rubu_al_hizb/4)), so the global rubʿ index 1-240 is
  the single key and the rest derive from it.
* **the rasm** — a diacritic-stripped form of the rasm_uthmani text for search.

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


_SURAH_NAMES = {}


def surah_names():
    """{number: (code, display)} — the 114 names, from the terminology standard.

    quran.com's `name_simple` is the publisher's own transliteration, quoted
    here as it writes it.  terminology: ignore
    The standard fixes one name per surah, so what this project shows a reader
    comes from the registry (Naba, Aal Imran, Saad) and not from whatever the
    source happened to write.
    """
    if not _SURAH_NAMES:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "surah_names.tsv")
        for line in open(path, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            num, code, _arabic, display = line.rstrip("\n").split("\t")
            _SURAH_NAMES[int(num)] = (code, display)
    return _SURAH_NAMES


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
                "name_latin": surah_names()[int(c["id"])][1],
                "name_code": surah_names()[int(c["id"])][0],
                "name_simple": c["name_simple"],   # the publisher's, kept as read
                "name_complex": c["name_complex"],
                "name_english": c["translated_name"]["name"],
                "revelation_place": c["revelation_place"],
                "revelation_order": c["revelation_order"],
                "ayah_count": int(c["verses_count"]),
                "basmalah_pre": bool(c["bismillah_pre"]),
                "pages": list(c["pages"]),
            }
    return _CH


def rubu_al_hizb_starts(words_cache=None):
    """{rubʿ 1-240: (surah, ayah)} — the first ayah of each of the 240 quarters.

    Built by scanning the page word cache and keeping, per `rub_el_hizb_number`,
    the numerically first ayah key. The mushaf order and the numeric order of
    (surah, ayah) coincide, so "first" is unambiguous.
    """
    if not _RUB:
        # Derived once and memoised on disk: scanning all 604 page files costs
        # about a second, and every page build would otherwise pay it.
        derived = os.path.join(_meta_dir(), "rubu_al_hizb_starts.json")
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
        rubu_al_hizb_starts()
        _RUB["_o"] = sorted(((v, k) for k, v in _RUB.items()
                             if isinstance(k, int)))
    return _RUB["_o"]


def position(surah, ayah):
    """{'juz','hizb','rubu_al_hizb','rubu_al_hizb_in_hizb','nisf'} for one ayah.

    `rubu_al_hizb` is the global quarter index 1-240; `rubu_al_hizb_in_hizb` is 1-4 inside its
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
    return rubu_al_hizb_position(r)


def rubu_al_hizb_position(r):
    r = int(r)
    return {"juz": (r + 7) // 8, "hizb": (r + 3) // 4, "rubu_al_hizb": r,
            "rubu_al_hizb_in_hizb": ((r - 1) % 4) + 1,
            "nisf": 1 if ((r - 1) % 4) < 2 else 2}


def starts_at(surah, ayah):
    """Which division, if any, BEGINS at this ayah: {'juz','hizb','rubu_al_hizb'} subset."""
    seq = {v: k for k, v in rubu_al_hizb_starts().items() if isinstance(k, int)}
    r = seq.get((int(surah), int(ayah)))
    if r is None:
        return {}
    p = rubu_al_hizb_position(r)
    out = {"rubu_al_hizb": r}
    if p["rubu_al_hizb_in_hizb"] == 1:
        out["hizb"] = p["hizb"]
        if p["hizb"] % 2 == 1:
            out["juz"] = p["juz"]
    if p["rubu_al_hizb_in_hizb"] == 3:
        out["nisf"] = p["hizb"]
    return out


# ---------------------------------------------------------------------------
# The rasm — a clean search key
# ---------------------------------------------------------------------------
#
# Measured over all 77,429 words of the cached rasm_uthmani text: 72 distinct code
# points appear. Every one of them falls into exactly two groups —
#
#   KEEP  category Lo, 47 code points: the Arabic letters, INCLUDING every
#         alef form separately (ا U+0627, أ U+0623, إ U+0625, آ U+0622,
#         ٱ U+0671), ى U+0649 beside ي U+064A, and ة U+0629 beside ه U+0647.
#         Abdullah ruled these are NOT folded, so they are not.
#   DROP  categories Mn (24 code points: every harakah, tanwin, sukun,
#         shaddah, superscript alef, and every small high/low sign),
#         Lm (U+0640 tatweel ×6,736, U+06E5 small waw ×1,257,
#         U+06E6 small yeh ×957 — modifier letters, drawn as marks in this
#         print), So (U+06DE rubu_al_hizb sign ×199, U+06E9 sajdah ×15) and
#         Cf (U+200F RLM ×1).
#
# The two groups are disjoint by Unicode category, so the rule is a category
# test rather than a hand-written code-point list — nothing to keep in sync.
_DROP_CATEGORIES = ("Mn", "Lm", "So", "Cf", "Me", "Sk")


def rasm(text):
    """Diacritic-stripped rasm_uthmani: the letters only, folded nowhere.

    `ٱلرَّحْمَٰنِ` → `ٱلرحمن`. Note the alef hamzat_al_wasl is KEPT as itself — Abdullah
    ruled against alef/hamzah/ya folding, so this is the letter skeleton of the
    rasm_uthmani spelling, not a normalised search form.
    """
    if not text:
        return ""
    out = [ch for ch in text
           if unicodedata.category(ch) not in _DROP_CATEGORIES]
    return " ".join("".join(out).split())


if __name__ == "__main__":
    import sys
    ch = chapters()
    print("chapters %d, rubu_al_hizb starts %d"
          % (len(ch), len([k for k in rubu_al_hizb_starts() if isinstance(k, int)])))
    for a in sys.argv[1:]:
        print(a, "->", rasm(a))
