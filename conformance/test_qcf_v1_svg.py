#!/usr/bin/env python
"""Focused contracts for the QCF V1 body-vector stage."""

import argparse
import hashlib
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_qcf_v1_svg as qcf

SOURCE_MANIFEST = json.loads((ROOT / "conformance/qcf-v1-source.json").read_text())
SURAH_CODEPOINTS = SOURCE_MANIFEST["header_assets"]["surah_name"]["codepoints"]


class FakeSurahMetadata:
    chapters_sha256 = "chapters"
    names_sha256 = "names"

    def for_surah(self, surah):
        return {
            "arabic": f"سورة {surah}",
            "latin": f"Surah {surah}",
            "english": f"Meaning {surah}",
            "revelation_place": "makkah",
            "ayah_count": surah + 1,
        }


class FakeWaqfSourceGlyphs:
    sha256 = "waqf"

    def __init__(self, *_):
        pass

    def classify_page(self, _):
        return {}, qcf.Counter()

    def summary(self, _):
        return {
            "qualification": "source-glyph-qualified",
            "text_signs": 0,
            "separate_source_glyphs": 0,
            "fused_source_glyphs": 0,
            "text_signs_by_mark": {},
            "separate_source_glyphs_by_mark": {},
            "fused_source_glyphs_by_mark": {},
        }

    def verify_complete(self, *_):
        pass


class FakeDivisionSajdahSemantics:
    COUNT_FIELDS = qcf.DivisionSajdahSemantics.COUNT_FIELDS
    sha256 = "semantics"

    def __init__(self, *_):
        pass

    def page(self, _page):
        return {
            "boundaries": {},
            "counts": {},
            "divisions": {},
            "restored_glyphs": [],
            "sajdah_after": {},
            "sajdah_at_line_start": {},
            "skips": set(),
        }

    def verify_complete(self, *_):
        pass


class FakeHeaderAssets:
    summary_sha256 = "summary"
    files_sha256 = "files"

    def asset_for(self, line):
        if line["type"] == "surah_name":
            return {
                "kind": "surah-name",
                "surah": line["surah"],
                "codepoint": SURAH_CODEPOINTS[line["surah"] - 1],
                "path": f"surah/{line['surah']:03}.svg",
                "box": [67, -490, 8183, 490],
                "units_per_em": 2500,
                "d": "M67 -490L8183 -490L8183 490Z",
            }
        return {
            "kind": "basmalah",
            "codepoint": "U+F8DD",
            "path": "basmalah.svg",
            "box": [443, -1059, 15701, 2479],
            "units_per_em": 2500,
            "d": "M443 -1059L15701 -1059L15701 2479Z",
        }


class FakeFont:
    units_per_em = 1000

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def outline(self, codepoint):
        assert codepoint in {0xFB51, 0xFB52, 0xFB53}
        return "M0 0L100 0L100 200Z", (0, 0, 100, 200)

    def body_bounds(
        self,
        codepoint,
        painted,
        source_box_width,
        em_pixels,
        maximum_rsb_em,
        minimum_advance_advantage_em,
    ):
        assert source_box_width > 0
        assert em_pixels > 0
        assert maximum_rsb_em == -0.25
        assert minimum_advance_advantage_em == 0.125
        return painted

    def ink_outline(self, codepoint):
        return self.outline(codepoint)

    def body_ink_outline(
        self,
        codepoint,
        source_box_width,
        em_pixels,
        minimum_advantage_em,
        source_width_ratio,
    ):
        assert source_box_width > 0
        assert em_pixels > 0
        assert minimum_advantage_em == 1.75
        assert source_width_ratio == (0.95, 1.05)
        path, bounds = self.outline(codepoint)
        return path, bounds, False


def manifest() -> dict:
    return {
        "schema": "quran-svg-elements/qcf-v1-vector-source",
        "schema_version": 1,
        "edition": "hafs-qcf-v1",
        "print_year_hijri": 1405,
        "inputs": {
            "header_asset_summary_sha256": "summary",
            "header_asset_files_sha256": "files",
            "chapters_metadata_sha256": "chapters",
            "surah_names_sha256": "names",
            "page_font_tree_sha256": "a" * 64,
            "waqf_source_glyphs_sha256": "b" * 64,
            "division_sajdah_source_sha256": "c" * 64,
        },
        "output": {
            "source_width": 1920,
            "source_height": 3106,
            "page_width": 345,
            "em_pixels": 121,
            "page_em_pixels": {"270": 113.25},
            "body_advance_maximum_rsb_em": -0.25,
            "body_advance_minimum_advantage_em": 0.125,
            "body_advance_blend": 0.5,
            "body_visible_ink_minimum_advantage_em": 1.75,
            "body_visible_ink_source_width_ratio": [0.95, 1.05],
            "path_kind": "other",
        },
        "waqf": {
            "source": "canonical rasm sign plus pinned final source-glyph ownership",
            "qualification": "source-glyph-qualified",
            "path_kind": "mark",
            "mark_family": "waqf",
            "text_signs": 0,
            "separate_source_glyphs": 0,
            "fused_source_glyphs": 0,
        },
        "header_placement": {
            "source": "1405h-scan-calibrated-complete-v4-assets",
            "qualification": "mechanically-qualified",
            "path_kind": "header_ink",
            "line_grid": {
                "first_line_center": 126.42083333333333,
                "line_step": 200.91607142857143,
            },
            "center_x": 956,
            "surah_name": {"target_width": 1630, "center_y_offset": 10},
            "basmalah": {"target_width": 750, "center_y_offset": 10},
            "evidence": {
                "reference_scan_tree_sha256": "a" * 64,
                "comparison_report_sha256": "b" * 64,
                "mechanical_audit_report_sha256": "1" * 64,
                "clearance_search_sha256": "c" * 64,
                "comparison_pages_sha256": "d" * 64,
                "audited_pages_sha256": "e" * 64,
                "qualified_pages_sha256": "f" * 64,
                "qualified_index_sha256": "0" * 64,
                "header_pages": 116,
                "header_instances": 226,
                "body_overlap_pages": 0,
                "body_overlap_pixels": 0,
                "mean_precision_10px": 0.80,
                "mean_recall_10px": 0.59,
                "mean_distance": 7.4,
                "rejected_body_overlap_pages": 73,
                "rejected_body_overlap_pixels": 17847,
                "rejected_mean_precision_10px": 0.71,
                "rejected_mean_recall_10px": 0.55,
                "rejected_mean_distance": 11.2,
            },
        },
        "deferred": [],
    }


def glyph(codepoint, box):
    return {
        "text": chr(codepoint),
        "codepoint": f"U+{codepoint:04X}",
        "box": box,
    }


def word(key, line, codepoint, box):
    ayah = key.rsplit(":", 1)[0]
    return {
        "word_key": key,
        "ayah_key": ayah,
        "line": line,
        "box": box,
        "text": {
            "rasm_uthmani": f"uthmani-{key}",
            "rasm_imlai": f"imlai-{key}",
            "qpc": f"qpc-{key}",
            "rasm": f"rasm-{key}",
            "search": f"search-{key}",
        },
        "glyphs": [glyph(codepoint, box)],
    }


