#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "cairosvg==2.8.2",
#   "fonttools==4.66.1",
#   "numpy==2.3.3",
#   "pillow==11.3.0",
#   "scipy==1.16.2",
# ]
# ///
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location(
    "qcf_v1_visual_audit", ROOT / "tools/qcf_v1_visual_audit.py"
)
visual = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = visual
SPEC.loader.exec_module(visual)
SVG = visual.SVG


def test_parse_pages() -> None:
    assert visual.parse_pages("3,1-2,2") == [1, 2, 3]
    for value in ("", "0", "605", "4-2", "x"):
        try:
            visual.parse_pages(value)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"accepted invalid page selection: {value!r}")


def test_pair_reference_evidence_requires_supported_overlap_and_quality() -> None:
    first = np.zeros((20, 40), dtype=np.uint8)
    second = np.zeros_like(first)
    fallback_first = np.zeros_like(first)
    fallback_second = np.zeros_like(first)
    first[5:15, 5:16] = 255
    second[5:15, 15:26] = 255
    fallback_first[5:15, 5:15] = 255
    fallback_second[5:15, 16:26] = 255
    supported = (first >= 24) | (second >= 24)
    evidence = visual.pair_reference_evidence(
        (first, second),
        (fallback_first, fallback_second),
        ((5, 5, 16, 15), (15, 5, 26, 15)),
        ((5, 5, 15, 15), (16, 5, 26, 15)),
        supported,
        visual.DEFAULT_POLICY,
    )
    assert evidence is not None and evidence["attested"] is True
    unsupported = supported.copy()
    unsupported[:, 13:18] = False
    evidence = visual.pair_reference_evidence(
        (first, second),
        (fallback_first, fallback_second),
        ((5, 5, 16, 15), (15, 5, 26, 15)),
        ((5, 5, 15, 15), (16, 5, 26, 15)),
        unsupported,
        {**visual.DEFAULT_POLICY, "reference_tolerance_pixels": 0},
    )
    assert evidence is not None and evidence["attested"] is False
    weak_first = np.zeros_like(first)
    weak_second = np.zeros_like(first)
    weak_first[5:15, 5:12] = 255
    weak_second[5:15, 11:18] = 255
    evidence = visual.pair_reference_evidence(
        (weak_first, weak_second),
        (fallback_first, fallback_second),
        ((5, 5, 12, 15), (11, 5, 18, 15)),
        ((5, 5, 15, 15), (16, 5, 26, 15)),
        (fallback_first >= 24) | (fallback_second >= 24),
        visual.DEFAULT_POLICY,
    )
    assert evidence is not None and evidence["quality_acceptable"] is False
    assert evidence["overlap_support_fraction"] == 1.0
    assert evidence["attested"] is False


def test_boxes_do_not_decide_collision() -> None:
    first = np.zeros((20, 40), dtype=np.uint8)
    second = np.zeros_like(first)
    first[4:16, 2:8] = 255
    first[4:16, 30:36] = 255
    second[4:16, 14:24] = 255
    result = visual.pair_metrics(first, second, (0, 0, 40, 20), (0, 0, 40, 20), 24, 160)
    assert result["solid_overlap_pixels"] == 0
    assert result["soft_overlap_pixels"] == 0
    assert result["minimum_distance_pixels"] > 1


def test_actual_overlap_is_measured() -> None:
    first = np.zeros((12, 12), dtype=np.uint8)
    second = np.zeros_like(first)
    first[2:9, 2:8] = 255
    second[4:11, 6:11] = 255
    result = visual.pair_metrics(first, second, (0, 0, 12, 12), (0, 0, 12, 12), 24, 160)
    assert result["solid_overlap_pixels"] == 10
    assert result["minimum_distance_pixels"] == 0


def test_component_and_counter_counts_ignore_tiny_noise() -> None:
    ring = np.zeros((15, 15), dtype=bool)
    ring[2:13, 2:13] = True
    ring[5:10, 5:10] = False
    ring[0, 0] = True
    assert visual.component_count(ring) == 1
    assert visual.hole_count(ring) == 1


def test_review_ledger_cannot_waive_blocker_and_stale_decisions_fail() -> None:
    review = visual.finding("tight", "review", page=1, word_key="1:1:1")
    blocker = visual.finding("overlap", "blocker", page=1, word_key="1:1:2")
    ledger = {
        "schema": "qcf-v1/visual-review-ledger",
        "schema_version": 1,
        "findings": [
            {"id": review["id"], "status": "open", "reason": "unresolved"},
            {"id": blocker["id"], "status": "accepted", "reason": "must be ignored"},
            {"id": "stale", "status": "accepted", "reason": "old result"},
        ],
    }
    result = visual.apply_review([review, blocker], ledger)
    assert result["open"] == [review["id"]]
    assert result["accepted"] == []
    assert result["stale"] == ["stale"]
    assert blocker["review_ignored"] is True


