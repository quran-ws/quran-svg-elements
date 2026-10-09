#!/usr/bin/env python
"""Contracts for lossless QCF V1 waqf source-glyph ownership."""

import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_qcf_v1_svg as qcf
import build_qcf_v1_waqf_source as waqf_builder


class FakeFont:
    units_per_em = 1000

    def outline(self, codepoint):
        assert codepoint in {0xFB51, 0xFB52}
        return "M0 0L100 0L100 200Z", (0, 0, 100, 200)


def record(
    key: str,
    mark: str,
    text_codepoint: str,
    source_codepoint: str,
    glyph_index: int,
    glyph_count: int,
    semantic_glyph_indices: list[int] | None = None,
) -> dict:
    value = {
        "page": 3,
        "word_key": key,
        "text_codepoint": text_codepoint,
        "mark": mark,
        "source_codepoint": source_codepoint,
        "source_glyph_index": glyph_index,
        "source_glyph_count": glyph_count,
    }
    if semantic_glyph_indices:
        value["source_semantic_glyph_indices"] = semantic_glyph_indices
    return value


def ledger_value() -> dict:
    separate = [
        record(
            "2:1:1",
            "waqf_jaiz_wasl_awla",
            "U+06D6",
            "U+FB52",
            1,
            2,
        )
    ]
    fused = [
        record(
            "2:1:2",
            "waqf_jaiz_mustawi_al_tarafayn",
            "U+06DA",
            "U+FB51",
            0,
            1,
        )
    ]
    return {
        "schema": "quran-svg-elements/qcf-v1-waqf-source-glyphs",
        "schema_version": 2,
        "edition": "hafs-qcf-v1",
        "source": {
            "map": "fixture",
            "map_page_files_sha256": "1" * 64,
            "page_font_tree_sha256": "2" * 64,
            "division_sajdah_source_sha256": "4" * 64,
            "analysis_records_sha256": "3" * 64,
        },
        "text_marks": {
            "U+06D6": "waqf_jaiz_wasl_awla",
            "U+06D7": "waqf_jaiz_waqf_awla",
            "U+06D8": "waqf_lazim",
            "U+06DA": "waqf_jaiz_mustawi_al_tarafayn",
            "U+06DB": "waqf_al_muanaqah",
        },
        "counts": {
            "text_signs": 2,
            "separate_source_glyphs": 1,
            "fused_source_glyphs": 1,
            "text_signs_by_mark": {
                "waqf_jaiz_mustawi_al_tarafayn": 1,
                "waqf_jaiz_wasl_awla": 1,
            },
            "separate_source_glyphs_by_mark": {"waqf_jaiz_wasl_awla": 1},
            "fused_source_glyphs_by_mark": {"waqf_jaiz_mustawi_al_tarafayn": 1},
        },
        "separate": separate,
        "fused": fused,
    }