def marker(ayah, line, codepoint, box):
    return {
        "ayah_key": ayah,
        "line": line,
        "box": box,
        "glyphs": [glyph(codepoint, box)],
    }


def page(number=3):
    words = [
        word("2:1:1", 1, 0xFB51, [100, 200, 200, 400]),
        word("2:1:2", 1, 0xFB52, [210, 200, 310, 400]),
        word("2:2:1", 2, 0xFB51, [100, 500, 200, 700]),
    ]
    return {
        "schema": "quran-svg-elements/qcf-v1-map-page",
        "schema_version": 3,
        "edition": "hafs-qcf-v1",
        "page": number,
        "page_number_source": {"dataset": "qpc-old", "first_ayah_id": 8},
        "coordinate_space": {
            "width": 1920,
            "height": 3106,
            "origin": "top-left",
            "units": "pixels",
        },
        "lines": [
            {
                "line": 1,
                "type": "ayah",
                "is_centered": False,
                "surah": None,
                "word_keys": ["2:1:1", "2:1:2"],
                "shared_word_keys": [],
                "ayah_keys": ["2:1"],
                "content": [
                    {"kind": "word", "word_key": "2:1:1"},
                    {"kind": "word", "word_key": "2:1:2"},
                    {"kind": "ayah_mark", "ayah_key": "2:1"},
                ],
            },
            {
                "line": 2,
                "type": "ayah",
                "is_centered": False,
                "surah": None,
                "word_keys": ["2:2:1"],
                "shared_word_keys": [],
                "ayah_keys": ["2:2"],
                "content": [
                    {"kind": "word", "word_key": "2:2:1"},
                    {"kind": "ayah_mark", "ayah_key": "2:2"},
                ],
            },
        ],
        "words": words,
        "ayah_markers": [
            marker("2:1", 1, 0xFB53, [320, 200, 420, 400]),
            marker("2:2", 2, 0xFB53, [210, 500, 310, 700]),
        ],
        "shared_groups": [],
    }


def shared_page(number=254):
    value = page(number)
    owner_box = [430, 200, 530, 400]
    keys = ["2:1:3", "2:1:4"]
    canonical_words = []
    for key in keys:
        canonical_words.append(
            {
                "word_key": key,
                "text": {
                    "rasm_uthmani": f"uthmani-{key}",
                    "rasm_imlai": f"imlai-{key}",
                    "qpc": f"qpc-{key}",
                    "rasm": f"rasm-{key}",
                    "search": f"search-{key}",
                },
            }
        )
    group = {
        "id": "2:1:3-4",
        "page": number,
        "line": 1,
        "ayah_key": "2:1",
        "canonical_word_keys": list(keys),
        "canonical_words": canonical_words,
        "box": owner_box,
        "glyphs": [glyph(0xFB52, owner_box)],
        "source_text": chr(0xFB52),
    }
    value["shared_groups"] = [group]
    value["lines"][0]["shared_word_keys"] = list(keys)
    value["lines"][0]["content"].insert(
        -1,
        {
            "kind": "shared_group",
            "id": group["id"],
            "canonical_word_keys": list(keys),
        },
    )
    return value


def header_line(kind="surah_name", surah=2, line_number=3):
    if kind == "surah_name":
        asset = {
            "family": "qpc-v4-surah-header",
            "source_font": "QCF_SurahHeader_COLOR-Regular.ttf",
            "qcf4_layout_font_file_id": 0,
            "qcf4_layout_font_code": surah - 1,
            "codepoint": SURAH_CODEPOINTS[surah - 1],
            "asset_path": f"surah/{surah:03}.svg",
            "qcf4_source_page": surah,
            "qcf4_source_line": 1,
        }
    else:
        asset = {
            "family": "qpc-v4-basmalah",
            "source_font": "QCF4_Hafs_01_W.ttf",
            "font_file_id": 1,
            "source_font_file_id": 1,
            "font_code": 2013,
            "codepoint": "U+F8DD",
            "asset_path": "basmalah.svg",
            "qcf4_source_page": surah,
            "qcf4_source_line": 2,
        }
    return {
        "line": line_number,
        "type": kind,
        "is_centered": True,
        "surah": surah,
        "word_keys": [],
        "shared_word_keys": [],
        "ayah_keys": [],
        "content": [],
        "asset": asset,
    }


def page_with_headers(number=3):
    value = page(number)
    value["lines"].extend(
        [
            header_line("surah_name", 2, 3),
            header_line("basmalah", 2, 4),
        ]
    )
    return value


def write_header_asset(root, record):
    path = root / record["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = record["box"]
    width, height = x1 - x0, y1 - y0
    surah = f' data-surah="{record["surah"]}"' if record["kind"] == "surah-name" else ""
    data = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" data-kind="{record["kind"]}" '
        f'data-codepoint="{record["codepoint"]}" '
        f'data-units-per-em="{record["units_per_em"]}"{surah}>'
        f'<path data-kind="{record["kind"]}" d="M{x0} {y0}L{x1} {y1}Z" '
        f'transform="matrix(1 0 0 -1 {-x0} {y1})"/>'
        "</svg>\n"
    ).encode()
    path.write_bytes(data)
    return record | {"sha256": hashlib.sha256(data).hexdigest()}


def header_asset_fixture(root):
    records = []
    for surah in range(1, 115):
        records.append(
            write_header_asset(
                root,
                {
                    "kind": "surah-name",
                    "surah": surah,
                    "codepoint": SURAH_CODEPOINTS[surah - 1],
                    "path": f"surah/{surah:03}.svg",
                    "box": [67, -490, 8183, 490],
                    "advance": 8256,
                    "units_per_em": 2500,
                },
            )
        )
    records.append(
        write_header_asset(
            root,
            {
                "kind": "basmalah",
                "codepoint": "U+F8DD",
                "path": "basmalah.svg",
                "box": [0, -30, 200, 50],
                "advance": 200,
                "units_per_em": 1000,
            },
        )
    )
    paths = [root / record["path"] for record in records]
    summary = {
        "schema": "quran-svg-elements/qcf-v1-v4-header-assets",
        "schema_version": 1,
        "edition": "hafs-qcf-v1",
        "print_year_hijri": 1405,
        "source_manifest_sha256": "source-manifest",
        "input_digests": {},
        "surah_assets": 114,
        "basmalah_assets": 1,
        "asset_files_sha256": qcf.relative_tree_sha256(root, paths),
        "placement": "deferred",
        "assets": records,
    }
    summary_path = root / "summary.json"
    summary_path.write_text(json.dumps(summary))
    source = manifest()
    source["inputs"].update(
        {
            "map_source_manifest_sha256": "source-manifest",
            "header_asset_summary_sha256": qcf.sha256(summary_path),
            "header_asset_files_sha256": summary["asset_files_sha256"],
        }
    )
    return source


