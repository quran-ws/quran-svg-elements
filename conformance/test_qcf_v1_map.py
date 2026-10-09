#!/usr/bin/env python
"""Focused contracts for the QCF V1 source mapper."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_qcf_v1_map import (
    attach_boxes,
    attach_header_assets,
    complete_header_line_owners,
    line_content,
    load_page_number_source,
    load_qcf4_header_assets,
    normalize_box,
    observed_source_differences,
    parse_page,
    reconcile_words,
    verify_ayah_mark_positions,
    verify_source_differences,
)


def source_manifest() -> dict:
    return json.loads((ROOT / "conformance/qcf-v1-source.json").read_text())


def canonical(ayah: str, count: int) -> list[dict]:
    return [
        {
            "word_key": f"{ayah}:{position}",
            "ayah_key": ayah,
            "rasm_uthmani": f"word-{position}",
            "rasm_imlai": "",
            "qpc": "",
            "rasm": "",
            "search": "",
        }
        for position in range(1, count + 1)
    ]


def item(
    location: str, text: str, line: int = 3, page: int = 2, kind: str = "word"
) -> dict:
    position = int(location.rsplit(":", 1)[1])
    return {
        "kind": kind,
        "line": line,
        "page": page,
        "location": location,
        "source_word_id": position,
        "source_record_id": 1000 + position,
        "source_position": position,
        "text": text,
    }


def box(position: int, page: int = 2, line: int = 3) -> dict:
    source = [position, 10, position + 1, 20]
    return {
        "glyph_id": 2000 + position,
        "page": page,
        "line": line,
        "position": position,
        "source_box": source,
        "box": source,
    }


def mapped_item(location: str, text: str, line: int = 3, page: int = 2) -> dict:
    source = item(location, text, line=line, page=page)
    source["glyphs"] = [
        {
            "text": char,
            "codepoint": f"U+{ord(char):04X}",
            "qul_ayah_positions": [offset],
            "font_ayah_position": offset,
            "ayahinfo_position": offset,
            "glyph_id": 2000 + offset,
            "source_box": [offset, 10, offset + 1, 20],
            "box": [offset, 10, offset + 1, 20],
        }
        for offset, char in enumerate(text, 1)
    ]
    return source


def test_page_parser_keeps_line_roles_and_multi_glyph_words():
    page = parse_page(
        """<div id="page-2">
          <div class="line-container" data-line="1">
            <div class="line line--surah-name" id="line-1"></div>
          </div>
          <div class="line-container" data-line="2">
            <div class="line line--center line--bismillah" id="line-2"></div>
          </div>
          <div class="line-container" data-line="3">
            <div class="line" id="line-3">
              <span class="char char-word" data-word-id="10"
                    data-location="2:2:1" data-position="1" data-id="20">
                <a>ﭖﭗ</a>
              </span>
              <span class="char char-end" data-word-id="11"
                    data-location="2:2:2" data-position="2" data-id="21">
                <a>ﭘ</a>
              </span>
            </div>
          </div>
        </div>""",
        2,
    )
    assert page["page"] == 2
    assert [line["type"] for line in page["lines"]] == [
        "surah_name",
        "basmalah",
        "ayah",
    ]
    assert page["lines"][0]["is_centered"]
    assert page["lines"][1]["is_centered"]
    assert page["lines"][0]["surah"] == 2
    assert page["items"][0]["text"] == "ﭖﭗ"
    assert page["items"][0]["kind"] == "word"
    assert page["items"][1]["kind"] == "end"


def test_corpus_header_owners_complete_page_bottom_headings():
    pages = {}
    for surah in range(1, 115):
        heading = {
            "line": 1,
            "type": "surah_name",
            "is_centered": True,
            "surah": None if surah % 5 == 0 else surah,
        }
        lines = [heading]
        if surah >= 2 and surah != 9:
            lines.append(
                {
                    "line": 2,
                    "type": "basmalah",
                    "is_centered": True,
                    "surah": surah,
                }
            )
        pages[surah] = {"lines": lines}

    complete_header_line_owners(pages)

    headings = [
        line
        for page in pages.values()
        for line in page["lines"]
        if line["type"] == "surah_name"
    ]
    assert [line["surah"] for line in headings] == list(range(1, 115))

    pages[4]["lines"][0]["surah"] = 5
    try:
        complete_header_line_owners(pages)
    except ValueError as error:
        assert "heading order differs" in str(error)
    else:
        raise AssertionError("accepted a conflicting heading owner")


def qcf4_rows() -> list[str]:
    rows = ["Sura,Verse,PageNo,LineNo,FontFile,FontCode,Type"]
    for surah in range(1, 115):
        rows.append(f"{surah},0,{surah},1,0,{surah - 1},5")
        if surah >= 2 and surah != 9:
            rows.append(f"{surah},0,{surah},2,1,2013,4")
    return rows


def test_qcf4_header_assets_have_exact_semantic_ownership():
    with TemporaryDirectory() as directory:
        source = Path(directory) / "data.txt"
        source.write_text("\n".join(qcf4_rows()) + "\n")
        assets = load_qcf4_header_assets(source, source_manifest())

    assert assets["surah_name"][1]["codepoint"] == "U+FC45"
    assert assets["surah_name"][114]["codepoint"] == "U+FBEB"
    assert assets["surah_name"][4]["asset_path"] == "surah/004.svg"
    assert assets["surah_name"][4]["family"] == "qpc-v4-surah-header"
    assert assets["surah_name"][4]["qcf4_layout_font_code"] == 3
    assert assets["basmalah"][2]["codepoint"] == "U+F8DD"
    assert assets["basmalah"][2]["font_file_id"] == 1
    assert 1 not in assets["basmalah"] and 9 not in assets["basmalah"]


def test_v4_assets_join_v1_lines_without_importing_v4_placement():
    pages = {}
    for surah in range(1, 115):
        page = 604 if surah >= 112 else surah
        heading_line = 10 if surah == 114 else 1
        lines = [
            {
                "line": heading_line,
                "type": "surah_name",
                "is_centered": True,
                "surah": surah,
            }
        ]
        if surah >= 2 and surah != 9:
            lines.append(
                {
                    "line": heading_line + 1,
                    "type": "basmalah",
                    "is_centered": True,
                    "surah": surah,
                }
            )
        pages.setdefault(page, {"lines": []})["lines"].extend(lines)

    with TemporaryDirectory() as directory:
        source = Path(directory) / "data.txt"
        source.write_text("\n".join(qcf4_rows()) + "\n")
        attach_header_assets(pages, load_qcf4_header_assets(source, source_manifest()))

    surah_114 = next(
        line
        for line in pages[604]["lines"]
        if line["type"] == "surah_name" and line["surah"] == 114
    )
    assert surah_114["line"] == 10
    assert surah_114["asset"]["qcf4_source_page"] == 114
    assert surah_114["asset"]["qcf4_source_line"] == 1
    assert surah_114["asset"]["codepoint"] == "U+FBEB"
    assert surah_114["asset"]["qcf4_layout_font_code"] == 113


def test_qpc_old_owns_all_printed_page_numbers_and_boundaries():
    ayahs = [f"1:{page}" for page in range(1, 605)]
    pages = {
        page: {"items": [item(f"1:{page}:1", "A", page=page)]} for page in range(1, 605)
    }
    source = {"mushaf_pgs": list(range(1, 605)), "stops": ["1"] * 604}
    with TemporaryDirectory() as directory:
        path = Path(directory) / "qpc-old.json"
        path.write_text(json.dumps(source))
        page_numbers, stops = load_page_number_source(path, pages, ayahs)
        assert page_numbers[1] == {"dataset": "qpc-old", "first_ayah_id": 1}
        assert page_numbers[604] == {
            "dataset": "qpc-old",
            "first_ayah_id": 604,
        }
        assert stops == [[1]] * 604

        source["mushaf_pgs"][120:] = [value + 1 for value in source["mushaf_pgs"][120:]]
        path.write_text(json.dumps(source))
        try:
            load_page_number_source(path, pages, ayahs)
        except ValueError as error:
            assert "page 121 starts" in str(error)
        else:
            raise AssertionError("accepted a changed qpc-old page boundary")


def test_qpc_old_ayah_mark_positions_use_actual_marker_glyph_counts():
    def glyphs(count):
        return [{} for _ in range(count)]

    pages = {
        1: {
            "words": [
                {"ayah_key": "1:1", "glyphs": glyphs(2)},
                {"ayah_key": "1:2", "glyphs": glyphs(1)},
            ],
            "shared_groups": [],
            "ayah_markers": [
                {"ayah_key": "1:1", "glyphs": glyphs(1)},
                {"ayah_key": "1:2", "glyphs": glyphs(2)},
            ],
        },
        2: {
            "words": [],
            "shared_groups": [
                {"ayah_key": "2:1", "glyphs": glyphs(1)},
            ],
            "ayah_markers": [{"ayah_key": "2:1", "glyphs": glyphs(1)}],
        },
    }
    assert verify_ayah_mark_positions(pages, [[2, 5], [1]]) == 2
    try:
        verify_ayah_mark_positions(pages, [[2, 4], [1]])
    except ValueError as error:
        assert "ayah marker positions differ" in str(error)
    else:
        raise AssertionError("accepted stale qpc-old ayah marker positions")


def test_line_content_orders_words_shared_geometry_and_markers():
    content = line_content(
        [{"word_key": "13:37:10"}, {"word_key": "13:37:7"}],
        [
            {
                "id": "13:37:8-9",
                "canonical_word_keys": ["13:37:8", "13:37:9"],
            }
        ],
        [{"ayah_key": "13:37"}],
    )
    assert content == [
        {"kind": "word", "word_key": "13:37:7"},
        {
            "kind": "shared_group",
            "id": "13:37:8-9",
            "canonical_word_keys": ["13:37:8", "13:37:9"],
        },
        {"kind": "word", "word_key": "13:37:10"},
        {"kind": "ayah_mark", "ayah_key": "13:37"},
    ]
    assert line_content([{"word_key": "2:31:1"}], [], [{"ayah_key": "2:30"}]) == [
        {"kind": "ayah_mark", "ayah_key": "2:30"},
        {"kind": "word", "word_key": "2:31:1"},
    ]


def test_reversed_rtl_source_box_is_preserved_and_normalized():
    assert normalize_box([690, 465, 681, 490]) == [681, 465, 690, 490]
    assert normalize_box([681, 465, 681, 490]) == [681, 465, 681, 490]


def test_standard_ayah_joins_each_code_to_its_box():
    word = item("2:2:1", "ﭖﭗ")
    marker = item("2:2:2", "ﭘ", kind="end")
    pages = {2: {"items": [word, marker]}}
    boxes = {"2:2": [box(1), box(2), box(3)]}
    font = {"2:2": {"page": 2, "text": "ﭖﭗﭘ"}}

    by_ayah, shared = attach_boxes(pages, boxes, font, [], [])

    assert shared == []
    glyphs = by_ayah["2:2"][0]["glyphs"]
    assert [glyph["text"] for glyph in glyphs] == ["ﭖ", "ﭗ"]
    assert glyphs[1]["box"] == [2, 10, 3, 20]
    assert glyphs[1]["qul_ayah_positions"] == [2]
    assert glyphs[1]["font_ayah_position"] == 2
    assert by_ayah["2:2"][1]["glyphs"][0]["ayahinfo_position"] == 3


def test_font_stream_relabels_shifted_qul_codes_without_moving_boxes():
    word = item("13:38:1", "B", page=254, line=7)
    marker = item("13:38:2", "C", page=254, line=7, kind="end")
    pages = {254: {"items": [word, marker]}}
    boxes = {"13:38": [box(1, 254, 7), box(2, 254, 7)]}
    font = {"13:38": {"page": 254, "text": "AB"}}

    by_ayah, shared = attach_boxes(pages, boxes, font, ["13:38"], [])

    assert shared == []
    assert by_ayah["13:38"][0]["qul_text"] == "B"
    assert by_ayah["13:38"][0]["text"] == "A"
    assert by_ayah["13:38"][0]["glyphs"][0]["codepoint"] == "U+0041"
    assert by_ayah["13:38"][1]["qul_text"] == "C"
    assert by_ayah["13:38"][1]["text"] == "B"
    assert by_ayah["13:38"][1]["glyphs"][0]["box"] == [2, 10, 3, 20]


def test_two_logical_words_can_share_one_printed_glyph():
    first = item("13:37:1", "A", page=254, line=6)
    left = item("13:37:2", "B", page=254, line=6)
    right = item("13:37:3", "C", page=254, line=6)
    marker = item("13:37:4", "D", page=254, line=6, kind="end")
    pages = {254: {"items": [first, left, right, marker]}}
    boxes = {"13:37": [box(1, 254, 6), box(2, 254, 6), box(3, 254, 6)]}
    font = {"13:37": {"page": 254, "text": "AXD"}}
    plan = {
        "id": "13:37:2-3",
        "ayah": "13:37",
        "source_word_positions": [2, 3],
        "canonical_word_keys": ["13:37:2", "13:37:3"],
        "glyph_count": 1,
        "reason": "one printed glyph",
    }

    by_ayah, shared = attach_boxes(pages, boxes, font, ["13:37"], [plan])

    assert by_ayah["13:37"][0]["text"] == "A"
    assert by_ayah["13:37"][1]["glyphs"] == []
    assert by_ayah["13:37"][2]["glyphs"] == []
    assert by_ayah["13:37"][3]["text"] == "D"
    assert shared[0]["canonical_word_keys"] == ["13:37:2", "13:37:3"]
    assert shared[0]["qul_text"] == "BC"
    assert shared[0]["source_text"] == "X"
    assert shared[0]["glyphs"][0]["qul_ayah_positions"] == [2, 3]
    assert shared[0]["glyphs"][0]["font_ayah_position"] == 2
    assert shared[0]["glyphs"][0]["box"] == [2, 10, 3, 20]


def test_equal_boundaries_keep_multi_glyph_word_whole():
    mapped, adjustment = reconcile_words(
        "2:2",
        [mapped_item("2:2:1", "ﭖﭗ"), mapped_item("2:2:2", "ﭘ")],
        canonical("2:2", 2),
        {"splits": {}, "fuses": {}},
    )
    assert adjustment is None
    assert mapped[0]["word_key"] == "2:2:1"
    assert mapped[0]["source_text"] == "ﭖﭗ"
    assert len(mapped[0]["glyphs"]) == 2


def test_canonical_split_uses_two_source_glyphs():
    mapped, adjustment = reconcile_words(
        "37:130",
        [
            mapped_item("37:130:1", "ﭟ", page=451),
            mapped_item("37:130:2", "ﭠ", page=451),
            mapped_item("37:130:3", "ﭡﭢ", page=451),
        ],
        canonical("37:130", 4),
        {"splits": {"37:130": [3, 451]}, "fuses": {}},
    )
    assert adjustment == {
        "ayah": "37:130",
        "kind": "split",
        "source_positions": [3],
        "canonical_positions": [3, 4],
    }
    assert [word["source_text"] for word in mapped] == ["ﭟ", "ﭠ", "ﭡ", "ﭢ"]
    assert mapped[2]["source_locations"] == ["37:130:3"]
    assert mapped[3]["source_locations"] == ["37:130:3"]
    assert mapped[2]["source_glyph_part"] == 0
    assert mapped[3]["source_glyph_part"] == 1


def test_canonical_fuse_joins_two_source_words():
    source_words = [
        mapped_item(f"15:7:{position}", chr(0xFB83 + position), page=262)
        for position in range(1, 9)
    ]
    mapped, adjustment = reconcile_words(
        "15:7",
        source_words,
        canonical("15:7", 7),
        {"splits": {}, "fuses": {"15:7": [1, 2]}},
    )
    assert adjustment == {
        "ayah": "15:7",
        "kind": "fuse",
        "source_positions": [1, 2],
        "canonical_positions": [1],
    }
    assert mapped[0]["source_locations"] == ["15:7:1", "15:7:2"]
    assert mapped[0]["source_text"] == source_words[0]["text"] + source_words[1]["text"]
    assert mapped[1]["source_locations"] == ["15:7:3"]


def test_only_exact_manifested_source_differences_are_accepted():
    items = {
        "2:79": [
            item(f"2:79:{position}", char, page=12)
            for position, char in enumerate("ABC", 1)
        ],
        "69:8": [
            item(f"69:8:{position}", char, page=566)
            for position, char in enumerate("XY", 1)
        ],
        "83:35": [
            item(f"83:35:{position}", char, page=589)
            for position, char in enumerate("MN", 1)
        ],
    }
    font = {
        "2:79": {"page": 12, "text": "ABBC"},
        "69:8": {"page": 566, "text": "XYZ"},
        "83:35": {"page": 588, "text": "MN"},
    }
    observed = observed_source_differences(font, items)
    accepted = [record | {"decision": "reviewed"} for record in observed]

    verify_source_differences(observed, {"accepted_source_differences": accepted})
    try:
        verify_source_differences(
            observed[:-1], {"accepted_source_differences": accepted}
        )
    except ValueError as error:
        assert "source differences changed" in str(error)
    else:
        raise AssertionError("an unreviewed source-difference change was accepted")


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