def test_ornament_inventory_drift_is_json_serializable() -> None:
    candidate = ElementTree.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<g class="ayah-mark" data-ayah-key="1:1"><path d="M0 0H1V1H0Z"/></g>'
        "</svg>"
    )
    fallback = ElementTree.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>'
    )
    rows = visual.ornament_findings(1, candidate, fallback, visual.DEFAULT_POLICY)
    assert rows[0]["category"] == "ornament-inventory-drift"
    assert rows[0]["candidate"] == [
        {
            "class": "ayah-mark",
            "ayah_key": "1:1",
            "word_key": None,
            "sid": None,
            "count": 1,
        }
    ]
    assert rows[0]["fallback"] == []
    json.dumps(rows)


def test_optical_copies_are_cardinal_and_symmetric() -> None:
    paths = "".join(
        f'<path d="M0 0H1V1H0Z" transform="matrix(1 0 0 1 {x} {y})"/>'
        for x, y in ((10, 10), (9.5, 10), (10.5, 10), (10, 9.5), (10, 10.5))
    )
    group = ElementTree.fromstring(
        f'<g xmlns="http://www.w3.org/2000/svg" class="word" data-word-key="1:1:1">{paths}</g>'
    )
    row = {
        "hq": True,
        "paths": group.findall(f".//{SVG}path"),
        "line": 1,
        "key": "1:1:1",
        "text": "x",
    }
    assert visual.optical_copy_findings(1, [row]) == []
    row["paths"][-1].set("transform", "matrix(1 0 0 1 10.5 10.5)")
    assert (
        visual.optical_copy_findings(1, [row])[0]["category"]
        == "optical-copy-transform"
    )


def test_vertical_stretch_is_explicit_and_scan_corroboration_blocks() -> None:
    def row(scale_x: float, scale_y: float) -> dict:
        paths = "".join(
            f'<path d="M0 0H1V1H0Z" transform="matrix({scale_x} 0 0 {scale_y} {x} {y})"/>'
            for x, y in ((10, 10), (9.5, 10), (10.5, 10), (10, 9.5), (10, 10.5))
        )
        group = ElementTree.fromstring(
            f'<g xmlns="http://www.w3.org/2000/svg" class="word" '
            f'data-word-key="1:1:1">{paths}</g>'
        )
        return {
            "hq": True,
            "paths": group.findall(f".//{SVG}path"),
            "line": 1,
            "key": "1:1:1",
            "text": "x",
        }

    stretched = row(1.0, 1.09)
    flattened = row(1.0, 1.0)
    for path in flattened["paths"]:
        path.attrib.pop("transform")
    result = visual.vertical_stretch_finding(
        1,
        flattened,
        visual.DEFAULT_POLICY,
        source_record={"transform": [1.0, 0.0, 0.0, 1.09, 0.0, 0.0]},
    )
    assert result is not None
    assert result["severity"] == "review"
    assert result["scale_source"] == "source-record"

    result = visual.vertical_stretch_finding(1, stretched, visual.DEFAULT_POLICY)
    assert result is not None
    assert result["category"] == "hq-vertical-stretch"
    assert result["severity"] == "review"
    assert result["scan_corroborated"] is False
    assert result["vertical_scale_ratio"] == 1.09

    result = visual.vertical_stretch_finding(
        1,
        stretched,
        visual.DEFAULT_POLICY,
        scan_regression=True,
        candidate_score={"f1": 0.7},
        fallback_score={"f1": 0.99},
    )
    assert result is not None
    assert result["severity"] == "blocker"
    assert result["scan_corroborated"] is True
    assert result["candidate_score"] == {"f1": 0.7}

    assert (
        visual.vertical_stretch_finding(1, row(1.09, 1.0), visual.DEFAULT_POLICY)
        is None
    )
    assert (
        visual.vertical_stretch_finding(1, row(1.0, 1.08), visual.DEFAULT_POLICY)
        is None
    )


def test_source_records_are_exact_and_source_bound() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "source-qualified.ndjson"
        row = {
            "page": 1,
            "word_key": "1:1:1",
            "text": "x",
            "transform": [1.0, 0.0, 0.0, -1.09, 10.0, 20.0],
        }
        path.write_text(json.dumps(row) + "\n")
        records = visual.read_source_records(path, {"1:1:1"})
        assert records["1:1:1"]["transform"] == row["transform"]

        digest = visual.sha256(path)
        map_path = root / "hq-map.json"
        map_path.write_text(
            json.dumps({"words": ["1:1:1"], "source_records_sha256": digest})
        )
        keys, expected_digest = visual.read_hq_map(map_path)
        assert keys == {"1:1:1"}
        assert expected_digest == digest

        map_path.write_text(
            json.dumps({"words": ["1:1:1"], "source_records_sha256": "bad"})
        )
        try:
            visual.read_hq_map(map_path)
        except ValueError as error:
            assert "digest differs" in str(error)
        else:
            raise AssertionError("accepted an invalid source-record digest")

        try:
            visual.read_source_records(path, {"1:1:2"})
        except ValueError as error:
            assert "coverage differs" in str(error)
        else:
            raise AssertionError("accepted source records for another HQ map")


