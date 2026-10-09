#!/usr/bin/env python3
"""Contracts for the public text forms copied into bundle indexes."""

from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import assign_words  # noqa: E402
import bundle_extract  # noqa: E402


def test_qpc_uses_the_source_faithful_spelling_not_the_budget_form():
    word = {
        "surah": 1,
        "ayah": 1,
        "pos": 1,
        "rasm_uthmani": "emitted",
        "rasm_imlai": "imlai",
        "qpc": "budget-order",
        "qpc_text": "published-order",
    }

    def page_words(page, _cache):
        return {1: [word]} if page == 1 else {}

    with patch.object(assign_words, "page_words", page_words):
        forms = bundle_extract.text_forms(1, "/unused")

    assert forms["1:1:1"]["qpc"] == "published-order"


def test_qpc_falls_back_for_the_legacy_source():
    word = {
        "surah": 1,
        "ayah": 1,
        "pos": 1,
        "rasm_uthmani": "emitted",
        "rasm_imlai": "imlai",
        "qpc": "legacy-published",
    }

    def page_words(page, _cache):
        return {1: [word]} if page == 1 else {}

    with patch.object(assign_words, "page_words", page_words):
        forms = bundle_extract.text_forms(1, "/unused")

    assert forms["1:1:1"]["qpc"] == "legacy-published"


if __name__ == "__main__":
    tests = sorted((name, fn) for name, fn in globals().items()
                   if name.startswith("test_") and callable(fn))
    for name, test in tests:
        test()
        print("ok ", name)
    print(f"\n{len(tests)} tests passed")