def test_page_spec_is_sorted_unique_and_bounded():
    assert qcf.parse_pages("5,3-4,3,7") == [3, 4, 5, 7]
    for value in ("", "0", "605", "7-3"):
        try:
            qcf.parse_pages(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid page selection {value!r}")


def test_glyph_transform_uses_one_scale_and_translation_only():
    scale, tx, baseline = qcf.glyph_transform(
        [100, 200, 220, 440],
        (0, -200, 1000, 1800),
        2000,
        120,
        345 / 1920,
    )
    assert abs(scale - (120 / 2000) * (345 / 1920)) < 1e-12
    assert abs(tx - (160 - 30) * (345 / 1920)) < 1e-12
    expected_baseline = ((200 + 108) + (440 - 12)) / 2
    assert abs(baseline - expected_baseline * (345 / 1920)) < 1e-12


def test_ink_outline_keeps_an_ordinary_glyph_byte_for_byte():
    font = qcf.PageFont.__new__(qcf.PageFont)
    font.ink_cache = {}
    font.glyph_set = {
        "glyph": type(
            "Glyph",
            (),
            {
                "draw": lambda self, pen: (
                    pen.moveTo((0, 0)),
                    pen.lineTo((100, 0)),
                    pen.lineTo((100, 100)),
                    pen.lineTo((0, 100)),
                    pen.closePath(),
                )
            },
        )()
    }
    font.cmap = {0xFB53: "glyph"}
    expected = ("M0 0H100V100H0Z", (0, 0, 100, 100))
    font.outline = lambda codepoint: expected
    assert font.ink_outline(0xFB53) == expected
    assert font.ink_outline(0xFB53) == expected


def test_ink_outline_removes_zero_area_positioning_contours():
    font = qcf.PageFont.__new__(qcf.PageFont)
    font.ink_cache = {}
    font.glyph_set = {
        "glyph": type(
            "Glyph",
            (),
            {
                "draw": lambda self, pen: (
                    pen.moveTo((0, 0)),
                    pen.lineTo((100, 0)),
                    pen.lineTo((100, 100)),
                    pen.lineTo((0, 100)),
                    pen.closePath(),
                    pen.moveTo((2000, 0)),
                    pen.lineTo((2000, 100)),
                    pen.closePath(),
                )
            },
        )()
    }
    font.cmap = {0xFB53: "glyph"}
    font.outline = lambda codepoint: (
        "M0 0H100V100H0ZM2000 0V100Z",
        (0, 0, 2000, 100),
    )
    expected = ("M0 0H100V100H0Z", (0, 0, 100, 100))
    assert font.ink_outline(0xFB53) == expected
    assert font.ink_outline(0xFB53) == expected


def test_body_ink_outline_requires_strong_source_box_evidence():
    font = qcf.PageFont.__new__(qcf.PageFont)
    font.units_per_em = 1000
    full = ("full", (0, 0, 2000, 1000))
    visible = ("visible", (0, 0, 100, 1000))
    font.outline = lambda codepoint: full
    font.ink_outline = lambda codepoint: visible
    assert font.body_ink_outline(0xFB53, 10, 100, 1.75, (0.95, 1.05)) == (
        "visible",
        visible[1],
        True,
    )
    assert font.body_ink_outline(0xFB53, 10, 100, 2.0, (0.95, 1.05)) == (
        "full",
        full[1],
        False,
    )
    assert font.body_ink_outline(0xFB53, 12, 100, 1.75, (0.95, 1.05)) == (
        "full",
        full[1],
        False,
    )


def test_body_bounds_require_overhang_and_mapped_box_evidence():
    font = object.__new__(qcf.PageFont)
    font.cmap = {0xFB53: "glyph"}
    font.hmtx = {"glyph": (1000, 100)}
    font.units_per_em = 2000
    painted = (100, -200, 1500, 1800)  # RSB = -500 = -0.25 em.
    em_pixels = 120
    # The box agrees 0.125 em (15 px) better with advance than painted.
    assert font.body_bounds(0xFB53, painted, 64.5, em_pixels, -0.25, 0.125) == (
        50,
        -200,
        1250,
        1800,
    )
    # One fraction below the evidence boundary keeps painted-bounds placement.
    assert font.body_bounds(0xFB53, painted, 64.501, em_pixels, -0.25, 0.125) == painted
    # Strong box evidence is insufficient without the quarter-em overhang.
    font.hmtx = {"glyph": (1100, 100)}  # RSB = -400 = -0.20 em.
    assert font.body_bounds(0xFB53, painted, 66, em_pixels, -0.25, 0.125) == painted


def test_body_advance_rule_is_explicit_and_optional_in_path_element():
    class BodyFont(FakeFont):
        units_per_em = 2000

        def outline(self, codepoint):
            assert codepoint == 0xFB53
            return "M100 -200H1500V1800H100Z", (100, -200, 1500, 1800)

        def body_bounds(
            self,
            codepoint,
            painted,
            source_box_width,
            em_pixels,
            maximum_rsb_em,
            minimum_advance_advantage_em,
        ):
            assert codepoint == 0xFB53
            assert painted == (100, -200, 1500, 1800)
            assert source_box_width == 100
            assert em_pixels == 121
            assert maximum_rsb_em == -0.25
            assert minimum_advance_advantage_em == 0.125
            return (50, -200, 1250, 1800)

    page_factor = 345 / 1920
    ordinary = ElementTree.fromstring(
        qcf.path_element(
            glyph(0xFB53, [320, 200, 420, 400]), BodyFont(), 121, page_factor
        )
    )
    advance = ElementTree.fromstring(
        qcf.path_element(
            glyph(0xFB53, [320, 200, 420, 400]),
            BodyFont(),
            121,
            page_factor,
            body_advance_maximum_rsb_em=-0.25,
            body_advance_minimum_advantage_em=0.125,
        )
    )
    ordinary_matrix = [
        float(value)
        for value in ordinary.get("transform")[7:-1].replace(",", " ").split()
    ]
    advance_matrix = [
        float(value)
        for value in advance.get("transform")[7:-1].replace(",", " ").split()
    ]
    full_scale, full_tx, full_baseline = qcf.glyph_transform(
        [320, 200, 420, 400],
        (0, -200, 1000, 1800),
        BodyFont.units_per_em,
        121,
        page_factor,
    )
    assert advance_matrix[:4] == ordinary_matrix[:4]
    assert abs(advance_matrix[5] - ordinary_matrix[5]) < 1e-8
    assert abs(advance_matrix[5] - full_baseline) < 1e-8
    assert abs(advance_matrix[0] - full_scale) < 1e-8
    assert abs(advance_matrix[4] - (ordinary_matrix[4] + full_tx) / 2) < 1e-8
    for maximum, minimum in ((-0.25, None), (None, 0.125)):
        try:
            qcf.path_element(
                glyph(0xFB53, [320, 200, 420, 400]),
                BodyFont(),
                121,
                page_factor,
                body_advance_maximum_rsb_em=maximum,
                body_advance_minimum_advantage_em=minimum,
            )
        except ValueError as error:
            assert "policy is incomplete" in str(error)
        else:
            raise AssertionError("accepted an incomplete body advance-cell policy")


def test_body_visible_ink_rule_is_explicit_and_optional_in_path_element():
    class VisibleInkFont(FakeFont):
        units_per_em = 1000

        def outline(self, codepoint):
            return "full", (0, 0, 2000, 1000)

        def body_ink_outline(
            self,
            codepoint,
            source_box_width,
            em_pixels,
            minimum_advantage_em,
            source_width_ratio,
        ):
            assert codepoint == 0xFB53
            assert source_box_width == 100
            assert em_pixels == 121
            assert minimum_advantage_em == 1.75
            assert source_width_ratio == (0.95, 1.05)
            return "visible", (0, 0, 100, 1000), True

    value = qcf.path_element(
        glyph(0xFB53, [320, 200, 420, 400]),
        VisibleInkFont(),
        121,
        345 / 1920,
        body_visible_ink_minimum_advantage_em=1.75,
        body_visible_ink_source_width_ratio=(0.95, 1.05),
    )
    element = ElementTree.fromstring(value)
    assert element.get("d") == "visible"
    assert element.get("data-source-bounds") == "visible-ink"
    for minimum, ratio in ((1.75, None), (None, (0.95, 1.05))):
        try:
            qcf.path_element(
                glyph(0xFB53, [320, 200, 420, 400]),
                VisibleInkFont(),
                121,
                345 / 1920,
                body_visible_ink_minimum_advantage_em=minimum,
                body_visible_ink_source_width_ratio=ratio,
            )
        except ValueError as error:
            assert "policy is incomplete" in str(error)
        else:
            raise AssertionError("accepted an incomplete body visible-ink policy")


def test_vector_settings_reject_changed_body_advance_policy():
    value = manifest()
    assert qcf.vector_settings(value)[4:] == (-0.25, 0.125)
    cases = {
        "body_advance_maximum_rsb_em": (None, -0.249, -0.251, 0, 1),
        "body_advance_minimum_advantage_em": (None, 0.124, 0.126, 0, 1),
        "body_advance_blend": (None, 0.499, 0.501, 0, 1),
    }
    for field, values in cases.items():
        for threshold in values:
            changed = json.loads(json.dumps(value))
            if threshold is None:
                del changed["output"][field]
            else:
                changed["output"][field] = threshold
            try:
                qcf.vector_settings(changed)
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted changed {field}: {threshold!r}")


def test_vector_settings_reject_changed_body_visible_ink_policy():
    cases = {
        "body_visible_ink_minimum_advantage_em": (None, 1.749, 1.751, 0, 1),
        "body_visible_ink_source_width_ratio": (
            None,
            [0.949, 1.05],
            [0.95, 1.051],
            [0.95],
            "0.95-1.05",
        ),
    }
    for field, values in cases.items():
        for changed_value in values:
            changed = json.loads(json.dumps(manifest()))
            if changed_value is None:
                del changed["output"][field]
            else:
                changed["output"][field] = changed_value
            try:
                qcf.vector_settings(changed)
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted changed {field}: {changed_value!r}")


def test_ayah_marker_uses_ink_bearing_horizontal_bounds():
    class MarkerFont(FakeFont):
        def outline(self, codepoint):
            assert codepoint == 0xFB53
            return "M-200 -100ZM0 0L100 0L100 200Z", (-200, -100, 100, 200)

        def ink_outline(self, codepoint):
            assert codepoint == 0xFB53
            return "M0 0L100 0L100 200Z", (0, 0, 100, 200)

    page_factor = 345 / 1920
    value = qcf.path_element(
        glyph(0xFB53, [320, 200, 420, 400]),
        MarkerFont(),
        121,
        page_factor,
        visible_horizontal=True,
    )
    element = ElementTree.fromstring(value)
    assert "-200" not in element.get("d")
    values = [float(part) for part in element.get("transform")[7:-1].split()]
    scale = (121 / 1000) * page_factor
    expected_tx = (370 - (121 / 1000) * 50) * page_factor
    expected_baseline = ((200 + (121 / 1000) * 200) + (400 - (121 / 1000) * 100)) / 2
    assert abs(values[0] - scale) < 1e-9
    assert abs(values[4] - expected_tx) < 1e-9
    assert abs(values[5] - expected_baseline * page_factor) < 1e-9


def test_fragments_are_counted_across_lines():
    value = page()
    value["words"].append(word("2:1:3", 2, 0xFB52, [320, 500, 420, 700]))
    value["lines"][1]["word_keys"].insert(0, "2:1:3")
    value["lines"][1]["content"].insert(0, {"kind": "word", "word_key": "2:1:3"})
    fragments = qcf.line_fragments(value)
    assert (fragments[1][0]["fragment"], fragments[1][0]["fragments"]) == (1, 2)
    assert (fragments[2][0]["fragment"], fragments[2][0]["fragments"]) == (2, 2)
    assert (fragments[2][1]["fragment"], fragments[2][1]["fragments"]) == (1, 1)


def test_page_accepts_one_declared_shared_unit_and_rejects_corruption():
    shared = shared_page()
    qcf.verify_page(shared)
    words = qcf.logical_words(shared)
    assert [word["word_key"] for word in words] == [
        "2:1:1",
        "2:1:2",
        "2:1:3",
        "2:1:4",
        "2:2:1",
    ]
    assert words[2]["glyphs"] and not words[3]["glyphs"]
    assert words[3]["shared_path_owner"] == "2:1:3"

    broken = shared_page()
    broken["shared_groups"][0]["canonical_word_keys"][1] = "2:1:5"
    broken["shared_groups"][0]["canonical_words"][1]["word_key"] = "2:1:5"
    broken["lines"][0]["shared_word_keys"][1] = "2:1:5"
    broken["lines"][0]["content"][-2]["canonical_word_keys"][1] = "2:1:5"
    try:
        qcf.verify_page(broken)
    except ValueError as error:
        assert "not consecutive" in str(error)
    else:
        raise AssertionError("accepted nonconsecutive shared logical words")

    broken = shared_page()
    broken["shared_groups"][0]["glyphs"] = []
    try:
        qcf.verify_page(broken)
    except ValueError as error:
        assert "no glyphs" in str(error)
    else:
        raise AssertionError("accepted a shared unit without geometry")

    broken = shared_page()
    broken["lines"][0]["shared_word_keys"].pop()
    try:
        qcf.verify_page(broken)
    except ValueError as error:
        assert "shared-word coverage" in str(error)
    else:
        raise AssertionError("accepted incomplete shared-word coverage")


def test_page_distinguishes_deferred_headers_from_corrupt_geometry():
    header = page_with_headers()
    try:
        qcf.verify_page(header)
    except qcf.DeferredPage as error:
        assert "V4 placement asset required" in str(error)
    else:
        raise AssertionError("accepted a header page without its assets")
    qcf.verify_page(header, FakeHeaderAssets())

    broken = page()
    broken["ayah_markers"][0]["glyphs"][0]["box"] = None
    try:
        qcf.verify_page(broken)
    except ValueError as error:
        assert "incomplete geometry" in str(error)
    else:
        raise AssertionError("accepted a marker without geometry")


def test_vector_settings_are_manifest_owned_and_page_wide():
    (
        output,
        default,
        overrides,
        page_width,
        maximum_rsb_em,
        minimum_advance_advantage_em,
    ) = qcf.vector_settings(manifest())
    assert output["path_kind"] == "other"
    assert default == 121
    assert overrides == {270: 113.25}
    assert page_width == 345
    assert maximum_rsb_em == -0.25
    assert minimum_advance_advantage_em == 0.125
    assert output["body_visible_ink_minimum_advantage_em"] == 1.75
    assert output["body_visible_ink_source_width_ratio"] == [0.95, 1.05]
    assert overrides.get(269, default) == 121
    assert overrides.get(270, default) == 113.25
    assert overrides.get(271, default) == 121

    for patch in (
        {"schema": "wrong"},
        {"schema_version": 2},
        {"edition": "wrong"},
        {"print_year_hijri": 1400},
        {"output": manifest()["output"] | {"path_kind": "body"}},
        {"output": manifest()["output"] | {"page_em_pixels": {"0270": 113.25}}},
        {"output": manifest()["output"] | {"page_em_pixels": {"0": 113.25}}},
        {"output": manifest()["output"] | {"page_em_pixels": {"605": 113.25}}},
        {"output": manifest()["output"] | {"page_em_pixels": {"270": 0}}},
    ):
        wrong = manifest() | patch
        try:
            qcf.vector_settings(wrong)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"accepted invalid vector manifest patch {patch}")