def manifest(path: Path, value: dict) -> dict:
    path.write_text(json.dumps(value, sort_keys=True))
    return {
        "edition": "hafs-qcf-v1",
        "inputs": {
            "page_font_tree_sha256": "2" * 64,
            "division_sajdah_source_sha256": "4" * 64,
            "waqf_source_glyphs_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
        "waqf": {
            "source": "canonical rasm sign plus pinned semantic-aware source-glyph ownership",
            "qualification": "source-glyph-qualified",
            "path_kind": "mark",
            "mark_family": "waqf",
            "text_signs": value["counts"]["text_signs"],
            "separate_source_glyphs": value["counts"]["separate_source_glyphs"],
            "fused_source_glyphs": value["counts"]["fused_source_glyphs"],
        },
    }


def page() -> dict:
    return {
        "page": 3,
        "words": [
            {
                "word_key": "2:1:1",
                "text": {"rasm_uthmani": "كَلِمَةۖ"},
                "glyphs": [
                    {"codepoint": "U+FB51", "box": [0, 0, 100, 200]},
                    {"codepoint": "U+FB52", "box": [100, 0, 120, 20]},
                ],
            },
            {
                "word_key": "2:1:2",
                "text": {"rasm_uthmani": "فِيۚ"},
                "glyphs": [{"codepoint": "U+FB51", "box": [120, 0, 220, 200]}],
            },
            {
                "word_key": "2:1:3",
                "text": {"rasm_uthmani": "هُدًى"},
                "glyphs": [{"codepoint": "U+FB51", "box": [220, 0, 320, 200]}],
            },
        ],
        "shared_groups": [],
    }


def fixture(root: Path) -> tuple[qcf.WaqfSourceGlyphs, Path, dict]:
    path = root / "waqf.json"
    value = ledger_value()
    source = manifest(path, value)
    return qcf.WaqfSourceGlyphs(path, source), path, source


def test_committed_ledger_is_strict_and_complete():
    source = json.loads((ROOT / "conformance/qcf-v1-vector-source.json").read_text())
    ledger = qcf.WaqfSourceGlyphs(
        ROOT / "conformance/qcf-v1-waqf-source-glyphs.json", source
    )
    assert ledger.expected_counts["text_signs"] == 4272
    assert ledger.expected_counts["separate_source_glyphs"] == 4221
    assert ledger.expected_counts["fused_source_glyphs"] == 51
    page_339 = ledger.by_page[339]["22:60:1"]
    assert page_339["status"] == "fused"
    assert page_339["source_glyph_count"] == 2
    assert page_339["source_semantic_glyph_indices"] == [0]
    assert sum(len(records) for records in ledger.by_page.values()) == 4272


def test_committed_semantic_exceptions_match_the_semantic_ledger():
    waqf = json.loads((ROOT / "conformance/qcf-v1-waqf-source-glyphs.json").read_text())
    semantics = json.loads(
        (ROOT / "conformance/qcf-v1-division-sajdah-source.json").read_text()
    )
    waqf_records = {
        (record["page"], record["word_key"]): record
        for status in ("separate", "fused")
        for record in waqf[status]
    }
    expected = {}
    for record in (*semantics["divisions"], *semantics["sajdahs"]):
        source = record["source_glyph"]
        key = (record["page"], record["word_key"])
        if key in waqf_records and source is not None and source["index"] is not None:
            expected.setdefault(key, []).append(source["index"])
    actual = {
        key: record["source_semantic_glyph_indices"]
        for key, record in waqf_records.items()
        if "source_semantic_glyph_indices" in record
    }
    assert actual == {key: sorted(indices) for key, indices in expected.items()}
    assert actual == {(339, "22:60:1"): [0]}


def test_only_independent_final_source_glyph_is_typed():
    with TemporaryDirectory() as directory:
        ledger, _, _ = fixture(Path(directory))
        paths, counts = ledger.classify_page(page())
        assert paths == {("2:1:1", 1): "waqf_jaiz_wasl_awla"}
        assert ledger.summary(counts) == {
            "qualification": "source-glyph-qualified",
            "text_signs": 2,
            "separate_source_glyphs": 1,
            "fused_source_glyphs": 1,
            "text_signs_by_mark": {
                "waqf_jaiz_mustawi_al_tarafayn": 1,
                "waqf_jaiz_wasl_awla": 1,
            },
            "separate_source_glyphs_by_mark": {"waqf_jaiz_wasl_awla": 1},
            "fused_source_glyphs_by_mark": {"waqf_jaiz_mustawi_al_tarafayn": 1},
        }


def test_typed_path_changes_metadata_not_geometry():
    glyph = {"codepoint": "U+FB52", "box": [100, 0, 120, 20]}
    ordinary = qcf.path_element(glyph, FakeFont(), 121, 1)
    typed = qcf.path_element(glyph, FakeFont(), 121, 1, "waqf_jaiz_wasl_awla")
    element = ElementTree.fromstring(typed)
    assert element.attrib["data-kind"] == "mark"
    assert element.attrib["data-mark"] == "waqf_jaiz_wasl_awla"
    assert element.attrib["data-mark-family"] == "waqf"
    assert element.attrib["d"] == "M0 0L100 0L100 200Z"
    assert qcf.qualified_geometry_svg(typed.encode()) == ordinary.encode()


def test_ledger_and_mapped_source_drift_fail_closed():
    with TemporaryDirectory() as directory:
        ledger, path, source = fixture(Path(directory))
        changed = page()
        changed["words"][0]["glyphs"][1]["codepoint"] = "U+FB51"
        try:
            ledger.classify_page(changed)
        except ValueError as error:
            assert "source glyph differs" in str(error)
        else:
            raise AssertionError("accepted a different source glyph")

        path.write_text(path.read_text() + "\n")
        try:
            qcf.WaqfSourceGlyphs(path, source)
        except ValueError as error:
            assert "ledger digest differs" in str(error)
        else:
            raise AssertionError("accepted a changed ownership ledger")


def test_unlisted_or_shared_sign_fails_closed():
    with TemporaryDirectory() as directory:
        ledger, _, _ = fixture(Path(directory))
        changed = page()
        changed["words"][2]["text"]["rasm_uthmani"] += "ۗ"
        try:
            ledger.classify_page(changed)
        except ValueError as error:
            assert "missing or ambiguous" in str(error)
        else:
            raise AssertionError("accepted an unlisted waqf sign")

        changed = page()
        changed["shared_groups"] = [
            {
                "canonical_words": [
                    {
                        "word_key": "2:1:4",
                        "text": {"rasm_uthmani": "مَاۗ"},
                    }
                ]
            }
        ]
        try:
            ledger.classify_page(changed)
        except ValueError as error:
            assert "shared word" in str(error)
        else:
            raise AssertionError("accepted unresolved shared waqf ownership")


def test_evidence_builder_derives_records_and_ledger_without_guessing():
    (
        records,
        direct_words,
        direct_source_glyphs,
        shared_groups,
        shared_canonical_words,
        shared_source_glyphs,
    ) = waqf_builder.page_records(page(), FakeFont(), {})
    assert direct_words == 3
    assert direct_source_glyphs == 4
    assert shared_groups == 0
    assert shared_canonical_words == 0
    assert shared_source_glyphs == 0
    assert [
        (record["word_key"], record["glyph_index"], record["glyph_count"])
        for record in records
    ] == [
        ("2:1:1", 1, 2),
        ("2:1:2", 0, 1),
    ]
    assert all("semantic_glyph_indices" not in record for record in records)
    assert records[0]["mark"] == "waqf_jaiz_wasl_awla"
    assert records[0]["source_codepoint"] == "U+FB52"
    assert (
        records[0]["outline_sha256"]
        == hashlib.sha256(b"M0 0L100 0L100 200Z").hexdigest()
    )
    assert records[0]["preceding_box_max_height"] == 200
    assert records[0]["preceding_box_max_width"] == 100
    assert records[1]["preceding_box_max_height"] is None

    evidence = waqf_builder.ledger("1" * 64, "2" * 64, "4" * 64, records)
    assert evidence["counts"] == ledger_value()["counts"]
    assert evidence["separate"] == ledger_value()["separate"]
    assert evidence["fused"] == ledger_value()["fused"]
    expected_digest = hashlib.sha256()
    for record_value in records:
        expected_digest.update(
            (json.dumps(record_value, sort_keys=True) + "\n").encode()
        )
    assert waqf_builder.records_digest(records) == expected_digest.hexdigest()
    assert evidence["source"]["analysis_records_sha256"] == expected_digest.hexdigest()


def test_semantic_prefix_does_not_make_fused_body_a_separate_mark():
    (
        records,
        direct_words,
        direct_source_glyphs,
        shared_groups,
        shared_canonical_words,
        shared_source_glyphs,
    ) = waqf_builder.page_records(page(), FakeFont(), {"2:1:1": {0}})
    assert (direct_words, direct_source_glyphs) == (3, 4)
    assert (shared_groups, shared_canonical_words, shared_source_glyphs) == (0, 0, 0)
    assert records[0]["semantic_glyph_indices"] == [0]
    evidence = waqf_builder.ledger("1" * 64, "2" * 64, "4" * 64, records)
    assert not evidence["separate"]
    assert [record["word_key"] for record in evidence["fused"]] == [
        "2:1:1",
        "2:1:2",
    ]
    assert evidence["fused"][0]["source_glyph_count"] == 2
    assert evidence["fused"][0]["source_semantic_glyph_indices"] == [0]


def test_runtime_accepts_semantic_prefix_fused_ownership():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        value = ledger_value()
        moved = value["separate"].pop()
        moved["source_semantic_glyph_indices"] = [0]
        value["fused"].insert(0, moved)
        value["counts"]["separate_source_glyphs"] = 0
        value["counts"]["fused_source_glyphs"] = 2
        value["counts"]["separate_source_glyphs_by_mark"] = {}
        value["counts"]["fused_source_glyphs_by_mark"] = {
            "waqf_jaiz_mustawi_al_tarafayn": 1,
            "waqf_jaiz_wasl_awla": 1,
        }
        path = root / "waqf.json"
        source = manifest(path, value)
        ledger = qcf.WaqfSourceGlyphs(path, source)
        paths, counts = ledger.classify_page(page())
        assert paths == {}
        assert ledger.summary(counts)["fused_source_glyphs"] == 2


def test_semantic_and_waqf_source_ownership_cannot_conflict():
    try:
        waqf_builder.page_records(page(), FakeFont(), {"2:1:1": {1}})
    except ValueError as error:
        assert "source ownership conflicts" in str(error)
    else:
        raise AssertionError(
            "accepted one source glyph for semantic and waqf ownership"
        )


def test_evidence_builder_requires_one_final_canonical_sign():
    changed = page()
    changed["words"][0]["text"]["rasm_uthmani"] = "كۖلِمَة"
    try:
        waqf_builder.page_records(changed, FakeFont(), {})
    except ValueError as error:
        assert "not unique and final" in str(error)
    else:
        raise AssertionError("accepted a non-final canonical waqf sign")

    changed = page()
    changed["words"][0]["text"]["rasm_uthmani"] += "ۗ"
    try:
        waqf_builder.page_records(changed, FakeFont(), {})
    except ValueError as error:
        assert "not unique and final" in str(error)
    else:
        raise AssertionError("accepted two canonical waqf signs")


def test_record_shape_and_counts_are_exact():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for number, (mutate, message) in enumerate(
            (
                (
                    lambda value: value["separate"][0].update(source_glyph_index=0),
                    "invalid waqf separate ownership",
                ),
                (
                    lambda value: value["separate"][0].update(
                        source_semantic_glyph_indices=[1]
                    ),
                    "invalid waqf separate ownership",
                ),
                (
                    lambda value: value["source"].update(
                        division_sajdah_source_sha256="5" * 64
                    ),
                    "source evidence differs",
                ),
                (
                    lambda value: value["counts"].update(text_signs=3),
                    "counts differ",
                ),
                (
                    lambda value: value["text_marks"].update({"U+06D6": "wrong"}),
                    "mapping differs",
                ),
            )
        ):
            value = ledger_value()
            mutate(value)
            path = root / f"{number}.json"
            source = manifest(path, value)
            try:
                qcf.WaqfSourceGlyphs(path, source)
            except ValueError as error:
                assert message in str(error)
            else:
                raise AssertionError(f"accepted invalid ledger: {message}")


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
