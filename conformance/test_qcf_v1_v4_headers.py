#!/usr/bin/env python
"""Focused contracts for standalone QPC V4 heading assets."""

import copy
import json
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_qcf_v1_v4_headers import asset_plan, source_settings, svg_asset


def manifest() -> dict:
    return json.loads((ROOT / "conformance/qcf-v1-source.json").read_text())


def test_asset_plan_is_complete_and_unambiguous():
    assets = asset_plan(manifest())
    assert len(assets) == 115
    assert assets[0] == {
        "kind": "surah-name",
        "surah": 1,
        "codepoint": "U+FC45",
        "path": "surah/001.svg",
        "font": "surah",
    }
    assert assets[113]["surah"] == 114
    assert assets[113]["codepoint"] == "U+FBEB"
    assert assets[114] == {
        "kind": "basmalah",
        "codepoint": "U+F8DD",
        "path": "basmalah.svg",
        "font": "basmalah",
    }


def test_svg_asset_preserves_outline_and_normalizes_only_the_viewbox():
    data = svg_asset(
        "surah-name",
        "U+FC45",
        "M10 -20L110 -20L110 30Z",
        (10, -20, 110, 30),
        120,
        2048,
        1,
    )
    root = ElementTree.fromstring(data)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    assert root.attrib["viewBox"] == "0 0 100 50"
    assert root.attrib["data-surah"] == "1"
    assert root.attrib["data-codepoint"] == "U+FC45"
    path = root.find("svg:path", namespace)
    assert path.attrib["d"] == "M10 -20L110 -20L110 30Z"
    assert path.attrib["transform"] == "matrix(1 0 0 -1 -10 30)"
    assert path.attrib["data-kind"] == "surah-name"


def test_manifest_rejects_duplicate_complete_header_identity():
    source = copy.deepcopy(manifest())
    source["header_assets"]["surah_name"]["codepoints"][1] = source["header_assets"][
        "surah_name"
    ]["codepoints"][0]
    try:
        source_settings(source)
    except ValueError as error:
        assert "complete-header" in str(error)
    else:
        raise AssertionError("accepted duplicate full-header codepoints")


def test_manifest_rejects_an_unresolved_print_year():
    source = manifest()
    source["print_year_hijri"] = 1400
    try:
        source_settings(source)
    except ValueError as error:
        assert "1405H" in str(error)
    else:
        raise AssertionError("accepted a non-1405H header source")


if __name__ == "__main__":
    tests = sorted(
        (name, function)
        for name, function in globals().items()
        if name.startswith("test_") and callable(function)
    )
    for name, test in tests:
        test()
        print("ok ", name)
    print(f"\n{len(tests)} tests passed")