def test_header_placement_uses_scan_calibrated_source_geometry():
    settings = qcf.header_settings(manifest())
    assert settings["qualification"] == "mechanically-qualified"
    assets = FakeHeaderAssets()
    for line_number in (1, 8, 15):
        for kind, width, offset in (
            ("surah_name", 1630, 10),
            ("basmalah", 750, 10),
        ):
            line = header_line(kind, 2, line_number)
            asset = assets.asset_for(line)
            box = qcf.header_source_box(line, asset, 1920, 3106, settings)
            centre_y = (
                settings["line_grid"]["first_line_center"]
                + (line_number - 1) * settings["line_grid"]["line_step"]
                + offset
            )
            assert abs(box[2] - box[0] - width) < 1e-9
            assert abs((box[0] + box[2]) / 2 - 956) < 1e-9
            assert abs((box[1] + box[3]) / 2 - centre_y) < 1e-9
            assert box[0] >= 0 and box[1] >= 0
            assert box[2] <= 1920 and box[3] <= 3106
            expected_scale = width / (asset["box"][2] - asset["box"][0])
            assert abs(qcf.header_scale(kind, asset, settings) - expected_scale) < 1e-12

    for patch in (
        {"qualification": "candidate"},
        {"path_kind": "other"},
        {"center_x": 0},
        {"line_grid": {"first_line_center": 0, "line_step": 201}},
        {"surah_name": {"target_width": 0, "center_y_offset": 10}},
        {"basmalah": {"target_width": 750}},
        {
            "evidence": manifest()["header_placement"]["evidence"]
            | {"body_overlap_pages": 1}
        },
        {
            "evidence": manifest()["header_placement"]["evidence"]
            | {"header_pages": 115}
        },
        {
            "evidence": manifest()["header_placement"]["evidence"]
            | {"mean_precision_10px": 0.70}
        },
    ):
        source = manifest()
        source["header_placement"] |= patch
        try:
            qcf.header_settings(source)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid header placement patch {patch}")


