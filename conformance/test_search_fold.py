"""The shared search-fold conformance vector — see docs/SEARCH-FOLD.md.

`search-fold.json` is byte-identical to the copies in quran-text and
quran-engine, so all three implementations are pinned to one specification.
Every input in it is copied from a real data file; none is typed by hand.

Runnable either way:  pytest conformance/  |  python3 conformance/test_search_fold.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import quran_meta  # noqa: E402
import search_fold  # noqa: E402

VECTORS = json.loads(
    (pathlib.Path(__file__).with_name("search-fold.json")).read_text(encoding="utf8")
)["vectors"]


def test_conformance_vector():
    for case in VECTORS:
        text = case["input"]
        assert search_fold.search_key(text) == case["search_key"], case["note"]
        assert search_fold.match_fold(text) == case["match_fold"], case["note"]
        assert search_fold.loose_key(text) == case["loose_key"], case["note"]


def test_rasm_is_the_search_key():
    """The `search` field this repo already ships IS the spec's stored key.

    `search` is built as quran_meta.rasm(rasm_imlai). If these two ever diverge,
    the published index stops matching what the other blocks compute.
    """
    for case in VECTORS:
        assert quran_meta.rasm(case["input"]) == search_fold.search_key(case["input"]), (
            f"quran_meta.rasm disagrees with the spec on {case['note']}"
        )


def test_both_sides_must_be_folded():
    """The gap this module closes: the stored key is not folded, on purpose."""
    stored = "أنعمت"      # as `search` ships it, hamzah intact
    typed = "انعمت"       # as a keyboard produces it
    assert stored != typed, "raw equality misses this — the old recipe's bug"
    assert search_fold.match_fold(stored) == search_fold.match_fold(typed)


def test_omitted_alif_stays_stripped():
    # ٱلرَّحۡمَٰنِ keys as الرحمن, not الرحمان. quran-text used to do the opposite.
    rasm_uthmani = VECTORS[0]["input"]
    assert search_fold.match_fold(rasm_uthmani) == "الرحمن"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print(f"\n{len(VECTORS)} vectors, all implementations agree.")
