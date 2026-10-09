#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools>=4.60",
#   "skia-pathops>=0.8.0",
# ]
# ///
"""Focused contracts for native KFGQPC page frames."""

import hashlib
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pathops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from add_surah_ornaments import path_data
from assign_words import Page, attach_page_frame, normalize_frame
from audit_export import check_svg
from prepare_page_frames import (
    check_emitted_page_frames,
    frame_path,
    load_manifest,
    prepare_target,
    prepared_tag,
)


def ordinary_source(layer="Ornaments", fill_rule="evenodd", contours=2):
    hole = "M20 20H80V80H20Z" if contours >= 2 else ""
    extra = "M30 30H40V40H30Z" if contours >= 3 else ""
    return f'''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <g data-name="{layer}"><path fill="#bfffbf" fill-rule="{fill_rule}"
        d="M-10 -20H110V120H-10Z{hole}{extra}"/></g>
    </svg>'''


def opening_source(fill_rule="evenodd", contours=3):
    extra = "M10 10H90V30H10Z" if contours >= 2 else ""
    body = "M15 40H85V95H15Z" if contours >= 3 else ""
    fourth = "M1 1H2V2H1Z" if contours >= 4 else ""
    return f'''<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <g data-name="Ornaments"><path fill="#bfffbf" fill-rule="{fill_rule}"
        d="M0 0H100V100H0Z{extra}{body}{fourth}"/></g>
    </svg>'''


def target_svg(view_box="0 0 100 100", root="1 0 0 1 0 0"):
    return f'''<svg viewBox="{view_box}"><g transform="matrix({root})">
      <g id="ayah_markers"></g><g id="content"></g>
    </g></svg>'''


def variant(source, role="odd"):
    _, frame = frame_path(source, role == "opening")
    return {
        "role": role,
        "source_page": 1 if role == "opening" else 3,
        "bytes": 1,
        "crc32": "00000000",
        "sha256": "0" * 64,
        "frame_sha256": hashlib.sha256(path_data(frame).encode()).hexdigest(),
    }



def test_export_audit_requires_one_first_painted_page_frame():
    source = ordinary_source()
    prepared = prepare_target(target_svg(), prepared_tag(source, "fixture", variant(source)))
    emitted = attach_page_frame(prepared)
    assert check_svg(emitted).get("frame", 0) == 0
    assert check_svg(emitted.replace('<g class="page-frame">', "", 1))["frame"] > 0
    reversed_order = emitted.replace(
        '<g class="page-frame">', '<g id="after"></g><g class="page-frame">', 1)
    assert check_svg(reversed_order)["frame"] > 0

def test_manifest_assigns_every_page_to_one_exact_variant():
    _, variants, assignments = load_manifest(ROOT / "conformance/page-frames.json")
    assert len(assignments) == 604
    assert len(variants) == 10
    assert assignments[1] == "opening-1"
    assert assignments[2] == "opening-2"
    assert assignments[3] == "odd-main"
    assert assignments[4] == "even-main"
    assert assignments[603] == "odd-603"


def test_manifest_rejects_another_edition():
    data = json.loads((ROOT / "conformance/page-frames.json").read_text())
    data["edition"] = "hafs-other"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(data))
        try:
            load_manifest(path)
        except ValueError as error:
            assert "must target hafs-kfgqpc" in str(error)
        else:
            raise AssertionError("another edition's frame manifest was accepted")


def test_ordinary_selection_trims_layer_whitespace_and_keeps_source_geometry():
    source = ordinary_source("  Ornaments")
    view_box, frame = frame_path(source, False)
    assert view_box == [0.0, 0.0, 100.0, 100.0]
    assert frame.fillType == pathops.FillType.EVEN_ODD
    assert sum(verb == "moveTo" for verb, _ in frame.segments) == 2
    assert frame.bounds == (-10.0, -20.0, 110.0, 120.0)


def test_opening_selection_requires_three_evenodd_contours():
    _, frame = frame_path(opening_source(), True)
    assert sum(verb == "moveTo" for verb, _ in frame.segments) == 3
    for source, text in (
        (opening_source(fill_rule="nonzero"), "must use even-odd"),
        (opening_source(contours=4), "4 contours, expected 3"),
    ):
        try:
            frame_path(source, True)
        except ValueError as error:
            assert text in str(error)
        else:
            raise AssertionError("invalid opening frame was accepted")


def test_prepared_tag_records_exact_local_bounds_and_is_source_verified():
    source = ordinary_source()
    tag = prepared_tag(source, "fixture", variant(source))
    assert 'data-page-frame="fixture"' in tag
    assert 'data-page-frame-box="-10 -20 110 120"' in tag
    assert 'fill-rule="evenodd"' in tag
    wrong = variant(source)
    wrong["frame_sha256"] = "0" * 64
    try:
        prepared_tag(source, "fixture", wrong)
    except ValueError as error:
        assert "source geometry" in str(error)
    else:
        raise AssertionError("wrong source geometry hash was accepted")


def test_preparation_expands_only_the_visual_viewbox_and_is_idempotent():
    source = ordinary_source()
    tag = prepared_tag(source, "fixture", variant(source))
    once = prepare_target(target_svg(), tag)
    twice = prepare_target(once, tag)
    assert once == twice
    root = ET.fromstring(once)
    assert root.get("viewBox") == "-10 -20 120 140"
    assert root.get("data-content-view-box") == "0 0 100 100"
    assert once.count('data-page-frame="fixture"') == 1
    assert once.index('data-page-frame="fixture"') < once.index('id="ayah_markers"')


