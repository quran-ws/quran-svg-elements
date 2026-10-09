#!/usr/bin/env python3
"""Regression for the line-wrap boundary around 5:83 on printed page 121."""

from pathlib import Path
import contextlib
import hashlib
import io
import os
import sys

os.environ.setdefault("QSVG_PROFILE", "production")
ARTWORK = os.environ.get("QSVG_ROOT")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import assign_words  # noqa: E402

EXPECTED_SHA256 = "e0a137e79b0e5be9a46b751b808fdb8c62905f225926e73f9c66ff4c770ea7a2"
EXPECTED = {
    "41.1,444.0,50.9,461.8": ("5:83:4", "body", None),
    "44.5,439.6,50.8,443.0": ("5:83:4", "mark", "fathah"),
    "34.7,465.5,39.0,467.8": ("5:83:5", "mark", "kasrah"),
    "33.2,443.6,36.3,460.4": ("5:83:5", "body", None),
    "5.9,442.8,31.4,464.5": ("5:83:5", "body", None),
    "22.9,439.2,29.9,442.8": ("5:83:5", "mark", "fathah"),
    "328.8,480.7,331.9,497.1": ("5:83:6", "body", None),
    "313.0,479.0,326.8,501.4": ("5:83:6", "body", None),
    "314.7,477.0,322.5,480.7": ("5:83:6", "mark", "fathah"),
    "317.6,481.8,321.9,485.1": ("5:83:6", "mark", "shaddah"),
    "292.7,488.9,317.6,501.9": ("5:83:6", "body", None),
    "306.9,480.2,312.2,486.9": ("5:83:6", "mark", "dammah"),
    "293.6,496.2,299.3,499.3": ("5:83:6", "mark", "kasrah"),
    "287.3,477.9,297.1,497.2": ("5:83:6", "body", None),
}


def main():
    if not ARTWORK:
        raise SystemExit("QSVG_ROOT must name the prepared artwork root")
    root = Path(ARTWORK)
    captured = {}
    original = assign_words.rewrite

    def spy(page, assignment):
        captured["assignment"] = assignment
        return original(page, assignment)

    assign_words.rewrite = spy
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _, svg, _, _ = assign_words.assign_page(
                "hafs/kfqc", 121, root / ".cache/words"
            )
    finally:
        assign_words.rewrite = original

    actual = {}
    seen = set()
    for word, atoms in captured["assignment"]:
        if not word:
            continue
        owner = f"{word['surah']}:{word['ayah']}:{word['pos']}"
        for atom in atoms:
            for element in atom["els"]:
                if id(element) in seen:
                    continue
                seen.add(id(element))
                key = "%.1f,%.1f,%.1f,%.1f" % (
                    element["x1"], element["y1"], element["x2"], element["y2"]
                )
                if key in EXPECTED:
                    if key in actual:
                        raise AssertionError(f"duplicate page-121 geometry key: {key}")
                    actual[key] = (owner, element["kind"], element.get("mark"))

    assert actual == EXPECTED, (actual, EXPECTED)
    digest = hashlib.sha256(svg.encode()).hexdigest()
    assert digest == EXPECTED_SHA256, digest
    print(f"ok: page 121 owns all {len(EXPECTED)} boundary elements; sha256 {digest}")


if __name__ == "__main__":
    main()
