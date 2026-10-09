#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fonttools>=4.60",
#   "skia-pathops>=0.8.0",
# ]
# ///
"""Focused contracts for native surah cartouches."""

from pathlib import Path
import hashlib
import json
import re
import sys
import tempfile
import zlib

import pathops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from add_surah_ornaments import (  # noqa: E402
    frame_paths, path_data, prepared_page,
)
from assign_words import Page, attach_surah_ornaments, page_elements  # noqa: E402
from audit_export import check_svg  # noqa: E402
from audit_headerbands import group_paths  # noqa: E402
from prepare_surah_ornaments import (  # noqa: E402
    check_emitted_surah_frames, fetch_source, load_manifest, parse_pages,
    source_matches, validate_targets,
)


def source_svg():
    return """<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <g data-name="Ornament"><path fill="#bfffbf" d="M10 10H90V18H10Z"/></g>
      <g data-name="Quran Text">
        <path fill="#ffffff" d="M30 11H70V17H30Z"/>
        <path transform="matrix(1 0 0 -1 10 80)" d="M0 0H80V60H0Z"/>
      </g>
    </svg>"""


def target_svg():
    return """<svg viewBox="0 0 100 100"><g><g id="content">
      <g class="line" data-line="7"><g transform="translate(10 20)">
        <path d="M0 0H80V60H0Z"/>
      </g></g>
    </g></g></svg>"""


def semantic_svg(surah=3, headers=(3,)):
    frame = (
        '<path data-kind="ornament" data-surah-ornament="1" '
        f'data-surah="{surah}" fill="#231f20" d="M0 0H10V10Z"/>'
    )
    groups = "".join(
        '<g class="surah-name" data-sid="%d">'
        '<path data-kind="header_ink" d="M2 2H8V8Z"/></g>' % sid
        for sid in headers
    )
    return '<svg><g id="content">%s%s</g></svg>' % (frame, groups)


def test_frame_selection_subtracts_the_white_centre():
    _, _, frames = frame_paths(source_svg(), 1)
    frame = frames[0]
    assert frame.contains((15, 15))
    assert not frame.contains((50, 14))



def test_path_serialization_limits_moveto_precision():
    path = pathops.Path()
    pen = path.getPen()
    pen.moveTo((1.23456, -2.34567))
    pen.curveTo((3.1234567, 4.7654321), (5.1111114, 6.2222225), (7.3333336, 8.4444444))
    pen.endPath()
    data = path_data(path)
    move, curve = re.match(r"M([^C]+)C(.+)", data).groups()
    move_values = move.split()
    curve_values = curve.split()
    assert move_values == ["1.235", "-2.346"]
    assert all("." not in value or len(value.split(".")[1]) <= 6 for value in curve_values)
    assert any("." in value and len(value.split(".")[1]) == 6 for value in curve_values)

def test_preparation_rejects_headers_out_of_line_order():
    try:
        prepared_page(source_svg(), target_svg(), [(4, 8), (3, 7)])
    except ValueError as error:
        assert "top-to-bottom line order" in str(error)
    else:
        raise AssertionError("out-of-order source ownership was accepted")


def test_preparation_is_idempotent_and_records_ownership():
    once = prepared_page(source_svg(), target_svg(), [(3, 7)])
    twice = prepared_page(source_svg(), once, [(3, 7)])
    assert once == twice
    assert once.count('data-surah-ornament="1"') == 1
    assert once.count('data-surah="3"') == 1
    assert once.count('data-kind="ornament"') == 1
    assert once.index('data-surah-ornament="1"') > once.index('data-line="7"')


def test_preparation_rejects_a_partial_rerun():
    prepared = prepared_page(source_svg(), target_svg(), [(3, 7)])
    try:
        prepared_page(source_svg(), prepared, [(4, 7)])
    except ValueError as error:
        assert "already has surah ornaments for [3], not [4]" in str(error)
    else:
        raise AssertionError("a partial rerun replaced the existing frame set")


def embedded_source(layer="Quran Text"):
    return source_svg().replace(
        '<path fill="#bfffbf" d="M10 10H90V18H10Z"/>',
        '<path fill="#bfffbf" fill-rule="evenodd" '
        'd="M10 10H90V18H10ZM30 11H70V17H30Z"/>',
    ).replace(
        '<path fill="#ffffff" d="M30 11H70V17H30Z"/>', ""
    ).replace('data-name="Quran Text"', f'data-name="{layer}"')


def test_frame_selection_accepts_the_two_page_layer_1_fallback():
    _, matrix, frames = frame_paths(embedded_source("Layer 1"), 1)
    assert matrix == (1.0, 0.0, 0.0, -1.0, 10.0, 80.0)
    assert len(frames) == 1