def fixture_svg(left_end: float) -> str:
    lines = []
    for number in range(1, 16):
        words = ""
        if number == 1:
            words = (
                '<g class="word" data-word-key="1:1:1" data-rasm-uthmani="a">'
                '<path d="M60 5H80V25H60Z"/></g>'
                '<g class="word" data-word-key="1:1:2" data-rasm-uthmani="b">'
                f'<path d="M40 5H{left_end}V25H40Z"/></g>'
            )
        lines.append(f'<g class="line" data-line="{number}">{words}</g>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 30">'
        + "".join(lines)
        + "</svg>"
    )


def audit_fixture(left_end: float, reference_support: bool | None = None) -> dict:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for name in ("candidate", "base"):
            (root / name / "pages").mkdir(parents=True)
        (root / "index/by-page").mkdir(parents=True)
        (root / "candidate/pages/001.svg").write_text(fixture_svg(left_end))
        (root / "base/pages/001.svg").write_text(fixture_svg(55.0))
        reference_dir = None
        if reference_support is not None:
            reference_dir = root / "reference"
            reference_dir.mkdir()
            reference = np.full((300, 1000), 255, dtype=np.uint8)
            reference[50:250, 400 : round(left_end * 10)] = 0
            reference[50:250, 600:800] = 0
            if not reference_support:
                reference[45:255, 590:620] = 255
            Image.fromarray(reference).save(reference_dir / "page001.png")
        (root / "index/by-page/001.json").write_text(
            json.dumps(
                {
                    "page": 1,
                    "words": [
                        {
                            "word_key": "1:1:1",
                            "line": 1,
                            "box": [60, 5, 80, 25],
                            "rasm_uthmani": "a",
                        },
                        {
                            "word_key": "1:1:2",
                            "line": 1,
                            "box": [40, 5, 55, 25],
                            "rasm_uthmani": "b",
                        },
                    ],
                }
            )
        )
        return visual.audit_page(
            {
                "page": 1,
                "policy": {
                    **visual.DEFAULT_POLICY,
                    "high_width": 1000,
                    "reading_width": 200,
                },
                "candidate_dir": str(root / "candidate"),
                "qvp_dir": None,
                "converter": None,
                "base_dir": str(root / "base"),
                "index_dir": str(root / "index"),
                "reference_dir": str(reference_dir) if reference_dir else None,
                "hq_keys": [],
                "cross_renderer": False,
                "resvg": None,
            }
        )


def test_page_audit_uses_actual_ink_for_adjacent_words() -> None:
    result = audit_fixture(59.8)
    categories = {row["category"] for row in result["findings"]}
    assert result["counters"]["adjacent_pairs"] == 1
    assert "adjacent-new-solid-overlap" not in categories
    assert "reading-size-new-solid-merge" not in categories


def test_page_audit_reports_new_actual_overlap() -> None:
    result = audit_fixture(61.0)
    categories = {row["category"] for row in result["findings"]}
    assert "adjacent-new-solid-overlap" in categories


def test_scan_attested_overlap_is_review_not_blocker() -> None:
    result = audit_fixture(61.0, reference_support=True)
    findings = {row["category"]: row for row in result["findings"]}
    assert findings["adjacent-scan-attested-overlap"]["severity"] == "review"
    assert findings["reading-size-scan-attested-merge"]["severity"] == "review"
    evidence = findings["adjacent-scan-attested-overlap"]["reference_evidence"]
    assert evidence["1000"]["attested"] is True
    assert evidence["200"]["attested"] is True
    assert "adjacent-new-solid-overlap" not in findings
    assert "reading-size-new-solid-merge" not in findings


def test_scan_does_not_excuse_unsupported_overlap() -> None:
    result = audit_fixture(61.0, reference_support=False)
    findings = {row["category"]: row for row in result["findings"]}
    assert findings["adjacent-new-solid-overlap"]["severity"] == "blocker"
    assert findings["reading-size-new-solid-merge"]["severity"] == "blocker"


def test_high_width_attestation_does_not_excuse_reading_merge() -> None:
    original = visual.pair_reference_evidence

    def width_specific(*args, **kwargs):
        reference = args[4]
        return {
            "attested": reference.shape[1] == 1000,
            "quality_acceptable": True,
            "overlap_support_fraction": 1.0,
            "candidate_score": {},
            "fallback_score": {},
        }

    visual.pair_reference_evidence = width_specific
    try:
        result = audit_fixture(61.0, reference_support=True)
    finally:
        visual.pair_reference_evidence = original
    findings = {row["category"]: row for row in result["findings"]}
    assert findings["adjacent-scan-attested-overlap"]["severity"] == "review"
    assert findings["reading-size-new-solid-merge"]["severity"] == "blocker"
    assert "reading-size-scan-attested-merge" not in findings


def main() -> None:
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    main()