def test_surah_metadata_is_complete_and_pinned():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        names = root / "surah_names.tsv"
        names.write_text(
            "".join(
                f"{surah}\tcode_{surah}\tسورة {surah}\tSurah {surah}\n"
                for surah in range(1, 115)
            )
        )
        chapters = root / "chapters.json"
        chapters.write_text(
            json.dumps(
                {
                    "chapters": [
                        {
                            "id": surah,
                            "name_arabic": f"سورة {surah}",
                            "translated_name": {"name": f"Meaning {surah}"},
                            "revelation_place": "makkah",
                            "verses_count": surah + 1,
                        }
                        for surah in range(1, 115)
                    ]
                }
            )
        )
        source = manifest()
        source["inputs"].update(
            {
                "chapters_metadata_sha256": qcf.sha256(chapters),
                "surah_names_sha256": qcf.sha256(names),
            }
        )
        metadata = qcf.SurahMetadata(chapters, names, source)
        assert metadata.for_surah(1) == {
            "arabic": "سورة 1",
            "latin": "Surah 1",
            "english": "Meaning 1",
            "revelation_place": "makkah",
            "ayah_count": 2,
        }
        assert metadata.for_surah(114)["ayah_count"] == 115

        names.write_text(names.read_text().replace("Surah 1", "Changed", 1))
        try:
            qcf.SurahMetadata(chapters, names, source)
        except ValueError as error:
            assert "digest mismatch" in str(error)
        else:
            raise AssertionError("accepted changed surah metadata")


def test_audited_header_svg_normalizes_semantics_and_qualification_only():
    source = (
        b'<g data-placement-qualification="mechanically-qualified" '
        b'data-target-width="1630"><path data-kind="mark" '
        b'data-mark="waqf_jaiz_wasl_awla" data-mark-family="waqf" d="M0 0"/></g>'
    )
    assert qcf.qualified_geometry_svg(source) == source.replace(
        b'data-kind="mark" data-mark="waqf_jaiz_wasl_awla" data-mark-family="waqf"',
        b'data-kind="other"',
    )
    assert qcf.audited_header_svg(source) == (
        b'<g data-placement-qualification="candidate" '
        b'data-target-width="1630"><path data-kind="other" d="M0 0"/></g>'
    )


def test_path_geometry_contract_allows_only_explicit_insertions():
    base = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/><path d="M1 1" transform="matrix(1 0 0 1 0 0)"/></svg>'
    emitted = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/><path data-kind="mark" d="M0.5 0.5"/><path d="M1 1" transform="matrix(1 0 0 1 0 0)"/></svg>'
    base_records = qcf.path_geometry_records(base)
    emitted_records = qcf.path_geometry_records(emitted)
    assert qcf.inserted_path_geometry(base_records, emitted_records) == [
        ("M0.5 0.5", "", "", "")
    ]
    assert (
        qcf.path_geometry_bytes(base_records)
        == b'[["M0 0","","",""],["M1 1","matrix(1 0 0 1 0 0)","",""]]\n'
    )
    try:
        qcf.inserted_path_geometry(
            base_records,
            qcf.path_geometry_records(
                b'<svg xmlns="http://www.w3.org/2000/svg"><path d="changed"/><path d="M1 1" transform="matrix(1 0 0 1 0 0)"/></svg>'
            ),
        )
    except ValueError as error:
        assert "changed path geometry or order" in str(error)
    else:
        raise AssertionError("accepted changed path geometry")