def test_frame_selection_rejects_ambiguous_layer_1_fallback():
    source = embedded_source("Layer 1").replace(
        "</svg>",
        '<g data-name="Layer 1"><path transform="matrix(1 0 0 -1 10 80)" '
        'd="M0 0H70V50H0Z"/></g></svg>',
    )
    try:
        frame_paths(source, 1)
    except ValueError as error:
        assert "2 Layer 1 candidates" in str(error)
    else:
        raise AssertionError("ambiguous Layer 1 body frame was accepted")


def test_frame_selection_prefers_quran_text_over_layer_1():
    source = embedded_source().replace(
        "</svg>",
        '<g data-name="Layer 1"><path transform="matrix(1 0 0 -1 11 80)" '
        'd="M0 0H80V60H0Z"/></g></svg>',
    )
    _, matrix, _ = frame_paths(source, 1)
    assert matrix == (1.0, 0.0, 0.0, -1.0, 10.0, 80.0)


def test_preparation_accepts_an_embedded_evenodd_opening():
    prepared = prepared_page(embedded_source(), target_svg(), [(3, 7)])
    assert prepared.count('data-surah-ornament="1"') == 1
    assert 'fill-rule="evenodd"' in prepared


def test_preparation_requires_a_transparent_centre():
    source = source_svg().replace('<path fill="#ffffff" d="M30 11H70V17H30Z"/>', "")
    try:
        prepared_page(source, target_svg(), [(3, 7)])
    except ValueError as error:
        assert "no transparent centre" in str(error)
    else:
        raise AssertionError("a solid cartouche was accepted")


def test_preparation_rejects_wrong_line_frame():
    wrong = target_svg().replace('translate(10 20)', 'translate(11 20)')
    try:
        prepared_page(source_svg(), wrong, [(3, 7)])
    except ValueError as error:
        assert "does not match line 7" in str(error)
    else:
        raise AssertionError("wrong line coordinate frame was accepted")


def test_page_elements_bypass_prepared_frame_path():
    prepared = prepared_page(source_svg(), target_svg(), [(3, 7)])
    page = Page("fixture.svg", svg=prepared)
    frame_paths = [i for i, path in enumerate(page.paths) if 'data-surah-ornament="1"' in path["text"]]
    assert len(frame_paths) == 1
    assert frame_paths[0] not in {element["path"] for element in page_elements(page)}


def test_reparenting_uses_explicit_surah_and_preserves_path():
    source = semantic_svg()
    frame = source[source.index('<path'):source.index('/>') + 2]
    attached = attach_surah_ornaments(source)
    assert 'data-surah-ornament' not in attached
    assert 'data-surah="3"' not in attached
    assert attached.count('data-kind="ornament"') == 1
    assert attached.index('data-kind="ornament"') < attached.index('data-kind="header_ink"')
    expected = frame.replace(' data-surah-ornament="1"', "", 1).replace(' data-surah="3"', "", 1)
    assert expected in attached
    assert attach_surah_ornaments(attached) == attached


def test_export_audit_accepts_frame_before_title_and_rejects_reverse_order():
    attached = attach_surah_ornaments(semantic_svg())
    page = attached.replace("<svg>", '<svg viewBox="0 0 345 550">', 1)
    assert check_svg(page).get("headers", 0) == 0
    reverse = page.replace(
        '<path data-kind="ornament" fill="#231f20" d="M0 0H10V10Z"/>'
        '<path data-kind="header_ink" d="M2 2H8V8Z"/>',
        '<path data-kind="header_ink" d="M2 2H8V8Z"/>'
        '<path data-kind="ornament" fill="#231f20" d="M0 0H10V10Z"/>',
    )
    assert check_svg(reverse)["headers"] == 1


def test_header_band_audit_ignores_frame_geometry():
    attached = attach_surah_ornaments(semantic_svg())
    assert group_paths(attached, "surah-name")["3"] == [(2.0, 2.0, 8.0, 8.0)]


def test_reparenting_rejects_existing_non_title_path():
    source = semantic_svg().replace(
        '<path data-kind="header_ink"',
        '<path data-kind="ornament" d="M0 0Z"/><path data-kind="header_ink"',
    )
    try:
        attach_surah_ornaments(source)
    except ValueError as error:
        assert "expected one header_ink" in str(error)
    else:
        raise AssertionError("an already-decorated title group was accepted")


