"""The shared quran-ws search fold — see docs/SEARCH-FOLD.md.

This repository already builds the right *stored* key: `search` is
`quran_meta.rasm(rasm_imlai)`, the modern spelling with its marks removed, and
that is what a search box should match against. Abdullah settled that on
2026-08-29 and the conformance test pins it.

What was missing is the other half. The stored key is deliberately NOT folded —
`أنعمت` keeps its hamzah — so a consumer comparing a raw query against it
silently misses every word whose letter forms the user typed differently. That
is 4,385 of the 14,897 distinct keys, 29% of them.

So: `match_fold` is applied to BOTH sides at match time, `loose_key` is a
flagged fallback, and `search_variants` is for sources with no rasm_imlai
spelling. The implementations here are character-for-character the same
specification as quran-text (JavaScript, Python) and quran-engine (Rust).
"""

import unicodedata

#: Marks, tatweel, Quranic annotation signs, joiners — everything that is not a
#: letter. The same six categories `quran_meta.rasm` drops, named once here.
DROP_CATEGORIES = frozenset(("Mn", "Me", "Lm", "Sk", "So", "Cf"))

FOLD_LETTERS = {
    "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا",
    "ى": "ي", "ئ": "ي",
    "ؤ": "و",
    "ة": "ه",
}
FOLD_LETTERS.update({chr(0x0660 + d): str(d) for d in range(10)})
FOLD_LETTERS.update({chr(0x06F0 + d): str(d) for d in range(10)})


def _strip(text):
    return "".join(c for c in text
                   if unicodedata.category(c) not in DROP_CATEGORIES)


def search_key(text):
    """The stored key: letters only, nothing folded.

    Identical to `quran_meta.rasm`, and pinned to it by the conformance test.
    Feed it `rasm_imlai`, never `rasm_uthmani` — the rasm_uthmani writes long
    vowels as combining marks, so stripping it deletes them outright.
    """
    return " ".join(_strip(unicodedata.normalize("NFC", text)).split())


def match_fold(text):
    """Applied to BOTH the query and the stored `search` value at match time.

    Stripping comes before the letter mapping: a mark sitting between a bearer
    and its hamzah would otherwise block it.
    """
    stripped = _strip(unicodedata.normalize("NFKC", text))
    return " ".join("".join(FOLD_LETTERS.get(c, c) for c in stripped).split())


def loose_key(text):
    """Fallback only, and only when the strict pass found nothing.

    Deliberately lossy — it merges كاتب, كتاب and كتب — so results matched this
    way must be shown as approximate.
    """
    return "".join(c for c in match_fold(text) if c not in "اء")


def search_variants(text):
    """Every spelling a word might reasonably be typed as, for sources with no
    rasm_imlai spelling. Not needed for this repository's own `search` field,
    which has one; here for parity with quran-text and quran-engine.
    """
    out = []
    for spelling in (text, text.replace("ٰ", "ا")):
        base = match_fold(spelling)
        for cand in (base, base.replace("ء", ""), base.replace("ء", "ي")):
            if cand and cand not in out:
                out.append(cand)
    return out