def test_header_qualification_locks_the_complete_output_digest():
    settings = qcf.header_settings(manifest())
    pages = [{"page": page} for page in range(1, 605)]
    evidence = settings["evidence"]
    qcf.verify_header_qualification_output(
        settings,
        pages,
        evidence["qualified_pages_sha256"],
        evidence["audited_pages_sha256"],
        evidence["qualified_index_sha256"],
    )
    for pages_sha256, audited_pages_sha256, index_sha256 in (
        (
            "1" * 64,
            evidence["audited_pages_sha256"],
            evidence["qualified_index_sha256"],
        ),
        (
            evidence["qualified_pages_sha256"],
            "1" * 64,
            evidence["qualified_index_sha256"],
        ),
        (
            evidence["qualified_pages_sha256"],
            evidence["audited_pages_sha256"],
            "1" * 64,
        ),
    ):
        try:
            qcf.verify_header_qualification_output(
                settings,
                pages,
                pages_sha256,
                audited_pages_sha256,
                index_sha256,
            )
        except ValueError as error:
            assert "header" in str(error)
        else:
            raise AssertionError("accepted a changed qualified-header corpus")
    qcf.verify_header_qualification_output(
        settings, pages[:1], "1" * 64, "1" * 64, "1" * 64
    )


def test_header_assets_verify_the_complete_pinned_corpus():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = header_asset_fixture(root)
        assets = qcf.HeaderAssets(root, source)
        assert (
            assets.asset_for(header_line("surah_name", 114, 10))["codepoint"]
            == SURAH_CODEPOINTS[113]
        )
        assert (
            assets.asset_for(header_line("basmalah", 114, 11))["codepoint"] == "U+F8DD"
        )

        (root / "surah/001.svg").write_text("changed")
        try:
            qcf.HeaderAssets(root, source)
        except ValueError as error:
            assert "files digest differs" in str(error)
        else:
            raise AssertionError("accepted a changed V4 header asset")


def test_page_emits_native_v4_header_decorations():
    value = page_with_headers()
    settings = qcf.header_settings(manifest())
    svg, _ = qcf.build_page(
        value,
        FakeFont(),
        121,
        345,
        -0.25,
        0.125,
        FakeHeaderAssets(),
        settings,
        FakeSurahMetadata(),
    )
    root = ElementTree.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    lines = root.findall("svg:g", namespace)
    surah = lines[2].find("svg:g[@class='surah-name']", namespace)
    basmalah = lines[3].find("svg:g[@class='basmalah']", namespace)
    assert surah.attrib["data-sid"] == basmalah.attrib["data-sid"] == "2"
    assert surah.attrib["data-source"] == basmalah.attrib["data-source"] == "qpc-v4"
    assert surah.attrib["data-codepoint"] == SURAH_CODEPOINTS[1]
    assert basmalah.attrib["data-codepoint"] == "U+F8DD"
    for group in (surah, basmalah):
        assert group.attrib["data-surah-name-ar"] == "سورة 2"
        assert group.attrib["data-surah-name-latin"] == "Surah 2"
        assert group.attrib["data-surah-name-en"] == "Meaning 2"
        assert group.attrib["data-revelation-place"] == "makkah"
        assert group.attrib["data-ayah-count"] == "3"
    for group in (surah, basmalah):
        path = group.find("svg:path", namespace)
        assert path.attrib["data-kind"] == "header_ink"
        assert path.attrib["transform"].startswith("matrix(")
        assert group.attrib["data-placement-qualification"] == "mechanically-qualified"


def test_manifest_owns_page_coordinates():
    qcf.verify_coordinate_space(page(), manifest()["output"])
    wrong = page()
    wrong["coordinate_space"]["width"] = 1919
    try:
        qcf.verify_coordinate_space(wrong, manifest()["output"])
    except ValueError as error:
        assert "coordinate space changed" in str(error)
    else:
        raise AssertionError("accepted another coordinate space")


def test_supported_selection_records_only_known_deferrals():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        pages = root / "pages"
        pages.mkdir()
        for number in range(1, 605):
            value = shared_page(number) if number == 254 else page(number)
            if number == 1:
                value["lines"].append(header_line("surah_name", 1, 3))
            (pages / f"{number:03}.json").write_text(json.dumps(value))

        selected, rejected = qcf.select_pages(root, "supported")
        assert len(selected) == 603
        assert [item["page"] for item in rejected] == [1]
        selected, rejected = qcf.select_pages(root, "supported", FakeHeaderAssets())
        assert len(selected) == 604
        assert rejected == []
        selected, rejected = qcf.select_pages(root, "254")
        assert [item["page"] for item in selected] == [254]
        assert rejected == []
        try:
            qcf.select_pages(root, "1")
        except qcf.DeferredPage:
            pass
        else:
            raise AssertionError("explicit selection silently skipped a deferred page")


def test_page_rejects_changed_line_content_order():
    value = page()
    value["lines"][0]["content"][0], value["lines"][0]["content"][1] = (
        value["lines"][0]["content"][1],
        value["lines"][0]["content"][0],
    )
    try:
        qcf.verify_page(value)
    except ValueError as error:
        assert "word order differs" in str(error)
    else:
        raise AssertionError("accepted reordered line content")

    value = page()
    value["lines"][0]["content"] = [
        value["lines"][0]["content"][-1],
        *value["lines"][0]["content"][:-1],
    ]
    try:
        qcf.verify_page(value)
    except ValueError as error:
        assert "content order differs" in str(error)
    else:
        raise AssertionError("accepted a marker before its ayah words")

    value = page()
    value["page_number_source"]["dataset"] = "current-index"
    try:
        qcf.verify_page(value)
    except ValueError as error:
        assert "page-number source" in str(error)
    else:
        raise AssertionError("accepted another page-number source")


def test_shared_unit_emits_two_words_and_one_path_range():
    svg, index = qcf.build_page(shared_page(), FakeFont(), 121, 345, -0.25, 0.125)
    root = ElementTree.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    words = root.findall(".//svg:g[@class='word']", namespace)
    by_key = {item.attrib["data-word-key"]: item for item in words}
    owner = by_key["2:1:3"]
    alias = by_key["2:1:4"]
    assert len(owner.findall("svg:path", namespace)) == 1
    assert alias.findall("svg:path", namespace) == []
    assert alias.attrib["data-shared-paths-with"] == "2:1:3"
    assert "data-shared-paths-with" not in owner.attrib

    payload = json.loads(index)
    assert payload["count"] == 5
    records = {item["word_key"]: item for item in payload["words"]}
    assert records["2:1:3"]["box"] == records["2:1:4"]["box"]
    assert records["2:1:3"]["rasm_uthmani"] == "uthmani-2:1:3"
    assert records["2:1:4"]["rasm_uthmani"] == "uthmani-2:1:4"
    assert sum(1 for _ in qcf.page_glyphs(shared_page())) == 6