def test_reparenting_rejects_missing_or_duplicate_ownership():
    for source, text in (
        (semantic_svg(headers=(4,)), "surah 3 has 0 emitted title groups"),
        (semantic_svg(headers=(3, 3)), "surah 3 has 2 emitted title groups"),
    ):
        try:
            attach_surah_ornaments(source)
        except ValueError as error:
            assert text in str(error)
        else:
            raise AssertionError("ambiguous frame ownership was accepted")


def test_manifest_covers_every_surah_once():
    source, rows = load_manifest(ROOT / "conformance" / "surah-ornaments.json")
    assert len(rows) == 96
    assert [header["surah"] for row in rows for header in row["headers"]] == list(range(3, 115))
    assert sum(row["bytes"] for row in rows) == 123464215
    assert source["archive_sha256"] == "280c5d71ca16aaeeb3a343be1b92c76fa6df71d0671e202c026fde12402d9eef"


def test_manifest_rejects_another_edition():
    data = json.loads((ROOT / "conformance" / "surah-ornaments.json").read_text())
    data["edition"] = "hafs-other"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "manifest.json"
        path.write_text(json.dumps(data))
        try:
            load_manifest(path)
        except ValueError as error:
            assert "must target hafs-kfgqpc" in str(error)
        else:
            raise AssertionError("a manifest for another edition was accepted")


def test_page_selection_accepts_lists_and_ranges():
    assert parse_pages(None) is None
    assert parse_pages("1-2,50,587-589,604") == {1, 2, 50, 587, 588, 589, 604}
    try:
        parse_pages("604-587")
    except ValueError as error:
        assert "invalid page range" in str(error)
    else:
        raise AssertionError("descending page range was accepted")


def test_target_preflight_requires_line_structure_and_complete_frames():
    row = {
        "page": 50,
        "bytes": 1,
        "crc32": "00000000",
        "sha256": "0" * 64,
        "headers": [{"surah": 3, "line": 7}],
    }
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "mushafs/hafs/kfqc/svg/050.svg"
        target.parent.mkdir(parents=True)
        target.write_text(target_svg())
        validate_targets(directory, [row])
        try:
            validate_targets(directory, [row], require_prepared=True)
        except ValueError as error:
            assert "native surah frames are not prepared" in str(error)
        else:
            raise AssertionError("shipping preflight accepted a frame-free page")
        target.write_text(prepared_page(source_svg(), target.read_text(), [(3, 7)]))
        validate_targets(directory, [row], require_prepared=True)


def test_target_preflight_rejects_a_frame_on_the_wrong_line():
    row = {
        "page": 50,
        "bytes": 1,
        "crc32": "00000000",
        "sha256": "0" * 64,
        "headers": [{"surah": 3, "line": 7}],
    }
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "mushafs/hafs/kfqc/svg/050.svg"
        target.parent.mkdir(parents=True)
        prepared = prepared_page(source_svg(), target_svg(), [(3, 7)])
        prepared = prepared.replace(
            '<g class="line" data-line="7"><g transform="translate(10 20)">',
            '<g class="line" data-line="7"><g transform="translate(10 20)"></g></g>'
            '<g class="line" data-line="8"><g transform="translate(10 20)">',
            1,
        )
        target.write_text(prepared)
        try:
            validate_targets(directory, [row], require_prepared=True)
        except ValueError as error:
            assert "surah 3 frame is not on line 7" in str(error)
        else:
            raise AssertionError("a frame on the wrong line was accepted")