def test_offset_preparation_is_idempotent_at_the_persisted_precision():
    source = opening_source()
    tag = prepared_tag(source, "opening", variant(source, "opening"))
    once = prepare_target(
        target_svg("-53.3109 -198.4777 100 100", root="1 0 0 -1 0 100"), tag
    )
    twice = prepare_target(once, tag)
    assert once == twice
    root = ET.fromstring(once)
    assert root.get("data-content-view-box") == "-53.3109 -198.4777 100 100"


def test_sub_thousandth_frame_overshoot_does_not_grow_the_paper():
    tag = (
        '<path data-kind="ornament" data-page-frame="opening" '
        'data-page-frame-box="-0.001 -0.001 100.001 100.001" '
        'fill="#231f20" fill-rule="evenodd" '
        'd="M-0.001 -0.001H100.001V100.001H-0.001Z"/>'
    )
    prepared = prepare_target(target_svg(), tag)
    root = ET.fromstring(prepared)
    assert root.get("viewBox") == "0 0 100 100"
    assert root.get("data-content-view-box") == "0 0 100 100"


def test_page_uses_the_content_viewbox_for_decomposition():
    source = ordinary_source()
    svg = prepare_target(target_svg(), prepared_tag(source, "fixture", variant(source)))
    page = Page("fixture.svg", svg=svg)
    assert page.visual_viewbox == [-10.0, -20.0, 120.0, 140.0]
    assert page.viewbox == [0.0, 0.0, 100.0, 100.0]
    assert page.frame_offset == (0.0, 0.0)


def test_semantic_attachment_preserves_paint_order_and_removes_private_attributes():
    source = ordinary_source()
    prepared = prepare_target(target_svg(), prepared_tag(source, "fixture", variant(source)))
    emitted = attach_page_frame(prepared)
    assert emitted.count('<g class="page-frame">') == 1
    assert "data-page-frame=" not in emitted
    assert "data-page-frame-box=" not in emitted
    assert emitted.index('<g class="page-frame">') < emitted.index('id="ayah_markers"')
    assert attach_page_frame(emitted) == emitted


def test_opening_normalization_moves_visual_and_content_frames_together():
    source = opening_source()
    tag = prepared_tag(source, "opening", variant(source, "opening"))
    prepared = prepare_target(target_svg("-50 -200 100 100", root="1 0 0 -1 0 100"), tag)
    page = Page("001.svg", svg=prepared)
    emitted = normalize_frame(attach_page_frame(prepared), page)
    root = ET.fromstring(emitted)
    assert root.get("data-content-view-box") == "0 0 100 100"
    visual = [float(value) for value in root.get("viewBox").split()]
    assert visual[0] >= 0 and visual[1] >= 0
    assert visual[2:] == page.visual_viewbox[2:]


def test_attachment_rejects_duplicate_prepared_frames():
    source = ordinary_source()
    tag = prepared_tag(source, "fixture", variant(source))
    prepared = prepare_target(target_svg(), tag)
    duplicate = prepared.replace(tag, tag + tag)
    try:
        attach_page_frame(duplicate)
    except ValueError as error:
        assert "2 prepared page frames" in str(error)
    else:
        raise AssertionError("duplicate page frame was accepted")


def test_emitted_preflight_checks_all_pages_and_viewboxes():
    manifest = ROOT / "conformance/page-frames.json"
    with tempfile.TemporaryDirectory() as directory:
        pages = Path(directory) / "pages"
        prepared_root = Path(directory) / "prepared"
        prepared_dir = prepared_root / "mushafs/hafs/kfqc/svg"
        pages.mkdir()
        prepared_dir.mkdir(parents=True)
        _, _, assignments = load_manifest(manifest)
        for page, name in assignments.items():
            private = (
                f'<path data-kind="ornament" data-page-frame="{name}" '
                'data-page-frame-box="0 0 100 100" fill="#231f20" '
                'fill-rule="evenodd" d="M0 0H100V100H0Z"/>'
            )
            prepared = target_svg().replace(
                '<g transform="matrix(1 0 0 1 0 0)">',
                '<g transform="matrix(1 0 0 1 0 0)">' + private,
                1,
            ).replace('<svg ', '<svg data-content-view-box="0 0 100 100" ', 1)
            emitted = attach_page_frame(prepared)
            (prepared_dir / f"{page:03d}.svg").write_text(prepared)
            (pages / f"{page:03d}.svg").write_text(emitted)
        check_emitted_page_frames(pages, prepared_root, manifest)

        broken = pages / "003.svg"
        original = broken.read_text()
        broken.write_text(original.replace('data-content-view-box="0 0 100 100"', ""))
        try:
            check_emitted_page_frames(pages, prepared_root, manifest)
        except ValueError as error:
            assert "content viewBox" in str(error)
        else:
            raise AssertionError("missing content viewBox was accepted")


if __name__ == "__main__":
    tests = sorted((name, fn) for name, fn in globals().items() if name.startswith("test_") and callable(fn))
    for name, test in tests:
        test()
        print("ok ", name)
    print(f"\n{len(tests)} tests passed")