def test_page_emits_tagged_svg_and_sidecar():
    svg, index = qcf.build_page(page(), FakeFont(), 121, 345, -0.25, 0.125)
    root = ElementTree.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    lines = root.findall("svg:g", namespace)
    assert len(lines) == 2
    assert lines[0].attrib == {"class": "line", "data-line": "1"}
    fragments = lines[0].findall("svg:g[@class='ayah-fragment']", namespace)
    assert fragments[0].attrib["data-ayah-key"] == "2:1"
    words = fragments[0].findall("svg:g[@class='word']", namespace)
    assert [item.attrib["data-word-key"] for item in words] == ["2:1:1", "2:1:2"]
    path = words[0].find("svg:path", namespace)
    assert path.attrib["data-kind"] == "other"
    assert path.attrib["d"] == "M0 0L100 0L100 200Z"
    assert path.attrib["transform"].startswith("matrix(")
    marker_group = lines[0].find("svg:g[@class='ayah-mark']", namespace)
    assert marker_group.attrib["id"] == "ayah-mark-2-1"

    payload = json.loads(index)
    assert payload["edition"] == "hafs-qcf-v1"
    assert payload["count"] == 3
    assert payload["page_number_source"] == {
        "dataset": "qpc-old",
        "first_ayah_id": 8,
    }
    assert payload["words"][0]["qpc"] == "qpc-2:1:1"


def page_with_division_and_sajdah(split_ayah=False):
    value = page()
    division_glyph = glyph(0xFB51, [60, 220, 90, 320])
    body_glyph = glyph(0xFB52, [100, 200, 200, 400])
    value["words"][0]["glyphs"] = [division_glyph, body_glyph]
    value["words"][0]["box"] = [60, 200, 200, 400]
    sajdah_glyph = glyph(0xFB51, [315, 220, 345, 320])
    value["words"][1]["glyphs"].append(sajdah_glyph)
    value["words"][1]["box"] = [210, 200, 345, 400]
    value["words"][1]["text"]["rasm_uthmani"] += "۩"

    sajdah_line = 1
    if split_ayah:
        sajdah_line = 2
        value["words"][1]["line"] = 2
        value["lines"][0]["word_keys"] = ["2:1:1"]
        value["lines"][0]["content"] = [{"kind": "word", "word_key": "2:1:1"}]
        value["lines"][1]["word_keys"].insert(0, "2:1:2")
        value["lines"][1]["ayah_keys"] = ["2:1", "2:2"]
        value["lines"][1]["content"] = [
            {"kind": "word", "word_key": "2:1:2"},
            {"kind": "ayah_mark", "ayah_key": "2:1"},
            *value["lines"][1]["content"],
        ]
        value["ayah_markers"][0]["line"] = 2

    division = {
        "ayah_key": "2:1",
        "line": 1,
        "page": 3,
        "rubu_al_hizb": 1,
        "source_glyph": division_glyph,
        "word_key": "2:1:1",
    }
    sajdah = {
        "anchor_line": sajdah_line,
        "ayah_key": "2:1",
        "line": sajdah_line,
        "page": 3,
        "source": "mapped-word",
        "source_glyph": sajdah_glyph,
        "word_key": "2:1:2",
    }
    return value, {
        "boundaries": {"2:1": division},
        "divisions": {"2:1": division},
        "restored_glyphs": [],
        "sajdah_after": {"2:1": [sajdah]},
        "sajdah_at_line_start": {},
        "skips": {("2:1:1", 0), ("2:1:2", 1)},
    }


def test_page_emits_division_and_sajdah_without_changing_path_geometry():
    value, semantics = page_with_division_and_sajdah()
    ordinary, ordinary_index = qcf.build_page(value, FakeFont(), 121, 345, -0.25, 0.125)
    semantic, semantic_index = qcf.build_page(
        value, FakeFont(), 121, 345, -0.25, 0.125, semantics=semantics
    )
    assert ordinary_index == semantic_index
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    ordinary_root = ElementTree.fromstring(ordinary)
    semantic_root = ElementTree.fromstring(semantic)
    ordinary_paths = [
        (path.attrib["d"], path.attrib["transform"])
        for path in ordinary_root.findall(".//svg:path", namespace)
    ]
    semantic_paths = [
        (path.attrib["d"], path.attrib["transform"])
        for path in semantic_root.findall(".//svg:path", namespace)
    ]
    assert semantic_paths == ordinary_paths

    line = semantic_root.findall("svg:g", namespace)[0]
    assert [child.attrib.get("class") for child in line] == [
        "division-mark",
        "ayah-fragment",
        "sajdah-mark",
        "ayah-mark",
    ]
    fragment = line[1]
    assert fragment.attrib["data-juz-start"] == "1"
    assert fragment.attrib["data-hizb-start"] == "1"
    assert fragment.attrib["data-rubu-al-hizb-start"] == "1"
    assert line[0].attrib["data-word-key"] == "2:1:1"
    assert line[2].attrib["data-word-key"] == "2:1:2"
    assert line[2].attrib["data-source"] == "mapped-word"
    division_path = line[0].find("svg:path", namespace)
    assert division_path.attrib == {
        "data-kind": "mark",
        "data-mark": "hizb",
        "data-standalone": "1",
        "data-ayah-key": "2:1",
        "d": "M0 0L100 0L100 200Z",
        "transform": division_path.attrib["transform"],
    }
    sajdah_path = line[2].find("svg:path", namespace)
    assert sajdah_path.attrib["data-kind"] == "mark"
    assert sajdah_path.attrib["data-mark"] == "sajdah_mark"
    assert sajdah_path.attrib["data-mark-family"] == "sajdah"
    assert sajdah_path.attrib["data-standalone"] == "1"
    words = fragment.findall("svg:g", namespace)
    assert [len(word.findall("svg:path", namespace)) for word in words] == [1, 1]


def test_semantic_groups_emit_once_when_ayah_spans_lines():
    value, semantics = page_with_division_and_sajdah(split_ayah=True)
    semantic, _ = qcf.build_page(
        value, FakeFont(), 121, 345, -0.25, 0.125, semantics=semantics
    )
    root = ElementTree.fromstring(semantic)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    lines = root.findall("svg:g", namespace)
    assert len(root.findall(".//svg:g[@class='division-mark']", namespace)) == 1
    assert len(root.findall(".//svg:g[@class='sajdah-mark']", namespace)) == 1
    assert [child.attrib.get("class") for child in lines[0]] == [
        "division-mark",
        "ayah-fragment",
    ]
    assert [child.attrib.get("class") for child in lines[1]] == [
        "ayah-fragment",
        "sajdah-mark",
        "ayah-mark",
        "ayah-fragment",
        "ayah-mark",
    ]
    first = lines[0].find("svg:g[@class='ayah-fragment']", namespace)
    second = lines[1].find("svg:g[@class='ayah-fragment']", namespace)
    assert first.attrib["data-rubu-al-hizb-start"] == "1"
    assert "data-rubu-al-hizb-start" not in second.attrib