def test_emitted_preflight_requires_every_ordered_frame():
    _, rows = load_manifest(ROOT / "conformance/surah-ornaments.json")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pages = root / "pages"
        prepared = root / "prepared/mushafs/hafs/kfqc/svg"
        pages.mkdir()
        prepared.mkdir(parents=True)
        for row in rows:
            semantic_lines = []
            prepared_lines = []
            for header in row["headers"]:
                semantic_lines.append(
                    '<g class="line" data-line="%d"><g transform="translate(10 20)">'
                    '<g class="surah-name" data-sid="%d">'
                    '<path data-kind="ornament" fill-rule="evenodd" d="M0 0Z"/>'
                    '<path data-kind="header_ink" d="M0 0Z"/></g></g></g>'
                    % (header["line"], header["surah"])
                )
                prepared_lines.append(
                    '<g class="line" data-line="%d"><g transform="translate(10 20)">'
                    '<path data-kind="ornament" data-surah-ornament="1" '
                    'data-surah="%d" fill-rule="evenodd" d="M0 0Z"/></g></g>'
                    % (header["line"], header["surah"])
                )
            (pages / f"{row['page']:03d}.svg").write_text("<svg>" + "".join(semantic_lines) + "</svg>")
            (prepared / f"{row['page']:03d}.svg").write_text("<svg>" + "".join(prepared_lines) + "</svg>")
        check_emitted_surah_frames(pages, root / "prepared")

        # Ordinary source frames can be normalized nonzero paths. The release gate
        # must preserve the source fill form, not force every frame to even-odd.
        ordinary = pages / "050.svg"
        ordinary_prepared = prepared / "050.svg"
        ordinary_svg = ordinary.read_text()
        ordinary_source = ordinary_prepared.read_text()
        ordinary.write_text(ordinary_svg.replace(' fill-rule="evenodd"', "", 1))
        ordinary_prepared.write_text(ordinary_source.replace(' fill-rule="evenodd"', "", 1))
        check_emitted_surah_frames(pages, root / "prepared")
        ordinary.write_text(ordinary_svg)
        ordinary_prepared.write_text(ordinary_source)

        page = pages / "050.svg"
        original = page.read_text()
        page.write_text(original.replace('<path data-kind="ornament" fill-rule="evenodd" d="M0 0Z"/>', ""))
        try:
            check_emitted_surah_frames(pages)
        except ValueError as error:
            assert "emitted surah frames do not match manifest" in str(error)
        else:
            raise AssertionError("semantic output missing a surah frame was accepted")

        page.write_text(original.replace('data-kind="ornament"', 'data-kind="header_ink"', 1))
        try:
            check_emitted_surah_frames(pages, root / "prepared")
        except ValueError as error:
            assert "emitted surah frames do not match manifest" in str(error)
        else:
            raise AssertionError("semantic output with the wrong frame kind was accepted")

        page.write_text(original.replace('data-line="1"', 'data-line="2"', 1))
        try:
            check_emitted_surah_frames(pages, root / "prepared")
        except ValueError as error:
            assert "emitted surah frames do not match manifest" in str(error)
        else:
            raise AssertionError("semantic output on the wrong printed line was accepted")

        page.write_text(original.replace('translate(10 20)', 'translate(11 20)', 1))
        try:
            check_emitted_surah_frames(pages, root / "prepared")
        except ValueError as error:
            assert "changed during emission" in str(error)
        else:
            raise AssertionError("changed semantic frame placement was accepted")


def test_shipping_preflight_rejects_frames_outside_the_manifest():
    from prepare_surah_ornaments import check_prepared_artwork
    _, rows = load_manifest(ROOT / "conformance/surah-ornaments.json")
    with tempfile.TemporaryDirectory() as directory:
        svg_dir = Path(directory) / "mushafs/hafs/kfqc/svg"
        svg_dir.mkdir(parents=True)
        for manifest_row in rows:
            page = svg_dir / f"{manifest_row['page']:03d}.svg"
            headers = manifest_row["headers"]
            body = "".join(
                '<g class="line" data-line="%d"><g transform="translate(10 20)">'
                '<path data-kind="ornament" data-surah-ornament="1" data-surah="%d" '
                'd="M0 0Z"/></g></g>' % (header["line"], header["surah"])
                for header in headers
            )
            page.write_text(f"<svg>{body}</svg>")
        extra = svg_dir / "049.svg"
        extra.write_text(
            '<svg><path data-kind="ornament" data-surah-ornament="1" '
            'data-surah="2" d="M0 0Z"/></svg>'
        )
        try:
            check_prepared_artwork(directory, ROOT / "conformance/surah-ornaments.json")
        except ValueError as error:
            assert "outside the manifest" in str(error)
            assert "049.svg" in str(error)
        else:
            raise AssertionError("an out-of-manifest frame was accepted")


def test_source_cache_is_verified_before_reuse():
    payload = b"official cartouche fixture"
    row = {
        "page": 50,
        "bytes": len(payload),
        "crc32": f"{zlib.crc32(payload) & 0xffffffff:08x}",
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "050___Hafs39__DM.ai"
        path.write_bytes(payload)
        assert source_matches(path, row)
        path.write_bytes(payload + b"!")
        assert not source_matches(path, row)
        try:
            fetch_source({"filename": "{page:03d}___Hafs39__DM.ai", "base_url": "https://invalid/"},
                         row, directory, offline=True)
        except ValueError as error:
            assert "missing or corrupt" in str(error)
        else:
            raise AssertionError("corrupt cached source was accepted offline")


if __name__ == "__main__":
    tests = sorted((name, fn) for name, fn in globals().items() if name.startswith("test_") and callable(fn))
    for name, test in tests:
        test()
        print("ok ", name)
    print(f"\n{len(tests)} tests passed")