def test_marker_can_lead_a_line_without_same_ayah_words():
    value = page()
    value["ayah_markers"][0]["line"] = 2
    value["lines"][0]["content"] = value["lines"][0]["content"][:-1]
    value["lines"][1]["ayah_keys"] = ["2:1", "2:2"]
    value["lines"][1]["content"].insert(0, {"kind": "ayah_mark", "ayah_key": "2:1"})

    svg, _ = qcf.build_page(value, FakeFont(), 121, 345, -0.25, 0.125)
    root = ElementTree.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    lines = root.findall("svg:g", namespace)
    children = [child.attrib.get("class") for child in lines[1]]
    assert children == ["ayah-mark", "ayah-fragment", "ayah-mark"]
    assert lines[1][0].attrib["data-ayah-key"] == "2:1"


def test_source_verification_hashes_actual_page_files():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        map_dir = root / "map"
        pages = map_dir / "pages"
        fonts = root / "fonts"
        pages.mkdir(parents=True)
        fonts.mkdir()
        for number in range(1, 605):
            (pages / f"{number:03}.json").write_text(f"{number}\n")
            (fonts / f"QCF_P{number:03}.TTF").write_bytes(f"font-{number}\n".encode())
        page_files = sorted(pages.glob("*.json"))
        font_files = sorted(fonts.glob("*.TTF"))
        source = manifest()
        source["inputs"] = {
            "map_page_files_sha256": qcf.tree_sha256(page_files),
            "map_source_manifest_sha256": "source-manifest",
            "page_font_tree_sha256": qcf.tree_sha256(font_files),
        }
        (map_dir / "summary.json").write_text(
            json.dumps(
                {
                    "schema": "quran-svg-elements/qcf-v1-map",
                    "schema_version": 3,
                    "edition": "hafs-qcf-v1",
                    "page_files_sha256": source["inputs"]["map_page_files_sha256"],
                    "source_manifest_sha256": "source-manifest",
                }
            )
        )

        qcf.verify_sources(map_dir, fonts, source)
        (pages / "003.json").write_text("changed\n")
        try:
            qcf.verify_sources(map_dir, fonts, source)
        except ValueError as error:
            assert "summary does not match its page files" in str(error)
        else:
            raise AssertionError("trusted a stale map summary")


def test_build_uses_manifest_settings_and_publishes_once():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "manifest.json"
        source.write_text(json.dumps(manifest()))
        output = root / "output"
        args = argparse.Namespace(
            manifest=source,
            map_dir=root / "map",
            fonts_dir=root / "fonts",
            out_dir=output,
            header_assets_dir=root / "headers",
            chapters_metadata=root / "chapters.json",
            surah_names=root / "surah_names.tsv",
            waqf_source_glyphs=root / "waqf.json",
            division_sajdah_source=root / "semantics.json",
            pages="supported",
        )
        original_font = qcf.PageFont
        original_sources = qcf.verify_sources
        original_pages = qcf.select_pages
        original_headers = qcf.HeaderAssets
        original_metadata = qcf.SurahMetadata
        original_waqf = qcf.WaqfSourceGlyphs
        original_semantics = qcf.DivisionSajdahSemantics
        try:
            qcf.PageFont = lambda _: FakeFont()
            qcf.HeaderAssets = lambda *_: FakeHeaderAssets()
            qcf.SurahMetadata = lambda *_: FakeSurahMetadata()
            qcf.WaqfSourceGlyphs = FakeWaqfSourceGlyphs
            qcf.DivisionSajdahSemantics = FakeDivisionSajdahSemantics
            qcf.verify_sources = lambda *_: None
            qcf.select_pages = lambda *_: (
                [page(270)],
                [{"page": 1, "reason": "header"}],
            )
            with redirect_stdout(StringIO()):
                qcf.build(args)
            summary = json.loads((output / "summary.json").read_text())
            assert summary["em_pixels"] == 121
            assert summary["page_em_pixels"] == {"270": 113.25}
            assert summary["body_advance_maximum_rsb_em"] == -0.25
            assert summary["body_advance_minimum_advantage_em"] == 0.125
            assert summary["body_advance_blend"] == 0.5
            assert summary["body_visible_ink_minimum_advantage_em"] == 1.75
            assert summary["body_visible_ink_source_width_ratio"] == [0.95, 1.05]
            assert summary["counts"]["body_visible_ink_paths"] == 0
            assert summary["page_width"] == 345
            svg_root = ElementTree.parse(output / "pages/270.svg").getroot()
            path = svg_root.find(".//{http://www.w3.org/2000/svg}path")
            expected_scale = 113.25 / 1000 * 345 / 1920
            assert path.attrib["transform"].startswith(
                f"matrix({qcf.number(expected_scale)} "
            )
            assert summary["counts"]["pages"] == 1
            assert summary["counts"]["rejected_pages"] == 1
            assert summary["counts"]["headers"] == 0
            assert summary["header_asset_summary_sha256"] == "summary"
            assert summary["header_asset_files_sha256"] == "files"
            assert summary["chapters_metadata_sha256"] == "chapters"
            assert summary["surah_names_sha256"] == "names"
            assert summary["schema_version"] == 5
            assert summary["waqf_source_glyphs_sha256"] == "waqf"
            assert summary["division_sajdah_source_sha256"] == "semantics"
            assert summary["header_qualified_geometry_pages_sha256"]
            assert summary["path_geometry"]["qualification"] == "base-order-preserved"
            assert summary["path_geometry"]["base_paths"] > 0
            assert (
                summary["path_geometry"]["emitted_paths"]
                == summary["path_geometry"]["base_paths"]
            )
            assert summary["path_geometry"]["restored_paths"] == 0
            for name in FakeDivisionSajdahSemantics.COUNT_FIELDS:
                assert summary["counts"][name] == 0
            assert not (root / "output.tmp").exists()
            try:
                with redirect_stdout(StringIO()):
                    qcf.build(args)
            except ValueError as error:
                assert "output path already exists" in str(error)
            else:
                raise AssertionError("overwrote an existing build")
        finally:
            qcf.PageFont = original_font
            qcf.HeaderAssets = original_headers
            qcf.SurahMetadata = original_metadata
            qcf.WaqfSourceGlyphs = original_waqf
            qcf.DivisionSajdahSemantics = original_semantics
            qcf.verify_sources = original_sources
            qcf.select_pages = original_pages


def test_cli_has_no_geometry_overrides():
    args = qcf.parser().parse_args(
        [
            "--fonts-dir",
            "/tmp/fonts",
            "--header-assets-dir",
            "/tmp/headers",
            "--chapters-metadata",
            "/tmp/chapters.json",
        ]
    )
    assert args.pages == "supported"
    assert not hasattr(args, "em_pixels")
    assert not hasattr(args, "page_width")


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
